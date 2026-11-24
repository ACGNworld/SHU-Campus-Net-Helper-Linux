import os
import queue
import sys
import threading
import time
import tkinter as tk
import traceback
from datetime import datetime
from tkinter import messagebox, scrolledtext, simpledialog

from shu_network import (
    CHECK_INTERVAL,
    CONFIRM_INTERVAL,
    DEFAULT_LOGIN_URL,
    EMAIL_CONFIG,
    LOGIN_CONFIG,
    ConfigStore,
    JobError,
    ReconnectSchedule,
    capture_login,
    internet_available,
    login,
    portal_available,
    send_ip_report,
)


class NetworkAutoLoginApp:
    def __init__(self, root):
        self.root = root
        root.title("SHU 校园网助手 v0.3.1")
        root.geometry("520x460")
        root.minsize(460, 400)
        root.protocol("WM_DELETE_WINDOW", self.hide_window)
        root.report_callback_exception = self.report_callback_exception

        self.events = queue.Queue()
        self.stop = threading.Event()
        self.reconnect = ReconnectSchedule()
        self.config = ConfigStore()
        self.busy = False
        self.mail_busy = False
        self.monitor_timer = None
        self.tray = None
        self.user_opened_window = False
        self.status = tk.StringVar(value="等待检测")
        self.last_check = tk.StringVar(value="--:--:--")

        self.create_widgets()
        self.login_config = self.load_config(LOGIN_CONFIG)
        self.email_config = self.load_config(EMAIL_CONFIG)
        if self.login_config is None:
            self.log("请先录制校园网登录配置。")

        self.root.after(50, self.drain_events)
        threading.Thread(target=self.run_tray, daemon=True).start()
        self.schedule_monitor(0)

    def create_widgets(self):
        tk.Label(self.root, text="SHU 校园网助手", font=("微软雅黑", 16, "bold")).pack(pady=(15, 6))

        info = tk.Frame(self.root)
        info.pack(fill="x", padx=20)
        tk.Label(info, textvariable=self.status, font=("微软雅黑", 11)).pack(side="left")
        tk.Label(info, textvariable=self.last_check).pack(side="right")
        tk.Label(info, text="上次检测").pack(side="right", padx=6)

        controls = tk.Frame(self.root)
        controls.pack(pady=12)
        self.capture_button = tk.Button(controls, text="录制登录配置", command=self.start_capture)
        self.capture_button.pack(side="left", padx=4)
        tk.Button(controls, text="配置汇报邮箱", command=self.configure_email).pack(side="left", padx=4)
        self.test_button = tk.Button(controls, text="测试连接并发信", command=self.test_connection)
        self.test_button.pack(side="left", padx=4)
        self.hide_button = tk.Button(controls, text="隐藏到托盘", command=self.hide_window, state="disabled")
        self.hide_button.pack(side="left", padx=4)

        self.log_text = scrolledtext.ScrolledText(self.root, state="disabled", font=("Consolas", 10))
        self.log_text.pack(fill="both", expand=True, padx=20, pady=(0, 15))

    def load_config(self, name):
        try:
            return self.config.load(name)
        except (OSError, ValueError) as error:
            self.log(f"读取 {name} 失败，需重新配置（{error}）")
            return None

    def save_config(self, name, config):
        try:
            self.config.save(name, config)
        except OSError as error:
            messagebox.showerror("保存失败", str(error), parent=self.root)
            return False
        return True

    def post(self, callback, *args):
        self.events.put((callback, args))

    def drain_events(self):
        try:
            for _ in range(100):
                try:
                    callback, args = self.events.get_nowait()
                except queue.Empty:
                    break
                callback(*args)
                if self.stop.is_set() and not self.busy:
                    return
        finally:
            if not self.stop.is_set() or self.busy:
                self.root.after(50, self.drain_events)

    def log(self, message):
        self.post(self.append_log, message)

    def append_log(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"[{datetime.now():%H:%M:%S}] {message}\n")
        lines = int(self.log_text.index("end-1c").split(".")[0])
        if lines > 501:
            self.log_text.delete("1.0", f"{lines - 500}.0")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def report_callback_exception(self, error_type, error, trace):
        self.log("界面操作失败\n" + "".join(traceback.format_exception(error_type, error, trace)))

    def start_job(self, task, on_done, *args):
        if self.busy or self.stop.is_set():
            return
        self.busy = True
        if self.monitor_timer is not None:
            self.root.after_cancel(self.monitor_timer)
            self.monitor_timer = None

        def work():
            result = None
            try:
                result = task(*args)
            except JobError as error:
                self.log(str(error))
            except Exception as error:
                self.log(f"操作失败（{type(error).__name__}）")
            finally:
                self.post(self.finish_job, on_done, result)

        try:
            threading.Thread(target=work, daemon=True).start()
        except RuntimeError:
            self.finish_job(None, None)
            raise

    def finish_job(self, on_done, result):
        delay = CHECK_INTERVAL
        try:
            if not self.stop.is_set():
                next_delay = on_done(result) if on_done is not None else result
                if next_delay is not None:
                    delay = next_delay
        finally:
            self.busy = False
            if self.stop.is_set():
                self.root.destroy()
            else:
                self.capture_button.config(state="normal")
                self.test_button.config(state="normal")
                self.schedule_monitor(delay)

    def schedule_monitor(self, delay):
        self.monitor_timer = self.root.after(int(delay * 1000), self.monitor_tick)

    def monitor_tick(self):
        self.monitor_timer = None
        self.start_job(self.check_connection, None, self.login_config, False)

    def set_network_status(self, status):
        self.post(self.status.set, status)

    def probe(self):
        online = internet_available()
        self.post(self.last_check.set, datetime.now().strftime("%H:%M:%S"))
        return online

    def check_connection(self, config, manual):
        if self.probe():
            self.reconnect.reset()
            self.set_network_status("在线")
            if manual and not self.stop.is_set():
                self.log("外网已连通。")
                self.post(self.queue_email, True)
            return CHECK_INTERVAL

        if config is None:
            self.set_network_status("外网不可达 · 待录制配置")
            if manual:
                self.log("外网不可达，请先录制校园网登录配置。")
            return CHECK_INTERVAL

        if not manual and not self.reconnect.ready(time.monotonic()):
            if self.reconnect.probe_failures == 1:
                self.set_network_status("外网探测失败 · 正在复查")
                return CONFIRM_INTERVAL
            self.set_network_status("外网不可达 · 等待重试")
            return CHECK_INTERVAL

        if self.stop.is_set():
            return CHECK_INTERVAL
        try:
            if not portal_available(config["url"]):
                raise JobError("认证页不可达，请检查校园网网线或 Wi-Fi")
            self.set_network_status("正在认证…")
            self.log("开始校园网认证。")
            if login(config, self.stop, self.log, headless=not manual):
                self.reconnect.reset()
                self.set_network_status("在线")
                self.post(self.last_check.set, datetime.now().strftime("%H:%M:%S"))
                self.log("校园网认证完成，外网已恢复。")
                self.post(self.queue_email, manual)
                return CHECK_INTERVAL
        except Exception as error:
            self.reconnect.defer(time.monotonic())
            reason = str(error) if isinstance(error, JobError) else f"浏览器操作失败（{type(error).__name__}）"
            self.set_network_status("外网不可达 · 等待重试")
            self.log(reason)
        return CHECK_INTERVAL

    def start_capture(self):
        if self.busy:
            self.log("正在执行其他任务，请稍后录制。")
            return
        self.capture_button.config(state="disabled")
        self.test_button.config(state="disabled")
        self.log("请在浏览器内按提示点击账号框、密码框和登录按钮。")
        self.start_job(capture_login, self.save_login, self.stop, self.log)

    def save_login(self, paths):
        if not paths:
            self.log("录制结束，配置未更新。")
            return
        previous_user = self.login_config["user"] if self.login_config else ""
        user = simpledialog.askstring("登录配置", "校园网账号", initialvalue=previous_user, parent=self.root)
        if not user or not user.strip():
            return
        password = simpledialog.askstring("登录配置", "校园网密码", show="*", parent=self.root)
        if not password:
            return
        config = {
            "url": DEFAULT_LOGIN_URL,
            "u_xp": paths[0], "p_xp": paths[1], "b_xp": paths[2],
            "user": user.strip(), "pwd": password,
        }
        if self.save_config(LOGIN_CONFIG, config):
            self.login_config = config
            self.reconnect.reset()
            self.log("登录配置已保存。")
            return 0

    def test_connection(self):
        if self.busy:
            self.log("正在执行其他任务，请稍后测试。")
            return
        self.capture_button.config(state="disabled")
        self.test_button.config(state="disabled")
        self.log("正在测试外网连接。")
        self.start_job(self.check_connection, None, self.login_config, True)

    def configure_email(self):
        current = self.email_config or {}
        config = {}
        fields = (
            ("smtp", "SMTP 服务器（SSL 465 或 STARTTLS 587）", "smtp.qq.com"),
            ("sender", "发件人邮箱", ""),
            ("pwd", "邮箱 SMTP 授权码", ""),
            ("target", "接收 IP 报告的邮箱", ""),
        )
        for key, prompt, default in fields:
            if key == "target":
                default = config["sender"]
            options = {"show": "*"} if key == "pwd" else {}
            value = simpledialog.askstring(
                "邮箱配置", prompt, initialvalue=current.get(key, default), parent=self.root, **options
            )
            if value is None or not value.strip() or self.stop.is_set():
                return
            config[key] = value.strip()
        if self.save_config(EMAIL_CONFIG, config):
            self.email_config = config
            self.log("邮箱配置已保存，可点击“测试连接并发信”。")

    def queue_email(self, manual):
        if self.stop.is_set():
            return
        if not self.email_config:
            if manual:
                self.log("尚未配置汇报邮箱。")
            return
        if self.mail_busy:
            self.log("上一封 IP 报告正在发送。")
            return
        self.mail_busy = True
        config = self.email_config
        self.log("正在发送 IP 报告。")

        def work():
            try:
                send_ip_report(config)
                self.log("IP 报告已发送。")
            except JobError as error:
                self.log(str(error))
            except Exception as error:
                self.log(f"邮件发送失败（{type(error).__name__}）")
            finally:
                self.post(self.finish_email)

        try:
            threading.Thread(target=work, daemon=True).start()
        except RuntimeError:
            self.finish_email()
            raise

    def finish_email(self):
        self.mail_busy = False

    def run_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw

            # AppIndicator opens the menu on click and has no default action.
            if os.name != "nt" and not (
                pystray.Icon.HAS_MENU and self.linux_tray_available(
                    appindicator=not pystray.Icon.HAS_DEFAULT_ACTION
                )
            ):
                self.log("当前桌面没有可用的系统托盘，窗口保持可见。")
                return
            image = Image.new("RGB", (64, 64), (0, 150, 136))
            ImageDraw.Draw(image).rectangle((16, 16, 48, 48), fill="white")
            icon = pystray.Icon(
                "shu_helper", image, "SHU 校园网助手",
                menu=pystray.Menu(
                    pystray.MenuItem("显示主界面", lambda *_: self.post(self.show_window), default=True),
                    pystray.MenuItem("退出", lambda *_: self.post(self.quit)),
                ),
            )

            def setup(ready_icon):
                if self.stop.is_set():
                    ready_icon.stop()
                    return
                try:
                    ready_icon.visible = True
                except Exception:
                    self.log("托盘图标不可用，窗口保持可见。")
                    ready_icon.stop()
                else:
                    if self.stop.is_set():
                        ready_icon.stop()
                    else:
                        self.post(self.tray_ready, ready_icon)

            icon.run(setup=setup)
        except Exception:
            self.log("托盘启动失败，窗口保持可见。")
        finally:
            self.post(self.tray_closed)

    @staticmethod
    def linux_tray_available(appindicator):
        if appindicator and os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
            from gi.repository import Gio, GLib

            try:
                bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
                name = "org.kde.StatusNotifierWatcher"
                reply = bus.call_sync(
                    name, "/StatusNotifierWatcher", "org.freedesktop.DBus.Properties", "Get",
                    GLib.Variant("(ss)", (name, "IsStatusNotifierHostRegistered")),
                    None, Gio.DBusCallFlags.NO_AUTO_START, 1000, None,
                )
                if reply.unpack() == (True,):
                    return True
            except GLib.Error:
                pass

        if os.environ.get("DISPLAY"):
            from Xlib import X, display, error

            try:
                connection = display.Display()
                try:
                    selection = connection.intern_atom(f"_NET_SYSTEM_TRAY_S{connection.get_default_screen()}")
                    return connection.get_selection_owner(selection) != X.NONE
                finally:
                    connection.close()
            except error.DisplayError:
                pass
        return False

    def tray_ready(self, icon):
        if self.stop.is_set():
            icon.stop()
            return
        self.tray = icon
        self.hide_button.config(state="normal")
        if self.login_config and not self.user_opened_window:
            self.root.withdraw()

    def tray_closed(self):
        self.tray = None
        if not self.stop.is_set():
            self.hide_button.config(state="disabled")
            self.root.deiconify()

    def show_window(self):
        self.user_opened_window = True
        self.root.deiconify()
        self.root.lift()

    def hide_window(self):
        if self.tray is not None:
            self.root.withdraw()
        else:
            self.quit()

    def quit(self):
        if self.stop.is_set():
            return
        self.stop.set()
        self.status.set("正在退出…")
        if self.monitor_timer is not None:
            self.root.after_cancel(self.monitor_timer)
            self.monitor_timer = None
        if self.tray is not None:
            self.tray.stop()
        if not self.busy:
            self.root.destroy()


if __name__ == "__main__":
    try:
        window = tk.Tk()
    except tk.TclError as error:
        sys.exit(f"无法启动图形界面，请在桌面会话中运行（{error}）")
    NetworkAutoLoginApp(window)
    window.mainloop()

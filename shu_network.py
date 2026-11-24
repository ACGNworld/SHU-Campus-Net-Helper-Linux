"""Connectivity, campus login and IP reports for SHU Campus Net Helper."""

import json
import locale
import os
import re
import shutil
import smtplib
import socket
import ssl
import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack, contextmanager
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

import requests
from urllib3.exceptions import HTTPError


DEFAULT_LOGIN_URL = "http://10.10.9.9"
CHECK_INTERVAL = 30
CONFIRM_INTERVAL = 5
NETWORK_TIMEOUT = 3
PROBES = (
    ("http://connect.rom.miui.com/generate_204", 204, None),
    ("http://www.msftconnecttest.com/connecttest.txt", 200, b"Microsoft Connect Test"),
)

LOGIN_CONFIG = "login_config.json"
EMAIL_CONFIG = "email_config.json"
CONFIG_FIELDS = {
    LOGIN_CONFIG: ("url", "u_xp", "p_xp", "b_xp", "user", "pwd"),
    EMAIL_CONFIG: ("smtp", "sender", "pwd", "target"),
}


class JobError(Exception):
    """A task failure with a message suitable for the UI."""


class ConfigStore:
    def __init__(self):
        app_dir = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
        if os.name == "nt":
            config_home = Path(os.environ.get("LOCALAPPDATA") or Path.home())
        else:
            config_home = Path(os.environ.get("XDG_CONFIG_HOME", ""))
            if not config_home.is_absolute():
                config_home = Path.home() / ".config"
        self.directory = config_home / "SHU-Campus-Net-Helper"
        self.legacy_directories = (app_dir, app_dir / "output_exe", Path.cwd())

    def load(self, name):
        for directory in (self.directory, *self.legacy_directories):
            path = directory / name
            try:
                with path.open(encoding="utf-8-sig") as file:
                    config = json.load(file)
            except FileNotFoundError:
                continue

            if not isinstance(config, dict) or any(
                not isinstance(config.get(key), str) or not config[key].strip() for key in CONFIG_FIELDS[name]
            ):
                raise ValueError(f"{path} 缺少必要字段")
            if directory != self.directory:
                self.save(name, config)
            return config
        return None

    def save(self, name, config):
        self.directory.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.directory, delete=False
            ) as file:
                temp_path = Path(file.name)
                json.dump(config, file, ensure_ascii=False, indent=2)
                file.write("\n")
            temp_path.replace(self.directory / name)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)


class ReconnectSchedule:
    def __init__(self):
        self.reset()

    def reset(self):
        self.probe_failures = 0
        self.next_attempt = 0
        self.retry_delay = 30

    def ready(self, now):
        self.probe_failures += 1
        return self.probe_failures >= 2 and now >= self.next_attempt

    def defer(self, now):
        self.next_attempt = now + self.retry_delay
        self.retry_delay = min(self.retry_delay * 2, 300)


@contextmanager
def direct_get(url):
    # Test the network path used by the campus connection itself.
    with requests.Session() as session:
        session.trust_env = False
        with session.get(
            url, timeout=NETWORK_TIMEOUT, allow_redirects=False, stream=True,
            headers={"Accept-Encoding": "identity"},
        ) as response:
            yield response


def internet_available():
    for url, status, body in PROBES:
        try:
            with direct_get(url) as response:
                if response.status_code != status:
                    continue
                if body is None or response.raw.read(len(body) + 1).strip() == body:
                    return True
        except (HTTPError, OSError):
            continue
    return False


def portal_available(url):
    try:
        with direct_get(url) as response:
            return 200 <= response.status_code < 400
    except OSError:
        return False


def _browser_path():
    if os.name == "nt":
        for browser in ("Microsoft/Edge/Application/msedge.exe", "Google/Chrome/Application/chrome.exe"):
            for location in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
                directory = os.environ.get(location)
                if directory:
                    path = Path(directory) / browser
                    if path.is_file():
                        return path

    for executable in (
        "microsoft-edge", "microsoft-edge-stable", "msedge", "google-chrome",
        "google-chrome-stable", "chrome", "chromium", "chromium-browser",
    ):
        path = shutil.which(executable)
        if path:
            return path
    raise JobError("找不到 Edge、Chrome 或 Chromium，请先安装其中一个浏览器")


@contextmanager
def _browser(headless, log):
    from DrissionPage import ChromiumOptions, ChromiumPage
    from DrissionPage.common import Settings

    Settings.set_browser_connect_timeout(12)
    Settings.set_cdp_timeout(8)
    options = ChromiumOptions(read_file=False)
    options.set_browser_path(str(_browser_path()))
    options.auto_port()
    options.headless(headless)
    options.set_timeouts(base=5, page_load=12, script=5)
    options.set_argument("--no-proxy-server")
    try:
        page = ChromiumPage(options)
    except Exception as exc:
        raise JobError(f"浏览器启动失败（{type(exc).__name__}）") from exc
    try:
        yield page
    finally:
        try:
            page.quit(timeout=3, force=False)
        except Exception:
            log("浏览器清理失败")


CAPTURE_JS = r"""
const steps = ["账号输入框", "密码输入框", "登录按钮"];
const result = {paths: [], cancelled: false};
window.__shuCapture = result;
const prompt = document.createElement("div");
prompt.style.cssText = "position:fixed;top:0;left:0;right:0;z-index:2147483647;" +
    "padding:12px;background:#124870;color:white;text-align:center;pointer-events:none;" +
    "font:16px sans-serif";
document.body.appendChild(prompt);

function showStep() {
    const i = result.paths.length;
    prompt.textContent = `录制 ${i + 1}/3 · 请点击${steps[i]}（Esc 取消）`;
}
function xpath(node) {
    if (node.id && !node.id.includes('"') && document.getElementById(node.id) === node) {
        return '//*[@id="' + node.id + '"]';
    }
    const parts = [];
    for (; node; node = node.parentElement) {
        let index = 1;
        for (let sibling = node.previousElementSibling; sibling; sibling = sibling.previousElementSibling) {
            if (sibling.localName === node.localName) index++;
        }
        parts.unshift(node.localName + "[" + index + "]");
    }
    return "/" + parts.join("/");
}
function finish() {
    prompt.remove();
    window.removeEventListener("click", onClick, true);
    window.removeEventListener("keydown", onKey, true);
}
function onClick(event) {
    event.preventDefault();
    event.stopImmediatePropagation();
    const target = event.target;
    if (!(target instanceof Element)) return;
    const i = result.paths.length;
    const node = i < 2 ? target.closest("input") || target.querySelector("input")
        : target.closest("button,input,[role=button],a") || target;
    if (!node || (i === 0 && node.type === "password") ||
        (i === 1 && node.type !== "password")) {
        prompt.textContent = `请点击${steps[i]}（Esc 取消）`;
        return;
    }
    const path = xpath(node);
    if (result.paths.includes(path)) {
        prompt.textContent = `这个元素已录制，请点击${steps[i]}（Esc 取消）`;
        return;
    }
    result.paths.push(path);
    if (result.paths.length === steps.length) finish();
    else showStep();
}
function onKey(event) {
    if (event.key === "Escape") {
        result.cancelled = true;
        finish();
    }
}
window.addEventListener("click", onClick, true);
window.addEventListener("keydown", onKey, true);
showStep();
return true;
"""

FILL_INPUT_JS = r"""
const [path, value, password] = arguments;
let input = document.evaluate(path, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null)
    .singleNodeValue;
if (input && input.tagName !== "INPUT") input = input.querySelector("input");
const usable = element => element && element.getClientRects().length &&
    !element.disabled && !element.readOnly;
if (password && (!usable(input) || input.type !== "password")) {
    const fields = Array.from(document.querySelectorAll("input[type=password]")).filter(usable);
    if (fields.length === 1) input = fields[0];
}
if (!usable(input) || /^(button|checkbox|file|hidden|radio|reset|submit)$/.test(input.type) ||
    (!password && input.type === "password")) return false;
input.focus();
Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(input, value);
input.dispatchEvent(new Event("input", {bubbles:true}));
input.dispatchEvent(new Event("change", {bubbles:true}));
return input.value === value;
"""

CLICK_LOGIN_JS = r"""
const target = document.evaluate(arguments[0], document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null)
    .singleNodeValue;
const button = target && (target.closest("button,input,[role=button],a") || target);
if (!button || typeof button.click !== "function" || !button.getClientRects().length ||
    button.disabled || button.getAttribute("aria-disabled") === "true") return false;
setTimeout(() => button.click(), 25);
return true;
"""


def _xpath(path):
    # The original recorder used relative paths starting with BODY for elements without ids.
    if re.fullmatch(r"BODY(?:/[A-Z0-9-]+\[\d+\])+", path):
        return "/html/" + path.lower()
    return path


def capture_login(stop, log):
    with _browser(False, log) as page:
        if not page.get(DEFAULT_LOGIN_URL, retry=0):
            raise JobError("无法打开校园网认证页，请检查网线或 Wi-Fi")
        if page.run_js(CAPTURE_JS) is not True:
            raise JobError("无法启动录制，请重新打开认证页")
        deadline = time.monotonic() + 120
        while not stop.wait(0.25) and time.monotonic() < deadline:
            result = page.run_js("return JSON.stringify(window.__shuCapture);")
            if not result:
                raise JobError("认证页已刷新，请重新录制")
            state = json.loads(result)
            if state["cancelled"]:
                return None
            if len(state["paths"]) == 3:
                return state["paths"]
        if stop.is_set():
            return None
        raise JobError("录制超时，请重新录制")


def login(config, stop, log, headless):
    if stop.is_set():
        return False

    with _browser(headless, log) as page:
        if not page.get(config["url"], retry=0):
            raise JobError("无法打开校园网认证页")

        for path_key, value_key, label in (("u_xp", "user", "账号框"), ("p_xp", "pwd", "密码框")):
            deadline = time.monotonic() + 5
            while not stop.is_set():
                if page.run_js(
                    FILL_INPUT_JS, _xpath(config[path_key]), config[value_key], value_key == "pwd"
                ) is True:
                    break
                if time.monotonic() >= deadline:
                    raise JobError(f"无法填写{label}，请重新录制登录配置")
                stop.wait(0.25)

        if stop.is_set():
            return False
        if page.run_js(CLICK_LOGIN_JS, _xpath(config["b_xp"])) is not True:
            raise JobError("登录按钮不可用，请检查配置或重新录制")

        log("已提交登录表单，正在验证外网连接")
        deadline = time.monotonic() + 20
        while not stop.wait(1.5) and time.monotonic() < deadline:
            if internet_available():
                return True
        if stop.is_set():
            return False
        raise JobError("提交后仍无法访问外网，请检查校园网账号和认证页提示")


def ip_report():
    if os.name == "nt":
        return subprocess.check_output(
            ["ipconfig", "/all"], timeout=8, encoding="oem", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    for command in (["ip", "addr"], ["ifconfig"]):
        try:
            return subprocess.check_output(
                command, timeout=8, encoding=locale.getpreferredencoding(False), errors="replace",
            )
        except (OSError, subprocess.SubprocessError):
            continue
    raise JobError("无法获取 IP 信息，请确认 ip addr 或 ifconfig 可运行")


def send_ip_report(config):
    message = EmailMessage()
    message["Subject"] = f"【网络已连接】{socket.gethostname()} IP配置报告 - {datetime.now():%m-%d %H:%M}"
    message["From"] = config["sender"]
    message["To"] = config["target"]
    message.set_content(ip_report())
    context = ssl.create_default_context()
    errors = []
    for port in (465, 587):
        with ExitStack() as cleanup:
            try:
                if port == 465:
                    server = smtplib.SMTP_SSL(config["smtp"], port, timeout=8, context=context)
                else:
                    server = smtplib.SMTP(config["smtp"], port, timeout=8)
                cleanup.callback(server.close)
                if port == 587:
                    server.starttls(context=context)
                server.login(config["sender"], config["pwd"])
            except OSError as error:
                errors.append(f"{port}（{type(error).__name__}）")
                continue
            server.send_message(message)
            return
    raise JobError("无法连接或登录 SMTP " + "、".join(errors))

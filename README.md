# SHU 校园网助手

用于上海大学校园网自动认证，默认认证地址为 `http://10.10.9.9`。原项目来自 [labourer-bobo/SHU-Campus-Net-Helper](https://github.com/labourer-bobo/SHU-Campus-Net-Helper)。Windows EXE 和打包说明见 [windows 分支](https://github.com/ACGNworld/SHU-Campus-Net-Helper-Linux/tree/windows)。

## Linux 安装

需要 Python 3.8+、Tk、图形桌面和 Edge、Chrome 或 Chromium。浏览器命令应在 `PATH` 中。在 Ubuntu 或 Debian 上运行以下命令。

```bash
sudo apt install python3-tk python3-venv python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 iproute2
git clone https://github.com/ACGNworld/SHU-Campus-Net-Helper-Linux.git
cd SHU-Campus-Net-Helper-Linux
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python SHU_net_helper.py
```

首次运行会显示主窗口。配置登录后，如果桌面提供可用的托盘，程序会在启动后隐藏到托盘。GNOME 桌面可能需要启用 AppIndicator 扩展。桌面没有托盘时，程序会保留可见窗口。

## 使用

1. 点击“录制登录配置”，按网页顶部的提示依次点击账号框、密码框和登录按钮，再输入校园网账号和密码。录制时可按 Esc 取消。
2. 点击“测试连接并发信”。外网不可用时会尝试校园网认证。外网可用时直接测试邮件。
3. 如需 IP 报告，点击“配置汇报邮箱”填写服务器、发件人、SMTP 授权码及收件人。邮件使用 SSL 465 端口，连接或认证失败时尝试 STARTTLS 587。报告由 `ip addr` 获取，也支持 `ifconfig`。

后台约每 30 秒检查外网。两个探测地址均失败时，约 5 秒后复查。连续两轮失败且认证页可达才尝试后台登录。登录失败后等待时间从 30 秒逐步增加至 5 分钟。提交表单后确认外网恢复才会发出 IP 报告。

配置保存在 `${XDG_CONFIG_HOME:-$HOME/.config}/SHU-Campus-Net-Helper/`。首次启动时会从脚本目录或当前工作目录导入旧版 JSON 配置。既有配置可以继续使用。

## 登录桌面后自动启动

可在系统的“启动应用程序”中添加一项，也可以在 `~/.config/autostart/` 中创建 `shu-campus-net-helper.desktop`。请将以下路径替换为实际安装路径。

```ini
[Desktop Entry]
Type=Application
Name=SHU Campus Net Helper
Exec=/path/to/SHU-Campus-Net-Helper-Linux/.venv/bin/python /path/to/SHU-Campus-Net-Helper-Linux/SHU_net_helper.py
Terminal=false
```

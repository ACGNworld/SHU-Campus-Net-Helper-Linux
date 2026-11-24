# SHU 校园网助手

Windows 托盘工具，用于上海大学校园网自动认证。登录成功后可向指定邮箱发送本机的 `ipconfig /all` 报告。默认认证地址为 `http://10.10.9.9`，需要安装 Edge 或 Chrome。

## 使用

1. 双击 `output_exe\SHU校园网助手.exe`。首次运行时会打开主界面，已有登录配置时可从系统托盘打开界面。
2. 点击“录制登录配置”，按浏览器页面顶部的提示依次点击账号框、密码框和登录按钮，再输入校园网账号和密码。录制时可按 Esc 取消。
3. 如需接收 IP 报告，点击“配置汇报邮箱”，填写 SMTP 服务器、发件人、SMTP 授权码和收件人。使用 SSL 465 端口，例如 QQ 邮箱的 `smtp.qq.com`。
4. 点击“测试连接并发信”。外网已经可用时直接测试邮件，外网不可用时先尝试校园网认证。

后台每 30 秒检测外网。首次检测失败后约 5 秒复查。两个探测地址均不可用且校园网认证页可达时，程序在后台打开浏览器尝试登录。连续重试失败后，等待时间从 30 秒逐步增加到 5 分钟。“测试连接并发信”可立即检查。关闭主窗口会将程序隐藏到托盘，可从托盘菜单退出。

配置保存在 `%LOCALAPPDATA%\SHU-Campus-Net-Helper`。首次启动时可从旧 EXE 所在目录或原工作目录自动导入现有的 `login_config.json` 和 `email_config.json`。

## 登录 Windows 后自动启动

按 Win + R，输入 `shell:startup`。将 EXE 的快捷方式放进打开的文件夹。

## 从源码运行或打包

在 Windows 上使用 Python 3：

```powershell
python -m pip install -r requirements.txt
python SHU_net_helper.py
python -m PyInstaller --noconfirm --distpath output_exe "SHU校园网助手.spec"
```

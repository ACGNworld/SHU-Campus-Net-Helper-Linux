# SHU-Campus-Net-Helper (上海大学校园网助手)
##  项目简介
原win版来自https://github.com/labourer-bobo/SHU-Campus-Net-Helper

这是一个基于 Python 开发的上海大学校园网自动连接工具。
能够智能识别输入框并完成登录
默认访问地址是10.10.9.9，可用于实验室服务器周期性自动网络验证

当前版本已支持 Windows 和 Linux 系统。

**✨ 核心功能：**
* **自动连接**：断网自动重连。
* **后台静默**：启动后自动隐藏至系统托盘，不打扰日常使用。
* **IP汇报**：连接成功后，自动抓取本机网络配置信息 (`ipconfig` 或 `ip addr`) 并发送到指定邮箱（方便远程管理）。

---

## 环境要求 (Linux)
在 Linux 上运行，需要安装以下系统依赖和浏览器：

1. **图形界面与系统托盘支持**：
   ```bash
   sudo apt-get update
   sudo apt-get install -y python3-tk libayatana-appindicator3-dev gir1.2-ayatanaappindicator3-0.1
   ```
2. **浏览器支持**：
   程序支持 Edge (推荐)、Chrome、Chromium。如果未安装，可以执行：
   - 安装 Edge: [微软官网下载](https://www.microsoft.com/zh-cn/edge/download) 或通过命令安装。
   - 安装 Chromium: `sudo apt install -y chromium-browser`

## 使用步骤 (Linux)

### 1. 运行程序
1.  安装 Python 依赖：`pip install -r requirements.txt`
2.  启动：`python SHU_net_helper.py`
3.  程序启动后会默认隐藏到**系统托盘**（右上角或底部工具栏）。

### 2. 配置与连接
1.  在托盘图标右键 -> 点击 **“显示主界面”**。
2.  点击 **“🛠️ 1. 录制登录配置”**：
    - 程序会自动尝试打开 Edge 或 Chrome。
    - 依次点击：**账号框** -> **密码框** -> **登录按钮**。
    - 在后续弹窗输入真实的账号和密码并确定。
3.  点击 **“🚀 3. 测试连接”** 验证是否能成功登录。

### 3. 配置 IP 邮件汇报 (可选)
- 点击 **“📧 2. 配置汇报邮箱”**。
- 支持 QQ 邮箱等主流邮箱，程序会自动尝试 465 (SSL) 和 587 (STARTTLS) 端口。
- 成功连接后，会自动将 `ip addr` 信息发送到你的邮箱。

### 4. Linux 下设置开机自启
任何方式都需要桌面关闭自动锁屏、打开自动登录
- **方式 A (GUI)**：搜索并打开“启动应用程序”(Startup Applications)，点击“添加”，命令填写：`python3 /你的路径/SHU_net_helper.py &`。
- **方式 B (命令行)**：可以在 `~/.config/autostart/` 目录下创建一个 `.desktop` 文件。
- **方式C (systemd)**:
---

## 常见问题 (FAQ)

**Q: 报错 `Namespace AyatanaAppIndicator3 not available`**
A: 请确保运行了 `sudo apt install gir1.2-ayatanaappindicator3-0.1`。

**Q: 无法找到浏览器**
A: 程序会按顺序查找 `microsoft-edge`, `google-chrome`, `chromium`。如果你的浏览器在特殊位置，请确保它在系统的 `PATH` 环境变量中，或安装 `chromium-browser`。

**Q: 邮件发送失败**
A: 程序已内置 465/587 端口自动切换逻辑。如果依然失败，请确认使用的是邮箱**授权码**而非密码，并检查学校网络是否拦截了外发邮件端口。

---

##  使用步骤(win)

### 1. 下载与运行
1.  下载最新版本的 `SHU校园网助手.exe`：[最新版本下载](https://github.com/labourer-bobo/SHU-Campus-Net-Helper/releases/latest)
2.  双击运行，程序会自动隐藏到右下角系统托盘（绿色小方块图标）。

### 2. 初始化配置
1.  **右键托盘图标** -> 点击 **“显示主界面”**。
2.  点击 **“🛠️ 1. 录制登录配置”**：
    * 浏览器弹出后，依次点击网页上的：**账号框** -> **密码框** -> **登录按钮**。
    * 在弹窗中输入**真实账号密码**。
3.  点击 **“🚀 3. 测试连接”** 验证是否成功。

### 3. (可选) 开启 IP 邮件汇报
如果你需要远程管理电脑，可点击 **“📧 2. 配置汇报邮箱”**。
* **SMTP服务器**：如 QQ 邮箱填 `smtp.qq.com`。
* **授权码**：请在邮箱设置中开启 POP3/SMTP 服务获取（非登录密码）。
* QQ邮箱配置教程： https://help.mail.qq.com/detail/106/985

---

## 开机自启
### 一键进入自启动目录
1.  按 `Win + R`，输入 `shell:startup`。
2.  将 `exe` 文件的**快捷方式**拖入打开的文件夹中即可。

### 手动进入自启动目录
如果直接访问失败，可以手动找到类似如下地址
C:\Users\你的用户名\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup

* 在顶部的菜单栏，点击 “查看”，然后把 “隐藏的项目” 勾选上
* 依次进入以下路径：
* C 盘
* 用户 (Users)
* 你的用户名文件夹 (例如 xxx 或 Administrator)
* AppData (是半透明的隐藏文件夹)
* Roaming 
* Microsoft
* Windows
* 「开始」菜单 (Start Menu)
* 程序 (Programs)  程序
* 启动 (Startup)

---

##  开发者指南

### 环境依赖
* Python 3.8+
* 依赖库：见 `requirements.txt`

### 如何运行源码
```bash
git clone https://github.com/ACGNworld/SHU-Campus-Net-Helper-Linux.git
pip install -r requirements.txt
python SHU_net_helper.py

### 如何打包为 .exe 文件
pyinstaller -F -w --distpath output_exe --name "SHU校园网助手" SHU_net_helper.py

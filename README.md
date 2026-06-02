# 🎮 BroadlinkAC

macOS 桌面应用，通过 Broadlink RM4 Mini 红外遥控器控制空调，集成实时天气与台风监测。

## ✨ 功能

- 🎯 **多品牌支持** — 格力 / 美的 / 海尔 / 奥克斯 / 海信 / 大金 / 三菱 / 松下
- 🌤️ **实时天气** — 和风天气 API，温度 + 湿度 + 体感 + 风向
- ⏰ **智能定时** — 根据室外温度自动开关空调（可配规则）
- 🌀 **台风监测** — 中央气象台数据，预警距离提醒
- 📋 **操作日志** — 每日自动记录，可回溯查看
- 🔧 **故障诊断** — 内置一键检测，自动安装缺失依赖

## 🧰 硬件要求

- 一台 Mac（Apple Silicon / Intel）
- [Broadlink RM 系列](https://www.broadlink.com.cn/) 红外遥控器（RM Mini / RM Pro / RM4 Mini 等）
- 空调（支持品牌见上）

## 🚀 快速开始

### 方式一：下载 .app（推荐）

从 [Releases](https://github.com/oywq00008-cell/BroadlinkAC/releases) 下载 `智能空调.app`，拖到应用程序文件夹，双击运行。

首次启动如提示"无法验证开发者"：
```bash
xattr -cr /Applications/智能空调.app
```

### 方式二：从源码运行

```bash
git clone https://github.com/oywq00008-cell/BroadlinkAC.git
cd BroadlinkAC
pip install -r requirements.txt
python3 ac_controller.py
```

## ⚙️ 配置

首次运行后在菜单栏 **设置** 中填入：

| 项目 | 说明 |
|------|------|
| 和风 API Key | [和风天气控制台](https://console.qweather.com) 免费申请 |
| 个人 Host | 免费订阅的 API Host 地址 |
| 空调品牌 | 选择你家空调品牌 |

博联设备会自动扫描局域网发现，无需手动配 IP。

## 📁 项目结构

```
ac_controller.py          # 主程序（customtkinter GUI）
protocols/
├── haier.py              # 海尔协议（从 IRremoteESP8266 C++ 移植）
├── aux.py                # 奥克斯协议
└── panasonic.py          # 松下协议
requirements.txt          # Python 依赖
```

## 🔐 隐私

所有配置（API Key、城市、时间规则）保存在本地 `~/.ac_controller/`，不上传任何服务器。天气和台风数据直接从官方 API 获取。

## 📜 协议

MIT License

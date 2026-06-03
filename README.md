# 🎮 BroadlinkAC v3.1

[English](README_EN.md) | 中文

博联空调智能控制器 — macOS / Windows 桌面应用 + **AI Agent 可编程调用**。

> 💡 **每天定时自动开关** · **根据室外温度智能调温** · **每2小时自动微调** · **天气预警 + 台风监测** · **Agent 零门槛调用**。

```python
from broadlinkac_core import init, send_ac

# 一行初始化，自动保存所有配置
init(api_key="你的Key", qw_host="https://你的Host",
     location={"lat": 22.54, "lon": 114.05, "name": "深圳"}, brand="格力")

send_ac("on", "cool", 26, "auto")   # 开机 · 制冷 26°C
send_ac("off", "cool", 26, "auto")  # 关机
```

## ✨ 核心功能

- 🎯 **多品牌支持** — 格力 / 美的 / 小米 / 海尔 / 奥克斯 / 海信 / 大金 / 三菱 / 松下
- ⏰ **定时开关机** — 每天自动开机 / 关机
- 🌡️ **温度规则** — 室外温度变化自动调整制冷/制热目标，规则完全可编辑
- 🔄 **自动调温** — 每 2 小时检测室外温度，按规则微调，无需手动干预
- 🌤️ **实时天气** — 和风天气 API，温度 / 湿度 / 体感 / 风向
- ⚠️ **预警信息** — 当地天气预警（高温/暴雨/大风等）+ 台风监测，等级颜色区分，分页浏览
- 🎨 **主题切换** — 跟随系统 / 亮色 / 暗色，设置窗口卡片化布局
- 📋 **操作日志** — 每日自动记录，系统编辑器打开直接搜索
- 🔧 **故障诊断** — 内置一键检测
- 🤖 **Agent 可调用** — `import` 零副作用，`init()` 即用，适配所有 AI Agent

### 🕐 定时规则示例

| 室外温度 | 动作 | 目标温度 |
|----------|------|----------|
| ≥ 36°C | 制冷 | 24°C |
| 33-35°C | 制冷 | 25°C |
| 30-32°C | 制冷 | 26°C |
| 25-29°C | 制冷 | 27°C |
| 18-24°C | 不启动 | — |
| ≤ 17°C | 制热 | 28°C |

## 🧰 硬件要求

- 任何能运行 Python 3.9+ 的设备（macOS / Windows / Linux / 树莓派 / NAS / 服务器）
- [Broadlink RM 系列](https://www.broadlink.com.cn/) 红外遥控器（RM Mini / RM Pro / RM4 Mini 等）
- 支持品牌的空调

## 🚀 快速开始

### 方式一：下载安装包（推荐）

| 平台 | 下载 |
|------|------|
| macOS | [BroadlinkAC.app.zip](https://github.com/oywq00008-cell/BroadlinkAC-For-AI-Agent/releases/latest) |
| Windows | [BroadlinkAC-Windows.zip](https://github.com/oywq00008-cell/BroadlinkAC-For-AI-Agent/releases/latest) |

macOS 首次提示「无法验证开发者」：
```bash
xattr -cr /Applications/BroadlinkAC.app
```

### 方式二：从源码运行

```bash
git clone https://github.com/oywq00008-cell/BroadlinkAC-For-AI-Agent.git
cd BroadlinkAC
pip install -r requirements.txt
python3 ac_controller.py
```

### 方式三：Agent / 无头模式（Linux / 树莓派 / 服务器）

```bash
git clone https://github.com/oywq00008-cell/BroadlinkAC-For-AI-Agent.git
cd BroadlinkAC-For-AI-Agent
pip install -r requirements-core.txt
```

```python
from broadlinkac_core import init, send_ac

init(api_key="你的Key", qw_host="https://你的Host")
send_ac("on", "cool", 26, "auto")
```

无需 GUI，`broadlinkac_core/` 纯 Python 跨平台，Linux / Ubuntu / Debian / 树莓派均可运行。
## ⚙️ 配置

首次运行后在菜单栏 **设置** 中填入：

| 项目 | 说明 |
|------|------|
| 和风 API Key | [和风天气控制台](https://console.qweather.com) 免费申请 |
| 个人 Host | 免费订阅的 API Host 地址 |
| 空调品牌 | 选择品牌 |

博联设备自动扫描局域网发现，无需手动配 IP。

## 📁 项目结构

```
ac_controller.py              # 入口（19 行）
broadlinkac_core/             # 核心库（零 GUI 依赖）
├── __init__.py               # 公共 API
├── config.py                 # 配置 + init()
├── weather.py                # 天气 + 预警
├── typhoon.py                # 台风监测
├── ac_control.py             # 空调控制 + 发码
├── scheduler.py              # 定时任务 + 自动调温
└── logger.py                 # 日志
broadlinkac_desktop/          # 桌面 GUI（跨平台）
└── app.py                    # CustomTkinter 界面
protocols/                    # 红外协议（C++ 移植）
├── haier.py
├── aux_ac.py                 # AUX（Electra 协议）
└── panasonic.py
requirements.txt
requirements-core.txt         # 无头模式（无 GUI 依赖）
```

## 🔐 隐私

所有配置存储在本地 `~/.ac_controller/`，不上传任何服务器。天气和台风数据直接来自官方 API。

## 📜 协议

MIT License

## 💝 致谢

- [IRremoteESP8266](https://github.com/crankyoldgit/IRremoteESP8266) — 海尔/奥克斯/松下红外协议 C++ 源码参考
- [python-broadlink](https://github.com/mjg59/python-broadlink) — 博联 RM 设备 Python 驱动
- [hvac_ir](https://github.com/nicko858/hvac_ir) — 格力/美的/海信/大金/三菱红外协议库
- [和风天气](https://www.qweather.com) — 天气与预警数据
- [中央气象台](https://www.nmc.cn) — 台风监测数据

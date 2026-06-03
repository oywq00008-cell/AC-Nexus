# 🎮 BroadlinkAC v3.0

[English](README_EN.md) | 中文

博联空调智能控制器 — macOS 桌面应用 + **AI Agent 可编程调用**。

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
- ⚠️ **预警信息** — 当地天气预警（高温/暴雨/大风等）+ 台风监测，等级颜色区分
- 📋 **操作日志** — 每日自动记录，可回溯查看
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

- 一台 Mac（Apple Silicon / Intel）
- [Broadlink RM 系列](https://www.broadlink.com.cn/) 红外遥控器（RM Mini / RM Pro / RM4 Mini 等）
- 支持品牌的空调

## 🚀 快速开始

### 方式一：下载 .app（推荐）

从 [Releases](https://github.com/oywq00008-cell/BroadlinkAC-For-AI-Agent/releases) 下载 `BroadlinkAC.app`，双击运行。

首次提示「无法验证开发者」：
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

### 方式三：Agent 全自动调用

```bash
git clone https://github.com/oywq00008-cell/BroadlinkAC-For-AI-Agent.git
cd BroadlinkAC
pip install -r requirements.txt
```

```python
from broadlinkac_core import init, send_ac, fetch_weather

init(api_key="你的Key", qw_host="https://你的Host")
weather = fetch_weather()
send_ac("on", "cool", 26, "auto")
```

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
broadlinkac_desktop/          # macOS GUI
└── app.py                    # CustomTkinter 界面
protocols/                    # 红外协议（C++ 移植）
├── haier.py
├── aux.py
└── panasonic.py
requirements.txt
```

## 🔐 隐私

所有配置存储在本地 `~/.ac_controller/`，不上传任何服务器。天气和台风数据直接来自官方 API。

## 📜 协议

MIT License

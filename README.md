# 🎮 BroadlinkAC v3A

[English](README_EN.md) | 中文

博联空调智能控制器 — 桌面应用 + **AI Agent 可编程 API**。支持局域网多设备管理、定时/自动调温、双源天气预警、台风路径图。

![主界面](assets/screenshot-main.png)
![台风预警](assets/screenshot-typhoon.png)
![设置](assets/screenshot-settings.png)

## 🤖 Agent 调用

```python
from broadlinkac_core import init, send_ac, get_device_list

# 一行初始化（自动保存 config.json）
init(api_key="你的Key", qw_host="https://你的Host",
     location={"lat": 22.54, "lon": 114.05, "name": "深圳"})

# 控制空调 — 品牌名中英文均可，自动匹配红外协议
send_ac("on", "cool", 26, "auto")                    # 当前设备
send_ac("off", "cool", 26, "auto", mac="e870723f")   # 指定设备

# 多设备
for mac, name in get_device_list():
    print(f"{name}: {mac}")

# 读取天气
from broadlinkac_core import fetch_weather, fetch_weather_alerts
w = fetch_weather()          # {temp, humidity, condition, ...}
alerts = fetch_weather_alerts()
```

Agent 无需 GUI，`pip install -r requirements-core.txt` 即可。

## 🎯 支持的空调品牌

核心支持全部 **17 种** 协议（桌面端下拉菜单显示其中 10 个中文品牌）。

| 中文名 | 英文 / Agent 传参 | 协议来源 |
|--------|-------------------|----------|
| 格力 | `gree` | hvac_ir |
| 美的 / 华凌 / 小米 | `midea` | hvac_ir |
| 海尔 | `haier` | 自研 protocols |
| 奥克斯 | `aux_ac` | 自研 protocols |
| 海信 | `hisense` | hvac_ir |
| 大金 | `daikin` | hvac_ir |
| 三菱 | `mitsubishi` | hvac_ir |
| 松下 | `panasonic` | 自研 protocols |
| 日立 | `hitachi` | hvac_ir |
| 富士通 | `fujitsu` | hvac_ir |
| 巴鲁 | `ballu` | hvac_ir |
| 开利 | `carriermca` | hvac_ir |
| 现代 | `hyundai` | hvac_ir |
| Fuego | `fuego` | hvac_ir |

Agent 传参 `brand="日立"` 或 `brand="hitachi"` 均可自动解析。上表未列出的 hvac_ir 品牌（如 `carriernqv`、`daikin2`）也支持，传英文模块名即可。

## ✨ 功能

- 📡 **多设备** — 局域网自动发现，下拉切换，离线标注
- ⏰ **并行定时** — 每台设备独立定时开关、自动调温
- 🌡️ **温度规则** — 室外温度变化自动调整制冷/制热目标
- 🌤️ **双源天气** — 百度 / 和风，一键切换
- ⚠️ **预警 + 台风** — 当地预警 + 🌀 台风路径 Canvas 图
- 🎨 **品牌 Logo** — 控制面板动态显示
- 📋 **操作日志** — 每日自动记录
- 🔧 **故障诊断** — 三层网络诊断

## 🧰 硬件要求

- Python 3.9+（macOS / Windows / Linux / 树莓派 / NAS）
- [Broadlink RM 系列](https://www.broadlink.com.cn/) 红外遥控器

## 🚀 快速开始

### 桌面应用

| 平台 | 下载 |
|------|------|
| Windows | [BroadlinkAC-V3A.7z](https://github.com/oywq00008-cell/BroadlinkAC-For-Agent/releases/latest) |
| macOS | [BroadlinkAC.app.zip](https://github.com/oywq00008-cell/BroadlinkAC-For-Agent/releases/latest) |

macOS 首次运行：
```bash
xattr -cr /Applications/BroadlinkAC.app
```

源码运行：
```bash
git clone https://github.com/oywq00008-cell/BroadlinkAC-For-Agent.git
cd BroadlinkAC-For-Agent
pip install -r requirements.txt
python ac_controller.py
```

### Agent / 无头模式

```bash
pip install -r requirements-core.txt
```

```python
from broadlinkac_core import init, send_ac
init()
send_ac("on", "cool", 26, "auto")
```

## ⚙️ 配置

首次运行后在设置中填入天气 API Key（百度 5,000 次/天或和风 50,000 次/月，免费注册）。博联设备局域网自动扫描。Agent 模式通过 `init()` 传参或直接编辑 `~/.ac_controller/config.json`。

## 📁 项目结构

```
ac_controller.py              # 入口
broadlinkac_core/             # 核心库（零 GUI 依赖）
├── __init__.py               # 公共 API
├── config.py                 # 配置 + resolve_brand() + 设备管理
├── weather.py                # 双源天气 + 预警 + 台风
├── ac_control.py             # 空调控制 + 动态协议导入
├── scheduler.py              # 多设备并行定时调度
└── logger.py                 # 日志
broadlinkac_desktop/          # 桌面 GUI
└── app.py
protocols/                    # 自研红外协议
└── haier.py / aux_ac.py / panasonic.py
logos/                        # 品牌 Logo
```

## 🔐 隐私

所有配置本地存储 `~/.ac_controller/`，不上传任何服务器。

## 📜 协议

MIT License

## 💝 致谢

- [python-broadlink](https://github.com/mjg59/python-broadlink) — 博联 RM 驱动
- [hvac_ir](https://github.com/nicko858/hvac_ir) — 红外协议库
- [IRremoteESP8266](https://github.com/crankyoldgit/IRremoteESP8266) — C++ 协议参考
- [和风天气](https://www.qweather.com) / [百度地图开放平台](https://lbsyun.baidu.com) — 天气数据
- [中央气象台](https://www.nmc.cn) — 台风数据

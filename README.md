# 🎮 BroadlinkAC v5.0

[English](README_EN.md) | 中文

BroadlinkAC 不止是一个空调遥控器桌面应用——它是一套**为 AI Agent 而生的红外控制协议栈**。接入博联 RM 红外模块后，任何 AI Agent 只需 `import broadlinkac_core`，即可用一行 Python 控制格力、日立、大金等 **17 种品牌**的空调。支持多设备并行调度、室外温度自适应调温、台风路径预报，桌面应用（PySide6）和命令行/Agent 两个模式共享同一套核心，Windows / macOS / Linux 即装即用。

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

# 风暴威胁评估
from broadlinkac_core import typhoon_threat_distance
dist, name = typhoon_threat_distance()
if dist < 100:
    send_ac("off", "cool", 26, "auto", source="台风")  # 风暴临近自动关机
```

Agent 无需 GUI，`pip install -r requirements-core.txt` 即可。

> `send_ac` 仅保证开关/模式/温度/风速四个通用能力。若你的空调支持强力、扫风等高级功能，可让 Agent 修改 `broadlinkac_core/ac_control.py` 添加可选参数透传。

## 🎯 支持的空调品牌

核心支持全部 **17 种** 协议，桌面端下拉菜单现已全部覆盖，Logo 齐全。

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

Agent 传参 `brand="日立"` 或 `brand="hitachi"` 均可自动解析。

## ✨ 功能

- 📡 **多设备** — 局域网自动发现，下拉切换，离线标注
- ⏰ **定时模板** — 多日期组独立设置（工作日/周末不同时段）
- 🌡️ **智能温控** — 室外温度变化自动调整制冷/制热目标
- 🌤️ **双源天气** — 百度 / 和风，一键切换
- 🌀 **双源风暴** — 中国中央气象台 (NMC) + 美国飓风中心 (NHC)，路径预报图
- 🌪️ **风暴保护** — 距离 < 100km 自动关闭所有空调
- ⚠️ **预警信息** — 风暴监测 + 当地天气预警，左右分栏
- 🎨 **深色主题** — 浅色/深色一键切换
- 📋 **操作日志** — 按日期检索
- 🔧 **故障诊断** — 自动检测环境和设备

## 📸 界面截图

| 主界面 | 
|--------|
 ![主界面](assets/screenshot-main.png) |

| 设置 | 预警信息 |
|--------|----------|
 ![设置](assets/screenshot-settings.png) | ![预警信息](assets/screenshot-typhoon.png) |

## 🧰 硬件要求

- Python 3.9+（macOS / Windows / Linux / 树莓派 / NAS）
- [Broadlink RM 系列](https://www.broadlink.com.cn/) 红外遥控器

## 📡 部署到 OpenWRT 路由器

> **[BroadlinkAC-OpenWRT](https://github.com/oywq00008-cell/BroadlinkAC-OpenWRT)** — LuCI 控制面板 + procd 守护 + IPK 一键安装

两项目共享核心算法和红外协议，独立进化。

## 🚀 快速开始

### 桌面应用

| 平台 | 下载 |
|------|------|
| 🪟 Windows | [BroadlinkAC.exe](https://github.com/oywq00008-cell/BroadlinkAC-For-Agent/releases/latest/download/BroadlinkAC-Windows.zip) |
| 🍎 macOS | [BroadlinkAC.app](https://github.com/oywq00008-cell/BroadlinkAC-For-Agent/releases/latest/download/BroadlinkAC-macOS.zip) |
| 🐧 Linux | [BroadlinkAC-linux](https://github.com/oywq00008-cell/BroadlinkAC-For-Agent/releases/latest/download/BroadlinkAC-linux.tar.gz) |

macOS 首次运行如果提示"无法验证开发者"，解压后先看 `打不开请看我.txt`。

源码运行：
```bash
git clone https://github.com/oywq00008-cell/BroadlinkAC-For-Agent.git
cd BroadlinkAC-For-Agent
pip install -r requirements.txt
python ac_controller_pyside6.py
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
ac_controller_pyside6.py      # PySide6 入口
broadlinkac_core/             # 核心库（零 GUI 依赖）
├── __init__.py               # 公共 API
├── config.py                 # 配置 + resolve_brand() + 设备管理
├── weather.py                # 双源天气 + 预警
├── typhoon.py                # 风暴 (NMC) + 飓风 (NHC) + KMZ 预报
├── ac_control.py             # 空调控制 + 动态协议导入
├── scheduler.py              # 定时调度（多日期组模板）
└── logger.py                 # 日志
broadlinkac_desktop/          # PySide6 桌面 GUI
├── app_pyside6.py            # 主窗口
└── pyside/                   # UI 模块
    ├── ac_tab.py             # 空调 + 天气 + 定时 + 规则
    ├── ty_tab.py             # 台风 + 预警 + 预报图
    ├── dialogs.py            # 所有弹窗
    └── _utils.py             # 工具函数
protocols/                    # 自研红外协议
logos/                        # 品牌 Logo
fonts/                        # 字体 (HarmonyOS Sans SC)
icons/                        # SVG 图标系统
BroadlinkAC.spec              # Windows 打包
BroadlinkAC-macOS.spec        # macOS 打包
BroadlinkAC-linux.spec        # Linux 打包
requirements.txt              # 完整依赖
requirements-core.txt         # Agent 最小依赖
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
- [中国中央气象台](https://www.nmc.cn) — 风暴数据
- [NHC](https://www.nhc.noaa.gov) — 北大西洋飓风数据

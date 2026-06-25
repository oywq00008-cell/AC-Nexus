# 🌀 AC-Nexus v5.3.1

[English](README_EN.md) | 中文

**全球首款内置智能风暴安全防护的空调控制系统。** 实时分析风暴风速与距离，智能判断是否关闭空调保护外机——风力越强、保护半径越大，热带低压自动排除，避免误关。这是市面上任何空调遥控器或智能家居平台都没有的功能。

博联Broadlink+米家MIoT双生态兼容，米家海量码库+内置**17种常见空调品牌红外协议**，**红外学习**适配任意品牌。AI Agent通过 `import acnexus_core` 一行代码控制空调，桌面应用全平台下载即用，并附带完整的使用指南，保证新手也能快速上手。

## 📸 界面

| 主界面 | 预警信息 |
|--------|----------|
| ![主界面](assets/screenshot-main.png) | ![预警信息](assets/screenshot-typhoon.png) |

| 设备切换（博联 / 米家） | 设置 |
|--------|------|
| ![设备切换](assets/screenshot-devices.png) | ![设置](assets/screenshot-settings.png) |

## 🤖 Agent 调用

```python
from acnexus_core import init, send_ac

init(api_key="你的Key", qw_host="https://你的Host",
     location={"lat": 22.54, "lon": 114.05, "name": "深圳"})

send_ac("on", "cool", 26, "auto")                     # 控制空调
send_ac("off", "cool", 26, "auto", mac="e870723f")    # 指定设备

# 风暴威胁评估 — 独家功能
from acnexus_core import typhoon_threat_distance, typhoon
dist, name = typhoon_threat_distance()
alerts = typhoon.judge_and_shutdown(print)  # 智能风速+距离分级判断，一键关机+暂停调度器
```

Agent 无需 GUI，`pip install -r requirements-core.txt` 即可。

## 🎯 内置协议

17种空调红外协议，桌面端全部覆盖，Logo齐全美观，一目了然。

| 格力 | 美的 | 海尔 | 奥克斯 | 海信 | 大金 | 三菱 | 松下 | 日立 |
|------|------|------|--------|------|------|------|------|------|
| 富士通 | 巴鲁 | 开利 | 现代 | Fuego | 华凌 | 小米 | — | — |

**所有支持米家MIoT的红外设备都能接入软件**，并引用海量码库，无论是Agent完全掌控还是桌面端完善的功能全部适配

Agent 传参中文/英文均可：`brand="日立"` 或 `brand="hitachi"` 自动解析
**项目内含skill，给Agent完整指导，解锁完全体**

## ✨ 功能

- 🌪️ **风暴保护** — 智能风速+距离分级判断（强台风<100km / 台风<70km / 默认<50km），热带低压自动排除，自动关闭空调+暂停调度器
- 📡 **双生态设备** — 博联 RM 局域网发现 + 米家 MIoT 云登录扫码添加
- 🎓 **红外学习** — 用原装遥控器教软件发码，适配任意品牌
- ⏰ **定时模板** — 多日期组独立设置（工作日 / 周末不同时段），可自由设置日期和时段
- 🌡️ **智能温控** — 室外温度变化自动调温，规则灵活编辑
- 🌤️ **双源天气** — 百度 / 和风API实时天气 + 预警（完全免费）
- 🌀 **双源风暴** — NMC 西北太平洋台风 + NHC 北大西洋飓风，路径预报图，覆盖全球主受灾区
- 🎨 **深色主题** — 浅色 / 深色 / 跟随系统
- 🌐 **中英双语** — 外挂 JSON 翻译，切换即时生效，不影响功能代码
- 🔧 **故障诊断** — 一键检测环境、依赖、设备连接

## 🚀 快速开始

| 平台 | 下载 |
|------|------|
| 🪟 Windows | [AC-Nexus.exe](https://github.com/oywq00008-cell/AC-Nexus/releases/latest/download/AC-Nexus-Windows.zip) |
| 🍎 macOS | [AC-Nexus.app](https://github.com/oywq00008-cell/AC-Nexus/releases/latest/download/AC-Nexus-macOS.zip) |
| 🐧 Linux | [AC-Nexus-linux](https://github.com/oywq00008-cell/AC-Nexus/releases/latest/download/AC-Nexus-linux.tar.gz) |

源码运行：

```bash
git clone https://github.com/oywq00008-cell/AC-Nexus.git
cd AC-Nexus
pip install -r requirements.txt
python ac_controller_pyside6.py
```

## 🧰 硬件

- Python 3.9+
- [Broadlink RM 系列](https://www.broadlink.com.cn/) 或米家 MIoT 红外遥控器

## 📁 结构

```
ac_controller_pyside6.py      # 入口
acnexus_core/             # 核心库（零 GUI 依赖）
├── ac_control.py             # 空调控制 + 动态协议
├── scheduler.py              # 定时调度
├── typhoon.py                # 双源风暴
├── weather.py                # 双源天气
├── ir_learner.py             # 红外学习
├── xiaomi_cloud.py            # 小米云扫码登录 + 加密
├── xiaomi_cloud.py           # 米家云 API
├── xiaomi_local.py           # 米家局域网
├── config.py                 # 配置
└── logger.py                 # 日志
acnexus_desktop/          # PySide6 桌面
├── app_pyside6.py            # 主窗口
└── pyside/                   # UI 模块
protocols/                    # 自研红外协议
```
## 📁 OpenWRT 路由器版本

[AC-Nexus-OpenWRT](https://github.com/oywq00008-cell/AC-Nexus-OpenWRT)
专为 OpenWRT 路由器重写的 AC-Nexus 版本，拥有原版全部重要功能并保持极致轻量化，专为低性能路由器重新设计代码！

## 🔐 隐私

所有配置本地存储 `~/.ac_controller/`，不上传任何服务器。

## 📜 协议

MIT License

## 💝 致谢

- [python-broadlink](https://github.com/mjg59/python-broadlink) — 博联 RM 驱动
- [python-miio](https://github.com/rytilahti/python-miio) — 米家 MIoT 局域网协议
- [hvac_ir](https://github.com/nicko858/hvac_ir) — 红外协议库
- [IRremoteESP8266](https://github.com/crankyoldgit/IRremoteESP8266) — C++ 协议参考
- [miot-spec.org](https://miot-spec.org) — 米家设备 siid/piid 规格
- [OpenStreetMap](https://www.openstreetmap.org) — 城市搜索（Nominatim）
- [和风天气](https://www.qweather.com) / [百度地图开放平台](https://lbsyun.baidu.com) — 天气数据
- [中国中央气象台](https://www.nmc.cn) — 西北太平洋台风数据
- [美国国家飓风中心](https://www.nhc.noaa.gov) — 北大西洋飓风数据
- [schedule](https://github.com/dbader/schedule) — Python 定时任务库

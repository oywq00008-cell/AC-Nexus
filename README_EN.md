# 🎮 BroadlinkAC v5.0

[中文](README.md) | English

BroadlinkAC is more than a desktop AC remote — it's an **IR control protocol stack built for AI Agents**. Plug in a Broadlink RM IR blaster, and any AI Agent can control **17 AC brands** (Gree, Hitachi, Daikin, etc.) with a single line of Python: `import broadlinkac_core`. **Built-in IR learning** lets you teach the system codes from your original remote for any brand not in the list. Multi-device parallel scheduling, outdoor-temperature-aware auto-adjust, typhoon path forecasting — the desktop app (PySide6) and headless Agent mode share the exact same core. Windows, macOS & Linux, works out of the box.

## 🤖 Agent API

```python
from broadlinkac_core import init, send_ac, get_device_list

# One-time init (auto-persisted to config.json)
init(api_key="your_key", qw_host="https://your_host",
     location={"lat": 22.54, "lon": 114.05, "name": "Shenzhen"})

# Control AC — brand name auto-resolved to IR protocol
send_ac("on", "cool", 26, "auto")                    # current device
send_ac("off", "cool", 26, "auto", mac="e870723f")   # specific device

# Multi-device
for mac, name in get_device_list():
    print(f"{name}: {mac}")

# Storm threat assessment
from broadlinkac_core import typhoon_threat_distance
dist, name = typhoon_threat_distance()
if dist < 100:
    send_ac("off", "cool", 26, "auto", source="typhoon")  # auto-shutdown near storm
```

No GUI needed — `pip install -r requirements-core.txt` is enough.

## 🎯 Supported AC Brands

The core supports all **17 protocols**, now fully available in the desktop dropdown with brand logos.

| Brand (CN) | Brand (EN) | Protocol Source |
|------------|------------|-----------------|
| 格力 | `gree` | hvac_ir |
| 美的 / 华凌 / 小米 | `midea` | hvac_ir |
| 海尔 | `haier` | Custom protocols |
| 奥克斯 | `aux_ac` | Custom protocols |
| 海信 | `hisense` | hvac_ir |
| 大金 | `daikin` | hvac_ir |
| 三菱 | `mitsubishi` | hvac_ir |
| 松下 | `panasonic` | Custom protocols |
| 日立 | `hitachi` | hvac_ir |
| 富士通 | `fujitsu` | hvac_ir |
| 巴鲁 | `ballu` | hvac_ir |
| 开利 | `carriermca` | hvac_ir |
| 现代 | `hyundai` | hvac_ir |
| Fuego | `fuego` | hvac_ir |

Agent can pass either Chinese `brand="日立"` or English `brand="hitachi"` — both resolve automatically.

## ✨ Features

- 📡 **Multi-device** — LAN auto-discovery, dropdown switch, offline label
- 🎓 **IR Learning** — Teach the system codes from your original remote for any unsupported brand, supporting any mode+temp+fan combination
- ⏰ **Schedule templates** — Multi-group timers (workdays vs weekends)
- 🌡️ **Smart temp control** — Adaptive cool/heat based on outdoor temperature; validates custom remote commands when editing rules
- 🌤️ **Dual weather** — Baidu / QWeather API, one-click switch
- 🌀 **Dual storm source** — NW Pacific (NMC) + N. Atlantic hurricanes (NHC), path forecast
- 🌪️ **Storm protection** — Auto-shutdown all ACs when storm < 100km
- ⚠️ **Alerts** — Storm tracking + local weather warnings, split layout
- 🎨 **Dark theme** — Light/dark/system, instant apply
- 📋 **Activity log** — Browse by date
- 🔧 **Diagnostics** — One-click health check

## Screenshot


| main | 
|--------|
 ![主界面](assets/screenshot-main.png) |

| settings | warning |
|--------|----------|
 ![设置](assets/screenshot-settings.png) | ![预警信息](assets/screenshot-typhoon.png) |
 
## 🧰 Hardware

- Python 3.9+ (macOS / Windows / Linux / Raspberry Pi / NAS)
- [Broadlink RM series](https://www.broadlink.com.cn/) IR blaster

## 📡 Deploy on OpenWRT Router

> **[BroadlinkAC-OpenWRT](https://github.com/oywq00008-cell/BroadlinkAC-OpenWRT)** — LuCI control panel + procd daemon + IPK one-click install

Both projects share the core algorithm and IR protocols, evolving independently.

## 🚀 Quick Start

### Desktop App

| Platform | Download |
|----------|----------|
| 🪟 Windows | [BroadlinkAC.exe](https://github.com/oywq00008-cell/BroadlinkAC-For-Agent/releases/latest/download/BroadlinkAC-Windows.zip) |
| 🍎 macOS | [BroadlinkAC.app](https://github.com/oywq00008-cell/BroadlinkAC-For-Agent/releases/latest/download/BroadlinkAC-macOS.zip) |
| 🐧 Linux | [BroadlinkAC-linux](https://github.com/oywq00008-cell/BroadlinkAC-For-Agent/releases/latest/download/BroadlinkAC-linux.tar.gz) |

macOS first run: if you see "unable to verify developer", unzip and open `打不开请看我.txt` first.

From source:
```bash
git clone https://github.com/oywq00008-cell/BroadlinkAC-For-Agent.git
cd BroadlinkAC-For-Agent
pip install -r requirements.txt
python ac_controller_pyside6.py
```

### Agent / Headless

```bash
pip install -r requirements-core.txt
```

```python
from broadlinkac_core import init, send_ac
init()
send_ac("on", "cool", 26, "auto")
```

## ⚙️ Configuration

Fill in weather API key via Settings on first run (Baidu 5k/day or QWeather 50k/mo, free). Broadlink devices auto-discovered on LAN. Agent mode: pass via `init()` or edit `~/.ac_controller/config.json` directly.

## 📁 Project Structure

```
ac_controller_pyside6.py      # PySide6 entry point
broadlinkac_core/             # Core library (zero GUI deps)
├── __init__.py               # Public API
├── config.py                 # Config + resolve_brand() + device mgmt + city search
├── weather.py                # Dual-source weather + alerts
├── typhoon.py                # Storm (NMC) + Hurricane (NHC) + KMZ forecast
├── ac_control.py             # AC control + dynamic protocol import + learned codes
├── ir_learner.py             # IR learning core (learn_one / get_raw_code)
├── scheduler.py              # Scheduling (multi-group templates)
├── autostart.py              # Cross-platform auto-start
└── logger.py                 # Logging
broadlinkac_desktop/          # PySide6 desktop GUI
├── app_pyside6.py            # Main window + global styles
└── pyside/                   # UI modules (6 files)
    ├── ac_tab.py             # AC + Weather + Timer + Rules
    ├── ty_tab.py             # Storm + Alerts + Forecast chart
    ├── theme.py              # Theme engine (light/dark/system)
    ├── settings_dialog.py    # Settings dialog
    ├── schedule_dialog.py    # Schedule template editor
    ├── repair_dialog.py      # Diagnostics
    ├── learn_dialog.py       # IR learning wizard
    ├── dialogs.py            # Base dialogs + rules + typhoon alert
    └── _utils.py             # Utilities
protocols/                    # Custom IR protocols
logos/                        # Brand logos
fonts/                        # Fonts (HarmonyOS Sans SC)
icons/                        # SVG icon system
BroadlinkAC.spec              # Windows build
BroadlinkAC-macOS.spec        # macOS build
BroadlinkAC-linux.spec        # Linux build
requirements.txt              # Full deps
requirements-core.txt         # Agent-only deps
```

## 🔐 Privacy

All config stored locally at `~/.ac_controller/`. Nothing uploaded.

## 📜 License

MIT License

## 💝 Acknowledgments

- [python-broadlink](https://github.com/mjg59/python-broadlink) — Broadlink RM driver
- [hvac_ir](https://github.com/nicko858/hvac_ir) — IR protocol library
- [IRremoteESP8266](https://github.com/crankyoldgit/IRremoteESP8266) — C++ protocol reference
- [QWeather](https://www.qweather.com) / [Baidu Maps](https://lbsyun.baidu.com) — Weather data
- [China NMC](https://www.nmc.cn) — Storm data
- [USA NHC](https://www.nhc.noaa.gov) — Atlantic hurricane data

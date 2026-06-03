# 🎮 BroadlinkAC v3.0

[中文](README.md) | English

Smart AC controller for Broadlink RM series — macOS / Windows desktop app + **AI Agent programmable API**.

> 💡 **Daily auto on/off** · **Smart temperature rules** · **Auto-adjust every 2h** · **Weather alerts + typhoon** · **Zero-setup Agent API**.

```python
from broadlinkac_core import init, send_ac

# One-time setup, auto-persisted to config.json
init(api_key="your_key", qw_host="https://your_host",
     location={"lat": 22.54, "lon": 114.05, "name": "Shenzhen"}, brand="Gree")

send_ac("on", "cool", 26, "auto")   # Turn on · Cool 26°C
send_ac("off", "cool", 26, "auto")  # Turn off
```

## ✨ Features

- 🎯 **Multi-brand** — Gree, Midea, Xiaomi, Haier, AUX, Hisense, Daikin, Mitsubishi, Panasonic
- ⏰ **Scheduled on/off** — Auto power on/off daily
- 🌡️ **Temperature rules** — Smart adjustment based on outdoor temp, fully editable
- 🔄 **Auto-adjust** — Checks outdoor temp every 2h, adjusts AC if rules changed
- 🌤️ **Live weather** — QWeather API: temperature, humidity, feels-like, wind
- ⚠️ **Alerts** — Local weather warnings (heat/rain/wind) + typhoon monitor, color-coded severity
- 📋 **Activity log** — Daily auto-log, searchable
- 🔧 **Diagnostics** — One-click health check
- 🤖 **Agent-ready** — `import` with zero side effects, `init()` to start

### 🕐 Temperature Rules (default)

| Outdoor Temp | Action | Target |
|-------------|--------|--------|
| ≥ 36°C | Cool | 24°C |
| 33-35°C | Cool | 25°C |
| 30-32°C | Cool | 26°C |
| 25-29°C | Cool | 27°C |
| 18-24°C | Off | — |
| ≤ 17°C | Heat | 28°C |

## 🧰 Hardware

- A computer (macOS / Windows / Linux)
- [Broadlink RM series](https://www.broadlink.com.cn/) IR blaster (RM Mini / RM Pro / RM4 Mini etc.)
- Supported AC

## 🚀 Quick Start

### Option 1: Download (recommended)

| Platform | Download |
|----------|----------|
| macOS | [BroadlinkAC.app.zip](https://github.com/oywq00008-cell/BroadlinkAC-For-AI-Agent/releases/latest) |
| Windows | [BroadlinkAC-Windows.zip](https://github.com/oywq00008-cell/BroadlinkAC-For-AI-Agent/releases/latest) |

On macOS, if Gatekeeper blocks:
```bash
xattr -cr /Applications/BroadlinkAC.app
```

### Option 2: Run from source

```bash
git clone https://github.com/oywq00008-cell/BroadlinkAC-For-AI-Agent.git
cd BroadlinkAC
pip install -r requirements.txt
python3 ac_controller.py
```

### Option 3: Agent / Headless (Linux / Raspberry Pi / Server)

```bash
git clone https://github.com/oywq00008-cell/BroadlinkAC-For-AI-Agent.git
cd BroadlinkAC-For-AI-Agent
pip install -r requirements-core.txt
```

```python
from broadlinkac_core import init, send_ac

init(api_key="your_key", qw_host="https://your_host")
send_ac("on", "cool", 26, "auto")
```

No GUI needed — `broadlinkac_core/` is pure Python, runs on Linux / Ubuntu / Debian / Raspberry Pi.

## ⚙️ Configuration

Fill in via the Settings menu on first run:

| Field | Description |
|-------|-------------|
| QWeather API Key | Free from [QWeather Console](https://console.qweather.com) |
| Personal Host | Your API Host URL (for free tier) |
| AC Brand | Select your AC brand |

Broadlink device auto-discovered on LAN. No manual IP config.

## 📁 Project Structure

```
ac_controller.py              # Entry point (19 lines)
broadlinkac_core/             # Core library (no GUI dep)
├── __init__.py               # Public API
├── config.py                 # Config + init()
├── weather.py                # Weather + alerts
├── typhoon.py                # Typhoon monitor
├── ac_control.py             # AC control + IR
├── scheduler.py              # Scheduler + auto-adjust
└── logger.py                 # Logging
broadlinkac_desktop/          # Desktop GUI (cross-platform)
└── app.py                    # CustomTkinter UI
protocols/                    # IR protocols (C++ port)
├── haier.py
├── aux_ac.py                 # AUX (Electra protocol)
└── panasonic.py
requirements.txt
requirements-core.txt         # Headless mode (no GUI deps)
```

## 🔐 Privacy

All config stored locally in `~/.ac_controller/`. Nothing uploaded. Weather and typhoon data fetched directly from official APIs.

## 📜 License

MIT License

## 💝 Acknowledgments

- [IRremoteESP8266](https://github.com/crankyoldgit/IRremoteESP8266) — C++ reference for Haier/AUX/Panasonic IR protocols
- [python-broadlink](https://github.com/mjg59/python-broadlink) — Broadlink RM device Python driver
- [hvac_ir](https://github.com/nicko858/hvac_ir) — Gree/Midea/Hisense/Daikin/Mitsubishi IR protocol library
- [QWeather](https://www.qweather.com) — Weather and alert data
- [China NMC](https://www.nmc.cn) — Typhoon monitoring data

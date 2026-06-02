# 🎮 BroadlinkAC

[中文](README.md) | English

Smart AC controller for Broadlink RM series — macOS desktop app + **AI Agent programmable API**.

> 💡 One app for everything: **daily auto on/off**, **smart temperature rules based on outdoor weather**, **typhoon alerts**, **Agent remote control**. Just plug in a Broadlink RM series IR blaster.

```python
from ac_controller import init, send_ac

# One-time setup — all config persisted to config.json
init(
    api_key="your_qweather_key",
    qw_host="https://xxx.re.qweatherapi.com",
    location={"lat": 22.54, "lon": 114.05, "name": "Shenzhen"},
    brand="Gree",
)

send_ac("on", "cool", 26, "auto")   # Turn on, cool 26°C, auto fan
send_ac("off", "cool", 26, "auto")  # Turn off
```

## ✨ Features

- 🎯 **Multi-brand** — Gree, Midea, Xiaomi, Haier, AUX, Hisense, Daikin, Mitsubishi, Panasonic
- ⏰ **Scheduled on/off** — Auto power on/off at set times daily
- 🌡️ **Temperature rules** — Smart adjustment based on outdoor temp: e.g. ≥36°C → cool 24°C, 25-29°C → cool 27°C, 18-24°C → do nothing, ≤17°C → heat 28°C. Rules fully editable
- 🌤️ **Live weather** — QWeather API: temperature, humidity, feels-like, wind
- 🌀 **Typhoon monitor** — China NMC data, real-time tracking, distance alerts
- 📋 **Activity log** — Daily auto-log of on/off, temp changes, typhoon updates
- 🔧 **Diagnostics** — One-click health check, auto-install missing deps
- 🤖 **Agent-ready** — `import` with zero side effects, `init()` to start. Works with OpenAI, Claude, Hermes, OpenCalw, etc.

### 🕐 Temperature Rules (default)

| Outdoor Temp | Action | Target |
|-------------|--------|--------|
| ≥ 36°C | Cool | 24°C |
| 33-35°C | Cool | 25°C |
| 30-32°C | Cool | 26°C |
| 25-29°C | Cool | 27°C |
| 18-24°C | Off | — |
| ≤ 17°C | Heat | 28°C |

At trigger time each day, the app checks outdoor temperature and decides whether to turn on and to what setting. Also supports a separate timed shutdown (e.g. 22:00 daily).

## 🧰 Hardware

- A Mac (Apple Silicon / Intel)
- [Broadlink RM series](https://www.broadlink.com.cn/) IR blaster (RM Mini / RM Pro / RM4 Mini etc.)
- Air conditioner (supported brands listed above)

## 🚀 Quick Start

### Option 1: Download .app (recommended)

Download `BroadlinkAC.app` from [Releases](https://github.com/oywq00008-cell/BroadlinkAC/releases), drag to Applications, double-click.

If Gatekeeper blocks it:
```bash
xattr -cr /Applications/BroadlinkAC.app
```

### Option 2: Run from source

```bash
git clone https://github.com/oywq00008-cell/BroadlinkAC.git
cd BroadlinkAC
pip install -r requirements.txt
python3 ac_controller.py
```

### Option 3: Agent auto control

```bash
git clone https://github.com/oywq00008-cell/BroadlinkAC.git
cd BroadlinkAC
pip install -r requirements.txt
```

Then any AI Agent can `import ac_controller` and control the AC directly:

```python
from ac_controller import init, send_ac

init(api_key="your_key", qw_host="https://your_host")
send_ac("on", "cool", 26, "auto")
```

No manual file editing needed — pass everything through `init()` parameters, auto-persisted to config.json.

## ⚙️ Configuration

Fill in via the Settings menu on first run:

| Field | Description |
|-------|-------------|
| QWeather API Key | Free from [QWeather Console](https://console.qweather.com) |
| Personal Host | Your API Host URL (for free tier) |
| AC Brand | Select your AC brand |

The Broadlink device is auto-discovered on the LAN. No manual IP config needed.

## 📁 Project Structure

```
ac_controller.py          # Main program (customtkinter GUI + programmable API)
protocols/
├── haier.py              # Haier protocol (ported from IRremoteESP8266 C++)
├── aux.py                # AUX protocol
└── panasonic.py          # Panasonic protocol
requirements.txt          # Python dependencies
```

## 🔐 Privacy

All config (API key, city, rules) stored locally in `~/.ac_controller/`. Nothing uploaded. Weather and typhoon data fetched directly from official APIs.

## 📜 License

MIT License

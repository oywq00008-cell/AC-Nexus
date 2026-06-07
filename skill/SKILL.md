---
name: broadlinkac
version: 3.1.1
description: Control air conditioners via Broadlink RM devices — 16 AC brands, dual weather source (Baidu/QWeather), dual typhoon source (NMC/NHC), scheduled automation, auto-adjust, threat alerts. Clone, pip install, import — zero-config Agent API.
---

# BroadlinkAC — AI Agent Smart AC Controller

Cross-platform AC control library for Broadlink RM series IR blasters. **Zero GUI dependency** — designed for AI agents to clone, install, and control air conditioners programmatically.

## Quick Start (Agent)

```bash
git clone https://github.com/oywq00008-cell/BroadlinkAC-For-Agent.git
cd BroadlinkAC-For-Agent
pip install -r requirements-core.txt
```

```python
from broadlinkac_core import init, send_ac, fetch_weather

# One-time setup — all config persisted
init(
    baidu_key="your_baidu_key",       # Baidu weather (default)
    # or use QWeather:
    # api_key="your_qw_key", qw_host="https://xxx.re.qweatherapi.com",
    location={"lat": 22.54, "lon": 114.05, "name": "Shenzhen"},
    brand="Gree"
)

# Control AC
send_ac("on", "cool", 26, "auto")     # Turn on, cool 26°C, auto fan
send_ac("off", "cool", 26, "auto")    # Turn off

# Weather — dual source (Baidu default, falls back to QWeather)
weather = fetch_weather()              # Real-time temp, humidity, feels-like

# Typhoon threat — returns (distance_km, storm_name)
from broadlinkac_core import typhoon_threat_distance
dist, name = typhoon_threat_distance()
if dist < 100:
    send_ac("off", "cool", 26, "auto")  # Storm protection: auto-shutdown
```

## API Reference

### Setup
| Function | Description |
|----------|-------------|
| `init(baidu_key=None, api_key=None, qw_host=None, location=None, brand=None)` | Initialize config + start background scheduler |

### AC Control (16 brands)
| Function | Description |
|----------|-------------|
| `send_ac(power, mode, temp, fan)` | Send IR command. `power`: `"on"`/`"off"`. `mode`: `"cool"`/`"heat"`/`"dry"`/`"fan"`/`"auto"`. `temp`: 16-30. `fan`: `"auto"`/`"1"`/`"2"`/`"3"` |
| `decide_ac(outdoor_temp)` | Run temperature rules → returns `(target_temp, mode)` |
| `get_device()` | Get connected Broadlink device |

> **Extending `send_ac` for advanced features**: `send_ac` intentionally covers only the minimum common set (power/mode/temp/fan) that works on **all** AC brands. If your specific AC supports turbo, swing, eco, sleep, etc., your Agent can modify `broadlinkac_core/ac_control.py` to add optional parameters (`turbo=True`, `swing_v="swing"`, etc.) and pass them through to the underlying protocol. Back up the file before editing — changes are local and won't affect the core library.

### Weather & Alerts (Dual Source)
| Function | Description |
|----------|-------------|
| `fetch_weather()` | Current weather — auto-routes via Baidu/QWeather based on config |
| `fetch_weather_alerts()` | Local weather warnings — `[{headline, severity, description, ...}]` |

### Typhoon & Hurricane (Dual Source: NMC + NHC)
| Function | Description |
|----------|-------------|
| `fetch_typhoons()` | Active storms from NMC (NW Pacific) or NHC (Atlantic, configurable) |
| `fetch_typhoon_detail(typhoon_id)` | Detailed track + forecast points |
| `typhoon_threat_distance()` | **Agent-critical**: nearest storm distance (km) + name. < 100km = should shutdown |
| `calc_distance(lat1, lon1, lat2, lon2)` | Haversine distance |

### Logger
| Function | Description |
|----------|-------------|
| `write_log(category, msg)` | Append daily operation log |
| `read_log(date_str)` | Read log by date |
| `get_log_dates()` | List dates with logs |

## Supported AC Brands (16)

**hvac_ir:** Gree, Midea, Hisense, Daikin, Mitsubishi, Hitachi, Fujitsu, Ballu, Carrier MCA, Hyundai, Fuego

**Custom protocols:** Haier, AUX, Panasonic (ported from IRremoteESP8266 C++)

**Multi-brand mappings:** Xiaomi, Hualing → Midea protocol

Select in Settings or pass `brand=` to `init()`. Supports English names too (`"hitachi"`, `"fujitsu"`, etc.).

## Weather Providers

| Provider | Endpoint | Daily Calls | Features |
|----------|----------|-------------|----------|
| Baidu | `api.map.baidu.com` (default) | 5,000 | Real-time + 7-day forecast + hourly + alerts + AQI |
| QWeather | Personal Host | 50,000/month | Real-time + forecast + alerts (personal host required) |

Agent can read/write provider via `_cfg.config["weather_provider"]` and `_cfg.config["baidu_key"]`.

## Key Design

- `import broadlinkac_core` has **zero side effects** — no I/O, no threads
- `init()` is idempotent — safe to call multiple times
- Config auto-persisted to `~/.ac_controller/config.json`
- Runs on any device with Python 3.9+ (macOS/Windows/Linux/Raspberry Pi)
- `typhoon_threat_distance()` never throws — returns `(99999, "")` on any error
- `_fetch_all()` auto-retries on network failure

## Common Agent Tasks

### "Is there a typhoon nearby? Should I turn off the AC?"
```python
from broadlinkac_core import init, typhoon_threat_distance, send_ac
init()
dist, name = typhoon_threat_distance()
if dist < 100:
    send_ac("off", "cool", 26, "auto")
    print(f"⚠️ {name} only {dist}km away — AC shut down for safety")
```

### "Turn on the AC and auto-adjust based on outdoor temperature"
```python
from broadlinkac_core import init, fetch_weather, decide_ac, send_ac
init()
w = fetch_weather()
if w:
    target, mode = decide_ac(float(w["temp"]))
    send_ac("on", mode, target, "auto")
```

### "What's the weather and are there any alerts?"
```python
from broadlinkac_core import init, fetch_weather, fetch_weather_alerts
init()
w = fetch_weather()
alerts, provider = fetch_weather_alerts()
for a in alerts:
    print(f"[{a['severity']}] {a['headline']}")
```

## Desktop GUI

Pre-built installers for all platforms, auto-built by GitHub Actions:
- 🍎 macOS `.app` — double-click to run
- 🪟 Windows `.exe` — double-click to run
- 🐧 Linux `.tar.gz` — extract and run

Download from [Releases](https://github.com/oywq00008-cell/BroadlinkAC-For-Agent/releases/latest).

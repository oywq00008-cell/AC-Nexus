"""BroadlinkAC Core — 天气与城市搜索"""

import json
import gzip
import ssl
import urllib.request
import urllib.parse
import broadlinkac_core.config as _cfg


def _urlopen(url, timeout=8):
    """兼容 Windows：绕过自签名证书验证"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": "BroadlinkAC/2.0"})
    return urllib.request.urlopen(req, timeout=timeout, context=ctx)


def fetch_weather():
    """获取实况天气（根据 provider 路由，未明确指定时降级）"""
    provider = _cfg.config.get("weather_provider", "baidu")
    if provider == "baidu":
        result = _fetch_weather_baidu()
        if result is not None or _cfg.config.get("weather_provider_set", False):
            return result
        # 未明确设置 → 回退和风
        return _fetch_weather_qweather()
    return _fetch_weather_qweather()


def city_lookup(query: str):
    """OpenStreetMap 搜索 → [{name, display, lat, lon}, ...]"""
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
        "q": query, "format": "json", "limit": 8,
        "accept-language": "zh", "countrycodes": "cn"
    })
    try:
        raw = _urlopen(url).read()
        data = json.loads(raw)
        return [{
            "name": r.get("name", ""),
            "display": r.get("display_name", ""),
            "lat": float(r["lat"]), "lon": float(r["lon"]),
        } for r in data]
    except Exception as e:
        print(f"[Nominatim] {e}")
    return []


def fetch_weather_alerts():
    """获取当地天气预警 → (数据列表, 实际数据源)
    未明确指定时降级：百度无预警则回退和风。
    """
    provider = _cfg.config.get("weather_provider", "baidu")
    if provider == "baidu":
        result = _fetch_weather_alerts_baidu()
        if result or _cfg.config.get("weather_provider_set", False):
            return result, "baidu"
        result = _fetch_weather_alerts_qweather()
        return result, "qweather" if result else "baidu"
    result = _fetch_weather_alerts_qweather()
    return result, "qweather" if result else "baidu"


def _fetch_weather_baidu():
    """百度实况 → 标准化字段"""
    key = _cfg.config.get("baidu_key", "")
    if not key:
        return None
    lat = _cfg.LOCATION["lat"]
    lon = _cfg.LOCATION["lon"]
    url = (f"https://api.map.baidu.com/weather/v1/?"
           f"location={lon},{lat}&coordtype=wgs84&data_type=now&ak={key}")
    try:
        raw = _urlopen(url).read()
        data = json.loads(raw)
        if data.get("status") == 0:
            n = data["result"]["now"]
            return {
                "temp": str(n["temp"]),
                "text": n["text"],
                "humidity": str(n["rh"]),
                "windDir": n["wind_dir"],
                "windScale": n["wind_class"].replace("级", ""),
                "feelsLike": str(n["feels_like"]),
                "obsTime": n.get("uptime", ""),
            }
    except Exception as e:
        print(f"[百度实况] {e}")
    return None


def _fetch_weather_alerts_baidu():
    """百度预警 → [{headline, severity, description, ...}]"""
    key = _cfg.config.get("baidu_key", "")
    if not key:
        return []
    lat = _cfg.LOCATION["lat"]
    lon = _cfg.LOCATION["lon"]
    url = (f"https://api.map.baidu.com/weather/v1/?"
           f"location={lon},{lat}&coordtype=wgs84&data_type=alert&ak={key}")
    try:
        raw = _urlopen(url).read()
        data = json.loads(raw)
        if data.get("status") == 0:
            alerts = []
            for a in data["result"].get("alerts", []):
                sev_map = {"蓝色预警": "minor", "黄色预警": "moderate",
                           "橙色预警": "severe", "红色预警": "extreme"}
                alerts.append({
                    "headline": a.get("title", ""),
                    "severity": sev_map.get(a.get("level", ""), "minor"),
                    "description": a.get("desc", ""),
                    "senderName": a.get("type", "") + "预警",
                    "effectiveTime": "", "expireTime": "",
                })
            return alerts
    except Exception as e:
        print(f"[百度预警] {e}")
    return []


def _fetch_weather_qweather():
    """和风实况 → 原始格式"""
    url = f"{_cfg.QW_HOST}/v7/weather/now?location={_cfg.LOCATION['lon']},{_cfg.LOCATION['lat']}&key={_cfg.QW_KEY}"
    try:
        raw = _urlopen(url).read()
        data = json.loads(gzip.decompress(raw))
        if data["code"] == "200":
            return data["now"]
    except Exception as e:
        print(f"[和风天气] {e}")
    return None


def _fetch_weather_alerts_qweather():
    """和风预警 → 原始格式"""
    host = _cfg.QW_HOST
    key = _cfg.QW_KEY
    if not host or not key:
        return []
    lat = _cfg.LOCATION["lat"]
    lon = _cfg.LOCATION["lon"]
    url = f"{host}/weatheralert/v1/current/{lat:.2f}/{lon:.2f}?key={key}"
    try:
        raw = _urlopen(url).read()
        data = json.loads(gzip.decompress(raw))
        return data.get("alerts", [])
    except Exception as e:
        print(f"[和风预警] {e}")
    return []

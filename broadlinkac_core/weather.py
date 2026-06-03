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
    url = f"{_cfg.QW_HOST}/v7/weather/now?location={_cfg.LOCATION['lon']},{_cfg.LOCATION['lat']}&key={_cfg.QW_KEY}"
    try:
        raw = _urlopen(url).read()
        data = json.loads(gzip.decompress(raw))
        if data["code"] == "200":
            return data["now"]
    except Exception as e:
        print(f"[天气] {e}")
    return None


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
    """获取当地天气预警"""
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
        print(f"[天气预警] {e}")
    return []

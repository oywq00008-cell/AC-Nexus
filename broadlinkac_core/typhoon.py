"""BroadlinkAC Core — 台风监测"""

import json
import math
import re
import ssl
import urllib.request
from datetime import datetime

NMC_HOST = "https://typhoon.nmc.cn/weatherservice"


def _urlopen(url, timeout=8):
    """兼容 Windows：绕过自签名证书验证"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": "BroadlinkAC/2.0"})
    return urllib.request.urlopen(req, timeout=timeout, context=ctx)


def fetch_typhoons():
    year = datetime.now().year
    url = f"{NMC_HOST}/typhoon/jsons/list_{year}?callback=cb"
    try:
        resp = _urlopen(url).read().decode("utf-8")
        body = re.search(r'\((.*)\)', resp, re.DOTALL)
        if not body:
            return []
        data = json.loads(body.group(1))
        active = []
        for t in data.get("typhoonList", []):
            if t[7] == "start":
                active.append({
                    "id": t[0], "eng": t[1], "cn": t[2],
                    "code": str(t[3]), "meaning": t[6] or ""
                })
        return active
    except Exception as e:
        print(f"[台风列表] {e}")
    return []


def fetch_typhoon_detail(ty_id):
    url = f"{NMC_HOST}/typhoon/jsons/view_{ty_id}?callback=cb"
    try:
        resp = _urlopen(url).read().decode("utf-8")
        body = re.search(r'\((.*)\)', resp, re.DOTALL)
        if not body:
            return None
        data = json.loads(body.group(1))
        t = data.get("typhoon", [])
        if not t:
            return None
        if len(t) < 9:
            return None
        pts = t[8]
        if not pts:
            return None
        latest = pts[-1]
        forecast_raw = latest[11]
        if not isinstance(forecast_raw, dict):
            forecast_raw = {}
        forecasts = []
        if "BABJ" in forecast_raw:
            for f in forecast_raw["BABJ"]:
                forecasts.append({
                    "hours": f[0], "lon": f[2], "lat": f[3],
                    "pressure": f[4], "wind": f[5], "cat": f[6]
                })

        def cat_name(c):
            return {"TD": "热带低压", "TS": "热带风暴", "STS": "强热带风暴",
                    "TY": "台风", "STY": "强台风", "SuperTY": "超强台风"}.get(c, c)

        return {
            "cn": t[2], "eng": t[1], "code": str(t[3]),
            "cat": cat_name(latest[3]),
            "lon": latest[4], "lat": latest[5],
            "pressure": latest[6], "wind": latest[7],
            "direction": latest[8], "speed": latest[9],
            "update_time": latest[1],
            "forecasts": forecasts,
        }
    except Exception as e:
        print(f"[台风详情] {e}")
    return None


def calc_distance(lat1, lon1, lat2, lon2):
    """Haversine 距离 (km)"""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

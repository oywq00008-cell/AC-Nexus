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
                cn = t[2]
                eng = t[1]
                if cn == "nameless":
                    cn = "尚未编号"
                if eng == "nameless":
                    eng = "尚未编号"
                active.append({
                    "id": t[0], "eng": eng, "cn": cn,
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

        cn = t[2]
        eng = t[1]
        if cn == "nameless":
            cn = "尚未编号"
        if eng == "nameless":
            eng = "尚未编号"

        return {
            "cn": cn, "eng": eng, "code": str(t[3]),
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


# ── NHC 飓风数据源 ──

NHC_CAT = {"TD": "热带低压", "TS": "热带风暴", "HU": "飓风", "PTC": "后热带气旋"}
DIRS = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]


def fetch_nhc_storms():
    """拉取 NHC 活跃飓风，归一化为与 NMC 相同的 _typhoons_data 格式"""
    try:
        req = urllib.request.Request(
            "https://www.nhc.noaa.gov/CurrentStorms.json",
            headers={"User-Agent": "BroadlinkAC/3.0"}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[NHC] 请求失败: {e}")
        return []

    results = []
    for s in data.get("activeStorms", []):
        try:
            kt = int(s["intensity"])
            wind_ms = round(kt * 0.514)
            wind_kmh = round(kt * 1.852)
            move_spd = round(int(s["movementSpeed"]) * 1.852)
            move_dir = DIRS[round(int(s["movementDir"]) / 45) % 8]
            update = s["lastUpdate"].replace("T", " ").replace("Z", "").split(".")[0]

            results.append({
                "id": s["id"], "eng": s["name"], "cn": s["name"],
                "code": s["binNumber"], "meaning": "",
                "detail": {
                    "cn": s["name"], "eng": s["name"],
                    "cat": NHC_CAT.get(s["classification"], s["classification"]),
                    "lat": s["latitudeNumeric"], "lon": s["longitudeNumeric"],
                    "pressure": int(s["pressure"]), "wind": wind_ms,
                    "direction": f"{move_dir} ({s['movementDir']}°)",
                    "speed": move_spd,
                    "update_time": update,
                    "forecasts": [],  # NHC 预报在 KMZ 文件里，不解析
                }
            })
        except Exception as e:
            print(f"[NHC] 解析 {s.get('name', '?')} 失败: {e}")
    return results

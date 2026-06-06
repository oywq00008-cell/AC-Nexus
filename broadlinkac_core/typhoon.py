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


def typhoon_threat_distance(provider=None):
    """评估最近风暴/飓风距离 (km)。
    Agent 可直接调用：<100km 即应关机。返回 (距离, 名称)。
    provider 不传则走 config 当前设置。
    任何异常均返回 (99999, "")，不抛异常。
    """
    import broadlinkac_core.config as _cfg
    try:
        provider = provider or _cfg.config.get("typhoon_provider", "nmc")
        lat = _cfg.LOCATION["lat"]
        lon = _cfg.LOCATION["lon"]
        min_dist, name = 99999, ""

        if provider == "nhc":
            storms = fetch_nhc_storms()
            for s in storms:
                d = s.get("detail", {})
                if d:
                    dist = calc_distance(lat, lon, d["lat"], d["lon"])
                    if dist < min_dist:
                        min_dist, name = dist, d["cn"]
        else:
            for t in fetch_typhoons():
                d = fetch_typhoon_detail(t["id"])
                if d:
                    dist = calc_distance(lat, lon, d["lat"], d["lon"])
                    if dist < min_dist:
                        min_dist, name = dist, d["cn"]
        return min_dist, name
    except Exception as e:
        print(f"[威胁评估] {e}")
        return 99999, ""


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
                    "cn": s["name"], "eng": s["name"], "code": s["binNumber"],
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


# ── 台风缓存与调度 ──
_ty_cache = []


def fetch_and_cache():
    global _ty_cache
    try:
        import broadlinkac_core.config as _cfg
        provider = _cfg.config.get("typhoon_provider", "nmc")
        _ty_cache = []
        if provider == "nhc":
            _ty_cache = fetch_nhc_storms()
        else:
            for t in fetch_typhoons():
                d = fetch_typhoon_detail(t["id"])
                if d:
                    _ty_cache.append({
                        "id": t["id"], "eng": t["eng"], "cn": t["cn"],
                        "code": t.get("code", ""), "meaning": t.get("meaning", ""),
                        "detail": d
                    })
    except Exception as e:
        _ty_cache = []
        print(f"[台风缓存] {e}")


def get_cached():
    return _ty_cache


def judge_and_shutdown(write_log_func, ty_alert_muted=False, ty_ac_off_sent=False):
    alerts = []
    min_dist = 99999
    import broadlinkac_core.config as _cfg

    alert_km = _cfg.config.get("typhoon_alert_km", 800)
    alert_enabled = _cfg.config.get("typhoon_alert_enabled", True)
    ac_off_enabled = _cfg.config.get("typhoon_ac_off", True)
    loc_lat = _cfg.LOCATION["lat"]
    loc_lon = _cfg.LOCATION["lon"]

    for t in _ty_cache:
        detail = t.get("detail")
        if not detail:
            continue
        dist = calc_distance(loc_lat, loc_lon, detail["lat"], detail["lon"])
        status = "⚠️ 预警" if dist < alert_km else "✅ 安全"
        write_log_func("台风", f"{detail['cn']} ({detail['eng']}) {detail['cat']} 距{dist}km {status}")
        if dist < min_dist:
            min_dist = dist
        if dist < alert_km and alert_enabled and not ty_alert_muted:
            alerts.append((detail, dist))

    if ac_off_enabled and min_dist < 100 and not ty_ac_off_sent:
        ty_ac_off_sent = True
        from broadlinkac_core.ac_control import send_ac
        devices = _cfg.config.get("devices", {})
        offline_count = off_count = 0
        for mac, dev in devices.items():
            name = dev.get("name", mac[:8])
            online = not _cfg._online_macs or mac in _cfg._online_macs
            if not online:
                offline_count += 1
                continue
            try:
                send_ac("off", "cool", 26, "auto", source="台风", mac=mac)
                write_log_func("空调", f"[{datetime.now():%H:%M}] 台风靠近（距{min_dist}km）→ [{name}] 已自动关机")
                off_count += 1
            except Exception as e:
                write_log_func("系统", f"台风关机失败 [{name}]: {e}")
        write_log_func("系统", f"[{datetime.now():%H:%M}] 台风自动关机完成: 关闭 {off_count} 台, 离线 {offline_count} 台")
    elif min_dist >= 100:
        ty_ac_off_sent = False

    return alerts, ty_ac_off_sent

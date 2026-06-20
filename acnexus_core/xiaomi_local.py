"""MIoT 局域网协议发送器 — 通用 siid/piid 映射 + miot-spec 动态匹配"""

from pathlib import Path
from miio import Device

# ── 硬编码兜底（大多数设备通用）──
_POWER = (3, 1)
_MODE  = (3, 2)
_TEMP  = (3, 4)
_FAN   = (4, 2)

_MODES = {"cool": 0, "dry": 4, "fan": 3, "auto": 2}
_FANS  = {"auto": 0, "1": 1, "2": 2, "3": 3}


def fetch_miot_spec(model: str) -> dict | None:
    """从 miot-spec.org 拉取设备的 siid/piid 映射。失败返回 None。
    索引文件本地缓存 7 天，避免每次下载 2.7 MB。"""
    import json, urllib.request, urllib.parse, ssl, time, os
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        # 1. 索引缓存
        cache_dir = Path.home() / ".ac_controller"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / "miot_instances.txt"
        cache_ttl = 7 * 86400  # 7 天

        instances = None
        if cache_file.exists():
            age = time.time() - os.path.getmtime(str(cache_file))
            if age < cache_ttl:
                instances = cache_file.read_text(encoding="utf-8")

        if instances is None:
            url = "https://miot-spec.org/miot-spec-v2/instances?status=all"
            req = urllib.request.Request(url, headers={"User-Agent": "AC-Nexus"})
            resp = urllib.request.urlopen(req, timeout=30, context=ctx)
            raw = json.loads(resp.read()).get("instances", [])
            # 清洗为 model|type 行式缓存 + 内存 dict
            lines = []
            instances = {}
            for i in raw:
                if i.get("model") and i.get("type"):
                    lines.append(f"{i['model']}|{i['type']}")
                    instances[i["model"]] = i["type"]
            cache_file.write_text("\n".join(lines), encoding="utf-8")

        # 解析行式缓存：model|type
        if isinstance(instances, str):
            parsed = {}
            for line in instances.splitlines():
                line = line.strip()
                if "|" in line:
                    m, t = line.split("|", 1)
                    parsed[m] = t
            instances = parsed

        # 2. 查 model → type urn
        urn = instances.get(model)
        if not urn:
            return None

        # 2. 拉 spec JSON
        url = f"https://miot-spec.org/miot-spec-v2/instance?type={urllib.parse.quote(urn)}"
        req = urllib.request.Request(url, headers={"User-Agent": "AC-Nexus"})
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        spec = json.loads(resp.read())

        # 3. 提取 AC 相关 siid/piid
        result = {}
        for svc in spec.get("services", []):
            svc_desc = (svc.get("description") or "").lower()
            svc_type = (svc.get("type") or "").lower()
            siid = svc["iid"]

            # Air Conditioner 服务: 开关 / 模式 / 温度
            if "air-conditioner" in svc_type or "air conditioner" in svc_desc:
                for prop in svc.get("properties", []):
                    desc = (prop.get("description") or "").lower()
                    ptype = (prop.get("type") or "").lower()
                    piid = prop["iid"]
                    if "switch" in desc or (("on" in desc or "off" in desc) and "switch" in ptype):
                        if "sleep" not in desc and "fault" not in desc:
                            result["power"] = {"siid": siid, "piid": piid}
                    elif "mode" in desc and "sleep" not in desc:
                        if "temperature" not in desc and "temp" not in desc:
                            result["mode"] = {"siid": siid, "piid": piid}
                    elif "temperature" in desc or "temp" in desc:
                        result["temp"] = {"siid": siid, "piid": piid}

            # Fan Control 服务: 风速
            if "fan" in svc_type or "fan" in svc_desc:
                for prop in svc.get("properties", []):
                    desc = (prop.get("description") or "").lower()
                    if "fan" in desc or "level" in desc:
                        result["fan"] = {"siid": siid, "piid": prop["iid"]}
                        break

        # 写入日志（部分匹配时提示缺少哪项）
        all_keys = {"power", "mode", "temp", "fan"}
        missing = all_keys - set(result.keys())
        if missing:
            from acnexus_core.logger import write_log
            write_log("系统", f"[{model}] MIoT spec 部分匹配，缺少: {', '.join(sorted(missing))}，已用硬编码补全")
        return result
    except Exception:
        return None


def build_miot_cmds(power: str, mode: str, temp: int, fan: str,
                    model: str = "", spec: dict | None = None) -> list:
    """构建 MIoT set_properties 指令列表。
    spec 为 fetch_miot_spec() 的返回值，有则优先，否则用硬编码兜底。
    """
    def _get(key):
        if spec and key in spec:
            return spec[key]["siid"], spec[key]["piid"]
        return {"power": _POWER, "mode": _MODE, "temp": _TEMP, "fan": _FAN}[key]

    if power == "off":
        siid, piid = _get("power")
        return [{"siid": siid, "piid": piid, "value": False}]

    cmds = []
    siid, piid = _get("power")
    cmds.append({"siid": siid, "piid": piid, "value": True})

    siid, piid = _get("mode")
    cmds.append({"siid": siid, "piid": piid, "value": _MODES.get(mode, 0)})

    siid, piid = _get("temp")
    cmds.append({"siid": siid, "piid": piid, "value": min(max(temp, 16), 30)})

    siid, piid = _get("fan")
    cmds.append({"siid": siid, "piid": piid, "value": _FANS.get(fan, 0)})

    return cmds


def send_miot(host: str, token: str, cmds: list) -> list:
    """通过局域网 MIoT 发送指令"""
    d = Device(host, token)
    return d.send("set_properties", cmds)

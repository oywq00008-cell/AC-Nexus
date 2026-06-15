"""红外学习与自定义码库管理 (v2: 全局码库 + 自由组合学习)"""
import json
import time
from pathlib import Path

import broadlink

CUSTOM_CODES_FILE = Path.home() / ".ac_controller" / "custom_codes.json"


def learn_one(host, timeout=45):
    """让博联设备进入学习模式，等待红外信号。返回 raw hex 或 None"""
    d = broadlink.hello(host)
    d.auth()
    d.enter_learning()
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(0.3)
        try:
            data = d.check_data()
            if data:
                return data.hex()
        except Exception:
            pass
    return None


def load_custom_codes():
    if CUSTOM_CODES_FILE.exists():
        return json.loads(CUSTOM_CODES_FILE.read_text(encoding="utf-8"))
    return {}


def save_custom_codes(data):
    CUSTOM_CODES_FILE.parent.mkdir(parents=True, exist_ok=True)
    CUSTOM_CODES_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def list_custom():
    """返回所有自定义设备名列表"""
    return list(load_custom_codes().keys())


def save_learned_codes(name, logo, code_map):
    """保存学习结果（合并模式）。code_map: {组合名: raw_hex}"""
    all_codes = load_custom_codes()
    existing = all_codes.get(name, {})
    existing["logo"] = logo
    existing["learned_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    merged = existing.get("codes", {})
    merged.update(code_map)
    existing["codes"] = merged
    all_codes[name] = existing
    save_custom_codes(all_codes)


def get_raw_code(name, power, mode, temp, fan):
    """从全局码库取匹配的 raw hex"""
    all_codes = load_custom_codes()
    entry = all_codes.get(name)
    if not entry:
        return None
    codes = entry.get("codes", {})

    if power == "off":
        if "关机" in codes:
            return codes["关机"]
        return None

    mode_map = {"cool": "制冷", "heat": "制热", "fan_only": "送风", "dry": "除湿", "auto": "自动"}
    fan_map = {"auto": "自动", "1": "低", "2": "中", "3": "高"}
    mode_ch = mode_map.get(mode, "制冷")
    fan_ch = fan_map.get(str(fan), "自动")

    for suffix in [f"开机_{mode_ch}_{temp}°C_{fan_ch}", f"开机_{mode_ch}_{temp}°C_自动"]:
        if suffix in codes:
            return codes[suffix]
    return None

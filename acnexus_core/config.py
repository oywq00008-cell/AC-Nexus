"""AC-Nexus Core — 配置与初始化

所有共享状态集中管理：config 字典、QW_KEY、QW_HOST、LOCATION、AC_BRAND、_cached_temp。
"""

import json
import threading
from pathlib import Path

# ── 路径常量 ──
APP_DIR = Path.home() / ".ac_controller"
CONFIG_FILE = APP_DIR / "config.json"
LOG_DIR = APP_DIR / "logs"

# ── 运行时全局 ──
LOCATION = {"lat": 39.90, "lon": 116.40, "name": "北京"}
QW_KEY = ""
QW_HOST = ""  # 从 config 加载
AC_BRAND = "gree"

# ── 品牌映射（中文/英文 → hvac_ir 或 protocols 模块名）──
AC_BRANDS = {
    "格力": "gree", "美的": "midea", "海尔": "haier", "华凌": "midea",
    "奥克斯": "aux_ac", "海信": "hisense", "大金": "daikin", "三菱": "mitsubishi",
    "小米": "midea", "松下": "panasonic",
    "日立": "hitachi", "富士通": "fujitsu", "巴鲁": "ballu",
    "开利": "carriermca", "现代": "hyundai", "Fuego": "fuego",
}


def resolve_brand(raw):
    """将任意品牌名（中文/英文）解析为协议模块名。
    查 AC_BRANDS → 尝试直接当模块名 → 回退 gree。
    """
    if not raw:
        return "gree"
    key = AC_BRANDS.get(raw) or AC_BRANDS.get(raw.lower()) or AC_BRANDS.get(raw.capitalize())
    if key:
        return key
    # 英文名直接当 hvac_ir 模块名用（如 "hitachi" / "Hitachi"）
    return raw.lower() if raw.isascii() else "gree"

# ── 默认规则 ──
DEFAULT_RULES = [
    (36, 99, 24, "cool"),
    (33, 35, 25, "cool"),
    (30, 32, 26, "cool"),
    (25, 29, 27, "cool"),
    (18, 24, 0, "off"),
    (0, 17, 28, "heat"),
]

config = None  # 由 init() 设置

_save_lock = threading.Lock()  # 线程安全：保护 save_config 写盘


def load_config():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {
        "current_device_mac": "",
        "current_brand_type": "broadlink",
        "devices": {},
        "typhoon_alert_km": 800,
        "typhoon_alert_enabled": True,
        "typhoon_ac_off": True,
        "typhoon_provider": "nmc",
        "api_key": "",
        "qw_host": "",
        "location": dict(LOCATION),
        "appearance_mode": "system",
        "baidu_key": "",
        "weather_provider": "baidu",
        "weather_provider_set": False,
    }


def save_config(cfg, sync_device=True):
    """保存配置。sync_device=True 时先把扁平键写回当前设备"""
    with _save_lock:
        if sync_device:
            mac = cfg.get("current_device_mac", "")
            provider = cfg.get("current_brand_type", "broadlink")
            if mac and mac in cfg.get("devices", {}).get(provider, {}):
                dev = cfg["devices"][provider][mac]
                for k in DEVICE_KEYS:
                    if k in cfg:
                        dev[k] = cfg[k]
        tmp = CONFIG_FILE.with_suffix('.tmp')
        tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(CONFIG_FILE)


def apply_config():
    """将 config 同步到运行时全局变量"""
    global QW_KEY, QW_HOST, LOCATION, AC_BRAND
    QW_KEY = config.get("api_key") or config.get("qweather_key", "")
    QW_HOST = config.get("qw_host") or config.get("qweather_host", "")
    if QW_HOST and not QW_HOST.startswith("http"):
        QW_HOST = "https://" + QW_HOST
    LOCATION = config.get("location", {"lat": 39.90, "lon": 116.40, "name": "北京"})
    dev = get_current_device()
    AC_BRAND = resolve_brand(dev.get("brand", "格力"))


def get_current_device():
    """返回当前选中设备的配置字典（可能为空 {}）"""
    mac = config.get("current_device_mac", "")
    provider = config.get("current_brand_type", "broadlink")
    return config.get("devices", {}).get(provider, {}).get(mac, {})


def find_device(mac):
    """按 MAC 在所有 provider 中查找设备，返回 (provider, device_dict)。
    找不到返回 ("broadlink", {})。"""
    for provider, devs in config.get("devices", {}).items():
        if not isinstance(devs, dict):
            continue
        if mac in devs:
            return provider, devs[mac]
    return "broadlink", {}


def get_device_list(brand_type=None):
    """返回设备列表 [(device_id, name), ...]。brand_type 筛选品牌类型。"""
    if brand_type:
        devs = config.get("devices", {}).get(brand_type, {})
    else:
        devs = {}
        for provider in config.get("devices", {}):
            devs.update(config["devices"][provider])
    result = []
    for device_id in devs:
        result.append((device_id, devs[device_id].get("name", device_id[:8])))
    return result


def switch_device(device_id):
    """切换到指定设备，同步扁平键到 config 根级"""
    provider = config.get("current_brand_type", "broadlink")
    if device_id not in config.get("devices", {}).get(provider, {}):
        return
    old = config.get("current_device_mac", "")
    if old and old in config.get("devices", {}).get(provider, {}):
        _save_flat_to_device(old)
    config["current_device_mac"] = device_id
    _load_device_to_flat(device_id)
    apply_config()


DEVICE_KEYS = ("host", "port", "mac", "model", "name", "brand", "fan",
               "schedule_enabled", "auto_adjust", "temp_rules",
               "token", "did", "miot_spec")


def _save_flat_to_device(device_id):
    """将 config 根级扁平键回写到 devices[provider][device_id]。
    仅修改已存在的条目，绝不创建 ghost entry。"""
    provider = config.get("current_brand_type", "broadlink")
    dev = config.get("devices", {}).get(provider, {}).get(device_id)
    if dev is None:
        return
    for k in DEVICE_KEYS:
        if k in config:
            dev[k] = config[k]


def _load_device_to_flat(device_id):
    """将 devices[provider][device_id] 键展平到 config 根级"""
    provider = config.get("current_brand_type", "broadlink")
    dev = config.get("devices", {}).get(provider, {}).get(device_id, {})
    DEFAULTS = {
        "schedule_enabled": False, "auto_adjust": False,
        "temp_rules": [[36,99,24,"cool"],[33,35,25,"cool"],[30,32,26,"cool"],[25,29,27,"cool"],[18,24,0,"off"],[0,17,28,"heat"]],
        "did": "",
    }
    for k in DEVICE_KEYS:
        config[k] = dev.get(k, DEFAULTS.get(k)) if k in DEFAULTS else dev.get(k, "")


def add_or_update_device(device_id, info):
    """添加或更新设备信息，不覆盖已有配置。自动添加到当前品牌子字典。"""
    provider = config.get("current_brand_type", "broadlink")
    config.setdefault("devices", {}).setdefault(provider, {})
    existing = config["devices"][provider].get(device_id, {})
    # 已有设备不覆盖用户昵称
    if device_id in config["devices"][provider]:
        old_name = config["devices"][provider][device_id].get("name", "")
        if old_name:
            info = dict(info)
            info.pop("name", None)
    else:
        # 新设备：同名加序号
        base = info.get("name", "")
        exist_names = [d.get("name","") for d in config["devices"][provider].values()]
        if base in exist_names:
            n = 2
            while f"{base} {n}" in exist_names:
                n += 1
            info = dict(info)
            info["name"] = f"{base} {n}"
    existing.update(info)
    config["devices"][provider][device_id] = existing
    if not config.get("current_device_mac"):
        config["current_device_mac"] = device_id
        _load_device_to_flat(device_id)  # 同步扁平键，防止后续 save_config 覆写


def _migrate_old_config():
    """旧版扁平 config → devices 结构，清理 device.json"""
    if "devices" in config:
        return  # 已迁移

    # 扫描局域网找设备
    mac = "temp_" + str(int(__import__("time").time()))
    host = ""; port = 80; model = ""
    try:
        from acnexus_core.ac_control import discover_devices
        devices_list = discover_devices(timeout=5)
        if devices_list:
            d = devices_list[0]
            mac = d.mac.hex() if isinstance(d.mac, bytes) else str(d.mac)
            host = d.host[0] if isinstance(d.host, tuple) else str(d.host)
            port = d.host[1] if isinstance(d.host, tuple) and len(d.host) > 1 else 80
            model = getattr(d, "model", "")
    except Exception:
        pass

    device_entry = {
        "host": host, "port": port, "mac": mac, "model": model,
        "name": model or "博联设备",
        "brand": config.pop("brand", "格力"),
        "fan": config.pop("fan", "auto"),
        "schedule_enabled": config.pop("schedule_enabled", True),
        "auto_adjust": config.pop("auto_adjust", True),
        "temp_rules": config.pop("temp_rules", None) or [list(r) for r in DEFAULT_RULES],
    }
    config["devices"] = {"broadlink": {mac: device_entry}}
    config["current_device_mac"] = mac
    if "current_brand_type" not in config:
        config["current_brand_type"] = "broadlink"

    # 清理残余键
    for k in ("brand", "fan", "schedule_enabled",
              "auto_adjust", "temp_rules"):
        config.pop(k, None)

    save_config(config)

    # 首次有设备时，展平到根级
    if config.get("current_device_mac") and config.get("devices"):
        _load_device_to_flat(config["current_device_mac"])

    # 删除旧 device.json
    old_cache = APP_DIR / "device.json"
    if old_cache.exists():
        old_cache.unlink()


def search_city(name):
    """城市搜索（单条）— 返回 (lat, lon, 显示名) 或 (None, None, '')。保留以兼容旧调用。"""
    results = search_cities(name)
    if results:
        return results[0]
    return None, None, ""


def search_cities(name):
    """城市搜索（多条）— 返回 [(lat, lon, 显示名, 省, 归一化层级), ...] 或 []"""
    import urllib.request, json, re, ssl
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(name)}&format=json&limit=8&accept-language=zh&addressdetails=1"
        req = urllib.request.Request(url, headers={"User-Agent": "AC-Nexus"})
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        resp = urllib.request.urlopen(req, timeout=8, context=ctx)
        data = json.loads(resp.read())
        results = []
        for item in data:
            lat = float(item["lat"])
            lon = float(item["lon"])
            # 用 display_name 展示（只去掉邮编，其余保留 Nominatim 本来的顺序）
            raw = item.get("display_name", "")
            normalized = re.sub(r",\s*\d{6}", "", raw)       # 去邮编 "518000"
            normalized = re.sub(r"\s{2,}", " ", normalized.strip())  # 合并多余空格
            # 省/国从 address 取（用于保存到 config）
            addr = item.get("address", {})
            province = addr.get("state") or addr.get("province") or ""
            nation = addr.get("country", "")
            results.append((lat, lon, normalized.split(",")[0].strip(),
                           province, nation, normalized))
        return results
    except Exception:
        pass
    return []


def _migrate_v6_nested():
    """v6 迁移：扁平 devices → 嵌套品牌子字典。

    自动识别旧版扁平格式（设备条目直接挂在 devices 下），迁移到新版嵌套格式
    （devices[品牌名][设备ID]）。同时清理历史残留：同一设备出现在多个 provider
    时只保留字段最多的那一份。
    """
    devs = config.get("devices", {})
    if not devs:
        return False

    changed = False

    # ── 1. 收集扁平设备条目 ──
    # 特征：值是 dict，且顶层有 host/mac/port 等设备配置键（而非子设备 dict）
    flat_entries = {}  # {device_id: device_data}
    for key, value in list(devs.items()):
        if not isinstance(value, dict):
            # 非 dict 的值直接删除
            del devs[key]
            changed = True
            continue
        # 判断是设备条目还是 provider 容器
        if "host" in value or "mac" in value or "port" in value:
            flat_entries[key] = value

    # ── 2. 迁移扁平条目 → 嵌套 ──
    for device_id, device_data in flat_entries.items():
        # 检查该设备是否已存在于某个 provider 中
        found_in = None
        for p, sub in devs.items():
            if isinstance(sub, dict) and device_id in sub:
                found_in = p
                break

        if found_in:
            # 已在嵌套结构中 → 扁平版本是幽灵，直接删除
            del devs[device_id]
            changed = True
        else:
            # 未在嵌套结构中 → 迁移
            provider = device_data.pop("type", None) or "broadlink"
            devs.setdefault(provider, {})[device_id] = device_data
            del devs[device_id]
            changed = True

    # ── 3. 清理重复设备（同一设备出现在多个 provider）──
    # 保留字段最多的版本（通常是最新的），删除其他
    all_ids = {}
    for p, sub in list(devs.items()):
        if not isinstance(sub, dict):
            del devs[p]
            changed = True
            continue
        for did in list(sub.keys()):
            all_ids.setdefault(did, []).append(p)

    for did, providers in all_ids.items():
        if len(providers) <= 1:
            continue
        best_p = max(providers, key=lambda p: len(devs[p].get(did, {})))
        for p in providers:
            if p != best_p and did in devs.get(p, {}):
                del devs[p][did]
                changed = True

    return changed


def init(api_key=None, qw_host=None, location=None, brand=None):
    """初始化：加载配置、迁移旧版、同步全局变量、启动调度"""
    global config
    config = load_config()
    _migrate_old_config()
    migrated = _migrate_v6_nested()
    if config.get("current_device_mac") and config.get("devices"):
        _load_device_to_flat(config["current_device_mac"])
    changed = migrated
    if api_key:
        config["api_key"] = api_key
        changed = True
    if qw_host:
        config["qw_host"] = qw_host
        changed = True
    if location:
        config["location"] = location
        changed = True
    if brand:
        dev = get_current_device()
        if dev:
            dev["brand"] = brand
            config["brand"] = brand  # 同步根级，防止 save_config sync_device 回写旧值
            changed = True
    if changed:
        save_config(config)
    apply_config()

    # 后台线程：2 秒后为缺少 miot_spec 的米家设备补拉（避免阻塞启动）
    def _migrate_miot_spec_bg():
        import time; time.sleep(2)
        try:
            from acnexus_core.xiaomi_local import fetch_miot_spec
            devs = config.get("devices", {}).get("xiaomi_cloud", {})
            needs_save = False
            for did, dev in devs.items():
                if isinstance(dev, dict) and dev.get("model") and len(dev.get("miot_spec") or {}) < 4:
                    try:
                        spec = fetch_miot_spec(dev["model"])
                        if spec:
                            dev["miot_spec"] = spec
                            if did == config.get("current_device_mac"):
                                config["miot_spec"] = spec  # 同步扁平键，防止 save_config 倒灌
                            needs_save = True
                    except Exception:
                        pass
            if needs_save:
                save_config(config)
        except Exception:
            pass
    import threading
    threading.Thread(target=_migrate_miot_spec_bg, daemon=True).start()

    from acnexus_core.scheduler import start_scheduler
    start_scheduler()


# 缓存的室外温度
_cached_temp = None

# 最近扫描在线的设备 MAC 集合
_online_macs = set()

# 台风自动关空调：防止每30分钟重复触发
_ty_ac_off_sent = False

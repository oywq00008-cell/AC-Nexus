"""BroadlinkAC Core — 配置与初始化

所有共享状态集中管理：config 字典、QW_KEY、QW_HOST、LOCATION、AC_BRAND、_cached_temp。
"""

import json
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


def load_config():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {
        "current_device_mac": "",
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
    if sync_device:
        mac = cfg.get("current_device_mac", "")
        if mac and mac in cfg.get("devices", {}):
            dev = cfg["devices"][mac]
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
    return config.get("devices", {}).get(mac, {})


def get_device_list():
    """返回设备列表 [(mac, name), ...]"""
    devs = config.get("devices", {})
    return [(mac, devs[mac].get("name", mac[:8])) for mac in devs]


def switch_device(mac):
    """切换到指定设备，同步扁平键到 config 根级"""
    if mac not in config.get("devices", {}):
        return
    old = config.get("current_device_mac", "")
    if old and old in config.get("devices", {}):
        _save_flat_to_device(old)
    config["current_device_mac"] = mac
    _load_device_to_flat(mac)
    apply_config()


DEVICE_KEYS = ("host", "port", "mac", "model", "name", "brand", "fan",
               "schedule_enabled", "auto_adjust", "temp_rules")


def _save_flat_to_device(mac):
    """将 config 根级扁平键回写到 devices[mac]"""
    dev = config["devices"].setdefault(mac, {})
    for k in DEVICE_KEYS:
        if k in config:
            dev[k] = config[k]


def _load_device_to_flat(mac):
    """将 devices[mac] 键展平到 config 根级"""
    dev = config.get("devices", {}).get(mac, {})
    DEFAULTS = {
        "schedule_enabled": True, "auto_adjust": True,
        "temp_rules": [[36,99,24,"cool"],[33,35,25,"cool"],[30,32,26,"cool"],[25,29,27,"cool"],[18,24,0,"off"],[0,17,28,"heat"]],
    }
    for k in DEVICE_KEYS:
        config[k] = dev.get(k, DEFAULTS.get(k)) if k in DEFAULTS else dev.get(k, "")


def add_or_update_device(mac, info):
    """添加或更新设备信息，不覆盖已有配置"""
    if "devices" not in config:
        config["devices"] = {}
    existing = config["devices"].get(mac, {})
    # 已有设备不覆盖用户昵称
    if mac in config["devices"]:
        old_name = config["devices"][mac].get("name", "")
        if old_name:
            info = dict(info)
            info.pop("name", None)
    else:
        # 新设备：同名加序号
        base = info.get("name", "")
        exist_names = [d.get("name","") for d in config["devices"].values()]
        if base in exist_names:
            n = 2
            while f"{base} {n}" in exist_names:
                n += 1
            info = dict(info)
            info["name"] = f"{base} {n}"
    existing.update(info)
    config["devices"][mac] = existing
    if not config.get("current_device_mac"):
        config["current_device_mac"] = mac


def _migrate_old_config():
    """旧版扁平 config → devices 结构，清理 device.json"""
    if "devices" in config:
        return  # 已迁移

    # 扫描局域网找设备
    mac = "temp_" + str(int(__import__("time").time()))
    host = ""; port = 80; model = ""
    try:
        from broadlinkac_core.ac_control import discover_devices
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
    config["devices"] = {mac: device_entry}
    config["current_device_mac"] = mac

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
    import urllib.request, json, re
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(name)}&format=json&limit=8&accept-language=zh&addressdetails=1"
        req = urllib.request.Request(url, headers={"User-Agent": "BroadlinkAC"})
        resp = urllib.request.urlopen(req, timeout=8)
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


def init(api_key=None, qw_host=None, location=None, brand=None):
    """初始化：加载配置、迁移旧版、同步全局变量、启动调度"""
    global config
    config = load_config()
    _migrate_old_config()
    if config.get("current_device_mac") and config.get("devices"):
        _load_device_to_flat(config["current_device_mac"])
    changed = False
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
            changed = True
    if changed:
        save_config(config)
    apply_config()
    from broadlinkac_core.scheduler import start_scheduler
    start_scheduler()


# 缓存的室外温度
_cached_temp = None

# 最近扫描在线的设备 MAC 集合
_online_macs = set()

# 台风自动关空调：防止每30分钟重复触发
_ty_ac_off_sent = False

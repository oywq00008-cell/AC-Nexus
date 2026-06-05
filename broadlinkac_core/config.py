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

# ── 品牌映射 ──
AC_BRANDS = {
    "格力": "gree", "美的": "midea", "海尔": "haier", "华凌": "midea",
    "奥克斯": "aux_ac", "海信": "hisense", "大金": "daikin", "三菱": "mitsubishi",
    "小米": "midea", "松下": "panasonic",
}

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
        return json.loads(CONFIG_FILE.read_text())
    return {
        "trigger_time": "12:00",
        "schedule_enabled": True,
        "temp_rules": [list(r) for r in DEFAULT_RULES],
        "typhoon_alert_km": 800,
        "typhoon_alert_enabled": True,
        "api_key": "",
        "qw_host": "",
        "location": dict(LOCATION),
        "brand": "格力",
        "off_time": "22:00",
        "off_enabled": False,
        "auto_adjust": True,
        "appearance_mode": "system",
        "baidu_key": "",
        "weather_provider": "baidu",
        "weather_provider_set": False,
    }


def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))


def apply_config():
    """将 config 同步到运行时全局变量"""
    global QW_KEY, QW_HOST, LOCATION, AC_BRAND
    QW_KEY = config.get("api_key", "")
    QW_HOST = config.get("qw_host", "")
    if QW_HOST and not QW_HOST.startswith("http"):
        QW_HOST = "https://" + QW_HOST
    LOCATION = config.get("location", {"lat": 39.90, "lon": 116.40, "name": "北京"})
    AC_BRAND = AC_BRANDS.get(config.get("brand", "格力"), "gree")


def init(api_key=None, qw_host=None, location=None, brand=None):
    """初始化：加载配置、同步全局变量、启动后台定时任务。

       Agent 可直接传入配置，无需手动编辑 config.json：
           init(api_key="xxx", qw_host="https://xxx.re.qweatherapi.com",
                location={"lat": 22.54, "lon": 114.05, "name": "深圳"})
    """
    global config
    config = load_config()
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
        config["brand"] = brand
        changed = True
    if changed:
        save_config(config)
    apply_config()
    # 延迟导入避免循环依赖
    from broadlinkac_core.scheduler import start_scheduler
    start_scheduler()


# 缓存的室外温度
_cached_temp = None

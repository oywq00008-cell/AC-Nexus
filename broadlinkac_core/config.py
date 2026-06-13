def apply_config():
    """将 config 同步到运行时全局变量"""
    global QW_KEY, QW_HOST, LOCATION, AC_BRAND
    QW_KEY = config.get("api_key") or config.get("qweather_key", "")
    QW_HOST = config.get("qw_host") or config.get("qweather_host", "")
    if QW_HOST and not QW_HOST.startswith("http"):
        QW_HOST = "https://" + QW_HOST
    LOCATION = config.get("location", {"lat": 39.90, "lon": 116.40, "name": "北京"})
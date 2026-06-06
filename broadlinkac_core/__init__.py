"""BroadlinkAC Core — 公共 API

用法:
    from broadlinkac_core import init, send_ac, fetch_weather

    init(api_key="xxx", qw_host="https://xxx.re.qweatherapi.com")
    send_ac("on", "cool", 26, "auto")
    weather = fetch_weather()
"""

from broadlinkac_core.config import init, apply_config, save_config, load_config
from broadlinkac_core.ac_control import send_ac, decide_ac, get_device
from broadlinkac_core.weather import fetch_weather, city_lookup, fetch_weather_alerts
from broadlinkac_core.typhoon import fetch_typhoons, fetch_typhoon_detail, calc_distance, typhoon_threat_distance, fetch_and_cache, get_cached
from broadlinkac_core.logger import write_log, read_log, get_log_dates
from broadlinkac_core.scheduler import _sched_lock, scheduled_job, scheduled_off_job

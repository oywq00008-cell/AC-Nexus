"""BroadlinkAC Core — 定时任务"""

import time
import threading
from datetime import datetime
import schedule as sch

import broadlinkac_core.config as _cfg

from broadlinkac_core.weather import fetch_weather
from broadlinkac_core.ac_control import send_ac, decide_ac, MODE_KEYS
from broadlinkac_core.logger import write_log, get_last_ac_state

_sched_lock = threading.Lock()


def _device_online(mac):
    """判断设备最近是否在线"""
    return not _cfg._online_macs or mac in _cfg._online_macs


def scheduled_job(mac):
    dev = _cfg.config.get("devices", {}).get(mac, {})
    name = dev.get("name", mac[:8])
    if not _device_online(mac):
        write_log("系统", f"⏰ [{name}] 定时触发 → 设备离线，跳过")
        return None
    if _cfg._cached_temp is None:
        w = fetch_weather()
        if not w:
            return None
        outdoor = float(w["temp"])
    else:
        outdoor = _cfg._cached_temp

    target, mode = decide_ac(outdoor, mac)
    if mode == "off":
        name = dev.get("name", mac[:8])
        write_log("空调", f"⏰ [{name}] 定时触发: 室外 {outdoor}°C → 关闭，不发送指令")
        return None

    # 台风保护：风暴 < 100km 时不启动空调
    from broadlinkac_core.typhoon import typhoon_threat_distance
    min_dist, storm_name = typhoon_threat_distance()
    if min_dist < 100:
        write_log("系统",
                  f"⏰ [{name}] 定时触发: 风暴 {storm_name} 距 {min_dist}km，跳过开机")
        return None

    try:
        result = send_ac("on", mode, target, "auto", source="定时", mac=mac)
        write_log("空调", result)
        return result
    except Exception as e:
        write_log("系统", f"定时发送失败: {e}")
    return None


def scheduled_off_job(mac):
    """定时关机"""
    dev = _cfg.config.get("devices", {}).get(mac, {})
    name = dev.get("name", mac[:8])
    if not _device_online(mac):
        write_log("系统", f"⏰ [{name}] 定时关机 → 设备离线，跳过")
        return None
    # 检测空调状态：已关则跳过
    state = get_last_ac_state()
    if state["power"] == "off":
        return None
    # 台风保护：已被台风关机的跳过
    from broadlinkac_core.typhoon import typhoon_threat_distance
    min_dist, _ = typhoon_threat_distance()
    if min_dist < 100:
        write_log("系统", f"⏰ [{name}] 定时关机 → 风暴已处理，跳过")
        return None

    try:
        result = send_ac("off", "cool", 26, "auto", source="定时", mac=mac)
        write_log("空调", result)
        return result
    except Exception as e:
        write_log("系统", f"定时关机失败: {e}")
    return None


def auto_adjust_job(mac):
    """每2小时自动调温：读日志判状态 → 跑规则 → 温度无变化则跳过"""
    dev = _cfg.config.get("devices", {}).get(mac, {})
    name = dev.get("name", mac[:8])
    if not _device_online(mac):
        write_log("系统", f"🔄 [{name}] 自动调温 → 设备离线，跳过")
        return
    state = get_last_ac_state()
    if state["power"] == "off":
        return

    if _cfg._cached_temp is None:
        w = fetch_weather()
        if not w:
            write_log("系统", f"🔄 [{name}] 自动调温: 天气获取失败，跳过")
            return
        outdoor = float(w["temp"])
    else:
        outdoor = _cfg._cached_temp

    target, mode = decide_ac(outdoor, mac)
    if mode == "off":
        write_log("空调", send_ac("off", "cool", 26, "auto", source="自动", mac=mac))
        return

    if state["mode"] == mode and state["temp"] == target:
        write_log("空调", f"[{datetime.now():%H:%M}] [{name}] 自动调温 → 不更改温度")
        return

    try:
        write_log("空调", send_ac("on", mode, target, "auto", source="自动", mac=mac))
    except Exception as e:
        write_log("系统", f"自动调温失败: {e}")


def register_all_jobs():
    """注册所有设备的 AC 定时任务（在 _sched_lock 内调用）"""
    sch.clear()
    for mac, dev in _cfg.config.get("devices", {}).items():
        if dev.get("schedule_enabled", True):
            sch.every().day.at(dev.get("trigger_time", "12:00")).do(scheduled_job, mac=mac)
        if dev.get("off_enabled"):
            sch.every().day.at(dev.get("off_time", "22:00")).do(scheduled_off_job, mac=mac)
        if dev.get("auto_adjust", True):
            sch.every(2).hours.do(auto_adjust_job, mac=mac)


def scheduler_loop():
    register_all_jobs()
    while True:
        with _sched_lock:
            sch.run_pending()
        time.sleep(max(sch.idle_seconds(), 0) if sch.idle_seconds() is not None else 15)


_sched_started = False


def start_scheduler():
    """启动后台调度线程（幂等，仅首次调用生效）"""
    global _sched_started
    if _sched_started:
        return
    _sched_started = True
    threading.Thread(target=scheduler_loop, daemon=True).start()

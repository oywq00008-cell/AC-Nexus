"""BroadlinkAC Core — 定时任务"""

import time
import threading
import schedule as sch

import broadlinkac_core.config as _cfg

from broadlinkac_core.weather import fetch_weather
from broadlinkac_core.typhoon import fetch_typhoons, fetch_typhoon_detail, calc_distance
from broadlinkac_core.ac_control import send_ac, decide_ac, MODE_KEYS
from broadlinkac_core.logger import write_log, get_last_ac_state

_sched_lock = threading.Lock()


def scheduled_job():
    if _cfg._cached_temp is None:
        w = fetch_weather()
        if not w:
            return None
        outdoor = float(w["temp"])
    else:
        outdoor = _cfg._cached_temp

    target, mode = decide_ac(outdoor)
    if mode == "off":
        write_log("空调", f"⏰ 定时触发: 室外 {outdoor}°C → 关闭，不发送指令")
        return None

    try:
        result = send_ac("on", mode, target, "auto")
        write_log("空调", f"⏰ 定时触发: 室外 {outdoor}°C → {MODE_KEYS.get(mode, mode)} {target}°C")
        return result
    except Exception as e:
        write_log("系统", f"定时发送失败: {e}")
    return None


def scheduled_off_job():
    """定时关机"""
    try:
        result = send_ac("off", "cool", 26, "auto")
        write_log("空调", f"⏰ 定时关机: {result}")
        return result
    except Exception as e:
        write_log("系统", f"定时关机失败: {e}")
    return None


def refresh_typhoon_silent():
    """后台静默刷新台风，记录日志"""
    try:
        typhoons = fetch_typhoons()
        for t in typhoons:
            detail = fetch_typhoon_detail(t["id"])
            if detail:
                dist = calc_distance(_cfg.LOCATION["lat"], _cfg.LOCATION["lon"], detail["lat"], detail["lon"])
                status = "⚠️ 预警" if dist < _cfg.config["typhoon_alert_km"] else "✅ 安全"
                write_log("台风", f"{detail['cn']} ({detail['eng']}) {detail['cat']} 距{dist}km {status}")
    except Exception as e:
        print(f"[台风后台] {e}")


def register_all_jobs():
    """统一注册所有定时任务（在 _sched_lock 内调用）"""
    sch.clear()
    sch.every(30).minutes.do(refresh_typhoon_silent)
    if _cfg.config.get("schedule_enabled", True):
        sch.every().day.at(_cfg.config["trigger_time"]).do(scheduled_job)
    if _cfg.config.get("off_enabled"):
        sch.every().day.at(_cfg.config["off_time"]).do(scheduled_off_job)
    if _cfg.config.get("auto_adjust", True):
        sch.every(2).hours.do(auto_adjust_job)


def scheduler_loop():
    register_all_jobs()
    while True:
        with _sched_lock:
            sch.run_pending()
        time.sleep(15)


def auto_adjust_job():
    """每2小时自动调温：读日志判状态 → 跑规则 → 温度无变化则跳过"""
    state = get_last_ac_state()
    if state["power"] == "off":
        return  # 空调没在运行

    if _cfg._cached_temp is None:
        w = fetch_weather()
        if not w:
            return
        outdoor = float(w["temp"])
    else:
        outdoor = _cfg._cached_temp

    target, mode = decide_ac(outdoor)
    if mode == "off":
        send_ac("off", "cool", 26, "auto")
        write_log("空调", f"🔄 自动调温: 室外 {outdoor}°C → 规则判定关闭 → 已关机")
        return

    if state["mode"] == mode and state["temp"] == target:
        return  # 温度无变化

    try:
        send_ac("on", mode, target, "auto")
        write_log("空调", f"🔄 自动调温: 室外 {outdoor}°C → {MODE_KEYS.get(mode, mode)} {target}°C")
    except Exception as e:
        write_log("系统", f"自动调温失败: {e}")


def start_scheduler():
    """启动后台调度线程"""
    threading.Thread(target=scheduler_loop, daemon=True).start()

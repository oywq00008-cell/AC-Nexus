"""BroadlinkAC Core — 定时任务"""

import time
import threading
from datetime import datetime
import schedule as sch

import broadlinkac_core.config as _cfg

from broadlinkac_core.weather import fetch_weather
from broadlinkac_core.typhoon import fetch_typhoons, fetch_typhoon_detail, calc_distance
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
    try:
        result = send_ac("off", "cool", 26, "auto", source="定时", mac=mac)
        write_log("空调", result)
        return result
    except Exception as e:
        write_log("系统", f"定时关机失败: {e}")
    return None


def refresh_typhoon_silent():
    """后台静默刷新台风，记录日志，必要时自动关闭所有空调"""
    try:
        typhoons = fetch_typhoons()
        min_dist = 99999
        for t in typhoons:
            detail = fetch_typhoon_detail(t["id"])
            if detail:
                dist = calc_distance(_cfg.LOCATION["lat"], _cfg.LOCATION["lon"], detail["lat"], detail["lon"])
                status = "⚠️ 预警" if dist < _cfg.config["typhoon_alert_km"] else "✅ 安全"
                write_log("台风", f"{detail['cn']} ({detail['eng']}) {detail['cat']} 距{dist}km {status}")
                if dist < min_dist:
                    min_dist = dist

        # ── 台风自动关空调 ──
        if not _cfg.config.get("typhoon_ac_off", True):
            return
        if min_dist < 100 and not _cfg._ty_ac_off_sent:
            _cfg._ty_ac_off_sent = True
            offline_count = 0
            off_count = 0
            for mac, dev in _cfg.config.get("devices", {}).items():
                name = dev.get("name", mac[:8])
                if not _device_online(mac):
                    offline_count += 1
                    continue
                try:
                    send_ac("off", "cool", 26, "auto", source="台风", mac=mac)
                    write_log("空调", f"🌀 台风靠近（距{min_dist}km）→ [{name}] 已自动关机")
                    off_count += 1
                except Exception as e:
                    write_log("系统", f"台风关机失败 [{name}]: {e}")
            write_log("系统", f"🌀 台风自动关机完成: 关闭 {off_count} 台, 离线 {offline_count} 台")
        elif min_dist >= 100:
            _cfg._ty_ac_off_sent = False  # 远离后重置
    except Exception as e:
        print(f"[台风后台] {e}")


def register_all_jobs():
    """注册所有设备的定时任务（在 _sched_lock 内调用）"""
    sch.clear()
    sch.every(30).minutes.do(refresh_typhoon_silent)
    
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
        time.sleep(15)


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


def start_scheduler():
    """启动后台调度线程"""
    threading.Thread(target=scheduler_loop, daemon=True).start()

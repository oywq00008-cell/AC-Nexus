"""AC-Nexus Core — 定时任务"""

import time
import threading
from datetime import datetime
import schedule as sch

import acnexus_core.config as _cfg

from acnexus_core.weather import fetch_weather
from acnexus_core.ac_control import send_ac, decide_ac, MODE_KEYS
from acnexus_core.logger import write_log, get_last_ac_state

_sched_lock = threading.RLock()
_sched_event = threading.Event()
_sched_thread = None
_sched_paused = False


def pause_scheduler():
    """台风靠近时暂停调度器：标记暂停 + 唤醒线程重新检查状态"""
    global _sched_paused
    _sched_paused = True
    _sched_event.set()


def resume_scheduler():
    """台风远离/用户关开关时恢复调度器：取消暂停 + 唤醒线程"""
    global _sched_paused
    _sched_paused = False
    _sched_event.set()


def _device_online(mac):
    """判断设备最近是否在线。米家设备始终视为在线（走 MIoT 协议）。"""
    provider, _ = _cfg.find_device(mac)
    if provider == "xiaomi_cloud":
        return True
    return not _cfg._online_macs or mac in _cfg._online_macs


def scheduled_job(mac):
    provider, dev = _cfg.find_device(mac)
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
    provider, dev = _cfg.find_device(mac)
    name = dev.get("name", mac[:8])
    if not _device_online(mac):
        write_log("系统", f"⏰ [{name}] 定时关机 → 设备离线，跳过")
        return None
    # 检测空调状态：未知或已关则跳过
    state = get_last_ac_state()
    if state["power"] == "unknown":
        write_log("系统", f"⏰ [{name}] 定时关机 → 无法判定空调状态，跳过")
        return None
    if state["power"] == "off":
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
    provider, dev = _cfg.find_device(mac)
    name = dev.get("name", mac[:8])
    if not _device_online(mac):
        write_log("系统", f"🔄 [{name}] 自动调温 → 设备离线，跳过")
        return
    state = get_last_ac_state()
    if state["power"] == "unknown":
        write_log("系统", f"🔄 [{name}] 自动调温 → 无法判定空调状态，跳过")
        return
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


def _scheduled_on_wrapper(mac, days):
    """仅在指定星期几执行开机"""
    if datetime.now().isoweekday() in days:
        return scheduled_job(mac)


def _scheduled_off_wrapper(mac, days):
    """仅在指定星期几执行关机"""
    if datetime.now().isoweekday() in days:
        return scheduled_off_job(mac)


def _migrate_schedule_config():
    """将旧字段迁移到模板结构（自动执行一次）"""
    if _cfg.config.get("_schedule_migrated"):
        return
    old_trigger = _cfg.config.get("trigger_time")
    old_off = _cfg.config.get("off_time")
    old_on_enabled = _cfg.config.get("schedule_enabled", False)
    old_off_enabled = _cfg.config.get("off_enabled", False)
    if old_trigger or old_off:
        slots = []
        if old_on_enabled and old_trigger:
            slots.append({"on": old_trigger, "off": old_off if old_off_enabled else None})
        elif old_off_enabled and old_off:
            slots.append({"on": old_off, "off": None})
        if slots:
            _cfg.config.setdefault("schedule_templates", {})["默认"] = {
                "groups": [{"days": [1, 2, 3, 4, 5, 6, 7], "slots": slots}]
            }
            mac = _cfg.config.get("current_device_mac")
            if mac:
                provider = _cfg.config.get("current_brand_type", "broadlink")
                _cfg.config.setdefault("devices", {}).setdefault(provider, {}).setdefault(mac, {})["active_template"] = "默认"
        for k in ("trigger_time", "off_time", "schedule_enabled", "off_enabled"):
            _cfg.config.pop(k, None)
    # 迁移旧 days/slots 结构 → groups
    for name, tmpl in (_cfg.config.get("schedule_templates", {}) or {}).items():
        if "groups" not in tmpl and "days" in tmpl:
            tmpl["groups"] = [{"days": tmpl.pop("days", [1,2,3,4,5]),
                                "slots": tmpl.pop("slots", [])}]
    _cfg.config["_schedule_migrated"] = True
    from acnexus_core.config import save_config
    save_config(_cfg.config)


def _do_register():
    """纯注册逻辑：清空并重新注册所有品牌所有设备的定时任务。返回是否有任务。"""
    with _sched_lock:
        sch.clear()
        _migrate_schedule_config()
        templates = _cfg.config.get("schedule_templates", {}) or {}
        for provider, devs in _cfg.config.get("devices", {}).items():
            if not isinstance(devs, dict):
                continue
            for mac, dev in devs.items():
                if not isinstance(dev, dict):
                    continue
                tmpl_name = dev.get("active_template")
                tmpl = templates.get(tmpl_name) if tmpl_name else None
                if tmpl and dev.get("schedule_enabled", True):
                    groups = tmpl.get("groups", [])
                    # 向后兼容：无 groups 但有 days
                    if not groups and tmpl.get("days"):
                        groups = [{"days": tmpl["days"], "slots": tmpl.get("slots", [])}]
                    for grp in groups:
                        days = set(grp.get("days", []))
                        for slot in grp.get("slots", []):
                            on_t = slot.get("on")
                            off_t = slot.get("off")
                            if on_t and slot.get("on_enabled", True):
                                sch.every().day.at(on_t).do(_scheduled_on_wrapper, mac=mac, days=days)
                            if off_t and slot.get("off_enabled", True):
                                sch.every().day.at(off_t).do(_scheduled_off_wrapper, mac=mac, days=days)
                else:
                    # 向后兼容：没有模板时用旧字段
                    if dev.get("schedule_enabled", True) and dev.get("trigger_time"):
                        sch.every().day.at(dev["trigger_time"]).do(scheduled_job, mac=mac)
                    if dev.get("off_enabled") and dev.get("off_time"):
                        sch.every().day.at(dev["off_time"]).do(scheduled_off_job, mac=mac)
                if dev.get("auto_adjust", True):
                    sch.every(2).hours.do(auto_adjust_job, mac=mac)
    return bool(sch.get_jobs())


def register_all_jobs():
    """公开接口：注册任务 + 确保调度线程存活/唤醒"""
    _do_register()
    start_scheduler()


def scheduler_loop():
    """调度守护线程主循环：异常自动重生，无任务自动退出"""
    while True:
        try:
            has_jobs = _do_register()
            if not has_jobs:
                return
            while True:
                if _sched_paused:
                    _sched_event.wait()          # 暂停：阻塞等待恢复信号
                    _sched_event.clear()
                    break                        # 跳出，外层重新 _do_register
                idle = sch.idle_seconds()
                timeout = min(max(idle, 1), 30) if idle is not None else 30  # 最长30秒，防止 macOS 合并定时器
                if _sched_event.wait(timeout=timeout):
                    _sched_event.clear()
                    break
                with _sched_lock:
                    sch.run_pending()
        except Exception as e:
            try:
                write_log("系统", f"调度器异常，5秒后重启: {e}")
            except Exception:
                pass
            time.sleep(5)


def start_scheduler():
    """确保调度线程存活：已死则重建，存活则唤醒"""
    global _sched_thread
    if _sched_thread and _sched_thread.is_alive():
        _sched_event.set()
        return
    _sched_thread = threading.Thread(target=scheduler_loop, daemon=True)
    _sched_thread.start()

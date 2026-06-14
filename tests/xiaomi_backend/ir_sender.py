"""小米红外发送后端 — 对接 python-miio 的 ChuangmiIr

设计：和 Broadlink 的 ac_control.py 完全对等
输入: power, mode, temp, fan → hvac_ir 算 duration → play_raw 发送

集成后 ac_control.py 只需要:
    if dev_type == "xiaomi":
        xiaomi_ir.send_ac(ip, token, duration)
    else:
        broadlink.send_data(data)
"""

import json
from datetime import datetime

from .token_manager import get_token


def _get_device(ip: str, token: str):
    """连接米家空调伴侣"""
    from miio import ChuangmiIr
    return ChuangmiIr(ip, token)


def play_raw(ip: str, token: str, frequency: int, durations: list[int]):
    """发送原始红外码（等同于 Broadlink 的 send_data）"""
    d = _get_device(ip, token)
    d.play_raw(freq=frequency, raw_codes=durations)


def send_ac(ip: str, token: str, durations: list[int],
            power: str, mode: str, temp: int, fan: str,
            source: str = "手动") -> str:
    """完整发送流程：和 broadlinkac_core.ac_control.send_ac 签名兼容

    durations: hvac_ir 协议层算出的红外脉冲数组
    返回: 日志描述字符串
    """
    d = _get_device(ip, token)
    d.play_raw(freq=38000, raw_codes=durations)

    now = datetime.now()
    MODE_KEYS = {"cool": "制冷", "heat": "制热", "dry": "除湿", "fan": "送风", "auto": "自动"}
    label = {"手动": "手动", "定时": "定时", "自动": "自动调温"}.get(source, source)

    if power == "on":
        if source == "自动":
            return f"[{now:%H:%M}] 自动调温 → {MODE_KEYS.get(mode, mode)} {temp}°C"
        return f"[{now:%H:%M}] {label}开机 → {MODE_KEYS.get(mode, mode)} {temp}°C"
    if source == "自动":
        return f"[{now:%H:%M}] 自动关机"
    return f"[{now:%H:%M}] {label}关机"


# ── 集成到 ac_control.py 的代码（届时直接粘贴）──

def ac_control_send_ac_placeholder(power: str, mode: str, temp: int, fan: str,
                                     source="手动", mac=None):
    """【集成参考】修改 send_ac() 后的样子，这里只是伪代码展示流程"""
    from broadlinkac_core.config import config
    from broadlinkac_core.ac_control import MODES, FANS, MODE_KEYS

    # ... 前面拿到 brand, durations 的逻辑不变 ...

    mac = mac or config.get("current_device_mac", "")
    dev = config.get("devices", {}).get(mac, {})
    dev_type = dev.get("type", "broadlink")

    if dev_type == "xiaomi":
        ip = dev.get("host", "")
        token = get_token(dev.get("did", mac))
        if not token:
            raise RuntimeError(
                f"米家设备 {dev.get('name', mac[:8])} 的 Token 不存在。"
                f"请重新扫码登录。"
            )
        return send_ac(ip, token, durations, power, mode, temp, fan, source)

    # ... 原有的 Broadlink 发送逻辑 ...
    return "Broadlink OK"  # placeholder

"""BroadlinkAC Core — 空调控制（博联设备 + 红外发码 + 温度规则）"""

import json
import socket
import struct
from datetime import datetime

import broadlink
from broadlink.remote import pulses_to_data

import broadlinkac_core.config as _cfg

from broadlinkac_core.config import (
    APP_DIR, AC_BRANDS,
)

DEVICE_CACHE = APP_DIR / "device.json"

# UI 显示用（从 config.py 导入但这里定义一份用于 MODE_KEYS）
MODES = {"制冷": "cool", "制热": "heat", "除湿": "dry", "送风": "fan", "自动": "auto", "关闭": "off"}
FANS = {"自动": "auto", "1 档": "1", "2 档": "2", "3 档": "3"}
MODE_KEYS = {v: k for k, v in MODES.items()}


def load_device_cache():
    if DEVICE_CACHE.exists():
        return json.loads(DEVICE_CACHE.read_text())
    return None


def save_device_cache(device):
    info = {
        "host": device.host[0],
        "port": device.host[1],
        "mac": device.mac.hex() if isinstance(device.mac, bytes) else str(device.mac),
        "model": device.model,
        "name": device.name,
        "devtype": device.devtype,
    }
    DEVICE_CACHE.write_text(json.dumps(info, indent=2))


def _get_local_ips():
    """获取本机所有非回环 IPv4 地址（排除 127.x, docker, 虚拟网卡等）"""
    ips = []
    try:
        import netifaces
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface).get(netifaces.AF_INET, [])
            for addr in addrs:
                ip = addr.get('addr', '')
                if ip and not ip.startswith('127.') and ip != '0.0.0.0':
                    ips.append(ip)
    except ImportError:
        pass

    if not ips:
        # fallback: 用 socket 连接外部地址来推断本机 IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 1))
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith('127.'):
                ips.append(ip)
        except Exception:
            ips.append('0.0.0.0')
    return ips


def discover_devices(timeout=5):
    """遍历所有本机网卡，逐个尝试 UDP 广播发现博联设备。返回设备列表。"""
    local_ips = _get_local_ips()
    all_devices = []
    for ip in local_ips:
        try:
            devices = broadlink.discover(
                timeout=timeout,
                local_ip_address=ip,
                discover_ip_address='255.255.255.255',
                discover_ip_port=80,
            )
            all_devices.extend(devices)
        except Exception:
            pass
    return all_devices


def get_device():
    """获取博联设备: 优先缓存直连, 失败则重新扫描并更新缓存"""
    cached = load_device_cache()
    if cached:
        try:
            d = broadlink.hello(cached["host"])
            d.auth()
            return d
        except Exception:
            pass

    all_devices = discover_devices(timeout=5)

    if not all_devices:
        raise Exception("未发现博联设备，请确认：\n1. 电脑和博联设备在同一个局域网\n"
                        "2. Windows 防火墙允许 UDP 端口 80 的入站/出站通信")

    d = all_devices[0]
    d.auth()
    save_device_cache(d)
    return d


def send_ac(power: str, mode: str, temp: int, fan: str, source="手动"):
    """发红外码，自动根据当前品牌选择协议。
       source: \"手动\" | \"定时\" | \"自动\" — 写入日志的前缀"""
    brand = _cfg.AC_BRAND
    t = min(max(temp, 16), 30)

    if brand in ("gree", "midea", "hisense", "daikin", "mitsubishi"):
        mod = __import__(f"hvac_ir.{brand}", fromlist=[brand])
        cls_name = brand.capitalize()
        sender = getattr(mod, cls_name)()
        mode_map = {"auto": sender.MODE_AUTO, "cool": sender.MODE_COOL,
                    "dry": sender.MODE_DRY, "fan": sender.MODE_FAN,
                    "heat": sender.MODE_HEAT}
        fan_map = {"auto": sender.FAN_AUTO, "1": sender.FAN_1,
                   "2": sender.FAN_2, "3": sender.FAN_3}
        pwr = sender.POWER_ON if power == "on" else sender.POWER_OFF
        m = mode_map.get(mode, sender.MODE_COOL)
        f = fan_map.get(fan, sender.FAN_AUTO)
        vsw = getattr(sender, "VDIR_SWING", None)
        hsw = getattr(sender, "HDIR_SWING", None)
        sender.send(pwr, m, f, t, vsw, hsw, False)
    else:
        mod = __import__(f"protocols.{brand}", fromlist=[brand])
        cls_map = {"haier": "Haier", "aux_ac": "AUX", "panasonic": "Panasonic"}
        cls_name = cls_map.get(brand, brand.capitalize())
        sender = getattr(mod, cls_name)()
        mode_maps = {
            "haier": {"auto": 0x00, "cool": 0x01, "dry": 0x02, "fan": 0x04, "heat": 0x03},
            "aux_ac": {"auto": 0, "cool": 1, "dry": 2, "fan": 6, "heat": 4},
            "panasonic": {"auto": 0, "cool": 3, "dry": 2, "fan": 6, "heat": 4},
        }
        fan_maps = {
            "haier": {"auto": 0x00, "1": 0x01, "2": 0x02, "3": 0x03},
            "aux_ac": {"auto": 5, "1": 1, "2": 2, "3": 3},
            "panasonic": {"auto": 7, "1": 3, "2": 2, "3": 1},
        }
        mode_map = mode_maps.get(brand, {"auto": 0, "cool": 1, "dry": 2, "fan": 3, "heat": 4})
        fan_map = fan_maps.get(brand, {"auto": 7, "1": 0, "2": 1, "3": 2})
        pwr = mod.POWER_ON if power == "on" else mod.POWER_OFF
        m = mode_map.get(mode, mode_map["cool"])
        f = fan_map.get(fan, fan_map["auto"])
        sender.send(pwr, m, f, t)

    data = pulses_to_data(sender.get_durations())
    d = get_device()
    d.send_data(data)

    now = datetime.now()
    label = {"手动": "手动", "定时": "定时", "自动": "自动调温"}.get(source, source)
    if power == "on":
        if source == "自动":
            return f"[{now:%H:%M}] 自动调温 → {MODE_KEYS.get(mode, mode)} {temp}°C"
        return f"[{now:%H:%M}] {label}开机 → {MODE_KEYS.get(mode, mode)} {temp}°C"
    if source == "自动":
        return f"[{now:%H:%M}] 自动关机"
    return f"[{now:%H:%M}] {label}关机"


def decide_ac(outdoor):
    for low, high, target, mode in _cfg.config["temp_rules"]:
        if low <= outdoor <= high:
            return target, mode
    return 26, "cool"

"""BroadlinkAC Core — 空调控制（博联设备 + 红外发码 + 温度规则）"""

import socket
from datetime import datetime

import broadlink
from broadlink.remote import pulses_to_data

import broadlinkac_core.config as _cfg


# UI 显示用
MODES = {"制冷": "cool", "制热": "heat", "除湿": "dry", "送风": "fan", "自动": "auto", "关闭": "off"}
FANS = {"自动": "auto", "1 档": "1", "2 档": "2", "3 档": "3"}
MODE_KEYS = {v: k for k, v in MODES.items()}


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


def get_device(mac=None):
    """获取博联设备：优先从 config 读 host 直连，失败扫描"""
    devs = _cfg.config.get("devices", {})
    if not mac:
        mac = _cfg.config.get("current_device_mac", "")
    dev = devs.get(mac, {})
    host = dev.get("host", "")
    
    if host:
        try:
            d = broadlink.hello(host)
            d.auth()
            return d
        except Exception:
            pass

    # 回退扫描
    all_devices = discover_devices(timeout=5)
    if not all_devices:
        raise Exception("未发现博联设备，请确认：\n1. 电脑和博联设备在同一个局域网\n"
                        "2. Windows 防火墙允许 UDP 端口 80 的入站/出站通信")
    d = all_devices[0]
    d.auth()
    # 更新到 config
    new_mac = d.mac.hex() if isinstance(d.mac, bytes) else str(d.mac)
    _cfg.add_or_update_device(new_mac, {
        "host": d.host[0] if isinstance(d.host, tuple) else str(d.host),
        "port": d.host[1] if isinstance(d.host, tuple) and len(d.host) > 1 else 80,
        "mac": new_mac, "model": d.model, "name": d.name,
    })
    _cfg.save_config(_cfg.config)
    return d


def send_ac(power: str, mode: str, temp: int, fan: str, source="手动", mac=None):
    """发红外码，自动根据当前设备品牌选择协议。
       source: \"手动\" | \"定时\" | \"自动\" — 写入日志的前缀
       mac: 设备 MAC，不传则用当前选中设备"""
    if not mac:
        mac = _cfg.config.get("current_device_mac", "")
    dev = _cfg.config.get("devices", {}).get(mac, {})
    brand = _cfg.resolve_brand(dev.get("brand", "格力"))
    t = min(max(temp, 16), 30)

    # 优先 hvac_ir（标准化 API），回退自定义 protocols
    try:
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
    except (ModuleNotFoundError, AttributeError):
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
    d = get_device(mac)
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


def decide_ac(outdoor, mac=None):
    """根据室外温度 + 当前设备规则，返回 (目标温度, 模式)"""
    if not mac:
        mac = _cfg.config.get("current_device_mac", "")
    dev = _cfg.config.get("devices", {}).get(mac, {})
    rules = dev.get("temp_rules", [])
    if not rules:
        return 26, "cool"
    for low, high, target, mode in rules:
        if low <= outdoor <= high:
            return target, mode
    return 26, "cool"

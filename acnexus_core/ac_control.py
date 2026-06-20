"""AC-Nexus Core — 空调控制（博联设备 + 红外发码 + 温度规则）"""

import socket
from datetime import datetime

import broadlink
from broadlink.remote import pulses_to_data

import acnexus_core.config as _cfg
from acnexus_core.logger import write_log


# UI 显示用
MODES = {"制冷": "cool", "制热": "heat", "除湿": "dry", "送风": "fan", "自动": "auto", "关闭": "off"}
FANS = {"自动": "auto", "1 档": "1", "2 档": "2", "3 档": "3"}
MODE_KEYS = {v: k for k, v in MODES.items()}


def _get_primary_ip():
    """获取本机主网卡 IP（能路由到外网的那张）"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '0.0.0.0'


def _subnet_broadcast(ip):
    """根据 IP 和常见子网掩码计算广播地址。假设 /24 网段。"""
    parts = ip.split('.')
    if len(parts) == 4 and not ip.startswith('127.'):
        return '.'.join(parts[:3] + ['255'])
    return '255.255.255.255'


def discover_devices(timeout=5):
    """在主网卡上用子网广播发现博联设备。macOS 上只扫主网卡，避免虚拟网卡超时。"""
    ip = _get_primary_ip()
    broadcast = _subnet_broadcast(ip)
    all_devices = []
    try:
        devices = broadlink.discover(
            timeout=timeout,
            local_ip_address=ip,
            discover_ip_address=broadcast,
            discover_ip_port=80,
        )
        all_devices.extend(devices)
    except Exception as e:
        write_log("系统", f"设备扫描失败 ({ip}): {e}")
    return all_devices


def get_device(mac=None):
    """获取博联设备：优先从 config 读 host 直连，失败扫描"""
    provider = _cfg.config.get("current_brand_type", "broadlink")
    devs = _cfg.config.get("devices", {}).get(provider, {})
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
        raise Exception("未发现博联设备，请确认：\n"
                        "1. 电脑和博联设备在同一个局域网\n"
                        "2. 防火墙允许 UDP 端口 80 的通信")
    d = all_devices[0]
    d.auth()
    # 更新到 config
    new_mac = d.mac.hex() if isinstance(d.mac, bytes) else str(d.mac)
    _cfg.add_or_update_device(new_mac, {
        "host": d.host[0] if isinstance(d.host, tuple) else str(d.host),
        "port": d.host[1] if isinstance(d.host, tuple) and len(d.host) > 1 else 80,
        "mac": new_mac, "model": d.model, "name": d.model or d.name,
    })
    _cfg.save_config(_cfg.config)
    return d


def send_ac(power: str, mode: str, temp: int, fan: str, source="手动", mac=None):
    """发红外码，自动根据当前设备品牌选择协议。
       source: \"手动\" | \"定时\" | \"自动\" — 写入日志的前缀
       mac: 设备 MAC，不传则用当前选中设备"""
    if not mac:
        mac = _cfg.config.get("current_device_mac", "")
        provider = _cfg.config.get("current_brand_type", "broadlink")
        dev = _cfg.config.get("devices", {}).get(provider, {}).get(mac, {})
    else:
        provider, dev = _cfg.find_device(mac)
    raw_brand = dev.get("brand", "格力")
    brand = _cfg.resolve_brand(raw_brand)
    t = min(max(temp, 16), 30)

    # ── 米家 MIoT 局域网分支 ──
    if provider == "xiaomi_cloud":
        from acnexus_core.xiaomi_local import build_miot_cmds, send_miot
        model = dev.get("model", "")
        token = dev.get("token", "")
        host = dev.get("host", "")
        if not host or not token:
            raise Exception(f"米家设备缺少 host/token: host={host} token={bool(token)}")
        cmds = build_miot_cmds(power, mode, t, fan, model, dev.get("miot_spec"))
        send_miot(host, token, cmds)
        now = datetime.now()
        label = {"手动": "手动", "定时": "定时", "自动": "自动调温"}.get(source, source)
        if power == "on":
            return f"[{now:%H:%M}] {label}开机 → {MODE_KEYS.get(mode, mode)} {temp}°C"
        return f"[{now:%H:%M}] {label}关机"

    # ── 自定义品牌：用 ir_learner 生成 raw hex 发送 ──
    if raw_brand != "格力" and raw_brand not in _cfg.AC_BRANDS:
        from acnexus_core.ir_learner import get_raw_code
        raw_hex = get_raw_code(raw_brand, power, mode, t, fan)
        if raw_hex:
            d = get_device(mac)
            d.send_data(bytes.fromhex(raw_hex))
            now = datetime.now()
            return f"[{now:%H:%M}] {'开机' if power == 'on' else '关机'} → {raw_brand} ({mode} {t}°C)"
        return f"[{datetime.now():%H:%M}] 自定义品牌 '{raw_brand}' 中未找到匹配码"

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
            "haier": {"auto": 0, "cool": 0, "dry": 1, "fan": 3, "heat": 2},
            "aux_ac": {"auto": 0, "cool": 1, "dry": 2, "fan": 6, "heat": 4},
            "panasonic": {"auto": 0, "cool": 3, "dry": 2, "fan": 6, "heat": 4},
        }
        fan_maps = {
            "haier": {"auto": 5, "1": 1, "2": 2, "3": 3},
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
        provider = _cfg.config.get("current_brand_type", "broadlink")
        dev = _cfg.config.get("devices", {}).get(provider, {}).get(mac, {})
    else:
        provider, dev = _cfg.find_device(mac)
    rules = dev.get("temp_rules", [])
    if not rules:
        return 26, "cool"
    for low, high, target, mode in rules:
        if low <= outdoor <= high:
            return target, mode
    return 26, "cool"

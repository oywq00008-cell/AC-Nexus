"""MIoT 局域网协议发送器 — 通用 siid/piid 映射"""

from miio import Device

# ── 通用 MIoT siid/piid ──
_POWER = (3, 1)
_MODE  = (3, 2)
_TEMP  = (3, 4)
_FAN   = (4, 2)

_MODES = {"cool": 0, "dry": 4, "fan": 3, "auto": 2}
_FANS  = {"auto": 0, "1": 1, "2": 2, "3": 3}


def build_miot_cmds(power: str, mode: str, temp: int, fan: str, model: str = "") -> list:
    """构建 MIoT set_properties 指令列表。model 参数保留，未来可按需扩展。"""
    if power == "off":
        siid, piid = _POWER
        return [{"siid": siid, "piid": piid, "value": False}]

    cmds = []
    siid, piid = _POWER
    cmds.append({"siid": siid, "piid": piid, "value": True})

    siid, piid = _MODE
    cmds.append({"siid": siid, "piid": piid, "value": _MODES.get(mode, 0)})

    siid, piid = _TEMP
    cmds.append({"siid": siid, "piid": piid, "value": min(max(temp, 16), 30)})

    siid, piid = _FAN
    cmds.append({"siid": siid, "piid": piid, "value": _FANS.get(fan, 0)})

    return cmds


def send_miot(host: str, token: str, cmds: list) -> list:
    """通过局域网 MIoT 发送指令"""
    d = Device(host, token)
    return d.send("set_properties", cmds)

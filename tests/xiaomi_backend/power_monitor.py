"""米家空调伴侣功率监测（待硬件到货后测试）

重要：双线并行，不替代日志方案

- 博联 RM 设备 → 继续用 logger.py 的 get_last_ac_state() 日志推断
- 米家空调伴侣 → 新增功率读取，直接判定空调状态

设计原则：send_ac() / auto_adjust 中根据 dev.type 走不同判定路径
"""


def get_ac_state_broadlink():
    """博联 RM：翻日志推断空调状态（现有方案，不动）"""
    from broadlinkac_core.logger import get_last_ac_state
    return get_last_ac_state()


def get_ac_state_xiaomi(ip: str, token: str):
    """米家空调伴侣：读功率判定空调状态

    返回: {"power": "on"/"off", "watt": float | None}
    """
    # 临时占位，硬件到货后实现
    # from miio import ChuangmiPlug
    # plug = ChuangmiPlug(ip, token)
    # status = plug.status()
    # watt = status.power
    # return {"power": "on" if watt > 50 else "off", "watt": watt}
    return {"power": "off", "watt": None}


def get_ac_state(dev_type: str, **kwargs):
    """统一入口：根据设备类型走不同判定路径"""
    if dev_type == "xiaomi":
        return get_ac_state_xiaomi(kwargs["ip"], kwargs["token"])
    return get_ac_state_broadlink()

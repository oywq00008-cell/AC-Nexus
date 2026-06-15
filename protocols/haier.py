"""
海尔空调红外协议 (实测遥控器 — 9字节状态码)
基于 IRremoteESP8266 ir_Haier.cpp 结构，经14步实测校准
2026-06-15 修正: MSB-first、Pre-header、字段布局匹配实测数据
"""

# 时序常量
HDR_MARK = 3000
HDR_SPACE = 4300
BIT_MARK = 520
ONE_SPACE = 1650
ZERO_SPACE = 650
MSG_SPACE = 150000

# 模式 — Byte[7] bits 7-6 (2-bit)
MODE_AUTO = 0  # 与制冷共享 0, 由 Byte[4] 区分
MODE_COOL = 0
MODE_DRY  = 1
MODE_HEAT = 2
MODE_FAN  = 3

# 风速 — Byte[5] bits 7-5 (3-bit)
FAN_AUTO = 5
FAN_HIGH = 1
FAN_MED  = 2
FAN_LOW  = 3

# 开关
POWER_ON  = 1
POWER_OFF = 0

# 摆风
SWING_OFF = 0
SWING_ON  = 1

# 温度
MIN_TEMP = 16
MAX_TEMP = 30

# 前缀 (实测)
PREFIX = 0xA6


class Haier:
    def __init__(self):
        self.durations = []

    def mark(self, us=HDR_MARK):
        self.durations.append(us)

    def space(self, us=HDR_SPACE):
        self.durations.append(us)

    def bit(self, b):
        self.mark(BIT_MARK)
        if b:
            self.space(ONE_SPACE)
        else:
            self.space(ZERO_SPACE)

    def send_byte(self, byte):
        for i in range(7, -1, -1):  # MSB first — IRremote sendGeneric(true)
            self.bit((byte >> i) & 1)

    def send_generic(self, data):
        """Pre-header: mark(HDR)+space(HDR) + Header: mark(HDR)+space(HDR_GAP) + data + footer"""
        self.mark(HDR_MARK)
        self.space(HDR_MARK)
        self.mark()
        self.space()
        for b in data:
            self.send_byte(b)
        self.mark()
        self.space(MSG_SPACE)

    def send(self, power, mode, fan, temp, swing_v=SWING_OFF, swing_h=SWING_OFF, turbo=False):
        data = bytearray(9)

        t = min(max(temp, MIN_TEMP), MAX_TEMP) - MIN_TEMP  # 0-14

        # Byte 0: Prefix (实测 0xA6)
        data[0] = PREFIX
        # Byte 1: Temp(4bit, bits 4-7) | 固定低4位=0x0C
        data[1] = ((t & 0x0F) << 4) | 0x0C
        # Byte 2: 实测全 0
        data[2] = 0x00
        # Byte 3: 实测全 0
        data[3] = 0x00
        # Byte 4: 模式组标志 (制冷/除湿=0x40, 制热/自动/送风=0xC0)
        data[4] = 0xC0 if mode in (MODE_HEAT, MODE_AUTO, MODE_FAN) else 0x40
        # Byte 5: Fan(3bit, bits 7-5)
        data[5] = ((fan & 0x07) << 5)
        # Byte 6: 实测全 0
        data[6] = 0x00
        # Byte 7: Mode(2bit, bits 7-6)
        data[7] = (mode & 0x03) << 6
        # Byte 8: 实测全 0 (无常量校验)
        data[8] = 0x00

        self.durations = []
        self.send_generic(data)

    def get_durations(self):
        return self.durations

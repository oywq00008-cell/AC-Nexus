"""
海尔空调红外协议 (Haier HSU07-HEA03)
基于 IRremoteESP8266 ir_Haier.cpp v2.8.3 移植
"""

# 时序常量
HDR_MARK = 3000
HDR_SPACE = 4300
BIT_MARK = 520
ONE_SPACE = 1650
ZERO_SPACE = 650
MSG_SPACE = 150000

# 模式和命令常量
MODE_AUTO = 0x00
MODE_COOL = 0x01
MODE_DRY = 0x02
MODE_HEAT = 0x03
MODE_FAN = 0x04

FAN_AUTO = 0x00
FAN_HIGH = 0x01
FAN_MED = 0x02
FAN_LOW = 0x03

POWER_ON = 0x01
POWER_OFF = 0x00

CMD_ON = 1
CMD_OFF = 0
CMD_MODE = 2
CMD_FAN = 3
CMD_TEMP_UP = 4
CMD_TEMP_DOWN = 5

MIN_TEMP = 16
MAX_TEMP = 30
PREFIX = 0xA5

# Swing
VDIR_AUTO = 0
VDIR_SWING = 1
HDIR_AUTO = 0
HDIR_SWING = 1


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
        for i in range(8):
            self.bit((byte >> i) & 1)

    def send_generic(self, data):
        """发送标准海尔帧: 两次 pre-header + Header + data + footer"""
        # Pre-header: 两次 HDR_MARK + HDR_SPACE
        for _ in range(2):
            self.mark()
            self.space()
        # Header
        self.mark()
        self.space()
        # Data
        for b in data:
            self.send_byte(b)
        # Footer: mark + long gap
        self.mark()
        self.space(MSG_SPACE)

    def checksum(self, data):
        """简单求和校验 (除最后一个字节)"""
        return sum(data[:-1]) & 0xFF

    def send(self, power, mode, fan, temp, swing_v=VDIR_SWING, swing_h=HDIR_SWING, turbo=False):
        """
        生成海尔红外码
        power: POWER_ON / POWER_OFF
        mode:  MODE_AUTO / MODE_COOL / MODE_DRY / MODE_FAN / MODE_HEAT
        fan:   FAN_AUTO / FAN_HIGH / FAN_MED / FAN_LOW
        temp:  16-30
        """
        data = bytearray(9)
        # Byte 0: Prefix
        data[0] = PREFIX
        # Byte 1: Command(4bit) | Temp(4bit)
        cmd = CMD_ON if power == POWER_ON else CMD_OFF
        t = min(max(temp, MIN_TEMP), MAX_TEMP) - MIN_TEMP
        data[1] = (t & 0x0F) | ((cmd & 0x0F) << 4)
        # Byte 2: CurrHours(5bit) | unknown=1(1bit) | SwingV(2bit)
        data[2] = 0x20  # unknown=1 at bit5
        if swing_v:
            data[2] |= 0xC0  # swing both directions
        # Byte 3: CurrMins(6bit) | OffTimer(1bit) | OnTimer(1bit)
        data[3] = 0x00  # no timer
        # Byte 4: OffHours(5bit) | Health(1bit)
        data[4] = 0x0C  # OffHours=12 (default)
        # Byte 5: OffMins(6bit) | Fan(2bit)
        data[5] = (fan & 0x03) << 6
        # Byte 6: OnHours(5bit) | Mode(3bit)
        data[6] = (mode & 0x07) << 5
        # Byte 7: OnMins(6bit) | Sleep(1bit)
        data[7] = 0x00
        # Byte 8: Checksum
        data[8] = self.checksum(data)

        self.durations = []
        self.send_generic(data)

    def get_durations(self):
        return self.durations

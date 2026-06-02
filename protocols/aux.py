"""
奥克斯 / AUX 空调红外协议 (Electra 协议)
基于 IRremoteESP8266 ir_Electra.h v2.8.3 移植
"""

HDR_MARK = 9160
HDR_SPACE = 4510
BIT_MARK = 580
ONE_SPACE = 1660
ZERO_SPACE = 530
MSG_SPACE = 20000

# 模式
MODE_AUTO = 0b000
MODE_COOL = 0b001
MODE_DRY = 0b010
MODE_HEAT = 0b100
MODE_FAN = 0b110

# 风速
FAN_AUTO = 0b101
FAN_HIGH = 0b001
FAN_MED = 0b010
FAN_LOW = 0b011

# 开关
POWER_ON = 1
POWER_OFF = 0

# 摆风
SWING_OFF = 0b111
SWING_ON = 0b000

# 温度偏移
TEMP_DELTA = 8   # 存储值 = 实际温度 - 16 + 8
MIN_TEMP = 16
MAX_TEMP = 32

LIGHT_ON = 0x15
LIGHT_OFF = 0x08


class AUX:
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
        for i in range(7, -1, -1):  # MSB first
            self.bit((byte >> i) & 1)

    def checksum(self, data):
        return sum(data[:12]) & 0xFF

    def send(self, power, mode, fan, temp, swing_v=SWING_ON, swing_h=SWING_OFF, turbo=False):
        """
        power: 1=on, 0=off
        mode:  MODE_AUTO / MODE_COOL / MODE_DRY / MODE_HEAT / MODE_FAN
        fan:   FAN_AUTO / FAN_HIGH / FAN_MED / FAN_LOW
        temp:  16-32
        """
        t = min(max(temp, MIN_TEMP), MAX_TEMP)
        data = bytearray(13)

        # Byte 0: unused
        data[0] = 0x00
        # Byte 1: SwingV(3bit) | Temp(5bit)
        data[1] = ((swing_v & 0x07) << 5) | ((t - MIN_TEMP + TEMP_DELTA) & 0x1F)
        # Byte 2: reserved(5bit) | SwingH(3bit)
        data[2] = (swing_h & 0x07)
        # Byte 3: reserved(6bit) | SensorUpdate(1bit) | reserved(1bit)
        data[3] = 0x40
        # Byte 4: reserved(5bit) | Fan(3bit)
        data[4] = (fan & 0x07)
        # Byte 5: reserved(6bit) | Turbo(1bit) | Quiet(1bit)
        data[5] = (1 if turbo else 0)
        # Byte 6: reserved(3bit) | IFeel(1bit) | reserved(1bit) | Mode(3bit)
        data[6] = (mode & 0x07)
        # Byte 7: SensorTemp (8bit)
        data[7] = 0x4A + 25  # default sensor 25°C
        # Byte 8: unused
        data[8] = 0x00
        # Byte 9: reserved(2bit) | Clean(1bit) | reserved(2bit) | Power(1bit) | reserved(2bit)
        data[9] = (power & 0x01) << 5
        # Byte 10: unused
        data[10] = 0x00
        # Byte 11: LightToggle
        data[11] = LIGHT_ON
        # Byte 12: Checksum
        data[12] = self.checksum(data)

        self.durations = []
        # Header
        self.mark()
        self.space()
        # Data
        for b in data:
            self.send_byte(b)
        # Footer
        self.mark()
        self.space(MSG_SPACE)

    def get_durations(self):
        return self.durations

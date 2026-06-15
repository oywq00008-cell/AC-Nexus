"""
奥克斯 / AUX 空调红外协议 (Electra 协议)
基于 IRremoteESP8266 ir_Electra.h v2.8.3 移植
2026-06-15 修正: LSB-first 位序、Byte0=0xC3、BIT_MARK=646、字段布局匹配 C struct bitfield
"""

HDR_MARK = 9166
HDR_SPACE = 4470
BIT_MARK = 646
ONE_SPACE = 1647
ZERO_SPACE = 547
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
        for i in range(8):  # LSB first — 与 IRremoteESP8266 sendGeneric(false) 一致
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
        temp_raw = t - TEMP_DELTA  # 内部值 = 实际温度 - 8
        data = bytearray(13)

        # Byte 0: 固定值 (IRremoteESP8266 stateReset 设为 0xC3)
        data[0] = 0xC3
        # Byte 1: SwingV(3bit, bits 0-2) | Temp(5bit, bits 3-7)
        data[1] = (swing_v & 0x07) | ((temp_raw & 0x1F) << 3)
        # Byte 2: reserved(5bit, bits 0-4) | SwingH(3bit, bits 5-7)
        data[2] = (swing_h & 0x07) << 5
        # Byte 3: 实测遥控器全为 0
        data[3] = 0x00
        # Byte 4: reserved(5bit) | Fan(3bit, bits 5-7); bit2=1 与实测一致
        data[4] = ((fan & 0x07) << 5) | 0x04
        # Byte 5: reserved(6bit, bits 0-5) | Turbo(1bit, bit6)
        data[5] = (1 if turbo else 0) << 6
        # Byte 6: reserved(3bit) | IFeel(bit3) | reserved(bit4) | Mode(3bit, bits 5-7)
        data[6] = (mode & 0x07) << 5
        # Byte 7: 实测遥控器为 0x00
        data[7] = 0x00
        # Byte 8-10
        data[8] = 0x00
        data[9] = (power & 0x01) << 5
        data[10] = 0x00
        # Byte 11: 实测遥控器为 0x05
        data[11] = 0x05
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

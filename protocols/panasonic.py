"""
松下 / Panasonic 空调红外协议 (NKE/DKE 系列)
基于 IRremoteESP8266 ir_Panasonic.h v2.8.3 移植
"""

HDR_MARK = 3500
HDR_SPACE = 1750
BIT_MARK = 435
ONE_SPACE = 1300
ZERO_SPACE = 480
MSG_SPACE = 10000

# 模式
MODE_AUTO = 0
MODE_DRY = 2
MODE_COOL = 3
MODE_HEAT = 4
MODE_FAN = 6

# 风速
FAN_AUTO = 7
FAN_MIN = 0
FAN_LOW = 1
FAN_MED = 2
FAN_HIGH = 3
FAN_MAX = 4

# 开关
POWER_ON = 1
POWER_OFF = 0

# 摆风
VDIR_AUTO = 0xF
VDIR_MIDDLE = 0x3
HDIR_AUTO = 0xD
HDIR_MIDDLE = 0x6

MIN_TEMP = 16
MAX_TEMP = 30


class Panasonic:
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
        for i in range(7, -1, -1):
            self.bit((byte >> i) & 1)

    def calc_checksum(self, data):
        """Panasonic checksum: initial 0xF4, XOR all bytes"""
        cks = 0xF4
        for b in data:
            cks ^= b
        return cks

    def send(self, power, mode, fan, temp, swing_v=VDIR_AUTO, swing_h=HDIR_AUTO,
             turbo=False, quiet=False):
        """
        基于已知良好状态模板修改关键字段
        """
        state = bytearray([
            0x02, 0x20, 0xE0, 0x04, 0x00, 0x00, 0x00, 0x06, 0x02,
            0x20, 0xE0, 0x04, 0x00, 0x00, 0x00, 0x80, 0x00, 0x00,
            0x00, 0x0E, 0xE0, 0x00, 0x00, 0x81, 0x00, 0x00, 0x00
        ])

        # Byte[0]: Power bit = bit0, Mode bits
        t = min(max(temp, MIN_TEMP), MAX_TEMP)
        temp_val = t - MIN_TEMP  # 0-14

        if power:
            state[0] = (mode & 0x07) | 0x08  # Power on + mode
        else:
            state[0] = mode & 0x07  # Power off + mode

        # Byte[1]: Temp(5bit offset 1) + ?
        state[1] = (state[1] & 0xC1) | ((temp_val & 0x1F) << 1)

        # Fan speed in state[16]
        fan_val = fan & 0x0F
        state[16] = (state[16] & 0xF0) | min(fan_val, 7)

        # Swing
        state[17] = (swing_v & 0x0F) | ((swing_h & 0x0F) << 4)

        # Turbo / Quiet
        if turbo:
            state[5] |= 0x20   # Powerful bit
            state[5] &= ~0x01  # Clear quiet
        elif quiet:
            state[5] |= 0x01   # Quiet bit
            state[5] &= ~0x20  # Clear powerful

        # Checksum at byte 26
        state[26] = self.calc_checksum(state[:26])

        self.durations = []
        # Header
        self.mark()
        self.space()
        # 2 frames with gap between
        for _ in range(2):
            for b in state:
                self.send_byte(b)
            if _ == 0:
                self.mark()
                self.space(MSG_SPACE)
        self.mark()

    def get_durations(self):
        return self.durations

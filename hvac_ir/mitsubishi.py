from . import ACProtocol


class Mitsubishi(ACProtocol):
    # Midea timing constants
    HDR_MARK = 3500
    HDR_SPACE = 1700
    BIT_MARK = 430
    ONE_SPACE = 1250
    ZERO_SPACE = 390
    MSG_SPACE = 17500

    # MIDEA codes

    MITSUBISHI_AIRCON1_MODE_AUTO = 0x20
    MITSUBISHI_AIRCON3_MODE_AUTO = 0x60  # FA auto mode
    MITSUBISHI_AIRCON1_MODE_HEAT = 0x08
    MITSUBISHI_AIRCON3_MODE_HEAT = 0x48  # FA heat mode
    MITSUBISHI_AIRCON1_MODE_COOL = 0x18
    MITSUBISHI_AIRCON2_MODE_COOL = 0x18  # MSY cool mode
    MITSUBISHI_AIRCON3_MODE_COOL = 0x58  # FA cool mode
    MITSUBISHI_AIRCON1_MODE_DRY = 0x10
    MITSUBISHI_AIRCON2_MODE_DRY = 0x18  # MSY DRY mode
    MITSUBISHI_AIRCON3_MODE_DRY = 0x50  # FA dry mode
    MITSUBISHI_AIRCON1_MODE_FAN = 0x38  # EF 'FAN' mode
    MITSUBISHI_AIRCON2_MODE_FAN = 0x38  # MSY fan mode
    MITSUBISHI_AIRCON1_MODE_ISEE = 0x40  # Isee
    MITSUBISHI_AIRCON2_MODE_IFEEL = 0x00  # MSY

    MITSUBISHI_AIRCON1_MODE_OFF = 0x00  # Power OFF
    MITSUBISHI_AIRCON1_MODE_ON = 0x20  # Power ON
    MITSUBISHI_AIRCON1_FAN_AUTO = 0x40
    MITSUBISHI_AIRCON1_FAN1 = 0x60
    MITSUBISHI_AIRCON1_FAN2 = 0x80
    MITSUBISHI_AIRCON1_FAN3 = 0xA0

    temperatures = [0, 8, 12, 4, 6, 14, 10, 2, 3, 11, 9, 1, 5, 13]

    op_modes = {
        ACProtocol.MODE_AUTO: MITSUBISHI_AIRCON1_MODE_AUTO,
        ACProtocol.MODE_HEAT: MITSUBISHI_AIRCON1_MODE_HEAT,
        ACProtocol.MODE_COOL: MITSUBISHI_AIRCON1_MODE_COOL,
        ACProtocol.MODE_DRY: MITSUBISHI_AIRCON1_MODE_DRY,
        ACProtocol.MODE_FAN: MITSUBISHI_AIRCON1_MODE_FAN,
    }

    fan_speeds = {
        ACProtocol.FAN_AUTO: MITSUBISHI_AIRCON1_FAN_AUTO,
        ACProtocol.FAN_1: MITSUBISHI_AIRCON1_FAN1,
        ACProtocol.FAN_2: MITSUBISHI_AIRCON1_FAN2,
        ACProtocol.FAN_3: MITSUBISHI_AIRCON1_FAN3,
    }

    def __init__(self):
        ACProtocol.__init__(self)

    @classmethod
    def list_modes(cls):
        return list(cls.op_modes)

    @classmethod
    def list_fan_speeds(cls):
        return list(cls.fan_speeds)

    # noinspection PyUnusedLocal
    def send(self, power_mode_cmd, operating_mode_cmd, fan_speed_cmd, temperature_cmd, swing_v_cmd, swing_h_cmd,
             turbo_cmd=False):
        operating_mode = self.MITSUBISHI_AIRCON1_MODE_OFF if power_mode_cmd == self.POWER_OFF \
            else self.op_modes.get(operating_mode_cmd, self.MITSUBISHI_AIRCON1_MODE_HEAT)
        fan_speed = self.fan_speeds.get(fan_speed_cmd, self.MITSUBISHI_AIRCON1_FAN_AUTO)
        temperature = 23
        if 16 < temperature_cmd < 31:
            temperature = self.temperatures[(temperature_cmd - 17)]
        self.durations = []
        self.send_midea(operating_mode, fan_speed, temperature)

    def send_midea(self, operating_mode, fan_speed, temperature):
        send_buffer = bytearray(b'\x4d\xde\x07')  # Turn OFF default value
        if operating_mode != self.MITSUBISHI_AIRCON1_MODE_OFF:
            send_buffer[1] = ~fan_speed & 0xFF
            if operating_mode == self.MITSUBISHI_AIRCON1_MODE_FAN:
                send_buffer[2] = self.MITSUBISHI_AIRCON1_MODE_DRY | 0x07
            else:
                send_buffer[2] = operating_mode | temperature
        return self.send_midea_raw(send_buffer)

    def send_midea_raw(self, send_buffer):

        self.durations.extend([self.HDR_MARK, self.HDR_SPACE, ])
        for i in range(3):
            self.send_byte(send_buffer[i])
            self.send_byte(~send_buffer[i])
        self.mark()
        self.space(self.MSG_SPACE)
        self.mark(self.HDR_MARK)
        self.space(self.HDR_SPACE)

        for i in range(3):
            self.send_byte(send_buffer[i])
            self.send_byte(~send_buffer[i])
        self.mark()
        self.space(0)

from machine import I2C, Pin
import time

_SDA = 12
_SCL = 11
_ADDRS = (0x6B, 0x6A)  # SA0 floating — probe entrambi

_REG_WHO_AM_I = 0x00
_REG_RESET    = 0x60
_REG_CTRL1    = 0x02
_REG_CTRL2    = 0x03
_REG_CTRL7    = 0x08
_REG_TEMP_L   = 0x33

_WHO_AM_I_VAL = 0x05


class IMU:

    def __init__(self):
        self._ok = False
        self._addr = None
        try:
            self._i2c = I2C(0, scl=Pin(_SCL), sda=Pin(_SDA), freq=400_000)
            self._probe()
            if self._addr is not None:
                self._init_hw()
                self._ok = True
        except Exception as e:
            print(f"[imu] Init failed: {e}")

    def _probe(self):
        for addr in _ADDRS:
            try:
                who = self._i2c.readfrom_mem(addr, _REG_WHO_AM_I, 1)[0]
                if who == _WHO_AM_I_VAL:
                    self._addr = addr
                    print(f"[imu] QMI8658C found at 0x{addr:02X}")
                    return
            except Exception:
                pass
        print("[imu] QMI8658C not found")

    def _write(self, reg, val):
        self._i2c.writeto_mem(self._addr, reg, bytes([val]))

    def _read(self, reg, n):
        return self._i2c.readfrom_mem(self._addr, reg, n)

    def _init_hw(self):
        self._write(_REG_RESET, 0xB0)   # soft reset
        time.sleep_ms(50)
        self._write(_REG_CTRL1, 0x40)   # auto-increment indirizzi
        self._write(_REG_CTRL2, 0x16)   # accel ±4g 125Hz
        self._write(_REG_CTRL7, 0x01)   # enable accel (necessario per la temperatura)

    def get_temperature(self):
        """Returns ambient temperature in Celsius, or None on error."""
        if not self._ok:
            return None
        try:
            raw = self._read(_REG_TEMP_L, 2)
            val = (raw[1] << 8) | raw[0]
            if val >= 0x8000:
                val -= 0x10000
            return round(val / 256.0 - 20.0, 1)
        except Exception:
            return None


imu = IMU()

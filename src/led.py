from machine import Pin
import neopixel
import time
from board import RGB_PWR, RGB_DATA

dim = 0.2  # brightness dimming factor (0.0-1.0)
class RGBStatus:

    def __init__(self):
        self._ok = False
        try:
            Pin(RGB_PWR, Pin.OUT, value=1)
            self._np = neopixel.NeoPixel(Pin(RGB_DATA), 1)
            self._np[0] = (0, 0, 0)
            self._np.write()
            self._ok = True
        except Exception as e:
            print(f"[led] Init failed: {e}")

    def _set(self, r, g, b):
        if not self._ok:
            return
        self._np[0] = (g, r, b)  # WS2812B wire order is GRB, not RGB
        self._np.write()

    def update(self, is_ap, is_sta, sim_connected, alpaca_connected, is_moving):
        """
        States (priority order):
          is_moving     → green breathing (triangular fade, period 2s)
          alpaca_connected → green solid
          is_sta and sim_connected → cyan
          is_sta        → yellow
          AP mode       → blue
        """
        if not self._ok:
            return
        if is_moving:
            t = time.ticks_ms() % 2000
            bright = t / 1000.0 if t < 1000 else (2000 - t) / 1000.0
            self._set(0, int(200 * bright * dim)+1, 0)
        elif alpaca_connected:
            self._set(0, int(200 * dim)+1, 0)
        elif is_sta and sim_connected:
            self._set(0, int(180 * dim)+1, int(180 * dim)+1)
        elif is_sta:
            self._set(int(200 * dim)+1, int(160 * dim)+1, 0)
        else:
            self._set(0, 0, int(200 * dim)+1)


led = RGBStatus()

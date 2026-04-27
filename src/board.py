"""
Hardware pin map for LoLin S3 Mini Pro (schematic v1.0.0).

All constants use micropython.const() to avoid runtime dict lookups.
"""

from micropython import const

# Display GC9107
TFT_MOSI = const(38)
TFT_CLK  = const(40)
TFT_CS   = const(35)
TFT_DC   = const(36)
TFT_RST  = const(34)
TFT_BL   = const(33)

# RGB LED WS2812B
RGB_PWR  = const(7)
RGB_DATA = const(8)

# IMU QMI8658C (I2C bus 0)
IMU_SDA  = const(12)
IMU_SCL  = const(11)

# Buttons (active-low, internal pull-up)
BTN_LEFT   = const(0)   # IO0 BOOT — move in
BTN_CENTER = const(47)  # IO47     — cycle step / long-press halt
BTN_RIGHT  = const(48)  # IO48     — move out

import time
import framebuf
from machine import SPI, Pin
from board import TFT_MOSI, TFT_CLK, TFT_CS, TFT_DC, TFT_RST, TFT_BL

_WIDTH  = 128
_HEIGHT = 128

# RGB565 color constants
BLACK  = 0x0000
WHITE  = 0xFFFF
RED    = 0xF800
GREEN  = 0x07E0
BLUE   = 0x001F
YELLOW = 0xFFE0
CYAN   = 0x07FF
ORANGE = 0xFD20
GRAY   = 0x8410


def _swap16(color):
    return ((color & 0xFF) << 8) | (color >> 8)


class StatusDisplay:

    def __init__(self):
        self._ok = False
        self._last_state = None
        try:
            self._init_hw()
            self._ok = True
        except Exception as e:
            print(f"[display] Init failed: {e}")

    def _init_hw(self):
        self._dc  = Pin(TFT_DC,  Pin.OUT, value=0)
        self._cs  = Pin(TFT_CS,  Pin.OUT, value=1)
        self._rst = Pin(TFT_RST, Pin.OUT, value=1)
        self._bl  = Pin(TFT_BL,  Pin.OUT, value=0)

        self._spi = SPI(
            1,
            baudrate=40_000_000,
            polarity=0,
            phase=0,
            sck=Pin(TFT_CLK),
            mosi=Pin(TFT_MOSI),
        )

        # Allocate framebuffer (128×128×2 bytes, RGB565 little-endian in MicroPython)
        self._buf = bytearray(_WIDTH * _HEIGHT * 2)
        self._fb  = framebuf.FrameBuffer(self._buf, _WIDTH, _HEIGHT, framebuf.RGB565)
        self._tmp = bytearray(512)  # reused by show() to avoid GC pressure

        self._hard_reset()
        self._send_init_sequence()

    def _hard_reset(self):
        self._rst(1)
        time.sleep_ms(10)
        self._rst(0)
        time.sleep_ms(10)
        self._rst(1)
        time.sleep_ms(50)

    def _cmd(self, cmd):
        self._dc(0)
        self._cs(0)
        self._spi.write(bytes([cmd]))
        self._cs(1)

    def _data(self, *args):
        self._dc(1)
        self._cs(0)
        self._spi.write(bytes(args))
        self._cs(1)

    def _cmd_data(self, cmd, *args):
        self._cmd(cmd)
        if args:
            self._data(*args)

    def _send_init_sequence(self):
        self._cmd(0xFE)                   # Inter Register Enable 1
        self._cmd(0xEF)                   # Inter Register Enable 2
        self._cmd_data(0x36, 0x08)        # MADCTL: BGR=1
        self._cmd_data(0x3A, 0x05)        # Pixel Format: RGB565
        self._cmd_data(0xB0, 0xC0)
        self._cmd_data(0xB1, 0x80)
        self._cmd_data(0xB2, 0x27)
        self._cmd_data(0xB3, 0x13)
        self._cmd_data(0xB6, 0x00, 0x00)
        self._cmd_data(0xB7, 0x35)
        self._cmd_data(0xAC, 0xC8)
        self._cmd_data(0xAB, 0x0E)
        self._cmd_data(0xB4, 0x04)
        self._cmd_data(0xA8, 0x19)
        self._cmd_data(0xB8, 0x08)
        self._cmd_data(0xE8, 0x24)
        self._cmd_data(0xBB, 0x27)
        self._cmd_data(0xBC, 0x47)
        self._cmd_data(0xC0, 0xE9)
        self._cmd_data(0xC1, 0x11)
        self._cmd_data(0xC2, 0x07)
        self._cmd_data(0xC7, 0x08)
        self._cmd_data(0xCC, 0x10)
        self._cmd_data(0xCD, 0x08)
        self._cmd(0x21)                   # INVON — hardware color inversion must be cancelled
        self._cmd(0x11)                   # Sleep Out
        time.sleep_ms(120)
        self._cmd(0x29)                   # Display On
        self._bl(1)                       # Backlight ON

    def _set_window(self, x0, y0, x1, y1):
        # Physical offset: visible area starts at column +2, row +1
        x0 += 2; x1 += 2
        y0 += 1; y1 += 1

        self._cmd(0x2A)
        self._data(x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF)
        self._cmd(0x2B)
        self._data(y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF)
        self._cmd(0x2C)

    def _hline(self, y, color):
        self._fb.hline(0, y, _WIDTH, color)

    def show(self):
        self._set_window(0, 0, _WIDTH - 1, _HEIGHT - 1)

        # MicroPython framebuf.RGB565 is little-endian; SPI needs big-endian (byte-swap every pixel)
        chunk_size = 512
        view = memoryview(self._buf)
        length = len(self._buf)
        tmp = self._tmp

        self._dc(1)
        self._cs(0)
        offset = 0
        while offset < length:
            end = min(offset + chunk_size, length)
            seg = view[offset:end]
            seg_len = end - offset
            for i in range(0, seg_len, 2):
                tmp[i]   = seg[i + 1]
                tmp[i + 1] = seg[i]
            self._spi.write(tmp[:seg_len])
            offset = end
        self._cs(1)

    def _draw_screen(self, wifi_state, wifi_ssid, wifi_ip, is_ap, focuser_connected, focuser_mode='hardware', alpaca_client=False, focuser_position=None, step=1):
        fb = self._fb
        fb.fill(BLACK)

        # Title
        fb.text("  ROBOFOCUS", 0, 4, YELLOW)

        # Separator
        self._hline(18, BLUE)

        # Mode
        mode_str = "MODE: AP " if is_ap else "MODE: STA"
        fb.text(mode_str, 0, 26, CYAN)

        # SSID or IP
        if is_ap:
            ssid_trunc = (wifi_ssid or "")[:9]
            fb.text("SSID:" + ssid_trunc, 0, 38, WHITE)
        else:
            ip_str = (wifi_ip or "")
            fb.text("IP:" + ip_str, 0, 38, WHITE)

        # Separator
        self._hline(54, BLUE)

        # Focuser status
        if focuser_connected:
            if focuser_mode == 'simulator':
                fb.text("FOCUS:SIM", 0, 62, CYAN)
            else:
                fb.text("FOCUS: OK", 0, 62, GREEN)
        else:
            fb.text("FOCUS: --", 0, 62, ORANGE)

        # Alpaca client status
        if alpaca_client:
            fb.text("ALPACA:YES", 0, 74, GREEN)
        else:
            fb.text("ALPACA: NO", 0, 74, ORANGE)

        # Separator
        self._hline(90, BLUE)

        if focuser_position is not None:
            pos_str = "POS:" + str(focuser_position)
        else:
            pos_str = "POS: ----"
        fb.text(pos_str, 0, 98, GRAY)

        fb.text("STEP:" + str(step), 0, 110, WHITE)

    def update(self, wifi_state, wifi_ssid, wifi_ip, is_ap, focuser_connected, focuser_mode='hardware', alpaca_client=False, focuser_position=None, step=1):
        if not self._ok:
            return

        state = (wifi_state, wifi_ssid, wifi_ip, is_ap, focuser_connected, focuser_mode, alpaca_client, focuser_position, step)
        if state == self._last_state:
            return
        self._last_state = state

        self._draw_screen(wifi_state, wifi_ssid, wifi_ip, is_ap, focuser_connected, focuser_mode, alpaca_client, focuser_position, step)
        self.show()


display = StatusDisplay()

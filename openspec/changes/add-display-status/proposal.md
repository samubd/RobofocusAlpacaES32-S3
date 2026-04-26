# Change: Add GC9107 display status screen

## Why
The LoLin S3 Mini Pro board has an onboard 0.85" 128×128 TFT LCD (GC9107 controller).
Without it, the only way to know the device state (Wi-Fi mode, focuser connection) is via serial console or web UI. Adding a status screen makes the device self-describing during setup and field use.

## What Changes
- New module `display.py`: GC9107 SPI driver + status rendering via MicroPython `framebuf`
- `main.py`: initialise display at boot, call `display.update()` on every state-change cycle
- Static layout shows: mode (AP/STA), SSID or IP, Robofocus connection status, Alpaca server status

## Impact
- Affected specs: display (new capability)
- Affected code: `src/display.py` (new), `src/main.py` (modified)
- No breaking changes to Alpaca API or serial protocol

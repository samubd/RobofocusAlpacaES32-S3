# Project Context

## Purpose
ASCOM Alpaca server running on an ESP32-S3 microcontroller (MicroPython) for controlling a Robofocus electronic focuser. The device connects to the focuser via UART/serial, exposes an Alpaca-compliant REST API over Wi-Fi, and can be discovered by astronomy clients (NINA, Voyager, SGP) on the local network without any PC-side software.

## Tech Stack
- MicroPython (ESP32-S3 target — LoLin S3 Mini Pro, 4 MB Flash, 2 MB PSRAM)
- `uasyncio` for cooperative multitasking (3 concurrent tasks: main/1 Hz, led/20 Hz, buttons/10 Hz)
- Built-in `network` module for Wi-Fi (STA + AP fallback)
- Built-in `machine.UART` for serial communication with Robofocus
- Built-in `machine.SPI` for GC9107 display (40 MHz)
- Built-in `machine.I2C` for QMI8658C IMU (400 kHz)
- Built-in `neopixel` for WS2812B RGB LED
- Built-in HTTP server (no FastAPI/uvicorn)
- `ujson` / `json` for JSON serialisation

## Project Conventions

### Code Style
- MicroPython-compatible Python (no type hints in hot paths)
- No third-party packages (must run without pip)
- Keep memory footprint minimal (avoid large string operations in loops)

### Architecture Patterns
- **3-Layer Focuser Architecture**:
  - Layer 1: `serial_protocol.py` – UART communication with Robofocus
  - Layer 2: `controller.py` – Focuser state machine (business logic); IMU as primary temperature source
  - Layer 3: `alpaca_api.py` – Alpaca HTTP endpoint handlers
- `web_server.py` – minimal async HTTP routing with Keep-Alive
- `discovery.py` – UDP broadcast for Alpaca discovery (port 32227)
- `wifi_manager.py` – Wi-Fi STA connect / AP fallback
- `main.py` – MicroPython entry point; 3 async tasks (main loop, led_loop, button_loop)
- `board.py` – centralised pin map with `micropython.const()` (single source of truth for GPIO)
- `display.py` – GC9107 driver, state-change guard, pre-allocated SPI swap buffer
- `led.py` – WS2812B state machine (AP/STA/moving/Alpaca-client states)
- `buttons.py` – ISR-based debounce, long-press detection, producer/consumer pattern
- `imu.py` – QMI8658C temperature via I2C; -20 °C offset for self-heating compensation
- `log_buffer.py` – circular buffer (100 entries); hooks `builtins.print` at boot
- **Simulator Mode**: `simulator.py` replaces serial hardware for testing without Robofocus

### Deployment
- Flash MicroPython firmware to ESP32-S3, then upload `src/` files via `mpremote` or Thonny
- Firmware binary provided in `src/firmware/`

### Git Workflow
- Main branch for stable releases
- Feature branches: `feature/<name>`
- Commit messages: Conventional Commits format
- Co-authored by: Claude Sonnet 4.6 <noreply@anthropic.com>

## Domain Context

### ASCOM Alpaca Protocol
- RESTful API standard for astronomy devices (v1)
- Discovery via UDP broadcast on port 32227
- HTTP endpoints follow `/api/v1/focuser/{device_id}/` pattern
- Responses in JSON envelope with ClientTransactionID/ServerTransactionID
- Error codes: 0x400-0x5FF range

### Robofocus Hardware
- Electronic focuser for telescopes (deep-sky astrophotography)
- RS-232 serial communication (9600 baud, 8N1) → connected to ESP32 UART
- Fixed 9-byte command/response protocol
- Supports absolute positioning, temperature sensor, backlash compensation
- Used with clients: NINA, Voyager, Sequence Generator Pro (SGP)

### Astrophotography Workflow
- Focuser integrates in autofocus routines (HFR/FWHM optimisation)
- Typical session: 4-8 hours unattended imaging
- Reliability critical: failed focus = lost data
- Temperature compensation needed (focus shifts with temp)

## Important Constraints

### Hardware Limitations
- Serial communication is synchronous (no concurrent commands)
- Robofocus firmware timeout: 3-5 seconds per command
- No absolute encoder: power loss = position unknown
- Movement speed fixed by motor configuration (not controllable via API)
- ESP32-S3 RAM: ~320 KB usable for MicroPython heap

### Software Constraints
- Must run entirely on MicroPython – no CPython-only libraries
- Wi-Fi must support both Station (STA) mode and AP fallback for first-time setup
- Alpaca standard compliance mandatory (NINA compatibility)
- Web UI served from `src/static/` as embedded files

### Performance Requirements
- API response time: <200ms for GET requests (over local Wi-Fi)
- Move command initiation: <100ms
- Uptime target: multi-night sessions (hours unattended)

## External Dependencies

### Reference Implementations
- `ASCOM.NGCAT.Focuser` (C# ASCOM driver) – protocol reference
- `robofocus.cpp` (INDI driver) – alternative implementation
- ASCOM Alpaca API specification v1

### Client Software
- NINA (Nighttime Imaging 'N' Astronomy) – primary target
- Voyager Advanced – secondary target
- Sequence Generator Pro (SGP) – tertiary target

### Hardware
- Robofocus electronic focuser (various firmware versions)
- ESP32-S3 LoLin S3 Mini Pro (4 MB Flash, 2 MB PSRAM)
- RS-232 level shifter (MAX3232 or similar) between ESP32 UART and Robofocus DB9
- GC9107 128×128 SPI display (on-board)
- WS2812B RGB LED (on-board, IO7=power, IO8=data)
- QMI8658C IMU — I2C IO11/IO12; used for ambient temperature (primary source for Alpaca)
- 3 tactile buttons: IO0 (BOOT/move-in), IO47 (step-cycle/halt), IO48 (move-out)

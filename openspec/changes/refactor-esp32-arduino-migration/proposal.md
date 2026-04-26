# Change: Migrazione ESP32 da MicroPython ad Arduino/C++

## Why

L'implementazione MicroPython dell'ESP32 Alpaca server ha mostrato prestazioni insoddisfacenti nei test reali:

- **GIL e uasyncio**: il Global Interpreter Lock di MicroPython serializza tutto il lavoro I/O; `uasyncio` e` cooperativo e non puo` sfruttare i due core dell'ESP32 (Xtensa LX6 dual-core)
- **Garbage Collector**: pause stop-the-world del GC MicroPython causano spike di latenza (osservati 100-500ms) incompatibili con il requisito di risposta HTTP <100ms
- **HTTP server custom**: il web server scritto sopra `uasyncio` ha overhead elevato per ogni richiesta (parsing in Python puro, allocazioni frequenti)
- **Memoria**: MicroPython consuma ~60-80KB di RAM per il runtime, lasciando ~120-140KB per l'applicazione; il firmware Arduino lascia >200KB disponibili per heap applicativo

La conseguenza pratica e` che durante sessioni di autofocus con NINA (50+ richieste ravvicinate) si osservano timeout e risposte lente che degradano la qualita` dell'autofocus.

## What Changes

Riscrittura completa del firmware ESP32 in C++ con il framework Arduino (PlatformIO), mantenendo **identica** la superficie API esterna (Alpaca v1, Web GUI, Discovery UDP).

### Stack tecnico adottato

| Componente | MicroPython (attuale) | Arduino/C++ (nuovo) |
|---|---|---|
| HTTP server | custom su uasyncio | ESPAsyncWebServer (non-blocking, FreeRTOS) |
| JSON | `json` stdlib | ArduinoJson 7 |
| UDP discovery | custom socket | AsyncUDP |
| File statici | filesystem interno | LittleFS (SPIFFS successor) |
| WiFi provisioning | custom AP+web | WiFiManager (captive portal) |
| Config persistenza | NVS (MicroPython) | Preferences (NVS wrapper Arduino) |
| Seriale | `machine.UART` | `HardwareSerial` / `SoftwareSerial` |
| Build system | mpremote / ampy | PlatformIO + platformio.ini |
| Linguaggio | Python 3 (MicroPython) | C++17 |

### Struttura progetto risultante

```
esp32-arduino/
├── platformio.ini          # Toolchain, dipendenze, target board
├── src/
│   ├── main.cpp            # setup() + loop(), boot sequence
│   ├── wifi_manager.cpp/.h # WiFi STA/AP, captive portal
│   ├── alpaca_api.cpp/.h   # Route Alpaca REST (device_id=0)
│   ├── gui_api.cpp/.h      # Route Web GUI
│   ├── discovery.cpp/.h    # UDP broadcast porta 32227
│   ├── controller.cpp/.h   # Logica focuser, state machine
│   ├── serial_protocol.cpp/.h # Protocollo 9-byte Robofocus
│   └── simulator.cpp/.h    # Simulatore hardware (no UART)
└── data/                   # Filesystem LittleFS
    ├── index.html          # Control panel
    ├── setup.html          # WiFi config (fallback)
    └── logs.html           # Log viewer
```

### Comportamento invariato (nessuna breaking change lato client)

- Tutti gli endpoint Alpaca `/api/v1/focuser/0/*` rimangono identici
- Discovery UDP porta 32227 invariato
- Web GUI accessibile via browser identica
- AP mode per configurazione iniziale WiFi invariato
- Modalita` simulator/hardware selezionabile da GUI invariata

## Impact

### Specifiche nuove (ADDED)

- **specs/esp32-firmware**: requisiti per il firmware Arduino, sostituisce l'implementazione MicroPython non formalmente specificata

### Codice coinvolto

- **REMOVED**: `esp32/*.py` (tutti i file MicroPython)
- **REMOVED**: `esp32/firmware/ESP32_GENERIC-20241129-v1.24.1.bin` (firmware MicroPython)
- **ADDED**: `esp32-arduino/` (nuovo progetto PlatformIO)
- **RETAINED**: `esp32/static/*.html` (riutilizzati in `esp32-arduino/data/`)

### Breaking Changes

Nessuna breaking change lato client ASCOM Alpaca (NINA, Voyager, SGP).

**BREAKING** per sviluppatori: il workflow di deploy cambia da `mpremote` a `pio run --target uploadfs && pio run --target upload`.

### Rischi

- **Curva di apprendimento C++**: la gestione manuale della memoria in C++ richiede attenzione (stack overflow, heap fragmentation)
- **ESPAsyncWebServer e thread safety**: le callback HTTP girano in task FreeRTOS separati; accessi allo stato condiviso richiedono mutex espliciti
- **WiFiManager overhead**: la libreria aggiunge ~30KB al firmware ma elimina codice custom non testato
- **Regressioni API**: il porting da Python a C++ puo` introdurre differenze sottili nel comportamento dei JSON response; servono test end-to-end con NINA prima del rilascio

### Success Criteria

- GET `/api/v1/focuser/0/position` risponde in <50ms (p99) sotto carico NINA autofocus
- Nessun timeout HTTP durante sessione autofocus di 20+ movimenti consecutivi
- Uptime 24h senza reset watchdog
- NINA discovery funzionante entro 5 secondi dall'avvio
- Flash firmware via `pio run --target upload` in <30 secondi

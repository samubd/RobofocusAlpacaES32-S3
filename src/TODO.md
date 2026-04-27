# Robofocus ESP32 - Stato del Progetto e TODO

## Panoramica

Server ASCOM Alpaca per ESP32 che controlla un focuser Robofocus via protocollo seriale.
Permette il controllo del focuser da software astronomici come NINA, SGP, etc.

## Architettura

```
┌─────────────────────────────────────────────────────────────┐
│                        ESP32-S3                              │
├─────────────────────────────────────────────────────────────┤
│  main.py            - Entry point, boot sequence, task loop │
│  board.py           - Pin map centralizzata (micropython.const)│
│  wifi_manager.py    - WiFi STA/AP mode management           │
│  web_server.py      - HTTP server async lightweight         │
│  alpaca_api.py      - ASCOM Alpaca REST API endpoints       │
│  gui_api.py         - Web GUI REST endpoints + /gui/logs    │
│  discovery.py       - UDP discovery (port 32227)            │
│  controller.py      - Logica focuser, dual mode support     │
│  serial_protocol.py - Protocollo seriale Robofocus          │
│  simulator.py       - Simulatore focuser (no hardware)      │
│  config.py          - Configurazione NVS (persistente)      │
│  log_buffer.py      - Buffer circolare, hook su print()     │
│  display.py         - Driver GC9107 128x128, status screen  │
│  led.py             - WS2812B RGB LED, state machine        │
│  buttons.py         - 3 pulsanti con debounce e long-press  │
│  imu.py             - QMI8658C: temperatura ambiente via I2C│
├─────────────────────────────────────────────────────────────┤
│  static/index.html  - Control Panel web GUI                 │
│  static/setup.html  - WiFi configuration page               │
│  static/logs.html   - System logs viewer                    │
└─────────────────────────────────────────────────────────────┘
```

## Flusso di Boot

1. Se nessun WiFi configurato → AP mode (`Robofocus-XXXX`)
2. Utente si connette all'AP e configura WiFi via `setup.html`
3. ESP32 si connette alla rete WiFi configurata
4. In STA mode: attiva API Alpaca + Discovery + Web GUI
5. Monitor WiFi: se perde connessione, fallback ad AP mode

## Cosa Funziona

- [x] AP mode per configurazione iniziale
- [x] Scan reti WiFi (fix applicato per MicroPython `decode()`)
- [x] Connessione a rete WiFi
- [x] Salvataggio credenziali in NVS
- [x] Web server HTTP async con Keep-Alive
- [x] Web GUI control panel (`index.html`)
- [x] Discovery UDP Alpaca (porta 32227)
- [x] Registrazione route Alpaca dopo connessione WiFi
- [x] API Alpaca base (connected, position, ismoving, move, halt, temperature, ecc.)
- [x] Modalità Simulator — funziona senza hardware Robofocus
- [x] Toggle Serial/Simulator nella GUI
- [x] Navigazione post-WiFi — link al nuovo IP dopo connessione
- [x] Pagina LOGS — `/logs.html` con auto-refresh, `hook_print()` attivo
- [x] Display GC9107 128×128 — schermata di stato con WiFi, focuser, posizione
- [x] RGB LED WS2812B — state machine con colori per AP/STA/moving/Alpaca client
- [x] 3 Pulsanti hardware — left=move-in, right=move-out, center=ciclo step / long-press halt
- [x] Step size configurabile da pulsante: 1→5→10→20→50→1 (visualizzato su display)
- [x] Temperatura via IMU QMI8658C (I2C) — trasmessa a NINA come `temperature`
- [x] `board.py` — pin map centralizzata con `micropython.const()` per tutti i moduli
- [x] Display refresh ogni secondo durante il movimento (era 5s)

## TODO - Problemi da Risolvere

### 1. Test con NINA
**Priorità: Alta**

Verificare che NINA riesca a:
1. Vedere il dispositivo via Alpaca Discovery
2. Connettersi al focuser (in modalità Simulator)
3. Leggere posizione e temperatura
4. Muovere il focuser

**Test da fare:**
1. Avviare ESP32 connesso a WiFi
2. Aprire NINA → Equipment → Focuser
3. Cercare dispositivi Alpaca
4. Connettere e testare movimenti

---

### 2. Test modalità Hardware
**Priorità: Media**

Quando disponibile hardware Robofocus:
1. Collegare ESP32 via TTL 3.3V (con level shifter se necessario)
2. Selezionare "Hardware" nella GUI
3. Verificare comunicazione seriale
4. Testare movimenti reali

---

## Funzionalità Implementate

### Modalità Simulator
- File: `simulator.py`
- Simula posizione focuser (default 30000), temperatura con rumore (18°C ± 0.5°C)
- Permette test completi senza hardware Robofocus

### Toggle Serial/Simulator
- GUI: Radio buttons in sezione "Mode & Connection"
- API: `PUT /gui/mode` con `{"use_simulator": true/false}`
- Persiste la scelta in NVS; richiede disconnect prima di cambiare

### Pagina LOGS
- File: `static/logs.html`, `log_buffer.py`
- `hook_print()` intercetta tutte le chiamate a `print()` dal boot
- API: `GET /gui/logs?limit=N`, `DELETE /gui/logs`
- Buffer circolare 100 entries; auto-refresh ogni 2 secondi opzionale

### Display GC9107 (128×128 SPI)
- File: `display.py`
- Driver custom per GC9107 (non ST7789-compatibile al 100%)
- Schermata: WiFi mode/IP, focuser status, Alpaca client, posizione, step size
- Refresh solo quando lo stato cambia (guard su tupla di stato)
- Buffer temporaneo pre-allocato (no GC pressure durante show)

### RGB LED WS2812B
- File: `led.py`
- State machine: AP=arancione, STA idle=verde, STA+Alpaca=blu, moving=bianco pulsante
- Dimming globale 20%, aggiornato a 20 Hz (`asyncio.sleep_ms(50)`)

### Pulsanti Hardware
- File: `buttons.py`, integrazione in `main.py` (`button_loop`)
- IO0 (BOOT)=move in, IO47=cycle step/long-press halt, IO48=move out
- Debounce 50ms via ISR timestamp; long-press rilevato su RISING edge (≥600ms)
- Step sizes: 1 → 5 → 10 → 20 → 50 → 1 (ciclico, visualizzato su display)
- Pattern producer/consumer: ISR scrive flag, `process()` drena nel loop asincrono

### Temperatura via IMU QMI8658C
- File: `imu.py`
- I2C bus 0, SDA=IO12, SCL=IO11; probe automatico su 0x6B e 0x6A (SA0 floating)
- Accel attivo (CTRL7=0x01) necessario per attivare il sensore di temperatura
- Formula: `val / 256.0 - 20.0` (offset -20°C per compensare self-heating)
- `controller.get_temperature()` usa IMU come sorgente primaria, fallback su seriale

### Pin map centralizzata
- File: `board.py`
- Tutte le costanti hardware con `micropython.const()` (no dict lookup runtime)
- Importato da `display.py`, `led.py`, `buttons.py`, `imu.py`

---

## Come Deployare su ESP32

```bash
# Requisiti: mpremote installato
pip install mpremote

# Upload completo (prima volta o dopo modifiche estese)
python -m mpremote connect COM41 cp src/board.py : \
  + cp src/main.py : + cp src/config.py : + cp src/wifi_manager.py : \
  + cp src/web_server.py : + cp src/alpaca_api.py : + cp src/gui_api.py : \
  + cp src/discovery.py : + cp src/controller.py : + cp src/serial_protocol.py : \
  + cp src/simulator.py : + cp src/log_buffer.py : \
  + cp src/display.py : + cp src/led.py : + cp src/buttons.py : + cp src/imu.py : \
  + cp src/static/index.html :/static/ + cp src/static/setup.html :/static/ \
  + cp src/static/logs.html :/static/ + reset

# Monitor seriale (REPL)
python -m mpremote connect COM41 repl
```

> **Porta COM**: su questo setup la board è su `COM41`. Verificare in Device Manager se cambia.

## Struttura API Alpaca

### Management (Discovery)
- `GET /management/apiversions` → `{"Value": [1]}`
- `GET /management/v1/description` → info server
- `GET /management/v1/configureddevices` → lista dispositivi

### Focuser API
- `GET /api/v1/focuser/0/connected` → stato connessione
- `PUT /api/v1/focuser/0/connected` → connetti/disconnetti
- `GET /api/v1/focuser/0/position` → posizione attuale
- `PUT /api/v1/focuser/0/move` → muovi a posizione
- `PUT /api/v1/focuser/0/halt` → ferma movimento
- `GET /api/v1/focuser/0/ismoving` → sta muovendo?
- `GET /api/v1/focuser/0/temperature` → temperatura

### GUI API
- `GET /gui/status` → stato completo (include mode)
- `GET /gui/mode` → modalità corrente
- `PUT /gui/mode` → cambia modalità
- `POST /gui/connect` → connetti focuser
- `POST /gui/disconnect` → disconnetti
- `POST /gui/move` → muovi
- `POST /gui/halt` → ferma
- `GET /gui/logs` → log di sistema
- `DELETE /gui/logs` → pulisci log

---

## Note per il Prossimo Sviluppatore

1. **MicroPython != Python**: alcune funzioni standard non esistono o hanno signature diverse
2. **Memoria limitata**: ESP32-S3 ha ~200KB RAM libera; evitare allocazioni in loop caldi
3. **Async**: tutto usa `uasyncio`; non bloccare mai il loop con `time.sleep()` (usare `sleep_ms`)
4. **NVS errors**: `ESP_ERR_NVS_NOT_FOUND` è normale se config non esiste ancora
5. **COM port**: su Windows la porta seriale potrebbe essere bloccata da altri programmi
6. **Simulator default**: per default parte in modalità simulator (nessun hardware richiesto)
7. **ISR safety**: negli interrupt handler usare solo flag booleani/stringa, mai list.append()
8. **IMU temperatura**: offset -20°C è empirico per self-heating; non calibrato per compensazione termica del tubo ottico (NINA gestisce già la compensazione interna — non implementare doppia compensazione)
9. **board.py**: ogni modifica ai pin va fatta qui; i moduli importano da `board` con `const()`
10. **display.py**: `update()` non ridisegna se lo stato non cambia (guard su tupla); `show()` riusa `self._tmp` allocato in `__init__` per evitare GC pressure

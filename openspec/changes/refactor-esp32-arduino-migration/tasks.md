# Tasks: Migrazione ESP32 Arduino/C++

## Roadmap con Milestone

Ogni milestone ha criteri di accettazione verificabili prima di procedere al successivo.
La colonna "Verifica" indica cosa deve essere TRUE per considerare il milestone completato.

---

## M1 - Toolchain e Struttura Progetto

**Obiettivo**: Build funzionante, LED blink su ESP32, toolchain configurata.

**Verifica**: `pio run` compila senza errori; il firmware flashato fa lampeggiare il LED onboard.

- [ ] M1.1 Creare cartella `esp32-arduino/` con `platformio.ini` (target `esp32dev`, framework arduino)
- [ ] M1.2 Dichiarare dipendenze in `platformio.ini`: ESPAsyncWebServer, ArduinoJson 7, WiFiManager, AsyncTCP
- [ ] M1.3 Creare `src/main.cpp` con `setup()` + `loop()` minimi (LED blink ogni secondo)
- [ ] M1.4 Verificare build pulita: `pio run` → 0 errori, 0 warning critici
- [ ] M1.5 Verificare deploy: `pio run --target upload` → firmware in esecuzione, LED lampeggia
- [ ] M1.6 Decidere: OTA si/no (influenza partition scheme in `platformio.ini`) — vedi Q2 design.md
- [ ] M1.7 Creare cartella `esp32-arduino/data/` e copiare `esp32/static/*.html` (per LittleFS)
- [ ] M1.8 Verificare upload LittleFS: `pio run --target uploadfs` → file leggibili da `LITTLEFS.open()`

---

## M2 - WiFi + Web Server Base

**Obiettivo**: ESP32 si connette al WiFi, serve pagine statiche, risponde su HTTP.

**Verifica**: browser su PC riesce ad aprire `http://<ip-esp32>/` e riceve `index.html`; in assenza di credenziali, AP `Robofocus-XXXX` appare nella lista reti.

- [ ] M2.1 Rispondere alla Q1 del design.md: WiFiManager vs AP+setup.html custom
- [ ] M2.2 Implementare `wifi_manager.cpp`: integrazione WiFiManager con callback `saveConfigCallback`
- [ ] M2.3 Salvare/leggere credenziali WiFi via `Preferences` (namespace `"wifi"`)
- [ ] M2.4 Avviare `ESPAsyncWebServer` su porta 80 dopo connessione WiFi
- [ ] M2.5 Configurare serve LittleFS: `server.serveStatic("/", LITTLEFS, "/")` con fallback `index.html`
- [ ] M2.6 Implementare endpoint `GET /management/apiversions` → `{"Value": [1], ...}`
- [ ] M2.7 Implementare endpoint `GET /management/v1/description` → info server
- [ ] M2.8 Implementare endpoint `GET /management/v1/configureddevices` → lista dispositivi
- [ ] M2.9 Verificare: curl `http://<ip>/management/apiversions` ritorna JSON Alpaca corretto
- [ ] M2.10 Implementare endpoint `GET /gui/status` → JSON con stato connessione, IP, modalita`
- [ ] M2.11 Verificare: browser apre `index.html` e la sezione status mostra dati reali

---

## M3 - Alpaca API Completa (Simulator)

**Obiettivo**: tutti gli endpoint Alpaca focuser implementati e testati con simulatore in-memory.

**Verifica**: NINA riesce a (1) scoprire il dispositivo via Alpaca Discovery, (2) connettersi al focuser in modalita` Simulator, (3) leggere posizione e temperatura, (4) inviare un comando di movimento.

- [ ] M3.1 Implementare interfaccia `IFocuserHardware` (C++ abstract class)
- [ ] M3.2 Implementare `RobofocusSimulator`: posizione iniziale 30000, temperatura 18°C ± rumore, movimento simulato con FreeRTOS task
- [ ] M3.3 Implementare `FocuserController` con mutex FreeRTOS (Decision 7 design.md)
- [ ] M3.4 Implementare `alpaca_api.cpp`: tutti gli endpoint `/api/v1/focuser/0/*`
  - [ ] M3.4a `GET /connected`, `PUT /connected`
  - [ ] M3.4b `GET /position`
  - [ ] M3.4c `GET /ismoving`
  - [ ] M3.4d `PUT /move` (non-bloccante, avvia FreeRTOS task — Decision 8 design.md)
  - [ ] M3.4e `PUT /halt`
  - [ ] M3.4f `GET /temperature`
  - [ ] M3.4g `GET /maxstep`, `GET /stepsize`, `GET /absolute`, `GET /name`, `GET /description`, `GET /driverinfo`, `GET /driverversion`, `GET /interfaceversion`, `GET /supportedactions`
- [ ] M3.5 Implementare `discovery.cpp`: UDP broadcast su porta 32227 (risposta Alpaca discovery)
- [ ] M3.6 Verificare JSON response envelope: tutti i campi `ClientTransactionID`, `ServerTransactionID`, `ErrorNumber`, `ErrorMessage` presenti e corretti
- [ ] M3.7 **Test NINA Simulator**: NINA scopre dispositivo, si connette, legge posizione → PASS
- [ ] M3.8 **Test NINA Move**: NINA invia move(35000), isMoving=true poi false, posizione aggiornata → PASS
- [ ] M3.9 **Test NINA Autofocus**: sessione autofocus completa 20+ movimenti senza timeout → PASS

---

## M4 - Protocollo Seriale Hardware

**Obiettivo**: comunicazione reale con Robofocus via UART.

**Verifica**: con focuser fisico collegato, `GET /position` ritorna la posizione reale del focuser; `PUT /move` muove il motore fisicamente.

- [ ] M4.1 Implementare `serial_protocol.cpp`: encoding/decoding comandi 9-byte, checksum modulo 256
- [ ] M4.2 Implementare `RobofocusSerial`: gestione UART, timeout 5s, reconnect automatico
- [ ] M4.3 Supportare comandi: `FV` (versione), `FG` (goto), `FD` (posizione), `FT` (temperatura), `FQ` (halt), `FB` (backlash), `FL`/`FC` (limiti)
- [ ] M4.4 Implementare parsing caratteri movimento in-flight: `'I'` (inward), `'O'` (outward), `'F'` (finished)
- [ ] M4.5 Configurare pin UART in `platformio.ini` o `config.h` (RX/TX pin, default UART2)
- [ ] M4.6 Implementare switch simulator/hardware via `Preferences` (namespace `"focuser"`, chiave `"use_simulator"`)
- [ ] M4.7 **Test hardware**: collegare Robofocus, selezionare modalita` Hardware da GUI, verificare `FV` risponde con versione firmware
- [ ] M4.8 **Test movimento hardware**: NINA invia move(35000), motore si muove fisicamente, posizione aggiornata → PASS
- [ ] M4.9 **Test halt**: NINA invia halt durante movimento, motore si ferma entro 500ms → PASS

---

## M5 - Web GUI Completa

**Obiettivo**: pannello di controllo web funzionante identico alla versione MicroPython.

**Verifica**: tutte le funzionalita` GUI testate via browser (Chrome/Firefox): status display, move manuale, switch simulator/hardware, pagina logs.

- [ ] M5.1 Implementare `gui_api.cpp`: endpoint GUI REST
  - [ ] M5.1a `GET /gui/status` → stato completo (posizione, temperatura, modalita`, WiFi, free heap)
  - [ ] M5.1b `GET /gui/mode`, `PUT /gui/mode` (simulator/hardware)
  - [ ] M5.1c `POST /gui/connect`, `POST /gui/disconnect`
  - [ ] M5.1d `POST /gui/move`, `POST /gui/halt`
  - [ ] M5.1e `GET /gui/logs`, `DELETE /gui/logs`
- [ ] M5.2 Implementare ring buffer C++ per logs (100 entries, ~4KB RAM, thread-safe con mutex)
- [ ] M5.3 Implementare endpoint `/api/wifi/scan` (per pagina setup.html)
- [ ] M5.4 Verificare `index.html`: posizione aggiornata ogni 1s, bottoni move funzionanti
- [ ] M5.5 Verificare `setup.html`: scan reti WiFi funzionante, connessione a nuova rete
- [ ] M5.6 Verificare `logs.html`: log appaiono in tempo reale, clear funziona
- [ ] M5.7 Verificare switch Simulator/Hardware dalla GUI persiste dopo riavvio

---

## M6 - Stabilita` e Performance

**Obiettivo**: verificare requisiti non-funzionali prima del field test.

**Verifica**: benchmark latenza HTTP soddisfatto; test 24h senza crash.

- [ ] M6.1 Misurare latenza HTTP: `GET /api/v1/focuser/0/position` × 1000 richieste → p99 <50ms
- [ ] M6.2 Misurare latenza `PUT /move` initiation: < 30ms (risposta HTTP, non completamento movimento)
- [ ] M6.3 Test carico autofocus simulato: 50 movimenti consecutivi in 5 minuti → 0 timeout
- [ ] M6.4 Monitorare heap: `ESP.getFreeHeap()` loggato ogni 30s; nessun trend decrescente dopo 1h
- [ ] M6.5 Test watchdog: ESP32 non esegue reset spontanei in 4h di operazione continua
- [ ] M6.6 Test recovery WiFi: disconnettere router per 60s, riconnettersi → Alpaca API torna disponibile automaticamente entro 30s
- [ ] M6.7 Verificare assenza stack overflow FreeRTOS (configCHECK_FOR_STACK_OVERFLOW=2 in build debug)
- [ ] M6.8 Review thread safety: audit manuale di tutti gli accessi a `FocuserController` fuori da `loop()` → ogni accesso protetto da mutex

---

## M7 - Field Test con NINA

**Obiettivo**: sessione di imaging reale con autofocus automatico, equivalente all'uso in produzione.

**Verifica**: sessione autofocus 4h con NINA senza intervento manuale, 0 errori critici nel log.

- [ ] M7.1 Setup ambiente test: ESP32 collegato a Robofocus fisico, connesso alla rete locale
- [ ] M7.2 NINA configurato con Alpaca discovery → individua `Robofocus ESP32` entro 5s dall'avvio
- [ ] M7.3 Sessione autofocus manuale (5 movimenti): HFR calcolato correttamente per ogni punto → PASS
- [ ] M7.4 Sessione autofocus automatica NINA (20+ movimenti): completata senza timeout → PASS
- [ ] M7.5 Test temperatura: lettura ogni 60s per 1h, nessun valore anomalo (fuori da range -20/+50°C) → PASS
- [ ] M7.6 Soak test 4h: NINA lasciato in imaging con autofocus periodico → 0 reset ESP32, 0 timeout Alpaca
- [ ] M7.7 Confronto benchmark: misurare latenza media `GET /position` durante soak → documentare miglioramento vs MicroPython
- [ ] M7.8 **GO/NO-GO**: se tutti i test M7 passano → procedere con cleanup (rimozione `esp32/`)

---

## M8 - Cleanup e Documentazione

**Obiettivo**: rimozione codice MicroPython, documentazione aggiornata.

**Eseguire SOLO dopo M7 completato con successo.**

- [ ] M8.1 Rimuovere cartella `esp32/` (MicroPython) dal repository
- [ ] M8.2 Aggiornare `README.md` con istruzioni deploy Arduino/PlatformIO
- [ ] M8.3 Aggiornare `esp32-arduino/TODO.md` (ex `esp32/TODO.md`) con stato post-migrazione
- [ ] M8.4 Aggiornare `openspec/project.md`: rimuovere riferimenti MicroPython, aggiungere stack Arduino
- [ ] M8.5 Archiviare questa change: `openspec archive refactor-esp32-arduino-migration --yes`
- [ ] M8.6 Creare GitHub Release v2.0.0 con note di rilascio che includono:
  - Breaking change toolchain (mpremote → pio)
  - Istruzioni migrazione per chi usa la versione MicroPython

---

## Dipendenze tra Milestone

```
M1 (Toolchain)
  └─> M2 (WiFi + Web Server)
        └─> M3 (Alpaca API Simulator)
              ├─> M4 (Hardware Seriale)   ← richiede hardware fisico
              └─> M5 (Web GUI)
                    └─> M6 (Stabilita`)
                          └─> M7 (Field Test)   ← richiede hardware fisico + NINA
                                └─> M8 (Cleanup)
```

M4 e M5 possono procedere in parallelo dopo M3.

## Stima Complessita` per Milestone

| Milestone | Complessita` | Note |
|---|---|---|
| M1 | Bassa | Solo configurazione toolchain |
| M2 | Media | WiFiManager ha edge cases su alcune reti |
| M3 | Alta | Alpaca API completa + test NINA critici |
| M4 | Media | Protocollo gia` documentato, porta da Python |
| M5 | Bassa | GUI API e` porting diretto da gui_api.py |
| M6 | Media | Richiede setup benchmark e patience per 24h test |
| M7 | Alta | Dipende da disponibilita` hardware + notte chiara |
| M8 | Bassa | Solo cleanup e documentazione |

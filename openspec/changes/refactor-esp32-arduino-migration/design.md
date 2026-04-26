# Design Document: ESP32 Firmware - Migrazione Arduino/C++

## Context

Il firmware MicroPython attuale ha dimostrato latenze inaccettabili per l'uso con NINA in sessioni di autofocus. L'ESP32 e` un SoC dual-core Xtensa LX6 a 240MHz con 520KB SRAM e 4MB flash: le sue capacita` reali sono significativamente sottoutilizzate da un runtime Python interpretato.

Questo documento definisce le decisioni architetturali per il nuovo firmware C++ con framework Arduino, garantendo compatibilita` API completa verso i client Alpaca esistenti.

### Stakeholder

- **Utenti finali**: astrofotografi che usano NINA/Voyager; richiedono latenza bassa e affidabilita` 24h
- **Sviluppatori**: unico maintainer principale; preferisce strumenti consolidati su novita`
- **Client software**: NINA (primario), Voyager, SGP; si aspettano conformita` ASCOM Alpaca v1 stretta

### Vincoli

- ESP32 DevKit v1 (o equivalente); target board: `esp32dev`
- Flash disponibile: 4MB (partition scheme: default con OTA o senza OTA)
- RAM disponibile: ~300KB heap dopo FreeRTOS + WiFi stack (~220KB overhead sistema)
- Compatibilita` Alpaca v1 non negoziabile
- Il protocollo seriale Robofocus (9 byte, 9600 baud, 8N1) non cambia

## Goals / Non-Goals

### Goals

1. **Performance**: risposta HTTP <50ms p99 per GET, <30ms per PUT move initiation
2. **Stabilita`**: uptime 24h senza watchdog reset, recovery automatica da disconnessione WiFi
3. **Compatibilita` API**: zero breaking changes verso NINA/Voyager
4. **Toolchain moderna**: PlatformIO, build riproducibile, deploy in un comando
5. **Testabilita`**: modalita` simulator C++ equivalente a quella MicroPython

### Non-Goals

1. OTA update (Over-The-Air): fuori scope per v1, valutabile in v2
2. HTTPS/TLS: rete locale trusted, overhead SSL non giustificato
3. Multi-focuser: device_id=0 hardcoded come nel driver Python
4. WebSocket: polling HTTP a 250ms e` sufficiente per la GUI

## Decisions

### Decision 1: Framework Arduino su PlatformIO (non ESP-IDF nativo)

**Scelta**: Arduino framework con PlatformIO come build system

**Rationale**:
- Arduino astrae le API FreeRTOS/ESP-IDF piu` verbose mantenendo accesso completo quando necessario
- Ecosistema librerie maturo: ESPAsyncWebServer, ArduinoJson, WiFiManager sono battle-tested su migliaia di dispositivi
- PlatformIO gestisce dipendenze in `platformio.ini` (equivalente a `requirements.txt`), build riproducibile
- Curva di apprendimento inferiore rispetto a ESP-IDF nativo per un singolo sviluppatore

**Alternativa scartata**: ESP-IDF nativo (C)
- Pro: massima performance, controllo totale scheduler FreeRTOS
- Contro: boilerplate molto maggiore, nessuna libreria pronta per Alpaca/WiFiManager, sviluppo 3-4x piu` lento
- Decisione: performance di Arduino e` sufficiente per i requisiti, complessita` non giustificata

**Alternativa scartata**: Rust (esp-rs/Embassy)
- Pro: memory safety, performance nativa
- Contro: toolchain immatura per ESP32, assenza di librerie HTTP/WiFi mature, ecosistema limitato
- Decisione: rischio tecnico troppo alto per un progetto di produzione

### Decision 2: ESPAsyncWebServer per HTTP

**Scelta**: libreria `me-no-dev/ESP Async WebServer`

**Rationale**:
- Gestisce le connessioni in task FreeRTOS separati (non blocca il loop principale)
- Supporta keep-alive, chunked transfer, file serving da LittleFS nativo
- API dichiarativa con lambda per handler (`server.on("/path", HTTP_GET, handler)`)
- Usata da migliaia di progetti ESP32 Alpaca/domotica, ben testata

**Architettura risultante**:
```
FreeRTOS Task: WiFi/Network stack
FreeRTOS Task: AsyncWebServer (gestisce connessioni TCP in background)
FreeRTOS Task: loop() Arduino (logica applicativa, polling seriale)
```

**Considerazione thread safety**: le callback di ESPAsyncWebServer vengono eseguite nel task del server, non in `loop()`. Tutti gli accessi a `controller` e `config` dalle callback HTTP devono usare un mutex (`SemaphoreHandle_t`).

**Alternativa scartata**: WebServer.h (sincrono, bloccante)
- Bloccherebbe `loop()` durante ogni richiesta HTTP
- Non accettabile per polling seriale continuo durante movimento focuser

### Decision 3: ArduinoJson 7 per serializzazione JSON

**Scelta**: `bblanchon/ArduinoJson` versione 7.x

**Rationale**:
- Parsing e serializzazione zero-allocation con `JsonDocument` stack-allocated
- API type-safe, evita cast manuali
- Supporto per stream diretto su `AsyncResponseStream` (nessuna copia stringa intermedia)
- Benchmark: ~10x piu` veloce del parser `json` MicroPython su payload simili

**Pattern di utilizzo**:
```
// Risposta JSON Alpaca senza allocazione heap
JsonDocument doc;
doc["Value"] = controller.getPosition();
doc["ClientTransactionID"] = clientTransactionId;
doc["ServerTransactionID"] = serverTransactionId;
doc["ErrorNumber"] = 0;
doc["ErrorMessage"] = "";
// Serializza direttamente sulla connessione TCP
```

### Decision 4: LittleFS per file statici

**Scelta**: LittleFS (sostituisce SPIFFS deprecato)

**Rationale**:
- Piu` robusto di SPIFFS su power-off imprevisti (journaling)
- Supportato nativamente da ESPAsyncWebServer per file serving
- I file HTML esistenti (`esp32/static/`) vengono copiati in `esp32-arduino/data/` senza modifiche
- Upload via PlatformIO: `pio run --target uploadfs`

**Partition scheme**: `default` (1.2MB app + 1.5MB SPIFFS/LittleFS)

**Nota**: se in futuro si aggiunge OTA, usare `min_spiffs` (1.8MB app + 190KB LittleFS). Le pagine HTML sono piccole (<30KB totali), entrambi gli scheme funzionano.

### Decision 5: Preferences (NVS) per configurazione persistente

**Scelta**: libreria `Preferences` (wrapper Arduino su ESP-IDF NVS)

**Rationale**:
- Stessa memoria NVS usata dall'implementazione MicroPython (dati gia` presenti non vengono cancellati)
- API semplice: `prefs.putString("ssid", ssid)` / `prefs.getString("ssid", "")`
- Namespace-based: separare `wifi`, `focuser`, `server` evita collisioni di chiavi

**Schema namespace**:
```
namespace "wifi":    ssid, password
namespace "focuser": use_simulator, step_size, max_step
namespace "server":  device_name, device_id
```

### Decision 6: WiFiManager per provisioning WiFi

**Scelta**: `tzapu/WiFiManager`

**Rationale**:
- Gestisce AP mode con captive portal automatico (redirect browser su qualsiasi URL)
- Tenta connessione STA con credenziali salvate al boot; se fallisce, apre AP
- Callback `saveConfigCallback` per salvare credenziali in Preferences
- Elimina ~200 righe di codice custom non testato (`wifi_manager.py`)

**Comportamento**:
1. Boot: WiFiManager tenta connessione con credenziali NVS
2. Successo: entra in STA mode, avvia Alpaca server
3. Fallimento / primo avvio: apre AP `Robofocus-XXXX`, captive portal su `192.168.4.1`
4. Utente configura WiFi, ESP32 si riconnette e riavvia in STA mode

**Limite**: WiFiManager non espone la pagina di scan reti attiva come la GUI custom MicroPython. Soluzione: mantenere endpoint `/api/wifi/scan` custom sopra WiFiManager per la pagina `setup.html`.

### Decision 7: Mutex per accesso condiviso al controller

**Scelta**: `SemaphoreHandle_t` FreeRTOS (mutex) sul singleton `FocuserController`

**Pattern**:
```cpp
// In FocuserController.h
class FocuserController {
    SemaphoreHandle_t _mutex;
public:
    bool move(int position);   // acquisisce mutex internamente
    int  getPosition();        // acquisisce mutex internamente
    bool isMoving();
};
```

**Rationale**: le callback HTTP (task server) e `loop()` (task principale) accedono entrambi a `_position` e `_isMoving`. Senza mutex il comportamento e` undefined behavior.

**Regola**: il mutex viene acquisito per il tempo minimo necessario (lettura/scrittura stato), mai durante operazioni seriali bloccanti.

### Decision 8: Gestione movimento non-bloccante con FreeRTOS Task

**Scelta**: il comando `move` avvia un FreeRTOS task dedicato per il polling seriale

**Flusso**:
```
HTTP PUT /move (pos=5000)
  → acquisisce mutex
  → imposta _isMoving = true, _targetPosition = 5000
  → invia comando FG005000 su UART
  → avvia vTaskCreate("moveTask", ...)
  → rilascia mutex
  → risponde HTTP 200 immediatamente

moveTask (background):
  → legge caratteri 'I'/'O'/'F' dalla UART
  → aggiorna _position in tempo reale (con mutex)
  → quando riceve 'F': legge posizione finale, imposta _isMoving = false
  → si auto-termina (vTaskDelete(NULL))
```

**Questo pattern e` identico alla spec del driver Python** (Decision 4 in design.md driver) ma sfrutta task FreeRTOS reali invece di uasyncio cooperativo.

### Decision 9: Simulator come implementazione alternativa di IFocuserHardware

**Scelta**: interfaccia C++ pura `IFocuserHardware` con due implementazioni

```cpp
class IFocuserHardware {
public:
    virtual bool connect() = 0;
    virtual void disconnect() = 0;
    virtual bool move(int position) = 0;
    virtual int  getPosition() = 0;
    virtual bool isMoving() = 0;
    virtual float getTemperature() = 0;
    virtual bool halt() = 0;
};

class RobofocusSerial : public IFocuserHardware { /* UART */ };
class RobofocusSimulator : public IFocuserHardware { /* in-memory */ };
```

`FocuserController` riceve un puntatore `IFocuserHardware*` al boot; la scelta simulator/hardware viene letta da Preferences.

### Decision 10: Logging via Serial Monitor (USB)

**Scelta**: `Serial.printf()` su UART0 (USB) per logging debug

**Rationale**:
- In sviluppo: output visibile via PlatformIO Serial Monitor o `pio device monitor`
- In produzione: nessun overhead se `Serial.begin()` non viene chiamato (o si usa `#ifdef DEBUG`)
- Il `log_buffer.py` MicroPython (buffer circolare in RAM per `/gui/logs`) viene mantenuto come endpoint HTTP per la pagina logs.html, ma implementato con un ring buffer C++ fisso (100 entries, ~4KB RAM)

## Risks / Trade-offs

### Rischio 1: Thread safety ESPAsyncWebServer

**Rischio**: race condition tra callback HTTP e `loop()` / moveTask

**Probabilita`**: Alta se non gestita esplicitamente

**Impatto**: corruzione stato, crash non deterministici in sessioni lunghe

**Mitigazione**: mutex su `FocuserController` (Decision 7), review code prima del M5

### Rischio 2: Heap fragmentation in sessioni lunghe

**Rischio**: `String` e `JsonDocument` allocano/liberano heap; dopo 24h possibile frammentazione

**Probabilita`**: Media

**Impatto**: `malloc` fallisce, crash con reset watchdog

**Mitigazione**:
- Usare `JsonDocument` stack-allocated dove possibile
- Evitare `String` Arduino (preferire `char[]` o `std::string`)
- Monitorare `ESP.getFreeHeap()` nell'endpoint `/gui/status`
- Aggiungere al M6 un test di stress 24h con logging heap

### Rischio 3: WiFiManager captive portal non compatibile con setup.html esistente

**Rischio**: la pagina `setup.html` custom presuppone endpoint REST `/api/wifi/scan` e `/api/wifi/connect` che WiFiManager non espone

**Probabilita`**: Certa (gia` identificata, Decision 6)

**Impatto**: pagina configurazione WiFi non funzionante

**Mitigazione**: implementare endpoint `/api/wifi/scan` custom che chiama `WiFi.scanNetworks()`, mantenere `setup.html` come pagina di fallback (non usata se WiFiManager captive portal e` sufficiente)

### Rischio 4: Regressioni protocollo Alpaca

**Rischio**: porting da Python a C++ puo` introdurre differenze nel JSON response (campi mancanti, tipi sbagliati)

**Probabilita`**: Media

**Impatto**: NINA non riesce a connettersi o riceve errori imprevisti

**Mitigazione**: test end-to-end con NINA in modalita` simulator prima di testare hardware (Milestone M4 prima di M5)

## Migration Plan

### Coesistenza durante sviluppo

I due firmware coesistono in cartelle separate:
- `esp32/` - MicroPython (attuale, NON modificare durante migrazione)
- `esp32-arduino/` - Arduino/C++ (nuovo)

La directory `esp32/` viene rimossa solo dopo che M7 (field test) e` completato con successo.

### Rollback

Se la migrazione Arduino introduce regressioni critiche prima del M7:
1. Riflashare il firmware MicroPython (`esp32/firmware/ESP32_GENERIC-*.bin`)
2. Re-uploadare i file Python con `mpremote`
3. Documentare il problema come issue, pianificare fix

### Deploy finale

```bash
# Build + upload firmware Arduino
pio run --target upload

# Upload file HTML su LittleFS
pio run --target uploadfs

# Monitor seriale
pio device monitor
```

## Open Questions

### Q1: Usare WiFiManager captive portal o mantenere AP+setup.html custom?

**Contesto**: WiFiManager semplifica molto il codice ma cambia la UX (captive portal vs pagina web custom).

**Opzioni**:
- A) WiFiManager captive portal (default): piu` semplice, meno controllo UX
- B) AP+setup.html custom: piu` controllo, piu` codice da mantenere
- C) Ibrida: WiFiManager per connessione, setup.html per configurazioni avanzate

**Da decidere prima di M2.**

### Q2: Abilitare OTA update?

**Contesto**: OTA permette di aggiornare il firmware via WiFi senza cavo USB. Richiede partition scheme diverso.

**Impatto**: cambio partition scheme richiede flash completo (cancella NVS). Da fare prima del primo deploy utente se si vuole OTA.

**Da decidere prima di M1** (la scelta influenza `platformio.ini`).

### Q3: Mantenere la pagina logs.html con ring buffer in memoria?

**Contesto**: la pagina logs richiede ~4KB RAM per il buffer circolare. Con 300KB disponibili non e` un problema, ma aggiunge complessita`.

**Alternativa**: eliminare `/gui/logs` e usare solo il Serial Monitor per debug.

**Raccomandazione**: mantenere, utile per debug in campo senza cavo USB.

---

**Document Version**: 1.0
**Data**: 2026-03-06
**Autori**: Samuele Vecchi, Claude Sonnet 4.6

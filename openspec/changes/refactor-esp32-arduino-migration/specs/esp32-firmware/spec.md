## ADDED Requirements

### Requirement: Toolchain Arduino PlatformIO

Il firmware ESP32 SHALL essere compilato e deployato tramite PlatformIO con framework Arduino. Il progetto SHALL includere un `platformio.ini` che dichiara tutte le dipendenze esterne in modo riproducibile. Un singolo comando (`pio run --target upload`) SHALL essere sufficiente per compilare e flashare il firmware. Un singolo comando (`pio run --target uploadfs`) SHALL essere sufficiente per caricare i file HTML su LittleFS.

#### Scenario: Build da zero su nuova macchina

- **WHEN** uno sviluppatore clona il repository ed esegue `pio run` nella cartella `esp32-arduino/`
- **THEN** PlatformIO scarica automaticamente le dipendenze dichiarate e compila senza errori

#### Scenario: Deploy su ESP32 fisico

- **WHEN** lo sviluppatore esegue `pio run --target upload` con ESP32 collegato via USB
- **THEN** il firmware viene flashato e l'ESP32 si avvia entro 10 secondi

---

### Requirement: Gestione WiFi STA/AP

Il firmware SHALL tentare la connessione a una rete WiFi con credenziali salvate al boot. In assenza di credenziali o in caso di connessione fallita, SHALL aprire un Access Point con SSID `Robofocus-XXXX` (XXXX = ultimi 4 caratteri MAC). Le credenziali WiFi SHALL essere persistite in NVS (via Preferences Arduino) e sopravvivere a riavvii e aggiornamenti firmware. Il firmware SHALL monitorare la connessione WiFi e tentare riconnessione automatica in caso di disconnessione.

#### Scenario: Primo avvio (nessuna credenziale)

- **WHEN** il firmware si avvia senza credenziali WiFi in NVS
- **THEN** apre AP mode con SSID `Robofocus-XXXX` e un portale di configurazione raggiungibile via browser su `192.168.4.1`

#### Scenario: Avvio con credenziali valide

- **WHEN** il firmware si avvia con credenziali WiFi valide in NVS
- **THEN** si connette alla rete entro 15 secondi, ottiene IP via DHCP, e avvia il server Alpaca

#### Scenario: Recovery da disconnessione WiFi

- **WHEN** la connessione WiFi viene persa durante operazione normale
- **THEN** il firmware tenta riconnessione automatica e ripristina l'API Alpaca entro 30 secondi dal ritorno della rete

---

### Requirement: HTTP Server Non-Bloccante

Il firmware SHALL usare un server HTTP asincrono (ESPAsyncWebServer) che gestisce le connessioni in task FreeRTOS dedicati, senza bloccare il loop principale. Il server SHALL rispondere a richieste HTTP GET in meno di 50ms (p99) e a richieste PUT in meno di 30ms (p99) quando il sistema e` idle. Il server SHALL supportare connessioni concorrenti da piu` client.

#### Scenario: Risposta rapida durante polling NINA

- **WHEN** NINA invia 10 richieste `GET /api/v1/focuser/0/position` in rapida successione (100ms intervallo)
- **THEN** tutte le risposte arrivano entro 50ms ciascuna e nessuna va in timeout

#### Scenario: Serve file statici da LittleFS

- **WHEN** il browser richiede `GET /`
- **THEN** il server risponde con `index.html` da LittleFS con status 200

---

### Requirement: Alpaca API v1 Completa

Il firmware SHALL implementare l'API ASCOM Alpaca v1 per un dispositivo Focuser su device_id=0. Tutti i response body SHALL includere i campi `ClientTransactionID`, `ServerTransactionID`, `ErrorNumber`, `ErrorMessage` secondo la specifica Alpaca. Gli endpoint SHALL essere:

**Management:**
- `GET /management/apiversions` → `{"Value": [1]}`
- `GET /management/v1/description` → info server
- `GET /management/v1/configureddevices` → lista dispositivi

**Focuser (device_id=0):**
- `GET /api/v1/focuser/0/connected`
- `PUT /api/v1/focuser/0/connected`
- `GET /api/v1/focuser/0/position`
- `PUT /api/v1/focuser/0/move`
- `PUT /api/v1/focuser/0/halt`
- `GET /api/v1/focuser/0/ismoving`
- `GET /api/v1/focuser/0/temperature`
- `GET /api/v1/focuser/0/maxstep`
- `GET /api/v1/focuser/0/stepsize`
- `GET /api/v1/focuser/0/absolute`
- `GET /api/v1/focuser/0/name`
- `GET /api/v1/focuser/0/description`
- `GET /api/v1/focuser/0/driverinfo`
- `GET /api/v1/focuser/0/driverversion`
- `GET /api/v1/focuser/0/interfaceversion`
- `GET /api/v1/focuser/0/supportedactions`

#### Scenario: NINA connette il focuser

- **WHEN** NINA invia `PUT /api/v1/focuser/0/connected` con `Connected=True`
- **THEN** il server risponde HTTP 200 con `{"Value": null, "ErrorNumber": 0, "ErrorMessage": ""}`

#### Scenario: Movimento non-bloccante

- **WHEN** NINA invia `PUT /api/v1/focuser/0/move` con `Position=35000`
- **THEN** il server risponde HTTP 200 immediatamente (entro 30ms), `isMoving` ritorna `true`, e il movimento avviene in background

#### Scenario: Errore Alpaca corretto

- **WHEN** si richiede `GET /api/v1/focuser/0/position` e il focuser non e` connesso
- **THEN** il server risponde con `{"ErrorNumber": 1031, "ErrorMessage": "Not connected"}` (codice Alpaca 0x407)

---

### Requirement: Alpaca Discovery UDP

Il firmware SHALL rispondere a broadcast UDP sulla porta 32227 secondo il protocollo Alpaca Discovery v1. La risposta SHALL includere il JSON con `AlpacaPort` e i metadati del server. Il servizio discovery SHALL avviarsi automaticamente quando il firmware e` in modalita` STA (connesso al WiFi).

#### Scenario: NINA discovery automatico

- **WHEN** NINA esegue una scansione Alpaca sulla rete locale
- **THEN** il dispositivo ESP32 appare nell'elenco entro 5 secondi con nome `Robofocus ESP32`

#### Scenario: Discovery non attivo in AP mode

- **WHEN** il firmware e` in AP mode (nessuna connessione WiFi)
- **THEN** il servizio UDP discovery NON e` attivo (evitare confusione con IP non raggiungibili)

---

### Requirement: Interfaccia IFocuserHardware e Dependency Injection

Il firmware SHALL definire un'interfaccia C++ astratta `IFocuserHardware` con i metodi `connect`, `disconnect`, `move`, `getPosition`, `isMoving`, `getTemperature`, `halt`. Il componente `FocuserController` SHALL ricevere un puntatore `IFocuserHardware*` al boot. La selezione tra implementazione hardware e simulator SHALL avvenire leggendo la Preference `focuser.use_simulator` senza ricompilare il firmware.

#### Scenario: Switch a runtime tra hardware e simulator

- **WHEN** l'utente cambia modalita` via `PUT /gui/mode` con `{"use_simulator": true}`
- **THEN** il firmware salva la preferenza in NVS, si disconnette dall'implementazione corrente e si connette all'implementazione selezionata; il cambiamento persiste dopo riavvio

---

### Requirement: Simulatore Hardware in-Memory

Il firmware SHALL includere un'implementazione `RobofocusSimulator` di `IFocuserHardware` che simula il comportamento del focuser senza hardware fisico. Il simulatore SHALL: partire da posizione 30000, simulare il movimento con velocita` configurabile (default: 500 steps/sec) in un FreeRTOS task dedicato, esporre temperatura 18.0°C con rumore gaussiano ±0.5°C, rispettare i limiti di posizione (0, MaxStep).

#### Scenario: Movimento simulato con aggiornamento posizione

- **WHEN** viene inviato `PUT /move` con `Position=35000` mentre il simulatore e` in posizione 30000
- **THEN** `GET /ismoving` ritorna `true` per ~10 secondi, la posizione si aggiorna progressivamente, e alla fine `isMoving` ritorna `false` con posizione=35000

#### Scenario: Halt simulatore

- **WHEN** viene inviato `PUT /halt` durante un movimento simulato
- **THEN** `isMoving` diventa `false` entro 100ms, la posizione si ferma al valore intermedio raggiunto

---

### Requirement: Protocollo Seriale Robofocus

Il firmware SHALL implementare il protocollo seriale Robofocus: comandi 9 byte (2 char comando + 6 char valore + 1 byte checksum), checksum calcolato come somma modulo 256 dei primi 8 byte ASCII. La comunicazione SHALL avvenire su UART a 9600 baud 8N1. Il firmware SHALL supportare i comandi `FV`, `FG`, `FD`, `FT`, `FQ`, `FB`, `FL`, `FC`. Il firmware SHALL gestire i caratteri di stato movimento `'I'`, `'O'`, `'F'` in modo da aggiornare la posizione in tempo reale durante il movimento.

#### Scenario: Comando FG (Goto)

- **WHEN** il controller invia il comando `FG035000` + checksum su UART
- **THEN** il focuser fisico inizia il movimento e risponde con sequenza di `'I'`/`'O'` seguiti da `'F'` + pacchetto posizione finale

#### Scenario: Checksum non valido nella risposta

- **WHEN** il controller riceve un pacchetto 9-byte con checksum errato
- **THEN** scarta il pacchetto, logga un warning, e riprova la comunicazione

#### Scenario: Timeout comunicazione seriale

- **WHEN** il focuser non risponde entro 5 secondi
- **THEN** il controller ritorna errore Alpaca 0x500 (DriverError) e imposta `connected=false`

---

### Requirement: Thread Safety su FocuserController

Il firmware SHALL proteggere tutti gli accessi allo stato condiviso di `FocuserController` (posizione, isMoving, temperatura) con un mutex FreeRTOS (`SemaphoreHandle_t`). Le callback HTTP di ESPAsyncWebServer e il FreeRTOS task di movimento SHALL acquisire il mutex prima di leggere o scrivere lo stato. Il mutex SHALL essere acquisito per il tempo minimo necessario (nessuna operazione seriale bloccante mentre il mutex e` held).

#### Scenario: Richiesta HTTP durante movimento attivo

- **WHEN** NINA invia `GET /position` mentre il task di movimento sta aggiornando la posizione
- **THEN** la risposta HTTP riporta un valore di posizione consistente (non corrotto da race condition)

#### Scenario: Doppia richiesta di movimento concorrente

- **WHEN** due client inviano `PUT /move` simultaneamente
- **THEN** il secondo `PUT /move` viene rifiutato con errore Alpaca appropriato (o accettato e il movimento precedente annullato), mai corruzione dello stato

---

### Requirement: API Web GUI

Il firmware SHALL esporre un'API REST per la Web GUI che permette il controllo manuale del focuser da browser. Gli endpoint SHALL essere:

- `GET /gui/status` → stato completo (posizione, temperatura, modalita`, WiFi SSID, IP, free heap bytes)
- `GET /gui/mode`, `PUT /gui/mode` → lettura/scrittura modalita` simulator/hardware
- `POST /gui/connect`, `POST /gui/disconnect`
- `POST /gui/move`, `POST /gui/halt`
- `GET /gui/logs` → ultimi 100 messaggi di log
- `DELETE /gui/logs` → svuota buffer log
- `GET /api/wifi/scan` → lista reti WiFi disponibili

#### Scenario: Status panel aggiornato

- **WHEN** il browser richiede `GET /gui/status` ogni secondo
- **THEN** il JSON ritornato include `free_heap` corrente, `position`, `temperature`, `is_moving`, `wifi_ssid`, `ip_address`

#### Scenario: Log persistenti in sessione

- **WHEN** l'utente apre `logs.html` dopo 30 minuti di operazione
- **THEN** vengono mostrati gli ultimi 100 eventi di log con timestamp relativo al boot

---

### Requirement: Persistenza Configurazione in NVS

Il firmware SHALL persistere la configurazione in NVS tramite la libreria `Preferences` Arduino. I parametri persistiti SHALL includere: credenziali WiFi, modalita` simulator/hardware, nome dispositivo. I dati SHALL sopravvivere a riavvii, aggiornamenti firmware (se non si usa `nvs_flash_erase`), e disconnessioni WiFi.

#### Scenario: Persistenza modalita` dopo riavvio

- **WHEN** l'utente seleziona "Hardware" da GUI e poi riavvia l'ESP32
- **THEN** al riavvio il firmware parte gia` in modalita` Hardware senza ulteriore configurazione

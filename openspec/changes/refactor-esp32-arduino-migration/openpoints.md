# Open Points - Decisioni richieste prima dell'implementazione

Questo file raccoglie tutte le decisioni che richiedono input da parte tua.
Ogni punto indica **entro quale milestone serve la risposta** e **quale impatto ha sul codice**.

---

## OP-1: Abilitare OTA (Over-The-Air update)?

**Serve entro**: M1 (influenza `platformio.ini` e partition scheme)

**Contesto**: L'OTA permette di aggiornare il firmware via WiFi senza cavo USB. Il tradeoff e`:

| | Senza OTA | Con OTA |
|---|---|---|
| Spazio app | 1.2MB (piu` spazio per codice) | ~1.8MB (due slot firmware) |
| Spazio LittleFS | 1.5MB (pagine HTML ok) | ~190KB (le pagine HTML devono stare in <190KB) |
| Cambio partition | No (piu` semplice) | Si (richiede flash completo una tantum) |
| Deploy futuro | Sempre via USB | Via WiFi o USB |

**Le pagine HTML attuali pesano ~25KB** → entrambe le opzioni funzionano, ma con OTA lo spazio per LittleFS e` molto ridotto.

**Opzioni**:
- **A) Nessun OTA** (raccomandato per v1): partition `default`, 1.2MB app + 1.5MB LittleFS, deploy sempre via USB
- **B) OTA abilitato**: partition `min_spiffs`, 1.8MB app + 190KB LittleFS, deploy via WiFi (richiede libreria AsyncElegantOTA)

**Tua decisione**: ___

---

## OP-2: WiFiManager captive portal o pagina setup.html custom?

**Serve entro**: M2 (determina quanto codice WiFi scrivere)

**Contesto**: Il provisioning WiFi (come l'ESP32 si connette alla rete) puo` avvenire in due modi:

| | WiFiManager (libreria) | setup.html custom |
|---|---|---|
| Codice da scrivere | ~20 righe | ~150 righe (porta da wifi_manager.py) |
| UX utente | Captive portal automatico (come router WiFi) | Pagina web identica alla versione MicroPython |
| Scan reti WiFi | Integrato | Endpoint `/api/wifi/scan` da implementare |
| Robustezza | Battle-tested su migliaia di dispositivi | Testata solo nel progetto corrente |
| Controllo UI | Basso (stile fisso) | Alto (identica alla versione attuale) |

**Nota**: le due opzioni sono **non esclusive** — si puo` usare WiFiManager per la logica di connessione e mantenere `setup.html` come pagina avanzata accessibile dopo la connessione.

**Opzioni**:
- **A) WiFiManager puro**: captive portal gestisce tutto, `setup.html` viene rimossa o mantenuta come pagina di riconfiguration
- **B) setup.html custom**: porta il codice WiFi da Python a C++ mantenendo la stessa UX
- **C) Ibrida** (raccomandato): WiFiManager gestisce la connessione al boot, `setup.html` rimane per riconfigurare la rete da interfaccia conosciuta

**Tua decisione**: ___

---

## OP-3: Pin UART per connessione seriale Robofocus

**Serve entro**: M4 (necessario per `serial_protocol.cpp`)

**Contesto**: L'ESP32 ha 3 UART hardware. UART0 e` usato dal monitor seriale USB. Servono i pin fisici su cui hai collegato (o collegherai) il Robofocus.

**Pin UART2 (default suggerito)**:
- RX: GPIO16
- TX: GPIO17
- Questi pin sono liberi su quasi tutti i DevKit standard

**Domanda**: quale UART e quali pin GPIO usi per collegare il Robofocus all'ESP32?

**Risposta attesa**: `UART_NUM=___, RX=GPIO___, TX=GPIO___`

**Tua decisione**: ___

---

## OP-4: Board target ESP32

**Serve entro**: M1 (valore `board` in `platformio.ini`)

**Contesto**: PlatformIO richiede di specificare la board esatta per i pin corretti e il flash size. Il default usato nelle specifiche e` `esp32dev` (ESP32 DevKit v1, 4MB flash).

**Domande**:
1. Che board/modulo ESP32 stai usando? (es. ESP32 DevKit v1, ESP32-S3, WEMOS D1 Mini ESP32, NodeMCU-32S, ecc.)
2. Quanta flash ha? (4MB e` il piu` comune)
3. E` un ESP32 classico (dual-core Xtensa LX6) o una variante S2/S3/C3?

**Nota**: se non sei sicuro, `esp32dev` funziona per la maggior parte dei moduli generici con chip ESP32.

**Tua decisione**: ___

---

## OP-5: Mantenere la pagina logs.html?

**Serve entro**: M5 (determina se implementare il ring buffer C++)

**Contesto**: La pagina `logs.html` mostra gli ultimi 100 eventi di log via `GET /gui/logs`. Richiede un ring buffer in RAM (~4KB). Con ~300KB heap disponibili non e` un problema di memoria, ma aggiunge complessita`.

**Alternativa**: eliminare `/gui/logs` e usare solo il Serial Monitor via USB per debug. In campo (senza cavo USB) non si potrebbe vedere i log.

**Opzioni**:
- **A) Mantenere logs.html** (raccomandato): utile per debug in campo senza cavo USB, costo basso
- **B) Eliminare logs.html**: meno codice, debug solo via Serial Monitor

**Tua decisione**: ___

---

## OP-6: Comportamento alla perdita connessione WiFi

**Serve entro**: M2 (influenza il WiFi monitor loop)

**Contesto**: se il WiFi cade durante una sessione di imaging attiva, ci sono due comportamenti possibili:

**Opzioni**:
- **A) Continua a operare offline**: mantiene l'ultimo stato, i comandi seriali al Robofocus continuano a funzionare localmente; quando WiFi torna, riprende a servire le richieste HTTP
- **B) Apre AP mode come fallback**: come nella versione MicroPython attuale; permette accesso alla GUI anche senza rete domestica ma interrompe NINA
- **C) Solo riconnessione silente**: non apre AP, tenta riconnessione in background ogni 30s, nessun cambio di stato visibile

**Tua decisione**: ___

---

## OP-7: Nome dispositivo Alpaca nel discovery

**Serve entro**: M3 (usato nella risposta UDP discovery e nella GUI)

**Contesto**: il nome con cui il dispositivo appare in NINA quando si fa la scansione Alpaca. Attualmente nella versione MicroPython il nome e` fisso nel codice.

**Domanda**: vuoi un nome fisso (es. `"Robofocus ESP32"`) o configurabile via GUI?

**Opzioni**:
- **A) Nome fisso**: `"Robofocus ESP32"` — piu` semplice
- **B) Configurabile**: campo editabile nella GUI, salvato in NVS — utile se si hanno piu` ESP32

**Tua decisione**: ___

---

## Riepilogo priorita`

| ID | Decisione | Serve entro | Impatto se ritardata |
|---|---|---|---|
| OP-1 | OTA si/no | **M1** | Blocca inizio sviluppo |
| OP-4 | Board target | **M1** | Blocca inizio sviluppo |
| OP-3 | Pin UART seriale | **M4** | Non blocca M1-M3 |
| OP-2 | WiFiManager vs custom | **M2** | Blocca M2 |
| OP-6 | Comportamento WiFi loss | **M2** | Blocca M2 |
| OP-5 | Mantenere logs.html | **M5** | Non blocca M1-M4 |
| OP-7 | Nome dispositivo Alpaca | **M3** | Non blocca M1-M2 |

**Per iniziare con M1 bastano OP-1 e OP-4.**

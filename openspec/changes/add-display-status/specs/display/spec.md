## ADDED Requirements

### Requirement: GC9107 Status Display
The system SHALL drive the onboard 0.85" 128×128 GC9107 TFT LCD over SPI and render a status screen reflecting the current runtime state of the device.

#### Scenario: Boot display
- **WHEN** the device boots
- **THEN** the display initialises within 500 ms and shows the status screen

#### Scenario: AP mode display
- **WHEN** Wi-Fi is in AP mode
- **THEN** the display shows `MODE: AP`, the AP SSID, and `FOCUS: --` / `ALPACA: --`

#### Scenario: STA mode display
- **WHEN** Wi-Fi is connected in Station mode
- **THEN** the display shows `MODE: STA`, the assigned IP address, and the live focuser / Alpaca status

#### Scenario: Robofocus connected
- **WHEN** the focuser serial connection is established
- **THEN** the FOCUS field shows `OK` in green

#### Scenario: Robofocus disconnected
- **WHEN** the focuser serial connection is not established
- **THEN** the FOCUS field shows `--` in orange

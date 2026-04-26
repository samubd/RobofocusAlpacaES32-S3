# Delta: Serial Protocol - COM Port Auto-Discovery

## ADDED Requirements

### Requirement: COM Port Enumeration

The system SHALL enumerate all available serial (COM) ports on the host system and provide port metadata including name, description, and hardware ID.

#### Scenario: List available COM ports on Windows
- **GIVEN** Windows system with USB-serial adapters
- **WHEN** driver calls `list_available_ports()`
- **THEN** result SHALL contain list of `PortInfo` objects
- **AND** each object SHALL have properties:
  - `name`: e.g., "COM3", "COM12"
  - `description`: e.g., "USB Serial Device", "FTDI FT232R"
  - `hardware_id`: e.g., "USB VID:PID=0403:6001"

#### Scenario: No COM ports available
- **GIVEN** system has no serial ports
- **WHEN** driver calls `list_available_ports()`
- **THEN** result SHALL be empty list
- **AND** no exception SHALL be raised

#### Scenario: Filter Bluetooth virtual ports
- **GIVEN** system has Bluetooth serial ports (e.g., "COM5 - Bluetooth Serial")
- **WHEN** driver calls `list_available_ports()`
- **THEN** Bluetooth ports MAY be included but SHALL be marked as `is_bluetooth=True`
- **AND** auto-discovery SHALL skip Bluetooth ports by default

### Requirement: Robofocus Auto-Discovery

The system SHALL provide a scan function that probes each available COM port to identify connected Robofocus devices by sending FV command and validating the response.

#### Scenario: Discover Robofocus on COM5
- **GIVEN** Robofocus is connected to COM5
- **AND** COM3 has an Arduino (responds with garbage)
- **AND** COM8 is unresponsive (timeout)
- **WHEN** driver calls `scan_for_robofocus()`
- **THEN** result SHALL contain one discovered device:
  - `port`: "COM5"
  - `firmware_version`: "002100"
  - `description`: "USB Serial Device"
- **AND** COM3 and COM8 SHALL NOT be in result

#### Scenario: Multiple Robofocus devices found
- **GIVEN** two Robofocus units connected on COM5 and COM12
- **WHEN** driver calls `scan_for_robofocus()`
- **THEN** result SHALL contain both devices
- **AND** each with correct port and firmware version
- **AND** driver SHALL log INFO: "Found 2 Robofocus devices"

#### Scenario: No Robofocus found
- **GIVEN** no Robofocus connected to any port
- **WHEN** driver calls `scan_for_robofocus()`
- **THEN** result SHALL be empty list
- **AND** driver SHALL log WARNING: "No Robofocus device found on any COM port"

#### Scenario: Port busy during scan
- **GIVEN** COM5 is in use by another application
- **WHEN** driver attempts to scan COM5
- **THEN** scan SHALL skip COM5 gracefully
- **AND** log DEBUG: "Skipping COM5: port in use"
- **AND** continue scanning remaining ports

#### Scenario: Scan timeout per port
- **GIVEN** scan timeout is configured as 1 second
- **WHEN** driver probes an unresponsive port
- **THEN** timeout SHALL occur after 1 second (not 5 seconds)
- **AND** scan proceeds to next port immediately

### Requirement: Discovery Scan Timeout Configuration

The system SHALL allow configuration of per-port scan timeout, separate from normal command timeout, to enable fast scanning.

#### Scenario: Fast scan with 1-second timeout
- **GIVEN** config `serial.scan_timeout_seconds=1.0`
- **AND** 5 COM ports available
- **WHEN** driver scans all ports (all unresponsive)
- **THEN** total scan time SHALL be approximately 5 seconds
- **AND** NOT 25 seconds (5 ports x 5s default timeout)

#### Scenario: Thorough scan with longer timeout
- **GIVEN** config `serial.scan_timeout_seconds=3.0`
- **AND** slow USB-serial adapter
- **WHEN** driver scans ports
- **THEN** each port gets 3 seconds to respond
- **AND** slow devices are not incorrectly skipped

### Requirement: Auto-Discovery Mode Configuration

The system SHALL support configuration option to enable or disable auto-discovery, with fallback to manual port specification.

#### Scenario: Auto-discovery enabled (default)
- **GIVEN** config `serial.auto_discover=true`
- **AND** config `serial.port` is empty or not specified
- **WHEN** driver starts
- **THEN** driver SHALL scan for Robofocus automatically
- **AND** connect to first discovered device
- **AND** log INFO: "Auto-discovered Robofocus on COM5 (firmware: 002100)"

#### Scenario: Auto-discovery disabled, manual port
- **GIVEN** config `serial.auto_discover=false`
- **AND** config `serial.port="COM12"`
- **WHEN** driver starts
- **THEN** driver SHALL NOT scan ports
- **AND** connect directly to COM12
- **AND** validate with FV handshake

#### Scenario: Auto-discovery enabled but port specified
- **GIVEN** config `serial.auto_discover=true`
- **AND** config `serial.port="COM12"` (explicit override)
- **WHEN** driver starts
- **THEN** driver SHALL skip auto-discovery
- **AND** use specified COM12 directly
- **AND** log INFO: "Using manually specified port COM12"

#### Scenario: Auto-discovery finds nothing, port specified as fallback
- **GIVEN** config `serial.auto_discover=true`
- **AND** config `serial.port="COM12"` as fallback
- **AND** auto-discovery finds no devices
- **WHEN** driver starts
- **THEN** driver SHALL attempt COM12 as fallback
- **AND** log WARNING: "Auto-discovery failed, trying fallback port COM12"

### Requirement: Port Scan API Endpoint

The system SHALL expose REST API endpoints to list available ports and trigger Robofocus discovery scan.

#### Scenario: List available ports via API
- **GIVEN** server is running
- **WHEN** client sends `GET /api/v1/management/ports`
- **THEN** response SHALL be JSON:
```json
{
  "Value": [
    {"name": "COM3", "description": "USB Serial Device", "hardware_id": "USB\\VID_0403"},
    {"name": "COM5", "description": "FTDI FT232R", "hardware_id": "USB\\VID_0403"}
  ]
}
```

#### Scenario: Trigger discovery scan via API
- **GIVEN** server is running
- **WHEN** client sends `POST /api/v1/management/scan`
- **THEN** server SHALL perform Robofocus scan
- **AND** response SHALL be JSON:
```json
{
  "Value": [
    {"port": "COM5", "firmware_version": "002100", "description": "FTDI FT232R"}
  ],
  "scan_duration_ms": 3500
}
```

#### Scenario: Scan while connected
- **GIVEN** driver is already connected to COM5
- **WHEN** client sends `POST /api/v1/management/scan`
- **THEN** server SHALL skip COM5 (already in use by self)
- **AND** scan remaining ports
- **AND** response SHALL note: `"current_port": "COM5"`

### Requirement: Discovery Result Selection

The system SHALL allow runtime selection of discovered port without restarting the driver.

#### Scenario: Select discovered port via API
- **GIVEN** scan found Robofocus on COM5 and COM12
- **AND** driver is not yet connected
- **WHEN** client sends `PUT /api/v1/management/select-port` with body `{"port": "COM12"}`
- **THEN** driver SHALL connect to COM12
- **AND** response SHALL confirm: `{"selected": "COM12", "firmware_version": "002100"}`

#### Scenario: Select invalid port
- **GIVEN** only COM5 has Robofocus
- **WHEN** client sends `PUT /api/v1/management/select-port` with body `{"port": "COM99"}`
- **THEN** response SHALL be error: `{"error": "Port COM99 not found or not a Robofocus device"}`
- **AND** HTTP status SHALL be 400

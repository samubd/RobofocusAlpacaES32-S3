# Capability: Alpaca Driver

ASCOM Alpaca HTTP API implementation for Robofocus focuser control. Provides RESTful endpoints compliant with ASCOM Alpaca v1 specification.

## ADDED Requirements

### Requirement: HTTP Server

The system SHALL run an HTTP server on a configurable IP address and port (default: 0.0.0.0:5000).

#### Scenario: Server starts successfully
- **GIVEN** valid configuration with `server.ip="0.0.0.0"` and `server.port=5000`
- **WHEN** the driver application is started
- **THEN** HTTP server listens on all interfaces port 5000
- **AND** server logs "Server started on http://0.0.0.0:5000"

#### Scenario: Port already in use
- **GIVEN** another application is using port 5000
- **WHEN** the driver attempts to start
- **THEN** the application SHALL exit with error code 1
- **AND** log message "Failed to bind to port 5000: Address already in use"

### Requirement: UDP Discovery Protocol

The system SHALL implement ASCOM Alpaca discovery protocol on UDP port 32227 to enable automatic device detection by astronomy clients.

#### Scenario: Discovery request received
- **GIVEN** server is running on TCP port 5000
- **AND** UDP listener is active on port 32227
- **WHEN** client sends UDP packet "alpacadiscovery1" to 255.255.255.255:32227
- **THEN** server SHALL respond to sender's IP with JSON `{"AlpacaPort": 5000}`

#### Scenario: Discovery disabled in configuration
- **GIVEN** configuration has `server.discovery_enabled=false`
- **WHEN** server starts
- **THEN** UDP listener SHALL NOT be created
- **AND** log message "Discovery protocol disabled"

### Requirement: JSON Response Envelope

All API responses SHALL use the ASCOM Alpaca JSON envelope format with `Value`, `ClientTransactionID`, `ServerTransactionID`, `ErrorNumber`, and `ErrorMessage` fields.

#### Scenario: Successful GET request
- **GIVEN** connected focuser at position 5000
- **WHEN** client calls `GET /api/v1/focuser/0/position?ClientTransactionID=123`
- **THEN** response SHALL be HTTP 200 with body:
  ```json
  {
    "Value": 5000,
    "ClientTransactionID": 123,
    "ServerTransactionID": 1,
    "ErrorNumber": 0,
    "ErrorMessage": ""
  }
  ```

#### Scenario: Request without ClientTransactionID
- **GIVEN** client omits ClientTransactionID parameter
- **WHEN** client calls `GET /api/v1/focuser/0/position`
- **THEN** response SHALL have `ClientTransactionID: 0`
- **AND** `ServerTransactionID` SHALL still increment

#### Scenario: Error during processing
- **GIVEN** focuser is not connected
- **WHEN** client calls `GET /api/v1/focuser/0/position?ClientTransactionID=456`
- **THEN** response SHALL be HTTP 200 with body:
  ```json
  {
    "Value": null,
    "ClientTransactionID": 456,
    "ServerTransactionID": 2,
    "ErrorNumber": 1031,
    "ErrorMessage": "Focuser not connected"
  }
  ```

### Requirement: ServerTransactionID Increment

The system SHALL maintain a global counter for ServerTransactionID, incrementing atomically for each API request.

#### Scenario: Sequential requests increment counter
- **GIVEN** ServerTransactionID is currently 10
- **WHEN** client makes 3 sequential requests
- **THEN** responses SHALL have ServerTransactionID values: 11, 12, 13

#### Scenario: Concurrent requests have unique IDs
- **GIVEN** 10 clients make simultaneous requests
- **WHEN** all responses are collected
- **THEN** all 10 ServerTransactionID values SHALL be unique
- **AND** counter SHALL have incremented by exactly 10

### Requirement: GET /api/v1/focuser/0/connected

The endpoint SHALL return the current connection status as a boolean value.

#### Scenario: Focuser connected
- **GIVEN** serial port is open and device responsive
- **WHEN** client calls `GET /api/v1/focuser/0/connected`
- **THEN** response SHALL have `Value: true`

#### Scenario: Focuser disconnected
- **GIVEN** serial port is closed
- **WHEN** client calls `GET /api/v1/focuser/0/connected`
- **THEN** response SHALL have `Value: false`

### Requirement: PUT /api/v1/focuser/0/connected

The endpoint SHALL accept `Connected=true` or `Connected=false` (form-encoded) to open or close the serial connection.

#### Scenario: Connect to focuser
- **GIVEN** focuser is currently disconnected
- **AND** configuration has `serial.port="COM12"`
- **WHEN** client calls `PUT /api/v1/focuser/0/connected` with body `Connected=true`
- **THEN** driver SHALL open serial port COM12 at 9600 baud
- **AND** send handshake command `FV000000` + checksum
- **AND** response SHALL have `Value: true` if successful

#### Scenario: Disconnect from focuser
- **GIVEN** focuser is currently connected
- **WHEN** client calls `PUT /api/v1/focuser/0/connected` with body `Connected=false`
- **THEN** driver SHALL close serial port
- **AND** set internal state to disconnected
- **AND** response SHALL have `Value: false`

#### Scenario: Connect with invalid port
- **GIVEN** configuration has `serial.port="COM99"` (non-existent)
- **WHEN** client calls `PUT /api/v1/focuser/0/connected` with body `Connected=true`
- **THEN** response SHALL have `ErrorNumber: 1280` (DriverError)
- **AND** `ErrorMessage: "Failed to open COM99: Port not found"`

### Requirement: GET /api/v1/focuser/0/position

The endpoint SHALL return the current focuser position in steps (integer).

#### Scenario: Read position while idle
- **GIVEN** focuser is connected and stationary at position 12345
- **WHEN** client calls `GET /api/v1/focuser/0/position`
- **THEN** driver SHALL send command `FG000000` + checksum
- **AND** parse response `FD012345` + checksum
- **AND** return `Value: 12345`

#### Scenario: Read position while moving
- **GIVEN** focuser is moving toward target 20000
- **AND** cached position is 15000
- **WHEN** client calls `GET /api/v1/focuser/0/position`
- **THEN** driver SHALL return cached value `Value: 15000`
- **AND** NOT send serial command (to avoid interrupting movement)

### Requirement: PUT /api/v1/focuser/0/move

The endpoint SHALL accept `Position=<integer>` (form-encoded) to initiate absolute movement. The operation SHALL be non-blocking (return immediately).

#### Scenario: Move to valid position
- **GIVEN** focuser is connected at position 5000
- **AND** `focuser.max_step=60000` in configuration
- **WHEN** client calls `PUT /api/v1/focuser/0/move` with body `Position=10000`
- **THEN** driver SHALL send command `FG010000` + checksum
- **AND** set internal flag `is_moving=true`
- **AND** return HTTP 200 immediately (NOT wait for completion)
- **AND** start background polling of position

#### Scenario: Move beyond MaxStep
- **GIVEN** `focuser.max_step=60000`
- **WHEN** client calls `PUT /api/v1/focuser/0/move` with body `Position=70000`
- **THEN** driver SHALL clamp position to 60000
- **AND** send command `FG060000` + checksum
- **AND** log warning "Position clamped: 70000 -> 60000"

#### Scenario: Move while already moving
- **GIVEN** focuser is currently moving to position 20000
- **WHEN** client calls `PUT /api/v1/focuser/0/move` with body `Position=30000`
- **THEN** driver SHALL cancel current movement
- **AND** send new command `FG030000` + checksum
- **AND** update target position to 30000

#### Scenario: Move while disconnected
- **GIVEN** focuser is not connected
- **WHEN** client calls `PUT /api/v1/focuser/0/move` with body `Position=5000`
- **THEN** response SHALL have `ErrorNumber: 1031` (NotConnected)
- **AND** `ErrorMessage: "Cannot move: focuser not connected"`

### Requirement: GET /api/v1/focuser/0/ismoving

The endpoint SHALL return a boolean indicating whether the focuser is currently moving.

#### Scenario: Focuser is moving
- **GIVEN** a move command was issued 2 seconds ago
- **AND** target position not yet reached
- **WHEN** client calls `GET /api/v1/focuser/0/ismoving`
- **THEN** response SHALL have `Value: true`

#### Scenario: Focuser reached target
- **GIVEN** focuser was moving
- **AND** current position equals target position
- **WHEN** client calls `GET /api/v1/focuser/0/ismoving`
- **THEN** response SHALL have `Value: false`

#### Scenario: Focuser halted mid-movement
- **GIVEN** focuser was moving
- **AND** halt command was issued
- **WHEN** client calls `GET /api/v1/focuser/0/ismoving`
- **THEN** response SHALL have `Value: false`

### Requirement: PUT /api/v1/focuser/0/halt

The endpoint SHALL immediately stop focuser movement (emergency stop).

#### Scenario: Halt during movement
- **GIVEN** focuser is moving toward target 50000
- **AND** current position is 30000
- **WHEN** client calls `PUT /api/v1/focuser/0/halt`
- **THEN** driver SHALL send stop command `FQ000000` + checksum
- **AND** set `is_moving=false` immediately
- **AND** update position to current hardware position
- **AND** return HTTP 200 within 50ms

#### Scenario: Halt while idle
- **GIVEN** focuser is stationary
- **WHEN** client calls `PUT /api/v1/focuser/0/halt`
- **THEN** response SHALL succeed with HTTP 200
- **AND** no serial command sent (optimization)

### Requirement: GET /api/v1/focuser/0/temperature

The endpoint SHALL return the ambient temperature in degrees Celsius (double precision).

#### Scenario: Read temperature
- **GIVEN** focuser is connected
- **WHEN** client calls `GET /api/v1/focuser/0/temperature`
- **THEN** driver SHALL send command `FT000000` + checksum
- **AND** parse response `FT000580` + checksum (raw ADC value 580)
- **AND** convert using formula `(580 / 2.0) - 273.15 = 16.85`
- **AND** return `Value: 16.85`

#### Scenario: Temperature sensor not available
- **GIVEN** focuser hardware lacks temperature sensor
- **WHEN** client calls `GET /api/v1/focuser/0/temperature`
- **THEN** response SHALL have `ErrorNumber: 1024` (NotImplemented)
- **AND** `ErrorMessage: "Temperature sensor not available"`

### Requirement: GET /api/v1/focuser/0/absolute

The endpoint SHALL return `true` (boolean) indicating the focuser supports absolute positioning.

#### Scenario: Query absolute support
- **WHEN** client calls `GET /api/v1/focuser/0/absolute`
- **THEN** response SHALL have `Value: true`

### Requirement: GET /api/v1/focuser/0/maxstep

The endpoint SHALL return the maximum position value in steps (integer).

#### Scenario: Query maximum position
- **GIVEN** configuration has `focuser.max_step=60000`
- **WHEN** client calls `GET /api/v1/focuser/0/maxstep`
- **THEN** response SHALL have `Value: 60000`

### Requirement: GET /api/v1/focuser/0/maxincrement

The endpoint SHALL return the maximum single move increment in steps (integer).

#### Scenario: Query maximum increment
- **GIVEN** configuration has `focuser.max_step=60000`
- **WHEN** client calls `GET /api/v1/focuser/0/maxincrement`
- **THEN** response SHALL have `Value: 60000`
- **AND** (same as maxstep for Robofocus)

### Requirement: GET /api/v1/focuser/0/stepsize

The endpoint SHALL return the step size in microns (double precision).

#### Scenario: Query step size
- **GIVEN** configuration has `focuser.step_size_microns=4.5`
- **WHEN** client calls `GET /api/v1/focuser/0/stepsize`
- **THEN** response SHALL have `Value: 4.5`

### Requirement: GET /api/v1/focuser/0/tempcomp

The endpoint SHALL return `false` indicating temperature compensation is not active.

#### Scenario: Query temperature compensation status
- **WHEN** client calls `GET /api/v1/focuser/0/tempcomp`
- **THEN** response SHALL have `Value: false`
- **AND** (Robofocus lacks automatic temp compensation)

### Requirement: GET /api/v1/focuser/0/tempcompavailable

The endpoint SHALL return `false` indicating temperature compensation is not available.

#### Scenario: Query temperature compensation availability
- **WHEN** client calls `GET /api/v1/focuser/0/tempcompavailable`
- **THEN** response SHALL have `Value: false`

### Requirement: GET /api/v1/focuser/0/interfaceversion

The endpoint SHALL return the ASCOM Alpaca interface version (integer).

#### Scenario: Query interface version
- **WHEN** client calls `GET /api/v1/focuser/0/interfaceversion`
- **THEN** response SHALL have `Value: 2`
- **AND** (IFocuserV2 interface)

### Requirement: GET /api/v1/focuser/0/driverversion

The endpoint SHALL return the driver version string.

#### Scenario: Query driver version
- **WHEN** client calls `GET /api/v1/focuser/0/driverversion`
- **THEN** response SHALL have `Value: "1.0.0"`
- **AND** format SHALL be semantic versioning (MAJOR.MINOR.PATCH)

### Requirement: GET /api/v1/focuser/0/driverinfo

The endpoint SHALL return a description of the driver (string).

#### Scenario: Query driver information
- **WHEN** client calls `GET /api/v1/focuser/0/driverinfo`
- **THEN** response SHALL have `Value: "ASCOM Alpaca Driver for Robofocus Focuser"`

### Requirement: GET /api/v1/focuser/0/description

The endpoint SHALL return a human-readable device description (string).

#### Scenario: Query device description
- **WHEN** client calls `GET /api/v1/focuser/0/description`
- **THEN** response SHALL have `Value: "Robofocus Electronic Focuser"`

### Requirement: GET /api/v1/focuser/0/name

The endpoint SHALL return the device name (string).

#### Scenario: Query device name
- **WHEN** client calls `GET /api/v1/focuser/0/name`
- **THEN** response SHALL have `Value: "Robofocus"`

### Requirement: GET /api/v1/focuser/0/supportedactions

The endpoint SHALL return an empty array indicating no custom actions are supported.

#### Scenario: Query supported actions
- **WHEN** client calls `GET /api/v1/focuser/0/supportedactions`
- **THEN** response SHALL have `Value: []`

### Requirement: Error Handling

The system SHALL catch all exceptions during request processing and return appropriate ASCOM Alpaca error codes in the JSON envelope (HTTP 200 with ErrorNumber != 0).

#### Scenario: Serial timeout during position read
- **GIVEN** hardware is unresponsive (unplugged cable)
- **WHEN** client calls `GET /api/v1/focuser/0/position`
- **THEN** after 5 seconds timeout
- **AND** response SHALL have `ErrorNumber: 1280` (DriverError)
- **AND** `ErrorMessage: "Serial timeout: no response from hardware"`

#### Scenario: Unhandled exception
- **GIVEN** a bug causes uncaught TypeError in handler code
- **WHEN** client calls any endpoint
- **THEN** response SHALL have `ErrorNumber: 1280` (DriverError)
- **AND** `ErrorMessage: "Internal error: <exception details>"`
- **AND** full stack trace logged at ERROR level

### Requirement: Request Logging

The system SHALL log all incoming API requests with timestamp, endpoint, parameters, and response status.

#### Scenario: Request logged at INFO level
- **GIVEN** logging level is INFO
- **WHEN** client calls `PUT /api/v1/focuser/0/move` with `Position=5000`
- **THEN** log SHALL contain:
  ```
  [2026-01-12 14:30:45] INFO: PUT /api/v1/focuser/0/move Position=5000 ClientTransactionID=10 -> 200 OK ServerTransactionID=5
  ```

#### Scenario: Request logged at DEBUG level
- **GIVEN** logging level is DEBUG
- **WHEN** client calls `GET /api/v1/focuser/0/position`
- **THEN** log SHALL contain full request headers and response body

### Requirement: CORS Support

The system SHALL allow Cross-Origin Resource Sharing (CORS) to enable browser-based astronomy clients.

#### Scenario: Preflight OPTIONS request
- **WHEN** browser sends `OPTIONS /api/v1/focuser/0/position`
- **THEN** response SHALL include headers:
  ```
  Access-Control-Allow-Origin: *
  Access-Control-Allow-Methods: GET, PUT, POST
  Access-Control-Allow-Headers: Content-Type
  ```

#### Scenario: GET request with CORS
- **WHEN** client calls `GET /api/v1/focuser/0/position` with `Origin: http://localhost:3000`
- **THEN** response SHALL include `Access-Control-Allow-Origin: *`

### Requirement: Content-Type Handling

The system SHALL accept form-encoded (`application/x-www-form-urlencoded`) and JSON (`application/json`) request bodies for PUT methods.

#### Scenario: PUT with form encoding
- **WHEN** client calls `PUT /api/v1/focuser/0/move` with header `Content-Type: application/x-www-form-urlencoded`
- **AND** body `Position=5000&ClientTransactionID=10`
- **THEN** request SHALL be parsed successfully

#### Scenario: PUT with JSON encoding
- **WHEN** client calls `PUT /api/v1/focuser/0/move` with header `Content-Type: application/json`
- **AND** body `{"Position": 5000, "ClientTransactionID": 10}`
- **THEN** request SHALL be parsed successfully

### Requirement: Thread Safety

All API endpoints SHALL be thread-safe, allowing concurrent requests from multiple clients without data corruption.

#### Scenario: Concurrent position queries
- **GIVEN** 10 clients simultaneously call `GET /api/v1/focuser/0/position`
- **WHEN** all requests are processed
- **THEN** all responses SHALL have valid position values
- **AND** no race conditions or deadlocks occur
- **AND** all ServerTransactionID values are unique

#### Scenario: Concurrent move and position read
- **GIVEN** client A calls `PUT /api/v1/focuser/0/move` with `Position=10000`
- **AND** simultaneously client B calls `GET /api/v1/focuser/0/position`
- **WHEN** both requests complete
- **THEN** no deadlock occurs
- **AND** position read returns valid value (either old or new position)

### Requirement: Graceful Shutdown

The system SHALL handle SIGINT (Ctrl+C) and SIGTERM signals by closing the serial port and shutting down the HTTP server gracefully.

#### Scenario: User presses Ctrl+C
- **GIVEN** driver is running with active connection
- **WHEN** user presses Ctrl+C
- **THEN** driver SHALL log "Shutting down..."
- **AND** close serial port
- **AND** stop HTTP server
- **AND** exit with code 0 within 5 seconds

#### Scenario: Shutdown during active movement
- **GIVEN** focuser is moving
- **WHEN** shutdown signal received
- **THEN** driver SHALL send halt command to hardware
- **AND** wait up to 2 seconds for movement to stop
- **AND** then close serial port and exit

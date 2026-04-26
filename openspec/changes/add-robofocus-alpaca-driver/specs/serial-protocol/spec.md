# Capability: Serial Protocol

Low-level RS-232 communication protocol for Robofocus electronic focuser hardware. Implements 9-byte fixed-length command/response format with checksum validation.

## CRITICAL: Response Reading Pattern (Reference: INDI robofocus.cpp)

**The INDI driver is the authoritative reference. See `references/robofocus.cpp` ReadResponse() function.**

### Requirement: Blocking Read Loop Until 'F'

The system SHALL read responses using a blocking loop that continues until the 'F' character (0x46) is received. This is the ONLY correct pattern.

#### Scenario: Normal query response
- **GIVEN** focuser is idle
- **WHEN** driver sends FG query command
- **THEN** first byte received SHALL be 'F' (0x46)
- **AND** driver SHALL read remaining 8 bytes
- **AND** return complete 9-byte response

#### Scenario: Response during handset movement
- **GIVEN** user is pressing handset buttons during query
- **WHEN** driver sends FG query command
- **THEN** first bytes received SHALL be 'I' (0x49) or 'O' (0x4F) characters
- **AND** driver SHALL set internal `is_moving` flag to true
- **AND** driver SHALL continue reading in loop (NOT throw exception)
- **AND** when 'F' (0x46) is received, driver SHALL read remaining 8 bytes
- **AND** driver SHALL set `is_moving` flag to false
- **AND** return complete 9-byte response with final position

#### Scenario: Long handset press
- **GIVEN** user holds handset button for 30 seconds
- **WHEN** driver is in read loop
- **THEN** driver SHALL receive hundreds of 'I' or 'O' characters
- **AND** driver SHALL remain in loop for entire 30 seconds
- **AND** when user releases button, 'F' + response arrives
- **AND** driver returns with correct final position

### Requirement: FORBIDDEN - Exception on I/O Characters

The system SHALL NOT throw exceptions, raise errors, or exit the read loop when receiving 'I' or 'O' characters. These characters indicate movement in progress and MUST be handled by continuing to read.

#### Anti-pattern: DO NOT implement
```python
# WRONG - DO NOT DO THIS
if char == 'I' or char == 'O':
    raise ManualMovementDetected()  # FORBIDDEN
```

#### Correct pattern: Continue loop
```python
# CORRECT - Follow INDI driver pattern
while True:
    char = read_one_byte()
    if char == 'I':
        is_moving = True
        continue  # Keep reading
    elif char == 'O':
        is_moving = True
        continue  # Keep reading
    elif char == 'F':
        response = char + read_8_more_bytes()
        is_moving = False
        return response
```

### Requirement: No Complex State Machines

The system SHALL NOT implement separate movement states like "MOVING_PROGRAMMATIC" vs "MOVING_EXTERNAL". The protocol is identical for both cases - read until 'F'.

### Requirement: Buffer Handling

The system SHALL flush serial buffers ONLY:
- Before sending a command (flush output buffer)
- After receiving complete 'F' + 8 bytes response (flush input buffer)

The system SHALL NOT flush buffers when receiving 'I' or 'O' characters mid-read.

## ADDED Requirements

### Requirement: Serial Port Configuration

The system SHALL configure the serial port with fixed parameters: 9600 baud, 8 data bits, no parity, 1 stop bit, no flow control.

#### Scenario: Open serial port successfully
- **GIVEN** configuration specifies `serial.port="COM12"`
- **WHEN** driver opens the serial connection
- **THEN** port SHALL be configured with:
  - Baud rate: 9600
  - Data bits: 8
  - Parity: None
  - Stop bits: 1
  - Flow control: None
- **AND** receive timeout SHALL be set to 5 seconds

#### Scenario: Serial port does not exist
- **GIVEN** configuration specifies `serial.port="COM99"` (non-existent)
- **WHEN** driver attempts to open the connection
- **THEN** operation SHALL raise `PortNotFoundError`
- **AND** error message SHALL be "Failed to open COM99: Port not found"

#### Scenario: Serial port already in use
- **GIVEN** another application has opened COM12
- **WHEN** driver attempts to open COM12
- **THEN** operation SHALL raise `PortInUseError`
- **AND** error message SHALL be "COM12 is already in use by another application"

### Requirement: Command Packet Format

All commands sent to the hardware SHALL be exactly 9 bytes: 2-byte ASCII command code, 6-byte ASCII numeric value (zero-padded), 1-byte binary checksum.

#### Scenario: Encode position command
- **GIVEN** command "FG" (Go to position)
- **AND** target position 2500
- **WHEN** command is encoded
- **THEN** packet SHALL be 9 bytes: `FG002500` + checksum byte
- **AND** checksum SHALL be `(70+71+48+48+50+53+48+48) % 256 = 127`

#### Scenario: Encode query command
- **GIVEN** command "FV" (Get version)
- **WHEN** command is encoded
- **THEN** packet SHALL be 9 bytes: `FV000000` + checksum byte
- **AND** checksum SHALL be `(70+86+48+48+48+48+48+48) % 256 = 54`

#### Scenario: Value exceeds 6 digits
- **GIVEN** position value 1234567 (7 digits)
- **WHEN** encoding FG command
- **THEN** encoder SHALL raise `ValueError`
- **AND** message SHALL be "Value 1234567 exceeds 6-digit maximum (999999)"

### Requirement: Response Packet Format

All responses from hardware SHALL be exactly 9 bytes: 2-byte ASCII command echo, 6-byte ASCII data, 1-byte binary checksum. The system SHALL validate response length and checksum.

#### Scenario: Parse valid position response
- **GIVEN** hardware sends `FD012345` + checksum byte 0x7F
- **WHEN** response is parsed
- **THEN** command SHALL be extracted as "FD"
- **AND** value SHALL be extracted as integer 12345
- **AND** checksum SHALL be validated as correct

#### Scenario: Parse temperature response
- **GIVEN** hardware sends `FT000580` + checksum byte 0x3A
- **WHEN** response is parsed
- **THEN** command SHALL be "FT"
- **AND** value SHALL be 580 (raw ADC)
- **AND** checksum SHALL be validated

#### Scenario: Response too short
- **GIVEN** hardware sends only 7 bytes (cable disconnected mid-transmission)
- **WHEN** driver reads response
- **THEN** operation SHALL raise `ProtocolError`
- **AND** message SHALL be "Expected 9 bytes, received 7"

#### Scenario: Checksum mismatch
- **GIVEN** hardware sends `FD005000` + incorrect checksum 0xFF
- **WHEN** response is parsed
- **THEN** operation SHALL raise `ChecksumMismatchError`
- **AND** message SHALL include "Expected checksum: 0x7D, Received: 0xFF"
- **AND** raw packet SHALL be logged at WARNING level

### Requirement: Checksum Calculation

Checksum SHALL be calculated as the sum of ASCII values of the first 8 bytes, modulo 256, returned as unsigned byte (0-255).

#### Scenario: Calculate checksum for FG002500
- **GIVEN** message string "FG002500"
- **WHEN** checksum is calculated
- **THEN** result SHALL be `(70+71+48+48+50+53+48+48) % 256 = 127`

#### Scenario: Calculate checksum for FV000000
- **GIVEN** message string "FV000000"
- **WHEN** checksum is calculated
- **THEN** result SHALL be `(70+86+48+48+48+48+48+48) % 256 = 54`

#### Scenario: Verify checksum on received packet
- **GIVEN** received packet `FT000580` + byte 0x3A
- **WHEN** checksum is validated
- **THEN** calculated checksum SHALL match received checksum 0x3A
- **AND** validation SHALL return True

### Requirement: FV Command - Get Firmware Version

The system SHALL send `FV000000` + checksum to query firmware version, expecting response `FVxxxxxx` + checksum where xxxxxx is version number.

#### Scenario: Query firmware version successfully
- **GIVEN** serial port is open
- **WHEN** driver sends FV command
- **THEN** hardware SHALL respond with `FV002100` + checksum (version 2.1.0)
- **AND** driver SHALL parse version as integer 2100

#### Scenario: No response to FV command
- **GIVEN** serial port is open but hardware is unresponsive
- **WHEN** driver sends FV command
- **THEN** after 5 second timeout
- **AND** operation SHALL raise `SerialTimeoutError`
- **AND** message SHALL be "No response to FV command within 5 seconds"

### Requirement: FG Command - Move to Absolute Position

The system SHALL send `FGxxxxx0` + checksum to initiate movement to position xxxxx (5-digit, last digit always 0), expecting response `FDxxxxxx` + checksum echoing final position.

#### Scenario: Move to position 10000
- **GIVEN** serial port is open
- **WHEN** driver sends `FG010000` + checksum
- **THEN** hardware begins movement
- **AND** driver receives initial response `FD010000` + checksum
- **AND** movement continues until target reached

#### Scenario: Move to position 0 (home)
- **GIVEN** focuser is at position 50000
- **WHEN** driver sends `FG000000` + checksum
- **THEN** hardware moves inward to position 0
- **AND** during movement, asynchronous 'I' characters are sent

#### Scenario: Target position same as current
- **GIVEN** focuser is at position 25000
- **WHEN** driver sends `FG025000` + checksum
- **THEN** hardware SHALL respond immediately with `FD025000` + checksum
- **AND** no movement occurs (optimization)

### Requirement: FD Command - Query Current Position

The system SHALL send `FG000000` + checksum as a query (not move) to read current position, expecting response `FDxxxxxx` + checksum.

#### Scenario: Query position while stationary
- **GIVEN** focuser is idle at position 15000
- **WHEN** driver sends `FG000000` + checksum (query, not move to 0)
- **THEN** hardware SHALL respond `FD015000` + checksum
- **AND** no movement occurs

#### Scenario: Query position repeatedly
- **GIVEN** focuser is idle
- **WHEN** driver sends FG query 10 times in succession
- **THEN** all responses SHALL return consistent position value
- **AND** each response arrives within 200ms

### Requirement: FT Command - Query Temperature

The system SHALL send `FT000000` + checksum to read raw ADC temperature value, expecting response `FTxxxxxx` + checksum. The raw value SHALL be converted to Celsius using formula `(raw / 2.0) - 273.15`.

#### Scenario: Read temperature 16.85°C
- **GIVEN** ambient temperature is 16.85°C
- **WHEN** driver sends `FT000000` + checksum
- **THEN** hardware responds `FT000580` + checksum (raw ADC = 580)
- **AND** driver converts: `(580 / 2.0) - 273.15 = 16.85`°C

#### Scenario: Read temperature -5°C
- **GIVEN** cold environment at -5°C
- **WHEN** driver sends FT command
- **THEN** hardware responds `FT000536` + checksum (raw = 536)
- **AND** driver converts: `(536 / 2.0) - 273.15 = -5.15`°C (approximately -5°C)

#### Scenario: Temperature sensor disconnected
- **GIVEN** temperature sensor cable is unplugged
- **WHEN** driver sends FT command
- **THEN** hardware MAY respond with `FT000000` or invalid value
- **AND** driver SHALL detect out-of-range value (<200 or >1000 raw ADC)
- **AND** raise `SensorError` with message "Temperature sensor not responding"

### Requirement: FQ Command - Emergency Halt

The system SHALL send `FQ000000` + checksum to immediately stop focuser movement.

#### Scenario: Halt during outward movement
- **GIVEN** focuser is moving from 10000 to 50000
- **AND** current position is approximately 30000
- **WHEN** driver sends `FQ000000` + checksum
- **THEN** hardware SHALL stop movement within 500ms
- **AND** final position SHALL be logged (e.g., 30127)

#### Scenario: Halt during inward movement
- **GIVEN** focuser is moving from 50000 to 10000
- **WHEN** driver sends FQ command
- **THEN** hardware stops immediately
- **AND** driver queries final position with FG command

#### Scenario: Halt while idle
- **GIVEN** focuser is stationary
- **WHEN** driver sends FQ command
- **THEN** hardware accepts command without error
- **AND** no position change occurs

### Requirement: Asynchronous Movement Characters

During movement, hardware SHALL send unsolicited single-byte characters: 'I' (0x49) for inward, 'O' (0x4F) for outward, 'F' (0x46) for finished. The system SHALL parse these to update cached position.

#### Scenario: Inward movement with 'I' characters
- **GIVEN** focuser is moving from 10000 to 5000
- **WHEN** driver polls serial port during movement
- **THEN** hardware SHALL send multiple 'I' characters (one per step)
- **AND** driver SHALL decrement cached position for each 'I'

#### Scenario: Outward movement with 'O' characters
- **GIVEN** focuser is moving from 5000 to 10000
- **WHEN** driver polls serial port
- **THEN** hardware SHALL send multiple 'O' characters
- **AND** driver SHALL increment cached position for each 'O'

#### Scenario: Movement completion with 'F' character
- **GIVEN** focuser is approaching target position 20000
- **WHEN** target is reached
- **THEN** hardware SHALL send 'F' character (0x46)
- **FOLLOWED BY** 8 additional bytes forming final position packet `FD020000`
- **AND** driver SHALL parse complete 9-byte packet starting with 'F'
- **AND** update cached position to 20000
- **AND** set `is_moving=false`

#### Scenario: Unexpected character received
- **GIVEN** driver is waiting for response
- **WHEN** hardware sends unknown character 'X' (0x58)
- **THEN** driver SHALL log warning "Unexpected character: 0x58"
- **AND** continue reading until valid packet received or timeout

### Requirement: FB Command - Backlash Compensation

The system SHALL send `FBxyyzzz` + checksum to configure backlash compensation, where x=mode (1=off, 2=inward, 3=outward), yy=00 (reserved), zzz=amount (0-255 steps).

#### Scenario: Set inward backlash 50 steps
- **GIVEN** user wants to compensate 50 steps on inward moves
- **WHEN** driver sends `FB200050` + checksum
- **THEN** hardware SHALL apply 50-step backlash compensation on inward movements
- **AND** respond with echo `FB200050` + checksum

#### Scenario: Set outward backlash 30 steps
- **GIVEN** user wants 30 steps outward backlash
- **WHEN** driver sends `FB300030` + checksum
- **THEN** hardware configures outward compensation
- **AND** responds `FB300030` + checksum

#### Scenario: Disable backlash compensation
- **GIVEN** backlash is currently enabled
- **WHEN** driver sends `FB100000` + checksum
- **THEN** hardware disables all backlash compensation
- **AND** responds `FB100000` + checksum

#### Scenario: Query current backlash setting
- **GIVEN** backlash is configured as inward 50 steps
- **WHEN** driver sends `FB000000` + checksum (query)
- **THEN** hardware responds `FB200050` + checksum

### Requirement: FL Command - Maximum Travel Limit

The system SHALL send `FLxxxxx0` + checksum to set maximum position limit, expecting echo response. Query with `FL000000`.

#### Scenario: Set maximum travel to 60000 steps
- **GIVEN** user configures `focuser.max_step=60000`
- **WHEN** driver sends `FL060000` + checksum
- **THEN** hardware SHALL enforce limit at 60000
- **AND** respond `FL060000` + checksum

#### Scenario: Query maximum travel limit
- **GIVEN** limit is set to 60000
- **WHEN** driver sends `FL000000` + checksum
- **THEN** hardware responds `FL060000` + checksum

#### Scenario: Attempt move beyond limit
- **GIVEN** max limit is 60000
- **AND** driver sends `FG065000` + checksum (move to 65000)
- **THEN** hardware SHALL clamp to 60000
- **AND** move to 60000 instead

### Requirement: FC Command - Motor Configuration

The system SHALL send `FCxyzabc` + checksum to configure motor parameters: x=duty cycle (1-9), y=delay (0-9), z=ticks per step (1-9), abc=000 (reserved).

#### Scenario: Set motor parameters
- **GIVEN** optimal motor config is duty=5, delay=2, ticks=3
- **WHEN** driver sends `FC523000` + checksum
- **THEN** hardware SHALL configure motor accordingly
- **AND** respond `FC523000` + checksum

#### Scenario: Query motor configuration
- **GIVEN** motor is configured
- **WHEN** driver sends `FC000000` + checksum
- **THEN** hardware responds with current settings (e.g., `FC523000`)

### Requirement: FP Command - Power Switches

The system SHALL send `FPxxxxx0` + checksum to control auxiliary power switches, expecting response `FPxabcd0` where a,b,c,d are switch states (1=off, 2=on).

#### Scenario: Query power switch states
- **GIVEN** switches 1,2 are on, 3,4 are off
- **WHEN** driver sends `FP000000` + checksum
- **THEN** hardware responds `FP022110` + checksum
- **AND** driver parses: SW1=off(1), SW2=on(2), SW3=on(2), SW4=off(1)

#### Scenario: Toggle switch 1
- **GIVEN** switch 1 is currently off
- **WHEN** driver sends `FP100000` + checksum
- **THEN** hardware SHALL toggle switch 1 to on
- **AND** respond with new state `FP021110`

### Requirement: FS Command - Sync Position

The system SHALL send `FSxxxxx0` + checksum to reset current position to specified value without moving hardware.

#### Scenario: Sync position to 30000
- **GIVEN** physical position is unknown after power loss
- **AND** user manually set focuser to known position
- **WHEN** driver sends `FS030000` + checksum
- **THEN** hardware SHALL set internal counter to 30000
- **AND** no movement occurs
- **AND** subsequent position queries return 30000

#### Scenario: Sync to zero after homing
- **GIVEN** user manually moved focuser to physical hard stop (home)
- **WHEN** driver sends `FS000000` + checksum
- **THEN** hardware SHALL reset position counter to 0

### Requirement: Serial Buffer Flushing

Before sending each command, the system SHALL flush the serial input and output buffers to discard stale data.

#### Scenario: Flush before command
- **GIVEN** previous command left data in buffer
- **WHEN** driver prepares to send new FG command
- **THEN** driver SHALL call `flush_input()` and `flush_output()`
- **AND** then send command
- **AND** avoid reading stale response

### Requirement: Timeout Handling

All serial read operations SHALL have a 5-second timeout. If timeout occurs, the system SHALL raise `SerialTimeoutError`.

#### Scenario: Command timeout after 5 seconds
- **GIVEN** hardware is unplugged
- **WHEN** driver sends FV command
- **THEN** after exactly 5 seconds
- **AND** operation SHALL raise `SerialTimeoutError`
- **AND** error message SHALL include command that timed out

#### Scenario: Partial response timeout
- **GIVEN** hardware sends first 4 bytes then stops
- **WHEN** driver waits for remaining 5 bytes
- **THEN** after 5 seconds total
- **AND** operation SHALL raise `ProtocolError` with message "Incomplete response: received 4/9 bytes"

### Requirement: Thread Safety for Serial Access

All serial port read/write operations SHALL be protected by a mutex lock to prevent concurrent access corruption.

#### Scenario: Concurrent command attempts
- **GIVEN** thread A is sending FG command (write + read in progress)
- **WHEN** thread B attempts to send FT command
- **THEN** thread B SHALL block until thread A completes
- **AND** thread B then executes successfully
- **AND** no interleaved bytes occur

#### Scenario: Lock timeout
- **GIVEN** thread A has acquired serial lock
- **AND** thread A hangs (bug in code)
- **WHEN** thread B waits for lock for 10 seconds
- **THEN** thread B SHALL raise `LockTimeoutError`
- **AND** system SHALL log "Serial lock timeout: possible deadlock"

### Requirement: Raw Packet Logging

When logging level is DEBUG, the system SHALL log all raw bytes sent and received in hexadecimal format.

#### Scenario: Debug logging enabled
- **GIVEN** config has `logging.level="DEBUG"`
- **WHEN** driver sends `FG002500` + checksum 0x7F
- **THEN** log SHALL contain: `TX: 46 47 30 30 32 35 30 30 7F`
- **AND** when response `FD002500` + 0x7D received
- **THEN** log SHALL contain: `RX: 46 44 30 30 32 35 30 30 7D`

#### Scenario: Info logging (no raw bytes)
- **GIVEN** config has `logging.level="INFO"`
- **WHEN** driver sends FG command
- **THEN** log SHALL contain: `Sending command: FG, value: 2500`
- **AND** NOT contain raw hex bytes (reduce log size)

### Requirement: Connection Validation

After opening serial port, the system SHALL send FV command to validate hardware responds correctly.

#### Scenario: Successful handshake
- **GIVEN** serial port just opened
- **WHEN** driver sends FV command
- **THEN** hardware responds with `FVxxxxxx` + valid checksum
- **AND** connection is marked as validated
- **AND** firmware version is stored for diagnostics

#### Scenario: Handshake failure
- **GIVEN** serial port opened but wrong device connected (e.g., GPS receiver)
- **WHEN** driver sends FV command
- **THEN** timeout or garbled response received
- **AND** driver SHALL close port
- **AND** raise `HandshakeError` with message "Hardware did not respond to FV command, wrong device?"

### Requirement: Retry Logic

If a command fails with timeout or checksum error, the system SHALL retry up to 3 times with 500ms delay between attempts before raising exception.

#### Scenario: First attempt fails, second succeeds
- **GIVEN** intermittent connection issue
- **WHEN** driver sends FG command
- **AND** first attempt times out
- **THEN** driver SHALL wait 500ms
- **AND** retry command
- **AND** second attempt succeeds
- **AND** log warning "Command FG retried: attempt 2/3"

#### Scenario: All retries exhausted
- **GIVEN** hardware is completely unresponsive
- **WHEN** driver sends FT command
- **AND** all 3 attempts timeout
- **THEN** driver SHALL raise `MaxRetriesExceededError`
- **AND** message SHALL be "FT command failed after 3 attempts"
- **AND** suggest checking cable/power

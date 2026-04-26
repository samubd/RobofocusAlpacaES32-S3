# Capability: Hardware Simulator

Mock Robofocus hardware implementation for development and testing without physical device. Simulates serial protocol behavior with configurable responses, delays, and error injection.

## ADDED Requirements

### Requirement: Interface Compatibility

The simulator SHALL implement the same interface as the real serial protocol handler, allowing transparent substitution via dependency injection.

#### Scenario: Drop-in replacement for real hardware
- **GIVEN** application code uses `SerialProtocolInterface`
- **WHEN** simulator is injected instead of `RobofocusSerial`
- **THEN** all API calls SHALL work identically
- **AND** no code changes required in upper layers

#### Scenario: Enable simulator via configuration
- **GIVEN** config file has `simulator.enabled=true`
- **WHEN** driver starts
- **THEN** simulator SHALL be instantiated instead of real serial connection
- **AND** log message "Running in SIMULATOR mode"

### Requirement: Virtual Position Tracking

The simulator SHALL maintain an internal position counter (integer) that updates during simulated movements.

#### Scenario: Initialize at position 0
- **GIVEN** simulator is created
- **WHEN** simulator starts
- **THEN** virtual position SHALL be 0

#### Scenario: Initialize at configured position
- **GIVEN** config has `simulator.initial_position=30000`
- **WHEN** simulator starts
- **THEN** virtual position SHALL be 30000

### Requirement: FV Command Simulation

The simulator SHALL respond to `FV000000` command with configurable firmware version.

#### Scenario: Return firmware version 2.1.0
- **GIVEN** config has `simulator.firmware_version="002100"`
- **WHEN** simulator receives `FV000000` + checksum
- **THEN** simulator SHALL respond `FV002100` + valid checksum
- **AND** log "Simulator: FV -> version 2100"

### Requirement: FG Command Simulation - Movement

The simulator SHALL simulate movement to target position with realistic timing based on configured speed.

#### Scenario: Move from 0 to 10000 at 500 steps/sec
- **GIVEN** simulator is at position 0
- **AND** config has `simulator.movement_speed_steps_per_sec=500`
- **WHEN** simulator receives `FG010000` + checksum
- **THEN** simulator SHALL respond immediately with `FD010000` + checksum
- **AND** spawn background thread to simulate movement
- **AND** send 'O' characters asynchronously during 20-second movement
- **AND** after 20 seconds, send 'F' + `FD010000` + checksum

#### Scenario: Move inward from 10000 to 5000
- **GIVEN** simulator is at position 10000
- **WHEN** simulator receives `FG005000` + checksum
- **THEN** simulator SHALL send 'I' characters during movement
- **AND** decrement internal position counter
- **AND** complete after 10 seconds (5000 steps / 500 steps/sec)

#### Scenario: Move to same position (no-op)
- **GIVEN** simulator is at position 5000
- **WHEN** simulator receives `FG005000` + checksum
- **THEN** simulator SHALL respond immediately with `FD005000`
- **AND** no movement thread spawned (optimization)

#### Scenario: Multiple move commands (cancel previous)
- **GIVEN** simulator is moving from 0 to 20000
- **AND** currently at position 8000
- **WHEN** simulator receives new command `FG015000` + checksum
- **THEN** simulator SHALL cancel ongoing movement
- **AND** start new movement toward 15000 from current position 8000

### Requirement: FG/FD Query Simulation

The simulator SHALL respond to position queries with current virtual position.

#### Scenario: Query position while idle
- **GIVEN** simulator is stationary at position 12345
- **WHEN** simulator receives `FG000000` + checksum (query)
- **THEN** simulator SHALL respond `FD012345` + checksum immediately

#### Scenario: Query position during movement
- **GIVEN** simulator is moving
- **AND** current virtual position is 7500
- **WHEN** position query received
- **THEN** simulator SHALL respond `FD007500` + checksum (current position)

### Requirement: FT Command Simulation - Temperature

The simulator SHALL return simulated temperature with configurable drift and noise.

#### Scenario: Static temperature 16.85°C
- **GIVEN** config has `simulator.temperature_celsius=16.85`
- **WHEN** simulator receives `FT000000` + checksum
- **THEN** simulator SHALL calculate raw ADC: `(16.85 + 273.15) * 2 = 580`
- **AND** respond `FT000580` + checksum

#### Scenario: Temperature with random noise
- **GIVEN** config has `simulator.temperature_noise_celsius=0.5`
- **WHEN** simulator receives multiple FT commands
- **THEN** each response SHALL vary by ±0.5°C randomly
- **EXAMPLE**: 16.3°C, 16.9°C, 16.6°C, etc.

#### Scenario: Temperature drift over time
- **GIVEN** config has `simulator.temperature_drift_per_hour=2.0`
- **AND** simulator started 1 hour ago at 16.85°C
- **WHEN** FT command received
- **THEN** simulator SHALL return 18.85°C (16.85 + 2.0)

### Requirement: FQ Command Simulation - Halt

The simulator SHALL immediately stop ongoing movement when FQ command received.

#### Scenario: Halt during movement
- **GIVEN** simulator is moving from 0 to 50000
- **AND** current position is 23456
- **WHEN** simulator receives `FQ000000` + checksum
- **THEN** movement thread SHALL stop immediately
- **AND** 'F' + final position packet sent
- **AND** virtual position frozen at 23456

#### Scenario: Halt while idle
- **GIVEN** simulator is stationary
- **WHEN** FQ command received
- **THEN** simulator accepts command without error
- **AND** no position change

### Requirement: FB Command Simulation - Backlash

The simulator SHALL store backlash configuration and echo it on query.

#### Scenario: Set and query backlash
- **GIVEN** simulator starts with no backlash
- **WHEN** simulator receives `FB200050` + checksum (inward 50 steps)
- **THEN** simulator SHALL store backlash mode=2, amount=50
- **AND** respond `FB200050` + checksum
- **AND** when queried with `FB000000`
- **THEN** respond `FB200050` + checksum

#### Scenario: Backlash affects movement (optional realism)
- **GIVEN** backlash is configured as outward 30 steps
- **WHEN** simulator moves outward
- **THEN** simulator MAY add 30 extra steps (realistic behavior)
- **OR** simply store configuration (simple mode)

### Requirement: FL Command Simulation - Max Limit

The simulator SHALL enforce maximum travel limit and clamp movements beyond it.

#### Scenario: Set max limit to 60000
- **GIVEN** simulator starts
- **WHEN** receives `FL060000` + checksum
- **THEN** simulator SHALL store max_limit=60000
- **AND** respond `FL060000` + checksum

#### Scenario: Movement clamped to limit
- **GIVEN** max_limit=60000
- **WHEN** receives `FG065000` + checksum (move to 65000)
- **THEN** simulator SHALL clamp to 60000
- **AND** move to 60000 instead
- **AND** log warning "Position clamped: 65000 -> 60000"

### Requirement: FC Command Simulation - Motor Config

The simulator SHALL store and echo motor configuration parameters.

#### Scenario: Set motor parameters
- **GIVEN** simulator starts
- **WHEN** receives `FC523000` + checksum
- **THEN** simulator SHALL store duty=5, delay=2, ticks=3
- **AND** respond `FC523000` + checksum
- **AND** when queried with `FC000000`
- **THEN** respond `FC523000` + checksum

### Requirement: FP Command Simulation - Power Switches

The simulator SHALL maintain state of 4 virtual power switches and support toggling.

#### Scenario: Query switch states
- **GIVEN** switches initialized as [off, on, on, off]
- **WHEN** simulator receives `FP000000` + checksum
- **THEN** simulator SHALL respond `FP012210` + checksum

#### Scenario: Toggle switch 1
- **GIVEN** switch 1 is off
- **WHEN** receives `FP100000` + checksum
- **THEN** simulator SHALL toggle switch 1 to on
- **AND** respond `FP022210` + checksum (updated state)

### Requirement: FS Command Simulation - Sync Position

The simulator SHALL accept position sync commands and update internal counter without movement.

#### Scenario: Sync to known position
- **GIVEN** simulator is at unknown position
- **WHEN** receives `FS030000` + checksum
- **THEN** simulator SHALL set virtual position to 30000
- **AND** no movement occurs
- **AND** subsequent queries return 30000

### Requirement: Checksum Validation

The simulator SHALL validate checksums on incoming commands and reject invalid packets.

#### Scenario: Valid checksum accepted
- **GIVEN** client sends `FG002500` + correct checksum 0x7F
- **WHEN** simulator receives packet
- **THEN** simulator processes command normally

#### Scenario: Invalid checksum rejected
- **GIVEN** client sends `FG002500` + wrong checksum 0xFF
- **WHEN** simulator receives packet
- **THEN** simulator SHALL log warning "Invalid checksum: expected 0x7F, got 0xFF"
- **AND** ignore command (no response)
- **OR** optionally send error response

### Requirement: Configurable Latency

The simulator SHALL introduce configurable artificial delays to simulate real hardware response time.

#### Scenario: Add 100ms response latency
- **GIVEN** config has `simulator.response_latency_ms=100`
- **WHEN** simulator receives any command
- **THEN** simulator SHALL sleep 100ms before responding
- **AND** mimic real hardware timing

#### Scenario: Variable latency
- **GIVEN** config has `simulator.response_latency_range_ms=[50, 200]`
- **WHEN** multiple commands received
- **THEN** each response SHALL have random delay between 50-200ms

### Requirement: Error Injection

The simulator SHALL support configurable error scenarios for testing error handling code.

#### Scenario: Inject timeout error
- **GIVEN** config has `simulator.inject_timeout=true`
- **WHEN** simulator receives FG command
- **THEN** simulator SHALL NOT respond
- **AND** client times out after 5 seconds

#### Scenario: Inject checksum error
- **GIVEN** config has `simulator.inject_checksum_error_rate=0.1` (10%)
- **WHEN** simulator sends responses
- **THEN** 10% of packets SHALL have corrupted checksum
- **AND** client detects and handles error

#### Scenario: Inject random disconnects
- **GIVEN** config has `simulator.inject_disconnect_after_commands=50`
- **WHEN** 50 commands processed
- **THEN** simulator SHALL simulate serial port closure
- **AND** raise `ConnectionLostError` on next command

### Requirement: Movement Status Characters

During simulated movement, the simulator SHALL send 'I'/'O' characters at realistic intervals and 'F' upon completion.

#### Scenario: Send 'O' characters during outward move
- **GIVEN** simulating move from 1000 to 1100 (100 steps)
- **AND** movement speed 500 steps/sec
- **WHEN** movement in progress
- **THEN** simulator SHALL send 100 'O' characters over 0.2 seconds
- **AND** send one 'O' approximately every 2ms

#### Scenario: Send 'I' characters during inward move
- **GIVEN** simulating move from 1000 to 900 (100 steps)
- **WHEN** movement in progress
- **THEN** simulator SHALL send 100 'I' characters

#### Scenario: Send 'F' + final position on completion
- **GIVEN** movement to 5000 is completing
- **WHEN** target reached
- **THEN** simulator SHALL send 'F' (0x46)
- **FOLLOWED BY** `D005000` + checksum (8 bytes)
- **TOTAL**: 9 bytes starting with 'F'

### Requirement: Concurrent Access Handling

The simulator SHALL be thread-safe, handling concurrent command attempts gracefully.

#### Scenario: Concurrent position queries
- **GIVEN** 10 threads simultaneously query position
- **WHEN** all threads call send_command("FG000000")
- **THEN** simulator SHALL process all requests
- **AND** return consistent position to all
- **AND** no race conditions or crashes

### Requirement: State Inspection

The simulator SHALL expose internal state for testing assertions (position, is_moving, switch states, config).

#### Scenario: Inspect virtual position
- **GIVEN** test code using simulator
- **WHEN** test calls `simulator.get_position()`
- **THEN** SHALL return current virtual position (e.g., 12345)
- **AND** without sending serial command

#### Scenario: Inspect movement status
- **GIVEN** simulator is moving
- **WHEN** test calls `simulator.is_moving()`
- **THEN** SHALL return True
- **AND** allow synchronous testing without waiting

### Requirement: Reset to Default State

The simulator SHALL provide a reset method to return to initial conditions between tests.

#### Scenario: Reset between tests
- **GIVEN** simulator has been used in previous test (position 50000, switches toggled)
- **WHEN** test calls `simulator.reset()`
- **THEN** simulator SHALL reset to:
  - Position: 0 (or configured initial_position)
  - Is moving: False
  - Switches: all off
  - Backlash: disabled
  - Limits: default max_step

### Requirement: Logging

The simulator SHALL log all received commands and sent responses at DEBUG level for troubleshooting.

#### Scenario: Debug log of command
- **GIVEN** logging level is DEBUG
- **WHEN** simulator receives `FG010000` + checksum
- **THEN** log SHALL contain: `[SIMULATOR] RX: FG010000 (checksum OK)`
- **AND** `[SIMULATOR] TX: FD010000 + checksum`

#### Scenario: Info log of movement
- **GIVEN** logging level is INFO
- **WHEN** simulator starts movement
- **THEN** log SHALL contain: `[SIMULATOR] Moving: 5000 -> 10000 (5000 steps, 10.0 sec)`

### Requirement: Configuration Validation

The simulator SHALL validate configuration parameters at initialization and reject invalid values.

#### Scenario: Invalid movement speed
- **GIVEN** config has `simulator.movement_speed_steps_per_sec=-100` (negative)
- **WHEN** simulator initializes
- **THEN** SHALL raise `ConfigurationError`
- **AND** message "Movement speed must be positive, got -100"

#### Scenario: Invalid initial position
- **GIVEN** config has `simulator.initial_position=100000`
- **AND** `simulator.max_step=60000`
- **WHEN** simulator initializes
- **THEN** SHALL raise `ConfigurationError`
- **AND** message "Initial position 100000 exceeds max_step 60000"

### Requirement: Performance Testing Support

The simulator SHALL support high-frequency command rates for stress testing (>100 commands/sec).

#### Scenario: Handle 1000 position queries/sec
- **GIVEN** simulator with minimal latency (1ms)
- **WHEN** test sends 1000 FG queries in rapid succession
- **THEN** simulator SHALL process all without crashing
- **AND** maintain consistent state
- **AND** complete within reasonable time (< 5 seconds total)

### Requirement: Simulator-Specific Error Codes

When error injection is active, the simulator SHALL use distinct error messages to distinguish real errors from injected errors.

#### Scenario: Injected timeout vs real timeout
- **GIVEN** simulator injects timeout
- **WHEN** timeout occurs
- **THEN** log SHALL contain `[SIMULATOR] Injected timeout for testing`
- **AND** client code treats it as normal timeout
- **BUT** developer knows it's simulated

### Requirement: Documentation of Limitations

The simulator SHALL document behaviors that differ from real hardware (e.g., perfect checksums, no electrical noise).

#### Scenario: No electromagnetic interference
- **GIVEN** real hardware may have EMI causing bit flips
- **WHEN** simulator is used
- **THEN** simulator SHALL NOT simulate bit errors (unless error injection enabled)
- **AND** documentation SHALL note "Simulator does not model EMI or bit errors"

#### Scenario: Instant command processing
- **GIVEN** real hardware has firmware processing time
- **WHEN** simulator processes command
- **THEN** simulator MAY respond faster than real hardware
- **AND** documentation SHALL note "Add response_latency_ms for realistic timing"

### Requirement: Web GUI Control Panel

The simulator SHALL provide a web-based graphical user interface for manual control and monitoring, accessible via HTTP on a configurable port.

#### Scenario: Enable web GUI via configuration
- **GIVEN** config has `simulator.web_gui.enabled=true` and `simulator.web_gui.port=8080`
- **WHEN** simulator starts
- **THEN** web server SHALL start on port 8080
- **AND** log message "Simulator Web GUI available at http://localhost:8080"

#### Scenario: Disable web GUI
- **GIVEN** config has `simulator.web_gui.enabled=false`
- **WHEN** simulator starts
- **THEN** no web server SHALL be created
- **AND** log message "Simulator Web GUI disabled"

#### Scenario: Access control panel in browser
- **GIVEN** web GUI is enabled on port 8080
- **WHEN** user opens browser to `http://localhost:8080`
- **THEN** browser SHALL display simulator control panel HTML page
- **AND** page SHALL load without errors

### Requirement: Position Display

The web GUI SHALL display the current virtual position in real-time, updating automatically during movement.

#### Scenario: Display current position
- **GIVEN** simulator is at position 12345
- **WHEN** user opens web GUI
- **THEN** page SHALL display "Current Position: 12345"

#### Scenario: Position updates during movement
- **GIVEN** simulator is moving from 10000 to 20000
- **AND** web GUI is open
- **WHEN** position changes to 15000
- **THEN** displayed position SHALL update to "Current Position: 15000"
- **AND** update SHALL occur within 500ms

#### Scenario: Display movement indicator
- **GIVEN** simulator is moving
- **WHEN** web GUI refreshes
- **THEN** page SHALL show visual indicator "Status: MOVING"
- **AND** indicator SHALL be prominent (e.g., colored badge, animation)

#### Scenario: Display idle status
- **GIVEN** simulator is stationary
- **WHEN** web GUI refreshes
- **THEN** page SHALL show "Status: IDLE"

### Requirement: Manual Step Control Buttons

The web GUI SHALL provide buttons to manually increment or decrement the focuser position by fixed amounts (±1 step, ±10 steps).

#### Scenario: Move +1 step
- **GIVEN** simulator is at position 5000
- **AND** web GUI is open
- **WHEN** user clicks "+1 Step" button
- **THEN** simulator SHALL move to position 5001
- **AND** displayed position SHALL update to 5001

#### Scenario: Move -1 step
- **GIVEN** simulator is at position 5000
- **WHEN** user clicks "-1 Step" button
- **THEN** simulator SHALL move to position 4999
- **AND** displayed position SHALL update to 4999

#### Scenario: Move +10 steps
- **GIVEN** simulator is at position 5000
- **WHEN** user clicks "+10 Steps" button
- **THEN** simulator SHALL move to position 5010
- **AND** movement SHALL be simulated (not instant)
- **AND** position SHALL update incrementally (5001, 5002, ..., 5010)

#### Scenario: Move -10 steps
- **GIVEN** simulator is at position 5000
- **WHEN** user clicks "-10 Steps" button
- **THEN** simulator SHALL move to position 4990

#### Scenario: Button disabled during movement
- **GIVEN** simulator is currently moving
- **WHEN** web GUI refreshes
- **THEN** all step control buttons SHALL be disabled
- **AND** buttons SHALL have visual indication (grayed out, cursor not-allowed)

#### Scenario: Buttons respect limits
- **GIVEN** simulator is at position 0 (minimum)
- **WHEN** user clicks "-1 Step" button
- **THEN** simulator SHALL NOT move below 0
- **AND** log warning "Cannot move below minimum position"
- **AND** web GUI SHALL display error message "Already at minimum position"

### Requirement: Custom Step Input

The web GUI SHALL provide an input field and buttons to move the focuser by a user-specified number of steps in either direction.

#### Scenario: Move +N steps
- **GIVEN** simulator is at position 5000
- **AND** user enters "250" in custom step input field
- **WHEN** user clicks "+N Steps" button
- **THEN** simulator SHALL move to position 5250
- **AND** movement SHALL be simulated with realistic timing

#### Scenario: Move -N steps
- **GIVEN** simulator is at position 5000
- **AND** user enters "150" in custom step input field
- **WHEN** user clicks "-N Steps" button
- **THEN** simulator SHALL move to position 4850

#### Scenario: Invalid input handling
- **GIVEN** user enters "abc" (non-numeric) in input field
- **WHEN** user clicks "+N Steps" button
- **THEN** web GUI SHALL display error message "Invalid input: must be a positive integer"
- **AND** no movement SHALL occur

#### Scenario: Negative input handling
- **GIVEN** user enters "-50" in input field
- **WHEN** user clicks "+N Steps" button
- **THEN** web GUI SHALL display error message "Step count must be positive (use -N button for negative movement)"
- **AND** no movement SHALL occur

#### Scenario: Zero step input
- **GIVEN** user enters "0" in input field
- **WHEN** user clicks "+N Steps" button
- **THEN** web GUI SHALL display info message "Zero steps: no movement"
- **AND** no command sent to simulator

#### Scenario: Large step input clamped
- **GIVEN** simulator is at position 5000
- **AND** max_step is 60000
- **AND** user enters "70000" in input field
- **WHEN** user clicks "+N Steps" button
- **THEN** simulator SHALL clamp to max position 60000
- **AND** web GUI SHALL display warning "Clamped to maximum: moving to 60000"

### Requirement: Temperature Display

The web GUI SHALL display the current simulated temperature in degrees Celsius, updating periodically.

#### Scenario: Display temperature
- **GIVEN** simulator temperature is 16.85°C
- **WHEN** user opens web GUI
- **THEN** page SHALL display "Temperature: 16.85°C"

#### Scenario: Temperature updates with noise
- **GIVEN** simulator has temperature noise enabled
- **AND** web GUI is open
- **WHEN** temperature refreshes multiple times
- **THEN** displayed values SHALL vary (e.g., 16.3°C, 16.9°C, 16.6°C)

#### Scenario: Temperature with drift
- **GIVEN** simulator has temperature drift enabled (2°C/hour)
- **AND** simulator started 30 minutes ago at 16°C
- **WHEN** web GUI displays temperature
- **THEN** page SHALL show approximately "Temperature: 17.0°C"

### Requirement: Halt Button

The web GUI SHALL provide a prominent halt/stop button to immediately stop any ongoing movement.

#### Scenario: Halt during movement
- **GIVEN** simulator is moving from 10000 to 50000
- **AND** current position is 25000
- **AND** web GUI is open
- **WHEN** user clicks "HALT" button
- **THEN** simulator SHALL stop immediately
- **AND** position SHALL remain at approximately 25000
- **AND** status SHALL change to "IDLE"

#### Scenario: Halt button always enabled
- **GIVEN** web GUI is open
- **WHEN** simulator is idle OR moving
- **THEN** HALT button SHALL always be enabled (not disabled)

#### Scenario: Visual distinction of halt button
- **GIVEN** web GUI is rendered
- **THEN** HALT button SHALL have distinctive styling (e.g., red color, larger size)
- **AND** button text SHALL be clear: "HALT" or "EMERGENCY STOP"

### Requirement: Absolute Position GoTo

The web GUI SHALL provide an input field and button to move the focuser to an absolute position.

#### Scenario: GoTo absolute position
- **GIVEN** simulator is at position 5000
- **AND** user enters "30000" in GoTo input field
- **WHEN** user clicks "GoTo" button
- **THEN** simulator SHALL move to position 30000
- **AND** movement SHALL be simulated with realistic timing

#### Scenario: GoTo current position (no-op)
- **GIVEN** simulator is at position 10000
- **AND** user enters "10000" in GoTo field
- **WHEN** user clicks "GoTo" button
- **THEN** web GUI SHALL display info message "Already at target position"
- **AND** no movement SHALL occur

#### Scenario: GoTo out of range position
- **GIVEN** max_step is 60000
- **AND** user enters "80000" in GoTo field
- **WHEN** user clicks "GoTo" button
- **THEN** web GUI SHALL display error "Position 80000 exceeds maximum 60000"
- **AND** no movement SHALL occur

### Requirement: Configuration Display

The web GUI SHALL display current simulator configuration parameters (speed, limits, firmware version).

#### Scenario: Display configuration summary
- **GIVEN** simulator is configured with:
  - movement_speed: 500 steps/sec
  - max_step: 60000
  - firmware_version: 2.1.0
- **WHEN** user opens web GUI
- **THEN** page SHALL display configuration section:
  ```
  Configuration:
  - Movement Speed: 500 steps/sec
  - Max Position: 60000
  - Firmware Version: 2.1.0
  ```

### Requirement: Real-time Updates via Polling

The web GUI SHALL automatically refresh position and status data by polling the simulator at regular intervals (e.g., 250ms) using JavaScript.

#### Scenario: Polling updates position
- **GIVEN** web GUI is open
- **AND** polling interval is 250ms
- **WHEN** simulator position changes
- **THEN** within 250ms, displayed position SHALL update
- **AND** polling SHALL use AJAX request to REST endpoint (e.g., `/simulator/status`)

#### Scenario: Polling status endpoint
- **GIVEN** web GUI JavaScript makes request to `/simulator/status`
- **WHEN** request completes
- **THEN** response SHALL be JSON:
  ```json
  {
    "position": 12345,
    "target_position": 20000,
    "is_moving": true,
    "temperature": 16.85,
    "firmware_version": "2.1.0",
    "max_step": 60000
  }
  ```

#### Scenario: Stop polling when page hidden
- **GIVEN** web GUI is open and polling
- **WHEN** user switches to another browser tab
- **THEN** polling MAY pause (to reduce CPU usage)
- **AND** polling SHALL resume when tab becomes active again

### Requirement: Error Feedback

The web GUI SHALL display user-friendly error messages for failed operations (invalid input, hardware errors).

#### Scenario: Display error message
- **GIVEN** user attempts invalid operation (e.g., move below 0)
- **WHEN** error occurs
- **THEN** web GUI SHALL show error message in dedicated error box
- **AND** error SHALL be styled prominently (red background, icon)
- **AND** error SHALL auto-dismiss after 5 seconds OR user closes manually

#### Scenario: Clear previous errors on new action
- **GIVEN** an error message is currently displayed
- **WHEN** user performs a new valid action
- **THEN** previous error SHALL be cleared
- **AND** new action proceeds normally

### Requirement: Responsive Layout

The web GUI SHALL use responsive CSS to ensure usability on different screen sizes (desktop, tablet).

#### Scenario: Desktop layout
- **GIVEN** browser window width is 1920px
- **WHEN** web GUI is rendered
- **THEN** controls SHALL be laid out horizontally with ample spacing

#### Scenario: Tablet layout
- **GIVEN** browser window width is 768px
- **WHEN** web GUI is rendered
- **THEN** controls SHALL reflow to vertical stacked layout
- **AND** buttons SHALL remain touch-friendly (minimum 44x44px)

### Requirement: No External Dependencies (Embedded Assets)

The web GUI SHALL use embedded HTML/CSS/JavaScript without requiring external CDN resources, ensuring functionality without internet connection.

#### Scenario: Offline operation
- **GIVEN** computer has no internet connection
- **WHEN** user opens web GUI at `http://localhost:8080`
- **THEN** page SHALL load completely with all styling and interactivity
- **AND** no broken resources or console errors

#### Scenario: Self-contained assets
- **GIVEN** web GUI uses CSS framework (e.g., minimal embedded styles)
- **THEN** all CSS and JavaScript SHALL be embedded in HTML file OR served from local filesystem
- **AND** no requests to external domains (cdn.js, fonts.googleapis.com, etc.)

### Requirement: Logging of Web GUI Actions

All actions performed via the web GUI SHALL be logged at INFO level for debugging and audit purposes.

#### Scenario: Log button click
- **GIVEN** web GUI is open
- **WHEN** user clicks "+10 Steps" button
- **THEN** log SHALL contain:
  ```
  [2026-01-12 15:30:45] INFO: [Web GUI] User action: +10 steps (from 5000 to 5010)
  ```

#### Scenario: Log GoTo action
- **GIVEN** user enters 30000 in GoTo field and clicks button
- **THEN** log SHALL contain:
  ```
  [2026-01-12 15:31:10] INFO: [Web GUI] User action: GoTo position 30000 (current: 5000)
  ```

#### Scenario: Log halt action
- **GIVEN** user clicks HALT during movement
- **THEN** log SHALL contain:
  ```
  [2026-01-12 15:32:00] INFO: [Web GUI] User action: HALT (stopped at position 25123)
  ```

### Requirement: Web Server Technology

The web GUI SHALL be served using the same FastAPI application instance that hosts the Alpaca API, on a separate port or path prefix (e.g., `/simulator/gui`).

#### Scenario: Serve GUI on separate port
- **GIVEN** config has `simulator.web_gui.port=8080` and Alpaca API on port 5000
- **WHEN** simulator starts
- **THEN** FastAPI SHALL run two servers:
  - Port 5000: Alpaca API
  - Port 8080: Web GUI (static HTML + REST endpoints for simulator control)

#### Scenario: Serve GUI on path prefix (alternative)
- **GIVEN** config has `simulator.web_gui.use_path_prefix=true`
- **WHEN** simulator starts
- **THEN** web GUI SHALL be accessible at `http://localhost:5000/simulator/gui`
- **AND** Alpaca API remains at `http://localhost:5000/api/v1/focuser/0/`
- **AND** simulator status API at `http://localhost:5000/simulator/status`

### Requirement: Concurrent Access

The web GUI SHALL support multiple concurrent browser connections without data corruption or race conditions.

#### Scenario: Two users control simultaneously
- **GIVEN** User A and User B both have web GUI open
- **WHEN** User A clicks "+10 Steps"
- **AND** simultaneously User B clicks "+5 Steps"
- **THEN** both commands SHALL be processed sequentially (serial lock)
- **AND** final position SHALL be consistent (e.g., 5000 + 10 + 5 = 5015)
- **AND** both browsers SHALL update to show same final position

#### Scenario: Position display synchronized
- **GIVEN** three browser windows open with web GUI
- **WHEN** simulator moves via any interface (GUI, API, or serial command)
- **THEN** all three browser windows SHALL display same position
- **AND** updates SHALL occur within polling interval (250ms)

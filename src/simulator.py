"""
Focuser simulator for ESP32.

Simulates Robofocus hardware without requiring physical device.
Uses _thread for background movement on ESP32's second core.
"""

import time
import random
import _thread


class FocuserSimulator:
    """
    Simulated focuser using background thread for movement.

    ESP32 dual-core: Thread runs on Core 1, WiFi on Core 0.
    Movement updates independently of HTTP request handling.
    """

    # Movement speed (steps per second)
    MOVEMENT_SPEED = 500

    # Temperature simulation
    BASE_TEMPERATURE = 18.0  # Celsius
    TEMP_NOISE = 0.5  # +/- noise range

    def __init__(self):
        self._connected = False
        self._position = 30000  # Start at mid-range
        self._target_position = 30000
        self._is_moving = False
        self._firmware_version = "2.0"

        # Movement timing
        self._last_move_time = 0
        self._move_direction = 0  # -1=in, 0=stopped, 1=out

        # Temperature
        self._start_time = time.time()

        # Thread control
        self._thread_running = False
        self._lock = _thread.allocate_lock()

        print("[simulator] Initialized (threaded)")

    def _movement_thread(self):
        """Background thread for movement updates."""
        print("[simulator] Movement thread started")
        while self._thread_running:
            if self._is_moving:
                self._tick()
            time.sleep(0.05)  # 50ms tick rate
        print("[simulator] Movement thread stopped")

    def connect(self) -> bool:
        """Connect to simulator and start movement thread."""
        if self._connected:
            print("[simulator] Already connected")
            return True

        self._connected = True

        # Start background movement thread
        if not self._thread_running:
            self._thread_running = True
            _thread.start_new_thread(self._movement_thread, ())

        print(f"[simulator] Connected (firmware: {self._firmware_version})")
        return True

    def disconnect(self):
        """Disconnect and stop movement thread."""
        if self._is_moving:
            self.halt()

        # Stop thread
        self._thread_running = False
        time.sleep(0.1)  # Wait for thread to stop

        self._connected = False
        print("[simulator] Disconnected")

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    @property
    def firmware_version(self) -> str:
        """Get firmware version."""
        return self._firmware_version if self._connected else None

    def get_position(self) -> int:
        """Get current position (thread-safe)."""
        if not self._connected:
            return 0
        with self._lock:
            return self._position

    def is_moving(self) -> bool:
        """Check if moving (thread-safe)."""
        if not self._connected:
            return False
        with self._lock:
            return self._is_moving

    def move_absolute(self, target: int) -> bool:
        """
        Start movement to absolute position (thread-safe).

        Args:
            target: Target position (0-65535)

        Returns:
            True if movement started.
        """
        if not self._connected:
            return False

        # Clamp target
        target = max(0, min(65535, target))

        with self._lock:
            if target == self._position:
                return True

            self._target_position = target
            self._is_moving = True
            self._move_direction = 1 if target > self._position else -1
            self._last_move_time = time.time()
            print(f"[simulator] Move: {self._position} -> {target}")

        return True

    def halt(self) -> bool:
        """Stop movement immediately (thread-safe)."""
        if not self._connected:
            return False

        with self._lock:
            if self._is_moving:
                print(f"[simulator] Halt at {self._position}")
                self._is_moving = False
                self._move_direction = 0
                self._target_position = self._position

        return True

    def get_temperature(self) -> float:
        """
        Get simulated temperature.

        Returns:
            Temperature in Celsius with slight noise.
        """
        if not self._connected:
            return None

        # Add random noise
        noise = random.uniform(-self.TEMP_NOISE, self.TEMP_NOISE)

        # Small drift over time (0.1 deg per hour)
        elapsed_hours = (time.time() - self._start_time) / 3600.0
        drift = elapsed_hours * 0.1

        return self.BASE_TEMPERATURE + noise + drift

    def _tick(self):
        """
        Update movement state (called by background thread).
        Thread-safe with lock.
        """
        with self._lock:
            if not self._is_moving:
                return

            now = time.time()
            elapsed = now - self._last_move_time

            if elapsed < 0.05:  # 50ms minimum tick
                return

            # Calculate steps to move
            steps = int(elapsed * self.MOVEMENT_SPEED)
            if steps < 1:
                return

            self._last_move_time = now

            # Move towards target
            if self._move_direction > 0:
                self._position = min(self._position + steps, self._target_position)
            else:
                self._position = max(self._position - steps, self._target_position)

            # Check if reached target
            if self._position == self._target_position:
                self._is_moving = False
                self._move_direction = 0
                print(f"[simulator] Reached {self._position}")

    def sync_position(self, value: int):
        """Set position counter to specific value (thread-safe)."""
        if not self._connected:
            return

        with self._lock:
            old_pos = self._position
            self._position = max(0, min(65535, value))
            self._target_position = self._position
            print(f"[simulator] Sync: {old_pos} -> {self._position}")


# Global simulator instance
simulator = FocuserSimulator()

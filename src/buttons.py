from machine import Pin
import time

_PIN_LEFT   = 0   # IO0 BOOT — move in
_PIN_CENTER = 47  # IO47     — short: cycle step / long: halt
_PIN_RIGHT  = 48  # IO48     — move out

_STEPS = (1, 5, 10, 20, 50)
_DEBOUNCE_MS  = 50
_LONG_PRESS_MS = 600


class ButtonManager:

    def __init__(self):
        self._step_idx = 0
        self.step = _STEPS[0]

        # left/right: False = no event, True = pressed
        # center: None = no event, 'step' = short press, 'halt' = long press
        self._flags = [False, None, False]
        self._last_ms = [0, 0, 0]
        self._center_press_time = 0

        self._pins = [
            Pin(_PIN_LEFT,   Pin.IN, Pin.PULL_UP),
            Pin(_PIN_CENTER, Pin.IN, Pin.PULL_UP),
            Pin(_PIN_RIGHT,  Pin.IN, Pin.PULL_UP),
        ]
        self._pins[0].irq(trigger=Pin.IRQ_FALLING, handler=self._isr_left)
        self._pins[1].irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=self._isr_center)
        self._pins[2].irq(trigger=Pin.IRQ_FALLING, handler=self._isr_right)

    def _debounce(self, idx):
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_ms[idx]) < _DEBOUNCE_MS:
            return False
        self._last_ms[idx] = now
        return True

    def _isr_left(self, pin):
        if self._debounce(0):
            self._flags[0] = True

    def _isr_center(self, pin):
        now = time.ticks_ms()
        if pin.value() == 0:  # falling — button pressed
            if time.ticks_diff(now, self._last_ms[1]) >= _DEBOUNCE_MS:
                self._last_ms[1] = now
                self._center_press_time = now
        else:  # rising — button released
            if self._center_press_time > 0:
                elapsed = time.ticks_diff(now, self._center_press_time)
                self._center_press_time = 0
                if elapsed >= _LONG_PRESS_MS:
                    self._flags[1] = 'halt'
                else:
                    self._flags[1] = 'step'

    def _isr_right(self, pin):
        if self._debounce(2):
            self._flags[2] = True

    def process(self):
        """Drain pending button events. Returns list of (action, step) tuples."""
        events = []
        if self._flags[0]:
            self._flags[0] = False
            events.append(('move_in', self.step))
        if self._flags[1] is not None:
            action = self._flags[1]
            self._flags[1] = None
            if action == 'halt':
                events.append(('halt', self.step))
            else:
                self._step_idx = (self._step_idx + 1) % len(_STEPS)
                self.step = _STEPS[self._step_idx]
                events.append(('step_changed', self.step))
        if self._flags[2]:
            self._flags[2] = False
            events.append(('move_out', self.step))
        return events


buttons = ButtonManager()

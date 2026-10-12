"""Pomodoro-style study/break timer."""
from __future__ import annotations

import math
import time
from typing import Dict

from PySide6.QtCore import QObject, QTimer, Signal

FOCUS = "focus"
SHORT_BREAK = "short_break"
LONG_BREAK = "long_break"

PHASE_LABELS = {
    FOCUS: "Focus",
    SHORT_BREAK: "Short break",
    LONG_BREAK: "Long break",
}


class PomodoroTimer(QObject):
    ticked = Signal(int, int)            # remaining_sec, total_sec
    progressed = Signal(str, float)      # phase, seconds elapsed since last tick
    phase_changed = Signal(str)
    running_changed = Signal(bool)
    phase_completed = Signal(str)        # phase that just ran to zero

    def __init__(self, settings: Dict, parent=None):
        super().__init__(parent)
        self._settings = dict(settings)
        self.phase = FOCUS
        self.completed_focus = 0
        self.total = self.duration_for(FOCUS)
        self.remaining = float(self.total)
        self.running = False
        self._last = 0.0
        self._qtimer = QTimer(self)
        self._qtimer.setInterval(200)
        self._qtimer.timeout.connect(self._on_tick)

    # ----------------------------------------------------------------- config
    def duration_for(self, phase: str) -> int:
        key = {FOCUS: "focus_min", SHORT_BREAK: "short_break_min",
               LONG_BREAK: "long_break_min"}[phase]
        return int(self._settings[key]) * 60

    def configure(self, settings: Dict) -> None:
        self._settings = dict(settings)
        # only re-arm the clock if the current phase hasn't been started yet
        if not self.running and self.remaining >= self.total:
            self.total = self.duration_for(self.phase)
            self.remaining = float(self.total)
            self._emit_tick()

    @property
    def long_every(self) -> int:
        return max(1, int(self._settings["long_every"]))

    # --------------------------------------------------------------- controls
    def start(self) -> None:
        if self.running:
            return
        self._last = time.monotonic()
        self._qtimer.start()
        self.running = True
        self.running_changed.emit(True)

    def pause(self) -> None:
        if not self.running:
            return
        self._on_tick(check_done=False)   # bank the time since the last tick
        self._qtimer.stop()
        self.running = False
        self.running_changed.emit(False)

    def toggle(self) -> None:
        self.pause() if self.running else self.start()

    def reset(self) -> None:
        self.pause()
        self.remaining = float(self.total)
        self._emit_tick()

    def skip(self) -> None:
        self._advance(natural=False)

    def set_phase(self, phase: str) -> None:
        self.pause()
        self.phase = phase
        self.total = self.duration_for(phase)
        self.remaining = float(self.total)
        self.phase_changed.emit(phase)
        self._emit_tick()

    # --------------------------------------------------------------- internals
    def _on_tick(self, check_done: bool = True) -> None:
        if not self.running:
            return
        now = time.monotonic()
        dt = min(now - self._last, self.remaining)
        self._last = now
        self.remaining -= dt
        self.progressed.emit(self.phase, dt)
        self._emit_tick()
        if check_done and self.remaining <= 0.05:
            self.phase_completed.emit(self.phase)
            self._advance(natural=True)

    def _advance(self, natural: bool) -> None:
        finished = self.phase
        if finished == FOCUS:
            if natural:
                self.completed_focus += 1
            if natural and self.completed_focus % self.long_every == 0:
                nxt = LONG_BREAK
            else:
                nxt = SHORT_BREAK
        else:
            nxt = FOCUS
        self.set_phase(nxt)
        if natural and self._settings.get("auto_start_next"):
            self.start()

    def _emit_tick(self) -> None:
        self.ticked.emit(int(math.ceil(max(0.0, self.remaining))), self.total)

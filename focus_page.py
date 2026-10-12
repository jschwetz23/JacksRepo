"""Focus page: pomodoro timer + live camera attention tracking."""
from __future__ import annotations

import sys
import time
from datetime import date, datetime, timedelta
from typing import Dict, Optional

from PySide6.QtCore import Qt, QProcess, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QApplication, QButtonGroup, QComboBox, QHBoxLayout, QLabel,
                               QProgressBar, QPushButton, QSizePolicy, QVBoxLayout, QWidget)

from .. import focus as fx
from ..db import Database
from ..timer import FOCUS, LONG_BREAK, PHASE_LABELS, SHORT_BREAK, PomodoroTimer
from . import theme
from .widgets import Card, LineChart, ProgressRing, fmt_clock, fmt_duration, label, set_chip

PHASE_COLORS = {FOCUS: theme.ACCENT, SHORT_BREAK: theme.BREAK, LONG_BREAK: theme.SUCCESS}
STATE_COLORS = {fx.FOCUSED: theme.SUCCESS, fx.DISTRACTED: theme.WARNING,
                fx.AWAY: theme.DANGER, fx.OFF: theme.FAINT}
LIVE_BUCKET_SEC = 5
MIN_SESSION_SEC = 60


def play_sound(name: str = "Glass") -> None:
    if sys.platform == "darwin":
        QProcess.startDetached("afplay", [f"/System/Library/Sounds/{name}.aiff"])
    else:
        QApplication.beep()


class FocusPage(QWidget):
    session_saved = Signal()

    def __init__(self, db: Database, settings: Dict, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        self.db = db
        self.settings = dict(settings)
        self.timer = PomodoroTimer(self.settings, self)
        self.camera: Optional[fx.CameraWorker] = None
        self.cam_state = fx.OFF

        self._session: Optional[Dict] = None
        self._completed_naturally = False
        self._bucket = [0.0, 0.0]               # camera seconds, focused seconds
        self._not_focused_since: Optional[float] = None
        self._away_since: Optional[float] = None
        self._alerted = False

        self._build()
        self._wire()
        self.refresh_tasks()
        self._on_phase_changed(self.timer.phase)
        self._update_today()

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(18)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(label("Focus", "h1"))
        titles.addWidget(label(datetime.now().strftime("%A, %B %-d" if sys.platform != "win32"
                                                       else "%A, %B %d"), "muted"))
        header.addLayout(titles)
        header.addStretch()
        task_box = QVBoxLayout()
        task_box.setSpacing(4)
        task_box.addWidget(label("STUDYING", "faint"))
        self.task_combo = QComboBox()
        self.task_combo.setMinimumWidth(320)
        task_box.addWidget(self.task_combo)
        header.addLayout(task_box)
        root.addLayout(header)

        self.banner = label("", "banner", wrap=True)
        self.banner.hide()
        root.addWidget(self.banner)

        content = QHBoxLayout()
        content.setSpacing(18)
        root.addLayout(content, 1)

        # ---- timer card
        timer_card = Card()
        timer_card.body.setSpacing(16)
        pills = QHBoxLayout()
        pills.addStretch()
        self.phase_group = QButtonGroup(self)
        self.phase_group.setExclusive(True)
        self.phase_buttons = {}
        for phase in (FOCUS, SHORT_BREAK, LONG_BREAK):
            b = QPushButton(PHASE_LABELS[phase])
            b.setObjectName("pill")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            self.phase_group.addButton(b)
            self.phase_buttons[phase] = b
            pills.addWidget(b)
        pills.addStretch()
        timer_card.body.addLayout(pills)

        self.ring = ProgressRing()
        timer_card.body.addWidget(self.ring, 1)

        controls = QHBoxLayout()
        controls.setSpacing(18)
        controls.addStretch()
        self.reset_btn = QPushButton("↺")
        self.reset_btn.setProperty("variant", "round")
        self.reset_btn.setToolTip("Reset this block")
        self.play_btn = QPushButton("Start")
        self.play_btn.setProperty("variant", "play")
        self.skip_btn = QPushButton("⏭")
        self.skip_btn.setProperty("variant", "round")
        self.skip_btn.setToolTip("Skip to the next block")
        for b in (self.reset_btn, self.play_btn, self.skip_btn):
            b.setCursor(Qt.PointingHandCursor)
            controls.addWidget(b)
        controls.addStretch()
        timer_card.body.addLayout(controls)

        today_row = QHBoxLayout()
        self.today_label = label("", "muted")
        today_row.addWidget(self.today_label)
        today_row.addStretch()
        self.goal_label = label("", "faint")
        today_row.addWidget(self.goal_label)
        timer_card.body.addLayout(today_row)
        self.goal_bar = QProgressBar()
        self.goal_bar.setTextVisible(False)
        timer_card.body.addWidget(self.goal_bar)

        content.addWidget(timer_card, 3)

        # ---- right column
        right = QVBoxLayout()
        right.setSpacing(18)
        content.addLayout(right, 2)

        cam_card = Card()
        cam_head = QHBoxLayout()
        cam_head.addWidget(label("Attention tracking", "h2"))
        cam_head.addStretch()
        self.state_chip = QLabel()
        cam_head.addWidget(self.state_chip)
        cam_card.body.addLayout(cam_head)

        self.preview = label("Camera is off\n\nTurn it on to measure your active study rate",
                             "cameraView", wrap=True)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(300, 210)
        self.preview.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        cam_card.body.addWidget(self.preview, 1)

        cam_foot = QHBoxLayout()
        cam_foot.addWidget(label("Processed locally · nothing is recorded", "faint"))
        cam_foot.addStretch()
        self.cam_btn = QPushButton("Turn on camera")
        self.cam_btn.setCursor(Qt.PointingHandCursor)
        cam_foot.addWidget(self.cam_btn)
        cam_card.body.addLayout(cam_foot)
        right.addWidget(cam_card, 3)

        rate_card = Card()
        rate_card.body.setSpacing(6)
        rate_head = QHBoxLayout()
        rate_head.addWidget(label("Active study rate", "h2"))
        rate_head.addStretch()
        rate_head.addWidget(label("THIS SESSION", "faint"))
        rate_card.body.addLayout(rate_head)
        rate_row = QHBoxLayout()
        self.rate_value = label("—", "bigPercent")
        rate_row.addWidget(self.rate_value)
        rate_row.addSpacing(12)
        self.rate_detail = label("Start a focus block with the camera on", "muted", wrap=True)
        rate_row.addWidget(self.rate_detail, 1)
        rate_card.body.addLayout(rate_row)
        self.live_chart = LineChart(theme.SUCCESS, show_axis=False,
                                    empty_text="Live focus graph appears here")
        self.live_chart.max_points = 60
        self.live_chart.setMinimumHeight(90)
        rate_card.body.addWidget(self.live_chart, 1)
        right.addWidget(rate_card, 2)

        self._set_cam_state(fx.OFF)

    def _wire(self) -> None:
        self.play_btn.clicked.connect(self.timer.toggle)
        self.reset_btn.clicked.connect(self._reset)
        self.skip_btn.clicked.connect(self.timer.skip)
        self.cam_btn.clicked.connect(self.toggle_camera)
        for phase, btn in self.phase_buttons.items():
            btn.clicked.connect(lambda _=False, p=phase: self._pick_phase(p))
        self.task_combo.currentIndexChanged.connect(self._on_task_changed)

        self.timer.ticked.connect(self._on_tick)
        self.timer.progressed.connect(self._on_progress)
        self.timer.phase_changed.connect(self._on_phase_changed)
        self.timer.phase_completed.connect(self._on_phase_completed)
        self.timer.running_changed.connect(self._on_running_changed)

    # ------------------------------------------------------------- public API
    def refresh_tasks(self) -> None:
        current = self.current_task_id()
        self.task_combo.blockSignals(True)
        self.task_combo.clear()
        self.task_combo.addItem("General study (no specific item)", None)
        for t in self.db.tasks(include_done=False):
            due = date.fromisoformat(t["due_date"])
            subject = f" · {t['subject']}" if t["subject"] else ""
            self.task_combo.addItem(f"{t['title']}{subject}  (due {due.strftime('%b %d')})",
                                    t["id"])
        idx = self.task_combo.findData(current)
        self.task_combo.setCurrentIndex(max(0, idx))
        self.task_combo.blockSignals(False)

    def select_task(self, task_id: int) -> None:
        self.refresh_tasks()
        idx = self.task_combo.findData(task_id)
        if idx >= 0:
            self.task_combo.setCurrentIndex(idx)

    def current_task_id(self) -> Optional[int]:
        return self.task_combo.currentData() if self.task_combo.count() else None

    def apply_settings(self, settings: Dict) -> None:
        old = self.settings
        self.settings = dict(settings)
        self.timer.configure(self.settings)
        if self.camera is not None:
            self.camera.sensitivity = self.settings["sensitivity"]
            if old["camera_index"] != self.settings["camera_index"]:
                self.stop_camera()
                self.start_camera()
        self._update_today()

    def shutdown(self) -> None:
        self.timer.pause()
        self._finalize_session(completed=False)
        self.stop_camera()

    # ----------------------------------------------------------------- camera
    def toggle_camera(self) -> None:
        if self.camera is None:
            self.start_camera()
        else:
            self.stop_camera()

    def start_camera(self) -> None:
        if self.camera is not None:
            return
        self.preview.setText("Starting camera…")
        self.camera = fx.CameraWorker(self.settings["camera_index"], self.settings["sensitivity"])
        self.camera.frame_ready.connect(self._on_frame)
        self.camera.state_changed.connect(self._on_cam_state)
        self.camera.failed.connect(self._on_cam_failed)
        self.camera.start()
        self.cam_btn.setText("Turn off camera")

    def stop_camera(self, message: str = "") -> None:
        if self.camera is not None:
            self.camera.requestInterruption()
            self.camera.wait(2000)
            self.camera.deleteLater()
            self.camera = None
        self.cam_btn.setText("Turn on camera")
        self.preview.clear()
        self.preview.setText(message or
                             "Camera is off\n\nTurn it on to measure your active study rate")
        self._set_cam_state(fx.OFF)

    def _on_frame(self, image: QImage) -> None:
        if self.camera is None:
            return
        pix = QPixmap.fromImage(image).scaled(self.preview.size(), Qt.KeepAspectRatio,
                                              Qt.SmoothTransformation)
        self.preview.setPixmap(pix)

    def _on_cam_failed(self, message: str) -> None:
        self.stop_camera(message)

    def _on_cam_state(self, state: str, _share: float) -> None:
        if self.camera is None:
            return
        self._set_cam_state(state)

    def _set_cam_state(self, state: str) -> None:
        now = time.monotonic()
        if state != self.cam_state:
            set_chip(self.state_chip, "● " + fx.STATE_LABELS[state], STATE_COLORS[state])
        self.cam_state = state

        if state in (fx.FOCUSED, fx.OFF):
            self._not_focused_since = None
            self._away_since = None
            if self._alerted:
                self._alerted = False
                self.banner.hide()
            return
        if self._not_focused_since is None:
            self._not_focused_since = now
        if state == fx.AWAY:
            if self._away_since is None:
                self._away_since = now
        else:
            self._away_since = None

    # ------------------------------------------------------------------ timer
    def _pick_phase(self, phase: str) -> None:
        if phase != self.timer.phase:
            self.timer.set_phase(phase)

    def _reset(self) -> None:
        if self.timer.phase == FOCUS:
            self._finalize_session(completed=False)
        self.timer.reset()

    def _on_task_changed(self, _index: int) -> None:
        # a session belongs to one task: close the old one, a new one opens on next tick
        self._finalize_session(completed=False)

    def _on_running_changed(self, running: bool) -> None:
        if running:
            self.play_btn.setText("Pause")
            self.banner.hide()
            self._alerted = False
            now = time.monotonic()
            # don't count distraction that happened while paused
            if self._not_focused_since is not None:
                self._not_focused_since = now
            if self._away_since is not None:
                self._away_since = now
        else:
            started = self.timer.remaining < self.timer.total
            self.play_btn.setText("Resume" if started else "Start")
            self.window().setWindowTitle("StudyFlow")

    def _on_tick(self, remaining: int, total: int) -> None:
        phase = self.timer.phase
        every = self.timer.long_every
        if phase == FOCUS:
            footer = f"Round {self.timer.completed_focus % every + 1} of {every}"
        elif phase == SHORT_BREAK:
            footer = "Stretch · hydrate · rest your eyes"
        else:
            footer = "Long break — you earned it"
        progress = 1 - remaining / total if total else 0
        self.ring.update_state(progress, fmt_clock(remaining), PHASE_LABELS[phase], footer,
                               PHASE_COLORS[phase])
        if self.timer.running:
            self.window().setWindowTitle(f"{fmt_clock(remaining)} · {PHASE_LABELS[phase]}")

    def _on_phase_changed(self, phase: str) -> None:
        self._finalize_session(completed=self._completed_naturally)
        self._completed_naturally = False
        self.phase_buttons[phase].setChecked(True)
        self.play_btn.setText("Start")
        self.timer.ticked.emit(int(self.timer.remaining), self.timer.total)

    def _on_phase_completed(self, phase: str) -> None:
        if phase == FOCUS:
            self._completed_naturally = True
            self._show_banner("Focus block complete — nice work. Time for a break.",
                              theme.SUCCESS)
            play_sound("Glass")
        else:
            self._show_banner("Break's over. Ready for another focus block?", theme.BREAK)
            play_sound("Hero")

    def _on_progress(self, phase: str, dt: float) -> None:
        if phase != FOCUS or dt <= 0:
            return
        if self._session is None:
            self._session = {
                "task_id": self.current_task_id(),
                "started_at": datetime.now() - timedelta(seconds=dt),
                "planned": self.timer.total,
                "studied": 0.0, "camera": 0.0, "focused": 0.0,
            }
            self.live_chart.set_data([])
        s = self._session
        s["studied"] += dt
        if self.cam_state != fx.OFF:
            s["camera"] += dt
            self._bucket[0] += dt
            if self.cam_state == fx.FOCUSED:
                s["focused"] += dt
                self._bucket[1] += dt
        if self._bucket[0] >= LIVE_BUCKET_SEC:
            self.live_chart.append(100 * self._bucket[1] / self._bucket[0])
            self._bucket = [0.0, 0.0]

        self._update_rate()
        self._check_distraction()

    def _check_distraction(self) -> None:
        now = time.monotonic()
        st = self.settings
        if (st["auto_pause_away"] and self._away_since is not None
                and now - self._away_since >= st["away_pause_sec"]):
            self.timer.pause()
            self._alerted = True
            self._show_banner("Timer paused — looks like you stepped away. "
                              "Press Resume when you're back.", theme.DANGER)
            play_sound("Basso")
            return
        if (st["distraction_alert"] and not self._alerted
                and self._not_focused_since is not None
                and now - self._not_focused_since >= st["alert_after_sec"]):
            self._alerted = True
            what = "away from your desk" if self.cam_state == fx.AWAY else "distracted"
            self._show_banner(f"You've seemed {what} for a bit — eyes back on the material 👀",
                              theme.WARNING)
            play_sound("Tink")

    def _update_rate(self) -> None:
        s = self._session
        if not s or s["camera"] < 1:
            self.rate_value.setText("—")
            self.rate_value.setStyleSheet("")
            if s and self.cam_state == fx.OFF:
                self.rate_detail.setText(f"{fmt_duration(s['studied'])} studied · "
                                         "turn on the camera to track focus")
            return
        pct = 100 * s["focused"] / s["camera"]
        color = theme.SUCCESS if pct >= 75 else theme.WARNING if pct >= 50 else theme.DANGER
        self.rate_value.setText(f"{pct:.0f}%")
        self.rate_value.setStyleSheet(f"color: {color};")
        self.rate_detail.setText(
            f"Focused {fmt_clock(s['focused'])} of {fmt_clock(s['camera'])} tracked")

    def _show_banner(self, text: str, color: str) -> None:
        set_chip(self.banner, text, color)
        self.banner.setObjectName("banner")
        self.banner.setStyleSheet(self.banner.styleSheet() + "border-radius: 12px;"
                                  "padding: 10px 14px; font-size: 13px;")
        self.banner.show()

    def _finalize_session(self, completed: bool) -> None:
        s, self._session = self._session, None
        self._bucket = [0.0, 0.0]
        if s is None or s["studied"] < MIN_SESSION_SEC:
            return
        self.db.add_session(
            task_id=s["task_id"], started_at=s["started_at"], ended_at=datetime.now(),
            planned_sec=s["planned"], studied_sec=int(s["studied"]),
            camera_sec=int(s["camera"]), focused_sec=int(s["focused"]), completed=completed,
        )
        self._update_today()
        self.session_saved.emit()

    def _update_today(self) -> None:
        studied = self.db.studied_on(date.today())
        goal = int(self.settings["daily_goal_min"]) * 60
        self.today_label.setText(f"Today: {fmt_duration(studied)} studied")
        self.goal_label.setText(f"DAILY GOAL {fmt_duration(goal)}")
        self.goal_bar.setRange(0, max(1, goal))
        self.goal_bar.setValue(min(goal, studied))

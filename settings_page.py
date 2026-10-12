"""Settings page."""
from __future__ import annotations

from typing import Dict

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QPushButton,
                               QSpinBox, QVBoxLayout, QWidget)

from ..db import DATA_DIR
from . import theme
from .widgets import Card, label


def _spin(lo: int, hi: int, suffix: str) -> QSpinBox:
    s = QSpinBox()
    s.setRange(lo, hi)
    s.setSuffix(suffix)
    s.setFixedWidth(130)
    return s


class SettingsPage(QWidget):
    settings_changed = Signal(dict)

    def __init__(self, settings: Dict, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(18)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(label("Settings", "h1"))
        titles.addWidget(label("Tune the timer and how strict attention tracking is", "muted"))
        root.addLayout(titles)

        row = QHBoxLayout()
        row.setSpacing(18)
        root.addLayout(row)

        timer_card = Card("Timer")
        tf = QFormLayout()
        tf.setSpacing(12)
        self.focus_min = _spin(1, 180, " min")
        self.short_min = _spin(1, 60, " min")
        self.long_min = _spin(1, 90, " min")
        self.long_every = _spin(1, 12, " blocks")
        self.goal_min = _spin(10, 960, " min")
        self.goal_min.setSingleStep(15)
        self.auto_next = QCheckBox("Auto-start the next block")
        tf.addRow("Focus block", self.focus_min)
        tf.addRow("Short break", self.short_min)
        tf.addRow("Long break", self.long_min)
        tf.addRow("Long break every", self.long_every)
        tf.addRow("Daily goal", self.goal_min)
        tf.addRow("", self.auto_next)
        timer_card.body.addLayout(tf)
        timer_card.body.addStretch()
        row.addWidget(timer_card)

        cam_card = Card("Camera & attention")
        cf = QFormLayout()
        cf.setSpacing(12)
        self.camera_index = _spin(0, 9, "")
        self.sensitivity = QComboBox()
        self.sensitivity.addItems(["Lenient", "Balanced", "Strict"])
        self.sensitivity.setFixedWidth(130)
        self.alert = QCheckBox("Alert me when I get distracted")
        self.alert_after = _spin(5, 600, " sec")
        self.auto_pause = QCheckBox("Pause the timer when I walk away")
        self.pause_after = _spin(10, 900, " sec")
        cf.addRow("Camera number", self.camera_index)
        cf.addRow("Sensitivity", self.sensitivity)
        cf.addRow("", self.alert)
        cf.addRow("Alert after", self.alert_after)
        cf.addRow("", self.auto_pause)
        cf.addRow("Pause after", self.pause_after)
        cam_card.body.addLayout(cf)
        cam_card.body.addWidget(label(
            "Lenient works better with glasses, dim light or reading from paper on the desk. "
            "Strict counts any time your eyes aren't clearly visible as distraction.",
            "faint", wrap=True))
        cam_card.body.addStretch()
        row.addWidget(cam_card)

        actions = QHBoxLayout()
        actions.addWidget(label(f"Your data is stored locally in {DATA_DIR}", "faint"))
        actions.addStretch()
        self.saved_label = label("")
        self.saved_label.setStyleSheet(f"color: {theme.SUCCESS};")
        actions.addWidget(self.saved_label)
        save = QPushButton("Save settings")
        save.setProperty("variant", "primary")
        save.clicked.connect(self._save)
        actions.addWidget(save)
        root.addLayout(actions)
        root.addStretch()

        self.alert.toggled.connect(self.alert_after.setEnabled)
        self.auto_pause.toggled.connect(self.pause_after.setEnabled)
        self.load(settings)

    def load(self, s: Dict) -> None:
        self.focus_min.setValue(s["focus_min"])
        self.short_min.setValue(s["short_break_min"])
        self.long_min.setValue(s["long_break_min"])
        self.long_every.setValue(s["long_every"])
        self.goal_min.setValue(s["daily_goal_min"])
        self.auto_next.setChecked(s["auto_start_next"])
        self.camera_index.setValue(s["camera_index"])
        self.sensitivity.setCurrentIndex(s["sensitivity"] - 1)
        self.alert.setChecked(s["distraction_alert"])
        self.alert_after.setValue(s["alert_after_sec"])
        self.alert_after.setEnabled(s["distraction_alert"])
        self.auto_pause.setChecked(s["auto_pause_away"])
        self.pause_after.setValue(s["away_pause_sec"])
        self.pause_after.setEnabled(s["auto_pause_away"])

    def values(self) -> Dict:
        return {
            "focus_min": self.focus_min.value(),
            "short_break_min": self.short_min.value(),
            "long_break_min": self.long_min.value(),
            "long_every": self.long_every.value(),
            "daily_goal_min": self.goal_min.value(),
            "auto_start_next": self.auto_next.isChecked(),
            "camera_index": self.camera_index.value(),
            "sensitivity": self.sensitivity.currentIndex() + 1,
            "distraction_alert": self.alert.isChecked(),
            "alert_after_sec": self.alert_after.value(),
            "auto_pause_away": self.auto_pause.isChecked(),
            "away_pause_sec": self.pause_after.value(),
        }

    def _save(self) -> None:
        self.settings_changed.emit(self.values())
        self.saved_label.setText("✓ Saved")
        QTimer.singleShot(2000, lambda: self.saved_label.setText(""))

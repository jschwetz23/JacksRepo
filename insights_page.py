"""Insights page: study time and active-study-rate analytics."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QGridLayout, QHBoxLayout, QHeaderView,
                               QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from ..db import Database
from . import theme
from .widgets import BarChart, Card, HBarList, LineChart, StatCard, fmt_duration, label


class InsightsPage(QWidget):
    def __init__(self, db: Database, settings: Dict, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        self.db = db
        self.settings = settings

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        inner = QWidget()
        inner.setObjectName("page")
        scroll.setWidget(inner)

        root = QVBoxLayout(inner)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(18)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(label("Insights", "h1"))
        titles.addWidget(label("How much you study — and how much of it is real focus", "muted"))
        root.addLayout(titles)

        stats = QHBoxLayout()
        stats.setSpacing(18)
        self.stat_today = StatCard("Today", theme.ACCENT)
        self.stat_week = StatCard("Last 7 days", theme.BREAK)
        self.stat_rate = StatCard("Active study rate", theme.SUCCESS)
        self.stat_streak = StatCard("Streak", theme.WARNING)
        for s in (self.stat_today, self.stat_week, self.stat_rate, self.stat_streak):
            stats.addWidget(s)
        root.addLayout(stats)

        grid = QGridLayout()
        grid.setSpacing(18)
        root.addLayout(grid)

        week_card = Card("Study time", "Minutes studied over the last 7 days")
        self.week_chart = BarChart(unit_formatter=lambda v: f"{int(v)}m")
        week_card.body.addWidget(self.week_chart)
        grid.addWidget(week_card, 0, 0, 1, 2)

        subj_card = Card("By subject", "Last 30 days")
        self.subject_bars = HBarList()
        subj_card.body.addWidget(self.subject_bars)
        subj_card.body.addStretch()
        grid.addWidget(subj_card, 1, 1)

        rate_card = Card("Active study rate per session",
                         "Share of camera-tracked time you were looking at your work")
        self.rate_chart = LineChart(theme.SUCCESS,
                                    empty_text="Finish two sessions with the camera on")
        self.rate_chart.setMinimumHeight(200)
        rate_card.body.addWidget(self.rate_chart)
        grid.addWidget(rate_card, 1, 0)

        recent_card = Card("Recent sessions")
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["When", "Studied", "Item", "Focus"])
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.verticalHeader().setDefaultSectionSize(34)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        recent_card.body.addWidget(self.table)
        grid.addWidget(recent_card, 2, 0, 1, 2)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        root.addStretch()

    def refresh(self) -> None:
        today_sec = self.db.studied_on(date.today())
        goal = int(self.settings["daily_goal_min"]) * 60
        self.stat_today.set(fmt_duration(today_sec),
                            f"{min(100, 100 * today_sec // max(goal, 1))}% of daily goal")

        totals = self.db.daily_totals(7)
        week_sec = sum(s for _, s in totals)
        active_days = sum(1 for _, s in totals if s > 0)
        self.stat_week.set(fmt_duration(week_sec), f"{active_days} of 7 days active")

        rate = self.db.focus_rate(7)
        if rate is None:
            self.stat_rate.set("—", "Turn on the camera while studying")
        else:
            self.stat_rate.set(f"{rate * 100:.0f}%", "of tracked time, last 7 days")

        streak = self.db.streak()
        self.stat_streak.set(f"{streak} day{'s' if streak != 1 else ''}",
                             "Keep it going!" if streak else "Study today to start one")

        self.week_chart.set_data(
            [s / 60 for _, s in totals],
            ["Today" if d == date.today() else d.strftime("%a") for d, _ in totals],
            goal=goal / 60,
        )
        self.subject_bars.set_rows(
            [(name, sec, fmt_duration(sec)) for name, sec in self.db.subject_totals(30)])

        sessions = self.db.recent_sessions(30)
        tracked = [s for s in reversed(sessions) if s["camera_sec"] > 0][-15:]
        self.rate_chart.set_data([100 * s["focused_sec"] / s["camera_sec"] for s in tracked])

        rows = sessions[:12]
        self.table.setRowCount(len(rows))
        self.table.setFixedHeight(self.table.horizontalHeader().sizeHint().height()
                                  + 34 * max(1, len(rows)) + 4)
        for r, s in enumerate(rows):
            started = datetime.fromisoformat(s["started_at"])
            when = started.strftime("%I:%M %p").lstrip("0")
            if started.date() == date.today():
                when = f"Today {when}"
            elif started.date() == date.today() - timedelta(days=1):
                when = f"Yesterday {when}"
            else:
                when = started.strftime("%b %d ") + when
            items = [
                QTableWidgetItem(when),
                QTableWidgetItem(fmt_duration(s["studied_sec"]) +
                                 ("" if s["completed"] else " ·partial")),
                QTableWidgetItem(s["task_title"] or "General study"),
            ]
            if s["camera_sec"]:
                pct = 100 * s["focused_sec"] / s["camera_sec"]
                f = QTableWidgetItem(f"{pct:.0f}%")
                f.setForeground(QColor(theme.SUCCESS if pct >= 75 else
                                       theme.WARNING if pct >= 50 else theme.DANGER))
            else:
                f = QTableWidgetItem("—")
                f.setForeground(QColor(theme.FAINT))
            items.append(f)
            items[0].setForeground(QColor(theme.MUTED))
            for c, item in enumerate(items):
                self.table.setItem(r, c, item)

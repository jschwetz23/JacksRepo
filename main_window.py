"""Main window: sidebar navigation + page stack."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QMainWindow, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)

from ..db import Database
from . import theme
from .focus_page import FocusPage
from .insights_page import InsightsPage
from .planner_page import PlannerPage
from .settings_page import SettingsPage
from .widgets import label

NAV = [("◉   Focus", 0), ("▦   Planner", 1), ("▲   Insights", 2), ("⚙   Settings", 3)]


class MainWindow(QMainWindow):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.settings = db.settings()
        self.setWindowTitle("StudyFlow")
        self.resize(1280, 820)
        self.setMinimumSize(1080, 700)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ---- sidebar
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(14, 24, 14, 20)
        side.setSpacing(4)
        brand = label("◆ StudyFlow", "brand")
        brand.setStyleSheet(f"color: {theme.TEXT};")
        side.addWidget(brand)
        side.addWidget(label("Focus · plan · improve", "brandSub"))
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for text, idx in NAV:
            b = QPushButton(text)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            self.nav_group.addButton(b, idx)
            side.addWidget(b)
        side.addStretch()
        side.addWidget(label("UP NEXT", "faint"))
        self.upcoming = label("", "muted", wrap=True)
        self.upcoming.setTextFormat(Qt.RichText)
        side.addWidget(self.upcoming)
        layout.addWidget(sidebar)

        # ---- pages
        self.stack = QStackedWidget()
        self.focus_page = FocusPage(db, self.settings)
        self.planner_page = PlannerPage(db)
        self.insights_page = InsightsPage(db, self.settings)
        self.settings_page = SettingsPage(self.settings)
        for page in (self.focus_page, self.planner_page, self.insights_page,
                     self.settings_page):
            self.stack.addWidget(page)
        layout.addWidget(self.stack, 1)

        self.nav_group.idClicked.connect(self.go_to)
        self.planner_page.tasks_changed.connect(self._on_tasks_changed)
        self.planner_page.study_requested.connect(self._study_task)
        self.focus_page.session_saved.connect(self._on_session_saved)
        self.settings_page.settings_changed.connect(self._apply_settings)

        self.go_to(0)
        self._refresh_upcoming()

    def go_to(self, index: int) -> None:
        self.nav_group.button(index).setChecked(True)
        self.stack.setCurrentIndex(index)
        if index == 1:
            self.planner_page.refresh()
        elif index == 2:
            self.insights_page.refresh()

    def _study_task(self, task_id: int) -> None:
        self.focus_page.select_task(task_id)
        self.go_to(0)

    def _on_tasks_changed(self) -> None:
        self.focus_page.refresh_tasks()
        self._refresh_upcoming()

    def _on_session_saved(self) -> None:
        self.planner_page.refresh()
        if self.stack.currentIndex() == 2:
            self.insights_page.refresh()

    def _apply_settings(self, values: dict) -> None:
        self.settings.update(values)
        self.db.save_settings(self.settings)
        self.focus_page.apply_settings(self.settings)
        self.insights_page.settings = self.settings

    def _refresh_upcoming(self) -> None:
        tasks = self.db.tasks(include_done=False)[:4]
        if not tasks:
            self.upcoming.setText("Nothing due — add items in the Planner.")
            return
        lines = []
        for t in tasks:
            days = (date.fromisoformat(t["due_date"]) - date.today()).days
            if days < 0:
                when, color = f"{-days}d late", theme.DANGER
            elif days == 0:
                when, color = "today", theme.WARNING
            else:
                when, color = f"in {days}d", theme.WARNING if days <= 3 else theme.MUTED
            title = t["title"] if len(t["title"]) <= 22 else t["title"][:21] + "…"
            lines.append(f"<div style='margin-bottom:6px'><span style='color:{theme.TEXT}'>"
                         f"{title}</span><br><span style='color:{color}'>{when}</span></div>")
        self.upcoming.setText("".join(lines))

    def closeEvent(self, event) -> None:
        self.focus_page.shutdown()
        self.db.close()
        super().closeEvent(event)

"""Planner page: add due dates and what needs to be studied."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QComboBox, QDateEdit,
                               QDoubleSpinBox, QHBoxLayout, QHeaderView, QLineEdit,
                               QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..db import PRIORITIES, Database
from . import theme
from .widgets import Card, label, set_chip

FILTERS = ["Open", "This week", "Overdue", "Done", "All"]
PRIORITY_COLORS = [theme.MUTED, theme.WARNING, theme.DANGER]


def due_text(due: date, done: bool):
    days = (due - date.today()).days
    base = due.strftime("%a %b %d")
    if done:
        return base, theme.FAINT
    if days < 0:
        return f"{base} · {-days}d late", theme.DANGER
    if days == 0:
        return f"{base} · today", theme.WARNING
    if days == 1:
        return f"{base} · tomorrow", theme.WARNING
    if days <= 3:
        return f"{base} · in {days}d", theme.WARNING
    return f"{base} · in {days}d", theme.TEXT


class PlannerPage(QWidget):
    study_requested = Signal(int)
    tasks_changed = Signal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        self.db = db
        self.editing_id: Optional[int] = None
        self.filter = "Open"
        self._build()
        self.refresh()

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(18)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(label("Planner", "h1"))
        titles.addWidget(label("Track due dates and everything you need to study", "muted"))
        header.addLayout(titles)
        header.addStretch()
        self.chip_overdue = label()
        self.chip_week = label()
        self.chip_open = label()
        for c in (self.chip_overdue, self.chip_week, self.chip_open):
            header.addWidget(c, 0, Qt.AlignBottom)
        root.addLayout(header)

        content = QHBoxLayout()
        content.setSpacing(18)
        root.addLayout(content, 1)

        # ---- form
        self.form_card = Card("Add a study item")
        self.form_card.setFixedWidth(330)
        f = self.form_card.body
        f.setSpacing(6)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("e.g. Chapter 5 — Thermodynamics")
        self.subject_combo = QComboBox()
        self.subject_combo.setEditable(True)
        self.subject_combo.lineEdit().setPlaceholderText("e.g. Physics")
        self.due_edit = QDateEdit()
        self.due_edit.setCalendarPopup(True)
        self.due_edit.setDisplayFormat("ddd, MMM d yyyy")
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(PRIORITIES)
        self.est_spin = QDoubleSpinBox()
        self.est_spin.setRange(0.5, 500)
        self.est_spin.setSingleStep(0.5)
        self.est_spin.setSuffix(" h")
        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setPlaceholderText("Topics, page numbers, practice problems…")
        self.notes_edit.setMaximumHeight(110)

        def field(name, widget):
            f.addSpacing(4)
            f.addWidget(label(name.upper(), "faint"))
            f.addWidget(widget)

        field("What to study", self.title_edit)
        field("Subject / course", self.subject_combo)
        row = QHBoxLayout()
        left, right = QVBoxLayout(), QVBoxLayout()
        left.setSpacing(6)
        right.setSpacing(6)
        left.addWidget(label("PRIORITY", "faint"))
        left.addWidget(self.priority_combo)
        right.addWidget(label("EST. TIME", "faint"))
        right.addWidget(self.est_spin)
        row.addLayout(left)
        row.addLayout(right)
        field("Due date", self.due_edit)
        f.addSpacing(4)
        f.addLayout(row)
        field("Notes", self.notes_edit)
        f.addStretch()

        self.save_btn = QPushButton("Add to planner")
        self.save_btn.setProperty("variant", "primary")
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.hide()
        btns = QHBoxLayout()
        btns.addWidget(self.cancel_btn)
        btns.addWidget(self.save_btn, 1)
        f.addLayout(btns)
        content.addWidget(self.form_card)

        # ---- list
        list_card = Card()
        toolbar = QHBoxLayout()
        self.filter_group = QButtonGroup(self)
        for name in FILTERS:
            b = QPushButton(name)
            b.setObjectName("pill")
            b.setCheckable(True)
            b.setChecked(name == self.filter)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, n=name: self._set_filter(n))
            self.filter_group.addButton(b)
            toolbar.addWidget(b)
        toolbar.addStretch()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search…")
        self.search.setFixedWidth(200)
        self.search.textChanged.connect(lambda _: self.refresh())
        toolbar.addWidget(self.search)
        list_card.body.addLayout(toolbar)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["", "Item", "Subject", "Due", "Priority",
                                              "Progress"])
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.verticalHeader().setDefaultSectionSize(48)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 36)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        for col in (2, 3, 4):
            hh.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 150)
        hh.setHighlightSections(False)
        hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        list_card.body.addWidget(self.table, 1)

        self.empty_label = label("Nothing here yet — add what you need to study on the left.",
                                 "muted")
        self.empty_label.setAlignment(Qt.AlignCenter)
        list_card.body.addWidget(self.empty_label)

        actions = QHBoxLayout()
        actions.addWidget(label("Tip: tick the box to mark done · double-click to edit",
                                "faint"))
        actions.addStretch()
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setProperty("variant", "danger")
        self.edit_btn = QPushButton("Edit")
        self.study_btn = QPushButton("▶  Study now")
        self.study_btn.setProperty("variant", "primary")
        for b in (self.delete_btn, self.edit_btn, self.study_btn):
            b.setCursor(Qt.PointingHandCursor)
            actions.addWidget(b)
        list_card.body.addLayout(actions)
        content.addWidget(list_card, 1)

        self.save_btn.clicked.connect(self._save)
        self.cancel_btn.clicked.connect(self._clear_form)
        self.title_edit.returnPressed.connect(self._save)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.itemSelectionChanged.connect(self._update_actions)
        self.table.cellDoubleClicked.connect(lambda r, _c: self._edit_row(r))
        self.edit_btn.clicked.connect(lambda: self._edit_row(self.table.currentRow()))
        self.delete_btn.clicked.connect(self._delete)
        self.study_btn.clicked.connect(self._study)
        self._clear_form()

    # ------------------------------------------------------------------ data
    def refresh(self) -> None:
        today = date.today()
        all_tasks = self.db.tasks(include_done=True)
        open_tasks = [t for t in all_tasks if not t["done"]]
        overdue = [t for t in open_tasks if date.fromisoformat(t["due_date"]) < today]
        week = [t for t in open_tasks
                if 0 <= (date.fromisoformat(t["due_date"]) - today).days <= 7]
        set_chip(self.chip_overdue, f"{len(overdue)} overdue",
                 theme.DANGER if overdue else theme.FAINT)
        set_chip(self.chip_week, f"{len(week)} due this week", theme.WARNING)
        set_chip(self.chip_open, f"{len(open_tasks)} open", theme.ACCENT)

        query = self.search.text().strip().lower()

        def keep(t) -> bool:
            due = date.fromisoformat(t["due_date"])
            if query and query not in f"{t['title']} {t['subject']} {t['notes']}".lower():
                return False
            return {
                "Open": not t["done"],
                "This week": not t["done"] and (due - today).days <= 7,
                "Overdue": not t["done"] and due < today,
                "Done": bool(t["done"]),
                "All": True,
            }[self.filter]

        rows = [t for t in all_tasks if keep(t)]
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        for r, t in enumerate(rows):
            done = bool(t["done"])
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            check.setCheckState(Qt.Checked if done else Qt.Unchecked)
            check.setData(Qt.UserRole, t["id"])
            self.table.setItem(r, 0, check)

            title = QTableWidgetItem(t["title"])
            font = QFont(self.font())
            font.setBold(True)
            font.setStrikeOut(done)
            title.setFont(font)
            if t["notes"]:
                title.setToolTip(t["notes"])
            if done:
                title.setForeground(QColor(theme.FAINT))
            self.table.setItem(r, 1, title)

            subj = QTableWidgetItem(t["subject"] or "—")
            subj.setForeground(QColor(theme.MUTED))
            self.table.setItem(r, 2, subj)

            text, color = due_text(date.fromisoformat(t["due_date"]), done)
            due_item = QTableWidgetItem(text)
            due_item.setForeground(QColor(color))
            self.table.setItem(r, 3, due_item)

            pr = QTableWidgetItem("●  " + PRIORITIES[t["priority"]])
            pr.setForeground(QColor(PRIORITY_COLORS[t["priority"]]))
            self.table.setItem(r, 4, pr)

            self.table.setCellWidget(r, 5, self._progress_widget(t["studied_sec"] / 3600,
                                                                 t["est_hours"], done))
        self.table.blockSignals(False)
        self.table.setVisible(bool(rows))
        self.empty_label.setVisible(not rows)
        self.empty_label.setText(
            "Nothing here yet — add what you need to study on the left."
            if not all_tasks else "No items match this filter.")
        self._refresh_subjects()
        self._update_actions()

    def _progress_widget(self, studied_h: float, est_h: float, done: bool) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 6, 8, 6)
        lay.setSpacing(3)
        bar = QProgressBar()
        bar.setRange(0, 1000)
        bar.setValue(1000 if done else int(min(1.0, studied_h / max(est_h, 0.01)) * 1000))
        if done:
            bar.setStyleSheet(f"QProgressBar::chunk {{ background: {theme.SUCCESS}; }}")
        lay.addWidget(bar)
        lay.addWidget(label(f"{studied_h:.1f} / {est_h:g} h studied", "faint"))
        return w

    def _refresh_subjects(self) -> None:
        text = self.subject_combo.currentText()
        self.subject_combo.blockSignals(True)
        self.subject_combo.clear()
        self.subject_combo.addItems(self.db.subjects())
        self.subject_combo.setCurrentText(text)
        self.subject_combo.blockSignals(False)

    def _selected_id(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0 or not self.table.selectedItems():
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _update_actions(self) -> None:
        has = self._selected_id() is not None
        for b in (self.delete_btn, self.edit_btn, self.study_btn):
            b.setEnabled(has)

    def _set_filter(self, name: str) -> None:
        self.filter = name
        self.refresh()

    # --------------------------------------------------------------- actions
    def _save(self) -> None:
        title = self.title_edit.text().strip()
        if not title:
            self.title_edit.setStyleSheet(f"border-color: {theme.DANGER};")
            self.title_edit.setFocus()
            return
        self.title_edit.setStyleSheet("")
        values = dict(
            title=title,
            subject=self.subject_combo.currentText().strip(),
            due_date=self.due_edit.date().toPython(),
            priority=self.priority_combo.currentIndex(),
            est_hours=self.est_spin.value(),
            notes=self.notes_edit.toPlainText().strip(),
        )
        if self.editing_id is None:
            self.db.add_task(**values)
        else:
            self.db.update_task(self.editing_id, **values)
        self._clear_form()
        self.refresh()
        self.tasks_changed.emit()

    def _clear_form(self) -> None:
        self.editing_id = None
        self.title_edit.clear()
        self.title_edit.setStyleSheet("")
        self.subject_combo.setCurrentText("")
        d = date.today() + timedelta(days=7)
        self.due_edit.setDate(QDate(d.year, d.month, d.day))
        self.priority_combo.setCurrentIndex(1)
        self.est_spin.setValue(2)
        self.notes_edit.clear()
        self.save_btn.setText("Add to planner")
        self.cancel_btn.hide()
        self.form_card.body.itemAt(0).widget().setText("Add a study item")

    def _edit_row(self, row: int) -> None:
        if row < 0:
            return
        task = self.db.task(self.table.item(row, 0).data(Qt.UserRole))
        if task is None:
            return
        self.editing_id = task["id"]
        self.title_edit.setText(task["title"])
        self.subject_combo.setCurrentText(task["subject"])
        d = date.fromisoformat(task["due_date"])
        self.due_edit.setDate(QDate(d.year, d.month, d.day))
        self.priority_combo.setCurrentIndex(task["priority"])
        self.est_spin.setValue(task["est_hours"])
        self.notes_edit.setPlainText(task["notes"])
        self.save_btn.setText("Save changes")
        self.cancel_btn.show()
        self.form_card.body.itemAt(0).widget().setText("Edit study item")
        self.title_edit.setFocus()

    def _delete(self) -> None:
        task_id = self._selected_id()
        if task_id is None:
            return
        task = self.db.task(task_id)
        answer = QMessageBox.question(
            self, "Delete item",
            f"Delete “{task['title']}”? Study time you logged stays in your insights.")
        if answer == QMessageBox.Yes:
            self.db.delete_task(task_id)
            if self.editing_id == task_id:
                self._clear_form()
            self.refresh()
            self.tasks_changed.emit()

    def _study(self) -> None:
        task_id = self._selected_id()
        if task_id is not None:
            self.study_requested.emit(task_id)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        self.db.set_done(item.data(Qt.UserRole), item.checkState() == Qt.Checked)
        self.refresh()
        self.tasks_changed.emit()

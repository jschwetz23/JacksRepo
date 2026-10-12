"""SQLite persistence for tasks, study sessions and settings."""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

DATA_DIR = Path.home() / ".studyflow"

DEFAULT_SETTINGS = {
    "focus_min": 25,
    "short_break_min": 5,
    "long_break_min": 15,
    "long_every": 4,
    "auto_start_next": False,
    "camera_index": 0,
    "sensitivity": 2,           # 1 = lenient, 2 = balanced, 3 = strict
    "distraction_alert": True,
    "alert_after_sec": 20,
    "auto_pause_away": False,
    "away_pause_sec": 60,
    "daily_goal_min": 120,
}

PRIORITIES = ["Low", "Medium", "High"]


class Database:
    def __init__(self, path: Optional[Path] = None):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path or DATA_DIR / "studyflow.db"))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def _migrate(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                subject     TEXT NOT NULL DEFAULT '',
                due_date    TEXT NOT NULL,
                priority    INTEGER NOT NULL DEFAULT 1,
                est_hours   REAL NOT NULL DEFAULT 1,
                notes       TEXT NOT NULL DEFAULT '',
                done        INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id      INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
                started_at   TEXT NOT NULL,
                ended_at     TEXT NOT NULL,
                planned_sec  INTEGER NOT NULL,
                studied_sec  INTEGER NOT NULL,
                camera_sec   INTEGER NOT NULL,
                focused_sec  INTEGER NOT NULL,
                completed    INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    # ------------------------------------------------------------------ tasks
    def add_task(self, title: str, subject: str, due_date: date, priority: int,
                 est_hours: float, notes: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO tasks (title, subject, due_date, priority, est_hours, notes, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, subject, due_date.isoformat(), priority, est_hours, notes,
             datetime.now().isoformat(timespec="seconds")),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_task(self, task_id: int, title: str, subject: str, due_date: date,
                    priority: int, est_hours: float, notes: str) -> None:
        self.conn.execute(
            "UPDATE tasks SET title=?, subject=?, due_date=?, priority=?, est_hours=?, notes=?"
            " WHERE id=?",
            (title, subject, due_date.isoformat(), priority, est_hours, notes, task_id),
        )
        self.conn.commit()

    def set_done(self, task_id: int, done: bool) -> None:
        self.conn.execute("UPDATE tasks SET done=? WHERE id=?", (int(done), task_id))
        self.conn.commit()

    def delete_task(self, task_id: int) -> None:
        self.conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        self.conn.commit()

    def task(self, task_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()

    def tasks(self, include_done: bool = True) -> List[sqlite3.Row]:
        sql = """
            SELECT t.*, COALESCE(SUM(s.studied_sec), 0) AS studied_sec
            FROM tasks t LEFT JOIN sessions s ON s.task_id = t.id
            {where}
            GROUP BY t.id
            ORDER BY t.done, t.due_date, t.priority DESC
        """.format(where="" if include_done else "WHERE t.done = 0")
        return self.conn.execute(sql).fetchall()

    def subjects(self) -> List[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT subject FROM tasks WHERE subject != '' ORDER BY subject"
        ).fetchall()
        return [r["subject"] for r in rows]

    # --------------------------------------------------------------- sessions
    def add_session(self, task_id: Optional[int], started_at: datetime, ended_at: datetime,
                    planned_sec: int, studied_sec: int, camera_sec: int, focused_sec: int,
                    completed: bool) -> None:
        self.conn.execute(
            "INSERT INTO sessions (task_id, started_at, ended_at, planned_sec, studied_sec,"
            " camera_sec, focused_sec, completed) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (task_id, started_at.isoformat(timespec="seconds"),
             ended_at.isoformat(timespec="seconds"), planned_sec, studied_sec,
             camera_sec, focused_sec, int(completed)),
        )
        self.conn.commit()

    def recent_sessions(self, limit: int = 20) -> List[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT s.*, t.title AS task_title, t.subject AS subject
            FROM sessions s LEFT JOIN tasks t ON t.id = s.task_id
            ORDER BY s.started_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()

    def daily_totals(self, days: int = 7) -> List[tuple]:
        """[(date, studied_sec), ...] oldest first, including empty days."""
        start = date.today() - timedelta(days=days - 1)
        rows = self.conn.execute(
            "SELECT substr(started_at, 1, 10) AS d, SUM(studied_sec) AS sec FROM sessions"
            " WHERE started_at >= ? GROUP BY d",
            (start.isoformat(),),
        ).fetchall()
        by_day = {r["d"]: r["sec"] for r in rows}
        return [(start + timedelta(days=i),
                 by_day.get((start + timedelta(days=i)).isoformat(), 0))
                for i in range(days)]

    def subject_totals(self, days: int = 30) -> List[tuple]:
        since = (date.today() - timedelta(days=days - 1)).isoformat()
        rows = self.conn.execute(
            """
            SELECT COALESCE(NULLIF(t.subject, ''), 'Unassigned') AS subject,
                   SUM(s.studied_sec) AS sec
            FROM sessions s LEFT JOIN tasks t ON t.id = s.task_id
            WHERE s.started_at >= ? GROUP BY 1 ORDER BY sec DESC LIMIT 6
            """,
            (since,),
        ).fetchall()
        return [(r["subject"], r["sec"]) for r in rows]

    def studied_on(self, day: date) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(studied_sec), 0) AS sec FROM sessions"
            " WHERE substr(started_at, 1, 10) = ?",
            (day.isoformat(),),
        ).fetchone()
        return row["sec"]

    def focus_rate(self, days: int = 7) -> Optional[float]:
        """Share of camera-tracked study time spent actively focused (0..1)."""
        since = (date.today() - timedelta(days=days - 1)).isoformat()
        row = self.conn.execute(
            "SELECT SUM(camera_sec) AS cam, SUM(focused_sec) AS foc FROM sessions"
            " WHERE started_at >= ?",
            (since,),
        ).fetchone()
        if not row["cam"]:
            return None
        return row["foc"] / row["cam"]

    def streak(self) -> int:
        rows = self.conn.execute(
            "SELECT DISTINCT substr(started_at, 1, 10) AS d FROM sessions"
            " WHERE studied_sec > 0"
        ).fetchall()
        days = {r["d"] for r in rows}
        day = date.today()
        if day.isoformat() not in days:
            day -= timedelta(days=1)   # streak survives until today is over
        count = 0
        while day.isoformat() in days:
            count += 1
            day -= timedelta(days=1)
        return count

    # --------------------------------------------------------------- settings
    def settings(self) -> Dict:
        values = dict(DEFAULT_SETTINGS)
        for row in self.conn.execute("SELECT key, value FROM settings"):
            if row["key"] in values:
                values[row["key"]] = json.loads(row["value"])
        return values

    def save_settings(self, values: Dict) -> None:
        self.conn.executemany(
            "INSERT INTO settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            [(k, json.dumps(v)) for k, v in values.items()],
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

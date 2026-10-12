# StudyFlow

A desktop study app in Python (PySide6 + OpenCV) with:

- **Focus timer**: Pomodoro-style focus blocks, short breaks and long breaks, with a progress ring, a round counter, sounds, and a daily-goal bar.
- **Camera attention tracking**: your webcam is analysed live (on your machine only; nothing is recorded or uploaded) to estimate your **active study rate**, the share of each focus block you were actually looking at your work. You get a live focus graph, optional "you seem distracted" alerts, and optional auto-pause when you walk away.
- **Planner dashboard**: add what you need to study with a due date, subject, priority, time estimate and notes. Items are colour-coded by urgency, can be filtered and searched, and show how many hours you've logged against each one. **Study now** starts a session for that item.
- **Insights**: today, the last 7 days, active study rate and streak, plus a daily study-time chart, time per subject, focus rate per session, and recent sessions.

## Run it

```bash
./run.sh
```

Or manually:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

On macOS the first camera use triggers a permission prompt for the app that launched Python (Terminal, iTerm, VS Code…). If the camera won't open, allow it under **System Settings → Privacy & Security → Camera** and restart that app.

## How focus detection works

Each frame goes through OpenCV's Haar cascades:

| What the camera sees            | State      |
|---------------------------------|------------|
| No face                         | Away       |
| Face, but eyes not visible      | Distracted (head turned or down, phone, eyes closed) |
| Face with visible eyes          | Focused    |

Readings are smoothed over a 3-second window. Only time inside a **focus block** with the camera on counts toward the active study rate. If you read from paper flat on the desk, or wear glasses in dim light, set **Settings → Sensitivity** to *Lenient*.

## Project layout

```
main.py                    entry point
studyflow/db.py            SQLite storage (~/.studyflow/studyflow.db)
studyflow/focus.py         camera thread + attention classifier
studyflow/timer.py         pomodoro state machine
studyflow/ui/              main window, pages, custom-painted widgets, theme
```

Note: `opencv-python` is pinned below 5.0 because OpenCV 5 removed the Haar cascade face/eye detectors that this app uses.

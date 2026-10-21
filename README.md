# StudyFlow

A study app that runs in your browser, hosted on GitHub Pages:

- **Focus timer**: Pomodoro-style focus blocks, short breaks and long breaks, with a progress ring, a round counter, sounds and a daily-goal bar.
- **Camera attention tracking** (optional): your webcam is analysed live in the browser (nothing is recorded or uploaded) to estimate your **active study rate**, the share of each focus block you were actually facing your work. You get a live focus graph, optional "you seem distracted" alerts and optional auto-pause when you walk away.
- **Planner**: add what you need to study with a due date, subject, priority, time estimate and notes. Items are colour-coded by urgency, can be filtered and searched, and show how many hours you've logged against each one. **Study** starts a session for that item.
- **Insights**: today, the last 7 days, active study rate and streak, plus a daily study-time chart, time per subject, focus rate per session and recent sessions.

## Files

| File | What it does |
|------|--------------|
| `index.html` | Page layout (all four pages) |
| `style.css` | Look and feel |
| `app.js` | Timer, planner, insights, settings and storage |
| `camera.js` | Webcam attention tracking |

No build step and no server: GitHub Pages serves these files as they are.

## Your data

Tasks, sessions and settings are saved in your browser's local storage. They stay on the device and browser you use, and clearing browser data erases them, so use **Settings → Export backup** now and then.

## How focus detection works

The camera feed goes through Google's MediaPipe Face Landmarker (loaded from a CDN the first time you turn the camera on):

| What the camera sees | State |
|----------------------|-------|
| No face | Away |
| Head turned well away, or eyes closed | Distracted |
| Facing the screen with eyes open | Focused |

Readings are smoothed over a 3-second window. Only time inside a **focus block** with the camera on counts toward the active study rate. If you read from paper on the desk or wear glasses, set **Settings → Sensitivity** to *Lenient*.

The first time you turn the camera on, your browser asks for permission. If you block it by accident, click the camera icon in the address bar to allow it again.

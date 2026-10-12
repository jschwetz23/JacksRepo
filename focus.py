"""Camera-based attention tracking.

A background thread grabs webcam frames and runs OpenCV Haar cascades:

* no face found                      -> AWAY
* face found, eyes not visible       -> DISTRACTED (head turned/down, eyes closed, phone...)
* face found with visible eyes       -> FOCUSED

Raw per-frame readings are smoothed over a short rolling window so a single
missed detection doesn't flip the state.
"""
from __future__ import annotations

import time
from collections import deque

import cv2
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

FOCUSED = "focused"
DISTRACTED = "distracted"
AWAY = "away"
OFF = "off"

STATE_LABELS = {
    FOCUSED: "Focused",
    DISTRACTED: "Distracted",
    AWAY: "Away",
    OFF: "Camera off",
}

# sensitivity -> (eye detector minNeighbors, share of focused frames required)
SENSITIVITY = {
    1: (2, 0.35),
    2: (4, 0.50),
    3: (6, 0.65),
}

SMOOTHING_WINDOW_SEC = 3.0
DETECT_WIDTH = 360

_BOX_COLORS = {  # BGR
    FOCUSED: (153, 211, 52),
    DISTRACTED: (36, 191, 251),
    AWAY: (113, 113, 248),
}


class CameraWorker(QThread):
    frame_ready = Signal(QImage)
    state_changed = Signal(str, float)   # smoothed state, focused share of window (0..1)
    failed = Signal(str)

    def __init__(self, camera_index: int = 0, sensitivity: int = 2, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self.sensitivity = sensitivity

    def run(self) -> None:
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            self.failed.emit(
                "Couldn't open the camera. Check that it isn't in use and that this "
                "app (or your terminal) has camera permission."
            )
            return

        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        eye_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_eye_tree_eyeglasses.xml")

        history = deque()   # (timestamp, raw_state)
        misses = 0
        try:
            while not self.isInterruptionRequested():
                ok, frame = cap.read()
                if not ok:
                    misses += 1
                    if misses > 60:
                        self.failed.emit("The camera stopped sending frames.")
                        return
                    self.msleep(30)
                    continue
                misses = 0

                frame = cv2.flip(frame, 1)
                raw = self._classify(frame, face_cascade, eye_cascade)

                now = time.monotonic()
                history.append((now, raw))
                while history and now - history[0][0] > SMOOTHING_WINDOW_SEC:
                    history.popleft()

                n = len(history)
                focused_share = sum(1 for _, s in history if s == FOCUSED) / n
                away_share = sum(1 for _, s in history if s == AWAY) / n
                _, threshold = SENSITIVITY.get(self.sensitivity, SENSITIVITY[2])
                if focused_share >= threshold:
                    state = FOCUSED
                elif away_share >= 0.5:
                    state = AWAY
                else:
                    state = DISTRACTED
                self.state_changed.emit(state, focused_share)

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                image = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()
                self.frame_ready.emit(image)
                self.msleep(15)
        finally:
            cap.release()

    def _classify(self, frame, face_cascade, eye_cascade) -> str:
        """Detect on a downscaled grayscale copy and draw overlays on the full frame."""
        h, w = frame.shape[:2]
        scale = DETECT_WIDTH / float(w)
        small = cv2.resize(frame, (DETECT_WIDTH, int(h * scale)))
        gray = cv2.equalizeHist(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY))

        faces = face_cascade.detectMultiScale(
            gray, scaleFactor=1.15, minNeighbors=5, minSize=(50, 50))
        if len(faces) == 0:
            return AWAY

        x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
        # eyes sit in the upper ~60% of the face box
        roi = gray[y:y + int(fh * 0.6), x:x + fw]
        neighbors, _ = SENSITIVITY.get(self.sensitivity, SENSITIVITY[2])
        min_eye = max(8, fw // 9)
        eyes = eye_cascade.detectMultiScale(
            roi, scaleFactor=1.1, minNeighbors=neighbors, minSize=(min_eye, min_eye))
        state = FOCUSED if len(eyes) > 0 else DISTRACTED

        inv = 1.0 / scale
        color = _BOX_COLORS[state]
        p1 = (int(x * inv), int(y * inv))
        p2 = (int((x + fw) * inv), int((y + fh) * inv))
        _draw_corner_box(frame, p1, p2, color)
        for (ex, ey, ew, eh) in eyes[:2]:
            cx = int((x + ex + ew / 2) * inv)
            cy = int((y + ey + eh / 2) * inv)
            cv2.circle(frame, (cx, cy), int(ew * inv / 2.5), color, 2, cv2.LINE_AA)
        return state


def _draw_corner_box(img, p1, p2, color, thickness=3):
    """Draw only the corners of a rectangle, for a cleaner 'tracking' look."""
    (x1, y1), (x2, y2) = p1, p2
    length = max(12, (x2 - x1) // 5)
    for (cx, cy, dx, dy) in ((x1, y1, 1, 1), (x2, y1, -1, 1), (x1, y2, 1, -1), (x2, y2, -1, -1)):
        cv2.line(img, (cx, cy), (cx + dx * length, cy), color, thickness, cv2.LINE_AA)
        cv2.line(img, (cx, cy), (cx, cy + dy * length), color, thickness, cv2.LINE_AA)

"""Reusable, custom-painted widgets: cards, timer ring, charts."""
from __future__ import annotations

from typing import List, Optional, Sequence

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget

from . import theme


def fmt_duration(seconds: float, short: bool = False) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m = rem // 60
    if h:
        return f"{h}h {m:02d}m" if not short else f"{h}h{m:02d}"
    return f"{m}m"


def fmt_clock(seconds: int) -> str:
    m, s = divmod(max(0, int(seconds)), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def label(text: str = "", name: Optional[str] = None, wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    if name:
        lbl.setObjectName(name)
    lbl.setWordWrap(wrap)
    return lbl


def set_chip(lbl: QLabel, text: str, color: str) -> None:
    c = QColor(color)
    lbl.setObjectName("chip")
    lbl.setText(text)
    lbl.setStyleSheet(
        f"color: {color}; background: rgba({c.red()},{c.green()},{c.blue()},0.14);"
        f"border: 1px solid rgba({c.red()},{c.green()},{c.blue()},0.4);"
    )


class Card(QFrame):
    """Rounded panel with an optional title row."""

    def __init__(self, title: str = "", subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(20, 18, 20, 18)
        self.body.setSpacing(12)
        if title:
            self.body.addWidget(label(title, "h2"))
        if subtitle:
            sub = label(subtitle, "muted", wrap=True)
            self.body.addWidget(sub)


class StatCard(Card):
    def __init__(self, title: str, accent: str = theme.ACCENT, parent=None):
        super().__init__(parent=parent)
        self.body.setSpacing(4)
        self._accent = accent
        self.title = label(title.upper(), "faint")
        self.value = label("—", "statValue")
        self.sub = label("", "muted")
        self.body.addWidget(self.title)
        self.body.addWidget(self.value)
        self.body.addWidget(self.sub)
        self.value.setStyleSheet(f"color: {accent};")

    def set(self, value: str, sub: str = "") -> None:
        self.value.setText(value)
        self.sub.setText(sub)


class ProgressRing(QWidget):
    """Big circular countdown display."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.progress = 0.0           # 0..1 elapsed
        self.time_text = "25:00"
        self.caption = "Focus"
        self.footer = ""
        self.color = QColor(theme.ACCENT)
        self.setMinimumSize(280, 280)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def update_state(self, progress: float, time_text: str, caption: str,
                     footer: str, color: str) -> None:
        self.progress = max(0.0, min(1.0, progress))
        self.time_text = time_text
        self.caption = caption
        self.footer = footer
        self.color = QColor(color)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height()) - 24
        rect = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        thickness = max(10.0, side * 0.045)

        # glow + track
        glow = QColor(self.color)
        glow.setAlpha(28)
        p.setPen(QPen(glow, thickness * 2.4, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, 90 * 16, int(-360 * 16 * (1 - self.progress)))
        p.setPen(QPen(QColor(theme.BORDER), thickness, Qt.SolidLine, Qt.RoundCap))
        p.drawEllipse(rect)

        # remaining arc
        if self.progress < 1.0:
            grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            grad.setColorAt(0, self.color.lighter(130))
            grad.setColorAt(1, self.color)
            pen = QPen(grad, thickness, Qt.SolidLine, Qt.RoundCap)
            p.setPen(pen)
            p.drawArc(rect, 90 * 16, int(-360 * 16 * (1 - self.progress)))

        # text
        p.setPen(QColor(theme.TEXT))
        f = QFont(self.font())
        f.setPixelSize(int(side * 0.19))
        f.setWeight(QFont.Bold)
        p.setFont(f)
        p.drawText(rect, Qt.AlignCenter, self.time_text)

        f.setPixelSize(max(12, int(side * 0.055)))
        f.setWeight(QFont.DemiBold)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 2)
        p.setFont(f)
        p.setPen(self.color)
        cap_rect = QRectF(rect.left(), rect.center().y() - side * 0.26, side, side * 0.1)
        p.drawText(cap_rect, Qt.AlignCenter, self.caption.upper())

        f.setLetterSpacing(QFont.AbsoluteSpacing, 0)
        f.setWeight(QFont.Normal)
        p.setFont(f)
        p.setPen(QColor(theme.MUTED))
        foot_rect = QRectF(rect.left(), rect.center().y() + side * 0.15, side, side * 0.1)
        p.drawText(foot_rect, Qt.AlignCenter, self.footer)
        p.end()


class BarChart(QWidget):
    """Vertical bars with labels; the last bar is highlighted."""

    def __init__(self, unit_formatter=None, color: str = theme.ACCENT, parent=None):
        super().__init__(parent)
        self.values: List[float] = []
        self.labels: List[str] = []
        self.goal: Optional[float] = None
        self.color = QColor(color)
        self.fmt = unit_formatter or (lambda v: str(int(v)))
        self.setMinimumHeight(200)

    def set_data(self, values: Sequence[float], labels: Sequence[str],
                 goal: Optional[float] = None) -> None:
        self.values, self.labels, self.goal = list(values), list(labels), goal
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if not self.values:
            return
        top, bottom = 24, 26
        h = self.height() - top - bottom
        w = self.width()
        n = len(self.values)
        vmax = max(max(self.values), self.goal or 0, 1)
        slot = w / n
        bar_w = min(42.0, slot * 0.55)

        if self.goal:
            gy = top + h * (1 - self.goal / vmax)
            pen = QPen(QColor(theme.FAINT), 1, Qt.DashLine)
            p.setPen(pen)
            p.drawLine(QPointF(0, gy), QPointF(w, gy))
            p.drawText(QRectF(0, gy - 18, w - 2, 16), Qt.AlignRight, "goal")

        small = QFont(self.font())
        small.setPixelSize(11)
        p.setFont(small)
        for i, v in enumerate(self.values):
            x = slot * i + (slot - bar_w) / 2
            bh = max(3.0, h * v / vmax) if v > 0 else 3.0
            y = top + h - bh
            col = QColor(self.color)
            if i != n - 1:
                col.setAlpha(140)
            if v <= 0:
                col = QColor(theme.BORDER)
            path = QPainterPath()
            path.addRoundedRect(QRectF(x, y, bar_w, bh), 6, 6)
            p.fillPath(path, col)
            p.setPen(QColor(theme.MUTED))
            if v > 0:
                p.drawText(QRectF(x - 20, y - 18, bar_w + 40, 16), Qt.AlignCenter, self.fmt(v))
            p.setPen(QColor(theme.TEXT if i == n - 1 else theme.MUTED))
            p.drawText(QRectF(slot * i, self.height() - bottom + 6, slot, 18),
                       Qt.AlignCenter, self.labels[i])
        p.end()


class LineChart(QWidget):
    """Percent (0-100) line chart with a gradient fill."""

    def __init__(self, color: str = theme.SUCCESS, show_axis: bool = True,
                 empty_text: str = "No data yet", parent=None):
        super().__init__(parent)
        self.values: List[float] = []
        self.color = QColor(color)
        self.show_axis = show_axis
        self.empty_text = empty_text
        self.max_points: Optional[int] = None
        self.setMinimumHeight(120)

    def set_data(self, values: Sequence[float]) -> None:
        self.values = list(values)
        self.update()

    def append(self, value: float) -> None:
        self.values.append(value)
        if self.max_points and len(self.values) > self.max_points:
            self.values = self.values[-self.max_points:]
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        left = 34 if self.show_axis else 4
        top, right, bottom = 10, 8, 10
        w = self.width() - left - right
        h = self.height() - top - bottom

        small = QFont(self.font())
        small.setPixelSize(11)
        p.setFont(small)
        for pct in (0, 50, 100):
            y = top + h * (1 - pct / 100)
            p.setPen(QPen(QColor(theme.BORDER), 1, Qt.DotLine))
            p.drawLine(QPointF(left, y), QPointF(left + w, y))
            if self.show_axis:
                p.setPen(QColor(theme.FAINT))
                p.drawText(QRectF(0, y - 8, left - 6, 16), Qt.AlignRight | Qt.AlignVCenter,
                           f"{pct}%")

        if len(self.values) < 2:
            p.setPen(QColor(theme.FAINT))
            p.drawText(QRectF(left, top, w, h), Qt.AlignCenter, self.empty_text)
            p.end()
            return

        n = len(self.values)
        pts = [QPointF(left + w * i / (n - 1), top + h * (1 - max(0, min(100, v)) / 100))
               for i, v in enumerate(self.values)]

        line = QPainterPath(pts[0])
        for a, b in zip(pts, pts[1:]):
            mid_x = (a.x() + b.x()) / 2
            line.cubicTo(QPointF(mid_x, a.y()), QPointF(mid_x, b.y()), b)

        fill = QPainterPath(line)
        fill.lineTo(pts[-1].x(), top + h)
        fill.lineTo(pts[0].x(), top + h)
        fill.closeSubpath()
        grad = QLinearGradient(0, top, 0, top + h)
        c1, c2 = QColor(self.color), QColor(self.color)
        c1.setAlpha(90)
        c2.setAlpha(0)
        grad.setColorAt(0, c1)
        grad.setColorAt(1, c2)
        p.fillPath(fill, grad)

        p.setPen(QPen(self.color, 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(line)
        p.setBrush(self.color)
        p.setPen(QPen(QColor(theme.CARD), 2))
        p.drawEllipse(pts[-1], 4.5, 4.5)
        p.end()


class HBarList(QWidget):
    """Horizontal labelled bars, e.g. time per subject."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows: List[tuple] = []   # (label, value, value_text)
        self.palette = [theme.ACCENT, theme.BREAK, theme.SUCCESS, theme.WARNING,
                        theme.DANGER, "#c084fc"]
        self.setMinimumHeight(60)

    def set_rows(self, rows: List[tuple]) -> None:
        self.rows = rows
        self.setMinimumHeight(max(60, 34 * len(rows)))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        small = QFont(self.font())
        small.setPixelSize(12)
        p.setFont(small)
        if not self.rows:
            p.setPen(QColor(theme.FAINT))
            p.drawText(self.rect(), Qt.AlignCenter, "Study a few sessions to see this")
            return
        vmax = max(r[1] for r in self.rows) or 1
        label_w, value_w = 110, 64
        bar_area = self.width() - label_w - value_w
        for i, (name, value, text) in enumerate(self.rows):
            y = i * 34 + 6
            p.setPen(QColor(theme.TEXT))
            p.drawText(QRectF(0, y, label_w - 8, 20), Qt.AlignLeft | Qt.AlignVCenter,
                       p.fontMetrics().elidedText(name, Qt.ElideRight, label_w - 10))
            track = QPainterPath()
            track.addRoundedRect(QRectF(label_w, y + 6, bar_area, 8), 4, 4)
            p.fillPath(track, QColor(theme.BG))
            bar = QPainterPath()
            bar.addRoundedRect(QRectF(label_w, y + 6, max(8, bar_area * value / vmax), 8), 4, 4)
            p.fillPath(bar, QColor(self.palette[i % len(self.palette)]))
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRectF(label_w + bar_area, y, value_w, 20),
                       Qt.AlignRight | Qt.AlignVCenter, text)
        p.end()

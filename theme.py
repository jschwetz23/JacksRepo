"""Colour palette and the global Qt stylesheet."""
from pathlib import Path

ASSETS = (Path(__file__).resolve().parent.parent / "assets").as_posix()

BG = "#0e1016"
SIDEBAR = "#13161f"
CARD = "#181c27"
CARD_HI = "#1f2433"
BORDER = "#262c3d"
TEXT = "#e7e9f0"
MUTED = "#8a91a8"
FAINT = "#5b6178"
ACCENT = "#7c6cff"
ACCENT_HI = "#9286ff"
SUCCESS = "#34d399"
WARNING = "#fbbf24"
DANGER = "#f87171"
BREAK = "#38bdf8"

STYLESHEET = f"""
* {{
    color: {TEXT};
    font-size: 13px;
}}
QMainWindow, QWidget#root {{
    background: {BG};
}}
QWidget#page {{
    background: {BG};
}}
QFrame#sidebar {{
    background: {SIDEBAR};
    border-right: 1px solid {BORDER};
}}
QLabel#brand {{
    font-size: 20px;
    font-weight: 700;
    padding: 4px 8px;
}}
QLabel#brandSub {{
    color: {MUTED};
    padding: 0 8px 12px 8px;
    font-size: 11px;
}}
QPushButton#nav {{
    background: transparent;
    border: none;
    border-radius: 10px;
    padding: 10px 14px;
    text-align: left;
    color: {MUTED};
    font-size: 14px;
    font-weight: 600;
}}
QPushButton#nav:hover {{
    background: {CARD};
    color: {TEXT};
}}
QPushButton#nav:checked {{
    background: {CARD_HI};
    color: {TEXT};
    border-left: 3px solid {ACCENT};
}}
QFrame#card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 16px;
}}
QLabel#h1 {{
    font-size: 26px;
    font-weight: 700;
}}
QLabel#h2 {{
    font-size: 15px;
    font-weight: 700;
}}
QLabel#muted {{
    color: {MUTED};
}}
QLabel#faint {{
    color: {FAINT};
    font-size: 11px;
}}
QLabel#statValue {{
    font-size: 26px;
    font-weight: 700;
}}
QLabel#bigPercent {{
    font-size: 44px;
    font-weight: 800;
}}
QLabel#chip {{
    border-radius: 11px;
    padding: 3px 10px;
    font-weight: 600;
    font-size: 12px;
}}
QLabel#banner {{
    background: rgba(251, 191, 36, 0.12);
    border: 1px solid rgba(251, 191, 36, 0.45);
    color: {WARNING};
    border-radius: 12px;
    padding: 10px 14px;
    font-weight: 600;
}}
QLabel#cameraView {{
    background: #0a0c11;
    border-radius: 12px;
    color: {FAINT};
}}

QPushButton {{
    background: {CARD_HI};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 8px 16px;
    font-weight: 600;
}}
QPushButton:hover {{
    border-color: {ACCENT};
}}
QPushButton:disabled {{
    color: {FAINT};
    border-color: {BORDER};
}}
QPushButton[variant="primary"] {{
    background: {ACCENT};
    border: none;
    color: white;
}}
QPushButton[variant="primary"]:hover {{
    background: {ACCENT_HI};
}}
QPushButton[variant="danger"]:hover {{
    border-color: {DANGER};
    color: {DANGER};
}}
QPushButton[variant="round"] {{
    border-radius: 24px;
    min-width: 48px; max-width: 48px;
    min-height: 48px; max-height: 48px;
    padding: 0;
    font-size: 18px;
}}
QPushButton[variant="play"] {{
    background: {ACCENT};
    border: none;
    color: white;
    border-radius: 32px;
    min-width: 140px;
    min-height: 64px;
    font-size: 18px;
    font-weight: 700;
}}
QPushButton[variant="play"]:hover {{
    background: {ACCENT_HI};
}}
QPushButton#pill {{
    background: transparent;
    border: 1px solid {BORDER};
    border-radius: 14px;
    min-height: 28px;
    max-height: 28px;
    padding: 0 14px;
    color: {MUTED};
}}
QPushButton#pill:checked {{
    background: {CARD_HI};
    border-color: {ACCENT};
    color: {TEXT};
}}

QLineEdit, QPlainTextEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {{
    background: {BG};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 7px 10px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QDateEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down, QDateEdit::drop-down {{
    border: none;
    width: 26px;
}}
QComboBox::down-arrow, QDateEdit::down-arrow {{
    image: url({ASSETS}/chevron.svg);
    width: 12px;
    height: 12px;
}}
QComboBox QAbstractItemView {{
    background: {CARD};
    border: 1px solid {BORDER};
    selection-background-color: {CARD_HI};
    outline: none;
}}
QCheckBox {{
    spacing: 8px;
}}
QCheckBox::indicator, QTableWidget::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 5px;
    border: 1px solid {FAINT};
    background: {BG};
}}
QCheckBox::indicator:hover, QTableWidget::indicator:hover {{
    border-color: {ACCENT};
}}
QCheckBox::indicator:checked, QTableWidget::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
    image: url({ASSETS}/check.svg);
}}

QTableWidget {{
    background: transparent;
    border: none;
    gridline-color: transparent;
    selection-background-color: {CARD_HI};
    selection-color: {TEXT};
    outline: none;
}}
QTableWidget::item {{
    padding: 6px;
    border-bottom: 1px solid {BORDER};
}}
QHeaderView {{
    background: transparent;
    border: none;
}}
QHeaderView::section {{
    background: transparent;
    color: {MUTED};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 8px 6px;
    font-weight: 600;
    font-size: 12px;
}}
QTableCornerButton::section {{
    background: transparent;
    border: none;
}}
QProgressBar {{
    background: {BG};
    border: none;
    border-radius: 4px;
    max-height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 4px;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QToolTip {{
    background: {CARD_HI};
    border: 1px solid {BORDER};
    color: {TEXT};
    padding: 6px;
}}
QCalendarWidget QWidget {{
    alternate-background-color: {CARD};
}}
"""

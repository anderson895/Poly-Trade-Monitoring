"""Dark theme (QSS) — pattern sa PolyTrade Pro mockup."""

# Palette
BG = "#0b0f1a"
CARD = "#111827"
BORDER = "#1f2937"
INPUT_BG = "#0d1424"
TEXT = "#e5e7eb"
MUTED = "#9ca3af"
ACCENT = "#6366f1"
ACCENT_DIM = "#1e1b4b"
GREEN = "#22c55e"
RED = "#ef4444"
AMBER = "#f59e0b"
BTC_BLUE = "#3b82f6"

STYLESHEET = f"""
QMainWindow, QWidget {{
    background: {BG};
    color: {TEXT};
    font-family: 'Segoe UI';
    font-size: 13px;
}}
QLabel {{ background: transparent; border: none; }}
QLabel[muted="true"] {{ color: {MUTED}; }}
QLabel[h1="true"] {{ font-size: 26px; font-weight: bold; }}
QLabel[h2="true"] {{ font-size: 16px; font-weight: bold; }}
QLabel[accent="true"] {{ color: {ACCENT}; font-weight: bold; font-size: 14px; }}

QFrame[card="true"] {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

QListWidget#sidebar {{
    background: {BG};
    border: none;
    outline: none;
    font-size: 14px;
}}
QListWidget#sidebar::item {{
    padding: 10px 14px;
    border-radius: 6px;
    margin: 2px 8px;
    color: {MUTED};
}}
QListWidget#sidebar::item:hover {{ background: {CARD}; }}
QListWidget#sidebar::item:selected {{
    background: {ACCENT_DIM};
    color: #c7d2fe;
}}

QPushButton {{
    background: {BORDER};
    border: 1px solid #374151;
    border-radius: 6px;
    padding: 8px 14px;
    color: {TEXT};
}}
QPushButton:hover {{ background: #374151; }}
QPushButton:disabled {{ color: #6b7280; }}
QPushButton#startBtn {{
    background: #16a34a; color: white;
    font-weight: bold; font-size: 15px; padding: 10px 28px;
    border: none;
}}
QPushButton#startBtn:hover {{ background: {GREEN}; }}
QPushButton#startBtn:disabled {{ background: #14532d; color: {MUTED}; }}
QPushButton#stopBtn {{
    background: transparent; color: {RED};
    border: 1px solid {RED};
    font-weight: bold; font-size: 15px; padding: 10px 28px;
}}
QPushButton#stopBtn:hover {{ background: #7f1d1d; }}
QPushButton#stopBtn:disabled {{ border-color: #7f1d1d; color: #7f1d1d; }}
QPushButton#accentBtn {{ background: {ACCENT}; color: white; border: none; }}
QPushButton#accentBtn:hover {{ background: #818cf8; }}

QComboBox {{
    background: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px;
    color: {TEXT};
}}
QComboBox QAbstractItemView {{
    background: {CARD};
    border: 1px solid {BORDER};
    color: {TEXT};
    selection-background-color: {ACCENT_DIM};
}}

QLineEdit, QDoubleSpinBox, QSpinBox {{
    background: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px;
    color: {TEXT};
}}
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus {{ border-color: {ACCENT}; }}

QTableWidget {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: {BORDER};
}}
QTableWidget::item {{ padding: 4px; }}
QHeaderView::section {{
    background: {INPUT_BG};
    border: none;
    padding: 8px;
    color: {MUTED};
    font-weight: bold;
}}
QListWidget {{ background: {CARD}; border: none; border-radius: 8px; }}
QToolButton {{ background: transparent; border: none; color: {MUTED}; font-size: 14px; }}
QToolButton:hover {{ color: {TEXT}; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {BORDER}; border-radius: 4px;
    background: {INPUT_BG};
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

QScrollBar:vertical {{
    background: {BG}; width: 10px; border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    background: #374151; border-radius: 5px; min-height: 24px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""

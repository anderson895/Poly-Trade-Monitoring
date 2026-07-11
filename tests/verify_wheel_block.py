"""One-off: naka-block ba ang mouse wheel sa spinboxes/dropdowns?"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

from src.core.engine import BotEngine  # noqa: E402
from src.storage.db import Database  # noqa: E402
from src.ui.main_window import MainWindow  # noqa: E402

db = Database()
engine = BotEngine(db)
window = MainWindow(engine, db)


def wheel(widget) -> None:
    ev = QWheelEvent(
        QPointF(10, 10), QPointF(100, 100), QPoint(0, 120), QPoint(0, 120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase, False,
    )
    app.sendEvent(widget, ev)


risk_before = window.settings._risk.value()
wheel(window.settings._risk)
risk_after = window.settings._risk.value()
print(f"[{'OK' if risk_before == risk_after else 'FAIL'}] Risk USDC: "
      f"{risk_before} -> {risk_after} (dapat WALANG pagbabago sa wheel)")

mode_before = window.settings._mode.currentIndex()
wheel(window.settings._mode)
mode_after = window.settings._mode.currentIndex()
print(f"[{'OK' if mode_before == mode_after else 'FAIL'}] Trading Mode: "
      f"index {mode_before} -> {mode_after} (dapat WALANG pagbabago)")

tf_before = window.dash._window_combo.currentIndex()
wheel(window.dash._window_combo)
tf_after = window.dash._window_combo.currentIndex()
print(f"[{'OK' if tf_before == tf_after else 'FAIL'}] Time filter combo: "
      f"index {tf_before} -> {tf_after} (dapat WALANG pagbabago)")

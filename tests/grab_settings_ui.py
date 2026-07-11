"""One-off visual check: i-render ang Settings page at i-save bilang PNG
(walang interaction na kailangan — QWidget.grab()).

Run:  .\\venv\\Scripts\\python.exe -m tests.grab_settings_ui
"""
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

from src.core.engine import BotEngine  # noqa: E402
from src.storage.db import Database  # noqa: E402
from src.ui.main_window import MainWindow  # noqa: E402

db = Database()
engine = BotEngine(db)
window = MainWindow(engine, db)
window.resize(1600, 900)
window._nav.setCurrentRow(1)  # Settings page
window.show()


def snap() -> None:
    window.grab().save("data/settings_ui.png")
    print("[OK] saved data/settings_ui.png")
    app.quit()


QTimer.singleShot(600, snap)
app.exec()

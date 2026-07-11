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
    window.settings._mode.setCurrentIndex(0)  # Paper
    window.grab().save("data/settings_paper.png")
    hidden = not window.settings._pm_funder.isVisible()
    print(f"[{'OK' if hidden else 'FAIL'}] Paper mode: nakatago ang "
          "live fields (Private Key/Funder/Sign-up)")
    window.settings._mode.setCurrentIndex(1)  # Live
    window.grab().save("data/settings_live.png")
    shown = window.settings._pm_funder.isVisible()
    paper_hidden = not window.settings._paper_start.isVisible()
    print(f"[{'OK' if shown else 'FAIL'}] Live mode: kita ang live fields")
    print(f"[{'OK' if paper_hidden else 'FAIL'}] Live mode: nakatago ang "
          "Paper Starting Balance")
    window.settings._mode.setCurrentIndex(0)  # ibalik sa Paper
    print("[OK] saved data/settings_paper.png + settings_live.png")
    app.quit()


QTimer.singleShot(600, snap)
app.exec()

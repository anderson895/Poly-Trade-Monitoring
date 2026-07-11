"""One-off check: pagkatapos mag-Save Settings, lumalabas ba ang
credential verification notification? (totoong Polymarket network)

Run:  .\\venv\\Scripts\\python.exe -m tests.verify_save_check
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import truststore  # noqa: E402

truststore.inject_into_ssl()

from src.core.netdns import install_doh_resolver  # noqa: E402

install_doh_resolver()

import asyncio  # noqa: E402

import qasync  # noqa: E402
from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
loop = qasync.QEventLoop(app)
asyncio.set_event_loop(loop)

from src.core.engine import BotEngine  # noqa: E402
from src.storage.db import Database  # noqa: E402
from src.ui.main_window import MainWindow  # noqa: E402

db = Database()
engine = BotEngine(db)
window = MainWindow(engine, db)
window._nav.setCurrentRow(1)  # Settings page
window.show()


def do_save() -> None:
    print("--- clicking Save Settings ---")
    window.settings._save()
    print(f"status agad: {window.settings._status.text()!r}")
    QTimer.singleShot(20_000, report)


def report() -> None:
    text = window.settings._status.text()
    ok = "credentials OK" in text
    print(f"[{'OK' if ok else 'FAIL'}] final status: {text!r}")
    app.quit()


QTimer.singleShot(1_000, do_save)
with loop:
    loop.run_forever()

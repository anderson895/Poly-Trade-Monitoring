"""PolyTrade Bot — entry point.

Run:  .\\venv\\Scripts\\python.exe -m src.main
"""
from __future__ import annotations

import asyncio
import sys

import truststore

truststore.inject_into_ssl()  # gamitin ang Windows cert store para sa TLS

import qasync
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from src.core.applog import asyncio_exception_handler, setup_logging
from src.core.engine import BotEngine
from src.storage.db import Database
from src.ui.main_window import MainWindow


def main() -> None:
    setup_logging()  # lahat ng errors -> data/app.log

    app = QApplication(sys.argv)
    app.setApplicationName("PolyTrade Bot")

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    loop.set_exception_handler(asyncio_exception_handler)

    db = Database()
    engine = BotEngine(db)
    window = MainWindow(engine, db)
    window.showMaximized()  # default: fullscreen/maximized pag-open

    # I-defer ang startup hanggang tumatakbo na ang event loop
    # (kailangan ng asyncio.create_task ng running loop)
    def _on_loop_started() -> None:
        engine.start_monitors()
        engine.log("INFO", "Application started")

    QTimer.singleShot(0, _on_loop_started)

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()

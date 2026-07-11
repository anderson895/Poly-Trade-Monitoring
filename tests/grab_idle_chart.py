"""One-off visual check: dapat gumagalaw ang LIVE chart kahit hindi
naka-START ang bot (totoong Binance WS, kaya kailangan ng internet).

Run:  .\\venv\\Scripts\\python.exe -m tests.grab_idle_chart
"""
import sys

import truststore

truststore.inject_into_ssl()

from src.core.netdns import install_doh_resolver  # noqa: E402

install_doh_resolver()

import asyncio  # noqa: E402

import qasync  # noqa: E402
from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from src.core.engine import BotEngine  # noqa: E402
from src.storage.db import Database  # noqa: E402
from src.ui.main_window import MainWindow  # noqa: E402

app = QApplication(sys.argv)
loop = qasync.QEventLoop(app)
asyncio.set_event_loop(loop)

db = Database()
engine = BotEngine(db)
window = MainWindow(engine, db)
window.resize(1600, 900)
window.show()


def _span_days() -> tuple[float, bool, int]:
    times = list(window.dash.chart._times)
    span = (times[-1] - times[0]) / 86400 if len(times) > 1 else 0
    monotonic = all(a <= b for a, b in zip(times, times[1:]))
    return span, monotonic, len(times)


def snap() -> None:
    import time
    n = len(window.dash.chart._prices)
    times = list(window.dash.chart._times)
    monotonic = all(a <= b for a, b in zip(times, times[1:]))
    no_future = not times or times[-1] <= time.time() + 1
    window.grab().save("data/idle_chart.png")
    # Dapat >100 points agad dahil sa 2h history prefill (120 x 1m klines)
    print(f"[{'OK' if n >= 100 else 'FAIL'}] points habang STOPPED: {n} "
          f"(bot state: {engine.state.value})")
    print(f"[{'OK' if monotonic else 'FAIL'}] monotonic timestamps "
          f"(walang gulo sa linya)")
    print(f"[{'OK' if no_future else 'FAIL'}] walang future points")
    # Subukan ang YTD Time filter
    window.dash._window_combo.setCurrentIndex(6)  # YTD
    QTimer.singleShot(6_000, check_ytd)


def check_ytd() -> None:
    span, monotonic, n = _span_days()
    # 2026-07-11 → ~190 araw mula Enero 1
    print(f"[{'OK' if span >= 180 else 'FAIL'}] YTD: span = {span:.0f} days "
          f"({n} points, monotonic: {monotonic})")
    ylo, yhi = window.dash.chart.getViewBox().viewRange()[1]
    # Dapat naka-fit sa YTD data (~57k-96k), hindi bumababa sa 0
    print(f"[{'OK' if ylo > 30000 else 'FAIL'}] y-range fits data: "
          f"[{ylo:,.0f}, {yhi:,.0f}]")
    window.grab().save("data/ytd_chart.png")
    window.dash._window_combo.setCurrentIndex(7)  # All
    QTimer.singleShot(6_000, check_all)


def check_all() -> None:
    span, monotonic, n = _span_days()
    print(f"[{'OK' if span >= 365 else 'FAIL'}] All: span = {span:.0f} days "
          f"({n} points, monotonic: {monotonic})")
    window.grab().save("data/all_chart.png")
    app.quit()


def begin() -> None:
    engine.start_monitors()  # feed + monitors LANG — walang START
    QTimer.singleShot(15_000, snap)


QTimer.singleShot(0, begin)
with loop:
    loop.run_forever()

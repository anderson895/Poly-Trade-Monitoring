"""One-off debug: bakit sira ang 1W view (diagonal + kulang ang data)?"""
import sys

import truststore

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
window.resize(1600, 900)
window.show()

window.dash.rangeRequested.connect(
    lambda i, n: print(f"rangeRequested: {i} x{n}")
)
engine.rangeHistoryLoaded.connect(
    lambda rows: print(f"rangeHistoryLoaded: {len(rows)} rows, "
                       f"span {(rows[-1][0]-rows[0][0])/86400:.1f}d")
)


def select_all() -> None:
    print("--- selecting ALL muna (weekly 2017+ data) ---")
    window.dash._window_combo.setCurrentIndex(7)
    QTimer.singleShot(8_000, select_1w)


def select_1w() -> None:
    print("--- tapos 1W (ang sequence na sumisira dati) ---")
    window.dash._window_combo.setCurrentIndex(5)
    QTimer.singleShot(8_000, report)


def report() -> None:
    import time
    c = window.dash.chart
    times = list(c._times)
    prices = list(c._prices)
    mono = all(a <= b for a, b in zip(times, times[1:]))
    now = time.time()
    # Ang mahalaga: may HOURLY data ba sa loob ng 1W window?
    week = [t for t in times if t >= now - 7 * 86400]
    week_gaps = [week[i + 1] - week[i] for i in range(len(week) - 1)]
    max_gap_h = max(week_gaps) / 3600 if week_gaps else 999
    print(f"total points: {len(times)}, monotonic: {mono}")
    print(f"points sa loob ng 1W window: {len(week)}")
    print(f"[{'OK' if len(week) >= 150 else 'FAIL'}] buo ang linggo "
          f"(hourly data merged kahit na-All muna)")
    print(f"[{'OK' if max_gap_h <= 2.5 else 'FAIL'}] max gap sa window: "
          f"{max_gap_h:.1f}h (dapat ~1h — walang diagonal)")
    ylo, yhi = c.getViewBox().viewRange()[1]
    print(f"[{'OK' if yhi - ylo > 800 else 'FAIL'}] y-range = buong linggo: "
          f"[{ylo:,.0f}, {yhi:,.0f}]")
    window.grab().save("data/debug_1w.png")
    app.quit()


def begin() -> None:
    engine.start_monitors()
    QTimer.singleShot(12_000, select_all)


QTimer.singleShot(0, begin)
with loop:
    loop.run_forever()

"""One-off visual check: i-render ang Dashboard chart na may simulated
na daily open + presyo + 1m klines (OHLCV), tapos i-save bilang PNG.

Run:  .\\venv\\Scripts\\python.exe -m tests.grab_chart_ui
"""
import math
import random
import sys
import time as real_time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

from src.core.engine import BotEngine  # noqa: E402
from src.storage.db import Database  # noqa: E402
from src.ui import chart as chart_mod  # noqa: E402
from src.ui.main_window import MainWindow  # noqa: E402

db = Database()
db.set_setting("chart_type", "line")  # simulan sa Line para sa unang snaps
engine = BotEngine(db)
window = MainWindow(engine, db)
window.resize(1600, 900)
window._nav.setCurrentRow(0)  # Dashboard
window.show()

# Simulate: ~60 minuto ng 1m klines (OHLCV) + live ticks sa dulo
OPEN = 64161.72
rng = random.Random(7)
N_MIN = 60
BASE = int(real_time.time() // 60) * 60 - N_MIN * 60

rows = []
price = OPEN + 40
for i in range(N_MIN):
    o = price
    drift = 30 * math.sin(i / 9) + rng.uniform(-14, 14)
    c = o + drift
    h = max(o, c) + rng.uniform(1, 12)
    l = min(o, c) - rng.uniform(1, 12)
    v = rng.uniform(4, 30) * (1.6 if abs(drift) > 20 else 1.0)
    rows.append((BASE + i * 60, o, h, l, c, v))
    price = c

window.dash.load_history(rows)

# Live ticks para sa line chart (fake timestamps sa dulo ng history)
_i = {"n": 0}
chart_mod.time.time = lambda: BASE + N_MIN * 60 + _i["n"]
for i in range(30):
    _i["n"] = i
    window.dash.update_price(price + 4 * math.sin(i / 4))
chart_mod.time.time = real_time.time


def snap_price_view() -> None:
    window.grab().save("data/chart_price_view.png")
    print("[OK] saved data/chart_price_view.png")
    window.dash._type_combo.setCurrentIndex(1)  # Candles (may volume pane)
    # Live kline update sa huling candle
    t, o, h, l, c, v = rows[-1]
    window.dash.update_candle((t, o, h, l, c + 8, v + 5))
    QTimer.singleShot(700, snap_candles)


def snap_candles() -> None:
    window.grab().save("data/chart_candles.png")
    print("[OK] saved data/chart_candles.png")
    db.set_setting("chart_type", "line")  # ibalik para sa totoong user run
    app.quit()


QTimer.singleShot(700, snap_price_view)
app.exec()

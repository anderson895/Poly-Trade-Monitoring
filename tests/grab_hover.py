"""One-off check: gumagana ba ang hover crosshair sa line chart?

Sine-simulate ang mouse position sa ibabaw ng isang kilalang point at
chine-check na tama ang ipinapakitang presyo.

Run:  .\\venv\\Scripts\\python.exe -m tests.grab_hover
"""
import math
import sys
import time as real_time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PySide6.QtCore import QPointF, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

from src.ui import chart as chart_mod  # noqa: E402
from src.ui.chart import PriceChart  # noqa: E402

chart = PriceChart()
chart.resize(1400, 500)

BASE = real_time.time() - 600
_i = {"n": 0}
chart_mod.time.time = lambda: BASE + _i["n"]
prices = []
for i in range(600):
    _i["n"] = i
    p = 64150 + 40 * math.sin(i / 60)
    prices.append(p)
    chart.add_point(p)
chart_mod.time.time = real_time.time
chart.show()


def check() -> None:
    # I-hover sa point index 300 (kilalang presyo)
    target_t = BASE + 300
    target_p = prices[300]
    vb = chart.getViewBox()
    scene_pos = vb.mapViewToScene(QPointF(target_t, target_p))
    chart._on_mouse_moved(scene_pos)

    label = chart._hover_label.toPlainText()
    shown = chart._hover_label.isVisible() and chart._cross_v.isVisible()
    expect = f"{target_p:,.2f}"
    print(f"[{'OK' if shown else 'FAIL'}] crosshair + label lumabas sa hover")
    print(f"[{'OK' if expect in label else 'FAIL'}] tamang presyo sa label: "
          f"{label!r} (expected ${expect})")
    chart.grab().save("data/hover_check.png")

    # Paglabas ng mouse sa chart -> dapat mawala
    outside = vb.mapViewToScene(QPointF(target_t, target_p))
    outside.setX(-100)
    chart._on_mouse_moved(outside)
    hidden = not chart._hover_label.isVisible()
    print(f"[{'OK' if hidden else 'FAIL'}] nawawala kapag labas sa chart")
    app.quit()


QTimer.singleShot(700, check)
app.exec()

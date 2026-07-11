"""Live BTC price chart (pyqtgraph) — dark style, trading-app look.

Mga elemento:
- Blue line na may gradient fill : live BTC price
- Price badge (kanan)            : kasalukuyang presyo, naka-highlight
- Y-axis sa KANAN (gaya ng trading apps), oras sa baba
- Time filter (1s-All) sa dashboard header
"""
from __future__ import annotations

import time
from collections import deque

import pyqtgraph as pg
from PySide6.QtGui import QColor

from src.ui import theme

MAX_POINTS = 20000  # live ticks + on-demand history (hanggang 1W view)


class PriceChart(pg.PlotWidget):
    def __init__(self) -> None:
        super().__init__(axisItems={"bottom": pg.DateAxisItem()})
        self.setBackground(theme.CARD)
        self.setMinimumHeight(220)
        self.showGrid(x=True, y=True, alpha=0.15)
        self.setMouseEnabled(x=True, y=False)
        # Y-axis sa KANAN gaya ng trading apps
        self.hideAxis("left")
        self.showAxis("right")
        self.getAxis("right").setWidth(86)

        self._times: deque[float] = deque(maxlen=MAX_POINTS)
        self._prices: deque[float] = deque(maxlen=MAX_POINTS)
        self._window_secs: int | None = 15 * 60  # default: last 15 min

        # Gradient fill sa ilalim ng price line
        fill = QColor(theme.BTC_BLUE)
        fill.setAlpha(38)
        self._curve = self.plot(
            pen=pg.mkPen(theme.BTC_BLUE, width=2), brush=fill, fillLevel=0
        )

        # Current price badge sa kanang gilid (walang linya, badge lang)
        self._price_marker = pg.InfiniteLine(
            angle=0, pen=pg.mkPen(None),
            label="", labelOpts={
                "position": 0.997,
                "color": "#ffffff",
                "fill": pg.mkBrush(theme.BTC_BLUE),
                "anchors": [(1, 0.5), (1, 0.5)],
            },
        )
        self._price_marker.hide()
        self.addItem(self._price_marker, ignoreBounds=True)

        # Y auto-range batay sa NAKIKITANG data lang (visible x window)
        self.getViewBox().setAutoVisible(y=True)

    # ------------------------------------------------------------------ API

    def load_history(self, rows: list) -> None:
        """Prefill mula 1m klines: (ts, o, h, l, c) — close prices ang guhit.

        Inilalagay ang history BAGO ang anumang live ticks na nauna nang
        dumating, para tuloy-tuloy ang linya.
        """
        live_times = list(self._times)
        live_prices = list(self._prices)
        first_live = live_times[0] if live_times else float("inf")
        now = time.time()
        self._times.clear()
        self._prices.clear()
        for t, _o, _h, _l, close, _v in rows:
            # t = OPEN time ng candle — interval-agnostic at laging monotonic.
            # t <= now: huwag tanggapin ang future points — gumugulo sila sa
            # linya kapag humalo sa live ticks
            if t < first_live and t <= now:
                self._times.append(t)
                self._prices.append(close)
        for t, p in zip(live_times, live_prices):
            self._times.append(t)
            self._prices.append(p)
        if self._prices:
            self._curve.setData(list(self._times), list(self._prices))
            self._apply_x_window()

    def add_point(self, price: float) -> None:
        self._times.append(time.time())
        self._prices.append(price)
        self._curve.setData(list(self._times), list(self._prices))

        self._price_marker.setValue(price)
        self._price_marker.show()
        # setFormat (hindi setText): ang InfLineLabel ay nagre-re-render mula
        # sa format string sa bawat galaw/range change — buburahin nito ang
        # setText, kaya ang format mismo ang lagyan ng final na text
        self._price_marker.label.setFormat(f"{price:,.2f}")

        self._apply_x_window()

    def set_window_minutes(self, minutes: int | None) -> None:
        """Ipakita ang huling N minuto lang; None = lahat ng data."""
        self._window_secs = None if minutes is None else minutes * 60
        self._apply_x_window()

    # -------------------------------------------------------------- helpers

    def _apply_x_window(self) -> None:
        """Laging sumunod sa pinakabagong presyo (auto-follow).

        Tinatawag ito kada tick — kahit na-drag/na-zoom ng mouse ang view,
        babalik ito sa tamang window sa susunod na update, para hindi
        maiwang 'nakapako' ang chart.
        """
        if not self._times:
            return
        now = self._times[-1]
        start = self._times[0] if self._window_secs is None else now - self._window_secs
        self.setXRange(start, now, padding=0.02)

        # Ang gradient fill ay hanggang sa ibaba ng NAKIKITANG data lang —
        # kung global min ang gamit, ang lumang history (hal. $3k noong 2017
        # mula sa All view) ay hihilain pababa ang y-axis ng ibang windows.
        visible = [p for t, p in zip(self._times, self._prices) if t >= start]
        if visible:
            span = max(visible) - min(visible)
            self._curve.setFillLevel(min(visible) - max(span * 0.02, 2))

    def clear_data(self) -> None:
        self._times.clear()
        self._prices.clear()
        self._curve.setData([], [])
        self._price_marker.hide()

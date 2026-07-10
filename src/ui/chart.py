"""Live BTC price chart (pyqtgraph) — dark style, may strategy bands.

Mga guhit:
- Blue line  : live BTC price
- Mean       : daily open / 00:00 UTC ("Price to Beat"), gray dashed
- Upper Band : open × (1 + entry stretch %), red dashed — entry zone pataas
- Lower Band : open × (1 − entry stretch %), green dashed — entry zone pababa
"""
from __future__ import annotations

import time
from collections import deque

import pyqtgraph as pg
from PySide6.QtCore import Qt

from src.ui import theme

MAX_POINTS = 7200  # ~2 oras ng data sa ~1 update/segundo


def _dashed(color: str) -> pg.mkPen:
    return pg.mkPen(color, width=1, style=Qt.PenStyle.DashLine)


class PriceChart(pg.PlotWidget):
    def __init__(self) -> None:
        super().__init__(axisItems={"bottom": pg.DateAxisItem()})
        self.setBackground(theme.CARD)
        self.setMinimumHeight(220)
        self.showGrid(x=True, y=True, alpha=0.15)
        self.setMouseEnabled(x=True, y=False)
        self.getAxis("left").setWidth(72)

        self._times: deque[float] = deque(maxlen=MAX_POINTS)
        self._prices: deque[float] = deque(maxlen=MAX_POINTS)

        self._curve = self.plot(pen=pg.mkPen(theme.BTC_BLUE, width=2))

        label_opts = {"position": 0.03, "color": theme.MUTED}
        self._mean = pg.InfiniteLine(
            angle=0, pen=_dashed(theme.MUTED),
            label="Mean {value:,.0f}", labelOpts=label_opts,
        )
        self._upper = pg.InfiniteLine(
            angle=0, pen=_dashed(theme.RED),
            label="Upper {value:,.0f}", labelOpts={**label_opts, "color": theme.RED},
        )
        self._lower = pg.InfiniteLine(
            angle=0, pen=_dashed(theme.GREEN),
            label="Lower {value:,.0f}", labelOpts={**label_opts, "color": theme.GREEN},
        )
        for line in (self._mean, self._upper, self._lower):
            line.hide()
            self.addItem(line)

    def add_point(self, price: float) -> None:
        self._times.append(time.time())
        self._prices.append(price)
        self._curve.setData(list(self._times), list(self._prices))

    def set_bands(self, open_price: float, entry_stretch_pct: float) -> None:
        """Mean = daily open; bands = entry threshold ng strategy."""
        self._mean.setValue(open_price)
        self._upper.setValue(open_price * (1 + entry_stretch_pct / 100))
        self._lower.setValue(open_price * (1 - entry_stretch_pct / 100))
        for line in (self._mean, self._upper, self._lower):
            line.show()

    def clear_data(self) -> None:
        self._times.clear()
        self._prices.clear()
        self._curve.setData([], [])

"""Binance read-only BTC price feed.

Streams real-time BTCUSDT price via public WebSocket (walang API key na
kailangan para sa public market data) at kinukuha ang Daily Open Price
(00:00 UTC) via REST klines. Awtomatikong nagre-reconnect at nagre-refresh
ng daily open kapag nag-rollover ang UTC day.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
from typing import Awaitable, Callable, Optional

import httpx
import websockets

filelog = logging.getLogger("polytrade.binance")

BINANCE_WS_URL = "wss://stream.binance.com:9443/ws/btcusdt@miniTicker"
BINANCE_REST_URL = "https://api.binance.com"

PriceCallback = Callable[[float], None]
OpenCallback = Callable[[float], None]
StatusCallback = Callable[[bool], None]


class BinanceFeed:
    """Real-time BTCUSDT feed with daily-open (00:00 UTC) tracking."""

    def __init__(
        self,
        on_price: PriceCallback,
        on_daily_open: OpenCallback,
        on_status: StatusCallback,
    ) -> None:
        self._on_price = on_price
        self._on_daily_open = on_daily_open
        self._on_status = on_status
        self._task: Optional[asyncio.Task] = None
        self._current_utc_date: Optional[dt.date] = None
        self.last_price: Optional[float] = None
        self.daily_open: Optional[float] = None
        self.hourly_volumes: list[float] = []  # completed 1h candles, oldest->newest
        self._volumes_fetched_at: float = 0.0

    # ------------------------------------------------------------------ API

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="binance-feed")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._on_status(False)

    @property
    def pct_from_open(self) -> Optional[float]:
        """% distance ng current price mula sa daily open (stretch)."""
        if self.last_price is None or not self.daily_open:
            return None
        return (self.last_price - self.daily_open) / self.daily_open * 100.0

    # ------------------------------------------------------------- internals

    async def _run(self) -> None:
        while True:
            try:
                await self._refresh_daily_open()
                await self._refresh_volumes()
                async with websockets.connect(BINANCE_WS_URL, ping_interval=20) as ws:
                    self._on_status(True)
                    async for raw in ws:
                        msg = json.loads(raw)
                        price = float(msg["c"])
                        self.last_price = price
                        self._on_price(price)
                        await self._check_day_rollover()
                        await self._maybe_refresh_volumes()
            except asyncio.CancelledError:
                raise
            except Exception:
                filelog.exception("Binance feed error (magre-reconnect sa 5s):")
                self._on_status(False)
                await asyncio.sleep(5)  # backoff bago mag-reconnect

    async def _refresh_daily_open(self) -> None:
        """Kunin ang open ng kasalukuyang 1d UTC candle (ang 'Price to Beat')."""
        async with httpx.AsyncClient(base_url=BINANCE_REST_URL, timeout=10) as client:
            resp = await client.get(
                "/api/v3/klines",
                params={"symbol": "BTCUSDT", "interval": "1d", "limit": 1},
            )
            resp.raise_for_status()
            kline = resp.json()[0]
            self.daily_open = float(kline[1])  # index 1 = open price
            self._current_utc_date = dt.datetime.now(dt.timezone.utc).date()
            self._on_daily_open(self.daily_open)

    async def _check_day_rollover(self) -> None:
        today = dt.datetime.now(dt.timezone.utc).date()
        if self._current_utc_date is not None and today != self._current_utc_date:
            await self._refresh_daily_open()

    async def _refresh_volumes(self) -> None:
        """Kunin ang hourly volumes para sa volume escalation filter.

        Kinukuha ang 25 candles tapos tinatanggal ang huli (in-progress pa),
        para completed hours lang ang ginagamit sa comparison.
        """
        async with httpx.AsyncClient(base_url=BINANCE_REST_URL, timeout=10) as client:
            resp = await client.get(
                "/api/v3/klines",
                params={"symbol": "BTCUSDT", "interval": "1h", "limit": 25},
            )
            resp.raise_for_status()
            klines = resp.json()
            self.hourly_volumes = [float(k[5]) for k in klines[:-1]]  # index 5 = volume
            self._volumes_fetched_at = dt.datetime.now(dt.timezone.utc).timestamp()

    async def _maybe_refresh_volumes(self) -> None:
        now = dt.datetime.now(dt.timezone.utc).timestamp()
        if now - self._volumes_fetched_at >= 300:  # kada 5 minuto
            await self._refresh_volumes()

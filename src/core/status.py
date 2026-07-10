"""Periodic connection checks: Internet, Binance, Polymarket.

Bawat 15 segundo, chine-check kung reachable ang bawat service,
tapos ini-report sa UI via callback.
"""
from __future__ import annotations

import asyncio
from typing import Callable, Optional

import httpx

CHECK_INTERVAL = 15  # seconds

INTERNET_URL = "https://1.1.1.1"                       # Cloudflare - internet check
BINANCE_URL = "https://api.binance.com/api/v3/ping"    # Binance REST ping
POLYMARKET_URL = "https://clob.polymarket.com/time"    # Polymarket CLOB server time

StatusCallback = Callable[[str, bool], None]  # (service_name, is_up)


class ConnectionMonitor:
    SERVICES = {
        "internet": INTERNET_URL,
        "binance": BINANCE_URL,
        "polymarket": POLYMARKET_URL,
    }

    def __init__(self, on_status: StatusCallback) -> None:
        self._on_status = on_status
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="conn-monitor")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        async with httpx.AsyncClient(timeout=8, verify=True) as client:
            while True:
                await asyncio.gather(
                    *(self._check(client, name, url) for name, url in self.SERVICES.items())
                )
                await asyncio.sleep(CHECK_INTERVAL)

    async def _check(self, client: httpx.AsyncClient, name: str, url: str) -> None:
        try:
            resp = await client.get(url)
            self._on_status(name, resp.status_code < 500)
        except Exception:
            self._on_status(name, False)

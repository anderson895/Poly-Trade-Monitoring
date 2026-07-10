"""Phase 1 smoke test: DB + Binance REST (daily open) + status endpoints."""
import asyncio

import httpx

from src.core.status import ConnectionMonitor
from src.feed.binance import BinanceFeed
from src.storage.db import Database


def test_db() -> None:
    db = Database()
    db.add_log("INFO", "Phase 1 smoke test")
    db.set_setting("risk_usdc", 20.0)
    assert db.get_setting("risk_usdc") == "20.0"
    assert len(db.recent_logs()) >= 1
    print("[OK] SQLite DB - logs:", len(db.recent_logs()))
    db.close()


async def test_binance_daily_open() -> None:
    feed = BinanceFeed(lambda p: None, lambda o: None, lambda s: None)
    await feed._refresh_daily_open()
    assert feed.daily_open and feed.daily_open > 0
    print(f"[OK] Binance REST - daily open (00:00 UTC): ${feed.daily_open:,.2f}")


async def test_status_endpoints() -> None:
    results: dict[str, bool] = {}
    monitor = ConnectionMonitor(lambda name, up: results.update({name: up}))
    async with httpx.AsyncClient(timeout=8) as client:
        await asyncio.gather(
            *(monitor._check(client, n, u) for n, u in ConnectionMonitor.SERVICES.items())
        )
    for name, up in results.items():
        print(f"[{'OK' if up else 'FAIL'}] {name} reachable: {up}")


async def test_binance_ws_stream() -> None:
    prices: list[float] = []
    done = asyncio.Event()

    def on_price(p: float) -> None:
        prices.append(p)
        if len(prices) >= 2:
            done.set()

    feed = BinanceFeed(on_price, lambda o: None, lambda s: None)
    feed.start()
    await asyncio.wait_for(done.wait(), timeout=30)
    await feed.stop()
    print(f"[OK] Binance WebSocket - live BTC: ${prices[-1]:,.2f} "
          f"(stretch: {feed.pct_from_open:+.2f}%)")


if __name__ == "__main__":
    test_db()
    asyncio.run(test_binance_daily_open())
    asyncio.run(test_status_endpoints())
    asyncio.run(test_binance_ws_stream())
    print("\nPhase 1 smoke test: PASSED")

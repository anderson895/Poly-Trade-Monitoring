"""Phase 1 smoke test: DB + market REST (daily open) + status endpoints.

Ginagaya ang app startup (main.py): truststore + DoH resolver, para ang
tine-test ay ang aktwal na network path na ginagamit ng app. Sumusunod
din ito sa parehong source selection ng app, kaya tumatakbo kahit sa US
VPS kung saan naka-block ang Binance.

Run:  .\\venv\\Scripts\\python.exe -m tests.smoke_phase1 [source]
      source = auto (default) | binance | coinbase
"""
import truststore

truststore.inject_into_ssl()

from src.core.netdns import install_doh_resolver  # noqa: E402

install_doh_resolver()  # bypass sa ISP DNS poisoning, gaya ng app

import asyncio  # noqa: E402
import sys  # noqa: E402

import httpx  # noqa: E402

from src.core.status import ConnectionMonitor
from src.feed.source import SOURCE_LABELS, make_feed, resolve_source
from src.storage.db import Database

SOURCE = "auto"  # ino-override ng CLI arg sa __main__


def _feed(**overrides):
    kwargs = {"on_price": lambda p: None, "on_daily_open": lambda o: None,
              "on_status": lambda s: None}
    kwargs.update(overrides)
    return make_feed(SOURCE, **kwargs)


def test_db() -> None:
    db = Database()
    db.add_log("INFO", "Phase 1 smoke test")
    # Test key lang — huwag galawin ang totoong risk_usdc setting ng user
    db.set_setting("_smoke_test", 20.0)
    assert db.get_setting("_smoke_test") == "20.0"
    assert len(db.recent_logs()) >= 1
    print("[OK] SQLite DB - logs:", len(db.recent_logs()))
    db.close()


async def test_daily_open() -> None:
    feed = _feed()
    await feed._refresh_daily_open()
    assert feed.daily_open and feed.daily_open > 0
    print(f"[OK] {SOURCE_LABELS[SOURCE]} REST - daily strike "
          f"(12:00 PM ET): ${feed.daily_open:,.2f}")


async def test_status_endpoints() -> None:
    results: dict[str, bool] = {}
    monitor = ConnectionMonitor(
        lambda name, up: results.update({name: up}), source=SOURCE
    )
    async with httpx.AsyncClient(timeout=8) as client:
        await asyncio.gather(
            *(monitor._check(client, n, u) for n, u in monitor.SERVICES.items())
        )
    for name, up in results.items():
        print(f"[{'OK' if up else 'FAIL'}] {name} reachable: {up}")


async def test_ws_stream() -> None:
    prices: list[float] = []
    done = asyncio.Event()

    def on_price(p: float) -> None:
        prices.append(p)
        if len(prices) >= 2:
            done.set()

    feed = _feed(on_price=on_price)
    feed.start()
    await asyncio.wait_for(done.wait(), timeout=30)
    await feed.stop()
    print(f"[OK] {SOURCE_LABELS[SOURCE]} WebSocket - live BTC: "
          f"${prices[-1]:,.2f} (stretch: {feed.pct_from_open:+.2f}%)")


if __name__ == "__main__":
    SOURCE = asyncio.run(resolve_source(
        sys.argv[1] if len(sys.argv) > 1 else "auto"
    ))
    print(f"Data source: {SOURCE_LABELS[SOURCE]}")
    test_db()
    asyncio.run(test_daily_open())
    asyncio.run(test_status_endpoints())
    asyncio.run(test_ws_stream())
    print("\nPhase 1 smoke test: PASSED")

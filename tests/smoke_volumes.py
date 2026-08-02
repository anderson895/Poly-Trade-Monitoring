"""Live smoke test: hourly volume fetch + escalation check sa totoong data.

Run:  .\\venv\\Scripts\\python.exe -m tests.smoke_volumes [source]
      source = auto (default) | binance | coinbase
"""
import asyncio
import sys

from src.feed.source import SOURCE_LABELS, make_feed, resolve_source
from src.strategy.filters import is_volume_escalating


async def main() -> None:
    source = await resolve_source(sys.argv[1] if len(sys.argv) > 1 else "auto")
    print(f"Data source: {SOURCE_LABELS[source]}")
    feed = make_feed(source, on_price=lambda p: None,
                     on_daily_open=lambda o: None, on_status=lambda s: None)
    await feed._refresh_volumes()
    vols = feed.hourly_volumes
    print(f"[OK] Fetched {len(vols)} completed 1h volumes "
          f"(latest: {vols[-1]:,.0f} BTC)")
    esc, why = is_volume_escalating(vols)
    print(f"[OK] Escalation check right now: {esc} — {why}")


if __name__ == "__main__":
    asyncio.run(main())

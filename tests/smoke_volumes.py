"""Live smoke test: hourly volume fetch + escalation check sa totoong data."""
import asyncio

from src.feed.binance import BinanceFeed
from src.strategy.filters import is_volume_escalating


async def main() -> None:
    feed = BinanceFeed(lambda p: None, lambda o: None, lambda s: None)
    await feed._refresh_volumes()
    vols = feed.hourly_volumes
    print(f"[OK] Fetched {len(vols)} completed 1h volumes "
          f"(latest: {vols[-1]:,.0f} BTC)")
    esc, why = is_volume_escalating(vols)
    print(f"[OK] Escalation check right now: {esc} — {why}")


if __name__ == "__main__":
    asyncio.run(main())

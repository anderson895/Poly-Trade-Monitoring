"""Ilang 15m entry setup ang nagkaroon sa nakaraang 48 oras? (totoong data)

Run:  .\\venv\\Scripts\\python.exe -m tests._scan_15m_setups [source]
      source = auto (default) | binance | coinbase
"""
import datetime as dt
import sys

from src.feed.history import describe_source, fetch_range, resolve_source_sync

MIN_S, MAX_S = 0.15309, 0.25516  # 15m stretch band ng bot

source = resolve_source_sync(sys.argv[1] if len(sys.argv) > 1 else "auto")
print(f"Data source: {describe_source(source)}")

now = dt.datetime.now(dt.timezone.utc).timestamp()
# 1m candles para makita ang intra-period high/low sa entry window
rows = [(r[0], r[1], r[2], r[3])
        for r in fetch_range("1m", now - 48 * 3600, now, source=source)]

periods: dict[float, list] = {}
for ts, o, h, l in rows:
    p = ts - ts % 900
    periods.setdefault(p, []).append((ts, o, h, l))

total = in_band = 0
hits = []
for p in sorted(periods):
    cs = periods[p]
    popen = cs[0][1]
    stretches = []
    for ts, o, h, l in cs:
        m = (ts - p) / 60.0
        if 2.5 <= m <= 7.5:
            stretches += [(h - popen) / popen * 100, (l - popen) / popen * 100]
    if not stretches:
        continue
    total += 1
    peak = max(abs(min(stretches)), abs(max(stretches)))
    if MIN_S <= peak <= MAX_S:
        in_band += 1
        hits.append(dt.datetime.fromtimestamp(p, dt.timezone.utc))

print(f"48 oras = {total} na 15m periods")
print(f"May stretch sa band (0.153-0.255%) sa loob ng window: {in_band} "
      f"({in_band / total * 100:.1f}%)")
for h in hits:
    print(f"  - {h:%m-%d %H:%M} UTC")
print("\n(Tandaan: kahit pumasok sa band, kailangan PA ring 15-25c ang")
print(" OTM share sa mismong sandali — mas kaunti pa ang aktwal na trades.)")

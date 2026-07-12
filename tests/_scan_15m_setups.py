"""Ilang 15m entry setup ang nagkaroon sa nakaraang 48 oras? (totoong data)"""
import datetime as dt

import httpx

MIN_S, MAX_S = 0.15309, 0.25516  # 15m stretch band ng bot

now = dt.datetime.now(dt.timezone.utc)
start = now - dt.timedelta(hours=48)
rows = []
start_ms = int(start.timestamp() * 1000)
client = httpx.Client(timeout=20)
while True:
    r = client.get("https://api.binance.com/api/v3/klines",
                   params={"symbol": "BTCUSDT", "interval": "1m",
                           "startTime": start_ms, "limit": 1000})
    batch = r.json()
    if not batch:
        break
    rows += [(k[0] / 1000.0, float(k[1]), float(k[2]), float(k[3])) for k in batch]
    start_ms = batch[-1][0] + 60_000
    if len(batch) < 1000:
        break

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

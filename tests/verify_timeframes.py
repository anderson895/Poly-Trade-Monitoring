"""One-off: hanapin ang KASALUKUYANG market ng bawat timeframe sa
totoong Gamma API (read-only).

Run:  .\\venv\\Scripts\\python.exe -m tests.verify_timeframes
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import truststore  # noqa: E402

truststore.inject_into_ssl()

from src.core.netdns import install_doh_resolver  # noqa: E402

install_doh_resolver()

import datetime as dt  # noqa: E402

from src.execution.polymarket import find_btc_market  # noqa: E402

now = dt.datetime.now(dt.timezone.utc)
for tf in ("daily", "4h", "1h", "15m"):
    try:
        m = find_btc_market(tf, now)
        print(f"[OK] {tf:>5}: {m.question}")
    except Exception as e:
        print(f"[FAIL] {tf:>5}: {type(e).__name__}: {e}")

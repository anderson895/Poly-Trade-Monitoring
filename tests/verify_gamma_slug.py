"""One-off developer check: i-verify ang daily BTC market slug pattern
sa TOTOONG Gamma API (walang pera, read-only query lang).

Run:  .\\venv\\Scripts\\python.exe -m tests.verify_gamma_slug
"""
import truststore

truststore.inject_into_ssl()

from src.core.netdns import install_doh_resolver  # noqa: E402

install_doh_resolver()

import datetime as dt  # noqa: E402

from src.execution.polymarket import find_daily_btc_market  # noqa: E402

today = dt.datetime.now(dt.timezone.utc).date()
slug = f"bitcoin-up-or-down-on-{today.strftime('%B').lower()}-{today.day}"
print(f"Checking slug: {slug}")
try:
    m = find_daily_btc_market(today)
    print("[OK] Slug pattern VERIFIED sa totoong Gamma API!")
    print(f"     Question : {m.question}")
    print(f"     Token UP : {m.token_up[:24]}...")
    print(f"     Token DN : {m.token_down[:24]}...")
except Exception as e:
    print(f"[FAIL] {type(e).__name__}: {e}")

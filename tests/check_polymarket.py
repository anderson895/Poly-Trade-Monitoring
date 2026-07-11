"""One-off check: alin sa mga Polymarket endpoints ang reachable dito.

Ginagaya ang app startup (main.py): truststore + DoH resolver, para ang
tine-test ay ang aktwal na network path na ginagamit ng app.
"""
import truststore

truststore.inject_into_ssl()

from src.core.netdns import install_doh_resolver  # noqa: E402

install_doh_resolver()  # bypass sa ISP DNS poisoning, gaya ng app

import httpx  # noqa: E402

ENDPOINTS = [
    "https://clob.polymarket.com/time",
    "https://gamma-api.polymarket.com/markets?limit=1",
    "https://polymarket.com",
]

for url in ENDPOINTS:
    for attempt in (1, 2):
        try:
            r = httpx.get(url, timeout=15, follow_redirects=True)
            print(f"[{r.status_code}] {url} (attempt {attempt}) -> {r.text[:80]!r}")
            break
        except Exception as e:
            print(f"[ERR] {url} (attempt {attempt}): {type(e).__name__}: {e}")

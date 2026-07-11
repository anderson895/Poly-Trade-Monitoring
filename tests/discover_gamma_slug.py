"""One-off developer check: hanapin ang TOTOONG slug pattern ng daily
BTC Up/Down markets sa Gamma API.

Run:  .\\venv\\Scripts\\python.exe -m tests.discover_gamma_slug
"""
import truststore

truststore.inject_into_ssl()

from src.core.netdns import install_doh_resolver  # noqa: E402

install_doh_resolver()

import httpx  # noqa: E402

GAMMA = "https://gamma-api.polymarket.com"

with httpx.Client(timeout=20) as client:
    # 1) Public search para sa "bitcoin up or down"
    print("=== public-search: 'bitcoin up or down' ===")
    try:
        r = client.get(
            f"{GAMMA}/public-search",
            params={"q": "bitcoin up or down", "limit_per_type": 5},
        )
        r.raise_for_status()
        data = r.json()
        for ev in data.get("events", [])[:5]:
            print(f"  event: slug={ev.get('slug')!r}  title={ev.get('title')!r}")
        for mk in data.get("markets", [])[:5]:
            print(f"  market: slug={mk.get('slug')!r}  q={mk.get('question')!r}")
    except Exception as e:
        print(f"  [ERR] {type(e).__name__}: {e}")

    # 2) Active markets na may 'bitcoin' sa question — tingnan ang slugs
    print("\n=== /markets?closed=false, filter 'up or down' ===")
    try:
        r = client.get(
            f"{GAMMA}/markets",
            params={"closed": "false", "limit": 100, "order": "id", "ascending": "false"},
        )
        r.raise_for_status()
        hits = 0
        for mk in r.json():
            q = (mk.get("question") or "").lower()
            if "up or down" in q and ("bitcoin" in q or "btc" in q):
                print(f"  slug={mk.get('slug')!r}")
                print(f"    q={mk.get('question')!r}  endDate={mk.get('endDate')!r}")
                hits += 1
        if hits == 0:
            print("  (walang tumama sa unang 100 — subukan ang search sa itaas)")
    except Exception as e:
        print(f"  [ERR] {type(e).__name__}: {e}")

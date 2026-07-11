"""One-off developer check: may DAILY BTC Up/Down market pa ba, at ano
ang slug pattern nito?

Run:  .\\venv\\Scripts\\python.exe -m tests.discover_gamma_daily
"""
import truststore

truststore.inject_into_ssl()

from src.core.netdns import install_doh_resolver  # noqa: E402

install_doh_resolver()

import httpx  # noqa: E402

GAMMA = "https://gamma-api.polymarket.com"

with httpx.Client(timeout=20) as client:
    # Probe 1: candidate daily slugs
    print("=== direct slug probes ===")
    for slug in (
        "btc-updown-1d-1783728000",       # 2026-07-11 00:00 UTC
        "bitcoin-up-or-down-july-11",
        "bitcoin-up-or-down-on-july-11-2026",
        "btc-updown-daily-1783728000",
    ):
        try:
            r = client.get(f"{GAMMA}/markets", params={"slug": slug})
            n = len(r.json()) if r.status_code == 200 else 0
            print(f"  {slug!r}: {r.status_code}, {n} market(s)")
        except Exception as e:
            print(f"  {slug!r}: [ERR] {e}")

    # Probe 2: search na may 'daily'
    print("\n=== public-search: 'bitcoin up or down daily' ===")
    try:
        r = client.get(
            f"{GAMMA}/public-search",
            params={"q": "bitcoin up or down daily", "limit_per_type": 8},
        )
        for ev in r.json().get("events", [])[:8]:
            print(f"  event: slug={ev.get('slug')!r}  title={ev.get('title')!r}")
    except Exception as e:
        print(f"  [ERR] {e}")

    # Probe 3: series listing — ang recurring markets ay naka-series
    print("\n=== /series?slug=... probes ===")
    for s in ("btc-updown", "bitcoin-up-or-down", "btc-up-or-down-daily"):
        try:
            r = client.get(f"{GAMMA}/series", params={"slug": s, "limit": 3})
            data = r.json()
            items = data if isinstance(data, list) else [data]
            for it in items[:3]:
                print(f"  series slug={it.get('slug')!r} title={it.get('title')!r} "
                      f"recurrence={it.get('recurrence')!r}")
        except Exception as e:
            print(f"  {s!r}: [ERR] {type(e).__name__}")

    # Probe 4: hanapin sa events ang may 'up or down' na hindi 5m/15m
    print("\n=== /events?closed=false — non-5m/15m 'up or down' ===")
    try:
        r = client.get(
            f"{GAMMA}/events",
            params={"closed": "false", "limit": 100, "order": "id",
                    "ascending": "false"},
        )
        hits = 0
        for ev in r.json():
            slug = ev.get("slug", "")
            title = (ev.get("title") or "").lower()
            if "up or down" in title and "-5m-" not in slug and "-15m-" not in slug:
                print(f"  slug={slug!r}  title={ev.get('title')!r}")
                hits += 1
        if hits == 0:
            print("  (wala sa unang 100 active events)")
    except Exception as e:
        print(f"  [ERR] {e}")

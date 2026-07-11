"""One-off: alamin ang slug patterns ng 15m/1h/4h BTC Up/Down markets.

Run:  .\\venv\\Scripts\\python.exe -m tests.discover_gamma_timeframes
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import truststore  # noqa: E402

truststore.inject_into_ssl()

from src.core.netdns import install_doh_resolver  # noqa: E402

install_doh_resolver()

import time  # noqa: E402

import httpx  # noqa: E402

GAMMA = "https://gamma-api.polymarket.com"
now = int(time.time())

with httpx.Client(timeout=20) as client:
    # Current period starts (aligned sa UTC)
    starts = {
        "15m": now - now % 900,
        "1h": now - now % 3600,
        "4h": now - now % 14400,
    }
    print("=== direct slug probes (btc-updown-<tf>-<period_start>) ===")
    for tf, start in starts.items():
        for probe_start in (start, start - {"15m": 900, "1h": 3600,
                                            "4h": 14400}[tf]):
            slug = f"btc-updown-{tf}-{probe_start}"
            try:
                r = client.get(f"{GAMMA}/markets", params={"slug": slug})
                m = r.json()
                if m:
                    q = m[0].get("question")
                    print(f"  [HIT] {slug} -> {q!r}")
                else:
                    print(f"  [miss] {slug}")
            except Exception as e:
                print(f"  [ERR] {slug}: {e}")

    print("\n=== active na 'up or down' events, grouped by pattern ===")
    r = client.get(f"{GAMMA}/events",
                   params={"closed": "false", "limit": 200, "order": "id",
                           "ascending": "false"})
    seen = {}
    for ev in r.json():
        slug = ev.get("slug", "")
        title = (ev.get("title") or "")
        if "btc" in slug or "bitcoin" in slug:
            if "updown" in slug or "up-or-down" in slug:
                # kunin ang pattern prefix
                key = slug.rsplit("-", 1)[0] if slug[-1].isdigit() else slug
                if key not in seen:
                    seen[key] = (slug, title)
    for key, (slug, title) in sorted(seen.items()):
        print(f"  {slug}  ->  {title!r}")

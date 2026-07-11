"""One-off SAFE check: tama ba ang Polymarket credentials?

Ginagawa: (1) derive API creds mula sa private key, (2) basahin ang
USDC balance, (3) hanapin ang daily market. WALANG order na inilalagay.

Run:  .\\venv\\Scripts\\python.exe -m tests.verify_live_creds
"""
import truststore

truststore.inject_into_ssl()

from src.core.netdns import install_doh_resolver  # noqa: E402

install_doh_resolver()

import datetime as dt  # noqa: E402

from src.core import secrets  # noqa: E402
from src.execution.polymarket import (  # noqa: E402
    PolymarketClient,
    find_daily_btc_market,
)

pk = secrets.get_secret(secrets.KEY_PM_PRIVATE)
funder = secrets.get_secret(secrets.KEY_PM_FUNDER)
print(f"Private Key : {secrets.mask(pk)}")
print(f"Funder      : {funder}")

try:
    client = PolymarketClient(private_key=pk, funder=funder, signature_type=1)
    client.connect()
    print("[OK] API credentials derived — tanggap ng Polymarket ang key")
except Exception as e:
    print(f"[FAIL] connect: {type(e).__name__}: {e}")
    raise SystemExit(1)

try:
    balance = client.get_usdc_balance()
    print(f"[OK] USDC balance: {balance:,.2f}")
    if balance == 0:
        print("     (0 ang balance — kung may USDC ka sa Polymarket, baka")
        print("      mali ang Funder address; subukan ang nasa Deposit page)")
except Exception as e:
    print(f"[FAIL] balance: {type(e).__name__}: {e}")

try:
    market = find_daily_btc_market(dt.datetime.now(dt.timezone.utc).date())
    print(f"[OK] Daily market: {market.question}")
except Exception as e:
    print(f"[FAIL] market: {type(e).__name__}: {e}")

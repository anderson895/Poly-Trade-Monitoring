"""One-off: anong nangyayari sa iba't ibang klase ng MALING credentials?

Ligtas: read-only checks lang, at hindi ginagalaw ang naka-save na
totoong credentials sa Credential Manager.

Run:  .\\venv\\Scripts\\python.exe -m tests.verify_bad_creds
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import truststore  # noqa: E402

truststore.inject_into_ssl()

from src.core.netdns import install_doh_resolver  # noqa: E402

install_doh_resolver()

from src.execution.polymarket import PolymarketClient  # noqa: E402

REAL_FUNDER = "0x1f55a040f666dB780ceaC47B4E414527fcC29245"


def try_creds(label: str, pk: str, funder: str) -> None:
    print(f"\n=== {label} ===")
    try:
        client = PolymarketClient(private_key=pk, funder=funder,
                                  signature_type=1)
        client.connect()
        print("  connect: OK (na-derive ang API creds)")
    except Exception as e:
        print(f"  connect: SUMABOG -> {type(e).__name__}: {e}")
        return
    try:
        bal = client.get_usdc_balance()
        print(f"  balance: {bal:,.2f} USDC")
    except Exception as e:
        print(f"  balance: SUMABOG -> {type(e).__name__}: {e}")


# 1) Basurang private key (hindi valid na format)
try_creds("Case 1: basurang key ('hindi-ako-key')",
          "hindi-ako-key", REAL_FUNDER)

# 2) Maikling hex na hindi kumpletong key
try_creds("Case 2: kulang na hex key ('0x1234abcd')",
          "0x1234abcd", REAL_FUNDER)

# 3) VALID na key pero HINDI sa iyo (random na gawa-gawa)
try_creds("Case 3: valid pero IBANG wallet ang key",
          "0x" + "ab" * 32, REAL_FUNDER)

# 4) Tamang key format pero maling funder address
try_creds("Case 4: maling funder address",
          "0x" + "ab" * 32, "0x0000000000000000000000000000000000000001")

"""LIVE E2E plumbing test — TOTOONG PERA, maliit na halaga (~$3).

Vine-verify nito ang buong order path na hindi pa nagagamit ng bot:
  connect -> market discovery -> order book -> BUY (limit sa best ask)
  -> fill check -> SELL pabalik (limit sa best bid) -> fill check -> balances

GANAP NA HIWALAY sa tumatakbong app:
  - Sariling proseso at sariling Polymarket client
  - HINDI sumusulat sa data/bot.db (read-only lang ang isang setting)
  - HINDI ginagalaw ang position/state ng bot — ang bot ay walang
    kamalayan sa test na ito (mag-iiba lang panandalian ang balance card)

Inaasahang gastos: ang spread lang (~$0.05-0.30 sa $3 na order).

Run:  .\\venv\\Scripts\\python.exe -m tests.live_e2e_order
      (magtatanong ng kumpirmasyon bago maglagay ng totoong order)
"""
from __future__ import annotations

import datetime as dt
import sqlite3
import sys
import time

import truststore

truststore.inject_into_ssl()
from src.core import netdns  # noqa: E402

netdns.install_doh_resolver()

from py_clob_client_v2 import (  # noqa: E402
    AssetType,
    BalanceAllowanceParams,
)

from src.core import secrets as secret_store  # noqa: E402
from src.execution.polymarket import (  # noqa: E402
    PolymarketClient,
    find_btc_market,
)
from src.strategy.mean_reversion import period_start_utc  # noqa: E402

AMOUNT_USDC = 3.0     # sukat ng test order (min ~5 shares ang Polymarket)
FILL_WAIT_SECS = 20   # gaano katagal hihintayin ang fill bago i-cancel
MIN_PERIOD_LEFT = 5 * 60  # huwag mag-test kung <5 min na lang sa period


def shares_balance(client: PolymarketClient, token: str) -> float:
    """Ilang shares ng token ang hawak natin ngayon."""
    resp = client._client.get_balance_allowance(
        BalanceAllowanceParams(asset_type=AssetType.CONDITIONAL, token_id=token)
    )
    raw = resp.get("balance", "0") if isinstance(resp, dict) else "0"
    return int(raw) / 10**6


def wait_for(desc: str, check, timeout: float = FILL_WAIT_SECS) -> bool:
    """Mag-poll hanggang totoo ang check() o mag-timeout."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        if check():
            return True
        time.sleep(2)
        print(f"  ... hinihintay ang {desc} ({time.time() - t0:.0f}s)")
    return False


def main() -> None:
    now = dt.datetime.now(dt.timezone.utc)

    # --- guard: sapat pa ba ang oras sa kasalukuyang 15m period? --------
    period_start = period_start_utc(now, "15m")
    left = period_start.timestamp() + 900 - now.timestamp()
    if left < MIN_PERIOD_LEFT:
        print(f"[ABORT] {left / 60:.1f} min na lang sa 15m period — "
              "patakbuhin ulit sa simula ng susunod na period "
              "(mga :00/:15/:30/:45 UTC) para ligtas ang sell-back.")
        sys.exit(1)

    # --- creds (read-only; walang isinusulat kahit saan) ----------------
    pk = secret_store.get_secret(secret_store.KEY_PM_PRIVATE)
    funder = secret_store.get_secret(secret_store.KEY_PM_FUNDER)
    if not pk or not funder:
        print("[ABORT] Walang Private Key / Funder sa Credential Manager.")
        sys.exit(1)
    conn = sqlite3.connect("file:data/bot.db?mode=ro", uri=True)
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'pm_signature_type'"
    ).fetchone()
    conn.close()
    sig_type = int(row[0]) if row else 1

    # Optional overrides:  python -m tests.live_e2e_order [funder] [sig_type]
    # (hal. ang deposit wallet address mula sa polymarket.com Settings
    #  "For API use only" + sig type 3)
    if len(sys.argv) > 1:
        funder = sys.argv[1]
    if len(sys.argv) > 2:
        sig_type = int(sys.argv[2])

    client = PolymarketClient(pk, funder, signature_type=sig_type)
    client.connect()
    usdc_before = client.get_usdc_balance()
    print(f"Konektado (funder={funder[:10]}…, sig_type={sig_type}). "
          f"USDC balance: {usdc_before:.2f}")

    market = find_btc_market("15m", now)
    print(f"Market: {market.question}")

    # --- pumili ng side: ang may pinakamanipis na spread -----------------
    quotes = {}
    for side in ("UP", "DOWN"):
        bid, ask = client.get_best_prices(market.token_for(side))
        quotes[side] = (bid, ask)
        print(f"  {side}: bid={bid} ask={ask}")
    tradable = {
        s: (b, a) for s, (b, a) in quotes.items()
        if b is not None and a is not None and 0.05 <= a <= 0.95
    }
    if not tradable:
        print("[ABORT] Walang sapat na liquidity sa order book.")
        sys.exit(1)
    side = min(tradable, key=lambda s: tradable[s][1] - tradable[s][0])
    bid, ask = tradable[side]
    token = market.token_for(side)
    shares = max(5.0, round(AMOUNT_USDC / ask, 2))  # min 5 shares
    cost = shares * ask
    print(f"\nPlano: BUY {shares} {side} shares @ {ask:.2f} "
          f"(~${cost:.2f}), tapos SELL agad sa ~{bid:.2f} "
          f"(inaasahang gastos ~${shares * (ask - bid):.2f} spread)")

    resp = input("Ituloy ang TOTOONG order? I-type ang 'yes': ").strip().lower()
    if resp != "yes":
        print("Kinansela — walang order na nilagay.")
        sys.exit(0)

    # --- BUY -------------------------------------------------------------
    held_before = shares_balance(client, token)
    order_id = client.buy_limit(token, ask, cost)
    print(f"[OK] BUY order posted (id={order_id or 'n/a'})")
    filled = wait_for(
        "BUY fill",
        lambda: shares_balance(client, token) >= held_before + shares * 0.99,
    )
    if not filled:
        print("[WARN] Hindi na-fill ang BUY sa oras — kinakansela...")
        client.cancel_all()
        print("[OK] Cancelled. Walang position na naiwan. TEST INCOMPLETE "
              "(subukan ulit kapag mas liquid ang book).")
        sys.exit(1)
    held = shares_balance(client, token) - held_before
    print(f"[OK] BUY FILLED — hawak: {held:.2f} shares")

    # --- SELL pabalik ------------------------------------------------------
    bid2, _ = client.get_best_prices(token)
    sell_px = bid2 if bid2 is not None else bid
    order_id = client.sell_limit(token, sell_px, held)
    print(f"[OK] SELL order posted @ {sell_px:.2f} (id={order_id or 'n/a'})")
    sold = wait_for(
        "SELL fill",
        lambda: shares_balance(client, token) <= held_before + 0.01,
    )
    if not sold:
        client.cancel_all()
        print("[WARN] Hindi na-fill ang SELL — na-cancel ang order. MAY "
              f"{held:.2f} {side} shares KA PA sa market na ito! Ibenta "
              "manually sa polymarket.com o patakbuhin ulit ang script.")
        sys.exit(1)

    usdc_after = client.get_usdc_balance()
    print(f"\n=== E2E LIVE TEST: PASSED ===")
    print(f"BUY {held:.2f} {side} @ {ask:.2f} -> SELL @ {sell_px:.2f}")
    print(f"USDC: {usdc_before:.2f} -> {usdc_after:.2f} "
          f"(gastos: {usdc_before - usdc_after:+.2f})")
    print("Ang buong order path (connect/discovery/book/buy/fill/sell) ay "
          "VERIFIED na sa totoong pera. Pwede nang i-check ang E2E item "
          "sa DevelopmentPlan.")


if __name__ == "__main__":
    main()

"""Backtest ng daily mean-reversion strategy sa historical BTC data.

Vina-validate nito ang dalawang bagay mula sa DevelopmentPlan §7:
  1. Ang "over 90% of daily candles have wicks" claim — gaano kadalas
     bumabalik ang presyo papunta sa strike pagkatapos ma-stretch?
  2. Ang aktwal na strategy PnL — parehong rules ng bot (entry window
     4-12h, stretch band 1.5-2.5%, share gate 15-25c, profit +100%,
     stop -50%, EOD exit 23.5h) sa tanghali-ET periods.

Ginagamit ang PAREHONG code paths ng bot: StrategyConfig defaults,
estimate_otm_share_price/position_share_price (paper pricing model), at
period_start_utc (tanghali-ET anchor). WALANG volume/premium filters dito
(walang historical order book) — kaya bahagyang MAS maluwag ang entries
kaysa sa totoong bot.

LIMITASYON: ang share prices ay mula sa paper linear model, HINDI totoong
Polymarket order book — ang PnL ay strategy-shape validation lang, hindi
eksaktong kita.

Ang data source ay Binance kung naaabot, Coinbase kung hindi (hal. sa US
VPS na sinasagot ng HTTP 451) — tingnan ang `src/feed/history.py`.
Bahagyang naiiba ang BTC-USD sa BTCUSDT, kaya huwag ihambing nang tuwiran
ang resulta ng dalawang source.

Run:  .\\venv\\Scripts\\python.exe -m tests.backtest_daily [days] [source]
      days   = default 365
      source = auto (default) | binance | coinbase
"""
from __future__ import annotations

import datetime as dt
import sys

from src.execution.paper import estimate_otm_share_price, position_share_price
from src.feed.history import describe_source, fetch_range, resolve_source_sync
from src.strategy.mean_reversion import (
    StrategyConfig,
    period_start_utc,
    target_side,
)

CANDLE_SECS = 900  # 15m candles — sapat na resolution para sa daily periods
RISK_USDC = 200.0

cfg = StrategyConfig()  # daily defaults, pareho ng bot


def fetch_15m_closes(days: int, source: str) -> list[tuple[float, float]]:
    """(open_ts_sec, close_price) ng bawat 15m candle sa nakaraang N araw."""
    end = dt.datetime.now(dt.timezone.utc).timestamp()
    start = end - (days + 2) * 86400
    return [(r[0], r[4]) for r in fetch_range("15m", start, end, source=source)]


def simulate(days: int, source: str = "auto") -> None:
    resolved = resolve_source_sync(source)
    print(f"Data source: {describe_source(resolved)}")
    rows = fetch_15m_closes(days, resolved)
    by_ts = {ts: close for ts, close in rows}
    print(f"Nakuha: {len(rows):,} candles "
          f"({dt.datetime.fromtimestamp(rows[0][0], dt.timezone.utc):%Y-%m-%d} "
          f"hanggang {dt.datetime.fromtimestamp(rows[-1][0], dt.timezone.utc):%Y-%m-%d})")

    # Mga tanghali-ET period anchors sa saklaw ng data
    anchors: list[float] = []
    t = dt.datetime.fromtimestamp(rows[0][0], dt.timezone.utc)
    seen: set[float] = set()
    while t.timestamp() < rows[-1][0]:
        a = period_start_utc(t, "daily").timestamp()
        if a not in seen and a >= rows[0][0]:
            seen.add(a)
            anchors.append(a)
        t += dt.timedelta(hours=12)
    anchors.sort()

    periods = stretched = reverted = 0
    trades: list[tuple[str, float, str]] = []  # (exit_reason, pnl, date)

    for anchor in anchors:
        if anchor + 86400 > rows[-1][0]:
            break  # kulang ang data para sa buong period
        strike = by_ts.get(anchor)
        if strike is None:
            continue
        periods += 1

        position = None  # (side, entry_price)
        entered = False
        was_stretched = False
        did_revert = False
        max_abs_stretch = 0.0

        ts = anchor + CANDLE_SECS
        while ts <= anchor + 86400:
            close = by_ts.get(ts)
            if close is None:
                ts += CANDLE_SECS
                continue
            hrs = (ts - anchor) / 3600.0
            stretch = (close - strike) / strike * 100.0
            max_abs_stretch = max(max_abs_stretch, abs(stretch))

            # --- wick-claim tracking -----------------------------------
            if abs(stretch) >= cfg.min_stretch_pct:
                was_stretched = True
            if was_stretched and abs(stretch) <= 0.6:
                did_revert = True  # bumalik malapit sa strike (ref: 0.6%)

            # --- strategy simulation -----------------------------------
            if position is None and not entered:
                if (cfg.entry_start_hour <= hrs <= cfg.entry_end_hour
                        and cfg.min_stretch_pct <= abs(stretch)
                        <= cfg.max_stretch_pct):
                    share = estimate_otm_share_price(stretch)
                    if cfg.min_share_price <= share <= cfg.max_share_price:
                        position = (target_side(stretch), share)
                        entered = True
            elif position is not None:
                side, entry = position
                cur = position_share_price(stretch, side)
                chg = (cur - entry) / entry * 100.0
                reason = None
                if chg >= cfg.profit_target_pct:
                    reason = "profit"
                elif chg <= -cfg.stop_loss_pct:
                    reason = "stop"
                elif hrs >= cfg.eod_exit_hour:
                    reason = "eod"
                if reason:
                    shares = RISK_USDC / entry
                    pnl = shares * (cur - entry)
                    day = dt.datetime.fromtimestamp(
                        anchor, dt.timezone.utc).strftime("%Y-%m-%d")
                    trades.append((reason, pnl, day))
                    position = None
            ts += CANDLE_SECS

        if was_stretched:
            stretched += 1
            if did_revert:
                reverted += 1

    # ------------------------------------------------------------ report
    print(f"\n=== WICK/REVERSION CLAIM (validation ng reference) ===")
    print(f"Periods na sinuri (tanghali ET -> tanghali ET): {periods}")
    print(f"Na-stretch ng >= {cfg.min_stretch_pct}%: {stretched} "
          f"({stretched / periods * 100:.0f}% ng mga araw)")
    if stretched:
        print(f"Sa mga na-stretch, bumalik sa <= 0.6% ng strike: {reverted} "
              f"({reverted / stretched * 100:.0f}%)  <- ito ang 'rubber band'")

    print(f"\n=== STRATEGY BACKTEST (${RISK_USDC:.0f} risk kada trade) ===")
    if not trades:
        print("Walang trade na na-trigger sa saklaw na ito.")
        return
    wins = [p for _, p, _ in trades if p > 0]
    total = sum(p for _, p, _ in trades)
    by_reason: dict[str, int] = {}
    for r, _, _ in trades:
        by_reason[r] = by_reason.get(r, 0) + 1
    print(f"Trades: {len(trades)} sa {periods} periods "
          f"(~{len(trades) / periods * 100:.0f}% ng mga araw may trade)")
    print(f"Win rate: {len(wins)}/{len(trades)} "
          f"({len(wins) / len(trades) * 100:.0f}%)")
    print(f"Exits: {by_reason}")
    print(f"Avg PnL/trade: {total / len(trades):+,.2f} USDC")
    print(f"TOTAL PnL: {total:+,.2f} USDC")
    worst = min(trades, key=lambda t: t[1])
    best = max(trades, key=lambda t: t[1])
    print(f"Best: {best[1]:+,.2f} ({best[2]}, {best[0]}) | "
          f"Worst: {worst[1]:+,.2f} ({worst[2]}, {worst[0]})")


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 365
    src = sys.argv[2] if len(sys.argv) > 2 else "auto"
    simulate(days, src)

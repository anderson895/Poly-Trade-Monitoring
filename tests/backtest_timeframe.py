"""Backtest ng mean-reversion strategy sa KAHIT ANONG timeframe.

Ang `backtest_daily.py` ay daily lang. Ito ay para sa 4h/1h/15m markets,
kung saan ang mga threshold ay hindi na direktang kalibrado kundi
sqrt-of-time-scaled mula sa daily — at hindi pa napapatunayan.

Ginagamit ang PAREHONG code paths ng bot: `scale_config_for_timeframe`,
`estimate_otm_share_price` / `position_share_price`, at `period_start_utc`.
WALANG volume/premium/econ filters (walang historical order book), kaya
bahagyang MAS maluwag ang entries kaysa sa totoong bot.

LIMITASYON: paper pricing model ang share prices, HINDI totoong Polymarket
order book. Ang PnL ay pang-hugis lang ng strategy, hindi eksaktong kita.

Run:  .\\venv\\Scripts\\python.exe -m tests.backtest_timeframe [tf] [days] [min] [max] [source]
      tf     = 4h (default) | 1h | 15m | daily
      days   = 365 default
      min/max = daily-calibrated stretch band (default 1.5 / 2.5)
"""
from __future__ import annotations

import datetime as dt
import sys
from collections import Counter

from src.execution.paper import estimate_otm_share_price, position_share_price
from src.feed.history import describe_source, fetch_range, resolve_source_sync
from src.strategy.mean_reversion import (
    StrategyConfig,
    period_start_utc,
    scale_config_for_timeframe,
    stretch_scale,
    target_side,
)

RISK_USDC = 200.0
# Resolution ng candles kada timeframe — kailangang sapat ang samples sa
# loob ng entry window, kung hindi ay malalampasan ang maiikling touch
CANDLES = {"daily": "15m", "4h": "5m", "1h": "1m", "15m": "1m"}
CANDLE_SECS = {"1m": 60, "5m": 300, "15m": 900}


def simulate(tf: str, days: int, mn: float, mx: float, source: str) -> None:
    cfg = scale_config_for_timeframe(
        StrategyConfig(min_stretch_pct=mn, max_stretch_pct=mx), tf
    )
    scale = stretch_scale(tf)
    interval = CANDLES[tf]
    step = CANDLE_SECS[interval]
    period_secs = cfg.period_hours * 3600.0

    print(f"Timeframe   : {tf}  (period {cfg.period_hours:g}h)")
    print(f"Data source : {describe_source(source)}  ({interval} candles)")
    print(f"Stretch band: {mn}% - {mx}% daily  ->  "
          f"{cfg.min_stretch_pct:.3f}% - {cfg.max_stretch_pct:.3f}% sa {tf}")
    print(f"Entry window: {cfg.entry_start_hour * 60:.0f}-"
          f"{cfg.entry_end_hour * 60:.0f} min | EOD exit "
          f"{cfg.eod_exit_hour * 60:.0f} min")

    end = dt.datetime.now(dt.timezone.utc).timestamp()
    start = end - (days + 1) * 86400
    rows = fetch_range(interval, start, end, source=source)
    if not rows:
        print("Walang nakuhang data.")
        return
    by_ts = {r[0]: r for r in rows}
    print(f"Candles     : {len(rows):,} "
          f"({dt.datetime.fromtimestamp(rows[0][0], dt.timezone.utc):%Y-%m-%d} "
          f"-> {dt.datetime.fromtimestamp(rows[-1][0], dt.timezone.utc):%Y-%m-%d})")

    # Mga period anchor sa saklaw ng data
    anchors: list[float] = []
    t = dt.datetime.fromtimestamp(rows[0][0], dt.timezone.utc)
    a = period_start_utc(t, tf).timestamp()
    while a + period_secs <= rows[-1][0]:
        if a >= rows[0][0]:
            anchors.append(a)
        a += period_secs

    periods = 0
    trades: list[tuple[str, float, str]] = []
    blocked = Counter()          # bakit hindi nakapasok
    reached_window = 0           # may kandidatong stretch sa loob ng window

    for anchor in anchors:
        first = by_ts.get(anchor)
        if first is None:
            continue
        strike = first[1]        # open ng period = "price to beat"
        periods += 1

        position = None
        entered = False
        saw_band = False

        ts = anchor
        while ts <= anchor + period_secs:
            row = by_ts.get(ts)
            if row is None:
                ts += step
                continue
            close = row[4]
            hrs = (ts - anchor) / 3600.0
            stretch = (close - strike) / strike * 100.0

            if position is None and not entered:
                in_window = cfg.entry_start_hour <= hrs <= cfg.entry_end_hour
                in_band = (cfg.min_stretch_pct <= abs(stretch)
                           <= cfg.max_stretch_pct)
                if in_window and in_band:
                    saw_band = True
                    share = estimate_otm_share_price(stretch, scale)
                    if cfg.min_share_price <= share <= cfg.max_share_price:
                        position = (target_side(stretch), share)
                        entered = True
                    elif share > cfg.max_share_price:
                        blocked["share price MAHAL (>0.25)"] += 1
                    else:
                        blocked["share price MURA (<0.15)"] += 1
            elif position is not None:
                side, entry = position
                cur = position_share_price(stretch, side, scale)
                chg = (cur - entry) / entry * 100.0
                reason = None
                if chg >= cfg.profit_target_pct:
                    reason = "profit"
                elif chg <= -cfg.stop_loss_pct:
                    reason = "stop"
                elif hrs >= cfg.eod_exit_hour:
                    reason = "eod"
                if reason:
                    pnl = (RISK_USDC / entry) * (cur - entry)
                    day = dt.datetime.fromtimestamp(
                        anchor, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
                    trades.append((reason, pnl, day))
                    position = None
            ts += step

        if saw_band:
            reached_window += 1

    # ---------------------------------------------------------------- report
    print()
    print(f"=== BAKIT HINDI PUMAPASOK ({periods:,} periods) ===")
    print(f"Umabot sa stretch band sa loob ng window: {reached_window:,} "
          f"({reached_window / periods * 100:.1f}% ng periods)")
    for why, n in blocked.most_common():
        print(f"  hinarang ng {why}: {n:,} ticks")

    print()
    print(f"=== BACKTEST (${RISK_USDC:.0f} risk kada trade) ===")
    if not trades:
        print("WALANG TRADE na na-trigger sa saklaw na ito.")
        return
    wins = [p for _, p, _ in trades if p > 0]
    total = sum(p for _, p, _ in trades)
    by_reason = Counter(r for r, _, _ in trades)
    print(f"Trades   : {len(trades):,} sa {periods:,} periods "
          f"({len(trades) / periods * 100:.1f}% ng periods)")
    print(f"Win rate : {len(wins)}/{len(trades)} "
          f"({len(wins) / len(trades) * 100:.0f}%)")
    print(f"Exits    : {dict(by_reason)}")
    print(f"Avg/trade: {total / len(trades):+,.2f} USDC")
    print(f"TOTAL PnL: {total:+,.2f} USDC")
    best, worst = max(trades, key=lambda x: x[1]), min(trades, key=lambda x: x[1])
    print(f"Best     : {best[1]:+,.2f} ({best[2]}, {best[0]})")
    print(f"Worst    : {worst[1]:+,.2f} ({worst[2]}, {worst[0]})")


if __name__ == "__main__":
    tf = sys.argv[1] if len(sys.argv) > 1 else "4h"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 365
    mn = float(sys.argv[3]) if len(sys.argv) > 3 else 1.5
    mx = float(sys.argv[4]) if len(sys.argv) > 4 else 2.5
    src = resolve_source_sync(sys.argv[5] if len(sys.argv) > 5 else "auto")
    simulate(tf, days, mn, mx, src)

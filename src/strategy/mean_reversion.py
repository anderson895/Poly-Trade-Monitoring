"""Mean Reversion / "Rubber Band" strategy — pure logic, walang I/O.

Mula sa reference (details.txt):
- Maghintay ng 4-12 hours pagkatapos ng daily open (00:00 UTC)
- Entry kapag ang BTC ay naka-stretch ng 1.5%-2.5% mula sa daily open
  (lampas 2.5% = posibleng momentum expansion day — DEATH TRAP, iwasan)
- Bilhin ang out-of-the-money side (DOWN kung pumped, UP kung dumped)
  kapag ang share price ay 15c-25c
- HUWAG hintayin ang settlement — i-sell sa profit target (~+150%)
- Safety exits: stop loss at end-of-day force exit
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional

# Polymarket BTC Up/Down market timeframes -> period sa oras
TIMEFRAMES: dict[str, float] = {
    "daily": 24.0,
    "4h": 4.0,
    "1h": 1.0,
    "15m": 0.25,
}


class Action(Enum):
    NONE = "NONE"
    ENTER = "ENTER"
    EXIT = "EXIT"


@dataclass(frozen=True)
class StrategyConfig:
    period_hours: float = 24.0      # haba ng minarkahang market period
    min_stretch_pct: float = 1.5    # minimum stretch bago mag-entry
    max_stretch_pct: float = 2.5    # lampas dito = death trap, huwag pumasok
    entry_start_hour: float = 4.0   # oras MULA SA period open (hintayin ang stretch)
    entry_end_hour: float = 12.0    # huwag nang pumasok pagkalampas nito
    min_share_price: float = 0.15   # bilhin lang kung 15c-25c ang OTM share
    max_share_price: float = 0.25
    profit_target_pct: float = 100.0  # +100% ng entry price -> SELL
    stop_loss_pct: float = 50.0       # -50% ng entry price -> SELL (cut loss)
    eod_exit_hour: float = 23.5       # force exit bago mag-settlement
    max_trades_per_day: int = 1
    # Volume escalation filter (death trap guard)
    volume_spike_mult: float = 2.0    # recent avg >= 2x baseline = momentum day
    volume_recent_hours: int = 3
    volume_baseline_hours: int = 20
    # Coinbase premium filter (death trap guard)
    premium_threshold_pct: float = 0.15  # |premium| >= 0.15% = aggressive US flow


@dataclass
class Position:
    side: str            # 'UP' | 'DOWN'
    entry_price: float   # share price sa pagbili (0.00-1.00)
    shares: float
    entry_ts: dt.datetime


@dataclass(frozen=True)
class Signal:
    action: Action
    side: Optional[str] = None   # para sa ENTER
    reason: str = ""


def hours_into_period(now_utc: dt.datetime, period_hours: float = 24.0) -> float:
    """Ilang oras na ang lumipas sa loob ng kasalukuyang market period.

    Ang lahat ng Polymarket BTC periods (15m/1h/4h/daily) ay naka-align sa
    UTC epoch boundaries, kaya simpleng modulo sa period length.
    """
    period_secs = period_hours * 3600.0
    return (now_utc.timestamp() % period_secs) / 3600.0


def hours_since_utc_open(now_utc: dt.datetime) -> float:
    """Back-compat alias para sa daily (24h) period."""
    return hours_into_period(now_utc, 24.0)


def stretch_scale(timeframe: str) -> float:
    """Volatility scale ng timeframe kumpara sa daily (sqrt-of-time).

    Ang tipikal na galaw ng BTC sa 15 minuto ay mas maliit kaysa sa isang
    araw — humigit-kumulang proporsyonal sa sqrt ng haba ng panahon.
    """
    return math.sqrt(TIMEFRAMES[timeframe] / 24.0)


def scale_config_for_timeframe(
    cfg: StrategyConfig, timeframe: str
) -> StrategyConfig:
    """I-adapt ang daily-calibrated na config sa napiling market timeframe.

    - Mga oras (entry window, end-of-period exit) -> parehong FRACTION
      ng period (hal. daily 4h-12h ng 24h = 16.7%-50% -> sa 1h market:
      10min-30min)
    - Stretch thresholds -> sqrt-of-time scaling (hal. 1.5% daily ->
      ~0.31% sa 1h)
    - Share price gates, profit target, stop loss -> hindi ginagalaw
      (magkapareho ang share-price dynamics ng lahat ng markets)
    """
    period = TIMEFRAMES[timeframe]
    t = period / 24.0
    k = stretch_scale(timeframe)
    return dataclasses.replace(
        cfg,
        period_hours=period,
        min_stretch_pct=cfg.min_stretch_pct * k,
        max_stretch_pct=cfg.max_stretch_pct * k,
        entry_start_hour=cfg.entry_start_hour * t,
        entry_end_hour=cfg.entry_end_hour * t,
        eod_exit_hour=cfg.eod_exit_hour * t,
    )


def target_side(stretch_pct: float) -> str:
    """Ang binibili ay ang KABALIGTARAN ng stretch direction (mean reversion)."""
    return "DOWN" if stretch_pct > 0 else "UP"


def evaluate_entry(
    now_utc: dt.datetime,
    stretch_pct: Optional[float],
    share_price: Optional[float],
    trades_today: int,
    cfg: StrategyConfig = StrategyConfig(),
) -> Signal:
    """Dapat bang pumasok? Tawagin lang ito kapag WALANG open position."""
    if stretch_pct is None or share_price is None:
        return Signal(Action.NONE, reason="waiting for data")

    if trades_today >= cfg.max_trades_per_day:
        return Signal(Action.NONE, reason="max trades for this period reached")

    hrs = hours_into_period(now_utc, cfg.period_hours)
    if hrs < cfg.entry_start_hour:
        if cfg.period_hours <= 4:  # maikling period — minutes ang malinaw
            window = (f"{cfg.entry_start_hour * 60:.1f}-"
                      f"{cfg.entry_end_hour * 60:.1f} min into period, "
                      f"now {hrs * 60:.1f} min")
        else:
            window = (f"{cfg.entry_start_hour:.0f}h-{cfg.entry_end_hour:.0f}h "
                      f"into period, now {hrs:.1f}h")
        return Signal(
            Action.NONE,
            reason=f"waiting for entry window ({window})",
        )
    if hrs > cfg.entry_end_hour:
        scope = "today" if cfg.period_hours >= 24 else "this period"
        return Signal(Action.NONE, reason=f"entry window closed for {scope}")

    abs_stretch = abs(stretch_pct)
    if abs_stretch < cfg.min_stretch_pct:
        return Signal(
            Action.NONE,
            reason=f"stretch {stretch_pct:+.2f}% < {cfg.min_stretch_pct}% minimum",
        )
    if abs_stretch > cfg.max_stretch_pct:
        return Signal(
            Action.NONE,
            reason=f"stretch {stretch_pct:+.2f}% > {cfg.max_stretch_pct}% "
                   "— possible momentum day (death trap), skipping",
        )

    if not (cfg.min_share_price <= share_price <= cfg.max_share_price):
        return Signal(
            Action.NONE,
            reason=f"share price {share_price:.2f} outside "
                   f"{cfg.min_share_price:.2f}-{cfg.max_share_price:.2f} range",
        )

    side = target_side(stretch_pct)
    return Signal(
        Action.ENTER,
        side=side,
        reason=f"stretch {stretch_pct:+.2f}% in range, {side} share at "
               f"{share_price:.2f} — mean reversion entry",
    )


def evaluate_exit(
    now_utc: dt.datetime,
    position: Position,
    share_price: Optional[float],
    cfg: StrategyConfig = StrategyConfig(),
) -> Signal:
    """Dapat bang lumabas? Tawagin lang ito kapag MAY open position."""
    if share_price is None:
        return Signal(Action.NONE, reason="waiting for data")

    change_pct = (share_price - position.entry_price) / position.entry_price * 100.0
    EPS = 1e-9  # floating-point tolerance sa boundary comparisons

    if change_pct >= cfg.profit_target_pct - EPS:
        return Signal(
            Action.EXIT,
            reason=f"profit target hit: {change_pct:+.0f}% "
                   f"(entry {position.entry_price:.2f} -> {share_price:.2f})",
        )

    if change_pct <= -cfg.stop_loss_pct + EPS:
        return Signal(
            Action.EXIT,
            reason=f"stop loss hit: {change_pct:+.0f}% "
                   f"(entry {position.entry_price:.2f} -> {share_price:.2f})",
        )

    if hours_into_period(now_utc, cfg.period_hours) >= cfg.eod_exit_hour:
        return Signal(
            Action.EXIT,
            reason=f"end-of-period force exit ({change_pct:+.0f}%) — "
                   "never hold to settlement",
        )

    return Signal(Action.NONE, reason=f"holding ({change_pct:+.0f}%)")

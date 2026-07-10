"""Position resume pagkatapos ng app restart — pure decision logic.

Ang open position ay naka-persist sa SQLite (db.save_open_position) tuwing
BUY at binubura tuwing SELL. Sa pag-START ng bot, dinedesisyunan dito kung
ire-restore ito sa executor:

- Ibang UTC day na  -> STALE: settled na ang daily market, huwag i-restore
- Ibang mode        -> huwag i-restore (pero kung LIVE ang naiwan, i-ERROR
                       nang malakas — may totoong pera pang nakalagay doon)
- Same day + mode   -> i-restore
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from src.strategy.mean_reversion import Position


def decide_restore(
    saved: Optional[dict], mode: str, today_utc: dt.date
) -> tuple[Optional[Position], str, str]:
    """Ibinabalik ang (position | None, log_level, log_message).

    Kapag None ang position, dapat i-clear ng caller ang saved record
    (maliban kung walang saved talaga — blanko rin ang message doon).
    """
    if not saved:
        return None, "", ""

    try:
        entry_ts = dt.datetime.fromisoformat(saved["entry_ts"])
        position = Position(
            side=saved["side"],
            entry_price=float(saved["entry_price"]),
            shares=float(saved["shares"]),
            entry_ts=entry_ts,
        )
        saved_mode = saved["mode"]
        market = saved.get("market", "?")
    except (KeyError, ValueError, TypeError) as e:
        return None, "WARN", f"Corrupt saved position discarded ({e})"

    if entry_ts.date() != today_utc:
        return None, "WARN", (
            f"Stale open position from {entry_ts.date().isoformat()} discarded "
            f"— settled na ang daily market ({market})"
        )

    if saved_mode != mode:
        if saved_mode == "LIVE":
            # May TOTOONG position pa sa Polymarket na hindi natin mata-track
            # sa paper mode — ipaalam nang malakas sa user.
            return None, "ERROR", (
                f"May naiwang LIVE position sa Polymarket ({position.side} "
                f"{position.shares:,.1f} shares @ {position.entry_price:.2f}, "
                f"{market}) pero PAPER mode ka ngayon — hindi ito mata-track. "
                "I-manage ito manually sa polymarket.com o mag-Live mode ulit."
            )
        return None, "WARN", (
            f"Paper position discarded — {mode} mode na ngayon "
            f"(dating PAPER: {position.side} @ {position.entry_price:.2f})"
        )

    return position, "INFO", (
        f"Restored open position after restart: {position.side} "
        f"{position.shares:,.1f} shares @ {position.entry_price:.2f} ({market})"
    )

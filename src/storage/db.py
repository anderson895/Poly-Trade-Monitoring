"""SQLite storage: trades, logs, at non-secret settings.

Ang secrets (private key, API key) ay HINDI dito naka-store —
nasa Windows Credential Manager sila via core/secrets.py.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path
from typing import Any, Optional

DB_DIR = Path(__file__).resolve().parents[2] / "data"
DB_PATH = DB_DIR / "bot.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,                -- ISO-8601 UTC
    market TEXT NOT NULL,            -- e.g. 'BTC Up/Down 2026-07-10'
    side TEXT NOT NULL,              -- 'UP' | 'DOWN'
    action TEXT NOT NULL,            -- 'BUY' | 'SELL'
    price REAL NOT NULL,             -- share price (0.00-1.00)
    size REAL NOT NULL,              -- USDC amount
    status TEXT NOT NULL,            -- 'OPEN' | 'FILLED' | 'CANCELLED'
    pnl REAL                         -- realized PnL sa SELL
);

CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    level TEXT NOT NULL,             -- 'INFO' | 'WARN' | 'ERROR' | 'TRADE'
    message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path = DB_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ---------------------------------------------------------------- logs

    def add_log(self, level: str, message: str) -> None:
        self._conn.execute(
            "INSERT INTO logs (ts, level, message) VALUES (?, ?, ?)",
            (_utc_now(), level, message),
        )
        self._conn.commit()

    def recent_logs(self, limit: int = 200) -> list[sqlite3.Row]:
        cur = self._conn.execute(
            "SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,)
        )
        return cur.fetchall()

    def clear_logs(self) -> None:
        self._conn.execute("DELETE FROM logs")
        self._conn.commit()

    # -------------------------------------------------------------- trades

    def add_trade(
        self,
        market: str,
        side: str,
        action: str,
        price: float,
        size: float,
        status: str = "OPEN",
        pnl: Optional[float] = None,
    ) -> int:
        cur = self._conn.execute(
            "INSERT INTO trades (ts, market, side, action, price, size, status, pnl)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (_utc_now(), market, side, action, price, size, status, pnl),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def recent_trades(self, limit: int = 100) -> list[sqlite3.Row]:
        cur = self._conn.execute(
            "SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,)
        )
        return cur.fetchall()

    def total_pnl(self) -> float:
        cur = self._conn.execute(
            "SELECT COALESCE(SUM(pnl), 0) FROM trades WHERE pnl IS NOT NULL"
        )
        return float(cur.fetchone()[0])

    def trade_stats(self) -> dict:
        cur = self._conn.execute(
            "SELECT COUNT(*) AS n,"
            " SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS wins,"
            " SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) AS losses"
            " FROM trades WHERE action = 'SELL'"
        )
        row = cur.fetchone()
        return {
            "closed": row["n"] or 0,
            "wins": row["wins"] or 0,
            "losses": row["losses"] or 0,
        }

    # ------------------------------------------------------------ settings

    def get_setting(self, key: str, default: Any = None) -> Any:
        cur = self._conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        return row["value"] if row is not None else default

    def set_setting(self, key: str, value: Any) -> None:
        self._conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
        self._conn.commit()


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

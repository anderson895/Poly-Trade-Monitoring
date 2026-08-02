"""Historical klines para sa offline tooling (backtests, scans).

Iba ito sa mga live feed: **sync** at **range-based** (mula petsa A
hanggang B), samantalang ang `CoinbaseMarketFeed` ay count-based at
paatras mula ngayon. Ang mga backtest script ay sync at humihingi ng
tiyak na saklaw ng kasaysayan, kaya sariling paging ang kailangan.

Sinusuportahan ang Binance AT Coinbase para tumakbo ang tooling kahit sa
US VPS, kung saan sinasagot ng Binance ang HTTP 451.

Ang volume ng dalawa ay pareho sa base asset (BTC), kaya direktang
maikukumpara ang mga resulta.
"""
from __future__ import annotations

import datetime as dt
import logging
import time
from typing import Optional

import httpx

from src.feed.coinbase_market import (
    DERIVED,
    GRANULARITY,
    PRODUCT_ID,
    aggregate_rows,
)

filelog = logging.getLogger("polytrade.history")

BINANCE_REST = "https://api.binance.com"
COINBASE_REST = "https://api.exchange.coinbase.com"

BINANCE_MAX = 1000  # candles kada request
COINBASE_MAX = 300

BINANCE_PING = f"{BINANCE_REST}/api/v3/ping"
PROBE_TIMEOUT = 8.0
PAGE_DELAY = 0.15  # huwag i-hammer ang API

# (ts, open, high, low, close, volume) — pareho ng shape sa mga feed
Row = tuple


def interval_secs(interval: str) -> int:
    """Haba ng isang candle sa segundo (kasama ang derived na 4h/1w)."""
    if interval in DERIVED:
        base, factor = DERIVED[interval]
        return GRANULARITY[base] * factor
    return GRANULARITY[interval]


def binance_reachable_sync() -> bool:
    """Sync na bersyon ng probe — ang tooling ay hindi async."""
    try:
        with httpx.Client(timeout=PROBE_TIMEOUT) as client:
            return client.get(BINANCE_PING).status_code == 200
    except Exception as e:
        filelog.info("Binance probe failed (%s: %s)", type(e).__name__, e)
        return False


def resolve_source_sync(setting: str = "auto") -> str:
    """"auto"/"binance"/"coinbase" -> aktwal na source."""
    source = (setting or "auto").lower()
    if source in ("binance", "coinbase"):
        return source
    return "binance" if binance_reachable_sync() else "coinbase"


def _iso(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _fetch_binance(interval: str, start_ts: float, end_ts: float) -> list[Row]:
    secs = GRANULARITY[interval] if interval not in DERIVED else None
    # Ang Binance ay may native na 4h/1w, kaya walang aggregation dito
    binance_interval = interval
    step_ms = int((secs or interval_secs(interval)) * 1000)
    start_ms, end_ms = int(start_ts * 1000), int(end_ts * 1000)
    rows: list[Row] = []
    with httpx.Client(timeout=30) as client:
        while start_ms < end_ms:
            resp = client.get(f"{BINANCE_REST}/api/v3/klines", params={
                "symbol": "BTCUSDT", "interval": binance_interval,
                "startTime": start_ms, "endTime": end_ms,
                "limit": BINANCE_MAX,
            })
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            rows += [
                (k[0] / 1000.0, float(k[1]), float(k[2]),
                 float(k[3]), float(k[4]), float(k[5]))
                for k in batch
            ]
            start_ms = batch[-1][0] + step_ms
            if len(batch) < BINANCE_MAX:
                break
            time.sleep(PAGE_DELAY)
    return rows


def _fetch_coinbase(interval: str, start_ts: float, end_ts: float) -> list[Row]:
    """Coinbase: 300 candles kada request, kaya window-by-window ang paging.

    Ang 4h/1w ay walang native granularity — kinukuha ang base (1h/1d) at
    ini-aggregate, gaya ng ginagawa ng live feed.
    """
    if interval in DERIVED:
        base, factor = DERIVED[interval]
        base_rows = _fetch_coinbase(base, start_ts, end_ts)
        return aggregate_rows(base_rows, GRANULARITY[base] * factor)

    gran = GRANULARITY[interval]
    rows: list[Row] = []
    cur = start_ts
    with httpx.Client(timeout=30) as client:
        while cur < end_ts:
            stop = min(cur + COINBASE_MAX * gran, end_ts)
            resp = client.get(
                f"{COINBASE_REST}/products/{PRODUCT_ID}/candles",
                params={"granularity": gran,
                        "start": _iso(cur), "end": _iso(stop)},
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict):  # {"message": ...} = error payload
                raise RuntimeError(
                    f"Coinbase candles error: {data.get('message', data)}"
                )
            # [time, low, high, open, close, volume], newest-first
            rows += [
                (float(c[0]), float(c[3]), float(c[2]),
                 float(c[1]), float(c[4]), float(c[5]))
                for c in data
            ]
            cur = stop
            time.sleep(PAGE_DELAY)
    return rows


def fetch_range(
    interval: str,
    start_ts: float,
    end_ts: Optional[float] = None,
    source: str = "auto",
) -> list[Row]:
    """Klines mula `start_ts` hanggang `end_ts`, oldest->newest.

    Ibinabalik ang (ts, open, high, low, close, volume) — pareho ng shape
    na ginagamit ng mga live feed. De-duplicated at naka-sort; tinatanggal
    ang in-progress na huling candle.
    """
    if end_ts is None:
        end_ts = dt.datetime.now(dt.timezone.utc).timestamp()
    resolved = resolve_source_sync(source)
    fetch = _fetch_binance if resolved == "binance" else _fetch_coinbase
    rows = fetch(interval, start_ts, end_ts)

    secs = interval_secs(interval)
    by_ts = {r[0]: r for r in rows if start_ts <= r[0] <= end_ts}
    ordered = [by_ts[ts] for ts in sorted(by_ts)]
    # Ang huling candle ay in-progress pa kung hindi pa lumilipas ang buong
    # haba nito — tinatanggal para completed candles lang ang nasa resulta
    if ordered and ordered[-1][0] + secs > end_ts:
        ordered.pop()
    return ordered


def describe_source(source: str) -> str:
    return ("Coinbase BTC-USD" if source == "coinbase"
            else "Binance BTCUSDT")

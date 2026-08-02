"""Coinbase BTC-USD market feed — drop-in kapalit ng BinanceFeed.

Kailangan ito dahil hina-harang ng Binance ang mga US IP (HTTP 451), kaya
hindi gumagana ang bot sa US-based VPS. Pareho ang public API ng klase na
ito sa ``BinanceFeed`` para pwedeng ipagpalit nang walang binabago sa
engine: start/stop, set_period, pct_from_open, last_price, daily_open,
hourly_volumes, at fetch_klines.

Tatlong pagkakaiba ng Coinbase sa Binance na inaayos dito:

1. Walang kline stream ang WebSocket — ``ticker`` channel lang (price +
   last_size kada trade), kaya ang 1m candles ay binubuo LOKAL mula sa
   ticks.
2. Limitado ang granularity ng REST candles: 60/300/900/3600/21600/86400
   lang. Walang 4h at walang 1w — ini-aggregate mula sa 1h at 1d.
3. Max 300 candles kada request — pina-page kapag mas marami ang hinihingi.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
from typing import Callable, Optional

import httpx
import websockets

from src.strategy.mean_reversion import period_start_utc

filelog = logging.getLogger("polytrade.coinbase_market")

COINBASE_WS_URL = "wss://ws-feed.exchange.coinbase.com"
COINBASE_REST_URL = "https://api.exchange.coinbase.com"
PRODUCT_ID = "BTC-USD"

PriceCallback = Callable[[float], None]
OpenCallback = Callable[[float], None]
StatusCallback = Callable[[bool], None]
HistoryCallback = Callable[[list], None]
KlineCallback = Callable[[tuple], None]
HISTORY_MINUTES = 120  # tugma sa BinanceFeed — 2 oras ng 1m candles

# Interval name -> Coinbase granularity (segundo). Ito LANG ang tinatanggap
# ng API; ang iba ay sinasagot ng "Unsupported granularity".
GRANULARITY = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600,
               "6h": 21600, "1d": 86400}
# Interval na WALA sa Coinbase -> (base interval, ilang base candles kada isa)
DERIVED = {"4h": ("1h", 4), "1w": ("1d", 7)}

MAX_CANDLES_PER_REQUEST = 300  # hard limit ng Coinbase
MAX_PAGES = 20                 # takot sa runaway loop (6000 candles)
PAGE_DELAY = 0.12              # public rate limit ay ~10 req/s

# Ang unix epoch ay Huwebes; +4 araw para Lunes ang simula ng weekly
# bucket — ganito rin ang weekly klines ng Binance.
WEEK_ALIGN_OFFSET = 345_600


def _iso(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _parse_ts(value: Optional[str]) -> float:
    """ISO-8601 ng Coinbase -> unix secs. Local UTC kung wala/masama."""
    if value:
        try:
            return dt.datetime.fromisoformat(
                value.replace("Z", "+00:00")
            ).timestamp()
        except ValueError:
            pass
    return dt.datetime.now(dt.timezone.utc).timestamp()


def bucket_start(ts: float, secs: int) -> float:
    """Aligned na simula ng bucket. Lunes ang anchor ng weekly."""
    if secs == 604_800:
        return ts - (ts - WEEK_ALIGN_OFFSET) % secs
    return ts - ts % secs


def aggregate_rows(rows: list, secs: int) -> list:
    """Pagsamahin ang (ts,o,h,l,c,v) rows sa mas malalaking bucket.

    Para sa 4h at 1w na walang katumbas na granularity sa Coinbase.
    Inaasahan na oldest->newest ang `rows`.
    """
    out: list = []
    for ts, o, h, l, c, v in rows:
        start = bucket_start(ts, secs)
        if out and out[-1][0] == start:
            p = out[-1]
            out[-1] = (p[0], p[1], max(p[2], h), min(p[3], l), c, p[5] + v)
        else:
            out.append((start, o, h, l, c, v))
    return out


class CoinbaseMarketFeed:
    """Real-time BTC-USD feed with period-open ("price to beat") tracking."""

    PERIOD_SECS = {"1d": 86400, "4h": 14400, "1h": 3600, "15m": 900}

    def __init__(
        self,
        on_price: PriceCallback,
        on_daily_open: OpenCallback,
        on_status: StatusCallback,
        on_history: Optional[HistoryCallback] = None,
        on_kline: Optional[KlineCallback] = None,
    ) -> None:
        self._on_price = on_price
        self._on_daily_open = on_daily_open
        self._on_status = on_status
        self._on_history = on_history
        self._on_kline = on_kline
        self._history_sent = False
        self._task: Optional[asyncio.Task] = None
        self._period_interval = "1d"
        self._period_start: Optional[float] = None
        self.last_price: Optional[float] = None
        self.daily_open: Optional[float] = None
        self.hourly_volumes: list[float] = []
        self._volumes_fetched_at: float = 0.0
        # In-progress na 1m candle na binubuo mula sa ticks
        self._candle: Optional[tuple] = None

    # ------------------------------------------------------------------ API

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="coinbase-market-feed")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._on_status(False)

    def set_period(self, interval: str) -> None:
        """Palitan ang market period ("1d", "4h", "1h", "15m")."""
        if interval != self._period_interval:
            self._period_interval = interval
            self._period_start = None  # pipilitin ang refresh sa susunod na tick

    @property
    def pct_from_open(self) -> Optional[float]:
        """% distance ng current price mula sa PERIOD open (stretch)."""
        if self.last_price is None or not self.daily_open:
            return None
        return (self.last_price - self.daily_open) / self.daily_open * 100.0

    # ------------------------------------------------------------------ REST

    async def _get_candles(
        self,
        client: httpx.AsyncClient,
        granularity: int,
        start: Optional[float] = None,
        end: Optional[float] = None,
    ) -> list:
        """Isang raw candles request -> (ts,o,h,l,c,v) rows, oldest->newest.

        Ang Coinbase ay nagbabalik ng [time, low, high, open, close, volume]
        na newest-first — hindi ito ang pagkakasunod ng Binance, kaya dito
        na natin isinasalin para pare-pareho ang lahat ng caller.
        """
        params: dict = {"granularity": granularity}
        if start is not None and end is not None:
            params["start"] = _iso(start)
            params["end"] = _iso(end)
        resp = await client.get(f"/products/{PRODUCT_ID}/candles", params=params)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):  # {"message": "..."} = error payload
            raise RuntimeError(f"Coinbase candles error: {data.get('message', data)}")
        rows = [
            (float(c[0]), float(c[3]), float(c[2]),
             float(c[1]), float(c[4]), float(c[5]))
            for c in data
        ]
        rows.sort(key=lambda r: r[0])
        return rows

    async def _fetch_base(
        self, client: httpx.AsyncClient, interval: str, limit: int
    ) -> list:
        """Kunin ang `limit` na candles ng natively-supported na interval.

        Pina-page pabalik sa nakaraan dahil 300 lang ang max kada request.
        """
        granularity = GRANULARITY[interval]
        by_ts: dict[float, tuple] = {}
        end: Optional[float] = None
        for _ in range(MAX_PAGES):
            if len(by_ts) >= limit:
                break
            chunk = min(limit - len(by_ts), MAX_CANDLES_PER_REQUEST)
            if end is None:
                rows = await self._get_candles(client, granularity)
            else:
                rows = await self._get_candles(
                    client, granularity, start=end - chunk * granularity, end=end
                )
            if not rows:
                break  # naubos na ang history ng product
            for row in rows:
                by_ts[row[0]] = row
            end = rows[0][0]  # susunod na page ay magtatapos sa pinakaluma nito
            await asyncio.sleep(PAGE_DELAY)
        ordered = [by_ts[ts] for ts in sorted(by_ts)]
        return ordered[-limit:]

    async def _fetch_rows(
        self, client: httpx.AsyncClient, interval: str, limit: int
    ) -> list:
        """Rows para sa kahit anong interval — kasama ang derived (4h/1w)."""
        if interval in DERIVED:
            base, factor = DERIVED[interval]
            # +1 bucket na sobra para hindi mapudpod ang pinakalumang bucket
            base_rows = await self._fetch_base(client, base, (limit + 1) * factor)
            merged = aggregate_rows(base_rows, GRANULARITY[base] * factor)
            return merged[-limit:]
        return await self._fetch_base(client, interval, limit)

    async def fetch_klines(self, interval: str, limit: int) -> list:
        """Kunin ang klines bilang (ts,o,h,l,c,v) rows.

        TINATANGGAL ang huling kline — in-progress pa ito, kaya gugulo ang
        linya kapag pinaghalo sa live ticks (hindi monotonic ang timestamps).
        """
        async with httpx.AsyncClient(base_url=COINBASE_REST_URL, timeout=20) as client:
            rows = await self._fetch_rows(client, interval, limit)
        return rows[:-1]

    # ------------------------------------------------------------- internals

    async def _run(self) -> None:
        while True:
            try:
                await self._refresh_daily_open()
                await self._refresh_volumes()
                await self._send_history()
                async with websockets.connect(COINBASE_WS_URL, ping_interval=20) as ws:
                    await ws.send(json.dumps({
                        "type": "subscribe",
                        "product_ids": [PRODUCT_ID],
                        "channels": ["ticker"],
                    }))
                    self._on_status(True)
                    async for raw in ws:
                        msg = json.loads(raw)
                        kind = msg.get("type")
                        if kind == "error":
                            raise RuntimeError(
                                f"Coinbase WS error: {msg.get('message')}"
                            )
                        if kind != "ticker" or "price" not in msg:
                            continue  # subscriptions/heartbeat — huwag i-crash
                        price = float(msg["price"])
                        self.last_price = price
                        self._update_candle(
                            price,
                            float(msg.get("last_size") or 0.0),
                            msg.get("time"),
                        )
                        self._on_price(price)
                        await self._check_day_rollover()
                        await self._maybe_refresh_volumes()
            except asyncio.CancelledError:
                raise
            except Exception:
                filelog.exception("Coinbase feed error (reconnecting in 5s):")
                self._on_status(False)
                await asyncio.sleep(5)  # backoff bago mag-reconnect

    def _update_candle(self, price: float, size: float, ts_iso: Optional[str]) -> None:
        """Buuin ang 1m candle mula sa ticks — walang kline stream ang Coinbase.

        Ginagamit ang oras ng exchange (hindi lokal na orasan) para hindi
        mapunta sa maling minuto ang tick kapag may clock skew ang VPS.
        """
        bucket = bucket_start(_parse_ts(ts_iso), 60)
        cur = self._candle
        if cur is not None and bucket < cur[0]:
            return  # huli nang dumating, luma na ang bucket — huwag baguhin
        if cur is None or bucket > cur[0]:
            cur = (bucket, price, price, price, price, size)
        else:
            cur = (cur[0], cur[1], max(cur[2], price), min(cur[3], price),
                   price, cur[5] + size)
        self._candle = cur
        if self._on_kline is not None:
            self._on_kline(cur)

    async def _refresh_daily_open(self) -> None:
        """Kunin ang 'Price to Beat' ng KASALUKUYANG period.

        1d (Polymarket daily): ang strike ay ang CLOSE ng 1m candle sa
        nakaraang TANGHALI ET. 4h/1h/15m: open ng in-progress na period
        candle (UTC-aligned).
        """
        async with httpx.AsyncClient(base_url=COINBASE_REST_URL, timeout=15) as client:
            if self._period_interval == "1d":
                anchor = period_start_utc(
                    dt.datetime.now(dt.timezone.utc), "daily"
                ).timestamp()
                # Maluwag na window: kung walang trade eksakto sa minutong
                # iyon, ang huling candle bago ang anchor ang gagamitin
                rows = await self._get_candles(
                    client, 60, start=anchor - 600, end=anchor + 60
                )
                usable = [r for r in rows if r[0] <= anchor]
                if not usable:
                    raise RuntimeError(
                        f"walang 1m candle sa paligid ng anchor {_iso(anchor)}"
                    )
                self.daily_open = usable[-1][4]  # index 4 = close (strike)
                self._period_start = anchor
            else:
                secs = self.PERIOD_SECS[self._period_interval]
                aligned = bucket_start(
                    dt.datetime.now(dt.timezone.utc).timestamp(), secs
                )
                # Ang 4h ay walang native granularity — 1h candles ang base,
                # at ang open ng UNANG 1h candle ng bucket ang period open
                base = "1h" if self._period_interval == "4h" else self._period_interval
                rows = await self._get_candles(
                    client, GRANULARITY[base], start=aligned, end=aligned + secs
                )
                usable = [r for r in rows if r[0] >= aligned]
                if not usable:
                    raise RuntimeError(
                        f"walang {base} candle sa period start {_iso(aligned)}"
                    )
                self.daily_open = usable[0][1]  # index 1 = open price
                self._period_start = aligned
            self._on_daily_open(self.daily_open)

    async def _send_history(self) -> None:
        """Isang beses na 1m-kline history para agad may laman ang chart."""
        if self._history_sent or self._on_history is None:
            return
        rows = await self.fetch_klines("1m", HISTORY_MINUTES)
        self._history_sent = True
        self._on_history(rows)

    async def _check_day_rollover(self) -> None:
        """Mag-refresh ng period open kapag pumasok na sa bagong period."""
        now_utc = dt.datetime.now(dt.timezone.utc)
        if self._period_interval == "1d":
            aligned = period_start_utc(now_utc, "daily").timestamp()
        else:
            aligned = bucket_start(
                now_utc.timestamp(), self.PERIOD_SECS[self._period_interval]
            )
        if self._period_start is None or aligned != self._period_start:
            await self._refresh_daily_open()

    async def _refresh_volumes(self) -> None:
        """Hourly volumes para sa volume escalation filter.

        25 candles tapos tinatanggal ang huli (in-progress pa), para
        completed hours lang ang ginagamit sa comparison — gaya ng Binance.
        """
        async with httpx.AsyncClient(base_url=COINBASE_REST_URL, timeout=15) as client:
            rows = await self._get_candles(client, GRANULARITY["1h"])
        self.hourly_volumes = [r[5] for r in rows[-25:-1]]
        self._volumes_fetched_at = dt.datetime.now(dt.timezone.utc).timestamp()

    async def _maybe_refresh_volumes(self) -> None:
        now = dt.datetime.now(dt.timezone.utc).timestamp()
        if now - self._volumes_fetched_at >= 300:  # kada 5 minuto
            await self._refresh_volumes()

"""Unit tests para sa Coinbase market feed at data-source selection.

Walang network dito — mock lahat ng HTTP. Ang layunin ay ang mga bahaging
madaling masira nang tahimik: ang pagsasalin ng candle format (iba ang
column order ng Coinbase sa Binance), ang aggregation ng 4h/1w na walang
native granularity, ang 300-candle pagination, at ang pagbuo ng 1m candle
mula sa ticks.

Run:  .\\venv\\Scripts\\python.exe -m unittest tests.test_coinbase_feed -v
"""
from __future__ import annotations

import asyncio
import datetime as dt
import unittest
from unittest import mock

from src.feed.coinbase_market import (
    CoinbaseMarketFeed,
    aggregate_rows,
    bucket_start,
)
from src.feed.source import make_feed, resolve_source


def noop_feed(**overrides) -> CoinbaseMarketFeed:
    kwargs = {"on_price": lambda p: None, "on_daily_open": lambda o: None,
              "on_status": lambda s: None}
    kwargs.update(overrides)
    return CoinbaseMarketFeed(**kwargs)


def cb_candle(ts: int, low: float, high: float, o: float, c: float, v: float) -> list:
    """Isang raw Coinbase candle: [time, low, high, open, close, volume]."""
    return [ts, low, high, o, c, v]


class FakeResponse:
    def __init__(self, payload) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self):
        return self._payload


class FakeClient:
    """Sumasagot ng candles ayon sa hinihinging start/end window."""

    def __init__(self, pages: list) -> None:
        self.pages = list(pages)
        self.calls: list[dict] = []

    async def get(self, url, params=None):
        self.calls.append(dict(params or {}))
        return FakeResponse(self.pages.pop(0) if self.pages else [])


class TestBucketing(unittest.TestCase):
    def test_minute_bucket(self) -> None:
        self.assertEqual(bucket_start(1785634837.9, 60), 1785634800)

    def test_four_hour_bucket_is_utc_aligned(self) -> None:
        ts = dt.datetime(2026, 8, 2, 5, 37, tzinfo=dt.timezone.utc).timestamp()
        got = dt.datetime.fromtimestamp(bucket_start(ts, 14400), dt.timezone.utc)
        self.assertEqual(got.hour, 4)

    def test_weekly_bucket_starts_on_monday(self) -> None:
        # Ang unix epoch ay Huwebes — kung mali ang offset, Huwebes ang
        # lalabas dito imbes na Lunes (gaya ng weekly klines ng Binance)
        ts = dt.datetime(2026, 8, 2, 12, 0, tzinfo=dt.timezone.utc).timestamp()
        start = dt.datetime.fromtimestamp(bucket_start(ts, 604800), dt.timezone.utc)
        self.assertEqual(start.weekday(), 0)
        self.assertEqual(start.hour, 0)


class TestAggregation(unittest.TestCase):
    def test_four_1h_rows_merge_into_one_4h_row(self) -> None:
        base = [
            (0, 100.0, 110.0, 95.0, 105.0, 1.0),
            (3600, 105.0, 120.0, 104.0, 118.0, 2.0),
            (7200, 118.0, 119.0, 90.0, 92.0, 3.0),
            (10800, 92.0, 99.0, 91.0, 98.0, 4.0),
        ]
        (ts, o, h, l, c, v), = aggregate_rows(base, 14400)
        self.assertEqual(ts, 0)
        self.assertEqual(o, 100.0)   # open ng UNA
        self.assertEqual(h, 120.0)   # pinakamataas na high
        self.assertEqual(l, 90.0)    # pinakamababang low
        self.assertEqual(c, 98.0)    # close ng HULI
        self.assertEqual(v, 10.0)    # suma ng volume

    def test_partial_bucket_stays_separate(self) -> None:
        base = [(0, 1, 2, 1, 2, 1.0), (3600, 2, 3, 2, 3, 1.0), (14400, 3, 4, 3, 4, 1.0)]
        merged = aggregate_rows(base, 14400)
        self.assertEqual([r[0] for r in merged], [0, 14400])


class TestCandleParsing(unittest.IsolatedAsyncioTestCase):
    async def test_coinbase_column_order_is_translated(self) -> None:
        # Coinbase: [time, low, high, open, close, volume]
        # Natin:    (time, open, high, low, close, volume)  <- gaya ng Binance
        client = FakeClient([[cb_candle(60, 90.0, 110.0, 95.0, 105.0, 7.0)]])
        rows = await noop_feed()._get_candles(client, 60)
        self.assertEqual(rows, [(60.0, 95.0, 110.0, 90.0, 105.0, 7.0)])

    async def test_rows_are_sorted_oldest_first(self) -> None:
        # Newest-first ang isinasagot ng Coinbase — kabaligtaran ng Binance
        client = FakeClient([[
            cb_candle(180, 1, 2, 1, 2, 1.0),
            cb_candle(120, 1, 2, 1, 2, 1.0),
            cb_candle(60, 1, 2, 1, 2, 1.0),
        ]])
        rows = await noop_feed()._get_candles(client, 60)
        self.assertEqual([r[0] for r in rows], [60.0, 120.0, 180.0])

    async def test_error_payload_raises(self) -> None:
        client = FakeClient([{"message": "Unsupported granularity"}])
        with self.assertRaises(RuntimeError):
            await noop_feed()._get_candles(client, 604800)


class TestPagination(unittest.IsolatedAsyncioTestCase):
    async def test_requests_are_paged_and_deduped(self) -> None:
        # 400 candles > 300 na limit ng Coinbase -> dapat dalawang request
        page1 = [cb_candle(t, 1, 2, 1, 2, 1.0)
                 for t in range(100 * 60, 400 * 60, 60)]   # 300 candles
        page2 = [cb_candle(t, 1, 2, 1, 2, 1.0)
                 for t in range(0, 100 * 60, 60)]          # 100 pa
        client = FakeClient([page1, page2])
        with mock.patch("src.feed.coinbase_market.asyncio.sleep",
                        new=mock.AsyncMock()):
            rows = await noop_feed()._fetch_base(client, "1m", 400)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(len(rows), 400)
        self.assertEqual([r[0] for r in rows], sorted(r[0] for r in rows))
        # Ang ikalawang page ay dapat magtapos kung saan nagsimula ang una
        self.assertIn("end", client.calls[1])

    async def test_stops_when_history_runs_out(self) -> None:
        client = FakeClient([[cb_candle(60, 1, 2, 1, 2, 1.0)], []])
        with mock.patch("src.feed.coinbase_market.asyncio.sleep",
                        new=mock.AsyncMock()):
            rows = await noop_feed()._fetch_base(client, "1m", 500)
        self.assertEqual(len(rows), 1)  # huminto, hindi umikot ng 20 beses


class TestTickAggregation(unittest.TestCase):
    def test_ticks_build_one_minute_candle(self) -> None:
        got: list[tuple] = []
        feed = noop_feed(on_kline=got.append)
        feed._update_candle(100.0, 1.0, "2026-08-02T01:41:05Z")
        feed._update_candle(105.0, 2.0, "2026-08-02T01:41:30Z")
        feed._update_candle(95.0, 3.0, "2026-08-02T01:41:59Z")
        ts, o, h, l, c, v = got[-1]
        self.assertEqual(o, 100.0)
        self.assertEqual(h, 105.0)
        self.assertEqual(l, 95.0)
        self.assertEqual(c, 95.0)
        self.assertEqual(v, 6.0)
        self.assertEqual(len(got), 3)  # kada tick ay may update sa chart

    def test_new_minute_starts_new_candle(self) -> None:
        got: list[tuple] = []
        feed = noop_feed(on_kline=got.append)
        feed._update_candle(100.0, 1.0, "2026-08-02T01:41:59Z")
        feed._update_candle(200.0, 5.0, "2026-08-02T01:42:00Z")
        self.assertEqual(got[-1][0] - got[0][0], 60)
        self.assertEqual(got[-1][1], 200.0)  # bagong open
        self.assertEqual(got[-1][5], 5.0)    # volume nag-reset

    def test_late_tick_from_old_minute_is_ignored(self) -> None:
        feed = noop_feed()
        feed._update_candle(200.0, 5.0, "2026-08-02T01:42:10Z")
        feed._update_candle(999.0, 5.0, "2026-08-02T01:41:10Z")  # huli dumating
        self.assertEqual(feed._candle[4], 200.0)  # hindi nagalaw ang close


class TestStretch(unittest.TestCase):
    def test_pct_from_open(self) -> None:
        feed = noop_feed()
        feed.daily_open = 100.0
        feed.last_price = 101.5
        self.assertAlmostEqual(feed.pct_from_open, 1.5)

    def test_none_without_data(self) -> None:
        self.assertIsNone(noop_feed().pct_from_open)


class TestSourceSelection(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_source_skips_probe(self) -> None:
        with mock.patch("src.feed.source.binance_reachable",
                        new=mock.AsyncMock()) as probe:
            self.assertEqual(await resolve_source("coinbase"), "coinbase")
            self.assertEqual(await resolve_source("binance"), "binance")
        probe.assert_not_called()

    async def test_auto_falls_back_to_coinbase_when_binance_blocked(self) -> None:
        with mock.patch("src.feed.source.binance_reachable",
                        new=mock.AsyncMock(return_value=False)):
            self.assertEqual(await resolve_source("auto"), "coinbase")

    async def test_auto_prefers_binance_when_reachable(self) -> None:
        with mock.patch("src.feed.source.binance_reachable",
                        new=mock.AsyncMock(return_value=True)):
            self.assertEqual(await resolve_source("auto"), "binance")

    async def test_unknown_setting_is_treated_as_auto(self) -> None:
        with mock.patch("src.feed.source.binance_reachable",
                        new=mock.AsyncMock(return_value=False)):
            self.assertEqual(await resolve_source("kraken"), "coinbase")

    def test_both_feeds_share_the_same_public_api(self) -> None:
        # Drop-in dapat ang Coinbase feed — kung may madagdag sa BinanceFeed
        # na wala sa Coinbase, dito dapat masira, hindi sa runtime ng VPS
        cbs = {"on_price": lambda p: None, "on_daily_open": lambda o: None,
               "on_status": lambda s: None}
        binance, coinbase = make_feed("binance", **cbs), make_feed("coinbase", **cbs)
        for name in ("start", "stop", "set_period", "pct_from_open",
                     "fetch_klines", "last_price", "daily_open",
                     "hourly_volumes"):
            self.assertTrue(hasattr(binance, name), name)
            self.assertTrue(hasattr(coinbase, name), name)


if __name__ == "__main__":
    unittest.main()

"""Unit tests para sa historical kline fetcher ng offline tooling.

Walang network — mock lahat. Ang mahalaga rito ay ang mga bagay na
tahimik na nagkakamali: magkaibang column order ng dalawang exchange,
magkaibang paging scheme (Binance = pasulong mula startTime, Coinbase =
window-by-window dahil 300 lang ang cap), at ang pagtanggal ng
in-progress na huling candle.

Run:  .\\venv\\Scripts\\python.exe -m unittest tests.test_history -v
"""
from __future__ import annotations

import unittest
from unittest import mock

from src.feed import history
from src.feed.history import fetch_range, interval_secs, resolve_source_sync


class FakeResponse:
    def __init__(self, payload) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, pages) -> None:
        self.pages = list(pages)
        self.calls: list[dict] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def get(self, url, params=None):
        self.calls.append(dict(params or {}))
        return FakeResponse(self.pages.pop(0) if self.pages else [])


def patch_client(pages):
    """I-patch ang httpx.Client at ang page delay ng history module."""
    client = FakeClient(pages)
    return client, mock.patch.multiple(
        history,
        httpx=mock.Mock(Client=mock.Mock(return_value=client)),
        PAGE_DELAY=0,
    )


def binance_kline(ts_s: int, o: float, h: float, l: float,
                  c: float, v: float) -> list:
    """[openTime_ms, open, high, low, close, volume, ...]"""
    return [ts_s * 1000, o, h, l, c, v, 0, 0, 0, 0, 0, 0]


def coinbase_candle(ts_s: int, low: float, high: float, o: float,
                    c: float, v: float) -> list:
    """[time_s, low, high, open, close, volume]"""
    return [ts_s, low, high, o, c, v]


class TestIntervalSecs(unittest.TestCase):
    def test_native_intervals(self) -> None:
        self.assertEqual(interval_secs("1m"), 60)
        self.assertEqual(interval_secs("15m"), 900)
        self.assertEqual(interval_secs("1d"), 86400)

    def test_derived_intervals(self) -> None:
        # Walang native na 4h/1w sa Coinbase — dapat pa rin tama ang haba
        self.assertEqual(interval_secs("4h"), 14400)
        self.assertEqual(interval_secs("1w"), 604800)


class TestBinanceFetch(unittest.TestCase):
    def test_column_order_and_ordering(self) -> None:
        pages = [[binance_kline(60, 1.0, 3.0, 0.5, 2.0, 9.0)]]
        client, patcher = patch_client(pages)
        with patcher:
            rows = fetch_range("1m", 0, 600, source="binance")
        self.assertEqual(rows, [(60.0, 1.0, 3.0, 0.5, 2.0, 9.0)])

    def test_pages_forward_from_last_timestamp(self) -> None:
        full = [binance_kline(t, 1, 2, 1, 2, 1.0)
                for t in range(0, 1000 * 60, 60)]          # 1000 = full page
        tail = [binance_kline(t, 1, 2, 1, 2, 1.0)
                for t in range(1000 * 60, 1100 * 60, 60)]  # 100 = last page
        client, patcher = patch_client([full, tail])
        with patcher:
            rows = fetch_range("1m", 0, 1200 * 60, source="binance")
        self.assertEqual(len(client.calls), 2)
        # Ang ikalawang request ay dapat magsimula pagkatapos ng huling candle
        self.assertEqual(client.calls[1]["startTime"], 1000 * 60 * 1000)
        self.assertEqual(len(rows), 1100)


class TestCoinbaseFetch(unittest.TestCase):
    def test_column_order_is_translated(self) -> None:
        # Coinbase: [time, low, high, open, close, volume]
        pages = [[coinbase_candle(60, 0.5, 3.0, 1.0, 2.0, 9.0)]]
        client, patcher = patch_client(pages)
        with patcher:
            rows = fetch_range("1m", 0, 600, source="coinbase")
        self.assertEqual(rows, [(60.0, 1.0, 3.0, 0.5, 2.0, 9.0)])

    def test_newest_first_response_is_sorted(self) -> None:
        pages = [[coinbase_candle(t, 1, 2, 1, 2, 1.0)
                  for t in (180, 120, 60)]]
        client, patcher = patch_client(pages)
        with patcher:
            rows = fetch_range("1m", 0, 600, source="coinbase")
        self.assertEqual([r[0] for r in rows], [60.0, 120.0, 180.0])

    def test_windows_are_capped_at_300_candles(self) -> None:
        # 700 minuto ng 1m candles -> 3 window (300 + 300 + 100)
        pages = [
            [coinbase_candle(t, 1, 2, 1, 2, 1.0)
             for t in range(s * 60, min(s + 300, 700) * 60, 60)]
            for s in (0, 300, 600)
        ]
        client, patcher = patch_client(pages)
        with patcher:
            rows = fetch_range("1m", 0, 700 * 60, source="coinbase")
        self.assertEqual(len(client.calls), 3)
        self.assertEqual(len(rows), 700)
        self.assertEqual([r[0] for r in rows], sorted(r[0] for r in rows))

    def test_error_payload_raises(self) -> None:
        client, patcher = patch_client([{"message": "Unsupported granularity"}])
        with patcher, self.assertRaises(RuntimeError):
            fetch_range("1m", 0, 600, source="coinbase")


class TestRangeTrimming(unittest.TestCase):
    def test_candles_outside_range_are_dropped(self) -> None:
        pages = [[binance_kline(t, 1, 2, 1, 2, 1.0)
                  for t in (0, 60, 120, 180, 240)]]
        client, patcher = patch_client(pages)
        with patcher:
            rows = fetch_range("1m", 60, 180, source="binance")
        self.assertEqual([r[0] for r in rows], [60.0, 120.0])

    def test_in_progress_last_candle_is_dropped(self) -> None:
        # end_ts ay nasa gitna ng candle sa 120 -> hindi pa ito kumpleto
        pages = [[binance_kline(t, 1, 2, 1, 2, 1.0) for t in (60, 120)]]
        client, patcher = patch_client(pages)
        with patcher:
            rows = fetch_range("1m", 0, 150, source="binance")
        self.assertEqual([r[0] for r in rows], [60.0])

    def test_duplicate_timestamps_are_deduped(self) -> None:
        pages = [[binance_kline(60, 1, 2, 1, 2, 1.0),
                  binance_kline(60, 1, 2, 1, 2, 1.0),
                  binance_kline(120, 1, 2, 1, 2, 1.0)]]
        client, patcher = patch_client(pages)
        with patcher:
            rows = fetch_range("1m", 0, 600, source="binance")
        self.assertEqual([r[0] for r in rows], [60.0, 120.0])


class TestSyncSourceResolution(unittest.TestCase):
    def test_explicit_source_skips_probe(self) -> None:
        with mock.patch.object(history, "binance_reachable_sync") as probe:
            self.assertEqual(resolve_source_sync("coinbase"), "coinbase")
            self.assertEqual(resolve_source_sync("binance"), "binance")
        probe.assert_not_called()

    def test_auto_falls_back_when_binance_blocked(self) -> None:
        with mock.patch.object(history, "binance_reachable_sync",
                               return_value=False):
            self.assertEqual(resolve_source_sync("auto"), "coinbase")

    def test_auto_prefers_binance_when_reachable(self) -> None:
        with mock.patch.object(history, "binance_reachable_sync",
                               return_value=True):
            self.assertEqual(resolve_source_sync("auto"), "binance")


if __name__ == "__main__":
    unittest.main()

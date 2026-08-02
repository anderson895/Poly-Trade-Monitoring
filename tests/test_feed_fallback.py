"""Runtime fallback sa Coinbase kapag bumagsak ang Binance feed.

Ang launch-time probe ay hindi sapat: sa VPS ay pumasa ang REST ping pero
naka-block ang WebSocket, kaya napili ang Binance at walang katapusang
nagre-reconnect ang feed — patay ang chart, walang presyo. Dito
sinisiguradong lumilipat na ang engine sa halip na umikot nang tuluyan.

Run:  .\\venv\\Scripts\\python.exe -m unittest tests.test_feed_fallback -v
"""
from __future__ import annotations

import asyncio
import pathlib
import tempfile
import unittest
from unittest import mock

from src.core.engine import FEED_FAILURE_LIMIT, BotEngine
from src.feed.coinbase_market import CoinbaseMarketFeed
from src.storage.db import Database


def make_engine(source_setting: str = "auto") -> BotEngine:
    db = Database(pathlib.Path(tempfile.mkdtemp()) / "t.db")
    db.set_setting("market_data_source", source_setting)
    return BotEngine(db)


class TestRuntimeFallback(unittest.IsolatedAsyncioTestCase):
    async def test_repeated_binance_failures_switch_to_coinbase(self) -> None:
        eng = make_engine("auto")
        eng._auto_source = True
        eng._feed = mock.Mock(stop=mock.AsyncMock())
        with mock.patch.object(eng, "_start_feed_sync") as restart:
            for _ in range(FEED_FAILURE_LIMIT):
                eng._handle_feed_status(False)
            await asyncio.sleep(0)  # hayaang tumakbo ang switch task
        restart.assert_called_once_with("coinbase", fell_back=True)
        eng._feed.stop.assert_awaited_once()

    async def test_below_the_limit_does_not_switch(self) -> None:
        eng = make_engine("auto")
        eng._auto_source = True
        with mock.patch.object(eng, "_start_feed_sync") as restart:
            for _ in range(FEED_FAILURE_LIMIT - 1):
                eng._handle_feed_status(False)
            await asyncio.sleep(0)
        restart.assert_not_called()

    async def test_a_successful_connect_resets_the_counter(self) -> None:
        # Panandaliang blip ay hindi dapat magpalipat ng source
        eng = make_engine("auto")
        eng._auto_source = True
        with mock.patch.object(eng, "_start_feed_sync") as restart:
            for _ in range(FEED_FAILURE_LIMIT - 1):
                eng._handle_feed_status(False)
            eng._handle_feed_status(True)   # nakabalik
            eng._handle_feed_status(False)
            await asyncio.sleep(0)
        restart.assert_not_called()
        self.assertEqual(eng._feed_failures, 1)

    async def test_explicit_binance_choice_is_respected(self) -> None:
        # Kung tahasang pinili ng user ang Binance, huwag itong palitan
        eng = make_engine("binance")
        eng._auto_source = False
        with mock.patch.object(eng, "_start_feed_sync") as restart:
            for _ in range(FEED_FAILURE_LIMIT * 2):
                eng._handle_feed_status(False)
            await asyncio.sleep(0)
        restart.assert_not_called()

    async def test_coinbase_failures_do_not_loop_back(self) -> None:
        # Nasa Coinbase na — wala nang mapipiling iba, huwag mag-switch
        eng = make_engine("auto")
        eng._auto_source = True
        eng._feed_source = "coinbase"
        with mock.patch.object(eng, "_start_feed_sync") as restart:
            for _ in range(FEED_FAILURE_LIMIT * 2):
                eng._handle_feed_status(False)
            await asyncio.sleep(0)
        restart.assert_not_called()

    async def test_switch_happens_only_once(self) -> None:
        eng = make_engine("auto")
        eng._auto_source = True
        eng._feed = mock.Mock(stop=mock.AsyncMock())
        with mock.patch.object(eng, "_start_feed_sync") as restart:
            for _ in range(FEED_FAILURE_LIMIT * 3):
                eng._handle_feed_status(False)
            await asyncio.sleep(0)
        self.assertEqual(restart.call_count, 1)

    async def test_status_signal_still_reaches_the_ui(self) -> None:
        eng = make_engine("auto")
        seen: list[tuple] = []
        eng.connectionChanged.connect(lambda n, up: seen.append((n, up)))
        eng._handle_feed_status(True)
        eng._handle_feed_status(False)
        self.assertEqual(seen, [("market_ws", True), ("market_ws", False)])


class TestProbeFailureDefault(unittest.IsolatedAsyncioTestCase):
    async def test_probe_error_defaults_to_coinbase_on_auto(self) -> None:
        # Ang patay na bot ay mas masama kaysa sa bahagyang maluwag na
        # strike — Coinbase ang ligtas na default kapag hindi matukoy
        eng = make_engine("auto")
        with mock.patch("src.core.engine.resolve_source",
                        side_effect=RuntimeError("probe exploded")), \
             mock.patch.object(eng, "_start_feed_sync") as started:
            await eng._start_feed()
        started.assert_called_once_with("coinbase", fell_back=True)

    async def test_probe_error_keeps_explicit_choice(self) -> None:
        eng = make_engine("coinbase")
        with mock.patch("src.core.engine.resolve_source",
                        side_effect=RuntimeError("probe exploded")), \
             mock.patch.object(eng, "_start_feed_sync") as started:
            await eng._start_feed()
        started.assert_called_once_with("coinbase", fell_back=False)


class TestFallbackWiring(unittest.IsolatedAsyncioTestCase):
    async def test_fallback_builds_a_real_coinbase_feed(self) -> None:
        eng = make_engine("auto")
        eng._auto_source = True
        eng._feed = mock.Mock(stop=mock.AsyncMock())
        await eng._fallback_to_coinbase()
        self.assertIsInstance(eng._feed, CoinbaseMarketFeed)
        self.assertEqual(eng._feed_source, "coinbase")
        self.assertEqual(eng._feed_failures, 0)
        self.assertFalse(eng._switching_source)
        await eng._feed.stop()


if __name__ == "__main__":
    unittest.main()

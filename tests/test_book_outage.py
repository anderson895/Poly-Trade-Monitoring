"""Kilos ng bot kapag bumagsak ang Polymarket order book habang LIVE.

Dalawang totoong bug ang sakop dito, parehong nakita sa production log:

1. Tuwing walang order book, tumitigil ang LAHAT ng exit checks — kasama
   ang end-of-period exit na batay lang naman sa ORAS. Kayang dumaan ang
   position sa stop loss papuntang settlement habang bagsak ang koneksyon.
2. Tahimik na nilalaktawan ang entry — walang WARN, walang bakas sa
   app.log. Dalawang buong entry window ang lumipas nang walang record.

Run:  .\\venv\\Scripts\\python.exe -m unittest tests.test_book_outage -v
"""
from __future__ import annotations

import datetime as dt
import pathlib
import tempfile
import unittest
from unittest import mock

from src.core.engine import BOOK_STALE_SECS, BotEngine
from src.execution.polymarket import LiveExecutor
from src.storage.db import Database
from src.strategy.mean_reversion import (
    Action,
    Position,
    Signal,
    StrategyConfig,
    evaluate_exit,
)

CFG = StrategyConfig()  # daily: eod_exit_hour = 23.5


def utc(hour: float) -> dt.datetime:
    """Araw na naka-anchor sa 00:00 UTC, `hour` na oras papasok."""
    base = dt.datetime(2026, 8, 11, 0, 0, tzinfo=dt.timezone.utc)
    return base + dt.timedelta(hours=hour)


def a_position(entry: float = 0.20) -> Position:
    return Position(side="DOWN", entry_price=entry, shares=1000.0,
                    entry_ts=utc(5))


class TestTimeBasedExitWithoutPrice(unittest.TestCase):
    """Ang end-of-period exit ay hindi nangangailangan ng presyo."""

    def test_exits_at_end_of_period_even_without_price(self) -> None:
        sig = evaluate_exit(utc(23.6), a_position(), None, CFG)
        self.assertIs(sig.action, Action.EXIT)
        self.assertIn("walang order book", sig.reason)

    def test_still_waits_when_period_is_not_over(self) -> None:
        sig = evaluate_exit(utc(10), a_position(), None, CFG)
        self.assertIs(sig.action, Action.NONE)
        self.assertEqual(sig.reason, "waiting for data")

    def test_priced_path_is_unchanged(self) -> None:
        # Ang dating kilos ay dapat pareho pa rin kapag may presyo
        self.assertIs(evaluate_exit(utc(14), a_position(), 0.50, CFG).action,
                      Action.EXIT)   # profit target
        self.assertIs(evaluate_exit(utc(14), a_position(), 0.09, CFG).action,
                      Action.EXIT)   # stop loss
        self.assertIs(evaluate_exit(utc(14), a_position(), 0.22, CFG).action,
                      Action.NONE)   # hawak pa
        self.assertIn("end-of-period",
                      evaluate_exit(utc(23.6), a_position(), 0.22, CFG).reason)


class TestBookAge(unittest.TestCase):
    def setUp(self) -> None:
        db = Database(pathlib.Path(tempfile.mkdtemp()) / "t.db")
        self.eng = BotEngine(db)

    def test_age_is_infinite_before_any_fetch(self) -> None:
        self.assertEqual(self.eng._book_age(), float("inf"))

    def test_age_counts_from_last_successful_fetch(self) -> None:
        now = dt.datetime.now(dt.timezone.utc).timestamp()
        self.eng._books_fetched_at = now - 30
        self.assertAlmostEqual(self.eng._book_age(), 30, delta=2)

    def test_stale_threshold_is_beyond_a_few_refresh_cycles(self) -> None:
        # Nire-refresh kada 5s — ang 60s ay ilang sunod-sunod nang pagkabigo,
        # hindi isang panandaliang blip
        self.assertGreaterEqual(BOOK_STALE_SECS, 30)


class TestSkipLogging(unittest.TestCase):
    """Ang mga skip ay dapat may bakas, pero hindi nag-spam."""

    def setUp(self) -> None:
        db = Database(pathlib.Path(tempfile.mkdtemp()) / "t.db")
        self.eng = BotEngine(db)
        self.logged: list[tuple[str, str]] = []
        self.eng.logAdded.connect(lambda lv, m: self.logged.append((lv, m)))

    def test_skip_is_logged(self) -> None:
        self.eng._log_book_skip("Entry skipped", "walang order book data")
        self.assertEqual(len(self.logged), 1)
        self.assertEqual(self.logged[0][0], "WARN")
        self.assertIn("Entry skipped", self.logged[0][1])

    def test_same_reason_does_not_spam(self) -> None:
        for _ in range(50):
            self.eng._log_book_skip("Entry skipped", "walang order book data")
        self.assertEqual(len(self.logged), 1)

    def test_different_reason_logs_again(self) -> None:
        self.eng._log_book_skip("Entry skipped", "walang order book data")
        self.eng._log_book_skip("Exit check degraded", "walang order book data")
        self.assertEqual(len(self.logged), 2)

    def test_recovery_re_arms_the_warning(self) -> None:
        self.eng._log_book_skip("Entry skipped", "walang order book data")
        self.eng._book_skip_logged = ""   # ginagawa ito ng loop kapag OK na
        self.eng._log_book_skip("Entry skipped", "walang order book data")
        self.assertEqual(len(self.logged), 2)

    def test_numbers_do_not_defeat_the_dedup(self) -> None:
        # "laos na ang order book (61s)" tapos "(66s)" = iisang klase
        for secs in (61, 66, 70, 75):
            self.eng._log_book_skip(
                "Entry skipped", f"laos na ang order book ({secs}s)"
            )
        self.assertEqual(len(self.logged), 1)


class TestExitBlockedIsLoud(unittest.IsolatedAsyncioTestCase):
    """Kapag oras nang lumabas pero walang presyo, dapat ERROR — hindi tahimik.

    Async ang mga test dahil ang matagumpay na SELL ay nag-i-schedule ng
    balance refresh via asyncio.create_task — gaya sa totoong app kung
    saan laging may tumatakbong qasync loop.
    """

    def setUp(self) -> None:
        db = Database(pathlib.Path(tempfile.mkdtemp()) / "t.db")
        self.eng = BotEngine(db)
        self.logged: list[tuple[str, str]] = []
        self.eng.logAdded.connect(lambda lv, m: self.logged.append((lv, m)))
        # spec=LiveExecutor -> pumapasa sa isinstance check ng engine
        self.executor = mock.Mock(spec=LiveExecutor)
        self.executor.MODE = "LIVE"
        self.executor.position = a_position()
        self.executor.market = mock.Mock(question="BTC Up or Down")
        self.eng.executor = self.executor
        self.eng._live_books = {}      # bagsak ang order book

    def _run_with_exit_signal(self) -> None:
        with mock.patch("src.core.engine.evaluate_exit",
                        return_value=Signal(Action.EXIT, reason="end-of-period")):
            self.eng._evaluate_strategy(stretch=1.8)

    async def test_blocked_exit_logs_an_error(self) -> None:
        self._run_with_exit_signal()
        errors = [m for lv, m in self.logged if lv == "ERROR"]
        self.assertEqual(len(errors), 1)
        self.assertIn("HINDI makakalabas", errors[0])
        self.assertIn("Manu-manong isara", errors[0])

    async def test_blocked_exit_does_not_place_an_order(self) -> None:
        # Walang presyo = walang order na maipapadala; huwag subukan
        self._run_with_exit_signal()
        self.executor.sell.assert_not_called()

    async def test_exit_still_sells_when_a_price_exists(self) -> None:
        self.eng._live_books = {"DOWN": (0.42, 0.44)}
        self.executor.sell.return_value = 44.0
        self._run_with_exit_signal()
        self.executor.sell.assert_called_once()
        self.assertEqual([lv for lv, _ in self.logged if lv == "ERROR"], [])
        self.assertTrue(any(lv == "TRADE" for lv, _ in self.logged))


if __name__ == "__main__":
    unittest.main()

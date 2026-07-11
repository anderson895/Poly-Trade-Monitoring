"""Unit tests para sa Market Timeframe feature (15m/1h/4h/daily).

Run:  .\\venv\\Scripts\\python.exe -m pytest tests\\test_timeframes.py -v
"""
from __future__ import annotations

import datetime as dt
import unittest

from src.execution.paper import estimate_otm_share_price
from src.execution.polymarket import build_market_slugs
from src.strategy.mean_reversion import (
    StrategyConfig,
    hours_into_period,
    scale_config_for_timeframe,
    stretch_scale,
)


def utc(y, mo, d, h, mi=0):
    return dt.datetime(y, mo, d, h, mi, tzinfo=dt.timezone.utc)


class TestScaling(unittest.TestCase):
    def test_daily_unchanged(self) -> None:
        cfg = scale_config_for_timeframe(StrategyConfig(), "daily")
        self.assertEqual(cfg.period_hours, 24.0)
        self.assertEqual(cfg.min_stretch_pct, 1.5)
        self.assertEqual(cfg.entry_start_hour, 4.0)
        self.assertEqual(cfg.eod_exit_hour, 23.5)

    def test_1h_scaling(self) -> None:
        cfg = scale_config_for_timeframe(StrategyConfig(), "1h")
        self.assertEqual(cfg.period_hours, 1.0)
        # sqrt(1/24) ~ 0.204 -> 1.5% * 0.204 ~ 0.306%
        self.assertAlmostEqual(cfg.min_stretch_pct, 0.306, places=2)
        self.assertAlmostEqual(cfg.max_stretch_pct, 0.510, places=2)
        # 4h ng 24h = 16.7% ng period -> 10 minuto ng 1h
        self.assertAlmostEqual(cfg.entry_start_hour, 4 / 24, places=4)
        self.assertAlmostEqual(cfg.entry_end_hour, 12 / 24, places=4)
        self.assertAlmostEqual(cfg.eod_exit_hour, 23.5 / 24, places=4)
        # Hindi ginagalaw ang share gates at profit/stop
        self.assertEqual(cfg.min_share_price, 0.15)
        self.assertEqual(cfg.profit_target_pct, 100.0)

    def test_15m_scaling(self) -> None:
        cfg = scale_config_for_timeframe(StrategyConfig(), "15m")
        self.assertEqual(cfg.period_hours, 0.25)
        self.assertAlmostEqual(cfg.min_stretch_pct, 0.153, places=2)

    def test_paper_price_scales(self) -> None:
        # Daily: 2.0% stretch -> ~20c. Sa 1h: ang katumbas ay 2.0*k%
        k = stretch_scale("1h")
        self.assertAlmostEqual(
            estimate_otm_share_price(2.0 * k, scale=k),
            estimate_otm_share_price(2.0),
            places=6,
        )


class TestHoursIntoPeriod(unittest.TestCase):
    def test_daily(self) -> None:
        self.assertAlmostEqual(
            hours_into_period(utc(2026, 7, 11, 8, 30), 24.0), 8.5
        )

    def test_1h_period(self) -> None:
        self.assertAlmostEqual(
            hours_into_period(utc(2026, 7, 11, 8, 45), 1.0), 0.75
        )

    def test_15m_period(self) -> None:
        # 08:40 -> 5 minuto sa loob ng 08:30-08:45 period? Hindi —
        # 15m boundaries: 08:30, 08:45 -> 08:40 ay 10 min = 0.1667h
        self.assertAlmostEqual(
            hours_into_period(utc(2026, 7, 11, 8, 40), 0.25), 10 / 60
        )


class TestSlugBuilders(unittest.TestCase):
    def test_daily_slugs(self) -> None:
        slugs = build_market_slugs("daily", utc(2026, 7, 11, 5))
        self.assertEqual(slugs[0], "bitcoin-up-or-down-on-july-11-2026")
        self.assertEqual(slugs[1], "bitcoin-up-or-down-on-july-11")

    def test_15m_slug_alignment(self) -> None:
        # 08:40 UTC -> period start 08:30 UTC
        now = utc(2026, 7, 11, 8, 40)
        start = int(utc(2026, 7, 11, 8, 30).timestamp())
        self.assertEqual(build_market_slugs("15m", now),
                         [f"btc-updown-15m-{start}"])

    def test_4h_slug_alignment(self) -> None:
        # 09:00 UTC -> period start 08:00 UTC (4h grid: 0,4,8,...)
        now = utc(2026, 7, 11, 9, 0)
        start = int(utc(2026, 7, 11, 8, 0).timestamp())
        self.assertEqual(build_market_slugs("4h", now),
                         [f"btc-updown-4h-{start}"])

    def test_1h_slug_et_conversion(self) -> None:
        # Hulyo = EDT (UTC-4): 13:xx UTC -> 9AM ET
        slugs = build_market_slugs("1h", utc(2026, 7, 13, 13, 25))
        self.assertEqual(slugs, ["bitcoin-up-or-down-july-13-2026-9am-et"])

    def test_1h_slug_noon_and_midnight(self) -> None:
        # 16:xx UTC Hulyo -> 12PM ET (noon)
        self.assertEqual(
            build_market_slugs("1h", utc(2026, 7, 13, 16, 5)),
            ["bitcoin-up-or-down-july-13-2026-12pm-et"],
        )
        # 04:xx UTC Hulyo -> 12AM ET (hatinggabi)
        self.assertEqual(
            build_market_slugs("1h", utc(2026, 7, 13, 4, 5)),
            ["bitcoin-up-or-down-july-13-2026-12am-et"],
        )

    def test_1h_slug_est_winter(self) -> None:
        # Enero = EST (UTC-5): 14:xx UTC -> 9AM ET
        self.assertEqual(
            build_market_slugs("1h", utc(2026, 1, 13, 14, 25)),
            ["bitcoin-up-or-down-january-13-2026-9am-et"],
        )


if __name__ == "__main__":
    unittest.main()

"""Ang stretch band at ang share price gate ay magkakabit, hindi hiwalay.

Sa paper model ay `presyo = 0.50 - 0.15 x stretch`, kaya ang pagpili ng
stretch band ay pagpili na rin ng price range. Madaling makapili ng band na
imposibleng makapasok — nangyari ito sa produksyon: 8 araw, 58 beses na
na-block sa "share price outside range", zero trade. Ang math dito ang
nagpapagana sa babala sa Settings.

Run:  .\\venv\\Scripts\\python.exe -m unittest tests.test_stretch_band -v
"""
from __future__ import annotations

import unittest

from src.execution.paper import (
    band_overlap_pct,
    estimate_otm_share_price,
    usable_stretch_band,
)
from src.strategy.mean_reversion import StrategyConfig

CFG = StrategyConfig()
GATE = (CFG.min_share_price, CFG.max_share_price)  # 0.15 - 0.25


def overlap(mn: float, mx: float) -> float:
    return band_overlap_pct(mn, mx, *GATE)


class TestUsableBand(unittest.TestCase):
    def test_default_gate_maps_to_expected_stretch_range(self) -> None:
        lo, hi = usable_stretch_band(*GATE)
        self.assertAlmostEqual(lo, 5 / 3, places=3)     # 1.667%
        self.assertAlmostEqual(hi, 7 / 3, places=3)     # 2.333%

    def test_edges_land_exactly_on_the_gate(self) -> None:
        lo, hi = usable_stretch_band(*GATE)
        self.assertAlmostEqual(estimate_otm_share_price(lo), CFG.max_share_price)
        self.assertAlmostEqual(estimate_otm_share_price(hi), CFG.min_share_price)

    def test_widening_the_gate_widens_the_band(self) -> None:
        lo, hi = usable_stretch_band(0.10, 0.30)
        base_lo, base_hi = usable_stretch_band(*GATE)
        self.assertLess(lo, base_lo)
        self.assertGreater(hi, base_hi)


class TestOverlap(unittest.TestCase):
    def test_production_failure_case_is_zero(self) -> None:
        # 0.40-0.75% — tumakbo ng 8 araw, zero trade. Dapat mahuli ito.
        self.assertEqual(overlap(0.40, 0.75), 0.0)

    def test_too_high_a_band_is_also_zero(self) -> None:
        # Lampas sa death-trap edge: mura na masyado ang share
        self.assertEqual(overlap(3.0, 4.0), 0.0)

    def test_defaults_are_usable_but_not_fully(self) -> None:
        # Ang 1.5-1.667 at 2.333-2.5 ay patay pa rin kahit default
        pct = overlap(CFG.min_stretch_pct, CFG.max_stretch_pct)
        self.assertAlmostEqual(pct, 66.7, delta=0.5)

    def test_band_inside_the_usable_range_is_fully_usable(self) -> None:
        self.assertEqual(overlap(1.7, 2.3), 100.0)

    def test_partial_overlap_is_measured(self) -> None:
        # 1.20-1.80: (1.80-1.667)/(1.80-1.20) = 22%
        self.assertAlmostEqual(overlap(1.20, 1.80), 22.2, delta=0.5)

    def test_inverted_band_is_zero_not_negative(self) -> None:
        self.assertEqual(overlap(2.5, 1.5), 0.0)

    def test_zero_width_band_does_not_divide_by_zero(self) -> None:
        self.assertEqual(overlap(2.0, 2.0), 0.0)

    def test_lowering_the_band_reduces_usability(self) -> None:
        # Ang bitag: pagbaba ng band para "mas madalas mag-trade" ay
        # siyang sumisira nito
        self.assertGreater(overlap(1.5, 2.5), overlap(1.0, 2.0))
        self.assertGreater(overlap(1.0, 2.0), overlap(0.5, 1.5))
        self.assertEqual(overlap(0.5, 1.5), 0.0)


if __name__ == "__main__":
    unittest.main()

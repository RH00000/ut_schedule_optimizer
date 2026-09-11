"""Tests for the gap_cost curve. Assert relative ordering, not exact values."""

import unittest

from scheduler.distance import gap_cost

TOO_TIGHT = gap_cost(scheduled_gap=0, walk_minutes=30)  # slack = 15 - 30 = -15
SWEET_SPOT = gap_cost(scheduled_gap=5, walk_minutes=10)  # slack = 20 - 10 = 10
TOO_LOOSE = gap_cost(scheduled_gap=60, walk_minutes=3)  # slack = 75 - 3 = 72


class GapCostOrderingTest(unittest.TestCase):
    def test_too_tight_is_most_expensive(self):
        self.assertGreater(TOO_TIGHT, TOO_LOOSE)
        self.assertGreater(TOO_TIGHT, SWEET_SPOT)

    def test_too_loose_beats_sweet_spot_but_not_too_tight(self):
        self.assertGreater(TOO_LOOSE, SWEET_SPOT)
        self.assertLess(TOO_LOOSE, TOO_TIGHT)

    def test_sweet_spot_is_cheapest(self):
        self.assertLess(SWEET_SPOT, TOO_LOOSE)
        self.assertLess(SWEET_SPOT, TOO_TIGHT)

    def test_idle_growth_slows_past_the_cap(self):
        at_45 = gap_cost(scheduled_gap=45, walk_minutes=0)  # 45 min past the annoyance threshold
        at_90 = gap_cost(scheduled_gap=90, walk_minutes=0)  # 90 min past the threshold
        self.assertLess(at_90, 3 * at_45)


if __name__ == "__main__":
    unittest.main()

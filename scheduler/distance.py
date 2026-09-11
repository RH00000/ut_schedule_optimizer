"""Walking-time estimate between two buildings. See PLAN.md §3."""

from __future__ import annotations

import json
import math
from pathlib import Path

BUILDINGS_PATH = Path(__file__).resolve().parent.parent / "data" / "buildings.json"

EARTH_RADIUS_M = 6_371_000
ROUTE_FACTOR = 1.3  # straight-line -> real-route detour fudge
WALK_SPEED_M_PER_MIN = 78  # ~4.7 km/h

# gap_cost constants are calibrated against the grade_cost / rmp_cost range from
# scores_manual.json (per-section ~0.1-0.3, schedule-level deltas ~0.05-0.15):
# three sweet-spot transitions must not outweigh a real quality difference.
# Recheck these if the grade/rmp scoring formulas change.
# EARLY_RELEASE_BUFFER_MINUTES calibrated against a real registered schedule: a
# makable 0-gap FAC->ETC hop (~11 min walk) flagged MISS at 10, sweet spot at 15.
EARLY_RELEASE_BUFFER_MINUTES = 15  # typical minutes a professor lets class out early
IDLE_ANNOYANCE_THRESHOLD_MINUTES = 15  # slack past this starts to feel like dead time
IDLE_CAP_MINUTES = 45  # slack past this reads as useful free time, not dead time
SWEET_SPOT_COST = 0.02  # flat cost when slack is comfortable
IDLE_COST_PER_MINUTE = 0.01  # gentle growth for dead time past the threshold
IDLE_CAP_COST_PER_MINUTE = 0.001  # one-tenth rate once the gap is long enough to use
MISS_BASE_COST = 2.0  # can't make the transition: dominates the objective
MISS_COST_PER_MINUTE = 0.2  # extra penalty per minute short

_buildings_cache: dict | None = None


def load_buildings(path: Path | None = None) -> dict:
    """Load buildings.json -> {key: {"lat": float, "long": float}}."""
    with open(path or BUILDINGS_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _default_buildings() -> dict:
    global _buildings_cache
    if _buildings_cache is None:
        _buildings_cache = load_buildings()
    return _buildings_cache


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def walking_time(building_a: str | None, building_b: str | None, buildings: dict | None = None) -> int:
    """Estimated whole minutes to walk between two building keys."""
    if building_a is None or building_b is None:
        return 0
    if building_a == building_b:
        return 0
    coords = buildings if buildings is not None else _default_buildings()
    try:
        a, b = coords[building_a], coords[building_b]
    except KeyError as exc:
        raise KeyError(f"unknown building key: {exc.args[0]!r}") from None
    meters = _haversine_m(a["lat"], a["long"], b["lat"], b["long"]) * ROUTE_FACTOR
    return math.ceil(meters / WALK_SPEED_M_PER_MIN)


def gap_cost(scheduled_gap: int, walk_minutes: int) -> float:
    """Cost curve for one same-day back-to-back transition. See PLAN.md §4.

    Four regimes on slack = scheduled_gap + early-release buffer - walk time:
    too tight (slack < 0), sweet spot (up to the annoyance threshold),
    idle (linear growth to the idle cap), long break (much slower growth past
    the cap, where the gap is long enough to be useful free time).
    """
    effective_gap = scheduled_gap + EARLY_RELEASE_BUFFER_MINUTES
    slack = effective_gap - walk_minutes
    if slack < 0:
        return MISS_BASE_COST + MISS_COST_PER_MINUTE * (-slack)
    if slack <= IDLE_ANNOYANCE_THRESHOLD_MINUTES:
        return SWEET_SPOT_COST
    excess = slack - IDLE_ANNOYANCE_THRESHOLD_MINUTES
    if excess <= IDLE_CAP_MINUTES:
        return SWEET_SPOT_COST + IDLE_COST_PER_MINUTE * excess
    capped = SWEET_SPOT_COST + IDLE_COST_PER_MINUTE * IDLE_CAP_MINUTES
    return capped + IDLE_CAP_COST_PER_MINUTE * (excess - IDLE_CAP_MINUTES)

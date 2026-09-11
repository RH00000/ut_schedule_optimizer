"""Constraint solving + weighted objective. See PLAN.md §2, §4, §5."""

from __future__ import annotations

from itertools import product

from scheduler.distance import gap_cost, walking_time
from scheduler.models import Course, Schedule, Section

W_WALK = 0.5
W_GRADE = 1.0
W_RMP = 1.0

DEFAULT_AVG_GPA = 3.0  # neutral fallback when grade data is missing
DEFAULT_RMP_RATING = 3.5  # neutral fallback when RMP data is missing


def _timed_meetings(section: Section) -> list:
    """Meetings that occupy a time block (async sections have none)."""
    return [] if section.mode == "online_async" else list(section.meetings)


def _meetings_conflict(a, b) -> bool:
    if not (set(a.days) & set(b.days)):
        return False
    return a.start_min < b.end_min and b.start_min < a.end_min


def _has_conflict(sections: tuple[Section, ...]) -> bool:
    for i in range(len(sections)):
        for j in range(i + 1, len(sections)):
            for m_a in _timed_meetings(sections[i]):
                for m_b in _timed_meetings(sections[j]):
                    if _meetings_conflict(m_a, m_b):
                        return True
    return False


def _gap_cost_total(sections: tuple[Section, ...], buildings: dict) -> float:
    """Sum gap_cost over every same-day back-to-back transition.
       walks thruough consecutive pairs computing gap_cost for each 
       back to back transition, then adding it all up"""
    by_day: dict[str, list] = {}
    for section in sections:
        for meeting in _timed_meetings(section):
            for day in meeting.days:
                by_day.setdefault(day, []).append(meeting)
    total = 0.0
    for day_meetings in by_day.values():
        day_meetings.sort(key=lambda m: m.start_min)
        for earlier, later in zip(day_meetings, day_meetings[1:]):
            scheduled_gap = later.start_min - earlier.end_min
            walk = walking_time(earlier.building, later.building, buildings)
            total += gap_cost(scheduled_gap, walk)
    return total


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))

# converts gpa to cost 
def _grade_cost(section: Section, scores: dict) -> float:
    entry = scores.get(f"{section.course_id}|{section.instructor}", {})
    avg_gpa = entry.get("grade", {}).get("avg_gpa", DEFAULT_AVG_GPA)
    return _clamp((4.0 - avg_gpa) / 4.0, 0.0, 1.0)


def _rmp_cost(section: Section, scores: dict) -> float:
    entry = scores.get(f"{section.course_id}|{section.instructor}", {})
    rating = entry.get("rmp", {}).get("rating", DEFAULT_RMP_RATING)
    return _clamp((5.0 - rating) / 5.0, 0.0, 1.0)


def optimize(
    courses: list[Course],
    scores: dict,
    buildings: dict,
    w_walk: float = W_WALK,
    w_grade: float = W_GRADE,
    w_rmp: float = W_RMP,
    top_n: int = 5,
) -> list[Schedule]:
    """Brute-force every one-section-per-course combination; return the best top_n."""
    feasible: list[Schedule] = []
    print("total combinations:", len(list(product(*(c.sections for c in courses)))))
    for combo in product(*(course.sections for course in courses)):
        if _has_conflict(combo):
            continue
        walk_cost = _gap_cost_total(combo, buildings)
        grade_cost = sum(_grade_cost(s, scores) for s in combo) / len(combo)
        rmp_cost = sum(_rmp_cost(s, scores) for s in combo) / len(combo)
        feasible.append(
            Schedule(
                sections=list(combo),
                walking_time_cost=walk_cost,
                grade_quality_cost=grade_cost,
                rmp_cost=rmp_cost,
                total_cost=w_walk * walk_cost + w_grade * grade_cost + w_rmp * rmp_cost,
            )
        )
    feasible.sort(key=lambda s: s.total_cost)
    return feasible[:top_n]

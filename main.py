"""CLI entry point: load manual data, optimize, print the top schedules."""

from __future__ import annotations

import argparse
from pathlib import Path

from scheduler.data_loader import load_all
from scheduler.distance import gap_cost, walking_time
from scheduler.optimizer import W_GRADE, W_RMP, W_WALK, optimize

DAY_ORDER = ["M", "T", "W", "TH", "F"]


def _fmt_time(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _fmt_days(days: list[str]) -> str:
    return "".join(d for d in DAY_ORDER if d in days)


def _walk_detail_rows(sched, buildings) -> list:
    """(day, earlier section/meeting, later section/meeting, gap, walk_min, cost) per back-to-back pair."""
    by_day: dict[str, list] = {}
    for section in sched.sections:
        if section.mode == "online_async":
            continue
        for m in section.meetings:
            for day in m.days:
                by_day.setdefault(day, []).append((section, m))
    rows = []
    for day in DAY_ORDER:
        items = sorted(by_day.get(day, []), key=lambda sm: sm[1].start_min)
        for (sa, ma), (sb, mb) in zip(items, items[1:]):
            gap = mb.start_min - ma.end_min
            walk = walking_time(ma.building, mb.building, buildings)
            rows.append((day, sa, ma, sb, mb, gap, walk, gap_cost(gap, walk)))
    return rows


def _print_schedule(rank: int, sched, weights: tuple[float, float, float], buildings, walk_detail: bool = False) -> None:
    w_walk, w_grade, w_rmp = weights
    print(f"\n#{rank}  total_cost = {sched.total_cost:.4f}")
    for section in sched.sections:
        print(f"  {section.course_id:<8} section {section.section_id}  {section.instructor}  [{section.mode}]")
        for m in section.meetings:
            where = m.building or "online"
            room = f" {m.room}" if m.room else ""
            print(f"      {_fmt_days(m.days):<5} {_fmt_time(m.start_min)}-{_fmt_time(m.end_min)}  {where}{room}")
        if not section.meetings:
            print("      (no scheduled meetings)")
    print("  breakdown:")
    print(f"      walk (summed gap_cost)  {sched.walking_time_cost:8.4f}  x {w_walk} = {w_walk * sched.walking_time_cost:.4f}")
    print(f"      grade                   {sched.grade_quality_cost:8.4f}  x {w_grade} = {w_grade * sched.grade_quality_cost:.4f}")
    print(f"      rmp                     {sched.rmp_cost:8.4f}  x {w_rmp} = {w_rmp * sched.rmp_cost:.4f}")
    if walk_detail:
        rows = _walk_detail_rows(sched, buildings)
        print("  walk detail (same-day back-to-back):")
        if not rows:
            print("      (no back-to-back pairs)")
        for day, sa, ma, sb, mb, gap, walk, cost in rows:
            print(f"      {day:<2} {sa.course_id} {ma.building} ends {_fmt_time(ma.end_min)} -> "
                  f"{sb.course_id} {mb.building} at {_fmt_time(mb.start_min)}:  gap {gap}m, walk {walk}m, cost {cost:.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="UT course schedule optimizer (v1, manual data)")
    parser.add_argument("--walk-weight", type=float, default=W_WALK,
                        help="weight on the summed gap cost (default: %(default)s)")
    parser.add_argument("--grade-weight", type=float, default=W_GRADE,
                        help="weight on the grade-quality cost (default: %(default)s)")
    parser.add_argument("--rmp-weight", type=float, default=W_RMP,
                        help="weight on the RateMyProfessor cost (default: %(default)s)")
    parser.add_argument("--top", type=int, default=5,
                        help="number of schedules to print (default: %(default)s)")
    parser.add_argument("--courses", type=Path, default=None,
                        help="courses JSON to load (default: data/courses_demo.json)")
    parser.add_argument("--walk-detail", action="store_true",
                        help="print per-transition walking cost for each schedule")
    args = parser.parse_args()

    courses, scores, buildings = load_all(args.courses)
    print(f"Loaded {len(courses)} courses: {', '.join(c.course_id for c in courses)}")
    print(f"Weights: walk={args.walk_weight} grade={args.grade_weight} rmp={args.rmp_weight}")

    results = optimize(
        courses, scores, buildings,
        w_walk=args.walk_weight, w_grade=args.grade_weight, w_rmp=args.rmp_weight, top_n=args.top,
    )
    if not results:
        print("\nNo feasible schedule found.")
        return
    print(f"\nTop {len(results)} schedules (lower cost is better):")
    for rank, sched in enumerate(results, start=1):
        _print_schedule(rank, sched, (args.walk_weight, args.grade_weight, args.rmp_weight),
                        buildings, args.walk_detail)


if __name__ == "__main__":
    main()

"""Core dataclasses. Fields only — see PLAN.md §1. No logic yet."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Meeting:
    days: list[str]  # subset of ["M", "T", "W", "TH", "F"]
    start_min: int  # minutes past midnight
    end_min: int
    building: str | None = None  # key into buildings.json
    room: str | None = None


@dataclass
class Section:
    section_id: str  # UT unique number
    course_id: str
    instructor: str  # "Last, First"
    meetings: list[Meeting] = field(default_factory=list)
    mode: str = "in_person"  # in_person | online_sync | online_async


@dataclass
class Course:
    course_id: str  # e.g. "CS 314"
    title: str
    sections: list[Section] = field(default_factory=list)


@dataclass
class Schedule:
    sections: list[Section] = field(default_factory=list)  # one per requested course
    walking_time_cost: float = 0.0
    grade_quality_cost: float = 0.0
    rmp_cost: float = 0.0
    total_cost: float = 0.0

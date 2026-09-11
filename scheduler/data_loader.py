"""Loads and validates the JSON files in data/. See PLAN.md §1."""

from __future__ import annotations

import json
from pathlib import Path

from scheduler.distance import load_buildings
from scheduler.models import Course, Meeting, Section

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
COURSES_PATH = DATA_DIR / "courses_demo.json"
SCORES_PATH = DATA_DIR / "scores_manual.json"

VALID_DAYS = {"M", "T", "W", "TH", "F"}
VALID_MODES = {"in_person", "online_sync", "online_async"}


def load_scores(path: Path | None = None) -> dict:
    """Load scores_manual.json -> {"course_id|instructor": {...}}."""
    with open(path or SCORES_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def load_courses(path: Path | None = None) -> list[Course]:
    """Load a courses JSON file into Course/Section/Meeting dataclasses."""
    with open(path or COURSES_PATH, encoding="utf-8") as fh:
        raw = json.load(fh)
    courses = []
    for c in raw:
        sections = [
            Section(
                section_id=s["section_id"],
                course_id=s["course_id"],
                instructor=s["instructor"],
                mode=s.get("mode", "in_person"),
                meetings=[
                    Meeting(
                        days=m["days"],
                        start_min=m["start_min"],
                        end_min=m["end_min"],
                        building=m.get("building"),
                        room=m.get("room"),
                    )
                    for m in s.get("meetings", [])
                ],
            )
            for s in c["sections"]
        ]
        courses.append(Course(course_id=c["course_id"], title=c["title"], sections=sections))
    return courses


def validate(courses: list[Course], buildings: dict) -> None:
    """Raise ValueError on any structural problem in the loaded data."""
    for course in courses:
        if not course.sections:
            raise ValueError(f"course {course.course_id!r} has no sections")
        for section in course.sections:
            tag = f"{course.course_id}/{section.section_id}"
            if section.mode not in VALID_MODES:
                raise ValueError(f"section {tag} has invalid mode {section.mode!r}")
            for meeting in section.meetings:
                bad_days = set(meeting.days) - VALID_DAYS
                if bad_days:
                    raise ValueError(f"section {tag} has invalid days {sorted(bad_days)}")
                if meeting.end_min <= meeting.start_min:
                    raise ValueError(f"section {tag} has non-positive meeting duration")
                if meeting.building is not None and meeting.building not in buildings:
                    raise ValueError(f"section {tag} references unknown building {meeting.building!r}")


def load_all(courses_path: Path | None = None) -> tuple[list[Course], dict, dict]:
    """Load courses, scores, buildings and validate; returns (courses, scores, buildings)."""
    buildings = load_buildings()
    courses = load_courses(courses_path)
    scores = load_scores()
    validate(courses, buildings)
    return courses, scores, buildings

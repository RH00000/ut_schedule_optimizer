# ut-schedule-optimizer — Design (v1)

Picks the best combination of class sections for a UT Austin student, subject to
time-conflict constraints, walking distance between back-to-back classes, and a
class-quality score. v1 runs entirely on hand-entered JSON in `data/`.

---

## 1. Data model

### Course
A course is a subject + number the student wants to take (e.g. `CS 314`). The
optimizer must pick exactly one section per requested course.

| Field         | Type            | Notes                                             |
|---------------|-----------------|--------------------------------------------------|
| `course_id`   | str             | Canonical key, e.g. `"CS 314"`.                   |
| `title`       | str             | Human-readable name.                              |
| `sections`    | list[Section]   | Candidate sections; the optimizer chooses one.    |

### Section
One concrete offering of a course: a unique number, an instructor, and one or
more weekly meeting blocks.

| Field           | Type              | Notes                                                        |
|-----------------|-------------------|-------------------------------------------------------------|
| `section_id`    | str               | UT unique number, e.g. `"50825"`.                            |
| `course_id`     | str               | Back-reference to the owning course.                         |
| `instructor`    | str               | `"Last, First"`; used to join against `scores_manual.json`.  |
| `meetings`      | list[Meeting]     | Weekly meeting blocks (see below).                           |
| `mode`          | str               | `"in_person"`, `"online_sync"`, `"online_async"`.            |

### Meeting
A single recurring weekly time block for a section.

| Field         | Type          | Notes                                                          |
|---------------|---------------|--------------------------------------------------------------|
| `days`        | list[str]     | Subset of `["M", "T", "W", "TH", "F"]`.                       |
| `start_min`   | int           | Minutes past midnight, local time (e.g. `9*60 = 540`).        |
| `end_min`     | int           | Minutes past midnight; `end_min > start_min`.                 |
| `building`    | str \| None   | Building key into `buildings.json`; `None` if online/async.   |
| `room`        | str \| None   | Free text.                                                   |

### Schedule
A candidate solution: one chosen section per requested course, plus cached
objective terms for ranking and display.

| Field             | Type                | Notes                                             |
|-------------------|---------------------|-------------------------------------------------|
| `sections`        | list[Section]       | One per requested course.                         |
| `walking_time_cost` | float             | Objective term (see §4).                          |
| `grade_quality_cost` | float            | Objective term (see §4).                          |
| `rmp_cost`        | float               | Objective term (see §4).                          |
| `total_cost`      | float               | Weighted sum; lower is better.                    |

### Supporting JSON files

- **`buildings.json`** — `{ "<building key>": { "lat": float, "long": float } }`.
- **`courses_*.json`** — list of Course objects with nested sections/meetings
  (`courses_demo.json` is the default; `--courses` selects another, e.g.
  `courses_fall_actual.json`).
- **`scores_manual.json`** — keyed by `"<course_id>|<instructor>"`, value:
  `{ "grade": { "a_rate": float, "avg_gpa": float, "n": int }, "rmp": { "rating": float, "difficulty": float, "n": int } }`.
  All score fields optional; missing data falls back to a neutral default (§4).

---

## 2. Time conflict — exact definition

Two meetings **A** and **B** conflict iff **all** of:

1. **Shared day:** `set(A.days) ∩ set(B.days)` is non-empty.
2. **Overlapping interval:** `A.start_min < B.end_min AND B.start_min < A.end_min`
   (half-open intervals; touching end-to-start does **not** conflict).
3. Both meetings are in-person or online-sync (an `online_async` meeting has no
   time block and never conflicts).

A **Schedule is infeasible** if any pair of meetings from any two chosen sections
conflicts. No passing-time buffer is required for feasibility — passing time is
handled as a soft cost in §3–§4, not a hard constraint.

---

## 3. Back-to-back transitions

Applies to an **ordered back-to-back pair**: two meetings on the same day where B
starts after A ends, with no third meeting between them.

- `scheduled_gap = B.start_min - A.end_min`
- `walk_min = estimated walking time between A.building and B.building` (from
  `distance.py`; `0` if same building or either meeting is online).

There is **no hard walkability cutoff**. A transition that is too tight to make
is scored with a heavy penalty by the `gap_cost` curve (§4) and ranks very low,
but is not excluded outright. Only time conflicts (§2) make a schedule
infeasible.

Walking-time estimate: straight-line distance from lat/long via the haversine
formula, multiplied by a `ROUTE_FACTOR = 1.3` detour fudge, divided by
`WALK_SPEED = 78 m/min` (~4.7 km/h), rounded up to the next minute.

---

## 4. Objective function

Rank feasible schedules by `total_cost` (lower is better):

```
total_cost =  W_WALK * walking_time_cost
            + W_GRADE * grade_quality_cost
            + W_RMP   * rmp_cost
```

Default weights (tunable, exposed as CLI flags later):

| Weight    | Default | Meaning                                  |
|-----------|---------|------------------------------------------|
| `W_WALK`  | 0.5     | Penalty on the summed gap cost.          |
| `W_GRADE` | 1.0     | Penalty for lower expected grade quality.|
| `W_RMP`   | 1.0     | Penalty for lower RateMyProfessor rating.|

### Term definitions

**`walking_time_cost`** — sum of `gap_cost(scheduled_gap, walk_min)` over every
same-day back-to-back pair of chosen sections. A MWF↔MWF adjacency contributes
three pairs (one per shared day), TTH↔TTH contributes two. `gap_cost` is a cost
curve, not a binary cutoff, built from two named constants:

- `EARLY_RELEASE_BUFFER_MINUTES` (default 10) — professors typically let class
  out this early, so the time actually available is
  `effective_gap = scheduled_gap + EARLY_RELEASE_BUFFER_MINUTES`.
- `IDLE_ANNOYANCE_THRESHOLD_MINUTES` (default 15) — slack beyond the walk time
  past which sitting around campus starts to feel like wasted time.
- `IDLE_CAP_MINUTES` (default 45) — slack past this reads as legitimately useful
  free time (lunch, studying), not dead time.

Let `slack = effective_gap - walk_min`. Then:

- **`slack < 0`** — you can't make it even with the early-release buffer. Heavy
  penalty that grows with how many minutes short you are; large enough to
  dominate `total_cost` and bury the schedule, but it does not hard-exclude the
  combination.
- **`0 <= slack <= IDLE_ANNOYANCE_THRESHOLD_MINUTES`** — the sweet spot: enough
  time to walk over comfortably without dead time. Low, roughly flat cost.
- **`IDLE_ANNOYANCE_THRESHOLD_MINUTES < slack <= threshold + IDLE_CAP_MINUTES`**
  — idle time on campus. Cost rises linearly with excess slack, but far more
  gently than the "can't make it" penalty: being 40 minutes early is annoying,
  not as bad as missing the start of class.
- **`slack > threshold + IDLE_CAP_MINUTES`** — the gap is now long enough to be
  useful free time (lunch, studying). Cost keeps rising but at roughly a tenth
  of the idle rate, so a 90-minute gap costs only marginally more than a
  50-minute one and nowhere near a missed transition.

The term is no longer normalized to `[0, 1]`: a comfortable schedule scores a
small amount per adjacency, an unmakeable one scores roughly two orders of
magnitude higher. The `gap_cost` constants are calibrated against the observed
`grade_cost` / `rmp_cost` range so a few sweet-spot transitions cannot outweigh
a genuine professor-quality difference; revisit them if that scoring changes.

**`grade_quality_cost`** — for each chosen section, look up `avg_gpa` for
`course_id|instructor`. Cost per section = `(4.0 - avg_gpa) / 4.0`, clamped to
`[0, 1]`. Missing data → neutral default `avg_gpa = 3.0` (cost `0.25`). Schedule
term = mean over sections.

**`rmp_cost`** — for each chosen section, look up `rmp.rating` (0–5). Cost per
section = `(5.0 - rating) / 5.0`. Missing data → neutral default `rating = 3.5`
(cost `0.30`). Schedule term = mean over sections.

`grade_quality_cost` and `rmp_cost` are `[0, 1]`-scaled; `walking_time_cost` is
deliberately unbounded above so an unmakeable transition dominates the ranking.

---

## 5. Solving approach (v1)

Requested course list is small (≤ ~7), each with a handful of sections, so v1
does an exhaustive product of section choices: enumerate, drop only those with a
time conflict (§2), score the rest (tight transitions are penalized by
`gap_cost`, not excluded), return the top N. A real constraint solver is
deferred until problem size demands it.

---

## 6. Out of scope for v1

- Live scraping (grade distributions, RMP, the course schedule) — `scrapers/` is
  a placeholder.
- Waitlist / seat-availability data.
- Preferred time-of-day windows, professor blocklists, lunch breaks.
- Multi-campus or non-weekly meeting patterns.

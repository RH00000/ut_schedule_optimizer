# ut-schedule-optimizer

A course scheduling tool for UT Austin registration. Given a list of courses and the sections offered for each, it picks the combination that avoids time conflicts and ranks the rest by walking distance between back-to-back classes and instructor quality (grade distribution, RateMyProfessor rating).

I built this because UT registration involves the same manual trade-off every semester: pick classes that don't overlap, aren't too far apart, and have decent professors. This automates it and makes the trade-offs explicit instead of guessed.

## How it works

Each course can have multiple sections, and each section can have multiple meetings. A lecture plus a separately-scheduled lab in a different building, for example. The optimizer enumerates every combination of one section per course, drops any combination with a real time conflict, and scores the rest.

Scoring is a weighted sum of three costs: walking cost, grade cost, and RMP cost, each tunable via CLI flag. The walking cost is the part with actual design behind it. For every pair of back-to-back classes on the same day, it takes the scheduled gap, adds a fixed buffer for the fact that professors tend to let class out early, and subtracts the estimated walk time (straight-line distance between building coordinates, scaled by a route factor to account for not walking through buildings). What's left is slack, and the cost curve has four regimes based on it: negative slack, a small comfortable window (flat, low cost), a wider window (idle cost that grows with how much dead time there is), and a long-break cutoff past which the cost barely grows further, since a 90-minute gap isn't meaningfully worse than a 50-minute one.

Two implementation details worth calling out. First, the walk-cost constants weren't picked correctly on the first attempt. This is an early version let the "comfortable walk" cost dominate real differences in instructor quality, so a worse-but-zero-walk schedule would outrank a better one with a short comfortable walk. Fixed by rescaling the constants against the actual observed range of grade/RMP costs in the data, not by feel. Second, the early-release buffer was initially 10 minutes and misjudged a real, makable back-to-back transition on my own schedule as physically impossible; bumped to 15 after checking it against how early professors actually let classes out.

Weekday identity affects only feasibility. Two meetings on different days never conflict, but once a schedule is feasible, a Monday walk isn't weighted differently from a Friday one. That's a deliberate simplification, not an oversight.

## Validation

- **Real schedule** (`data/courses_fall_actual.json`): my actual registered Fall courses, used to confirm the parser and conflict checker agree with UT's own registration system.
- **Synthetic stress test** (`data/courses_test_pool.json`): a wider dataset built to force genuine trade-offs between walking distance and instructor quality, confirming neither factor dominates the ranking by default.
- **Demo fixture** (`data/courses_demo.json`): hand-built cases covering each walk-cost regime end to end, anchored to real UT building coordinates.

## Getting started

```bash
git clone https://github.com/<your-username>/ut-schedule-optimizer.git
cd ut-schedule-optimizer
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate # macOS/Linux
pip install -r requirements.txt
python main.py
```

## Usage

```bash
python main.py                                    # default weights
python main.py --walk-weight 2.0 --top 10          # weight walking more heavily, show top 10
python main.py --grade-weight 1.5 --rmp-weight 0   # ignore RMP, favor easy grading
python main.py --courses data/courses_fall_actual.json --walk-detail
```

`--courses` points at a different courses file. `--walk-detail` prints the walking cost of each individual back-to-back transition instead of just the total. `python main.py --help` lists every flag.

## Project structure

```
data/            course, building, and instructor-score JSON (hand-entered)
scheduler/
  models.py      Course, Section, Meeting dataclasses
  distance.py    walking-time estimate and the gap_cost curve
  optimizer.py   conflict detection and weighted ranking
  data_loader.py loads and validates the JSON files
tests/           unit tests for distance.py and optimizer.py
main.py          CLI entry point
```

## Limitations

All data is hand-entered for this version. Only same-day, back-to-back adjacencies are modeled; a gap spanning two days (an 8am after a class that ended at 9pm the night before) isn't considered. UT's official course evaluations (CES) are gated behind a per-student login and can't be collected at scale, so they're deliberately excluded in favor of grade distributions and RateMyProfessor.

## Future work

A live scraping pipeline for grade distributions, the course schedule, and RMP data. NLP sentiment analysis on RMP free-text reviews rather than just the star rating. Semester-long optimization that accounts for workload balance and exam clustering, not just a single weekly grid.
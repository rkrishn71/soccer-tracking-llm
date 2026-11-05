# Can LLMs read a football pitch?

> **Status: work in progress.** The data pipeline and the first 300 benchmark questions are built;
> no models have been evaluated yet. Everything below about *data* is measured. Anything about
> *model behaviour* is still a hypothesis.

A benchmark that measures **where frontier LLMs fail at spatial and tactical reasoning** about
football, using real tracking data.

Each question shows a model one moment from a real match (where all 22 players and the ball are)
and asks something with an objectively correct answer: *Is this player offside? Who is nearest
the ball carrier? How many defenders are goal-side of the ball?* The correct answers are computed
from the tracking data, never written by a person or an LLM.

## The questions this project asks

1. **Can frontier LLMs read the pitch?** How accurate are they on questions a short script answers perfectly?
2. **Where do they break?** Accuracy against difficulty: how tight an offside call, how crowded the
   area around the ball, how long the pass.
3. **Does the input format matter?** The same question given as a **table of coordinates** versus a
   **rendered image of the pitch**.
4. **Rule or geometry?** When a model gets offside wrong, does it not know the rule, or does it
   know the rule and misread the positions?
5. **Calibration.** When a model says it is 90% sure, is it right 90% of the time?

The aim is a map of where general-purpose LLMs are reliable on tracking data, and where
specialist models and structured data are still needed.

## How it works

| Tier | What it tests | Example | Ground truth | Target items |
|---|---|---|---|---|
| **1. Geometric** | Reading positions | "Is Blue 9 in an offside position?" | Computed from coordinates | 300 ✅ |
| 2. Model-derived | Space and options | "Which passing option is most open?" | Pitch-control model (reported as agreement, not truth) | 200 |
| 3. Tactical | Team shape | "Is the defending team in a high press, mid block or low block?" | SkillCorner phase-of-play labels | 200 |
| 4. Judgement | Decision quality | "What is the best passing option?" | Author's hand labels | 100 |

Each item is run on 2–3 frontier models, in both input formats (coordinates and image) and two
prompt styles (answer directly, or reason first), and compared with simple baselines.

**Design rules that keep the benchmark honest:**

- **Only trustworthy moments.** Broadcast tracking *estimates* the position of off-camera players
  (43% of player positions here). A question is used only if every player whose position decides
  the answer was actually **seen** by the camera.
- **The answer follows from what the model sees.** Ground truth is computed from exactly the
  rounded coordinates shown in the prompt, so no item can be marked wrong because of hidden detail.
- **No leaks.** Players are listed by team and shirt number, never by position, with no roles,
  margins or detection flags. Tests check that every answer can be recomputed from the prompt text alone.
- **Balanced answers.** For example, real offsides are rare (2.7% of eligible passes), so the
  offside set pairs each offside with an onside near-miss *at the same margin*: 96 offside and 96
  onside. A model that always says "onside" scores 50%, not 97%.

## Progress

| Phase | Output | Status |
|---|---|---|
| 1. Data | 23 matches in one schema (31.8M rows), reproducible build, hand-traced transforms | ✅ done |
| 2. Exploration | Where the data can be trusted: `is_usable(frame, question_type)`, figures, caveats | ✅ done |
| 3. Question bank | Tier 1: 300 items ✅ · Tiers 2–4 · 20% private test split · data card | 🔄 in progress |
| 4. Model runs | Pilot on 30 items, then full logged runs (models × format × prompt style) | ⏳ |
| 5. Analysis | Accuracy by tier and format, error-vs-difficulty curves, calibration, short memo | ⏳ |

## What the data has shown so far

Building the benchmark turned up findings about **broadcast tracking data** that matter to anyone
building on it:

- **The back line is often off camera.** At the moment of a pass, the second-last defender (the
  player who defines offside) is actually seen only **45%** of the time.
- **Coverage is biased.** Moments usable for an offside question drop from **86%** with the ball
  in the final third to **8%** in a team's own third, and to **3%** for long balls played 30 m+
  ahead. Those long balls are classic offside situations.
  ([figure](notebooks/figures/fig3_offside_usable_bias.png))
- **The biggest moments are missing.** After a goal, tracking is absent for **97–100%** of the
  following 10–40 seconds (broadcast replays). Those moments can't be sampled.
  ([figure](notebooks/figures/fig5_no_tracking_after_shots.png))
- **Real offsides are razor-thin.** 75 of the 96 offside positions found are within 1 m.
  ([figure](notebooks/figures/fig4_offside_margins.png))

Details: [CAVEATS.md](CAVEATS.md) (what the data is safe for) and [DECISIONS.md](DECISIONS.md)
(every design decision and why).

## Data

| Source | Matches | Rate | Notes |
|---|---|---|---|
| [SkillCorner open data](https://github.com/SkillCorner/opendata) (master @ `4340d27`) | 20 A-League 2024/25 | 10 fps | Broadcast tracking with a per-player detected/extrapolated flag, dynamic events, phases of play |
| [Metrica Sports sample data](https://github.com/metrica-sports/sample-data) (@ `e706dd5`) | 3 anonymised games | 25 fps | Full-pitch tracking (every player always visible); games 1–2 CSV, game 3 FIFA EPTS |

Raw data is not stored in this repo. `scripts/setup_data.sh` fetches it at the pinned commits.

## Repository layout

```
src/                  pipeline and benchmark code
  load.py               get_frame(match_id, frame_id) - any frame, any source, one schema
  usable.py             is_usable(frame, question_type) - is every answer-relevant player detected?
  moments.py            candidate moments (every pass) with usability flags
  items.py, tier1.py    question format, ground truth from the displayed scene, item builders
  prompts.py            coordinates prompt, image prompt + pitch renderer
items/                question bank (tier1_v0.jsonl: 300 items)
notebooks/            phase1_checks, phase2_usable, phase2_exploration, phase3_items, phase3_tier1
notebooks/figures/    exploration figures and example items
tests/                pytest suite (246 tests)
CONVENTIONS.md        every coordinate transform, sign flip and unit conversion, with code line refs
CAVEATS.md            which data is safe for which question type, and known biases
DECISIONS.md          decision log
PHASE1_REPORT.md      data build report: row counts, anomalies
SETUP.md              step-by-step local setup
```

## Quick start

Full walkthrough: [SETUP.md](SETUP.md). Short version (Python 3.11+, git-lfs installed):

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
bash scripts/setup_data.sh          # raw data at pinned commits, LFS verified (~1.8 GB)
python -m src.build                 # -> data/processed/
python -m pytest -q                 # all tests pass
python scripts/verify_phase1.py     # counts identical to the original build
```

```python
from src.load import get_frame
from src.items import load_items
from src.prompts import text_prompt, render_scene

get_frame("1874553", 1000)                      # one frame: 22 players + ball, in metres
item = load_items("items/tier1_v0.jsonl")[0]    # one benchmark question
print(text_prompt(item))                        # what a model is shown (coordinates format)
render_scene(item, "item.png")                  # the image format
```

## Credits

- **Data from [SkillCorner](https://skillcorner.com)**: broadcast tracking data, Dynamic Events and
  Phases of Play for the Australian A-League 2024/25, released as open data by SkillCorner in a
  joint initiative with [PySport](https://pysport.org/). As requested in their repository: if you
  use this data, please credit SkillCorner (and let them know on
  [Twitter/X @skillcorner](https://twitter.com/skillcorner)).
- **Metrica Sports** sample data (https://github.com/metrica-sports/sample-data), acknowledged as
  their README requests for public use.

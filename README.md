# Soccer tracking data - Phase 1 (acquisition & preprocessing)

Converts two open tracking datasets into one common, per-frame schema (metres, centre origin),
with per-match metadata, tests and visual checks. **No analysis in this phase.**

| Source | Matches | Rate | Notes |
|---|---|---|---|
| [SkillCorner open data](https://github.com/SkillCorner/opendata) (master @ `4340d27`) | 20 A-League 2024/25 | 10 fps | broadcast tracking, `is_detected` flag, dynamic events, phases of play |
| [Metrica Sports sample data](https://github.com/metrica-sports/sample-data) (@ `e706dd5`) | 3 anonymised games | 25 fps | games 1-2 CSV, game 3 FIFA EPTS |

## Layout

```
data/raw/            untouched clones (not modified by any code)
data/processed/      {match_id}.parquet + {match_id}.meta.json, qa/ summaries
src/                 config, skillcorner, metrica, normalize, build, load, viz
tests/               pytest suite (218 tests)
notebooks/           phase1_checks.ipynb (+ exported PNGs)
scripts/             setup_data.sh, verify_phase1.py, check_conventions.py
reference/           phase1_summary.json - counts from the original build (for verify_phase1.py)
CONVENTIONS.md       every transform / flip / unit conversion, with line refs
PHASE1_REPORT.md     what was done, row counts, anomalies, open questions
DECISIONS.md         decisions log (open questions and how they were resolved)
SETUP.md             step-by-step local setup (macOS, VS Code, GitHub)
```

`data/` is not in git. Rebuild it with the quick start below.

## Quick start

Full walkthrough: [SETUP.md](SETUP.md). Short version (Python 3.11+, git-lfs installed):

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
bash scripts/setup_data.sh          # raw data at pinned commits, LFS verified
python -m src.build                 # -> data/processed/
python -m pytest -q                 # 218 passed
python scripts/verify_phase1.py     # counts identical to the original build
```

```python
from src.load import get_frame, load_meta
get_frame("1874553", 1000)            # SkillCorner (match id)
get_frame("metrica_game_3", 5000)     # Metrica (metrica_game_1/2/3)
load_meta("1874553")["attack_direction"]
```

## Credits

- **Data from [SkillCorner](https://skillcorner.com)**: broadcast tracking data, Dynamic Events and
  Phases of Play for the Australian A-League 2024/25, released as open data by SkillCorner in a
  joint initiative with [PySport](https://pysport.org/). As requested in their repository: if you
  use this data, please credit SkillCorner (and let them know on
  [Twitter/X @skillcorner](https://twitter.com/skillcorner)).
- **Metrica Sports** sample data (https://github.com/metrica-sports/sample-data), acknowledged as
  their README requests for public use.

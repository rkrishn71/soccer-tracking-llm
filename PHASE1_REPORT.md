# Phase 1 report: data acquisition and preprocessing

Scope: acquisition, conversion to a common frame schema, normalisation, and QA only.
No analysis, question generation or modelling was done.

## 1. What was done

### Acquisition (`data/raw/`, never modified)

**`skillcorner_opendata/`**
- A shallow clone of `SkillCorner/opendata` **master** at commit `4340d27` (2026-09-14, "Refresh four matches to dynamic events v3").
- **20** A-League 2024/25 matches. The README still says 10, but `matches.json` and `data/matches/` both hold 20. Per your decision, all 20 were processed.
- **Git LFS:** yes. `*.jsonl` (the tracking files) are LFS-tracked.
  - `git lfs pull` was refused by this environment's git proxy, which does not hold credentials for the repo's LFS endpoint.
  - Each of the 20 LFS objects was downloaded instead from GitHub's public LFS media URL (`media.githubusercontent.com/media/SkillCorner/opendata/master/<path>`).
  - Each download's **SHA-256 was checked against the `oid` in its LFS pointer before it replaced the pointer**. All 20 matched. `git lfs ls-files` now shows `*` (content present) for every file, and `git diff` is empty (test `test_raw_repos_unmodified`).
  - Total size: about 1.8 GB.
- The older 2019/20 release was not used.

**`metrica_sample_data/`**
- A clone of `metrica-sports/sample-data` at commit `e706dd5` (2021-04-15).
- **No LFS** (no `.gitattributes`, `git lfs ls-files` is empty).
- 3 games:
  - Games 1–2: CSV, one file per team, plus an events CSV.
  - Game 3: FIFA EPTS metadata XML, a tracking `.txt` and an events JSON.

### Environment

`.venv` runs Python 3.11 with versions pinned in `requirements.txt`: kloppy 3.19.0, pandas 3.0.6, numpy 2.4.6, pyarrow 25.0.1, matplotlib 3.11.2, mplsoccer 1.8.1, pytest 9.1.1. orjson and jupyter/nbconvert are also installed.

### Processing (`python -m src.build`)

For each match, `data/processed/` gets:
- `{match_id}.parquet`: the common schema (CONVENTIONS.md §5), zstd-compressed, 50k-row groups sorted by frame.
- `{match_id}.meta.json`: pitch size, frame rate, team ids and names, lineups with on/off frames, substitutions, periods, and the attack direction per team per period. Metrica files also carry the direction-check evidence.

Also written:
- `data/processed/qa/summary.json`: per-match counts, used for the tables below.
- `data/processed/qa/out_of_bounds_<match>.csv`: every row more than 2 m outside the pitch (written by the tests).

### Deliverables

| File | Contents |
|---|---|
| `src/load.py` | `get_frame(match_id, frame_id)`, `load_match`, `load_meta`, `list_matches` |
| `CONVENTIONS.md` | Every transform, with line references. `scripts/check_conventions.py` re-verifies all 38 cited lines |
| `tests/` | **218 tests, all passing** (about 2 min). Bounds violations are reported as warnings and CSVs, not failures (§3.1) |
| `notebooks/phase1_checks.ipynb` | Executed. 5 random frames per source, the detection-share table, the off-pitch cross-tab and the Metrica direction checks |

### Decisions applied (from your answers)

1. All 20 SkillCorner matches were processed. 1953632 carries `status_conflict=True` (see §3.2).
2. `x_att_m`/`y_att_m` are NaN when possession is empty, with no carrying forward. The `x_home_m`/`y_home_m` columns are added for every row, and the raw `possession_group` value is kept as a column.
3. All 3 Metrica games were processed. Attack direction was verified with the kick-off halves check, the shot-direction check, and the Player11/Player25-deepest check (§3.3).

## 2. Row counts per match

One row per (match, period, frame, object). "Frames" are in-period frames.

- **SkillCorner** frames are listed only when they have a period. Pre-match, half-time and post-match frames carry no objects and produce no rows.
- **Metrica** games 1–2 include bench players' rows (NaN position), so their player-frame detected share is diluted. Restricted to each player's on-pitch window, the share is 100.0% for all three games (notebook table).

| match_id | source | frames P1 | frames P2 | rows total | player rows | ball rows | players seen | player-frames detected | possession empty (frames) |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|
| 1874553 | skillcorner | 28,981 | 31,301 | 1,033,650 | 973,368 | 60,282 | 32 | 57.9% | 45.4% |
| 1886347 | skillcorner | 27,781 | 31,261 | 1,015,118 | 956,076 | 59,042 | 29 | 59.3% | 45.6% |
| 1899585 | skillcorner | 29,751 | 30,760 | 955,493 | 894,982 | 60,511 | 30 | 55.2% | 51.1% |
| 1925299 | skillcorner | 30,231 | 31,051 | 1,116,006 | 1,054,724 | 61,282 | 32 | 57.9% | 41.9% |
| 1927964 | skillcorner | 28,371 | 30,680 | 1,043,749 | 984,698 | 59,051 | 32 | 61.5% | 36.7% |
| 1953632 ⚑ | skillcorner | 28,961 | 30,270 | 1,025,295 | 966,064 | 59,231 | 30 | 62.1% | 43.7% |
| 1959846 | skillcorner | 27,961 | 30,571 | 998,790 | 940,258 | 58,532 | 30 | 57.0% | 46.9% |
| 1986691 | skillcorner | 27,771 | 31,300 | 1,006,743 | 947,672 | 59,071 | 32 | 58.8% | 45.7% |
| 1996435 | skillcorner | 28,011 | 29,591 | 1,015,284 | 957,682 | 57,602 | 30 | 65.8% | 43.4% |
| 1996436 | skillcorner | 30,131 | 30,130 | 1,007,713 | 947,452 | 60,261 | 31 | 55.4% | 54.2% |
| 2006229 | skillcorner | 28,471 | 30,780 | 1,031,013 | 971,762 | 59,251 | 32 | 62.9% | 45.2% |
| 2006363 | skillcorner | 28,941 | 30,131 | 1,034,706 | 975,634 | 59,072 | 32 | 53.0% | 44.4% |
| 2007448 | skillcorner | 28,521 | 29,541 | 1,032,288 | 974,226 | 58,062 | 29 | 54.0% | 48.9% |
| 2007721 | skillcorner | 27,701 | 29,841 | 1,076,076 | 1,018,534 | 57,542 | 32 | 59.6% | 40.8% |
| 2010085 | skillcorner | 29,431 | 29,541 | 1,060,434 | 1,001,462 | 58,972 | 32 | 55.4% | 44.1% |
| 2011166 | skillcorner | 28,991 | 30,301 | 917,622 | 858,330 | 59,292 | 32 | 52.4% | 53.4% |
| 2013725 | skillcorner | 27,891 | 28,901 | 1,046,616 | 989,824 | 56,792 | 30 | 54.0% | 44.1% |
| 2015213 | skillcorner | 28,831 | 31,071 | 1,127,826 | 1,067,924 | 59,902 | 32 | 52.5% | 47.7% |
| 2016236 | skillcorner | 30,551 | 29,491 | 1,025,468 | 965,426 | 60,042 | 32 | 49.1% | 44.8% |
| 2017461 | skillcorner | 27,701 | 30,751 | 947,340 | 888,888 | 58,452 | 32 | 51.2% | 50.6% |
| metrica_game_1 | metrica | 71,268 | 73,738 | 4,205,174 | 4,060,168 | 145,006 | 28 | 78.6% | n/a |
| metrica_game_2 | metrica | 67,941 | 73,215 | 3,811,212 | 3,670,056 | 141,156 | 26 | 84.6% | n/a |
| metrica_game_3 | metrica | 69,661 | 74,100 | 3,306,503 | 3,162,742 | 143,761 | 35 | 100.0% | n/a |
| **total** | | | | **31,840,119** | | | | | |

## 3. Anomalies found

### 3.1 Off-pitch positions × detection flag (your request)

"Off-pitch" means outside the touch lines or goal lines, using the match's own L × W.
">2 m" is the test's report margin. Counts are player rows unless marked as ball.
For Metrica, "detected" just means a position is present: there is no extrapolated class.

| match_id | off-pitch · detected | off-pitch · extrapolated | >2 m · detected | >2 m · extrapolated | ball >2 m · detected | ball >2 m · not detected | max abs x (m) | max abs y (m) |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| 1874553 | 3,776 | 3,558 | 279 | 870 | 354 | 1,069 | 57.2 | 39.4 |
| 1886347 | 4,009 | 2,763 | 116 | 606 | 126 | 1,186 | 58.3 | 37.2 |
| 1899585 | 2,943 | 3,490 | 269 | 833 | 87 | 972 | 57.6 | 38.0 |
| 1925299 | 3,452 | 2,735 | 115 | 861 | 185 | 1,263 | 57.9 | 41.0 |
| 1927964 | 2,145 | 3,030 | 172 | 934 | 181 | 960 | 59.1 | 39.0 |
| 1953632 | 3,958 | 3,650 | 122 | 775 | 103 | 1,258 | 57.3 | 39.2 |
| 1959846 | 2,548 | 3,711 | 248 | 1,151 | 176 | 1,160 | 58.2 | 43.0 |
| 1986691 | 3,051 | 3,904 | 316 | 1,162 | 301 | 879 | 56.1 | 39.9 |
| 1996435 | 3,486 | 2,945 | 295 | 682 | 167 | 1,024 | 58.2 | 38.6 |
| 1996436 | 4,286 | 4,610 | 292 | 1,181 | 272 | 1,283 | 57.0 | 38.9 |
| 2006229 | 3,020 | 4,334 | 154 | 1,622 | 176 | 808 | 57.5 | 40.5 |
| 2006363 | 3,407 | 3,862 | 213 | 1,124 | 143 | 975 | 57.7 | 47.4 |
| 2007448 | 3,597 | 4,178 | 214 | 923 | 365 | 1,352 | 58.1 | 45.7 |
| 2007721 | 2,755 | 4,812 | 197 | 1,442 | 237 | 1,137 | 59.0 | 40.0 |
| 2010085 | 2,568 | 2,560 | 91 | 638 | 233 | 740 | 56.0 | 39.1 |
| 2011166 | 3,464 | 3,590 | 135 | 845 | 283 | 1,393 | 63.5 | 40.3 |
| 2013725 | 3,362 | 4,588 | 174 | 1,200 | 293 | 1,128 | 57.8 | 38.8 |
| 2015213 | 3,252 | 5,076 | 180 | 1,339 | 370 | 1,399 | 56.7 | 43.3 |
| 2016236 | 3,086 | 3,930 | 164 | 829 | 325 | 1,304 | 58.2 | 39.2 |
| 2017461 | 2,155 | 3,854 | 163 | 1,313 | 477 | 1,590 | 60.1 | 40.9 |
| **SkillCorner total** | **64,320** | **75,180** | **3,909** | **20,330** | **4,854** | **22,880** | | |
| metrica_game_1 | 30,437 | 0 | 3,069 | 0 | 284 | 0 | 57.5 | 37.4 |
| metrica_game_2 | 21,342 | 0 | 5,275 | 0 | 34 | 0 | 57.8 | 37.4 |
| metrica_game_3 | 23,266 | 0 | 1,534 | 0 | 4 | 0 | 56.3 | 39.3 |

Observations (descriptive only):
- Just past the line, detected and extrapolated rows are about equally common.
- **More than 2 m out, 84% of SkillCorner player rows are extrapolated**, even though extrapolated rows are 43% of player rows overall. Likewise, 82% of far-out ball rows are "not detected".
- The furthest point is 11 m past the goal line (x = 63.5 on a 105 m pitch, match 2011166).
- The worst touch-line excursion is about 13 m (|y| = 47.4 on a 68 m pitch, match 2006363).
- No row is more than 15 m out, which would suggest a unit or origin bug.
- Every such row is kept. Per-row lists are in `data/processed/qa/out_of_bounds_*.csv`.

### 3.2 SkillCorner

1. **1953632 status conflict.** It is `status: not_started` in both `matches.json` and `1953632_match.json`, yet it has full tracking, events and phases. Its match_id is set to `status_conflict=True` on every row and in its meta JSON. The data looks structurally normal: 22 players per frame, the GKs on the correct sides, and a detected share of 62.1%. Left for your manual inspection.
2. **Frames with no tracking.** **19–34% of in-period frames** (per match) contain no player and no ball data at all. These are probably broadcast cutaways or replays, and SkillCorner does not extrapolate through them. The ball row, with a NaN position, keeps the frame id present. Frames that do have data always carry exactly 22 players.
3. **The tracking file ends one frame early** in 6 matches: 1899585, 1927964, 1953632, 1986691, 1996436, 2006229. The last frame is `end_frame − 1` of period 2 in match.json. The test allows exactly this and nothing else.
4. **Phase `frame_end` goes past the period end** in 3 matches:

   | Match | Phase frame_end | Period 1 end_frame |
   |---|---|---|
   | 1959846 | 27969 | 27960 |
   | 2013725 | 31931 | 31930 |
   | 2016236 | 31727 | 31720 |

   In each case it is the last phase of period 1, and it ends 1–9 frames past the period's `end_frame`, in the half-time gap. All dynamic-event `frame_start`/`frame_end` values and all phase `frame_start` values exist in the tracking data.
5. **Late-season matches have longer pre-match and half-time gaps.** The last five by date (2011166 … 2017461) start at frame 1170–4040, with gaps of about 9,000–10,000 frames between periods. Earlier matches start at frame 10 (0 for 1959846) with a 10-frame gap. Frame ids are preserved exactly, so this only matters for time arithmetic.
6. **`player_id` in tracking = `players[].id`**, not `trackable_object`, as the README might suggest.
7. **Ball height** (`ball_z`) is present on 66–81% of ball rows.
8. **Pitch sizes vary**: 104, 105 or 106 m by 68 m. The per-match values are used everywhere.

### 3.3 Metrica: attack direction and goalkeeper checks (your request)

For all 3 games × 2 periods × 2 teams, the three methods agree:

| Check | Result |
|---|---|
| (a) kick-off halves | Same direction as (b) and (c) in all cases |
| (b) shot direction | 2–11 shots per team-period. In every team-period, 100% of shots point the same way |
| (c) deepest player | Games 1–2: **Player11 (home) and Player25 (away) are the deepest players of their team in 97.3–99.1% of frames in every period**. Game 3: P3578 / P3595, 98.2–98.9%, both listed as `Goalkeeper` in the metadata |

Game 3's metadata (`attack_direction_first_half`) also agrees. Details are in the notebook and in each meta JSON under `direction_checks`.

One disagreement with the strict form of (a), where every player must be in their own half:
- **Game 1, period 1, kick-off frame 1:** 6 players stand 2.8–12.8 m over halfway, and the ball is at (0.45, 0.39), not on the centre spot.
- Positions over the next 50 frames show play already under way. Tracking appears to start just after the real kick-off, even though the event file puts the `KICK OFF` at frame 1.
- The team means are still clearly in their own halves, so the direction is unambiguous.
- The second kick-off of that period (after a goal, frame 3675) is clean: 0 home players and 3 away players over halfway, all within 0.6 m.
- Every other kick-off passes the strict check within the 1 m tolerance, which allows for the kicker standing on the line. The largest excursion in games 1–2 is 0.82 m.

I treated this as a data-start artefact rather than a conflict, because no method points the other way. The test lists it as a known exception.

Other Metrica notes:
- **Substitution overlap frame:** at each substitution in games 1–2 there is **one frame with 12 players** for a team, because the incoming player gets a position one frame before the outgoing one is NaN. Games 1 and 2 have 6 and 4 such frames respectively.
- **Naming quirk in game 2:** one away player is `Player 26`, with a space, where the others are `Player15` etc. The game 2 events file uses the same spelling, so it is kept verbatim as the `player_id` and joins to events still work.
- **13 substitutions in game 3** (7 away, 6 home), including 3 at half-time. That is unusual for a competitive match, but it is consistent with the 11 `DataFormatSpecification` blocks.
- **Off-pitch rows:** game 2 has 5,275 player rows more than 2 m outside the lines, versus 3,069 and 1,534 in games 1 and 3. Metrica has no detection flag to separate them.

## 4. Open questions

1. **1953632** (`not_started` but full data): keep it in the analysis set, or exclude it? It is flagged, not removed.
2. **Frames with no tracking** (19–34%): should later phases treat them as gaps (the current state), or also exclude the neighbouring frames, where extrapolation resumes and may jump?
3. **Metrica possession:** there is no per-frame possession, so `x_att_m` is NaN throughout. Should possession be derived from the Metrica event file (team of the last on-ball event)? That would be an inference, so I did not do it.
4. **Game 2 `Player 26` naming:** it is consistent between tracking and events, so it is left raw. Normalise it to `Player26` only if you want uniform ids across games.
5. **Off-pitch extrapolated rows** more than 2 m out: flag-only (the current state), or down-weight or mask them in later phases?
6. **Game 1's first frames:** tracking starts after the kick-off. If later work needs a "kick-off frame" for period 1, the post-goal kick-off at frame 3675 is the first clean one.

## 5. How to reproduce

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
# data/raw/ must contain the two clones (see README). LFS files: see §1.
python -m src.build                 # ~6 min on 2 CPUs, writes data/processed/
python -m pytest -q                 # 218 tests
python scripts/check_conventions.py # verifies CONVENTIONS.md line references
jupyter nbconvert --to notebook --execute --inplace notebooks/phase1_checks.ipynb
```

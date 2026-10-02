# Conventions

Every coordinate transform, sign flip, unit conversion and assumption in Phase 1, with the
line of code where it happens. Line numbers refer to the files as delivered;
`python scripts/check_conventions.py` re-checks that each cited line still contains the quoted code.

## 1. Target coordinate system (all sources)

| Property | Convention |
|---|---|
| Units | metres |
| Origin | pitch centre (kick-off spot) |
| x | along the pitch length, range ±L/2 |
| y | across the width, range ±W/2, **+y = "up"** in the provider's top-down view |
| L, W | each match's own pitch dimensions (SkillCorner: `pitch_length`/`pitch_width` in `{id}_match.json`: 104, 105 or 106 × 68; Metrica: 105 × 68) |
| Frame ids | the provider's original ids, unchanged |

Coordinate columns in each row:

| Columns | Meaning |
|---|---|
| `x_raw`, `y_raw` | the provider's values, untouched (SkillCorner: metres; Metrica: 0..1) |
| `x_m`, `y_m` | the target system above, **in the provider's own orientation**: whichever team attacks +x in that period |
| `x_home_m`, `y_home_m` | the home team always attacks +x. Defined for every row with a position |
| `x_att_m`, `y_att_m` | the team in possession attacks +x. **NaN when `possession_group` is empty.** Possession is never carried forward. All NaN for Metrica, which has no per-frame possession |
| `possession_group` | the raw SkillCorner per-frame value (`home team` / `away team` / null), kept as its own column |

## 2. SkillCorner

| # | What | Where | Detail |
|---|---|---|---|
| SC-1 | Raw → `x_m`/`y_m` | `src/skillcorner.py:173-174` | **Identity.** The README says "the unit of the field modelization is the meter, the center of the coordinates is at the center of the pitch… x axis is the long side". `assets/field.jpg` shows +y pointing up (the point (0, 34) is at the top). No flips, no scaling. |
| SC-2 | Attack direction | `src/skillcorner.py:55` | `home_team_side[i]` in match.json is the direction the **home** team attacks in period i+1. `left_to_right` means towards +x. Away is the opposite. Checked in all 20 matches: the home GK's median x is on the side opposite that direction in every period (`tests/test_goalkeepers.py`). |
| SC-3 | Timestamp | `src/skillcorner.py:33` | `timestamp` string `HH:MM:SS.ss` → float seconds. This is the match clock: period 2 starts at 2700 s (45:00), not 0. |
| SC-4 | Frames with `period == null` | `src/skillcorner.py:144` | Pre-match, half-time and post-match frames. An assert confirms they have no player or ball data at all, so they produce no rows. Every frame that has a period gets **one ball row** (`src/skillcorner.py:155`), even when the ball position is null. That keeps every in-period frame id present for joins. |
| SC-5 | `is_detected` | `src/skillcorner.py:175` | The raw per-object flag. Players: True = detected, False = extrapolated. Never filled. Ball: the raw flag is null whenever the ball position is null, and it stays `<NA>`. |
| SC-6 | Frames with no player data | none (kept) | About 19–34% of in-period frames contain **no players and no ball**. They appear as a single ball row with NaN position (see report). They are not dropped or filled. |
| SC-7 | `player_id` | `src/skillcorner.py` `build_frames` | The tracking file's `player_id` equals `players[].id` in match.json, **not** `trackable_object` (verified: 0 unknown ids in all 20 matches). Stored as a string. |
| SC-8 | Position / role | `lineups[].position` | `player_role.acronym` from match.json (GK, LCB, RW, …). It is one role per player per match, not per frame. `SUB` means the player never came on. |
| SC-9 | `status_conflict` | `src/skillcorner.py:105` | True when `status` in match.json or in `matches.json` is not `closed`. Only 1953632 is flagged (`not_started` in both files, despite having full data). |
| SC-10 | Substitutions | `src/skillcorner.py:91` | Pairs a player going on with a player going off in the same team when their frames are within 5 s of each other. An unpaired player going off is listed with `player_in = null`. |

## 3. Metrica

Conventions confirmed from the repo before converting:

- **Coordinates:** README says "the data goes from 0 to 1 on each axis. The coordinate (0,0) is the top left, (1,1) is the bottom right, and (0.5,0.5) is the kick off point."
- **Pitch size:** README says "105x68 meters" for games 1–2. Game 3's metadata has `<FieldSize><Width>105</Width><Height>68</Height>`, which is read at runtime.
- **Frame rate:** 25 fps. Game 3's metadata has `<FrameRate>25</FrameRate>`. In games 1–2, `Time [s] == Frame × 0.04` holds exactly on every row (checked).

| # | What | Where | Detail |
|---|---|---|---|
| ME-1 | x unit/origin | `src/metrica.py:350` | `x_m = (x_raw − 0.5) × L`. **No sign flip**: raw x = 0 is the left goal line, so raw x = 1 is +x. |
| ME-2 | y unit/origin + **sign flip** | `src/metrica.py:352` | `y_m = −(y_raw − 0.5) × W`. Raw y = 0 is the **top** edge, so raw y grows downward. The minus sign makes +y point up, matching SkillCorner. Unit-tested on a known point (`tests/test_transforms.py::test_metrica_transform_known_points`). |
| ME-3 | `is_detected` | `src/metrica.py:354` | Metrica has no detection flag, so `is_detected = position is not NaN`. NaN means the player is not on the pitch: bench, substituted off, or never used. The rows are **kept**, with NaN position. |
| ME-4 | Games 1–2 row coverage | `src/metrica.py` `load_long_raw` | The CSV has a column for every squad player (13–14 per team) on every frame, so bench players appear as NaN rows. Game 3 (EPTS) lists only the 22 players in the active `DataFormatSpecification` block, so there are no bench rows. |
| ME-5 | Ball | `src/metrica.py:165` | The ball columns are identical in the home and away CSV files (verified), so the home file's ball is used. `ball_z` is NaN (`src/metrica.py:355`); Metrica gives no height. |
| ME-6 | Timestamp | CSV: `Time [s]` column (`src/metrica.py:162`). EPTS: `src/metrica.py:187` | EPTS has no time column, so `timestamp_s = frame_id / 25`. That is the same convention as the CSV games, where `Time = Frame × 0.04`: continuous, and it does not reset at half-time. |
| ME-7 | Period (EPTS) | `src/metrica.py:184` | Taken from the metadata `first_half_end` (69661) and `second_half_start` (69662). |
| ME-8 | EPTS parsing | `src/metrica.py:106-121` | Each line is `frame:x,y;x,y;…:ballx,bally`. The player in each slot comes from whichever of the 11 `DataFormatSpecification` blocks covers that frame. The mapping changes at substitutions. Cross-checked against kloppy 3.19 on sampled frames (`tests/test_transforms.py::test_epts_parser_matches_kloppy`). |
| ME-9 | Jersey numbers | CSV header row 2 (`src/metrica.py:53`). EPTS `<ShirtNumber>` | Names are anonymised. `player_id` is `Player11` (CSV) or `P3578` (EPTS). |
| ME-10 | Position | EPTS `position_type` (raw string, e.g. `Right Center Back (4)`) | The CSV games have no positions (NA). kloppy maps many of these positions to `Unknown`, so the XML is parsed directly. |
| ME-11 | Possession | `src/metrica.py:356` | Metrica tracking has no per-frame possession, so `possession_group` is null and `x_att_m`/`y_att_m` are NaN. |
| ME-12 | Substitutions / lineups | `src/metrica.py:326` | **Derived** from the NaN pattern: each player's first and last frame with a position. A player going on is paired with the nearest player going off in the same team within 60 s. Starter = has a position at the first frame. |

### Metrica attack direction (games 1–3)

There is no direction metadata for games 1–2, and game 3 only states the first half. So the
direction comes from three independent checks, and the build raises an error if they disagree
(`src/metrica.py:282`):

| Check | Where | Rule |
|---|---|---|
| (a) kick-off halves | `src/metrica.py:248` | At the frame of each period's first `KICK OFF` event, the team's mean raw x < 0.5 means it defends the left, so it attacks left_to_right. Players more than 1 m over halfway are listed. |
| (b) shots | `src/metrica.py:259` | For the team's `SHOT` events in the period, the majority sign of `End X − Start X`. |
| (c) deepest player | `src/metrica.py:263-267` | The player closest to the team's own goal in the most frames of the whole period, and the side that player sits on. Games 1–2: it must be `Player11` (home) / `Player25` (away) in more than 95% of frames (`tests/test_goalkeepers.py`). |

- **Game 3 only:** it must also match the metadata's `attack_direction_first_half` (`src/metrica.py:289`).
- **Final mapping:** raw left_to_right = +x (`src/metrica.py:293`).
- **Results:** all 12 period×team cases agree across (a), (b) and (c). The one exception to the strict version of (a) is game 1, period 1: tracking starts after the kick-off. See PHASE1_REPORT.md.

## 4. Shared normalisation (`src/normalize.py`)

| # | What | Where | Detail |
|---|---|---|---|
| N-1 | Home attacks +x | `src/normalize.py:22-23` | If the home team attacks −x in a period, both `x` and `y` are negated. That is a **180° rotation about the centre, not a mirror**. It keeps handedness: +y is always the attacking team's left side, so wing assignments survive. A mirror (flipping x only) would swap left and right. |
| N-2 | Possession attacks +x | `src/normalize.py:26-28` | `sign = +1` if `possession_group == 'home team'`, `−1` if `'away team'`, NaN otherwise. `x_att = sign × x_home`, `y_att = sign × y_home`. |

Why both sets exist: SkillCorner possession is given per frame but is empty in 37–54% of frames.
The possession set is therefore undefined for those frames, and the home set is always defined.

## 5. Schema and dtypes (`src/normalize.py` `finalize_schema`)

One row per (match, period, frame, object). The ball row always comes first within a frame.
Rows are sorted by `period, frame_id, object (ball first), team_side, player_id`.

| Column | Type | Notes |
|---|---|---|
| `match_id` | string | SkillCorner id (e.g. `"1874553"`) or `metrica_game_{1,2,3}` |
| `source` | string | `skillcorner` / `metrica` |
| `period`, `frame_id` | int8, int64 | original ids |
| `timestamp_s` | float64 | see SC-3 / ME-6 |
| `object_type` | string | `player` / `ball` |
| `player_id`, `team_id`, `team_side`, `jersey_number`, `position` | string / Int16 | NA for the ball |
| `x_raw`, `y_raw`, `x_m`, `y_m` | float64 | see above |
| `is_detected` | boolean (nullable) | see SC-5 / ME-3 |
| `ball_z` | float64 | SkillCorner ball only; about 70% of ball rows have it |
| `possession_group`, `possession_player_id` | string | raw SkillCorner values; null for Metrica |
| `x_home_m`, `y_home_m`, `x_att_m`, `y_att_m` | float64 | see §4 |
| `status_conflict` | bool | True for all rows of 1953632 |

## 6. QA thresholds (not transforms)

| Threshold | Where | Use |
|---|---|---|
| Off-pitch "any" = outside the lines. Report margin = 2 m | `src/build.py:19`, `tests/test_bounds.py:20` | Reported, never dropped |
| Hard limit = 15 m outside | `tests/test_bounds.py:21` | Catches unit or origin bugs. No row exceeds it (max is 11 m) |
| Kick-off tolerance = 1 m over halfway | `src/metrica.py:217` | For the kicker standing on the line |

# Caveats: what the data is safe for

A one-page summary of Phase 2 (plan: "which matches, periods and frame types are safe for which question
types"). Evidence is in `notebooks/phase2_usable.ipynb` and `notebooks/phase2_exploration.ipynb`; figures are in
`notebooks/figures/`. Decisions are in `DECISIONS.md`.

## 1. The core rule

A question may only be asked about a moment where **every player whose position decides the answer was
detected** (seen by the camera), not extrapolated. `src/usable.py` implements this as
`is_usable(frame, question_type, attacking_side=..., carrier_id=..., receiver_id=...)`.
Ground truth is defined on the coordinates shown to the model (D10).

## 2. Safe-use table

| Question type | SkillCorner (20 matches) | Metrica (3 games) | Notes |
|---|---|---|---|
| `offside` | **40%** of pass moments usable (6,349 / 16,072); 59% of offside-possible ones | 100% | Bottleneck: the second-last defender is detected at only 45% of passes. Only 96 real offsides in total (85 + 11) |
| `nearest_to_carrier` | **94%** usable | 100% | Abundant |
| `defenders_goal_side` | **95%** usable | 100% | Abundant |
| `overload_zone` (15 m circle around the carrier) | **67%** usable | 100% | Plenty |

Metrica has no extrapolation: a player with a position was tracked. Its positions are treated as fully reliable.

## 3. Known biases (state these in the memo)

1. **Broadcast tracking under-records the back line and long balls.** Usable offside moments: 8% with the
   ball in a team's own third, 86% in the final third. Receiver 30+ m ahead of the ball: 3% usable. Long balls
   over the top, the classic offside situation, are nearly absent (about 19 usable across both sources).
   *Figure 3.*
2. **Big moments are invisible.** Tracking disappears after shots: no-tracking frames rise from the 26%
   baseline to about 65% around 10–15 s after a shot, and to **97–100% for 10–40 s after a goal** (replays).
   Event files are derived from tracking, so these moments don't exist in the data at all. Anything that happens
   in the minute after a goal is unsampled. *Figure 5.*
3. **Real offsides are rare and thin.** 2.7% of usable offside-possible passes are offside, and 75 of the 96 are within 1 m.
   Handled by balancing within margin bins (D11). *Figure 4.*
4. **Late-season matches are worse.** The five latest matches (2011166 to 2017461) have the lowest detection
   (49–54% of player rows) and 25–34% offside usability, and they start later in the file with longer half-time gaps.
   Likely a different broadcast setup. *Figure 2.*

## 4. Match- and frame-level notes

| Item | Status |
|---|---|
| **1953632** (`not_started` in metadata) | Data looks normal: detection 62% (others 49–66%), offside usability 44% (others 25–57%), plausible frames. **Kept**, flag retained (D1). |
| Frames with no tracking (19–34% per match) | Not usable for anything. They exist only as a ball row with no position. |
| Tracking glitches (speed > 12 m/s between frames) | Rare: at most 0.015% of player steps in SkillCorner and 0.035% in Metrica. Some are teleports (max 243 m/s in 2011166, 557 m/s in Metrica game 1), probably identity swaps. Too rare to filter globally. Excluding the specific frames in Phase 3 is optional (D14). |
| Metrica game 1, period 1 | Tracking starts just after the kick-off. Use frame 3675 for a clean kick-off (D6). |
| Phase-of-play labels | Clip `frame_end` to the period end when joining. Three phases overrun by up to 9 frames (D8). |
| Metrica `Player 26` (game 2) | Kept raw; it matches the event file (D4). |

## 5. What is not covered by the checks

- `is_usable` only covers Tier 1 geometric questions. Tier 2 (pitch control) needs all 22 players detected, or
  must be reported as model agreement with extrapolated inputs. Decide in Phase 3.
- Detection is SkillCorner's own flag. It can't be verified independently. SkillCorner reports that about 97%
  of player identities are accurate.

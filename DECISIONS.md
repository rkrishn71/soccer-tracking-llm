# Decisions log

A record of each decision: what was chosen, when, and why. It covers the six open questions in
PHASE1_REPORT.md §4, plus calls made along the way.

| # | Question | Decision | Status |
|---|---|---|---|
| D1 | Match 1953632 (`not_started` but full data) | Keep it flagged (`status_conflict=True`). Plot a few frames early in Phase 2, then decide whether to keep or exclude it. Its usable-pass share (44%) is in line with other matches. | decided, revisit in Phase 2 |
| D2 | Frames with no tracking (19–34%) | _to decide._ First check in Phase 2: do these frames cluster just after shot and goal events? If so, the benchmark under-samples big moments, and the memo must say so. Note: every SkillCorner pass event falls in a tracked frame, because events are derived from tracking. Moments during cutaways are therefore missing from the event file entirely, not just unusable. | open |
| D3 | Metrica possession | Derive it **only at event moments**, from the event file (who passed). No per-frame possession is needed, because Metrica items are anchored to passes. | decided |
| D4 | Game 2 `Player 26` naming | Keep the raw name. Tracking and the event file use the same spelling, so joins work. Renaming would break that. | decided (2026-10-15) |
| D5 | Off-pitch extrapolated rows >2 m | Keep them flagged and never drop them. They can't affect any item's answer, because `is_usable` requires every player the answer depends on to be detected. Whether to show them in prompts is part of D7. | decided (2026-10-15) |
| D6 | Game 1 period-1 kick-off | Accept the Phase 1 call: tracking starts after the kick-off. The shot and deepest-player checks agree, and team averages are clearly in their own halves. Use frame 3675 if a clean period-1 kick-off frame is needed. | decided |
| D7 | Extrapolated players in LLM prompts | **Show all players** (detected and extrapolated), with no detection flags. Answers only ever depend on detected players (`is_usable`), so the scene looks complete without the answer resting on a guess. | decided (2026-10-27) |
| D8 | Phase labels running past the period end | Clip each phase's `frame_end` to its period's `end_frame` when joining. | decided |
| D9 | Definition of a usable pass (offside items) | At the pass frame (`frame_end` of a `player_possession` ending in `pass`), the passer, the **intended** receiver (`player_targeted_id`), the ball and the second-last defender must all be detected. Ties in defender position are broken by `player_id` (stable sort), so the result is deterministic. First cut: all passes counted; next step is to restrict to forward passes in the attacking half. | decided (2026-10-15), refine |
| D10 | What "correct answer" means | Ground truth is defined **relative to the coordinates shown to the model**, not the real-world refereeing call. A 20 cm offside is a valid (hard) item because its answer follows exactly from the input. The memo must state this. | decided (2026-10-16) |
| D11 | Getting enough offside positives | v1 uses **all real offside positions** (85 SkillCorner + 11 Metrica = 96), each matched with an onside near-miss **in the same \|margin\| bin** (0–0.5, 0.5–1, 1–2, 2–5 m), sampled with a fixed seed (2026). Result: 192 items, 96/96. Counterfactual (nudged) scenes and PFF data are deferred to v2. | decided (2026-10-16) |
| D15 | Prompt orientation | **The team in possession always attacks to the right (+x)** (`orientation="attack_right"`). This keeps "which way is forward" out of the reasoning load. `"broadcast"` orientation is available as an optional extra Phase 4 factor. | decided (2026-10-27) |
| D16 | Coordinate precision | **2 decimal places.** Ground truth is computed from the rounded, displayed scene; exact ties after rounding are dropped (none in v0). | decided (2026-10-27) |
| D17 | Labels and team names | Team in possession = **Blue**, other team = **Orange**, players labelled "Blue 9" (shirt number), matching the image colours. Options are lettered A, B, …; team names are words, so they never clash with option letters. | decided (2026-10-27) |
| D18 | Tier 1 non-offside items | 36 each of nearest_to_carrier, defenders_goal_side, overload_zone (Tier 1 = 300 with offside). Balanced by difficulty bin and correct letter (nearest, goal-side) or outcome (overload). Distractors: 2nd–4th nearest players; 4 consecutive counts with the correct count at a balanced letter. No frame reused across Tier 1. Seed 2026. | decided (2026-10-29) |
| D19 | Overload zone in the image format | Draw the 15 m circle around the carrier (the zone is part of the question); the coordinates format states the radius in text. | decided (2026-10-29) |

## Log

- **2026-10-13:** Rebuilt Phase 1 locally: 218 tests pass, and `verify_phase1.py` matches every count (31,840,119 rows).
- **2026-10-15:** Hand trace passed. SkillCorner 1874553, frame 40000, player 26766, and Metrica game 1, frame 100000, Player4: every coordinate column matched the hand-computed predictions, including the unit conversion, the y-flip and both direction rotations.
- **2026-10-15:** CONVENTIONS.md §6 corrected: the maximum off-pitch distance is about 13 m (past a touch line), not 11 m.
- **2026-10-15:** Usable-pass count (`notebooks/phase2_usable.ipynb`): 6,349 / 16,072 SkillCorner passes usable. The rate per match runs from 25% to 57%, and the five latest matches are all 25–34%. Fixed a tie-break bug that made one pass differ between machines.
- **2026-10-16:** Metrica offside check: 2,884 passes, all usable; 861 offside-possible; only **11 offside** (10 within 1 m). The plan's assumption that Metrica fills the offside gap does not hold. It adds just 11 positives and 11 long balls (30+ m).
- **2026-10-16:** Built the balanced offside candidate set (`data/processed/qa/offside_candidates.parquet`): 192 items, 96 offside / 96 onside, balanced within each margin bin.
- **2026-10-27:** Phase 3 step 1: `src/items.py` (Item format, scene builder, offside ground truth from the displayed scene), `src/prompts.py` (coordinates + image formats, direct + reason styles), 192 offside items in `items/tier1_offside_v0.jsonl`.
- **2026-10-29:** Phase 3 step 2: Tier 1 complete, 300 items in `items/tier1_v0.jsonl` (192 offside + 36 nearest + 36 goal-side + 36 overload). `src/tier1.py`, `tests/test_tier1.py`, `notebooks/phase3_tier1.ipynb`.
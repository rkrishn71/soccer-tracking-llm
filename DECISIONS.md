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
| D7 | Extrapolated players in LLM prompts | _to decide; goes in the memo._ Candidate: show all players, but only build questions whose answer depends entirely on detected players (an `is_usable` flag). Evidence so far: the second-last defender is detected at only 45% of pass moments, the bottleneck. 6,349 of 16,072 SkillCorner passes (39.5%) are fully usable, plus 2,884 Metrica passes, all usable. | open |
| D8 | Phase labels running past the period end | Clip each phase's `frame_end` to its period's `end_frame` when joining. | decided |
| D9 | Definition of a usable pass (offside items) | At the pass frame (`frame_end` of a `player_possession` ending in `pass`), the passer, the **intended** receiver (`player_targeted_id`), the ball and the second-last defender must all be detected. Ties in defender position are broken by `player_id` (stable sort), so the result is deterministic. First cut: all passes counted; next step is to restrict to forward passes in the attacking half. | decided (2026-10-15), refine |
| D10 | What "correct answer" means | Ground truth is defined **relative to the coordinates shown to the model**, not the real-world refereeing call. A 20 cm offside is a valid (hard) item because its answer follows exactly from the input. The memo must state this. | decided (2026-10-16) |
| D11 | Getting enough offside positives | v1 uses **all real offside positions** (85 SkillCorner + 11 Metrica = 96), each matched with an onside near-miss **in the same \|margin\| bin** (0–0.5, 0.5–1, 1–2, 2–5 m), sampled with a fixed seed (2026). Result: 192 items, 96/96. Counterfactual (nudged) scenes and PFF data are deferred to v2. | decided (2026-10-16) |

## Log

- **2026-10-13:** Rebuilt Phase 1 locally: 218 tests pass, and `verify_phase1.py` matches every count (31,840,119 rows).
- **2026-10-15:** Hand trace passed. SkillCorner 1874553, frame 40000, player 26766, and Metrica game 1, frame 100000, Player4: every coordinate column matched the hand-computed predictions, including the unit conversion, the y-flip and both direction rotations.
- **2026-10-15:** CONVENTIONS.md §6 corrected: the maximum off-pitch distance is about 13 m (past a touch line), not 11 m.
- **2026-10-15:** Usable-pass count (`notebooks/phase2_usable.ipynb`): 6,349 / 16,072 SkillCorner passes usable. The rate per match runs from 25% to 57%, and the five latest matches are all 25–34%. Fixed a tie-break bug that made one pass differ between machines.
- **2026-10-16:** Metrica offside check: 2,884 passes, all usable; 861 offside-possible; only **11 offside** (10 within 1 m). The plan's assumption that Metrica fills the offside gap does not hold. It adds just 11 positives and 11 long balls (30+ m).
- **2026-10-16:** Built the balanced offside candidate set (`data/processed/qa/offside_candidates.parquet`): 192 items, 96 offside / 96 onside, balanced within each margin bin.
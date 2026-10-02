# Decisions log

A record of each decision: what was chosen, when, and why. It covers the six open questions in
PHASE1_REPORT.md §4, plus calls made along the way.

| # | Question | Decision | Status |
|---|---|---|---|
| D1 | Match 1953632 (`not_started` but full data) | Keep it flagged (`status_conflict=True`). Plot a few frames early in Phase 2, then decide whether to keep or exclude it. | decided, revisit in Phase 2 |
| D2 | Frames with no tracking (19–34%) | _to decide._ First check in Phase 2: do these frames cluster just after shot and goal events? If so, the benchmark under-samples big moments, and the memo must say so. | open |
| D3 | Metrica possession | Derive it **only at event moments**, from the event file (who passed). No per-frame possession is needed, because Metrica items are anchored to passes. | decided |
| D4 | Game 2 `Player 26` naming | _to decide_ (currently kept raw; it matches the event file). | open |
| D5 | Off-pitch extrapolated rows >2 m | _to decide_ (currently flagged only). | open |
| D6 | Game 1 period-1 kick-off | Accept the Phase 1 call: tracking starts after the kick-off. The shot and deepest-player checks agree, and team averages are clearly in their own halves. Use frame 3675 if a clean period-1 kick-off frame is needed. | decided |
| D7 | Extrapolated players in LLM prompts | _to decide; goes in the memo._ Candidate: show all players, but only build questions whose answer depends entirely on detected players (an `is_usable` flag). | open |
| D8 | Phase labels running past the period end | Clip each phase's `frame_end` to its period's `end_frame` when joining. | decided |

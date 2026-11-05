"""Tier 1 question types beyond offside: nearest player, defenders goal-side, overload.

Same rules as src/items.py (D10, D16): every answer is computed from the stored, rounded
scene the model sees; exact ties after rounding are dropped; nothing in the prompt leaks the
answer. See DECISIONS D18 for the selection design.

    from src.tier1 import nearest_item, goal_side_item, overload_item, build_tier1_others
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .items import ATTACK, DEFEND, DECIMALS, Item, _dir, _player, build_scene, make_item_id
from .load import get_frame

OVERLOAD_RADIUS_M = 15.0          # zone = circle around the ball carrier (same as src/usable.py)
LETTERS = "ABCD"


# ----------------------------------------------------------------------------- ground truth
def nearest_truth(scene: dict, carrier: str) -> dict:
    """Players of EITHER team ranked by distance to the carrier (carrier excluded)."""
    c = _player(scene, carrier)
    ranked = sorted(((float(np.hypot(p["x"] - c["x"], p["y"] - c["y"])), p["label"])
                     for p in scene["players"] if p["label"] != carrier))
    (d1, nearest), (d2, _) = ranked[0], ranked[1]
    return {"nearest": nearest, "ranked": [l for _, l in ranked], "distances": [d for d, _ in ranked],
            "nearest_m": d1, "gap_m": d2 - d1}


def goal_side_truth(scene: dict) -> dict:
    """Number of Orange (defending) players strictly closer than the ball to the goal Orange defends."""
    d = _dir(scene)
    bx = scene["ball"]["x"] * d
    xs = [p["x"] * d for p in scene["players"] if p["team"] == DEFEND]
    return {"count": sum(x > bx for x in xs), "n_defending": len(xs),
            "tie": any(x == bx for x in xs),
            "near_line_1m": sum(abs(x - bx) <= 1.0 for x in xs),
            "closest_to_line_m": min(abs(x - bx) for x in xs)}


def overload_truth(scene: dict, carrier: str, radius: float = OVERLOAD_RADIUS_M) -> dict:
    """Players of each team within `radius` m of the carrier (carrier counts for Blue)."""
    c = _player(scene, carrier)
    dist = {p["label"]: float(np.hypot(p["x"] - c["x"], p["y"] - c["y"])) for p in scene["players"]}
    team = {p["label"]: p["team"] for p in scene["players"]}
    blue = sum(1 for l, dd in dist.items() if dd <= radius and team[l] == ATTACK)
    orange = sum(1 for l, dd in dist.items() if dd <= radius and team[l] == DEFEND)
    outcome = "blue" if blue > orange else "orange" if orange > blue else "equal"
    return {"blue": blue, "orange": orange, "outcome": outcome,
            "on_edge": any(dd == radius for dd in dist.values()),
            "near_edge_1m": sum(1 for dd in dist.values() if abs(dd - radius) <= 1.0)}


# ----------------------------------------------------------------------------- item builders
def _scene(m, decimals, include_extrapolated):
    frame = get_frame(m.match, int(m.frame))
    scene, hidden = build_scene(frame, m.match, m.attacking_side, orientation="attack_right",
                                decimals=decimals, include_extrapolated=include_extrapolated)
    by_id = {v["player_id"]: k for k, v in hidden.items()}
    return frame, scene, hidden, by_id.get(str(m.carrier_id))


def _base(m, qtype, frame, scene, hidden, carrier, decimals, include_extrapolated, extra=None):
    return dict(tier=1, question_type=qtype, source=m.source, match_id=str(m.match),
                period=int(frame.period.iloc[0]), frame_id=int(m.frame), scene=scene,
                provenance={"carrier": carrier, "labels": hidden, "orientation": "attack_right",
                            "decimals": decimals, "include_extrapolated": include_extrapolated,
                            "moment_event_id": str(m.event_id), **(extra or {})})


def nearest_item(m, correct_letter: str, *, decimals=DECIMALS, include_extrapolated=True,
                 seed: int = 2026) -> Item | None:
    """'Which player is closest to <carrier>?' 4 options: the nearest + the 2nd-4th nearest."""
    frame, scene, hidden, carrier = _scene(m, decimals, include_extrapolated)
    if carrier is None or scene["ball"] is None:
        return None
    t = nearest_truth(scene, carrier)
    if t["gap_m"] == 0:
        return None
    distractors = t["ranked"][1:4]
    rng = np.random.default_rng([seed, int(m.frame)])
    distractors = list(rng.permutation(distractors))
    opts = distractors[:]
    opts.insert(LETTERS.index(correct_letter), t["nearest"])
    options = dict(zip(LETTERS, opts))
    question = (f"Which player (from either team, not counting {carrier} itself) is closest to {carrier}, "
                f"who has the ball? Measure straight-line distance between the points given.")
    return Item(item_id=make_item_id("t1-nearest", m.match, m.frame, m.carrier_id),
                question=question, options=options, answer=correct_letter, answer_value=t["nearest"],
                difficulty={"gap_m": round(t["gap_m"], 4), "nearest_m": round(t["nearest_m"], 4),
                            "players_within_10m_of_carrier": int(sum(d <= 10 for d in t["distances"]))},
                **_base(m, "nearest_to_carrier", frame, scene, hidden, carrier, decimals, include_extrapolated))


def goal_side_item(m, correct_letter: str, *, decimals=DECIMALS, include_extrapolated=True,
                   seed: int = 2026) -> Item | None:
    """'How many Orange players are goal-side of the ball?'

    Options = 4 consecutive counts containing the answer (window kept inside 0..n_defending).
    The correct count is placed at `correct_letter`; the 3 distractors fill the other letters in
    ascending order. (Fully sorted options would force e.g. a count of 11 to always be "D".)"""
    frame, scene, hidden, carrier = _scene(m, decimals, include_extrapolated)
    if scene["ball"] is None:
        return None
    t = goal_side_truth(scene)
    if t["tie"]:
        return None
    n, c = t["n_defending"], t["count"]
    if n < 4:
        return None
    rng = np.random.default_rng([seed, int(m.frame)])
    lo = int(np.clip(c - rng.integers(0, 4), 0, n - 3))          # window [lo, lo+3] contains c
    distractors = [v for v in range(lo, lo + 4) if v != c]
    vals = distractors[:]
    vals.insert(LETTERS.index(correct_letter), c)
    options = {L: str(v) for L, v in zip(LETTERS, vals)}
    L = scene["pitch"]["length_m"]
    question = (f"How many {DEFEND} players are goal-side of the ball, i.e. closer than the ball to the goal "
                f"{DEFEND} defends (the goal at x = +{L / 2:g})? Compare x coordinates only.")
    return Item(item_id=make_item_id("t1-goalside", m.match, m.frame),
                question=question, options=options, answer=correct_letter, answer_value=t["count"],
                difficulty={"count": t["count"], "near_line_1m": t["near_line_1m"],
                            "closest_to_line_m": round(t["closest_to_line_m"], 4),
                            "ball_x": scene["ball"]["x"]},
                **_base(m, "defenders_goal_side", frame, scene, hidden, carrier, decimals, include_extrapolated))


OVERLOAD_OPTIONS = {"A": f"{ATTACK} has more players", "B": f"{DEFEND} has more players",
                    "C": "Both teams have the same number"}
OVERLOAD_LETTER = {"blue": "A", "orange": "B", "equal": "C"}


def overload_item(m, *, decimals=DECIMALS, include_extrapolated=True,
                  radius: float = OVERLOAD_RADIUS_M) -> Item | None:
    """'Within 15 m of <carrier>, which team has more players?' Blue more / Orange more / equal."""
    frame, scene, hidden, carrier = _scene(m, decimals, include_extrapolated)
    if carrier is None:
        return None
    t = overload_truth(scene, carrier, radius)
    if t["on_edge"]:
        return None
    question = (f"Count the players of each team within {radius:g} m (straight-line distance) of {carrier}, "
                f"who has the ball. Include {carrier} in the {ATTACK} count. Which team has more players "
                f"inside that circle?")
    return Item(item_id=make_item_id("t1-overload", m.match, m.frame, m.carrier_id),
                question=question, options=dict(OVERLOAD_OPTIONS), answer=OVERLOAD_LETTER[t["outcome"]],
                answer_value=t["outcome"],
                difficulty={"blue_in_zone": t["blue"], "orange_in_zone": t["orange"],
                            "abs_diff": abs(t["blue"] - t["orange"]), "near_edge_1m": t["near_edge_1m"]},
                **_base(m, "overload_zone", frame, scene, hidden, carrier, decimals, include_extrapolated,
                        {"radius_m": radius}))


# ----------------------------------------------------------------------------- selection
def _candidates(moments: pd.DataFrame, usable_col: str, n: int, seed: int, exclude: set) -> pd.DataFrame:
    pool = moments[moments[usable_col] & ~moments.set_index(["match", "frame"]).index.isin(exclude)]
    return pool.sample(n=min(n, len(pool)), random_state=seed)


def build_tier1_others(moments: pd.DataFrame, *, per_type: int = 36, seed: int = 2026,
                       exclude_frames: set | None = None, pool_size: int = 600) -> tuple[list[Item], pd.DataFrame]:
    """Build `per_type` items for each of the three types, balanced by difficulty and answer.

    nearest_to_carrier  : equal numbers per gap bin (<0.5, 0.5-1, 1-2, 2+ m); correct letter cycles A-D.
    defenders_goal_side : equal numbers per count band (<=6, 7-8, 9-10, 11);  correct letter cycles A-D.
    overload_zone       : equal numbers of Blue-more / Orange-more / equal.
    No frame is used twice (across types, and not reused from `exclude_frames`, e.g. offside items).
    """
    used = set(exclude_frames or ())
    items, log = [], []

    def take(qtype, usable_col, make, key, bins, per_bin):
        nonlocal used
        cands = _candidates(moments, usable_col, pool_size, seed, used)
        built = []
        for m in cands.itertuples():
            it = make(m)
            if it is not None:
                built.append(it)
        df = pd.DataFrame({"i": range(len(built)), "key": [key(it) for it in built]})
        df["bin"] = pd.cut(df.key, bins, right=False) if bins is not None else df.key
        chosen = []
        for b, g in df.groupby("bin", observed=True):
            chosen += list(g.i.head(per_bin))           # candidates are already in random order
        sel = [built[i] for i in sorted(chosen)]
        for it in sel:
            used.add((it.match_id, it.frame_id))
        log.append({"question_type": qtype, "candidates": len(cands), "built": len(built), "selected": len(sel)})
        return sel

    # nearest / goal-side: build with a placeholder letter, then assign letters cyclically after selection
    near = take("nearest_to_carrier", "usable_nearest_to_carrier",
                lambda m: nearest_item(m, "A", seed=seed), lambda it: it.difficulty["gap_m"],
                [0, 0.5, 1, 2, np.inf], per_type // 4)
    near = [nearest_item(_moment_of(it, moments), LETTERS[k % 4], seed=seed) for k, it in enumerate(near)]

    gs_built = take("defenders_goal_side", "usable_defenders_goal_side",
                    lambda m: goal_side_item(m, "A", seed=seed),
                    lambda it: it.answer_value, [0, 7, 9, 11, 12], per_type // 4)
    gs = [goal_side_item(_moment_of(it, moments), LETTERS[k % 4], seed=seed) for k, it in enumerate(gs_built)]

    ov = take("overload_zone", "usable_overload_zone", lambda m: overload_item(m),
              lambda it: it.answer_value, None, per_type // 3)

    items = near + gs + ov
    return items, pd.DataFrame(log)


def _moment_of(it: Item, moments: pd.DataFrame):
    r = moments[(moments.match == it.match_id) & (moments.frame == it.frame_id) &
                (moments.event_id.astype(str) == it.provenance["moment_event_id"])]
    return next(r.itertuples())

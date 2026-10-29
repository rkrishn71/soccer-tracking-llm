"""Benchmark items: a self-contained question about one frame, with ground truth.

Design rules (DECISIONS D10, D15–D17):
* An item stores the exact SCENE the model will see (rounded coordinates, neutral labels).
  Ground truth is computed from that stored scene, never from the raw data, so rounding can
  never make the stored answer disagree with what the model is shown.
* Labels are neutral: the team in possession is "Blue", the other team "Orange", players are
  "Blue 9", "Orange 4" (shirt numbers). No roles, no detection flags, nothing pre-sorted.
* Hidden provenance (real player ids, detection flags) lives in `provenance` and is never
  rendered into a prompt.

    from src.items import build_scene, offside_item, save_items, load_items
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .load import get_frame, load_meta

BANK_VERSION = "v0"
ATTACK, DEFEND = "Blue", "Orange"           # team in possession / other team
DECIMALS = 2                                # coordinate precision shown to the model (metres)
ORIENTATIONS = ("attack_right", "broadcast")


# ----------------------------------------------------------------------------- data model
@dataclass
class Item:
    item_id: str
    tier: int
    question_type: str
    source: str
    match_id: str
    period: int
    frame_id: int
    scene: dict                 # exactly what the model sees (see build_scene)
    question: str
    options: dict               # {"A": "...", "B": "..."}
    answer: str                 # option letter
    answer_value: object        # raw answer (bool / label / int), for analysis
    difficulty: dict            # difficulty features, e.g. offside margin
    provenance: dict            # hidden: real ids, detection flags, build settings
    bank_version: str = BANK_VERSION
    split: str | None = None    # "public" / "private", assigned when the bank is frozen

    def to_dict(self) -> dict:
        return asdict(self)


def make_item_id(*parts) -> str:
    h = hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:10]
    return f"{parts[0]}-{h}"


def save_items(items, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for it in items:
            f.write(json.dumps(it.to_dict() if isinstance(it, Item) else it, sort_keys=True) + "\n")
    return path


def load_items(path) -> list[Item]:
    with open(path) as f:
        return [Item(**json.loads(line)) for line in f if line.strip()]


# ----------------------------------------------------------------------------- scenes
def build_scene(frame: pd.DataFrame, match_id: str, attacking_side: str, *,
                orientation: str = "attack_right", decimals: int = DECIMALS,
                include_extrapolated: bool = True) -> tuple[dict, dict]:
    """Turn one processed frame into (scene, hidden).

    scene  : what the model sees - pitch size, attack direction, players, ball (rounded).
    hidden : label -> {player_id, detected}; never shown.

    orientation="attack_right": Blue (in possession) always attacks towards +x.
    orientation="broadcast":    raw x_m/y_m; Blue attacks whichever way it did on TV.
    """
    if orientation not in ORIENTATIONS:
        raise ValueError(f"orientation must be one of {ORIENTATIONS}")
    meta = load_meta(match_id)
    period = int(frame.period.iloc[0])
    if orientation == "attack_right":
        s = 1.0 if attacking_side == "home" else -1.0
        xs, ys = frame.x_home_m * s, frame.y_home_m * s
        direction = "+x"
    else:
        xs, ys = frame.x_m, frame.y_m
        home_plus = meta["attack_direction"][str(period)]["home_attacks_plus_x"]
        direction = "+x" if (home_plus == (attacking_side == "home")) else "-x"

    f = frame.assign(xd=xs.round(decimals), yd=ys.round(decimals))
    players, hidden = [], {}
    pl = f[(f.object_type == "player") & f.xd.notna()]
    if not include_extrapolated:
        pl = pl[pl.is_detected.fillna(False).astype(bool)]
    for r in pl.itertuples():
        team = ATTACK if r.team_side == attacking_side else DEFEND
        num = int(r.jersey_number) if pd.notna(r.jersey_number) else None
        label = f"{team} {num}" if num is not None else f"{team} ?{r.player_id}"
        players.append({"label": label, "team": team, "x": float(r.xd), "y": float(r.yd)})
        hidden[label] = {"player_id": str(r.player_id), "detected": bool(pd.notna(r.is_detected) and r.is_detected)}
    labels = [p["label"] for p in players]
    if len(labels) != len(set(labels)):
        raise ValueError(f"duplicate player labels in {match_id} frame {int(frame.frame_id.iloc[0])}: {labels}")
    # neutral order: team (Blue first), then shirt number - never by position
    players.sort(key=lambda p: (p["team"] != ATTACK, _num(p["label"])))
    b = f[f.object_type == "ball"].iloc[0]
    scene = {
        "pitch": {"length_m": meta["pitch_length_m"], "width_m": meta["pitch_width_m"]},
        "origin": "centre spot", "units": "metres", "y_up": "+y is the top touchline in the image",
        "attack_direction": direction, "in_possession": ATTACK,
        "players": players,
        "ball": {"x": float(b.xd), "y": float(b.yd)} if pd.notna(b.xd) else None,
    }
    return scene, hidden


def _num(label: str) -> float:
    try:
        return float(label.split()[-1])
    except ValueError:
        return 1e9


def _dir(scene) -> float:
    return 1.0 if scene["attack_direction"] == "+x" else -1.0


def _player(scene, label):
    return next(p for p in scene["players"] if p["label"] == label)


# ----------------------------------------------------------------------------- ground truth
def offside_truth(scene: dict, receiver: str) -> dict:
    """Offside position of `receiver`, computed ONLY from the scene (what the model sees).

    In an offside position = in the opponents' half AND nearer the opponents' goal line than
    both the ball and the second-last opponent. Level = not offside.
    """
    d = _dir(scene)
    rx = _player(scene, receiver)["x"] * d
    bx = scene["ball"]["x"] * d
    opp = sorted((p["x"] * d for p in scene["players"] if p["team"] == DEFEND), reverse=True)
    second_last = opp[1]
    return {
        "offside": bool(rx > 0 and rx > bx and rx > second_last),
        "margin_m": round(rx - second_last, 6),
        "ahead_of_ball_m": round(rx - bx, 6),
        "in_opponents_half": bool(rx > 0),
    }


# ----------------------------------------------------------------------------- item builders
OFFSIDE_RULE = ("Offside position (Laws of the Game, Law 11): a player is in an offside position if "
                "any part of the head, body or feet is in the opponents' half (excluding the halfway "
                "line) and is nearer to the opponents' goal line than both the ball and the "
                "second-last opponent. Being level with the second-last opponent or the ball is NOT "
                "an offside position. Treat each player as the single point given.")


def offside_item(match_id: str, frame_id: int, attacking_side: str, passer_id: str, receiver_id: str, *,
                 source: str, orientation: str = "attack_right", decimals: int = DECIMALS,
                 include_extrapolated: bool = True) -> Item | None:
    """Build one Tier 1 offside item. Returns None if the displayed scene is unusable
    (missing players/ball, or an exact tie after rounding)."""
    frame = get_frame(match_id, frame_id)
    scene, hidden = build_scene(frame, match_id, attacking_side, orientation=orientation,
                                decimals=decimals, include_extrapolated=include_extrapolated)
    by_id = {v["player_id"]: k for k, v in hidden.items()}
    passer, receiver = by_id.get(str(passer_id)), by_id.get(str(receiver_id))
    if passer is None or receiver is None or scene["ball"] is None:
        return None
    t = offside_truth(scene, receiver)
    if t["margin_m"] == 0:            # exact tie after rounding: legal but too ambiguous to keep
        return None
    px, py = _player(scene, passer)["x"], _player(scene, passer)["y"]
    rx, ry = _player(scene, receiver)["x"], _player(scene, receiver)["y"]
    bx, by = scene["ball"]["x"], scene["ball"]["y"]
    near_ball = sum(1 for p in scene["players"] if np.hypot(p["x"] - bx, p["y"] - by) <= 10)
    question = (f"{passer} is about to pass the ball to {receiver}. "
                f"At this moment, is {receiver} in an offside position?")
    options = {"A": "Yes, offside position", "B": "No, not in an offside position"}
    return Item(
        item_id=make_item_id("t1-offside", match_id, frame_id, passer_id, receiver_id, orientation),
        tier=1, question_type="offside", source=source, match_id=str(match_id),
        period=int(frame.period.iloc[0]), frame_id=int(frame_id),
        scene=scene, question=question, options=options,
        answer="A" if t["offside"] else "B", answer_value=t["offside"],
        difficulty={"offside_margin_m": t["margin_m"], "abs_margin_m": abs(t["margin_m"]),
                    "receiver_ahead_of_ball_m": t["ahead_of_ball_m"],
                    "pass_distance_m": round(float(np.hypot(rx - px, ry - py)), 2),
                    "players_within_10m_of_ball": near_ball},
        provenance={"passer": passer, "receiver": receiver, "labels": hidden,
                    "orientation": orientation, "decimals": decimals,
                    "include_extrapolated": include_extrapolated,
                    "rule_text": OFFSIDE_RULE},
    )


# ----------------------------------------------------------------------------- selection
MARGIN_BINS = [0, 0.5, 1, 2, 5]


def select_balanced_offside(moments: pd.DataFrame, seed: int = 2026) -> pd.DataFrame:
    """D11: every usable offside moment + an equal number of onside near-misses per |margin| bin.

    `moments` = output of src.moments.evaluate_moments / evaluate_all (any order-preserving concat,
    SkillCorner matches first, then Metrica - the same order as notebooks/phase2_usable.ipynb).
    """
    pool = moments[moments.offside_possible & moments.usable_offside].copy()
    pool["abs_margin_m"] = pool.offside_margin_m.abs()
    pool["margin_bin"] = pd.cut(pool.abs_margin_m, MARGIN_BINS, include_lowest=True)
    pos = pool[pool.offside]
    parts = [pos]
    for b, n in pos.groupby("margin_bin", observed=True).size().items():
        neg = pool[(~pool.offside) & (pool.margin_bin == b)]
        parts.append(neg.sample(n=min(n, len(neg)), random_state=seed))
    out = pd.concat(parts).sort_values(["source", "match", "frame"]).reset_index(drop=True)
    out["margin_bin"] = out.margin_bin.astype(str)
    return out


def build_offside_items(selected: pd.DataFrame, **kw) -> tuple[list[Item], pd.DataFrame]:
    """offside_item for each selected moment. Returns (items, dropped) - dropped rows say why."""
    items, dropped = [], []
    for r in selected.itertuples():
        it = offside_item(r.match, int(r.frame), r.attacking_side, r.carrier_id, r.receiver_id,
                          source=r.source, **kw)
        if it is None:
            dropped.append({"match": r.match, "frame": r.frame, "reason": "unusable after rounding/missing"})
        elif it.answer_value != bool(r.offside):
            dropped.append({"match": r.match, "frame": r.frame, "reason": "label flipped by rounding"})
        else:
            items.append(it)
    return items, pd.DataFrame(dropped)

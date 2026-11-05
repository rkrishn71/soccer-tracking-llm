"""Tier 1 question types beyond offside: ground truth, options, balance, consistency."""
import re
from collections import Counter

import pytest

from src.items import ATTACK, DEFEND, Item
from src.prompts import text_prompt
from src.tier1 import goal_side_truth, nearest_truth, overload_truth


def scene(players, ball=(0.0, 0.0), direction="+x"):
    return {"pitch": {"length_m": 105.0, "width_m": 68.0}, "origin": "centre spot", "units": "metres",
            "y_up": "", "attack_direction": direction, "in_possession": ATTACK,
            "players": [{"label": l, "team": l.split()[0], "x": x, "y": y} for l, x, y in players],
            "ball": {"x": ball[0], "y": ball[1]}}


# ---------------------------------------------------------------- nearest
def test_nearest_either_team_and_gap():
    sc = scene([("Blue 10", 0, 0), ("Blue 7", 5, 0), ("Orange 4", 0, 3), ("Orange 5", 10, 10)])
    t = nearest_truth(sc, "Blue 10")
    assert t["nearest"] == "Orange 4"             # an opponent can be nearest
    assert t["ranked"][:2] == ["Orange 4", "Blue 7"]
    assert t["gap_m"] == pytest.approx(2.0)


def test_nearest_uses_2d_distance_not_x():
    sc = scene([("Blue 10", 0, 0), ("Blue 7", 3, 9), ("Orange 4", 6, 0)])
    assert nearest_truth(sc, "Blue 10")["nearest"] == "Orange 4"   # 6 m vs 9.49 m, despite larger x


# ---------------------------------------------------------------- goal side
@pytest.mark.parametrize("direction", ["+x", "-x"])
def test_goal_side_count(direction):
    d = 1 if direction == "+x" else -1
    sc = scene([("Blue 9", 0, 0)] + [(f"Orange {k}", d * x, 0) for k, x in
                                     enumerate([40, 30, 20, 11, 9, -5], start=1)],
               ball=(d * 10, 0), direction=direction)
    t = goal_side_truth(sc)
    assert t["count"] == 4 and not t["tie"]        # 40, 30, 20, 11 are beyond the ball's x=10
    assert t["near_line_1m"] == 2                  # 11 and 9 are within 1 m of the ball line


def test_goal_side_tie_flagged():
    sc = scene([("Orange 1", 10, 0), ("Orange 2", 20, 0)], ball=(10, 0))
    assert goal_side_truth(sc)["tie"] is True


# ---------------------------------------------------------------- overload
def test_overload_counts_and_carrier_included():
    sc = scene([("Blue 10", 0, 0), ("Blue 7", 10, 0), ("Orange 4", 0, 14.9), ("Orange 5", 15.1, 0),
                ("Orange 6", -5, 5)])
    t = overload_truth(sc, "Blue 10", radius=15)
    assert (t["blue"], t["orange"], t["outcome"]) == (2, 2, "equal")   # Orange 5 at 15.1 m is outside


def test_overload_edge_flag():
    sc = scene([("Blue 10", 0, 0), ("Orange 4", 15, 0)])
    assert overload_truth(sc, "Blue 10", radius=15)["on_edge"] is True


# ---------------------------------------------------------------- built bank (real data)
@pytest.fixture(scope="module")
def built():
    import pandas as pd
    from src.config import PROCESSED
    from src.tier1 import build_tier1_others
    path = PROCESSED / "qa" / "tier1_moments.parquet"
    if not path.exists():
        pytest.skip("run notebooks/phase2_exploration.ipynb first (creates tier1_moments.parquet)")
    items, _ = build_tier1_others(pd.read_parquet(path), per_type=12, pool_size=200)
    return items


@pytest.mark.slow
def test_built_items_balanced_and_unique(built):
    by_type = Counter(i.question_type for i in built)
    assert by_type == {"nearest_to_carrier": 12, "defenders_goal_side": 12, "overload_zone": 12}
    for q in ("nearest_to_carrier", "defenders_goal_side"):
        assert Counter(i.answer for i in built if i.question_type == q) == {"A": 3, "B": 3, "C": 3, "D": 3}
    assert Counter(i.answer for i in built if i.question_type == "overload_zone") == {"A": 4, "B": 4, "C": 4}
    assert len({(i.match_id, i.frame_id) for i in built}) == len(built)


@pytest.mark.slow
def test_built_answers_recomputable_from_prompt(built):
    """Parse the coordinates back out of each prompt and recompute the answer."""
    for it in built:
        p = text_prompt(it)
        rows = re.findall(r"^(Blue \d+|Orange \d+|Ball) \| (-?[\d.]+) \| (-?[\d.]+)$", p, flags=re.M)
        players = [(l, float(x), float(y)) for l, x, y in rows if l != "Ball"]
        bx, by = [(float(x), float(y)) for l, x, y in rows if l == "Ball"][0]
        sc = scene(players, ball=(bx, by), direction=it.scene["attack_direction"])
        if it.question_type == "nearest_to_carrier":
            assert it.options[it.answer] == nearest_truth(sc, it.provenance["carrier"])["nearest"]
        elif it.question_type == "defenders_goal_side":
            assert int(it.options[it.answer]) == goal_side_truth(sc)["count"]
        else:
            assert overload_truth(sc, it.provenance["carrier"])["outcome"] == it.answer_value
        for banned in ("goalkeeper", "detected", "extrapolated"):
            assert banned not in p.lower()

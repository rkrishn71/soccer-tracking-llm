"""Items and prompts: ground truth, no-leak rules, rounding consistency, I/O, rendering."""
import re

import pytest

from src.items import ATTACK, DEFEND, Item, load_items, offside_truth, save_items
from src.prompts import image_prompt, render_scene, text_prompt


def scene(direction="+x", receiver_x=31.0, ball_x=10.0):
    d = 1 if direction == "+x" else -1
    players = [
        {"label": "Blue 9", "team": ATTACK, "x": receiver_x * d, "y": 0.0},
        {"label": "Blue 10", "team": ATTACK, "x": ball_x * d, "y": 5.0},
        {"label": "Orange 1", "team": DEFEND, "x": 50.0 * d, "y": 0.0},   # last opponent
        {"label": "Orange 4", "team": DEFEND, "x": 30.0 * d, "y": -3.0},  # second-last
        {"label": "Orange 5", "team": DEFEND, "x": 25.0 * d, "y": 8.0},
    ]
    return {"pitch": {"length_m": 105.0, "width_m": 68.0}, "origin": "centre spot", "units": "metres",
            "y_up": "", "attack_direction": direction, "in_possession": ATTACK,
            "players": players, "ball": {"x": ball_x * d, "y": 5.0}}


def item(sc=None):
    sc = sc or scene()
    t = offside_truth(sc, "Blue 9")
    return Item(item_id="t1-offside-test", tier=1, question_type="offside", source="test",
                match_id="m", period=1, frame_id=1, scene=sc,
                question="Blue 10 is about to pass the ball to Blue 9. At this moment, is Blue 9 in an offside position?",
                options={"A": "Yes, offside position", "B": "No, not in an offside position"},
                answer="A" if t["offside"] else "B", answer_value=t["offside"], difficulty={},
                provenance={"rule_text": "Offside position rule text."})


# ---------------------------------------------------------------- ground truth
@pytest.mark.parametrize("direction", ["+x", "-x"])
def test_offside_truth_basic(direction):
    assert offside_truth(scene(direction, receiver_x=31.0), "Blue 9")["offside"] is True     # beyond 2nd-last
    assert offside_truth(scene(direction, receiver_x=29.0), "Blue 9")["offside"] is False    # behind 2nd-last
    assert offside_truth(scene(direction, receiver_x=30.0), "Blue 9")["offside"] is False    # level = onside
    assert offside_truth(scene(direction, receiver_x=31.0, ball_x=35.0), "Blue 9")["offside"] is False  # behind ball


def test_offside_truth_own_half():
    sc = scene(receiver_x=-1.0, ball_x=-10.0)
    for p in sc["players"]:
        if p["team"] == DEFEND:
            p["x"] -= 40          # pull the defence deep into Blue's half
    assert offside_truth(sc, "Blue 9")["offside"] is False


# ---------------------------------------------------------------- prompts: no leaks
def test_text_prompt_contents_and_no_leaks():
    p = text_prompt(item(), "direct")
    assert "105 m long" in p and "centre spot" in p and "attacks towards +x" in p
    assert "Offside position rule text." in p
    assert '"confidence"' in p and "A) Yes" in p
    for banned in ("margin", "goalkeeper", "detected", "extrapolated", "second-last defender is"):
        assert banned not in p.lower()


def test_rows_not_sorted_by_position():
    # Orange numbers 1,4,5 have x = 50, 30, 25: number order != x order
    p = text_prompt(item())
    orange_rows = [l.split(" | ")[0] for l in p.splitlines() if l.startswith("Orange") and " | " in l]
    assert orange_rows == ["Orange 1", "Orange 4", "Orange 5"]
    blue_rows = [l.split(" | ")[0] for l in p.splitlines() if l.startswith("Blue") and " | " in l]
    assert blue_rows == ["Blue 9", "Blue 10"]   # as stored (scene builder sorts by number)


def test_answer_recomputable_from_prompt_text():
    """Parse the table back out of the prompt and recompute: must equal the stored answer."""
    for rx in (29.99, 30.01, 31.0, 28.5):
        it = item(scene(receiver_x=rx))
        p = text_prompt(it)
        rows = re.findall(r"^(Blue \d+|Orange \d+|Ball) \| (-?[\d.]+) \| (-?[\d.]+)$", p, flags=re.M)
        players = [{"label": l, "team": l.split()[0], "x": float(x), "y": float(y)} for l, x, y in rows if l != "Ball"]
        bx, by = [(float(x), float(y)) for l, x, y in rows if l == "Ball"][0]
        parsed = dict(it.scene, players=players, ball={"x": bx, "y": by})
        assert offside_truth(parsed, "Blue 9")["offside"] == it.answer_value


def test_both_styles_and_image_prompt():
    it = item()
    assert "Respond with only this JSON" in text_prompt(it, "direct")
    assert "Reason step by step" in text_prompt(it, "reason")
    ip = image_prompt(it, "direct")
    assert "towards the right" in ip and " | " not in ip       # no coordinate table in image format
    with pytest.raises(ValueError):
        text_prompt(it, "chatty")


# ---------------------------------------------------------------- I/O and rendering
def test_save_load_roundtrip(tmp_path):
    it = item()
    path = save_items([it], tmp_path / "bank.jsonl")
    back = load_items(path)
    assert back[0] == it


def test_render_fixed_size(tmp_path):
    from PIL import Image
    for d in ("+x", "-x"):
        path = tmp_path / f"scene_{d}.png"
        render_scene(item(scene(d)), path)
        assert Image.open(path).size == (1050, 720)


# ---------------------------------------------------------------- real data, consistent with Phase 2
@pytest.mark.slow
def test_real_offside_items_match_phase2_labels():
    import pandas as pd
    from src.items import offside_item
    from src.moments import evaluate_moments, pass_moments

    m = "1874553"
    ev = evaluate_moments(m, pass_moments(m), question_types=("offside",))
    rel = ev[ev.offside_possible & ev.usable_offside]
    sample = pd.concat([rel[rel.offside].head(3), rel[~rel.offside].head(3)])
    for r in sample.itertuples():
        it = offside_item(m, r.frame, r.attacking_side, r.carrier_id, r.receiver_id, source="skillcorner")
        assert it is not None
        assert it.answer_value == bool(r.offside), (r.frame, it.difficulty, r.offside_margin_m)
        assert abs(it.difficulty["offside_margin_m"] - r.offside_margin_m) < 0.011   # rounding to 2 dp
        assert len(it.scene["players"]) == 22

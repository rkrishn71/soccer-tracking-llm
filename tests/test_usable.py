"""is_usable: synthetic unit tests for each question type, plus a regression on real data."""
import pandas as pd
import pytest

from src.usable import QUESTION_TYPES, is_usable, usable_report


def make_frame(players, ball=(0.0, 0.0, True)):
    """players: list of (player_id, team_side, x, y, detected) in the HOME-attacks-+x frame."""
    rows = [dict(object_type="ball", player_id=None, team_side=None,
                 x_home_m=ball[0], y_home_m=ball[1], is_detected=ball[2])]
    for pid, side, x, y, det in players:
        rows.append(dict(object_type="player", player_id=pid, team_side=side,
                         x_home_m=x, y_home_m=y, is_detected=det))
    f = pd.DataFrame(rows)
    f["is_detected"] = f.is_detected.astype("boolean")
    return f


# home attacks +x. Away defenders: GK at 50, second-last at 30, others deeper in their half.
BASE = [
    ("h9", "home", 31.0, 0.0, True),     # receiver, 1 m beyond the second-last defender
    ("h10", "home", 10.0, 5.0, True),    # passer / carrier, at the ball
    ("a1", "away", 50.0, 0.0, True),     # goalkeeper (last defender)
    ("a4", "away", 30.0, -3.0, True),    # second-last defender
    ("a5", "away", 25.0, 8.0, True),
    ("a6", "away", -20.0, 0.0, True),    # far from everything
]


def frame(changes=None, ball=(10.0, 5.0, True)):
    ps = [list(p) for p in BASE]
    for pid, det in (changes or {}).items():
        for p in ps:
            if p[0] == pid:
                p[4] = det
    return make_frame([tuple(p) for p in ps], ball=ball)


def test_unknown_type_raises():
    with pytest.raises(ValueError):
        is_usable(frame(), "not_a_type", attacking_side="home")


def test_all_types_usable_when_everyone_detected():
    for q in QUESTION_TYPES:
        assert is_usable(frame(), q, attacking_side="home", carrier_id="h10", receiver_id="h9"), q


def test_offside_needs_second_last_defender():
    assert not is_usable(frame({"a4": False}), "offside", attacking_side="home",
                         carrier_id="h10", receiver_id="h9")
    # a far-away extrapolated defender does not matter for offside
    assert is_usable(frame({"a6": False}), "offside", attacking_side="home",
                     carrier_id="h10", receiver_id="h9")


def test_offside_needs_receiver_passer_ball():
    kw = dict(attacking_side="home", carrier_id="h10", receiver_id="h9")
    assert not is_usable(frame({"h9": False}), "offside", **kw)
    assert not is_usable(frame({"h10": False}), "offside", **kw)
    assert not is_usable(frame(ball=(10.0, 5.0, False)), "offside", **kw)


def test_attacking_side_flips_defenders():
    # if AWAY attacks, home players defend; h9/h10 become defenders, a-players attackers
    r = usable_report(frame(), "offside", attacking_side="away", carrier_id="a5", receiver_id="a6")
    assert r["usable"]


def test_nearest_to_carrier_buffer():
    kw = dict(attacking_side="home", carrier_id="h10")
    # nearest to h10 (10,5) is a5 (25,8) at ~15.3 m; h9 (31,0) at ~21.6 m is outside +3 m buffer
    assert is_usable(frame({"h9": False}), "nearest_to_carrier", **kw)
    assert not is_usable(frame({"a5": False}), "nearest_to_carrier", **kw)
    assert not is_usable(frame({"h10": False}), "nearest_to_carrier", **kw)


def test_defenders_goal_side_only_near_ball_line_matters():
    kw = dict(attacking_side="home", carrier_id="h10")
    # ball x = 10; an extrapolated defender at x=-20 is 30 m from the line: still usable
    assert is_usable(frame({"a6": False}), "defenders_goal_side", **kw)
    # move ball next to a5 (x=25): a5 is now within 3 m of the line and must be detected
    assert not is_usable(frame({"a5": False}, ball=(24.0, 5.0, True)), "defenders_goal_side", **kw)


def test_overload_zone_radius():
    kw = dict(attacking_side="home", carrier_id="h10")
    # carrier at (10,5); a5 is ~15.3 m away -> within radius 15 + 3 m buffer -> must be detected
    assert not is_usable(frame({"a5": False}), "overload_zone", **kw)
    # a1 at (50,0) is 40 m away -> irrelevant
    assert is_usable(frame({"a1": False}), "overload_zone", **kw)


@pytest.mark.slow
def test_regression_offside_count_one_match():
    """Same definition as notebooks/phase2_usable.ipynb: 336 usable passes in 1874553."""
    from src.moments import evaluate_moments, pass_moments
    r = evaluate_moments("1874553", pass_moments("1874553"), question_types=("offside",))
    assert len(r) == 837
    assert int(r.usable_offside.sum()) == 336

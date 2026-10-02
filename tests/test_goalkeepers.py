"""Each team's goalkeeper is on the expected side in each period.

Expected side = the half the team DEFENDS according to the match metadata
(SkillCorner: match.json home_team_side; Metrica: data-driven directions, see CONVENTIONS.md).
Uses the median x of the GK over the whole period, in raw-orientation metres (x_m).
"""
import pytest

from src.load import load_match, load_meta
from conftest import MATCHES, ME_MATCHES


def goalkeepers(meta):
    if meta["source"] == "skillcorner":
        return {l["player_id"]: l["team_side"] for l in meta["lineups"] if l["position"] == "GK"}
    if meta["match_id"] in ("metrica_game_1", "metrica_game_2"):
        # CSV has no roles. Player11/Player25 confirmed as deepest players in tests below.
        return {"Player11": "home", "Player25": "away"}
    return {l["player_id"]: l["team_side"] for l in meta["lineups"] if l["position"] == "Goalkeeper"}


@pytest.mark.parametrize("match_id", MATCHES)
def test_goalkeeper_side(match_id):
    meta = load_meta(match_id)
    gks = goalkeepers(meta)
    assert {"home", "away"} <= set(gks.values()), f"no GK for a team: {gks}"
    df = load_match(match_id, columns=["period", "player_id", "x_m", "x_home_m"])
    df = df[df.player_id.isin(list(gks))]
    failures = []
    for (period, pid), g in df.groupby(["period", "player_id"]):
        if g.x_m.notna().sum() == 0:
            continue
        side = gks[pid]
        direction = meta["attack_direction"][str(period)][side]
        expected_sign = -1 if direction == "left_to_right" else 1  # attacking +x => defends -x
        med = g.x_m.median()
        if med * expected_sign <= 0:
            failures.append((period, pid, side, direction, round(med, 1)))
        # in the home-attacks-+x frame the home GK must be at -x, away GK at +x
        med_h = g.x_home_m.median()
        if (side == "home" and med_h >= 0) or (side == "away" and med_h <= 0):
            failures.append(("x_home_m", period, pid, side, round(med_h, 1)))
    assert not failures, failures


@pytest.mark.parametrize("match_id", ["metrica_game_1", "metrica_game_2"])
def test_metrica_player11_player25_are_deepest(match_id):
    """User requirement: Player11 / Player25 are the deepest players on their team across each full period."""
    checks = load_meta(match_id)["direction_checks"]
    for key, r in checks.items():
        expected = "Player11" if key.endswith("home") else "Player25"
        assert r["c_deepest_player"] == expected, (key, r)
        assert r["c_deepest_share"] > 0.95, (key, r)


@pytest.mark.parametrize("match_id", ME_MATCHES)
def test_metrica_direction_methods_agree(match_id):
    """Kick-off halves, shot direction and deepest-player side must all give the same direction."""
    checks = load_meta(match_id)["direction_checks"]
    for key, r in checks.items():
        d = {r["a_kickoff_direction"], r["c_deepest_direction"]}
        if r["b_shots_direction"]:
            d.add(r["b_shots_direction"])
        assert len(d) == 1, (key, r)


@pytest.mark.parametrize("match_id", ME_MATCHES)
def test_metrica_kickoff_own_half(match_id):
    """Every player in own half (1 m tolerance for the kicker on the line) at each period's kick-off.

    Known exception: Game 1 period 1 - tracking starts ~0.04 s into open play (ball already
    at (0.45, 0.39), 6 players 2.8-12.8 m over halfway). Documented in PHASE1_REPORT.md.
    The post-goal kick-off at frame 3675 of the same period is clean (checked below).
    """
    checks = load_meta(match_id)["direction_checks"]
    known = {("metrica_game_1", "1_home"), ("metrica_game_1", "1_away")}
    bad = {k: r["a_kickoff_wrong_half"] for k, r in checks.items()
           if r["a_kickoff_wrong_half"] and (match_id, k) not in known}
    assert not bad, bad


def test_metrica_game1_second_kickoff_clean():
    from src.load import get_frame
    f = get_frame("metrica_game_1", 3675)
    p = f[(f.object_type == "player") & f.x_m.notna()]
    # period 1: home attacks +x => home players x<=0, away x>=0 (1 m tolerance)
    assert (p[p.team_side == "home"].x_m <= 1.0).all()
    assert (p[p.team_side == "away"].x_m >= -1.0).all()

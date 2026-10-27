"""is_usable(frame, question_type, ...): can a Tier 1 question be asked about this frame?

A frame is usable for a question type when every player whose position decides the answer
was DETECTED (seen by the camera), not extrapolated. See DECISIONS.md D7/D9/D13.

All checks work in the "attacking frame": the attacking team (the team with the ball)
attacks towards +x, so the defending team defends the +x goal. Built from x_home_m/y_home_m:
negate both when the attacking side is "away" (same 180-degree rotation as CONVENTIONS N-1).

Usage:
    from src.load import get_frame
    from src.usable import is_usable, usable_report
    f = get_frame("1874553", 40000)
    is_usable(f, "offside", attacking_side="away", carrier_id="809759", receiver_id="26766")
    usable_report(f, "nearest_to_carrier", attacking_side="away", carrier_id="809759")
"""
from __future__ import annotations

import numpy as np
import pandas as pd

QUESTION_TYPES = ("offside", "nearest_to_carrier", "defenders_goal_side", "overload_zone")

# Buffers (metres): a player whose position would have to be wrong by LESS than this to change
# the answer is "answer-relevant" and must be detected. Players further away than the buffer
# from any decision boundary may be extrapolated. Chosen in DECISIONS.md D13.
NEAREST_BUFFER_M = 3.0        # anyone within (nearest distance + 3 m) of the carrier
GOAL_SIDE_BUFFER_M = 3.0      # any defender within 3 m (in x) of the ball's x line
OVERLOAD_RADIUS_M = 15.0      # the zone: a circle of this radius around the ball carrier
OVERLOAD_BUFFER_M = 3.0       # anyone within radius +/- 3 m of the circle edge, or inside it


def attacking_frame(frame: pd.DataFrame, attacking_side: str) -> pd.DataFrame:
    """Copy of `frame` with x_att/y_att: attacking_side ("home"/"away") attacks +x."""
    if attacking_side not in ("home", "away"):
        raise ValueError(f"attacking_side must be 'home' or 'away', got {attacking_side!r}")
    s = 1.0 if attacking_side == "home" else -1.0
    f = frame.copy()
    f["x_att"] = f["x_home_m"] * s
    f["y_att"] = f["y_home_m"] * s
    return f


def _detected(rows: pd.DataFrame) -> bool:
    """True only if there is exactly one row, it has a position, and it was detected."""
    return (len(rows) == 1 and pd.notna(rows.x_att.iloc[0])
            and bool(rows.is_detected.fillna(False).iloc[0]))


def _all_detected(rows: pd.DataFrame) -> bool:
    return bool(rows.is_detected.fillna(False).all())


def _players(f: pd.DataFrame) -> pd.DataFrame:
    # players with a position (Metrica bench rows have NaN and are not on the pitch)
    return f[(f.object_type == "player") & f.x_att.notna()]


def usable_report(frame: pd.DataFrame, question_type: str, *, attacking_side: str,
                  carrier_id: str | None = None, receiver_id: str | None = None) -> dict:
    """Per-check breakdown for one frame; `usable` is the AND of all checks."""
    if question_type not in QUESTION_TYPES:
        raise ValueError(f"unknown question_type {question_type!r}; expected one of {QUESTION_TYPES}")
    f = attacking_frame(frame, attacking_side)
    pl = _players(f)
    ball = f[f.object_type == "ball"]
    att = pl[pl.team_side == attacking_side]
    dfn = pl[pl.team_side != attacking_side]
    carrier = pl[pl.player_id == str(carrier_id)] if carrier_id is not None else pl.iloc[:0]
    r: dict = {"question_type": question_type, "tracked": len(pl) > 0, "ball": _detected(ball)}

    if question_type == "offside":
        receiver = pl[pl.player_id == str(receiver_id)] if receiver_id is not None else pl.iloc[:0]
        # defenders defend the +x goal: deepest = largest x_att; ties broken by player_id
        d = dfn.sort_values(["x_att", "player_id"], ascending=[False, True], kind="stable")
        r.update(passer=_detected(carrier), receiver=_detected(receiver),
                 second_last_def=_detected(d.iloc[1:2]))

    elif question_type == "nearest_to_carrier":
        r["carrier"] = _detected(carrier)
        others = pl[pl.player_id != str(carrier_id)]
        if len(carrier) == 1 and len(others):
            dist = np.hypot(others.x_att - carrier.x_att.iloc[0], others.y_att - carrier.y_att.iloc[0])
            relevant = others[dist <= dist.min() + NEAREST_BUFFER_M]
            r["n_relevant"] = int(len(relevant))
            r["relevant_players"] = _all_detected(relevant)
        else:
            r["relevant_players"] = False

    elif question_type == "defenders_goal_side":
        # answer = number of defending players with x_att > ball x (between ball and their goal)
        r["n_defenders"] = int(len(dfn))
        if len(ball) == 1 and pd.notna(ball.x_att.iloc[0]) and len(dfn):
            near_line = dfn[(dfn.x_att - ball.x_att.iloc[0]).abs() <= GOAL_SIDE_BUFFER_M]
            r["n_relevant"] = int(len(near_line))
            r["defenders_near_ball_line"] = _all_detected(near_line)
        else:
            r["defenders_near_ball_line"] = False

    elif question_type == "overload_zone":
        # zone = circle of OVERLOAD_RADIUS_M around the carrier; answer = attackers vs defenders inside
        r["carrier"] = _detected(carrier)
        if len(carrier) == 1:
            dist = np.hypot(pl.x_att - carrier.x_att.iloc[0], pl.y_att - carrier.y_att.iloc[0])
            relevant = pl[dist <= OVERLOAD_RADIUS_M + OVERLOAD_BUFFER_M]
            r["n_relevant"] = int(len(relevant))
            r["players_in_or_near_zone"] = _all_detected(relevant)
        else:
            r["players_in_or_near_zone"] = False

    checks = [v for k, v in r.items() if isinstance(v, bool)]
    r["usable"] = all(checks)
    return r


def is_usable(frame: pd.DataFrame, question_type: str, *, attacking_side: str,
              carrier_id: str | None = None, receiver_id: str | None = None) -> bool:
    """True if every position that decides this question's answer was detected."""
    return usable_report(frame, question_type, attacking_side=attacking_side,
                         carrier_id=carrier_id, receiver_id=receiver_id)["usable"]

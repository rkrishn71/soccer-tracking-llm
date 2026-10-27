"""Candidate moments for Tier 1 questions: one row per pass, from both sources.

A "moment" = the frame a pass is played. The passer is the ball carrier; the intended receiver
is the pass target. Every Tier 1 question type is anchored to these moments (DECISIONS D9/D13).

    from src.moments import pass_moments, evaluate_moments
    m = pass_moments("1874553")             # or "metrica_game_1"
    ev = evaluate_moments("1874553", m)     # adds usable_<type> columns + offside geometry
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import skillcorner
from .config import METRICA_DIR
from .load import load_match, load_meta
from .usable import QUESTION_TYPES, attacking_frame, usable_report

SC_RESTART_TAKER = {"throw_in_for", "goal_kick_for", "corner_for"}     # offside doesn't apply
ME_RESTART_SUBTYPES = {"THROW IN", "CORNER KICK", "GOAL KICK"}


def _skillcorner_moments(match_id: str) -> pd.DataFrame:
    home_id = load_meta(match_id)["teams"]["home"]["team_id"]
    ev = skillcorner.load_dynamic_events(match_id)
    p = ev[(ev.event_type == "player_possession") & (ev.end_type == "pass")]
    return pd.DataFrame({
        "match": match_id, "source": "skillcorner",
        "event_id": p.event_id.astype(str).values,
        "frame": p.frame_end.astype(int).values,
        "period": p.period.astype(int).values,
        "attacking_side": np.where(p.team_id.astype(str) == home_id, "home", "away"),
        "carrier_id": p.player_id.astype("Int64").astype(str).values,
        "receiver_id": p.player_targeted_id.astype("Int64").astype(str).replace("<NA>", None).values,
        "restart": ((p.start_type == "unknown") & p.game_interruption_before.isin(SC_RESTART_TAKER)).values,
    })


def _metrica_moments(match_id: str) -> pd.DataFrame:
    game = int(match_id.rsplit("_", 1)[1])
    gdir = METRICA_DIR / f"Sample_Game_{game}"
    if game in (1, 2):
        ev = pd.read_csv(gdir / f"Sample_Game_{game}_RawEventsData.csv").rename(columns={
            "Type": "type", "Subtype": "subtype", "Start Frame": "frame", "Period": "period",
            "From": "passer", "To": "receiver", "Team": "team"})
        ev["team_side"] = ev.team.str.lower()
    else:
        home_id = load_meta(match_id)["teams"]["home"]["team_id"]
        rows = []
        for e in json.loads((gdir / f"Sample_Game_{game}_events.json").read_text())["data"]:
            st = e.get("subtypes") or []
            st = [st] if isinstance(st, dict) else st
            rows.append(dict(type=e["type"]["name"], subtype=",".join(s["name"] for s in st),
                             frame=e["start"]["frame"], period=e["period"],
                             passer=(e.get("from") or {}).get("id"), receiver=(e.get("to") or {}).get("id"),
                             team_side="home" if e["team"]["id"] == home_id else "away"))
        ev = pd.DataFrame(rows)
    ev["subtype"] = ev.subtype.fillna("")
    sp = ev[(ev.type == "SET PIECE") & ev.subtype.isin(ME_RESTART_SUBTYPES)]
    keys = set(zip(sp.frame, sp.passer))
    p = ev[ev.type == "PASS"].reset_index(drop=True)
    return pd.DataFrame({
        "match": match_id, "source": "metrica",
        "event_id": [f"{match_id}_{i}" for i in p.index],
        "frame": p.frame.astype(int).values, "period": p.period.astype(int).values,
        "attacking_side": p.team_side.values,
        "carrier_id": p.passer.values, "receiver_id": p.receiver.where(p.receiver.notna(), None).values,
        "restart": [((f, a) in keys) or ("GOAL KICK" in s) for f, a, s in zip(p.frame, p.passer, p.subtype)],
    })


def pass_moments(match_id: str) -> pd.DataFrame:
    match_id = str(match_id)
    return _metrica_moments(match_id) if match_id.startswith("metrica_") else _skillcorner_moments(match_id)


def evaluate_moments(match_id: str, moments: pd.DataFrame,
                     question_types=QUESTION_TYPES) -> pd.DataFrame:
    """Add usable_<type> for each question type, plus offside geometry (attacking frame)."""
    cols = ["frame_id", "object_type", "player_id", "team_side", "x_home_m", "y_home_m", "is_detected"]
    df = load_match(str(match_id), columns=cols)
    frames = dict(tuple(df[df.frame_id.isin(moments.frame)].groupby("frame_id")))
    out = []
    for m in moments.itertuples():
        f = frames.get(m.frame)
        row = {}
        for q in question_types:
            if f is None:
                row[f"usable_{q}"] = False
                continue
            rep = usable_report(f, q, attacking_side=m.attacking_side,
                                carrier_id=m.carrier_id, receiver_id=m.receiver_id)
            row[f"usable_{q}"] = rep["usable"]
        # offside geometry (attacking frame): receiver, ball, second-last defender x
        if f is not None:
            a = attacking_frame(f, m.attacking_side)
            pl = a[(a.object_type == "player") & a.x_att.notna()]
            rec = pl[pl.player_id == str(m.receiver_id)]
            ball = a[a.object_type == "ball"]
            d = pl[pl.team_side != m.attacking_side].sort_values(
                ["x_att", "player_id"], ascending=[False, True], kind="stable")
            row["x_receiver"] = rec.x_att.iloc[0] if len(rec) == 1 else np.nan
            row["x_ball"] = ball.x_att.iloc[0] if len(ball) == 1 else np.nan
            row["x_second_last"] = d.x_att.iloc[1] if len(d) > 1 else np.nan
        out.append(row)
    res = pd.concat([moments.reset_index(drop=True), pd.DataFrame(out)], axis=1)
    res["offside_possible"] = (~res.restart) & (res.x_receiver > 0) & (res.x_receiver > res.x_ball)
    res["offside"] = res.offside_possible & (res.x_receiver > res.x_second_last)
    res["offside_margin_m"] = res.x_receiver - res.x_second_last
    return res


def _evaluate_one(match_id: str) -> pd.DataFrame:
    return evaluate_moments(match_id, pass_moments(match_id))


def evaluate_all(match_ids, workers: int = 4) -> pd.DataFrame:
    """evaluate_moments for many matches in parallel (one process per match)."""
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(workers) as ex:
        parts = list(ex.map(_evaluate_one, [str(m) for m in match_ids]))
    return pd.concat(parts, ignore_index=True)

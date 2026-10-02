"""SkillCorner open data (A-League 2024/25, current master) -> common frame schema."""
import json

import numpy as np
import orjson
import pandas as pd

from .config import SKILLCORNER_DIR, SKILLCORNER_FPS, SKILLCORNER_MATCHES_JSON
from .normalize import add_normalized_columns, finalize_schema

SOURCE = "skillcorner"


def list_match_ids() -> list[str]:
    return sorted(p.name for p in SKILLCORNER_DIR.iterdir() if p.is_dir())


def _paths(match_id: str):
    d = SKILLCORNER_DIR / match_id
    return {
        "match": d / f"{match_id}_match.json",
        "tracking": d / f"{match_id}_tracking_extrapolated.jsonl",
        "events": d / f"{match_id}_dynamic_events.csv",
        "phases": d / f"{match_id}_phases_of_play.csv",
    }


def _parse_timestamp(ts):
    """'HH:MM:SS.ss' match clock -> seconds (period 2 starts at 45:00 in the raw data)."""
    if ts is None:
        return np.nan
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)  # [U-TS] string clock -> float seconds


def status_from_matches_json(match_id: str):
    for m in json.loads(SKILLCORNER_MATCHES_JSON.read_text()):
        if str(m["id"]) == str(match_id):
            return m.get("status")
    return None


def build_metadata(match_id: str) -> dict:
    m = json.loads(_paths(match_id)["match"].read_text())
    home, away = m["home_team"], m["away_team"]
    side_of_team = {home["id"]: "home", away["id"]: "away"}
    periods = [{"period": p["period"], "start_frame": p["start_frame"], "end_frame": p["end_frame"]}
               for p in m["match_periods"]]
    # home_team_side[i] is the direction the HOME team attacks in period i+1
    # (verified against goalkeeper positions for all 20 matches; see tests/test_goalkeepers.py)
    attack = {}
    for i, d in enumerate(m["home_team_side"]):
        other = "right_to_left" if d == "left_to_right" else "left_to_right"
        attack[str(i + 1)] = {"home": d, "away": other,
                              "home_attacks_plus_x": d == "left_to_right"}  # [A-SC] left_to_right == +x

    lineup, ons, offs = [], [], []
    match_end = max(p["end_frame"] for p in periods)
    first_start = min(p["start_frame"] for p in periods)
    for p in m["players"]:
        pt = p.get("playing_time") or {}
        tot = pt.get("total") or {}
        started = p.get("start_time") == "00:00:00"
        entry = {
            "player_id": str(p["id"]),
            "trackable_object": p.get("trackable_object"),
            "team_id": str(p["team_id"]),
            "team_side": side_of_team[p["team_id"]],
            "name": p.get("short_name"),
            "jersey_number": p.get("number"),
            "position": p["player_role"]["acronym"],
            "position_name": p["player_role"]["name"],
            "starter": started,
            "start_time": p.get("start_time"),
            "end_time": p.get("end_time"),
            "start_frame": tot.get("start_frame"),
            "end_frame": tot.get("end_frame"),
            "sequences": pt.get("sequences"),
            "red_card": p.get("red_card"),
            "yellow_card": p.get("yellow_card"),
        }
        lineup.append(entry)
        if entry["start_frame"] is not None and not started:
            ons.append(entry)
        if entry["end_frame"] is not None and p.get("end_time") is not None:
            offs.append(entry)
    subs = []
    used_off = set()
    for on in sorted(ons, key=lambda e: e["start_frame"]):
        match_off = [o for o in offs if o["team_id"] == on["team_id"] and o["player_id"] not in used_off
                     and abs(o["end_frame"] - on["start_frame"]) <= SKILLCORNER_FPS * 5]
        off = match_off[0] if match_off else None
        if off:
            used_off.add(off["player_id"])
        subs.append({"team_id": on["team_id"], "team_side": on["team_side"], "frame": on["start_frame"],
                     "player_in": on["player_id"], "player_out": off["player_id"] if off else None})
    for o in offs:
        if o["player_id"] not in used_off and o["end_frame"] < match_end - SKILLCORNER_FPS:
            subs.append({"team_id": o["team_id"], "team_side": o["team_side"], "frame": o["end_frame"],
                         "player_in": None, "player_out": o["player_id"],
                         "note": "left without paired replacement (red card / injury / unpaired)"})

    status_match_json = m.get("status")
    status_list = status_from_matches_json(match_id)
    status_conflict = (status_match_json != "closed") or (status_list != "closed")
    return {
        "match_id": str(match_id),
        "source": SOURCE,
        "competition": m["competition_edition"]["name"],
        "date_time": m["date_time"],
        "status_match_json": status_match_json,
        "status_matches_list": status_list,
        "status_conflict": bool(status_conflict),
        "pitch_length_m": float(m["pitch_length"]),
        "pitch_width_m": float(m["pitch_width"]),
        "frame_rate_hz": SKILLCORNER_FPS,
        "coordinate_system": "meters, origin pitch centre, x along length, y across width (+y up per SkillCorner field.jpg)",
        "teams": {
            "home": {"team_id": str(home["id"]), "name": home["name"], "short_name": home["short_name"]},
            "away": {"team_id": str(away["id"]), "name": away["name"], "short_name": away["short_name"]},
        },
        "score": {"home": m["home_team_score"], "away": m["away_team_score"]},
        "periods": periods,
        "attack_direction": attack,
        "lineups": lineup,
        "substitutions": sorted(subs, key=lambda s: s["frame"]),
        "ball_trackable_object": m["ball"]["trackable_object"],
        "first_period_start_frame": first_start,
    }


def build_frames(match_id: str, meta: dict | None = None) -> pd.DataFrame:
    meta = meta or build_metadata(match_id)
    players = {p["player_id"]: p for p in meta["lineups"]}
    team_side = {meta["teams"]["home"]["team_id"]: "home", meta["teams"]["away"]["team_id"]: "away"}

    cols = {k: [] for k in ["period", "frame_id", "timestamp_s", "object_type", "player_id",
                            "x_raw", "y_raw", "is_detected", "ball_z",
                            "possession_group", "possession_player_id"]}
    with open(_paths(match_id)["tracking"], "rb") as f:
        for line in f:
            r = orjson.loads(line)
            period = r["period"]
            if period is None:
                # Pre-match / half-time / post-match frames. Checked: they carry no player
                # or ball data at all, so there are no object rows to keep.
                assert not r["player_data"] and r["ball_data"]["x"] is None, (match_id, r["frame"])
                continue
            fr = r["frame"]
            ts = _parse_timestamp(r["timestamp"])
            pg = r["possession"]["group"]
            pp = r["possession"]["player_id"]
            pp = None if pp is None else str(pp)
            b = r["ball_data"]
            # ball row is always emitted for an in-period frame, even when position is null
            cols["period"].append(period); cols["frame_id"].append(fr); cols["timestamp_s"].append(ts)
            cols["object_type"].append("ball"); cols["player_id"].append(None)
            cols["x_raw"].append(b["x"]); cols["y_raw"].append(b["y"])
            cols["is_detected"].append(b["is_detected"]); cols["ball_z"].append(b["z"])
            cols["possession_group"].append(pg); cols["possession_player_id"].append(pp)
            for p in r["player_data"]:
                cols["period"].append(period); cols["frame_id"].append(fr); cols["timestamp_s"].append(ts)
                cols["object_type"].append("player"); cols["player_id"].append(str(p["player_id"]))
                cols["x_raw"].append(p["x"]); cols["y_raw"].append(p["y"])
                cols["is_detected"].append(p["is_detected"]); cols["ball_z"].append(None)
                cols["possession_group"].append(pg); cols["possession_player_id"].append(pp)

    df = pd.DataFrame(cols)
    df["x_raw"] = df["x_raw"].astype("float64")
    df["y_raw"] = df["y_raw"].astype("float64")
    df["ball_z"] = df["ball_z"].astype("float64")
    # [T-SC] SkillCorner is already metres, centre origin, x long axis, +y up: identity transform
    df["x_m"] = df["x_raw"]
    df["y_m"] = df["y_raw"]
    df["is_detected"] = df["is_detected"].astype("boolean")  # raw flag; null kept as <NA> (ball not found)

    df["match_id"] = str(match_id)
    df["source"] = SOURCE
    pid = df["player_id"]
    df["team_id"] = pid.map(lambda i: players[i]["team_id"] if i in players else None)
    df["team_side"] = df["team_id"].map(team_side)
    df["jersey_number"] = pid.map(lambda i: players[i]["jersey_number"] if i in players else None)
    df["position"] = pid.map(lambda i: players[i]["position"] if i in players else None)
    df["status_conflict"] = meta["status_conflict"]

    home_plus_x = {int(k): v["home_attacks_plus_x"] for k, v in meta["attack_direction"].items()}
    df = add_normalized_columns(df, home_plus_x)
    return finalize_schema(df)


def load_dynamic_events(match_id: str) -> pd.DataFrame:
    return pd.read_csv(_paths(match_id)["events"], low_memory=False)


def load_phases(match_id: str) -> pd.DataFrame:
    return pd.read_csv(_paths(match_id)["phases"])

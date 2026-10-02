"""Metrica Sports sample data (Games 1-3) -> common frame schema.

Conventions confirmed from the repo (README.md and Sample_Game_3_metadata.xml):
  * coordinates normalised 0..1 on each axis; (0,0) = TOP-LEFT, (1,1) = bottom-right,
    (0.5,0.5) = kick-off spot  -> y grows DOWNWARDS
  * pitch 105 x 68 m for all games
  * 25 fps (metadata FrameRate=25; CSV 'Time [s]' == Frame * 0.04 exactly)
  * NaN position = player not on the pitch (bench / subbed off / sent off)
"""
import json
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

from .config import METRICA_CSV_PITCH, METRICA_DIR, METRICA_FPS
from .normalize import add_normalized_columns, finalize_schema

SOURCE = "metrica"


def match_id_for(game: int) -> str:
    return f"metrica_game_{game}"


def game_from_match_id(match_id: str) -> int:
    return int(str(match_id).rsplit("_", 1)[1])


def list_match_ids() -> list[str]:
    return [match_id_for(g) for g in (1, 2, 3)]


def _gdir(game):
    return METRICA_DIR / f"Sample_Game_{game}"


# ----------------------------------------------------------------------------- raw readers
def read_csv_team(game: int, team: str) -> tuple[pd.DataFrame, dict]:
    """Read Sample_Game_{1,2}_RawTrackingData_{Home,Away}_Team.csv.

    Returns (wide frame df, {player_col: jersey_number}). Header rows: 0 team, 1 jersey, 2 names.
    """
    f = _gdir(game) / f"Sample_Game_{game}_RawTrackingData_{team}_Team.csv"
    hdr = pd.read_csv(f, header=None, nrows=3)
    names = hdr.iloc[2].tolist()
    jerseys = hdr.iloc[1].tolist()
    cols, jersey_of = [], {}
    for i, n in enumerate(names):
        if isinstance(n, str) and (n.startswith("Player") or n == "Ball"):
            cols += [f"{n}_x", f"{n}_y"]
            if n != "Ball":
                jersey_of[n] = int(float(jerseys[i]))
        elif isinstance(n, str):
            cols.append(n)
    df = pd.read_csv(f, skiprows=3, header=None, names=cols)
    return df, jersey_of


def read_csv_events(game: int) -> pd.DataFrame:
    return pd.read_csv(_gdir(game) / f"Sample_Game_{game}_RawEventsData.csv")


def read_epts_metadata(game: int = 3) -> dict:
    root = ET.parse(_gdir(game) / f"Sample_Game_{game}_metadata.xml").getroot()
    md = root.find("Metadata")
    gc = md.find("GlobalConfig")
    params = {p.find("Name").text: p.find("Value").text
              for p in gc.find("ProviderGlobalParameters").findall("ProviderParameter")}
    sess = md.find("Sessions").find("Session")
    fs = sess.find("FieldSize")
    score = sess.find("MatchParameters").find("Score")
    teams = {}
    for t in md.find("Teams").findall("Team"):
        tp = {p.find("Name").text: p.find("Value").text
              for p in t.find("ProviderTeamsParameters").findall("ProviderParameter")}
        teams[t.get("id")] = {"name": t.find("Name").text,
                              "attack_direction_first_half": tp.get("attack_direction_first_half")}
    players = {}
    for p in md.find("Players").findall("Player"):
        pp = {q.find("Name").text: q.find("Value").text
              for q in p.find("ProviderPlayerParameters").findall("ProviderParameter")}
        players[p.get("id")] = {"team_id": p.get("teamId"), "name": p.find("Name").text,
                                "jersey_number": int(p.find("ShirtNumber").text),
                                "position": pp.get("position_type")}
    channels = {}
    for c in root.iter("PlayerChannel"):
        channels[c.get("id")] = (c.get("playerId"), c.get("channelId"))
    specs = []
    for s in root.iter("DataFormatSpecification"):
        refs = [r.get("playerChannelId") for r in s.iter("PlayerChannelRef")]
        order = []
        for r in refs[::2]:
            order.append(channels[r][0])
        specs.append({"start": int(s.get("startFrame")), "end": int(s.get("endFrame")), "players": order})
    return {
        "frame_rate": int(gc.find("FrameRate").text),
        "periods": {1: (int(params["first_half_start"]), int(params["first_half_end"])),
                    2: (int(params["second_half_start"]), int(params["second_half_end"]))},
        "pitch": (float(fs.find("Width").text), float(fs.find("Height").text)),
        "home_team_id": score.get("idLocalTeam"), "away_team_id": score.get("idVisitingTeam"),
        "teams": teams, "players": players, "specs": specs,
    }


def read_epts_tracking(game: int = 3, md: dict | None = None) -> pd.DataFrame:
    """Parse Sample_Game_3_tracking.txt using the DataFormatSpecifications in the metadata.

    Line format: 'frame:p1x,p1y;p2x,p2y;...;p22x,p22y:ballx,bally'. Which player is in which
    slot changes between the 11 specification blocks (substitutions).
    Returns long df: frame_id, player_id (None for ball), x_raw, y_raw.
    """
    md = md or read_epts_metadata(game)
    fr_l, pid_l, x_l, y_l = [], [], [], []
    spec_i = 0
    specs = md["specs"]
    with open(_gdir(game) / f"Sample_Game_{game}_tracking.txt") as f:
        for line in f:
            frame_s, pl_s, ball_s = line.rstrip("\n").split(":")
            fr = int(frame_s)
            while not (specs[spec_i]["start"] <= fr <= specs[spec_i]["end"]):
                spec_i += 1
            order = specs[spec_i]["players"]
            pts = pl_s.split(";")
            assert len(pts) == len(order), (fr, len(pts), len(order))
            for pid, pt in zip(order, pts):
                xs, ys = pt.split(",")
                fr_l.append(fr); pid_l.append(pid); x_l.append(float(xs)); y_l.append(float(ys))
            bx, by = ball_s.split(",")
            fr_l.append(fr); pid_l.append(None); x_l.append(float(bx)); y_l.append(float(by))
    return pd.DataFrame({"frame_id": fr_l, "player_id": pid_l, "x_raw": x_l, "y_raw": y_l})


def read_epts_events(game: int = 3) -> pd.DataFrame:
    d = json.loads((_gdir(game) / f"Sample_Game_{game}_events.json").read_text())["data"]
    rows = []
    for e in d:
        st = e.get("subtypes") or []
        if isinstance(st, dict):  # a single subtype is stored as an object, several as a list
            st = [st]
        rows.append({"team_id": e["team"]["id"], "type": e["type"]["name"],
                     "subtypes": ",".join(s["name"] for s in st),
                     "period": e["period"], "start_frame": e["start"]["frame"],
                     "start_x": e["start"]["x"], "end_x": (e.get("end") or {}).get("x"),
                     "from": (e.get("from") or {}).get("id")})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- long format
def load_long_raw(game: int):
    """Return (long df with period/frame_id/team_side/player_id/x_raw/y_raw, info dict)."""
    if game in (1, 2):
        parts = []
        jersey = {}
        for team, side in (("Home", "home"), ("Away", "away")):
            wide, j = read_csv_team(game, team)
            jersey.update(j)
            pcols = [c[:-2] for c in wide.columns if c.endswith("_x") and c.startswith("Player")]
            for p in pcols:
                parts.append(pd.DataFrame({
                    "period": wide["Period"].values, "frame_id": wide["Frame"].values,
                    "timestamp_s": wide["Time [s]"].values,
                    "object_type": "player", "player_id": p, "team_id": team, "team_side": side,
                    "x_raw": wide[f"{p}_x"].values, "y_raw": wide[f"{p}_y"].values}))
            if team == "Home":  # Ball columns are identical in both team files (verified)
                parts.append(pd.DataFrame({
                    "period": wide["Period"].values, "frame_id": wide["Frame"].values,
                    "timestamp_s": wide["Time [s]"].values, "object_type": "ball", "player_id": None,
                    "team_id": None, "team_side": None,
                    "x_raw": wide["Ball_x"].values, "y_raw": wide["Ball_y"].values}))
        df = pd.concat(parts, ignore_index=True)
        df["jersey_number"] = df["player_id"].map(jersey)
        df["position"] = None  # CSV format carries no positions
        info = {"pitch": METRICA_CSV_PITCH, "fps": METRICA_FPS,
                "teams": {"home": {"team_id": "Home", "name": "Home"},
                          "away": {"team_id": "Away", "name": "Away"}},
                "player_names": {p: p for p in jersey}, "jersey": jersey}
        return df, info

    md = read_epts_metadata(game)
    assert md["frame_rate"] == METRICA_FPS
    long = read_epts_tracking(game, md)
    (s1, e1), (s2, e2) = md["periods"][1], md["periods"][2]
    long["period"] = np.where(long["frame_id"] <= e1, 1, 2)
    assert long["frame_id"].between(s1, e2).all()
    # [U-TS3] EPTS has no time column: timestamp = frame / 25, same convention as CSV (Time = Frame*0.04)
    long["timestamp_s"] = long["frame_id"] / md["frame_rate"]
    pl = md["players"]
    side_of = {md["home_team_id"]: "home", md["away_team_id"]: "away"}
    long["object_type"] = np.where(long["player_id"].isna(), "ball", "player")
    long["team_id"] = long["player_id"].map(lambda p: pl[p]["team_id"] if p in pl else None)
    long["team_side"] = long["team_id"].map(side_of)
    long["jersey_number"] = long["player_id"].map(lambda p: pl[p]["jersey_number"] if p in pl else None)
    long["position"] = long["player_id"].map(lambda p: pl[p]["position"] if p in pl else None)
    info = {"pitch": md["pitch"], "fps": md["frame_rate"],
            "teams": {"home": {"team_id": md["home_team_id"], "name": md["teams"][md["home_team_id"]]["name"]},
                      "away": {"team_id": md["away_team_id"], "name": md["teams"][md["away_team_id"]]["name"]}},
            "player_names": {k: v["name"] for k, v in pl.items()},
            "jersey": {k: v["jersey_number"] for k, v in pl.items()},
            "positions": {k: v["position"] for k, v in pl.items()},
            "epts": md}
    return long, info


# ----------------------------------------------------------------------------- directions
def kickoff_frames(game: int) -> dict:
    """First KICK OFF event frame of each period (from the event file)."""
    if game in (1, 2):
        ev = read_csv_events(game)
        ko = ev[ev["Subtype"] == "KICK OFF"]
        return {int(p): int(g["Start Frame"].min()) for p, g in ko.groupby("Period")}
    ev = read_epts_events(game)
    ko = ev[(ev["type"] == "SET PIECE") & ev["subtypes"].str.contains("KICK OFF")]
    return {int(p): int(g["start_frame"].min()) for p, g in ko.groupby("period")}


def direction_checks(game: int, long: pd.DataFrame | None = None, kickoff_tol_m: float = 1.0) -> dict:
    """Three independent estimates of each team's attack direction per period (raw 0..1 x axis).

    (a) kick-off: team's mean x at the period's first KICK OFF event frame -> own half;
        also reports players on the wrong side of halfway beyond kickoff_tol_m.
    (b) shots: mean sign of (end_x - start_x) for that team's SHOT events in the period.
    (c) deepest player: which player is closest to the team's own goal (per (a)) in the most
        frames of the full period; expected Player11 (home) / Player25 (away) for Games 1-2.
    Direction strings: 'left_to_right' = attacking towards raw x=1 = +x in metres.
    """
    if long is None:
        long, _ = load_long_raw(game)
    L = METRICA_CSV_PITCH[0]
    ko = kickoff_frames(game)
    if game in (1, 2):
        ev = read_csv_events(game).rename(columns={"Team": "team", "Period": "period",
                                                  "Start X": "start_x", "End X": "end_x", "Type": "type"})
        ev["team_side"] = ev["team"].str.lower()
    else:
        ev = read_epts_events(game)
        md = read_epts_metadata(game)
        ev["team_side"] = ev["team_id"].map({md["home_team_id"]: "home", md["away_team_id"]: "away"})
    pl = long[long.object_type == "player"]
    out = {}
    for period in (1, 2):
        pdat = pl[pl.period == period]
        kof = ko[period]
        at_ko = pdat[(pdat.frame_id == kof) & pdat.x_raw.notna()]
        for side in ("home", "away"):
            res = {}
            t_ko = at_ko[at_ko.team_side == side]
            own_left = t_ko.x_raw.mean() < 0.5
            res["kickoff_frame"] = kof
            res["a_kickoff_direction"] = "left_to_right" if own_left else "right_to_left"
            over = ((t_ko.x_raw - 0.5) if own_left else (0.5 - t_ko.x_raw)) * L
            res["a_kickoff_n_players"] = int(len(t_ko))
            res["a_kickoff_wrong_half"] = {r.player_id: round(float(o), 2)
                                           for r, o in zip(t_ko.itertuples(), over) if o > kickoff_tol_m}
            s = ev[(ev["type"] == "SHOT") & (ev.team_side == side) & (ev.period == period)]
            n_right = int((s.end_x > s.start_x).sum())
            res["b_shots_n"] = int(len(s)); res["b_shots_towards_right"] = n_right
            res["b_shots_direction"] = (None if len(s) == 0 else
                                        "left_to_right" if n_right > len(s) / 2 else "right_to_left")
            # (c) deepest player across full period
            t = pdat[(pdat.team_side == side) & pdat.x_raw.notna()].copy()
            t["depth"] = t.x_raw if own_left else -t.x_raw
            idx = t.groupby("frame_id")["depth"].idxmin()
            deepest = t.loc[idx, "player_id"].value_counts(normalize=True)
            res["c_deepest_player"] = str(deepest.index[0])
            res["c_deepest_share"] = round(float(deepest.iloc[0]), 4)
            gk_mean_x = t[t.player_id == deepest.index[0]].x_raw.mean()
            res["c_deepest_direction"] = "left_to_right" if gk_mean_x < 0.5 else "right_to_left"
            out[f"{period}_{side}"] = res
    return out


def resolve_directions(game: int, long: pd.DataFrame, info: dict) -> tuple[dict, dict]:
    """Return ({period: home_attacks_plus_x}, check details). Raises on any conflict."""
    checks = direction_checks(game, long)
    dirs = {}
    for key, r in checks.items():
        methods = [r["a_kickoff_direction"], r["c_deepest_direction"]]
        if r["b_shots_direction"] is not None:
            methods.append(r["b_shots_direction"])
        if len(set(methods)) != 1:
            raise RuntimeError(f"Metrica game {game} {key}: direction methods disagree: {r}")
        dirs[key] = methods[0]
    if game == 3:  # metadata states first-half direction; must agree with the data-driven checks
        md = info["epts"]
        for tid, t in md["teams"].items():
            side = "home" if tid == md["home_team_id"] else "away"
            if t["attack_direction_first_half"] != dirs[f"1_{side}"]:
                raise RuntimeError(f"Game 3 metadata direction disagrees with data for {side}")
    for p in (1, 2):
        if dirs[f"{p}_home"] == dirs[f"{p}_away"]:
            raise RuntimeError(f"game {game} period {p}: both teams attack the same way")
    home_plus_x = {p: dirs[f"{p}_home"] == "left_to_right" for p in (1, 2)}  # [A-ME] raw x->1 == +x
    return home_plus_x, checks


# ----------------------------------------------------------------------------- build
def _lineups_from_data(long, info, match_id, team_ids):
    pl = long[(long.object_type == "player") & long.x_raw.notna()]
    first_frame = long.frame_id.min()
    g = pl.groupby("player_id").agg(start_frame=("frame_id", "min"), end_frame=("frame_id", "max"),
                                    team_side=("team_side", "first"), team_id=("team_id", "first"))
    last_frame = long.frame_id.max()
    lineups = []
    for pid, r in g.iterrows():
        lineups.append({"player_id": pid, "team_id": r.team_id, "team_side": r.team_side,
                        "name": info["player_names"].get(pid, pid),
                        "jersey_number": info["jersey"].get(pid),
                        "position": (info.get("positions") or {}).get(pid),
                        "starter": bool(r.start_frame == first_frame),
                        "start_frame": int(r.start_frame), "end_frame": int(r.end_frame),
                        "times_source": "derived: first/last frame with a non-NaN position"})
    all_players = long[long.object_type == "player"].player_id.unique()
    for pid in sorted(set(all_players) - set(g.index)):
        t = long[long.player_id == pid].iloc[0]
        lineups.append({"player_id": pid, "team_id": t.team_id, "team_side": t.team_side,
                        "name": info["player_names"].get(pid, pid),
                        "jersey_number": info["jersey"].get(pid), "position": (info.get("positions") or {}).get(pid),
                        "starter": False, "start_frame": None, "end_frame": None,
                        "times_source": "never on pitch (all NaN)"})
    ons = [l for l in lineups if l["start_frame"] is not None and not l["starter"]]
    offs = [l for l in lineups if l["end_frame"] is not None and l["end_frame"] < last_frame]
    subs, used = [], set()
    for on in sorted(ons, key=lambda l: l["start_frame"]):
        cand = [o for o in offs if o["team_side"] == on["team_side"] and o["player_id"] not in used
                and abs(o["end_frame"] - on["start_frame"]) <= METRICA_FPS * 60]
        cand.sort(key=lambda o: abs(o["end_frame"] - on["start_frame"]))
        off = cand[0] if cand else None
        if off:
            used.add(off["player_id"])
        subs.append({"team_id": on["team_id"], "team_side": on["team_side"], "frame": on["start_frame"],
                     "player_in": on["player_id"], "player_out": off["player_id"] if off else None,
                     "source": "derived from tracking NaN pattern"})
    for o in offs:
        if o["player_id"] not in used:
            subs.append({"team_id": o["team_id"], "team_side": o["team_side"], "frame": o["end_frame"],
                         "player_in": None, "player_out": o["player_id"],
                         "source": "derived; no replacement found (red card / injury / tracking gap)"})
    return lineups, sorted(subs, key=lambda s: s["frame"])


def build(game: int):
    """Return (frames df in common schema, metadata dict)."""
    match_id = match_id_for(game)
    long, info = load_long_raw(game)
    L, W = info["pitch"]
    home_plus_x, checks = resolve_directions(game, long, info)

    # [T-ME-X] x: 0..1 from the left goal line -> metres, centre origin (no sign flip)
    long["x_m"] = (long["x_raw"] - 0.5) * L
    # [T-ME-Y] y: 0..1 with 0 at TOP -> flip sign so +y is up (matches SkillCorner), centre origin
    long["y_m"] = -(long["y_raw"] - 0.5) * W
    # [F-ME-DET] Metrica has no detection flag: position present <=> on pitch / detected
    long["is_detected"] = long["x_raw"].notna() & long["y_raw"].notna()
    long["ball_z"] = np.nan  # not provided by Metrica
    long["possession_group"] = None  # no per-frame possession in Metrica tracking
    long["possession_player_id"] = None
    long["match_id"] = match_id
    long["source"] = SOURCE
    long["status_conflict"] = False
    long = add_normalized_columns(long, home_plus_x)
    df = finalize_schema(long)

    teams = info["teams"]
    team_ids = {teams["home"]["team_id"]: "home", teams["away"]["team_id"]: "away"}
    lineups, subs = _lineups_from_data(long, info, match_id, team_ids)
    periods = [{"period": int(p), "start_frame": int(g.frame_id.min()), "end_frame": int(g.frame_id.max())}
               for p, g in long.groupby("period")]
    attack = {}
    for p in (1, 2):
        h = "left_to_right" if home_plus_x[p] else "right_to_left"
        a = "right_to_left" if home_plus_x[p] else "left_to_right"
        attack[str(p)] = {"home": h, "away": a, "home_attacks_plus_x": home_plus_x[p]}
    meta = {
        "match_id": match_id, "source": SOURCE, "format": "csv" if game in (1, 2) else "fifa_epts",
        "status_conflict": False,
        "pitch_length_m": float(L), "pitch_width_m": float(W),
        "pitch_source": "README (105x68 for all games)" if game in (1, 2) else "metadata.xml FieldSize",
        "frame_rate_hz": info["fps"],
        "coordinate_system_raw": "normalised 0..1, (0,0) top-left, (1,1) bottom-right, (0.5,0.5) kick-off spot",
        "teams": teams,
        "periods": periods,
        "attack_direction": attack,
        "attack_direction_method": ("data-driven: kick-off halves, shot direction and deepest player agree"
                                    + ("; also matches metadata attack_direction_first_half" if game == 3 else "")),
        "direction_checks": checks,
        "lineups": lineups,
        "substitutions": subs,
        "notes": ["Anonymised data: no real player/team names.",
                  "No per-frame possession in Metrica tracking: x_att_m/y_att_m are NaN for all rows."],
    }
    return df, meta

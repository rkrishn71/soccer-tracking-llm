"""Shared normalisation: home-attacks-+x and possession-attacks-+x coordinate sets.

Both sets are a 180-degree ROTATION about the pitch centre (x -> -x AND y -> -y),
not a mirror. With y pointing "up" in the source frame, a team attacking +x has
its left-hand side at +y; rotating keeps that true after normalisation, so
+y is always the attacking team's left. A mirror (x only) would swap wings.
"""
import numpy as np
import pandas as pd

from .config import SCHEMA_COLUMNS


def add_normalized_columns(df: pd.DataFrame, home_attacks_plus_x: dict) -> pd.DataFrame:
    """Add x_home_m/y_home_m and x_att_m/y_att_m.

    home_attacks_plus_x: {period: bool} - True if the HOME team attacks towards +x
    in that period in the (x_m, y_m) frame.
    """
    sign_home = df["period"].map(lambda p: 1.0 if home_attacks_plus_x[int(p)] else -1.0)
    # [T-HOME] rotate 180 deg when home attacks -x so home always attacks +x
    df["x_home_m"] = df["x_m"] * sign_home
    df["y_home_m"] = df["y_m"] * sign_home

    # [T-ATT] possession-based set: +1 if home in possession, -1 if away, NaN if no/unknown possession
    poss_sign = df["possession_group"].map({"home team": 1.0, "away team": -1.0}).astype("float64")
    df["x_att_m"] = df["x_home_m"] * poss_sign  # NaN where possession is empty (never filled / carried)
    df["y_att_m"] = df["y_home_m"] * poss_sign
    return df


def finalize_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Order columns and set dtypes of the common schema."""
    df = df[SCHEMA_COLUMNS].copy()
    for c in ["match_id", "source", "object_type", "player_id", "team_id", "team_side",
              "position", "possession_group", "possession_player_id"]:
        df[c] = df[c].astype("string")
    df["period"] = df["period"].astype("int8")
    df["frame_id"] = df["frame_id"].astype("int64")
    df["jersey_number"] = df["jersey_number"].astype("Int16")
    df["is_detected"] = df["is_detected"].astype("boolean")
    df["status_conflict"] = df["status_conflict"].astype("bool")
    for c in ["timestamp_s", "x_raw", "y_raw", "x_m", "y_m", "ball_z",
              "x_home_m", "y_home_m", "x_att_m", "y_att_m"]:
        df[c] = df[c].astype("float64")
    obj_order = df["object_type"].map({"ball": 0, "player": 1})
    df = (df.assign(_o=obj_order)
            .sort_values(["period", "frame_id", "_o", "team_side", "player_id"], kind="stable")
            .drop(columns="_o").reset_index(drop=True))
    return df

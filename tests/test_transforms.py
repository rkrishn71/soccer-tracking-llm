"""Unit checks of the coordinate transforms, and raw data untouched."""
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.config import RAW
from src.load import get_frame, load_match, load_meta
from conftest import MATCHES


def test_metrica_transform_known_points():
    f = get_frame("metrica_game_1", 1)
    b = f[f.object_type == "ball"].iloc[0]
    # raw (0.45472, 0.38709): x=(0.45472-0.5)*105, y=-(0.38709-0.5)*68 (y flipped: raw y grows downward)
    assert np.isclose(b.x_m, (0.45472 - 0.5) * 105)
    assert np.isclose(b.y_m, -(0.38709 - 0.5) * 68)


@pytest.mark.parametrize("match_id", MATCHES)
def test_normalized_columns_consistent(match_id):
    meta = load_meta(match_id)
    df = load_match(match_id, columns=["period", "x_m", "y_m", "x_home_m", "y_home_m",
                                       "x_att_m", "y_att_m", "possession_group"]).sample(200_000, random_state=1)
    for p, g in df.groupby("period"):
        s = 1 if meta["attack_direction"][str(p)]["home_attacks_plus_x"] else -1
        assert np.allclose(g.x_home_m, s * g.x_m, equal_nan=True)
        assert np.allclose(g.y_home_m, s * g.y_m, equal_nan=True)
    h, a, n = (df.possession_group == "home team"), (df.possession_group == "away team"), df.possession_group.isna()
    assert np.allclose(df.x_att_m[h], df.x_home_m[h], equal_nan=True)
    assert np.allclose(df.x_att_m[a], -df.x_home_m[a], equal_nan=True)
    assert np.allclose(df.y_att_m[a], -df.y_home_m[a], equal_nan=True)
    assert df.x_att_m[n].isna().all() and df.y_att_m[n].isna().all()


@pytest.mark.parametrize("match_id", MATCHES)
def test_no_rows_dropped_or_filled(match_id):
    """Undetected / absent rows are kept: positions are never filled for is_detected == False in Metrica."""
    df = load_match(match_id, columns=["source", "object_type", "x_m", "is_detected"])
    if df.source.iloc[0] == "metrica":
        assert (df.x_m.isna() == ~df.is_detected.astype(bool)).all()
    else:
        pl = df[df.object_type == "player"]
        assert (pl.is_detected == False).any()      # extrapolated rows present
        assert pl.is_detected.notna().all()


def test_status_conflict_flag():
    assert load_meta("1953632")["status_conflict"] is True
    assert load_match("1953632", columns=["status_conflict"]).status_conflict.all()
    others = [m for m in MATCHES if m != "1953632"]
    assert not any(load_meta(m)["status_conflict"] for m in others)


@pytest.mark.parametrize("repo", ["skillcorner_opendata", "metrica_sample_data"])
def test_raw_repos_unmodified(repo):
    """git sees no content change in data/raw (LFS files hash back to their pointers)."""
    r = subprocess.run(["git", "diff", "--quiet"], cwd=RAW / repo)
    assert r.returncode == 0
    u = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=RAW / repo,
                       capture_output=True, text=True).stdout
    assert all(l.startswith(" M") for l in u.splitlines()), u  # only stat-dirty LFS files, no new files


def test_epts_parser_matches_kloppy():
    """Cross-check the hand-written EPTS parser against kloppy on sampled frames of Game 3."""
    from kloppy import metrica as km
    d = RAW / "metrica_sample_data" / "data" / "Sample_Game_3"
    ds = km.load_tracking_epts(meta_data=str(d / "Sample_Game_3_metadata.xml"),
                               raw_data=str(d / "Sample_Game_3_tracking.txt"),
                               coordinates="metrica", limit=None)
    by_id = {f.frame_id: f for f in ds.frames}
    for fid in [1, 5000, 69661, 69662, 93453, 120000, 143761]:
        mine = get_frame("metrica_game_3", fid)
        kf = by_id[fid]
        n_compared = 0
        for p, pd_ in kf.players_data.items():
            row = mine[mine.player_id == p.player_id]
            if pd_.coordinates is None or np.isnan(pd_.coordinates.x):
                # kloppy lists off-pitch players with NaN; we only emit players in the active
                # EPTS DataFormatSpecification block, so they are absent or NaN here
                assert len(row) == 0 or row.x_raw.isna().all(), (fid, p.player_id)
                continue
            assert len(row) == 1, (fid, p.player_id)
            assert np.isclose(row.x_raw.iloc[0], pd_.coordinates.x)
            assert np.isclose(row.y_raw.iloc[0], pd_.coordinates.y)
            n_compared += 1
        assert n_compared >= 20, (fid, n_compared)
        b = mine[mine.object_type == "ball"].iloc[0]
        if kf.ball_coordinates is not None and not np.isnan(kf.ball_coordinates.x):
            assert np.isclose(b.x_raw, kf.ball_coordinates.x)

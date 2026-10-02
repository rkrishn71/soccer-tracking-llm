"""Frame ids are unique and increasing per period; ids are preserved from the raw files."""
import numpy as np
import orjson
import pandas as pd
import pytest

from src.config import SKILLCORNER_DIR
from src.load import get_frame, load_match, load_meta
from src.config import SCHEMA_COLUMNS
from conftest import MATCHES, SC_MATCHES


@pytest.mark.parametrize("match_id", MATCHES)
def test_frame_ids_unique_and_increasing(match_id):
    df = load_match(match_id, columns=["period", "frame_id", "object_type", "player_id"])
    # one row per (period, frame, object)
    key = df.player_id.fillna("__ball__")
    dup = df.assign(k=key).duplicated(["period", "frame_id", "k"])
    assert not dup.any(), df[dup].head()
    for p, g in df.groupby("period", sort=True):
        fr = g.frame_id.drop_duplicates().to_numpy()
        assert (np.diff(fr) > 0).all(), f"period {p}: frame ids not strictly increasing"
    # periods do not overlap and are ordered
    rng = df.groupby("period").frame_id.agg(["min", "max"]).sort_index()
    assert (rng["min"].iloc[1:].to_numpy() > rng["max"].iloc[:-1].to_numpy()).all()
    # exactly one ball row per frame
    assert (df[df.object_type == "ball"].groupby("frame_id").size() == 1).all()
    assert df.frame_id.nunique() == (df.object_type == "ball").sum()


@pytest.mark.parametrize("match_id", SC_MATCHES)
def test_skillcorner_frame_ids_preserved(match_id):
    """Every raw frame that has a period is present with the identical id; nothing else is."""
    raw = []
    with open(SKILLCORNER_DIR / match_id / f"{match_id}_tracking_extrapolated.jsonl", "rb") as f:
        for line in f:
            r = orjson.loads(line)
            if r["period"] is not None:
                raw.append((r["period"], r["frame"]))
    raw = pd.DataFrame(raw, columns=["period", "frame_id"])
    proc = load_match(match_id, columns=["period", "frame_id"]).drop_duplicates()
    assert len(raw) == len(proc)
    assert (raw.sort_values("frame_id").to_numpy() == proc.sort_values("frame_id").to_numpy()).all()
    # periods match match.json
    meta = load_meta(match_id)
    # Known anomaly (PHASE1_REPORT.md): in several matches the tracking file ends ONE frame
    # before match.json's final end_frame. Allow exactly that, nothing else.
    for p in meta["periods"]:
        g = proc[proc.period == p["period"]]
        assert g.frame_id.min() == p["start_frame"]
        gap = p["end_frame"] - g.frame_id.max()
        is_last = p["period"] == max(q["period"] for q in meta["periods"])
        assert gap == 0 or (is_last and gap == 1), (p, g.frame_id.max())


@pytest.mark.parametrize("match_id", MATCHES)
def test_get_frame_schema(match_id):
    meta = load_meta(match_id)
    rng = np.random.default_rng(0)
    p = meta["periods"][0]
    for fid in rng.integers(p["start_frame"], p["end_frame"], size=3):
        f = get_frame(match_id, int(fid))
        assert list(f.columns) == SCHEMA_COLUMNS
        assert (f.object_type == "ball").sum() == 1
        assert (f.frame_id == fid).all()
        assert f.player_id[f.object_type == "player"].notna().all()
        assert set(f.team_side.dropna()) <= {"home", "away"}

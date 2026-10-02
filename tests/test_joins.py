"""Event / phase frame ids exist in the tracking data (join keys preserved)."""
import numpy as np
import pandas as pd
import pytest

from src import metrica, skillcorner
from src.load import get_frame, load_match, load_meta
from conftest import ME_MATCHES, SC_MATCHES


@pytest.mark.parametrize("match_id", SC_MATCHES)
def test_sampled_dynamic_event_frame_exists(match_id):
    ev = skillcorner.load_dynamic_events(match_id)
    ev = ev.sample(n=min(25, len(ev)), random_state=42)
    for r in ev.itertuples():
        f = get_frame(match_id, int(r.frame_start))
        assert len(f), f"event {r.event_id} frame_start {r.frame_start} not in tracking"
        assert (f.period == r.period).all(), (r.event_id, r.period, f.period.unique())


@pytest.mark.parametrize("match_id", SC_MATCHES)
def test_all_event_and_phase_frames_exist(match_id):
    frames = set(load_match(match_id, columns=["frame_id"]).frame_id.unique())
    ev = skillcorner.load_dynamic_events(match_id)
    ph = skillcorner.load_phases(match_id)
    missing_ev = set(ev.frame_start) - frames
    missing_ev_end = set(ev.frame_end.dropna().astype(int)) - frames
    assert not missing_ev, sorted(missing_ev)[:20]
    assert not missing_ev_end, sorted(missing_ev_end)[:20]
    assert not (set(ph.frame_start) - frames), sorted(set(ph.frame_start) - frames)[:20]
    # Known anomaly (PHASE1_REPORT.md): in 3 matches the LAST phase of period 1 has a frame_end
    # 1-9 frames after the period's end_frame (i.e. in the half-time gap, where tracking has no
    # objects). Allow <= 10 frames past the end of that phase's own period; anything else fails.
    meta = load_meta(match_id)
    ends = {p["period"]: p["end_frame"] for p in meta["periods"]}
    bad = ph[~ph.frame_end.isin(frames)]
    over = bad.frame_end - bad.period.map(ends)
    assert ((over > 0) & (over <= 10)).all(), bad[["frame_start", "frame_end", "period"]].to_string()


@pytest.mark.parametrize("match_id", ME_MATCHES)
def test_metrica_event_frames_exist(match_id):
    g = metrica.game_from_match_id(match_id)
    frames = set(load_match(match_id, columns=["frame_id"]).frame_id.unique())
    if g in (1, 2):
        ev = metrica.read_csv_events(g)
        starts = set(ev["Start Frame"])
    else:
        starts = set(metrica.read_epts_events(g)["start_frame"])
    assert not (starts - frames), sorted(starts - frames)[:20]

"""All x/y within pitch bounds + margin; out-of-bounds rows are REPORTED, not dropped.

Two tiers:
  * report tier  (MARGIN_M = 2 m): every row outside is written to
    data/processed/qa/out_of_bounds_<match>.csv and summarised as a pytest warning.
    Off-pitch positions occur in real data (players/ball beyond the lines, extrapolation
    drift), so this tier does not fail the suite.
  * hard tier (HARD_M = 15 m): anything this far out indicates a coordinate/unit bug
    (e.g. a 0..1 value left unscaled would be <1 m, a missing centre shift ~52 m), so it fails.
"""
import warnings

import pandas as pd
import pytest

from src.config import QA_DIR
from src.load import load_match, load_meta
from conftest import MATCHES

MARGIN_M = 2.0
HARD_M = 15.0


@pytest.mark.parametrize("match_id", MATCHES)
def test_positions_within_pitch(match_id):
    meta = load_meta(match_id)
    L, W = meta["pitch_length_m"], meta["pitch_width_m"]
    df = load_match(match_id, columns=["period", "frame_id", "object_type", "player_id",
                                       "x_m", "y_m", "is_detected"])
    pos = df[df.x_m.notna()]
    out = pos[(pos.x_m.abs() > L / 2 + MARGIN_M) | (pos.y_m.abs() > W / 2 + MARGIN_M)]
    QA_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(QA_DIR / f"out_of_bounds_{match_id}.csv", index=False)
    if len(out):
        summary = out.groupby(["object_type", "is_detected"], dropna=False).size().to_dict()
        warnings.warn(f"{match_id}: {len(out)} rows beyond pitch+{MARGIN_M}m {summary}")
    hard = pos[(pos.x_m.abs() > L / 2 + HARD_M) | (pos.y_m.abs() > W / 2 + HARD_M)]
    assert hard.empty, hard.head(20).to_string()


@pytest.mark.parametrize("match_id", [m for m in MATCHES if m.startswith("metrica_")])
def test_metrica_raw_in_unit_square_approx(match_id):
    df = load_match(match_id, columns=["x_raw", "y_raw"]).dropna()
    assert df.x_raw.between(-0.2, 1.2).all() and df.y_raw.between(-0.2, 1.2).all()

"""Read access to data/processed/ in the common frame schema.

    from src.load import get_frame, list_matches, load_meta
    get_frame("1874553", 1000)          # SkillCorner match id (str or int)
    get_frame("metrica_game_1", 1000)   # Metrica: metrica_game_{1,2,3}
"""
from functools import lru_cache
import json

import pandas as pd
import pyarrow.parquet as pq

from .config import PROCESSED, SCHEMA_COLUMNS


def _path(match_id) -> "Path":
    p = PROCESSED / f"{match_id}.parquet"
    if not p.exists():
        raise FileNotFoundError(f"No processed file for match {match_id!r} (run `python -m src.build`)")
    return p


def list_matches() -> list[str]:
    return sorted(p.stem for p in PROCESSED.glob("*.parquet"))


@lru_cache(maxsize=None)
def load_meta(match_id) -> dict:
    return json.loads((PROCESSED / f"{match_id}.meta.json").read_text())


def get_frame(match_id, frame_id: int, period: int | None = None) -> pd.DataFrame:
    """All objects (ball + players) at one frame, in the common schema.

    frame_id is the ORIGINAL provider frame id (unique within a match for both sources,
    so period is optional; pass it only as an extra filter).
    Returns an empty DataFrame with the schema columns if the frame has no objects
    (e.g. SkillCorner pre-match / half-time frames).
    """
    filters = [("frame_id", "=", int(frame_id))]
    if period is not None:
        filters.append(("period", "=", int(period)))
    t = pq.read_table(_path(str(match_id)), filters=filters)
    df = t.to_pandas()
    return df[SCHEMA_COLUMNS].reset_index(drop=True)


def load_match(match_id, columns=None) -> pd.DataFrame:
    """Whole match (can be ~1-4M rows)."""
    return pd.read_parquet(_path(str(match_id)), columns=columns)

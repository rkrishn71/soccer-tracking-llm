"""Build data/processed/: one parquet + one metadata JSON per match, plus QA summaries.

Usage:  python -m src.build            # everything
        python -m src.build 1874553    # selected match ids
"""
import json
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from . import metrica, skillcorner
from .config import PROCESSED, QA_DIR

ROW_GROUP = 50_000
OFFPITCH_MARGIN_M = 2.0


def _stats(df: pd.DataFrame, meta: dict) -> dict:
    L, W = meta["pitch_length_m"], meta["pitch_width_m"]
    pl = df[df.object_type == "player"]
    ball = df[df.object_type == "ball"]
    has_pos = pl.x_m.notna()
    off = has_pos & ((pl.x_m.abs() > L / 2) | (pl.y_m.abs() > W / 2))
    off_margin = has_pos & ((pl.x_m.abs() > L / 2 + OFFPITCH_MARGIN_M) | (pl.y_m.abs() > W / 2 + OFFPITCH_MARGIN_M))
    b_has = ball.x_m.notna()
    b_off = b_has & ((ball.x_m.abs() > L / 2) | (ball.y_m.abs() > W / 2))
    b_off_m = b_has & ((ball.x_m.abs() > L / 2 + OFFPITCH_MARGIN_M) | (ball.y_m.abs() > W / 2 + OFFPITCH_MARGIN_M))

    def xtab(mask, sub):
        det = sub.is_detected
        return {"detected": int((mask & (det == True)).sum()),
                "extrapolated_or_absent": int((mask & (det == False)).sum()),
                "flag_missing": int((mask & det.isna()).sum())}

    frames = df.drop_duplicates(["period", "frame_id"])
    return {
        "match_id": meta["match_id"], "source": meta["source"],
        "pitch_length_m": L, "pitch_width_m": W,
        "n_rows": int(len(df)), "n_player_rows": int(len(pl)), "n_ball_rows": int(len(ball)),
        "n_frames": int(len(frames)),
        "n_frames_by_period": {str(k): int(v) for k, v in frames.groupby("period").size().items()},
        "n_players_seen": int(pl.player_id.nunique()),
        "player_rows_with_position": int(has_pos.sum()),
        "player_rows_detected": int((pl.is_detected == True).sum()),
        "share_player_rows_detected": float((pl.is_detected == True).mean()),
        "ball_rows_with_position": int(b_has.sum()),
        "ball_rows_detected": int((ball.is_detected == True).sum()),
        "ball_rows_with_z": int(ball.ball_z.notna().sum()),
        "frames_possession_null_share": float(frames.possession_group.isna().mean()),
        "player_offpitch_any": xtab(off, pl),
        "player_offpitch_beyond_margin": xtab(off_margin, pl),
        "player_max_abs_x_m": float(pl.x_m.abs().max()), "player_max_abs_y_m": float(pl.y_m.abs().max()),
        "ball_offpitch_any": xtab(b_off, ball),
        "ball_offpitch_beyond_margin": xtab(b_off_m, ball),
        "status_conflict": bool(meta["status_conflict"]),
    }


def _write(df: pd.DataFrame, meta: dict) -> dict:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    mid = meta["match_id"]
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, PROCESSED / f"{mid}.parquet", row_group_size=ROW_GROUP, compression="zstd")
    (PROCESSED / f"{mid}.meta.json").write_text(json.dumps(meta, indent=2, default=_jsonable))
    return _stats(df, meta)


def _jsonable(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    raise TypeError(type(o))


def build_one(match_id: str) -> dict:
    if match_id.startswith("metrica_"):
        df, meta = metrica.build(metrica.game_from_match_id(match_id))
    else:
        meta = skillcorner.build_metadata(match_id)
        df = skillcorner.build_frames(match_id, meta)
    s = _write(df, meta)
    print(f"built {match_id}: {s['n_rows']:,} rows", flush=True)
    return s


def stats_from_disk(match_id: str) -> dict:
    df = pd.read_parquet(PROCESSED / f"{match_id}.parquet")
    meta = json.loads((PROCESSED / f"{match_id}.meta.json").read_text())
    return _stats(df, meta)


def all_match_ids() -> list[str]:
    return skillcorner.list_match_ids() + metrica.list_match_ids()


def main(ids=None, workers=2, stats_only=False):
    """Metrica games are built one at a time (each needs ~3 GB RAM in the long reshape)."""
    ids = ids or all_match_ids()
    if stats_only:
        stats = [stats_from_disk(m) for m in ids]
    else:
        sc = [m for m in ids if not m.startswith("metrica_")]
        me = [m for m in ids if m.startswith("metrica_")]
        with ProcessPoolExecutor(workers) as ex:
            stats = list(ex.map(build_one, sc))
        stats += [build_one(m) for m in me]
    QA_DIR.mkdir(parents=True, exist_ok=True)
    existing = {}
    sp = QA_DIR / "summary.json"
    if sp.exists():
        existing = {s["match_id"]: s for s in json.loads(sp.read_text())}
    for s in stats:
        existing[s["match_id"]] = s
    order = all_match_ids()
    merged = [existing[m] for m in order if m in existing]
    sp.write_text(json.dumps(merged, indent=2))
    return merged


if __name__ == "__main__":
    args = sys.argv[1:]
    stats_only = "--stats-only" in args
    args = [a for a in args if a != "--stats-only"]
    main(args or None, stats_only=stats_only)

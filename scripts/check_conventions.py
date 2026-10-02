"""Verify every `file:line` cited in CONVENTIONS.md still points at the intended code."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECT = {
    ("src/skillcorner.py", 173): 'df["x_m"] = df["x_raw"]',
    ("src/skillcorner.py", 174): 'df["y_m"] = df["y_raw"]',
    ("src/skillcorner.py", 55): '"home_attacks_plus_x": d == "left_to_right"',
    ("src/skillcorner.py", 33): "return int(h) * 3600",
    ("src/skillcorner.py", 144): "if period is None",
    ("src/skillcorner.py", 155): "ball row is always emitted",
    ("src/skillcorner.py", 175): 'df["is_detected"] = df["is_detected"].astype("boolean")',
    ("src/skillcorner.py", 105): "status_conflict = (status_match_json",
    ("src/skillcorner.py", 91): 'abs(o["end_frame"] - on["start_frame"])',
    ("src/metrica.py", 350): 'long["x_m"] = (long["x_raw"] - 0.5) * L',
    ("src/metrica.py", 352): 'long["y_m"] = -(long["y_raw"] - 0.5) * W',
    ("src/metrica.py", 354): 'long["is_detected"] = long["x_raw"].notna()',
    ("src/metrica.py", 355): 'long["ball_z"] = np.nan',
    ("src/metrica.py", 356): 'long["possession_group"] = None',
    ("src/metrica.py", 165): "Ball columns are identical",
    ("src/metrica.py", 162): '"timestamp_s": wide["Time [s]"]',
    ("src/metrica.py", 187): 'long["timestamp_s"] = long["frame_id"] / md["frame_rate"]',
    ("src/metrica.py", 184): 'long["period"] = np.where(long["frame_id"] <= e1, 1, 2)',
    ("src/metrica.py", 106): "def read_epts_tracking",
    ("src/metrica.py", 121): "while not (specs[spec_i]",
    ("src/metrica.py", 53): "int(float(jerseys[i]))",
    ("src/metrica.py", 326): 'abs(o["end_frame"] - on["start_frame"]) <= METRICA_FPS * 60',
    ("src/metrica.py", 282): "direction methods disagree",
    ("src/metrica.py", 248): "own_left = t_ko.x_raw.mean() < 0.5",
    ("src/metrica.py", 259): "n_right > len(s) / 2",
    ("src/metrica.py", 263): "idxmin",
    ("src/metrica.py", 267): 'gk_mean_x = t[t.player_id == deepest.index[0]]',
    ("src/metrica.py", 289): "Game 3 metadata direction disagrees",
    ("src/metrica.py", 293): 'home_plus_x = {p: dirs[f"{p}_home"] == "left_to_right"',
    ("src/metrica.py", 217): "kickoff_tol_m: float = 1.0",
    ("src/normalize.py", 22): 'df["x_home_m"] = df["x_m"] * sign_home',
    ("src/normalize.py", 23): 'df["y_home_m"] = df["y_m"] * sign_home',
    ("src/normalize.py", 26): "poss_sign = ",
    ("src/normalize.py", 27): 'df["x_att_m"] = df["x_home_m"] * poss_sign',
    ("src/normalize.py", 28): 'df["y_att_m"] = df["y_home_m"] * poss_sign',
    ("src/build.py", 19): "OFFPITCH_MARGIN_M = 2.0",
    ("tests/test_bounds.py", 20): "MARGIN_M = 2.0",
    ("tests/test_bounds.py", 21): "HARD_M = 15.0",
}
bad = []
for (f, n), snip in EXPECT.items():
    lines = (ROOT / f).read_text().splitlines()
    if n > len(lines) or snip not in lines[n - 1]:
        bad.append(f"{f}:{n} expected {snip!r}, found {lines[n-1].strip() if n <= len(lines) else 'EOF'!r}")
# every file:line cited in CONVENTIONS.md must be covered above (ranges -> both ends)
cited = set()
for f, a, b in re.findall(r"`?(src/\w+\.py|tests/\w+\.py):(\d+)(?:-(\d+))?", (ROOT / "CONVENTIONS.md").read_text()):
    cited.add((f, int(a)))
    if b:
        cited.add((f, int(b)))
missing = sorted(cited - set(EXPECT))
if missing:
    bad.append(f"cited but not checked: {missing}")
print("\n".join(bad) if bad else f"OK: {len(EXPECT)} cited lines verified")
sys.exit(1 if bad else 0)

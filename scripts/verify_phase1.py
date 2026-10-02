"""Compare a fresh build's QA summary with the reference numbers from the original Phase 1 run.

    python scripts/verify_phase1.py

Every integer count (rows, frames, detected rows, off-pitch counts, ...) must match exactly;
shares and max distances must match to 1e-9. Exit code 1 on any difference.
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "reference" / "phase1_summary.json"
NEW = ROOT / "data" / "processed" / "qa" / "summary.json"


def flatten(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        else:
            out[key] = v
    return out


ref = {s["match_id"]: flatten(s) for s in json.loads(REF.read_text())}
if not NEW.exists():
    sys.exit(f"{NEW} not found - run `python -m src.build` first")
new = {s["match_id"]: flatten(s) for s in json.loads(NEW.read_text())}

problems = []
for m in sorted(set(ref) | set(new)):
    if m not in new:
        problems.append(f"{m}: missing from new build"); continue
    if m not in ref:
        problems.append(f"{m}: not in reference"); continue
    for k, rv in ref[m].items():
        nv = new[m].get(k)
        if isinstance(rv, float) or isinstance(nv, float):
            ok = nv is not None and math.isclose(rv, nv, rel_tol=1e-9, abs_tol=1e-9)
        else:
            ok = rv == nv
        if not ok:
            problems.append(f"{m}.{k}: reference={rv} new={nv}")

total_ref = sum(s["n_rows"] for s in ref.values())
total_new = sum(s.get("n_rows", 0) for s in new.values())
print(f"matches: {len(new)}/{len(ref)}   total rows: new {total_new:,} vs reference {total_ref:,}")
if problems:
    print(f"{len(problems)} differences:")
    print("\n".join("  " + p for p in problems[:50]))
    sys.exit(1)
print("OK - every count matches the original Phase 1 build")

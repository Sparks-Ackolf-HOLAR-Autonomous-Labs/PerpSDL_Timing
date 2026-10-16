#!/usr/bin/env python3
"""Deviation-as-observable comparison (decision of 2026-09-22: the
protocol deviation itself is an observable, and its effect on the
mechanism is measured).

Grades the SAME attempt-2 campaigns two ways and diffs them:
  A) fallback regrade  (deviation D-2026-09-22-B): folded 1x1 gaps,
     qualification at F2 completion, as-run billing;
  B) repair regrade    (amendment D-2026-09-22-A): measured 8x8 F3
     gaps, qualification at F3 completion, corrected billing.

Reported observables:
  1. per-candidate gap: 8x8 F3 measured vs folded 1x1 (window flips);
  2. per-pair PW60 verdict flips and first-qualifier identity changes;
  3. overall PW60 under each grading and the registered directional
     prediction P-2026-09-22 (repair PW60 >= fallback PW60, because the
     fallback prices CEDT's masking holds but excludes the F3 stage
     where CEDT's reservation advantage is largest);
  4. billed_first_qual shift (F2-time vs F3-time qualification).

Usage: deviation_comparison.py [fallback_graded] [repair_graded]
                               [repair_gaps] [outdir]
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
fb_f = Path(sys.argv[1]) if len(sys.argv) > 1 else \
    HERE.parent / "fallback_regrade" / "results" / "fallback_graded.json"
rp_f = Path(sys.argv[2]) if len(sys.argv) > 2 else \
    HERE / "results" / "repair_graded.json"
gp_f = Path(sys.argv[3]) if len(sys.argv) > 3 else \
    HERE.parent / "results_repair" / "repair_gaps.json"
outdir = Path(sys.argv[4]) if len(sys.argv) > 4 else HERE / "results"
outdir.mkdir(parents=True, exist_ok=True)

fb = json.load(open(fb_f))
rp = json.load(open(rp_f))
gaps = json.load(open(gp_f))["gaps"]
MAN = json.load(open(HERE.parent / "inputs" / "manifest2.json"))
G1 = {r["name"]: r["gap_1x1_ev"] for r in MAN["candidates"]}
LO, HI = 1.0, 2.0


def inwin(g):
    return g is not None and LO <= g <= HI


cand_rows = []
for name, r in sorted(gaps.items()):
    g8 = r.get("gap_ev")
    g1 = G1.get(name)
    cand_rows.append({
        "candidate": name, "gap_8x8_f3": g8, "gap_1x1_folded": g1,
        "delta_ev": round(g8 - g1, 4) if g8 is not None and
        g1 is not None else None,
        "window_flip": inwin(g8) != inwin(g1),
        "fallback_gradeable": g1 is not None,
    })

fbp = {p["seed"]: p for p in fb["pairs"]}
rpp = {p["seed"]: p for p in rp["pairs"]}
pair_rows = []
for s in sorted(set(fbp) & set(rpp)):
    a, b = fbp[s], rpp[s]
    pair_rows.append({
        "seed": s,
        "fallback_cedt_win": a["cedt_win"],
        "repair_cedt_win": b["cedt_win"],
        "verdict_flip": a["cedt_win"] != b["cedt_win"],
        "fallback_first": [a["dtde_first_qualifier"],
                           a["cedt_first_qualifier"]],
        "repair_first": [b["dtde_first_qualifier"],
                         b["cedt_first_qualifier"]],
        "identity_change": [a["dtde_first_qualifier"],
                            a["cedt_first_qualifier"]] !=
                           [b["dtde_first_qualifier"],
                            b["cedt_first_qualifier"]],
    })

out = {
    "prediction_P_2026_09_22":
        "repair PW60 >= fallback PW60 (registered before repair data)",
    "prediction_holds": rp["pw"] >= fb["pw"],
    "pw_fallback": fb["pw"], "pw_repair": rp["pw"],
    "pw60_pass": {"fallback": fb["pw60_pass_fallback"],
                  "repair": rp["pw60_pass_repair"]},
    "n_verdict_flips": sum(p["verdict_flip"] for p in pair_rows),
    "n_identity_changes": sum(p["identity_change"] for p in pair_rows),
    "n_window_flips": sum(c["window_flip"] for c in cand_rows),
    "pairs": pair_rows, "candidates": cand_rows,
}
json.dump(out, open(outdir / "deviation_report.json", "w"), indent=1)
print(json.dumps({k: out[k] for k in
                  ("pw_fallback", "pw_repair", "prediction_holds",
                   "n_verdict_flips", "n_identity_changes",
                   "n_window_flips")}, indent=1))

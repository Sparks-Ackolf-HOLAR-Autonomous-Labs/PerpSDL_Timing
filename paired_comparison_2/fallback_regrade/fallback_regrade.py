#!/usr/bin/env python3
"""Cheap fallback regrade for comparison No. 2.

Protocol deviation D-2026-09-22-B (authorized by the authors as an *observed*
deviation, not a silent metric swap): grade the R-side metric by joining
each campaign's F2-completion order to the candidates' already-measured
1x1 band gaps (manifest2.json gap_1x1_ev). A candidate "qualifies" the
moment its F2 converges, at the campaign's as-run cumulative billed
pc-nh, if its folded 1x1 gap sits in the preregistered 1.0-2.0 eV
window.

Systematic differences vs the repaired protocol (f3_repair/), recorded
so the deviation itself is an observable:
  1. Qualification happens at F2 time -> billed_first_qual is cheaper
     by construction (no F3 cost, no F3 wait).
  2. The gap is the 1x1 folded value, not the measured 8x8 F3 value.
  3. Candidates without a recorded 1x1 gap (gap_1x1_ev null, 13 of 29)
     can never qualify under the fallback, whatever their true gap.
  4. The F3 gate (an F3 must actually run and converge) is skipped: the
     fallback can crown a qualifier whose ladder never reached F3.

PW60 pair rule is copied verbatim from the frozen analyze_live2.py:
CEDT wins iff it has a first qualifier AND (DTDE has none OR CEDT's
billed_first_qual is lower); both-none pairs are non-wins.

Usage: fallback_regrade.py [campaigns.jsonl] [outdir]
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
src = Path(sys.argv[1]) if len(sys.argv) > 1 else \
    HERE.parent / "results" / "campaigns.jsonl"
outdir = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "results_midrun"
outdir.mkdir(parents=True, exist_ok=True)

MAN = json.load(open(HERE.parent / "inputs" / "manifest2.json"))
GAP = {r["name"]: r["gap_1x1_ev"] for r in MAN["candidates"]}
GAP_LO, GAP_HI = 1.0, 2.0

camps = [json.loads(l) for l in open(src) if l.strip()]

regraded = []
for c in camps:
    cum = 0.0
    first = None
    quals = []
    first_reached_f3 = None
    f3_attempted = {j["candidate"] for j in c["jobs"] if j["cls"] == "f3"}
    for j in c["jobs"]:
        cum += j["billed_nh"]
        if j["cls"] == "f2" and j.get("converged"):
            g = GAP.get(j["candidate"])
            if g is not None and GAP_LO <= g <= GAP_HI:
                quals.append(j["candidate"])
                if first is None:
                    first = round(cum, 4)
                    first_reached_f3 = j["candidate"] in f3_attempted
    regraded.append({
        "arm": c["arm"], "seed": c["seed"],
        "billed": c["billed"], "labels_f2": c["labels_f2"],
        "fallback_first_qual": first,
        "fallback_qualifiers": quals,
        "first_qual_ladder_reached_f3": first_reached_f3,
    })

by = {(r["arm"], r["seed"]): r for r in regraded}
pairs = sorted({s for a, s in by
                if ("DTDE", s) in by and ("CEDT_P4", s) in by})
wins = 0
pair_rows = []
for s in pairs:
    d, c = by[("DTDE", s)], by[("CEDT_P4", s)]
    cf, df = c["fallback_first_qual"], d["fallback_first_qual"]
    win = cf is not None and (df is None or cf < df)
    wins += win
    pair_rows.append({"seed": s, "dtde_first": df, "cedt_first": cf,
                      "cedt_win": bool(win),
                      "dtde_first_qualifier":
                          (d["fallback_qualifiers"] or [None])[0],
                      "cedt_first_qualifier":
                          (c["fallback_qualifiers"] or [None])[0]})
n = len(pairs)
pw = wins / n if n else float("nan")
p_sign = sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n \
    if n else float("nan")

skip_f3_gate = sum(1 for r in regraded
                   if r["first_qual_ladder_reached_f3"] is False)
out = {
    "deviation_id": "D-2026-09-22-B (fallback: folded 1x1 gaps at F2)",
    "n_campaigns": len(regraded), "n_pairs": n,
    "cedt_wins": wins, "pw": round(pw, 3),
    "pw60_pass_fallback": bool(n and pw >= 0.60),
    "sign_p": round(p_sign, 4),
    "pairs": pair_rows,
    "campaigns": regraded,
    "mechanism_observables": {
        "first_qualifiers_whose_ladder_never_reached_f3": skip_f3_gate,
        "candidates_ungradeable_by_fallback":
            sorted(n_ for n_, g in GAP.items() if g is None),
    },
}
json.dump(out, open(outdir / "fallback_graded.json", "w"), indent=1)
print(json.dumps({k: out[k] for k in
                  ("n_pairs", "cedt_wins", "pw", "pw60_pass_fallback",
                   "sign_p")}, indent=1))
for r in pair_rows:
    print(r)

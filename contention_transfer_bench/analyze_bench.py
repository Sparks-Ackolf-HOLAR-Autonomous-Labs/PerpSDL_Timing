#!/usr/bin/env python3
"""Analysis of the measured contention-vs-scale + transfer bench
(granite grn061 SLURM job 1919944). Writes results/bench_analysis.json.

1. Contention factor per scale: co-tenant wall / solo wall for the
   TiS2_1T probe (mean over reps), testing whether interference grows
   with task size.
2. Transfer probes: measured SCF cost vs the MX2-only power-law
   prediction wall = A * nelec^p fitted to this job's own solo+partner
   MX2 points (same node, same day — no cross-machine confound).
"""
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
RES = HERE / "results"

rows = [json.loads(x) for x in open(RES / "bench_results.jsonl")]

# --- contention ---
walls = defaultdict(list)
for r in rows:
    if r["kind"] in ("solo", "cotenant"):
        walls[(r["scale"], r["kind"])].append(r["wall_s"])
contention = {}
for scale in ("s1", "s2", "s3"):
    solo = float(np.mean(walls[(scale, "solo")]))
    cot = float(np.mean(walls[(scale, "cotenant")]))
    contention[scale] = {"solo_s": round(solo, 2),
                         "cotenant_s": round(cot, 2),
                         "factor": round(cot / solo, 4)}

# --- MX2 power-law fit (solo + partner points) ---
pts = [(r["nelec"], r["wall_s"]) for r in rows
       if r["kind"] in ("solo", "partner")]
# dedupe by (nelec) using mean wall
agg = defaultdict(list)
for n, w in pts:
    agg[n].append(w)
x = np.log([n for n in agg])
y = np.log([np.mean(w) for w in agg.values()])
p, loga = np.polyfit(x, y, 1)
transfer = {}
for r in rows:
    if r["kind"] != "transfer":
        continue
    pred = float(np.exp(loga) * r["nelec"] ** p)
    transfer[r["name"]] = {
        "nelec": r["nelec"], "measured_s": r["wall_s"],
        "mx2_law_pred_s": round(pred, 1),
        "ratio_measured_over_pred": round(r["wall_s"] / pred, 3),
        "converged": r["converged"],
    }

out = {"contention": contention,
       "mx2_power_law": {"exponent": round(float(p), 3),
                         "prefactor": round(float(np.exp(loga)), 5)},
       "transfer": transfer}
json.dump(out, open(RES / "bench_analysis.json", "w"), indent=1)
print(json.dumps(out, indent=1))

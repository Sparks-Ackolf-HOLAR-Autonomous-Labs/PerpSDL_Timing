#!/usr/bin/env python3
"""Analysis of the win-win-scale validation run (granite job 1914482):
real SCF cost at 1x/4x/9x/16x electron counts, testing where the
simulated x10-x100 win-win window sits in real node-hours and which
electron-scaling exponent governs the heavy regime (Stage-2 fit: 1.20 on
tiny cells; prior card: 2.5).
"""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
rows = [json.loads(l) for l in
        open(HERE / "results" / "results.jsonl") if l.strip()]
for r in rows:
    r["nelec"] = float(r["nelec"])
    r["nk"] = float(r["nk"])
    r["nh"] = r["ranks"] / 16 * r["wall_s"] / 3600

print(f"{'run':22s} {'nelec':>6} {'nk':>3} {'wall_s':>7} {'nh':>8} conv")
for r in rows:
    print(f"{r['name']:22s} {r['nelec']:6.0f} {r['nk']:3.0f} "
          f"{r['wall_s']:7.0f} {r['nh']:8.4f} {r['converged']}")

# per-family electron exponent at fixed nominal k-grid (nk normalized out
# linearly, the pilot-consistent assumption)
out = {"runs": rows}
for fam in ("TiS2_1T", "MoSe2_2H"):
    fr = [r for r in rows if r["name"].startswith(fam)
          and r["converged"] and r["name"].endswith("k6")]
    if len(fr) >= 2:
        x = np.log([r["nelec"] for r in fr])
        y = np.log([r["wall_s"] / r["nk"] for r in fr])
        p = np.polyfit(x, y, 1)[0]
        out[f"p_e_{fam}"] = float(p)
        print(f"{fam}: fitted electron exponent (k6 series) = {p:.2f}")
# k-linearity check (MoSe2 s2: k6 vs k12)
k6 = [r for r in rows if r["name"] == "MoSe2_2H_s2_k6"]
k12 = [r for r in rows if r["name"] == "MoSe2_2H_s2_k12"]
if k6 and k12:
    pk = np.log(k12[0]["wall_s"] / k6[0]["wall_s"]) / np.log(
        k12[0]["nk"] / k6[0]["nk"])
    out["p_k_measured"] = float(pk)
    print(f"k-point exponent (s2, k6->k12): {pk:.2f} (twin prior 1.0)")
# where the win-win window sits in real units: F2-ladder-equivalent cost
# multiplier vs the measured x1 ladder (~0.02 nh/ladder job envelope)
base = [r for r in rows if r["name"].endswith("_s1_k6")]
if base:
    b = np.mean([r["nh"] for r in base])
    out["cost_multipliers_vs_s1"] = {
        r["name"]: float(r["nh"] / b) for r in rows}
    print("cost multiplier vs s1 mean:")
    for k, v in out["cost_multipliers_vs_s1"].items():
        print(f"  {k}: {v:.1f}x")
json.dump(out, open(HERE / "results" / "scale_fit.json", "w"), indent=1)

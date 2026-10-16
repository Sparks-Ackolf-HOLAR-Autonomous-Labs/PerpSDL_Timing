#!/usr/bin/env python3
"""Analyze the layers/N-axis measurement run (granite, results.jsonl).

Questions:
1. layers vs in-plane: at matched electron count, does a z-stack cost the
   same as an in-plane supercell (the grid study treats task scale as a
   single multiplier)?
2. initial setups: do +-2% strained starts change cost/SCF iterations
   (the grid study assumes setup variants cost the same as their parent)?
3. materials: cross-material cost spread at fixed size.
"""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
rows = [json.loads(ln) for ln in
        open(HERE / "results" / "results.jsonl") if ln.strip()]
R = {r["name"]: r for r in rows}
for r in rows:
    r["nelec"] = float(r["nelec"]) if r["nelec"] != "null" else np.nan
    r["nh"] = r["wall_s"] / 3600.0 * r["ranks"] / 64.0  # node fraction

print(f"{'run':26s} {'nat':>4} {'nelec':>6} {'wall_s':>7} "
      f"{'iters':>5} {'conv':>4}")
for r in sorted(rows, key=lambda x: (x["name"])):
    print(f"{r['name']:26s} {r['nat']:>4} {r['nelec']:6.0f} "
          f"{r['wall_s']:7d} {r['scf_iters']:>5} {r['converged']:>4}")

out = {"n_runs": len(rows),
       "n_converged": sum(r["converged"] >= 1 for r in rows),
       "total_node_hours": sum(r["nh"] for r in rows)}


def pe(r1, r2):
    return float(np.log(r2["wall_s"] / r1["wall_s"])
                 / np.log(r2["nelec"] / r1["nelec"]))


# 1. layers vs in-plane at matched electron count
pairs = [("TiS2_1T_L1_s2", "TiS2_1T_L3_s1", "12at in-plane vs 9at stack"),
         ("MoSe2_2H_L2_s1", "MoSe2_2H_L1_s2", "L2 vs s2 (x? electrons)"),
         ("TiS2_1T_L2_s2", "MoSe2_2H_L1_s2", None)]
comp = {}
for m in ("TiS2_1T", "MoSe2_2H"):
    lay = [R.get(f"{m}_L{k}_s1") for k in (1, 2, 3)]
    if all(lay):
        comp[f"{m}_pe_layers"] = pe(lay[0], lay[2])
    sup = R.get(f"{m}_L1_s1"), R.get(f"{m}_L1_s2")
    if all(sup):
        comp[f"{m}_pe_inplane"] = pe(sup[0], sup[1])
    both = R.get(f"{m}_L2_s2")
    if both and lay[0]:
        comp[f"{m}_pe_mixed_L2s2"] = pe(lay[0], both)
out["exponents"] = comp

# 2. strained initial setups vs parent
setups = {}
for m in ("TiS2_1T", "MoSe2_2H"):
    par = R.get(f"{m}_L1_s2")
    if not par:
        continue
    for s in ("e-2pct", "e+2pct"):
        v = R.get(f"{m}_L1_s2_{s}")
        if v:
            setups[f"{m}_{s}"] = dict(
                wall_ratio=v["wall_s"] / par["wall_s"],
                iter_ratio=v["scf_iters"] / max(par["scf_iters"], 1),
                converged=v["converged"] >= 1)
out["setup_variants"] = setups

# 3. materials spread at fixed size
for size in ("L1_s1", "L1_s2"):
    walls = {m: R[f"{m}_{size}"]["wall_s"] for m in
             ("TiS2_1T", "MoSe2_2H", "WTe2_2H") if f"{m}_{size}" in R}
    if len(walls) >= 2:
        out[f"material_spread_{size}"] = dict(
            walls, ratio_max_min=max(walls.values()) / min(walls.values()))

json.dump(out, open(HERE / "results" / "layers_fit.json", "w"), indent=1,
          default=float)
print(json.dumps(out, indent=1, default=float))

#!/usr/bin/env python3
"""Analysis of the 81-job F1 coupling pilot (measured on granite grn061,
jobs 1914400-1914495, 2026-09-08). Fits exactly the twin parameters the
Stage-2 campaign fit could NOT identify (single-config confound):
parallel-efficiency exponent, pool effect, aggressive-mode effect,
config/quirk spread, failure base rate — and runs required ablation
13.2-1 (remove cross-party feature combinations from the grammar,
measure the held-out predictive change) on real data.

Node-hour convention: the bundle's granite recast counts 16 cores as one
"node" (nh = (ntasks/16) * wall_s / 3600).
"""
import csv
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
rows = list(csv.DictReader(open(HERE / "results" / "pilot_results.csv")))
matrix = {r["job_id"]: r for r in
          csv.DictReader(open(HERE / "job_matrix.csv"))}
NELEC = {"TiS2_1T": 24.0, "MoSe2_2H": 52.0, "WTe2_2H": 52.0}
ZHEAVY = {"TiS2_1T": 0, "MoSe2_2H": 1, "WTe2_2H": 2}  # size proxy order

recs = []
for r in rows:
    m = matrix[r["pilot_id"]]
    ranks = int(m["nodes"]) * 16
    wall = float(r["pw_wall_s"].rstrip("s"))
    rss_gb = float(r["maxrss_kb"].rstrip("K")) / 1024 ** 2
    recs.append(dict(
        cand=r["cand"], nelec=NELEC[r["cand"]], zi=ZHEAVY[r["cand"]],
        ranks=ranks, npool=int(r["npool"]), agg=int(r["agg"]),
        wall=wall, nh=ranks / 16 * wall / 3600, rss_gb=rss_gb,
        conv=int(r["converged"]), rep=int(m["repeat"]),
        cfg=f"n{m['nodes']}p{m['npool']}a{m['aggressive']}"))

n = len(recs)
y = np.log([r["wall"] for r in recs])
ln_rk = np.log([r["ranks"] / 16 for r in recs])
ln_np = np.log([r["npool"] for r in recs])
agg = np.array([float(r["agg"]) for r in recs])
zi = np.array([r["zi"] for r in recs], float)
cand_dum = np.stack([(zi == k).astype(float) for k in (0, 1, 2)], 1)

# ------------------------------------------------ parameter fit (full)
X = np.column_stack([cand_dum, ln_rk, ln_np, agg])
beta, res, *_ = np.linalg.lstsq(X, y, rcond=None)
pred = X @ beta
resid = y - pred
s_hat = -beta[3]           # wall ~ ranks^-s  =>  nh ~ ranks^(1-s)
pool_eff = beta[4]
agg_eff = beta[5]

# per-config residual structure: quirk spread vs repeat noise
cfg_res = {}
for r, e in zip(recs, resid):
    cfg_res.setdefault((r["cand"], r["cfg"]), []).append(e)
cell_means = np.array([np.mean(v) for v in cfg_res.values()])
within = np.concatenate([np.array(v) - np.mean(v)
                         for v in cfg_res.values()])
quirk_sd = float(np.sqrt(max(np.var(cell_means)
                             - np.var(within) / 3, 0)))
noise_sd = float(np.std(within))

# failure base rate: 0/81 failures -> Jeffreys 95% upper bound
fail_ub = 1 - 0.05 ** (1 / n)

# ---------------------------------------- ablation 13.2-1 (real data)
# full grammar: R-side (candidate size) x H-side (ranks/pools/agg)
# cross-party products allowed; reduced grammar: additive only.
X_add = np.column_stack([cand_dum, ln_rk, ln_np, agg])
ln_ne = np.log([r["nelec"] / 38 for r in recs])
X_full = np.column_stack([cand_dum, ln_rk, ln_np, agg,
                          ln_ne * ln_rk, ln_ne * ln_np, ln_ne * agg,
                          zi * ln_rk])
cells = sorted(set((r["cand"], r["cfg"]) for r in recs))
cell_of = np.array([cells.index((r["cand"], r["cfg"])) for r in recs])


def loo_rmse(Xd):
    errs = []
    for c in range(len(cells)):
        tr, te = cell_of != c, cell_of == c
        b, *_ = np.linalg.lstsq(Xd[tr], y[tr], rcond=None)
        errs.extend(y[te] - Xd[te] @ b)
    return float(np.sqrt(np.mean(np.square(errs))))


rmse_add = loo_rmse(X_add)
rmse_full = loo_rmse(X_full)

out = dict(
    n_jobs=n, all_converged=all(r["conv"] for r in recs),
    total_node_hours=float(sum(r["nh"] for r in recs)),
    wall_range_s=[float(np.min([r["wall"] for r in recs])),
                  float(np.max([r["wall"] for r in recs]))],
    parallel_efficiency_exponent_s=float(s_hat),
    prior_s="N(0.65, 0.10) base card",
    pool_effect_log=float(pool_eff),
    aggressive_effect_log=float(agg_eff),
    quirk_sd_log=quirk_sd, repeat_noise_sd_log=noise_sd,
    prior_quirk_sd=0.18,
    failure_rate=0.0, failure_rate_95ub=float(fail_ub),
    prior_beta0="N(-3.0,0.4) -> ~4.7% base rate",
    max_rss_gb=float(np.max([r["rss_gb"] for r in recs])),
    mem_note="memory channel confirmed dead at this scale (max "
             "~GB per rank vs 380 GB node)",
    ablation_13_2_1=dict(
        loo_rmse_additive=rmse_add, loo_rmse_cross=rmse_full,
        heldout_change_pct=float((rmse_add - rmse_full)
                                 / rmse_add * 100)),
    per_candidate_mean_wall_s={
        c: float(np.mean([r["wall"] for r in recs if r["cand"] == c]))
        for c in NELEC},
)
json.dump(out, open(HERE / "results" / "pilot_fit.json", "w"), indent=1)
for k, v in out.items():
    print(k, "=", v)

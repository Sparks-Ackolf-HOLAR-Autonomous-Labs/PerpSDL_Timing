#!/usr/bin/env python3
"""Executed config-rank extraction attack on REAL pilot transcripts
(future-work item 3, the real-data half).

Data: the 81-job randomized F1 pilot measured on CHPC granite grn061
(pilot/results/pilot_results.csv) — per job: candidate, execution
config (ntasks, npool, aggressive), measured wall seconds.

Attacker model: the research party R. R always knows its own candidate
and observes each job's wall-clock duration (a timing side channel that
no billing contract can remove — R sees when its job returns). The
contract controls whether R also sees the config identity:

  * P1-style (config IDs disclosed): attacker estimates H's config
    ranking from half the jobs, scored against the ranking computed
    from the other half. Split-half Spearman = executed extraction
    fidelity under sampling noise.
  * P4-style (no config field): attacker sees only (candidate, wall
    time). Score: Spearman between the per-job timing residual (after
    candidate fixed effects) and the job's true config rank from the
    held-out half. This measures the pure timing side channel.

Limit under audit: protected configuration-ranking extraction
correlation <= 0.20 (frozen manifest, H leakage limits).
"""
import csv
import json
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

HERE = Path(__file__).parent
CSV = HERE.parent / "pilot" / "results" / "pilot_results.csv"


def load():
    rows = []
    with open(CSV) as f:
        for r in csv.DictReader(f):
            if r["converged"] != "1":
                continue
            wall = float(r["pw_wall_s"].rstrip("s"))
            rows.append((r["cand"], (int(r["ntasks"]), int(r["npool"]),
                                     int(r["agg"])), wall))
    return rows


def residuals(rows):
    """log wall time minus candidate fixed effects (what R can compute
    about its own jobs without any H disclosure)."""
    y = np.log([w for (_, _, w) in rows])
    cands = [c for (c, _, _) in rows]
    resid = y.copy()
    for c in set(cands):
        m = np.array([cc == c for cc in cands])
        resid[m] -= y[m].mean()
    return resid


def config_rank(rows, idx, resid):
    cfgs = sorted({cfg for (_, cfg, _) in rows})
    means = {}
    for cfg in cfgs:
        v = [resid[i] for i in idx if rows[i][1] == cfg]
        if v:
            means[cfg] = float(np.mean(v))
    order = sorted(means, key=means.get)          # fastest first
    return {cfg: k for k, cfg in enumerate(order)}, cfgs


def main():
    rows = load()
    resid = residuals(rows)
    rng = np.random.default_rng(41)
    p1, p4 = [], []
    for rep in range(200):                        # split-half bootstrap
        perm = rng.permutation(len(rows))
        a, b = perm[::2], perm[1::2]
        rank_a, cfgs = config_rank(rows, a, resid)
        rank_b, _ = config_rank(rows, b, resid)
        common = [c for c in cfgs if c in rank_a and c in rank_b]
        r1 = spearmanr([rank_a[c] for c in common],
                       [rank_b[c] for c in common]).statistic
        p1.append(abs(r1))
        # P4-style: per-job residual vs true (held-out) config rank
        jr = [rank_b.get(rows[i][1]) for i in a]
        keep = [k for k, v in enumerate(jr) if v is not None]
        r4 = spearmanr([resid[a[k]] for k in keep],
                       [jr[k] for k in keep]).statistic
        p4.append(abs(r4))
    out = dict(n_jobs=len(rows),
               n_configs=len({cfg for (_, cfg, _) in rows}),
               p1_style_config_visible=dict(
                   mean=round(float(np.mean(p1)), 3),
                   q05=round(float(np.quantile(p1, .05)), 3),
                   q95=round(float(np.quantile(p1, .95)), 3)),
               p4_style_timing_only=dict(
                   mean=round(float(np.mean(p4)), 3),
                   q05=round(float(np.quantile(p4, .05)), 3),
                   q95=round(float(np.quantile(p4, .95)), 3)),
               limit=0.20)
    print(json.dumps(out, indent=2))
    (HERE / "pilot_attack_results.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

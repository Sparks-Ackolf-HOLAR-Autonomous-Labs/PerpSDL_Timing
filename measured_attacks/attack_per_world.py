#!/usr/bin/env python3
"""Per-world membership AUCs for the executed attack of attack_study.py.

attack_study.py stored only the pooled within-campaign AUC over the 60
held-out worlds. This script reruns the same training and held-out
campaigns (same worlds, same features, same logistic regression), keeps
the within-campaign AUC of every campaign, and writes per-world values
(mean over the campaigns of one world) so that intervals over worlds can
be drawn. The mean of the per-world values equals the pooled value
because every held-out world contributes the same number of campaigns.

The P3 randomized-response draws in attack_study.py are seeded with
hash((policy, label)), which Python randomizes per process; the P3 values
are therefore reproduced up to that draw and the differences from the
stored values are written to the output. P2 and P4 use no random draw.

Single process. Run:  OMP_NUM_THREADS=1 python3 attack_per_world.py
Output: attack_per_world.json
"""
import json
import os
import sys
import time
from pathlib import Path

for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_k, "1")
import numpy as np  # noqa: E402

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import attack_study as A  # noqa: E402

N_BOOT = 10000


def per_world(scores, y, groups):
    camp = {}
    for g in np.unique(groups):
        m = groups == g
        camp[int(g)] = A.auc(scores[m], y[m])
    worlds = {}
    for g, v in camp.items():
        worlds.setdefault(g // 1000, []).append(v)
    return camp, {w: float(np.mean(v)) for w, v in sorted(worlds.items())}


def main():
    stored = json.loads((HERE / "attack_results.json").read_text())
    train_w = list(range(A.N_TRAIN_WORLDS))
    test_w = list(range(5000, 5000 + A.N_TEST_WORLDS))
    out = {"n_worlds": A.N_TEST_WORLDS, "n_boot": N_BOOT, "interval": "95% percentile bootstrap over held-out worlds",
           "results": {}}
    boot_rng = np.random.default_rng(20261016)
    for policy in A.POLICIES:
        for (label, level, eps, rotate) in A.MECHS:
            t0 = time.time()
            rng = np.random.default_rng(hash((policy, label)) % 2**32)
            Xtr, ytr, _, _, _ = A.collect(train_w, policy, level, eps, rotate, rng)
            Xte, yte, gte, _, _ = A.collect(test_w, policy, level, eps, rotate, rng)
            wgt = A.fit_logreg(Xtr, ytr)
            scores = np.hstack([Xte, np.ones((len(Xte), 1))]) @ wgt
            camp, pw = per_world(scores, yte, gte)
            vals = np.array(list(pw.values()))
            pooled = float(np.mean(list(camp.values())))
            idx = boot_rng.integers(0, len(vals), (N_BOOT, len(vals)))
            bm = vals[idx].mean(1)
            key = f"{policy}/{label}"
            ref = stored[key]["membership_auc"]
            out["results"][key] = dict(
                membership_auc=round(pooled, 3), stored=ref, diff=round(round(pooled, 3) - ref, 3),
                mean_of_worlds=round(float(vals.mean()), 4),
                ci95=[round(float(np.percentile(bm, 2.5)), 4), round(float(np.percentile(bm, 97.5)), 4)],
                n_campaigns=len(camp), per_world={str(w): round(v, 5) for w, v in pw.items()})
            r = out["results"][key]
            print(f"{key:24s} auc={r['membership_auc']:.3f} stored={ref:.3f} diff={r['diff']:+.3f} "
                  f"ci95={r['ci95']} campaigns={r['n_campaigns']} ({time.time() - t0:.0f} s)", flush=True)
    (HERE / "attack_per_world.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Bootstrap intervals over seeds for the comparison No. 3 timing attack.

Companion of seed_bootstrap.py (comparisons 1 and 2). Runs the identical
attacks of paired_comparison_3/wire_attack3.py (same references, leave one
seed out), keeps the outcome of every held-out campaign, and resamples
the held-out seeds with replacement (cluster bootstrap, B = 10000,
percentile 95% intervals). DTDE and CEDT_P4 ran the same seeds 0-14 and
are resampled with the same seed indices, so the T3 difference
(CEDT_P4 minus DTDE identity) keeps its pairing.

As in seed_bootstrap.py, references inside each fold are not refitted per
replicate: the interval describes seed-to-seed variation of the held-out
outcomes given the leave-one-seed-out references.

Output: bootstrap_ci/seed_bootstrap3.json
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "paired_comparison_3"))
import wire_attack3 as wa3  # noqa: E402

B = 10000
RNG = np.random.default_rng(20261015)


def per_seed(result):
    """per_campaign entries of one attack -> {seed: outcome}."""
    out = {}
    for e in result["per_campaign"]:
        assert e["seed"] not in out, "one target per seed expected"
        out[e["seed"]] = dict(idc=e["correct"], idn=e["n"],
                              lab=e["lab"], sc=e["sc"])
    return out


def stats(per, seeds):
    idc = sum(per[s]["idc"] for s in seeds)
    idn = sum(per[s]["idn"] for s in seeds)
    lab = [x for s in seeds for x in per[s]["lab"]]
    sc = [x for s in seeds for x in per[s]["sc"]]
    return idc / idn, wa3.auc(lab, sc)


def summ(point, arr):
    lo, hi = np.nanpercentile(arr, [2.5, 97.5])
    return dict(point=round(float(point), 4), lo=round(float(lo), 4),
                hi=round(float(hi), 4))


def boot(pers):
    """pers: dict name -> per-seed dict; all share the resampled seeds."""
    names = list(pers)
    seeds = sorted(set.intersection(*[set(p) for p in pers.values()]))
    pt = {k: stats(pers[k], seeds) for k in names}
    draws = {k: np.empty((B, 2)) for k in names}
    for b in range(B):
        rs = list(RNG.choice(seeds, size=len(seeds), replace=True))
        for k in names:
            draws[k][b] = stats(pers[k], rs)
    res = {k: dict(n_seeds=len(seeds),
                   identity=summ(pt[k][0], draws[k][:, 0]),
                   auc=summ(pt[k][1], draws[k][:, 1])) for k in names}
    return res, pt, draws


def main():
    main_c = wa3.load(wa3.MAIN, "main")
    br = wa3.load(wa3.BRIDGE, "bridge")
    by = defaultdict(list)
    for c in main_c:
        by[c["arm"]].append(c)
    out = {"B": B, "interval": "percentile 95%, cluster bootstrap over "
           "held-out seeds", "identity_limit": round(wa3.ID_LIMIT, 4),
           "auc_limit": wa3.AUC_LIMIT, "arms": {}}

    pers = {}
    for arm in ("CTDE_P2", "DTDE", "CEDT_P4", "MIX50"):
        r = wa3.attack(by[arm], wa3.loso(by[arm]),
                       routed_only=(arm == "MIX50"), keep_scores=True)
        pers[arm if arm != "MIX50" else "MIX50_routed"] = per_seed(r)

    # DTDE and CEDT_P4 resampled together (paired seeds, T3)
    pair = {k: pers[k] for k in ("DTDE", "CEDT_P4")}
    res, pt, dr = boot(pair)
    out["arms"].update(res)
    diff = dr["CEDT_P4"][:, 0] - dr["DTDE"][:, 0]
    out["T3_identity_difference_CEDT_minus_DTDE"] = summ(
        pt["CEDT_P4"][0] - pt["DTDE"][0], diff)
    for k in ("CTDE_P2", "MIX50_routed"):
        r, _, _ = boot({k: pers[k]})
        out["arms"].update(r)

    # T1: notchpeak DTDE copies, granite DTDE references (other seeds)
    gran = [c for c in by["DTDE"] if c["cluster"] == "granite"]
    bdt = [c for c in br if c["arm"] == "DTDE"]
    t1 = wa3.attack(bdt, wa3.loso(gran), keep_scores=True)
    r, _, _ = boot({"T1": per_seed(t1)})
    out["T1_cross_cluster"] = r["T1"]

    for k, v in out["arms"].items():
        print(k, v)
    print("T3 diff", out["T3_identity_difference_CEDT_minus_DTDE"])
    print("T1", out["T1_cross_cluster"])
    json.dump(out, open(HERE / "seed_bootstrap3.json", "w"), indent=1)
    print("wrote", HERE / "seed_bootstrap3.json")


if __name__ == "__main__":
    main()

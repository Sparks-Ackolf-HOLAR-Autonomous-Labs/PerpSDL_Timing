#!/usr/bin/env python3
"""Bootstrap intervals over seeds for the measured timing attacks.

The executed attacks (paired_comparison_1/wire_attack.py,
paired_comparison_2/wire_attack2.py, timing_masking/mask_study.py) score
each held-out campaign (leave one seed out) and pool the held-out
outcomes. This script keeps the identical attacks and references, records
the outcome of every held-out seed, and resamples the held-out seeds with
replacement (cluster bootstrap, B = 10000, percentile 95% intervals).
Paired arms of one comparison are resampled with the same seed indices,
so the worse-arm statistic of the masking sweep keeps its pairing.

The references inside each held-out fold are not refitted per replicate,
so the interval describes seed-to-seed variation of the held-out
outcomes given the leave-one-seed-out references.

Output: bootstrap_ci/seed_bootstrap.json
"""
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "timing_masking"))
sys.path.insert(0, str(ROOT / "paired_comparison_2"))
import mask_study as ms  # noqa: E402
import wire_attack2 as wa2  # noqa: E402

B = 10000
RNG = np.random.default_rng(20261008)


def per_seed_c1(truth, jobs, cands, arm):
    """Held-out outcomes per seed for comparison 1 (mask_study attack)."""
    seeds = sorted({s for (_, s) in jobs})
    out = {}
    for held in seeds:
        train = [j for s in seeds if s != held for j in jobs[(arm, s)]]
        ref = ms.reference(train)
        fps = ms.fingerprints(jobs[(arm, held)])
        ran = {truth[(arm, held, o)] for o in fps}
        idc = 0
        for oid, fp in fps.items():
            d = {c: ms.dist(fp, ref[c]) for c in ref}
            idc += min(d, key=d.get) == truth[(arm, held, oid)]
        ml, msc = [], []
        for cand in cands:
            if cand in ref:
                ml.append(cand in ran)
                msc.append(-min(ms.dist(fp, ref[cand]) for fp in fps.values()))
        out[held] = dict(idc=idc, idn=len(fps), lab=ml, sc=msc)
    return out


def per_seed_c2(arm):
    """Held-out outcomes per seed for comparison 2 (wire_attack2 attack)."""
    op = wa2.salt_opaque()
    man = json.load(open(ROOT / "paired_comparison_2" / "inputs" / "manifest2.json"))
    names = [c.get("name", c.get("id")) for c in man["candidates"]]
    wire = [json.loads(l) for l in open(ROOT / "paired_comparison_2" / "results"
                                        / "wire_log.jsonl") if l.strip()]
    rev = {}
    for w in wire:
        key = (w["seed"], w["opaque_id"])
        if key not in rev:
            hits = [n for n in names if op(n, w["seed"]) == w["opaque_id"]]
            rev[key] = hits[0] if hits else None
    rows = [w for w in wire if w["arm"] == arm and w["ok"]
            and w["cls"] in ("f1", "f2")]
    seeds = sorted({w["seed"] for w in rows})
    out = {}
    for held in seeds:
        ref = defaultdict(lambda: defaultdict(list))
        for w in rows:
            if w["seed"] != held:
                ref[rev[(w["seed"], w["opaque_id"])]][w["cls"]].append(w["wall_s"])
        ref = {c: {k: float(np.median(v)) for k, v in d.items()}
               for c, d in ref.items()}
        bits = {rev[(w["seed"], w["opaque_id"])]: w["mem_bit"]
                for w in rows if w["mem_bit"] is not None}
        fps, fbit = defaultdict(dict), {}
        for w in rows:
            if w["seed"] == held:
                fps[w["opaque_id"]][w["cls"]] = w["wall_s"]
                fbit[w["opaque_id"]] = w["mem_bit"]

        def dist(oid, cand):
            fp = fps[oid]
            if fbit[oid] is not None and bits.get(cand, fbit[oid]) != fbit[oid]:
                return float("inf")
            d = [abs(math.log(fp[c]) - math.log(ref[cand][c]))
                 for c in fp if c in ref[cand]]
            return float(np.mean(d)) if d else float("inf")

        ran = {rev[(held, o)] for o in fps}
        idc = sum(min(ref, key=lambda c: dist(o, c)) == rev[(held, o)]
                  for o in fps)
        lab, sc = [], []
        for cand in ref:
            lab.append(cand in ran)
            v = -min(dist(o, cand) for o in fps)
            sc.append(v if np.isfinite(v) else -1e9)
        out[held] = dict(idc=idc, idn=len(fps), lab=lab, sc=sc)
    return out


def stats(per, seeds):
    idc = sum(per[s]["idc"] for s in seeds)
    idn = sum(per[s]["idn"] for s in seeds)
    lab = [x for s in seeds for x in per[s]["lab"]]
    sc = [x for s in seeds for x in per[s]["sc"]]
    return idc / idn, ms.auc(lab, sc)


def boot(pers):
    """pers: list of per-seed dicts sharing seed labels (paired arms).
    Returns point and 95% interval per arm and for the worse arm."""
    seeds = sorted(pers[0])
    pt = [stats(p, seeds) for p in pers]
    draws = np.empty((B, len(pers), 2))
    for b in range(B):
        rs = list(RNG.choice(seeds, size=len(seeds), replace=True))
        for k, p in enumerate(pers):
            draws[b, k] = stats(p, rs)

    def summ(point, arr):
        lo, hi = np.nanpercentile(arr, [2.5, 97.5])
        return dict(point=round(point, 4), lo=round(float(lo), 4),
                    hi=round(float(hi), 4))
    res = [dict(identity=summ(pt[k][0], draws[:, k, 0]),
                auc=summ(pt[k][1], draws[:, k, 1])) for k in range(len(pers))]
    worst = dict(identity=summ(max(p[0] for p in pt), draws[:, :, 0].max(1)),
                 auc=summ(max(p[1] for p in pt), draws[:, :, 1].max(1)))
    return res, worst, len(seeds)


def main():
    out = {"B": B, "interval": "percentile 95%, cluster bootstrap over held-out seeds"}
    truth, jobs, cands = ms.load()
    arms = sorted({a for (a, _) in jobs})
    pers = [per_seed_c1(truth, jobs, cands, a) for a in arms]
    res, worst, n = boot(pers)
    out["comparison1"] = {"n_seeds": n, **{a: r for a, r in zip(arms, res)}}
    print("comp1", n, out["comparison1"])

    # every masking clause of timing_masking/mask_results.json (worse arm)
    all_jobs = [j for l in jobs.values() for j in l]
    by_cls = defaultdict(list)
    for j in all_jobs:
        by_cls[j["cls"]].append(j["wall_s"])
    out["masking"] = []
    sweep = json.load(open(ROOT / "timing_masking" / "mask_results.json"))["sweep"]
    for kind, val in [(r["mask"], r["param"]) for r in sweep
                      if r["mask"] != "none"]:
        cls_pad = ({c: float(np.percentile(v, val)) for c, v in by_cls.items()}
                   if kind == "pad" else None)
        mj = ms.apply_mask(jobs, (kind, val), cls_pad)
        _, w, _ = boot([per_seed_c1(truth, mj, cands, a) for a in arms])
        out["masking"].append(dict(mask=kind, param=val, worse_arm=w))
        print(kind, val, w)

    c2 = {}
    for arm in ("DTDE", "CEDT_P4"):
        r, _, n = boot([per_seed_c2(arm)])
        c2[arm] = dict(n_seeds=n, **r[0])
        print("comp2", arm, c2[arm])
    out["comparison2"] = c2
    json.dump(out, open(HERE / "seed_bootstrap.json", "w"), indent=1)
    print("wrote", HERE / "seed_bootstrap.json")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Item 2 (timing masking), analytical pricing on the REAL wire log.

The live comparison's executed attacks (paired_comparison_1/wire_attack.py)
showed that wall-time fingerprints alone identify candidates at 96.3%
(limit 8.7%) and give membership AUC 1.000 (limit 0.60) at every
disclosure level including P4. This study prices two masking
clauses (defined below) against the same 480
measured QE calls, using the SAME leave-one-seed-out attacks:

  QUANT(q)  -- quantized durations / batched returns: the completion
      message is held until the next q-second boundary after the job
      finishes, so the wire shows wall' = ceil(wall/q)*q. (A batching
      period T is the same transform with q = T when dispatches are
      grid-aligned, so one sweep covers both clauses.)
      Cost: the campaign is serial, so every held completion delays the
      next decision -- latency inflation = sum(wall')/sum(wall) - 1.
      Under whole-node billing that idle time is also billed; under
      per-core billing with backfill it is latency only.

  PAD(p)    -- class-constant padding: every job of class c is padded to
      the p-th percentile of that class's population wall (p100 = class
      max). Jobs longer than the pad target cannot be shortened and
      report their true wall (residual leakage). Cost: real held node
      time, sum(padded)/sum(wall) - 1.

Attacker model: identical to wire_attack.py -- reference table built
from the other seeds' labeled MASKED jobs (the attacker observes the
same masked wire; for public CC0 candidates it could also build
unmasked references on its own hardware, which would only help it, so
numbers here are a lower bound on the attack at small q -- caveat
recorded in RESULTS.md).

Honest scope limit: masking protects the WIRE (broker transcripts,
audit logs, third parties). The executing party H physically measures
true wall times regardless; against H itself only proprietary-candidate
uncertainty (no labeled references) or noisy shared hardware helps.
"""
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
RES = HERE.parent / "paired_comparison_1" / "results"

IDENTITY_LIMIT_OVER_PRIOR = 0.05
AUC_LIMIT = 0.60


def load():
    camps = [json.loads(x) for x in open(RES / "campaigns.jsonl")]
    truth, jobs, cands = {}, defaultdict(list), set()
    for c in camps:
        for j in c["jobs"]:
            truth[(j["arm"], j["seed"], j["opaque_id"])] = j["candidate"]
            jobs[(j["arm"], j["seed"])].append(dict(j))
            cands.add(j["candidate"])
    return truth, jobs, sorted(cands)


def apply_mask(jobs, mask, cls_pad=None):
    kind, val = mask
    out = defaultdict(list)
    for k, lst in jobs.items():
        for j in lst:
            m = dict(j)
            w = j["wall_s"]
            if kind == "quant":
                m["wall_s"] = math.ceil(w / val) * val
            elif kind == "pad":
                m["wall_s"] = max(w, cls_pad[j["cls"]])
            out[k].append(m)
    return out


def fingerprints(lst):
    fp = defaultdict(lambda: defaultdict(list))
    for j in lst:
        fp[j["opaque_id"]][j["cls"]].append(j["wall_s"])
    return {o: {c: float(np.median(v)) for c, v in d.items()}
            for o, d in fp.items()}


def reference(lst):
    ref = defaultdict(lambda: defaultdict(list))
    for j in lst:
        ref[j["candidate"]][j["cls"]].append(j["wall_s"])
    return {cand: {c: float(np.median(v)) for c, v in d.items()}
            for cand, d in ref.items()}


def dist(fp, ref_entry):
    ds = [abs(math.log(fp[c]) - math.log(ref_entry[c]))
          for c in fp if c in ref_entry]
    return float(np.mean(ds)) if ds else float("inf")


def auc(labels, scores):
    ranks = np.empty(len(scores))
    ranks[np.argsort(scores)] = np.arange(1, len(scores) + 1)
    s = np.asarray(scores)
    for v in np.unique(s):
        m = s == v
        ranks[m] = ranks[m].mean()
    lab = np.asarray(labels, bool)
    n1, n0 = lab.sum(), (~lab).sum()
    return float((ranks[lab].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def attack(truth, jobs, cands):
    seeds = sorted({s for (_, s) in jobs})
    arms = sorted({a for (a, _) in jobs})
    res = {}
    for arm in arms:
        idc = idt = 0
        ml, ms = [], []
        for held in seeds:
            train = [j for s in seeds if s != held for j in jobs[(arm, s)]]
            ref = reference(train)
            fps = fingerprints(jobs[(arm, held)])
            ran = {truth[(arm, held, o)] for o in fps}
            for oid, fp in fps.items():
                d = {cand: dist(fp, ref[cand]) for cand in ref}
                idc += min(d, key=d.get) == truth[(arm, held, oid)]
                idt += 1
            for cand in cands:
                if cand in ref:
                    ml.append(cand in ran)
                    ms.append(-min(dist(fp, ref[cand])
                                   for fp in fps.values()))
        res[arm] = dict(identity_acc=round(idc / idt, 4),
                        membership_auc=round(auc(ml, ms), 4))
    return res


def main():
    truth, jobs, cands = load()
    prior = 1 / len(cands)
    id_limit = prior + IDENTITY_LIMIT_OVER_PRIOR
    all_jobs = [j for lst in jobs.values() for j in lst]
    base_wall = sum(j["wall_s"] for j in all_jobs)
    walls_by_cls = defaultdict(list)
    for j in all_jobs:
        walls_by_cls[j["cls"]].append(j["wall_s"])

    rows = []
    sweeps = ([("none", 0)] +
              [("quant", q) for q in (5, 15, 30, 60, 120, 300, 600,
                                      1200, 3600)] +
              [("pad", p) for p in (90, 95, 99, 100)])
    for kind, val in sweeps:
        if kind == "none":
            mj = jobs
            cost = 0.0
        elif kind == "quant":
            mj = apply_mask(jobs, ("quant", val))
            cost = (sum(j["wall_s"] for l in mj.values() for j in l)
                    / base_wall - 1)
        else:
            cls_pad = {c: float(np.percentile(v, val))
                       for c, v in walls_by_cls.items()}
            mj = apply_mask(jobs, ("pad", val), cls_pad)
            cost = (sum(j["wall_s"] for l in mj.values() for j in l)
                    / base_wall - 1)
        a = attack(truth, mj, cands)
        worst_id = max(v["identity_acc"] for v in a.values())
        worst_auc = max(v["membership_auc"] for v in a.values())
        row = dict(mask=kind, param=val, cost_inflation=round(cost, 4),
                   worst_identity_acc=worst_id,
                   worst_membership_auc=worst_auc,
                   identity_pass=bool(worst_id <= id_limit),
                   membership_pass=bool(worst_auc <= AUC_LIMIT),
                   per_arm=a)
        rows.append(row)
        print(f"{kind}({val}): cost +{cost*100:.1f}%  "
              f"identity {worst_id:.3f} (limit {id_limit:.3f})  "
              f"mem-AUC {worst_auc:.3f} (limit {AUC_LIMIT})")

    out = dict(n_candidates=len(cands), prior_identity=round(prior, 4),
               identity_limit=round(id_limit, 4),
               membership_auc_limit=AUC_LIMIT, sweep=rows)
    json.dump(out, open(HERE / "mask_results.json", "w"), indent=1)
    print("wrote", HERE / "mask_results.json")


if __name__ == "__main__":
    main()

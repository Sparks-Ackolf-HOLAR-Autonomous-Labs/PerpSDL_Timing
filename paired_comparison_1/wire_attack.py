#!/usr/bin/env python3
"""Executed timing-channel attacks on the REAL live-comparison wire log
(jobs 1919945; accept-and-measure clause of PREREGISTRATION.md).

Attacker: the HPC party H (or any wire observer). It sees exactly the
wire log fields — (arm, seed, opaque_id, cls, ranks, npool, wall_s,
charge_nh, ok) — and nothing else. Ground truth for scoring comes from
campaigns.jsonl (the experimenter's records, never visible to H).

Attack 1 — exact candidate identity from timing fingerprints.
  Leave-one-seed-out per arm: reference table = median wall_s per
  (candidate, cls) built from the other seeds' *labeled* jobs (models an
  attacker with accumulated history on these public CC0 structures).
  Each opaque ID in the held-out seed is matched by log-wall distance
  over its observed classes. Frozen limit: accuracy <= prior + 0.05,
  prior = 1/29.

Attack 2 — membership inference from timing fingerprints.
  For each held-out campaign, each of the 29 candidates gets score
  -min_j dist(fingerprint_j, candidate); AUC over (was-run, score).
  Frozen limit: AUC <= 0.60.

Both attacks use ONLY wall_s + cls, i.e. the residual timing channel
that P4's field-level redaction cannot remove.
"""
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
RES = HERE / "results"


def load():
    camps = [json.loads(x) for x in open(RES / "campaigns.jsonl")]
    # truth[(arm, seed, opaque_id)] = candidate; jobs list per campaign
    truth = {}
    jobs = defaultdict(list)
    cands = set()
    for c in camps:
        for j in c["jobs"]:
            key = (j["arm"], j["seed"], j["opaque_id"])
            truth[key] = j["candidate"]
            jobs[(j["arm"], j["seed"])].append(j)
            cands.add(j["candidate"])
    return camps, truth, jobs, sorted(cands)


def fingerprints(jobs_list):
    """opaque_id -> {cls: median wall_s} for one campaign's wire view."""
    fp = defaultdict(lambda: defaultdict(list))
    for j in jobs_list:
        fp[j["opaque_id"]][j["cls"]].append(j["wall_s"])
    return {oid: {c: float(np.median(v)) for c, v in d.items()}
            for oid, d in fp.items()}


def reference(jobs_train):
    """candidate -> {cls: median wall_s} from labeled training jobs."""
    ref = defaultdict(lambda: defaultdict(list))
    for j in jobs_train:
        ref[j["candidate"]][j["cls"]].append(j["wall_s"])
    return {cand: {c: float(np.median(v)) for c, v in d.items()}
            for cand, d in ref.items()}


def dist(fp, ref_entry):
    ds = [abs(math.log(fp[c]) - math.log(ref_entry[c]))
          for c in fp if c in ref_entry]
    return float(np.mean(ds)) if ds else float("inf")


def auc(labels, scores):
    order = np.argsort(scores)
    ranks = np.empty(len(scores))
    ranks[order] = np.arange(1, len(scores) + 1)
    # midranks for ties
    s = np.asarray(scores)
    for v in np.unique(s):
        m = s == v
        ranks[m] = ranks[m].mean()
    lab = np.asarray(labels, bool)
    n1, n0 = lab.sum(), (~lab).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    return float((ranks[lab].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def main():
    camps, truth, jobs, cands = load()
    seeds = sorted({s for (_, s) in jobs})
    arms = sorted({a for (a, _) in jobs})
    prior = 1.0 / len(cands)
    out = {"n_candidates": len(cands), "prior_identity_acc": prior,
           "identity_limit": prior + 0.05, "membership_auc_limit": 0.60}

    for arm in arms:
        id_correct = id_total = 0
        mem_labels, mem_scores = [], []
        for held in seeds:
            train = [j for s in seeds if s != held
                     for j in jobs[(arm, s)]]
            ref = reference(train)
            fps = fingerprints(jobs[(arm, held)])
            ran = {truth[(arm, held, oid)] for oid in fps}
            for oid, fp in fps.items():
                d = {cand: dist(fp, ref[cand]) for cand in ref}
                guess = min(d, key=d.get)
                id_correct += guess == truth[(arm, held, oid)]
                id_total += 1
            for cand in cands:
                if cand not in ref:
                    continue
                sc = -min(dist(fp, ref[cand]) for fp in fps.values())
                mem_labels.append(cand in ran)
                mem_scores.append(sc)
        acc = id_correct / id_total
        a = auc(mem_labels, mem_scores)
        out[arm] = {
            "identity_acc": round(acc, 4),
            "identity_n": id_total,
            "identity_breach": acc > prior + 0.05,
            "membership_auc": round(a, 4),
            "membership_breach": a > 0.60,
        }
        print(f"{arm}: identity {acc:.3f} (limit {prior+0.05:.3f}, "
              f"prior {prior:.3f}, n={id_total}) | membership AUC "
              f"{a:.3f} (limit 0.60)")

    json.dump(out, open(RES / "wire_attack_results.json", "w"), indent=1)
    print("wrote", RES / "wire_attack_results.json")


if __name__ == "__main__":
    main()

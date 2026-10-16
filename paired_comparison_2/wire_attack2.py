#!/usr/bin/env python3
"""Executed timing-channel attacks on the comparison No. 2 wire log
(jobs 1973175/1973176; preregistered leakage outcome, evaluated on the
quantized wire log as in ../paired_comparison_1/wire_attack.py).

Attacker view per job: (arm, seed, opaque_id, cls, mem_bit, t_start,
t_end, wall_s, billed_nh, ok) exactly as written to wire_log.jsonl.
For CEDT_P4 the completion time is quantized to the 600-s boundary;
DTDE and CEDT_P4_UNMASKED carry true times. Ground truth (candidate
behind each opaque id) is recovered offline from the salted hash and
never enters the attacker's features.

Attack 1 (identity): leave-one-seed-out per arm; reference = median
observed wall_s per (candidate, cls) from the other seeds' labeled
jobs (+ mem_bit where disclosed); held-out ids matched by mean
|log wall| distance over their successful f1/f2 jobs. Limit:
accuracy <= 1/29 + 0.05.
Attack 2 (membership): per held-out campaign, score each candidate by
-min distance to any observed fingerprint; AUC limit 0.60.
Failed jobs (the as-run F3 save-dir bug) are excluded: their ~10-s or
boundary-rounded walls carry no candidate information.
"""
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RES = HERE / "results"


def salt_opaque():
    src = (HERE / "live2_campaign.py").read_text()
    ns = {}
    for line in src.splitlines():
        if line.startswith("SALT"):
            exec(line, ns)
    import hashlib
    return lambda name, seed: hashlib.sha1(
        f"{ns['SALT']}:{seed}:{name}".encode()).hexdigest()[:10]


def auc(labels, scores):
    s = np.asarray(scores, float)
    lab = np.asarray(labels, bool)
    ranks = np.empty(len(s))
    ranks[np.argsort(s)] = np.arange(1, len(s) + 1)
    for v in np.unique(s):
        m = s == v
        ranks[m] = ranks[m].mean()
    n1, n0 = lab.sum(), (~lab).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    return float((ranks[lab].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def main():
    op = salt_opaque()
    man = json.load(open(HERE / "inputs" / "manifest2.json"))
    names = [c.get("name", c.get("id")) for c in man["candidates"]]
    wire = [json.loads(l) for l in open(RES / "wire_log.jsonl") if l.strip()]
    rev = {}
    for w in wire:
        key = (w["seed"], w["opaque_id"])
        if key not in rev:
            hits = [n for n in names if op(n, w["seed"]) == w["opaque_id"]]
            rev[key] = hits[0] if hits else None
    unresolved = sum(v is None for v in rev.values())
    prior = 1.0 / len(names)
    out = {"n_candidates": len(names), "prior_identity_acc": round(prior, 4),
           "identity_limit": round(prior + 0.05, 4),
           "membership_auc_limit": 0.60, "unresolved_ids": unresolved}
    for arm in sorted({w["arm"] for w in wire}):
        rows = [w for w in wire if w["arm"] == arm and w["ok"]
                and w["cls"] in ("f1", "f2")]
        seeds = sorted({w["seed"] for w in rows})
        idc = idn = 0
        ml, ms = [], []
        for held in seeds:
            ref = defaultdict(lambda: defaultdict(list))
            for w in rows:
                if w["seed"] != held:
                    ref[rev[(w["seed"], w["opaque_id"])]][w["cls"]].append(
                        w["wall_s"])
            ref = {c: {k: float(np.median(v)) for k, v in d.items()}
                   for c, d in ref.items()}
            bits = {rev[(w["seed"], w["opaque_id"])]: w["mem_bit"]
                    for w in rows if w["mem_bit"] is not None}
            fps = defaultdict(dict)
            fbit = {}
            for w in rows:
                if w["seed"] == held:
                    fps[w["opaque_id"]][w["cls"]] = w["wall_s"]
                    fbit[w["opaque_id"]] = w["mem_bit"]

            def dist(oid, cand):
                fp = fps[oid]
                if fbit[oid] is not None and bits.get(cand, fbit[oid]) \
                        != fbit[oid]:
                    return float("inf")
                d = [abs(math.log(fp[c]) - math.log(ref[cand][c]))
                     for c in fp if c in ref[cand]]
                return float(np.mean(d)) if d else float("inf")
            ran = {rev[(held, o)] for o in fps}
            for oid in fps:
                g = min(ref, key=lambda c: dist(oid, c))
                idc += g == rev[(held, oid)]
                idn += 1
            for cand in ref:
                ml.append(cand in ran)
                ms.append(-min(dist(o, cand) for o in fps))
        acc = idc / idn if idn else float("nan")
        ms = [x if np.isfinite(x) else -1e9 for x in ms]
        a = auc(ml, ms)
        out[arm] = {"identity_acc": round(acc, 4), "identity_n": idn,
                    "identity_breach": acc > prior + 0.05,
                    "membership_auc": round(a, 4),
                    "membership_breach": a > 0.60}
        print(arm, out[arm])
    json.dump(out, open(RES / "wire_attack_results.json", "w"), indent=1)


if __name__ == "__main__":
    main()

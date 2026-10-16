#!/usr/bin/env python3
"""Preregistered analysis for live comparison No. 2 (frozen BEFORE
submission; grading rules may not change after data exist).

Primary metrics (frozen 2026-09-11):
  R  PW60: CEDT-P4 beats DTDE on billed pc-nh to first qualifier in
     >= 60% of the 15 pairs. Pair win for CEDT iff CEDT found a
     qualifier AND (DTDE found none OR CEDT's billed_first_qual is
     lower). Both-none pairs count as non-wins (conservative).
     One-sided sign test at n=15 over decided pairs.
  H  pooled valid F2+ labels per billed pc-nh, CEDT/DTDE >= 1.05,
     with riders: failure rate <= DTDE + 0.04; no increase in
     memory-kill (rc!=0 with peak RSS > 0.9x reservation) count.

Secondary (preregistered): live timing-masking price = paired
CEDT_P4 (masked, windows A) vs CEDT_P4_UNMASKED (replay, window B) on
seeds 0-2: delta billed pc-nh, delta makespan, total held_s. Leakage:
wire_log.jsonl attacked with ../paired_comparison_1/wire_attack.py
(masked wire vs true walls).
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
res_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "results"
camps = [json.loads(l) for l in
         open(res_dir / "campaigns.jsonl") if l.strip()]

by = {}
for c in camps:
    by[(c["arm"], c["seed"])] = c

pairs = sorted({s for a, s in by if a in ("DTDE", "CEDT_P4")
                and ("DTDE", s) in by and ("CEDT_P4", s) in by})
wins = ties = 0
for s in pairs:
    d, c = by[("DTDE", s)], by[("CEDT_P4", s)]
    cf, df = c["billed_first_qual"], d["billed_first_qual"]
    if cf is not None and (df is None or cf < df):
        wins += 1
    elif cf is None and df is None:
        ties += 1
n = len(pairs)
pw = wins / n if n else float("nan")
# one-sided sign test P(X >= wins | n, 0.5)
p_sign = sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n \
    if n else float("nan")


def pool(arm):
    cs = [c for c in camps if c["arm"] == arm]
    labels = sum(c["labels_f2"] for c in cs)
    billed = sum(c["billed"] for c in cs)
    jobs = [j for c in cs for j in c["jobs"]] if cs and "jobs" in cs[0] \
        else []
    fails = sum(c["fails"] for c in cs)
    calls = sum(len(c.get("jobs", [])) or 0 for c in cs)
    return {"labels": labels, "billed": round(billed, 4),
            "lpn": labels / billed if billed else 0,
            "fails": fails, "calls": calls}

D, C = pool("DTDE"), pool("CEDT_P4")
h_ratio = C["lpn"] / D["lpn"] if D["lpn"] else float("nan")

mask = {}
for s in (0, 1, 2):
    m, u = by.get(("CEDT_P4", s)), by.get(("CEDT_P4_UNMASKED", s))
    if m and u:
        mask[s] = {"billed_masked": m["billed"],
                   "billed_unmasked": u["billed"],
                   "price_pct": round(100 * (m["billed"] / u["billed"]
                                             - 1), 2),
                   "makespan_masked_s": m["makespan_s"],
                   "makespan_unmasked_s": u["makespan_s"]}

out = {"n_pairs": n, "cedt_wins": wins, "pw": round(pw, 3),
       "pw60_pass": bool(n and pw >= 0.60), "sign_p": round(p_sign, 4),
       "dtde": D, "cedt": C, "h_ratio": round(h_ratio, 4),
       "h_pass": bool(h_ratio >= 1.05),
       "masking_price": mask,
       "preregistered_success": bool(n and pw >= 0.60
                                     and h_ratio >= 1.05)}
print(json.dumps(out, indent=1))
json.dump(out, open(res_dir / "graded.json", "w"), indent=1)

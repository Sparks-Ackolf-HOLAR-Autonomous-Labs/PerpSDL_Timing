#!/usr/bin/env python3
"""Repair-based regrade for comparison No. 2 attempt 2.

Reconstructs each attempt-2 campaign as if its F3 calls had not hit the
save-dir bug, using the repair pass measurements (repair_gaps.json):

  For every systematically-failed F3 job record (rc != 0), substitute
  the candidate's repaired gap and replace the ~10-s failed-call billing
  with the counterfactual F3 cost:
      billed_f3 = (f3_wall_s + hold) / 3600 * frac(res_gb of the
                  ORIGINAL record, i.e. that arm's own reservation)
      hold      = QUANT/2 = 300 s expected masking hold for masked
                  CEDT_P4 campaigns (quantized visibility); 0 for DTDE
                  and the unmasked replay.
  Qualifier rule unchanged: gap in [1.0, 2.0] eV at F3 completion;
  billed_first_qual = corrected cumulative billed at that call.

Approximations (recorded, cannot bias between arms):
  * hold is the 300-s expectation, not the exact boundary the real
    timeline would have produced (< 0.04 pc-nh per F3 either way);
  * launch ORDER is taken from the real transcript; multi-hour F3s
    could in principle have reordered later launches within the 8-call
    budget. Both arms carry the identical approximation.

PW60 pair rule copied verbatim from the frozen analyze_live2.py.
H-side is reported both as-run (frozen analyzer's number) and with
corrected billing, since real F3s would have raised both arms' bills.

Usage: repair_regrade.py [campaigns.jsonl] [repair_gaps.json] [outdir]
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
camps_f = Path(sys.argv[1]) if len(sys.argv) > 1 else \
    HERE.parent / "results" / "campaigns.jsonl"
gaps_f = Path(sys.argv[2]) if len(sys.argv) > 2 else \
    HERE.parent / "results_repair" / "repair_gaps.json"
outdir = Path(sys.argv[3]) if len(sys.argv) > 3 else HERE / "results"
outdir.mkdir(parents=True, exist_ok=True)

GAP_LO, GAP_HI = 1.0, 2.0
QUANT_HOLD = 300.0
RANKS, NODE_CORES, NODE_GB = 16, 64, 380.0

rep = json.load(open(gaps_f))["gaps"]
camps = [json.loads(l) for l in open(camps_f) if l.strip()]

regraded = []
for c in camps:
    masked = c["arm"] == "CEDT_P4" and c.get("quant", 0) > 0
    cum = 0.0
    first = None
    quals = []
    fails = 0
    subs = 0
    for j in c["jobs"]:
        if j["cls"] == "f3" and j["rc"] != 0:
            r = rep.get(j["candidate"])
            if not r or r.get("gap_ev") is None:
                # repair itself failed for this candidate: keep it a
                # genuine fail at the original (tiny) billed cost
                cum += j["billed_nh"]
                fails += 1
                continue
            subs += 1
            hold = QUANT_HOLD if masked else 0.0
            fr = max(RANKS / NODE_CORES, j["res_gb"] / NODE_GB)
            cum += (r["f3_wall_s"] + hold) / 3600.0 * fr
            gap = r["gap_ev"]
            if GAP_LO <= gap <= GAP_HI:
                quals.append(j["candidate"])
                if first is None:
                    first = round(cum, 4)
        else:
            cum += j["billed_nh"]
            if j.get("stage_failed"):
                fails += 1
    regraded.append({
        "arm": c["arm"], "seed": c["seed"],
        "billed_asrun": c["billed"],
        "billed_corrected": round(cum, 4),
        "labels_f2": c["labels_f2"],
        "repair_first_qual": first,
        "repair_qualifiers": quals,
        "fails_corrected": fails, "f3_substituted": subs,
    })

by = {(r["arm"], r["seed"]): r for r in regraded}
pairs = sorted({s for a, s in by
                if ("DTDE", s) in by and ("CEDT_P4", s) in by})
wins = 0
pair_rows = []
for s in pairs:
    d, c = by[("DTDE", s)], by[("CEDT_P4", s)]
    cf, df = c["repair_first_qual"], d["repair_first_qual"]
    win = cf is not None and (df is None or cf < df)
    wins += win
    pair_rows.append({"seed": s, "dtde_first": df, "cedt_first": cf,
                      "cedt_win": bool(win),
                      "dtde_first_qualifier":
                          (d["repair_qualifiers"] or [None])[0],
                      "cedt_first_qualifier":
                          (c["repair_qualifiers"] or [None])[0]})
n = len(pairs)
pw = wins / n if n else float("nan")
p_sign = sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n \
    if n else float("nan")


def pool(arm, key):
    cs = [r for r in regraded if r["arm"] == arm]
    lab = sum(r["labels_f2"] for r in cs)
    bil = sum(r[key] for r in cs)
    return lab / bil if bil else float("nan")


h_asrun = pool("CEDT_P4", "billed_asrun") / pool("DTDE", "billed_asrun")
h_corr = pool("CEDT_P4", "billed_corrected") / \
    pool("DTDE", "billed_corrected")

out = {"grading": "repair (measured 8x8 F3 gaps, corrected billing)",
       "n_pairs": n, "cedt_wins": wins, "pw": round(pw, 3),
       "pw60_pass_repair": bool(n and pw >= 0.60),
       "sign_p": round(p_sign, 4), "pairs": pair_rows,
       "h_ratio_asrun": round(h_asrun, 4),
       "h_ratio_corrected": round(h_corr, 4),
       "campaigns": regraded}
json.dump(out, open(outdir / "repair_graded.json", "w"), indent=1)
print(json.dumps({k: out[k] for k in
                  ("n_pairs", "cedt_wins", "pw", "pw60_pass_repair",
                   "sign_p", "h_ratio_asrun", "h_ratio_corrected")},
                 indent=1))
for r in pair_rows:
    print(r)

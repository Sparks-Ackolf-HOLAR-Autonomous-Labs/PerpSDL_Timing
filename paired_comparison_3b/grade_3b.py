#!/usr/bin/env python3
"""Comparison No. 3b interim grading (copy of ../paired_comparison_3/grade_both_lists.py, paths only changed) under several qualifier lists.

Decision of 5 Oct 2026 ("do both"): the research-side metric is
graded twice, side by side, with the same rule as the frozen analyzer
(../paired_comparison_2/analyze_live2.py):
  (a) as run    : the in-campaign gap test on the computed 8x8 cells
                  (billed_first_qual recorded by the driver; primary)
  (b) corrected : a compound counts once its F3 band step completes in the
                  campaign AND it is on the corrected single-layer list
  (c) bilayer   : same, with the D3 2H-stacked (AA') and 3R bilayer lists
                  (secondary, for bilayer devices)
PW60 rule: a sharing arm wins a pair iff it found a qualifier and DTDE
found none or found it at a higher billed pc-nh; both-none is a non-win.
The computing-centre metric (F2 labels per billed pc-nh) does not depend
on the list and is reported once per arm.

Usage: python3 grade_both_lists.py   (reads collected_*/*/campaigns.jsonl;
a later collection of the same campaign replaces an earlier one)
Writes graded_3b_interim.json.
"""
import glob
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
lists = json.load(open(HERE.parent / "paired_comparison_3" / "candidates_corrected.json",
                       encoding="utf-8"))["qualifier_lists"]
LISTS = {"b_single_layer": set(lists["q_single_layer"]),
         "c_bilayer_AA": set(lists["q_bilayer_AA"]),
         "c_bilayer_3R": set(lists["q_bilayer_3R"])}
SHARING = ["CEDT_P4", "MIX50", "CTDE_P2"]

camps = {}
for f in sorted(glob.glob(str(HERE / "collected_*/*/campaigns.jsonl"))):
    for line in open(f, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            camps[(r["arm"], r["seed"])] = r


def first_qual(r, names):
    if names is None:
        return r["billed_first_qual"]
    c = 0.0
    for j in r["jobs"]:
        c += j["billed_nh"]
        if (j["cls"] == "f3" and j.get("gap_ev") is not None
                and j["candidate"] in names):
            return round(c, 3)
    return None


def pw(arm, names):
    seeds = sorted(s for a, s in camps if a == arm and ("DTDE", s) in camps)
    wins = ties = 0
    detail = {}
    for s in seeds:
        x = first_qual(camps[(arm, s)], names)
        d = first_qual(camps[("DTDE", s)], names)
        win = x is not None and (d is None or x < d)
        wins += win
        ties += x is None and d is None
        detail[s] = [x, d, "win" if win else ("both none" if x is None
                                              and d is None else "loss")]
    n = len(seeds)
    p = (sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n
         if n else None)
    return {"n_pairs": n, "wins": wins, "both_none": ties,
            "pw": round(wins / n, 3) if n else None,
            "pw60_pass": bool(n and wins / n >= 0.60),
            "sign_p": round(p, 4) if p is not None else None,
            "pairs": detail}


def h(arm, seeds=None):
    cs = [c for (a, s), c in camps.items() if a == arm
          and (seeds is None or s in seeds)]
    lab = sum(c["labels_f2"] for c in cs)
    bil = sum(c["billed"] for c in cs)
    return {"campaigns": len(cs), "labels_f2": lab, "billed": round(bil, 3),
            "labels_per_pcnh": round(lab / bil, 4) if bil else None,
            "fails": sum(c["fails"] for c in cs)}


out = {"campaigns_collected": len(camps), "H": {}, "R": {}}
base = h("DTDE")
out["H"]["DTDE"] = base
for arm in SHARING:
    hh = h(arm)
    if hh["campaigns"]:
        hh["ratio_vs_DTDE"] = (round(hh["labels_per_pcnh"]
                                     / base["labels_per_pcnh"], 3)
                               if base["labels_per_pcnh"] else None)
        ps = {s for a, s in camps if a == arm and ("DTDE", s) in camps}
        hp, dp = h(arm, ps), h("DTDE", ps)
        hh["paired_seeds_only"] = {
            "seeds": sorted(ps), "labels_per_pcnh": hp["labels_per_pcnh"],
            "dtde_labels_per_pcnh": dp["labels_per_pcnh"],
            "ratio_vs_DTDE": round(hp["labels_per_pcnh"]
                                   / dp["labels_per_pcnh"], 3)
            if dp["labels_per_pcnh"] else None}
        out["H"][arm] = hh
        out["R"][arm] = {"a_as_run": pw(arm, None),
                         **{k: pw(arm, v) for k, v in LISTS.items()}}
json.dump(out, open(HERE / "graded_3b_interim.json", "w", encoding="utf-8"),
          indent=1)
print("campaigns", len(camps))
for arm, R in out["R"].items():
    print(arm, "H ratio all", out["H"][arm]["ratio_vs_DTDE"], "paired",
          out["H"][arm]["paired_seeds_only"]["ratio_vs_DTDE"])
    for k, v in R.items():
        print("  %-15s pairs %d wins %d both-none %d PW %s"
              % (k, v["n_pairs"], v["wins"], v["both_none"], v["pw"]))

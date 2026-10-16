#!/usr/bin/env python3
"""Corrected candidate list for paired comparison No. 3.

Joins three committed records for the 30 MX2 candidates:
  - first pass (dft_campaign/results/outcomes.jsonl): 1T monolayers and
    2H cells that were PBE-spaced bilayers;
  - corrected 2H structures (stacking_study/results_2088961/outcomes.jsonl):
    single layer, AA' and 3R bilayers with D3;
  - the No. 3 8x8 manifest (paired_comparison_2/inputs/manifest2.json), which
    the running campaigns use.
Writes candidates_corrected.json and prints an informal check of the
collected No. 3 campaigns against each qualifier list. The frozen grading
is not changed by this script.
"""
import glob
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent
LO, HI = 1.0, 2.0


def load(path):
    return {json.loads(l)["candidate"]: json.loads(l) for l in open(path)}


def gap_of(r):
    if r is None or not r["stages"].get("F2", {}).get("relax_converged"):
        return None, "not converged"
    f3 = r["stages"].get("F3") or {}
    if f3.get("metallic"):
        return 0.0, "metal"
    if r.get("gap_ev") is None:
        return None, "no gap"
    return round(r["gap_ev"], 4), "gap"


def inwin(g):
    return g is not None and LO <= g <= HI


first = load(PROJ / "dft_campaign/results/outcomes.jsonl")
stack = load(PROJ / "stacking_study/results_2088961/outcomes.jsonl")
man = {r["name"]: r for r in json.load(open(
    PROJ / "paired_comparison_2/inputs/manifest2.json"))["candidates"]}

rows = []
for M in ["Ti", "Zr", "Hf", "Mo", "W"]:
    for X in ["S", "Se", "Te"]:
        for ph in ["1T", "2H"]:
            name = f"{M}{X}2_{ph}"
            g1, s1 = gap_of(first.get(name))
            row = {"name": name, "in_no3_pool": name in man,
                   "no3_cell": (f"8x8, {man[name]['nat']} atoms"
                                + (" (first-pass PBE bilayer)" if ph == "2H" else ""))
                   if name in man else None,
                   "gap_first_pass_ev": g1, "first_pass_status": s1}
            if ph == "1T":
                row.update(gap_corrected_ev=g1, corrected_structure="1T monolayer",
                           gap_bilayer_AA_ev=None, gap_bilayer_3R_ev=None)
                row["q_single_layer"] = row["q_bilayer_AA"] = row["q_bilayer_3R"] = inwin(g1)
            else:
                gm, sm = gap_of(stack[f"{M}{X}2_mono2H"])
                ga, _ = gap_of(stack[f"{M}{X}2_bi2H"])
                g3, _ = gap_of(stack[f"{M}{X}2_bi3R"])
                row.update(gap_corrected_ev=gm, corrected_structure="2H single layer",
                           corrected_status=sm, gap_bilayer_AA_ev=ga, gap_bilayer_3R_ev=g3)
                row["q_single_layer"] = inwin(gm)
                row["q_bilayer_AA"] = inwin(ga)
                row["q_bilayer_3R"] = inwin(g3)
            row["q_first_pass"] = inwin(g1)
            rows.append(row)

lists = {k: sorted(r["name"] for r in rows if r[k]) for k in
         ["q_first_pass", "q_single_layer", "q_bilayer_AA", "q_bilayer_3R"]}
out = {"window_ev": [LO, HI], "candidates": rows, "qualifier_lists": lists,
       "sources": ["dft_campaign/results/outcomes.jsonl",
                   "stacking_study/results_2088961/outcomes.jsonl",
                   "paired_comparison_2/inputs/manifest2.json"]}
json.dump(out, open(HERE / "candidates_corrected.json", "w"), indent=1)
for k, v in lists.items():
    print(k, len(v), v)

# Informal check of collected campaigns: pc-nh billed when the first
# compound on each list completed its band step (F3) in the campaign.
camps = {}
for f in sorted(glob.glob(str(HERE / "collected_*/*/campaigns.jsonl"))):
    r = json.loads(open(f).readline())
    camps[(r["arm"], r["seed"])] = r


def first_qual(r, names):
    c = 0.0
    for j in r["jobs"]:
        c += j["billed_nh"]
        if j["cls"] == "f3" and j.get("gap_ev") is not None and j["candidate"] in names:
            return round(c, 2), j["candidate"]
    return None, None


check = []
for (arm, seed), r in sorted(camps.items()):
    rec = {"arm": arm, "seed": seed, "live": [r["billed_first_qual"], (r["qualifiers"] or [None])[0]]}
    for k in ["q_single_layer", "q_bilayer_AA", "q_bilayer_3R"]:
        rec[k] = list(first_qual(r, set(lists[k])))
    check.append(rec)
    print(rec)
json.dump(check, open(HERE / "candidates_corrected_check.json", "w"), indent=1)

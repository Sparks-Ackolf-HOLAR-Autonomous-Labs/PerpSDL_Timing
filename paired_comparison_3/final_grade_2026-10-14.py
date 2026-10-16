#!/usr/bin/env python3
"""Final grade of comparisons No. 3 and No. 3b (2026-10-14).

Reads the complete collections (paired_comparison_3/collected_2026-10-14,
paired_comparison_3b/collected_2026-10-14) with the pair-site labels written by
each folder's pair_sites.py, and reports, per sharing arm against DTDE:
  * the preregistered computing-centre ratio (pooled F2 labels per billed
    pc-nh), on all 15 pairs and on the pairs whose two campaigns ran on the
    same processor model ("same CPU"), as recommended in the 10 Oct snapshot;
  * the research-side pair wins (as-run list, rule of analyze_live2.py), all
    pairs and same-CPU pairs;
  * the compounds found first (for P3b-4).
Writes final_grade_2026-10-14.json next to this script.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SETS = {"No3": HERE, "No3b": HERE.parent / "paired_comparison_3b"}
SHARING = {"No3": ["CEDT_P4", "MIX50", "CTDE_P2"], "No3b": ["CEDT_P4"]}


def load(folder):
    camps = {}
    for d in sorted((folder / "collected_2026-10-14").iterdir()):
        f = d / "campaigns.jsonl"
        if f.exists():
            rec = json.loads(f.read_text().splitlines()[-1])
            camps[(rec["arm"], rec["seed"])] = rec
    sites = json.loads((folder / "pair_sites.json").read_text())["campaigns"]
    return camps, sites


def ratio(camps, arm, seeds):
    a = sum(camps[(arm, s)]["labels_f2"] for s in seeds) / sum(camps[(arm, s)]["billed"] for s in seeds)
    b = sum(camps[("DTDE", s)]["labels_f2"] for s in seeds) / sum(camps[("DTDE", s)]["billed"] for s in seeds)
    return round(a / b, 3)


def wins(camps, arm, seeds):
    w = 0
    for s in seeds:
        x, y = camps[(arm, s)]["billed_first_qual"], camps[("DTDE", s)]["billed_first_qual"]
        if x is not None and (y is None or x < y):
            w += 1
    return w


out = {}
for key, folder in SETS.items():
    camps, sites = load(folder)
    out[key] = {"campaigns": len(camps)}
    for arm in SHARING[key]:
        seeds = [s for s in range(15) if (arm, s) in camps and ("DTDE", s) in camps]
        same = [s for s in seeds if sites[f"{arm}_s{s}"]["cpu"] == sites[f"DTDE_s{s}"]["cpu"]]
        firsts = sorted({c["qualifiers"][0] for (a, s), c in camps.items()
                         if a in (arm, "DTDE") and c["qualifiers"]})
        out[key][arm] = {"pairs": len(seeds), "H_all": ratio(camps, arm, seeds),
                         "wins_all": wins(camps, arm, seeds),
                         "same_cpu_pairs": len(same),
                         "H_same_cpu": ratio(camps, arm, same) if same else None,
                         "wins_same_cpu": wins(camps, arm, same),
                         "first_qualifiers": firsts}
(HERE / "final_grade_2026-10-14.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))

#!/usr/bin/env python3
"""Site label for every No. 3 pair.

Reads the same collected_*/*/campaigns.jsonl files as grade_both_lists.py
(a later collection replaces an earlier one) and records, per campaign, the
node, cluster (grn* = granite, notch* = notchpeak) and CPU model. A pair is
"same-site" when the sharing arm and its DTDE baseline ran on the same
cluster and CPU model; cost and timing comparisons are only clean for those.
Writes pair_sites.json; prints one line per pair.
"""
import glob
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
camps = {}
for f in sorted(glob.glob(str(HERE / "collected_*/*/campaigns.jsonl"))):
    for line in open(f, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            camps[(r["arm"], r["seed"])] = r


def site(r):
    n = r.get("node") or {}
    host = n.get("host", "?")
    cl = "granite" if host.startswith("grn") else (
        "notchpeak" if host.startswith("notch") else "?")
    return {"host": host, "cluster": cl, "cpu": n.get("cpu_model", "?"),
            "slurm_job": n.get("slurm_job")}


out = {"campaigns": {f"{a}_s{s}": site(r) for (a, s), r in camps.items()},
       "pairs": {}}
for (a, s), r in sorted(camps.items()):
    if a == "DTDE" or ("DTDE", s) not in camps:
        continue
    x, b = site(r), site(camps[("DTDE", s)])
    same = x["cluster"] == b["cluster"] and x["cpu"] == b["cpu"]
    out["pairs"][f"{a}_s{s}"] = {"sharing": x, "dtde": b, "same_site": same}
    print(f"{a:8s} s{s:<3d} {x['cluster']:9s} {x['host']:9s} | DTDE "
          f"{b['cluster']:9s} {b['host']:9s} {'same' if same else 'SPLIT'}")
json.dump(out, open(HERE / "pair_sites.json", "w"), indent=1)

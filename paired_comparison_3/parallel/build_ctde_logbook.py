#!/usr/bin/env python3
"""Seed logbook for the CTDE_P2 arm of comparison No. 3 option C:
the shared training records the centre holds before the
campaign starts. Built from comparison No. 2 attempt 2 calls that ran
cleanly: job RAM = 16 ranks x peak rank RSS (an upper bound, since rank
0 is the largest), keyed by the P2 size bin and stage. Only bin-level
maxima are kept, so no compound identity enters the logbook."""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent
L2 = HERE.parent.parent / "paired_comparison_2"
man = {r["name"]: r for r in
       json.load(open(L2 / "inputs/manifest2.json"))["candidates"]}
mx, n = {}, {}
for line in open(L2 / "results/campaigns.jsonl"):
    for j in json.loads(line)["jobs"]:
        if j.get("rc") != 0 or not j.get("peak_rank_rss_gb"):
            continue
        b = "large" if man[j["candidate"]]["nelec"] > 2000 else "small"
        k = f"{b}:{j['cls']}"
        mx[k] = max(mx.get(k, 0.0), round(16 * j["peak_rank_rss_gb"], 1))
        n[k] = n.get(k, 0) + 1
out = {"source": "paired_comparison_2/results/campaigns.jsonl (attempt 2)",
       "bins": "small: <= 2000 electrons (1T 8x8), large: > 2000 (2H)",
       "max_job_gb": dict(sorted(mx.items())), "n_calls": n}
json.dump(out, open(HERE / "ctde_logbook_seed.json", "w"), indent=1)
print(json.dumps(out, indent=1))

#!/usr/bin/env python3
"""Multi-party scaling for the QE privacy-tax experiment.

Theme: multi-party scalability of autonomous materials discovery and research.

Sweeps the number of RESEARCH parties N in {1,2,3,5} that share one HPC
provider, for each named topology corner (DTDE/CTDE/CEDT and the CTCE-P0
ceiling) plus a MIX midpoint, and reports how the frozen metrics scale with N.
The N-party effects (contention, pooled surrogate, leakage crowding) are the
reduced-form modifiers implemented in surface.run_mix and documented there.

SIMULATED UNITS only. Twin physics imported from simulator.py unchanged.
"""
import argparse
import json
import os
from pathlib import Path

import numpy as np

import sys
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "prior_predictive"))
import simulator as S            # noqa: E402
import surface as SU             # noqa: E402

ARMS = [
    ("DTDE", 0.0, 0.0, "P4"),
    ("CTDE-P4", 1.0, 0.0, "P4"),
    ("CTDE-P2", 1.0, 0.0, "P2"),
    ("CEDT-P4", 0.0, 1.0, "P4"),
    ("CEDT-P2", 0.0, 1.0, "P2"),
    ("MIX-P4(.5,.5)", 0.5, 0.5, "P4"),
    ("CTCE-P0", 1.0, 1.0, "P0"),
]
NPARTIES = [1, 2, 3, 5]


def run_world(arg):
    card, wid = arg
    w = S.sample_world(card, wid)
    out = {}
    for N in NPARTIES:
        base = SU.run_mix(w, 0.0, 0.0, "P4", nparty=N)  # N-matched baseline
        for name, tau, eps, lvl in ARMS:
            res = SU.run_mix(w, tau, eps, lvl, nparty=N)
            d = SU.eval_point(res, base)
            out[(name, N)] = {
                "win_win": d["win_win"], "labels_ratio": d["labels_ratio"],
                "leak_ok": d["leak_ok"], "pw_rate": d["pw_rate"],
                "r_id_acc": d["r_id_acc"], "h_rank_corr": d["h_rank_corr"],
                "r_mi_auc": d["r_mi_auc"], "mean_qual": d["mean_qual"],
                "labels_per_nh": d["labels_per_nh"], "fail_rate": d["fail_rate"],
            }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worlds", type=int, default=200)
    ap.add_argument("--procs", type=int, default=os.cpu_count())
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    if args.smoke:
        args.worlds, args.procs = 4, 1
    cards = ["base", "strong_coupling", "adversarial"]
    tasks = [(cards[w * 3 // args.worlds] if args.worlds >= 3 else "base", w)
             for w in range(args.worlds)]
    if args.procs > 1:
        import multiprocessing as mp
        with mp.Pool(args.procs) as pool:
            res = pool.map(run_world, tasks, chunksize=2)
    else:
        res = [run_world(t) for t in tasks]
    agg = {}
    for out in res:
        for key, d in out.items():
            agg.setdefault(key, []).append(d)
    summary = {}
    for (name, N), lst in agg.items():
        summary.setdefault(name, {})[str(N)] = {
            k: float(np.mean([x[k] for x in lst])) for k in lst[0]
        }
    meta = dict(worlds=args.worlds, nparties=NPARTIES, seeds=SU.NSEED,
                note="SIMULATED UNITS; reduced-form N-party effects, see RESULTS.md")
    outp = HERE / "results" / "scaling.json"
    with open(outp, "w") as fh:
        json.dump({"meta": meta, "summary": summary}, fh, indent=1)
    print(f"wrote {outp} ({len(summary)} arms x {len(NPARTIES)} N)")


if __name__ == "__main__":
    main()

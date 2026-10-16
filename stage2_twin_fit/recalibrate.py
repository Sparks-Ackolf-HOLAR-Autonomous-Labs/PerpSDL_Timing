#!/usr/bin/env python3
"""Stage-2 recalibrated prior-predictive re-grade.

Patches the prior-predictive twin (prior_predictive/simulator.py) with the
empirically fitted cost/memory model from twin_fit.json and re-grades the
main condition grid, plus a task-scale sweep: measured costs x 10^x for
x in 0..4, to locate where the frozen 500-simulated-nh budget starts to
bind and the win-win question becomes non-degenerate again.

What is patched (measured):  per-fidelity amplitudes A, electron exponent
p_e (1.20 +/- fit sd), cost residual sd (0.34 in log), memory model
(~2.2 GB/node at reference, exponent 0.5, base 0.1 -> the memory-failure
channel is effectively dead at this task scale), per-attempt overhead
(two scenarios: in-allocation 0.0005 nh, per-sbatch 0.02 nh).
What is NOT patched (unidentifiable, priors carried): p_k, parallel
efficiency s, pool mismatch pm, quirks, contention/burst, failure base
rate beta0, attacker models.

All node-hours remain simulated units; this is calibration, not a live
claim.
"""
import argparse
import json
import os
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "prior_predictive"))
os.environ.setdefault("MPT_HARD_CAP", "1")
import simulator as sim  # noqa: E402

FIT = json.load(open(HERE / "twin_fit.json"))
A_MEAS = FIT["measured_fit"]["A"]
# twin fidelities F0..F4 mapped to measured stages (F0 ~ min-call cost;
# F4SCF folded into F4)
AF_EMP = np.array([FIT["min_call_node_hours"],
                   A_MEAS["F1"], A_MEAS["F2"], A_MEAS["F3"],
                   A_MEAS["F4"] + 0.1 * A_MEAS["F2"]])
P_E = FIT["measured_fit"]["p_e"]
SD_LOG = FIT["measured_fit"]["resid_sd_log"]

SCALE = 1.0
OVERHEAD = 0.02

_orig_sample = sim.sample_world


def sample_world_emp(card, wid):
    w = _orig_sample(card, wid)
    rng = np.random.default_rng(
        __import__("zlib").crc32(f"emp:{card}:{int(wid)}".encode()))
    w["A"] = AF_EMP * SCALE * np.exp(rng.normal(0, SD_LOG))
    w["p_e"] = np.clip(rng.normal(P_E, 0.1), 0.9, 1.5)
    # memory: measured ~2.2 GB/node at reference cfg, weak nelec
    # dependence, residual spread ~15% -> memory-failure channel dead
    # unless task scale grows; keep rho but shrink its sd to measured
    w["memq"] = float(np.exp(rng.normal(0, 0.05)))
    w["rho"] = np.exp(rng.normal(0, 0.15, sim.C))
    return w


def mem_per_node_emp(w, fid):
    grow = (sim.NK[fid] / 36.0) ** 0.3
    m = (2.1 * (sim.CAND["nelec"][:, None] / 38.0) ** 0.5 * grow
         * w["memq"] * w["rho"][:, None]
         / (sim.C_NODES[None, :] * sim.C_POOLS[None, :] ** 0.4)) + 0.1
    return m * SCALE ** 0.5   # memory grows ~sqrt of work scale (denser
    # grids/bands): conservative coupling for the sweep


def run_grid(worlds, card, procs):
    args = [(card, wid, sim.CONDITIONS_MAIN) for wid in range(worlds)]
    with Pool(procs) as p:
        out = p.map(sim.run_world, args)
    conds = [c[0] for c in sim.CONDITIONS_MAIN]
    agg = {}
    for name in conds:
        rows = [s[name] for _, s in out]
        agg[name] = dict(
            p_win_win=np.mean([r["win_win"] for r in rows]),
            p_r_gain=np.mean([r["r_gain"] for r in rows]),
            p_h_gain=np.mean([r["h_gain"] for r in rows]),
            p_leak_ok=np.mean([r["leak_ok"] for r in rows]),
            mean_nh_used=np.mean([r["mean_nh_used"] for r in rows]),
            mean_qual=np.mean([r["mean_qual"] for r in rows]),
            found_rate=np.mean([r["found_rate"] for r in rows]),
        )
    return agg


def main():
    global SCALE, OVERHEAD
    ap = argparse.ArgumentParser()
    ap.add_argument("--worlds", type=int, default=300)
    ap.add_argument("--procs", type=int, default=os.cpu_count())
    ap.add_argument("--card", default="base")
    ap.add_argument("--scales", default="1,10,100,1000,10000")
    args = ap.parse_args()

    sim.sample_world = sample_world_emp
    sim.mem_per_node = mem_per_node_emp

    results = {}
    for scale in [float(s) for s in args.scales.split(",")]:
        SCALE = scale
        for ov_name, ov in (("sbatch", 0.02), ("in_alloc", 0.0005)):
            if scale > 1 and ov_name == "in_alloc":
                continue   # scenario only matters at measured scale
            OVERHEAD = ov
            sim.OVERHEAD_NH = ov
            key = f"scale_{scale:g}_{ov_name}"
            print("running", key, flush=True)
            results[key] = run_grid(args.worlds, args.card, args.procs)
    meta = dict(worlds=args.worlds, card=args.card,
                AF_emp=AF_EMP.tolist(), p_e=P_E, sd_log=SD_LOG,
                hard_cap=os.environ.get("MPT_HARD_CAP"),
                note="simulated units; empirical calibration from the "
                     "measured DFT campaign; p_k/eff/contention priors "
                     "carried (unidentifiable from single-config data)")
    json.dump(dict(meta=meta, results=results),
              open(HERE / "recalibrated_grade.json", "w"), indent=1)
    for k, agg in results.items():
        best = max(((n, d["p_win_win"]) for n, d in agg.items()
                    if n != "CTCE_P0"), key=lambda t: t[1])
        used = agg["DTDE_P4"]["mean_nh_used"]
        print(f"{k}: best={best[0]} p_ww={best[1]:.3f} "
              f"dtde_nh_used={used:.2f}")


if __name__ == "__main__":
    main()

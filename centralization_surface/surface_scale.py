#!/usr/bin/env python3
"""Task-scale sweep of the centralization surface.

Question: how does the surface change as the workload and complexity of the
tasks increase?

Re-runs the (tau, eps) centralization surface of surface.py on the
MEASUREMENT-ANCHORED posterior twin at task-scale multipliers x1..x300,
using exactly the same empirical patching as scale_experiment_grid/grid_study.py:

  * per-call cost amplitudes = Stage-2 measured fit (twin_fit.json) x SCALE;
  * electron-scaling exponent p_e rises with scale per the measured
    scale-validation curve (1.20 at campaign cells -> ~2.5 by x300);
  * memory channel dead at x1, grows with SCALE^0.5 (measured convention);
  * scheduler priors (s, quirk) from the 81-job pilot fit;
  * per-sbatch overhead 0.02 nh, scale-INVARIANT in real units.

All numbers are SIMULATED UNITS anchored to measured fits. Nothing here is a
CHPC measurement.
"""
import json
import os
import zlib
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
import sys
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "prior_predictive"))
import simulator as sim  # noqa: E402
import surface as SF     # noqa: E402  (same module object for sim/S)

FIT = json.load(open(HERE.parent / "stage2_twin_fit" / "twin_fit.json"))
PFIT = json.load(open(HERE.parent / "pilot" / "results" / "pilot_fit.json"))
A_MEAS = FIT["measured_fit"]["A"]
AF_EMP = np.array([FIT["min_call_node_hours"], A_MEAS["F1"], A_MEAS["F2"],
                   A_MEAS["F3"], A_MEAS["F4"] + 0.1 * A_MEAS["F2"]])
SD_LOG = FIT["measured_fit"]["resid_sd_log"]

sim.PRIOR_CARDS["posterior"] = dict(
    s_mu=PFIT["parallel_efficiency_exponent_s"], s_sd=0.05,
    quirk_sd=PFIT["quirk_sd_log"], pm_lo=0.05, pm_hi=0.30,
    burst_lo=0.05, burst_hi=0.25, beta0_mu=-4.2, beta0_sd=0.4, atk=1.0)

# posterior p_e mean by task scale (scale_validation/results/scale_fit.json)
PE_MU = {1: 1.20, 10: 1.70, 30: 2.00, 100: 2.30, 300: 2.50}
SCALES = [1, 10, 30, 100, 300]

SCALE = 1.0
PE_MU_CELL = 1.20

_orig_sample = sim.sample_world
_orig_mem = sim.mem_per_node


def sample_world_post(card, wid):
    w = _orig_sample(card, wid)
    rng = np.random.default_rng(
        zlib.crc32(f"surfscale:{card}:{int(wid)}".encode()))
    w["A"] = AF_EMP * SCALE * np.exp(rng.normal(0, SD_LOG))
    w["p_e"] = np.clip(rng.normal(PE_MU_CELL, 0.15), 0.9, 3.0)
    w["memq"] = float(np.exp(rng.normal(0, 0.05)))
    w["rho"] = np.exp(rng.normal(0, 0.15, sim.C))
    return w


def mem_per_node_post(w, fid):
    """Measured-scale memory channel (dead at x1; grows with task scale) —
    identical convention to scale_experiment_grid/grid_study.py."""
    grow = (sim.NK[fid] / 36.0) ** 0.3
    m = (2.1 * (sim.CAND["nelec"][:, None] / 38.0) ** 0.5 * grow
         * w["memq"] * w["rho"][:, None]
         / (sim.C_NODES[None, :] * sim.C_POOLS[None, :] ** 0.4)) + 0.1
    return m * SCALE ** 0.5


def run_world(arg):
    wid, grid, levels = arg
    w = sim.sample_world("posterior", wid)
    base4 = SF.run_mix(w, 0.0, 0.0, "P4")  # DTDE-P4 canonical baseline
    out = {}
    for level in levels:
        for (tau, eps) in grid:
            res = SF.run_mix(w, tau, eps, level)
            out[(level, tau, eps)] = SF.eval_point(res, base4)
    ceil = SF.run_mix(w, 1.0, 1.0, "P0")
    out[("P0", "ceiling", "ceiling")] = SF.eval_point(ceil, base4)
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--worlds", type=int, default=120)
    ap.add_argument("--grid", type=int, default=5)
    ap.add_argument("--scales", default=",".join(map(str, SCALES)))
    ap.add_argument("--levels", default="P4")
    ap.add_argument("--p2-scales", default="1,100",
                    help="scales at which to also run the P2 panel")
    ap.add_argument("--procs", type=int, default=os.cpu_count())
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    if args.smoke:
        args.worlds, args.grid, args.procs = 2, 3, 1
        args.scales, args.p2_scales = "1,300", "1"

    sim.sample_world = sample_world_post
    sim.mem_per_node = mem_per_node_post
    sim.OVERHEAD_NH = 0.02
    # surface.py binds module-level constants at import; refresh the one that
    # changed (OVERHEAD) so run_mix uses the measured per-sbatch overhead
    SF.OVER = 0.02

    axis = np.linspace(0, 1, args.grid)
    grid = [(round(float(a), 4), round(float(b), 4))
            for a in axis for b in axis]
    scales = [int(s) for s in args.scales.split(",")]
    p2_scales = {int(s) for s in args.p2_scales.split(",") if s}

    global SCALE, PE_MU_CELL
    out = {"meta": dict(worlds=args.worlds, grid=args.grid,
                        seeds=SF.NSEED, scales=scales,
                        pe_mu_by_scale=PE_MU, overhead_nh=0.02,
                        note="SIMULATED UNITS; posterior twin anchored to "
                             "Stage-2 + pilot + scale-validation fits"),
           "cells": {}}
    for scale in scales:
        SCALE = float(scale)
        PE_MU_CELL = PE_MU.get(scale, 2.5)
        levels = ["P4"] + (["P2"] if scale in p2_scales else [])
        tasks = [(w, grid, levels) for w in range(args.worlds)]
        if args.procs > 1:
            import multiprocessing as mp
            with mp.Pool(args.procs) as pool:
                res = pool.map(run_world, tasks, chunksize=2)
        else:
            res = [run_world(t) for t in tasks]
        agg = {}
        for r in res:
            for key, d in r.items():
                agg.setdefault(key, []).append(d)
        for (level, tau, eps), lst in agg.items():
            k = f"x{scale}|{level}|{tau}|{eps}"
            out["cells"][k] = {
                "scale": scale, "level": level, "tau": tau, "eps": eps,
                "win_win": float(np.mean([x["win_win"] for x in lst])),
                "r_gain_pw60": float(np.mean([x["r_gain_pw60"] for x in lst])),
                "h_gain_package": float(np.mean(
                    [x["h_gain_package"] for x in lst])),
                "leak_ok": float(np.mean([x["leak_ok"] for x in lst])),
                "labels_ratio": float(np.mean(
                    [x["labels_ratio"] for x in lst])),
                "pw_rate": float(np.mean([x["pw_rate"] for x in lst])),
                "mean_qual": float(np.mean([x["mean_qual"] for x in lst])),
                "fail_rate": float(np.mean([x["fail_rate"] for x in lst])),
                "r_id_acc": float(np.mean([x["r_id_acc"] for x in lst])),
                "h_rank_corr": float(np.mean(
                    [x["h_rank_corr"] for x in lst])),
            }
        ww = {(c["tau"], c["eps"]): c["win_win"]
              for c in out["cells"].values()
              if c["scale"] == scale and c["level"] == "P4"
              and c["tau"] != "ceiling"}
        best = max(ww.values()) if ww else float("nan")
        print(f"x{scale}: best P4 win-win {best:.3f} "
              f"(ridge at eps=1: {ww.get((0.0, 1.0), float('nan')):.3f})",
              flush=True)

    outp = HERE / "results" / "surface_scale.json"
    with open(outp, "w") as fh:
        json.dump(out, fh, indent=1)
    print(f"wrote {outp} ({len(out['cells'])} cells)")


if __name__ == "__main__":
    main()

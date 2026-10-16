#!/usr/bin/env python3
"""Adaptive-schedule suite for the centralization surface.

Question: the surface is a map of *static* (tau, eps)
points, but a real consortium can change the degree of training / execution
centralization BEFORE or DURING a campaign -- an adaptive policy. This suite
asks whether a schedule that varies eps (execution centralization) or tau
(training / logbook centralization) over the T campaign rounds beats the best
static contract at the same *average* centralization.

Every schedule is compared against the STATIC contract at its own time-mean, so
the question is specifically "does the timing of disclosure matter, holding the
total amount fixed?" -- not "does more sharing help" (that is the surface).

Schedules (each defined over rounds 0..T-1, values clipped to [0,1]):
  * static      : constant at the mean m
  * ramp_up     : 0 -> 2m  (start private, open up as the campaign learns)
  * ramp_down   : 2m -> 0  (start open, close down once models are seeded)
  * mid_pulse   : 0 except a central window at ~2m (share only mid-campaign)
All share the same time-mean m, so they sit at the same surface point on
average and differ only in WHEN the sharing happens.

SIMULATED UNITS only. Twin physics from simulator.py, engine from surface.py.
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

T = S.T


def _profiles(mean):
    """Return {name: length-T schedule} all with time-mean == `mean`."""
    m = float(mean)
    t = np.arange(T)
    prof = {}
    prof["static"] = np.full(T, m)
    # ramp 0 -> 2m (mean m); clip keeps it legal if 2m > 1
    ramp = np.linspace(0.0, 2.0 * m, T)
    prof["ramp_up"] = _renorm(np.clip(ramp, 0, 1), m)
    prof["ramp_down"] = _renorm(np.clip(ramp[::-1], 0, 1), m)
    # central pulse over the middle third at height chosen to hit mean m
    pulse = np.zeros(T)
    lo, hi = T // 3, 2 * T // 3
    width = max(hi - lo, 1)
    height = min(m * T / width, 1.0)
    pulse[lo:hi] = height
    prof["mid_pulse"] = _renorm(pulse, m)
    return prof


def _renorm(arr, target_mean):
    """Scale a non-negative profile to the target mean without exceeding 1.
    If a pure scale would exceed 1, add a uniform floor instead (keeps shape
    where it can and tops up the mean)."""
    arr = np.clip(np.asarray(arr, float), 0, 1)
    cur = arr.mean()
    if cur <= 1e-9:
        return np.full(T, target_mean)
    scaled = arr * (target_mean / cur)
    if scaled.max() <= 1.0:
        return scaled
    # saturate at 1 and distribute the remaining mass as a floor
    sat = np.clip(scaled, 0, 1)
    deficit = target_mean - sat.mean()
    if deficit > 0:
        room = 1.0 - sat
        add = room * (deficit * T / max(room.sum(), 1e-9))
        sat = np.clip(sat + add, 0, 1)
    return sat


def run_world(arg):
    card, wid, axis, level, mean = arg
    w = S.sample_world(card, wid)
    base4 = SU.run_mix(w, 0.0, 0.0, "P4")     # canonical DTDE-P4 baseline
    prof = _profiles(mean)
    out = {}
    for name, sched in prof.items():
        if axis == "eps":
            tau, eps = 0.0, sched
        else:                                  # axis == "tau"
            tau, eps = sched, 0.0
        res = SU.run_mix(w, tau, eps, level)
        d = SU.eval_point(res, base4)
        out[name] = {
            "win_win": d["win_win"], "labels_ratio": d["labels_ratio"],
            "leak_ok": d["leak_ok"], "pw_rate": d["pw_rate"],
            "mean_qual": d["mean_qual"], "r_id_acc": d["r_id_acc"],
            "h_rank_corr": d["h_rank_corr"], "fail_rate": d["fail_rate"],
            "labels_per_nh": d["labels_per_nh"],
        }
    return axis, level, mean, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worlds", type=int, default=200)
    ap.add_argument("--procs", type=int, default=os.cpu_count())
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    if args.smoke:
        args.worlds, args.procs = 4, 1
    cards = ["base", "strong_coupling", "adversarial"]
    # eps-schedules at P4 (execution axis; where the win-win ridge lives) and
    # tau-schedules at P2 (training axis; where the logbook channel is live).
    settings = [("eps", "P4", 0.5), ("tau", "P2", 0.5)]
    tasks = []
    for (axis, level, mean) in settings:
        for wdi in range(args.worlds):
            card = cards[wdi * 3 // args.worlds] if args.worlds >= 3 else "base"
            tasks.append((card, wdi, axis, level, mean))
    if args.procs > 1:
        import multiprocessing as mp
        with mp.Pool(args.procs) as pool:
            res = pool.map(run_world, tasks, chunksize=4)
    else:
        res = [run_world(t) for t in tasks]

    agg = {}
    for axis, level, mean, out in res:
        key = f"{axis}@{level}|mean={mean}"
        for name, d in out.items():
            agg.setdefault(key, {}).setdefault(name, []).append(d)
    summary = {}
    for key, byname in agg.items():
        summary[key] = {name: {k: float(np.mean([x[k] for x in lst]))
                               for k in lst[0]}
                        for name, lst in byname.items()}
    meta = dict(worlds=args.worlds, rounds=T, seeds=SU.NSEED, settings=settings,
                note="SIMULATED UNITS; schedules share a time-mean, differ by timing")
    outp = HERE / "results" / "schedules.json"
    with open(outp, "w") as fh:
        json.dump({"meta": meta, "summary": summary}, fh, indent=1)
    print(f"wrote {outp} ({len(summary)} settings)")


if __name__ == "__main__":
    main()

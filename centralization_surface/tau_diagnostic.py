#!/usr/bin/env python3
"""Why is the training-centralization axis (tau) flat?

Three-part diagnostic, run after the continuity fix:

  A. P4 IDENTITY CHECK -- at the minimal disclosure level P4 the contract
     discloses NO descriptor (Contract.gamma = 0 for P4 in simulator.py), so a
     shared logbook keyed by descriptor classes has nothing to train on: the
     tau axis at P4 is dead BY CONTRACT SEMANTICS, not by a wiring accident.
     This check proves it operationally: campaigns at tau in {0, .5, 1} with
     everything else fixed produce numerically identical outcome vectors.

  B. INFORMATION-REDUNDANCY PROBE -- at P2, where the logbook does have
     content, how much cross-candidate cost information does the shared
     surrogate carry BEYOND what each seat already has for free?
       truth      : log cost of the ideal config per candidate/fidelity
       own (free) : R's own charge history = per-fidelity mean charge scaled
                    by the candidate's known relative size (rel = nelec-law);
                    R has this in EVERY arm including DTDE
       surrogate  : asymptotic best a P2 class-keyed logbook can know =
                    class-mean of truth (P2 size x memory-bin classes)
       broker     : H's disclosed runtime prediction at P2 precision
     Reported as variance explained (R^2) of each predictor, per fidelity,
     averaged over worlds. If own ~ surrogate, the logbook is redundant.

  C. DENSE TAU TRANSECTS at P2 -- tau in linspace(0,1,21) at eps in
     {0, 0.5, 1}, component metrics per point, so any real (small) tau
     gradient is resolved instead of being hidden by a coarse grid.

All numbers are SIMULATED UNITS (twin from simulator.py).
"""
import argparse
import json
import os
from pathlib import Path

import numpy as np

import sys
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "prior_predictive"))
import simulator as S  # noqa: E402
import surface as SF  # noqa: E402

CARDS = ["base", "strong_coupling", "adversarial"]


def part_a(nworld=6):
    """P4 identity: tau has no channel at P4 -> outputs bit-identical."""
    out = {"identical": True, "max_abs_diff": 0.0, "pairs": []}
    for i in range(nworld):
        w = S.sample_world(CARDS[i % 3], i)
        ref = SF.run_mix(w, 0.0, 0.75, "P4")
        for tau in (0.5, 1.0):
            r = SF.run_mix(w, tau, 0.75, "P4")
            d = max(float(np.max(np.abs(r[k] - ref[k])))
                    for k in ("labels_per_nh", "nh_first", "fail_rate",
                              "r_mi_auc", "h_rank_corr"))
            out["max_abs_diff"] = max(out["max_abs_diff"], d)
            out["pairs"].append({"world": i, "tau": tau, "max_diff": d})
            if d > 0:
                out["identical"] = False
    return out


def part_b(nworld=60):
    """Variance explained by each cost-information channel, P2, per fid."""
    r2 = {"own": [], "surrogate": [], "broker": []}
    rng = np.random.default_rng(7)
    rel = (S.CAND["nelec"] / 38.0) ** 2.5
    for i in range(nworld):
        w = S.sample_world(CARDS[i % 3], i)
        cls = S.world_classes(w, "P2")
        for f in (1, 2, 3):
            wk = S.base_work(w, f)
            eff = S.eff_matrix(w, f)
            truth = np.log(np.maximum((wk[:, None] / eff).min(1), 1e-3))
            vt = np.var(truth)
            if vt < 1e-9:
                continue

            def _r2(pred):
                a = np.polyfit(pred, truth, 1)
                fit = a[0] * pred + a[1]
                return float(1.0 - np.var(truth - fit) / vt)

            own = np.log(rel)                       # per-fid const drops out
            surr = np.array([truth[cls == cls[c]].mean()
                             for c in range(S.C)])  # class-mean (asymptote)
            brok = truth + rng.normal(0, 0.5, S.C)  # P2 cost_sd = 0.5
            r2["own"].append(_r2(own))
            r2["surrogate"].append(_r2(surr))
            r2["broker"].append(_r2(brok))
    return {k: {"mean": float(np.mean(v)), "sd": float(np.std(v))}
            for k, v in r2.items()}


def _transect_task(arg):
    wid, taus, eps, level = arg
    w = S.sample_world(CARDS[wid % 3], wid)
    base4 = SF.run_mix(w, 0.0, 0.0, "P4")
    row = {}
    for tau in taus:
        res = SF.run_mix(w, float(tau), float(eps), level)
        row[float(tau)] = SF.eval_point(res, base4)
    return wid, eps, row


def part_c(nworld=120, npts=21, procs=None, level="P2"):
    taus = [round(float(t), 4) for t in np.linspace(0, 1, npts)]
    tasks = [(wid, taus, eps, level)
             for eps in (0.0, 0.5, 1.0) for wid in range(nworld)]
    procs = procs or os.cpu_count()
    if procs > 1:
        import multiprocessing as mp
        with mp.Pool(procs) as pool:
            res = pool.map(_transect_task, tasks, chunksize=2)
    else:
        res = [_transect_task(t) for t in tasks]
    agg = {}
    for wid, eps, row in res:
        for tau, d in row.items():
            agg.setdefault((eps, tau), []).append(d)
    keys = ("win_win", "leak_ok", "labels_ratio", "pw_rate",
            "r_id_acc", "r_mi_auc", "h_rank_corr", "fail_rate")
    out = {}
    for (eps, tau), lst in sorted(agg.items()):
        out[f"{eps}|{tau}"] = {"eps": eps, "tau": tau,
                               **{k: float(np.mean([x[k] for x in lst]))
                                  for k in keys}}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worlds", type=int, default=120)
    ap.add_argument("--npts", type=int, default=21)
    ap.add_argument("--procs", type=int, default=os.cpu_count())
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    if args.smoke:
        args.worlds, args.npts, args.procs = 4, 3, 1
    a = part_a(3 if args.smoke else 6)
    print(f"A. P4 identity: identical={a['identical']} "
          f"max_diff={a['max_abs_diff']:.2e}")
    b = part_b(6 if args.smoke else 60)
    print("B. cost-information R^2 (P2):",
          {k: round(v["mean"], 3) for k, v in b.items()})
    c = part_c(args.worlds, args.npts, args.procs)
    outp = HERE / "results" / "tau_diagnostic.json"
    with open(outp, "w") as fh:
        json.dump({"meta": {"worlds": args.worlds, "npts": args.npts,
                            "note": "SIMULATED UNITS"},
                   "p4_identity": a, "info_r2": b, "transects": c}, fh,
                  indent=1)
    print(f"wrote {outp}")


if __name__ == "__main__":
    main()

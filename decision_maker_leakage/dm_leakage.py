#!/usr/bin/env python3
"""Finding-5 study (2026-09-08): leakage is
decision-maker-dependent; define and analyze it.

DEFINITION. For a fixed information contract m (topology x disclosure
level), the transcript an attacker sees is generated jointly by the
mechanism AND the decision policy pi that drives the queries. Leakage is
therefore a functional of both:

    L_c(m, pi)  for channel c in the six preregistered channels.

A single-policy audit certifies L_c(m, pi_audit) <= limit_c for one
pi_audit; a POLICY-ROBUST audit certifies

    L_hat_c(m, Pi) = max_{pi in Pi} L_c(m, pi) <= limit_c

over a declared policy class Pi. The 2026-09-02 LLM run showed the gap is
real (CEDT-P3 membership AUC 0.85 under an LLM vs 0.60 scripted). This
script measures L_c(m, pi) for five decision-maker archetypes spanning
the behaviors observed in the scripted/LLM/tool runs, on identical worlds
and noise fields, and reports which contracts survive a single-policy
audit but FAIL the policy-robust audit.

Archetypes (R seat; same information set, same contract enforcement):
  greedy       - the preregistered acquisition argmax (audit policy).
  depth_first  - commits to a started candidate until resolved (the
                 LLM ladder-climbing behavior).
  repeat_prone - anchoring: multiplicative stickiness on the previous
                 pick (the repeated-query concentration behavior).
  thompson     - posterior-sampling explorer (the tool-delegation
                 behavior preferred ~3:1 by LLM agents).
  eps_greedy   - 25%-random explorer (worst-case erratic operator).

All node-hours are simulated units.
"""
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

CHANNELS = ["r_mi_auc", "r_comp_adv", "r_id_acc",
            "h_tel_auc", "h_hw_adv", "h_rank_corr"]
LIMVALS = dict(r_mi_auc=0.60, r_comp_adv=0.10, r_id_acc=1 / 30 + 0.05,
               h_tel_auc=0.60, h_hw_adv=0.10, h_rank_corr=0.20)
CONDS = [("CEDT_P2", "CEDT", "P2", None),
         ("CEDT_P3_eps2", "CEDT", "P3", 2.0),
         ("CTDE_P3_eps2", "CTDE", "P3", 2.0),
         ("CEDT_P4", "CEDT", "P4", None)]


def make_policy(name):
    state = {"last": None}

    def pol(acq, value, cost_est, mu, prec, fid_done, dead, qualified, t):
        S, C = acq.shape
        if state["last"] is None or state["last"].shape[0] != S:
            state["last"] = np.full(S, -1)
        greedy = acq.argmax(1)
        if name == "greedy":
            pick = greedy
        elif name == "depth_first":
            started = (fid_done >= 1) & (acq > 1e-12)
            key = np.where(started, fid_done + 1e-6 * acq, -1.0)
            pick = np.where(started.any(1), key.argmax(1), greedy)
        elif name == "repeat_prone":
            bonus = np.ones_like(acq)
            rows = np.arange(S)
            last = state["last"]
            ok = last >= 0
            bonus[rows[ok], last[ok]] = 4.0
            pick = (acq * bonus).argmax(1)
        elif name == "thompson":
            rng = np.random.default_rng(7_000_000 + t)
            g = mu + rng.standard_normal((S, C)) / np.sqrt(prec)
            val = ((g >= sim.GAP_LO) & (g <= sim.GAP_HI)) * (acq > 1e-12)
            samp = val / (np.maximum(cost_est, 0.02) + sim.OVERHEAD_NH)
            pick = np.where(samp.max(1) > 0, samp.argmax(1), greedy)
        elif name == "eps_greedy":
            rng = np.random.default_rng(8_000_000 + t)
            elig = acq > 1e-12
            r = rng.random((S, C)) * elig
            rand_pick = np.where(elig.any(1), r.argmax(1), greedy)
            explore = rng.random(S) < 0.25
            pick = np.where(explore, rand_pick, greedy)
        else:
            raise ValueError(name)
        # never turn a movable seed into a no-move: fall back to greedy
        rows = np.arange(S)
        bad = (acq[rows, pick] <= 1e-12) & (acq[rows, greedy] > 1e-12)
        pick = np.where(bad, greedy, pick)
        state["last"] = pick
        return pick

    return pol


def run_one(args):
    card, wid, pol_name = args
    w = sim.sample_world(card, wid)
    sim.R_PICK_POLICY = None if pol_name == "greedy" \
        else make_policy(pol_name)
    res = {}
    for name, topo, lvl, eps in CONDS:
        r = sim.run_campaign(w, topo, sim.Contract(lvl, eps))
        res[name] = {c: float(np.mean(r[c])) for c in CHANNELS}
        res[name]["labels_per_nh"] = float(np.mean(r["labels_per_nh"]))
        res[name]["found"] = float(np.mean(r["found"]))
        res[name]["nh_first"] = float(np.mean(r["nh_first"]))
    sim.R_PICK_POLICY = None
    return pol_name, res


def main():
    worlds = int(os.environ.get("DM_WORLDS", "200"))
    pols = ["greedy", "depth_first", "repeat_prone", "thompson",
            "eps_greedy"]
    tasks = [("base", wid, p) for wid in range(worlds) for p in pols]
    with Pool(os.cpu_count()) as pool:
        out = pool.map(run_one, tasks, chunksize=4)
    agg = {p: {n: {k: [] for k in out[0][1][CONDS[0][0]]}
               for n, *_ in CONDS} for p in pols}
    for pol_name, res in out:
        for n, d in res.items():
            for k, v in d.items():
                agg[pol_name][n][k].append(v)
    table = {p: {n: {k: float(np.mean(v)) for k, v in d.items()}
                 for n, d in conds.items()}
             for p, conds in agg.items()}
    # per-world pass rates: single-policy vs policy-robust
    audit = {}
    for n, *_ in CONDS:
        per_pol_pass = {}
        for p in pols:
            ok = []
            for wi in range(worlds):
                vals = {c: agg[p][n][c][wi] for c in CHANNELS}
                ok.append(all(vals[c] <= LIMVALS[c] for c in CHANNELS))
            per_pol_pass[p] = float(np.mean(ok))
        robust = []
        for wi in range(worlds):
            worst = {c: max(agg[p][n][c][wi] for p in pols)
                     for c in CHANNELS}
            robust.append(all(worst[c] <= LIMVALS[c] for c in CHANNELS))
        audit[n] = dict(single_policy=per_pol_pass,
                        policy_robust=float(np.mean(robust)))
    json.dump(dict(worlds=worlds, table=table, audit=audit,
                   limits=LIMVALS),
              open(HERE / "dm_leakage.json", "w"), indent=1)
    for n, a in audit.items():
        sp = " ".join(f"{p}={v:.2f}" for p, v in a["single_policy"].items())
        print(f"{n}: robust={a['policy_robust']:.2f} | {sp}")


if __name__ == "__main__":
    main()

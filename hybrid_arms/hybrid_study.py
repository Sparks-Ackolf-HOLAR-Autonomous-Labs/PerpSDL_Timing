#!/usr/bin/env python3
"""Hybrid-mix / ALT / collusion arm study (2026-09-09):

  at least one model for each of DTDE, CTDE, CEDT, and CTCE in the
  campaign, plus a hybrid-mix model,
  + future-work item 4 (ALT negotiation baseline, collusion variants).

Arms (all on identical worlds/seeds/noise, CRN, hard budget cap):
  CTCE_P0            full-information ceiling
  DTDE_P4            no-sharing baseline (outside option)
  CTDE_P2/P3/P4      shared surrogate, local execution
  CEDT_P2/P3/P4      broker-matched execution, independent training
  HYB_P2/P3          hybrid-mix: shared surrogate feeds R's cost
                     estimates AND the broker matches execution configs
                     (both channels open, both leak). HYB_P4 == CEDT_P4
                     by construction (gamma=0 kills the surrogate), so
                     it is not run separately.
  ALT_P4             negotiation baseline: only price quotes cross
  *_collude          broker-H collusion: R leakage scored at
                     gamma_attack=1 (pre-DP class stream), utility
                     unchanged

Grading: frozen metrics (T20 R margin, 15% H margin) and the redesigned
metrics (PW60 paired win-rate + package H margins), on
  (a) the wide base prior at x1 task scale, and
  (b) the measurement-informed posterior (Stage-2 + 81-job pilot fits)
      at x100 scale — the operating point located by scale_validation/.

All node-hours are simulated units.
"""
import json
import os
import sys
import zlib
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "prior_predictive"))
os.environ.setdefault("MPT_HARD_CAP", "1")
import simulator as sim  # noqa: E402

FIT = json.load(open(HERE.parent / "stage2_twin_fit" / "twin_fit.json"))
PFIT = json.load(open(HERE.parent / "pilot" / "results" / "pilot_fit.json"))
A_MEAS = FIT["measured_fit"]["A"]
AF_EMP = np.array([FIT["min_call_node_hours"], A_MEAS["F1"], A_MEAS["F2"],
                   A_MEAS["F3"], A_MEAS["F4"] + 0.1 * A_MEAS["F2"]])
P_E = FIT["measured_fit"]["p_e"]
SD_LOG = FIT["measured_fit"]["resid_sd_log"]

sim.PRIOR_CARDS["posterior"] = dict(
    s_mu=PFIT["parallel_efficiency_exponent_s"], s_sd=0.05,
    quirk_sd=PFIT["quirk_sd_log"], pm_lo=0.05, pm_hi=0.30,
    burst_lo=0.05, burst_hi=0.25, beta0_mu=-4.2, beta0_sd=0.4, atk=1.0)

SCALE = 1.0
_orig_sample = sim.sample_world
_orig_mem = sim.mem_per_node


def sample_world_post(card, wid):
    w = _orig_sample(card, wid)
    rng = np.random.default_rng(
        zlib.crc32(f"post:{card}:{int(wid)}".encode()))
    w["A"] = AF_EMP * SCALE * np.exp(rng.normal(0, SD_LOG))
    w["p_e"] = np.clip(rng.normal(P_E, 0.1), 0.9, 1.5)
    w["memq"] = float(np.exp(rng.normal(0, 0.05)))
    w["rho"] = np.exp(rng.normal(0, 0.15, sim.C))
    return w


def mem_per_node_post(w, fid):
    grow = (sim.NK[fid] / 36.0) ** 0.3
    m = (2.1 * (sim.CAND["nelec"][:, None] / 38.0) ** 0.5 * grow
         * w["memq"] * w["rho"][:, None]
         / (sim.C_NODES[None, :] * sim.C_POOLS[None, :] ** 0.4)) + 0.1
    return m * SCALE ** 0.5


# (name, topology, level, eps, collude)
CONDS = [
    ("CTCE_P0", "CTCE", "P0", None, False),
    ("DTDE_P4", "DTDE", "P4", None, False),
    ("CTDE_P2", "CTDE", "P2", None, False),
    ("CTDE_P3_eps2", "CTDE", "P3", 2.0, False),
    ("CTDE_P4", "CTDE", "P4", None, False),
    ("CEDT_P2", "CEDT", "P2", None, False),
    ("CEDT_P3_eps2", "CEDT", "P3", 2.0, False),
    ("CEDT_P4", "CEDT", "P4", None, False),
    ("HYB_P2", "HYB", "P2", None, False),
    ("HYB_P3_eps2", "HYB", "P3", 2.0, False),
    ("ALT_P4", "ALT", "P4", None, False),
    ("CEDT_P3_eps2_collude", "CEDT", "P3", 2.0, True),
    ("HYB_P3_eps2_collude", "HYB", "P3", 2.0, True),
]


def make_contract(lvl, eps, collude):
    c = sim.Contract(lvl if lvl != "P0" else "P1", eps)
    if lvl == "P0":
        c.level, c.gamma, c.cost_sd = "P0", 1.0, 0.0
        c.classes, c.nclasses = np.arange(sim.C), sim.C
    if collude:
        c.gamma_attack = 1.0
    return c


def run_one(args):
    card, wid = args
    w = sim.sample_world(card, wid)
    res = {name: sim.run_campaign(w, topo, make_contract(lvl, eps, col))
           for name, topo, lvl, eps, col in CONDS}
    rows = sim.eval_world(res)
    for name, d in rows.items():
        d["card"], d["world"] = card, wid
    return rows


def main():
    global SCALE
    worlds = int(os.environ.get("HYB_WORLDS", "300"))
    procs = int(os.environ.get("HYB_PROCS", os.cpu_count()))
    out = {"worlds": worlds, "conds": [c[0] for c in CONDS]}

    with Pool(procs) as p:
        rows_x1 = p.map(run_one, [("base", i) for i in range(worlds)],
                        chunksize=2)
    out["wide_prior_x1"] = rows_x1

    SCALE = 100.0
    sim.sample_world = sample_world_post
    sim.mem_per_node = mem_per_node_post
    sim.OVERHEAD_NH = 0.02
    with Pool(procs) as p:
        rows_post = p.map(run_one, [("posterior", i) for i in range(worlds)],
                          chunksize=2)
    out["posterior_x100"] = rows_post

    json.dump(out, open(HERE / "hybrid_results.json", "w"))

    for setting in ("wide_prior_x1", "posterior_x100"):
        rows = out[setting]
        print(f"\n== {setting} ({worlds} worlds, 30 paired seeds) ==")
        print(f"{'condition':22s} {'P(ww froz)':>10} {'P(ww redesign)':>14} "
              f"{'pw_rate':>8} {'lnh_ratio':>9} {'P(leak)':>8} {'mi':>6} "
              f"{'rank':>6}")
        for name, _, _, _, _ in CONDS:
            rs = [r[name] for r in rows]
            base = [r["DTDE_P4"] for r in rows]
            lnhr = np.mean([r["labels_per_nh"] / max(b["labels_per_nh"], 1e-9)
                            for r, b in zip(rs, base)])
            print(f"{name:22s} {np.mean([r['win_win'] for r in rs]):10.3f} "
                  f"{np.mean([r['win_win_redesigned'] for r in rs]):14.3f} "
                  f"{np.mean([r['pw_rate'] for r in rs]):8.3f} "
                  f"{lnhr:9.3f} "
                  f"{np.mean([r['leak_ok'] for r in rs]):8.3f} "
                  f"{np.mean([r['r_mi_auc'] for r in rs]):6.3f} "
                  f"{np.mean([r['h_rank_corr'] for r in rs]):6.3f}")


if __name__ == "__main__":
    main()

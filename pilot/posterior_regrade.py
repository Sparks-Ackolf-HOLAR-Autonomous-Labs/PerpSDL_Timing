#!/usr/bin/env python3
"""Post-pilot posterior re-grade (the step the governance analysis called
the remaining path: collapse the prior with measurements, then re-grade).

Patches the twin with everything measured so far and re-grades the main
grid at the recommended operating scales (x10 / x100 / x300 of the
measured MX2 ladder):

  from the DFT campaign + SOC (Stage 2): cost amplitudes, p_e = 1.20,
    residual sd, dead memory channel;
  from the 81-job pilot (pilot_fit.json): parallel-efficiency exponent
    s = 0.425 +/- 0.05 (prior 0.65 +/- 0.10), config-quirk spread 0.061
    (prior 0.18), repeat/contention noise 0.076 -> burst U(0.05, 0.25),
    failure base rate 0/81 -> beta0 = logit(0.015) +/- 0.4.

Win-win graded under both the frozen preregistered metrics and the
renegotiated execution-layer package from ../governance_regrade/.
Simulated units; the posterior card is a measurement-informed belief,
not a certified posterior distribution.
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
PFIT = json.load(open(HERE / "results" / "pilot_fit.json"))
A_MEAS = FIT["measured_fit"]["A"]
AF_EMP = np.array([FIT["min_call_node_hours"], A_MEAS["F1"], A_MEAS["F2"],
                   A_MEAS["F3"], A_MEAS["F4"] + 0.1 * A_MEAS["F2"]])
P_E = FIT["measured_fit"]["p_e"]
SD_LOG = FIT["measured_fit"]["resid_sd_log"]
S_HAT = PFIT["parallel_efficiency_exponent_s"]
QUIRK_SD = PFIT["quirk_sd_log"]
SCALE = 100.0

# posterior card: pilot-informed
sim.PRIOR_CARDS["posterior"] = dict(
    s_mu=S_HAT, s_sd=0.05, quirk_sd=QUIRK_SD, pm_lo=0.05, pm_hi=0.30,
    burst_lo=0.05, burst_hi=0.25, beta0_mu=-4.2, beta0_sd=0.4, atk=1.0)

_orig_sample = sim.sample_world


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


def run_one(args):
    card, wid = args
    return sim.run_world((card, wid, sim.CONDITIONS_MAIN))


def regrade(rows, r_metric, g_r, h_labels, h_fail):
    counts = {}
    for _, summary in rows:
        base = summary["DTDE_P4"]
        for name, r in summary.items():
            if r_metric == "time":
                gA = (r["mean_nh_first"] <= g_r * base["mean_nh_first"]
                      and r["found_rate"] >= base["found_rate"] - 1e-9)
                gB = r["mean_qual"] >= base["mean_qual"] + 1.0
                r_ok = ((gA or gB)
                        and r["validity"] >= base["validity"] - 0.01)
            else:
                r_ok = (r["labels_per_nh"] >= (2 - g_r)
                        * base["labels_per_nh"]
                        and r["found_rate"] >= base["found_rate"] - 1e-9
                        and r["validity"] >= base["validity"] - 0.01)
            h_ok = (r["labels_per_nh"] >= h_labels * base["labels_per_nh"]
                    and r["fail_rate"] <= base["fail_rate"] + h_fail
                    and r["memfail_p95"] <= base["memfail_p95"] + 1e-9)
            ww = r_ok and h_ok and r["leak_ok"] >= 1.0
            c = counts.setdefault(name, [0, 0])
            c[0] += 1
            c[1] += ww
    return {n: c[1] / c[0] for n, c in counts.items()}


def main():
    global SCALE
    worlds = int(os.environ.get("POST_WORLDS", "300"))
    sim.sample_world = sample_world_post
    sim.mem_per_node = mem_per_node_post
    sim.OVERHEAD_NH = 0.02
    out = {}
    for sc in (10.0, 100.0, 300.0):
        SCALE = sc
        with Pool(os.cpu_count()) as p:
            rows = p.map(run_one,
                         [("posterior", wid) for wid in range(worlds)],
                         chunksize=4)
        out[f"scale_{sc:g}"] = dict(
            frozen=regrade(rows, "time", 0.80, 1.15, 0.02),
            package=regrade(rows, "exec", 0.90, 1.05, 0.04))
        f = out[f"scale_{sc:g}"]
        for g in ("frozen", "package"):
            best = max(((n, v) for n, v in f[g].items()
                        if n != "CTCE_P0"), key=lambda t: t[1])
            print(f"scale {sc:g} {g}: best {best[0]} = {best[1]:.3f}",
                  flush=True)
    json.dump(dict(worlds=worlds, posterior_card=sim.PRIOR_CARDS[
        "posterior"], results=out),
        open(HERE / "results" / "posterior_regrade.json", "w"), indent=1)


if __name__ == "__main__":
    main()

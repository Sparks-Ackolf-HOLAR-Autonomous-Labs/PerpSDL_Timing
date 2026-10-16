#!/usr/bin/env python3
"""Stage-2 parametric twin fit: calibrate the prior-predictive cost model
against the measured QE calls.

Fits the twin's own functional family (simulator.py):

    nh  = A_stage * (nelec/38)^p_e            [p_k NOT identifiable: every
                                               stage ran one fixed k-grid,
                                               so nk is confounded with the
                                               stage constant]
    mem = m0 * (nelec/38)^p_m + m_base        [per rank; single config only]

on log scale with shared exponents and per-stage amplitudes, and reports
the calibration against the prior card (A = AF*[stage], p_e ~ N(2.5,0.2),
mem 30*(nelec/38)^2 + 8).

Honest identifiability notes are emitted with the results: the campaign
ran ONE execution config (16 ranks / 4 pools), so parallel-efficiency,
pool-mismatch, and p_k parameters stay at their priors; the randomized
81-job pilot remains the instrument for those.
"""
import csv
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
NODE_CORES = 64.0

PRIOR = dict(p_e=2.5, p_k=1.0,
             AF={"F1": 1.2, "F2": 12.0, "F3": 8.0, "F4SCF": 8.0,
                 "F4": 40.0},
             mem_m0=30.0, mem_p=2.0, mem_base=8.0)


def load(scalar_only=True):
    rows = [r for r in csv.DictReader(open(HERE / "qe_calls.csv"))]
    for r in rows:
        for k in ("nelec", "wall_s", "node_hours", "ecut_ry"):
            r[k] = float(r[k]) if r[k] else None
        for k in ("nat", "nk", "soc", "restarts", "kgrid"):
            r[k] = int(r[k])
        r["mem_gb"] = float(r["mem_gb"]) if r["mem_gb"] else None
    if scalar_only:
        rows = [r for r in rows if not r["soc"]]
    return [r for r in rows if r["nelec"] and r["node_hours"]]


def fit_loglinear(rows, stages):
    """log nh = log A_stage + p_e*log(nelec/38); least squares."""
    rows = [r for r in rows if r["stage"] in stages]
    y = np.log([r["node_hours"] for r in rows])
    x_e = np.log([r["nelec"] / 38.0 for r in rows])
    stage_names = sorted({r["stage"] for r in rows})
    X = np.zeros((len(rows), 1 + len(stage_names)))
    X[:, 0] = x_e
    for i, r in enumerate(rows):
        X[i, 1 + stage_names.index(r["stage"])] = 1.0
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    r2 = 1 - resid.var() / y.var()
    return dict(p_e=round(float(beta[0]), 3),
                A={s: round(float(np.exp(beta[1 + i])), 6)
                   for i, s in enumerate(stage_names)},
                resid_sd_log=round(float(resid.std()), 3),
                r2=round(float(r2), 3), n=len(rows))


def fit_mem(rows):
    """mem = m0*(nelec/38)^p + base, nonlinear grid + lsq on (m0, base)."""
    rows = [r for r in rows if r["mem_gb"] and r["exe"].startswith("pw")]
    ne = np.array([r["nelec"] / 38.0 for r in rows])
    kf = np.array([(r["nk"] / 36.0) ** 0.3 for r in rows])  # prior nk shape
    m = np.array([r["mem_gb"] for r in rows])
    best = None
    for p in np.arange(0.5, 3.51, 0.05):
        X = np.stack([ne ** p * kf, np.ones_like(ne)], 1)
        beta, *_ = np.linalg.lstsq(X, m, rcond=None)
        rss = ((m - X @ beta) ** 2).sum()
        if best is None or rss < best[0]:
            best = (rss, p, beta)
    rss, p, beta = best
    r2 = 1 - rss / ((m - m.mean()) ** 2).sum()
    return dict(mem_m0=round(float(beta[0]), 4), mem_p=round(float(p), 2),
                mem_base=round(float(beta[1]), 4), r2=round(float(r2), 3),
                n=len(rows),
                note="per-rank RSS at 16 ranks/4 pools; the twin's "
                     "mem_per_node divides by nodes*pools^0.4 which this "
                     "single-config dataset cannot identify")


def main():
    rows = load()
    fit = fit_loglinear(rows, {"F1", "F2", "F3", "F4SCF", "F4"})
    memfit = fit_mem(rows)
    # calibration ratios prior/measured at the reference candidate
    ratios = {s: round(PRIOR["AF"][s] / fit["A"][s], 1)
              for s in fit["A"] if s in PRIOR["AF"]}
    # per-job overhead actually measured: mpirun+setup, approximated by the
    # min wall over trivial calls, in node-hours at 16/64 cores
    min_nh = min(r["node_hours"] for r in rows)
    out = dict(
        measured_fit=fit, measured_mem=memfit,
        prior_card=PRIOR,
        prior_over_measured_A=ratios,
        min_call_node_hours=min_nh,
        identifiability=dict(
            p_k="NOT identifiable: one fixed k-grid per stage (nk "
                "confounded with A_stage); prior p_k=1.0 carried",
            parallel_efficiency="NOT identifiable: single config "
                "(16 ranks, 4 pools); pilot bundle remains the instrument",
            contention="NOT identifiable: dedicated allocation, no "
                "co-tenant variation observed"),
        soc_rows_available=sum(1 for r in load(scalar_only=False)
                               if r["soc"]))
    json.dump(out, open(HERE / "twin_fit.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

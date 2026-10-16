#!/usr/bin/env python3
"""Measurement-calibrated pre-study for live comparison No. 2 (packing-based).

Purpose (written 2026-09-11, BEFORE cofit probe 1940907 was collected):
  1. Register a prediction for the cofit gate (concurrent 16+16 vs the
     measured 8,645 s sequential 32-rank baseline for MoSe2_2H + WTe2_2H
     6x6) so the probe grades the model, not vice versa.
  2. Find the task scale (6x6 / 7x7 / 8x8) at which the memory bit
     actually changes packing and billing, before spending the live
     budget: at 6x6 streams may be core-limited (4x16 ranks) with memory
     slack, in which case the bit has no surface and comparison No. 2 as
     drafted would be a null by construction at that scale.
  3. Check the power of 20 paired seeds under PW60 + the 1.05x H margin.

Everything is anchored to measured quantities (sources in ANCHORS below);
the only free choices are transfer jitters, swept as world priors. All
node-hours are simulated units.

Billing model (proposed prereg amendment, see RESULTS.md): TRES-style
per-core-equivalent — a job is charged
    wall * max(ranks/64, reserved_GB/380)
in node-hour units. Reserved memory blocks other users' cores on a
co-scheduled node, so over-reservation is a real cost; this is standard
SLURM TRES billing, and it is the accounting under which worst-case
provisioning (DTDE) pays for its ignorance. Facility throughput
(labels per makespan node-hour) is reported as the secondary accounting.

Arms (identical physics, identical candidate order within a pair;
16 MPI ranks per job, npool by class rule — probe 1928420):
  DTDE      : H sees calc class only -> reserves the population-max RAM
              (x1.10 model uncertainty) for every job.
  CEDT-bit  : broker gets 1 preregistered bit (RAM above/below the
              population median) -> reserves the bit-group max (x1.05).
  CEDT-full : exact RAM disclosed (x1.05) — P2-like ceiling, bounds what
              the single bit leaves on the table.
"""
import json, math, os, random
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MPT = os.path.abspath(os.path.join(HERE, "..", ".."))

# ---------------------------------------------------------------- anchors
# Measured, with sources:
NODE_CORES, NODE_GB = 64, 380.0            # grn061
MEM_BUDGET = 0.85 * NODE_GB                # 15% packing safety margin (prereg)
RANKS = 16                                 # per-job streams (cofit design)
SEQ_BASELINE_S = 3777.0 + 4868.0           # probe 1928420: MoSe2+WTe2 6x6 @32r
ANCHORS_W32 = {("TiS2_1T", 6): 1200.0,     # probe 1928420, lean walls, 32 ranks
               ("MoSe2_2H", 6): 3777.0, ("WTe2_2H", 6): 4868.0}
ANCHORS_RAM = {"1T": 30.9, "2H": (42.6 + 52.6) / 2.0}   # GB total @6x6 lean
RAM_SPREAD_SAMPLES = (42.6, 52.6)          # iso-electron spread anchor (23%)
# World priors (transfer uncertainty around measured values):
#   s      rank-scaling exponent, wall(16)=wall(32)*2**s   [measured 0.425]
#   c      co-tenant contention per extra stream           [measured 0.06-0.11]
#   p_w    wall scale exponent in electrons                [measured ~1.98 6x6->8x8]
#   p_r    RAM  scale exponent in electrons                [measured 1.65-1.68]
#   sig_w  lognormal jitter on the 1x1->big-cell wall multiplier transfer
#   sig_r  lognormal sigma of per-candidate iso-electron RAM spread
PRIORS = dict(s=(0.35, 0.50), c=(0.05, 0.12), p_w=(1.8, 2.2),
              p_r=(1.55, 1.75), sig_w=0.15, sig_r=(0.09, 0.15), rho=0.5)

N_WORLDS = int(os.environ.get("MPT_WORLDS", 400))
N_PAIRS = int(os.environ.get("MPT_PAIRS", 20))
N_CALLS = int(os.environ.get("MPT_CALLS", 12))
SCALES = [int(x) for x in os.environ.get("MPT_SCALES", "6,7,8").split(",")]
OUT_TAG = os.environ.get("MPT_TAG", "")     # suffix for the results file

# ------------------------------------------------- candidates (measured)
def load_candidates():
    """29 candidates with measured 1x1 F2 wall multipliers + qualifier flags."""
    recs = {}
    with open(os.path.join(MPT, "dft_campaign", "results", "outcomes.jsonl")) as f:
        for line in f:
            x = json.loads(line)
            if x["candidate"] == "HfSe2_2H":
                continue                    # never relaxed; excluded (prereg)
            old = recs.get(x["candidate"])
            if old is None or (old.get("qualifier") is None):
                recs[x["candidate"]] = dict(
                    name=x["candidate"], phase=x["phase"],
                    f2wall=x["stages"]["F2"]["wall_s"],
                    qualifier=bool(x.get("qualifier")))
    cands = sorted(recs.values(), key=lambda r: r["name"])
    for ph in ("1T", "2H"):
        walls = [c["f2wall"] for c in cands if c["phase"] == ph]
        mean = sum(walls) / len(walls)
        for c in cands:
            if c["phase"] == ph:
                c["m_wall"] = c["f2wall"] / mean   # measured multiplier
    return cands

def base_walls(cands):
    """Phase base walls at 6x6/32r implied by each measured anchor; the
    spread across anchors is the transfer cross-check reported in RESULTS."""
    implied = {}
    for (name, _), w in ANCHORS_W32.items():
        c = next(c for c in cands if c["name"] == name)
        implied.setdefault(c["phase"], []).append(w / c["m_wall"])
    return ({ph: sum(v) / len(v) for ph, v in implied.items()},
            {ph: v for ph, v in implied.items()})

# ------------------------------------------------------------- scheduler
def run_schedule(work, reserved, max_streams, c):
    """FIFO event-driven single-node schedule. work: uncontended seconds at
    16 ranks. Returns (start, completion, makespan). Contention: active
    streams progress at rate 1/(1 + c*(n_active-1))."""
    n = len(work)
    start, comp = [0.0] * n, [0.0] * n
    t, q, active = 0.0, list(range(n)), []          # active: [idx, remaining]
    def launch():
        while q and len(active) < max_streams and \
                sum(reserved[a[0]] for a in active) + reserved[q[0]] <= MEM_BUDGET:
            j = q.pop(0); active.append([j, work[j]]); start[j] = t
    launch()
    while active:
        rate = 1.0 / (1.0 + c * (len(active) - 1))
        dt = min(a[1] for a in active) / rate
        t += dt
        for a in active:
            a[1] -= dt * rate
        for a in [a for a in active if a[1] <= 1e-9]:
            comp[a[0]] = t; active.remove(a)
        launch()
    return start, comp, t

def charges(start, comp, reserved):
    """TRES per-core-equivalent node-hours per job."""
    return [(comp[j] - start[j]) / 3600.0 *
            max(RANKS / NODE_CORES, reserved[j] / NODE_GB)
            for j in range(len(start))]

def charge_to_first_qualifier(start, comp, ch, quals):
    tq = min((comp[j] for j in range(len(comp)) if quals[j]), default=None)
    if tq is None:
        return sum(ch)                               # censored at campaign end
    acc = 0.0
    for j in range(len(ch)):                          # linear accrual
        dur = comp[j] - start[j]
        if dur <= 0:
            continue
        acc += ch[j] * max(0.0, min(comp[j], tq) - start[j]) / dur
    return acc

# ------------------------------------------------------------------ main
def main():
    rng = np.random.default_rng(20260911)
    cands = load_candidates()
    base_w, implied = base_walls(cands)
    n_c = len(cands)
    is2H = np.array([c["phase"] == "2H" for c in cands])
    m_wall = np.array([c["m_wall"] for c in cands])
    quals = np.array([c["qualifier"] for c in cands])
    out = {"anchor_crosscheck": {ph: [round(v, 0) for v in vs]
                                 for ph, vs in implied.items()},
           "base_walls_6x6_32r": {k: round(v, 0) for k, v in base_w.items()},
           "scales": {}, "cofit_gate_prediction": {}}

    gate_savings = []
    for w in range(N_WORLDS):
        # ---- world parameters
        s = rng.uniform(*PRIORS["s"]); c_cont = rng.uniform(*PRIORS["c"])
        p_w = rng.uniform(*PRIORS["p_w"]); p_r = rng.uniform(*PRIORS["p_r"])
        sig_r = rng.uniform(*PRIORS["sig_r"])
        z_w = rng.standard_normal(n_c); z_r = rng.standard_normal(n_c)
        jit_w = np.exp(PRIORS["sig_w"] * z_w)
        m_ram = np.exp(sig_r * (PRIORS["rho"] * z_w +
                                math.sqrt(1 - PRIORS["rho"] ** 2) * z_r))
        # ---- cofit gate prediction (6x6, the two measured 2H anchors)
        w16 = np.array([3777.0, 4868.0]) * 2 ** s
        _, _, mk = run_schedule(list(w16), [50.0, 50.0], 2, c_cont)
        gate_savings.append(1.0 - mk / SEQ_BASELINE_S)

        for n_sc in SCALES:
            sc_w = (n_sc * n_sc / 36.0) ** p_w
            sc_r = (n_sc * n_sc / 36.0) ** p_r
            wall32 = np.where(is2H, base_w["2H"], base_w["1T"]) * m_wall * jit_w * sc_w
            work16 = wall32 * 2 ** s
            ram = np.where(is2H, ANCHORS_RAM["2H"], ANCHORS_RAM["1T"]) * m_ram * sc_r
            bit = ram > np.median(ram)
            res = {"DTDE": np.full(n_c, ram.max() * 1.10),
                   "CEDT-bit": np.where(bit, ram[bit].max(),
                                        ram[~bit].max()) * 1.05,
                   "CEDT-full": ram * 1.05}
            # infeasible single jobs would abort the campaign — record and clamp
            for k in res:
                res[k] = np.minimum(res[k], MEM_BUDGET)
            st = out["scales"].setdefault(n_sc, {
                "worlds": [], "streams": {k: [] for k in res},
                "memfrac": {k: [] for k in res}})
            rec = {}
            for arm, rv in res.items():
                tot_ch, tot_fac, cq, mkspans, streams = 0.0, 0.0, [], [], []
                for p in range(N_PAIRS):
                    order = np.random.RandomState(10_000 * w + p) \
                        .permutation(n_c)[:N_CALLS]
                    wk = list(work16[order]); rs = list(rv[order])
                    stt, cmp_, mk2 = run_schedule(wk, rs, NODE_CORES // RANKS,
                                                  c_cont)
                    ch = charges(stt, cmp_, rs)
                    tot_ch += sum(ch); mkspans.append(mk2 / 3600.0)
                    cq.append(charge_to_first_qualifier(stt, cmp_, ch,
                                                        list(quals[order])))
                    streams.append(N_CALLS * np.mean(wk) /
                                   max(mk2, 1e-9) * (1 + 0))  # avg co-residency
                rec[arm] = dict(charge=tot_ch, cq=cq, makespan=sum(mkspans),
                                labels=N_PAIRS * N_CALLS)
                st["streams"][arm].append(float(np.mean(streams)))
                st["memfrac"][arm].append(float(np.mean(
                    np.maximum(RANKS / NODE_CORES, rv / NODE_GB))))
            # ---- grade the pair CEDT-bit vs DTDE
            wins = sum(1 for a, b in zip(rec["CEDT-bit"]["cq"],
                                         rec["DTDE"]["cq"]) if a < b - 1e-12)
            h_ratio = (rec["CEDT-bit"]["labels"] / rec["CEDT-bit"]["charge"]) / \
                      (rec["DTDE"]["labels"] / rec["DTDE"]["charge"])
            h_full = (rec["CEDT-full"]["labels"] / rec["CEDT-full"]["charge"]) / \
                     (rec["DTDE"]["labels"] / rec["DTDE"]["charge"])
            fac_ratio = rec["DTDE"]["makespan"] / rec["CEDT-bit"]["makespan"]
            st["worlds"].append(dict(
                wins=wins, pw60=wins >= math.ceil(0.6 * N_PAIRS),
                h_ratio=h_ratio, h_full=h_full, fac_ratio=fac_ratio,
                budget_pair_total=rec["CEDT-bit"]["charge"] +
                                  rec["DTDE"]["charge"]))

    gs = np.array(gate_savings)
    out["cofit_gate_prediction"] = dict(
        median_saving=float(np.median(gs)),
        ci80=[float(np.percentile(gs, 10)), float(np.percentile(gs, 90))],
        p_pass=float(np.mean(gs > 0.0)), p_gt5pct=float(np.mean(gs > 0.05)),
        note="saving vs measured 8645 s sequential baseline, contention included")

    for n_sc in SCALES:
        st = out["scales"][n_sc]
        W = st["worlds"]
        st["summary"] = dict(
            p_pw60=float(np.mean([x["pw60"] for x in W])),
            median_wins=float(np.median([x["wins"] for x in W])),
            h_ratio_med=float(np.median([x["h_ratio"] for x in W])),
            h_ratio_ci80=[float(np.percentile([x["h_ratio"] for x in W], q))
                          for q in (10, 90)],
            p_h_pass=float(np.mean([x["h_ratio"] >= 1.05 for x in W])),
            p_joint=float(np.mean([x["pw60"] and x["h_ratio"] >= 1.05
                                   for x in W])),
            h_full_med=float(np.median([x["h_full"] for x in W])),
            fac_ratio_med=float(np.median([x["fac_ratio"] for x in W])),
            budget_med_nh=float(np.median([x["budget_pair_total"] for x in W])),
            budget_ci80=[float(np.percentile(
                [x["budget_pair_total"] for x in W], q)) for q in (10, 90)],
            memfrac_dtde=float(np.mean(st["memfrac"]["DTDE"])),
            memfrac_bit=float(np.mean(st["memfrac"]["CEDT-bit"])))
        st["h_ratios"] = [x["h_ratio"] for x in W]
        st["h_fulls"] = [x["h_full"] for x in W]
        st["budgets"] = [x["budget_pair_total"] for x in W]
        del st["worlds"], st["streams"]
    out["gate_savings"] = gs.tolist()

    with open(os.path.join(HERE, f"prestudy_results{OUT_TAG}.json"), "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps({k: out[k] for k in
                      ("anchor_crosscheck", "base_walls_6x6_32r",
                       "cofit_gate_prediction")}, indent=1))
    for n_sc in SCALES:
        print(n_sc, json.dumps(out["scales"][n_sc]["summary"]))

if __name__ == "__main__":
    main()

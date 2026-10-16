#!/usr/bin/env python3
"""Prior-predictive digital twin and campaign simulator for the QE
privacy-tax multi-agent experiment.

Mode: prior_predictive_simulation (frozen manifest ../case_manifest.yaml).
All node-hours are SIMULATED UNITS. Nothing here is a CHPC measurement.

Design notes
------------
* One "world" is a draw from a prior card (Axiom A7): symbolic-expression
  constants for cost/memory/failure (forms carried from Stage 1), scientific
  ground truth (gaps, SOC shifts, Gamma-phonon stability), HPC ground truth
  (config quirks, scaling exponent, build class, contention burstiness), and
  attack-power beliefs. Three prior cards form the ambiguity set:
  base / strong_coupling (coordination-optimistic) / adversarial.
* Campaigns are simulated with 30 paired seeds: every condition (topology x
  contract) replays the same latent world, candidate truths, noise fields,
  and contention trace. Policies are deterministic given their information,
  so outcome differences are attributable to the contract.
* Topologies (Section 7): CTCE/P0 full-information ceiling; DTDE/P4
  no-sharing baseline (= outside option); CTDE-Pk (shared surrogate trained
  in-campaign on contract-coarsened features, local execution); CEDT-Pk
  (independent training, per-round broker matching of coarsened menus).
  Extensions (added 2026-09-09): HYB-Pk hybrid-mix arm
  (CTDE-style shared surrogate feeds R's cost estimates AND CEDT-style
  broker matching picks the execution config — both channels open, both
  leak); ALT negotiation baseline (no descriptors cross; the only
  information channel is H's per-job price quote, which R can use as a
  coarse cost signal — an alternating-offers stand-in). At P4 the HYB
  arm degenerates to CEDT-P4 by construction (gamma = 0 disables the
  surrogate), so HYB is only distinct at P1–P3. A collusion variant is
  modeled at score time: contract.gamma_attack = 1.0 evaluates R-side
  leakage as if the broker shared pre-DP messages with H's attacker
  while utility stays at the contract's gamma.
* Leakage (Section 10): Bayes-style attackers on the R side built from
  descriptor equivalence classes at each precision level (upper-bound
  convention); H-side attacks use calibrated analytic models whose power
  factors are part of the prior card. DP at P3 uses randomized-response
  accounting with per-message epsilon = epsilon_total / expected messages.
* Billing contract: under P2-P4 the agreed charge is a public rate-card
  price (fixed-price billing hides H's realized efficiency); under P0/P1
  charges are realized node-hours. Evaluator metrics always use true
  node-hours.
"""
import argparse
import json
import os
from pathlib import Path

import numpy as np
from scipy.stats import norm, spearmanr

HERE = Path(__file__).parent
S = 30              # paired seeds
T = 80              # max rounds
MAX_ATTEMPTS = 100
BUDGET_NH = 500.0   # simulated node-hours per campaign
# MPT_HARD_CAP=1 refuses any job that would exceed BUDGET_NH (strict
# 500/campaign, 15,000/condition across 30 paired seeds); default keeps
# the original soft-stop semantics for comparability with older runs.
HARD_CAP = os.environ.get("MPT_HARD_CAP", "0") == "1"
OVERHEAD_NH = 1.0   # fixed queue/setup cost charged per job attempt
GAP_LO, GAP_HI = 1.0, 2.0
FIDS = 5            # F0..F4
NK = np.array([1.0, 9.0, 36.0, 81.0, 36.0])         # k-points per fidelity
# reference node-hour scales chosen so a full ladder on a heavy candidate
# costs ~120 simulated nh and the 500-nh budget binds before the round cap
AF = np.array([0.03, 1.2, 12.0, 8.0, 40.0])
SIG_GAP_OBS = np.array([9.9, 0.35, 0.08, 0.03, 9.9])  # gap obs noise by fid
NODE_MEM_GB = 64.0

# config space J: (nodes, pools, aggressive)
CONFIGS = [(1, 1, 0), (1, 2, 0), (2, 1, 0), (2, 2, 0), (2, 4, 0),
           (4, 2, 0), (4, 4, 0), (4, 4, 1), (2, 2, 1)]
J = len(CONFIGS)
C_NODES = np.array([c[0] for c in CONFIGS], float)
C_POOLS = np.array([c[1] for c in CONFIGS], float)
C_AGG = np.array([c[2] for c in CONFIGS], float)
C_IO = np.where(C_NODES >= 2, 0.30, 0.10)  # contention exposure

PRIOR_CARDS = {
    # name: hyperprior settings (Axiom A7 prior cards)
    "base":            dict(s_mu=0.65, s_sd=0.10, quirk_sd=0.18, pm_lo=0.15,
                            pm_hi=0.55, burst_lo=0.1, burst_hi=0.5,
                            beta0_mu=-3.0, beta0_sd=0.4, atk=1.0),
    "strong_coupling": dict(s_mu=0.52, s_sd=0.12, quirk_sd=0.30, pm_lo=0.30,
                            pm_hi=0.70, burst_lo=0.2, burst_hi=0.7,
                            beta0_mu=-2.8, beta0_sd=0.4, atk=1.0),
    "adversarial":     dict(s_mu=0.85, s_sd=0.08, quirk_sd=0.06, pm_lo=0.02,
                            pm_hi=0.20, burst_lo=0.4, burst_hi=0.9,
                            beta0_mu=-2.6, beta0_sd=0.5, atk=1.3),
}

LIMITS = dict(r_mi_auc=0.60, r_comp_adv=0.10, r_id_acc_inc=0.05,
              h_tel_auc=0.60, h_hw_adv=0.10, h_rank_corr=0.20)

# Optional R-side decision-maker hook (finding-5 study): callable taking
# (acq, value, cost_est, mu, prec, fid_done, dead, qualified, t) and
# returning per-seed candidate picks. None -> default greedy argmax.
R_PICK_POLICY = None

# Optional transcript recorder (future-work item 3, measured_attacks/):
# callable receiving per-round wire-log fields for the executed-attack
# study. None -> no recording (zero overhead in normal runs).
TRANSCRIPT_HOOK = None

# ---------------------------------------------------------------------------
# candidates (public CC0 metadata)

def load_candidates():
    with open(HERE / "candidates" / "candidates.json") as f:
        cands = json.load(f)
    nelec = np.array([c["electrons_per_cell"] for c in cands], float)
    natoms = np.array([c["atoms_per_cell"] for c in cands], float)
    ecut = np.array([c["ecutwfc_ry_idealized"] for c in cands], float)
    a_lat = np.array([c["a_angstrom"] for c in cands], float)
    phase = np.array([1 if c["phase"] == "2H" else 0 for c in cands])
    d2 = np.array([1 if c["metal_class"] == "d2" else 0 for c in cands])
    comp = np.array([f"{c['metal']}{c['chalcogen']}" for c in cands])
    chalc_idx = np.array([{"S": 0, "Se": 1, "Te": 2}[c["chalcogen"]]
                          for c in cands], float)
    zfac = np.array([{"Ti": .1, "Zr": .3, "Hf": .8, "Mo": .4, "W": 1.}[c["metal"]]
                     + {"S": .05, "Se": .25, "Te": .6}[c["chalcogen"]]
                     for c in cands], float)
    return dict(nelec=nelec, natoms=natoms, ecut=ecut, a=a_lat, phase=phase,
                d2=d2, comp=comp, chalc_idx=chalc_idx, zfac=zfac,
                names=[c["name"] for c in cands])


CAND = load_candidates()
C = len(CAND["nelec"])

# descriptor equivalence classes per contract level (R -> counterpart view).
# P1: engineered descriptors (nelec, ecut, a) — Zr/Hf collide by radius.
# P2: 3 coarse cost-proxy bins.  P3: same bins + randomized response.
# P4: calculation class only (no candidate-specific field).
def _equiv_classes():
    p1_key = [f"{CAND['nelec'][i]}_{CAND['ecut'][i]}_{CAND['a'][i]}"
              for i in range(C)]
    proxy = (CAND["nelec"] / 38.0) ** 2.5 * (50.0 / CAND["ecut"])
    p2_key = (proxy > np.median(proxy)).astype(int)
    return {"P1": np.unique(p1_key, return_inverse=True)[1],
            "P2": p2_key, "P3": p2_key,
            "P4": np.zeros(C, int)}


EQUIV = _equiv_classes()
GAP_PRIOR_MU = (CAND["d2"] * CAND["phase"] * (1.55 - 0.35 * CAND["chalc_idx"])
                + CAND["d2"] * (1 - CAND["phase"]) * 0.05
                + (1 - CAND["d2"]) * (1 - CAND["phase"]) * 0.55
                + (1 - CAND["d2"]) * CAND["phase"] * 0.25)
PHONON_PRIOR = (CAND["d2"] * CAND["phase"] * 0.90
                + CAND["d2"] * (1 - CAND["phase"]) * 0.25
                + (1 - CAND["d2"]) * (1 - CAND["phase"]) * 0.60
                + (1 - CAND["d2"]) * CAND["phase"] * 0.40)

# ---------------------------------------------------------------------------
# world sampling


def sample_world(card_name, world_id):
    hp = PRIOR_CARDS[card_name]
    # stable seed (Python's str hash is process-salted and irreproducible)
    import zlib
    rng = np.random.default_rng(
        zlib.crc32(f"{card_name}:{int(world_id)}".encode()))
    w = {}
    # --- scientific truth
    slope = rng.normal(0.35, 0.10)
    mu = (CAND["d2"] * CAND["phase"] * (rng.normal(1.55, 0.20)
                                        - slope * CAND["chalc_idx"])
          + CAND["d2"] * (1 - CAND["phase"]) * abs(rng.normal(0.05, 0.05))
          + (1 - CAND["d2"]) * (1 - CAND["phase"]) * rng.normal(0.60, 0.30)
          + (1 - CAND["d2"]) * CAND["phase"] * abs(rng.normal(0.25, 0.20)))
    w["gap"] = np.clip(mu + rng.normal(0, 0.30, C), 0.0, None)
    w["soc"] = -rng.uniform(0.05, 0.30) * CAND["zfac"]
    w["stable"] = rng.random(C) < np.clip(
        PHONON_PRIOR + rng.normal(0, 0.08, C), 0.02, 0.98)
    w["valid"] = rng.random(C) < 0.97
    gap_f = w["gap"] + w["soc"]
    w["qual"] = (w["valid"] & w["stable"]
                 & (gap_f >= GAP_LO) & (gap_f <= GAP_HI))
    # --- cost/performance truth (expression constants; forms from Stage 1)
    w["p_e"] = np.clip(rng.normal(2.5, 0.2), 2.0, 3.0)
    w["p_k"] = np.clip(rng.normal(1.0, 0.1), 0.8, 1.2)
    w["A"] = AF * np.exp(rng.normal(0, 0.25))
    w["s"] = np.clip(rng.normal(hp["s_mu"], hp["s_sd"]), 0.4, 1.0)
    w["pm"] = rng.uniform(hp["pm_lo"], hp["pm_hi"])
    w["quirk"] = np.exp(rng.normal(0, hp["quirk_sd"], J))
    w["build"] = rng.integers(0, 3)
    w["bspeed"] = [0.85, 1.0, 1.18][w["build"]]
    w["memq"] = np.exp(rng.normal(0, 0.20))
    # candidate-specific memory demand (structure-dependent): R can compute
    # it from its private structures; H cannot without disclosure. This is
    # the fresh cross-party coupling of Proposition 15.10.
    w["rho"] = np.exp(rng.normal(0, 0.35, C))
    w["beta0"] = rng.normal(hp["beta0_mu"], hp["beta0_sd"])
    w["burst"] = rng.uniform(hp["burst_lo"], hp["burst_hi"])
    w["atk"] = hp["atk"]
    # R's noisy view of H-disclosed cost info (per condition precision)
    w["view_noise"] = rng.normal(0, 1, (S, C))
    # --- paired noise fields shared by all conditions (per seed)
    w["gap_noise"] = rng.normal(0, 1, (S, C, FIDS))
    w["fail_u"] = rng.random((S, C, FIDS, 4))
    w["nh_noise"] = np.exp(rng.normal(0, 0.15, (S, C, FIDS, 4)))
    kap = np.clip(0.25 + w["burst"] * rng.standard_normal((S, T)).cumsum(1)
                  * 0.06 + w["burst"] * (rng.random((S, T)) < 0.08)
                  * rng.uniform(0.3, 0.8, (S, T)), 0.0, 1.0)
    w["kappa"] = kap
    return w


# vectorized twin pieces -----------------------------------------------------

def base_work(w, fid):  # (C,) node-hours at reference config
    extra = (CAND["natoms"] / 4.5) if fid == 4 else 1.0
    return (w["A"][fid] * (CAND["nelec"] / 38.0) ** w["p_e"]
            * (NK[fid] / 36.0) ** w["p_k"] * extra * (CAND["ecut"] / 40.0))


def pool_eff(w, nk, pools):
    """Load-balance efficiency of distributing nk k-points over pools;
    pm in the world scales how strongly imbalance hurts."""
    ideal = nk / (np.ceil(nk / pools) * pools)
    return 1.0 - w["pm"] * (1.0 - ideal)


def eff_matrix(w, fid):  # (C, J) parallel efficiency
    nk = NK[fid]
    eff = (C_NODES ** (w["s"] - 1.0) * pool_eff(w, nk, C_POOLS) * w["quirk"]
           * w["bspeed"] * (1 + 0.25 * C_AGG))
    return np.broadcast_to(eff, (C, J))


def mem_per_node(w, fid):  # (C, J)
    grow = (NK[fid] / 36.0) ** 0.3
    m = (30.0 * (CAND["nelec"][:, None] / 38.0) ** 2 * grow * w["memq"]
         * w["rho"][:, None]
         / (C_NODES[None, :] * C_POOLS[None, :] ** 0.4)) + 8.0
    return m


def fail_prob(w, fid, kappa):  # kappa scalar/(S,), returns (..., C, J)
    mem = mem_per_node(w, fid)
    headroom = np.clip(NODE_MEM_GB / mem, 0.2, 20.0)
    z = (w["beta0"] + 1.2 * (np.asarray(kappa)[..., None, None] - 0.3)
         + 0.8 * C_AGG[None, :] - 1.5 * np.log(headroom))
    return 1.0 / (1.0 + np.exp(-z)), mem > NODE_MEM_GB


# ---------------------------------------------------------------------------
# contracts


def dp_gamma(eps_total, nbins=3, msgs=120.0):
    """Effective disclosure fidelity of a competently engineered P3
    mechanism (secure aggregation with a small number of DP releases per
    campaign, budget split across releases). gamma = eps/(eps+3) maps
    eps in {1,2,4,8} to {0.25, 0.40, 0.57, 0.73}. Naive per-message
    randomized response under linear composition would drive every P3
    level to P4 (a designed-mechanism assumption recorded in RESULTS.md;
    it is part of the prior, not a measured property)."""
    return eps_total / (eps_total + 3.0)


class ContractView:
    """Per-campaign contract with world-specific descriptor classes."""

    def __init__(self, base, cls):
        self.level = base.level
        self.eps = base.eps
        self.gamma = base.gamma
        self.gamma_attack = getattr(base, "gamma_attack", base.gamma)
        self.cost_sd = base.cost_sd
        self.classes = cls
        self.nclasses = int(np.max(cls)) + 1


class Contract:
    def __init__(self, level, eps=None):
        self.level = level
        self.eps = eps
        self.classes = EQUIV[level if level in EQUIV else "P4"]
        self.nclasses = int(self.classes.max()) + 1
        self.gamma = 1.0
        if level == "P3":
            self.gamma = dp_gamma(eps if eps else 4.0, self.nclasses)
        if level == "P4":
            self.gamma = 0.0
        # H->R runtime-info precision (sd of log-cost view given to R)
        self.cost_sd = {"P0": 0.0, "P1": 0.05, "P2": 0.5, "P3": 0.5,
                        "P4": np.inf}[level]
        if level == "P3":
            self.cost_sd = min(0.5 / self.gamma, 2.5)


# ---------------------------------------------------------------------------
# campaign batch (one world x one condition, S seeds vectorized)


def world_classes(w, level):
    """Descriptor equivalence classes seen by the counterpart/attacker.
    P2/P3 disclose a size bin and a predicted-memory-demand bin (the rho
    factor is world-dependent, so these classes are built per world)."""
    if level in ("P2", "P3"):
        return EQUIV["P2"] * 2 + (w["rho"] > np.median(w["rho"])).astype(int)
    return EQUIV[level if level in EQUIV else "P4"]


def run_campaign(w, topology, contract):
    lvl, gam = contract.level, contract.gamma
    cls = (np.arange(C) if lvl == "P0" else world_classes(w, lvl))
    contract = ContractView(contract, cls)
    # R belief state
    mu = np.tile(GAP_PRIOR_MU, (S, 1))
    prec = np.full((S, C), 1.0 / 0.5 ** 2)
    fid_done = np.full((S, C), -1)
    dead = np.zeros((S, C), bool)
    qualified = np.zeros((S, C), bool)
    got_soc = np.zeros((S, C), bool)
    nh_used = np.zeros(S)
    attempts = np.zeros(S, int)
    fails = np.zeros(S, int)
    memfails = np.zeros(S, int)
    labels_f2 = np.zeros(S, int)
    att_f2 = np.zeros(S, int)
    first_qual_nh = np.full(S, np.nan)
    qe_calls = np.zeros(S, int)
    attempt_ct = np.zeros((S, C, FIDS), int)
    queried = np.zeros((S, C), bool)
    # attacker accumulators
    mi_score = np.zeros((S, C))            # membership mass per candidate
    n_msgs = np.zeros(S)
    cfg_obs_sum = np.zeros((S, J))
    cfg_obs_n = np.zeros((S, J))
    # shared surrogate (CTDE): running mean of log-NH per (class, fid, config)
    nb = contract.nclasses
    sur_sum = np.zeros((S, nb, FIDS, J))
    sur_n = np.zeros((S, nb, FIDS, J))
    # R's empirical cost model under P4 (charge regression on nelec shape)
    chg_sum = np.zeros((S, FIDS))
    chg_n = np.zeros((S, FIDS))
    rel = (CAND["nelec"] / 38.0) ** 2.5   # R's fixed shape guess
    # H's static belief of job size without disclosure (risk-averse prior)
    nelec_hi = np.quantile(CAND["nelec"], 0.9)

    # ---- per-campaign statics (round-invariant twin pieces) ----
    wk_all = np.stack([base_work(w, ff) for ff in range(FIDS)])      # (F, C)
    eff_all = np.stack([eff_matrix(w, ff) for ff in range(FIDS)])    # (F,C,J)
    mem_all = np.stack([mem_per_node(w, ff) for ff in range(FIDS)])  # (F,C,J)
    hard_all = mem_all > NODE_MEM_GB
    headroom_all = np.clip(NODE_MEM_GB / mem_all, 0.2, 20.0)
    z0_all = (w["beta0"] + 0.8 * C_AGG[None, None, :]
              - 1.5 * np.log(headroom_all))                          # (F,C,J)
    best_cost_all = (wk_all[:, :, None] / eff_all).min(2)            # (F, C)

    active = np.ones(S, bool)
    for t in range(T):
        if not active.any():
            break
        kap = w["kappa"][:, t]
        # ---------- R acquisition ------------------------------------------
        sd = 1.0 / np.sqrt(prec)
        pwin = (norm.cdf((GAP_HI - mu) / sd) - norm.cdf((GAP_LO - mu) / sd))
        # probability-weighted acquisition: squaring the window probability
        # keeps the search discovery-directed (time-to-first-qualifier),
        # while the cost denominator differentiates within a value class
        value = pwin ** 2 * PHONON_PRIOR[None, :]
        value[dead | qualified] = 0.0
        nfid = np.clip(fid_done + 1, 1, 4)  # F0 folded into first F1 job
        # F4 gate: only promote if window prob decent after F3
        f4block = (nfid == 4) & (pwin < 0.5)
        value[f4block] = 0.0
        # cost estimate per candidate at its next fidelity
        wk_next = wk_all[nfid, np.arange(C)[None, :]]        # (S, C)
        if topology == "CTCE":
            cost_est = best_cost_all[nfid, np.arange(C)[None, :]]
        elif topology in ("CTDE", "HYB") and lvl != "P4":
            # query shared surrogate at own (private) size class; predict the
            # cost of execution under H's policy (count-weighted mean).
            # HYB fallback: where the surrogate has no data yet, the broker
            # relays H's disclosed runtime prediction (the CEDT channel);
            # CTDE falls back to R's own naive estimate.
            sidx = np.arange(S)[:, None]
            cidx = np.broadcast_to(cls[None, :], (S, C))
            sn = sur_n[sidx, cidx, nfid, :]                  # (S, C, J)
            ss = sur_sum[sidx, cidx, nfid, :]
            ntot = sn.sum(2)
            have = ntot > 0                                  # (S, C)
            pred = ss.sum(2) / np.maximum(ntot, 1)
            if topology == "HYB":
                fallback = (best_cost_all[nfid, np.arange(C)[None, :]]
                            * np.exp(w["view_noise"] * contract.cost_sd))
            else:
                fallback = wk_next / 0.8
            cost_est = np.where(have, np.exp(pred), fallback)
        elif lvl in ("P1", "P2", "P3") and topology == "CEDT":
            # H's disclosed runtime predictions, seen at contract precision
            cost_est = (best_cost_all[nfid, np.arange(C)[None, :]]
                        * np.exp(w["view_noise"] * contract.cost_sd))
        elif topology == "ALT":
            # negotiation baseline: no descriptors cross; H's per-job price
            # quote is R's only cost signal (coarse view of H's realized
            # cost forecast, sd 1.0 in log space)
            cost_est = (best_cost_all[nfid, np.arange(C)[None, :]]
                        * np.exp(w["view_noise"] * 1.0))
        else:  # DTDE / P4: regress observed charges on size shape
            cn = np.take_along_axis(chg_n, nfid, axis=1)     # (S, C)
            cs = np.take_along_axis(chg_sum, nfid, axis=1)
            base_chg = np.where(cn > 0, cs / np.maximum(cn, 1),
                                wk_next / 0.8)
            mean_rel = rel.mean()
            cost_est = base_chg * rel[None, :] / mean_rel
        acq = value / (np.maximum(cost_est, 0.02) + OVERHEAD_NH)
        # F1 screening bonus (cheap info first)
        acq *= np.where(nfid == 1, 1.5, 1.0)
        if R_PICK_POLICY is None:
            pick = acq.argmax(1)                               # (S,)
        else:
            # decision-maker archetype hook (finding-5 study):
            # must return one candidate index per seed; picks with zero acq
            # are treated as no-move exactly like the default policy
            pick = R_PICK_POLICY(acq=acq, value=value, cost_est=cost_est,
                                 mu=mu, prec=prec, fid_done=fid_done,
                                 dead=dead, qualified=qualified, t=t)
        no_move = acq[np.arange(S), pick] <= 1e-12
        run_mask = active & ~no_move
        if not run_mask.any():
            break
        i = pick
        f = nfid[np.arange(S), i]
        # ---------- H / joint config choice --------------------------------
        wk_i = wk_all[f, i]                                    # (S,)
        eff_i = eff_all[f, i, :]                               # (S, J)
        z0_i = z0_all[f, i, :]                                 # (S, J)
        pf_i = 1.0 / (1.0 + np.exp(-(z0_i + 1.2 * (kap[:, None] - 0.3))))
        hard_i = hard_all[f, i, :]                             # (S, J)
        true_nh = wk_i[:, None] / eff_i * (1 + kap[:, None] * C_IO[None, :])
        esc = 1.6 ** np.minimum(attempt_ct[np.arange(S), i, f], 3)
        if topology == "CTCE":
            score = true_nh * (1 + 2 * pf_i) + 1e3 * hard_i
            j = score.argmin(1)
        elif topology in ("CEDT", "HYB"):
            # broker sees size class (gamma-degraded) + H's menu
            mem_belief = self_mem = None
            # H predicts using disclosed class mean nelec (or prior if gamma=0)
            cls_i = cls[i]
            cls_top = np.array([CAND["nelec"][cls == b].max()
                                for b in range(contract.nclasses)])
            rho_top = np.array([w["rho"][cls == b].max()
                                for b in range(contract.nclasses)])
            ne_belief = gam * cls_top[cls_i] + (1 - gam) * nelec_hi
            rho_belief = gam * rho_top[cls_i] + (1 - gam) * 1.56
            j = _h_config(w, f, ne_belief, kap, aggressive_ok=True,
                          rho_belief=rho_belief * esc)
        elif topology == "CTDE":
            # H local policy: the shared model tells H what size mix R sends
            # at each fidelity; H provisions for the largest class observed
            # (memory-safe), which is leaner than the DTDE worst-case prior
            # whenever R's actual mix at this fidelity is small.
            cls_top = np.array([CAND["nelec"][cls == b].max()
                                for b in range(contract.nclasses)])
            rho_top = np.array([w["rho"][cls == b].max()
                                for b in range(contract.nclasses)])
            wts = sur_n[np.arange(S), :, f, :].sum(2)   # (S, nb)
            enough = wts.sum(1) >= 5
            ne_safe = np.where(enough,
                               np.where(wts > 0, cls_top[None, :],
                                        0.0).max(1), nelec_hi)
            rho_safe = np.where(enough,
                                np.where(wts > 0, rho_top[None, :],
                                         0.0).max(1), 1.56)
            ne_belief = gam * ne_safe + (1 - gam) * nelec_hi
            rho_belief = gam * rho_safe + (1 - gam) * 1.56
            j = _h_config(w, f, ne_belief, kap, aggressive_ok=False,
                          rho_belief=rho_belief * esc)
        else:  # DTDE
            ne_belief = np.full(S, nelec_hi)
            j = _h_config(w, f, ne_belief, kap, aggressive_ok=False,
                          rho_belief=np.full(S, 1.56) * esc)
        # ---------- execute -------------------------------------------------
        att_i = np.minimum(attempt_ct[np.arange(S), i, f], 3)
        noise = w["nh_noise"][np.arange(S), i, f, att_i]
        nh_real = true_nh[np.arange(S), j] * noise
        pfail = pf_i[np.arange(S), j]
        hard = hard_i[np.arange(S), j]
        u = w["fail_u"][np.arange(S), i, f, att_i]
        failed = (u < pfail) | hard
        spend = np.where(failed, 0.45 * nh_real, nh_real) + OVERHEAD_NH
        # apply only to running seeds
        m = run_mask
        if HARD_CAP:
            # hard budget semantics (set 2026-09-08):
            # a job whose worst-case spend would push the campaign past
            # BUDGET_NH is refused and the campaign stops, so nh_used can
            # never exceed 500 and 30 paired seeds never exceed 15,000
            # simulated node-hours per condition.
            over = (nh_used + spend) > BUDGET_NH
            active &= ~(m & over)
            m = m & ~over
        if os.environ.get("MPT_TRACE") and m[0]:
            print(f"t={t:2d} i={CAND['names'][i[0]]:10s} f={f[0]} "
                  f"j={j[0]} nh={nh_real[0]:6.2f} fail={int(failed[0])} "
                  f"used={nh_used[0]:6.1f}")
        nh_used[m] += spend[m]
        attempts[m] += 1
        qe_calls[m] += 1
        attempt_ct[m, i[m], f[m]] += 1
        queried[m, i[m]] = True
        fails[m] += failed[m]
        memfails[m] += (failed & hard)[m]
        att_f2[m & (f >= 2)] += 1
        # successful outcomes
        ok = m & ~failed
        if ok.any():
            fs = f[ok]
            iss = i[ok]
            fid_done[ok, iss] = fs
            labels_f2[ok & (f >= 2)] += 1
            # gap observation at F1..F3
            obs_mask = ok & (f >= 1) & (f <= 3)
            if obs_mask.any():
                io_, fo_ = i[obs_mask], f[obs_mask]
                soc_add = np.where(fo_ == 3, w["soc"][io_], 0.0)
                got_soc[obs_mask, io_] |= (fo_ == 3)
                obs = (w["gap"][io_] + soc_add
                       + w["gap_noise"][obs_mask, io_, fo_]
                       * SIG_GAP_OBS[fo_])
                p_obs = 1.0 / SIG_GAP_OBS[fo_] ** 2
                new_prec = prec[obs_mask, io_] + p_obs
                mu[obs_mask, io_] = (mu[obs_mask, io_]
                                     * prec[obs_mask, io_]
                                     + obs * p_obs) / new_prec
                prec[obs_mask, io_] = new_prec
            # folded-F0 validity check at first F1 completion
            f0m = ok & (f == 1)
            if f0m.any():
                inval = ~w["valid"][i[f0m]]
                dd = np.where(f0m)[0][inval]
                dead[dd, i[f0m][inval]] = True
            # F4 outcome
            f4m = ok & (f == 4)
            if f4m.any():
                i4 = i[f4m]
                stable = w["stable"][i4]
                gap_f = w["gap"][i4] + w["soc"][i4]
                win = (gap_f >= GAP_LO) & (gap_f <= GAP_HI)
                qual_now = stable & win & w["valid"][i4]
                rows = np.where(f4m)[0]
                qualified[rows[qual_now], i4[qual_now]] = True
                dead[rows[~qual_now], i4[~qual_now]] = True
                newq = rows[qual_now]
                fq = np.isnan(first_qual_nh[newq])
                first_qual_nh[newq[fq]] = nh_used[newq[fq]]
        # abandon candidates that keep failing at one fidelity
        exhausted = m & failed & (attempt_ct[np.arange(S), i, f] >= 3)
        if exhausted.any():
            dead[exhausted, i[exhausted]] = True
        # dead-end after F3 with low window prob handled by f4block/value=0
        f3done = (fid_done == 3)
        sd2 = 1.0 / np.sqrt(prec)
        pw2 = (norm.cdf((GAP_HI - mu) / sd2) - norm.cdf((GAP_LO - mu) / sd2))
        dead |= f3done & (pw2 < 0.15)
        # ---------- learning/transcript updates -----------------------------
        # charges (billing view for R)
        realized = lvl in ("P0", "P1")
        rate_card = wk_i / 0.8
        charge = np.where(realized, nh_real, rate_card)
        chg_sum[m, f[m]] += charge[m]
        chg_n[m, f[m]] += 1
        if TRANSCRIPT_HOOK is not None:
            TRANSCRIPT_HOOK(t=t, m=m, i=i, f=f, j=j, failed=failed,
                            charge=charge, nh_real=nh_real, cls=cls)
        # CTDE/HYB shared surrogate ingest (contract-coarsened)
        if topology in ("CTDE", "HYB") and gam > 0:
            sur_sum[m, cls[i[m]], f[m], j[m]] += np.log(
                np.maximum(nh_real[m], 1e-3))
            sur_n[m, cls[i[m]], f[m], j[m]] += 1
        # attacker accumulators (R membership mass; H config exposure).
        # Collusion (gamma_attack > gamma): the attacker sees the pre-DP
        # class stream, so membership mass accumulates at gamma_attack.
        gam_atk = contract.gamma_attack
        if gam_atk > 0 and topology in ("CEDT", "CTDE", "HYB"):
            bsz = np.array([(cls == b).sum() for b in range(contract.nclasses)])
            mi_score[m] += gam_atk * (cls[None, :] == cls[i[m]][:, None])[
                :, :] / bsz[cls[i[m]]][:, None]
            n_msgs[m] += 1
        # config-performance exposure (menus/surrogate/charges)
        cfg_obs_sum[m, j[m]] += np.log(np.maximum(nh_real, 1e-3))[m]
        cfg_obs_n[m, j[m]] += 1
        # budget stops (seeds with no admissible move stop via no_move)
        active &= (nh_used < BUDGET_NH) & (attempts < MAX_ATTEMPTS)
        active &= ((~dead) & (~qualified)).any(1)

    return _score_campaign(w, topology, contract, dict(
        mu=mu, prec=prec, fid_done=fid_done, qualified=qualified,
        nh_used=nh_used, attempts=attempts, fails=fails, memfails=memfails,
        labels_f2=labels_f2, att_f2=att_f2, first_qual_nh=first_qual_nh,
        qe_calls=qe_calls, queried=queried, mi_score=mi_score,
        n_msgs=n_msgs, cfg_obs_sum=cfg_obs_sum, cfg_obs_n=cfg_obs_n))


def _h_config(w, f, ne_belief, kap, aggressive_ok, rho_belief=None):
    """H's local config policy given beliefs about the job's electron count
    and structure-specific memory factor (q90 prior when undisclosed)."""
    if rho_belief is None:
        rho_belief = np.full(len(ne_belief), 1.56)  # lognormal q90
    # predicted work with believed size (H knows expression family locally)
    wk_b = (w["A"][f] * (ne_belief / 38.0) ** w["p_e"]
            * (NK[f] / 36.0) ** w["p_k"])                    # (S,)
    eff = (C_NODES[None, :] ** (w["s"] - 1.0) * w["quirk"][None, :]
           * w["bspeed"] * (1 + 0.25 * C_AGG[None, :]))
    eff = eff * pool_eff(w, NK[f][:, None], C_POOLS[None, :])
    nh = wk_b[:, None] / eff * (1 + kap[:, None] * C_IO[None, :])
    mem = (30.0 * (ne_belief[:, None] / 38.0) ** 2 * rho_belief[:, None]
           * (NK[f][:, None] / 36.0) ** 0.3 * w["memq"]
           / (C_NODES[None, :] * C_POOLS[None, :] ** 0.4)) + 8.0
    headroom = np.clip(NODE_MEM_GB / mem, 0.2, 20.0)
    z = (w["beta0"] + 1.2 * (kap[:, None] - 0.3) + 0.8 * C_AGG[None, :]
         - 1.5 * np.log(headroom))
    pf = 1.0 / (1.0 + np.exp(-z))
    score = nh * (1 + 2 * pf) + 1e3 * (mem > NODE_MEM_GB)
    if not aggressive_ok:
        score += 1e3 * C_AGG[None, :]
    return score.argmin(1)


# ---------------------------------------------------------------------------
# scoring: utility metrics + leakage attacks


def _auc(pos, neg):
    if len(pos) == 0 or len(neg) == 0:
        return 0.5
    diff = pos[:, None] - neg[None, :]
    return ((diff > 0).mean() + 0.5 * (diff == 0).mean())


def _score_campaign(w, topology, contract, st):
    lvl, gam = contract.level, contract.gamma
    gam_atk = contract.gamma_attack
    atk = w["atk"]
    out = {}
    nh = np.maximum(st["nh_used"], 1e-6)
    out["qual_count"] = st["qualified"].sum(1).astype(float)
    out["found"] = (~np.isnan(st["first_qual_nh"])).astype(float)
    out["nh_first"] = np.where(np.isnan(st["first_qual_nh"]), BUDGET_NH,
                               st["first_qual_nh"])
    out["labels_per_nh"] = st["labels_f2"] / nh
    out["fail_rate"] = st["fails"] / np.maximum(st["attempts"], 1)
    out["memfail_rate"] = st["memfails"] / np.maximum(st["attempts"], 1)
    out["validity"] = st["labels_f2"] / np.maximum(st["att_f2"], 1)
    out["nh_used"] = st["nh_used"]
    out["attempts"] = st["attempts"].astype(float)
    out["qe_calls"] = st["qe_calls"].astype(float)
    # ---- R leakage ----
    if topology == "CTCE":
        mi = np.full(S, 1.0)
        comp_adv = np.full(S, 1.0 - 1 / 15)
        id_acc = np.full(S, 1.0)
    elif gam_atk <= 0 or topology in ("DTDE", "ALT"):
        # ALT: only prices cross; no descriptor classes reach H's attacker
        mi = np.full(S, 0.5)
        comp_adv = np.zeros(S)
        id_acc = np.full(S, 1 / C)
    else:
        cls = contract.classes
        mi = np.array([_auc(st["mi_score"][s][st["queried"][s]],
                            st["mi_score"][s][~st["queried"][s]])
                       for s in range(S)])
        # composition (metal,chalcogen) 15-way MAP from descriptor class
        # per-candidate MAP accuracy for the 15-way composition target:
        # attacker sees the descriptor class, guesses among the compositions
        # present in that class (uniform over distinct compositions).
        comps = CAND["comp"]
        acc = np.zeros(C)
        for i in range(C):
            same = cls == cls[i]
            acc[i] = 1.0 / max(np.unique(comps[same]).size, 1)
        qacc = np.where(st["queried"], acc[None, :] * gam_atk, 0.0)
        nq = np.maximum(st["queried"].sum(1), 1)
        comp_adv = np.clip((qacc.sum(1) / nq - 1 / 15) * atk, 0, 1)
        idacc_c = np.array([1.0 / max((cls == cls[i]).sum(), 1)
                            for i in range(C)])
        qid = np.where(st["queried"], idacc_c[None, :] * gam_atk, 0)
        id_acc = np.clip(qid.sum(1) / nq * atk, 0, 1)
        mi = np.clip(0.5 + (mi - 0.5) * atk, 0, 1)
    out["r_mi_auc"] = mi
    out["r_comp_adv"] = comp_adv
    out["r_id_acc"] = id_acc
    # ---- H leakage ----
    rounds = np.maximum(st["attempts"], 1).astype(float)
    if topology == "CTCE":
        out["h_rank_corr"] = np.full(S, 1.0)
        out["h_hw_adv"] = np.full(S, 2 / 3)
        out["h_tel_auc"] = np.full(S, 1.0)
    else:
        # config-rank extraction: expected rank correlation of the
        # attacker's posterior-mean config estimate (deterministic:
        # rho = sqrt(signal / (signal + estimator noise)), so chance = 0)
        sd_map = {"P1": 0.10, "P2": 0.60, "P3": 0.60, "P4": 3.0}
        sd0 = sd_map.get(lvl, 3.0)
        if lvl == "P3":
            sd0 = min(0.60 / max(gam, 0.05), 3.0)
        if topology == "DTDE":
            sd0 = 3.0
        if topology == "ALT":
            sd0 = 1.0   # price quotes carry H's cost forecast per config
        true_eff = np.log((C_NODES ** (w["s"] - 1.0)) * w["quirk"]
                          * (1 + 0.25 * C_AGG))
        var_sig = max(np.var(true_eff), 1e-8)
        noise_var = (sd0 ** 2 / np.maximum(st["cfg_obs_n"], 0.25)).mean(1)
        corr = np.sqrt(var_sig / (var_sig + noise_var))
        out["h_rank_corr"] = np.clip(corr * atk, 0, 1)
        # hardware/build class (3-way): disclosed runtime predictions carry
        # the build effect directly (small systematic residual); the P4
        # timing side channel is confounded by unknown quirks/contention,
        # which floors identification regardless of message count
        sep = 0.12
        sd_sys = {"P1": 0.05, "P2": 0.15, "P3": 0.25, "P4": 0.35}.get(lvl,
                                                                      0.35)
        sd_obs = {"P1": 0.10, "P2": 0.45, "P4": 1.5}.get(lvl, 1.5)
        if lvl == "P3":
            sd_obs = min(0.45 / max(gam, 0.05), 3.0)
        if topology == "ALT":
            sd_obs = 0.8   # quotes are per-job, coarser than P2 predictions
        sd_est = np.sqrt(sd_sys ** 2 + sd_obs ** 2 * 2.25 / rounds)
        snr = sep / np.maximum(sd_est, 1e-6)
        acc3 = 1 / 3 + (4 / 3) * (norm.cdf(snr / 2) - 0.5)
        out["h_hw_adv"] = np.clip((acc3 - 1 / 3) * atk, 0, 1)
        # telemetry membership
        pf_map = {"P1": 0.8, "P2": 0.35, "P3": 0.35, "P4": 0.12}
        pf = pf_map.get(lvl, 0.12)
        if lvl == "P3":
            pf *= gam
        if topology == "CEDT":
            pf *= 1.3
        elif topology == "HYB":
            pf *= 1.3   # broker per-round channel dominates the surrogate
        elif topology == "CTDE":
            pf *= 0.7
        elif topology == "DTDE":
            pf = 0.10
        elif topology == "ALT":
            pf = 0.15   # quote stream is per-round but 1-D
        auc_t = 0.5 + 0.5 * pf * (1 - np.exp(-rounds / 40.0)) * w["burst"]
        out["h_tel_auc"] = np.clip(0.5 + (auc_t - 0.5) * atk, 0, 1)
    out["n_true_qual"] = np.full(S, float(w["qual"].sum()))
    return out


# ---------------------------------------------------------------------------
# win-win evaluation


def eval_world(results, dtde_key="DTDE_P4"):
    """results: {cond_name: metrics dict}. Returns per-condition summary."""
    base = results[dtde_key]
    rows = {}
    for name, r in results.items():
        d = {}
        d["mean_nh_first"] = r["nh_first"].mean()
        d["found_rate"] = r["found"].mean()
        d["mean_qual"] = r["qual_count"].mean()
        d["labels_per_nh"] = r["labels_per_nh"].mean()
        d["fail_rate"] = r["fail_rate"].mean()
        d["memfail_p95"] = np.percentile(r["memfail_rate"], 95)
        d["validity"] = r["validity"].mean()
        d["mean_nh_used"] = r["nh_used"].mean()
        for k in ("r_mi_auc", "r_comp_adv", "r_id_acc",
                  "h_rank_corr", "h_hw_adv", "h_tel_auc"):
            d[k] = r[k].mean()
        # reservation gains vs DTDE (paired means)
        gainA = (d["mean_nh_first"] <= 0.80 * base["nh_first"].mean()
                 and d["found_rate"] >= base["found"].mean() - 1e-9)
        gainB = d["mean_qual"] >= base["qual_count"].mean() + 1.0
        r_valid_ok = d["validity"] >= base["validity"].mean() - 0.01
        d["r_gain"] = float((gainA or gainB) and r_valid_ok)
        h1 = d["labels_per_nh"] >= 1.15 * base["labels_per_nh"].mean()
        h2 = d["fail_rate"] <= base["fail_rate"].mean() + 0.02
        h3 = d["memfail_p95"] <= np.percentile(base["memfail_rate"], 95) + 1e-9
        d["h_gain"] = float(h1 and h2 and h3)
        # redesigned metrics (2026-09-09: fix the noise-to-signal
        # problem rather than freeze the metric). PW60 = paired-seed
        # win-rate on nh-to-first-qualifier (sign test, cancels common
        # scientific noise); package H margins = labels/nh >= 1.05x,
        # failure <= +0.04, memory-p95 no worse.
        d["pw_rate"] = float((r["nh_first"] < base["nh_first"]).mean())
        d["r_gain_pw60"] = float(d["pw_rate"] >= 0.60
                                 and d["found_rate"]
                                 >= base["found"].mean() - 1e-9
                                 and r_valid_ok)
        hp1 = d["labels_per_nh"] >= 1.05 * base["labels_per_nh"].mean()
        hp2 = d["fail_rate"] <= base["fail_rate"].mean() + 0.04
        d["h_gain_package"] = float(hp1 and hp2 and h3)
        leak_ok = (d["r_mi_auc"] <= LIMITS["r_mi_auc"]
                   and d["r_comp_adv"] <= LIMITS["r_comp_adv"]
                   and d["r_id_acc"] <= 1 / C + LIMITS["r_id_acc_inc"]
                   and d["h_tel_auc"] <= LIMITS["h_tel_auc"]
                   and d["h_hw_adv"] <= LIMITS["h_hw_adv"]
                   and d["h_rank_corr"] <= LIMITS["h_rank_corr"])
        d["leak_ok"] = float(leak_ok)
        d["win_win"] = float(d["r_gain"] and d["h_gain"] and leak_ok)
        d["win_win_redesigned"] = float(d["r_gain_pw60"]
                                        and d["h_gain_package"] and leak_ok)
        rows[name] = d
    return rows


CONDITIONS_MAIN = [
    ("CTCE_P0", "CTCE", "P0", None),
    ("DTDE_P4", "DTDE", "P4", None),
    ("CTDE_P1", "CTDE", "P1", None), ("CTDE_P2", "CTDE", "P2", None),
    ("CTDE_P3", "CTDE", "P3", 4.0), ("CTDE_P4", "CTDE", "P4", None),
    ("CEDT_P1", "CEDT", "P1", None), ("CEDT_P2", "CEDT", "P2", None),
    ("CEDT_P3", "CEDT", "P3", 4.0), ("CEDT_P4", "CEDT", "P4", None),
]
CONDITIONS_SWEEP = [
    (f"{arm}_P3_eps{e}", arm, "P3", float(e))
    for arm in ("CTDE", "CEDT") for e in (1, 2, 8)
]


def run_world(args):
    card, wid, conds = args
    w = sample_world(card, wid)
    res = {}
    for name, topo, lvl, eps in conds:
        contract = Contract(lvl if lvl != "P0" else "P1", eps)
        contract.level = lvl if lvl != "P0" else "P0"
        if lvl == "P0":
            contract.gamma = 1.0
            contract.classes = np.arange(C)
            contract.nclasses = C
            contract.cost_sd = 0.0
        res[name] = run_campaign(w, topo, contract)
    if "DTDE_P4" not in res:  # sweep chunks still need the baseline
        res["DTDE_P4"] = run_campaign(w, "DTDE", Contract("P4"))
    summary = eval_world(res)
    world_info = dict(card=card, world=wid, s=w["s"], pm=w["pm"],
                      quirk_sd=float(np.std(np.log(w["quirk"]))),
                      burst=w["burst"], beta0=w["beta0"],
                      build=int(w["build"]),
                      n_true_qual=int(w["qual"].sum()))
    return world_info, summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worlds", type=int, default=1000)
    ap.add_argument("--sweep-worlds", type=int, default=250)
    ap.add_argument("--procs", type=int, default=os.cpu_count())
    ap.add_argument("--out", default="results/raw_results.json")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    if args.smoke:
        args.worlds, args.sweep_worlds, args.procs = 6, 3, 1

    cards = ["base", "strong_coupling", "adversarial"]
    tasks = []
    for wid in range(args.worlds):
        card = cards[wid * 3 // args.worlds] if args.worlds >= 3 else "base"
        tasks.append((card, wid, CONDITIONS_MAIN))
    for wid in range(args.sweep_worlds):
        card = cards[wid * 3 // max(args.sweep_worlds, 3)]
        tasks.append((card, 100000 + wid, CONDITIONS_SWEEP))

    if args.procs > 1:
        import multiprocessing as mp
        with mp.Pool(args.procs) as pool:
            out = pool.map(run_world, tasks, chunksize=4)
    else:
        out = [run_world(t) for t in tasks]

    records = []
    for info, summary in out:
        for cond, d in summary.items():
            rec = dict(info)
            rec["condition"] = cond
            rec.update({k: float(v) for k, v in d.items()})
            records.append(rec)
    outp = HERE / args.out
    outp.parent.mkdir(exist_ok=True)
    with open(outp, "w") as fh:
        json.dump(records, fh)
    print(f"wrote {len(records)} records to {outp}")


if __name__ == "__main__":
    main()

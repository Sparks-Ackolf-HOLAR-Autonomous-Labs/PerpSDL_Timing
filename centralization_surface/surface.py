#!/usr/bin/env python3
"""Centralization surface for the QE privacy-tax experiment.

Aim: a graph whose x-y axes are the *degree of
centralization* of TRAINING and EXECUTION, each in [0, 1], so that the four
named topologies sit at the corners of the unit square, and whose z-axis is a
performance metric from the frozen evaluation:

      execution-centralization eps ->
   1 | CEDT ................ CTCE
     |  .                     .
     |  .      MIX(tau,eps)   .
     |  .                     .
   0 | DTDE ................ CTDE
     +------------------------------
       0                        1   training-centralization tau ->

    (tau=0, eps=0) = DTDE   decentralized train, decentralized execute
    (tau=1, eps=0) = CTDE   shared surrogate,    local execute
    (tau=0, eps=1) = CEDT   local train,         broker execute
    (tau=1, eps=1) = CTCE   shared everything,   coordinated execute

The interior is a genuinely continuous MIX arm: tau blends R's cost model and
H's size belief between the DTDE self-estimate and the shared surrogate; eps
blends H's execution policy between the local worst-case reservation and the
broker's class-matched config, and opens the broker's per-round runtime
channel to R. Leakage exposure scales with how far open the channels are.

All numbers are SIMULATED UNITS. Nothing here is a CHPC measurement. The twin
physics (cost/memory/failure expressions, prior cards, paired noise) are
imported unchanged from simulator.py, so the corners reproduce the native
DTDE/CTDE/CEDT arms and CTCE-P0 ceiling to within Monte-Carlo error.
"""
import argparse
import json
import os
from pathlib import Path

import numpy as np
from scipy.stats import norm

import sys
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "prior_predictive"))
import simulator as S  # noqa: E402

C = S.C
NSEED = S.S
T = S.T
BUDGET = S.BUDGET_NH
OVER = S.OVERHEAD_NH
GAP_LO, GAP_HI = S.GAP_LO, S.GAP_HI
NODE_MEM = S.NODE_MEM_GB
CONFIGS = S.CONFIGS
C_AGG = S.C_AGG
C_IO = S.C_IO
FIDS = S.FIDS
NK = S.NK
LIMITS = S.LIMITS
# Size-adjusted shared logbook (kMC rung, 2026-10-10). False keeps every
# earlier result unchanged: the logbook stores raw log node-hours per (class, fid, config)
# and predicts the class mean. True stores log node-hours minus R's public size law
# log(rel) and adds log(rel) back at prediction, so the logbook carries only the part of
# the cost that size does not explain (the class residual).
SURR_SIZE_ADJ = False

# Vacancy-immobility goal (2026-10-12;vacancy_barriers/GOAL_CHANGE.md).
# Both default off, so every earlier result is unchanged.
# IMMOBILE_FN: callable w -> (C,) bool. When set, a compound qualifies at F4 only if it
#   is also immobile (vacancy hop barrier >= E_min); the verdict reaches R at F4.
# PASSRATE_TRAIN: when True, the shared logbook (training channel, open by tau, P1-P3
#   only) also records the immobility outcome of each completed F3 step (the kMC anneal)
#   per descriptor class, and R multiplies its value for a compound by
#   (1 - tau) * 0.5 + tau * class pass rate, with a Beta(1, 1) prior (0.5 with no record).
IMMOBILE_FN = None
PASSRATE_TRAIN = False


def _as_schedule(x):
    """Return a length-T per-round array. Scalar -> constant schedule (so the
    scalar path is bit-identical to before); a length-T array is used as-is for
    the adaptive schedules in schedules.py (eps/tau varying during a campaign)."""
    a = np.atleast_1d(np.asarray(x, dtype=float))
    if a.size == 1:
        return np.full(T, float(a[0]))
    if a.size != T:
        raise ValueError(f"schedule length {a.size} != T={T}")
    return a


def run_mix(w, tau, eps, level, eps_dp=4.0, nparty=1):
    """One world, one (tau, eps) point at disclosure `level`, S seeds.

    tau and eps may each be a scalar (a fixed point on the surface) or a
    length-T array (an adaptive schedule that changes the degree of training /
    execution centralization DURING the campaign; see schedules.py). Scalars
    reproduce the static surface exactly.

    Reduces (approximately) to the native arms at the corners:
      (0,0)->DTDE  (1,0)->CTDE  (0,1)->CEDT  (1,1)->CTCE@level (filtered
      full centralization; formerly written "HYB" -- name retired 2026-09-22).
      CTCE@P0 is the unfiltered merged-seat ceiling.

    Multi-party (reduced form): with nparty > 1 research
    parties sharing one HPC provider, three aggregate effects are applied and
    documented in RESULTS.md (none change the N=1 result):
      * node CONTENTION rises (busier shared machine) -> kappa scaled up;
      * a POOLED shared surrogate learns from all parties -> centralized
        training (tau>0) ingests nparty samples per observed job;
      * leakage CROWDING -> the attacker aggregates across parties, so
        membership/identity/telemetry exposure grows ~log(nparty).
    """
    cont_scale = 1.0 + 0.10 * (nparty - 1)     # shared-node contention
    pool_boost = nparty                         # pooled-surrogate ingest
    crowd = 1.0 + 0.35 * np.log(max(nparty, 1))  # leakage crowding factor
    tau_sched = _as_schedule(tau)
    eps_sched = _as_schedule(eps)
    # campaign-mean centralization drives the cumulative leakage aggregate
    tau, eps = float(tau_sched.mean()), float(eps_sched.mean())
    contract = S.Contract(level if level != "P0" else "P1", eps_dp)
    contract.level = level
    if level == "P0":
        contract.gamma = 1.0
        contract.classes = np.arange(C)
        contract.nclasses = C
        contract.cost_sd = 0.0
    lvl = level
    gam = contract.gamma
    cls = (np.arange(C) if lvl == "P0" else S.world_classes(w, lvl))
    contract = S.ContractView(contract, cls)
    nb = contract.nclasses

    # channel availabilities (continuous)
    has_broker = eps if lvl in ("P0", "P1", "P2", "P3") else 0.0
    has_surr = tau if lvl != "P4" else 0.0
    # per-channel leakage union: the broker channel (open by eps) and the
    # surrogate channel (open by tau) each expose independently, so total
    # exposure is 1-(1-a_eps)(1-a_tau). This reduces to eps when tau=0 and to
    # tau when eps=0, and is smooth and monotone in BOTH coordinates.
    # (Replaces open_frac = max(tau, eps), which was flat in the smaller axis
    # and produced no gradient off the diagonal.)
    a_eps = eps if lvl in ("P0", "P1", "P2", "P3") else 0.0
    a_tau = tau if lvl != "P4" else 0.0
    open_frac = float(np.clip(1.0 - (1.0 - a_eps) * (1.0 - a_tau), 0.0, 1.0))
    # per-round execution-delegation thresholds (CRN, world-specific): a round
    # runs the broker's aggressive config iff its fixed uniform draw < eps, so
    # eps is a genuine mixing FRACTION of rounds -- monotone in eps and paired
    # across (tau, eps) points for the same world. Replaces the old
    # `aggressive_ok = eps > 0.5`, a hard switch at the grid midpoint.
    _dseed = int(abs(float(np.sum(w["kappa"][:, 0])) * 1e6)) % (2 ** 31 - 1)
    delg_u = np.random.default_rng(_dseed).random((NSEED, T))

    mu = np.tile(S.GAP_PRIOR_MU, (NSEED, 1))
    prec = np.full((NSEED, C), 1.0 / 0.5 ** 2)
    fid_done = np.full((NSEED, C), -1)
    dead = np.zeros((NSEED, C), bool)
    qualified = np.zeros((NSEED, C), bool)
    nh_used = np.zeros(NSEED)
    attempts = np.zeros(NSEED, int)
    fails = np.zeros(NSEED, int)
    memfails = np.zeros(NSEED, int)
    labels_f2 = np.zeros(NSEED, int)
    att_f2 = np.zeros(NSEED, int)
    first_qual_nh = np.full(NSEED, np.nan)
    qe_calls = np.zeros(NSEED, int)
    attempt_ct = np.zeros((NSEED, C, FIDS), int)
    queried = np.zeros((NSEED, C), bool)
    mi_score = np.zeros((NSEED, C))
    cfg_obs_sum = np.zeros((NSEED, len(CONFIGS)))
    cfg_obs_n = np.zeros((NSEED, len(CONFIGS)))
    sur_sum = np.zeros((NSEED, nb, FIDS, len(CONFIGS)))
    sur_n = np.zeros((NSEED, nb, FIDS, len(CONFIGS)))
    chg_sum = np.zeros((NSEED, FIDS))
    chg_n = np.zeros((NSEED, FIDS))
    rel = (S.CAND["nelec"] / 38.0) ** 2.5
    nelec_hi = np.quantile(S.CAND["nelec"], 0.9)

    wk_all = np.stack([S.base_work(w, ff) for ff in range(FIDS)])
    eff_all = np.stack([S.eff_matrix(w, ff) for ff in range(FIDS)])
    mem_all = np.stack([S.mem_per_node(w, ff) for ff in range(FIDS)])
    hard_all = mem_all > NODE_MEM
    headroom_all = np.clip(NODE_MEM / mem_all, 0.2, 20.0)
    z0_all = (w["beta0"] + 0.8 * C_AGG[None, None, :]
              - 1.5 * np.log(headroom_all))
    best_cost_all = (wk_all[:, :, None] / eff_all).min(2)

    immob = IMMOBILE_FN(w) if IMMOBILE_FN is not None else None
    use_pr = (PASSRATE_TRAIN and immob is not None and has_surr > 0 and gam > 0)
    pr_n = np.zeros((NSEED, nb))
    pr_k = np.zeros((NSEED, nb))

    cls_top = np.array([S.CAND["nelec"][cls == b].max() for b in range(nb)])
    rho_top = np.array([w["rho"][cls == b].max() for b in range(nb)])

    active = np.ones(NSEED, bool)
    for t in range(T):
        if not active.any():
            break
        kap = np.clip(w["kappa"][:, t] * cont_scale, 0.0, 1.0)
        # per-round execution-channel weight (broker). For a static point this
        # equals has_broker every round; for an adaptive eps-schedule it tracks
        # eps_sched[t], so the broker's influence rises/falls during the run.
        hb_t = eps_sched[t] if lvl in ("P0", "P1", "P2", "P3") else 0.0
        sd = 1.0 / np.sqrt(prec)
        pwin = norm.cdf((GAP_HI - mu) / sd) - norm.cdf((GAP_LO - mu) / sd)
        value = pwin ** 2 * S.PHONON_PRIOR[None, :]
        if use_pr:
            rate = (pr_k[:, cls] + 1.0) / (pr_n[:, cls] + 2.0)
            value = value * ((1.0 - has_surr) * 0.5 + has_surr * rate)
        value[dead | qualified] = 0.0
        nfid = np.clip(fid_done + 1, 1, 4)
        f4block = (nfid == 4) & (pwin < 0.5)
        value[f4block] = 0.0
        wk_next = wk_all[nfid, np.arange(C)[None, :]]
        ar = np.arange(NSEED)[:, None]

        # --- R cost estimate: geometric blend of open channels ---
        own_est = wk_next / 0.8
        cn = np.take_along_axis(chg_n, nfid, axis=1)
        cs = np.take_along_axis(chg_sum, nfid, axis=1)
        base_chg = np.where(cn > 0, cs / np.maximum(cn, 1), wk_next / 0.8)
        own_est = base_chg * rel[None, :] / rel.mean()
        log_own = np.log(np.maximum(own_est, 0.02))
        logblend = log_own.copy()
        if lvl == "P0":  # ceiling reference, only ever evaluated at (1,1)
            full_est = best_cost_all[nfid, np.arange(C)[None, :]]
            logblend = logblend + open_frac * (
                np.log(np.maximum(full_est, 0.02)) - logblend)
        else:
            # Channel corrections are convex-combined: raw weights are the
            # channel opennesses (wsurr, hb_t), but their SUM is capped at 1 so
            # the weight left on R's own estimate, 1 - wsurr - hb_t, can never
            # go negative. Without the cap, points with tau + eps > 1 (the
            # upper-right triangle) EXTRAPOLATED beyond the channels -- log
            # weights (1-tau-eps) < 0 on own_est -- instead of interpolating,
            # distorting R's cost ranking exactly where both channels are open.
            # Corners are unaffected (weight sums there are <= 1); at (1,1) the
            # blend is now the geometric mean of the surrogate and broker
            # estimates, a proper mixture.
            wsurr = np.zeros((NSEED, C))
            log_pred = log_own
            if has_surr > 0:
                sidx = ar
                cidx = np.broadcast_to(cls[None, :], (NSEED, C))
                sn = sur_n[sidx, cidx, nfid, :]
                ss = sur_sum[sidx, cidx, nfid, :]
                ntot = sn.sum(2)
                have = ntot > 0
                lmean = ss.sum(2) / np.maximum(ntot, 1)
                if SURR_SIZE_ADJ:
                    lmean = lmean + np.log(rel)[None, :]
                pred = np.where(have, np.exp(lmean), own_est)
                wsurr = has_surr * have
                log_pred = np.log(np.maximum(pred, 0.02))
            wbrok = 0.0
            log_brok = log_own
            if hb_t > 0:
                broker_est = (best_cost_all[nfid, np.arange(C)[None, :]]
                              * np.exp(w["view_noise"] * contract.cost_sd))
                wbrok = hb_t
                log_brok = np.log(np.maximum(broker_est, 0.02))
            wtot = wsurr + wbrok
            scale = np.where(wtot > 1.0, 1.0 / np.maximum(wtot, 1e-9), 1.0)
            logblend = (log_own
                        + scale * wsurr * (log_pred - log_own)
                        + scale * wbrok * (log_brok - log_own))
        cost_est = np.exp(logblend)

        acq = value / (np.maximum(cost_est, 0.02) + OVER)
        acq *= np.where(nfid == 1, 1.5, 1.0)
        pick = acq.argmax(1)
        no_move = acq[np.arange(NSEED), pick] <= 1e-12
        run_mask = active & ~no_move
        if not run_mask.any():
            break
        i = pick
        f = nfid[np.arange(NSEED), i]
        wk_i = wk_all[f, i]
        eff_i = eff_all[f, i, :]
        z0_i = z0_all[f, i, :]
        pf_i = 1.0 / (1.0 + np.exp(-(z0_i + 1.2 * (kap[:, None] - 0.3))))
        hard_i = hard_all[f, i, :]
        true_nh = wk_i[:, None] / eff_i * (1 + kap[:, None] * C_IO[None, :])
        esc = 1.6 ** np.minimum(attempt_ct[np.arange(NSEED), i, f], 3)

        # --- H / joint config choice: interpolate belief + policy ---
        if lvl == "P0":  # merged-seat oracle ceiling, only evaluated at (1,1)
            score = true_nh * (1 + 2 * pf_i) + 1e3 * hard_i
            j = score.argmin(1)
        else:
            cls_i = cls[i]
            # size belief informed by whichever channel is more open
            if has_surr > 0:
                wts = sur_n[np.arange(NSEED), :, f, :].sum(2)
                ntot_s = wts.sum(1)
                # smooth surrogate confidence n/(n+n0): 0 with no records,
                # rising continuously as the shared logbook fills. Blends the
                # size/memory belief from the q90 prior toward what the pooled
                # surrogate has seen. Replaces the `>= 5` warm-up cliff, which
                # made tau's effect switch on discontinuously.
                conf = ntot_s / (ntot_s + 4.0)
                ne_seen = np.where(wts > 0, cls_top[None, :], 0.0).max(1)
                rho_seen = np.where(wts > 0, rho_top[None, :], 0.0).max(1)
                ne_seen = np.where(ntot_s > 0, ne_seen, nelec_hi)
                rho_seen = np.where(ntot_s > 0, rho_seen, 1.56)
                ne_surr = conf * ne_seen + (1 - conf) * nelec_hi
                rho_surr = conf * rho_seen + (1 - conf) * 1.56
            else:
                ne_surr = np.full(NSEED, nelec_hi)
                rho_surr = np.full(NSEED, 1.56)
            ne_broker = gam * cls_top[cls_i] + (1 - gam) * nelec_hi
            rho_broker = gam * rho_top[cls_i] + (1 - gam) * 1.56
            # blend: weight toward broker by eps, toward surrogate by tau
            g_b = hb_t
            g_s = has_surr * (1 - g_b)
            g_own = max(0.0, 1 - g_b - g_s)
            ne_belief = (g_b * ne_broker + g_s * ne_surr
                         + g_own * nelec_hi)
            rho_belief = (g_b * rho_broker + g_s * rho_surr
                          + g_own * 1.56)
            # Probabilistic per-round delegation: the fraction eps of seeds
            # whose CRN draw this round is below eps run the broker's aggressive
            # config; the rest run H's local conservative config. Sweeping eps
            # 0 -> 1 mixes the two policies smoothly, so the execution axis is a
            # true gradient instead of a hard switch. rho_belief already blends
            # by channel openness (broker vs surrogate vs own prior).
            delegate = delg_u[:, t] < eps_sched[t]
            j_aggr = S._h_config(w, f, ne_belief, kap, aggressive_ok=True,
                                 rho_belief=rho_belief * esc)
            j_cons = S._h_config(w, f, ne_belief, kap, aggressive_ok=False,
                                 rho_belief=rho_belief * esc)
            j = np.where(delegate, j_aggr, j_cons)

        att_i = np.minimum(attempt_ct[np.arange(NSEED), i, f], 3)
        noise = w["nh_noise"][np.arange(NSEED), i, f, att_i]
        nh_real = true_nh[np.arange(NSEED), j] * noise
        pfail = pf_i[np.arange(NSEED), j]
        hard = hard_i[np.arange(NSEED), j]
        u = w["fail_u"][np.arange(NSEED), i, f, att_i]
        failed = (u < pfail) | hard
        spend = np.where(failed, 0.45 * nh_real, nh_real) + OVER
        m = run_mask
        nh_used[m] += spend[m]
        attempts[m] += 1
        qe_calls[m] += 1
        attempt_ct[m, i[m], f[m]] += 1
        queried[m, i[m]] = True
        fails[m] += failed[m]
        memfails[m] += (failed & hard)[m]
        att_f2[m & (f >= 2)] += 1
        ok = m & ~failed
        if ok.any():
            fs, iss = f[ok], i[ok]
            fid_done[ok, iss] = fs
            labels_f2[ok & (f >= 2)] += 1
            obs_mask = ok & (f >= 1) & (f <= 3)
            if obs_mask.any():
                io_, fo_ = i[obs_mask], f[obs_mask]
                soc_add = np.where(fo_ == 3, w["soc"][io_], 0.0)
                obs = (w["gap"][io_] + soc_add
                       + w["gap_noise"][obs_mask, io_, fo_] * S.SIG_GAP_OBS[fo_])
                p_obs = 1.0 / S.SIG_GAP_OBS[fo_] ** 2
                new_prec = prec[obs_mask, io_] + p_obs
                mu[obs_mask, io_] = (mu[obs_mask, io_] * prec[obs_mask, io_]
                                     + obs * p_obs) / new_prec
                prec[obs_mask, io_] = new_prec
            f0m = ok & (f == 1)
            if f0m.any():
                inval = ~w["valid"][i[f0m]]
                dd = np.where(f0m)[0][inval]
                dead[dd, i[f0m][inval]] = True
            f4m = ok & (f == 4)
            if f4m.any():
                i4 = i[f4m]
                gap_f = w["gap"][i4] + w["soc"][i4]
                qn = w["stable"][i4] & (gap_f >= GAP_LO) & (gap_f <= GAP_HI) & w["valid"][i4]
                if immob is not None:
                    qn = qn & immob[i4]
                rows = np.where(f4m)[0]
                qualified[rows[qn], i4[qn]] = True
                dead[rows[~qn], i4[~qn]] = True
                newq = rows[qn]
                fq = np.isnan(first_qual_nh[newq])
                first_qual_nh[newq[fq]] = nh_used[newq[fq]]
            if use_pr:
                f3m = ok & (f == 3)
                if f3m.any():
                    r3 = np.where(f3m)[0]
                    np.add.at(pr_n, (r3, cls[i[r3]]), pool_boost)
                    np.add.at(pr_k, (r3, cls[i[r3]]), pool_boost * immob[i[r3]])
        exhausted = m & failed & (attempt_ct[np.arange(NSEED), i, f] >= 3)
        if exhausted.any():
            dead[exhausted, i[exhausted]] = True
        f3done = (fid_done == 3)
        sd2 = 1.0 / np.sqrt(prec)
        pw2 = norm.cdf((GAP_HI - mu) / sd2) - norm.cdf((GAP_LO - mu) / sd2)
        dead |= f3done & (pw2 < 0.15)
        realized = lvl in ("P0", "P1")
        charge = np.where(realized, nh_real, wk_i / 0.8)
        chg_sum[m, f[m]] += charge[m]
        chg_n[m, f[m]] += 1
        if has_surr > 0 and gam > 0:
            sur_sum[m, cls[i[m]], f[m], j[m]] += pool_boost * (np.log(
                np.maximum(nh_real[m], 1e-3))
                - (np.log(rel[i[m]]) if SURR_SIZE_ADJ else 0.0))
            sur_n[m, cls[i[m]], f[m], j[m]] += pool_boost
        if open_frac > 0 and lvl != "P4":
            bsz = np.array([(cls == b).sum() for b in range(nb)])
            mi_score[m] += (cls[None, :] == cls[i[m]][:, None]) / bsz[cls[i[m]]][:, None]
        cfg_obs_sum[m, j[m]] += np.log(np.maximum(nh_real, 1e-3))[m]
        cfg_obs_n[m, j[m]] += 1
        active &= (nh_used < BUDGET) & (attempts < S.MAX_ATTEMPTS)
        active &= ((~dead) & (~qualified)).any(1)

    return _score_mix(w, tau, eps, lvl, gam, open_frac, has_broker, has_surr, crowd, dict(
        mu=mu, prec=prec, fid_done=fid_done, qualified=qualified,
        nh_used=nh_used, attempts=attempts, fails=fails, memfails=memfails,
        labels_f2=labels_f2, att_f2=att_f2, first_qual_nh=first_qual_nh,
        qe_calls=qe_calls, queried=queried, mi_score=mi_score,
        cfg_obs_sum=cfg_obs_sum, cfg_obs_n=cfg_obs_n))


def _score_mix(w, tau, eps, lvl, gam, open_frac, has_broker, has_surr, crowd, st):
    atk = w["atk"] * crowd
    out = {}
    nh = np.maximum(st["nh_used"], 1e-6)
    out["qual_count"] = st["qualified"].sum(1).astype(float)
    out["found"] = (~np.isnan(st["first_qual_nh"])).astype(float)
    out["nh_first"] = np.where(np.isnan(st["first_qual_nh"]), BUDGET,
                               st["first_qual_nh"])
    out["labels_per_nh"] = st["labels_f2"] / nh
    out["fail_rate"] = st["fails"] / np.maximum(st["attempts"], 1)
    out["memfail_rate"] = st["memfails"] / np.maximum(st["attempts"], 1)
    out["validity"] = st["labels_f2"] / np.maximum(st["att_f2"], 1)
    out["nh_used"] = st["nh_used"]
    # ---- leakage: scale native-arm exposure by channel openness ----
    if lvl == "P0":  # full-disclosure ceiling, only evaluated at (1,1)
        out["r_mi_auc"] = np.full(NSEED, 1.0)
        out["r_comp_adv"] = np.full(NSEED, 1 - 1 / 15)
        out["r_id_acc"] = np.full(NSEED, 1.0)
        out["h_rank_corr"] = np.full(NSEED, 1.0)
        out["h_hw_adv"] = np.full(NSEED, 2 / 3)
        out["h_tel_auc"] = np.full(NSEED, 1.0)
        return out
    cls = S.world_classes(w, lvl) if lvl not in ("P4",) else np.zeros(C, int)
    rounds = np.maximum(st["attempts"], 1).astype(float)
    if open_frac <= 0 or lvl == "P4":
        mi = np.full(NSEED, 0.5)
        comp_adv = np.zeros(NSEED)
        id_acc = np.full(NSEED, 1 / C)
    else:
        mi = np.array([S._auc(st["mi_score"][s][st["queried"][s]],
                              st["mi_score"][s][~st["queried"][s]])
                       for s in range(NSEED)])
        comps = S.CAND["comp"]
        acc = np.zeros(C)
        for i in range(C):
            same = cls == cls[i]
            acc[i] = 1.0 / max(np.unique(comps[same]).size, 1)
        nq = np.maximum(st["queried"].sum(1), 1)
        qacc = np.where(st["queried"], acc[None, :] * gam, 0.0)
        comp_adv = np.clip((qacc.sum(1) / nq - 1 / 15) * atk * open_frac, 0, 1)
        idacc_c = np.array([1.0 / max((cls == cls[i]).sum(), 1) for i in range(C)])
        qid = np.where(st["queried"], idacc_c[None, :] * gam, 0)
        id_acc = np.clip((1 / C) + (qid.sum(1) / nq - 1 / C) * atk * open_frac, 0, 1)
        mi = np.clip(0.5 + (mi - 0.5) * atk * open_frac, 0, 1)
    out["r_mi_auc"] = mi
    out["r_comp_adv"] = comp_adv
    out["r_id_acc"] = id_acc
    # H-side: rank/hw/telemetry driven by disclosure precision and open_frac
    sd_map = {"P1": 0.10, "P2": 0.60, "P3": 0.60, "P4": 3.0}
    sd0 = sd_map.get(lvl, 3.0)
    if lvl == "P3":
        sd0 = min(0.60 / max(gam, 0.05), 3.0)
    true_eff = np.log((S.C_NODES ** (w["s"] - 1.0)) * w["quirk"] * (1 + 0.25 * C_AGG))
    var_sig = max(np.var(true_eff), 1e-8)
    noise_var = (sd0 ** 2 / np.maximum(st["cfg_obs_n"], 0.25)).mean(1)
    corr = np.sqrt(var_sig / (var_sig + noise_var))
    out["h_rank_corr"] = np.clip(corr * atk * open_frac, 0, 1)
    sep = 0.12
    sd_sys = {"P1": 0.05, "P2": 0.15, "P3": 0.25, "P4": 0.35}.get(lvl, 0.35)
    sd_obs = {"P1": 0.10, "P2": 0.45, "P4": 1.5}.get(lvl, 1.5)
    if lvl == "P3":
        sd_obs = min(0.45 / max(gam, 0.05), 3.0)
    sd_est = np.sqrt(sd_sys ** 2 + sd_obs ** 2 * 2.25 / rounds)
    snr = sep / np.maximum(sd_est, 1e-6)
    acc3 = 1 / 3 + (4 / 3) * (norm.cdf(snr / 2) - 0.5)
    out["h_hw_adv"] = np.clip((acc3 - 1 / 3) * atk * open_frac, 0, 1)
    pf_map = {"P1": 0.8, "P2": 0.35, "P3": 0.35, "P4": 0.12}
    pf = pf_map.get(lvl, 0.12)
    if lvl == "P3":
        pf *= gam
    # broker per-round channel raises telemetry membership; surrogate lowers
    pf *= (1 + 0.3 * has_broker - 0.3 * has_surr * (1 - has_broker))
    auc_t = 0.5 + 0.5 * pf * (1 - np.exp(-rounds / 40.0)) * w["burst"]
    out["h_tel_auc"] = np.clip(0.5 + (auc_t - 0.5) * atk * open_frac, 0, 1)
    return out


def eval_point(res, base):
    d = {}
    d["nh_first"] = res["nh_first"].mean()
    d["found_rate"] = res["found"].mean()
    d["mean_qual"] = res["qual_count"].mean()
    d["labels_per_nh"] = res["labels_per_nh"].mean()
    d["fail_rate"] = res["fail_rate"].mean()
    d["validity"] = res["validity"].mean()
    for k in ("r_mi_auc", "r_comp_adv", "r_id_acc", "h_rank_corr",
              "h_hw_adv", "h_tel_auc"):
        d[k] = res[k].mean()
    base_lpnh = base["labels_per_nh"].mean()
    d["labels_ratio"] = d["labels_per_nh"] / max(base_lpnh, 1e-9)
    d["pw_rate"] = float((res["nh_first"] < base["nh_first"]).mean())
    r_valid_ok = d["validity"] >= base["validity"].mean() - 0.01
    d["r_gain_pw60"] = float(d["pw_rate"] >= 0.60
                             and d["found_rate"] >= base["found"].mean() - 1e-9
                             and r_valid_ok)
    hp1 = d["labels_per_nh"] >= 1.05 * base_lpnh
    hp2 = d["fail_rate"] <= base["fail_rate"].mean() + 0.04
    hp3 = (np.percentile(res["memfail_rate"], 95)
           <= np.percentile(base["memfail_rate"], 95) + 1e-9)
    d["h_gain_package"] = float(hp1 and hp2 and hp3)
    leak_ok = (d["r_mi_auc"] <= LIMITS["r_mi_auc"]
               and d["r_comp_adv"] <= LIMITS["r_comp_adv"]
               and d["r_id_acc"] <= 1 / C + LIMITS["r_id_acc_inc"]
               and d["h_tel_auc"] <= LIMITS["h_tel_auc"]
               and d["h_hw_adv"] <= LIMITS["h_hw_adv"]
               and d["h_rank_corr"] <= LIMITS["h_rank_corr"])
    d["leak_ok"] = float(leak_ok)
    d["win_win"] = float(d["r_gain_pw60"] and d["h_gain_package"] and leak_ok)
    return d


def run_grid_world(arg):
    card, wid, grid, level = arg
    w = S.sample_world(card, wid)
    base = run_mix(w, 0.0, 0.0, level)          # DTDE baseline at this level
    base4 = _score_mix_baseline(w)              # DTDE-P4 canonical baseline
    out = {}
    for (tau, eps) in grid:
        res = run_mix(w, tau, eps, level)
        out[(tau, eps)] = eval_point(res, base4)
    # CTCE ceiling at full disclosure, placed at (1,1)
    ceil = run_mix(w, 1.0, 1.0, "P0")
    out[("ceiling", "P0")] = eval_point(ceil, base4)
    return wid, card, out


def _score_mix_baseline(w):
    return run_mix(w, 0.0, 0.0, "P4")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worlds", type=int, default=150)
    ap.add_argument("--grid", type=int, default=6)
    ap.add_argument("--level", default="P2")
    ap.add_argument("--procs", type=int, default=os.cpu_count())
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    if args.smoke:
        args.worlds, args.grid, args.procs = 4, 3, 1
    axis = np.linspace(0, 1, args.grid)
    grid = [(round(float(a), 4), round(float(b), 4)) for a in axis for b in axis]
    cards = ["base", "strong_coupling", "adversarial"]
    tasks = [(cards[w * 3 // args.worlds] if args.worlds >= 3 else "base",
              w, grid, args.level) for w in range(args.worlds)]
    if args.procs > 1:
        import multiprocessing as mp
        with mp.Pool(args.procs) as pool:
            res = pool.map(run_grid_world, tasks, chunksize=2)
    else:
        res = [run_grid_world(t) for t in tasks]

    # aggregate
    agg = {}
    for wid, card, out in res:
        for key, d in out.items():
            agg.setdefault(key, []).append(d)
    surface = {}
    for key, lst in agg.items():
        tau, eps = key
        surface[f"{tau}|{eps}"] = {
            "tau": tau, "eps": eps,
            "win_win": float(np.mean([x["win_win"] for x in lst])),
            "r_gain_pw60": float(np.mean([x["r_gain_pw60"] for x in lst])),
            "h_gain_package": float(np.mean([x["h_gain_package"] for x in lst])),
            "leak_ok": float(np.mean([x["leak_ok"] for x in lst])),
            "labels_ratio": float(np.mean([x["labels_ratio"] for x in lst])),
            "pw_rate": float(np.mean([x["pw_rate"] for x in lst])),
            "mean_qual": float(np.mean([x["mean_qual"] for x in lst])),
            "r_id_acc": float(np.mean([x["r_id_acc"] for x in lst])),
            "h_rank_corr": float(np.mean([x["h_rank_corr"] for x in lst])),
        }
    meta = dict(worlds=args.worlds, grid=args.grid, level=args.level,
                seeds=NSEED, note="SIMULATED UNITS; twin from simulator.py")
    outp = HERE / "results" / f"surface_{args.level}.json"
    with open(outp, "w") as fh:
        json.dump({"meta": meta, "surface": surface}, fh, indent=1)
    print(f"wrote {outp} ({len(surface)} points, {args.worlds} worlds)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Educator/student conditions (spec
Sections 4.5-4.8, 8 Q-levels, 9.3) and the tractable Section 13.2 ablations.

This module deliberately does NOT modify simulator.py (the dataset of
record). run_campaign_ext is a copy of simulator.run_campaign with five
extensions, each gated by an `opts` field whose default reproduces the
original behavior:

  * h_policy="student": H's config choice is made by a student operator
    whose beliefs are set by the education level Q0-Q3 and hint budget
    (spec 4.6, 8). Execution truth is unchanged; only the config choice
    and its consequences differ.
  * cost_channel in {"rank", "bit"}: ablation 13.2-2 — H's disclosed
    runtime scores replaced by rank-only or one-bit disclosures (CEDT).
  * r_controls_config=True: ablation 13.2-7 — R chooses the config from
    H's P2-precision config menu (R knows its own rho exactly but not
    H's memq/quirk/scaling).
  * kappa_shift>0: ablation 13.2-8 — unanticipated contention-regime
    shift of +kappa_shift at round T_SHIFT.
  * The R membership attacker is additionally scored with only the last
    MI_WINDOW rounds of transcript: ablation 13.2-4 (composition/
    linkability risk = cumulative minus windowed AUC).

All node-hours remain SIMULATED UNITS (prior_predictive_simulation mode).
Educator-effort constants and curriculum-attack precisions are model
beliefs, recorded as such; kappa_S and b_E are not fixed by the
study design, so the analysis sweeps them instead of fixing them.
"""
import argparse
import json
import os
from pathlib import Path

import numpy as np
from scipy.stats import norm

import simulator as sim
from simulator import (S, T, FIDS, NK, C_NODES, C_POOLS, C_AGG, C_IO,
                       NODE_MEM_GB, BUDGET_NH, OVERHEAD_NH, MAX_ATTEMPTS,
                       GAP_LO, GAP_HI, SIG_GAP_OBS, CAND, C, J,
                       GAP_PRIOR_MU, PHONON_PRIOR, Contract, ContractView,
                       world_classes, base_work, eff_matrix, mem_per_node,
                       pool_eff, _h_config, _auc, eval_world)

HERE = Path(__file__).parent
T_SHIFT = 12   # campaigns exhaust the 500-nh budget near round ~27, so a
# mid-campaign regime change must land well before that (13.2-8)
MI_WINDOW = 10

# ---------------------------------------------------------------------------
# education levels: student operator beliefs (spec 4.6/8) and educator effort
# (model constants in educator-hours; kappa_S/b_E swept in analysis)

EDU = {
    #        s_bel  pm_bel beta0  kapc  ne_q  rho   agg    esc  gammaQ effort
    "Q0": dict(s=1.00, pm=0.0, b0=None, kc=0.0, neq=0.50, rho=1.00,
               agg=True, esc=False, gq=0.0, effort=0.0),
    "Q1": dict(s=0.70, pm=0.3, b0=-3.0, kc=0.5, neq=0.90, rho=1.56,
               agg=False, esc=True, gq=0.0, effort=6.0),
    "Q2": dict(s=0.70, pm=0.3, b0=-3.0, kc=0.75, neq=0.90, rho=1.56,
               agg=False, esc=True, gq=0.5, effort=10.0),
    "Q3": dict(agg=False, esc=True, gq=1.0, effort=20.0),  # oracle = expert
}
HINT_EFFORT = 0.75  # educator-hours per approved bounded hint


def student_h_config(w, f, kap, q, hints, att_esc):
    """Student's config choice for the current job under education level q.

    The student believes a version of the world set by the curriculum:
    Q0 naive defaults, Q1 textbook values, Q2 gamma-mixed redacted
    aggregates plus up to `hints` corrections (applied in a fixed
    impact order: memq, s, worst quirk, contention, 2nd/3rd quirk, pm,
    beta0), Q3 the truth (expert ceiling by construction).
    """
    p = EDU[q]
    if q == "Q3":
        ne = np.full(S, np.quantile(CAND["nelec"], 0.9))
        return _h_config(w, f, ne, kap, aggressive_ok=False,
                         rho_belief=np.full(S, 1.56) * att_esc)
    gq = p["gq"]
    s_bel = gq * w["s"] + (1 - gq) * p["s"]
    pm_bel = gq * w["pm"] + (1 - gq) * p["pm"]
    memq_bel = w["memq"] ** gq
    quirk_bel = w["quirk"] ** gq
    kc = p["kc"]
    b0_bel = (gq * w["beta0"] + (1 - gq) * p["b0"]) if p["b0"] is not None \
        else None
    # bounded hints correct one item each, in impact order
    h = hints
    if h >= 1:
        memq_bel = w["memq"]
    if h >= 2:
        s_bel = w["s"]
    worst = np.argsort(w["quirk"])  # ascending: worst (slowest) first
    if h >= 3:
        quirk_bel = quirk_bel.copy()
        quirk_bel[worst[0]] = w["quirk"][worst[0]]
    if h >= 4:
        kc = 1.0
    if h >= 5:
        quirk_bel = quirk_bel.copy()
        quirk_bel[worst[1]] = w["quirk"][worst[1]]
    if h >= 6:
        quirk_bel[worst[2]] = w["quirk"][worst[2]]
    if h >= 7:
        pm_bel = w["pm"]
    if h >= 8 and p["b0"] is not None:
        b0_bel = w["beta0"]

    ne_belief = np.full(S, np.quantile(CAND["nelec"], p["neq"]))
    rho_bel = np.full(S, p["rho"]) * (att_esc if p["esc"] else 1.0)
    wk_b = (w["A"][f] * (ne_belief / 38.0) ** 2.5
            * (NK[f] / 36.0) ** 1.0)
    eff = (C_NODES[None, :] ** (s_bel - 1.0) * quirk_bel[None, :]
           * (1 + 0.25 * C_AGG[None, :]))
    nkf = NK[f][:, None]
    ideal = nkf / (np.ceil(nkf / C_POOLS[None, :]) * C_POOLS[None, :])
    eff = eff * (1.0 - pm_bel * (1.0 - ideal))
    nh = wk_b[:, None] / eff * (1 + kc * kap[:, None] * C_IO[None, :])
    mem = (30.0 * (ne_belief[:, None] / 38.0) ** 2 * rho_bel[:, None]
           * (nkf / 36.0) ** 0.3 * memq_bel
           / (C_NODES[None, :] * C_POOLS[None, :] ** 0.4)) + 8.0
    over = mem > NODE_MEM_GB
    if b0_bel is None:      # Q0: failure risk not part of the mental model
        score = nh + 1e3 * over
    else:
        headroom = np.clip(NODE_MEM_GB / mem, 0.2, 20.0)
        z = (b0_bel + 1.2 * kc * (kap[:, None] - 0.3)
             + 0.8 * C_AGG[None, :] - 1.5 * np.log(headroom))
        pf = 1.0 / (1.0 + np.exp(-z))
        score = nh * (1 + 2 * pf) + 1e3 * over
    if not p["agg"]:
        score += 1e3 * C_AGG[None, :]
    return score.argmin(1)


DEFAULT_OPTS = dict(h_policy="expert", edu=None, hints=0,
                    cost_channel="default", r_controls_config=False,
                    kappa_shift=0.0)


def run_campaign_ext(w, topology, contract, opts=None):
    """Copy of simulator.run_campaign with the five gated extensions.
    With opts=None the trajectory is identical to the original."""
    o = dict(DEFAULT_OPTS)
    if opts:
        o.update(opts)
    lvl, gam = contract.level, contract.gamma
    cls = (np.arange(C) if lvl == "P0" else world_classes(w, lvl))
    contract = ContractView(contract, cls)
    mu = np.tile(GAP_PRIOR_MU, (S, 1))
    prec = np.full((S, C), 1.0 / 0.5 ** 2)
    fid_done = np.full((S, C), -1)
    dead = np.zeros((S, C), bool)
    qualified = np.zeros((S, C), bool)
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
    mi_score = np.zeros((S, C))
    mi_ring = np.zeros((MI_WINDOW, S, C))    # ablation 13.2-4 window
    n_msgs = np.zeros(S)
    cfg_obs_sum = np.zeros((S, J))
    cfg_obs_n = np.zeros((S, J))
    nb = contract.nclasses
    sur_sum = np.zeros((S, nb, FIDS, J))
    sur_n = np.zeros((S, nb, FIDS, J))
    chg_sum = np.zeros((S, FIDS))
    chg_n = np.zeros((S, FIDS))
    rel = (CAND["nelec"] / 38.0) ** 2.5
    nelec_hi = np.quantile(CAND["nelec"], 0.9)

    wk_all = np.stack([base_work(w, ff) for ff in range(FIDS)])
    eff_all = np.stack([eff_matrix(w, ff) for ff in range(FIDS)])
    mem_all = np.stack([mem_per_node(w, ff) for ff in range(FIDS)])
    hard_all = mem_all > NODE_MEM_GB
    headroom_all = np.clip(NODE_MEM_GB / mem_all, 0.2, 20.0)
    z0_all = (w["beta0"] + 0.8 * C_AGG[None, None, :]
              - 1.5 * np.log(headroom_all))
    best_cost_all = (wk_all[:, :, None] / eff_all).min(2)

    # rank/one-bit disclosure precomputation (ablation 13.2-2)
    if o["cost_channel"] in ("rank", "bit"):
        rank_pct = np.zeros((FIDS, C))
        for ff in range(FIDS):
            order = best_cost_all[ff].argsort().argsort()
            rank_pct[ff] = (order + 0.5) / C

    active = np.ones(S, bool)
    for t in range(T):
        if not active.any():
            break
        kap = w["kappa"][:, t]
        if o["kappa_shift"] and t >= T_SHIFT:
            kap = np.clip(kap + o["kappa_shift"], 0.0, 1.0)
        sd = 1.0 / np.sqrt(prec)
        pwin = (norm.cdf((GAP_HI - mu) / sd) - norm.cdf((GAP_LO - mu) / sd))
        value = pwin ** 2 * PHONON_PRIOR[None, :]
        value[dead | qualified] = 0.0
        nfid = np.clip(fid_done + 1, 1, 4)
        f4block = (nfid == 4) & (pwin < 0.5)
        value[f4block] = 0.0
        wk_next = wk_all[nfid, np.arange(C)[None, :]]
        if topology == "CTCE":
            cost_est = best_cost_all[nfid, np.arange(C)[None, :]]
        elif topology == "CTDE" and lvl != "P4":
            sidx = np.arange(S)[:, None]
            cidx = np.broadcast_to(cls[None, :], (S, C))
            sn = sur_n[sidx, cidx, nfid, :]
            ss = sur_sum[sidx, cidx, nfid, :]
            ntot = sn.sum(2)
            have = ntot > 0
            pred = ss.sum(2) / np.maximum(ntot, 1)
            fallback = wk_next / 0.8
            cost_est = np.where(have, np.exp(pred), fallback)
        elif topology == "CEDT" and o["cost_channel"] == "rank":
            # rank-only disclosure: exact ordering, magnitude from R's own
            # scale model (geometric mean of its rate-card prior)
            own = wk_next / 0.8
            gmean = np.exp(np.log(np.maximum(own, 1e-3)).mean(1,
                                                             keepdims=True))
            z = norm.ppf(rank_pct[nfid, np.arange(C)[None, :]])
            cost_est = gmean * np.exp(0.8 * z)
        elif topology == "CEDT" and o["cost_channel"] == "bit":
            # one-bit disclosure: cheap/expensive vs median
            own = wk_next / 0.8
            gmean = np.exp(np.log(np.maximum(own, 1e-3)).mean(1,
                                                             keepdims=True))
            bit = rank_pct[nfid, np.arange(C)[None, :]] > 0.5
            cost_est = gmean * np.where(bit, 1.6, 0.6)
        elif lvl in ("P1", "P2", "P3") and topology == "CEDT":
            cost_est = (best_cost_all[nfid, np.arange(C)[None, :]]
                        * np.exp(w["view_noise"] * contract.cost_sd))
        else:
            cn = np.take_along_axis(chg_n, nfid, axis=1)
            cs = np.take_along_axis(chg_sum, nfid, axis=1)
            base_chg = np.where(cn > 0, cs / np.maximum(cn, 1),
                                wk_next / 0.8)
            mean_rel = rel.mean()
            cost_est = base_chg * rel[None, :] / mean_rel
        acq = value / (np.maximum(cost_est, 0.02) + OVERHEAD_NH)
        acq *= np.where(nfid == 1, 1.5, 1.0)
        pick = acq.argmax(1)
        no_move = acq[np.arange(S), pick] <= 1e-12
        run_mask = active & ~no_move
        if not run_mask.any():
            break
        i = pick
        f = nfid[np.arange(S), i]
        wk_i = wk_all[f, i]
        eff_i = eff_all[f, i, :]
        z0_i = z0_all[f, i, :]
        pf_i = 1.0 / (1.0 + np.exp(-(z0_i + 1.2 * (kap[:, None] - 0.3))))
        hard_i = hard_all[f, i, :]
        true_nh = wk_i[:, None] / eff_i * (1 + kap[:, None] * C_IO[None, :])
        esc = 1.6 ** np.minimum(attempt_ct[np.arange(S), i, f], 3)
        if o["h_policy"] == "student":
            j = student_h_config(w, f, kap, o["edu"], o["hints"], esc)
        elif o["r_controls_config"]:
            # ablation 13.2-7: R picks the config from H's P2-precision
            # per-config menu; R knows its own rho exactly, not H's memq
            menu_noise = np.exp(0.3 * w["view_noise"][:, :J]
                                if w["view_noise"].shape[1] >= J else 1.0)
            eff_seen = eff_i * menu_noise[:, :J]
            nh_bel = wk_i[:, None] / eff_seen
            mem_bel = (30.0 * (CAND["nelec"][i][:, None] / 38.0) ** 2
                       * w["rho"][i][:, None] * (NK[f][:, None] / 36.0) ** 0.3
                       / (C_NODES[None, :] * C_POOLS[None, :] ** 0.4)) + 8.0
            score = nh_bel + 1e3 * (mem_bel > NODE_MEM_GB) \
                + 1e3 * C_AGG[None, :]
            j = score.argmin(1)
        elif topology == "CTCE":
            score = true_nh * (1 + 2 * pf_i) + 1e3 * hard_i
            j = score.argmin(1)
        elif topology == "CEDT":
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
            cls_top = np.array([CAND["nelec"][cls == b].max()
                                for b in range(contract.nclasses)])
            rho_top = np.array([w["rho"][cls == b].max()
                                for b in range(contract.nclasses)])
            wts = sur_n[np.arange(S), :, f, :].sum(2)
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
        else:
            ne_belief = np.full(S, nelec_hi)
            j = _h_config(w, f, ne_belief, kap, aggressive_ok=False,
                          rho_belief=np.full(S, 1.56) * esc)
        att_i = np.minimum(attempt_ct[np.arange(S), i, f], 3)
        noise = w["nh_noise"][np.arange(S), i, f, att_i]
        nh_real = true_nh[np.arange(S), j] * noise
        pfail = pf_i[np.arange(S), j]
        hard = hard_i[np.arange(S), j]
        u = w["fail_u"][np.arange(S), i, f, att_i]
        failed = (u < pfail) | hard
        spend = np.where(failed, 0.45 * nh_real, nh_real) + OVERHEAD_NH
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
            fs = f[ok]
            iss = i[ok]
            fid_done[ok, iss] = fs
            labels_f2[ok & (f >= 2)] += 1
            obs_mask = ok & (f >= 1) & (f <= 3)
            if obs_mask.any():
                io_, fo_ = i[obs_mask], f[obs_mask]
                soc_add = np.where(fo_ == 3, w["soc"][io_], 0.0)
                obs = (w["gap"][io_] + soc_add
                       + w["gap_noise"][obs_mask, io_, fo_]
                       * SIG_GAP_OBS[fo_])
                p_obs = 1.0 / SIG_GAP_OBS[fo_] ** 2
                new_prec = prec[obs_mask, io_] + p_obs
                mu[obs_mask, io_] = (mu[obs_mask, io_]
                                     * prec[obs_mask, io_]
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
        exhausted = m & failed & (attempt_ct[np.arange(S), i, f] >= 3)
        if exhausted.any():
            dead[exhausted, i[exhausted]] = True
        f3done = (fid_done == 3)
        sd2 = 1.0 / np.sqrt(prec)
        pw2 = (norm.cdf((GAP_HI - mu) / sd2) - norm.cdf((GAP_LO - mu) / sd2))
        dead |= f3done & (pw2 < 0.15)
        realized = lvl in ("P0", "P1")
        rate_card = wk_i / 0.8
        charge = np.where(realized, nh_real, rate_card)
        chg_sum[m, f[m]] += charge[m]
        chg_n[m, f[m]] += 1
        if topology == "CTDE" and gam > 0:
            sur_sum[m, cls[i[m]], f[m], j[m]] += np.log(
                np.maximum(nh_real[m], 1e-3))
            sur_n[m, cls[i[m]], f[m], j[m]] += 1
        if gam > 0 and topology in ("CEDT", "CTDE"):
            bsz = np.array([(cls == b).sum()
                            for b in range(contract.nclasses)])
            contrib = np.zeros((S, C))
            contrib[m] = gam * (cls[None, :] == cls[i[m]][:, None]) \
                / bsz[cls[i[m]]][:, None]
            mi_score += contrib
            mi_ring[t % MI_WINDOW] = contrib
            n_msgs[m] += 1
        elif gam > 0:
            mi_ring[t % MI_WINDOW] = 0.0
        cfg_obs_sum[m, j[m]] += np.log(np.maximum(nh_real, 1e-3))[m]
        cfg_obs_n[m, j[m]] += 1
        active &= (nh_used < BUDGET_NH) & (attempts < MAX_ATTEMPTS)
        active &= ((~dead) & (~qualified)).any(1)

    st = dict(mu=mu, prec=prec, fid_done=fid_done, qualified=qualified,
              nh_used=nh_used, attempts=attempts, fails=fails,
              memfails=memfails, labels_f2=labels_f2, att_f2=att_f2,
              first_qual_nh=first_qual_nh, qe_calls=qe_calls,
              queried=queried, mi_score=mi_score, n_msgs=n_msgs,
              cfg_obs_sum=cfg_obs_sum, cfg_obs_n=cfg_obs_n)
    out = sim._score_campaign(w, topology, contract, st)
    _score_extensions(w, topology, contract, st, mi_ring, o, out)
    return out


def _score_extensions(w, topology, contract, st, mi_ring, o, out):
    """Extra scoring: windowed membership attacker (13.2-4), rank/bit
    leakage adjustment (13.2-2), and curriculum attacks (9.3/10.1)."""
    atk = w["atk"]
    gam = contract.gamma
    # -- windowed R membership attacker (transcript history removed) --------
    if gam > 0 and topology in ("CEDT", "CTDE"):
        recent = mi_ring.sum(0)                       # (S, C)
        mi_r = np.array([_auc(recent[s][st["queried"][s]],
                              recent[s][~st["queried"][s]])
                         for s in range(S)])
        out["r_mi_auc_recent"] = np.clip(0.5 + (mi_r - 0.5) * atk, 0, 1)
    else:
        out["r_mi_auc_recent"] = np.full(S, 0.5)
    # -- rank/one-bit H->R channel: overwrite the config-rank extraction ----
    if o["cost_channel"] in ("rank", "bit"):
        sd0 = {"rank": 0.35, "bit": 1.20}[o["cost_channel"]]
        true_eff = np.log((C_NODES ** (w["s"] - 1.0)) * w["quirk"]
                          * (1 + 0.25 * C_AGG))
        var_sig = max(np.var(true_eff), 1e-8)
        noise_var = (sd0 ** 2 / np.maximum(st["cfg_obs_n"], 0.25)).mean(1)
        corr = np.sqrt(var_sig / (var_sig + noise_var))
        out["h_rank_corr"] = np.clip(corr * atk, 0, 1)
    # -- curriculum attacks (adversarial student, ablation 13.2-11) --------
    if o["edu"] is not None:
        q, h = o["edu"], o["hints"]
        true_eff = np.log((C_NODES ** (w["s"] - 1.0)) * w["quirk"]
                          * (1 + 0.25 * C_AGG))
        var_sig = max(np.var(true_eff), 1e-8)
        if q in ("Q0", "Q1"):
            cur_rank, cur_hw = 0.0, 0.0
        elif q == "Q2":
            sd_q = 0.35 / np.sqrt(1 + 0.5 * h)
            cur_rank = float(np.clip(
                np.sqrt(var_sig / (var_sig + sd_q ** 2)) * atk, 0, 1))
            sd_hw = 0.30 / np.sqrt(1 + 0.25 * h)
            acc3 = 1 / 3 + (4 / 3) * (norm.cdf(0.12 / sd_hw / 2) - 0.5)
            cur_hw = float(np.clip((acc3 - 1 / 3) * atk, 0, 1))
        else:  # Q3 oracle: materials NOT released; also report if-released
            cur_rank, cur_hw = 0.0, 0.0
            out["cur_rank_corr_if_released"] = np.full(
                S, float(np.clip(0.95 * atk, 0, 1)))
            out["cur_hw_adv_if_released"] = np.full(
                S, float(np.clip(2 / 3 * atk, 0, 1)))
        out["cur_rank_corr"] = np.full(S, cur_rank)
        out["cur_hw_adv"] = np.full(S, cur_hw)
        out["educator_effort"] = np.full(
            S, EDU[q]["effort"] + HINT_EFFORT * h)


# ---------------------------------------------------------------------------
# condition grid

def _conds():
    P4, P2, P3 = Contract("P4"), Contract("P2"), Contract("P3", 4.0)
    conds = [
        # pairing baseline (expert H, no sharing) — also A8 pre-shift ref
        ("DTDE_P4", "DTDE", P4, {}),
        # education axis: student operates H's config choice, DTDE regime
        ("EDU_Q0", "DTDE", P4, dict(h_policy="student", edu="Q0")),
        ("EDU_Q1", "DTDE", P4, dict(h_policy="student", edu="Q1")),
        ("EDU_Q2_h0", "DTDE", P4, dict(h_policy="student", edu="Q2",
                                       hints=0)),
        ("EDU_Q2_h2", "DTDE", P4, dict(h_policy="student", edu="Q2",
                                       hints=2)),
        ("EDU_Q2_h8", "DTDE", P4, dict(h_policy="student", edu="Q2",
                                       hints=8)),
        ("EDU_Q3", "DTDE", P4, dict(h_policy="student", edu="Q3")),
        # ablation 13.2-2: score granularity of the H->R cost channel
        ("CEDT_RANK", "CEDT", P2, dict(cost_channel="rank")),
        ("CEDT_BIT", "CEDT", P2, dict(cost_channel="bit")),
        # ablation 13.2-4 rides along on re-runs of the leading contracts
        ("CEDT_P2x", "CEDT", P2, {}),
        ("CEDT_P3x", "CEDT", P3, {}),
        ("CEDT_P4x", "CEDT", P4, {}),
        ("CTDE_P3x", "CTDE", P3, {}),
        # ablation 13.2-7: R controls the numerical/config knobs
        ("CEDT_P2_RCTL", "CEDT", P2, dict(r_controls_config=True)),
        # ablation 13.2-8: unanticipated contention shift at t=40
        ("DTDE_SHIFT", "DTDE", P4, dict(kappa_shift=0.35)),
        ("CTDE_P2_SHIFT", "CTDE", P2, dict(kappa_shift=0.35)),
        ("CEDT_P4_SHIFT", "CEDT", P4, dict(kappa_shift=0.35)),
        ("CEDT_P3_SHIFT", "CEDT", P3, dict(kappa_shift=0.35)),
    ]
    return conds


EXTRA_KEYS = ("r_mi_auc_recent", "cur_rank_corr", "cur_hw_adv",
              "educator_effort", "cur_rank_corr_if_released",
              "cur_hw_adv_if_released")


def run_world_ext(args):
    card, wid = args
    w = sim.sample_world(card, wid)
    res = {}
    for name, topo, contract, opts in _conds():
        res[name] = run_campaign_ext(w, topo, contract, opts)
    # win-win grading: shift conditions vs the shifted baseline, everything
    # else vs the unshifted DTDE run
    plain = {k: v for k, v in res.items() if not k.endswith("_SHIFT")}
    shift = {k: v for k, v in res.items() if k.endswith("_SHIFT")}
    summary = eval_world(plain, dtde_key="DTDE_P4")
    summary.update(eval_world(shift, dtde_key="DTDE_SHIFT"))
    for name, r in res.items():
        for k in EXTRA_KEYS:
            if k in r:
                summary[name][k] = float(np.mean(r[k]))
        summary[name]["labels_per_nh_ratio"] = float(
            np.mean(r["labels_per_nh"]) /
            max(np.mean(res["DTDE_P4"]["labels_per_nh"]), 1e-9))
        summary[name]["found_ratio"] = float(
            np.mean(r["found"]) /
            max(np.mean(res["DTDE_P4"]["found"]), 1e-9))
    info = dict(card=card, world=wid, s=w["s"], pm=w["pm"],
                burst=w["burst"], beta0=w["beta0"], build=int(w["build"]),
                n_true_qual=int(w["qual"].sum()))
    return info, summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worlds", type=int, default=1000)
    ap.add_argument("--procs", type=int, default=os.cpu_count())
    ap.add_argument("--out", default="results/ext_raw.json")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    if args.smoke:
        args.worlds, args.procs = 4, 1
    cards = ["base", "strong_coupling", "adversarial"]
    tasks = [(cards[wid * 3 // args.worlds] if args.worlds >= 3 else "base",
              wid) for wid in range(args.worlds)]
    if args.procs > 1:
        import multiprocessing as mp
        with mp.Pool(args.procs) as pool:
            out = pool.map(run_world_ext, tasks, chunksize=4)
    else:
        out = [run_world_ext(t) for t in tasks]
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

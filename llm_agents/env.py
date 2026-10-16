#!/usr/bin/env python3
"""Stepwise (single-seed) campaign environment for LLM decision-maker agents.

Replays exactly the same prior worlds, noise fields, and twin equations as
prior_predictive/simulator.py, but exposes one decision at a time so that an
LLM agent (with tools) can play the R and H roles instead of the scripted
policies. All node-hours are SIMULATED UNITS.

The scripted policies from the vectorized simulator are also reimplemented
here (scripted_pick_candidate / scripted_pick_config) so that the scripted
control arm runs through the identical env, giving exact paired comparisons
at the same budget, round cap, and noise draws.
"""
import sys
from pathlib import Path

import numpy as np
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).parent.parent / "prior_predictive"))
import simulator as sim  # noqa: E402

CAND = sim.CAND
C = sim.C
J = sim.J
FIDS = sim.FIDS
NK = sim.NK
GAP_LO, GAP_HI = sim.GAP_LO, sim.GAP_HI
NODE_MEM_GB = sim.NODE_MEM_GB
OVERHEAD_NH = sim.OVERHEAD_NH
C_NODES, C_POOLS, C_AGG, C_IO = sim.C_NODES, sim.C_POOLS, sim.C_AGG, sim.C_IO
CONFIGS = sim.CONFIGS


class CampaignEnv:
    """One campaign = one (world, seed, topology, contract) at reduced budget."""

    def __init__(self, w, seed, topology, level, eps=None,
                 budget=250.0, max_rounds=40, max_attempts=50):
        assert 0 <= seed < sim.S
        self.w = w
        self.s = seed
        self.topology = topology
        self.level = level
        contract = sim.Contract(level if level != "P0" else "P1", eps)
        if level == "P0":
            contract.level = "P0"
            contract.gamma = 1.0
            contract.cost_sd = 0.0
        self.gamma = contract.gamma
        self.cost_sd = contract.cost_sd
        self.cls = (np.arange(C) if level == "P0"
                    else sim.world_classes(w, level))
        self.nclasses = int(self.cls.max()) + 1
        self.budget = budget
        self.T = max_rounds
        self.max_attempts = max_attempts
        self.aggressive_ok = (topology in ("CTCE", "CEDT"))

        # statics (identical formulas to run_campaign)
        self.wk_all = np.stack([sim.base_work(w, f) for f in range(FIDS)])
        self.eff_all = np.stack([sim.eff_matrix(w, f) for f in range(FIDS)])
        self.mem_all = np.stack([sim.mem_per_node(w, f) for f in range(FIDS)])
        self.hard_all = self.mem_all > NODE_MEM_GB
        headroom = np.clip(NODE_MEM_GB / self.mem_all, 0.2, 20.0)
        self.z0_all = (w["beta0"] + 0.8 * C_AGG[None, None, :]
                       - 1.5 * np.log(headroom))
        self.best_cost_all = (self.wk_all[:, :, None] / self.eff_all).min(2)

        # R belief state
        self.mu = sim.GAP_PRIOR_MU.copy()
        self.prec = np.full(C, 1.0 / 0.5 ** 2)
        self.fid_done = np.full(C, -1)
        self.dead = np.zeros(C, bool)
        self.qualified = np.zeros(C, bool)
        # ledgers
        self.t = 0
        self.nh_used = 0.0
        self.attempts = 0
        self.fails = 0
        self.memfails = 0
        self.labels_f2 = 0
        self.att_f2 = 0
        self.first_qual_nh = np.nan
        self.attempt_ct = np.zeros((C, FIDS), int)
        self.queried = np.zeros(C, bool)
        self.mi_score = np.zeros(C)
        self.n_msgs = 0
        self.cfg_obs_sum = np.zeros(J)
        self.cfg_obs_n = np.zeros(J)
        self.sur_sum = np.zeros((self.nclasses, FIDS, J))
        self.sur_n = np.zeros((self.nclasses, FIDS, J))
        self.chg_sum = np.zeros(FIDS)
        self.chg_n = np.zeros(FIDS)
        self.rel = (CAND["nelec"] / 38.0) ** 2.5
        self.nelec_hi = np.quantile(CAND["nelec"], 0.9)
        self.cls_top_ne = np.array([CAND["nelec"][self.cls == b].max()
                                    for b in range(self.nclasses)])
        self.cls_top_rho = np.array([w["rho"][self.cls == b].max()
                                     for b in range(self.nclasses)])
        self.stopped = False
        self.events = []      # recent-history feed for the agents

    # ------------------------------------------------------------------ R side
    def next_fid(self):
        return np.clip(self.fid_done + 1, 1, 4)

    def window_prob(self):
        sd = 1.0 / np.sqrt(self.prec)
        return (norm.cdf((GAP_HI - self.mu) / sd)
                - norm.cdf((GAP_LO - self.mu) / sd))

    def admissible(self):
        """Candidates R may still run (value>0 in the scripted policy)."""
        pwin = self.window_prob()
        nfid = self.next_fid()
        ok = ~(self.dead | self.qualified)
        ok &= ~((nfid == 4) & (pwin < 0.5))   # F4 gate
        return ok

    def cost_est(self):
        """R's contract-filtered per-candidate cost estimate at next fid
        (same information channels as the vectorized simulator)."""
        w, s = self.w, self.s
        nfid = self.next_fid()
        wk_next = self.wk_all[nfid, np.arange(C)]
        if self.topology == "CTCE":
            return self.best_cost_all[nfid, np.arange(C)]
        if self.topology == "CTDE" and self.level != "P4":
            sn = self.sur_n[self.cls, nfid, :]
            ss = self.sur_sum[self.cls, nfid, :]
            ntot = sn.sum(1)
            pred = ss.sum(1) / np.maximum(ntot, 1)
            return np.where(ntot > 0, np.exp(pred), wk_next / 0.8)
        if self.level in ("P1", "P2", "P3") and self.topology == "CEDT":
            return (self.best_cost_all[nfid, np.arange(C)]
                    * np.exp(w["view_noise"][s] * self.cost_sd))
        # DTDE / P4: regress observed charges on the size shape
        cn = self.chg_n[nfid]
        cs = self.chg_sum[nfid]
        base_chg = np.where(cn > 0, cs / np.maximum(cn, 1), wk_next / 0.8)
        return base_chg * self.rel / self.rel.mean()

    def r_state(self):
        pwin = self.window_prob()
        sd = 1.0 / np.sqrt(self.prec)
        return dict(t=self.t, nh_used=self.nh_used, budget=self.budget,
                    attempts=self.attempts, fails=self.fails,
                    mu=self.mu, sd=sd, pwin=pwin,
                    phonon_prior=sim.PHONON_PRIOR,
                    next_fid=self.next_fid(), cost_est=self.cost_est(),
                    admissible=self.admissible(), dead=self.dead,
                    qualified=self.qualified,
                    attempt_ct=self.attempt_ct, events=self.events[-6:])

    # ------------------------------------------------------------------ H side
    def h_beliefs(self, i):
        """H's (ne, rho) belief for candidate i's next job, per topology and
        contract — same construction as the vectorized simulator, including
        the retry escalation of the memory belief."""
        w = self.w
        f = int(self.next_fid()[i])
        esc = 1.6 ** min(self.attempt_ct[i, f], 3)
        gam = self.gamma
        if self.topology == "CTCE":
            return f, CAND["nelec"][i], w["rho"][i], esc
        if self.topology == "CEDT":
            ne = gam * self.cls_top_ne[self.cls[i]] + (1 - gam) * self.nelec_hi
            rho = gam * self.cls_top_rho[self.cls[i]] + (1 - gam) * 1.56
            return f, ne, rho * esc, esc
        if self.topology == "CTDE":
            wts = self.sur_n[:, f, :].sum(1)
            enough = wts.sum() >= 5
            ne_s = (np.where(wts > 0, self.cls_top_ne, 0.0).max()
                    if enough else self.nelec_hi)
            rho_s = (np.where(wts > 0, self.cls_top_rho, 0.0).max()
                     if enough else 1.56)
            ne = gam * ne_s + (1 - gam) * self.nelec_hi
            rho = gam * rho_s + (1 - gam) * 1.56
            return f, ne, rho * esc, esc
        return f, self.nelec_hi, 1.56 * esc, esc   # DTDE

    def h_config_table(self, i):
        """H's own per-config predictions given its beliefs (this is H's
        private model — legitimately available to the H agent as a tool)."""
        w = self.w
        f, ne, rho, esc = self.h_beliefs(i)
        kap = w["kappa"][self.s, self.t]
        wk_b = (w["A"][f] * (ne / 38.0) ** w["p_e"]
                * (NK[f] / 36.0) ** w["p_k"])
        eff = (C_NODES ** (w["s"] - 1.0) * w["quirk"] * w["bspeed"]
               * (1 + 0.25 * C_AGG))
        eff = eff * sim.pool_eff(w, NK[f], C_POOLS)
        nh = wk_b / eff * (1 + kap * C_IO)
        mem = (30.0 * (ne / 38.0) ** 2 * rho * (NK[f] / 36.0) ** 0.3
               * w["memq"] / (C_NODES * C_POOLS ** 0.4)) + 8.0
        headroom = np.clip(NODE_MEM_GB / mem, 0.2, 20.0)
        z = (w["beta0"] + 1.2 * (kap - 0.3) + 0.8 * C_AGG
             - 1.5 * np.log(headroom))
        pf = 1.0 / (1.0 + np.exp(-z))
        allowed = np.ones(J, bool)
        if not self.aggressive_ok:
            allowed &= C_AGG == 0
        return dict(fid=f, kappa=float(kap), ne_belief=float(ne),
                    rho_belief=float(rho), esc=float(esc),
                    nh_est=nh, mem_est=mem, pfail=pf, allowed=allowed)

    # ------------------------------------------------------------------ step
    def step(self, i, j):
        """Execute candidate i at its next fidelity on config j."""
        w, s, t = self.w, self.s, self.t
        i, j = int(i), int(j)
        f = int(self.next_fid()[i])
        kap = w["kappa"][s, t]
        eff = self.eff_all[f, i, j]
        true_nh = (self.wk_all[f, i] / eff) * (1 + kap * C_IO[j])
        att = min(self.attempt_ct[i, f], 3)
        nh_real = true_nh * w["nh_noise"][s, i, f, att]
        pf = 1.0 / (1.0 + np.exp(-(self.z0_all[f, i, j]
                                   + 1.2 * (kap - 0.3))))
        hard = bool(self.hard_all[f, i, j])
        failed = bool(w["fail_u"][s, i, f, att] < pf) or hard
        spend = (0.45 * nh_real if failed else nh_real) + OVERHEAD_NH
        self.nh_used += spend
        self.attempts += 1
        self.attempt_ct[i, f] += 1
        self.queried[i] = True
        self.fails += failed
        self.memfails += (failed and hard)
        if f >= 2:
            self.att_f2 += 1
        ev = dict(t=t, cand=i, name=CAND["names"][i], fid=f, config=j,
                  nh=round(float(nh_real), 2), failed=failed, memfail=hard,
                  kappa=round(float(kap), 2))
        if not failed:
            self.fid_done[i] = f
            if f >= 2:
                self.labels_f2 += 1
            if 1 <= f <= 3:
                soc_add = w["soc"][i] if f == 3 else 0.0
                obs = (w["gap"][i] + soc_add
                       + w["gap_noise"][s, i, f] * sim.SIG_GAP_OBS[f])
                p_obs = 1.0 / sim.SIG_GAP_OBS[f] ** 2
                new_prec = self.prec[i] + p_obs
                self.mu[i] = (self.mu[i] * self.prec[i] + obs * p_obs) / new_prec
                self.prec[i] = new_prec
                ev["gap_obs"] = round(float(obs), 3)
            if f == 1 and not w["valid"][i]:
                self.dead[i] = True
                ev["invalid_structure"] = True
            if f == 4:
                stable = bool(w["stable"][i])
                gap_f = w["gap"][i] + w["soc"][i]
                win = GAP_LO <= gap_f <= GAP_HI
                if stable and win and w["valid"][i]:
                    self.qualified[i] = True
                    ev["qualified"] = True
                    if np.isnan(self.first_qual_nh):
                        self.first_qual_nh = self.nh_used
                else:
                    self.dead[i] = True
                    ev["failed_f4"] = True
        else:
            if self.attempt_ct[i, f] >= 3:
                self.dead[i] = True
                ev["abandoned"] = True
        # post-F3 dead-end pruning (same rule as vectorized)
        sd2 = 1.0 / np.sqrt(self.prec)
        pw2 = (norm.cdf((GAP_HI - self.mu) / sd2)
               - norm.cdf((GAP_LO - self.mu) / sd2))
        self.dead |= (self.fid_done == 3) & (pw2 < 0.15)
        # transcript / learning updates
        realized = self.level in ("P0", "P1")
        rate_card = self.wk_all[f, i] / 0.8
        charge = nh_real if realized else rate_card
        self.chg_sum[f] += charge
        self.chg_n[f] += 1
        if self.topology == "CTDE" and self.gamma > 0:
            self.sur_sum[self.cls[i], f, j] += np.log(max(nh_real, 1e-3))
            self.sur_n[self.cls[i], f, j] += 1
        if self.gamma > 0 and self.topology in ("CEDT", "CTDE"):
            bsz = (self.cls == self.cls[i]).sum()
            self.mi_score += self.gamma * (self.cls == self.cls[i]) / bsz
            self.n_msgs += 1
        self.cfg_obs_sum[j] += np.log(max(nh_real, 1e-3))
        self.cfg_obs_n[j] += 1
        self.t += 1
        self.events.append(ev)
        return ev

    @property
    def done(self):
        return (self.stopped or self.t >= self.T
                or self.nh_used >= self.budget
                or self.attempts >= self.max_attempts
                or not (~(self.dead | self.qualified)).any()
                or not self.admissible().any())

    # ------------------------------------------------------------------ score
    def score(self):
        w = self.w
        nh = max(self.nh_used, 1e-6)
        out = dict(
            qual_count=float(self.qualified.sum()),
            found=float(not np.isnan(self.first_qual_nh)),
            nh_first=float(self.budget if np.isnan(self.first_qual_nh)
                           else self.first_qual_nh),
            labels_per_nh=self.labels_f2 / nh,
            fail_rate=self.fails / max(self.attempts, 1),
            memfail_rate=self.memfails / max(self.attempts, 1),
            validity=self.labels_f2 / max(self.att_f2, 1),
            nh_used=float(self.nh_used), attempts=float(self.attempts),
            rounds=float(self.t),
            n_true_qual=float(w["qual"].sum()))
        # R-side leakage (same attacker construction, single seed)
        atk = w["atk"]
        if self.gamma <= 0 or self.topology == "DTDE":
            out.update(r_mi_auc=0.5, r_id_acc=1.0 / C)
        else:
            pos = self.mi_score[self.queried]
            neg = self.mi_score[~self.queried]
            mi = sim._auc(pos, neg)
            idacc_c = np.array([1.0 / max((self.cls == self.cls[i]).sum(), 1)
                                for i in range(C)])
            qid = np.where(self.queried, idacc_c * self.gamma, 0)
            nq = max(self.queried.sum(), 1)
            out.update(
                r_mi_auc=float(np.clip(0.5 + (mi - 0.5) * atk, 0, 1)),
                r_id_acc=float(np.clip(qid.sum() / nq * atk, 0, 1)))
        return out


# --------------------------------------------------------------------------
# scripted control policies (exact port of the vectorized greedy policies)

def scripted_pick_candidate(env):
    pwin = env.window_prob()
    value = pwin ** 2 * sim.PHONON_PRIOR
    value[~env.admissible()] = 0.0
    if value.max() <= 1e-12:
        return None
    nfid = env.next_fid()
    acq = value / (np.maximum(env.cost_est(), 0.02) + OVERHEAD_NH)
    acq *= np.where(nfid == 1, 1.5, 1.0)
    acq[~env.admissible()] = 0.0
    return int(acq.argmax())


def scripted_pick_config(env, i):
    tab = env.h_config_table(i)
    score = tab["nh_est"] * (1 + 2 * tab["pfail"])
    score = score + 1e3 * (tab["mem_est"] > NODE_MEM_GB)
    score = score + np.where(tab["allowed"], 0.0, 1e3)
    return int(score.argmin())


def run_scripted(env):
    while not env.done:
        i = scripted_pick_candidate(env)
        if i is None:
            break
        env.step(i, scripted_pick_config(env, i))
    return env.score()

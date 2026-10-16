#!/usr/bin/env python3
"""Toolbox for the LLM party agents.

Each tool is a real algorithm (Thompson sampling, UCB, expected-value
knapsack, constrained optimization, Monte-Carlo risk estimation) operating on
the party's OWN contract-filtered information in the env. The LLM chooses
which tool to call, with which parameters, and whether to follow its output —
nothing here decides for the agent.
"""
import numpy as np
from scipy.stats import norm

import env as envmod
from env import C, J, GAP_LO, GAP_HI, NODE_MEM_GB, OVERHEAD_NH, CONFIGS
import simulator as sim


def _cand_row(env, i, score=None):
    st = dict(cand=int(i), name=envmod.CAND["names"][i],
              next_fid=int(env.next_fid()[i]),
              mu=round(float(env.mu[i]), 3),
              sd=round(float(1 / np.sqrt(env.prec[i])), 3),
              pwin=round(float(env.window_prob()[i]), 3),
              cost_est=round(float(env.cost_est()[i]), 2))
    if score is not None:
        st["score"] = round(float(score), 4)
    return st


# ----------------------------------------------------------------- R tools

def rank_candidates(env, strategy="cost_aware_greedy", top_k=5,
                    explore_weight=1.0, n_samples=200, seed=0):
    """Rank admissible candidates by a chosen acquisition strategy.

    strategies:
      cost_aware_greedy : pwin^2 * phonon_prior / (cost + overhead)
      ucb               : window prob of (mu, sd*explore_weight)-optimistic
                          gap, cost-normalized
      thompson          : Monte-Carlo posterior sampling of gaps; score =
                          fraction of samples inside [1.0, 2.0] eV weighted
                          by phonon prior, cost-normalized
      pure_value        : pwin^2 * phonon_prior (ignore cost)
    """
    ok = env.admissible()
    if not ok.any():
        return {"ranking": [], "note": "no admissible candidates"}
    pwin = env.window_prob()
    sd = 1.0 / np.sqrt(env.prec)
    cost = np.maximum(env.cost_est(), 0.02) + OVERHEAD_NH
    prior = sim.PHONON_PRIOR
    if strategy == "ucb":
        lo = env.mu - explore_weight * sd
        hi = env.mu + explore_weight * sd
        # optimistic: candidate treated at its best plausible gap
        opt = np.clip(np.where(env.mu < 1.5, hi, lo), None, None)
        inwin = (opt >= GAP_LO) & (opt <= GAP_HI)
        score = np.where(inwin, 1.0, pwin) * prior / cost
    elif strategy == "thompson":
        rng = np.random.default_rng(1234 + seed + env.t)
        draws = rng.normal(env.mu, sd, size=(int(n_samples), C))
        frac = ((draws >= GAP_LO) & (draws <= GAP_HI)).mean(0)
        score = frac * prior / cost
    elif strategy == "pure_value":
        score = pwin ** 2 * prior
    else:  # cost_aware_greedy
        score = pwin ** 2 * prior / cost
    score = np.where(ok, score, -1.0)
    order = np.argsort(-score)[:int(top_k)]
    return {"strategy": strategy,
            "ranking": [_cand_row(env, i, score[i]) for i in order
                        if score[i] > 0]}


def portfolio_plan(env, horizon_nh=None, value_power=2.0):
    """Greedy knapsack: pick the sequence of next-fidelity jobs maximizing
    total (pwin^value_power * phonon_prior) within the remaining budget
    (or a shorter horizon). Returns the planned order."""
    left = env.budget - env.nh_used
    if horizon_nh:
        left = min(left, float(horizon_nh))
    pwin = env.window_prob()
    cost = np.maximum(env.cost_est(), 0.02) + OVERHEAD_NH
    val = pwin ** float(value_power) * sim.PHONON_PRIOR
    val[~env.admissible()] = 0.0
    density = val / cost
    order = np.argsort(-density)
    plan, spent = [], 0.0
    for i in order:
        if val[i] <= 1e-12 or spent + cost[i] > left:
            continue
        spent += cost[i]
        plan.append(_cand_row(env, i, density[i]))
        if len(plan) >= 10:
            break
    return {"horizon_nh": round(left, 1), "planned_spend": round(spent, 1),
            "plan": plan}


def posterior_summary(env, top_k=8):
    """Candidates sorted by window probability, with belief detail."""
    pwin = env.window_prob()
    order = np.argsort(-np.where(env.admissible(), pwin, -1))[:int(top_k)]
    return {"by_window_prob": [_cand_row(env, i) for i in order
                               if env.admissible()[i]]}


# ----------------------------------------------------------------- H tools

def config_table(env, cand):
    tab = env.h_config_table(int(cand))
    rows = []
    for j in range(J):
        rows.append(dict(config=j, nodes=CONFIGS[j][0], pools=CONFIGS[j][1],
                         aggressive=CONFIGS[j][2],
                         allowed=bool(tab["allowed"][j]),
                         nh_est=round(float(tab["nh_est"][j]), 2),
                         mem_est_gb=round(float(tab["mem_est"][j]), 1),
                         pfail=round(float(tab["pfail"][j]), 3)))
    return {"fid": tab["fid"], "kappa": tab["kappa"],
            "ne_belief": round(tab["ne_belief"], 1),
            "retry_escalation": round(tab["esc"], 2),
            "node_mem_gb": NODE_MEM_GB, "configs": rows}


def config_optimizer(env, cand, risk_weight=2.0, mem_margin=1.0):
    """Constrained optimizer: argmin nh_est*(1+risk_weight*pfail) subject to
    mem_est*mem_margin <= node memory (mem_margin>1 = extra safety)."""
    tab = env.h_config_table(int(cand))
    feas = (tab["mem_est"] * float(mem_margin) <= NODE_MEM_GB) & tab["allowed"]
    score = tab["nh_est"] * (1 + float(risk_weight) * tab["pfail"])
    if not feas.any():   # relax margin, keep hard memory bound
        feas = (tab["mem_est"] <= NODE_MEM_GB) & tab["allowed"]
        if not feas.any():
            feas = tab["allowed"]
    score = np.where(feas, score, np.inf)
    j = int(score.argmin())
    return {"best_config": j, "nodes": CONFIGS[j][0], "pools": CONFIGS[j][1],
            "aggressive": CONFIGS[j][2],
            "expected_nh": round(float(tab["nh_est"][j]), 2),
            "mem_est_gb": round(float(tab["mem_est"][j]), 1),
            "pfail": round(float(tab["pfail"][j]), 3),
            "n_feasible": int(feas.sum())}


def config_montecarlo(env, cand, n_draws=300, quantile=0.9, seed=0):
    """Monte-Carlo risk estimate per config: simulate runtime noise and
    failure/retry (retries at 0.45x sunk cost, same as billing), report
    expected total nh and the chosen quantile."""
    tab = env.h_config_table(int(cand))
    rng = np.random.default_rng(4321 + seed + env.t)
    n = int(n_draws)
    out = []
    for j in range(J):
        if not tab["allowed"][j]:
            continue
        mem_violation = bool(tab["mem_est"][j] > NODE_MEM_GB)
        # a predicted memory overrun is a hard failure, not a coin flip
        pfail = 1.0 if mem_violation else tab["pfail"][j]
        nh = tab["nh_est"][j] * np.exp(rng.normal(0, 0.15, n))
        fail = rng.random(n) < pfail
        # one modeled retry on failure (a retry after a hard overrun fails too)
        nh2 = tab["nh_est"][j] * np.exp(rng.normal(0, 0.15, n))
        retry = np.where(mem_violation, 0.45 * nh2, nh2)
        total = np.where(fail, 0.45 * nh + retry, nh) + OVERHEAD_NH
        out.append(dict(config=j,
                        mean_nh=round(float(total.mean()), 2),
                        q=round(float(np.quantile(total, float(quantile))), 2),
                        pfail=round(float(pfail), 3),
                        mem_est_gb=round(float(tab["mem_est"][j]), 1),
                        mem_violation=mem_violation))
    out.sort(key=lambda r: (r["mem_violation"], r["mean_nh"]))
    return {"quantile": float(quantile), "node_mem_gb": NODE_MEM_GB,
            "configs": out}


R_TOOLS = {"rank_candidates": rank_candidates,
           "portfolio_plan": portfolio_plan,
           "posterior_summary": posterior_summary}
H_TOOLS = {"config_table": config_table,
           "config_optimizer": config_optimizer,
           "config_montecarlo": config_montecarlo}


def tool_top_candidate(env, tool, args):
    """Top suggestion of an R tool (used for delegation / auto-accept)."""
    fn = R_TOOLS[tool]
    res = fn(env, **args)
    lst = res.get("ranking") or res.get("plan") or res.get("by_window_prob")
    if lst:
        return int(lst[0]["cand"]), res
    return None, res


def tool_top_config(env, cand, tool, args):
    """Top suggestion of an H tool for a given candidate."""
    if tool == "config_optimizer":
        res = config_optimizer(env, cand, **args)
        return int(res["best_config"]), res
    if tool == "config_montecarlo":
        res = config_montecarlo(env, cand, **args)
        if res["configs"]:
            return int(res["configs"][0]["config"]), res
        return None, res
    res = config_table(env, cand)
    rows = [r for r in res["configs"]
            if r["allowed"] and r["mem_est_gb"] <= NODE_MEM_GB]
    if rows:
        rows.sort(key=lambda r: r["nh_est"] * (1 + 2 * r["pfail"]))
        return int(rows[0]["config"]), res
    return None, res

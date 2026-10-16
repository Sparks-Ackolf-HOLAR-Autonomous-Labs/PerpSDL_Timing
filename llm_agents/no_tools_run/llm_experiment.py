#!/usr/bin/env python3
"""LLM agents as decision makers in the QE privacy-tax experiment.

Design (2026-09-02): the parties are played by
LLM agents, not scripted policies. This module re-implements the
campaign engine of ../prior_predictive/simulator.py as a scalar (single-seed)
loop with pluggable decision seats:

  * R seat  (research party): which candidate to advance next, or stop.
  * H seat  (HPC party / joint seat under CTCE): which execution config.

Both seats can be "scripted" (bit-exact port of the deterministic policies in
simulator.py) or "llm" (an OpenAI-compatible chat model served by vLLM on the
DGX). The harness — not the model — enforces the information set: each prompt
contains exactly the observations the contract level permits, the same ones the
scripted policy consumes. Illegal or unparseable model choices fall back to the
scripted choice and are counted.

All node-hours are SIMULATED UNITS. Nothing here is a CHPC measurement.

Models (served locally on the DGX, two parties = two different models):
  R: Qwen/Qwen3-4B-Instruct-2507                      (port 8010)
  H: nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4 (port 8011)
"""
import argparse
import asyncio
import gzip
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
from scipy.stats import norm

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "prior_predictive"))
import simulator as sim  # noqa: E402
from simulator import (CAND, C, CONFIGS, C_NODES, C_POOLS, C_AGG, C_IO,  # noqa
                       NK, FIDS, GAP_LO, GAP_HI, OVERHEAD_NH, BUDGET_NH,
                       NODE_MEM_GB, PHONON_PRIOR, GAP_PRIOR_MU, SIG_GAP_OBS,
                       Contract, ContractView, world_classes, sample_world,
                       base_work, eff_matrix, mem_per_node, pool_eff)

NSEEDS = 2
sim.S = NSEEDS  # noise-field and scoring shapes follow the reduced seed count

CONDITIONS = [
    ("CTCE_P0", "CTCE", "P0", None),
    ("DTDE_P4", "DTDE", "P4", None),
    ("CEDT_P4", "CEDT", "P4", None),
    ("CEDT_P3_eps2", "CEDT", "P3", 2.0),
]

R_SYSTEM = """You are the Research-party (R) planning agent in a two-party \
joint active-learning campaign searching 30 candidate 2D MX2 monolayers.
A candidate QUALIFIES if, at the final fidelity F4, its structure is valid, \
its band gap including spin-orbit correction lies in [1.0, 2.0] eV, and it \
has no Gamma-phonon instability. Fidelities run F1 (cheap screen, noisy gap) \
-> F2 (relaxation) -> F3 (bands + SOC, accurate gap) -> F4 (phonon check, \
confirms or kills). Each job costs simulated node-hours from a shared budget \
of 500; a fixed 1.0 nh overhead is charged per job attempt.
Your goals, in order: (1) find a first qualifying candidate in as few \
node-hours as possible; (2) qualify as many candidates as the budget allows.
You see only the information permitted by the information contract; cost \
estimates may be noisy or crude. Spend cheap F1 screens to locate candidates \
whose gap probability is high before paying for expensive promotions.
Reply with ONLY a JSON object: {"candidate": "<name>", "why": "<max 12 \
words>"} choosing from the ADMISSIBLE table, or {"stop": true} to end the \
campaign early."""

H_SYSTEM = """You are the HPC-party (H) operator agent choosing the execution \
configuration for one submitted job on a cluster whose nodes have 64 GB \
memory each. If the job's per-node memory demand exceeds 64 GB the job \
fails immediately and wastes its cost. Failures (crashes) also waste 45% of \
the predicted runtime plus overhead. Your goals: maximize completed useful \
work per node-hour and keep the failure rate low.
You see only contract-permitted information about the job; when the job size \
is undisclosed you must provision for the largest plausible job. Predictions \
below come from your own local performance model and are noisy.
Reply with ONLY a JSON object: {"config": <id>, "why": "<max 10 words>"}."""


def window_prob(mu, sd):
    return norm.cdf((GAP_HI - mu) / sd) - norm.cdf((GAP_LO - mu) / sd)


def world_statics(w):
    wk_all = np.stack([base_work(w, f) for f in range(FIDS)])
    eff_all = np.stack([eff_matrix(w, f) for f in range(FIDS)])
    mem_all = np.stack([mem_per_node(w, f) for f in range(FIDS)])
    hard_all = mem_all > NODE_MEM_GB
    headroom = np.clip(NODE_MEM_GB / mem_all, 0.2, 20.0)
    z0_all = (w["beta0"] + 0.8 * C_AGG[None, None, :]
              - 1.5 * np.log(headroom))
    best_cost_all = (wk_all[:, :, None] / eff_all).min(2)
    return dict(wk_all=wk_all, eff_all=eff_all, mem_all=mem_all,
                hard_all=hard_all, z0_all=z0_all, best_cost_all=best_cost_all)


def h_menu(w, f, ne_b, rho_b, kap):
    """H's local per-config predictions given its contract-limited beliefs
    (scalar port of simulator._h_config internals)."""
    wk_b = (w["A"][f] * (ne_b / 38.0) ** w["p_e"]
            * (NK[f] / 36.0) ** w["p_k"])
    eff = (C_NODES ** (w["s"] - 1.0) * w["quirk"] * w["bspeed"]
           * (1 + 0.25 * C_AGG)) * pool_eff(w, NK[f], C_POOLS)
    nh = wk_b / eff * (1 + kap * C_IO)
    mem = (30.0 * (ne_b / 38.0) ** 2 * rho_b * (NK[f] / 36.0) ** 0.3
           * w["memq"] / (C_NODES * C_POOLS ** 0.4)) + 8.0
    headroom = np.clip(NODE_MEM_GB / mem, 0.2, 20.0)
    z = (w["beta0"] + 1.2 * (kap - 0.3) + 0.8 * C_AGG
         - 1.5 * np.log(headroom))
    return nh, mem, 1.0 / (1.0 + np.exp(-z))


# ---------------------------------------------------------------------------
# LLM plumbing


def extract_json(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    for m in reversed(re.findall(r"\{[^{}]*\}", text)):
        try:
            return json.loads(m)
        except json.JSONDecodeError:
            continue
    return None


class Seat:
    """One decision seat bound to one model endpoint."""

    def __init__(self, client, base, model, max_tokens, concurrency,
                 extra_body=None):
        self.client = client
        self.base = base
        self.model = model
        self.max_tokens = max_tokens
        self.extra_body = extra_body or {}
        self.sem = asyncio.Semaphore(concurrency)
        self.calls = 0
        self.fallbacks = 0
        self.latency = 0.0

    async def decide(self, system, user):
        self.calls += 1
        t0 = time.monotonic()
        msgs = [{"role": "system", "content": system},
                {"role": "user", "content": user}]
        for attempt in range(2):
            try:
                async with self.sem:
                    r = await self.client.post(
                        f"{self.base}/v1/chat/completions",
                        json={"model": self.model, "messages": msgs,
                              "temperature": 0.0,
                              "max_tokens": self.max_tokens,
                              **self.extra_body})
                r.raise_for_status()
                out = extract_json(
                    r.json()["choices"][0]["message"]["content"])
                if out is not None:
                    self.latency += time.monotonic() - t0
                    return out
            except Exception:
                await asyncio.sleep(1.5)
            msgs = msgs[:2] + [{"role": "user",
                                "content": "Reply with ONLY the JSON object."}]
        self.latency += time.monotonic() - t0
        self.fallbacks += 1
        return None


# ---------------------------------------------------------------------------
# one campaign (one world x condition x seed x policy)


async def run_campaign(w, stw, topology, cbase, seed, policy, seats, trace):
    lvl, gam = cbase.level, cbase.gamma
    cls = (np.arange(C) if lvl == "P0" else world_classes(w, lvl))
    cv = ContractView(cbase, cls)
    nb = cv.nclasses
    rel = (CAND["nelec"] / 38.0) ** 2.5
    nelec_hi = float(np.quantile(CAND["nelec"], 0.9))
    cls_top = np.array([CAND["nelec"][cls == b].max() for b in range(nb)])
    rho_top = np.array([w["rho"][cls == b].max() for b in range(nb)])
    bsz = np.array([(cls == b).sum() for b in range(nb)])

    mu = GAP_PRIOR_MU.copy()
    prec = np.full(C, 1.0 / 0.5 ** 2)
    fid_done = np.full(C, -1)
    dead = np.zeros(C, bool)
    qualified = np.zeros(C, bool)
    nh_used = 0.0
    attempts = fails = memfails = labels_f2 = att_f2 = qe_calls = 0
    first_qual_nh = np.nan
    attempt_ct = np.zeros((C, FIDS), int)
    queried = np.zeros(C, bool)
    mi_score = np.zeros(C)
    n_msgs = 0.0
    cfg_obs_sum = np.zeros(sim.J)
    cfg_obs_n = np.zeros(sim.J)
    chg_sum = np.zeros(FIDS)
    chg_n = np.zeros(FIDS)
    agree_r = agree_h = n_r = n_h = 0

    for t in range(sim.T):
        kap = float(w["kappa"][seed, t])
        # ---------------- R seat ----------------
        sd = 1.0 / np.sqrt(prec)
        pwin = window_prob(mu, sd)
        value = pwin ** 2 * PHONON_PRIOR
        value[dead | qualified] = 0.0
        nfid = np.clip(fid_done + 1, 1, 4)
        value[(nfid == 4) & (pwin < 0.5)] = 0.0
        wk_next = stw["wk_all"][nfid, np.arange(C)]
        if topology == "CTCE":
            cost_est = stw["best_cost_all"][nfid, np.arange(C)]
        elif topology == "CEDT" and lvl in ("P1", "P2", "P3"):
            cost_est = (stw["best_cost_all"][nfid, np.arange(C)]
                        * np.exp(w["view_noise"][seed] * cv.cost_sd))
        else:  # DTDE / P4: regress observed charges on size shape
            base_chg = np.where(chg_n[nfid] > 0,
                                chg_sum[nfid] / np.maximum(chg_n[nfid], 1),
                                wk_next / 0.8)
            cost_est = base_chg * rel / rel.mean()
        acq = (value / (np.maximum(cost_est, 0.02) + OVERHEAD_NH)
               * np.where(nfid == 1, 1.5, 1.0))
        i_script = int(acq.argmax())
        if acq[i_script] <= 1e-12:
            break
        i = i_script
        if policy == "llm":
            adm = np.where(acq > 1e-12)[0]
            rows = ["name | next_fidelity | P(gap in window)% | gap est (eV) "
                    "| phonon prior | est cost (nh)"]
            for c in adm:
                rows.append(
                    f"{CAND['names'][c]} | F{nfid[c]} | {100*pwin[c]:.0f} | "
                    f"{mu[c]:.2f}+-{sd[c]:.2f} | {PHONON_PRIOR[c]:.2f} | "
                    f"{cost_est[c]:.1f}")
            user = (f"Round {t+1}/{sim.T}. Budget used {nh_used:.0f}/500 nh, "
                    f"attempts {attempts}/100. Contract level {lvl}, "
                    f"topology {topology}.\nADMISSIBLE candidates:\n"
                    + "\n".join(rows))
            out = await seats["R"].decide(R_SYSTEM, user)
            n_r += 1
            why = ""
            if out and out.get("stop"):
                if trace is not None:
                    trace.append(dict(t=t, seat="R", choice="stop",
                                      scripted=CAND["names"][i_script]))
                break
            if out and out.get("candidate") in CAND["names"]:
                c = CAND["names"].index(out["candidate"])
                if c in adm:
                    i = c
                    why = str(out.get("why", ""))[:120]
                else:
                    seats["R"].fallbacks += 1
            elif out is not None:
                seats["R"].fallbacks += 1
            agree_r += (i == i_script)
            if trace is not None:
                trace.append(dict(t=t, seat="R", choice=CAND["names"][i],
                                  scripted=CAND["names"][i_script], why=why))
        f = int(nfid[i])
        # ---------------- H seat ----------------
        esc = 1.6 ** min(attempt_ct[i, f], 3)
        if topology == "CTCE":
            nh_v = (stw["wk_all"][f, i] / stw["eff_all"][f, i, :]
                    * (1 + kap * C_IO))
            mem_v = stw["mem_all"][f, i, :]
            pf_v = 1.0 / (1.0 + np.exp(-(stw["z0_all"][f, i, :]
                                         + 1.2 * (kap - 0.3))))
            aggressive_ok = True
            size_line = (f"Job size fully disclosed: {CAND['nelec'][i]:.0f} "
                         f"electrons, fidelity F{f} (exact predictions).")
        else:
            if topology == "CEDT":
                ne_b = gam * cls_top[cls[i]] + (1 - gam) * nelec_hi
                rho_b = (gam * rho_top[cls[i]] + (1 - gam) * 1.56) * esc
                aggressive_ok = True
                size_line = (f"Disclosed size class upper bound: {ne_b:.0f} "
                             f"electrons (contract {lvl}), fidelity F{f}."
                             if gam > 0 else
                             f"Job size undisclosed (contract {lvl}); "
                             f"provisioned bound {ne_b:.0f} electrons, "
                             f"fidelity F{f}.")
            else:  # DTDE
                ne_b, rho_b = nelec_hi, 1.56 * esc
                aggressive_ok = False
                size_line = (f"Job size undisclosed; worst-case bound "
                             f"{ne_b:.0f} electrons, fidelity F{f}.")
            nh_v, mem_v, pf_v = h_menu(w, f, ne_b, rho_b, kap)
        score = nh_v * (1 + 2 * pf_v) + 1e3 * (mem_v > NODE_MEM_GB)
        if not aggressive_ok:
            score = score + 1e3 * C_AGG
        j_script = int(score.argmin())
        j = j_script
        if policy == "llm":
            rows = ["id | nodes | pools | aggressive_opts | pred hours | "
                    "pred mem GB/node | pred fail %"]
            for cj in range(sim.J):
                if not aggressive_ok and C_AGG[cj]:
                    continue
                rows.append(f"{cj} | {CONFIGS[cj][0]} | {CONFIGS[cj][1]} | "
                            f"{'yes' if CONFIGS[cj][2] else 'no'} | "
                            f"{nh_v[cj]:.2f} | {mem_v[cj]:.0f} | "
                            f"{100*pf_v[cj]:.0f}")
            retry = (f" This is retry attempt {attempt_ct[i, f]+1} after "
                     f"failures; beliefs already inflated." if
                     attempt_ct[i, f] else "")
            user = (f"{size_line} Cluster contention now {kap:.2f} "
                    f"(0=idle, 1=saturated).{retry}\nConfig menu:\n"
                    + "\n".join(rows))
            out = await seats["H"].decide(H_SYSTEM, user)
            n_h += 1
            why = ""
            ok_ids = [cj for cj in range(sim.J)
                      if aggressive_ok or not C_AGG[cj]]
            try:
                cfg = int(out.get("config")) if out is not None else None
            except (TypeError, ValueError):
                cfg = None
            if cfg is not None and cfg in ok_ids:
                j = cfg
                why = str(out.get("why", ""))[:120]
            elif out is not None:
                seats["H"].fallbacks += 1
            agree_h += (j == j_script)
            if trace is not None:
                trace.append(dict(t=t, seat="H", choice=j,
                                  scripted=j_script, why=why))
        # ---------------- execute ----------------
        att_i = min(attempt_ct[i, f], 3)
        noise = w["nh_noise"][seed, i, f, att_i]
        nh_real = (stw["wk_all"][f, i] / stw["eff_all"][f, i, j]
                   * (1 + kap * C_IO[j]) * noise)
        pfail = 1.0 / (1.0 + np.exp(-(stw["z0_all"][f, i, j]
                                      + 1.2 * (kap - 0.3))))
        hard = bool(stw["hard_all"][f, i, j])
        failed = bool(w["fail_u"][seed, i, f, att_i] < pfail) or hard
        nh_used += (0.45 * nh_real if failed else nh_real) + OVERHEAD_NH
        attempts += 1
        qe_calls += 1
        attempt_ct[i, f] += 1
        queried[i] = True
        fails += failed
        memfails += failed and hard
        att_f2 += f >= 2
        if not failed:
            fid_done[i] = f
            labels_f2 += f >= 2
            if 1 <= f <= 3:
                soc_add = w["soc"][i] if f == 3 else 0.0
                obs = (w["gap"][i] + soc_add
                       + w["gap_noise"][seed, i, f] * SIG_GAP_OBS[f])
                p_obs = 1.0 / SIG_GAP_OBS[f] ** 2
                new_prec = prec[i] + p_obs
                mu[i] = (mu[i] * prec[i] + obs * p_obs) / new_prec
                prec[i] = new_prec
            if f == 1 and not w["valid"][i]:
                dead[i] = True
            if f == 4:
                gap_f = w["gap"][i] + w["soc"][i]
                if (w["stable"][i] and w["valid"][i]
                        and GAP_LO <= gap_f <= GAP_HI):
                    qualified[i] = True
                    if np.isnan(first_qual_nh):
                        first_qual_nh = nh_used
                else:
                    dead[i] = True
        elif attempt_ct[i, f] >= 3:
            dead[i] = True
        sd2 = 1.0 / np.sqrt(prec)
        dead |= (fid_done == 3) & (window_prob(mu, sd2) < 0.15)
        # learning / transcript
        charge = nh_real if lvl in ("P0", "P1") else stw["wk_all"][f, i] / 0.8
        chg_sum[f] += charge
        chg_n[f] += 1
        if gam > 0 and topology in ("CEDT", "CTDE"):
            mi_score += gam * (cls == cls[i]) / bsz[cls[i]]
            n_msgs += 1
        cfg_obs_sum[j] += np.log(max(nh_real, 1e-3))
        cfg_obs_n[j] += 1
        if nh_used >= BUDGET_NH or attempts >= sim.MAX_ATTEMPTS:
            break
        if not ((~dead) & (~qualified)).any():
            break

    return dict(mu=mu, prec=prec, fid_done=fid_done, qualified=qualified,
                nh_used=nh_used, attempts=attempts, fails=fails,
                memfails=memfails, labels_f2=labels_f2, att_f2=att_f2,
                first_qual_nh=first_qual_nh, qe_calls=qe_calls,
                queried=queried, mi_score=mi_score, n_msgs=n_msgs,
                cfg_obs_sum=cfg_obs_sum, cfg_obs_n=cfg_obs_n,
                agree_r=agree_r, agree_h=agree_h, n_r=n_r, n_h=n_h), cv


def stack_seeds(per_seed):
    st = {}
    for k in ("mu", "prec", "fid_done", "qualified", "queried", "mi_score",
              "cfg_obs_sum", "cfg_obs_n"):
        st[k] = np.stack([p[k] for p in per_seed])
    for k in ("nh_used", "attempts", "fails", "memfails", "labels_f2",
              "att_f2", "first_qual_nh", "qe_calls", "n_msgs"):
        st[k] = np.array([p[k] for p in per_seed])
    return st


def make_contract(lvl, eps):
    contract = Contract(lvl if lvl != "P0" else "P1", eps)
    if lvl == "P0":
        contract.level = "P0"
        contract.gamma = 1.0
        contract.classes = np.arange(C)
        contract.nclasses = C
        contract.cost_sd = 0.0
    return contract


async def run_world(card, wid, policy, seats, trace_key=None):
    w = sample_world(card, wid)
    stw = world_statics(w)
    res, decisions = {}, {}
    for name, topo, lvl, eps in CONDITIONS:
        cbase = make_contract(lvl, eps)
        trace = ([] if trace_key == (card, wid, name) else None)
        outs = await asyncio.gather(*[
            run_campaign(w, stw, topo, cbase, s, policy, seats,
                         trace if s == 0 else None)
            for s in range(NSEEDS)])
        per_seed = [o[0] for o in outs]
        cv = outs[0][1]
        st = stack_seeds(per_seed)
        res[name] = sim._score_campaign(w, topo, cv, st)
        decisions[name] = dict(
            rounds=float(st["attempts"].mean()),
            agree_r=sum(p["agree_r"] for p in per_seed),
            n_r=sum(p["n_r"] for p in per_seed),
            agree_h=sum(p["agree_h"] for p in per_seed),
            n_h=sum(p["n_h"] for p in per_seed))
        if trace is not None:
            decisions[name]["trace"] = trace
    summary = sim.eval_world(res)
    info = dict(card=card, world=wid, policy=policy,
                n_true_qual=int(w["qual"].sum()))
    return info, summary, decisions


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worlds-per-card", type=int, default=4)
    ap.add_argument("--r-base", default="http://127.0.0.1:8010")
    ap.add_argument("--h-base", default="http://127.0.0.1:8011")
    ap.add_argument("--r-model", default="Qwen/Qwen3-4B-Instruct-2507")
    ap.add_argument("--h-model",
                    default="nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4")
    ap.add_argument("--concurrency", type=int, default=32)
    ap.add_argument("--out", default="results/llm_results.json")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    if args.smoke:
        args.worlds_per_card = 1
        sim.T = 8

    import httpx
    client = httpx.AsyncClient(timeout=300.0,
                               limits=httpx.Limits(max_connections=128))
    seats = {"R": Seat(client, args.r_base, args.r_model, 200,
                       args.concurrency),
             "H": Seat(client, args.h_base, args.h_model, 220,
                       args.concurrency,
                       extra_body={"chat_template_kwargs":
                                   {"enable_thinking": False}})}

    cards = (["base", "strong_coupling", "adversarial"]
             if not args.smoke else ["base"])
    worlds = [(card, wid) for card in cards
              for wid in range(args.worlds_per_card)]
    trace_key = ("base", 0, "CEDT_P4")

    t0 = time.time()
    tasks = []
    for card, wid in worlds:
        tasks.append(run_world(card, wid, "scripted", seats))
        tasks.append(run_world(card, wid, "llm", seats,
                               trace_key=trace_key))
    outs = await asyncio.gather(*tasks)
    await client.aclose()

    records, traces = [], {}
    for info, summary, decisions in outs:
        for cond, d in summary.items():
            rec = dict(info)
            rec["condition"] = cond
            rec.update({k: float(v) for k, v in d.items()})
            dd = decisions.get(cond, {})
            rec.update({k: dd[k] for k in
                        ("rounds", "agree_r", "n_r", "agree_h", "n_h")
                        if k in dd})
            records.append(rec)
            if "trace" in dd and info["policy"] == "llm":
                traces[f"{info['card']}:{info['world']}:{cond}"] = dd["trace"]

    meta = dict(nseeds=NSEEDS, worlds=len(worlds), conditions=len(CONDITIONS),
                r_model=args.r_model, h_model=args.h_model,
                r_calls=seats["R"].calls, r_fallbacks=seats["R"].fallbacks,
                h_calls=seats["H"].calls, h_fallbacks=seats["H"].fallbacks,
                r_mean_latency_s=seats["R"].latency / max(seats["R"].calls, 1),
                h_mean_latency_s=seats["H"].latency / max(seats["H"].calls, 1),
                wall_s=time.time() - t0)
    outp = HERE / args.out
    outp.parent.mkdir(exist_ok=True)
    with open(outp, "w") as fh:
        json.dump(dict(meta=meta, records=records), fh)
    with gzip.open(outp.with_name("llm_traces.json.gz"), "wt") as fh:
        json.dump(traces, fh)
    print(json.dumps(meta, indent=2))
    print(f"wrote {len(records)} records to {outp}")


if __name__ == "__main__":
    asyncio.run(main())

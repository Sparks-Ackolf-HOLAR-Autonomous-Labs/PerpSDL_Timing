#!/usr/bin/env python3
"""LLM decision-maker agents for the R and H parties.

Protocol: each decision is a fresh short conversation. The agent sees a
contract-filtered observation and replies with STRICT JSON — either a tool
call ({"action":"tool", ...}), a decision ({"action":"decide", ...}), or a
delegation (a decision plus {"delegate": {tool, args, rounds}} that lets the
chosen algorithm act unattended for a few rounds). Up to MAX_TOOL_CALLS tool
invocations per decision; if the agent keeps calling tools, the last tool's
top suggestion is auto-accepted (counted separately). If the reply cannot be
parsed twice in a row, the scripted policy decides (counted as a fallback).
"""
import asyncio
import inspect
import json
import re

import numpy as np

import env as envmod
import tools as T

MAX_TOOL_CALLS = 3
MAX_DELEGATE = 5

R_SYSTEM = """You are the decision agent for research party R in a joint
materials-screening campaign run under an information-sharing contract
({level}, topology {topology}). Goal: find candidates whose final band gap
lands in [1.0, 2.0] eV and that pass a phonon check at fidelity F4, using as
few node-hours as possible. Each round you choose ONE candidate to run at its
next fidelity (F1 screen -> F2 relax -> F3 bands -> F4 phonon), or stop.
Cost estimates come only from what the contract discloses; they can be wrong.
Balance exploring uncertain candidates against exploiting near-window ones,
and mind the remaining budget.

Tools you may call (real algorithms, you choose the parameters):
- rank_candidates(strategy, top_k, explore_weight, n_samples): strategy in
  [cost_aware_greedy, ucb, thompson, pure_value]
- portfolio_plan(horizon_nh, value_power): budget-constrained knapsack plan
- posterior_summary(top_k): belief detail sorted by window probability

Reply with ONE JSON object only, no other text. Formats:
{{"action":"tool","tool":"<name>","args":{{...}}}}
{{"action":"decide","candidate":<id>}}
{{"action":"decide","candidate":<id>,"delegate":{{"tool":"<name>","args":{{...}},"rounds":<1-5>}}}}
{{"action":"stop"}}
Delegation lets that tool's top pick act for the next N rounds without you.
Ground your choices in the algorithms: unless you are re-delegating an
approach that is working, call at least one tool (with parameters you chose
for the current situation) before deciding, and compare its suggestion with
your own reading of the table."""

H_SYSTEM = """You are the decision agent for HPC party H in a joint
materials-screening campaign under an information-sharing contract ({level},
topology {topology}). A job (candidate opaque to you at this contract level)
must run at fidelity F{fid}. You choose the execution config (nodes, k-point
pools, aggressive flag). Your objectives: high valid-label throughput per
node-hour, few failures, and NO memory-limit failures (node memory 64 GB).
Your size/memory beliefs come only from what the contract discloses; when
uncertain, protect against memory overruns. kappa is current contention.

Tools you may call (real algorithms, you choose the parameters):
- config_table(): your model's per-config predictions (nh, memory, pfail)
- config_optimizer(risk_weight, mem_margin): constrained argmin of
  nh*(1+risk_weight*pfail) s.t. mem*mem_margin <= 64 GB
- config_montecarlo(n_draws, quantile): Monte-Carlo cost-with-retries risk

Reply with ONE JSON object only, no other text. Formats:
{{"action":"tool","tool":"<name>","args":{{...}}}}
{{"action":"decide","config":<id>}}
{{"action":"decide","config":<id>,"delegate":{{"tool":"<name>","args":{{...}},"rounds":<1-5>}}}}
Delegation lets that tool's choice act for the next N jobs without you.
Ground your choices in the algorithms: unless you are re-delegating an
approach that is working, call at least one tool (with parameters you chose
for the current situation, e.g. raise mem_margin after a memory failure or
under high kappa) before deciding."""


def render_r_obs(env):
    st = env.r_state()
    lines = [f"round={st['t']} nh_used={st['nh_used']:.1f}"
             f"/{st['budget']:.0f} attempts={st['attempts']}"
             f" fails={st['fails']}"
             f" qualified={int(env.qualified.sum())}",
             "admissible candidates (id name nextF mu sd pwin cost_est):"]
    for i in range(envmod.C):
        if not st["admissible"][i]:
            continue
        lines.append(f"{i} {envmod.CAND['names'][i]} F{st['next_fid'][i]}"
                     f" {st['mu'][i]:.2f} {st['sd'][i]:.2f}"
                     f" {st['pwin'][i]:.2f} {st['cost_est'][i]:.1f}")
    if st["events"]:
        lines.append("recent jobs: " + json.dumps(st["events"]))
    return "\n".join(lines)


def render_h_obs(env, cand):
    tab = T.config_table(env, cand)
    lines = [f"job at F{tab['fid']}, contention kappa={tab['kappa']:.2f}, "
             f"believed job size (electrons)={tab['ne_belief']}, "
             f"retry_escalation={tab['retry_escalation']}",
             "configs (id nodes pools aggr allowed nh_est memGB pfail):"]
    for r in tab["configs"]:
        lines.append(f"{r['config']} {r['nodes']} {r['pools']}"
                     f" {r['aggressive']} {int(r['allowed'])}"
                     f" {r['nh_est']} {r['mem_est_gb']} {r['pfail']}")
    recent = [e for e in env.events[-5:]]
    if recent:
        lines.append("recent jobs: " + json.dumps(
            [{k: e[k] for k in ("t", "fid", "config", "nh", "failed",
                                "memfail") if k in e} for e in recent]))
    return "\n".join(lines)


def parse_json(text):
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("no JSON object found")
    return json.loads(m.group(0))


def filter_args(fn, args):
    sig = inspect.signature(fn)
    return {k: v for k, v in (args or {}).items()
            if k in sig.parameters and k not in ("env", "cand")}


class LLMClient:
    def __init__(self, base_url, model, session, sem,
                 temperature=0.2, max_tokens=350):
        self.base_url = base_url
        self.model = model
        self.session = session
        self.sem = sem
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.n_calls = 0

    async def chat(self, messages):
        async with self.sem:
            self.n_calls += 1
            r = await self.session.post(
                f"{self.base_url}/v1/chat/completions",
                json=dict(model=self.model, messages=messages,
                          temperature=self.temperature,
                          max_tokens=self.max_tokens),
                timeout=120)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]


class AgentTelemetry:
    def __init__(self):
        self.llm_calls = {"R": 0, "H": 0}
        self.tool_calls = {}
        self.delegated = {"R": 0, "H": 0}
        self.fallbacks = {"R": 0, "H": 0}
        self.auto_accepts = {"R": 0, "H": 0}
        self.overrides = {"R": 0, "H": 0}   # decided != last tool suggestion
        self.tool_informed = {"R": 0, "H": 0}
        self.direct = {"R": 0, "H": 0}      # decided with no tool call
        self.delegate_choices = {"R": {}, "H": {}}

    def note_delegate(self, role, deleg):
        args = deleg.get("args") or {}
        detail = args.get("strategy") or ",".join(
            f"{k}={args[k]}" for k in sorted(args)) or "default"
        key = f"{deleg['tool']}({detail})"
        d = self.delegate_choices[role]
        d[key] = d.get(key, 0) + 1

    def as_dict(self):
        return {k: getattr(self, k) for k in
                ("llm_calls", "tool_calls", "delegated", "fallbacks",
                 "auto_accepts", "overrides", "tool_informed", "direct",
                 "delegate_choices")}


async def agent_decide(role, env, cand, client, tel, sys_prompt, obs,
                       tool_reg, suggest_fn, scripted_fn):
    """One decision loop. Returns (choice, delegate_dict_or_None)."""
    messages = [{"role": "system", "content": sys_prompt},
                {"role": "user", "content": obs}]
    last_suggestion = None
    parse_fail = 0
    for _ in range(MAX_TOOL_CALLS + 3):
        try:
            tel.llm_calls[role] += 1
            reply = await client.chat(messages)
            act = parse_json(reply)
        except Exception:
            parse_fail += 1
            if parse_fail >= 2:
                tel.fallbacks[role] += 1
                return scripted_fn(), None
            messages.append({"role": "user", "content":
                             "Reply with ONE valid JSON object only."})
            continue
        messages.append({"role": "assistant", "content": reply})
        if act.get("action") == "stop" and role == "R":
            return None, None
        if act.get("action") == "tool":
            name = act.get("tool")
            n_tools = sum(1 for m in messages if m["role"] == "user"
                          and m["content"].startswith("tool_result"))
            if name not in tool_reg or n_tools >= MAX_TOOL_CALLS:
                # out of tool budget (or bad tool): auto-accept a suggestion
                choice, _ = suggest_fn(name if name in tool_reg
                                       else next(iter(tool_reg)),
                                       filter_args(
                                           tool_reg.get(name, next(iter(
                                               tool_reg.values()))),
                                           act.get("args")))
                tel.auto_accepts[role] += 1
                if choice is None:
                    tel.fallbacks[role] += 1
                    return scripted_fn(), None
                return choice, None
            fn = tool_reg[name]
            args = filter_args(fn, act.get("args"))
            tel.tool_calls[name] = tel.tool_calls.get(name, 0) + 1
            choice, res = suggest_fn(name, args)
            last_suggestion = choice
            messages.append({"role": "user", "content":
                             "tool_result " + json.dumps(res)[:2500]
                             + "\nNow decide (or call one more tool)."})
            continue
        if act.get("action") == "decide":
            key = "candidate" if role == "R" else "config"
            try:
                choice = int(act[key])
            except (KeyError, TypeError, ValueError):
                tel.fallbacks[role] += 1
                return scripted_fn(), None
            if last_suggestion is None:
                tel.direct[role] += 1
            else:
                tel.tool_informed[role] += 1
                if choice != last_suggestion:
                    tel.overrides[role] += 1
            deleg = act.get("delegate")
            if isinstance(deleg, dict) and deleg.get("tool") in tool_reg:
                deleg = dict(tool=deleg["tool"],
                             args=filter_args(tool_reg[deleg["tool"]],
                                              deleg.get("args")),
                             rounds=int(np.clip(deleg.get("rounds", 3),
                                                1, MAX_DELEGATE)))
            else:
                deleg = None
            return choice, deleg
        # unrecognized action
        parse_fail += 1
        if parse_fail >= 2:
            tel.fallbacks[role] += 1
            return scripted_fn(), None
        messages.append({"role": "user", "content":
                         'Use {"action":"tool"|"decide"|"stop", ...}.'})
    tel.fallbacks[role] += 1
    return scripted_fn(), None


async def run_llm_campaign(env, client):
    tel = AgentTelemetry()
    r_sys = R_SYSTEM.format(level=env.level, topology=env.topology)
    r_deleg = None   # (tool, args, rounds_left)
    h_deleg = None
    while not env.done:
        # ---- R decision
        if r_deleg and r_deleg["rounds"] > 0:
            i, _ = T.tool_top_candidate(env, r_deleg["tool"], r_deleg["args"])
            r_deleg["rounds"] -= 1
            tel.delegated["R"] += 1
            if i is None or not env.admissible()[i]:
                r_deleg = None
                i = None
        else:
            i = None
        if i is None:
            def r_suggest(name, args):
                return T.tool_top_candidate(env, name, args)
            i, deleg = await agent_decide(
                "R", env, None, client, tel, r_sys, render_r_obs(env),
                T.R_TOOLS, r_suggest,
                lambda: envmod.scripted_pick_candidate(env))
            if deleg:
                r_deleg = deleg
                tel.note_delegate("R", deleg)
            if i is None:
                break
            i = int(i)
            if not (0 <= i < envmod.C) or not env.admissible()[i]:
                tel.fallbacks["R"] += 1
                i = envmod.scripted_pick_candidate(env)
                if i is None:
                    break
        # ---- H decision
        fid = int(env.next_fid()[i])
        if h_deleg and h_deleg["rounds"] > 0:
            j, _ = T.tool_top_config(env, i, h_deleg["tool"], h_deleg["args"])
            h_deleg["rounds"] -= 1
            tel.delegated["H"] += 1
            if j is None:
                h_deleg = None
        else:
            j = None
        if j is None:
            h_sys = H_SYSTEM.format(level=env.level, topology=env.topology,
                                    fid=fid)

            def h_suggest(name, args, _i=i):
                return T.tool_top_config(env, _i, name, args)
            j, deleg = await agent_decide(
                "H", env, i, client, tel, h_sys, render_h_obs(env, i),
                T.H_TOOLS, h_suggest,
                lambda _i=i: envmod.scripted_pick_config(env, _i))
            if deleg:
                h_deleg = deleg
                tel.note_delegate("H", deleg)
            j = int(j)
            if not (0 <= j < envmod.J) or (
                    not env.aggressive_ok and envmod.C_AGG[j] > 0):
                tel.fallbacks["H"] += 1
                j = envmod.scripted_pick_config(env, i)
        env.step(i, j)
    return env.score(), tel.as_dict()

#!/usr/bin/env python3
"""Run the reduced LLM-agents-with-tools grid vs the scripted control.

Paired design: every (world, seed, condition) is run twice through the SAME
stepwise env — once driven by the scripted policies, once by LLM agents with
the tool registry. Reduced budget (250 simulated nh, 40 rounds) keeps the
LLM arm tractable. All node-hours are simulated units.
"""
import argparse
import asyncio
import json
import time
from pathlib import Path

import env as envmod
import simulator as sim
from agents import LLMClient, run_llm_campaign
from env import CampaignEnv, run_scripted

HERE = Path(__file__).parent
CONDS = [("DTDE_P4", "DTDE", "P4", None),
         ("CEDT_P4", "CEDT", "P4", None),
         ("CTDE_P2", "CTDE", "P2", None)]
BUDGET = 250.0
ROUNDS = 40
ATTEMPTS = 50


def make_env(card, wid, seed, topo, lvl, eps):
    w = sim.sample_world(card, wid)
    return CampaignEnv(w, seed, topo, lvl, eps,
                       budget=BUDGET, max_rounds=ROUNDS,
                       max_attempts=ATTEMPTS)


class MockClient:
    """Deterministic stand-in for local smoke tests (no LLM server)."""

    def __init__(self):
        self.n_calls = 0

    async def chat(self, messages):
        self.n_calls += 1
        sysmsg = messages[0]["content"]
        n_tool_results = sum(1 for m in messages if m["role"] == "user"
                             and m["content"].startswith("tool_result"))
        if "research party R" in sysmsg:
            if n_tool_results == 0:
                return ('{"action":"tool","tool":"rank_candidates",'
                        '"args":{"strategy":"thompson","top_k":5}}')
            last = [m for m in messages if m["role"] == "user"
                    and m["content"].startswith("tool_result")][-1]
            res = json.loads(last["content"][len("tool_result "):
                                             last["content"].rfind("}") + 1])
            rk = res.get("ranking") or []
            if not rk:
                return '{"action":"stop"}'
            return json.dumps({
                "action": "decide", "candidate": rk[0]["cand"],
                "delegate": {"tool": "rank_candidates",
                             "args": {"strategy": "thompson"}, "rounds": 3}})
        if n_tool_results == 0:
            return ('{"action":"tool","tool":"config_optimizer",'
                    '"args":{"risk_weight":2.0,"mem_margin":1.1}}')
        last = [m for m in messages if m["role"] == "user"
                and m["content"].startswith("tool_result")][-1]
        res = json.loads(last["content"][len("tool_result "):
                                         last["content"].rfind("}") + 1])
        return json.dumps({"action": "decide",
                           "config": res.get("best_config", 0)})


async def run_all(args):
    cards = ["base", "strong_coupling", "adversarial"]
    cells = []
    for ci, card in enumerate(cards):
        for k in range(args.worlds_per_card):
            wid = 200000 + ci * 1000 + k
            for seed in range(args.seeds):
                for cond in CONDS:
                    cells.append((card, wid, seed) + cond)
    print(f"{len(cells)} cells x 2 arms")

    records = []
    t0 = time.time()
    # scripted arms (fast, synchronous)
    for card, wid, seed, name, topo, lvl, eps in cells:
        e = make_env(card, wid, seed, topo, lvl, eps)
        sc = run_scripted(e)
        records.append(dict(card=card, world=wid, seed=seed, condition=name,
                            arm="scripted", **sc))
    print(f"scripted arms done in {time.time()-t0:.1f}s")

    if args.mock:
        client = MockClient()
        sem = None
    else:
        import httpx
        session = httpx.AsyncClient()
        sem = asyncio.Semaphore(args.concurrency)
        client = LLMClient(args.base_url, args.model, session, sem,
                           temperature=args.temperature)

    async def one(cell):
        card, wid, seed, name, topo, lvl, eps = cell
        e = make_env(card, wid, seed, topo, lvl, eps)
        sc, tel = await run_llm_campaign(e, client)
        return dict(card=card, world=wid, seed=seed, condition=name,
                    arm="llm", telemetry=tel, **sc)

    t0 = time.time()
    done = 0
    for fut in asyncio.as_completed([one(c) for c in cells]):
        rec = await fut
        records.append(rec)
        done += 1
        if done % 5 == 0 or done == len(cells):
            print(f"llm arm {done}/{len(cells)} "
                  f"({time.time()-t0:.0f}s, {client.n_calls} LLM calls)",
                  flush=True)

    out = HERE / args.out
    out.parent.mkdir(exist_ok=True)
    with open(out, "w") as fh:
        json.dump(dict(budget=BUDGET, rounds=ROUNDS, attempts=ATTEMPTS,
                       model=(None if args.mock else args.model),
                       records=records), fh)
    print(f"wrote {len(records)} records to {out}")
    if not args.mock:
        await session.aclose()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worlds-per-card", type=int, default=3)
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--concurrency", type=int, default=24)
    ap.add_argument("--base-url", default="http://localhost:8010")
    ap.add_argument("--model", default="Qwen/Qwen3-4B-Instruct-2507")
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--out", default="results/llm_grid_raw.json")
    ap.add_argument("--mock", action="store_true")
    args = ap.parse_args()
    asyncio.run(run_all(args))


if __name__ == "__main__":
    main()

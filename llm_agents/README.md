# LLM agents as decision makers (with tools)

Design (2026-09-02): the parties are played by
LLM agents making the round-by-round decisions, and those agents must
be able to use tools (optimization and sampling algorithms) rather than being
pure-LLM, while still not having everything scripted.

## Design

- `env.py` — stepwise, single-seed campaign environment. It replays exactly
  the same prior worlds, twin equations, noise fields, and contract filters as
  `../prior_predictive/simulator.py`, but exposes one decision at a time. The
  scripted greedy policies are reimplemented here too, so the control arm runs
  through the identical env: paired comparisons at the same (reduced) budget.
- `tools.py` — the toolbox. Real algorithms operating on the party's own
  contract-filtered information:
  - R: `rank_candidates` (cost-aware greedy / UCB / Thompson sampling /
    pure value), `portfolio_plan` (budget knapsack), `posterior_summary`.
  - H: `config_table`, `config_optimizer` (constrained argmin with
    caller-chosen risk weight and memory margin), `config_montecarlo`
    (sampled cost-with-retries risk estimate at a caller-chosen quantile).
- `agents.py` — the LLM loop. Each decision is a fresh short conversation:
  contract-filtered observation → optional tool calls (max 3, the LLM picks
  the tool AND its parameters) → strict-JSON decision. The agent may also
  **delegate**: hand the next 1–5 rounds to a tool it configured. If a reply
  cannot be parsed twice, the scripted policy decides (logged as a fallback).
  Telemetry records tool choices, parameters, delegation, overrides
  (deciding against the tool's suggestion), and fallbacks.
- `run_llm_grid.py` — reduced paired grid (default: DTDE-P4 / CEDT-P4 /
  CTDE-P2 × 9 worlds × 2 seeds × {scripted, LLM}, 250 simulated nh, 40
  rounds). `--mock` runs a deterministic stand-in agent for CI-side testing.
- `analyze_llm.py` — paired deltas + telemetry aggregation + figure.

Model: `Qwen/Qwen3-4B-Instruct-2507` served by the resident vLLM on the DGX
(port 8010). All node-hours are simulated units.

## What "not scripted" means here

The env computes physics/billing consequences and enforces the contract; the
agents decide. Every candidate pick and config choice is either (a) an LLM
decision, possibly informed by tool output it requested, or (b) the output of
an algorithm the LLM explicitly configured and delegated to for a bounded
number of rounds. The scripted policies run only in the control arm and as a
last-resort parse fallback (fallback counts are reported; they were 0 in the
production runs).

## Results

See `RESULTS_LLM.md`. Raw records: `results/llm_grid_raw.json.gz` (v1),
`results/llm_grid_raw_v2.json.gz` (v2, after fixing the Monte-Carlo tool's
missing hard-memory bound), summaries and figures alongside.

## Earlier run without tools

The first LLM-agent run (two models, no tools, 2 Sept 2026: Qwen3-4B as R, Nemotron 3.5 Lightning 30B as H) is in `no_tools_run/`. The tool-using run is the rest of this folder.

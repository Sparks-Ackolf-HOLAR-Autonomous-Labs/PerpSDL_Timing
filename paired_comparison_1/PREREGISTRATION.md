# Preregistration: live CEDT-P4 vs DTDE comparison (future-work item 1)

## Amendment and activation record (2026-09-09)

**Status: ACTIVATED with two flagged provisions.** The authors' decision of 2026-09-09
(fix the frozen metrics rather than keep them frozen, and assign work to grn061 first)
resolves the metric sign-off and the compute assignment. What changed from the draft:

| Field | Frozen value | Basis |
| --- | --- | --- |
| R metric | **PW60** (win-rate ≥ 0.60 on nh-to-first-qualifier across the 10 paired seeds, sign test) | the authors' metric fix; validated on 300 *fresh* simulated worlds (`../metric_redesign/fresh_world_validation.json`: 0.920 vs selection-set 0.920 — no measurable selection optimism) |
| H metrics | valid F2+ labels/nh ≥ 1.05× DTDE; failure ≤ DTDE + 0.04 | package margins (approved by the authors for trial 2026-09-08, kept) |
| Paired campaigns | N = 10 seeds × 2 arms, identical shuffled candidate orders, arm execution order alternated by seed parity | this document |
| Task | 29 candidates (HfSe2_2H excluded — never relaxed), 3×3 supercells, F1→F2→F3 ladder | scope amendment: production SCF at the measured relaxed geometry replaces fresh 54-atom relaxation; **no F4** in this comparison (budget) |
| Budget | **conservative cap: 100 node-hours total** (est. usage 20–40), per-campaign 5 nh, 24 QE-call cap; SLURM `--time=120:00:00` hard stop (node limit 20160 min) | *provision 1: the study design fixed granite compute and the 20160-min ceiling but no explicit nh number; 100 nh is a conservative reading and is trivially lowerable before results are graded* |
| Timing channel | **accept-and-measure**: the comparison runs with completion times visible and the executed timing attack is *reported*, not claimed as passing | *provision 2: still a governance call; a leakage-pass claim for the timing channel is out of scope of this comparison* |
| Analysis | `analyze_live.py` (committed before submission); wire logs feed the `../measured_attacks/` executed attacks | this document |

A null or negative result remains a publishable outcome and must be reported as prominently
as a positive one. Everything below this line is the original draft, kept verbatim for the
record.

---

**Original status: DRAFT — not in force.** This document becomes binding only when both parties
(the authors acting for R and for H, or two separate parties) sign off on every FROZEN field below
*before* any live campaign job is submitted. Per the governing spec (§20.8), it may
not be activated unilaterally. Nothing in the simulation record counts as evidence for the
live claim; this comparison is the experiment that could.

## 1. Claim under test

At 3×3-supercell task scale, the near-no-sharing broker contract (CEDT-P4) beats the
no-sharing baseline (DTDE) on the redesigned paired metrics, without breaching any leakage
limit measured by **executed** attacks on the real transcripts (not constructed attacker
beliefs — see `../measured_attacks/`).

Simulation predicts success with probability 0.92–0.96 (metric-selection optimism
acknowledged). **A null or negative result is a publishable outcome and must be reported as
prominently as a positive one.**

## 2. Frozen design (the authors must confirm each line)

| Field | Value | Status |
| --- | --- | --- |
| Arms | CEDT-P4 vs DTDE-P4, paired | proposed |
| Task | the 30 CC0 MX₂ candidates × 2 setups (±2% strain variants), 3×3 supercells, F1→F4 ladder | proposed |
| Paired campaigns | 2 × N campaigns, N ≥ 10, identical candidate pools and randomized job order seeds | proposed (N to be set by budget) |
| R metric | PW60: CEDT-P4 beats DTDE on node-hours-to-first-qualifier in ≥ 60% of pairs (sign test, one-sided, α = 0.05) | **requires both-party sign-off — selected post hoc from simulations, so it must be frozen here before data** |
| H metrics | valid F2+ labels per node-hour ≥ 1.05× DTDE; failure rate ≤ DTDE + 0.04 | requires sign-off |
| Leakage audit | executed attacks of `../measured_attacks/` run on the real wire logs; limits: membership AUC ≤ 0.60 (within-campaign), rank-extraction ≤ 0.20 **including the timing-only channel** | requires sign-off |
| Budget cap | live node-hour cap set by the authors (est. 20–60 measured nh per arm on granite) | **REQUIRED (field set by the authors)** |
| Compute | granite `sparks-gpu-grn`/grn061 primary; preemption note in `../pilot/README.md` applies | verified 2026-09-02/08 |
| Stopping rule | hard node-hour cap enforced per campaign; no post-hoc metric changes; analysis script committed before submission | proposed |

## 3. Known threat to the design, from the executed attacks

The real-pilot timing attack (`../measured_attacks/pilot_attack_results.json`) extracts H's
config ranking at correlation ≈ 0.74 from job wall times alone — P4 hides the config field
but cannot hide when a job returns. Before the live comparison can claim "leakage limits
hold," the contract text must either (a) accept the timing channel explicitly, or (b) add a
masking clause (batched/delayed result return, quantized completion times) whose utility cost
the comparison must then also measure. This decision is a governance call and is **blocking**.

## 4. What activation requires (in order)

1. The authors confirm/amend each "requires sign-off" line, set the
   node-hour cap, and resolve the §3 timing-channel decision.
2. The frozen version is committed (values moved to `case_manifest.yaml`), builds the
   input/submit bundle with the same guards as `../pilot/submit.sh` (`PILOT_AUTHORIZED=1`,
   cap enforced), and commits the analysis script.
3. The job is submitted through an authenticated login; results are collected after it completes.

## 5. Submission record (2026-09-09)

Submitted on 2026-09-09 to granite node grn061. First submission (bench `1919941`, live
`1919942`) failed in under 10 seconds on granite's default Python 3.6.8 (no
`time.time_ns`, no walrus operator) — no QE call ever ran, no node-hours consumed
beyond seconds. Fixed by loading `python/3.10.3` in both sbatch files and resubmitted
the same day: **bench `1919944`** (contention + transfer, `../contention_transfer_bench/`),
**live comparison `1919945`** (this document's design; `MPT_LIVE_NH_CAP=100`). The
`sparks-gpu-grn` partition was empty at both submissions — no guest jobs were
preempted. Job IDs are recorded in `.bench_jobid` / `.live_jobid` for result
collection. The timing channel runs accept-and-measure per the
activation record; its extraction correlation will be reported, not claimed as
passing.

## 6. Outcome record (2026-09-10, after collection)

Both jobs COMPLETED, exit 0: bench `1919944` (22 m 30 s), live comparison `1919945`
(19 h 49 m, 480 QE calls, 9.41 measured node-hours vs the 100 nh cap). Graded by the
preregistered `analyze_live.py` exactly as committed before submission:

- **R (PW60): 6/10 paired wins = 0.60** — meets the ≥ 0.60 bar exactly; one-sided
  sign test p = 0.377 (not distinguishable from chance).
- **H (labels/nh ≥ 1.05×): 1.005× — FAIL.** Failure-rate side condition passed
  (0.029 vs 0.033).
- **`preregistered_success: false`.** Per the stopping rule this is the recorded
  verdict; no metric was changed after data collection.

Accept-and-measure timing channel (executed attacks, `wire_attack.py`): exact
candidate-identity accuracy **0.963** (limit 0.087) and membership-inference AUC
**1.000** (limit 0.60) at BOTH arms including P4. As §3 required, this is reported,
not claimed as passing: on real hardware, no tested disclosure level holds its
leakage certificate without timing masking. Full analysis: `RESULTS.md`.

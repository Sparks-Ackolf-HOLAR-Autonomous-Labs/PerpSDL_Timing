# Executed attacks on campaign transcripts (future-work items 3 and 6)

2026-09-09 · run on a 2-core workstation (no cluster job)

Every leakage number graded before this study came from *constructed* attacker beliefs —
Bayes-style score accumulators inside the simulator, with attack power set by the prior card.
This study replaces them with attacks that are **executed**: per-message wire logs are
recorded for each campaign, a real attacker model is trained on transcripts from 120 training
worlds, and graded on 60 held-out worlds it has never seen. One attack also runs on **real
measured transcripts** (the 81 granite pilot jobs).

## Files

- `attack_study.py` — simulated-transcript attacks (CEDT topology, base prior card;
  transcript recording via the new `TRANSCRIPT_HOOK` in `../prior_predictive/simulator.py`)
- `pilot_timing_attack.py` — the real-data attack on `../pilot/results/pilot_results.csv`
- `attack_results.json`, `pilot_attack_results.json`, `attack_stdout.txt` — outputs

## 1. Membership inference (H attacks R): "was candidate X in R's campaign?"

Attacker: regularized logistic regression on transcript features (debiased class counts,
class sizes, opaque-ID repeat concentration, message totals). Reported as **within-campaign
AUC** — can the attacker tell which candidates were queried inside one transcript — which is
what the ≤ 0.60 limit is about. (Pooled AUC is also recorded; it runs 0.67–0.91 and is
inflated, because it additionally rewards predicting how busy a campaign was.)

| Mechanism | greedy R policy | depth-first R policy |
| --- | ---: | ---: |
| P2 (exact bins) | 0.567 | **0.803** |
| P3 (ε=2, persistent opaque IDs) | 0.540 | **0.724** |
| P3 (ε=2, IDs rotated every 10 rounds) | 0.541 | **0.721** |
| P4 (no per-candidate field) | 0.500 | 0.500 |

Findings:

1. **The decision-maker dependence of leakage survives the move from constructed to executed
   attacks.** Under a greedy policy every mechanism passes the 0.60 limit; under a
   depth-first policy (the style real LLM agents exhibited) P2 and P3 breach it decisively.
   This upgrades the H7 rejection from a simulated observation to one demonstrated with a
   trained attacker on held-out transcripts.
2. **ID rotation alone is worthless against this attacker** (0.724 → 0.721). The executed
   attack never needed to link IDs across epochs — the concentration signal lives in the
   retained class-count histogram. The earlier claim that per-epoch ID rotation is "the
   cheapest leakage fix" is hereby corrected: the operative clause is transcript **expiry**
   (deleting old messages), not re-keying them. Rotation only defeats attackers that rely on
   per-ID repeat linkage.
3. **P4's disclosed fields are clean** — within-campaign AUC is exactly chance, in agreement
   with the constructed attacks. (But see §2: P4's *side channel* is not clean.)

## 2. Config-rank extraction (R attacks H): recover the protected config ordering

R always observes its own jobs' wall-clock durations — it sees when results return; no
billing contract can hide that. The contract only controls whether the config *identity* is
also visible. Attack: remove candidate/fidelity fixed effects from log durations, then
estimate the config ordering (config field visible) or score per-job timing residuals against
the true ordering (timing only). Split-half validated. Limit ≤ 0.20.

| Transcript source | config field visible (P1-style) | timing only (P4-style) |
| --- | ---: | ---: |
| Simulated worlds (means across mechanisms) | 0.36–0.47 | 0.03–0.08 |
| **Real pilot transcripts (81 jobs, granite)** | **0.969** (q05 0.90) | **0.736** (q05 0.64) |

Findings:

4. **The timing side channel breaches the leakage limit on real data at every disclosure
   level — including P4.** 0.736 vs the 0.20 limit, from wall times alone. The simulated
   worlds never showed this (0.03–0.08) because the twin's per-job noise is much larger than
   real granite's — the pilot itself measured contention noise as near-silent, and this is
   the attack-side consequence. **"P4 passes every leakage limit" is therefore falsified as a
   statement about real transcripts**: its disclosed fields pass, its side channel does not.
5. Mitigations are contract clauses, not disclosure levels: batched/delayed result return or
   quantized completion times, whose utility cost the live comparison must measure. Recorded
   as a blocking governance item in `../paired_comparison_1/PREREGISTRATION.md`.

## Caveats

- One attacker family (logistic regression on count features); stronger attackers can only
  raise these numbers — a pass here is evidence, not a certificate.
- The real-pilot attack benefits from the pilot's balanced randomized design; a live
  campaign's transcripts are less balanced, so 0.736 is toward the attacker's best case on
  this channel. The live comparison should measure it on its own transcripts.
- Membership inference has no real-data test yet — it needs a live campaign with a held-out
  candidate pool (part of the preregistered comparison).
- Simulated transcripts come from the CEDT topology on the base prior card; the qualitative
  pattern (policy dependence, rotation vs expiry, P4-fields-clean) is expected to transfer,
  but the numbers are mechanism-specific.

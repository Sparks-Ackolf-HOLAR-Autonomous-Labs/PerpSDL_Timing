# Hybrid-mix, ALT, and collusion arms (2026-09-09)

Scope: at least one model for each of DTDE, CTDE, CEDT, and CTCE in the
campaign, plus a hybrid-mix model, plus future-work item 4 (ALT negotiation baseline, collusion variants).

Run: `hybrid_study.py`, 300 worlds x 30 paired seeds x 13 conditions,
common random numbers, hard budget cap, on (a) the wide base prior at
x1 task scale and (b) the measurement-informed posterior (Stage-2 +
81-job pilot) at x100 scale. Graded with both the frozen metrics and
the redesigned metrics (PW60 + package). All node-hours are simulated
units. Raw: `hybrid_results.json`; figure: `fig_hybrid_arms.png`.

## Arms

All four spec topologies were already in the campaign engine
(`prior_predictive/simulator.py` CONDITIONS_MAIN); this study adds:

- **HYB-Pk (hybrid-mix)**: CTDE's shared surrogate feeds R's cost
  estimates AND CEDT's broker matches the execution config each round.
  Both information channels are open and both leak (surrogate ingest +
  per-round proposal stream). At P4 the surrogate is disabled by
  construction (gamma = 0), so HYB-P4 is identically CEDT-P4 and is
  not run separately.
- **ALT-P4 (negotiation baseline)**: no descriptors cross the boundary
  in either direction; the only channel is H's per-job price quote,
  which R uses as a coarse (sd 1.0 in log space) cost signal. A
  minimal stand-in for alternating-offers negotiation.
- **Collusion variants** (CEDT-P3, HYB-P3): the broker shares the
  pre-DP message stream with H's attacker (`gamma_attack = 1`);
  utility is unchanged, R-side leakage is scored on the raw stream.

## Results (posterior x100, redesigned metrics; wide x1 in parentheses)

| arm | P(win-win) | pw_rate | labels/nh vs DTDE | P(leak ok) |
| --- | ---: | ---: | ---: | ---: |
| CTCE-P0 (ceiling) | 0.00 (0.00) | 0.82 | 1.50 | 0.00 |
| DTDE-P4 (baseline) | — | — | 1.00 | 1.00 |
| CTDE-P2 | 0.00 (0.00) | 0.58 | 1.07 | 0.00 |
| CTDE-P3 (ε=2) | 0.00 (0.02) | 0.56 | 1.00 | 0.62 |
| CTDE-P4 | 0.00 (0.00) | 0.00 | 1.00 | 1.00 |
| CEDT-P2 | 0.00 (0.00) | 0.76 | 1.40 | 0.00 |
| CEDT-P3 (ε=2) | 0.51 (0.05) | 0.70 | 1.28 | 0.61 |
| **CEDT-P4** | **0.92 (0.16)** | 0.95 | 1.18 | 1.00 |
| HYB-P2 | 0.00 (0.00) | 0.76 | 1.40 | 0.00 |
| HYB-P3 (ε=2) | 0.51 (0.06) | 0.69 | 1.28 | 0.61 |
| ALT-P4 | 0.00 (0.02) | 0.60 | 1.00 | 1.00 |
| CEDT-P3 (ε=2) collude | 0.00 (0.00) | 0.70 | 1.28 | 0.00 |
| HYB-P3 (ε=2) collude | 0.00 (0.00) | 0.69 | 1.28 | 0.00 |

## Findings

1. **The hybrid-mix buys nothing over CEDT.** At every disclosure
   level HYB is statistically indistinguishable from the matching CEDT
   arm (P2: 1.40 vs 1.40 labels/nh; P3: 0.51 vs 0.51 win-win). Once
   the broker matches execution configs at run time, the shared
   surrogate is redundant — the information it would deliver to R
   (what execution will cost) is already priced into the broker match.
   The hybrid also inherits CEDT's leakage profile unchanged: the
   per-round proposal stream dominates the surrogate channel. So the
   arm inventory is complete AND the ordering is unchanged: CEDT-P4
   remains the minimal viable contract; there is no hybrid sweet spot
   between CTDE and CEDT in these worlds.
2. **ALT (negotiation-only) is leakage-clean but utility-flat.** The
   price-quote channel passes essentially all leakage limits (0.96 to
   1.00) — prices reveal little that the rank-extraction and hardware
   attackers can use at this coarseness — but it also moves no utility
   metric (labels/nh 1.00 at x100; pw_rate 0.60 exactly at threshold
   but the package fails on H's side). Negotiation without any
   execution-time coordination trades privacy for nothing here; it is
   dominated by CEDT-P4 on every axis.
3. **Collusion voids the P3 certificate entirely.** If the broker
   shares pre-DP messages with H, P(leak ok) drops from 0.61 to 0.00
   for both CEDT-P3 and HYB-P3 — the DP guarantee at the aggregation
   point is the ONLY thing separating P3 from P2, so a corrupted
   broker makes P3 exactly as unsafe as undisclosed-DP P2. P4 has no
   broker-visible descriptor stream to collude over (single class), so
   CEDT-P4's certificate is collusion-robust by construction — one
   more argument for it as the minimal contract. Contract text
   implication: P3-class contracts need broker attestation /
   trusted-execution assumptions that P4-class contracts simply do not.
4. Sanity: on the redesigned metrics CEDT-P4 grades 0.92 in this
   independent 300-world run — matching `../metric_redesign/`
   (selection set 0.920, fresh worlds 0.920).

## Caveats

HYB's surrogate-to-broker interaction is modeled at the information
level (both channels open, count-weighted surrogate); richer hybrid
designs (e.g. surrogate-warm-started broker menus) are not explored.
ALT is a one-channel stand-in, not a full alternating-offers protocol
with strategic pricing. Collusion is scored, not simulated as strategic
behavior (H does not change its decisions on colluded information).

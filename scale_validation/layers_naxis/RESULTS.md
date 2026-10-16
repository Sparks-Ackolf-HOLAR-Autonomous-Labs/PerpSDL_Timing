# Layers/N-axis measurement run — results (SLURM job 1919292, granite grn061)

Live companion to the simulated `../../scale_experiment_grid/` study: it
tests, with real QE 7.4 SCFs, the three assumptions the grid treats as
axioms. Submitted 2026-09-08 23:51; COMPLETED 2026-09-09
(≈22 min wall, exit 0). **17/17 SCFs converged, total real cost 0.16
node-hours.** Raw: `results/results.jsonl`, per-run outputs in
`results/raw_outputs/`, fits in `results/layers_fit.json`.

## 1. Layers vs in-plane supercells: one scale axis is (approximately) enough

At matched electron count, z-stacked layers cost slightly *less* than
in-plane supercells, but the exponents are close:

| material | p_e (layers) | p_e (in-plane) | p_e (mixed L2×s2) |
| --- | ---: | ---: | ---: |
| TiS₂-1T | 1.32 | 1.60 | 1.61 |
| MoSe₂-2H | 1.95 | 2.03 | 2.07 |

The grid study's single task-scale multiplier (electron count with a
steepening exponent) is a fair abstraction: the layers-vs-in-plane split
changes cost by well under the factor-of-10 cell spacing of the grid.
The exponents at ≤ 416 electrons (1.3–2.1) sit between the Stage-2
tiny-cell fit (1.20) and the 832-electron measurement (≈2.6), consistent
with the steepening onset located by `../RESULTS.md`.

## 2. Strained initial setups cost the same as their parent

±2% strained starts (the grid's "different initial setups" pool variants)
change wall time by −7% to +8% and SCF iterations by −6% to +4%, all
converged. The grid's assumption that setup variants inherit their
parent's cost is confirmed at the measured scale.

| variant | wall ratio | iter ratio |
| --- | ---: | ---: |
| TiS₂ −2% | 1.08 | 1.04 |
| TiS₂ +2% | 0.97 | 0.96 |
| MoSe₂ ±2% | 0.93 | 0.94 |

## 3. Cross-material spread at fixed size is modest

Max/min wall-time ratio across TiS₂-1T / MoSe₂-2H / WTe₂-2H is 1.5× at
the 1×1 cells and 1.8× at the 2×2 supercells — the same order as the
pilot-fitted config-quirk spread, not a dominant cost axis.

## Implication for the grid conclusions

None of the three measurements undermines the grid finding: the
renegotiated package's win-win band (30 materials, ×10–×300 task scale,
peak 0.957 at 30×2 setups, ×30–×100) survives with the measured
layer/in-plane split, setup-cost equality, and material spread. The
practical recipe for a real win-win-scale campaign remains 3×3 in-plane
supercells (or 2-layer stacks × 2×2, equivalently by electron count).

All interpretation limits of the parent study apply; these are cost
measurements, not science claims.

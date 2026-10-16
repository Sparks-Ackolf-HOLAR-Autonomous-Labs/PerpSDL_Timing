# 81-job F1 coupling pilot — MEASURED results (granite grn061, 2026-09-08)

Run on 2026-09-08 with the 20160-minute node time limit as the outer
cap and `MAX_NODE_HOURS=100` passed to the guarded
`submit.sh`. The `sparks-gpu-grn` partition was **empty at submission —
no guest jobs were preempted**. Everything in this file is a real CHPC
measurement, not a simulated unit.

## Execution record

- First submission (jobs 1914315–1914395) hit two staged-bundle bugs:
  three inputs referenced non-GBRV pseudo filenames, and
  `srun pw.x` launched N independent serial pw.x processes (no MPI/PMIx
  integration) with 32 OpenMP threads each. **Cancelled the whole batch**
  (5 early failures recorded), fixed the template
  (`mpirun -np $SLURM_NTASKS --bind-to none`, `OMP_NUM_THREADS=1`,
  GBRV filenames), resubmitted as jobs 1914400–1914481 (+`1914495`).
- **81/81 completed, 81/81 SCF-converged, 0 failures.**
- Total measured cost: **0.212 node-hours** (16-core recast-node
  convention) — the pre-Stage-2 estimate was 120–160 nh, another
  ~600× cost overestimate now corrected.
- Wall time range 2.2–8.6 s per job; GBRV pseudo hashes frozen in
  `pseudos_manifest.txt`.

## Fitted twin parameters (`pilot_fit.json` — the previously
unidentifiable ones)

| parameter | prior (base card) | measured | consequence |
| --- | --- | --- | --- |
| parallel-efficiency exponent s | 0.65 ± 0.10 | **0.425** | strong scaling saturates much earlier than assumed: doubling ranks buys only 2^0.43 ≈ 1.34× — multi-"node" configs waste more than the prior thought |
| config-quirk spread (log sd) | 0.18 | **0.061** | config quirks ~3× smaller: less for config disclosure to reveal AND less for coordination to exploit |
| repeat/contention noise (log sd) | burst-driven, up to ~0.5 | **0.076** | quiet, dedicated node; contention channel nearly silent |
| failure base rate | ~4.7% | **0/81** (95% UB 3.6%) | failure-avoidance value smaller than assumed |
| aggressive-mode effect | +25% speed, +risk | **−27% wall, 0 failures** | aggressive settings dominated conservative ones at F1 |
| memory | 30·(size)² GB model | max 3.1 GB/task | dead channel, re-confirmed under config variation |

Caveats: strong-scaling exponent measured on tiny F1 jobs (seconds), one
shared node (no inter-node network), dedicated allocation (no co-tenant
contention), 3 candidates. The exponent should be re-measured at the
win-win scale — the scale-validation job (../scale_validation/) covers
the size axis.

## Required ablation 13.2-1 (real data, first execution)

Grammar with cross-party feature products (candidate size × ranks/pools/
aggressive) vs additive-only grammar, leave-one-(candidate,config)-cell-
out CV on log wall time:

- additive LOO-RMSE **0.124**, cross-party LOO-RMSE 0.134 —
  **removing cross-party operators IMPROVES held-out prediction by 8%.**

At the measured task scale there is **no detectable cross-party cost
coupling**: the additive grammar suffices, consistent with the dead
memory channel (the twin's coupling entered through candidate-specific
memory demand). This weakens the empirical case for the fresh-coupling
regime of Proposition 15.10 at ×1 scale — the CEDT-over-CTDE dominance
in the simulations rests on couplings that the real light-task system
does not exhibit. Whether coupling emerges at ×10–×100 scale is exactly
what the scale-validation job measures.

## Post-pilot posterior re-grade

`posterior_regrade.py` re-grades the main grid under the pilot-informed
card (s = 0.425 ± 0.05, quirk 0.061, low burst, low failure) at the
recommended ×10/×100/×300 operating scales, under both the frozen
metrics and the renegotiated execution-layer package — results in
`posterior_regrade.json`.

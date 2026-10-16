# Live comparison No. 2 — DRAFT preregistration (v2 design, packing-based)

Status: **AUTHORIZED AND FROZEN.** The authors authorized comparison 2
on 2026-09-11, after metrics (PW60 + 1.05× labels/nh) and the 520 pc-nh
cap were frozen the same day. This file is now the preregistration of record;
`analyze_live2.py` (the grading) and the implementation
(`build_live2_inputs.py`, `live2_campaign.py`) were committed before
submission and may not change after data exist.

> **2026-09-11 implementation freeze (pre-submission).** Final
> implementation details, fixed before the jobs were submitted:
>
> 1. **Physics:** f1 coarse SCF 40/320 Ry conv 1e-6; f2 production SCF
>    45/360 conv 1e-8; f3 NSCF 45/360, nbnd = 1.10·nocc + 16. All
>    stages `K_POINTS automatic 1 1 1` (NOT the Γ-trick: the measured
>    probe anchor — MoSe2_2H 8×8, 11,767 s / 112 GB — is this
>    configuration, and halved Γ-trick RAM would erase the reservation
>    surface the experiment prices). Scope amendment: f2 density is
>    the 8×8-folded Γ point (coarser than the 1×1 campaign's 12×12);
>    identical in both arms, so label definitions stay paired.
> 2. **Reservation model (the disclosure object):** per-candidate RAM
>    estimates anchored to the two measured probe points with
>    electrons^1.55 phase scaling and the measured Te/Se/S factors
>    (`inputs/manifest2.json`: 75–138 GB, median 98.9, 14 high-bit).
>    DTDE reserves 1.10 × class max (152 GB at f2) → 2 co-resident
>    streams max; CEDT-bit reserves 1.10 × bit-half max (109 GB for
>    bit 0) → 3 streams when low-bit jobs are available. Packing
>    budget 342 GB (0.9 × node); 16 ranks/job, npool 1, both arms.
> 3. **Windows:** A = seeds 0–7, cap 280 billed pc-nh; B = seeds 8–14
>    + the masking replay, cap 240; B `--dependency=afterany:A`; each
>    `--time=320 h`. Total cap 520 (frozen).
> 4. **Live timing-masking price (second task of the study design):**
>    CEDT campaigns for seeds 0–2 are re-run in window B with
>    quant = 0 on identical seeds/orders; the paired masked-vs-
>    unmasked billed-cost and makespan deltas are the *measured* price
>    of the 600-s clause at 8×8 scale. Known confound (accepted):
>    replay runs days after the masked originals; contention on the
>    dedicated node was measured at 2.4–3.9%, well under the expected
>    masking signal (~5–10%).
> 5. **Expected run time (estimate, from measured walls ×1.74
>    rank-scaling):** window A ≈ 9 days, window B ≈ 9.5 days,
>    execution total ≈ 18–19 days; completion ≈ 2026-09-29 to
>    2026-10-01 if the node stays free of owner jobs; hard ceiling
>    320 h per window (worst case ≈ 2026-10-08). Billed estimate
>    320–450 pc-nh against the 520 cap.

> **2026-09-11 post-cofit amendments (see
> `../cofit_probe/results/RESULTS.md`).** Probe `1940907`: the
> registered 19% (16–23%) packing-saving prediction was **falsified**
> (measured −1.8%). Diagnosis: the rank-scaling prior was wrong —
> measured wall(16)/wall(32) = 1.72–1.77× (s = 0.79–0.82, near-linear
> intra-node scaling), not the 1.27–1.41× assumed; contention is
> 2.4–3.9%, *below* its prior. With only s and c refit, the scheduler
> model reproduces the probe to 0.2%. Consequences, folded in below:
>
> 1. **Gate verdict:** no pair-packing makespan gain exists at 6×6
>    (memory never binds there) — per the gate's decision rule the
>    H-gain must come from memory-reservation (TRES) billing with up
>    to 4 co-resident streams at 8×8, which is this design. The 8×8
>    mechanism is reservation-based, not rank-scaling-based, so the
>    falsified prior does not touch it: regraded on measured s and c,
>    **P(H ≥ 1.05×) = 1.00** (median 1.145), P(PW60) = 0.68,
>    P(joint) = 0.68.
> 2. **Budget re-estimate:** the corrected s makes every 16-rank job
>    1.74× the 32-rank wall (not 1.34×), raising budgets ≈30%. The
>    8-calls × 15-pairs 8×8 design is now **median 432 per-core nh,
>    80% interval 376–512** (was 343 [301–402]).
> 3. **Sign-off by the authors recorded (2026-09-11):**
>    metrics = PW60 + 1.05× labels/nh (as frozen in this file);
>    `max_per_core_node_hours: 520` (the 90th-percentile budget,
>    rounded). `authorized` remains open.

> **2026-09-11 pre-study amendments (see `prestudy/RESULTS.md`).** The
> measurement-calibrated pre-study found that the design below is a
> **structural null at 6×6**: 16-rank streams are core-limited there and
> memory never binds, so both arms pack identically and all charges are
> equal by construction. Proposed amendments, pending sign-off by the authors:
>
> 1. **Task scale 6×6 → 8×8** (F2/F3 stages; ≈3,300/1,650 electrons for
>    2H/1T), where DTDE's worst-case reservation is billed at 0.44 of
>    the node vs CEDT-bit's 0.34 — predicted H gain 1.13× (80 % interval
>    1.06–1.16), P(H ≥ 1.05×) = 0.95.
> 2. **Billing = TRES max(ranks/64, reserved GB/380)** — under plain
>    per-core billing reservations cost nothing and no scale separates
>    the arms. This replaces the bare "per-core" accounting below.
> 3. **8 QE calls/campaign × 15 pairs** (power is flat in seeds/calls;
>    world-level luck limits PW60 at ≈ 0.64) — median budget **343
>    per-core nh, 80 % interval 301–402**, replacing the 250–450 sketch.
> 4. Governance option: grade **H as primary** (predicted pass 0.95),
>    PW60 secondary — the packing mechanism is H-side; PW60-primary is a
>    ~1-in-3 failure by luck even if the mechanism is real.
> 5. Leakage: the population-median memory bit is nearly a **phase bit**
>    at this scale; the 0.10 composition/phase advantage limit must be
>    graded on the bit channel explicitly.
> 6. Gate reinterpretation: the cofit probe's sequential-32-rank
>    baseline is *not* the DTDE counterfactual (DTDE can pack 4×16 at
>    6×6 without disclosure); the probe validates co-scheduling physics
>    and the model's contention/rank-scaling inputs. Registered
>    prediction: 19 % node-time saving, 80 % interval 16–23 %.

## Why v2 differs from the first No. 2 sketch

Probe `1928420` corrected the mechanism
(`../memory_band_probe/results/RESULTS.md`): below the memory wall the
optimal npool is class-determined (k-grid), and DTDE's conservative
lean config is accidentally optimal — an npool-right-sizing comparison
would be a null by construction. The measured per-candidate surface is
the 23–32% iso-electron RAM spread, which prices **memory-aware
co-residency**: whether two jobs can safely share the node. So v2 pits
packing policies, not config policies.

## Design

- **Task:** 29 CC0 MX2 candidates at 6×6 supercells (27/54 atoms,
  ≈900–1,900 electrons), F1→F3 ladder with density-matched k-grids
  (F1 Γ-only, F2 2×2×1, F3 3×3×1 — folding the 1×1 campaign's 6/12/18
  densities). Both arms run identical physics; npool = min(n_k, 2) for
  both arms (class rule, fixed, per probe `1928420`).
- **Arms (differ only in packing policy):**
  - **DTDE:** H sees calculation class only and must provision each
    job's memory at the class worst case (the max over the candidate
    population, ≈53 GB/job lean at 6×6 → at most K_dtde co-resident
    jobs per 380 GB node, K set by the worst case). In practice this
    serializes or under-packs the node; idle cores are still charged
    to nobody — that is the DTDE waste.
  - **CEDT-P4 + memory bit:** the broker receives one preregistered
    bit per job (RAM class: above/below the population median for its
    class — the Theorem-3 threshold statistic) and packs co-resident
    sets that fit in 380 GB with a 15% safety margin.
- **Accounting: per-core.** Each arm is charged core-seconds actually
  allocated to its jobs (prerequisite No. 1 from `../billing_regrade/`).
- **Timing masking active:** 600-s quantized returns (prerequisite
  No. 2 from `../timing_masking/`); its utility cost is a preregistered
  *secondary* outcome; wire logs recorded and attacked as in
  `../measured_attacks/`.
- **Pairing and power:** n = 20 paired seeds (10 gave a powerless sign
  test in comparison No. 1), 12 QE calls per campaign, identical
  candidate orders within a pair.
- **Primary metrics (frozen from `../metric_redesign/`):**
  - R: PW60 — CEDT beats DTDE on per-core node-hours to first
    qualifier in ≥ 60% of the 20 pairs (sign test, one-sided);
  - H: valid F2+ labels per per-core node-hour ≥ 1.05× DTDE;
  - leakage: the six limits, evaluated by the executed attacker suite
    on the quantized wire log.
- **Budget estimate:** from measured 6×6 walls (1.2–4.9 ks at 32
  ranks), ≈ 250–450 per-core node-hours total — two sequential grn061
  windows (each within the 20,160-min node limit), kingspeak general
  as overflow only if granite is occupied.

## Gate (must pass before submission)

From `../cofit_probe/` (job `1940907`): concurrent 16+16 execution of a
matched-length pair must beat the sequential 32-rank baseline on node
time by more than its measured contention cost. If it does not, the
packing gain needs > 2 co-resident streams and this design returns to
draft for a queue-depth revision.

## Fields set by the authors (REQUIRED)

```yaml
comparison2:
  authorized: true                # authorized by the authors 2026-09-11
  max_per_core_node_hours: 520    # frozen 2026-09-11 by the authors;
                                  # 90th-pct of the 432 [376-512] pc-nh
                                  # post-cofit budget; driver refuses beyond
  metrics_signed_off: true        # PW60 + 1.05x labels/nh, frozen 2026-09-11
                                  # by the authors
  design: 8x8_supercells_8calls_x_15pairs   # post-cofit cheapest adequate
  scheduler_priors: s 0.76-0.84, c 0.02-0.05  # measured, probe 1940907
```

## Run record

- **Attempt 1 — VOID.** Jobs `1948457` (window A) / `1948458` (window
  B), submitted 2026-09-11. Window A ended `OUT_OF_MEMORY` (153
  oom_kill events): the sbatch requested no memory, so SLURM granted
  the 125 GB partition default while the driver packed streams
  assuming the node's 380 GB. Nearly all QE calls were OOM-killed; no
  valid data. Window B, running under the same allocation, was
  cancelled 2026-09-14.
  **Protocol deviation, infrastructure-only:** no metric, input, seed,
  cap, or analyzer change; graded data from attempt 1 is discarded.
- **Attempt 2 — ACTIVE.** Jobs `1973175` (window A, seeds 0–7, cap
  280 pc-nh) / `1973176` (window B, seeds 8–14 + masked-replay seeds
  0–2, cap 240 pc-nh, `afterany` dependency), submitted 2026-09-14
  with the one-line fix `#SBATCH --mem=0` (whole-node memory) and
  otherwise identical staging. Window A verified RUNNING on grn061
  with `AllocMem=380000M`.
- **F3 save-dir bug (found 2026-09-22, mid-run).** The attempt-2
  driver deleted each candidate's QE save dir after every call, so all
  F3 calls failed and PW60 is ungradeable from as-run data. H-side
  metrics, masking replay, and wire logs are unaffected. The fix is in
  `live2_campaign.py` (save dir removed only when a candidate's ladder ends).
- **Amendment D-2026-09-22-A — F3 repair pass** (authorized by the authors
  2026-09-22): one fixed-driver F2+F3 per unique
  F3-attempted candidate on grn061 (`f3_repair/`, submitted
  `afterany` window B, guard `MPT_REPAIR_CAP=80` pc-nh inside the
  frozen 520 total; submitted 2026-09-22 as SLURM job `2048364`,
  `afterany:1973176`); per-campaign counterfactual reconstruction by
  `f3_repair/repair_regrade.py`. **This is the primary R-side grade
  for attempt 2.** Approximations recorded in
  `f3_repair/REPAIR_AND_FALLBACK_PLAN.md`.
- **Deviation D-2026-09-22-B — fallback regrade, kept as an
  observable** (same decision): folded 1×1 gaps at F2
  completion (`fallback_regrade/`). Reported alongside the repair
  grade, never in place of it; the diff between the two gradings is
  itself an outcome (`f3_repair/deviation_comparison.py`, registered
  directional prediction P-2026-09-22: repair PW60 ≥ fallback PW60).
  Mid-run fallback result on 9 complete pairs: PW60 = 0.111, FAIL.

## Outcome record, attempt 2 (2026-09-30)

Window B `1973176` and the F3 repair pass `2048364` COMPLETED (exit 0).
Grading run exactly as frozen; full write-up in `final/RESULTS.md`.

- H (labels per pc-nh >= 1.05x): **pass**, 1.133 as run, 1.207 with repaired F3 costs; failure and memory-kill riders pass.
- R (PW60, primary repair grade D-2026-09-22-A): **fail**, 5/15 = 0.33, sign p = 0.94. Fallback grade D-2026-09-22-B: 5/15, fail. Prediction P-2026-09-22 holds (tie); 2 verdict flips, 3 identity changes.
- Leakage on the quantized wire log: **fail**, identity accuracy 0.58 (limit 0.084), membership AUC 0.93 (limit 0.60).
- Masking price (seeds 0 to 2 replay): +3.0%, +7.2%, +2.7% billed.
- Preregistered win-win: **not confirmed**. No metric was changed after the data was seen.
- Spend: about 264 of the 520 pc-nh cap, including the void attempt 1.

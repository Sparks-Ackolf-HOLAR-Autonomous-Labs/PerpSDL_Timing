# F3 repair pass + fallback regrade (2026-09-22)

Decision of 2026-09-22: run an F3 repair pass with the fixed driver, and
also build the low-cost fallback regrade, because the protocol deviation
itself is an observable whose effect on the mechanism should be measured.

Both grading paths are therefore built, and their disagreement is
itself a registered observable. Everything here was frozen **before any
repair-pass data exists**.

## Background

Attempt 2 of live comparison No. 2 (jobs 1973175/1973176) carries a
driver bug (fixed 2026-09-22 in `../live2_campaign.py`): the QE save
dir was deleted after every call, so all F3 (NSCF/bands) calls failed
and no gap was ever measured. H-side metrics are unaffected; the R-side
metric PW60 (billed pc-nh to first qualifier) is ungradeable as-run.

## Path A — F3 repair pass (amendment D-2026-09-22-A, primary R verdict)

**Deduplication.** The gap and F3 wall time are candidate properties at
the fixed execution config (16 ranks, npool 1) — identical across arms
and seeds. So the repair runs **one F2+F3 per unique candidate** whose
ladder attempted an F3 anywhere in the attempt-2 transcript (17 unique
through window B campaign 3; the driver re-derives the union from the
full `results/campaigns.jsonl` at start time, so window B's remaining
campaigns are covered automatically). This collapses the earlier
30–40-ladder estimate (~100–150 pc-nh) to ≈ 25–45 pc-nh, which fits
inside the frozen 520 pc-nh cap with window B's worst case — **no cap
raise needed**.

**Execution** (`repair_driver.py` + `repair.sbatch`): granite grn061,
submitted `--dependency=afterany:1973176` so it starts only when
window B is done; ≤ 2 concurrent 16-rank streams gated by summed
worst-case reservations ≤ 342 GB (2 heaviest = 320 GB, always safe);
`--mem=0` per the void-run lesson; guard `MPT_REPAIR_CAP=80` pc-nh;
`--time=144:00:00` hard stop. Wall estimate ≈ 2–4 days.

**Reconstruction** (`repair_regrade.py`): walk each original campaign
transcript in order; substitute every systematically-failed F3 with the
repaired gap, replacing its ~10-s billing with the counterfactual F3
cost `(f3_wall + hold)/3600 × frac(original record's own res_gb)`,
hold = 300 s (expected 600-s-quantum masking hold) for masked CEDT
campaigns, 0 otherwise. First qualifier = first substituted F3 with a
gap in [1.0, 2.0] eV, at corrected cumulative billed. PW60 pair rule
verbatim from the frozen `analyze_live2.py`.

Recorded approximations (identical for both arms, so unbiased between
them): expected rather than exact masking hold (< 0.04 pc-nh per F3);
launch order taken from the real transcript although multi-hour F3s
could in principle have reordered later launches within the 8-call
budget.

## Path B — cheap fallback regrade (deviation D-2026-09-22-B, observed)

`../fallback_regrade/fallback_regrade.py`: qualification at **F2
completion** using the candidate's **folded 1×1 gap**
(`manifest2.json gap_1x1_ev`), at as-run billing. Systematic
differences vs Path A, each an observable:

1. cheaper `billed_first_qual` by construction (no F3 cost/wait);
2. folded 1×1 gap instead of the measured 8×8 F3 gap (window flips
   possible);
3. 13 of 29 candidates have no recorded 1×1 gap and can never qualify
   under the fallback;
4. the F3 gate is skipped — the fallback can crown a qualifier whose
   ladder never reached F3 (flagged per campaign in the output).

## Registered prediction P-2026-09-22 (frozen before repair data)

**Repair-graded PW60 ≥ fallback-graded PW60.** Mechanism: the fallback
prices CEDT's masking holds into every pre-qualification job but
excludes the F3 stage entirely — and F3 is where the reservation
differential is largest (DTDE reserves 159.7 GB → billed fraction
0.42/wall-h; CEDT bit-0 reserves ≈ 114 GB → 0.30). Real F3 costs
therefore penalize DTDE more. The mid-run fallback deltas
(0.05–0.36 pc-nh in DTDE's favor at F2 time) are the same order as the
expected per-F3 differential, so pair flips are plausible but not
certain. Graded by `deviation_comparison.py` when repair data lands.

## Mid-run fallback result (windows A + B campaign 3; 9 complete pairs)

**Fallback PW60 = 1/9 = 0.111 — FAIL** (sign test p = 0.998). In all
4 both-qualifier pairs both arms crown the *same* candidate and DTDE
reaches its F2 a hair cheaper (CEDT's masking holds are priced; its F3
savings are excluded). 4 of 9 pairs have no gradeable qualifier at all
under the fallback. Details:
`../fallback_regrade/results_midrun/fallback_graded.json`. This number
is informal until window B completes; the final fallback grade re-runs
on the full transcript.

## Grading precedence (frozen)

The **repair-based grade is the primary R-side verdict** for attempt 2
(it measures the preregistered quantity: an 8×8 F3 gap, at F3
completion). The fallback grade is reported alongside as deviation
D-2026-09-22-B, and `deviation_comparison.py` reports the differences
(prediction P-2026-09-22, verdict flips, identity changes, per-candidate
gap deltas, window flips). Neither grade may be dropped after the
numbers are seen.

## Submission record

Submitted 2026-09-22: **SLURM job `2048364`**,
`--dependency=afterany:1973176`, verified PENDING (Dependency) with
window B still RUNNING (1 d 06 h elapsed, billed 18.6 pc-nh at last
campaign write). Expected start ≈ when window B ends (~Sept 28),
repair wall ≈ 2–4 days → repair gaps ≈ Sept 30 – Oct 2, then
`repair_regrade.py` runs, followed by the final
`fallback_regrade.py` on the full transcript, `deviation_comparison.py`
and the frozen `analyze_live2.py`.

## Code-path validation

The full chain (repair_regrade → deviation_comparison) was smoke-tested
with clearly-synthetic stand-in gaps (folded 1×1 ± noise, /tmp only,
not committed); no synthetic number is a result.

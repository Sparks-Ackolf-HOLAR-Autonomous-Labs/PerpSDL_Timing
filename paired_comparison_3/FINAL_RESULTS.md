# Comparisons No. 3 and No. 3b: final grade (2026-10-14)

All 60 No. 3 campaigns (DTDE, CEDT_P4, MIX50, CTDE_P2 x 15 paired seeds), all
30 No. 3b campaigns (DTDE, CEDT_P4 x 15, single-layer 2H cells), the 12
site-bridge copies and the OOM repair job were collected on 2026-10-14
(`collected_2026-10-14/`, `site_bridge_2026-10-14/`, `oom_repair_2026-10-14/`,
`../paired_comparison_3b/collected_2026-10-14/`). Grading scripts:
`grade_both_lists.py` (preregistered rule, writes `graded_both_lists.json`),
`../paired_comparison_3b/grade_3b.py`, and `final_grade_2026-10-14.py` (same rule,
adds the same-processor subset and the first-qualifier list; writes
`final_grade_2026-10-14.json`). Timing attack: `TIMING_ATTACK_RESULTS.md`.

All runs were on free guest partitions (granite-guest, then notchpeak-guest
after the 9 Oct move), so a pair's two campaigns often ran on different
processor models (`pair_sites.json`). The preregistered grade uses all 15
pairs; the same-processor subset is a secondary reading.

## Computing-centre side (F2 labels per billed per-core node-hour, vs DTDE)

| comparison | arm | all 15 pairs | same-processor pairs (n) |
|---|---|---:|---:|
| No. 3 | CEDT_P4 (one memory bit, 25 % proportional mask) | **1.069** | 1.102 (10) |
| No. 3 | MIX50 (half the jobs routed) | 0.959 | 1.167 (3) |
| No. 3 | CTDE_P2 (shared logbook, no broker) | 0.929 | 0.953 (6) |
| No. 3b | CEDT_P4 (single-layer 2H) | 0.905 | 0.978 (7) |

## Research side (pairs won of 15, as-run list; PW60 needs 9)

| comparison | arm | as run | single-layer list | bilayer AA' list |
|---|---|---:|---:|---:|
| No. 3 | CEDT_P4 | 6 (5 both none) | 5 | 4 |
| No. 3 | MIX50 | 3 | 3 | 2 |
| No. 3 | CTDE_P2 | 2 | 2 | 2 |
| No. 3b | CEDT_P4 | 4 (2 both none) | 5 | 5 |

Every first qualifier, in every arm of both comparisons, is on the corrected
single-layer list (HfS2-1T, HfS2-2H, MoS2-2H, MoSe2-2H, MoTe2-2H, WSe2-2H,
ZrS2-1T).

## Registered predictions

| id | prediction | result | verdict |
|---|---|---|---|
| P-2026-09-30 (a) | CEDT_P4 with the proportional mask gains below 1.05 | 1.069 | fail |
| P-2026-09-30 (b) | CEDT_P4 PW60 at or below 8/15 | 6/15 | pass |
| P-2026-10-01 item 1 | gain order CTDE_P2 > MIX50 >= CEDT_P4, all below 1.05 | CEDT_P4 1.069 > MIX50 0.959 > CTDE_P2 0.929 | fail |
| P-2026-10-01 item 2 | CTDE_P2 wins at least as many research pairs as CEDT_P4 | 2 vs 6 | fail |
| P3b-1 | No. 3b CEDT_P4 ratio at least 1.05 | 0.905 | fail |
| P3b-2 | No. 3b ratio within 0.10 of No. 3 | 0.905 vs 1.069 (0.164) | fail |
| P3b-3 | PW60 fails in No. 3b | 4/15 | pass |
| P3b-4 | every first qualifier on the corrected single-layer list | yes | pass |

Timing items (P-2026-09-30 (c), P-2026-10-01 item 3, T1 to T4): see
`TIMING_ATTACK_RESULTS.md`.

## Reading

1. **The memory bit repeats its computing-centre gain on other hardware when
   the bit separates layer count (No. 3), and loses it when it separates
   chemistry (No. 3b).** In No. 3 the bit splits the 384-atom two-layer 2H
   cells from the 192-atom 1T cells, a reservation gap of about 1.6x, and the
   broker gains 7 % on all pairs and 10 % on same-processor pairs, in the
   range of comparison No. 2 (1.133) on the owned node. In No. 3b every cell
   has 192 atoms and the bit only separates tellurides and heavier selenides
   from the rest; the RAM estimates span 75 to 130 GB, so the two reservation
   levels are close and the extra packed stream rarely fits. The reservation
   model predicted a billed-fraction ratio of 1.18 for No. 3b; it overstated how often a fourth
   stream fits. The prediction failed and is reported as failed.
2. **The replay underestimated the proportional mask's arm.** The fast-path
   replay put CEDT_P4 with the 25 % mask at 1.01; live it reached 1.069, so
   the held time of the proportional mask cost less than the replay assumed.
3. **Coordination without a broker does not pay.** The shared logbook arm
   (CTDE_P2) is below no sharing on both sides (0.929, 2 wins), and routing
   only half of the jobs (MIX50) loses the packing gain on all pairs. This is
   the live counterpart of the simulated result that the execution axis, not
   the training axis, carries the value, and of the shared-station result
   that splitting work between two routings loses the batch.
4. **The research side fails everywhere**, as in No. 2: both arms explore the
   same compounds in the same order, and the first qualifier is set by that
   order, not by the disclosure.
5. **Mixed hardware is the main threat to validity.** Five of 15 CEDT_P4 pairs
   in No. 3 and 8 of 15 in No. 3b ran on different processor models; on
   same-processor pairs every arm's ratio rises (CEDT_P4 1.102, No. 3b
   0.978). A preregistered comparison on guest hardware needs pairs pinned to
   one processor model.

# Comparison No. 3b: single-layer companion to No. 3 (5 Oct 2026)

Decision of 5 Oct 2026 ("do both"), read as both answers to the two
open No. 3 questions:

1. **Grading list:** No. 3 is graded on the as-run in-campaign gap test
   (primary, as preregistered) and on the corrected single-layer list
   beside it, with the D3 bilayer lists as secondary readings
   (`../paired_comparison_3/grade_both_lists.py`).
2. **Inputs:** the 47 pending No. 3 campaigns keep the first-pass 8x8
   inputs, so all No. 3 pairs stay comparable, **and** a second campaign
   set, No. 3b, runs the same design on single layers.

## What differs from No. 3

| | No. 3 | No. 3b |
| --- | --- | --- |
| 1T cells | 8x8 single layer, 192 atoms | same inputs |
| 2H cells | 8x8 two-layer cell at PBE spacing, 384 atoms | 8x8 single layer, 192 atoms, c = 20 A |
| pool | 29 (HfSe2-2H out) | 29 (TiS2-2H out, HfSe2-2H in) |
| what the disclosed memory bit separates | layer count (all 2H vs most 1T) | chemistry: the 5 tellurides of 1T, plus 2H Te, MoSe2, WSe2 (12 of 29) |
| RAM estimate range | 75 to 138 GB | 75 to 130 GB |

Everything else is identical: driver `../paired_comparison_2/live2_campaign.py`
with `qe_retry.py`, arms DTDE and CEDT_P4, 15 paired seeds, 16 calls per
campaign, proportional timing mask 25 %, 25 pc-nh per campaign, free
granite-guest partition, `--constraint=gen`, 372000M per job. Separate
scratch tree `mpt_live3b`.

## Registered prediction P-2026-10-05 (written before any No. 3b job ran)

From the reservation model (packing streams and billed node fraction per
job, not a campaign simulation): No. 3 gives DTDE 2 streams vs CEDT_P4 3
streams, No. 3b gives DTDE 2 vs CEDT_P4 up to 4; billed fraction ratio
about 1.17 for No. 3 and 1.18 for No. 3b.

- **P3b-1 (computing side).** Pooled F2 labels per billed pc-nh,
  CEDT_P4 / DTDE >= 1.05 in No. 3b.
- **P3b-2 (same mechanism).** The No. 3b ratio is within 0.10 of the
  No. 3 ratio on the same seeds (the bit carries chemistry instead of
  layer count, but the reservation gap is about the same).
- **P3b-3 (research side).** PW60 fails in No. 3b as in No. 3 (fewer than
  9 of 15 pair wins), because the first qualifier depends mostly on the
  candidate order, which both arms share.
- **P3b-4 (labels).** Every first qualifier in No. 3b is on the corrected
  single-layer list (the 9 compounds, or HfSe2-2H if its 8x8 single-layer
  gap reaches 1.0 eV; predicted not to).

Any failed prediction is reported as failed.

## Submission record

Submitted 5 Oct 2026 about 05:45 UTC via `stage_and_submit3b.sh` (SSH login
to notchpeak, `sbatch -M granite`).
30 jobs, ids in `JOBIDS.txt` (2119223 to 2119273). All PENDING behind the
granite maintenance reservation that starts 5 Oct 07:00 UTC, together
with the 47 No. 3 campaigns. Results land in scratch
`mpt_live3b/results/<ARM>_s<seed>/`.

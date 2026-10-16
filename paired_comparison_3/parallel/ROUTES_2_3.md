# Comparison No. 3, routes 2 and 3 (2026-09-30)

Decision (2026-09-30 21:59 UTC): try route 2 (all pairs live in
parallel on free granite-guest nodes) and route 3 (measure the missing
run times, replay, then check live) from `../../fast_path/FAST_PATH.md`.

## What was submitted (granite-guest, free, preemptible)

All jobs are pinned to `--constraint=gen`, the AMD node family of
grn061, so run times stay comparable with the comparison No. 2 records.

| route | SLURM job | content |
| --- | --- | --- |
| 3, step 1 | array `2089126` (tasks 0-13) | F1-F3 ladders at 16 ranks for the 11 compounds No. 2 never finished (24 missing entries) and 3 repeat ladders (MoS2-1T, ZrS2-1T, WS2-1T) to compare guest nodes with grn061. `../../fast_path/library_ladder.py` |
| 2 | `2089132`-`2089161` | option A: 15 seeds x {DTDE, CEDT-P4}, one campaign per job, 16 calls, 64 ranks and 372000M per job (the 64-core, 380-GB node the driver assumes), proportional timing mask (run time rounded up to 25% of its expected value). `live3_guest.sbatch` |

Settings not fixed by the preregistration:
- Structures: the comparison No. 2 inputs (2H entries are still the
  PBE bilayers without D3). The stacking check (job 2088961) was still
  running; waiting would have delayed both routes by several hours, and
  keeping the No. 2 structures keeps the replay library consistent.
- Timing mask: the proportional clause listed for option A.
- Budget: the free partition carries no allocation charge. Guards per
  job: campaign cap 25 per-core node-hours, job cap 30. Replay estimate
  for all 30 campaigns: about 610 per-core node-hours (309 no sharing + 301 broker) in the driver's
  accounting units.

Driver changes (`../../paired_comparison_2/live2_campaign.py`, defaults
unchanged for No. 2): single-campaign mode, call budget and results
directory from the environment, proportional mask, host and processor
model on every record, restart after a preemption discards the lost
attempt's wire rows (kept in `wire_log.lost.jsonl`).

## Route 3, step 2: replay of arm sets and masks (provisional)

`../../fast_path/option_replay.py` replays the No. 2 driver rules with
recorded run times for five arrangements and three mask clauses,
15 seeds x 16 calls. 24 library entries are still filled from stage
ratios or the size law, so these numbers are provisional until the
library array lands. Output: `../../fast_path/results/option_replay.json`.

| arrangement, mask | computing-centre gain (labels per pc-nh vs DTDE) | research-group PW60 | compound identified from timing |
| --- | ---: | ---: | ---: |
| CTDE (shared training records), any mask | 1.00 | 0/15 (ties) | n/a |
| half delegation, none | 1.06 | 6/15 | 0.92 |
| broker (CEDT-P4), none | 1.16 | 10/15, pass | 0.92 |
| full sharing (CTCE), none | 1.35 | 9/15, pass | n/a |
| broker, fixed 600 s | 1.08 | 8/15 | 0.49 |
| broker, proportional 25% | 1.01 | 7/15 | 0.26 |
| half delegation, proportional 25% | 1.02 | 4/15 | 0.26 |

Limits: identity accuracy about 0.087, gain margin 1.05, PW60 needs 9/15.

Reading:
- With 16 calls instead of 8, the broker passes both gain tests when
  completions are not masked (at 8 calls only 6/15, with 8 pairs where
  neither arm confirmed a qualifier). The call budget, not the
  arrangement, set the No. 2 research-group score.
- CTDE gives no gain in this mechanism: sharing past records does not
  tell the centre how much memory the next job needs, so it still
  reserves for the worst case. This matches the flat training axis of
  the centralization surface.
- Every mask tested trades the gain away before it closes the timing
  leak. The proportional clause cuts identification from 0.92 to 0.26
  and removes almost all of the gain (1.16 to 1.01); no tested clause
  reaches 0.087.
- Replay check against No. 2 (8 calls, fixed 600 s): gain 1.26 replayed
  vs 1.21 measured, PW60 3/15 vs 5/15, identification 0.48 vs 0.58. The
  replay overstates the gain by about 5% and the attacker here is
  weaker than the one run on the No. 2 wire log.

## Registered prediction for route 2 (before any route 2 data)

P-2026-09-30: the live option A campaigns (broker with the proportional
mask) give a computing-centre gain below the 1.05 margin (replayed
1.01), PW60 at or below 8/15 (replayed 7/15), and timing identification
between 0.15 and 0.40 (replayed 0.26).

## Remaining steps for this route

Collect `2089126` into `../../fast_path/results_lib3/`, rerun
`option_replay.py` (status becomes final when no entry is filled),
collect the 30 campaign directories under `mpt_live3/results/`, grade
them against P-2026-09-30, and compare route 2 with route 3.

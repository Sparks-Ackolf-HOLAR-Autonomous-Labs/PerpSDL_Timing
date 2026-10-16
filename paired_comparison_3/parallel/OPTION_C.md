# Comparison No. 3, option C: four arrangements on 15 shared seeds (2026-10-01)

Design choice (2026-09-30 22:14 UTC): option C, which
contains options A and B. All four arms run 15 paired seeds, 16 calls
per campaign, one campaign per job on the free `granite-guest`
partition (`--constraint=gen`, the grn061 node family), with the same
8x8 inputs, physics and execution config (16 ranks, npool 1). They
differ only in what the computing centre knows when it reserves memory
and in what crosses the wire.

| arm | what the centre uses to reserve memory | timing mask | jobs |
| --- | --- | --- | --- |
| DTDE | calculation class only (worst case) | none (no wire) | 2089132-2089161 (even ids) |
| CEDT_P4 | one memory bit per job, via the broker | proportional, 25% | 2089132-2089161 (odd ids) |
| MIX50 | broker for a random half of the jobs, worst case for the rest | proportional, 25%, routed half only | 2089709-2089739 (MIX50 rows) |
| CTDE_P2 | shared logbook of measured job RAM by size bin and stage | none | 2089709-2089739 (CTDE_P2 rows) |

Job-to-arm map: `.live3_jobids` (option A) and `.live3c_jobids` (B and C).

## Definitions that were open before this run

- **MIX50.** The routing draw is the one in `fast_path/option_replay.py`:
  `Random(f"{seed}:{compound}:{stage}") < 0.5`, so the live and replayed
  campaigns route the same jobs.
- **CTDE_P2.** Centralized training means the centre holds a logbook of
  past jobs; decentralized execution means it still decides each
  reservation alone, without a per-job broker message. The logbook is
  keyed by the P2 size bin (small: 1T 8x8 cells, at most 2,000 electrons;
  large: 2H cells) and stage. It starts from comparison No. 2
  (`parallel/ctde_logbook_seed.json`, built by `build_ctde_logbook.py`:
  job RAM = 16 x peak rank RSS, an upper bound) and learns every clean
  job of the campaign. Reservation = 1.10 x the largest RAM recorded for
  the bin and stage, never above the DTDE worst case. The shared records
  carry true run times and the size bin, so the attacker sees all jobs.
  In practice the logbook lowers reservations only for 1T jobs
  (F1 115 GB, F2 136 GB, against 129 and 152 GB worst case); 2H jobs
  already reach the worst case.
- The earlier replay arm "CTDE" (logbook with no effect on reservations,
  identical to DTDE) is kept in the replay for reference only.

## Registered prediction P-2026-10-01 (before any option-C data)

From `fast_path/option_replay.py` (provisional library, 24 entries still
estimated; output `fast_path/results/option_replay_C.json`), relative to
DTDE on the same seeds:

| arm (live mask) | centre gain (pass at 1.05) | research wins of 15 (pass at 9) | compound identified from timing (limit 0.087) |
| --- | ---: | ---: | ---: |
| CEDT_P4 (prop25) | 1.01 | 7 | 0.26 |
| MIX50 (prop25 on routed half) | 1.02 | 4 | 0.26 (routed jobs) |
| CTDE_P2 (no mask) | 1.03 | 9 | 0.92 |

Predictions to be graded on the live campaigns:
1. Gain order CTDE_P2 > MIX50 >= CEDT_P4 under these masks, all below 1.05.
2. CTDE_P2 wins at least as many research pairs as CEDT_P4.
3. CTDE_P2 timing identification above 0.80; MIX50 and CEDT_P4 between
   0.15 and 0.40 on routed jobs.

Caution on prediction 2: in the replay, CTDE_P2 "wins" by billing a
little less before the first qualifier (median bill 21.05 vs 21.85
pc-nh), because both arms find the same compound in the same order.
Such narrow wins are within the 2 to 4% run-to-run spread measured in
No. 2, so a live 9 of 15 would not by itself show a research benefit.

## Collection

Results land in `/scratch/general/vast/<uNID>/mpt_live3c/results/<ARM>_s<seed>/`
(campaigns.jsonl, wire_log.jsonl, progress.json with the final logbook);
option A results stay in `mpt_live3/results/`. Grade all four arms
against the same DTDE campaigns.

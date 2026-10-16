# Timing attack on comparison No. 3: results

Run 2026-10-14 on the complete No. 3 collection, as registered in
`TIMING_ATTACK_PLAN.md` (2026-10-12) and `parallel/OPTION_C.md`
(P-2026-10-01, item 3). Script: `wire_attack3.py` (adapted from
`../paired_comparison_2/wire_attack2.py`); full output: `timing_attack3.json`.

## Data and attack

- 60 campaigns in `collected_2026-10-14/` (CEDT_P4, DTDE, MIX50, CTDE_P2;
  seeds 0 to 14) and the 12 notchpeak copies in `site_bridge_2026-10-14/`
  (10 DTDE, 2 CEDT_P4). Older snapshots were not read.
- Attacker view: the wire log row of each job (opaque id, stage, completion
  time, memory bit or size bin where disclosed). CEDT_P4 and the routed half
  of MIX50 carry the proportional mask (run time rounded up to 25 % of the
  expected run time); CTDE_P2 carries true times and the size bin. DTDE also
  wrote a wire log with true times; it was checked against the DTDE scheduler
  records and matches job for job (0 mismatches), so it is the view the plan
  names.
- Every opaque id in every wire row resolved offline to a compound (0 unresolved). Failed
  jobs were excluded (3 wire rows).
- Identity attack: leave one seed out; reference = median wall time per
  (compound, stage) from the other seeds of the same arm; each held-out id is
  assigned to the nearest reference in mean absolute log wall time over its
  successful F1/F2 jobs, with disclosed memory bit and size bin used as hard
  constraints. Membership attack: each reference compound scored by minus its
  smallest distance to any fingerprint in the held-out campaign; AUC.
- Limits: identity 1/29 + 0.05 = 0.084; membership AUC 0.60.
- MIX50 "routed jobs" uses only the masked jobs (visible on the wire as a
  non-null memory bit). MIX50 over all jobs is reported for reference.

## Identity accuracy and membership AUC per arm

| Arm (wire view) | Identity accuracy | Correct / ids | Membership AUC | Identity above 0.084 | AUC above 0.60 |
| --- | ---: | ---: | ---: | :---: | :---: |
| CTDE_P2 (true times + size bin) | 0.218 | 19 / 87 | 0.672 | yes | yes |
| DTDE (true times, scheduler view) | 0.750 | 66 / 88 | 0.945 | yes | yes |
| CEDT_P4 (proportional mask) | 0.484 | 45 / 93 | 0.826 | yes | yes |
| MIX50, routed jobs (proportional mask) | 0.174 | 12 / 69 | 0.722 | yes | yes |
| MIX50, all jobs (reference only) | 0.281 | 25 / 89 | 0.763 | yes | yes |

Every arm leaks compound identity and membership above the registered limits.

Split by the cluster of the attacked campaign (references unchanged):

| Arm | granite: campaigns, accuracy | notchpeak: campaigns, accuracy |
| --- | --- | --- |
| CTDE_P2 | 4, 0.17 | 11, 0.23 |
| DTDE | 12, 0.85 | 3, 0.35 |
| CEDT_P4 | 13, 0.49 | 2, 0.46 |
| MIX50 routed | 2, 0.30 | 13, 0.15 |

## Grades

| Test | Registered condition | Measured | Verdict |
| --- | --- | --- | :---: |
| P-2026-10-01 item 3 | CTDE_P2 above 0.80; MIX50 (routed) and CEDT_P4 between 0.15 and 0.40 | CTDE_P2 0.218; MIX50 routed 0.174 (in band); CEDT_P4 0.484 (above band) | **fail** |
| T1 | identity on notchpeak DTDE copies, references only from granite campaigns, above 0.084 | 0.466 (27 / 58, 10 copies, references from 12 granite DTDE campaigns, other seeds) | **pass** |
| T2 | the T1 attack after dividing every wall time by the campaign's median F1 wall time reaches at least the T1 accuracy | 0.069 vs T1 0.466 | **fail** |
| T3 | CEDT_P4 identity below DTDE (same seeds) and above 0.084; CEDT_P4 membership AUC above 0.60 | 0.484 < 0.750 and > 0.084; AUC 0.826 | **pass** |
| T4 | median repeat-to-repeat spread (sd of log wall time per compound and stage, within one cluster) above 0.0030 | 0.0152 (128 repeated pairs; granite 0.0053 over 64, notchpeak 0.0451 over 64) | **pass** |

Item 3 fails on two of its three parts: CTDE_P2 is far below 0.80 and CEDT_P4
is above 0.40. Only the MIX50 part holds.

Definitions used where the plan left a detail open (fixed before reading the
numbers, not tuned afterwards):

- T1 references exclude the attacked seed (leave one seed out, as the plan
  states). Including the same-seed granite twin gives 0.534; references from
  granite DTDE plus CTDE_P2 give 0.483; references from notchpeak DTDE
  campaigns only give 0.379. All are above 0.084.
- T2 divides both the references and the targets by their own campaign's
  median successful F1 wall time. With the same-seed twin included T2 reaches
  0.293, still below T1.
- T4 uses DTDE scheduler records (true run times), successful jobs, main and
  bridge campaigns, np.std of log wall time per (cluster, compound, stage)
  with at least two runs, as in the timing-leakage article Fig. 2. Variants: main campaigns only
  0.0064; all four arms (true run time) 0.0279 on granite and 0.1222 on
  notchpeak. Every variant is above 0.0030. The notchpeak group mixes three
  processor models (EPYC 9554, 9654, 9334), so its spread includes hardware
  differences, not only load from other users.

## Reading

- **Shared guest hardware is noisier but is not a defence.** Repeat runs of
  one compound spread by about 0.5 % on granite guest nodes and about 4.5 % on
  notchpeak guest nodes, against 0.3 % on the dedicated grn061 (T4). Yet the
  unmasked DTDE view still names the compound behind 75 % of opaque ids, and a
  timing table measured only on granite names 47 % of the compounds run on
  notchpeak (T1). A node change lowers the hit rate but leaves it more than
  five times the limit. The timing-leakage article can state that the leak transfers across
  clusters.
- **Rescaling by one speed factor per node is a weaker attack, not a
  defence.** T2 fails because dividing by the campaign's median F1 time throws
  away the absolute scale that separates compounds (and that median depends on
  which compounds the campaign happened to run). The attacker who skips this
  step already succeeds (T1), so the T2 failure does not close the leak.
- **The proportional mask lowers the leak but does not close it.** CEDT_P4
  falls from 0.75 (DTDE, same seeds) to 0.48 and its membership AUC from 0.94
  to 0.83 (T3). A materials group whose compounds run under this mask should
  expect about half of them to be named from completion times alone.
- **The unmasked CTDE_P2 arm leaked less than predicted (0.22, not above
  0.80).** Its run times for one compound varied by up to about 30 % between
  campaigns, on granite as well as notchpeak (for example HfS2-2H F1 took
  16,526 s on grn064 and 21,932 s on grn063). Its campaigns ran their own jobs
  side by side to the same degree as DTDE (on average about one other job of
  the campaign at a time in both arms), so the extra scatter is not from its
  own packing; the records do not show its source (other users' load on the
  guest nodes or node differences are the candidates). Ten of its 15
  campaigns ran on notchpeak, against 3 of 15 for DTDE, which also lowers its
  number. The low value is therefore a property of where and when these
  campaigns ran, not of the contract: the same true-time view gave 0.75 in
  DTDE. It still exceeds both limits.
- **Site mix is a confound for arm-to-arm comparisons.** DTDE and CEDT_P4 ran
  mostly on granite; CTDE_P2 and MIX50 mostly on notchpeak. The T3 comparison
  (DTDE vs CEDT_P4) is between two mostly-granite arms and is the cleanest;
  comparisons involving CTDE_P2 or MIX50 mix contract and site effects.

All tests could be computed from the collected data.

## Bootstrap intervals (added 2026-10-15)

`../bootstrap_ci/seed_bootstrap3.py` reruns the identical attacks and
resamples the held-out seeds (cluster bootstrap, B = 10000, percentile 95 %
intervals; DTDE and CEDT_P4 resampled with the same seeds). Output:
`../bootstrap_ci/seed_bootstrap3.json`. Point values reproduce the table
above.

| Attack | Seeds | Identity accuracy (95 % interval) | Membership AUC (95 % interval) |
| --- | ---: | --- | --- |
| DTDE | 15 | 0.750 (0.628 to 0.861) | 0.945 (0.903 to 0.975) |
| CEDT_P4 | 15 | 0.484 (0.391 to 0.576) | 0.826 (0.772 to 0.875) |
| CTDE_P2 | 15 | 0.218 (0.135 to 0.318) | 0.672 (0.613 to 0.735) |
| MIX50, routed jobs | 15 | 0.174 (0.090 to 0.270) | 0.722 (0.640 to 0.800) |
| T1 (notchpeak copies, granite references) | 10 | 0.466 (0.263 to 0.673) | 0.832 (0.731 to 0.914) |

- Every lower bound is above the identity limit (0.084) and the AUC limit
  (0.60), so no breach verdict depends on seed-to-seed variation. The
  closest is MIX50 routed identity, whose lower bound (0.090) sits just
  above the limit.
- T3 difference, CEDT_P4 minus DTDE identity on paired seeds: -0.266
  (-0.415 to -0.092). The proportional mask lowers the leak with an
  interval that excludes zero.

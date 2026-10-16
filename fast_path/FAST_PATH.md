# Shortening the wait for paired comparisons (2026-09-30)

Comparison No. 2 took 14.5 days of node time because its 33 campaigns
ran one after another on grn061. This note records what can run side by
side, what can be replaced by recorded run times, and the time each
route would take for the comparison No. 3 design options (the option
run is defined in `../paired_comparison_3/parallel/OPTION_C.md`).

## 1. Can several jobs share one node?

They already do inside a campaign: the driver packs 2 (no sharing) or
3 (broker arm) QE runs of 16 cores each onto the 64-core node. Two
whole campaigns cannot share grn061, because the quantity under test is
node memory: a campaign reserves up to 342 GB of the 380 GB and its
runs peaked at about 355 GiB. On free granite-guest nodes with 764 GB
and 96 cores (4 such nodes on 2026-09-30), the two arms of one seed fit
side by side: 2 x 342 GB and 32 + 48 cores. That also puts both arms of
a pair on the same hardware at the same time.

granite-guest on 2026-09-30 (`sinfo`): 39 nodes, all with at least
380 GB; 16 of 96 cores / 380 GB, 4 of 96 cores / 764 GB, 13 of 64 cores
/ 508 GB, 6 of 64 cores / 1 TB. Most were allocated or partly used.

## 2. Are run times repeatable enough to record and reuse?

Yes, at 8x8 supercells on grn061. The same compound at the same stage
repeated within 1.7% (median coefficient of variation over 45
compound-stage pairs), 4.1% at most, whether it ran in the no-sharing
arm, the broker arm, alone or next to two other jobs. The bill is a
fixed function of run time and reserved memory:
`billed = (run time + masking hold) x max(16/64, reserved GB / 380)`.

`replay.py` re-executes the driver's launch, packing, masking and
billing rules as an event simulation, reading run times from a library
of measured calls instead of launching QE. Leave-one-campaign-out check
on all 33 measured campaigns (`results/replay_validation.json`):

| check | result |
| --- | --- |
| same set of QE calls chosen | 31 of 33 campaigns |
| same order of QE calls | 28 of 33 |
| campaign bill, median / worst error | 0.9% / 4.1% |
| computing-centre ratio (labels per pc-nh, broker / no sharing) | 1.149 replayed vs 1.133 measured |
| which arm billed less, per pair | same answer in 13 of 15 pairs (the 2 others differ by under 1%) |

The library holds 63 of the 87 compound-stage entries (29 compounds x
F1, F2, F3). The 24 missing entries belong to 10 compounds that no
campaign reached: TiSe2-2H (F3), TiTe2-2H (F2, F3), ZrS2-2H, ZrSe2-2H
(F2, F3), ZrTe2-1T, ZrTe2-2H, HfSe2-1T (F2, F3), MoSe2-2H, MoTe2-2H
(F3), WS2-2H (F3), WTe2-2H.

## 3. Three routes and their wall-clock time

Campaign length from the replay (16 calls per campaign, as in options
A to C): median 24 to 27 h, longest 37 to 39 h.

| route | what runs on hardware | wall-clock for option A (15 pairs x 16 calls) |
| --- | --- | --- |
| sequential on grn061 (as No. 2) | all 30 campaigns | about 31 days |
| pairs in parallel on granite-guest | 30 campaigns on N nodes at once | about 1.6 days with 15 two-arm nodes; about 3.3 days with 10 single-campaign nodes; plus queue wait |
| recorded-cost library + replay, then a live check | the 24 missing entries as one job array (about 16 h, the longest ladder), 3 repeat runs to compare guest hardware with grn061, then 2 to 3 live pairs in parallel | about 1 day for the library, minutes for every option and arm set, about 1.5 days for the live check |

Notes on the parallel route:
- Each pair must run on one node model, since run time depends on the
  processor; pin the node class in the job request.
- Guest jobs can be cancelled by the node owner. The driver does not
  resume a half-finished campaign, so a cancelled campaign restarts
  from its first call (`--requeue`); the loss is at most one campaign.
- Records should add the node name and processor model to every call.

What the replay does not give: new solver failures, contention beyond
the measured 2 to 11%, or costs for structures not yet run (for
example, the corrected 2H monolayers or D3 bilayers from the stacking
check, job 2088961). Those need library entries measured first. It does
give every arm set (DTDE, CTDE, CEDT, the mixtures, CTCE), any number
of seeds and call budgets, and the timing-mask variants, from the same
library.

# Timing attack on comparison No. 3: plan and added predictions

Written 2026-10-12 18:10 UTC. At this time no timing attack had been run on any
No. 3 or No. 3b wire log, and their wall times had not been read for that
purpose. The timing-leakage article carries this test once No. 3 is collected, for the reasons below.

## Why No. 3 adds to the timing-leakage article

The timing-leakage article's timing results come from comparisons No. 1 and No. 2, both on the
dedicated node grn061, where repeat runs of one compound differed by about 0.3 %.
The timing-leakage article names "noisy shared hardware" as a possible defence and says it was not
tested. No. 3 tests it:

1. **Other hardware.** No. 3 ran on guest nodes of two clusters (granite-guest,
   then notchpeak-guest after the 9 Oct move), on more than one processor model
   (`pair_sites.json`). The attacker's reference timings and the target campaign
   then come from different machines.
2. **Same seed on two clusters.** The 12 site-bridge copies (`l3np_*`, notchpeak)
   repeat granite campaigns with the same seed and compound order, so the
   attacker can use references measured on one cluster to attack a campaign run
   on the other.
3. **A different mask.** CEDT_P4 and the routed half of MIX50 use the
   proportional mask (completion time rounded up to 25 % of the expected run
   time), not the fixed 600-s quantum of No. 2.
4. **Four contracts.** CTDE_P2 sends true run times and the size bin, so it is
   the unmasked upper bound; DTDE has no wire but its scheduler records are the
   same view.

## Prediction already registered

`parallel/OPTION_C.md`, prediction P-2026-10-01, item 3 (registered before any
option C data): CTDE_P2 identity accuracy above 0.80; MIX50 (routed jobs) and
CEDT_P4 between 0.15 and 0.40. Limit: 1/29 + 0.05 = 0.084 (the timing-leakage article rounds to
0.087 with the 27-compound prior of comparison No. 1; No. 3 uses 29).

## Added predictions (registered now, before the attack is run)

| Id | Prediction | Pass condition |
| --- | --- | --- |
| T1 | The fingerprint survives a change of node | identity accuracy on the notchpeak DTDE copies, with references built only from granite campaigns, above 0.084 |
| T2 | A per-machine speed factor does not remove the leak | the same attack after dividing every wall time by the campaign's median F1 wall time (one scale factor per node) reaches at least the accuracy of T1 |
| T3 | The proportional mask lowers but does not close the leak | CEDT_P4 identity accuracy below the DTDE value on the same seeds and above 0.084; membership AUC above 0.60 |
| T4 | Shared guest nodes are noisier than grn061 | median repeat-to-repeat spread of log wall time for the same (compound, stage) within one cluster above 0.0030, the grn061 value in the timing-leakage article |

If T1 fails while T4 passes, guest-node noise is a defence and the timing-leakage article states the
noise level at which it starts to work. If T1 and T2 pass, a node change is not a
defence and the timing-leakage article states that the leak transfers across clusters.

## How it will be run

After the last No. 3 campaigns finish (running jobs end by about 15 Oct; No. 3b
seeds 3 and 4 on grn061 by about 15 Oct), the analysis collects
`mpt_live3/results`, `mpt_live3c/results`, `mpt_live3/results_notchpeak` and
`mpt_live3b/results`, adapts `../paired_comparison_2/wire_attack2.py` (same attacks,
leave-one-seed-out references, failed jobs excluded) with the site split above,
grades item 3 and T1 to T4, and adds the result to the timing-leakage article as a third measured
row block in the timing table with one paragraph in the timing section.

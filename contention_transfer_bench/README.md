# contention_transfer_bench — contention-vs-scale + transfer probes (items 2 and 5)

One ~1-node-hour SLURM job on granite grn061 measuring:

1. **Contention vs scale** (the live half of `../coupling_onset/`):
   solo vs co-tenant (32+32 ranks sharing the box) wall times for
   TiS2_1T / MoSe2_2H at s1/s2/s3 supercell scales, 2 reps. The
   interference factor per scale tests whether co-tenant coupling
   grows with task size (memory-bandwidth saturation). Single-box
   contention only — inter-node scaling needs kingspeak's general
   partition (the account has a general allocation there; grn061 is
   the only *owned* node).
2. **Transfer probes** (item 5): a defect supercell
   (`MoS2_3x3_Svac`, 53 atoms) and a MoS2/WS2 heterobilayer
   (`MoS2_WS2_hetero_2x2`, 24 atoms, 3 species), SCF cost vs the
   MX2-fitted twin prediction from electron count alone.

Staged and submitted by `../paired_comparison_1/stage_and_submit.sh`;
collected by `../paired_comparison_1/collect_live.sh`; guards:
`MPT_BENCH_NH_CAP=5`, `--time=04:00:00`.

# 2H geometry check: monolayer, 2H bilayer and 3R bilayer with DFT-D3

Submitted 2026-09-30 to the free `granite-guest` partition (SLURM job
2088961) to check whether the 2H layers had been twisted.

What the first campaign actually computed: every "2H" entry was a 6-atom
bilayer in the 2H polytype stacking (second layer rotated 180 degrees,
AA'), in an 18 A cell, relaxed with plain PBE and no dispersion correction,
in-plane cell only (`cell_dofree='2Dxy'`). The idealized start put the
chalcogen planes of the two layers 1.7 A apart; relaxation pushed them to
3.7 to 4.3 A (metal-metal 6.7 to 7.7 A; MoS2 7.40 A against about 6.15 A in
bulk 2H-MoS2), because PBE has no van der Waals binding. The 1T entries are
3-atom monolayers. No twist angle and no 3R stacking was computed.

This run recomputes the 15 compositions three ways on the same PBE/GBRV
F1-F3 ladder (no phonons): `mono2H` (3-atom monolayer), `bi2H` (AA'
bilayer, DFT-D3 with Becke-Johnson damping), `bi3R` (AB bilayer, DFT-D3).
Bilayers start at a 6.2/6.5/7.0 A metal-metal distance (S/Se/Te) in a
30 A cell. Driver: `run_stacking.py` (reuses `dft_campaign/run_campaign.py`);
staging: `stage_and_submit_stacking.sh`. Twisted bilayers are not included:
the smallest commensurate twist (21.8 degrees) needs a 42-atom cell.

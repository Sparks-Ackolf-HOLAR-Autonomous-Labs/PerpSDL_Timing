# Comparison No. 3: corrected candidate list (2026-10-04)

Built by `build_candidate_list.py` from the first-pass screen
(`../dft_campaign/results/outcomes.jsonl`), the corrected 2H structures
(`../stacking_study/results_2088961/outcomes.jsonl`, granite-guest job
2088961) and the No. 3 input manifest (`../paired_comparison_2/inputs/manifest2.json`).
Machine-readable copy: `candidates_corrected.json`.

## What changed

The first-pass "2H" entries were two-layer cells held about 1.2 Å too far
apart, because plain PBE has no van der Waals attraction. They were
recomputed on the same PBE/GBRV F1 to F3 ladder in three forms: a single
2H layer (3 atoms), and a two-layer cell relaxed with the D3 dispersion
correction in 2H (AA') and in 3R stacking. The 1T entries were already
single layers and are unchanged.

## The list

PBE gaps in eV, primitive cells. Bold: inside the 1.0 to 2.0 eV window.
"In No. 3 pool" means the compound is one of the 29 that the running
campaigns draw from (HfSe₂-2H was left out because its first-pass
relaxation failed).

| candidate | in No. 3 pool | first pass | corrected (single layer) | 2H-stacked bilayer, D3 | 3R bilayer, D3 |
| --- | --- | ---: | ---: | ---: | ---: |
| TiS₂-1T | yes | 0.061 | 0.061 | same as single layer | same as single layer |
| TiS₂-2H | yes | 0.572 | not relaxed | 0.380 | 0.339 |
| TiSe₂-1T | yes | metal | metal | same as single layer | same as single layer |
| TiSe₂-2H | yes | 0.456 | 0.566 | 0.283 | 0.257 |
| TiTe₂-1T | yes | metal | metal | same as single layer | same as single layer |
| TiTe₂-2H | yes | 0.124 | 0.166 | metal | metal |
| ZrS₂-1T | yes | **1.201** | **1.201** | same as single layer | same as single layer |
| ZrS₂-2H | yes | 0.863 | 0.980 | 0.583 | not relaxed |
| ZrSe₂-1T | yes | 0.499 | 0.499 | same as single layer | same as single layer |
| ZrSe₂-2H | yes | 0.620 | 0.793 | 0.421 | 0.410 |
| ZrTe₂-1T | yes | metal | metal | same as single layer | same as single layer |
| ZrTe₂-2H | yes | 0.291 | 0.433 | 0.148 | 0.150 |
| HfS₂-1T | yes | **1.330** | **1.330** | same as single layer | same as single layer |
| HfS₂-2H | yes | **1.014** | **1.099** | 0.728 | 0.760 |
| HfSe₂-1T | yes | 0.646 | 0.646 | same as single layer | same as single layer |
| HfSe₂-2H | no | not relaxed | 0.903 | 0.538 | 0.518 |
| HfTe₂-1T | yes | metal | metal | same as single layer | same as single layer |
| HfTe₂-2H | yes | 0.304 | 0.325 | 0.106 | 0.145 |
| MoS₂-1T | yes | metal | metal | same as single layer | same as single layer |
| MoS₂-2H | yes | **1.557** | **1.673** | **1.259** | **1.237** |
| MoSe₂-1T | yes | metal | metal | same as single layer | same as single layer |
| MoSe₂-2H | yes | **1.449** | **1.459** | **1.161** | **1.166** |
| MoTe₂-1T | yes | metal | metal | same as single layer | same as single layer |
| MoTe₂-2H | yes | **1.035** | **1.058** | 0.821 | 0.853 |
| WS₂-1T | yes | metal | metal | same as single layer | same as single layer |
| WS₂-2H | yes | **1.770** | **1.837** | **1.394** | **1.409** |
| WSe₂-1T | yes | metal | metal | same as single layer | same as single layer |
| WSe₂-2H | yes | **1.551** | **1.577** | **1.324** | **1.352** |
| WTe₂-1T | yes | metal | metal | same as single layer | same as single layer |
| WTe₂-2H | yes | **1.027** | **1.064** | 0.948 | **1.014** |

Qualifiers under each structural model:

| model | count | compounds |
| --- | ---: | --- |
| first pass (2H as PBE-spaced bilayer) | 9 | ZrS₂-1T, HfS₂-1T; HfS₂, MoS₂, MoSe₂, MoTe₂, WS₂, WSe₂, WTe₂ (2H) |
| **corrected, single layer** | **9** | the same nine |
| 2H-stacked bilayer, D3 | 6 | ZrS₂-1T, HfS₂-1T; MoS₂, MoSe₂, WS₂, WSe₂ |
| 3R bilayer, D3 | 7 | as above plus WTe₂ |

## What it means for the running comparison No. 3

- **The single-layer correction does not change which compounds count as
  hits.** Single-layer 2H gaps are 0.01 to 0.17 eV wider than the first
  pass, and the three borderline compounds (MoTe₂ 1.058, WTe₂ 1.064, HfS₂
  1.099 eV) now clear the lower edge by 0.06 to 0.10 eV instead of 0.01 to
  0.04 eV. HfSe₂-2H now has a gap (0.903 eV) and ZrS₂-2H moves to 0.980 eV;
  both stay outside the window.
- **Checked on the 13 collected campaigns** (`candidates_corrected_check.json`):
  graded against the corrected single-layer list, every campaign has the
  same first hit at the same billed cost as the live run. The informal
  research-side reading of the four complete pairs stays at 0 of 4 wins
  for the broker arm.
- **A bilayer list would change the research-side score.** With the D3
  bilayer lists, HfS₂-2H and MoTe₂-2H stop counting: four collected
  campaigns lose their first hit (broker s0 and s4, no-sharing s3) or move
  it later (no-sharing s8, 11.0 to 12.8 pc-nh). The four complete pairs
  still read 0 of 4.
- **The cells being computed are still first-pass bilayers.** The 8×8 2H
  inputs of No. 3 are 384-atom supercells of the PBE-spaced bilayer. Their
  cost and memory are valid measurements of those cells, and the
  computing-centre metric does not depend on gaps. A single-layer 8×8 2H
  cell would have 192 atoms, the same as the 1T cells, so the memory split
  that the disclosed bit carries would then come from chemistry (heavier
  chalcogens and metals) rather than from layer count.
- Spin–orbit gaps were not recomputed for single layers. If the shifts
  measured on the first-pass cells carry over, MoTe₂-2H and WTe₂-2H leave
  the window after SOC (shifts 0.11 and 0.29 eV against margins of about
  0.06 eV), giving seven, as before. The window test in the preregistered
  grade is scalar-relativistic.
- Not converged after the retry: TiS₂ 2H single layer and ZrS₂ 3R bilayer.
  Neither is near the window in any other form.

## Design choices raised by the corrected list

Both choices were resolved on 5 Oct 2026 (see `../paired_comparison_3b/DESIGN.md`).

1. Grading list for the research-side metric of No. 3: (a) keep the live
   in-campaign gap test as preregistered, (b) grade against the corrected
   single-layer list (no change on any collected campaign so far), or (c)
   report a D3-bilayer grade as a secondary reading. Recommendation: (a) as
   primary with (b) reported beside it, since (b) is identical so far and
   records the structural correction; (c) only if the target is bilayer
   devices.
2. Whether the 47 pending campaigns (waiting behind the granite
   maintenance of 5 Oct 07:00 UTC) should keep the first-pass 8×8 inputs
   (recommended, so all pairs stay comparable) or be re-staged with
   single-layer 8×8 cells, which would start a new comparison rather than
   continue this one.

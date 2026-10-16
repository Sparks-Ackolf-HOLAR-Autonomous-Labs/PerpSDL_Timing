# Job Timing Reveals Secret Candidate Compounds in Shared-Cluster DFT Screening of Two-Dimensional Semiconductors at Every Disclosure Level

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23413484.svg)](https://doi.org/10.5281/zenodo.23413484)

Code and data for the article "Job Timing Reveals Secret Candidate Compounds in Shared-Cluster DFT Screening of Two-Dimensional Semiconductors at Every Disclosure Level" (prepared for Proceedings on Privacy Enhancing Technologies).

Groups screening two-dimensional semiconductors run density functional theory jobs on shared computing centres, where the group's candidate list and the centre's tuning knowledge are both secrets. Attacks were executed on the message logs of measured Quantum ESPRESSO campaigns over 29 MX2 layers (a dedicated node and shared guest nodes of two clusters) and of simulated campaigns driven by scripted and large language model agents. Wall-clock time alone identified the compound behind an opaque job identifier at every disclosure level; the article also measures the cost of timing masking, the forward use of the same records to predict a job's run time, and how leakage depends on the decision policy, collusion, the number of parties and shared tools.

The repository holds what the article reports and what is needed to rebuild
it: inputs, campaign drivers, registered predictions, raw records, result
summaries and the figure generator. Results are labelled **measured** (runs
on hardware) or **simulated** (the campaign simulator; simulated node-hours
are simulated units, not measured cost).

## Quick start

```
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cd papers/paperC_leakage_attacks/figures && python3 make_figures.py
```

The figure generator regenerates every figure of the article from the
records in this repository; the manuscript and the rendered figures are not
included. `figure_test.json` records a run of the generator from a copy of
this repository with no access to anything else.

## Contents

- `papers/paperC_leakage_attacks/figures/make_figures.py`: the figure generator.
- One folder per experiment:

| folder | content |
|---|---|
| `bootstrap_ci/` | cluster-bootstrap intervals over seeds for the measured timing attacks |
| `centralization_surface/` | simulated: gain for both parties over training and execution centralization, task scale, number of research parties and schedules |
| `contention_transfer_bench/` | measured: co-tenant contention and defect and heterostructure cost probes |
| `decision_maker_leakage/` | simulated: leakage under five query policies |
| `dft_campaign/` | measured: Quantum ESPRESSO screen of the 30 MX2 candidates (fidelity stages F1 to F4, spin-orbit finalists) |
| `fast_path/` | replay of recorded run times and the per-candidate run-time library |
| `hybrid_arms/` | simulated: hybrid, negotiation-only and collusion arms |
| `llm_agents/` | simulated campaigns with open-weight language-model agents in the decision roles (with and without tools) |
| `measured_attacks/` | trained leakage attacks on simulated and measured transcripts |
| `paired_comparison_1/` | measured: comparison No. 1, 3x3 supercells, 480 QE calls |
| `paired_comparison_2/` | measured: comparison No. 2, 8x8 supercells, job packing and timing masking, band-structure repair pass |
| `paired_comparison_3/` | measured: comparison No. 3 on guest nodes (DTDE, CEDT, half-routed mixture and CTDE), timing attack |
| `paired_comparison_3b/` | measured: comparison No. 3b, single-layer 2H cells at 8x8 |
| `pilot/` | measured: randomized 81-job pilot |
| `prior_predictive/` | campaign simulator, prior specifications and the 30 candidate structures |
| `reverse_timing/` | measured records: prediction of a job's run time from the compound (forward time map) |
| `scale_validation/` | measured: supercell, layer and strain cost series |
| `shared_stations/` | simulated: growth and deposition stations sharing controller logs |
| `stacking_study/` | measured: 2H single layers and DFT-D3 bilayers (AA' and 3R); read by the comparison No. 3 candidate list |
| `stage2_twin_fit/` | fit of the cost model to the measured QE calls |
| `timing_masking/` | measured completion times re-attacked under masking clauses |

- `prior_predictive/candidates/`: the 30 idealized MX2 structures and their
  metadata (CC0-1.0).
- `case_manifest.yaml`: the case definition (budgets, thresholds, leakage
  limits, fidelity ladder F0 to F4), fixed before the measured campaigns.
- Dated preregistration and results records use "frozen" for "fixed before
  the data were collected". They are kept as written, because their dates
  and content are what the preregistration states.

The folders `dft_campaign/`, `fast_path/`, `contention_transfer_bench/`, `paired_comparison_3b/`, `scale_validation/`, `stacking_study/`, `stage2_twin_fit/` are included because scripts in the reported folders read their files or stage them for a rerun.


Files the figure generator reads (`traced_inputs.json`):

- `bootstrap_ci/seed_bootstrap.json`
- `bootstrap_ci/seed_bootstrap3.json`
- `decision_maker_leakage/dm_leakage.json`
- `paired_comparison_1/results/campaigns.jsonl`
- `paired_comparison_2/results/campaigns.jsonl`
- `paired_comparison_2/results/wire_attack_results.json`
- `paired_comparison_3/collected_2026-10-14/DTDE_s0/campaigns.jsonl`
- `paired_comparison_3/collected_2026-10-14/DTDE_s1/campaigns.jsonl`
- `paired_comparison_3/collected_2026-10-14/DTDE_s10/campaigns.jsonl`
- `paired_comparison_3/collected_2026-10-14/DTDE_s11/campaigns.jsonl`
- `paired_comparison_3/collected_2026-10-14/DTDE_s12/campaigns.jsonl`
- `paired_comparison_3/collected_2026-10-14/DTDE_s13/campaigns.jsonl`
- `paired_comparison_3/collected_2026-10-14/DTDE_s14/campaigns.jsonl`
- `paired_comparison_3/collected_2026-10-14/DTDE_s2/campaigns.jsonl`
- `paired_comparison_3/collected_2026-10-14/DTDE_s3/campaigns.jsonl`
- `paired_comparison_3/collected_2026-10-14/DTDE_s4/campaigns.jsonl`
- `paired_comparison_3/collected_2026-10-14/DTDE_s5/campaigns.jsonl`
- `paired_comparison_3/collected_2026-10-14/DTDE_s6/campaigns.jsonl`
- `paired_comparison_3/collected_2026-10-14/DTDE_s7/campaigns.jsonl`
- `paired_comparison_3/collected_2026-10-14/DTDE_s8/campaigns.jsonl`
- `paired_comparison_3/collected_2026-10-14/DTDE_s9/campaigns.jsonl`
- `paired_comparison_3/site_bridge_2026-10-14/DTDE_s10/campaigns.jsonl`
- `paired_comparison_3/site_bridge_2026-10-14/DTDE_s11/campaigns.jsonl`
- `paired_comparison_3/site_bridge_2026-10-14/DTDE_s14/campaigns.jsonl`
- `paired_comparison_3/site_bridge_2026-10-14/DTDE_s3/campaigns.jsonl`
- `paired_comparison_3/site_bridge_2026-10-14/DTDE_s4/campaigns.jsonl`
- `paired_comparison_3/site_bridge_2026-10-14/DTDE_s5/campaigns.jsonl`
- `paired_comparison_3/site_bridge_2026-10-14/DTDE_s6/campaigns.jsonl`
- `paired_comparison_3/site_bridge_2026-10-14/DTDE_s7/campaigns.jsonl`
- `paired_comparison_3/site_bridge_2026-10-14/DTDE_s8/campaigns.jsonl`
- `paired_comparison_3/site_bridge_2026-10-14/DTDE_s9/campaigns.jsonl`
- `measured_attacks/attack_results.json`
- `measured_attacks/pilot_attack_results.json`
- `pilot/job_matrix.csv`
- `pilot/results/pilot_results.csv`
- `timing_masking/mask_results.json`

## Reproducing the results

`REPRODUCE.md` gives the software versions, the commands that regenerate
every summary and figure from the committed records, and the commands and
resources that re-run each computation (density functional theory jobs,
paired campaigns, simulations). `requirements.txt` lists the Python
packages; Quantum ESPRESSO 7.4 is needed only to re-run the DFT jobs.

## Licences and citation

Code (Python and shell scripts) is released under the MIT License
(`LICENSE`); data, result files and regenerated figures under the Creative
Commons Attribution 4.0 International licence (`LICENSE-CC-BY-4.0.txt`). The
candidate structures keep CC0-1.0. Cite with `CITATION.cff`.

`FILES.sha256` lists a SHA-256 hash for every file. Pseudopotentials are not
redistributed (GBRV 1.5 and PSlibrary 1.0.0 keep their own licences); file
names and hashes are given in `REPRODUCE.md` and in the experiment folders.
User identifiers were removed from the committed outputs.

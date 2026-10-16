# Reproducing: Job Timing Reveals Secret Candidate Compounds in Shared-Cluster DFT Screening of Two-Dimensional Semiconductors at Every Disclosure Level

This file explains how to reproduce every number, table and figure of the
article from this folder. All commands run from the folder root unless a
step says otherwise.

## Three levels of reproduction

1. **Check the archive.** `sha256sum -c FILES.sha256` confirms that every
   file is the one the article was written from.
2. **Re-analyse the committed records (no new compute).** Every summary,
   table and figure is regenerated from the raw records committed here
   (QE outputs parsed to JSON or JSONL, per-call campaign transcripts,
   simulator outputs). This level needs a workstation with Python and runs
   in minutes. It is the level a reader should run first.
3. **Re-run the computation.** The density functional theory jobs, the
   paired campaigns and the simulations can be repeated with the drivers,
   inputs and job scripts given for each experiment folder below. Measured
   job costs (wall time, memory, node-hours) depend on the hardware and on
   co-tenants; band gaps, energies and barriers do not. Simulations with
   fixed seeds reproduce exactly; the LLM-agent runs reproduce only
   statistically.

   Several steps below name a collector script (`collect_*.sh`). Those
   scripts copied the result files from the cluster into the working
   repository over the group's authenticated SSH connection and hard-code
   its account and paths, so they are not part of this folder. Copy the
   files each step lists by any means (`scp`, `rsync`) into the folder the
   step names; nothing else in the step changes.

Results are labelled in every folder as **measured** (from runs on
hardware) or **simulated** (from the campaign simulator); simulated
node-hours are simulated units, not measured cost.

## Software and data

**Analysis and figures.** Python 3.12 with numpy 2.5, scipy 1.18 and
matplotlib 3.11 (the versions the committed figures and summaries were
produced with; numpy 1.26 or later and matplotlib 3.8 or later also run the
scripts). Folders that need more state it in their section (for example
PySR for the cost-model fit, MACE for the machine-learned barriers, an
OpenAI-compatible LLM server for the LLM-agent campaigns).

```
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` lists the packages the scripts of this repository
import; packages needed only to re-run a computation are listed there as
comments.

**Density functional theory.** Quantum ESPRESSO 7.4 (`pw.x`, `ph.x`,
`neb.x`) built with Open MPI 5.0.3, loaded on the clusters used here with
`module load openmpi/5.0.3 quantum-espresso/7.4`. Campaign drivers that
run on compute nodes need Python 3.10 or later (`module load python/3.10.3`
on those clusters). Functional: PBE throughout; D3 dispersion only where the
stacking study states it.

**Pseudopotentials** (not redistributed; download from the original
sources and check the hashes):

- Scalar-relativistic runs: GBRV 1.5 ultrasoft sets (Garrity, Bennett,
  Rabe and Vanderbilt, Comput. Mater. Sci. 81, 446 (2014)), file names of
  the form `mo_pbe_v1.uspp.F.UPF`. SHA-256 hashes:
  `pilot/results/pseudos_manifest.txt`.
- Spin-orbit runs: PSlibrary 1.0.0 fully relativistic PAW sets, file names
  of the form `Mo.rel-pbe-spn-kjpaw_psl.1.0.0.UPF`. SHA-256 hashes and
  cutoffs: `dft_campaign/soc/PSEUDOS.md`.

Place the files in the `pseudos/` folder each driver names (or the path
its job script sets) before staging inputs.

**Cluster settings.** Job scripts keep the resource requests used for the
article (cores, memory, wall time). Account, partition and scratch paths
are site settings: replace them with your own (`<account>`,
`<partition>`, `$SCRATCH`). Jobs that pack several QE runs onto one node
must be given the whole node's memory (`--mem=0` or the node size); the
packing logic assumes it.

**Candidates.** `prior_predictive/candidates/` holds the 30 idealized 1T
and 2H MX2 structures and their metadata (CC0-1.0); every DFT driver reads
them from there. `case_manifest.yaml` is the case definition, fixed before
the measured campaigns (budgets, thresholds, leakage limits, fidelity ladder
F0 to F4).

## Figures

```
cd papers/paperC_leakage_attacks/figures && python3 make_figures.py
```

regenerates every figure of the article from the committed records. The
files the generator reads are listed in `traced_inputs.json`;
`figure_test.json` records a run of the generator from a copy of this
folder with no access to anything else. Tables in the article are read from
the result summaries named in the experiment sections below.

## Experiments

One section per experiment folder of this article, in the order of the
layout table in `README.md`.

### `bootstrap_ci/`: seed-level bootstrap intervals for the measured timing attacks of comparisons No. 1, No. 2 and No. 3

Level: analysis of committed records. Underlying records: comparison No. 1 (480 Quantum ESPRESSO calls, 10 paired seeds) and comparison No. 2 (15 paired seeds), both run on CHPC granite node grn061 (64 cores, 380 GB RAM); comparison No. 3 (60 campaigns, seeds 0 to 14, on granite-guest and notchpeak-guest nodes) and its 12 site-bridge copies run on notchpeak guest nodes.

**Re-analyse from the committed records (no new compute).**

Python 3 with `numpy`. Both scripts resolve paths from their own location, so they run from the repository root. Each overwrites its committed output; work in a fresh copy of the repository.

1. Comparisons No. 1 and No. 2 and the masking sweep:
   `python3 bootstrap_ci/seed_bootstrap.py`
   - imports `timing_masking/mask_study.py` and `paired_comparison_2/wire_attack2.py` (attack code reused unchanged);
   - reads `paired_comparison_1/results/campaigns.jsonl` (comparison No. 1), `timing_masking/mask_results.json` (list of masking clauses to re-evaluate), `paired_comparison_2/inputs/manifest2.json`, `paired_comparison_2/results/wire_log.jsonl`, and the `SALT` line of `paired_comparison_2/live2_campaign.py` (to map opaque identifiers back to compounds offline);
   - writes `bootstrap_ci/seed_bootstrap.json`.
2. Comparison No. 3:
   `python3 bootstrap_ci/seed_bootstrap3.py`
   - imports `paired_comparison_3/wire_attack3.py`, which reads `paired_comparison_3/collected_2026-10-14/<ARM>_s<seed>/{campaigns.jsonl,wire_log.jsonl}` (60 campaign folders), `paired_comparison_3/site_bridge_2026-10-14/<ARM>_s<seed>/` (12 folders) and `paired_comparison_2/inputs/manifest2.json`;
   - writes `bootstrap_ci/seed_bootstrap3.json`.

Method in both scripts: leave-one-seed-out identity and membership attacks as in the source folders; the per-seed held-out outcomes are resampled with replacement (cluster bootstrap over seeds, B = 10000, percentile 95 % intervals). References are not refitted per replicate. Paired arms share the resampled seed indices (No. 1 arms; DTDE and CEDT_P4 in No. 3, including the T3 difference). Seeds: `numpy.random.default_rng(20261008)` for `seed_bootstrap.py`, `default_rng(20261015)` for `seed_bootstrap3.py`. No command-line arguments or environment variables.

**Re-run the computation.**

The folder has no compute of its own. The records come from `paired_comparison_1/` (comparison No. 1), `paired_comparison_2/` (No. 2) and `paired_comparison_3/` (No. 3 and site bridge); re-running those campaigns and then the two scripts above regenerates the intervals.

**Outputs.**

- `bootstrap_ci/seed_bootstrap.json` (`comparison1`, `masking` worse-arm intervals for every clause, `comparison2`)
- `bootstrap_ci/seed_bootstrap3.json` (`arms`, `T3_identity_difference_CEDT_minus_DTDE`, `T1_cross_cluster`)
- The No. 3 table is reproduced in `paired_comparison_3/TIMING_ATTACK_RESULTS.md` (section "Bootstrap intervals").

**Checks.** Point estimates must equal the source attacks; intervals are 95 % percentile.

| record | identity accuracy | membership AUC |
| --- | --- | --- |
| No. 1, DTDE and CEDT_P4 (10 seeds) | 0.9625 (0.9125 to 1.0) | 1.0 (1.0 to 1.0) |
| No. 1, pad p99, worse arm | 0.075 (0.0375 to 0.1125) | 0.5013 (0.4726 to 0.5377) |
| No. 1, quant 600 s, worse arm | 0.05 (0.0125 to 0.0875) | 0.5 (0.5 to 0.5) |
| No. 2, DTDE (15 seeds) | 0.78 (0.68 to 0.875) | 0.9893 (0.979 to 0.9989) |
| No. 2, CEDT_P4 (15 seeds) | 0.5849 (0.4423 to 0.7193) | 0.9348 (0.9103 to 0.9587) |
| No. 3, DTDE (15 seeds) | 0.75 (0.6279 to 0.8605) | 0.9447 (0.9034 to 0.9754) |
| No. 3, CEDT_P4 | 0.4839 (0.3913 to 0.5761) | 0.8256 (0.7722 to 0.8749) |
| No. 3, CTDE_P2 | 0.2184 (0.1348 to 0.3177) | 0.6721 (0.613 to 0.7347) |
| No. 3, MIX50 routed jobs | 0.1739 (0.0895 to 0.2698) | 0.7216 (0.6395 to 0.7997) |
| No. 3, T1 cross-cluster (10 seeds) | 0.4655 (0.2632 to 0.6727) | 0.8324 (0.7313 to 0.9135) |

T3 difference (CEDT_P4 minus DTDE identity, No. 3): -0.2661 (-0.4154 to -0.0921). Identity limits: 0.087 (No. 1), 0.0845 (No. 3); AUC limit 0.60.

Limits: intervals describe seed-to-seed variation given fixed leave-one-seed-out references, not refitting uncertainty; with 10 or 15 seeds the percentile intervals are coarse; the measured walls, and therefore all values, depend on the nodes and co-tenant load during the original runs.

### `centralization_surface/`: continuous training-by-execution centralization surface, multi-party scaling, adaptive schedules and task-scale sweep

Level: simulated (twin physics imported unchanged from `prior_predictive/simulator.py`); the task-scale sweep is simulated on measured inputs. `RESULTS.md` records the 11 x 11 P1 and P3 surfaces as run on the DGX Spark (aarch64); hardware for the other runs is not in the repository.

**Re-analyse from the committed records (no new compute).** Python 3 with `numpy`, `scipy` and `matplotlib` (the 3D figure uses `mpl_toolkits.mplot3d`, shipped with matplotlib). Paths resolve relative to each script.

1. `python3 centralization_surface/make_figures.py` reads `results/surface_P4.json`, `surface_P3.json`, `surface_P2.json`, `surface_P1.json` (whichever exist), `results/scaling.json` and `results/schedules.json`, and writes `results/fig_centralization_surface.png`, `results/fig_centralization_heatmaps.png`, `results/fig_multiparty_scaling.png` and `results/fig_schedules.png`.
2. `python3 centralization_surface/make_tau_figure.py` reads `results/tau_diagnostic.json` and writes `results/fig_tau_answer.png`.
3. `python3 centralization_surface/make_scale_figure.py` reads `results/surface_scale.json` and writes `results/fig_surface_vs_scale.png`.

**Re-run the computation.** Each script below writes to `centralization_surface/results/` with a hard-coded file name; `--procs` defaults to `os.cpu_count()` and `--smoke` gives a tiny test run.

1. Surfaces at four disclosure levels (11 x 11 grid of (tau, eps) on [0, 1], 150 worlds, 30 paired seeds):
   `python3 centralization_surface/surface.py --worlds 150 --grid 11 --level P4` (repeat with `--level P3`, `P2`, `P1`); output `results/surface_<level>.json`. The default `--grid` is 6 and `--level` is P2, so pass both explicitly. P3 uses the default DP budget eps_DP = 4.
2. Training-axis diagnostic: `python3 centralization_surface/tau_diagnostic.py --worlds 120 --npts 21`; output `results/tau_diagnostic.json` (part A on 6 worlds, part B on 60 worlds with a fixed generator seed 7, part C transects on the requested worlds).
3. Multi-party scaling, N in {1, 2, 3, 5}: `python3 centralization_surface/scaling.py --worlds 200`; output `results/scaling.json`.
4. Adaptive schedules (eps-schedule at P4, tau-schedule at P2, time-mean 0.5, T = 80 rounds): `python3 centralization_surface/schedules.py --worlds 200`; output `results/schedules.json`.
5. Task-scale sweep on the posterior twin: `python3 centralization_surface/surface_scale.py --worlds 120 --grid 5` (defaults `--scales 1,10,30,100,300`, `--levels P4`, `--p2-scales 1,100`); output `results/surface_scale.json`. It reads the committed measured fits `stage2_twin_fit/twin_fit.json` and `pilot/results/pilot_fit.json`, and hard-codes the electron-scaling exponent by scale (1.20, 1.70, 2.00, 2.30, 2.50) and a 0.02 node-hour per-submission overhead. The scale is set through module globals before the worker pool starts, which relies on the `fork` start method (Linux default).
6. Corner and gradient check: run from inside the folder, because it uses working-directory-relative imports: `cd centralization_surface && python3 validate_continuity.py`. It uses 40 worlds at P4 and prints to stdout only (no file written).
7. Then rerun the three figure scripts above.

Seed handling: worlds come from `simulator.sample_world` (`crc32("<card>:<world_id>")`), with worlds split evenly over the three prior cards; the per-round delegation draws are seeded from each world's contention field, so (tau, eps) points are paired within a world; `surface_scale.py` adds `crc32("surfscale:<card>:<world_id>")` for the posterior patch. `MPT_HARD_CAP` has no effect on `surface.py`: its `run_mix` campaign loop stops once spend reaches the 500 node-hour budget (soft stop). Two module flags in `surface.py` (`SURR_SIZE_ADJ`, `IMMOBILE_FN`/`PASSRATE_TRAIN`) default to off and must stay off to reproduce these results.

**Outputs.**

- `results/surface_P1.json`, `surface_P2.json`, `surface_P3.json`, `surface_P4.json` (meta: 150 worlds, grid 11, 30 seeds)
- `results/tau_diagnostic.json` (120 worlds, 21 points), `results/scaling.json` (200 worlds), `results/schedules.json` (200 worlds), `results/surface_scale.json` (120 worlds, grid 5)
- Figures: `fig_centralization_surface.png`, `fig_centralization_heatmaps.png`, `fig_multiparty_scaling.png`, `fig_schedules.png`, `fig_tau_answer.png`, `fig_surface_vs_scale.png`

**Checks.**

- Corners of the mixed arm reproduce native DTDE and CEDT exactly and CTDE within 1.7 % on labels per node-hour (`RESULTS.md`).
- P4 at 11 x 11 (wide-prior cards): interior optimum win-win 0.26 at eps = 0.6 against 0.21 at the CEDT corner; every tau row is constant at P4 (part A of the diagnostic reports bit-identical outcomes for tau in {0, 0.5, 1}).
- P2 at 11 x 11: peak win-win 0.20 at (tau = 0, eps = 0.3) with leakage pass 0.99. P3: peak 0.19 at (0, 0.4). P1: win-win 0 in all 121 cells; throughput gain +25.3 % at full delegation.
- Cost-information R^2 at P2: own 0.986, surrogate 0.975, broker 0.759.
- Scaling: CEDT-P4 win-win 0.215 / 0.220 / 0.235 / 0.205 for N = 1, 2, 3, 5; CEDT-P2 identity accuracy rises 0.143 to 0.205.
- Schedules (eps at P4, mean 0.5): static 0.250, ramp-up 0.120, ramp-down 0.270, mid-pulse 0.230.
- Task scale (P4 ridge at eps = 1): 0.450 at x1, 0.942 at x10 and x30, 0.950 at x100 and x300.
- The tables in sections 2 and 3 of `RESULTS.md` quote an earlier 200-world, 6 x 6 run whose JSON is not in the repository; the committed `surface_P*.json` files are the later 11 x 11, 150-world grids. Reruns with the same code are expected to be identical (deterministic seeding), not recorded as verified. The N-party effects are reduced-form modifiers, and interior leakage is interpolated from the native attacker models.

### `decision_maker_leakage/`: leakage of a fixed contract under five decision-maker archetypes, single-policy against policy-robust audits

Level: simulated (base prior card, x1 task scale). The machine used for the committed run is not in the repository. All node-hours are simulated units.

The folder has no README; the definition, results and interpretation are in `decision_maker_leakage/RESULTS.md`.

**Re-analyse from the committed records (no new compute).**

1. The audit table in `RESULTS.md` is stored in `decision_maker_leakage/dm_leakage.json` (keys `worlds`, `table` with per-policy, per-contract channel means, `audit` with single-policy and policy-robust pass probabilities, `limits`). Print it with:
   `python -c "import json; d=json.load(open('decision_maker_leakage/dm_leakage.json')); [print(k, round(v['policy_robust'],2), {p: round(x,2) for p,x in v['single_policy'].items()}) for k,v in d['audit'].items()]"`
   This reproduces the lines of `decision_maker_leakage/dm_stdout.txt`.
2. The figure `decision_maker_leakage/fig_dm_leakage.png` is not written by any script in this folder. It is produced by `ceiling_diagnosis/make_figures.py` (figure 2 block), which reads `dm_leakage.json` and writes the PNG into this folder:
   `python ceiling_diagnosis/make_figures.py`
   The script has no main guard and also regenerates three other figures from committed files: `ceiling_diagnosis/results/fig_ceiling_decomposition.png`, `sociability_map/fig_sociability_map.png` and `governance_regrade/fig_governance.png`.
3. The paper version of this result (panel of `fig_policy.pdf`) is drawn by `fig_policy()` in `papers/paperC_leakage_attacks/figures/make_figures.py`, which also reads `measured_attacks/attack_results.json`.

Python packages: numpy, scipy (imported by the simulator), matplotlib.

**Re-run the computation.**

1. From the repository root:
   `python decision_maker_leakage/dm_leakage.py > decision_maker_leakage/dm_stdout.txt`
   Environment variables read: `DM_WORLDS` (default 200) and `MPT_HARD_CAP` (set to `1` by the script unless already defined). The process pool uses all CPU cores (`os.cpu_count()`); there is no option to change it.
2. The script imports `prior_predictive/simulator.py` (30 paired seeds per world) and installs each archetype through the simulator hook `R_PICK_POLICY`: `greedy` (the audit policy), `depth_first`, `repeat_prone` (factor 4 on the previous pick), `thompson`, `eps_greedy` (25 % random). It runs four contracts per world and archetype: CEDT-P2, CEDT-P3 (epsilon = 2), CTDE-P3 (epsilon = 2), CEDT-P4, giving 200 x 5 tasks.
3. Random-seed handling: worlds from `default_rng(crc32("base:<world>"))` in the simulator; the stochastic archetypes draw from fixed streams `default_rng(7000000 + round)` (thompson) and `default_rng(8000000 + round)` (eps_greedy). The only committed input is `prior_predictive/candidates/candidates.json`.
4. Output: the script overwrites `decision_maker_leakage/dm_leakage.json` (hard-coded path). Runtime is not in the repository.

**Outputs.**

- `decision_maker_leakage/dm_leakage.json`
- `decision_maker_leakage/dm_stdout.txt`
- `decision_maker_leakage/fig_dm_leakage.png` (via `ceiling_diagnosis/make_figures.py`)

**Checks.**

- P(all six leakage limits hold), policy-robust audit: CEDT-P2 0.00, CEDT-P3 0.03, CTDE-P3 0.01, CEDT-P4 1.00.
- Single-policy audits for CEDT-P3: greedy 0.56, depth_first 0.04, repeat_prone 0.43, thompson 0.49, eps_greedy 0.54; for CTDE-P3: 0.59, 0.01, 0.56, 0.46, 0.56.
- `RESULTS.md` reports a mean membership AUC of 0.80 to 0.82 for `depth_first` at P3 (limit 0.60), and, under CEDT-P3, found-rate 0.86 against 0.81 and labels per node-hour 0.022 against 0.031 for `depth_first` against `greedy`.
- The identification limit used here is `1/30 + 0.05` on `r_id_acc`, set in the script.
- All random streams are fixed, so a rerun with the same package versions is expected to reproduce the JSON exactly; a verified rerun is not in the repository.
- Limits: base prior card only; the attackers are the preregistered Bayes-style upper-bound constructions; the archetypes are scripted stand-ins for behaviours observed with LLM-driven decision makers, not LLM runs.

### `dft_campaign/`: Quantum ESPRESSO fidelity ladder (F1 to F4) on the 30 idealized MX2 candidates, plus spin-orbit gaps for the nine finalists (`dft_campaign/soc/`)

Level: measured on hardware. CHPC granite node grn061 (64 cores, 380 GB, one H100 not used), single-node partition of the group allocation; the jobs requested 48 of the 64 cores and 180 GB. All QE runs are CPU-only.

**Re-analyse from the committed records (no new compute).**

1. Python 3 standard library only (no third-party packages).
2. `python3 dft_campaign/analyze_dft.py` reads `dft_campaign/results/outcomes.jsonl` (later lines for a candidate override earlier ones) and `dft_campaign/results/campaign_summary.json`, and rewrites `dft_campaign/results/DFT_RESULTS.md` (per-candidate table, 1T minus 2H energy per formula unit within each composition, cost totals).
3. Optional, already applied to the committed files: `python3 dft_campaign/patch_f4.py` re-parses the nine raw phonon outputs in `dft_campaign/results/f4_outputs/*_f4.out` and backfills the Gamma frequencies into `outcomes.jsonl` and `campaign_summary.json` in place. Running it again is idempotent.
4. Spin-orbit sub-study: there is no separate analysis script; the summary is `dft_campaign/soc/results/soc_summary.json` as written by the driver (per-finalist `soc_gap_ev` and `soc_shift_ev`).

**Re-run the computation.**

1. Structures: `prior_predictive/candidates/candidates.json` (CC0-1.0, generated by `prior_predictive/make_candidates.py`, no arguments). The driver reads `candidates.json` from its working directory `$MPT_DFT_ROOT`, so copy it there.
2. Pseudopotentials: GBRV 1.5 ultrasoft PBE set (archive `all_pbe_UPF_v1.5.tar.gz`, Rutgers), files `ti_pbe_v1.4.uspp.F.UPF`, `zr_pbe_v1.uspp.F.UPF`, `hf_pbe_v1.uspp.F.UPF`, `mo_pbe_v1.uspp.F.UPF`, `w_pbe_v1.2.uspp.F.UPF`, `s_pbe_v1.4.uspp.F.UPF`, `se_pbe_v1.uspp.F.UPF`, `te_pbe_v1.uspp.F.UPF`, placed in `$MPT_DFT_ROOT/pseudos/`. sha256 hashes for six of them (Ti, Mo, W, S, Se, Te) are in `pilot/results/pseudos_manifest.txt`; no hash file for the Zr and Hf files is in the repository. `stacking_study/stage_and_submit_stacking.sh` shows a download loop for the same eight files.
3. Software: Quantum ESPRESSO 7.4 (`pw.x`, `ph.x`; version confirmed in the committed `f4_outputs`), modules `openmpi/5.0.3 quantum-espresso/7.4`, `python3` on the login stack, `/usr/bin/time -v` for memory telemetry.
4. Staging of `run_campaign.py`, `candidates.json` and `pseudos/` to `$SCRATCH/mpt_dft/` was done by hand; a staging script is not in the repository.
5. Submit `dft_campaign/campaign.sbatch` (`--nodes=1 --ntasks=48 --mem=180G --time=20160` minutes, `--account=<account> --partition=<partition> --qos=<qos>`). It runs `python3 run_campaign.py` in `$MPT_DFT_ROOT` (default `$SCRATCH/mpt_dft`) with `OMP_NUM_THREADS=1`. Driver settings via environment: `MPT_NPROC_PER_RUN` (16), `MPT_NPOOL` (4), `MPT_WORKERS` (3 concurrent `pw.x`), `MPT_NODE_HOUR_CAP` (330, soft guard). Each QE call is `mpirun -np 16 --bind-to none pw.x -nk 4`.
6. Ladder (per candidate): F1 SCF 40 Ry, 6x6x1; F2 `vc-relax`, `cell_dofree='2Dxy'`, 45 Ry, 12x12x1; F3 NSCF 18x18x1 (gap window 1.0 to 2.0 eV); F4 fresh SCF then `ph.x` at Gamma for qualifiers. One retry per failed stage (mixing 0.3 to 0.2, `cg`, 200 steps). Non-spin-polarized, no SOC.
7. A second pass, `python3 run_campaign.py --repair-f3` (the only command-line option), finalized F3/F4 records in the original run (29 s).
8. Collect `results/outcomes.jsonl`, `results/campaign_summary.json` and `campaign_<jobid>.log` from `$MPT_DFT_ROOT` into `dft_campaign/results/` (`dft_campaign/collect_dft.sh` does this over an authenticated SSH connection; it requires `CHPC_USERNAME`), copy the nine `work/<candidate>/f4.out` files to `results/f4_outputs/<candidate>_f4.out`, then run `patch_f4.py` and `analyze_dft.py` (steps 2 and 3 above).
9. Observed cost: 0.883 h wall, 108 QE calls, 0.59 node-hours (driver convention: wall x cores used / 64); budget cap not hit.

Sub-study `dft_campaign/soc/` (spin-orbit gaps):

1. Input: `dft_campaign/soc/finalists.json` (nine finalists with relaxed `a`, fixed F2 positions and scalar-relativistic gap). The script that built it from `results/outcomes.jsonl` is not in the repository.
2. Pseudopotentials: fully relativistic PSlibrary 1.0.0 PAW (`*.rel-pbe-spn-kjpaw_psl.1.0.0.UPF` for Zr, Hf, Mo, W; `*.rel-pbe-n-kjpaw_psl.1.0.0.UPF` for S, Se, Te), not bundled; file names and sha256 hashes in `dft_campaign/soc/PSEUDOS.md`. Cutoffs 60/400 Ry.
3. Stage `soc_campaign.py`, `finalists.json` and `pseudos/` into `$MPT_SOC_ROOT` (by hand; no staging script in the repository) and submit `dft_campaign/soc/soc.sbatch` (`--ntasks=48 --mem=180G --time=4:00:00`, node grn061, same module stack, `OMP_NUM_THREADS=1`, 16 ranks x 3 workers, `MPT_NODE_HOUR_CAP=10`). It runs `python3 soc_campaign.py` (no arguments): SOC SCF 12x12x1, then NSCF 18x18x1.
4. Collect with `dft_campaign/soc/collect_soc.sh` into `dft_campaign/soc/results/`. Observed cost: 0.126 h wall, 18 QE calls, 0.079 node-hours. A first submission (log `soc_1914220.log`) was cancelled because `OMP_NUM_THREADS` was unset and the node was oversubscribed; the committed sbatch file contains the fix.

**Outputs.**

- `dft_campaign/results/DFT_RESULTS.md`
- `dft_campaign/results/outcomes.jsonl`, `dft_campaign/results/campaign_summary.json`, `dft_campaign/results/campaign_1913865.log`
- `dft_campaign/results/f4_outputs/*_f4.out` (nine raw `ph.x` outputs)
- `dft_campaign/soc/results/soc_summary.json`, `dft_campaign/soc/results/soc_outcomes.jsonl`, `dft_campaign/soc/results/soc_1914274.log`

**Checks.**

- 30/30 candidates completed; 29 F2-converged (HfSe2_2H failed its relaxation retry); 9 qualifiers: HfS2_1T, HfS2_2H, MoS2_2H, MoSe2_2H, MoTe2_2H, WS2_2H, WSe2_2H, WTe2_2H, ZrS2_1T.
- Example PBE gaps: MoS2_2H 1.557 eV, WS2_2H 1.770 eV, ZrS2_1T 1.201 eV. Relaxed `a` of MoS2_2H 3.1818 A.
- All nine qualifiers pass the Gamma check (minimum frequency at least -16.6 cm-1; instability threshold -30 cm-1).
- 1T minus 2H energy: negative for all Ti, Zr, Hf compositions, positive for Mo and W (for example MoS2 +0.843, HfS2 -0.652 eV per formula unit).
- SOC gaps (eV): HfS2_1T 1.3106, HfS2_2H 1.0356, MoS2_2H 1.5519, MoSe2_2H 1.3502, MoTe2_2H 0.928, WS2_2H 1.5682, WSe2_2H 1.2617, WTe2_2H 0.7382, ZrS2_1T 1.1515. The SOC shift mixes the spin-orbit effect with the change of pseudopotential family (GBRV to PSL).
- Limits: the "2H" entries are 6-atom AA' bilayers relaxed with plain PBE and no dispersion correction (see `stacking_study/`). Gaps are PBE screening quantities; Gamma phonons are not a dynamical-stability proof. Wall times and node-hours depend on the node and its co-tenants; energies and gaps should agree to SCF tolerance with the same pseudopotentials.

### `fast_path/`: recorded-cost replay of the paired-comparison driver and the run-time library that completes it

Level: analysis of committed records (replay of the 33 campaigns of `paired_comparison_2/`, measured on CHPC granite node grn061, 64 cores, 380 GB) plus a measured run-time library (`results_lib3/`) on CHPC granite guest nodes (AMD EPYC 9654P, 96 cores; 16 MPI ranks per task).

**Re-analyse from the committed records (no new compute).**

`results/` (replay validation and option grades):

1. Validation: `python3 fast_path/replay.py --validate` (the `--out` default is `fast_path/results/replay_validation.json`). Reads `paired_comparison_2/inputs/manifest2.json`, `paired_comparison_2/results/campaigns.jsonl` and `paired_comparison_2/f3_repair/results_raw/repair_gaps.json`; rebuilds each campaign with a leave-one-campaign-out library.
2. Option grades as committed (library without the guest ladders): `python3 fast_path/option_replay.py --lib3 '' --calls 16 --seeds 15 --out fast_path/results/option_replay_C.json` and `python3 fast_path/option_replay.py --lib3 '' --calls 8 --seeds 15 --out fast_path/results/option_replay_8calls.json`. Also reads `paired_comparison_3/parallel/ctde_logbook_seed.json`. With `--lib3 ''` the 24 missing entries are filled from stage ratios or the size law and the status is `provisional`, as in the committed files.
3. Option grades with the library completed: `python3 fast_path/option_replay.py` (defaults `--lib3 fast_path/results_lib3 --calls 16 --seeds 15 --out fast_path/results/option_replay.json`). Only records with role `missing` are merged; when no entry is filled the status becomes `final`. No committed output of this final run exists in the folder.
4. Packages: Python 3 standard library only.

Note: the committed `results/option_replay.json` and `results/option_replay_8calls.json` were written by an earlier version of `option_replay.py` without the CTDE_P2 arm (10 grade rows); the current script writes the 13-row layout of `results/option_replay_C.json`. Running step 3 overwrites `results/option_replay.json`.

`results_lib3/` (run-time library): the per-compound JSON records are themselves the measured data; they are read directly by step 3. A script comparing the three repeat ladders (MoS2-1T, ZrS2-1T, WS2-1T) with the grn061 records is not in the repository.

**Re-run the computation (`results_lib3/`).**

1. Inputs: the comparison No. 2 decks `paired_comparison_2/inputs/<compound>.f1.in`, `.f2.in`, `.f3.in` (8x8 supercells) and `paired_comparison_2/inputs/manifest2.json`; task list `fast_path/compounds.txt` (14 lines: 11 `missing`, 3 `repeat`; line index = array task id). No input builder is needed.
2. Pseudopotentials: GBRV ultrasoft PBE, downloaded from the GBRV site by `paired_comparison_3/parallel/stage_and_submit3.sh`: `ti_pbe_v1.4.uspp.F.UPF`, `zr_pbe_v1.uspp.F.UPF`, `hf_pbe_v1.uspp.F.UPF`, `mo_pbe_v1.uspp.F.UPF`, `w_pbe_v1.2.uspp.F.UPF`, `s_pbe_v1.4.uspp.F.UPF`, `se_pbe_v1.uspp.F.UPF`, `te_pbe_v1.uspp.F.UPF`. No hash file for these is in the folder.
3. Staging: a run directory `$SCRATCH/mpt_lib3` with `inputs/`, `pseudos/`, `logs/`, `results/`, plus `library_ladder.py`, `library.sbatch`, `compounds.txt` and `qe_retry.py` copied in (`stage_and_submit3.sh` does this over SSH).
4. Submission: `sbatch --export=ALL,MPT_LIB_ROOT=$SCRATCH/mpt_lib3 fast_path/library.sbatch` from the run directory. Request: `--account=<account> --partition=<partition> --qos=<qos>` (a granite guest partition), `--constraint=gen` (the AMD node family of grn061), 1 node, 16 tasks, 180 GB, 72 h, `--requeue`, `--array=0-13`. Modules: `openmpi/5.0.3 quantum-espresso/7.4 python/3.10.3`.
5. Each task runs `library_ladder.py` (no arguments): `pw.x` F1, F2, F3 with `mpirun -np 16 --bind-to none pw.x -nk 1`, timed by `/usr/bin/time -v`; on a solver failure `qe_retry.py` supplies the next diagonalisation. A requeued task skips converged stages. Records go to `$SCRATCH/mpt_lib3/results/<compound>.json` (host, processor model, wall time, peak per-rank memory, F3 gap).
6. Collection: copy `results/*.json` into `fast_path/results_lib3/` (no collection script is in the repository), then run step 3 of the re-analysis.
7. Observed cost: recorded call wall times sum to 969,455 s (269 task-hours at 16 cores, about 4,300 core-hours), excluding time lost to preemption; longest ladder TiTe2-2H, 46.5 h; five tasks were requeued once after preemption (MoSe2-2H, MoTe2-2H, TiTe2-2H, ZrS2-2H, ZrTe2-2H).

**Outputs.**

- `fast_path/results/replay_validation.json`
- `fast_path/results/option_replay.json`, `fast_path/results/option_replay_8calls.json`, `fast_path/results/option_replay_C.json`
- `fast_path/results_lib3/<compound>.json` (14 files)
- `fast_path/FAST_PATH.md` (summary)

**Checks.**

- `replay_validation.json`: 33 campaigns; same call set in 31, same order in 28; bill error median 0.88%, worst 4.14%; computing-centre ratio 1.149 replayed against 1.133 measured; paired bill sign agrees in 13 of 15.
- `option_replay_C.json` (16 calls, 15 seeds, provisional): CEDT_P4 without mask H ratio 1.157, PW60 10/15; with the 25% proportional mask 1.013, 7/15, timing identification 0.26; CTDE_P2 1.029, 9/15; CTCE 1.348; DTDE median makespan 30.2 h.
- `results_lib3/`: all 14 ladders finished with F1 to F3 converged on AMD EPYC 9654P nodes; for example MoSe2-2H F3 gap 1.684 eV, WS2-2H 2.002 eV.
- Known limits: run times depend on the processor model, so library entries from guest nodes and grn061 are comparable only within one node family; guest jobs can be preempted; the replay does not model new solver failures or contention beyond the measured 2 to 11%.

### `hybrid_arms/`: hybrid-mix, negotiation-only (ALT) and broker-collusion arms graded beside the four standard topologies

Level: simulated (wide base prior at x1 task scale) and simulated on measured inputs (measurement-informed posterior at x100 scale). The machine used for the committed run is not in the repository. All node-hours are simulated units.

**Re-analyse from the committed records (no new compute).**

1. Regenerate the figure from the committed per-world records:
   `python hybrid_arms/make_figure.py`
   Input: `hybrid_arms/hybrid_results.json` (keys `wide_prior_x1` and `posterior_x100`, each a list of 300 per-world dictionaries keyed by condition). Output: `hybrid_arms/fig_hybrid_arms.png` (written next to the script; any working directory).
2. The summary table in `hybrid_arms/RESULTS.md` and `hybrid_arms/hybrid_run.log` is printed only by `hybrid_study.py` after a full run; no separate table script is committed. The same means can be read from the JSON, for example:
   `python -c "import json,numpy as np; d=json.load(open('hybrid_arms/hybrid_results.json')); r=d['posterior_x100']; print({c: round(np.mean([w[c]['win_win_redesigned'] for w in r]),3) for c in d['conds']})"`
   (replace `win_win_redesigned` by `leak_ok`, `pw_rate`, `win_win`, `r_mi_auc` or `h_rank_corr`; the labels-per-node-hour ratio is the per-world mean of `labels_per_nh` divided by the `DTDE_P4` value).

Python packages: numpy, scipy (imported by the simulator), matplotlib.

**Re-run the computation.**

1. From the repository root:
   `python hybrid_arms/hybrid_study.py > hybrid_arms/hybrid_run.log`
   Environment variables read: `HYB_WORLDS` (default 300), `HYB_PROCS` (default: all CPU cores), `MPT_HARD_CAP` (set to `1` by the script unless already defined; keep it at `1` to reproduce the strict 500 node-hour budget per campaign).
2. The script imports `prior_predictive/simulator.py` (30 paired seeds per world fixed by its constant `S`, 80 rounds at most) and runs 13 conditions (CTCE-P0, DTDE-P4, CTDE-P2/P3/P4, CEDT-P2/P3/P4, HYB-P2/P3, ALT-P4, and the two collusion variants; P3 uses epsilon = 2) on identical worlds, first on the `base` prior card at x1, then on a `posterior` card at x100 with `OVERHEAD_NH = 0.02`.
3. Committed measured inputs read: `stage2_twin_fit/twin_fit.json` (measured cost coefficients, electron exponent, residual spread), `pilot/results/pilot_fit.json` (parallel-efficiency exponent and quirk spread), and `prior_predictive/candidates/candidates.json` (public candidate metadata).
4. Random-seed handling: every world is drawn from `numpy.random.default_rng(crc32("<card>:<world>"))`, and the posterior perturbation from `crc32("post:<card>:<world>")`; all per-seed noise fields are drawn inside the world, so every condition shares common random numbers. No global random state is used.
5. Output: the script overwrites `hybrid_arms/hybrid_results.json` (hard-coded path next to the script). Runtime and hardware are not in the repository.

**Outputs.**

- `hybrid_arms/hybrid_results.json` (per-world records, both settings)
- `hybrid_arms/hybrid_run.log` (printed summary table)
- `hybrid_arms/fig_hybrid_arms.png`

**Checks.**

- Posterior x100, redesigned metrics: P(win-win) for CEDT-P4 0.920 (wide prior x1: 0.160); CEDT-P3 and HYB-P3 0.510; every other arm at most 0.003.
- P(all leakage limits hold): CEDT-P4 and CTDE-P4 1.000; ALT-P4 0.997 (wide prior 0.957); CEDT-P3 0.613 and HYB-P3 0.607, both 0.000 under collusion.
- Labels per node-hour relative to DTDE-P4 (posterior): CTCE-P0 1.498, CEDT-P2 1.401, HYB-P2 1.400, CEDT-P3 and HYB-P3 1.282, CEDT-P4 1.179, ALT-P4 1.000.
- Seeding is fixed, so a rerun with the same package versions is expected to reproduce `hybrid_run.log` exactly; the repository does not record a verified rerun or the package versions.
- Limits stated in `RESULTS.md`: the hybrid interaction is modelled at the information level only, ALT is a single-channel stand-in for alternating offers, and collusion is scored rather than simulated as strategic behaviour.

### `contention_transfer_bench/`: co-tenant contention against task size, and cost-transfer probes on a defect supercell and a heterobilayer

Level: measured on hardware (CHPC granite node grn061, owner partition, one 64-core allocation with 380 GB node memory; two 32-rank `pw.x` jobs share the node in the co-tenant runs; CPU only).

**Re-analyse from the committed records (no new compute).** Python 3 with `numpy`.

1. `python3 contention_transfer_bench/analyze_bench.py` (no arguments). Reads `contention_transfer_bench/results/bench_results.jsonl`; writes `contention_transfer_bench/results/bench_analysis.json` and prints it.
   - Contention: mean co-tenant wall over mean solo wall for the TiS2_1T job at each scale (s1, s2, s3), over 2 repeats.
   - Transfer: power law `wall = A × nelec^p` fitted to the solo and partner MX2 points of the same job, then measured over predicted wall for the two probes.
2. `paired_comparison_1/plot_live.py` reads `bench_analysis.json` for its fourth panel (outside this folder).

**Re-run the computation.**

1. Inputs:
   - Contention runs use the 6×6 k-grid supercell decks of `scale_validation/inputs/` (`TiS2_1T_s{1,2,3}_k6`, `MoSe2_2H_s{1,2,3}_k6`), built by `scale_validation/build_scale_inputs.py` (see that folder).
   - Transfer probes: `python3 contention_transfer_bench/build_transfer_inputs.py` (no arguments) writes `contention_transfer_bench/inputs/MoS2_3x3_Svac.pw.in` (3×3 MoS2 with one S vacancy, 53 atoms) and `contention_transfer_bench/inputs/MoS2_WS2_hetero_2x2.pw.in` (2×2 bilayer with the second-layer Mo replaced by W, 24 atoms). It reads the relaxed MoS2_2H lattice and positions from `dft_campaign/results/campaign_summary.json` and the vacuum from `prior_predictive/candidates/candidates.json` (both in the repository). Settings: ecutwfc 45 Ry, ecutrho 360 Ry, cold smearing 0.015 Ry, conv_thr 1e-7, 4×4×1 grid.
2. Pseudopotentials: GBRV ultrasoft PBE (`mo_pbe_v1.uspp.F.UPF`, `w_pbe_v1.2.uspp.F.UPF`, `s_pbe_v1.4.uspp.F.UPF`, plus `ti_pbe_v1.4.uspp.F.UPF` and `se_pbe_v1.uspp.F.UPF` for the contention decks). Hashes: `pilot/results/pseudos_manifest.txt`. Not in the repository; download from the GBRV site.
3. Software: Quantum ESPRESSO 7.4, modules `openmpi/5.0.3 quantum-espresso/7.4 python/3.10.3`. Python 3.10 is required: a first submission failed under the cluster's default Python 3.6 (`time.time_ns` missing; log `contention_transfer_bench/results/bench_1919941.log`, no QE run started).
4. Staging: create a directory `$SCRATCH/mpt_bench` containing `bench.py`, `bench.sbatch`, `inputs/` (the 2 probe decks plus the 8 decks of `scale_validation/inputs/`) and `pseudos/`. `paired_comparison_1/stage_and_submit.sh` performs this staging over SSH together with another job; its connection set-up is site-specific.
5. Submit: `sbatch --export=ALL,MPT_BENCH_ROOT=$SCRATCH/mpt_bench bench.sbatch` (1 node, 64 tasks, 4 h wall; replace `--account`, `--partition`, `--qos` by `<account>`, `<partition>`, `<qos>`). `bench.sbatch` sets the cost guard `MPT_BENCH_NH_CAP=5` and runs `python3 bench.py`.
6. Run order inside `bench.py`: for each of 2 repeats and each scale s1, s2, s3: TiS2_1T solo (32 ranks, `-nk 2`); then MoSe2_2H of the same scale started, 2 s later TiS2_1T started alongside it (32 + 32 ranks); then the two probes solo. Each run appends one record (wall, convergence, RAM per process, electrons) to `results/bench_results.jsonl`.
7. Collect `results/bench_results.jsonl` and `bench_<jobid>.log` into `contention_transfer_bench/results/` (`paired_comparison_1/collect_live.sh` does this), then run `analyze_bench.py`.
8. Observed cost: job 1919944, 22 min 30 s wall, 20 SCFs; the driver's own tally is 0.238 node-hours (`ranks / 64 × wall`, final log line), while `contention_transfer_bench/RESULTS.md` reports about 0.35 node-hours including the co-tenant pairs.

**Outputs.**

- `contention_transfer_bench/results/bench_results.jsonl`
- `contention_transfer_bench/results/bench_analysis.json`
- `contention_transfer_bench/results/bench_1919944.log` (completed run), `contention_transfer_bench/results/bench_1919941.log` (failed first submission)
- Summary: `contention_transfer_bench/RESULTS.md`

**Checks.**

- All 20 SCFs converged.
- Co-tenant interference factors: s1 1.064, s2 1.110, s3 1.076 (solo 3.12 s, 26.55 s, 141.2 s). Interference stays between 6 % and 11 % and does not grow with size up to 27 atoms and 216 electrons.
- MX2 power-law exponent 1.648. Transfer ratios (measured over predicted): `MoS2_3x3_Svac` 0.527 (161 s against 306 s, 462 electrons); `MoS2_WS2_hetero_2x2` 0.438 (36 s against 82 s, 208 electrons).
- Limits: single-node contention only (no inter-node measurement); 2 repeats per scale; absolute times and interference depend on the node's memory bandwidth and on any other load present during the run.

### `paired_comparison_1/`: preregistered live paired comparison of CEDT-P4 against DTDE with Quantum ESPRESSO on 3x3 MX2 supercells, plus executed timing attacks on the wire log

Level: measured on hardware. One whole node (granite `grn061`, 64 cores, CPU only; the node's GPU was not used), single SLURM allocation, 480 `pw.x` calls, 19.8 h wall, 9.41 node-hours.

**Re-analyse from the committed records (no new compute).** Python 3.8 or later; `analyze_live.py` uses the standard library only, `wire_attack.py` needs `numpy`, `plot_live.py` needs `numpy` and `matplotlib`. All three resolve paths relative to their own directory, so they can be run from the repository root. Each one overwrites its committed output in `paired_comparison_1/results/`; compare against the committed version (or run on a copy of the folder).

1. Preregistered grading (fixed before submission): `python3 paired_comparison_1/analyze_live.py`. Reads `paired_comparison_1/results/campaigns.jsonl`, prints the per-seed node-hours-to-first-qualifier table and writes `paired_comparison_1/results/live_grading.json`. Criteria in the script: R passes if CEDT-P4 has lower node-hours-to-first-qualifier in at least 0.60 of the paired seeds (a campaign without a qualifier scores its total spend), with a one-sided sign test; H passes if pooled valid F2 labels per node-hour are at least 1.05 times DTDE and the failure rate is at most DTDE + 0.04.
2. Executed timing attacks: `python3 paired_comparison_1/wire_attack.py`. Reads `paired_comparison_1/results/campaigns.jsonl` (it uses only the wire fields `cls` and `wall_s` per opaque ID as attacker input, and the `candidate` field only as scoring truth); writes `paired_comparison_1/results/wire_attack_results.json`. Leave-one-seed-out per arm: (a) exact candidate identity by nearest median log wall time per class, limit prior + 0.05; (b) membership inference AUC, limit 0.60. The 480-row wire view itself is `paired_comparison_1/results/wire_log.jsonl`.
3. Figure: `python3 paired_comparison_1/plot_live.py`. Reads `campaigns.jsonl`, `live_grading.json`, `wire_attack_results.json` and `contention_transfer_bench/results/bench_analysis.json` (panel D, co-tenant contention, produced by the separate `contention_transfer_bench/` study); writes `paired_comparison_1/results/fig_live_comparison.png`.

**Re-run the computation.**

1. Inputs: `python3 paired_comparison_1/build_live_inputs.py` (no arguments). Reads `dft_campaign/results/campaign_summary.json` (relaxed 1x1 geometries and lattice constants) and `prior_predictive/candidates/candidates.json`; writes 87 decks `paired_comparison_1/inputs/<name>.f{1,2,3}.in` and `inputs/manifest.json` (29 candidates; HfSe2_2H skipped, no converged relaxation). Decks: 3x3 in-plane supercells, `ibrav = 4`, c = 18 Å, PBE via GBRV ultrasoft pseudopotentials, cold smearing 0.015 Ry, `mixing_beta = 0.3`, `ecutrho = 8 ecutwfc`. F1 SCF 40 Ry, 2x2x1 k, `conv_thr 1e-6`; F2 SCF 45 Ry, 4x4x1 k, `1e-8`; F3 NSCF 45 Ry, 6x6x1 k, `nbnd = nelec/2 + max(8, 0.2 nelec)`. Full setup table: `paired_comparison_1/JOB_SETUP.md`.
2. Pseudopotentials: GBRV 1.5 USPP files `ti_pbe_v1.4`, `zr_pbe_v1`, `hf_pbe_v1`, `mo_pbe_v1`, `w_pbe_v1.2`, `s_pbe_v1.4`, `se_pbe_v1`, `te_pbe_v1` (`.uspp.F.UPF`), from `https://www.physics.rutgers.edu/gbrv/`, placed in `<staging dir>/pseudos/` (the driver symlinks this into every work directory). Not redistributed in the repository.
3. Software: modules `openmpi/5.0.3 quantum-espresso/7.4 python/3.10.3`. Python 3.8 or later is required on the compute node (the driver uses the walrus operator, and `analyze_live.py` uses `math.comb`; a first submission under the cluster default Python 3.6.8 died with a `SyntaxError` before any QE call, log `results/live_1919942.log`). `/usr/bin/time -v` must exist (peak RSS per call).
4. Staging and submission: `paired_comparison_1/stage_and_submit.sh` copies `live_campaign.py`, `live.sbatch`, `analyze_live.py`, `inputs/` and the pseudopotentials to `$SCRATCH/mpt_live` on the login node through an existing SSH ControlMaster (`CHPC_USERNAME` must be set; the login helper is not in this folder), then submits `sbatch --export=ALL,MPT_LIVE_ROOT=$SCRATCH/mpt_live,MPT_LIVE_NH_CAP=100 live.sbatch`. The same script also stages and submits the separate `contention_transfer_bench/` job first; to reproduce only this study, run the live part by hand.
5. `live.sbatch`: `--account=<account> --partition=<partition> --qos=<qos>`, `--nodes=1 --ntasks=64 --time=120:00:00` (whole node; node-hours are charged as wall x ranks / 64, which assumes whole-node accounting). It sets `MPT_LIVE_SEEDS=10`, `MPT_LIVE_MAX_CALLS=24`, `MPT_LIVE_CAMPAIGN_NH=5.0` and defaults `MPT_LIVE_NH_CAP=100`, then runs `python3 live_campaign.py`. Memory per call is not requested explicitly.
6. Driver `live_campaign.py`: for seed s in 0..9 the 29 candidates are shuffled with `random.Random(1000 + s)`; both arms replay the same order and inputs (DTDE first on even seeds, CEDT-P4 first on odd seeds). Execution configs (`mpirun -np`, `pw.x -nk`): DTDE 32/1 for every class; CEDT-P4 F1 16/1, F2 32/2, F3 32/4. Each candidate runs F1, F2, F3; an F1/F2 non-convergence stops that candidate; the F3 PBE gap qualifies if in [1.0, 2.0] eV. A campaign stops at 24 calls, 5 nh, or the global cap. Opaque IDs are `sha1("mpt-live-2026-09-09:<seed>:<name>")[:10]`. Writes `results/campaigns.jsonl`, `results/wire_log.jsonl` (appended, so start from an empty `results/`), `results/progress.json`, `results/live_summary.json`, and `live_<jobid>.log`; wavefunction directories are deleted after each candidate.
7. Collection: `paired_comparison_1/collect_live.sh` copies the four result files and `live_*.log` from `$SCRATCH/mpt_live` into `paired_comparison_1/results/` (and the bench results into `contention_transfer_bench/results/`). Then run the three analysis steps above.

Observed cost: 480 QE calls, 9.41 node-hours (cap 100), 19 h 49 min wall, 0.36 to 0.66 nh per campaign.

**Outputs.**
- `paired_comparison_1/results/campaigns.jsonl` (20 campaigns with per-job records and truth)
- `paired_comparison_1/results/wire_log.jsonl` (480 wire rows)
- `paired_comparison_1/results/live_summary.json`, `progress.json`, `live_1919945.log`
- `paired_comparison_1/results/live_grading.json`
- `paired_comparison_1/results/wire_attack_results.json`
- `paired_comparison_1/results/fig_live_comparison.png`

**Checks.**
- Every campaign made 24 calls and 8 valid F2 labels; total 480 calls, 9.411 nh, 19.82 h wall (`live_summary.json`).
- R: CEDT-P4 wins 6 of 10 pairs (seeds 1, 2, 4, 6, 8, 9), `pw_rate` 0.60, one-sided sign test p = 0.377; passes the bar exactly at the boundary.
- H: labels per node-hour ratio 1.005 (required 1.05), fail; failure rate 0.029 (CEDT-P4) against 0.033 (DTDE), pass. `preregistered_success: false`.
- Timing attacks: 27 candidates reached across campaigns (prior 0.037, identity limit 0.087); identity accuracy 0.9625 (n = 80) and membership AUC 1.000 in both arms; both limits breached. The timing channel was preregistered as accept-and-measure, so this is reported, not graded as a pass.
- Limits: wall times depend on the node, its load and the MPI build; the node partition was empty at submission and no co-tenant was recorded, so the timing fingerprints reflect a quiet dedicated node. The identity attack assumes labeled reference timings for the public candidate pool. Exact per-seed winners can change under re-run because the paired differences are a few percent of node-hours.

### `paired_comparison_2/`: preregistered live paired comparison No. 2 (DTDE against CEDT-P4 with one memory bit) as memory-reservation packing policies, Quantum ESPRESSO on 8x8 MX2 supercells, with pre-study, void first attempt, F3 repair pass, fallback regrade and timing attacks

Level: measured on hardware (granite node `grn061`, 64 cores, 380 GB, CPU-only `pw.x`, GPU unused; one whole-node allocation per window), except `prestudy/`, which is simulated (pure NumPy scheduler model, no QE). Arms differ only in the memory reserved per job; billing is TRES-style, billed pc-nh = wall_h x max(16/64, reserved_GB/380).

**Re-analyse from the committed records (no new compute).** Python 3.8 or later (`math.comb`). `analyze_live2.py`, `fallback_regrade.py`, `repair_regrade.py`, `deviation_comparison.py` use the standard library only; `wire_attack2.py` and `prestudy/prestudy.py` need `numpy`; `plot_final.py` and `prestudy/make_figure.py` need `matplotlib`. Every script resolves defaults relative to its own directory and overwrites its committed output, so compare against the committed version (or work on a copy of the folder). Run from the repository root in this order:

1. Preregistered grading (committed before submission): `python3 paired_comparison_2/analyze_live2.py` (optional argument: results directory). Reads `paired_comparison_2/results/campaigns.jsonl` (33 campaigns: 15 DTDE, 15 CEDT_P4, 3 CEDT_P4_UNMASKED replays), writes `paired_comparison_2/results/graded.json`. Rules: PW60 (CEDT wins a pair iff it has a first qualifier and DTDE has none or a higher billed cost to it; both-none pairs are non-wins; one-sided sign test); H = pooled F2 labels per billed pc-nh, CEDT/DTDE >= 1.05; masking price on seeds 0 to 2. On the as-run transcript PW60 is 0/15 because no F3 produced a gap (see Checks).
2. Fallback regrade (deviation D-2026-09-22-B, folded 1x1 gap at F2 completion): `python3 paired_comparison_2/fallback_regrade/fallback_regrade.py paired_comparison_2/results/campaigns.jsonl paired_comparison_2/fallback_regrade/results`. Give the output directory: the default `results_midrun/` is the location of an earlier interim grade that is not part of this repository. Reads `gap_1x1_ev` from `inputs/manifest2.json` (13 of 29 candidates have none).
3. Repair regrade (amendment D-2026-09-22-A, primary R-side grade): `python3 paired_comparison_2/f3_repair/repair_regrade.py paired_comparison_2/results/campaigns.jsonl paired_comparison_2/f3_repair/results_raw/repair_gaps.json paired_comparison_2/f3_repair/results`. The second argument must be given: the default `paired_comparison_2/results_repair/repair_gaps.json` is the on-cluster location and is not in the repository. Each failed F3 record is replaced by the measured 8x8 gap and cost (f3_wall + hold)/3600 x frac(original res_gb), hold 300 s for masked CEDT campaigns. Writes `f3_repair/results/repair_graded.json`.
4. Deviation comparison (prediction P-2026-09-22, repair PW60 >= fallback PW60): `python3 paired_comparison_2/f3_repair/deviation_comparison.py paired_comparison_2/fallback_regrade/results/fallback_graded.json paired_comparison_2/f3_repair/results/repair_graded.json paired_comparison_2/f3_repair/results_raw/repair_gaps.json paired_comparison_2/f3_repair/results` (third argument again required). Writes `f3_repair/results/deviation_report.json`.
5. Timing attacks on the quantized wire log: `python3 paired_comparison_2/wire_attack2.py` (no arguments). Reads `results/wire_log.jsonl` (264 rows) and `inputs/manifest2.json`; recovers ground truth from the salted hash in `live2_campaign.py`; leave-one-seed-out identity attack (limit 1/29 + 0.05) and membership AUC (limit 0.60) per arm on successful F1/F2 rows. Writes `results/wire_attack_results.json`. Do not feed the void wire log to it.
6. Figure: `python3 paired_comparison_2/final/plot_final.py`; reads `f3_repair/results/repair_graded.json`, `f3_repair/results_raw/repair_gaps.json`, `inputs/manifest2.json`, `results/wire_attack_results.json`; writes `final/fig_attempt2_verdict.png`.
7. Pre-study (simulated): `python3 paired_comparison_2/prestudy/prestudy.py` reads `dft_campaign/results/outcomes.jsonl` (measured 1x1 walls and qualifier flags) and writes `prestudy/prestudy_results.json` (defaults 400 worlds, 20 pairs, 12 calls, scales 6,7,8, seed 20260911). Environment: `MPT_WORLDS`, `MPT_PAIRS`, `MPT_CALLS`, `MPT_SCALES`, `MPT_TAG` (file suffix); the variants are e.g. `MPT_CALLS=8 MPT_PAIRS=15 MPT_TAG=_c8p15`, likewise `_c8p20`, `_c12p15`. Then `python3 paired_comparison_2/prestudy/make_figure.py` writes `prestudy/fig_prestudy.png`. The `prestudy_results_postcofit*.json` files used refit priors (s 0.76 to 0.84, c 0.02 to 0.05 from the co-scheduling probe in `cofit_probe/`); the script version with those priors is not in the repository (the committed `prestudy.py` hard-codes the pre-probe priors s 0.35 to 0.50, c 0.05 to 0.12).

**Re-run the computation.**

1. Inputs: `python3 paired_comparison_2/build_live2_inputs.py` (no arguments). Reads the 3x3 decks and `manifest.json` in `paired_comparison_1/inputs/`, recovers the relaxed 1x1 motif, and writes 87 decks `paired_comparison_2/inputs/<name>.f{1,2,3}.in` plus `inputs/manifest2.json` (29 candidates, HfSe2_2H excluded; 192 to 384 atoms; RAM estimates 75 to 138 GB, median 98.9 GB, 14 high-bit). Decks: 8x8 supercells, `ibrav = 4`, PBE GBRV USPP, cold smearing 0.015 Ry, `mixing_beta = 0.3`, Davidson, `K_POINTS automatic 1 1 1` (not the Gamma trick). F1 SCF 40/320 Ry, `conv_thr 1e-6`; F2 SCF 45/360 Ry, `1e-8`; F3 NSCF 45/360 Ry, `nbnd = int(1.10 nocc) + 16`.
2. Pseudopotentials: GBRV `ti_pbe_v1.4`, `zr_pbe_v1`, `hf_pbe_v1`, `mo_pbe_v1`, `w_pbe_v1.2`, `s_pbe_v1.4`, `se_pbe_v1`, `te_pbe_v1` (`.uspp.F.UPF`) from `https://www.physics.rutgers.edu/gbrv/`, fetched by the staging script into `$SCRATCH/mpt_live2/pseudos/`; not redistributed.
3. Software: modules `openmpi/5.0.3 quantum-espresso/7.4 python/3.10.3`; `mpirun -np 16 --bind-to none pw.x -nk 1` per job; `/usr/bin/time -v` for peak RSS. The driver imports `qe_retry.py` from the project root (staged alongside it).
4. Staging and submission: `paired_comparison_2/stage_and_submit2.sh` (needs `CHPC_USERNAME` and an existing SSH ControlMaster to the granite login node; the login helper is outside this project tree). It copies `qe_retry.py`, `live2_campaign.py`, `live2.sbatch`, `analyze_live2.py` and `inputs/` to `$SCRATCH/mpt_live2`, compiles the driver, and submits window A: `sbatch --export=ALL,MPT_LIVE2_ROOT=$SCRATCH/mpt_live2,MPT_SEED_LO=0,MPT_SEED_HI=7,MPT_W_CAP=280,MPT_QUANT=600 live2.sbatch`, then window B with `--dependency=afterany:<A>` and `MPT_SEED_LO=8,MPT_SEED_HI=14,MPT_W_CAP=240,MPT_QUANT=600,MPT_REPLAY_SEEDS=0:1:2`. Total cap 520 billed pc-nh.
5. `live2.sbatch`: `--account=<account> --partition=<partition> --qos=<qos> --nodes=1 --ntasks=64 --mem=0 --time=320:00:00`. `--mem=0` (whole-node memory) is required: without it the void first attempt received the 125 GB partition default.
6. Driver `live2_campaign.py` (default multi-campaign mode; leave `MPT_CAMPAIGN` unset and `MPT_MASK=fixed`): seed s shuffles the 29 candidates with `random.Random(2000 + s)`; DTDE first on even seeds, CEDT_P4 first on odd seeds; 8 calls per campaign, at most 3 open ladders, deepest-ready-first; campaign cap `MPT_CAMP_CAP` 25 pc-nh; window cap `MPT_W_CAP` (launch refused if the projected bill would cross it). Reservations: DTDE 1.10 x class maximum x stage factor (f1 0.85, f2 1.00, f3 1.05); CEDT_P4 uses the maximum of its bit half; packing budget 342 GB and 64 cores. CEDT completions become visible at the next 600 s boundary (`MPT_QUANT`) and are billed until then; replay seeds run as `CEDT_P4_UNMASKED`. Qualifier: F3 gap in [1.0, 2.0] eV. Writes `results/campaigns.jsonl`, `results/wire_log.jsonl` (appended: start from an empty `results/`), `results/progress.json`, `results/summary_w<lo>_<hi>.json`. The committed driver keeps each save directory until the ladder ends (the fix of the F3 bug) and also contains the solver-retry rule and the arms and options of comparison No. 3; the exact as-run attempt-2 driver revision is not in the repository.
7. F3 repair pass (only needed to reconstruct attempt 2; a re-run with the fixed driver measures F3 directly): `paired_comparison_2/f3_repair/submit_repair.sh` stages `repair_driver.py` and `repair.sbatch` and submits `sbatch --dependency=afterany:<window B> --export=ALL,MPT_LIVE2_ROOT=$SCRATCH/mpt_live2,MPT_REPAIR_CAP=80 f3_repair/repair.sbatch` (same module stack, `--ntasks=64 --mem=0 --time=144:00:00`). The driver takes every candidate with an F3 record in `results/campaigns.jsonl` (`MPT_REPAIR_SCOPE=attempted`, or `all`), runs F2 then F3 heaviest first, at most 2 streams within 342 GB, and writes `results_repair/repair_gaps.json`, `repair_progress.json` and `f3_outputs/`.
8. Collection: no collection script is in the repository; copy the result files listed under Outputs from `$SCRATCH/mpt_live2/` (and `results_repair/` into `f3_repair/results_raw/`), then run the re-analysis steps above.

Observed cost (attempt 2): window A 173.9 h wall, 107.3 billed pc-nh, 128 calls; window B 167.4 h wall, 101.1 pc-nh, 136 calls; repair pass about 2 d 3 h wall, 29.8 pc-nh, 18 candidates, cap not reached. Void attempt 1: about 56 node-hours wall, about 26 driver-billed pc-nh. Total about 264 of the 520 pc-nh cap.

**Outputs.**
- `paired_comparison_2/results/campaigns.jsonl`, `wire_log.jsonl`, `progress.json`, `summary_w0_7.json`, `summary_w8_14.json`, `graded.json`, `wire_attack_results.json`
- `paired_comparison_2/f3_repair/results_raw/repair_gaps.json`, `repair_progress.json`; `f3_repair/results/repair_graded.json`, `deviation_report.json`
- `paired_comparison_2/fallback_regrade/results/fallback_graded.json`
- `paired_comparison_2/void_run_1948457/` (void attempt records, `VOID_RUN.md`, two driver logs)
- `paired_comparison_2/final/RESULTS.md`, `fig_attempt2_verdict.png`; `paired_comparison_2/prestudy/prestudy_results*.json`, `fig_prestudy.png`, `RESULTS.md`

**Checks.**
- H (`graded.json`): 40 F2 labels per arm, billed 100.68 (DTDE) and 88.84 (CEDT_P4) pc-nh, ratio 1.133, pass; corrected for repaired F3 costs 1.207 (`repair_graded.json`).
- R: preregistered analyzer as run 0/15; repair grade 5/15 = 0.333, sign p = 0.941, fail; fallback grade 5/15, fail (mid-run 1/9 = 0.111). Deviation report: prediction holds as a tie, 2 verdict flips, 3 first-qualifier identity changes, 0 window flips.
- Masking price (seeds 0 to 2): +3.01 %, +7.15 %, +2.73 % billed.
- Attacks: CEDT_P4 identity accuracy 0.585 (n = 53), AUC 0.935; DTDE 0.78 (n = 50), AUC 0.989; limit 0.0845 and 0.60, all breached. The unmasked replay (n = 11) is too small for a separate estimate.
- Repaired gaps: HfS2_1T 1.329 eV, ZrS2_1T 1.199 eV, MoS2_2H 1.734 eV, WSe2_2H 1.812 eV, HfS2_2H 1.034 eV; Gamma-only F3 sampling widens the 2H direct gaps relative to 1x1.
- Pre-study (simulated): 6x6 is a structural null; at 8x8 predicted H gain 1.131 [1.06, 1.16], P(H >= 1.05) 0.95; post-refit 1.145 with budget 432 [376, 512] pc-nh for 8 calls x 15 pairs.
- Known limits: the void first attempt (jobs 1948457/1948458) ran without a memory request, received 125 GB, and nearly every QE call was OOM-killed (153 and 102 oom_kill events); its data are discarded. In attempt 2 the driver deleted save directories after every call, so all as-run F3 calls failed; the repair pass re-measured one F2+F3 per affected candidate and reconstructs costs with an expected 300 s hold and the transcript's launch order. Walls depend on the node, MPI build and co-tenants (contention 2.4 to 3.9 % measured); the masked replay ran days after the originals; 8 calls per campaign leave 8 of 15 pairs without any confirmed qualifier.

### `paired_comparison_3/`: paired comparison No. 3, four disclosure arrangements (DTDE, CEDT_P4, MIX50, CTDE_P2) x 15 seeds of live 8x8 MX2 Quantum ESPRESSO campaigns on guest nodes, with the corrected candidate list, an out-of-memory repair pass, notchpeak site-bridge copies, the final grade and the timing attack

Level: measured on hardware. One campaign per SLURM job, 64 MPI ranks (four 16-rank pw.x streams at most), on preemptible zero-charge guest nodes: CHPC granite guest nodes (AMD Genoa, `--constraint=gen`, 96 cores, e.g. EPYC 9654P) until 9 Oct 2026, then notchpeak guest nodes (AMD Genoa, 64 to 192 cores, EPYC 9554, 9654 and 9334 among others; 384 GB to 1.5 TB). The node and processor model of every campaign are recorded in `progress.json`/`campaigns.jsonl` and summarised in `paired_comparison_3/pair_sites.json`. The timing attack and grading are analyses of the committed records.

**Re-analyse from the committed records (no new compute).** Python 3.10 or later; standard library, plus `numpy` for the timing attack. Every script resolves its paths from its own folder, so the commands below work from the repository root. Each one overwrites its committed output in place; compare against the committed version with a version-control diff.

1. Corrected candidate list: `python3 paired_comparison_3/build_candidate_list.py` reads `dft_campaign/results/outcomes.jsonl`, `stacking_study/results_2088961/outcomes.jsonl` and `paired_comparison_2/inputs/manifest2.json`; writes `paired_comparison_3/candidates_corrected.json` (gap window 1.0 to 2.0 eV, lists `q_first_pass`, `q_single_layer`, `q_bilayer_AA`, `q_bilayer_3R`) and `paired_comparison_3/candidates_corrected_check.json`. The committed check file covers the 13 campaigns collected by 4 Oct; a rerun now covers every `collected_*` snapshot (first line of each `campaigns.jsonl`), so only the list file is expected to match.
2. Pair sites: `python3 paired_comparison_3/pair_sites.py` reads `paired_comparison_3/collected_*/*/campaigns.jsonl` (a later snapshot replaces an earlier one) and writes `paired_comparison_3/pair_sites.json` (host, cluster, CPU model, SLURM job per campaign; same-site flag per pair).
3. Preregistered grade (preregistered rule of `paired_comparison_2/analyze_live2.py`): `python3 paired_comparison_3/grade_both_lists.py` reads the same snapshots and `candidates_corrected.json`; writes `paired_comparison_3/graded_both_lists.json`: computing-centre metric (pooled F2 labels per billed per-core node-hour, pc-nh, ratio to DTDE) and research-side PW60 pair wins under (a) the as-run in-campaign gap test, (b) the corrected single-layer list, (c) the D3 AA' and 3R bilayer lists, with a one-sided sign-test p.
4. Final grade: `python3 paired_comparison_3/final_grade_2026-10-14.py` reads only `paired_comparison_3/collected_2026-10-14/` and `paired_comparison_3b/collected_2026-10-14/` plus each folder's `pair_sites.json` (run step 2 and `python3 paired_comparison_3b/pair_sites.py` first); writes `paired_comparison_3/final_grade_2026-10-14.json` (all 15 pairs, same-processor subset, first qualifiers).
5. Timing attack (registered in `TIMING_ATTACK_PLAN.md` and `parallel/OPTION_C.md`, prediction P-2026-10-01 item 3): `python3 paired_comparison_3/wire_attack3.py` reads `collected_2026-10-14/<ARM>_s<seed>/{campaigns,wire_log}.jsonl` (asserts 60 campaigns), the 12 copies in `site_bridge_2026-10-14/` and the candidate names in `paired_comparison_2/inputs/manifest2.json` (opaque ids are reversed offline with the driver's salted SHA-1). It runs the leave-one-seed-out identity and membership attacks per arm and tests T1 to T4; writes `paired_comparison_3/timing_attack3.json`. Seed-bootstrap intervals: `python3 bootstrap_ci/seed_bootstrap3.py` (imports `wire_attack3.py`; writes `bootstrap_ci/seed_bootstrap3.json`).
6. CTDE_P2 seed logbook: `python3 paired_comparison_3/parallel/build_ctde_logbook.py` reads `paired_comparison_2/inputs/manifest2.json` and `paired_comparison_2/results/campaigns.jsonl`; writes `paired_comparison_3/parallel/ctde_logbook_seed.json` (bin-level maxima of 16 x peak rank RSS).

**Re-run the computation.**

1. Inputs: the No. 3 campaigns use the comparison No. 2 inputs unchanged, `paired_comparison_2/inputs/*.in` and `manifest2.json` (29 compounds, HfSe2-2H excluded; 1T cells 8x8 single layer, 192 atoms; 2H cells 8x8 PBE-spaced bilayer, 384 atoms), regenerated by `python3 paired_comparison_2/build_live2_inputs.py` (no arguments). Stages: F1 SCF 40/320 Ry, conv 1e-6; F2 SCF 45/360 Ry, conv 1e-8; F3 NSCF 45/360 Ry, nbnd = 1.10 x nocc + 16; all Gamma-only.
2. Pseudopotentials: GBRV PBE ultrasoft `ti_pbe_v1.4`, `zr_pbe_v1`, `hf_pbe_v1`, `mo_pbe_v1`, `w_pbe_v1.2`, `s_pbe_v1.4`, `se_pbe_v1`, `te_pbe_v1` (`.uspp.F.UPF`), downloaded from the GBRV site by `parallel/stage_and_submit3.sh`. No checksums are in the repository.
3. Software: modules `openmpi/5.0.3 quantum-espresso/7.4 python/3.10.3`; each stream runs `mpirun -np 16 --bind-to none pw.x -nk 1`.
4. Driver: `paired_comparison_2/live2_campaign.py` with `qe_retry.py` (Davidson to conjugate-gradient solver retry) staged next to it. Option A (DTDE, CEDT_P4), the site-bridge copies and the repair pass ran the earlier driver revision kept as `paired_comparison_3/oom_repair_2026-10-14/live2_campaign.py`; option C (MIX50, CTDE_P2) ran the committed `paired_comparison_2` revision, which adds only the MIX50 routing draw (`Random(f"{seed}:{compound}:{stage}") < 0.5`) and the CTDE_P2 logbook reservation (1.10 x largest recorded RAM per size bin and stage, capped at the DTDE worst case, seeded from `parallel/ctde_logbook_seed.json`). The driver models a 64-core, 380 GB node (packing budget 342 GB) and bills pc-nh = wall_h x max(16/64, reservation_GB/380).
5. Environment variables read by the driver (set with `sbatch --export`): `MPT_LIVE2_ROOT` (staging dir with `inputs/`, `pseudos/`), `MPT_RESULTS`, `MPT_WORK`, `MPT_CAMPAIGN=<ARM>:<seed>` (ARM in DTDE, CEDT_P4, MIX50, CTDE_P2; seeds 0 to 14), `MPT_MAX_CALLS=16`, `MPT_CAMP_CAP=25` (campaign cap, pc-nh), `MPT_W_CAP=30` (launch refused if the projected bill crosses it), `MPT_MASK=prop`, `MPT_MASK_FRAC=0.25` (completion time rounded up to 25 % of the expected run time, CEDT_P4 and routed MIX50 jobs only).
6. Batch file `parallel/live3_guest.sbatch`: 1 node, `--ntasks=64`, `--mem=372000M` (the 380 GB node the driver assumes), `--time=72:00:00`, `--requeue`, `--constraint=gen`, account and partition `<account>`, `<partition>` (a granite guest partition). A requeued job restarts its campaign; the lost attempt's wire rows go to `wire_log.lost.jsonl`.
7. Staging and submission (SSH to the login node, username in `CHPC_USERNAME`): `bash paired_comparison_3/parallel/stage_and_submit3.sh` stages `$SCRATCH/mpt_live3` and submits 30 option A jobs (also a 14-task library array for `fast_path/`, see that folder); `bash paired_comparison_3/parallel/stage_and_submit3c.sh` stages `$SCRATCH/mpt_live3c` and submits 30 option C jobs. Job-to-arm maps: `parallel/.live3_jobids`, `parallel/.live3c_jobids`.
8. Site move (sub-study `move_2026-10-09/`): `bash paired_comparison_3/move_2026-10-09/move41.sh test|go` (run on the cluster) resubmits every pending `l3_*`, `l3b_*` and `l3_oom_repair` job to notchpeak guest nodes (`-M notchpeak`, `--constraint=gen`; DTDE `--mem=372000M`, all other arms and the repair `--mem=500000M`) with identical `--export` settings, then cancels the granite copy; old to new ids in `JOBMAP.txt`. `move_2026-10-09/site_bridge.sh test|go` submits 12 `l3np_*` notchpeak copies (CEDT_P4 s0 and s13, DTDE s3 to s11 and s14) into `results_notchpeak/` and `work_notchpeak/`.
9. Out-of-memory repair (sub-study `oom_repair_2026-10-14/`): three CEDT_P4 calls were killed when three 2H streams shared a 372000M node (s3 ZrTe2_2H F1, s4 ZrSe2_2H F2, s7 TiSe2_2H F3). `oom_repair_driver.py` (staged with its own `live2_campaign.py` and `qe_retry.py`) reruns them concurrently, TiSe2_2H F2 first as prerequisite, sampling summed pw.x RSS every 15 s. `oom_repair.sbatch`: 64 tasks, `--mem=500000M`, `--constraint=gen&m768`, `--time=36:00:00`; env `MPT_REPAIR_DIR`, `MPT_REPAIR_OUT`, `MPT_LIVE2_ROOT`. It ran on notchpeak after the move. The repaired calls are recorded separately and are not folded into the campaign records or the grade (CEDT_P4 shows 3 fails).
10. Collection: copy each `<ARM>_s<seed>/` results directory (`campaigns.jsonl`, `wire_log.jsonl`, `wire_log.lost.jsonl` if present, `progress.json`) into `collected_<date>/`, and the notchpeak copies into `site_bridge_<date>/`; a collection script is not in the repository. Then run the analysis steps above.
11. Observed cost: per-campaign makespan 63,806 to 164,335 s (17.7 to 45.6 h, `progress.json`); billed totals in the driver's units, DTDE 316.5, CEDT_P4 299.7, MIX50 325.9, CTDE_P2 340.7 pc-nh (no allocation charge on guest partitions). Repair pass 75,708 s on notch492, peak job RSS 426.5 GB.

**Outputs.**

- `paired_comparison_3/FINAL_RESULTS.md`, `final_grade_2026-10-14.json`, `graded_both_lists.json`, `pair_sites.json`
- `paired_comparison_3/TIMING_ATTACK_RESULTS.md`, `timing_attack3.json`
- `paired_comparison_3/CANDIDATE_LIST.md`, `candidates_corrected.json`, `candidates_corrected_check.json`
- `paired_comparison_3/oom_repair_2026-10-14/results/oom_repair.json` and `results/work/*/*.time`
- Raw records: `collected_2026-10-14/` (all 60 campaigns), `site_bridge_2026-10-14/`

**Checks.**

- Computing-centre ratio vs DTDE, all 15 pairs (same-processor pairs): CEDT_P4 1.069 (1.102, n = 10), MIX50 0.959 (1.167, n = 3), CTDE_P2 0.929 (0.953, n = 6). DTDE 80 labels over 316.481 pc-nh; CEDT_P4 81 over 299.68.
- Research-side wins of 15 (as run): CEDT_P4 6, MIX50 3, CTDE_P2 2; PW60 needs 9, fails in every arm. All first qualifiers lie on the corrected single-layer list (nine compounds, same as the first pass).
- Timing attack, identity accuracy (membership AUC): DTDE 0.750 (0.945), CEDT_P4 0.484 (0.826), CTDE_P2 0.218 (0.672), MIX50 routed 0.174 (0.722); limits 0.084 and 0.60. T1 0.466 pass, T2 0.069 fail, T3 pass, T4 0.0152 pass.
- Repair: all three calls converged; TiSe2_2H F3 gap 0.4927 eV.
- Limits: guest nodes are shared with other users and preemptible (21 of 60 final campaigns carry a `wire_log.lost.jsonl`); pairs often ran on different clusters or processor models (5 of 15 CEDT_P4 pairs), so wall times and bills depend on hardware and co-tenants. Fifty pending jobs were moved from granite to notchpeak on 9 Oct with only the scheduler request changed; DTDE then requested 372000M and the other arms 500000M.

### `paired_comparison_3b/`: paired comparison No. 3b, the single-layer companion of No. 3 (DTDE vs CEDT_P4, 15 seeds, every cell an 8x8 single layer of 192 atoms, so the disclosed memory bit separates chemistry instead of layer count)

Level: measured on hardware. One campaign per SLURM job, 64 MPI ranks (16-rank pw.x streams), submitted to the CHPC granite guest partition (`--constraint=gen`) on 5 Oct 2026. Seeds 0 to 4 ran on the group-owned granite node grn061 (AMD EPYC 9554, 64 cores); seeds 5 to 14 were moved before starting to notchpeak guest nodes (AMD EPYC 9554, 9554P, 9654, 9654P, 9454). Node and processor model per campaign are in `paired_comparison_3b/pair_sites.json`. Grading is an analysis of the committed records.

**Re-analyse from the committed records (no new compute).** Python 3.10 or later, standard library only. Scripts resolve paths from their own folder; run from the repository root. Each overwrites its committed output in place.

1. Pair sites: `python3 paired_comparison_3b/pair_sites.py` reads `paired_comparison_3b/collected_*/*/campaigns.jsonl` (the later snapshot replaces the earlier) and writes `paired_comparison_3b/pair_sites.json`.
2. Preregistered grade: `python3 paired_comparison_3b/grade_3b.py` (same rule as `paired_comparison_3/grade_both_lists.py`, paths changed) reads the same snapshots and the qualifier lists in `paired_comparison_3/candidates_corrected.json`; writes `paired_comparison_3b/graded_3b_interim.json` (the file name is historical; the committed copy holds all 30 campaigns): pooled F2 labels per billed per-core node-hour (pc-nh) per arm and the ratio to DTDE, and PW60 pair wins under the as-run gap test, the corrected single-layer list and the two D3 bilayer lists.
3. Final grade with the same-processor subset and first qualifiers: `python3 paired_comparison_3/final_grade_2026-10-14.py`, which reads `paired_comparison_3b/collected_2026-10-14/` and `paired_comparison_3b/pair_sites.json` (key `No3b` in `paired_comparison_3/final_grade_2026-10-14.json`).

**Re-run the computation.**

1. Inputs: `python3 paired_comparison_3b/build_live3b_inputs.py` (no arguments) writes `paired_comparison_3b/inputs/<name>.f1/f2/f3.in` and `inputs/manifest2.json` (file name kept for the unchanged driver). It imports `paired_comparison_2/build_live2_inputs.py` (stage blocks, valence table, chalcogen factors) and reads `paired_comparison_1/inputs/manifest.json` and the 3x3 `*.f2.in` files there for the 1T layers (identical to No. 3), `paired_comparison_3b/mono2H_geometries.json` for the relaxed single 2H layers (c = 20 A; taken from the single-layer vc-relax of `stacking_study/`, job 2088961; the extraction script is not in the repository) and `paired_comparison_3/candidates_corrected.json` for the reference gaps. Pool: 29 compounds (TiS2-2H out, HfSe2-2H in). RAM model: 30.9 GB x (nelec/864)^1.55 x chalcogen factor/0.90 x c/18 A; `mem_bit` = 1 above the median (94.8 GB). Stages as in No. 3: F1 SCF 40/320 Ry, conv 1e-6; F2 SCF 45/360 Ry, conv 1e-8; F3 NSCF, nbnd = 1.10 x nocc + 16; Gamma-only.
2. Pseudopotentials: the GBRV PBE ultrasoft set of No. 3, copied from the No. 3 staging directory by the staging script (see `paired_comparison_3.md`).
3. Software: modules `openmpi/5.0.3 quantum-espresso/7.4 python/3.10.3`.
4. Driver: `paired_comparison_2/live2_campaign.py` with `qe_retry.py`, unchanged; arms DTDE and CEDT_P4, seeds 0 to 14, environment `MPT_LIVE2_ROOT`, `MPT_RESULTS`, `MPT_WORK`, `MPT_CAMPAIGN=<ARM>:<seed>`, `MPT_MAX_CALLS=16`, `MPT_CAMP_CAP=25`, `MPT_W_CAP=30`, `MPT_MASK=prop`, `MPT_MASK_FRAC=0.25` (see `paired_comparison_3.md` for their meaning).
5. Batch file `live3b_guest.sbatch`: 1 node, `--ntasks=64`, `--mem=372000M`, `--time=72:00:00`, `--requeue`, `--constraint=gen`, account and partition `<account>`, `<partition>` (granite guest class); runs `python3 live2_campaign.py` in `$MPT_LIVE2_ROOT`.
6. Staging and submission: `bash paired_comparison_3b/stage_and_submit3b.sh` (SSH control connection, username in `CHPC_USERNAME`, login host `CHPC_HOST`, default notchpeak, with `sbatch -M granite`) stages `$SCRATCH/mpt_live3b` (inputs, pseudopotentials, driver, `qe_retry.py`, batch file) and submits 30 jobs `l3b_<ARM>_s<seed>`. Job ids: `JOBIDS.txt`.
7. Run order as executed: the jobs waited behind a granite maintenance window; seeds 0 to 4 were run on grn061 through the group-owned partition (the resubmission commands are not in the repository); seeds 5 to 14 were moved unstarted to notchpeak guest nodes with `paired_comparison_3/move_2026-10-09/move41.sh` (same `--export`, `--mem=372000M` for DTDE, `--mem=500000M` for CEDT_P4; ids in that folder's `JOBMAP.txt`).
8. Collection: copy each `$SCRATCH/mpt_live3b/results/<ARM>_s<seed>/` (`campaigns.jsonl`, `wire_log.jsonl`, `progress.json`) into `collected_<date>/`; a collection script is not in the repository. Then run the analysis steps.
9. Observed cost: per-campaign makespan 39,512 to 77,291 s (11.0 to 21.5 h, `progress.json`); billed totals in the driver's units DTDE 150.6, CEDT_P4 156.5 pc-nh.

**Outputs.**

- `paired_comparison_3b/graded_3b_interim.json` (final 30-campaign grade)
- `paired_comparison_3b/pair_sites.json`
- Key `No3b` of `paired_comparison_3/final_grade_2026-10-14.json`, summarised in `paired_comparison_3/FINAL_RESULTS.md`
- `paired_comparison_3b/inputs/` (87 inputs, `manifest2.json`), raw records in `collected_2026-10-14/` (all 30 campaigns)

**Checks.**

- RAM estimates 75 to 130 GB, median 94.8 GB; 12 of 29 compounds carry the high bit (`inputs/manifest2.json`).
- Computing-centre ratio CEDT_P4/DTDE: 0.905 on all 15 pairs (DTDE 84 F2 labels over 150.598 pc-nh, CEDT_P4 79 over 156.523), 0.978 on the 7 same-processor pairs; no failed calls.
- Research-side wins of 15: 4 as run (2 both none), 5 on the single-layer list, 5 on the AA' bilayer list; PW60 fails.
- Registered predictions (`DESIGN.md`, P-2026-10-05): P3b-1 (ratio at least 1.05) fail; P3b-2 (within 0.10 of the No. 3 ratio 1.069) fail; P3b-3 (PW60 fails) pass; P3b-4 (all first qualifiers on the corrected single-layer list) pass.
- Limits: 8 of 15 pairs ran on different processor models, and wall times on shared guest nodes depend on co-tenants; one campaign (DTDE s11) records a nonzero restart count after preemption.

### `llm_agents/`: LLM agents (with and without optimisation tools) replace the scripted decision policies, paired against the scripted control

Level: simulated (all node-hours are simulated units). Both runs used locally served LLMs on a DGX Spark (aarch64, GB10 GPU) through an OpenAI-compatible vLLM server; the campaign engine is CPU-only and reuses `prior_predictive/simulator.py` (imported by `llm_agents/env.py` and `llm_agents/no_tools_run/llm_experiment.py` via a `sys.path` insert to the sibling folder).

**Re-analyse from the committed records (no new compute).** Python 3 with numpy and matplotlib. Scripts resolve paths relative to their own folder, so they run from the repository root.

1. Tool-using run, v2 (fixed toolbox, the reported result):
   `gunzip -k llm_agents/results/llm_grid_raw_v2.json.gz`
   `python llm_agents/analyze_llm.py --raw results/llm_grid_raw_v2.json --tag v2`
   Regenerates `llm_agents/results/llm_grid_summary_v2.json` (paired deltas, telemetry) and `llm_agents/results/llm_vs_scripted_v2.png`. Note `--raw` is relative to `llm_agents/`.
2. Tool-using run, v1 (toolbox before the memory-bound fix):
   `gunzip -k llm_agents/results/llm_grid_raw.json.gz`
   `python llm_agents/analyze_llm.py --raw results/llm_grid_raw.json`
   Regenerates `llm_agents/results/llm_grid_summary.json` and `llm_agents/results/llm_vs_scripted.png`.
3. Run without tools:
   `python llm_agents/no_tools_run/analyze_llm.py`
   Reads the hard-coded `llm_agents/no_tools_run/results/llm_results_v2.json` (no arguments) and regenerates `fig_llm_vs_scripted.png`, `fig_llm_behavior.png` and `summary_fragment.md` in the same folder.

**Re-run the computation.** Python 3 with numpy, scipy and httpx (plus the packages above for analysis).

1. Serve the models with vLLM (OpenAI-compatible API). The scripts append `/v1/chat/completions` to the base URL, so pass the URL without `/v1`, e.g. `http://<host>:<port>`.
   - Tool-using run: `Qwen/Qwen3-4B-Instruct-2507` plays both parties. vLLM version for this run is not recorded in the repository.
   - Run without tools: vLLM 0.28, two servers resident at once: party R `Qwen/Qwen3-4B-Instruct-2507`, party H `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4` (requests send `chat_template_kwargs: {enable_thinking: false}`).
2. Tool-using grid (3 conditions DTDE-P4, CEDT-P4, CTDE-P2; 3 prior cards x 3 worlds, world ids 200000 + 1000 x card + k; 2 seeds; budget 250 simulated nh, 40 rounds; temperature 0.2, max_tokens 350, per-request timeout 120 s):
   `python llm_agents/run_llm_grid.py --worlds-per-card 3 --seeds 2 --concurrency 24 --base-url http://<host>:<port> --model Qwen/Qwen3-4B-Instruct-2507 --temperature 0.2 --out results/llm_grid_raw_v2.json`
   then `gzip llm_agents/results/llm_grid_raw_v2.json`. `--out` is relative to `llm_agents/`. `--mock` runs a deterministic stand-in agent with no LLM server (pipeline test only).
3. Run without tools (4 conditions CTCE-P0, DTDE-P4, CEDT-P4, CEDT-P3 eps=2; 3 cards x 8 worlds, world ids 0 to 7; 2 seeds; temperature 0; max_tokens 200 for R and 220 for H; concurrency 32):
   `python llm_agents/no_tools_run/llm_experiment.py --worlds-per-card 8 --r-base http://<host>:<port_R> --h-base http://<host>:<port_H> --out results/llm_results_v2.json`
   The script also writes `llm_traces.json.gz` (one transcript, base world 0, CEDT-P4) next to `--out`. `--smoke` runs one world with 8 rounds.
4. Seeds: worlds and noise fields are drawn from `prior_predictive/simulator.py` with CRC32-derived seeds, and the tools seed their samplers from fixed offsets plus the round index, so the scripted arm is deterministic. The LLM arm depends on model sampling.
5. Runtime: the run without tools took 888 s wall (2,147 calls per seat). The wall time of the tool-using run is not recorded.

**Outputs.**
- `llm_agents/results/llm_grid_raw.json.gz`, `llm_grid_summary.json`, `llm_vs_scripted.png` (v1)
- `llm_agents/results/llm_grid_raw_v2.json.gz`, `llm_grid_summary_v2.json`, `llm_vs_scripted_v2.png` (v2)
- `llm_agents/no_tools_run/results/llm_results_v2.json`, `llm_traces.json.gz`, `fig_llm_vs_scripted.png`, `fig_llm_behavior.png`, `summary_fragment.md`

**Checks.**
- Tool-using v2, paired deltas (LLM minus scripted, n = 18 pairs per condition), labels/nh: DTDE-P4 +0.003, CEDT-P4 +0.001, CTDE-P2 +0.002 (se 0.003 each); memory-failure deltas +0.004 / +0.002 / -0.003. Telemetry: 1,656 LLM calls (R 944, H 712), 769 interactive tool calls, 0 parse fallbacks.
- Tool-using v1 memory-failure deltas: +0.025 / +0.038 / +0.043.
- Without tools: R-seat agreement with the scripted choice 36.0 %, H-seat 12.2 %; 0 fallbacks on either seat; CEDT-P3 (eps=2) membership-inference AUC 0.849 (LLM) vs 0.603 (scripted).
- Re-analysis from the committed records is bit-identical. Re-running the LLM arms reproduces results only statistically (sampling at temperature 0.2; batched serving is not guaranteed deterministic even at temperature 0).
- The v1 toolbox is not in the repository: `llm_agents/tools.py` contains the v2 fix (hard 64 GB memory bound in `config_montecarlo`), so a fresh run reproduces v2 only.
- The no-tools driver's default `--out` is `results/llm_results.json`, while the analysis script reads `results/llm_results_v2.json`; pass `--out` as above.
- Pilot scale (18 or 48 pairs per condition, one or two models); see the caveats in `llm_agents/RESULTS_LLM.md` and `llm_agents/no_tools_run/RESULTS.md`.

### `measured_attacks/`: executed membership and configuration-rank attacks on simulated transcripts and on the measured pilot

Level: two parts. (a) `attack_study.py`: simulated campaign transcripts (prior-predictive simulator, base prior card, CEDT topology) attacked by a trained model; run on a 2-core workstation, no cluster job. (b) `pilot_timing_attack.py`: analysis of committed records, the 81-job F1 pilot measured on CHPC granite node grn061 (64 cores, 380 GB RAM).

**Re-analyse from the committed records (no new compute).**

Python 3 with `numpy` and `scipy` (both scripts). Paths are resolved relative to each script's directory, so the commands work from the repository root. Each script overwrites its committed output; work in a fresh copy of the repository.

1. Configuration-rank extraction on the measured pilot:
   `python3 measured_attacks/pilot_timing_attack.py`
   - reads `pilot/results/pilot_results.csv` (columns `cand`, `ntasks`, `npool`, `agg`, `pw_wall_s`, `converged`; only rows with `converged` = 1 are used);
   - removes candidate fixed effects from log wall time, then runs a 200-replicate split-half resampling (`numpy.random.default_rng(41)`), scoring the P1-style attack (configuration identity visible) and the P4-style attack (timing residual only) by absolute Spearman correlation; limit 0.20;
   - prints and writes `measured_attacks/pilot_attack_results.json`.

**Re-run the computation.**

1. Simulated-transcript attacks:
   `python3 measured_attacks/attack_study.py > measured_attacks/attack_stdout.txt`
   - imports `prior_predictive/simulator.py` (transcripts captured through its `TRANSCRIPT_HOOK`; candidate metadata from `prior_predictive/candidates/candidates.json`) and `make_policy` from `decision_maker_leakage/dm_leakage.py`;
   - no command-line arguments; constants in the script: training worlds 0 to 119, test worlds 5000 to 5059, opaque-ID epoch 10 rounds, card `base`, topology `CEDT`, policies `greedy` and `depth_first`, mechanisms P2, P3 (epsilon 2, persistent IDs), P3 (epsilon 2, IDs rotated every 10 rounds), P4; 30 paired seeds per world (simulator constant `S`);
   - attacker: L2-regularized logistic regression (L2 1e-3, 400 gradient steps, rate 0.5); reported as within-campaign (macro) AUC and pooled AUC; rank extraction by split-half Spearman;
   - writes `measured_attacks/attack_results.json`; stdout is the content of `attack_stdout.txt`.
   - Environment: the simulator reads `MPT_HARD_CAP` (default `0`, soft budget stop) at import, before `dm_leakage.py` sets its own default, so the committed run used the soft stop unless the variable was set; `MPT_TRACE` only adds debug output.
   - Random state: the randomized-response stream is seeded with `hash((policy, label)) % 2**32`. Python randomizes string hashing per process, so P3 rows are reproducible only in distribution unless `PYTHONHASHSEED` is fixed; the value used for the committed run is not in the repository. P2 and P4 rows do not use that stream.
2. Pilot records: re-running the 81-job pilot is documented in `pilot/` (`submit.sh`, `README.md`); then repeat the re-analysis step.

**Outputs.**

- `measured_attacks/attack_results.json`, `measured_attacks/attack_stdout.txt`
- `measured_attacks/pilot_attack_results.json`
- `measured_attacks/RESULTS.md` (summary tables)

**Checks.**

- Within-campaign membership AUC (limit 0.60), greedy / depth-first: P2 0.567 / 0.803; P3 persistent IDs 0.540 / 0.724; P3 rotated IDs 0.541 / 0.721; P4 0.500 / 0.500. Each cell uses 54000 held-out rows.
- Simulated rank extraction: 0.357 to 0.473 with the configuration field visible, 0.032 to 0.075 from timing only.
- Measured pilot (81 jobs, 5 configurations): P1-style 0.969 (q05 0.90, q95 1.00); P4-style timing only 0.736 (q05 0.638, q95 0.824), against the 0.20 limit.
- Limits: one attacker family (logistic regression on count features); the pilot's balanced randomized design favours the attacker; pilot wall times (2.2 to 8.6 s per job) are specific to grn061.

### `pilot/`: 81-job F1 cost pilot (3 candidate sizes x 9 parallel configurations x 3 repeats of a coarse `pw.x` SCF), its parameter fit, and a simulated posterior re-grade

Level: measured on hardware for the 81 jobs (CHPC granite node grn061: 64 cores, 380 GB, single-node partition, empty at submission, no co-tenant jobs); simulated for the posterior re-grade (`posterior_regrade.py`, simulated units).

**Re-analyse from the committed records (no new compute).**

1. Python 3 with `numpy` (both scripts); the re-grade also imports `prior_predictive/simulator.py` and its dependencies.
2. `python3 pilot/pilot_analysis.py` reads `pilot/results/pilot_results.csv` and `pilot/job_matrix.csv` and writes `pilot/results/pilot_fit.json` (parallel-efficiency exponent, pool and aggressive-mode effects, configuration spread, repeat noise, failure-rate bound, cross-term ablation by leave-one-cell-out CV). Node-hour convention here: 16 cores count as one node.
3. `python3 pilot/posterior_regrade.py` reads `pilot/results/pilot_fit.json` and `stage2_twin_fit/twin_fit.json`, re-runs the simulator at scales x10, x100, x300 with `POST_WORLDS` worlds (environment variable, default 300; uses all CPU cores through `multiprocessing`), and writes `pilot/results/posterior_regrade.json`.

**Re-run the computation.**

1. Inputs: `python3 pilot/make_inputs.py` (option `--check-pseudos` hashes the files in `pilot/pseudos/` into `pilot/pseudos_manifest.json`) builds six `pw.x` inputs (TiS2_1T, MoSe2_2H, WTe2_2H; conservative and `_agg`) from `prior_predictive/candidates/candidates.json`, and `pilot/job_matrix.csv` (81 rows, shuffled with seed 20260902). Caution: the pseudopotential file names in `make_inputs.py` (for example `Mo_ONCV_PBE-1.0.oncvpsp.upf`, `Se_pbe_v1.uspp.F.UPF`) differ from those in the committed inputs, which use the GBRV lower-case names (`mo_pbe_v1.uspp.F.UPF`, `se_pbe_v1.uspp.F.UPF`, `te_pbe_v1.uspp.F.UPF`, `w_pbe_v1.2.uspp.F.UPF`, `ti_pbe_v1.4.uspp.F.UPF`, `s_pbe_v1.4.uspp.F.UPF`). To reproduce the measured runs, use the committed `pilot/inputs/*.pw.in` and do not regenerate them.
2. Settings in the committed inputs: SCF, 6x6x1 k-points, `ecutwfc` from the candidate metadata (35 Ry for WTe2_2H), `ecutrho = 8 x ecutwfc`, cold smearing 0.02 Ry; conservative `mixing_beta = 0.3`, `conv_thr = 1e-8`; aggressive `mixing_beta = 0.7`, `conv_thr = 1e-6`.
3. Pseudopotentials: GBRV ultrasoft PBE (the README mentions SSSP, but the measured runs used GBRV); sha256 hashes of the six files used are in `pilot/results/pseudos_manifest.txt`. Place them in `pilot/pseudos/`.
4. Software: Quantum ESPRESSO 7.4, modules `openmpi/5.0.3 quantum-espresso/7.4`.
5. Submission: `PILOT_AUTHORIZED=1 MAX_NODE_HOURS=<cap> bash pilot/submit.sh` (optional `PILOT_TARGET=kingspeak` for a multi-node layout). It walks `job_matrix.csv`, refuses to run without the two variables or without files in `pilot/pseudos/`, stops when the worst-case projected spend (nodes x 0.5 h per job) exceeds the cap, and submits `pilot/job_template.sbatch` with `--nodes=1 --ntasks=<16 x nodes>` (16, 32 or 64 tasks) and `--export=ALL,PILOT_CAND,PILOT_NPOOL,PILOT_AGG,PILOT_JOBID`. The template requests `--time=00:30:00` and writes to `$SCRATCH/mpt_pilot/job_<id>/`; replace the account, partition and QoS lines with `<account>`, `<partition>`, `<qos>`. The recorded run used `MAX_NODE_HOURS=100`.
6. Known difference: the measured batch used a corrected template (`mpirun -np $SLURM_NTASKS --bind-to none pw.x`, `OMP_NUM_THREADS=1`, GBRV file names), as recorded in `pilot/results/PILOT_RESULTS.md`. The committed `job_template.sbatch` still launches `srun pw.x` without setting `OMP_NUM_THREADS`; apply those two changes before rerunning. A first batch with the uncorrected template was cancelled and is excluded.
7. Collection: `pilot/collect_pilot.sh` runs on the cluster in `$SCRATCH/mpt_pilot_bundle` (the staging of the bundle to that folder is not in the repository), reads each `slurm-<id>.out`, `sacct` and `pw.out`, keeps job ids from the resubmitted batch only (hard-coded threshold 1914396; change it for a new run), and writes `pilot_results.csv` with the columns `pilot_analysis.py` expects. Copy it to `pilot/results/`. (`pilot/collect_results.sh` writes a different, sacct-only CSV that `pilot_analysis.py` cannot read.)
8. Then run `pilot_analysis.py` and `posterior_regrade.py` as above.
9. Observed cost: 81 jobs, 0.212 node-hours in total (16-core convention), 2.15 to 8.56 s `pw.x` wall time per job.

**Outputs.**

- `pilot/results/PILOT_RESULTS.md`
- `pilot/results/pilot_results.csv`, `pilot/job_matrix.csv`
- `pilot/results/pilot_fit.json`
- `pilot/results/posterior_regrade.json`
- `pilot/results/pseudos_manifest.txt`

**Checks.**

- 81/81 completed and SCF-converged, 0 failures (95% upper bound on the failure rate 3.6%).
- `pilot_fit.json`: parallel-efficiency exponent s = 0.425 (prior 0.65 +/- 0.10); configuration spread 0.061 (log sd); repeat noise 0.076 (log sd); aggressive-mode effect -0.269 in log wall time; pool effect -0.078; maximum memory 3.05 GB; mean wall per candidate 3.88 s (TiS2_1T), 4.09 s (MoSe2_2H), 5.21 s (WTe2_2H).
- Cross-term ablation: leave-one-cell-out RMSE 0.124 (additive) against 0.134 (with cross-party products), a held-out change of -8.1%.
- `posterior_regrade.json` (300 worlds): the only configuration with a non-zero joint-gain rate is `CEDT_P4`, at 0.07 / 0.19 / 0.203 (preregistered metrics) and 0.713 / 0.817 / 0.813 (execution-layer package) for scales x10 / x100 / x300.
- Limits: jobs last seconds on one dedicated node, so the exponent and noise terms describe that regime only; timings depend on node and load. The re-grade is a simulation; the posterior patch seeds each world from its index (CRC32), so a rerun with the same `POST_WORLDS`, simulator and `twin_fit.json` is expected to reproduce the fractions, provided the base simulator is seeded in the same way.

### `prior_predictive/`: prior-predictive digital-twin simulator, main contract grid, extension grid and their gradings

Level: simulated (all node-hours are simulated units; the grids were run on the DGX Spark (aarch64) with 18 worker processes, about 45 s wall time for the main grid). The 30 MX2 candidate structures are generated idealized prototypes, not measured inputs.

**Re-analyse from the committed records (no new compute).** Python 3 with `numpy`, `scipy` and `matplotlib`. All scripts resolve paths relative to their own file, so they can be run from the repository root.

1. Hard-cap dataset of record (grades `results/summary.json`, `results/drivers.json` and the four main figures). `analyze.py` reads the uncompressed file `results/raw_results.json`, which is not committed, so decompress the hard-cap records under that name first:
   `gunzip -c prior_predictive/results/raw_results_hardcap.json.gz > prior_predictive/results/raw_results.json`
   `python3 prior_predictive/analyze.py`
   Outputs (overwritten): `results/summary.json`, `results/drivers.json`, `results/winwin_probability.png`, `results/privacy_utility_frontier.png`, `results/eps_sensitivity.png`, `results/privacy_tax_vector.png`.
2. Soft-stop grading (`results/summary_pre_hardcap.json`): no script writes this file name. Decompress `results/raw_results.json.gz` to `results/raw_results.json`, run `analyze.py`, and compare the resulting `summary.json` with `summary_pre_hardcap.json` (then repeat step 1 to restore the file of record).
3. Reservation-gain renegotiation (reads `results/raw_results.json.gz`, the soft-stop grid, directly):
   `python3 prior_predictive/reanalysis_gR.py`
   Outputs: `results/gR_renegotiation.json`, `results/gR_renegotiation.png`.
4. Education axis and ablations (reads `results/ext_raw.json.gz`; the post hoc leakage-matching block also reads the current `results/summary.json`, so run step 1 first):
   `python3 prior_predictive/analyze_extensions.py`
   Outputs: `results/ext_summary.json`, `results/fig_education.png`, `results/fig_ablations.png`.

**Re-run the computation.**

1. Candidates (deterministic, no random numbers): `python3 prior_predictive/make_candidates.py` rewrites `candidates/candidates.json`, the 30 `.cif` files and `candidates/LICENSE`. `simulator.py` reads `candidates/candidates.json` at import.
2. Main grid under the hard budget cap (dataset of record):
   `MPT_HARD_CAP=1 python3 prior_predictive/simulator.py --worlds 1000 --sweep-worlds 250 --procs 18 --out results/raw_results.json`
   then `gzip -c prior_predictive/results/raw_results.json > prior_predictive/results/raw_results_hardcap.json.gz` if a compressed copy is wanted. `--out` is resolved relative to `prior_predictive/`. Worlds are split evenly over the `base`, `strong_coupling` and `adversarial` prior cards; the sweep worlds use ids from 100000. Omitting `MPT_HARD_CAP` (default `0`) gives the earlier soft-stop semantics of `raw_results.json.gz`. `MPT_TRACE` enables debug tracing only. `--smoke` runs 6 + 3 worlds on one process.
3. Extension grid (education axis Q0 to Q3 and the ablations):
   `python3 prior_predictive/extensions.py --worlds 1000 --procs 18 --out results/ext_raw.json`, then gzip to `results/ext_raw.json.gz`. `extensions.py` carries its own copy of the campaign loop and does not read `MPT_HARD_CAP`.
4. Then run the re-analysis steps above.

Seed handling: each world is drawn from `numpy.random.default_rng(crc32("<card>:<world_id>"))`, and the 30 paired seeds share common noise fields across conditions. `results/README.md` records that `raw_results.json.gz` predates this stable seeding (it used a process-salted hash), so a rerun reproduces its distributions but not its exact worlds; runs made after the fix are stated to be exactly reproducible. Whether `ext_raw.json.gz` predates the fix is not documented.

**Outputs.**

- `results/raw_results_hardcap.json.gz` (11,750 records: 1,000 worlds x 10 conditions + 250 sweep worlds x 7 conditions) and `results/raw_results.json.gz` (soft-stop predecessor)
- `results/summary.json`, `results/summary_pre_hardcap.json`, `results/drivers.json`
- `results/gR_renegotiation.json`, `results/ext_raw.json.gz` (18,000 records), `results/ext_summary.json`
- Figures: `winwin_probability.png`, `privacy_utility_frontier.png`, `eps_sensitivity.png`, `privacy_tax_vector.png`, `gR_renegotiation.png`, `fig_education.png`, `fig_ablations.png`

**Checks.**

- Soft-stop grid: P(win-win) for CEDT-P4 0.051, CEDT-P3 (eps = 4) 0.014, CTDE-P3 0.005; no condition reaches 0.80.
- Hard-cap grid (`summary.json`): CEDT-P4 0.041 (P(R gain) 0.049, P(H gain) 0.234, leakage pass 1.0), CEDT-P3 0.006, CTDE-P3 0.001; maximum campaign spend 496.5 simulated node-hours.
- Renegotiated reservation gain at 10 %: CEDT-P4 win-win 0.097, CEDT-P3 (eps = 2) 0.056.
- Education axis: mean competency Q0 0.913, Q1 0.897, Q2 with 0 hints 0.987.
- Reruns of the hard-cap grid with fixed seeds are expected to be identical; reruns compared with `raw_results.json.gz` agree statistically only. The attacker models, educator-effort constants and prior cards are model beliefs, not measurements.

### `reverse_timing/`: prediction of a job's wall time from the compound (the reverse of the timing attack)

Level: analysis of committed records. Inputs are the measured Quantum ESPRESSO calls of live comparison No. 1 (3x3 MX2 supercells, PBE, CHPC granite node grn061, 64 cores, 380 GB RAM) and the 1x1-cell F1 times of the DFT campaign in `dft_campaign/` (also run on grn061).

**Re-analyse from the committed records (no new compute).**

Python 3 with `numpy` (plus the standard library).

1. `python3 reverse_timing/reverse_timing.py reverse_timing`
   - The single optional argument is the folder of the script (default `.`); input paths are built as `<argument>/../...`, so either pass `reverse_timing` from the repository root as shown, or run `python3 reverse_timing.py` from inside `reverse_timing/`.
   - reads `paired_comparison_1/results/campaigns.jsonl` (jobs with `ok` true and `converged` true; grouped by `cls`, `ranks`, `npool`, `candidate`) and `dft_campaign/results/outcomes.jsonl` (successful F1 stage `wall_s` per candidate);
   - writes `reverse_timing/reverse_timing_results.json` (overwrites the committed file; work in a fresh copy of the repository) and prints one summary line per setting.
   - No random numbers and no environment variables.

Predictors, per execution setting (stage, ranks, pools):

- A, repeat: each run predicted by the mean of the other runs of the same compound.
- B, 1x1 probe: log-linear fit of the 3x3 mean time on the 1x1 F1 time, leave one compound out.
- C, descriptors: log-linear fit on log electron count (GBRV valences hard-coded in the script), phase, metal row, chalcogen and group-6 flag, leave one compound out.
- Also reported: median spacing in log time between neighbouring compounds.

**Re-run the computation.**

The folder has no compute of its own. The records come from `paired_comparison_1/` (comparison No. 1) and `dft_campaign/`; re-running those campaigns and then step 1 regenerates the results.

**Outputs.**

- `reverse_timing/reverse_timing_results.json` (keys `f1_r16_nk1`, `f1_r32_nk1`, `f2_r32_nk1`, `f2_r32_nk2`, each with medians, p90 and per-compound mean times)
- `reverse_timing/RESULTS.md` (table)

**Checks.** Median absolute prediction error (27 compounds per setting):

| setting | A repeat | B 1x1 probe | C descriptors (p90) | neighbour spacing |
| --- | ---: | ---: | ---: | ---: |
| F1, 16 ranks | 0.28 % | 23.8 % | 7.8 % (20.6 %) | 3.77 % |
| F1, 32 ranks | 0.38 % | 21.2 % | 8.9 % (20.0 %) | 3.01 % |
| F2, 32 ranks, 1 pool | 0.34 % | 28.9 % | 7.8 % (15.8 %) | 3.61 % |
| F2, 32 ranks, 2 pools | 0.45 % | 26.7 % | 7.2 % (20.1 %) | 4.29 % |

Time ranges (s): F1 16 ranks 43.0 to 198.3; F1 32 ranks 25.9 to 116.7; F2 1 pool 59.8 to 343.7; F2 2 pools 60.8 to 341.1. `RESULTS.md` rounds these values.

Limits: `RESULTS.md` describes the data as 29 MX2 monolayers, while 27 compounds per setting pass the `ok` and `converged` filter. F3 jobs do not appear in the output settings because F3 records in `campaigns.jsonl` carry no `converged` field. One code (QE 7.4), one functional (PBE), one node type and one materials family; the fit must be refitted for other hardware and settings.

### `scale_validation/`: measured SCF cost against electron count (in-plane supercells), with the layers and initial-setup extension in `layers_naxis/`

Level: measured on hardware (CHPC granite node grn061, owner partition, CPU only, 32 MPI ranks of the node's 64 cores; node memory 380 GB; the node's GPU is not used).

**Re-analyse from the committed records (no new compute).** Python 3 with `numpy`.

1. Supercell series: `python3 scale_validation/scale_analysis.py`. Reads `scale_validation/results/results.jsonl`; prints the per-run table; writes `scale_validation/results/scale_fit.json` (electron exponent per family on the 6×6 k-grid series, k-point exponent from `MoSe2_2H_s2_k6` vs `MoSe2_2H_s2_k12`, cost multipliers relative to the mean 1×1 cost). Node-hours are computed as `ranks / 16 × wall_s / 3600`.
2. Layers and setup extension: `python3 scale_validation/layers_naxis/layers_analysis.py`. Reads `scale_validation/layers_naxis/results/results.jsonl`; writes `scale_validation/layers_naxis/results/layers_fit.json` (exponents for layers, in-plane and mixed series; strained-start wall and iteration ratios; cross-material spread). Node-hours here are computed as `ranks / 64 × wall_s / 3600`.

Neither script takes arguments. Per-run QE outputs (`scale_validation/results/*.out`, `scale_validation/layers_naxis/results/raw_outputs/*.out`) allow the jsonl fields (wall time aside) to be checked by hand.

**Re-run the computation.**

1. Inputs. Both builders derive their structures, cutoffs and pseudopotential names from `pilot/inputs/<candidate>.pw.in` and take no arguments:
   - `python3 scale_validation/build_scale_inputs.py` writes 8 decks to `scale_validation/inputs/`: TiS2_1T and MoSe2_2H at n×n = 1, 2, 3 on a 6×6×1 grid, `MoSe2_2H_s2_k12` (12×12×1, k-point check) and `MoSe2_2H_s4_k3` (4×4 supercell, 832 electrons, 3×3×1).
   - `python3 scale_validation/layers_naxis/build_layers_inputs.py` writes 17 decks to `scale_validation/layers_naxis/inputs/`: z-stacks L1 to L3 (3.2 Å gap between chalcogen planes) crossed with 1×1 and 2×2 in-plane cells, ±2 % strained 2×2 starts for TiS2_1T and MoSe2_2H, and WTe2_2H at 1×1 and 2×2; all on 6×6×1.
   - Common settings: SCF, ecutwfc 40 Ry, ecutrho 320 Ry, cold smearing 0.02 Ry, mixing 0.3, conv_thr 1e-8, Davidson, at most 80 steps. The committed decks are the ones that were run.
2. Pseudopotentials: GBRV ultrasoft PBE, files `ti_pbe_v1.4.uspp.F.UPF`, `s_pbe_v1.4.uspp.F.UPF`, `mo_pbe_v1.uspp.F.UPF`, `se_pbe_v1.uspp.F.UPF`, `w_pbe_v1.2.uspp.F.UPF`, `te_pbe_v1.uspp.F.UPF`. SHA-256 hashes: `pilot/results/pseudos_manifest.txt`. The UPF files are not in the repository; place them in a `pseudos/` directory next to the sbatch file (the scripts copy `pseudos/*.UPF` from the submit directory).
3. Software: Quantum ESPRESSO 7.4 (`pw.x`, "PWSCF v.7.4" in the outputs), modules `openmpi/5.0.3 quantum-espresso/7.4`, `OMP_NUM_THREADS=1`, `mpirun --bind-to none`.
4. Jobs (submit from the folder holding `inputs/` and `pseudos/`; replace `--account`, `--partition`, `--qos` by `<account>`, `<partition>`, `<qos>`; the working directory is `$SCRATCH/mpt_scale` or `$SCRATCH/mpt_layers`):
   - `sbatch scale.sbatch`: 1 node, 32 tasks, 8 h wall, runs the decks sequentially with a 4 h per-run timeout; `-npool 2` (1 for `*_k3`, 4 for `*_k12`).
   - `sbatch layers_naxis/layers.sbatch` (submitted from `layers_naxis/`): 1 node, 32 tasks, 2 h wall, 30 min per-run timeout, `-npool 2`.
   Each script appends one JSON line per run to `results.jsonl` (wall, convergence flag, electrons, k-points or atoms, SCF iterations, total energy for the layers run) and copies `results.jsonl` and `*.out` to a results directory in the submitting user's home area.
5. Collect: copy `results.jsonl` and the `.out` files into `scale_validation/results/` (layers: `results.jsonl` into `layers_naxis/results/`, `.out` files into `layers_naxis/results/raw_outputs/`), then run the two analysis scripts above. No collection script is in the repository for these two jobs.
6. Observed cost: supercell job 22 min 52 s wall, 0.76 node-hours in the ranks/16 convention; layers job about 22 min wall, 0.16 node-hours in the ranks/64 convention (`layers_fit.json`, `total_node_hours`).

**Outputs.**

- `scale_validation/results/results.jsonl`, `scale_validation/results/scale_fit.json`, `scale_validation/results/*.out`
- `scale_validation/layers_naxis/results/results.jsonl`, `scale_validation/layers_naxis/results/layers_fit.json`, `scale_validation/layers_naxis/results/raw_outputs/*.out`, `scale_validation/layers_naxis/results/slurm-1919292.out`
- Summaries: `scale_validation/RESULTS.md`, `scale_validation/layers_naxis/RESULTS.md`

**Checks.**

- Supercell series: 8/8 converged; wall times from 4 s (TiS2 1×1) to 695 s (MoSe2 4×4, 832 electrons). Electron exponents on the 6×6 series: TiS2_1T 1.63, MoSe2_2H 1.90; k-point exponent 0.61. Cost multipliers against the 1×1 mean: about 6 to 10 (2×2), 34 to 79 (3×3), 154 (4×4).
- Layers extension: 17/17 converged. Exponents (layers / in-plane / mixed L2×s2): TiS2_1T 1.32 / 1.60 / 1.61; MoSe2_2H 1.95 / 2.03 / 2.07. Strained starts change wall time by -7 % to +8 % against the unstrained parent. Max/min wall ratio across the three materials: 1.5 at 1×1, 1.81 at 2×2.
- Limits: wall times depend on the node, MPI layout and concurrent load; expect the exponents and ratios, not the seconds, to reproduce on other hardware. Each point is a single measurement (no repeats). The two analysis scripts use different node-hour conventions (ranks/16 and ranks/64); compare costs only within one convention.

### `shared_stations/`: disclosure contracts at a shared tube furnace and sputter deposition line (simulated growth stations)

Level: simulated. Every station parameter (temperatures, rates, run times, calibration errors) is an assumed value; the only measured content is the list of eight MX2 compositions with a PBE gap in 1.0 to 2.0 eV, which is hard-coded in `station_sim.py` (`COMPS`) and not read from a file at run time. The committed run took 132 s on 8 cores; the machine is not named in the repository.

Design and registered predictions S1 to S7: `shared_stations/DESIGN_AND_PREDICTION.md`; results: `shared_stations/RESULTS.md`.

**Re-analyse from the committed records (no new compute).**

1. Regenerate the figure from the committed graded summary (paths are taken from the command line, relative to the working directory):
   `python shared_stations/make_figure.py shared_stations/results/station_summary.json shared_stations/results/`
   Output: `shared_stations/results/fig_shared_stations.png`.
2. The grading step (`analyze.py`) needs the per-campaign file `station_raw.json` (about 74 MB), which is not committed. Re-grading therefore requires the rerun below; the committed `station_summary.json` and `predictions_graded.json` are its outputs.

Python packages: numpy, matplotlib.

**Re-run the computation.**

1. From the repository root:
   `python shared_stations/station_sim.py --worlds 150 --seeds 15 --procs 8 --out shared_stations/results`
   `--out` defaults to `results` relative to the working directory, so either pass it as shown or run from inside `shared_stations/`. Other options: `--grid` (default 6, giving the tau and eps grid 0, 0.2, ..., 1.0) and `--ps` (default `P2,P3`). Output: `shared_stations/results/station_raw.json` (not committed). The defaults (80 worlds, 10 seeds, 6 processes) are not those of the committed run.
2. Conditions per world: 36 (tau, eps) cells for each of P2 and P3, ten P4 variants (open tube with 50 C or 100 C programme menu, sealed ampoules with no, 50 C or 100 C menu, each at eps = 0 and 1) and a CTCE reference, 83 in total. `RESULTS.md` states 78 conditions; the committed `station_summary.json` holds 83 graded conditions.
3. Grade and write the summary and the prediction verdicts:
   `python shared_stations/analyze.py shared_stations/results/station_raw.json shared_stations/results/`
   Outputs: `station_summary.json` and `predictions_graded.json` in the given directory.
4. Redraw the figure as in step 1 of the re-analysis.
5. Random-seed handling: each world from `default_rng([world, 999])` and each campaign from `default_rng([world, seed, 7])`, so every condition shares the same world and seed streams and the result does not depend on the number of processes. `RESULTS.md` states that the command regenerates the raw file exactly.

**Outputs.**

- `shared_stations/results/station_summary.json` (graded metrics per condition; 150 worlds, 15 seeds)
- `shared_stations/results/predictions_graded.json` (S1 to S7)
- `shared_stations/results/fig_shared_stations.png`

**Checks.**

- S1 (logbook shortens hours to first film by at least 10 %): -0.004, fail.
- S2 (full brokering at P3 gives at least 1.05 x films per furnace-hour in at least 80 % of worlds): 0.947, pass; median ratio 1.19 x.
- S3 (furnace-log identification above 0.175 in at least 95 % of worlds, every arm): minimum 0.98, pass.
- S4 (sealed ampoules): identification drop 0.184; co-firing gain 1.189 (open) against 1.264 (ampoules), pass.
- S5: furnace log 0.506, deposition log 0.494, joined 0.94, pass.
- S6 (thermocouple offset recovered from a shared logbook): correlation 0.795 (P2), 0.704 (P3), 0.754 with no logbook, pass.
- S7: absolute-limit win-win 0 everywhere; best rebased win-win at tau = 0 is 0.367, fail.
- Limits stated in `RESULTS.md`: all station parameters assumed; offsets and rate factors constant within a campaign; identification scored one log entry at a time (a lower bound); leakage of one group's list to other groups through the logbook not graded.

### `stacking_study/`: 2H geometry check (single-layer 2H, AA' bilayer and 3R bilayer with DFT-D3) for 15 MX2 compositions

Level: measured on hardware (one CHPC granite guest node, 32 cores and 120 GB requested; CPU-only Quantum ESPRESSO). This article does not report these results; the folder is included because `paired_comparison_3/build_candidate_list.py` reads `stacking_study/results_2088961/outcomes.jsonl` to build the corrected single-layer candidate list of comparison No. 3. The follow-up relaxations, spin-orbit gaps and phonons of the companion article are not included.

**Re-analyse from the committed records (no new compute).** The records are JSON and can be read with the Python 3 standard library: `stacking_study/results_2088961/outcomes.jsonl` (one record per cell; fields `candidate`, `stages.F2.relax_converged`, `a_relaxed_angstrom`, `gap_ev`, `qualifier`) and `stacking_study/results_2088961/stacking_summary.json`.

**Re-run the computation.**

1. `stacking_study/run_stacking.py` (no arguments) builds 45 cells (Ti, Zr, Hf, Mo, W x S, Se, Te x `mono2H`, `bi2H`, `bi3R`), writes `candidates.json` into `$MPT_DFT_ROOT`, and reuses `dft_campaign/run_campaign.py` for the F1 to F3 ladder (F1 SCF 40 Ry 6x6x1; F2 `vc-relax` `2Dxy` 45 Ry 12x12x1; F3 NSCF 18x18x1). Bilayers add `vdw_corr = 'dft-d3'`, `dftd3_version = 4`.
2. Pseudopotentials: GBRV ultrasoft PBE, the same eight files as `dft_campaign/`. Partial sha256 manifest: `pilot/results/pseudos_manifest.txt` (Zr and Hf not hashed).
3. Staging and submission: `bash stacking_study/stage_and_submit_stacking.sh` (authenticated SSH connection and `CHPC_USERNAME`; submits only when `MPT_STACK_SUBMIT=1`), job script `stacking_study/stacking.sbatch` (`--nodes=1 --ntasks=32 --mem=120G --time=24:00:00`).
4. Observed cost: 2.712 h wall, 138 QE calls, 1.355 node-hours.

**Checks.** 45 cells, 43 relaxations converged; MoS2 single-layer PBE gap 1.6735 eV, `a` = 3.1817 A.

### `stage2_twin_fit/`: calibration of the cost twin against the measured Quantum ESPRESSO calls and recalibrated re-grade of the contract grid

Level: analysis of committed records (the 98 scalar QE calls of `dft_campaign/`, measured on CHPC granite node grn061, 64 cores, 380 GB, 16 MPI ranks and 4 pools per call), followed by a simulated re-grade (prior-predictive twin, simulated node-hours) on the DGX Spark (aarch64, 20 cores).

**Re-analyse from the committed records (no new compute).**

1. Rebuild the call table: `python3 stage2_twin_fit/build_dataset.py` (no arguments). Reads `dft_campaign/results/outcomes.jsonl`, `dft_campaign/soc/results/soc_outcomes.jsonl` (when present) and `prior_predictive/candidates/candidates.json`; writes `stage2_twin_fit/qe_calls.csv` (116 rows: 98 scalar calls and 18 spin-orbit calls).
2. Parametric fit: `python3 stage2_twin_fit/fit_twin.py` (no arguments). Reads `qe_calls.csv` (scalar rows only); writes `stage2_twin_fit/twin_fit.json` and prints it.
3. Symbolic refit: `python3 stage2_twin_fit/pysr_fit.py` (no arguments). Reads `qe_calls.csv`; writes `stage2_twin_fit/pysr_wall_fit.json`. The validation split is fixed (numpy seed 41, one fifth of candidates held out) but PySR runs with `deterministic=False` and multithreading, so the selected expression can differ between runs.
4. Packages: Python 3 with numpy (steps 1 and 2 need only the standard library and numpy); step 3 needs PySR with its Julia back end (the original run used the PySR environment of `stage1_symbolic_recovery/`, PySR 2.2.0 per that folder's RESULTS.md).

All three scripts overwrite the committed files in place; compare against the committed versions with a version-control diff.

**Re-run the computation.**

1. The measured QE calls are not re-run here; they come from `dft_campaign/` (see that folder's instructions for inputs, pseudopotentials and job scripts).
2. Recalibrated re-grade: `MPT_HARD_CAP=1 python3 stage2_twin_fit/recalibrate.py --worlds 300 --card base --scales 1,10,100,1000,10000` (these are the script defaults; `--procs` defaults to the number of CPU cores). Reads `twin_fit.json` and imports `prior_predictive/simulator.py`; writes `stage2_twin_fit/recalibrated_grade.json` and prints the best contract and DTDE node-hours per scale. The in-allocation overhead scenario is run at scale 1 only.
3. Run order: `build_dataset.py`, `fit_twin.py`, then `recalibrate.py`; `pysr_fit.py` is independent of the re-grade.
4. Hardware and cost: the original re-grade ran on the DGX Spark (CPU, multiprocessing). Its wall time is not recorded.
5. The two-panel figure `stage2_twin_fit/stage2_calibration.png` has no generating script in the repository.

**Outputs.**

- `stage2_twin_fit/qe_calls.csv`
- `stage2_twin_fit/twin_fit.json`
- `stage2_twin_fit/pysr_wall_fit.json`
- `stage2_twin_fit/recalibrated_grade.json`
- `stage2_twin_fit/STAGE2_RESULTS.md` (summary tables), `stage2_twin_fit/stage2_calibration.png`

**Checks.**

- `twin_fit.json`: electron exponent p_e = 1.202 (prior 2.5), R^2 = 0.953 over n = 98 calls, residual sd 0.342 in log; stage amplitudes A(F1) = 0.000398, A(F2) = 0.009462, A(F3) = 0.000906, A(F4) = 0.015754 node-hours, that is prior over measured ratios of 3,015, 1,268, 8,830 and 2,539. Memory fit R^2 = 0.009 with a flat 0.138 GB per rank; minimum call cost 0.0002 node-hours; 18 spin-orbit rows available.
- `pysr_wall_fit.json`: selected expression of complexity 22, validation MSE 0.067, R^2 = 0.971 over all calls (an in-range interpolator; do not extrapolate).
- `recalibrated_grade.json`: the best contract is CEDT-P4 at every scale; P(win-win) 0.003 at measured scale with per-job overhead, 0.207 with in-allocation overhead, peaking at 0.203 at 100 times the measured cost and falling to 0.030 at 10,000 times; DTDE uses 2.0 of the 500 simulated node-hours at measured scale. With 300 worlds the probabilities carry about plus or minus 0.02 to 0.03.
- Known limits: every QE stage ran one fixed k-grid and one execution configuration, so the k-point exponent, parallel efficiency and contention are not identifiable and stay at their priors; a single prior card (base) is re-graded; the overhead scenarios are estimates.

### `timing_masking/`: price of masking clauses (quantized completion times, class-constant padding) against the measured timing attack

Level: analysis of committed records. The underlying records are the 480 measured Quantum ESPRESSO calls of live comparison No. 1 (SLURM jobs 1919944/1919945), run on CHPC granite node grn061 (64 cores, 380 GB RAM, single-node partition). The masks are applied analytically to the measured wall times; no masked job was executed.

**Re-analyse from the committed records (no new compute).**

Python 3 with `numpy` (sweep) and `matplotlib` (figure). Both scripts locate their files relative to their own directory, so they can be called from the repository root. Each script overwrites its committed output in place; work in a fresh copy of the repository and compare the regenerated file with the committed one.

1. Masking sweep:
   `python3 timing_masking/mask_study.py`
   - reads `paired_comparison_1/results/campaigns.jsonl` (per-job `arm`, `seed`, `opaque_id`, `candidate`, `cls`, `wall_s`);
   - writes `timing_masking/mask_results.json` and prints one line per clause.
   - Sweep (hard-coded): no mask; quantization q = 5, 15, 30, 60, 120, 300, 600, 1200, 3600 s; padding to the class percentile p = 90, 95, 99, 100.
   - Attacks (identical to `paired_comparison_1/wire_attack.py`): leave-one-seed-out identity attack (median wall per candidate and class from the other seeds, nearest neighbour in mean absolute log-wall distance) and membership AUC. Limits: identity accuracy at most 1/27 + 0.05 = 0.087, membership AUC at most 0.60. The worst arm (DTDE or CEDT_P4) is reported.
2. Figure:
   `python3 timing_masking/make_figure.py`
   - reads `timing_masking/mask_results.json`; writes `timing_masking/fig_timing_masking.png`.

**Re-run the computation.**

The folder has no compute of its own and no random seed (the sweep is deterministic). To regenerate the input records, re-run live comparison No. 1 as documented in `paired_comparison_1/` (driver `live_campaign.py`, collection `collect_live.sh`), then repeat steps 1 and 2 above.

**Outputs.**

- `timing_masking/mask_results.json` (fields `n_candidates`, `prior_identity`, `identity_limit`, `membership_auc_limit`, and `sweep` rows with `cost_inflation`, `worst_identity_acc`, `worst_membership_auc`, pass flags and `per_arm`)
- `timing_masking/fig_timing_masking.png`
- `timing_masking/RESULTS.md` (summary table)

**Checks.**

From `mask_results.json` (27 candidates in the records, prior 0.037, identity limit 0.087):

| clause | cost inflation | worst identity | worst membership AUC |
| --- | ---: | ---: | ---: |
| none | 0 | 0.9625 | 1.000 |
| quant 60 s | +20.2 % | 0.575 | 0.884 |
| quant 300 s | +124.1 % | 0.1125 | 0.550 |
| quant 600 s | +303.7 % | 0.050 | 0.500 |
| pad p95 | +124.6 % | 0.200 | 0.482 |
| pad p99 | +151.1 % | 0.075 | 0.501 |

Known limits:

- The stratified-padding row of `RESULTS.md` (padding by class and phase, +62 %) is not produced by `mask_study.py`; `make_figure.py` draws it as a fixed point (62.1 %, 1/14). The script that computed it is not in the repository.
- Cost is computed as the ratio of masked to true summed wall time; whether it is latency or billed node time depends on the accounting (see `billing_regrade/`).
- References are built from masked walls (a wire-only attacker); an executor holding unmasked references would do somewhat better at small q, so the small-q rows are lower bounds on attack success.
- Wall times, and hence all numbers, are specific to grn061 and the 3x3 supercell job sizes; seed-level confidence intervals for every row are in `bootstrap_ci/seed_bootstrap.json`.

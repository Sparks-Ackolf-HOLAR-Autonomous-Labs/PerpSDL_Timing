# F1 coupling-measurement pilot (81 jobs) — reviewed SLURM bundle

Purpose: measure the H-side physical parameters that drive the win-win
event in the prior-predictive simulation (contention burstiness,
pool-mismatch coupling, scaling exponent, failure base rate, config-quirk
spread — see `../prior_predictive/results/drivers.json`), using **public
CC0-1.0 candidate structures only** (zero R IP), and produce the Stage-2
twin-fitting dataset.

Design (frozen from the prior-predictive round): **3 sizes x 9 configs x 3
repeats = 81 F1-class jobs** (coarse SCF, `pw.x`), submission order
randomized with a fixed seed, plus memory profiling via `sacct`
(MaxRSS/Elapsed). Estimated cost 120–160 node-hours (that estimate is a
simulated-unit extrapolation, not a CHPC measurement).

## Verified cluster facts used here (live-verified 2026-09-02)

Primary target: **granite**, verified live on `granite1.chpc.utah.edu`:

- Account `sparks`, partition `sparks-gpu-grn`, QoS `sparks-gpu-grn`
  (in the account's granite QoS list; 14-day max wall). The partition is
  exactly one node, `grn061`: 64 cores (1 socket, 2 threads/core), 380 GB
  RAM, 1x H100 NVL, DefMemPerCPU=2000M.
- Because the partition is single-node, the matrix's 2- and 4-node jobs
  are recast by `submit.sh` as wider single-node jobs (16 MPI tasks per
  former node, max 64). Set `PILOT_TARGET=kingspeak` to use the old
  multi-node layout on the general allocation instead.
- **Preemption caution (verified via `sbatch --test-only`):**
  `sparks-gpu-grn` has PreemptMode=CANCEL — submitting there cancels any
  running `granite-gpu-guest` jobs on grn061. Check
  `squeue -p sparks-gpu-grn` (it was busy with a guest GPU job at
  verification time) before authorizing.
- Module stack: `module load openmpi/5.0.3 quantum-espresso/7.4` —
  live-load-tested on granite1; `pw.x` resolves.
- Scratch: `/scratch/general/vast/$USER` (exists on granite; subject to
  CHPC purge).

Fallback (needed only if the pilot outgrows one node): `kingspeak`
(general, non-preemptable; QoS `kingspeak`, 3-day wall), `lonepeak`, or
`notchpeak-shared-short` (8 h wall, per-user cpu=32/mem=128G).

## Required before submission (set by the authors)

1. `live_node_hour_cap` — set by the allocation owner
   (`MAX_NODE_HOURS` env var for `submit.sh`).
2. `authorized_chpc_pilot: true` in `../case_manifest.yaml`
   (`PILOT_AUTHORIZED=1` env var for `submit.sh`).
3. Pseudopotentials: download the GBRV 1.5 ultrasoft PBE files for
   Ti, Zr, Hf, Mo, W, S, Se, Te into `pseudos/` (hashes of the files used
   for the measured run: `results/pseudos_manifest.txt`) (they retain their own
   licenses; `make_inputs.py --check-pseudos` records sha256 hashes into
   `pseudos_manifest.json` to freeze the manifest field).

`submit.sh` refuses to run unless 1 and 2 are satisfied, and it stops
submitting when the projected node-hour spend would exceed the cap.

## Files

- `make_inputs.py` — builds 3 `pw.x` F1 inputs (small/medium/large by
  electron count: TiS2_1T, MoSe2_2H, WTe2_2H) from the CC0 metadata in
  `../prior_predictive/candidates/`, plus `job_matrix.csv` (81 rows,
  seeded shuffle).
- `job_matrix.csv` — the frozen randomized job order
  (job_id, candidate, nodes, npool, aggressive, repeat).
- `job_template.sbatch` — one F1 job; parametrized by environment
  (`sbatch --export=...` from `submit.sh`); 30-min wall per job.
- `submit.sh` — guarded submission loop (see above).
- `collect_results.sh` — pulls sacct records (Elapsed, MaxRSS, ExitCode,
  NodeList) into `pilot_results.csv` for the twin fit.

## Config mapping (simulator config space -> QE/SLURM)

The 9 configs are the simulator's `CONFIGS` (nodes, pools, aggressive):
nodes -> `--nodes`; pools -> `pw.x -npool`; aggressive=1 ->
`mixing_beta=0.7, diagonalization='david'` with looser `conv_thr` and
`ndiag` unset (vs. the conservative `mixing_beta=0.3, conv_thr 1e-8`).
K-mesh 6x6x1 Monkhorst-Pack (F1 coarse), `ecutwfc` from the candidate
metadata, `ecutrho = 8*ecutwfc`, cold smearing 0.02 Ry (metallic-safe;
F1 rejects, it does not certify gaps).

## Interpretation limits

F1 results are cost/stability telemetry for the digital twin only:
coarse SCF at idealized geometry certifies nothing scientific
(no relaxation, no gap claims). Total energies are never compared across
compositions. This bundle submits nothing by itself and must be
re-reviewed if the manifest changes.

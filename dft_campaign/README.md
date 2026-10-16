# Actual-DFT campaign (2026-09-08)

Real Quantum ESPRESSO calculations — not the digital twin, not the 81-job
cost pilot — running the fidelity ladder from `case_manifest.yaml` over
all 30 CC0-1.0 idealized MX2 candidates
(`../prior_predictive/candidates/`).

## What runs

| Stage | Calculation | Grid | Purpose |
| --- | --- | --- | --- |
| F1 | coarse SCF, 40 Ry, idealized geometry | 6×6×1 | viability + cost row |
| F2 | `vc-relax`, `cell_dofree='2Dxy'`, 45 Ry | 12×12×1 | relaxed structure, max force, energies |
| F3 | dense NSCF at relaxed geometry | 18×18×1 | PBE screening gap (qualify: 1.0–2.0 eV) |
| F4 | `ph.x` at Γ (qualifiers only, after a fresh SCF) | Γ | obvious-instability check — **not** a stability proof |

- Pseudopotentials: GBRV 1.5 USPP (`all_pbe_UPF_v1.5.tar.gz`,
  Rutgers), downloaded to scratch; original GBRV license applies —
  listed separately from the CC0 structures per the manifest.
- One retry per failed stage (mixing 0.3→0.2, `cg`, 200 steps); restart
  and failure counts recorded per the target outcome vector.
- Non-spin-polarized, no SOC (recorded limitation; SOC for finalists is
  the manifest's optional item). PBE gaps are screening quantities.
- 1T–2H energy difference per composition is computed in analysis from
  E/formula-unit (never ranked across compositions).

## Where and how

- granite `grn061`, partition/QoS `sparks-gpu-grn`, account `sparks`,
  48 of 64 cores + 180 GB (leaves the resident GPU job untouched;
  same-QoS, so no preemption).
- `#SBATCH --time=20160` — the node time limit (minutes)
  for the entire run; the driver's soft cap (`MPT_NODE_HOUR_CAP`, 330
  node-hours) stops new QE calls earlier.
- 3 concurrent `pw.x` runs × 16 MPI ranks (`-nk 4`), QE 7.4 +
  openmpi/5.0.3 modules.
- Workspace: `/scratch/general/vast/$USER/mpt_dft/` (scratch purges —
  results are copied to `~/mpt_dft_results/` by the job and committed
  back to this folder).

## Files

- `run_campaign.py` — self-contained driver (input generation, QE
  execution, parsing, budget guard, `results/outcomes.jsonl` +
  `results/campaign_summary.json`).
- `campaign.sbatch` — the submitted job script.
- `collect_dft.sh` — run from the repository root (with an
  authenticated SSH connection to the cluster) to fetch results into
  `results/`.
- `results/` — fetched outcomes committed to the repo.

## Provenance

Submitted 2026-09-08 as SLURM job **1913865**; COMPLETED the same day at
01:29 MDT (53 min wall, exit 0), followed by a 29-second repair pass
(job **1913878**, `--repair-f3` mode) that finalized the outcome
records. Results were collected from scratch and match the post-repair
copy saved under `~/mpt_dft_results/`: 30/30 candidates, 29 F2-converged
(HfSe2-2H failed its relaxation retry), 9 qualifiers, 0.59 measured
node-hours, 108 driver QE calls (111 counting the repair pass), budget
cap not hit.

The launching run's `parse_ph` regex missed QE's `[THz] =` segment, so F4
records initially carried `freqs_cm1: null` even though every `ph.x` run
completed. The regex in `run_campaign.py` was then fixed, the
fetched the nine raw `f4.out` files into `results/f4_outputs/` for
provenance, and backfilled the records via `patch_f4.py`. All nine
qualifiers pass the Γ check (min frequency ≥ −16.6 cm⁻¹, acoustic-mode
numerical noise only; instability threshold −30 cm⁻¹). CHPC usernames are
scrubbed to `<uNID>` in all committed artifacts.

# Computational setup of the live comparison job (SLURM 1919945)

Functional and computational setup of the job, recorded on 2026-09-09.
Everything below is
read directly from the committed bundle that job 1919945 is executing:
`live.sbatch`, `live_campaign.py`, `build_live_inputs.py`, and the 87
generated input decks in `inputs/` (29 candidates × 3 stages).

## Level of theory

| Item | Value |
| --- | --- |
| Code | Quantum ESPRESSO 7.4 (`pw.x`), modules `openmpi/5.0.3 quantum-espresso/7.4 python/3.10.3` |
| Functional | **PBE** (GGA). No `input_dft` override — the functional comes from the pseudopotentials. |
| Pseudopotentials | **GBRV 1.5 ultrasoft** (Rutgers, e.g. `mo_pbe_v1.uspp.F.UPF`, `s_pbe_v1.4.uspp.F.UPF`); same set as the 1×1 DFT campaign. GBRV license applies, listed separately from the CC0 structures. |
| Spin / SOC | Non-spin-polarized, **no spin–orbit coupling** (scalar-relativistic USPP). SOC exists only in the separate 1×1 finalist study (`../dft_campaign/soc/`), not in this job. |
| Smearing | Marzari–Vanderbilt **cold smearing**, `degauss = 0.015 Ry` (≈ 0.2 eV) |
| Diagonalization / mixing | Davidson; `mixing_beta = 0.3`; `electron_maxstep = 120` |

PBE gaps remain screening quantities (preregistered interpretation
limit), qualifying window 1.0–2.0 eV.

## Structures

- The **29** CC0-1.0 MX₂ candidates (M = Ti, Zr, Hf, Mo, W; X = S, Se,
  Te; 1T and 2H phases) that have a converged relaxed geometry from the
  real 1×1 campaign. HfSe₂-2H is excluded (its relaxation never
  converged).
- **3×3 in-plane supercells** of the *measured relaxed* 1×1 geometries
  (`../dft_campaign/results/campaign_summary.json`): 27 atoms (1T) or
  54 atoms (2H), 216–468 electrons, hexagonal cell (`ibrav = 4`),
  a = 3 × a_relaxed, **c = 18 Å** (≈ 13 Å vacuum). This is the ×30–×100
  task-scale operating point located by `../scale_validation/`.
- SCF at the relaxed geometry replaces a fresh 54-atom relaxation — a
  preregistered scope amendment (budget); the label claim is
  "production SCF at a converged geometry".

## Fidelity ladder (per candidate; no F4 in this comparison)

| Stage | Calculation | `ecutwfc` / `ecutrho` (Ry) | k-grid | `conv_thr` | Purpose |
| --- | --- | --- | --- | --- | --- |
| F1 | coarse SCF | 40 / 320 | 2×2×1 | 1e-6 | viability + cost row |
| F2 | production SCF | 45 / 360 | 4×4×1 | 1e-8 | the "valid F2 label" |
| F3 | dense NSCF (`nbnd` ≈ nelec/2 + max(8, 20%)) | 45 / 360 | 6×6×1 | 1e-8 | PBE screening gap |

`ecutrho = 8 × ecutwfc`, appropriate for ultrasoft pseudopotentials.
K-grids are Monkhorst–Pack unshifted; on a 3×3 supercell the 2/4/6
grids fold back to 6/12/18 on the primitive cell — matching the 1×1
campaign's F1/F2/F3 densities.

## Experiment design executing around the physics

- 10 paired campaign seeds × 2 arms over identical shuffled candidate
  orders; **inputs are arm-independent — the arms differ only in
  execution config**, never in physics:
  - DTDE (no sharing): every job runs the worst-case config
    `mpirun -np 32`, `pw.x -nk 1`;
  - CEDT-P4 (broker): class-matched public rate card — F1 `-np 16 -nk 1`,
    F2 `-np 32 -nk 2`, F3 `-np 32 -nk 4`.
- Metrics per the activated preregistration: PW60 paired win-rate on
  node-hours-to-first-qualifier (R), labels/nh ≥ 1.05× and failure
  ≤ +0.04 (H); wire logs feed the executed leakage attacks, timing
  channel accept-and-measure.

## Resources and guards (job 1919945)

- granite `grn061`, account `sparks`, partition/QoS `sparks-gpu-grn`,
  1 node, 64 tasks, CPU-only (H100 untouched); `--time=120:00:00`
  hard stop (within the 20160-min node limit).
- Node-hours charged as wall × ranks / 64; guards:
  `MPT_LIVE_NH_CAP=100` (global), 5 nh per campaign, 24 QE calls per
  campaign. Estimated usage 20–40 nh.
- Submitted 2026-09-09 after the Python-3.6.8
  false start (`1919941`/`1919942`, seconds lost, no QE ran); details
  in `PREREGISTRATION.md` §5. Results were collected once the job
  completed.

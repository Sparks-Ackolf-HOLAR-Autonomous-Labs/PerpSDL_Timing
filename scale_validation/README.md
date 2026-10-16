# Win-win-scale validation (real QE, granite grn061)

Stage 2 predicted the
privacy-tax win-win window sits at **10–100× the measured MX₂ task
scale**; this bundle measures real SCF cost at 1×/4×/9×/16× electron
counts to locate that window in real node-hours and test which
electron-scaling exponent governs the heavy regime (Stage-2 fit on tiny
cells: p_e = 1.20; prior card: 2.5 — cubic-scaling onset expected).

- `build_scale_inputs.py` → 8 inputs: n×n in-plane supercells of two
  CC0 candidates (TiS₂-1T small / MoSe₂-2H mid), fixed 40 Ry cutoff,
  fixed nominal 6×6×1 grid (+ one 12×12 k-linearity check, + one 4×4
  supercell at 3×3 — 832 electrons, the ×10–×100-regime probe).
- `scale.sbatch` — SLURM job **1914482**, `sparks-gpu-grn`, 32 ranks,
  8 h wall / 4 h-per-run timeouts, sequential mpirun runs; GPU
  untouched. Submitted 2026-09-08 (same cap regime as the pilot).
- `scale_analysis.py` — exponent fits + real-unit cost multipliers;
  writes `results/scale_fit.json`.
- `results/` — fetched measurements (real CHPC node-hours, not
  simulated units).

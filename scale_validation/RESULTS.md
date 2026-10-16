# Scale validation results (granite job 1914482 — real QE, measured units)

Job `1914482` (partition `sparks-gpu-grn`, node grn061, 32 MPI ranks,
CPU only) COMPLETED in 22 min 52 s wall; **8/8 SCF runs converged**.
Total spend ≈ 0.76 node-hours (32-rank convention as in the pilot).
These are real CHPC measurements, not simulated units.

## Measured costs

| run | supercell | atoms | electrons | k-pts (irr.) | wall (s) | node-h |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| TiS2_1T_s1_k6 | 1×1 | 3 | 24 | 7 | 4 | 0.0022 |
| TiS2_1T_s2_k6 | 2×2 | 12 | 96 | 7 | 28 | 0.0156 |
| TiS2_1T_s3_k6 | 3×3 | 27 | 216 | 7 | 151 | 0.0839 |
| MoSe2_2H_s1_k6 | 1×1 | 6 | 52 | 7 | 5 | 0.0028 |
| MoSe2_2H_s2_k6 | 2×2 | 24 | 208 | 7 | 46 | 0.0256 |
| MoSe2_2H_s2_k12 | 2×2, 12×12 k | 24 | 208 | 19 | 85 | 0.0472 |
| MoSe2_2H_s3_k6 | 3×3 | 54 | 468 | 7 | 356 | 0.1978 |
| MoSe2_2H_s4_k3 | 4×4 | 96 | 832 | 3 | 695 | 0.3861 |

## Fits (`scale_analysis.py` → `results/scale_fit.json`)

- **Electron-scaling exponent steepens with size, as predicted.**
  Whole-series (k6) fits: TiS₂ 1.63, MoSe₂ 1.90 — between the Stage-2
  tiny-cell fit (1.20) and the prior card (2.5). Incremental exponents
  (k-normalized): ~1.4–1.6 on s1→s2, ~2.1–2.5 on s2→s3, **~2.6 on
  s3→s4** — the cubic-scaling onset is visible by ≈ 800 electrons. The
  Stage-2 value of 1.20 was a tiny-cell artifact; the prior card's 2.5
  is approximately right in the heavy regime.
- **k-point cost is sublinear**: measured exponent 0.61 (s2, 7→19
  irreducible k-points) vs the twin prior of 1.0 — k-pool parallelism
  is efficient on this node.
- **The ×10–×100 win-win window maps to 2×2–3×3 supercells** (≈ 100–470
  electrons): measured multipliers vs the 1×1 ladder are ≈ 6–10× (2×2),
  ≈ 34–79× (3×3), ≈ 154× (4×4). In absolute terms even the ×100 regime
  is cheap on granite (≈ 0.2–0.4 node-h per SCF), so a full 30-candidate
  validation campaign at 3×3 scale is an estimated ≈ 20–60 real
  node-hours — well within a modest cap.

## What this settles

The Stage-2 prediction that the privacy-tax question becomes
non-degenerate at ×10–×100 the measured MX₂ task is now located in real
units: **run the win-win-scale campaign on 3×3 (optionally 4×4)
in-plane supercells**, where per-job cost differences are large enough
for information contracts to trade on, and where the measured exponents
(p_e → 2.5–2.6, p_k ≈ 0.6) should be frozen into the twin's operating
card. See `../metric_redesign/RESULTS.md` for the metric that makes the
0.90 win-win threshold reachable at this operating point.

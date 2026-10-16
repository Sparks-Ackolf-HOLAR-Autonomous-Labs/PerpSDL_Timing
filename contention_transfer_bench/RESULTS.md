# contention_transfer_bench RESULTS (measured, granite grn061)

**SLURM job 1919944, COMPLETED, exit 0** (22 m 30 s wall, ≈0.35
node-hours incl. co-tenant pairs). Collected 2026-09-09; analysis:
`analyze_bench.py` → `results/bench_analysis.json`. All 20 SCFs
converged.

## 1. Contention vs scale (item 2, single-box half)

Solo vs co-tenant (32+32 ranks sharing grn061), TiS₂-1T probe, 2 reps:

| scale | atoms | solo | co-tenant | interference |
| --- | ---: | ---: | ---: | ---: |
| s1 (1×1) | 3 | 3.12 s | 3.31 s | +6.4% |
| s2 (2×2) | 12 | 26.55 s | 29.48 s | +11.0% |
| s3 (3×3) | 27 | 141.2 s | 151.9 s | +7.6% |

Measured co-tenant interference is **6–11% and does not grow with task
size** over this range (it peaks at s2). The coupling-onset hypothesis
that memory-bandwidth interference grows steadily with scale is *not
supported* up to 27-atom/216-electron jobs on this node; if a
contention-driven coupling band exists it starts above this range,
consistent with the ×300+ onset the posterior twin predicts.
Inter-node contention remains unmeasured (needs kingspeak general
partition).

## 2. Transfer probes (item 5)

Both non-MX₂-prototype tasks converged first try. Against the MX₂-only
power law fitted to this same job's points (wall ∝ nelec^1.65):

| probe | electrons | measured | electron-count prediction | ratio |
| --- | ---: | ---: | ---: | ---: |
| MoS₂ 3×3 + S vacancy (53 at.) | 462 | 161 s | 306 s | 0.53 |
| MoS₂/WS₂ heterobilayer 2×2 (24 at.) | 208 | 36 s | 82 s | 0.44 |

The electron-count-only cost model **overpredicts by ≈2× across task
families**: species mix and structure matter (the probes are S-rich
and cheaper per electron than the Se/Te-heavy fit set). A cost twin
transferred to defects/heterostructures needs at least a
species/row-of-the-periodic-table term — electron count alone is a
safe *upper* bound here but a poor estimator.

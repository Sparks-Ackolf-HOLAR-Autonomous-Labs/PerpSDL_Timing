#!/usr/bin/env python3
"""2H geometry check for the MX2 screen (2026-09-30).

The first campaign's "2H" entries were 6-atom bilayers in 2H (AA') stacking,
relaxed with plain PBE and no dispersion correction, so the layers sat about
1.2 A too far apart and no stacking or twist variants were tried. This run
recomputes the 15 compositions three ways with the same PBE/GBRV ladder
(F1 coarse SCF, F2 in-plane vc-relax, F3 dense NSCF gap; no phonons):

  mono2H  3-atom trigonal-prismatic monolayer (what a monolayer screen means)
  bi2H    2H (AA', second layer rotated 180 deg) bilayer with DFT-D3
  bi3R    3R (AB, same orientation, shifted) bilayer with DFT-D3

Twisted bilayers are not included (commensurate twist cells start at
42 atoms); see README.md. Reuses dft_campaign/run_campaign.py for the
ladder, parsers and cost telemetry; only the geometry and the dispersion
flag change. The solver-retry rule applies (F3 retries with cg).
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(HERE.parent / "dft_campaign"))
import run_campaign as rc  # noqa: E402

METALS = ["Ti", "Zr", "Hf", "Mo", "W"]
CHALC = ["S", "Se", "Te"]
A0 = {"S": 3.18, "Se": 3.31, "Te": 3.55}        # start in-plane a (A)
BOND = {"S": 2.42, "Se": 2.54, "Te": 2.73}      # start M-X bond (A)
DMM = {"S": 6.2, "Se": 6.5, "Te": 7.0}          # start interlayer M-M (A)
VARIANTS = ["mono2H", "bi2H", "bi3R"]


def build_metas():
    metas = []
    for M in METALS:
        for X in CHALC:
            for v in VARIANTS:
                bil = v.startswith("bi")
                nat = 6 if bil else 3
                metas.append({
                    "name": f"{M}{X}2_{v}", "metal": M, "chalcogen": X,
                    "phase": "2H", "variant": v,
                    "a_angstrom": A0[X], "mx_bond_angstrom": BOND[X],
                    "vacuum_angstrom": 30.0 if bil else 20.0,
                    "d_mm_angstrom": DMM[X], "atoms_per_cell": nat,
                    "vdw": bil, "license": "CC0-1.0"})
    return metas


def sites_for(meta):
    a, c = meta["a_angstrom"], meta["vacuum_angstrom"]
    d = meta["mx_bond_angstrom"]
    h = max(d * d - a * a / 3.0, 0.25) ** 0.5 / c
    M, X = meta["metal"], meta["chalcogen"]
    v = meta["variant"]
    if v == "mono2H":
        return [(M, 1 / 3, 2 / 3, 0.5), (X, 2 / 3, 1 / 3, 0.5 + h),
                (X, 2 / 3, 1 / 3, 0.5 - h)]
    z1 = 0.5 - meta["d_mm_angstrom"] / 2 / c
    z2 = 0.5 + meta["d_mm_angstrom"] / 2 / c
    lower = [(M, 1 / 3, 2 / 3, z1), (X, 2 / 3, 1 / 3, z1 + h),
             (X, 2 / 3, 1 / 3, z1 - h)]
    if v == "bi2H":      # AA': upper layer rotated 180 deg
        upper = [(M, 2 / 3, 1 / 3, z2), (X, 1 / 3, 2 / 3, z2 + h),
                 (X, 1 / 3, 2 / 3, z2 - h)]
    else:                # bi3R, AB: same orientation, shifted by (2/3,1/3)
        upper = [(M, 0.0, 0.0, z2), (X, 1 / 3, 2 / 3, z2 + h),
                 (X, 1 / 3, 2 / 3, z2 - h)]
    return lower + upper


_namelists = rc.namelists


def namelists(meta, *args, **kw):
    L = _namelists(meta, *args, **kw)
    if meta.get("vdw"):
        i = L.index("  degauss = 0.015")
        L[i + 1:i + 1] = ["  vdw_corr = 'dft-d3'", "  dftd3_version = 4"]
    return L


rc.sites_for = sites_for
rc.namelists = namelists


def main():
    rc.RESULTS.mkdir(parents=True, exist_ok=True)
    metas = build_metas()
    json.dump(metas, open(rc.ROOT / "candidates.json", "w"), indent=1)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=rc.WORKERS) as ex:
        recs = list(ex.map(rc.run_candidate, metas))
    summary = {"variants": VARIANTS, "candidates": len(recs),
               "total_node_hours": round(rc.STATE["node_hours"], 3),
               "qe_calls": rc.STATE["qe_calls"],
               "wall_hours": round((time.time() - t0) / 3600, 3),
               "records": recs}
    json.dump(summary, open(rc.RESULTS / "stacking_summary.json", "w"),
              indent=1)
    print("STACKING DONE", summary["candidates"], summary["total_node_hours"])


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Generate the 30 idealized MX2 monolayer prototypes (CC0-1.0).

M in {Ti, Zr, Hf, Mo, W}, X in {S, Se, Te}, phases 1T and 2H.
Structures are *idealized starting geometries* built from covalent-radius
heuristics — they are inputs for an F2 relaxation, not relaxed structures,
and carry no DFT-derived information. Released under CC0-1.0 per the frozen
manifest. Pseudopotentials are NOT bundled; they retain their own licenses.

Outputs: candidates/candidates.json, candidates/<name>.cif, candidates/LICENSE
"""
import json
import os
from pathlib import Path

# Covalent radii (Angstrom, Cordero 2008-style values) and pseudo-valence
# electron counts typical of common QE pseudopotential families.
METALS = {  # radius, valence electrons (semicore included), group class
    "Ti": (1.60, 12, "d0"), "Zr": (1.75, 12, "d0"), "Hf": (1.75, 12, "d0"),
    "Mo": (1.54, 14, "d2"), "W": (1.62, 14, "d2"),
}
CHALCS = {  # radius, valence electrons, idealized wavefunction cutoff (Ry)
    "S": (1.05, 6, 45.0), "Se": (1.20, 6, 40.0), "Te": (1.38, 6, 35.0),
}
PHASES = {"1T": 3, "2H": 6}  # atoms per cell (1 vs 2 formula units)
VACUUM = 18.0  # Angstrom slab spacing (c axis)
A_OVER_D = 1.22  # a = 1.22 * (r_M + r_X); reproduces MoS2 a ~ 3.16 A


def build(metal, chalc, phase):
    r_m, ve_m, mclass = METALS[metal]
    r_x, ve_x, ecut = CHALCS[chalc]
    d = r_m + r_x
    a = round(A_OVER_D * d, 4)
    # chalcogen height above metal plane from bond length and in-plane offset
    dz = round(max(d * d - (a * a) / 3.0, 0.25) ** 0.5, 4)
    natoms = PHASES[phase]
    nelec = (ve_m + 2 * ve_x) * (natoms // 3)
    if phase == "1T":  # octahedral: X at (2/3,1/3,+dz) and (1/3,2/3,-dz)
        sites = [(metal, 0.0, 0.0, 0.5),
                 (chalc, 2 / 3, 1 / 3, 0.5 + dz / VACUUM),
                 (chalc, 1 / 3, 2 / 3, 0.5 - dz / VACUUM)]
    else:  # 2H: trigonal prismatic, two mirrored MX2 layers per cell (2H stacking)
        z1, z2 = 0.35, 0.65
        sites = [(metal, 1 / 3, 2 / 3, z1),
                 (chalc, 2 / 3, 1 / 3, z1 + dz / VACUUM),
                 (chalc, 2 / 3, 1 / 3, z1 - dz / VACUUM),
                 (metal, 2 / 3, 1 / 3, z2),
                 (chalc, 1 / 3, 2 / 3, z2 + dz / VACUUM),
                 (chalc, 1 / 3, 2 / 3, z2 - dz / VACUUM)]
    name = f"{metal}{chalc}2_{phase}"
    meta = {
        "name": name, "metal": metal, "chalcogen": chalc, "phase": phase,
        "metal_class": mclass, "a_angstrom": a, "vacuum_angstrom": VACUUM,
        "mx_bond_angstrom": round(d, 4), "atoms_per_cell": natoms,
        "electrons_per_cell": nelec, "ecutwfc_ry_idealized": ecut,
        "license": "CC0-1.0",
        "provenance": "idealized prototype from covalent-radius heuristic; "
                      "requires F2 relaxation; no DFT-derived content",
    }
    return meta, sites


def cif_text(meta, sites):
    a, c = meta["a_angstrom"], VACUUM
    lines = [
        f"# {meta['name']} — idealized prototype, CC0-1.0, NOT relaxed",
        f"data_{meta['name']}",
        "_symmetry_space_group_name_H-M    'P 1'",
        f"_cell_length_a    {a}",
        f"_cell_length_b    {a}",
        f"_cell_length_c    {c}",
        "_cell_angle_alpha 90.0",
        "_cell_angle_beta  90.0",
        "_cell_angle_gamma 120.0",
        "loop_",
        "_atom_site_label",
        "_atom_site_fract_x",
        "_atom_site_fract_y",
        "_atom_site_fract_z",
    ]
    for k, (el, x, y, z) in enumerate(sites):
        lines.append(f"{el}{k + 1} {x:.6f} {y:.6f} {z:.6f}")
    return "\n".join(lines) + "\n"


def main():
    out = Path(__file__).parent / "candidates"
    out.mkdir(exist_ok=True)
    cands = []
    for metal in METALS:
        for chalc in CHALCS:
            for phase in PHASES:
                meta, sites = build(metal, chalc, phase)
                cands.append(meta)
                (out / f"{meta['name']}.cif").write_text(cif_text(meta, sites))
    (out / "candidates.json").write_text(json.dumps(cands, indent=2) + "\n")
    (out / "LICENSE").write_text(
        "Generated MX2 prototype structures and metadata: CC0-1.0\n"
        "(https://creativecommons.org/publicdomain/zero/1.0/)\n\n"
        "Pseudopotentials are not included; any pseudopotential used in a\n"
        "live pilot retains its original license and must be listed in the\n"
        "case manifest separately.\n")
    print(f"wrote {len(cands)} candidates to {out}")


if __name__ == "__main__":
    main()

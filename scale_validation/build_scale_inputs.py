#!/usr/bin/env python3
"""Build supercell pw.x inputs for the win-win-scale validation run.

Stage 2 predicted the privacy-tax win-win window sits at 10-100x the
measured MX2 task scale. This bundle measures real QE cost at 1x/4x/9x/16x
electron counts (n x n in-plane supercells of two CC0 candidates) at fixed
k-grid and cutoff, testing the fitted electron exponent p_e = 1.20 (prior
2.5) in the regime where cubic scaling should emerge, plus one denser-k
variant to check the assumed k-linearity.

Inputs are derived from ../pilot/inputs/*.pw.in (ibrav=4, crystal coords).
"""
import re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PILOT = HERE.parent / "pilot" / "inputs"

# (candidate, n, kgrid) ; n = in-plane supercell multiplier
MATRIX = [
    ("TiS2_1T", 1, (6, 6, 1)),
    ("TiS2_1T", 2, (6, 6, 1)),
    ("TiS2_1T", 3, (6, 6, 1)),
    ("MoSe2_2H", 1, (6, 6, 1)),
    ("MoSe2_2H", 2, (6, 6, 1)),
    ("MoSe2_2H", 3, (6, 6, 1)),
    ("MoSe2_2H", 2, (12, 12, 1)),   # k-linearity check
    ("MoSe2_2H", 4, (3, 3, 1)),     # 16x electrons: the 10-100x regime
]


def parse_input(path):
    txt = path.read_text()
    a = float(re.search(r"^\s*a = ([\d.]+)", txt, re.M).group(1))
    c = float(re.search(r"^\s*c = ([\d.]+)", txt, re.M).group(1))
    ecut = float(re.search(r"ecutwfc = ([\d.]+)", txt).group(1))
    ecutrho = float(re.search(r"ecutrho = ([\d.]+)", txt).group(1))
    species = re.search(r"ATOMIC_SPECIES\n(.*?)\nATOMIC_POSITIONS",
                        txt, re.S).group(1).rstrip()
    pos = []
    for line in re.search(r"ATOMIC_POSITIONS crystal\n(.*?)\nK_POINTS",
                          txt, re.S).group(1).strip().splitlines():
        el, x, y, z = line.split()
        pos.append((el, float(x), float(y), float(z)))
    return a, c, ecut, ecutrho, species, pos


def build(cand, n, kgrid):
    a, c, ecut, ecutrho, species, pos = parse_input(PILOT / f"{cand}.pw.in")
    ntyp = len(species.splitlines())
    sup = []
    for i in range(n):
        for j in range(n):
            for el, x, y, z in pos:
                sup.append((el, (x + i) / n, (y + j) / n, z))
    name = f"{cand}_s{n}_k{kgrid[0]}"
    lines = [
        "&CONTROL", "  calculation = 'scf'", f"  prefix = '{name}'",
        "  pseudo_dir = './pseudos'", "  outdir = './out'",
        "  disk_io = 'nowf'", "/",
        "&SYSTEM", "  ibrav = 4", f"  a = {a * n:.6f}", f"  c = {c}",
        f"  nat = {len(sup)}", f"  ntyp = {ntyp}",
        f"  ecutwfc = {ecut}", f"  ecutrho = {ecutrho}",
        "  occupations = 'smearing'", "  smearing = 'cold'",
        "  degauss = 0.02", "/",
        "&ELECTRONS", "  mixing_beta = 0.3", "  conv_thr = 1.0d-8",
        "  diagonalization = 'david'", "  electron_maxstep = 80", "/",
        "ATOMIC_SPECIES", species,
        "ATOMIC_POSITIONS crystal",
    ]
    for el, x, y, z in sup:
        lines.append(f"  {el}  {x:.10f}  {y:.10f}  {z:.10f}")
    lines += ["K_POINTS automatic",
              f"  {kgrid[0]} {kgrid[1]} {kgrid[2]} 0 0 0", ""]
    (HERE / "inputs").mkdir(exist_ok=True)
    (HERE / "inputs" / f"{name}.pw.in").write_text("\n".join(lines))
    return name, len(sup)


if __name__ == "__main__":
    for cand, n, kg in MATRIX:
        name, nat = build(cand, n, kg)
        print(f"{name}: nat={nat}")

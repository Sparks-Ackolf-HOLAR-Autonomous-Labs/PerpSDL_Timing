#!/usr/bin/env python3
"""Build pw.x inputs for the layers/N-axis scale-validation extension
(2026-09-08).

Extends the supercell scale run along two further axes:

* layers axis — z-stacks of the CC0 prototypes (Lz repeats of the cell's
  atom group at van-der-Waals spacing, 3.2 A between chalcogen planes),
  crossed with in-plane supercells: does real cost care whether the atoms
  come from layers or in-plane repeats, and do interacting layers change
  SCF iteration counts?
* N / initial-setup axis — same structure with a +-2% strained starting
  lattice ("different initial setup": tests the grid-study assumption
  that setup variants cost the same as their parent), plus a third
  material (WTe2_2H) at both sizes for the material-to-material spread.

All structures derive from ../../pilot/inputs/*.pw.in (CC0 idealized
prototypes; pseudopotentials retain their own licenses).
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PILOT = HERE.parent.parent / "pilot" / "inputs"
GAP_A = 3.2   # vdW gap between chalcogen planes of adjacent stacked units

# (candidate, Lz, in-plane n, strain, kgrid)
MATRIX = [
    ("TiS2_1T", 1, 1, 0.0), ("TiS2_1T", 2, 1, 0.0), ("TiS2_1T", 3, 1, 0.0),
    ("TiS2_1T", 1, 2, 0.0), ("TiS2_1T", 2, 2, 0.0), ("TiS2_1T", 3, 2, 0.0),
    ("MoSe2_2H", 1, 1, 0.0), ("MoSe2_2H", 2, 1, 0.0), ("MoSe2_2H", 3, 1, 0.0),
    ("MoSe2_2H", 1, 2, 0.0), ("MoSe2_2H", 2, 2, 0.0),
    # initial-setup (strain) variants
    ("TiS2_1T", 1, 2, -0.02), ("TiS2_1T", 1, 2, 0.02),
    ("MoSe2_2H", 1, 2, -0.02), ("MoSe2_2H", 1, 2, 0.02),
    # third material for the cross-material spread
    ("WTe2_2H", 1, 1, 0.0), ("WTe2_2H", 1, 2, 0.0),
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


def build(cand, lz, n, strain):
    a, c, ecut, ecutrho, species, pos = parse_input(PILOT / f"{cand}.pw.in")
    zs = [z * c for _, _, _, z in pos]           # angstrom heights
    span = max(zs) - min(zs)
    period = span + GAP_A
    c_new = c + (lz - 1) * period                # keeps >=14 A vacuum
    atoms = []
    for k in range(lz):
        for i in range(n):
            for j in range(n):
                for el, x, y, z in pos:
                    atoms.append((el, (x + i) / n, (y + j) / n,
                                  (z * c + k * period) / c_new))
    tag = f"L{lz}_s{n}" + (f"_e{strain:+.0%}".replace("%", "pct")
                           if strain else "")
    name = f"{cand}_{tag}"
    lines = [
        "&CONTROL", "  calculation = 'scf'", f"  prefix = '{name}'",
        "  pseudo_dir = './pseudos'", "  outdir = './out'",
        "  disk_io = 'nowf'", "/",
        "&SYSTEM", "  ibrav = 4", f"  a = {a * n * (1 + strain):.6f}",
        f"  c = {c_new:.6f}",
        f"  nat = {len(atoms)}", f"  ntyp = {len(species.splitlines())}",
        f"  ecutwfc = {ecut}", f"  ecutrho = {ecutrho}",
        "  occupations = 'smearing'", "  smearing = 'cold'",
        "  degauss = 0.02", "/",
        "&ELECTRONS", "  mixing_beta = 0.3", "  conv_thr = 1.0d-8",
        "  diagonalization = 'david'", "  electron_maxstep = 80", "/",
        "ATOMIC_SPECIES", species,
        "ATOMIC_POSITIONS crystal",
    ]
    for el, x, y, z in atoms:
        lines.append(f"  {el}  {x:.10f}  {y:.10f}  {z:.10f}")
    lines += ["K_POINTS automatic", "  6 6 1 0 0 0", ""]
    (HERE / "inputs").mkdir(exist_ok=True)
    (HERE / "inputs" / f"{name}.pw.in").write_text("\n".join(lines))
    return name, len(atoms)


if __name__ == "__main__":
    for cand, lz, n, strain in MATRIX:
        name, nat = build(cand, lz, n, strain)
        print(f"{name}: nat={nat}")

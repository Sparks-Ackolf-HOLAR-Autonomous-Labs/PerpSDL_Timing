#!/usr/bin/env python3
"""Build pw.x inputs for live comparison No. 2.

8x8 in-plane supercells of the measured relaxed 1x1 geometries for all
29 CC0 MX2 candidates (HfSe2-2H excluded upstream: never relaxed), at
the frozen post-cofit design scale. The 1x1 motif is recovered from the
committed 3x3 inputs of live comparison No. 1 (their first nat/9 atoms
are the (0,0) replica by construction of build_live_inputs.py).

Stages (identical physics in both arms; npool = 1 everywhere per probe
1928420 -- lean wins at this scale, k-grids are tiny):

  f1  coarse SCF      ecut 40/320, Gamma-only, conv 1e-6
  f2  production SCF  ecut 45/360, Gamma-only (folds the 1x1 8x8
                      density; preregistered scope amendment -- the
                      probe's measured 8x8 anchor walls are exactly
                      this configuration), conv 1e-8
  f3  NSCF bands      ecut 45/360, Gamma-only, nbnd = 1.10*nocc + 16,
                      conv 1e-8

Also writes manifest2.json with the reservation model each arm uses:

  ram_est_gb : total-node RAM estimate at 16 ranks, nk1, anchored to
               the measured probe points (MoSe2_2H 8x8 = 112 GB,
               TiS2_1T 6x6 = 30.9 GB) with electrons^1.55 scaling per
               phase and the measured iso-electron chalcogen factor
               (WTe2/MoSe2 = 1.235 -> Te 1.235, Se 1.0, S 0.90).
  mem_bit    : 1 if ram_est_gb above the population median (the single
               preregistered CEDT-P4 disclosure; Theorem-3 threshold
               statistic).
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "paired_comparison_1" / "inputs"
OUT = HERE / "inputs"
N = 8
CHALC_FACTOR = {"S": 0.90, "Se": 1.00, "Te": 1.235}
VALENCE = {"Ti": 12, "Zr": 12, "Hf": 12, "Mo": 14, "W": 14,
           "S": 6, "Se": 6, "Te": 6}


def parse3x3(path):
    txt = path.read_text()
    g = lambda p: float(re.search(p, txt, re.M).group(1))
    a3 = g(r"^\s*a = ([\d.]+)")
    c = g(r"^\s*c = ([\d.]+)")
    nat3 = int(g(r"nat = (\d+)"))
    species = re.search(r"ATOMIC_SPECIES\n(.*?)\nATOMIC_POSITIONS",
                        txt, re.S).group(1).rstrip()
    pos3 = []
    for line in re.search(r"ATOMIC_POSITIONS crystal\n(.*?)\nK_POINTS",
                          txt, re.S).group(1).strip().splitlines():
        el, x, y, z = line.split()
        pos3.append((el, float(x), float(y), float(z)))
    motif = [(el, x * 3, y * 3, z) for el, x, y, z in pos3[:nat3 // 9]]
    return a3 / 3, c, species, motif


def stage_block(name, calc, a, c, nat, ntyp, ecut, ecutrho, conv,
                species, sup, nbnd=None):
    lines = ["&CONTROL", f"  calculation = '{calc}'",
             f"  prefix = '{name}'", "  pseudo_dir = './pseudos'",
             "  outdir = './out'", "  verbosity = 'high'",
             "  disk_io = 'nowf'" if calc == "scf" else
             "  disk_io = 'low'", "/",
             "&SYSTEM", "  ibrav = 4", f"  a = {a:.6f}", f"  c = {c}",
             f"  nat = {nat}", "  ntyp = %d" % ntyp,
             f"  ecutwfc = {ecut}", f"  ecutrho = {ecutrho}",
             "  occupations = 'smearing'", "  smearing = 'cold'",
             "  degauss = 0.015"]
    if nbnd:
        lines.append(f"  nbnd = {nbnd}")
    lines += ["/", "&ELECTRONS", "  mixing_beta = 0.3",
              f"  conv_thr = {conv}", "  diagonalization = 'david'",
              "  electron_maxstep = 120", "/",
              "ATOMIC_SPECIES", species, "ATOMIC_POSITIONS crystal"]
    for el, x, y, z in sup:
        lines.append(f"  {el}  {x:.10f}  {y:.10f}  {z:.10f}")
    # NOTE: "automatic 1 1 1" (complex wavefunctions), NOT "gamma":
    # the measured 8x8 anchor (probe 1928420, MoSe2_2H 11,767 s /
    # 112 GB) is this configuration, and the reservation mechanism
    # needs the un-halved RAM footprint.
    lines += ["K_POINTS automatic", "  1 1 1 0 0 0", ""]
    return "\n".join(lines)


def main():
    OUT.mkdir(exist_ok=True)
    man1 = json.load(open(SRC / "manifest.json"))
    rows = []
    for m in man1:
        name = m["name"]
        a1, c, species, motif = parse3x3(SRC / f"{name}.f2.in")
        ntyp = len(species.splitlines())
        sup = [(el, (x + i) / N, (y + j) / N, z)
               for i in range(N) for j in range(N)
               for el, x, y, z in motif]
        nat = len(sup)
        nelec = sum(VALENCE[el] for el, *_ in sup)
        nocc = nelec // 2
        phase = "2H" if "_2H" in name else "1T"
        chalc = re.match(r"[A-Z][a-z]?([SsTe]+e?\d?|S\d?|Te\d?|Se\d?)",
                         name)
        x_el = ("Te" if "Te2" in name else
                "Se" if "Se2" in name else "S")
        cf = CHALC_FACTOR[x_el]
        if phase == "2H":
            ram = 112.0 * (nelec / 3328.0) ** 1.55 * cf
        else:
            ram = 30.9 * (nelec / 864.0) ** 1.55 * (cf / 0.90)
        for stage, calc, ecut, rho, conv, nbnd in (
                ("f1", "scf", 40.0, 320.0, "1.0d-6", None),
                ("f2", "scf", 45.0, 360.0, "1.0d-8", None),
                ("f3", "nscf", 45.0, 360.0, "1.0d-8",
                 int(nocc * 1.10) + 16)):
            (OUT / f"{name}.{stage}.in").write_text(stage_block(
                name, calc, a1 * N, c, nat, ntyp, ecut, rho, conv,
                species, sup, nbnd))
        rows.append({"name": name, "phase": phase, "nat": nat,
                     "nelec": nelec, "x": x_el,
                     "ram_est_gb": round(ram, 1),
                     "gap_1x1_ev": m.get("gap_1x1_ev")})
    med = sorted(r["ram_est_gb"] for r in rows)[len(rows) // 2]
    for r in rows:
        r["mem_bit"] = int(r["ram_est_gb"] > med)
    json.dump({"n_super": N, "ram_median_gb": med, "candidates": rows},
              open(OUT / "manifest2.json", "w"), indent=1)
    hi = [r for r in rows if r["mem_bit"]]
    print(f"{len(rows)} candidates; RAM est {min(r['ram_est_gb'] for r in rows)}"
          f"-{max(r['ram_est_gb'] for r in rows)} GB, median {med}, "
          f"{len(hi)} high-bit")


if __name__ == "__main__":
    main()

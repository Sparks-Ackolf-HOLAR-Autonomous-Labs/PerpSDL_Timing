#!/usr/bin/env python3
"""Build transfer-probe pw.x inputs (future-work item 5):
does the fitted cost twin survive other task families?

  defect  MoS2_2H 3x3 supercell with one S vacancy (53 atoms) — defect
          workload probe
  hetero  MoS2/WS2 vertical heterobilayer, 2x2 supercell (24 atoms,
          3 species): the second 2H layer's Mo is substituted by W —
          heterostructure workload probe

Both are SCF-only cost probes at the measured relaxed MoS2_2H geometry
(CC0). The twin's prediction is computed from electron count alone; the
probe measures whether family structure (broken symmetry, mixed
species) shifts cost off the MX2-fitted law.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent / "dft_campaign" / "results" / "campaign_summary.json"
CANDS = HERE.parent / "prior_predictive" / "candidates" / "candidates.json"

PSEUDO = {"Mo": "mo_pbe_v1.uspp.F.UPF", "W": "w_pbe_v1.2.uspp.F.UPF",
          "S": "s_pbe_v1.4.uspp.F.UPF"}
MASS = {"Mo": 95.95, "W": 183.84, "S": 32.06}


def get_relaxed(name):
    summary = json.load(open(CAMPAIGN))
    rec = next(r for r in summary["records"] if r["candidate"] == name)
    meta = next(m for m in json.load(open(CANDS)) if m["name"] == name)
    return (rec.get("a_relaxed_angstrom", meta["a_angstrom"]),
            meta["vacuum_angstrom"],
            rec["stages"]["F2"]["final_positions_crystal"])


def deck(name, a, c, sup, species):
    L = ["&CONTROL", "  calculation = 'scf'", f"  prefix = '{name}'",
         "  pseudo_dir = './pseudos'", "  outdir = './out'",
         "  disk_io = 'nowf'", "/",
         "&SYSTEM", "  ibrav = 4", f"  a = {a:.6f}", f"  c = {c}",
         f"  nat = {len(sup)}", f"  ntyp = {len(species)}",
         "  ecutwfc = 45.0", "  ecutrho = 360.0",
         "  occupations = 'smearing'", "  smearing = 'cold'",
         "  degauss = 0.015", "/",
         "&ELECTRONS", "  mixing_beta = 0.3", "  conv_thr = 1.0d-7",
         "  diagonalization = 'david'", "  electron_maxstep = 150", "/",
         "ATOMIC_SPECIES"]
    for s in species:
        L.append(f"  {s}  {MASS[s]}  {PSEUDO[s]}")
    L.append("ATOMIC_POSITIONS crystal")
    for el, x, y, z in sup:
        L.append(f"  {el}  {x:.10f}  {y:.10f}  {z:.10f}")
    L += ["K_POINTS automatic", "  4 4 1 0 0 0", ""]
    (HERE / "inputs" / f"{name}.pw.in").write_text("\n".join(L))
    print(f"{name}: nat={len(sup)} ntyp={len(species)}")


def main():
    (HERE / "inputs").mkdir(exist_ok=True)
    a, c, pos = get_relaxed("MoS2_2H")

    # defect: 3x3, drop the first S of the first replica
    n = 3
    sup = [(el, (x + i) / n, (y + j) / n, z)
           for i in range(n) for j in range(n) for el, x, y, z in pos]
    for idx, (el, *_xyz) in enumerate(sup):
        if el == "S":
            del sup[idx]
            break
    deck("MoS2_3x3_Svac", a * n, c, sup, ["Mo", "S"])

    # hetero: 2x2, substitute layer-2 (z > 0.5) Mo -> W
    n = 2
    sup = []
    for i in range(n):
        for j in range(n):
            for el, x, y, z in pos:
                el2 = "W" if (el == "Mo" and z > 0.5) else el
                sup.append((el2, (x + i) / n, (y + j) / n, z))
    deck("MoS2_WS2_hetero_2x2", a * n, c, sup, ["Mo", "W", "S"])


if __name__ == "__main__":
    main()

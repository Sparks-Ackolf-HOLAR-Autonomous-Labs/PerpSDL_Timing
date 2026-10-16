#!/usr/bin/env python3
"""Build pw.x inputs for the live CEDT-P4 vs DTDE comparison
(future-work item 1).

Task: the CC0 MX2 candidates at 3x3-supercell scale (the x30-x100
operating point located by scale_validation/), F1 -> F2 -> F3 ladder:

  F1  coarse SCF   (ecut 40 Ry, 2x2 k, conv 1e-6)  viability + cost row
  F2  production SCF at the measured relaxed geometry
                   (ecut 45 Ry, 4x4 k, conv 1e-8)  the "valid F2 label"
  F3  dense NSCF   (6x6 k, extended bands)          PBE screening gap

Geometries are the *measured relaxed* structures from the real 1x1 DFT
campaign (dft_campaign/results/campaign_summary.json, 29/30 candidates;
HfSe2_2H never converged and is excluded). Using SCF-at-relaxed-geometry
instead of a fresh 54-atom vc-relax is a preregistered scope amendment
(budget): the label quality claim is "production SCF at a converged
geometry", not "fresh relaxation".

Inputs are arm-independent: the two arms differ only in execution
config (mpirun -np / -nk), never in physics.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent / "dft_campaign" / "results" / "campaign_summary.json"
CANDS = HERE.parent / "prior_predictive" / "candidates" / "candidates.json"

PSEUDO = {"Ti": "ti_pbe_v1.4.uspp.F.UPF", "Zr": "zr_pbe_v1.uspp.F.UPF",
          "Hf": "hf_pbe_v1.uspp.F.UPF", "Mo": "mo_pbe_v1.uspp.F.UPF",
          "W": "w_pbe_v1.2.uspp.F.UPF", "S": "s_pbe_v1.4.uspp.F.UPF",
          "Se": "se_pbe_v1.uspp.F.UPF", "Te": "te_pbe_v1.uspp.F.UPF"}
MASS = {"Ti": 47.867, "Zr": 91.224, "Hf": 178.49, "Mo": 95.95,
        "W": 183.84, "S": 32.06, "Se": 78.971, "Te": 127.60}
N = 3  # in-plane supercell multiplier


def build(meta, rec):
    name = meta["name"]
    f2 = rec["stages"]["F2"]
    a = rec.get("a_relaxed_angstrom", meta["a_angstrom"])
    c = meta["vacuum_angstrom"]
    pos = f2["final_positions_crystal"]
    sup = [(el, (x + i) / N, (y + j) / N, z)
           for i in range(N) for j in range(N) for el, x, y, z in pos]
    M, X = meta["metal"], meta["chalcogen"]
    nelec_sc = rec["stages"]["F1"]["nelec"] * N * N
    nbnd = int(nelec_sc // 2 + max(8, int(nelec_sc * 0.2)))

    def deck(stage, calc, ecut, conv, kn, extra_sys=(), disk="'nowf'"):
        L = ["&CONTROL", f"  calculation = '{calc}'",
             f"  prefix = '{name}'", "  pseudo_dir = './pseudos'",
             "  outdir = './out'", "  verbosity = 'high'",
             f"  disk_io = {disk}", "/",
             "&SYSTEM", "  ibrav = 4", f"  a = {a * N:.6f}", f"  c = {c}",
             f"  nat = {len(sup)}", "  ntyp = 2",
             f"  ecutwfc = {ecut}", f"  ecutrho = {8 * ecut}",
             "  occupations = 'smearing'", "  smearing = 'cold'",
             "  degauss = 0.015"]
        L += list(extra_sys)
        L += ["/", "&ELECTRONS", "  mixing_beta = 0.3",
              f"  conv_thr = {conv}",
              "  diagonalization = 'david'", "  electron_maxstep = 120",
              "/",
              "ATOMIC_SPECIES",
              f"  {M}  {MASS[M]}  {PSEUDO[M]}",
              f"  {X}  {MASS[X]}  {PSEUDO[X]}",
              "ATOMIC_POSITIONS crystal"]
        for el, x, y, z in sup:
            L.append(f"  {el}  {x:.10f}  {y:.10f}  {z:.10f}")
        L += ["K_POINTS automatic", f"  {kn} {kn} 1 0 0 0", ""]
        (HERE / "inputs" / f"{name}.{stage}.in").write_text("\n".join(L))

    deck("f1", "scf", 40.0, "1.0d-6", 2)
    deck("f2", "scf", 45.0, "1.0d-8", 4, disk="'low'")
    deck("f3", "nscf", 45.0, "1.0d-8", 6,
         extra_sys=[f"  nbnd = {nbnd}"], disk="'nowf'")
    return len(sup), nelec_sc


def main():
    (HERE / "inputs").mkdir(exist_ok=True)
    metas = {m["name"]: m for m in json.load(open(CANDS))}
    summary = json.load(open(CAMPAIGN))
    manifest = []
    for rec in summary["records"]:
        f2 = rec["stages"].get("F2", {})
        if not (f2.get("relax_converged")
                and f2.get("final_positions_crystal")):
            print(f"SKIP {rec['candidate']} (no converged relaxed geometry)")
            continue
        nat, nelec = build(metas[rec["candidate"]], rec)
        manifest.append(dict(name=rec["candidate"], nat=nat,
                             nelec=nelec,
                             gap_1x1_ev=rec.get("gap_ev")))
    json.dump(manifest, open(HERE / "inputs" / "manifest.json", "w"),
              indent=1)
    print(f"built {len(manifest)} candidates x 3 stages "
          f"into {HERE / 'inputs'}")


if __name__ == "__main__":
    main()

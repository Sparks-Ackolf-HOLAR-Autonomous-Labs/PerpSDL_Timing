#!/usr/bin/env python3
"""Build the F1 pilot inputs and the randomized 81-row job matrix.

Uses only the CC0-1.0 candidate metadata (../prior_predictive/candidates).
Pseudopotentials are NOT bundled: run with --check-pseudos after placing
the GBRV 1.5 ultrasoft PBE UPFs in pilot/pseudos/ to freeze their hashes
(the measured run's hashes: results/pseudos_manifest.txt).
"""
import argparse
import csv
import hashlib
import json
import random
from pathlib import Path

HERE = Path(__file__).parent
CANDS = HERE.parent / "prior_predictive" / "candidates"

# small / medium / large by electrons_per_cell (24 / 60 / 72)
SIZES = ["TiS2_1T", "MoSe2_2H", "WTe2_2H"]
# simulator config space: (nodes, npool, aggressive)
CONFIGS = [(1, 1, 0), (1, 2, 0), (2, 1, 0), (2, 2, 0), (2, 4, 0),
           (4, 2, 0), (4, 4, 0), (4, 4, 1), (2, 2, 1)]
REPEATS = 3
SHUFFLE_SEED = 20260902

PSEUDO = {"Ti": "ti_pbe_v1.4.uspp.F.UPF", "Zr": "Zr_pbe_v1.uspp.F.UPF",
          "Hf": "Hf-sp.oncvpsp.upf", "Mo": "Mo_ONCV_PBE-1.0.oncvpsp.upf",
          "W": "W_pbe_v1.2.uspp.F.UPF", "S": "s_pbe_v1.4.uspp.F.UPF",
          "Se": "Se_pbe_v1.uspp.F.UPF", "Te": "Te_pbe_v1.uspp.F.UPF"}
MASS = {"Ti": 47.867, "Zr": 91.224, "Hf": 178.49, "Mo": 95.95,
        "W": 183.84, "S": 32.06, "Se": 78.971, "Te": 127.60}


def sites_for(meta):
    a, vac = meta["a_angstrom"], meta["vacuum_angstrom"]
    d = meta["mx_bond_angstrom"]
    dz = max(d * d - (a * a) / 3.0, 0.25) ** 0.5
    M, X = meta["metal"], meta["chalcogen"]
    if meta["phase"] == "1T":
        return [(M, 0.0, 0.0, 0.5),
                (X, 2 / 3, 1 / 3, 0.5 + dz / vac),
                (X, 1 / 3, 2 / 3, 0.5 - dz / vac)]
    z1, z2 = 0.35, 0.65
    return [(M, 1 / 3, 2 / 3, z1), (X, 2 / 3, 1 / 3, z1 + dz / vac),
            (X, 2 / 3, 1 / 3, z1 - dz / vac),
            (M, 2 / 3, 1 / 3, z2), (X, 1 / 3, 2 / 3, z2 + dz / vac),
            (X, 1 / 3, 2 / 3, z2 - dz / vac)]


def pw_input(meta, aggressive):
    a, vac = meta["a_angstrom"], meta["vacuum_angstrom"]
    M, X = meta["metal"], meta["chalcogen"]
    mix, conv = (0.7, "1.0d-6") if aggressive else (0.3, "1.0d-8")
    sites = sites_for(meta)
    lines = [
        "&CONTROL",
        "  calculation = 'scf'",
        f"  prefix = '{meta['name']}'",
        "  pseudo_dir = './pseudos'",
        "  outdir = './out'",
        "  disk_io = 'nowf'",
        "/",
        "&SYSTEM",
        "  ibrav = 4",
        f"  a = {a}",
        f"  c = {vac}",
        f"  nat = {meta['atoms_per_cell']}",
        "  ntyp = 2",
        f"  ecutwfc = {meta['ecutwfc_ry_idealized']}",
        f"  ecutrho = {8 * meta['ecutwfc_ry_idealized']}",
        "  occupations = 'smearing'",
        "  smearing = 'cold'",
        "  degauss = 0.02",
        "/",
        "&ELECTRONS",
        f"  mixing_beta = {mix}",
        f"  conv_thr = {conv}",
        "  diagonalization = 'david'",
        "  electron_maxstep = 60",
        "/",
        "ATOMIC_SPECIES",
        f"  {M}  {MASS[M]}  {PSEUDO[M]}",
        f"  {X}  {MASS[X]}  {PSEUDO[X]}",
        "ATOMIC_POSITIONS crystal",
    ]
    for s, x, y, z in sites:
        lines.append(f"  {s}  {x:.10f}  {y:.10f}  {z:.10f}")
    lines += ["K_POINTS automatic", "  6 6 1 0 0 0", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-pseudos", action="store_true")
    args = ap.parse_args()

    metas = {m["name"]: m for m in
             json.load(open(CANDS / "candidates.json"))}
    (HERE / "inputs").mkdir(exist_ok=True)
    for name in SIZES:
        for agg in (0, 1):
            suffix = "_agg" if agg else ""
            (HERE / "inputs" / f"{name}{suffix}.pw.in").write_text(
                pw_input(metas[name], agg))

    rows = []
    jid = 0
    for name in SIZES:
        for (nodes, npool, agg) in CONFIGS:
            for rep in range(REPEATS):
                rows.append(dict(job_id=jid, candidate=name, nodes=nodes,
                                 npool=npool, aggressive=agg, repeat=rep))
                jid += 1
    random.Random(SHUFFLE_SEED).shuffle(rows)
    for order, r in enumerate(rows):
        r["submit_order"] = order
    rows.sort(key=lambda r: r["submit_order"])
    with open(HERE / "job_matrix.csv", "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=["submit_order", "job_id",
                                            "candidate", "nodes", "npool",
                                            "aggressive", "repeat"])
        wr.writeheader()
        wr.writerows(rows)
    print(f"wrote {len(rows)} jobs to job_matrix.csv and "
          f"{2 * len(SIZES)} pw.x inputs")

    if args.check_pseudos:
        man = {}
        missing = []
        for el, fn in PSEUDO.items():
            p = HERE / "pseudos" / fn
            if p.exists():
                man[fn] = hashlib.sha256(p.read_bytes()).hexdigest()
            else:
                missing.append(fn)
        json.dump(man, open(HERE / "pseudos_manifest.json", "w"), indent=2)
        if missing:
            print("MISSING pseudopotentials (download the GBRV 1.5 "
                  "ultrasoft PBE set):", *missing, sep="\n  ")
        else:
            print("all pseudopotentials present; hashes frozen in "
                  "pseudos_manifest.json")


if __name__ == "__main__":
    main()

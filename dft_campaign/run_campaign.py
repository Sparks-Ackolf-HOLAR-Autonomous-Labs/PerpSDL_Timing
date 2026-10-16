#!/usr/bin/env python3
"""Actual-DFT campaign driver for the QE privacy-tax experiment.

Runs the real fidelity ladder on the 30 CC0-1.0 idealized MX2 candidates
with Quantum ESPRESSO (pw.x / ph.x) on a single node:

  F1  coarse SCF at the idealized geometry (viability + cost row)
  F2  vc-relax with cell_dofree='2Dxy' (in-plane lattice + ions), which
      ends in a production-quality final SCF
  F3  dense-grid NSCF -> PBE screening gap (eigenvalue HOMO/LUMO scan)
  F4  Gamma-point ph.x for qualifiers (gap in [1.0, 2.0] eV), explicitly
      NOT a full dynamical-stability proof

Every stage records the target outcome vector fields: convergence flags,
final max force, total energy, gap, phonon min frequency, QE calls,
node-hours (wall * cores_used/64 on grn061), wall time, peak rank RSS,
failure and restart counts.  A soft node-hour budget guard stops new work
before the cap; SLURM --time is the hard limit.

Designed to run inside a SLURM allocation on granite grn061 (64 cores).
Interpretation limits (frozen in case_manifest.yaml): Gamma phonons are
not dynamical stability; PBE gaps are screening quantities; total
energies are never ranked across compositions (only 1T-2H within one).
"""
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(os.environ.get("MPT_DFT_ROOT", ".")).resolve()
PSEUDO_DIR = ROOT / "pseudos"
WORK = ROOT / "work"
RESULTS = ROOT / "results"
NPROC = int(os.environ.get("MPT_NPROC_PER_RUN", "16"))
NPOOL = int(os.environ.get("MPT_NPOOL", "4"))
WORKERS = int(os.environ.get("MPT_WORKERS", "3"))
NODE_CORES = 64.0
# node time limit 20160 minutes for the entire run (hard SLURM
# limit); soft guard slightly under it
NODE_HOUR_CAP = float(os.environ.get("MPT_NODE_HOUR_CAP", "330"))
GAP_WINDOW = (1.0, 2.0)

PSEUDO = {"Ti": "ti_pbe_v1.4.uspp.F.UPF", "Zr": "zr_pbe_v1.uspp.F.UPF",
          "Hf": "hf_pbe_v1.uspp.F.UPF", "Mo": "mo_pbe_v1.uspp.F.UPF",
          "W": "w_pbe_v1.2.uspp.F.UPF", "S": "s_pbe_v1.4.uspp.F.UPF",
          "Se": "se_pbe_v1.uspp.F.UPF", "Te": "te_pbe_v1.uspp.F.UPF"}
MASS = {"Ti": 47.867, "Zr": 91.224, "Hf": 178.49, "Mo": 95.95,
        "W": 183.84, "S": 32.06, "Se": 78.971, "Te": 127.60}

spent_lock = __import__("threading").Lock()
STATE = {"node_hours": 0.0, "qe_calls": 0, "stopped": False}


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


def namelists(meta, calc, ecut, conv, mixing=0.3, maxstep=100, nbnd=None,
              diag="david"):
    M, X = meta["metal"], meta["chalcogen"]
    L = ["&CONTROL",
         f"  calculation = '{calc}'",
         f"  prefix = '{meta['name']}'",
         f"  pseudo_dir = '{PSEUDO_DIR}'",
         "  outdir = './out'",
         "  verbosity = 'high'"]
    if calc == "vc-relax":
        L += ["  etot_conv_thr = 1.0d-5", "  forc_conv_thr = 1.0d-4",
              "  nstep = 100"]
    L += ["/", "&SYSTEM", "  ibrav = 4",
          f"  a = {meta['a_angstrom']}", f"  c = {meta['vacuum_angstrom']}",
          f"  nat = {meta['atoms_per_cell']}", "  ntyp = 2",
          f"  ecutwfc = {ecut}", f"  ecutrho = {8 * ecut}",
          "  occupations = 'smearing'", "  smearing = 'cold'",
          "  degauss = 0.015"]
    if nbnd:
        L.append(f"  nbnd = {nbnd}")
    L += ["/", "&ELECTRONS",
          f"  mixing_beta = {mixing}",
          f"  conv_thr = {conv}",
          f"  diagonalization = '{diag}'",
          f"  electron_maxstep = {maxstep}",
          "/"]
    if calc == "vc-relax":
        L += ["&IONS", "  ion_dynamics = 'bfgs'", "/",
              "&CELL", "  cell_dynamics = 'bfgs'",
              "  cell_dofree = '2Dxy'", "  press_conv_thr = 0.1", "/"]
    L += ["ATOMIC_SPECIES",
          f"  {M}  {MASS[M]}  {PSEUDO[M]}",
          f"  {X}  {MASS[X]}  {PSEUDO[X]}"]
    return L


def kcard(n):
    return ["K_POINTS automatic", f"  {n} {n} 1 0 0 0", ""]


def run_qe(exe, workdir, inp, tag):
    """Run one QE executable; returns dict with wall/mem/ok and adds spend."""
    with spent_lock:
        if STATE["node_hours"] >= NODE_HOUR_CAP:
            STATE["stopped"] = True
            return {"ok": False, "skipped": "budget_cap"}
        STATE["qe_calls"] += 1
    out = workdir / f"{tag}.out"
    t0 = time.time()
    cmd = ["/usr/bin/time", "-v", "-o", str(workdir / f"{tag}.time"),
           "mpirun", "-np", str(NPROC), "--bind-to", "none",
           exe, "-nk", str(NPOOL), "-in", str(workdir / f"{tag}.in")]
    with open(out, "w") as fh:
        rc = subprocess.call(cmd, cwd=workdir, stdout=fh,
                             stderr=subprocess.STDOUT)
    wall = time.time() - t0
    nh = wall / 3600.0 * (NPROC / NODE_CORES)
    with spent_lock:
        STATE["node_hours"] += nh
    mem_kb = None
    tf = workdir / f"{tag}.time"
    if tf.exists():
        m = re.search(r"Maximum resident set size.*: (\d+)", tf.read_text())
        if m:
            mem_kb = int(m.group(1))
    return {"ok": rc == 0, "rc": rc, "wall_s": round(wall, 1),
            "node_hours": round(nh, 4),
            "peak_rank_rss_gb": round(mem_kb / 1048576, 3) if mem_kb else None,
            "out": str(out)}


def parse_pw(outfile):
    txt = Path(outfile).read_text(errors="replace")
    d = {"scf_converged": "convergence has been achieved" in txt,
         "job_done": "JOB DONE" in txt}
    m = re.findall(r"!\s+total energy\s+=\s+(-?[\d.]+) Ry", txt)
    d["etot_ry"] = float(m[-1]) if m else None
    m = re.findall(r"Total force =\s+([\d.]+)", txt)
    d["total_force_ry_au"] = float(m[-1]) if m else None
    m = re.search(r"number of electrons\s+=\s+([\d.]+)", txt)
    d["nelec"] = float(m.group(1)) if m else None
    d["relax_converged"] = ("Begin final coordinates" in txt)
    m = re.findall(r"CELL_PARAMETERS \(alat=\s*([\d.]+)\)\n\s+([\d.\-]+)\s+([\d.\-]+)", txt)
    if m:
        alat, ax = float(m[-1][0]), float(m[-1][1])
        d["a_relaxed_angstrom"] = round(alat * ax * 0.529177210903, 4)
    # final fractional coordinates from vc-relax
    fin = re.search(r"Begin final coordinates(.*?)End final coordinates",
                    txt, re.S)
    if fin:
        pos = re.findall(r"^([A-Z][a-z]?)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s*$",
                         fin.group(1), re.M)
        d["final_positions_crystal"] = [
            [s, float(x), float(y), float(z)] for s, x, y, z in pos]
    return d


def parse_gap(outfile, nelec):
    """Indirect screening gap from verbosity=high eigenvalue blocks."""
    txt = Path(outfile).read_text(errors="replace")
    blocks = re.findall(r"k =[^\n]*\([ 0-9]+ PWs\)\s+bands \(ev\):\n\n((?:\s+-?[\d.]+)+)",
                        txt)
    if not blocks or not nelec:
        return None
    nocc = int(round(nelec)) // 2
    vbm, cbm = -1e9, 1e9
    for b in blocks:
        ev = [float(x) for x in b.split()]
        if len(ev) <= nocc:
            return None
        vbm = max(vbm, ev[nocc - 1])
        cbm = min(cbm, ev[nocc])
    gap = cbm - vbm
    return {"vbm_ev": round(vbm, 4), "cbm_ev": round(cbm, 4),
            "gap_ev": round(max(gap, 0.0), 4),
            "metallic": gap < 0.05}


def parse_ph(outfile):
    txt = Path(outfile).read_text(errors="replace")
    freqs = [float(f) for f in
             re.findall(r"freq \(\s*\d+\) =\s*-?[\d.]+\s*\[THz\] =\s*"
                        r"(-?[\d.]+)\s*\[cm-1\]", txt)]
    if not freqs:
        return {"ph_done": "JOB DONE" in txt, "freqs_cm1": None}
    return {"ph_done": "JOB DONE" in txt,
            "freqs_cm1": freqs,
            "min_freq_cm1": min(freqs),
            # tolerance: acoustic modes at Gamma sit near 0 numerically
            "gamma_unstable": min(freqs) < -30.0}


def poscard(positions):
    L = ["ATOMIC_POSITIONS crystal"]
    for s, x, y, z in positions:
        L.append(f"  {s}  {x:.10f}  {y:.10f}  {z:.10f}")
    return L


def stage_input(meta, stage, workdir, nbnd=None, retry=False,
                positions=None):
    """positions: relaxed fractional coords (F3/F4SCF); default idealized.

    NSCF/phonon stages must be given the *relaxed* geometry explicitly:
    pw.x takes the cell/positions from the input file, only the density
    comes from outdir, and ph.x cannot start from an NSCF state.
    """
    mix = 0.2 if retry else 0.3
    steps = 200 if retry else 100
    diag = "cg" if retry else "david"
    pos = positions or sites_for(meta)
    if stage == "F1":
        L = namelists(meta, "scf", 40.0, "1.0d-6", mix, steps, diag=diag)
        L += poscard(pos) + kcard(6)
    elif stage == "F2":
        L = namelists(meta, "vc-relax", 45.0, "1.0d-8", mix, steps,
                      diag=diag)
        L += poscard(pos) + kcard(12)
    elif stage == "F4SCF":
        L = namelists(meta, "scf", 45.0, "1.0d-9", mix, steps, diag=diag)
        L += poscard(pos) + kcard(12)
    elif stage == "F3":
        # retry uses cg: Davidson NSCF can die with "cdiaghg: S matrix
        # not positive definite" on these USPP monolayers
        L = namelists(meta, "nscf", 45.0, "1.0d-8", nbnd=nbnd,
                      diag="cg" if retry else "david")
        L += poscard(pos) + kcard(18)
    (workdir / f"{stage.lower()}.in").write_text("\n".join(L))


def ph_input(meta, workdir):
    (workdir / "f4.in").write_text("\n".join([
        "gamma phonon check (not a stability proof)",
        "&INPUTPH",
        f"  prefix = '{meta['name']}'",
        "  outdir = './out'",
        "  tr2_ph = 1.0d-14",
        "  epsil = .false.",
        "  asr = .true.",
        "/",
        "0.0 0.0 0.0",
        ""]))


def emit(rec):
    with spent_lock:
        with open(RESULTS / "outcomes.jsonl", "a") as fh:
            fh.write(json.dumps(rec) + "\n")


def run_candidate(meta):
    name = meta["name"]
    wd = WORK / name
    wd.mkdir(parents=True, exist_ok=True)
    rec = {"candidate": name, "phase": meta["phase"],
           "metal": meta["metal"], "chalcogen": meta["chalcogen"],
           "stages": {}, "failures": 0, "restarts": 0}
    nelec = None
    for stage in ("F1", "F2"):
        stage_input(meta, stage, wd)
        r = run_qe("pw.x", wd, None, stage.lower())
        if r.get("skipped"):
            rec["stages"][stage] = r
            emit(rec)
            return rec
        p = parse_pw(r["out"]) if r["ok"] else {}
        conv = p.get("scf_converged") and (stage == "F1"
                                           or p.get("relax_converged"))
        if not conv:
            rec["restarts"] += 1
            stage_input(meta, stage, wd, retry=True)
            r2 = run_qe("pw.x", wd, None, stage.lower())
            if not r2.get("skipped") and r2["ok"]:
                p2 = parse_pw(r2["out"])
                if p2.get("scf_converged"):
                    r, p = r2, p2
                    conv = stage == "F1" or p.get("relax_converged")
        rec["stages"][stage] = {**r, **p}
        if p.get("nelec"):
            nelec = p["nelec"]
        if not conv:
            rec["failures"] += 1
            rec["stages"][stage]["stage_failed"] = True
            if stage == "F2":
                emit(rec)
                return rec
    # relaxed geometry for the higher-fidelity stages
    f2 = rec["stages"]["F2"]
    meta_rel = dict(meta)
    if f2.get("a_relaxed_angstrom"):
        meta_rel["a_angstrom"] = f2["a_relaxed_angstrom"]
    pos_rel = f2.get("final_positions_crystal")
    rec["a_relaxed_angstrom"] = meta_rel["a_angstrom"]
    # F3: dense NSCF for the screening gap (density from F2's final SCF)
    nbnd = int(nelec // 2 + max(8, int(nelec * 0.2))) if nelec else None
    stage_input(meta_rel, "F3", wd, nbnd=nbnd, positions=pos_rel)
    r = run_qe("pw.x", wd, None, "f3")
    if not r.get("skipped") and not r["ok"]:
        rec["restarts"] += 1
        stage_input(meta_rel, "F3", wd, nbnd=nbnd, positions=pos_rel,
                    retry=True)
        r = run_qe("pw.x", wd, None, "f3")
    if not r.get("skipped") and r["ok"]:
        g = parse_gap(r["out"], nelec)
        rec["stages"]["F3"] = {**r, **(g or {"gap_parse_failed": True})}
        if g and not g["metallic"]:
            rec["gap_ev"] = g["gap_ev"]
            lo, hi = GAP_WINDOW
            rec["qualifier"] = lo <= g["gap_ev"] <= hi
        else:
            rec["qualifier"] = False
    else:
        rec["stages"]["F3"] = r
        rec["failures"] += 1
        rec["qualifier"] = False
    emit(rec)
    return rec


def repair_f3():
    """Re-run failed F3 stages with cg (post-hoc fix for the Davidson
    'S matrix not positive definite' aborts); updates outcomes.jsonl by
    appending corrected records (analysis keeps the last line per
    candidate) and refreshes campaign_summary.json qualifiers."""
    metas = json.load(open(ROOT / "candidates.json"))
    latest = {}
    with open(RESULTS / "outcomes.jsonl") as fh:
        for line in fh:
            r = json.loads(line)
            latest[r["candidate"]] = r
    todo = [r for r in latest.values()
            if r["stages"].get("F2", {}).get("relax_converged")
            and (not r["stages"].get("F3", {}).get("ok")
                 or ("gap_ev" not in r["stages"].get("F3", {})
                     and not r["stages"].get("F3", {}).get("metallic")))]
    print(f"repairing F3 for {len(todo)} candidates:",
          [r["candidate"] for r in todo])

    def fix(rec):
        meta = next(m for m in metas if m["name"] == rec["candidate"])
        wd = WORK / rec["candidate"]
        f2 = rec["stages"]["F2"]
        meta_rel = dict(meta)
        if f2.get("a_relaxed_angstrom"):
            meta_rel["a_angstrom"] = f2["a_relaxed_angstrom"]
        nelec = None
        for st in ("F2", "F1"):
            if rec["stages"].get(st, {}).get("nelec"):
                nelec = rec["stages"][st]["nelec"]
                break
        nbnd = int(nelec // 2 + max(8, int(nelec * 0.2))) if nelec else None
        stage_input(meta_rel, "F3", wd, nbnd=nbnd,
                    positions=f2.get("final_positions_crystal"), retry=True)
        rec["restarts"] += 1
        r = run_qe("pw.x", wd, None, "f3")
        if not r.get("skipped") and r["ok"]:
            g = parse_gap(r["out"], nelec)
            rec["stages"]["F3"] = {**r, **(g or {"gap_parse_failed": True})}
            if g and not g["metallic"]:
                rec["gap_ev"] = g["gap_ev"]
                lo, hi = GAP_WINDOW
                rec["qualifier"] = lo <= g["gap_ev"] <= hi
            else:
                rec["qualifier"] = False
            if rec.get("qualifier") and "F4" not in rec["stages"]:
                stage_input(meta_rel, "F4SCF", wd,
                            positions=f2.get("final_positions_crystal"))
                rs = run_qe("pw.x", wd, None, "f4scf")
                if not rs.get("skipped") and rs["ok"]:
                    ph_input(meta, wd)
                    rp = run_qe("ph.x", wd, None, "f4")
                    if not rp.get("skipped") and rp["ok"]:
                        rec["stages"]["F4"] = {**rp, **parse_ph(rp["out"])}
        else:
            rec["stages"]["F3"] = r
        emit(rec)

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(fix, todo))
    print("REPAIR DONE node_hours=%.3f calls=%d"
          % (STATE["node_hours"], STATE["qe_calls"]))


def main():
    if "--repair-f3" in sys.argv:
        return repair_f3()
    RESULTS.mkdir(parents=True, exist_ok=True)
    metas = json.load(open(ROOT / "candidates.json"))
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        recs = list(ex.map(run_candidate, metas))
    # F4: Gamma phonon for qualifiers only
    quals = [r for r in recs if r.get("qualifier")]
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        def do_ph(rec):
            meta = next(m for m in metas if m["name"] == rec["candidate"])
            wd = WORK / rec["candidate"]
            f2 = rec["stages"]["F2"]
            meta_rel = dict(meta)
            if f2.get("a_relaxed_angstrom"):
                meta_rel["a_angstrom"] = f2["a_relaxed_angstrom"]
            # ph.x needs a fresh SCF state at the relaxed geometry (the
            # last pw run in this workdir was the F3 NSCF)
            stage_input(meta_rel, "F4SCF", wd,
                        positions=f2.get("final_positions_crystal"))
            rs = run_qe("pw.x", wd, None, "f4scf")
            if rs.get("skipped") or not rs["ok"]:
                rec["stages"]["F4"] = {"pre_scf": rs, "ok": False}
                if not rs.get("skipped"):
                    rec["failures"] += 1
                emit(rec)
                return
            ph_input(meta, wd)
            r = run_qe("ph.x", wd, None, "f4")
            if not r.get("skipped") and r["ok"]:
                rec["stages"]["F4"] = {**r, **parse_ph(r["out"])}
            else:
                rec["stages"]["F4"] = r
                if not r.get("skipped"):
                    rec["failures"] += 1
            emit(rec)
        list(ex.map(do_ph, quals))
    summary = {"candidates": len(recs),
               "f2_converged": sum(1 for r in recs
                                   if r["stages"].get("F2", {}).get("relax_converged")),
               "qualifiers": [r["candidate"] for r in quals],
               "total_node_hours": round(STATE["node_hours"], 3),
               "qe_calls": STATE["qe_calls"],
               "budget_cap_hit": STATE["stopped"],
               "wall_hours": round((time.time() - t0) / 3600, 3),
               "records": recs}
    json.dump(summary, open(RESULTS / "campaign_summary.json", "w"), indent=1)
    print("CAMPAIGN DONE", json.dumps({k: summary[k] for k in
          ("candidates", "f2_converged", "qualifiers", "total_node_hours",
           "qe_calls", "budget_cap_hit", "wall_hours")}))


if __name__ == "__main__":
    sys.exit(main())

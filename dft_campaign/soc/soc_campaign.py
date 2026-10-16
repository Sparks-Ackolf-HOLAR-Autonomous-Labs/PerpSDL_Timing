#!/usr/bin/env python3
"""SOC band-gap runs for the 9 DFT-campaign finalists (optional manifest item).

For each finalist (relaxed geometry frozen from the F2 vc-relax results in
../results/outcomes.jsonl):

  SOC-SCF   noncolin + lspinorb, fully-relativistic PSL PAW, 12x12x1
  SOC-NSCF  dense 18x18x1 at the same geometry -> SOC screening gap

Noncolinear bands hold one electron each, so the occupied-state count is
round(nelec), not nelec/2.  Gaps remain PBE screening quantities; SOC here
quantifies the spin-orbit correction to the scalar-relativistic screening
gap, nothing more.  Cost fields (wall, node-hours at cores/64, peak rank
RSS) are recorded per QE call for the Stage-2 twin fit.

Runs inside a SLURM allocation on granite grn061 (see soc.sbatch).
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(os.environ.get("MPT_SOC_ROOT", ".")).resolve()
PSEUDO_DIR = ROOT / "pseudos"
WORK = ROOT / "work"
RESULTS = ROOT / "results"
NPROC = int(os.environ.get("MPT_NPROC_PER_RUN", "16"))
NPOOL = int(os.environ.get("MPT_NPOOL", "4"))
WORKERS = int(os.environ.get("MPT_WORKERS", "3"))
NODE_CORES = 64.0
NODE_HOUR_CAP = float(os.environ.get("MPT_NODE_HOUR_CAP", "10"))

# fully relativistic PSL 1.0.0 PAW (downloaded separately; original PSL
# licenses apply -- see PSEUDOS.md, not bundled in the repo)
PSEUDO = {"Zr": "Zr.rel-pbe-spn-kjpaw_psl.1.0.0.UPF",
          "Hf": "Hf.rel-pbe-spn-kjpaw_psl.1.0.0.UPF",
          "Mo": "Mo.rel-pbe-spn-kjpaw_psl.1.0.0.UPF",
          "W": "W.rel-pbe-spn-kjpaw_psl.1.0.0.UPF",
          "S": "S.rel-pbe-n-kjpaw_psl.1.0.0.UPF",
          "Se": "Se.rel-pbe-n-kjpaw_psl.1.0.0.UPF",
          "Te": "Te.rel-pbe-n-kjpaw_psl.1.0.0.UPF"}
MASS = {"Zr": 91.224, "Hf": 178.49, "Mo": 95.95, "W": 183.84,
        "S": 32.06, "Se": 78.971, "Te": 127.60}
# max suggested cutoffs across the set: wfc 55 Ry / rho 373 Ry (W)
ECUTWFC, ECUTRHO = 60.0, 400.0

spent_lock = threading.Lock()
STATE = {"node_hours": 0.0, "qe_calls": 0, "stopped": False}


def qe_input(meta, calc, kgrid, nbnd=None, retry=False):
    M, X = meta["metal"], meta["chalcogen"]
    L = ["&CONTROL",
         f"  calculation = '{calc}'",
         f"  prefix = '{meta['name']}'",
         f"  pseudo_dir = '{PSEUDO_DIR}'",
         "  outdir = './out'",
         "  verbosity = 'high'",
         "/", "&SYSTEM", "  ibrav = 4",
         f"  a = {meta['a_relaxed_angstrom']}",
         f"  c = {meta['vacuum_angstrom']}",
         f"  nat = {meta['atoms_per_cell']}", "  ntyp = 2",
         f"  ecutwfc = {ECUTWFC}", f"  ecutrho = {ECUTRHO}",
         "  noncolin = .true.", "  lspinorb = .true.",
         "  occupations = 'smearing'", "  smearing = 'cold'",
         "  degauss = 0.015"]
    if nbnd:
        L.append(f"  nbnd = {nbnd}")
    L += ["/", "&ELECTRONS",
          f"  mixing_beta = {0.2 if retry else 0.3}",
          "  conv_thr = 1.0d-8",
          f"  diagonalization = '{'cg' if retry else 'david'}'",
          f"  electron_maxstep = {200 if retry else 100}",
          "/",
          "ATOMIC_SPECIES",
          f"  {M}  {MASS[M]}  {PSEUDO[M]}",
          f"  {X}  {MASS[X]}  {PSEUDO[X]}",
          "ATOMIC_POSITIONS crystal"]
    for s, x, y, z in meta["positions_crystal"]:
        L.append(f"  {s}  {x:.10f}  {y:.10f}  {z:.10f}")
    L += ["K_POINTS automatic", f"  {kgrid} {kgrid} 1 0 0 0", ""]
    return "\n".join(L)


def run_qe(workdir, tag):
    with spent_lock:
        if STATE["node_hours"] >= NODE_HOUR_CAP:
            STATE["stopped"] = True
            return {"ok": False, "skipped": "budget_cap"}
        STATE["qe_calls"] += 1
    out = workdir / f"{tag}.out"
    t0 = time.time()
    cmd = ["/usr/bin/time", "-v", "-o", str(workdir / f"{tag}.time"),
           "mpirun", "-np", str(NPROC), "--bind-to", "none",
           "pw.x", "-nk", str(NPOOL), "-in", str(workdir / f"{tag}.in")]
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


def parse_scf(outfile):
    txt = Path(outfile).read_text(errors="replace")
    d = {"scf_converged": "convergence has been achieved" in txt,
         "job_done": "JOB DONE" in txt}
    m = re.findall(r"!\s+total energy\s+=\s+(-?[\d.]+) Ry", txt)
    d["etot_ry"] = float(m[-1]) if m else None
    m = re.search(r"number of electrons\s+=\s+([\d.]+)", txt)
    d["nelec"] = float(m.group(1)) if m else None
    return d


def parse_gap_soc(outfile, nelec):
    """Screening gap scan; noncolinear -> one electron per band."""
    txt = Path(outfile).read_text(errors="replace")
    blocks = re.findall(
        r"k =[^\n]*\([ 0-9]+ PWs\)\s+bands \(ev\):\n\n((?:\s+-?[\d.]+)+)",
        txt)
    if not blocks or not nelec:
        return None
    nocc = int(round(nelec))
    vbm, cbm = -1e9, 1e9
    for b in blocks:
        ev = [float(x) for x in b.split()]
        if len(ev) <= nocc:
            return None
        vbm = max(vbm, ev[nocc - 1])
        cbm = min(cbm, ev[nocc])
    gap = cbm - vbm
    return {"vbm_ev": round(vbm, 4), "cbm_ev": round(cbm, 4),
            "gap_ev": round(max(gap, 0.0), 4), "metallic": gap < 0.05}


def emit(rec):
    with spent_lock:
        with open(RESULTS / "soc_outcomes.jsonl", "a") as fh:
            fh.write(json.dumps(rec) + "\n")


def run_finalist(meta):
    name = meta["name"]
    wd = WORK / name
    wd.mkdir(parents=True, exist_ok=True)
    rec = {"candidate": name, "phase": meta["phase"],
           "metal": meta["metal"], "chalcogen": meta["chalcogen"],
           "pbe_gap_ev_scalar_rel": meta["pbe_gap_ev_scalar_rel"],
           "stages": {}, "failures": 0, "restarts": 0}
    # SOC-SCF
    (wd / "socscf.in").write_text(qe_input(meta, "scf", 12))
    r = run_qe(wd, "socscf")
    if r.get("skipped"):
        rec["stages"]["SOC_SCF"] = r
        emit(rec)
        return rec
    p = parse_scf(r["out"]) if r["ok"] else {}
    if not p.get("scf_converged"):
        rec["restarts"] += 1
        (wd / "socscf.in").write_text(qe_input(meta, "scf", 12, retry=True))
        r2 = run_qe(wd, "socscf")
        if not r2.get("skipped") and r2["ok"]:
            p2 = parse_scf(r2["out"])
            if p2.get("scf_converged"):
                r, p = r2, p2
    rec["stages"]["SOC_SCF"] = {**r, **p}
    if not p.get("scf_converged"):
        rec["failures"] += 1
        rec["stages"]["SOC_SCF"]["stage_failed"] = True
        emit(rec)
        return rec
    nelec = p["nelec"]
    # SOC-NSCF (noncolinear: default band count is small; ask for
    # nelec occupied + a healthy conduction margin)
    nbnd = int(round(nelec)) + max(16, int(0.4 * nelec))
    (wd / "socnscf.in").write_text(qe_input(meta, "nscf", 18, nbnd=nbnd))
    r = run_qe(wd, "socnscf")
    if not r.get("skipped") and not r["ok"]:
        rec["restarts"] += 1
        (wd / "socnscf.in").write_text(
            qe_input(meta, "nscf", 18, nbnd=nbnd, retry=True))
        r = run_qe(wd, "socnscf")
    if not r.get("skipped") and r["ok"]:
        g = parse_gap_soc(r["out"], nelec)
        rec["stages"]["SOC_NSCF"] = {**r, **(g or {"gap_parse_failed": True})}
        if g:
            rec["soc_gap_ev"] = g["gap_ev"]
            rec["soc_metallic"] = g["metallic"]
            rec["soc_shift_ev"] = round(
                g["gap_ev"] - meta["pbe_gap_ev_scalar_rel"], 4)
    else:
        rec["stages"]["SOC_NSCF"] = r
        rec["failures"] += 1
    emit(rec)
    return rec


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    metas = json.load(open(ROOT / "finalists.json"))
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        recs = list(ex.map(run_finalist, metas))
    summary = {"finalists": len(recs),
               "soc_gaps": {r["candidate"]: r.get("soc_gap_ev")
                            for r in recs},
               "total_node_hours": round(STATE["node_hours"], 3),
               "qe_calls": STATE["qe_calls"],
               "budget_cap_hit": STATE["stopped"],
               "wall_hours": round((time.time() - t0) / 3600, 3),
               "records": recs}
    json.dump(summary, open(RESULTS / "soc_summary.json", "w"), indent=1)
    print("SOC DONE", json.dumps({k: summary[k] for k in
          ("finalists", "soc_gaps", "total_node_hours", "qe_calls",
           "budget_cap_hit", "wall_hours")}))


if __name__ == "__main__":
    sys.exit(main())

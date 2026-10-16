#!/usr/bin/env python3
"""Route 3, step 1: measure the run-time library entries
that comparison No. 2 never reached, plus three repeat ladders of
compounds already in the library to compare the free granite-guest
hardware with grn061.

One compound per SLURM array task: F1 -> F2 -> F3 on the comparison
No. 2 inputs (8x8 supercells), 16 MPI ranks, npool 1, the same execution
config every No. 2 call used. Each stage is recorded with its run time,
peak memory, outcome, host and processor model. The solver-retry rule
(../qe_retry.py) applies. Restart-safe: after a preemption the task
skips stages already recorded as converged (F2 is rerun if its save
directory is gone, since F3 reads it).
"""
import json, os, re, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import qe_retry

ROOT = Path(os.environ.get("MPT_LIB_ROOT", ".")).resolve()
INPUTS, WORK, RESULTS = ROOT / "inputs", ROOT / "work", ROOT / "results"
RANKS = 16
LIST = [l.split() for l in open(ROOT / "compounds.txt") if l.strip()]


def node_info():
    cpu = None
    for line in open("/proc/cpuinfo"):
        if line.startswith("model name"):
            cpu = line.split(":", 1)[1].strip()
            break
    return {"host": os.uname().nodename, "cpu_model": cpu,
            "slurm_job": os.environ.get("SLURM_JOB_ID"),
            "array_task": os.environ.get("SLURM_ARRAY_TASK_ID"),
            "restart_count": os.environ.get("SLURM_RESTART_COUNT", "0")}


def nelec_of(out):
    m = re.search(r"number of electrons\s+=\s+([\d.]+)",
                  Path(out).read_text(errors="replace"))
    return float(m.group(1)) if m else None


def gap_of(out, nelec):
    txt = Path(out).read_text(errors="replace")
    blocks = re.findall(
        r"k =[^\n]*\([ 0-9]+ PWs\)\s+bands \(ev\):\n\n((?:\s+-?[\d.]+)+)",
        txt)
    if not blocks or not nelec:
        return None
    nocc = int(round(nelec)) // 2
    vbm, cbm = -1e9, 1e9
    for b in blocks:
        ev = [float(x) for x in b.split()]
        if len(ev) <= nocc:
            return None
        vbm, cbm = max(vbm, ev[nocc - 1]), min(cbm, ev[nocc])
    return max(cbm - vbm, 0.0)


def run(wd, name, stage, solver=None):
    inp = INPUTS / f"{name}.{stage}.in"
    if solver:
        r = qe_retry.retry_input(inp, wd)
        if r:
            inp = r[0]
    tag = f"{stage}.{solver}" if solver else stage
    out = wd / f"{tag}.out"
    cmd = ["/usr/bin/time", "-v", "-o", str(wd / f"{tag}.time"),
           "mpirun", "-np", str(RANKS), "--bind-to", "none",
           "pw.x", "-nk", "1", "-in", str(inp)]
    t0 = time.time()
    with open(out, "w") as fh:
        rc = subprocess.call(cmd, cwd=wd, stdout=fh,
                             stderr=subprocess.STDOUT)
    wall = time.time() - t0
    mem = None
    tf = wd / f"{tag}.time"
    if tf.exists():
        m = re.search(r"Maximum resident set size.*: (\d+)", tf.read_text())
        if m:
            mem = round(int(m.group(1)) / 1048576, 2)
    outcome, kind = qe_retry.classify(out, rc)
    return {"stage": stage, "solver": solver or "david", "rc": rc,
            "wall_s": round(wall, 1), "peak_rank_rss_gb": mem,
            "outcome": outcome, "fail_kind": kind, "out": str(out)}


def main():
    idx = int(os.environ["SLURM_ARRAY_TASK_ID"])
    name, role = LIST[idx]
    wd = WORK / name
    wd.mkdir(parents=True, exist_ok=True)
    if not (wd / "pseudos").exists():
        (wd / "pseudos").symlink_to(ROOT / "pseudos")
    RESULTS.mkdir(parents=True, exist_ok=True)
    rp = RESULTS / f"{name}.json"
    rec = json.load(open(rp)) if rp.exists() else {
        "candidate": name, "role": role, "ranks": RANKS, "calls": []}
    rec.setdefault("attempts", []).append(node_info())
    done = {c["stage"] for c in rec["calls"]
            if c["outcome"] == "converged"}
    if "f3" not in done and "f2" in done and not (wd / "out").exists():
        done.discard("f2")
    nelec = None
    for stage in ("f1", "f2", "f3"):
        if stage in done:
            continue
        solver = None
        while True:
            c = run(wd, name, stage, solver)
            c["host"] = rec["attempts"][-1]["host"]
            c["cpu_model"] = rec["attempts"][-1]["cpu_model"]
            if stage != "f3":
                nelec = nelec_of(c["out"]) or nelec
                c["converged"] = ("convergence has been achieved"
                                  in Path(c["out"]).read_text(
                                      errors="replace"))
            else:
                if nelec is None:
                    f2o = wd / "f2.out"
                    nelec = nelec_of(f2o) if f2o.exists() else None
                g = gap_of(c["out"], nelec) if c["rc"] == 0 else None
                c["gap_ev"] = round(g, 4) if g is not None else None
            rec["calls"].append(c)
            json.dump(rec, open(rp, "w"), indent=1)
            nxt = qe_retry.next_solver(c["solver"])
            if c["outcome"] != "converged" and c["fail_kind"] == "solver" \
                    and nxt and solver is None:
                solver = nxt
                continue
            break
        if rec["calls"][-1]["outcome"] != "converged":
            break
    rec["finished"] = True
    json.dump(rec, open(rp, "w"), indent=1)
    print("LADDER DONE", name, [(c["stage"], c["wall_s"], c["outcome"])
                                for c in rec["calls"]], flush=True)


if __name__ == "__main__":
    main()

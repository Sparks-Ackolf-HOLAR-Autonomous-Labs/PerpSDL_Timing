#!/usr/bin/env python3
"""Repair pass for the three out-of-memory calls of comparison No. 3
(decision of 6 Oct 2026: run them as a separate repair pass).

Three CEDT_P4 campaigns each lost one QE call to a kernel OOM kill when
the broker packed three 2H jobs onto a 372000M guest node:

  campaign        candidate   stage  SLURM job
  CEDT_P4 s3      ZrTe2_2H    f1     2089139
  CEDT_P4 s4      ZrSe2_2H    f2     2089141
  CEDT_P4 s7      TiSe2_2H    f3     2089147

This pass re-runs exactly those calls with the same inputs, the same
16-rank npool-1 execution config and the same solver rule as the
campaign driver. TiSe2_2H f3 needs the f2 charge density, so its f2 is
re-run first as a prerequisite (measured and recorded, never billed to
the campaign). The three streams run concurrently on one 768-GB node,
which reproduces the three-2H co-residency that caused the kills while
giving it the memory it needs; the summed resident memory of the job's
pw.x processes is sampled every 15 s to measure the true footprint.

Reads   $MPT_LIVE2_ROOT/{inputs,pseudos}   (the No. 3 staging dir)
Writes  $MPT_REPAIR_OUT/oom_repair.json    (rewritten after every call)
        $MPT_REPAIR_OUT/outputs/<cand>.<stage>.out
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import live2_campaign as L  # noqa: E402  (staged next to this file)
import qe_retry  # noqa: E402

OUT = Path(os.environ.get("MPT_REPAIR_OUT", str(L.ROOT / "oom_repair")))
WORK = OUT / "work"
POLL_S = 15
REPAIRS = [
    {"arm": "CEDT_P4", "seed": 3, "candidate": "ZrTe2_2H",
     "stage": "f1", "prereq": [], "slurm_job_orig": "2089139"},
    {"arm": "CEDT_P4", "seed": 4, "candidate": "ZrSe2_2H",
     "stage": "f2", "prereq": [], "slurm_job_orig": "2089141"},
    {"arm": "CEDT_P4", "seed": 7, "candidate": "TiSe2_2H",
     "stage": "f3", "prereq": ["f2"], "slurm_job_orig": "2089147"},
]


def job_rss_gb():
    """Summed RSS of this SLURM job's pw.x processes (GB)."""
    jid = os.environ.get("SLURM_JOB_ID", "")
    tot = 0
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            if (p / "comm").read_text().strip() != "pw.x":
                continue
            if jid and f"job_{jid}" not in (p / "cgroup").read_text():
                continue
            for line in (p / "status").read_text().splitlines():
                if line.startswith("VmRSS:"):
                    tot += int(line.split()[1])
        except OSError:
            continue
    return tot / 1048576


def launch(name, stage, solver=None):
    wd = WORK / name
    wd.mkdir(parents=True, exist_ok=True)
    if not (wd / "pseudos").exists():
        (wd / "pseudos").symlink_to(L.ROOT / "pseudos")
    inp = L.INPUTS / f"{name}.{stage}.in"
    if solver:
        r = qe_retry.retry_input(inp, wd)
        if r:
            inp = r[0]
    tag = f"{stage}.{solver}" if solver else stage
    out = wd / f"{tag}.out"
    cmd = ["/usr/bin/time", "-v", "-o", str(wd / f"{tag}.time"),
           "mpirun", "-np", str(L.RANKS), "--bind-to", "none",
           "pw.x", "-nk", "1", "-in", str(inp)]
    fh = open(out, "w")
    proc = subprocess.Popen(cmd, cwd=wd, stdout=fh,
                            stderr=subprocess.STDOUT)
    print(f"[oom_repair] launch {name}.{tag}", flush=True)
    return {"proc": proc, "fh": fh, "wd": wd, "out": out, "tag": tag,
            "name": name, "stage": stage, "solver": solver or "david",
            "t0": time.time(), "peak_job_rss_gb": 0.0}


def peak_rank(wd, tag):
    import re
    tf = wd / f"{tag}.time"
    if tf.exists():
        m = re.search(r"Maximum resident set size.*: (\d+)", tf.read_text())
        if m:
            return round(int(m.group(1)) / 1048576, 2)
    return None


def main():
    (OUT / "outputs").mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    state = {"node": L.node_info(), "calls": [], "repairs": {},
             "peak_job_rss_gb": 0.0, "t_start": time.time()}
    queue = {r["candidate"]: r["prereq"] + [r["stage"]] for r in REPAIRS}
    nelec = {}
    running = [launch(n, q.pop(0)) for n, q in queue.items()]
    while running:
        time.sleep(POLL_S)
        rss = job_rss_gb()
        state["peak_job_rss_gb"] = round(max(state["peak_job_rss_gb"],
                                             rss), 1)
        for j in running:
            j["peak_job_rss_gb"] = max(j["peak_job_rss_gb"], rss)
        for j in running[:]:
            if j["proc"].poll() is None:
                continue
            running.remove(j)
            j["fh"].close()
            rc = j["proc"].returncode
            name, stage = j["name"], j["stage"]
            rec = {"candidate": name, "stage": stage, "solver": j["solver"],
                   "rc": rc, "wall_s": round(time.time() - j["t0"], 1),
                   "peak_rank_rss_gb": peak_rank(j["wd"], j["tag"]),
                   "peak_job_rss_gb_while_running":
                       round(j["peak_job_rss_gb"], 1)}
            outcome, kind = qe_retry.classify(j["out"], rc)
            rec["outcome"], rec["fail_kind"] = outcome, kind
            ok = rc == 0
            if stage in ("f1", "f2"):
                conv, ne = L.parse_scf(j["out"])
                rec["converged"] = conv
                if ne:
                    nelec[name] = ne
                ok = ok and conv
            else:
                gap = L.parse_gap(j["out"], nelec.get(name)) if ok else None
                rec["gap_ev"] = round(gap, 4) if gap is not None else None
                ok = ok and gap is not None
            shutil.copy2(j["out"], OUT / "outputs" / f"{name}.{j['tag']}.out")
            state["calls"].append(rec)
            target = next(r for r in REPAIRS if r["candidate"] == name)
            if (not ok and kind == "solver"
                    and qe_retry.next_solver(j["solver"]) is not None):
                running.append(launch(name, stage,
                                      qe_retry.next_solver(j["solver"])))
            elif ok and queue[name]:
                running.append(launch(name, queue[name].pop(0)))
            else:
                if stage == target["stage"] or not ok:
                    state["repairs"][name] = {**target, **rec,
                                              "ok": ok}
                shutil.rmtree(j["wd"] / "out", ignore_errors=True)
            print(f"[oom_repair] done {name}.{j['tag']} rc={rc} ok={ok}",
                  flush=True)
        state["elapsed_s"] = round(time.time() - state["t_start"], 1)
        json.dump(state, open(OUT / "oom_repair.json", "w"), indent=1)
    state["done"] = True
    json.dump(state, open(OUT / "oom_repair.json", "w"), indent=1)
    print(f"OOM_REPAIR DONE peak_job_rss={state['peak_job_rss_gb']} GB "
          f"ok={sum(v['ok'] for v in state['repairs'].values())}/3",
          flush=True)


if __name__ == "__main__":
    main()

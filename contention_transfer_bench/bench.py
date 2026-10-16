#!/usr/bin/env python3
"""Contention-vs-scale + transfer benchmark (future-work items 2 and 5,
and the live half of the coupling-onset question).

Runs on granite grn061 inside one SLURM allocation:

1. Contention vs scale (the co-tenant coupling channel). For supercell
   scales s1/s2/s3, run the TiS2_1T job solo (32 ranks) and then
   concurrently with a MoSe2_2H job of the same scale (32 + 32 ranks
   sharing the box). The interference factor wall_cotenant / wall_solo
   per scale measures whether co-tenant coupling grows with task scale
   (memory-bandwidth saturation) — grn061 is one box, so this is
   single-node contention; inter-node scaling still needs a multi-node
   cluster (kingspeak general partition).

2. Transfer probes: one defect supercell (MoS2 3x3 with S vacancy) and
   one MoS2/WS2 heterobilayer (2x2) SCF; measured cost is compared to
   the MX2-fitted twin prediction from electron count alone.

Inputs: ../scale_validation/inputs (committed, from job 1914482) and
./inputs (build_transfer_inputs.py). Everything is CC0 public-case
material; ~1 node-hour total.
"""
import json
import os
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(os.environ.get("MPT_BENCH_ROOT", ".")).resolve()
RESULTS = ROOT / "results"
NH_CAP = float(os.environ.get("MPT_BENCH_NH_CAP", "5.0"))
STATE = {"nh": 0.0}

SCALE_PAIRS = [  # (scale tag, jobA, jobB)
    ("s1", "TiS2_1T_s1_k6", "MoSe2_2H_s1_k6"),
    ("s2", "TiS2_1T_s2_k6", "MoSe2_2H_s2_k6"),
    ("s3", "TiS2_1T_s3_k6", "MoSe2_2H_s3_k6"),
]
TRANSFER = ["MoS2_3x3_Svac", "MoS2_WS2_hetero_2x2"]
REPS = 2


def launch(name, ranks=32, npool=2):
    wd = ROOT / "work" / f"{name}_{time.time_ns() % 10**9}"
    wd.mkdir(parents=True)
    if not (wd / "pseudos").exists():
        (wd / "pseudos").symlink_to(ROOT / "pseudos")
    inp = ROOT / "inputs" / f"{name}.pw.in"
    out = wd / "run.out"
    t0 = time.time()
    proc = subprocess.Popen(
        ["mpirun", "-np", str(ranks), "--bind-to", "none",
         "pw.x", "-nk", str(npool), "-in", str(inp)],
        cwd=wd, stdout=open(out, "w"), stderr=subprocess.STDOUT)
    return {"proc": proc, "t0": t0, "out": out, "name": name,
            "ranks": ranks, "wd": wd}


def finish(h):
    h["proc"].wait()
    wall = time.time() - h["t0"]
    txt = Path(h["out"]).read_text(errors="replace")
    conv = "convergence has been achieved" in txt
    ram = re.search(r"dynamical RAM per process >\s+([\d.]+) MB", txt)
    nel = re.search(r"number of electrons\s+=\s+([\d.]+)", txt)
    nh = wall / 3600.0 * h["ranks"] / 64.0
    STATE["nh"] += nh
    import shutil
    shutil.rmtree(h["wd"] / "out", ignore_errors=True)
    return {"name": h["name"], "wall_s": round(wall, 2), "converged": conv,
            "ram_mb_per_proc": float(ram.group(1)) if ram else None,
            "nelec": float(nel.group(1)) if nel else None,
            "nh": round(nh, 5), "ranks": h["ranks"]}


def emit(kind, rec):
    rec["kind"] = kind
    with open(RESULTS / "bench_results.jsonl", "a") as fh:
        fh.write(json.dumps(rec) + "\n")
    print(kind, rec, flush=True)


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    for rep in range(REPS):
        for tag, ja, jb in SCALE_PAIRS:
            if STATE["nh"] >= NH_CAP:
                break
            # solo baseline
            ra = finish(launch(ja))
            emit("solo", dict(ra, scale=tag, rep=rep))
            # co-tenant: same job while the partner occupies the other
            # half of the box
            hb = launch(jb)
            time.sleep(2)
            ha = launch(ja)
            rb_a = finish(ha)
            emit("cotenant", dict(rb_a, scale=tag, rep=rep, partner=jb))
            rb = finish(hb)
            emit("partner", dict(rb, scale=tag, rep=rep))
    for name in TRANSFER:
        if STATE["nh"] >= NH_CAP:
            break
        emit("transfer", finish(launch(name)))
    print("BENCH DONE nh=%.3f" % STATE["nh"], flush=True)


if __name__ == "__main__":
    main()

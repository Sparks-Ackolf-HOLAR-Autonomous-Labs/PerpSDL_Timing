#!/usr/bin/env python3
"""Live paired CEDT-P4 vs DTDE comparison driver (future-work item 1).
Runs REAL Quantum ESPRESSO on granite grn061 inside one
SLURM allocation. This is the experiment the preregistration
(PREREGISTRATION.md, amended 2026-09-09) points at.

Design
------
N paired campaign seeds. Each seed fixes one shuffled candidate order
over the 29 CC0 MX2 candidates at 3x3-supercell scale; BOTH arms replay
the same order, same inputs, same physics. The arms differ ONLY in the
execution config (mpirun -np / pw.x -nk), i.e. in what H's side knows:

  DTDE  (no sharing)    H sees "a QE job" and nothing else, so every
                        job gets the one-size-fits-all worst-case
                        config: -np 32 -nk 1.
  CEDT-P4 (broker)      the broker sees the calculation class (f1/f2/
                        f3) — the only candidate-linked field P4
                        disclosures carry — and matches it against the
                        PUBLIC class rate card (pilot + scale
                        measurements, all CC0): small cheap config for
                        the overhead-dominated F1 class, k-parallel
                        configs for the k-rich F2/F3 classes.

Ladder per candidate: F1 coarse SCF -> F2 production SCF (the "valid
F2 label") -> F3 dense NSCF -> PBE screening gap; qualifier = gap in
[1.0, 2.0] eV. No F4 in this comparison (scope amendment).

Campaign stops at >= MAX_CALLS QE calls, campaign node-hour cap, or
candidate exhaustion. nh-to-first-qualifier and labels/nh are recorded
per campaign; every QE call appends a wire-log row (timestamps, opaque
ID, class, config, charge) for the executed leakage attacks, including
the timing channel (accept-and-measure decision recorded in the
preregistration).

Node-hours are charged as wall * ranks / 64 (grn061 has 64 cores).
Guards: global NH cap refuses new jobs past MPT_LIVE_NH_CAP; SLURM
--time is the hard stop.
"""
import hashlib
import json
import os
import random
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(os.environ.get("MPT_LIVE_ROOT", ".")).resolve()
INPUTS = ROOT / "inputs"
WORK = ROOT / "work"
RESULTS = ROOT / "results"
NODE_CORES = 64.0
NH_CAP = float(os.environ.get("MPT_LIVE_NH_CAP", "100"))
SEEDS = int(os.environ.get("MPT_LIVE_SEEDS", "10"))
MAX_CALLS = int(os.environ.get("MPT_LIVE_MAX_CALLS", "24"))
CAMPAIGN_NH_CAP = float(os.environ.get("MPT_LIVE_CAMPAIGN_NH", "5.0"))
GAP_LO, GAP_HI = 1.0, 2.0
SALT = "mpt-live-2026-09-09"

# execution configs: (ranks, npool)
DTDE_CFG = {"f1": (32, 1), "f2": (32, 1), "f3": (32, 1)}
# broker rate card: class-matched configs justified by PUBLIC pilot
# measurements (s = 0.425 -> small np for overhead-dominated F1;
# pool_effect < 0 -> k-parallelism for the k-rich classes)
CEDT_CFG = {"f1": (16, 1), "f2": (32, 2), "f3": (32, 4)}
# public class rate card (charged nh, both arms; evaluator uses true nh)
RATE_CARD = {"f1": 0.02, "f2": 0.15, "f3": 0.10}

STATE = {"nh": 0.0, "calls": 0}


def opaque(name, seed):
    return hashlib.sha1(f"{SALT}:{seed}:{name}".encode()).hexdigest()[:10]


def run_qe(wd, name, stage, ranks, npool):
    if STATE["nh"] >= NH_CAP:
        return {"skipped": "nh_cap"}
    inp = INPUTS / f"{name}.{stage}.in"
    out = wd / f"{stage}.out"
    t0 = time.time()
    cmd = ["/usr/bin/time", "-v", "-o", str(wd / f"{stage}.time"),
           "mpirun", "-np", str(ranks), "--bind-to", "none",
           "pw.x", "-nk", str(npool), "-in", str(inp)]
    with open(out, "w") as fh:
        rc = subprocess.call(cmd, cwd=wd, stdout=fh,
                             stderr=subprocess.STDOUT)
    t1 = time.time()
    nh = (t1 - t0) / 3600.0 * ranks / NODE_CORES
    STATE["nh"] += nh
    STATE["calls"] += 1
    mem = None
    tf = wd / f"{stage}.time"
    if tf.exists():
        m = re.search(r"Maximum resident set size.*: (\d+)", tf.read_text())
        if m:
            mem = round(int(m.group(1)) / 1048576, 3)
    return {"rc": rc, "t_start": t0, "t_end": t1,
            "wall_s": round(t1 - t0, 2), "true_nh": round(nh, 5),
            "peak_rank_rss_gb": mem, "out": str(out)}


def parse_scf(outfile):
    txt = Path(outfile).read_text(errors="replace")
    return {"converged": "convergence has been achieved" in txt,
            "job_done": "JOB DONE" in txt,
            "nelec": (float(m.group(1)) if
                      (m := re.search(r"number of electrons\s+=\s+([\d.]+)",
                                      txt)) else None)}


def parse_gap(outfile, nelec):
    txt = Path(outfile).read_text(errors="replace")
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
        vbm = max(vbm, ev[nocc - 1])
        cbm = min(cbm, ev[nocc])
    return max(cbm - vbm, 0.0)


def wire(row):
    with open(RESULTS / "wire_log.jsonl", "a") as fh:
        fh.write(json.dumps(row) + "\n")


def run_campaign(arm, seed, order):
    cfg = CEDT_CFG if arm == "CEDT_P4" else DTDE_CFG
    camp = {"arm": arm, "seed": seed, "calls": 0, "nh": 0.0,
            "labels_f2": 0, "nh_first_qual": None, "qualifiers": [],
            "fails": 0, "jobs": []}
    for name in order:
        if (camp["calls"] >= MAX_CALLS or camp["nh"] >= CAMPAIGN_NH_CAP
                or STATE["nh"] >= NH_CAP):
            break
        wd = WORK / f"{arm}_s{seed}" / name
        wd.mkdir(parents=True, exist_ok=True)
        if not (wd / "pseudos").exists():
            (wd / "pseudos").symlink_to(ROOT / "pseudos")
        nelec = None
        ladder_ok = True
        for stage in ("f1", "f2", "f3"):
            if (camp["calls"] >= MAX_CALLS
                    or camp["nh"] >= CAMPAIGN_NH_CAP):
                ladder_ok = False
                break
            ranks, npool = cfg[stage]
            r = run_qe(wd, name, stage, ranks, npool)
            if r.get("skipped"):
                ladder_ok = False
                break
            camp["calls"] += 1
            camp["nh"] += r["true_nh"]
            row = dict(arm=arm, seed=seed, opaque_id=opaque(name, seed),
                       cls=stage, ranks=ranks, npool=npool,
                       t_start=r["t_start"], t_end=r["t_end"],
                       wall_s=r["wall_s"], charge_nh=RATE_CARD[stage],
                       ok=r["rc"] == 0)
            wire(row)
            rec = dict(row, candidate=name, true_nh=r["true_nh"],
                       peak_rank_rss_gb=r["peak_rank_rss_gb"])
            if stage in ("f1", "f2"):
                p = parse_scf(r["out"])
                rec["converged"] = p["converged"]
                if p["nelec"]:
                    nelec = p["nelec"]
                if not (r["rc"] == 0 and p["converged"]):
                    camp["fails"] += 1
                    rec["stage_failed"] = True
                    camp["jobs"].append(rec)
                    ladder_ok = False
                    break
                if stage == "f2":
                    camp["labels_f2"] += 1
            else:
                gap = (parse_gap(r["out"], nelec)
                       if r["rc"] == 0 else None)
                rec["gap_ev"] = round(gap, 4) if gap is not None else None
                if gap is None:
                    camp["fails"] += 1
                    rec["stage_failed"] = True
                elif GAP_LO <= gap <= GAP_HI:
                    camp["qualifiers"].append(name)
                    if camp["nh_first_qual"] is None:
                        camp["nh_first_qual"] = round(camp["nh"], 4)
            camp["jobs"].append(rec)
        # scratch hygiene: wavefunctions/densities are not needed after
        # the ladder; keep only the text outputs for provenance/attacks
        import shutil
        shutil.rmtree(wd / "out", ignore_errors=True)
        if not ladder_ok and STATE["nh"] >= NH_CAP:
            break
    camp["nh"] = round(camp["nh"], 4)
    with open(RESULTS / "campaigns.jsonl", "a") as fh:
        fh.write(json.dumps(camp) + "\n")
    return camp


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(exist_ok=True)
    manifest = json.load(open(INPUTS / "manifest.json"))
    names = [m["name"] for m in manifest]
    t0 = time.time()
    done = []
    for seed in range(SEEDS):
        order = names[:]
        random.Random(1000 + seed).shuffle(order)
        # alternate arm execution order to cancel temporal drift
        arms = (["DTDE", "CEDT_P4"] if seed % 2 == 0
                else ["CEDT_P4", "DTDE"])
        for arm in arms:
            c = run_campaign(arm, seed, order)
            done.append({k: c[k] for k in ("arm", "seed", "calls", "nh",
                                           "labels_f2", "nh_first_qual",
                                           "qualifiers", "fails")})
            print(f"seed {seed} {arm}: calls={c['calls']} nh={c['nh']} "
                  f"labels={c['labels_f2']} first={c['nh_first_qual']} "
                  f"quals={len(c['qualifiers'])}", flush=True)
            json.dump({"progress": done,
                       "total_nh": round(STATE["nh"], 3),
                       "total_calls": STATE["calls"],
                       "wall_h": round((time.time() - t0) / 3600, 2)},
                      open(RESULTS / "progress.json", "w"), indent=1)
    json.dump({"campaigns": done, "total_nh": round(STATE["nh"], 3),
               "total_calls": STATE["calls"], "seeds": SEEDS,
               "wall_h": round((time.time() - t0) / 3600, 2)},
              open(RESULTS / "live_summary.json", "w"), indent=1)
    print("LIVE COMPARISON DONE", STATE, flush=True)


if __name__ == "__main__":
    main()

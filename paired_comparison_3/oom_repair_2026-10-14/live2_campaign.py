#!/usr/bin/env python3
"""Live comparison No. 2 driver: DTDE vs CEDT-P4+bit as
PACKING policies on granite grn061, real QE 7.4, 8x8 supercells.

Frozen design (PREREGISTRATION_DRAFT.md, post-cofit amendments):
15 paired seeds x 2 arms x 8 QE calls/campaign; identical physics,
identical per-job execution config (16 ranks, npool 1); the arms differ
ONLY in the memory reservation each policy can justify, which controls
(a) how many jobs may co-reside on the 64-core/380-GB node and
(b) the TRES bill: billed pc-nh = wall_h * max(ranks/64, res_GB/380).

  DTDE      H sees the calculation class only -> every job reserves
            1.10 x the class-worst-case RAM estimate (no disclosure).
  CEDT-P4   the broker additionally receives ONE preregistered bit per
            job (RAM estimate above/below the population median) and
            reserves 1.10 x the bit-half worst case.

Timing masking (preregistered, active): in the CEDT arm every
completion message reaches the broker only at the next 600-s wall-clock
boundary; the reservation is held (and billed) until then, and the wire
log records only masked times. DTDE has no wire, so no masking.
The masking price is measured live by the window-B replay
(MPT_REPLAY_SEEDS): CEDT campaigns re-run with quant=0 on identical
seeds/orders -> paired masked-vs-unmasked billed cost and makespan.

Guards: window budget cap MPT_W_CAP (billed pc-nh; launch refused if
projected job would cross it), campaign cap 25 pc-nh, SLURM --time.
"""
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(1, str(Path(__file__).resolve().parent.parent))
import qe_retry  # solver-retry rule (Davidson -> cg), adopted 2026-09-30

ROOT = Path(os.environ.get("MPT_LIVE2_ROOT", ".")).resolve()
INPUTS = ROOT / "inputs"
WORK = Path(os.environ.get("MPT_WORK", str(ROOT / "work")))
RESULTS = Path(os.environ.get("MPT_RESULTS", str(ROOT / "results")))
NODE_CORES = 64
NODE_GB = 380.0
PACK_GB = 342.0                      # 0.9 x node, packing budget
RANKS = 16
QUANT = int(os.environ.get("MPT_QUANT", "600"))
W_CAP = float(os.environ.get("MPT_W_CAP", "280"))
SEED_LO = int(os.environ.get("MPT_SEED_LO", "0"))
SEED_HI = int(os.environ.get("MPT_SEED_HI", "7"))
# colon-separated (sbatch --export splits on commas)
REPLAY = [int(s) for s in
          os.environ.get("MPT_REPLAY_SEEDS", "").split(":") if s]
# comparison No. 3 (parallel guest route) overrides; defaults = No. 2
MAX_CALLS = int(os.environ.get("MPT_MAX_CALLS", "8"))
MAX_LADDERS = 3
CAMPAIGN_CAP = float(os.environ.get("MPT_CAMP_CAP", "25"))
# timing mask: "fixed" = round completion up to the next QUANT-s wall
# boundary (No. 2); "prop" = round the job's run time up to a multiple
# of MASK_FRAC x its expected run time (proportional clause, No. 3 A)
MASK = os.environ.get("MPT_MASK", "fixed")
MASK_FRAC = float(os.environ.get("MPT_MASK_FRAC", "0.25"))
# single-campaign mode "ARM:seed" (one SLURM job per campaign)
ONE = os.environ.get("MPT_CAMPAIGN", "")
GAP_LO, GAP_HI = 1.0, 2.0
SALT = "mpt-live2-2026-09-11"
STAGE_RAM = {"f1": 0.85, "f2": 1.00, "f3": 1.05}
STAGE_WALL_H16 = {"f1": 4.2, "f2": 6.5, "f3": 4.0}   # 2H-anchor est
POLL_S = float(os.environ.get("MPT_POLL", "10"))

MAN = json.load(open(INPUTS / "manifest2.json"))
CAND = {r["name"]: r for r in MAN["candidates"]}
CLASS_MAX = max(r["ram_est_gb"] for r in MAN["candidates"])
BIT0_MAX = max(r["ram_est_gb"] for r in MAN["candidates"]
               if r["mem_bit"] == 0)
STATE = {"billed": 0.0, "calls": 0}


def reservation(arm, name, stage):
    r = CAND[name]
    if arm.startswith("CEDT"):
        base = CLASS_MAX if r["mem_bit"] else BIT0_MAX
    else:
        base = CLASS_MAX
    return round(1.10 * base * STAGE_RAM[stage], 1)


def est_wall_h(name, stage):
    r = CAND[name]
    return STAGE_WALL_H16[stage] * (r["nelec"] / 3328.0) ** 2.0


def frac(res_gb):
    return max(RANKS / NODE_CORES, res_gb / NODE_GB)


def opaque(name, seed):
    return hashlib.sha1(f"{SALT}:{seed}:{name}".encode()).hexdigest()[:10]


def boundary(t):
    return math.ceil(t / QUANT) * QUANT if QUANT > 0 else t


def visible_at(j, now):
    """Time at which the broker learns job j finished (masked)."""
    if MASK == "prop":
        q = max(60.0, MASK_FRAC * est_wall_h(j["name"], j["stage"]) * 3600)
        return j["t0"] + math.ceil((now - j["t0"]) / q) * q
    return boundary(now)


def node_info():
    cpu = None
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    return {"host": os.uname().nodename, "cpu_model": cpu,
            "ncpu": os.cpu_count(),
            "slurm_job": os.environ.get("SLURM_JOB_ID"),
            "restart_count": os.environ.get("SLURM_RESTART_COUNT", "0")}


def wire(row):
    with open(RESULTS / "wire_log.jsonl", "a") as fh:
        fh.write(json.dumps(row) + "\n")


def parse_scf(out):
    txt = Path(out).read_text(errors="replace")
    m = re.search(r"number of electrons\s+=\s+([\d.]+)", txt)
    return ("convergence has been achieved" in txt,
            float(m.group(1)) if m else None)


def parse_gap(out, nelec):
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
        vbm = max(vbm, ev[nocc - 1])
        cbm = min(cbm, ev[nocc])
    return max(cbm - vbm, 0.0)


def launch(arm, seed, name, stage, solver=None):
    wd = WORK / f"{arm}_s{seed}" / name
    wd.mkdir(parents=True, exist_ok=True)
    if not (wd / "pseudos").exists():
        (wd / "pseudos").symlink_to(ROOT / "pseudos")
    inp = INPUTS / f"{name}.{stage}.in"
    if solver:
        # solver-retry rule: same input, next eigensolver on the ladder
        r = qe_retry.retry_input(inp, wd)
        if r:
            inp = r[0]
    tag = f"{stage}.{solver}" if solver else stage
    out = wd / f"{tag}.out"
    cmd = ["/usr/bin/time", "-v", "-o", str(wd / f"{tag}.time"),
           "mpirun", "-np", str(RANKS), "--bind-to", "none",
           "pw.x", "-nk", "1", "-in", str(inp)]
    fh = open(out, "w")
    proc = subprocess.Popen(cmd, cwd=wd, stdout=fh,
                            stderr=subprocess.STDOUT)
    return {"proc": proc, "fh": fh, "wd": wd, "out": out, "name": name,
            "stage": stage, "solver": solver or "david", "tag": tag,
            "t0": time.time(), "done_at": None,
            "res": reservation(arm, name, stage)}


def finalize(arm, seed, camp, j, t_vis, quant_on):
    j["fh"].close()
    rc = j["proc"].returncode
    wall = j["done_at"] - j["t0"]
    billed = (t_vis - j["t0"]) / 3600.0 * frac(j["res"])
    STATE["billed"] += billed
    STATE["calls"] += 1
    camp["billed"] += billed
    name, stage = j["name"], j["stage"]
    mem = None
    tf = j["wd"] / f"{j['tag']}.time"
    if tf.exists():
        m = re.search(r"Maximum resident set size.*: (\d+)",
                      tf.read_text())
        if m:
            mem = round(int(m.group(1)) / 1048576, 2)
    rec = {"arm": arm, "seed": seed, "candidate": name, "cls": stage,
           "ranks": RANKS, "res_gb": j["res"], "wall_s": round(wall, 1),
           "held_s": round(t_vis - j["done_at"], 1),
           "billed_nh": round(billed, 4), "rc": rc,
           "peak_rank_rss_gb": mem, "solver": j["solver"],
           "solver_retry": j["solver"] != "david",
           "host": camp.get("node", {}).get("host")}
    outcome, fail_kind = qe_retry.classify(j["out"], rc)
    rec["outcome"], rec["fail_kind"] = outcome, fail_kind
    ok = rc == 0
    st = camp["ladders"][name]
    if stage in ("f1", "f2"):
        conv, nelec = parse_scf(j["out"])
        rec["converged"] = conv
        if nelec:
            st["nelec"] = nelec
        ok = ok and conv
        if ok and stage == "f2":
            camp["labels_f2"] += 1
    else:
        gap = parse_gap(j["out"], st.get("nelec")) if ok else None
        rec["gap_ev"] = round(gap, 4) if gap is not None else None
        ok = ok and gap is not None
        if ok and GAP_LO <= gap <= GAP_HI:
            camp["qualifiers"].append(name)
            if camp["billed_first_qual"] is None:
                camp["billed_first_qual"] = round(camp["billed"], 4)
    retry = (not ok and fail_kind == "solver"
             and qe_retry.next_solver(j["solver"]) is not None)
    if ok:
        st["next"] = {"f1": "f2", "f2": "f3", "f3": None}[stage]
        st.pop("solver", None)
    elif retry:
        # eigensolver crash: rerun this stage once with the next solver;
        # counted as a retry, not as a failure of the compound
        st["next"] = stage
        st["solver"] = qe_retry.next_solver(j["solver"])
        camp["solver_retries"] = camp.get("solver_retries", 0) + 1
        rec["retry_scheduled"] = st["solver"]
    else:
        st["next"] = None
        camp["fails"] += 1
        rec["stage_failed"] = True
        # crashed compounds are reported apart from compounds that ran
        # and missed the band-gap window
        if outcome == "crashed":
            camp.setdefault("crashed", []).append(
                {"candidate": name, "stage": stage, "kind": fail_kind})
    camp["jobs"].append(rec)
    # wire: masked times for CEDT (quant on), true for DTDE/unmasked
    w_end = t_vis if quant_on else j["done_at"]
    wire({"arm": arm, "seed": seed, "opaque_id": opaque(name, seed),
          "cls": stage, "mem_bit": (CAND[name]["mem_bit"]
                                    if arm.startswith("CEDT") else None),
          "t_start": round(j["t0"], 1), "t_end": round(w_end, 1),
          "wall_s": round(w_end - j["t0"], 1),
          "billed_nh": round(billed, 4), "ok": ok})
    # The f3 NSCF reads the f2 SCF's charge density from ./out, so the
    # save dir may only be removed once this candidate's ladder is over
    # (f3 done or any stage failed). Unconditional removal here voided
    # every f3 in attempt 2 windows A/B ("needed files are missing").
    if st["next"] is None:
        shutil.rmtree(j["wd"] / "out", ignore_errors=True)


def run_campaign(arm, seed, order, quant_on):
    camp = {"arm": arm, "seed": seed, "quant": QUANT if quant_on else 0,
            "billed": 0.0, "labels_f2": 0, "billed_first_qual": None,
            "qualifiers": [], "fails": 0, "jobs": [],
            "ladders": {n: {"next": None} for n in order},
            "t_start": time.time(), "node": node_info(),
            "max_calls": MAX_CALLS,
            "mask": (MASK if quant_on else "none")}
    launched = 0
    opened = []
    running = []
    pending = []          # finished, awaiting visibility
    idx = 0
    while True:
        now = time.time()
        for j in running[:]:
            if j["proc"].poll() is not None and j["done_at"] is None:
                j["done_at"] = now
                j["t_vis"] = visible_at(j, now) if quant_on else now
                running.remove(j)
                pending.append(j)
        for j in pending[:]:
            if now >= j["t_vis"]:
                pending.remove(j)
                finalize(arm, seed, camp, j, j["t_vis"], quant_on)
        # launch phase: reservations of running + pending (still held)
        held = running + pending
        while launched < MAX_CALLS and camp["billed"] < CAMPAIGN_CAP:
            used_gb = sum(j["res"] for j in held)
            used_rk = len(running) * RANKS
            job = None
            # deepest-ready-first over opened ladders
            for st_want in ("f3", "f2", "f1"):
                for n in opened:
                    if camp["ladders"][n]["next"] == st_want and \
                       not any(h["name"] == n for h in held):
                        job = (n, st_want)
                        break
                if job:
                    break
            if job is None and len([n for n in opened
                                    if camp["ladders"][n]["next"]
                                    or any(h["name"] == n
                                           for h in held)]) < MAX_LADDERS \
                    and idx < len(order):
                job = (order[idx], "f1")
            if job is None:
                break
            name, stage = job
            res = reservation(arm, name, stage)
            est_billed = est_wall_h(name, stage) * frac(res) * 1.3
            if used_gb + res > PACK_GB or used_rk + RANKS > NODE_CORES:
                break
            if STATE["billed"] + est_billed > W_CAP:
                print(f"WCAP: refusing {name}.{stage} "
                      f"(billed={STATE['billed']:.1f})", flush=True)
                camp["cap_refused"] = True
                launched = MAX_CALLS
                break
            solver = None
            if stage == "f1" and name not in opened:
                camp["ladders"][name] = {"next": None}
                opened.append(name)
                idx = order.index(name) + 1
            else:
                solver = camp["ladders"][name].get("solver")
                camp["ladders"][name]["next"] = None   # in flight
            j = launch(arm, seed, name, stage, solver)
            running.append(j)
            held = running + pending
            launched += 1
            print(f"[{arm} s{seed}] launch {name}.{stage} "
                  f"res={j['res']}GB streams={len(running)} "
                  f"call={launched}/{MAX_CALLS}", flush=True)
        if launched >= MAX_CALLS and not running and not pending:
            break
        if not running and not pending and launched < MAX_CALLS:
            # nothing launchable (cap or exhaustion)
            break
        time.sleep(POLL_S)
    camp["makespan_s"] = round(time.time() - camp["t_start"], 1)
    camp["billed"] = round(camp["billed"], 4)
    # sweep save dirs of ladders the call budget cut off before f3
    for n in camp["ladders"]:
        shutil.rmtree(WORK / f"{arm}_s{seed}" / n / "out",
                      ignore_errors=True)
    del camp["ladders"]
    with open(RESULTS / "campaigns.jsonl", "a") as fh:
        fh.write(json.dumps(camp) + "\n")
    print(f"DONE {arm} s{seed}: billed={camp['billed']} "
          f"labels={camp['labels_f2']} quals={len(camp['qualifiers'])} "
          f"first={camp['billed_first_qual']} "
          f"makespan={camp['makespan_s']}s", flush=True)
    return camp


def main_one():
    """One campaign per SLURM job. A guest job cancelled by the node
    owner is requeued and restarts its campaign from the first call:
    partial wire-log rows and work files of the lost attempt are
    discarded (kept in wire_log.lost.jsonl for the record)."""
    import random
    arm, seed = ONE.split(":")
    seed = int(seed)
    RESULTS.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    done = RESULTS / "campaigns.jsonl"
    if done.exists() and done.read_text().strip():
        print("campaign already recorded; nothing to do", flush=True)
        return
    wl = RESULTS / "wire_log.jsonl"
    if wl.exists():
        with open(RESULTS / "wire_log.lost.jsonl", "a") as fh:
            fh.write(wl.read_text())
        wl.unlink()
    shutil.rmtree(WORK / f"{arm}_s{seed}", ignore_errors=True)
    names = [r["name"] for r in MAN["candidates"]]
    order = names[:]
    random.Random(2000 + seed).shuffle(order)
    quant_on = arm == "CEDT_P4" and (MASK == "prop" or QUANT > 0)
    c = run_campaign(arm, seed, order, quant_on=quant_on)
    json.dump({"campaign": {k: c[k] for k in
                            ("arm", "seed", "billed", "labels_f2",
                             "billed_first_qual", "qualifiers", "fails",
                             "makespan_s", "node", "mask")},
               "billed_total": round(STATE["billed"], 3),
               "calls": STATE["calls"]},
              open(RESULTS / "progress.json", "w"), indent=1)
    print("LIVE3 CAMPAIGN DONE", STATE, flush=True)


def main():
    if ONE:
        return main_one()
    RESULTS.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(exist_ok=True)
    names = [r["name"] for r in MAN["candidates"]]
    t0 = time.time()
    summary = []

    def prog():
        json.dump({"campaigns": summary,
                   "billed_total": round(STATE["billed"], 3),
                   "calls": STATE["calls"],
                   "wall_h": round((time.time() - t0) / 3600, 2)},
                  open(RESULTS / "progress.json", "w"), indent=1)

    import random
    for seed in range(SEED_LO, SEED_HI + 1):
        order = names[:]
        random.Random(2000 + seed).shuffle(order)
        arms = (["DTDE", "CEDT_P4"] if seed % 2 == 0
                else ["CEDT_P4", "DTDE"])
        for arm in arms:
            c = run_campaign(arm, seed, order, quant_on=(
                arm == "CEDT_P4" and QUANT > 0))
            summary.append({k: c[k] for k in
                            ("arm", "seed", "billed", "labels_f2",
                             "billed_first_qual", "qualifiers", "fails",
                             "makespan_s")})
            prog()
    for seed in REPLAY:
        order = names[:]
        random.Random(2000 + seed).shuffle(order)
        c = run_campaign("CEDT_P4_UNMASKED", seed, order, quant_on=False)
        summary.append({k: c[k] for k in
                        ("arm", "seed", "billed", "labels_f2",
                         "billed_first_qual", "qualifiers", "fails",
                         "makespan_s")})
        prog()
    json.dump({"campaigns": summary,
               "billed_total": round(STATE["billed"], 3),
               "calls": STATE["calls"], "quant": QUANT,
               "window": [SEED_LO, SEED_HI], "replay": REPLAY,
               "wall_h": round((time.time() - t0) / 3600, 2)},
              open(RESULTS / f"summary_w{SEED_LO}_{SEED_HI}.json", "w"),
              indent=1)
    print("LIVE2 WINDOW DONE", STATE, flush=True)


if __name__ == "__main__":
    main()

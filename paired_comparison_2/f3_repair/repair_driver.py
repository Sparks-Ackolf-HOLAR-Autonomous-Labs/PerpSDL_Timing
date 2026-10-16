#!/usr/bin/env python3
"""F3 repair pass for comparison No. 2 attempt 2.

The attempt-2 driver bug deleted each candidate's QE save directory
after every call, so all F3 (NSCF/bands) calls failed ("needed files
are missing") and no gap was ever measured. This pass re-measures, with
the FIXED ladder handling, the 8x8 F2 charge density + F3 gap for every
candidate whose ladder attempted an F3 anywhere in the attempt-2
transcript (windows A and B, replay included).

Deduplication argument (recorded in REPAIR_AND_FALLBACK_PLAN.md): the
gap and the F3 wall time are properties of the candidate at the fixed
execution config (16 ranks, npool 1) - identical in both arms and all
seeds - so ONE F2+F3 per unique candidate suffices to reconstruct every
campaign. The per-campaign counterfactual billing is done afterwards by
repair_regrade.py using each original job record's own reservation.

Scheduling here is operational only (not part of the graded
experiment): at most 2 concurrent 16-rank streams, gated so the summed
worst-case reservations stay under PACK_GB. Billing of the repair run
itself is tracked against MPT_REPAIR_CAP as a separate entry of the cost record.

Runs on granite grn061 after window B (sbatch --dependency=afterany).
Reads   $MPT_LIVE2_ROOT/results/campaigns.jsonl  (full attempt-2 data)
Writes  $MPT_LIVE2_ROOT/results_repair/repair_gaps.json (+ f3 outputs)
"""
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(os.environ.get("MPT_LIVE2_ROOT", ".")).resolve()
INPUTS = ROOT / "inputs"
WORK = ROOT / "work_repair"
RES = ROOT / "results_repair"
NODE_CORES = 64
NODE_GB = 380.0
PACK_GB = 342.0
RANKS = 16
MAX_STREAMS = 2
REPAIR_CAP = float(os.environ.get("MPT_REPAIR_CAP", "80"))
POLL_S = 15
STAGE_RAM = {"f2": 1.00, "f3": 1.05}

MAN = json.load(open(INPUTS / "manifest2.json"))
CAND = {r["name"]: r for r in MAN["candidates"]}


def res_gb(name, stage):
    return round(1.10 * CAND[name]["ram_est_gb"] * STAGE_RAM[stage], 1)


def frac(gb):
    return max(RANKS / NODE_CORES, gb / NODE_GB)


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


def launch(name, stage):
    wd = WORK / name
    wd.mkdir(parents=True, exist_ok=True)
    if not (wd / "pseudos").exists():
        (wd / "pseudos").symlink_to(ROOT / "pseudos")
    out = wd / f"{stage}.out"
    cmd = ["/usr/bin/time", "-v", "-o", str(wd / f"{stage}.time"),
           "mpirun", "-np", str(RANKS), "--bind-to", "none",
           "pw.x", "-nk", "1", "-in", str(INPUTS / f"{name}.{stage}.in")]
    fh = open(out, "w")
    proc = subprocess.Popen(cmd, cwd=wd, stdout=fh,
                            stderr=subprocess.STDOUT)
    print(f"[repair] launch {name}.{stage} res={res_gb(name, stage)}GB",
          flush=True)
    return {"proc": proc, "fh": fh, "wd": wd, "out": out, "name": name,
            "stage": stage, "t0": time.time()}


def main():
    RES.mkdir(parents=True, exist_ok=True)
    (RES / "f3_outputs").mkdir(exist_ok=True)
    WORK.mkdir(exist_ok=True)
    camps = [json.loads(l) for l in
             open(ROOT / "results" / "campaigns.jsonl") if l.strip()]
    scope = os.environ.get("MPT_REPAIR_SCOPE", "attempted")
    if scope == "all":
        todo = sorted(CAND)
    else:
        todo = sorted({j["candidate"] for c in camps
                       for j in c["jobs"] if j["cls"] == "f3"})
    print(f"[repair] scope={scope}: {len(todo)} candidates: {todo}",
          flush=True)
    # heaviest first so the tight pairings happen early and predictably
    todo.sort(key=lambda n: -CAND[n]["ram_est_gb"])
    gaps = {}
    calls = []
    billed = 0.0
    running = []
    pending = todo[:]
    cap_hit = False
    while running or (pending and not cap_hit):
        now = time.time()
        for j in running[:]:
            if j["proc"].poll() is None:
                continue
            running.remove(j)
            j["fh"].close()
            wall = now - j["t0"]
            rc = j["proc"].returncode
            b = wall / 3600.0 * frac(res_gb(j["name"], j["stage"]))
            billed += b
            name, stage = j["name"], j["stage"]
            rec = {"candidate": name, "stage": stage, "rc": rc,
                   "wall_s": round(wall, 1), "billed_nh": round(b, 4)}
            tf = j["wd"] / f"{stage}.time"
            if tf.exists():
                m = re.search(r"Maximum resident set size.*: (\d+)",
                              tf.read_text())
                if m:
                    rec["peak_rank_rss_gb"] = round(
                        int(m.group(1)) / 1048576, 2)
            g = gaps.setdefault(name, {})
            if stage == "f2":
                conv, nelec = parse_scf(j["out"])
                rec["converged"] = conv
                g.update({"f2_wall_s": round(wall, 1), "rc_f2": rc,
                          "f2_converged": conv, "nelec": nelec})
                if rc == 0 and conv:
                    running.append(launch(name, "f3"))
                else:
                    g["gap_ev"] = None
                    shutil.rmtree(j["wd"] / "out", ignore_errors=True)
            else:
                gap = parse_gap(j["out"], g.get("nelec")) if rc == 0 \
                    else None
                g.update({"f3_wall_s": round(wall, 1), "rc_f3": rc,
                          "gap_ev": round(gap, 4)
                          if gap is not None else None,
                          "f3_billed_16rk": round(b, 4)})
                shutil.copy2(j["out"],
                             RES / "f3_outputs" / f"{name}.f3.out")
                shutil.rmtree(j["wd"] / "out", ignore_errors=True)
            calls.append(rec)
            json.dump({"gaps": gaps, "billed": round(billed, 3),
                       "n_done": sum(1 for v in gaps.values()
                                     if "gap_ev" in v)},
                      open(RES / "repair_progress.json", "w"), indent=1)
        # launch: F3 continuations are appended directly above; here we
        # only open new candidates (F2), respecting streams/memory/cap
        while pending and len(running) < MAX_STREAMS:
            used = sum(res_gb(j["name"], j["stage"]) for j in running)
            pick = next((n for n in pending
                         if used + res_gb(n, "f3") <= PACK_GB), None)
            if pick is None:
                break
            # anchors: measured window-A F2 max 9.7 h at 3328 e (16
            # ranks); F3 assumed <= 0.6 x F2; ^2 nelec scaling; 1.3 pad
            est = (9.8 + 6.0) * (CAND[pick]["nelec"] / 3328.0) ** 2.0 \
                * frac(res_gb(pick, "f3")) * 1.3
            if billed + est > REPAIR_CAP:
                print(f"REPAIR_CAP: refusing {pick} "
                      f"(billed={billed:.1f})", flush=True)
                cap_hit = True
                break
            pending.remove(pick)
            running.append(launch(pick, "f2"))
        if running:
            time.sleep(POLL_S)
    json.dump({"scope": scope, "cap_hit": cap_hit,
               "billed_repair_nh": round(billed, 3),
               "calls": calls, "gaps": gaps},
              open(RES / "repair_gaps.json", "w"), indent=1)
    print(f"REPAIR DONE billed={billed:.2f} pc-nh "
          f"gaps={sum(1 for v in gaps.values() if v.get('gap_ev') is not None)}"
          f"/{len(todo)}", flush=True)


if __name__ == "__main__":
    main()

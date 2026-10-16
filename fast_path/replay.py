#!/usr/bin/env python3
"""Recorded-cost replay of the comparison No. 2 driver.

Re-executes the exact launch/packing/masking/billing logic of
paired_comparison_2/live2_campaign.py as a discrete-event simulation, with
each QE call's run time looked up in a cost library built from measured
calls instead of launching pw.x. Used to check whether recorded run
times can stand in for re-running a whole campaign.

Modes
  --validate   rebuild all 33 measured campaigns of No. 2 with the
               library built from the OTHER campaigns (leave-one-out),
               F3 treated as it actually ran (fails after 10 s);
               compare job sequence, bill, makespan, labels/nh ratio.
  --repaired   same campaigns, F3 priced from the repair pass
               (fixed driver), gaps from the repair pass.
"""
import argparse, json, math, random, statistics as st, sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
L2 = HERE.parent / "paired_comparison_2"
MAN = json.load(open(L2 / "inputs" / "manifest2.json"))
CAND = {r["name"]: r for r in MAN["candidates"]}
NAMES = [r["name"] for r in MAN["candidates"]]
NODE_CORES, NODE_GB, PACK_GB, RANKS = 64, 380.0, 342.0, 16
MAX_CALLS, MAX_LADDERS, CAMPAIGN_CAP = 8, 3, 25.0
GAP_LO, GAP_HI = 1.0, 2.0
STAGE_RAM = {"f1": 0.85, "f2": 1.00, "f3": 1.05}
CLASS_MAX = max(r["ram_est_gb"] for r in MAN["candidates"])
BIT0_MAX = max(r["ram_est_gb"] for r in MAN["candidates"]
               if r["mem_bit"] == 0)
POLL = 10.0


def reservation(arm, name, stage):
    r = CAND[name]
    base = (CLASS_MAX if r["mem_bit"] else BIT0_MAX) \
        if arm.startswith("CEDT") else CLASS_MAX
    return round(1.10 * base * STAGE_RAM[stage], 1)


def frac(res):
    return max(RANKS / NODE_CORES, res / NODE_GB)


def load_campaigns():
    return [json.loads(l) for l in open(L2 / "results" / "campaigns.jsonl")]


def build_library(camps, exclude=None):
    lib = defaultdict(list)
    for i, c in enumerate(camps):
        if i == exclude:
            continue
        for j in c["jobs"]:
            if j["rc"] == 0 and j["cls"] in ("f1", "f2"):
                lib[(j["candidate"], j["cls"])].append(j["wall_s"])
    return {k: st.mean(v) for k, v in lib.items()}


def load_repair():
    d = json.load(open(L2 / "f3_repair" / "results_raw" / "repair_gaps.json"))
    f3, gap = {}, {}
    for c in d["calls"]:
        if c["stage"] == "f3" and c["rc"] == 0:
            f3[c["candidate"]] = c["wall_s"]
    for k, v in d.items():
        if k in ("gaps", "gap_ev") and isinstance(v, dict):
            gap.update(v)
    return f3, gap, d


def simulate(arm, seed, lib, f3_mode, quant, t_start=0.0, f3lib=None,
             gaps=None):
    """f3_mode: 'asrun' (fails in 10 s) or 'repaired'."""
    order = NAMES[:]
    random.Random(2000 + seed).shuffle(order)
    q = quant

    def boundary(t):
        return math.ceil(t / q) * q if q > 0 else t
    camp = {"billed": 0.0, "labels_f2": 0, "billed_first_qual": None,
            "qualifiers": [], "jobs": [], "missing": []}
    lad = {n: {"next": None} for n in order}
    t = t_start
    launched, idx = 0, 0
    opened, running, pending = [], [], []

    def dur(name, stage):
        if stage == "f3":
            if f3_mode == "asrun":
                return 10.0, False
            w = (f3lib or {}).get(name)
            if w is None:
                camp["missing"].append((name, stage))
                return 3600.0, False
            return w, True
        w = lib.get((name, stage))
        if w is None:
            camp["missing"].append((name, stage))
            w = 3600.0
        return w, True

    while True:
        for j in running[:]:
            if j["end"] <= t:
                j["done_at"] = t
                j["t_vis"] = boundary(t)
                running.remove(j); pending.append(j)
        for j in pending[:]:
            if t >= j["t_vis"]:
                pending.remove(j)
                billed = (j["t_vis"] - j["t0"]) / 3600 * frac(j["res"])
                camp["billed"] += billed
                name, stage, ok = j["name"], j["stage"], j["ok"]
                if ok and stage == "f2":
                    camp["labels_f2"] += 1
                if stage == "f3" and ok:
                    g = (gaps or {}).get(name)
                    if g is not None and GAP_LO <= g <= GAP_HI:
                        camp["qualifiers"].append(name)
                        if camp["billed_first_qual"] is None:
                            camp["billed_first_qual"] = camp["billed"]
                lad[name]["next"] = ({"f1": "f2", "f2": "f3",
                                      "f3": None}[stage] if ok else None)
                camp["jobs"].append((name, stage, round(billed, 4)))
        held = running + pending
        while launched < MAX_CALLS and camp["billed"] < CAMPAIGN_CAP:
            used_gb = sum(j["res"] for j in held)
            job = None
            for want in ("f3", "f2"):
                for n in opened:
                    if lad[n]["next"] == want and \
                       not any(h["name"] == n for h in held):
                        job = (n, want); break
                if job:
                    break
            if job is None and len([n for n in opened if lad[n]["next"]
                                    or any(h["name"] == n for h in held)]) \
                    < MAX_LADDERS and idx < len(order):
                job = (order[idx], "f1")
            if job is None:
                break
            name, stage = job
            res = reservation(arm, name, stage)
            if used_gb + res > PACK_GB or \
               (len(running) + 1) * RANKS > NODE_CORES:
                break
            if stage == "f1":
                lad[name] = {"next": None}; opened.append(name)
                idx = order.index(name) + 1
            else:
                lad[name]["next"] = None
            w, ok = dur(name, stage)
            j = {"name": name, "stage": stage, "t0": t, "end": t + w,
                 "res": res, "ok": ok}
            running.append(j); held = running + pending
            launched += 1
        if launched >= MAX_CALLS and not running and not pending:
            break
        if not running and not pending:
            break
        # jump to next event on the driver's 10-s polling grid
        nxt = min([j["end"] for j in running] +
                  [j["t_vis"] for j in pending])
        t = t + max(POLL, math.ceil((nxt - t) / POLL) * POLL)
    camp["makespan_s"] = t - t_start
    return camp


def validate():
    camps = load_campaigns()
    rows = []
    for i, c in enumerate(camps):
        lib = build_library(camps, exclude=i)
        # fall back to the full library if a key was only seen here
        full = build_library(camps)
        for k, v in full.items():
            lib.setdefault(k, v)
        s = simulate(c["arm"], c["seed"], lib, "asrun", c["quant"],
                     t_start=c["t_start"])
        meas_seq = [(j["candidate"], j["cls"]) for j in c["jobs"]]
        sim_seq = [(a, b) for a, b, _ in s["jobs"]]
        rows.append({
            "arm": c["arm"], "seed": c["seed"],
            "seq_match": sorted(meas_seq) == sorted(sim_seq),
            "order_match": meas_seq == sim_seq,
            "billed_meas": c["billed"], "billed_sim": round(s["billed"], 4),
            "rel_err": round(s["billed"] / c["billed"] - 1, 4),
            "makespan_meas_h": round(c["makespan_s"] / 3600, 2),
            "makespan_sim_h": round(s["makespan_s"] / 3600, 2),
            "labels_meas": c["labels_f2"], "labels_sim": s["labels_f2"],
            "missing": s["missing"]})
    def ratio(key_b, key_l, src):
        a = {r["arm"]: [0, 0] for r in src}
        for r in src:
            a[r["arm"]][0] += r[key_l]; a[r["arm"]][1] += r[key_b]
        return (a["CEDT_P4"][0] / a["CEDT_P4"][1]) / \
               (a["DTDE"][0] / a["DTDE"][1])
    main_rows = [r for r in rows if r["arm"] in ("DTDE", "CEDT_P4")]
    errs = [abs(r["rel_err"]) for r in rows]
    out = {
        "n_campaigns": len(rows),
        "job_set_match": sum(r["seq_match"] for r in rows),
        "job_order_match": sum(r["order_match"] for r in rows),
        "bill_abs_rel_err_median": round(st.median(errs), 4),
        "bill_abs_rel_err_max": round(max(errs), 4),
        "H_ratio_measured": round(ratio("billed_meas", "labels_meas",
                                        main_rows), 4),
        "H_ratio_replayed": round(ratio("billed_sim", "labels_sim",
                                        main_rows), 4),
        "paired_bill_sign_agree": None,
        "rows": rows}
    agree = 0; n = 0
    for s_ in sorted({r["seed"] for r in main_rows}):
        d = {r["arm"]: r for r in main_rows if r["seed"] == s_}
        n += 1
        agree += ((d["CEDT_P4"]["billed_meas"] < d["DTDE"]["billed_meas"])
                  == (d["CEDT_P4"]["billed_sim"] < d["DTDE"]["billed_sim"]))
    out["paired_bill_sign_agree"] = f"{agree}/{n}"
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--out", default=str(HERE / "results" /
                                         "replay_validation.json"))
    a = ap.parse_args()
    res = validate()
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(a.out, "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "rows"},
                     indent=1))
    for r in res["rows"]:
        print(r["arm"], r["seed"], r["order_match"], r["billed_meas"],
              r["billed_sim"], r["rel_err"], r["makespan_meas_h"],
              r["makespan_sim_h"], r["missing"] or "")

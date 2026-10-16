#!/usr/bin/env python3
"""Route 3, step 2: grade comparison No. 3 arm sets and
timing-mask clauses by replaying the comparison No. 2 driver rules on
recorded run times (see replay.py for the validation).

Arms (all at 16 ranks, npool 1; they differ only in the memory each job
reserves and in whether completions are timing-masked):
  DTDE      no sharing: every job reserves 1.10 x class worst case
  CTDE      shared training records, no execution sharing: the centre
            still cannot tell jobs apart at launch, so it reserves as
            DTDE; the research side's candidate order is unchanged in
            this replay, so CTDE reduces to DTDE for this mechanism
  MIX50     half delegation: each job goes through the broker with
            probability 0.5 (common random numbers per seed and job)
  CEDT_P4   broker with one memory bit per job
  CTDE_P2   live option-C definition (2026-10-01): the centre reserves
            1.10 x the largest job RAM in its shared logbook for the
            job's P2 size bin and stage (seeded from No. 2, capped at
            the DTDE worst case); records are shared with true times
            and size bin, so every job is visible to the attacker
  CTCE      full sharing reference: reserves 1.10 x the job's own
            estimate, no mask (no leakage limits apply)
Masks (broker-routed jobs only): none, fixed600 (No. 2), prop25
(run time rounded up to 25% of its expected run time).

Library: measured No. 2 F1/F2 calls, repair-pass F3 calls, plus the
granite-guest library ladders when present (results_lib3/*.json).
Missing entries are filled, and flagged, by the median stage ratio
from the same compound's other stage, else by the size law; a result
counts as final only when no fill was used.
"""
import argparse, json, math, random, statistics as st
from pathlib import Path
import replay as R

HERE = Path(__file__).resolve().parent
EST_H16 = {"f1": 4.2, "f2": 6.5, "f3": 4.0}


def build(lib3_dir=None):
    camps = R.load_campaigns()
    lib = dict(R.build_library(camps))
    f3, _, d = R.load_repair()
    for n, w in f3.items():
        lib[(n, "f3")] = w
    gaps = {n: v["gap_ev"] for n, v in d["gaps"].items()
            if isinstance(v, dict) and v.get("gap_ev") is not None}
    src = {k: "No.2/repair (grn061)" for k in lib}
    if lib3_dir and Path(lib3_dir).exists():
        for p in Path(lib3_dir).glob("*.json"):
            r = json.load(open(p))
            if r.get("role") != "missing":
                continue
            for c in r["calls"]:
                if c["outcome"] == "converged":
                    lib[(r["candidate"], c["stage"])] = c["wall_s"]
                    src[(r["candidate"], c["stage"])] = "guest ladder"
                    if c["stage"] == "f3" and c.get("gap_ev") is not None:
                        gaps[r["candidate"]] = c["gap_ev"]
    # stage ratios from compounds with both entries
    rat = {}
    for a, b in (("f1", "f2"), ("f2", "f3")):
        rs = [lib[(n, b)] / lib[(n, a)] for n in R.NAMES
              if (n, a) in lib and (n, b) in lib]
        rat[(a, b)] = st.median(rs)
    law = {s: st.median([v / (R.CAND[n]["nelec"] / 3328) ** 2
                         for (n, ss), v in lib.items() if ss == s])
           for s in ("f1", "f2", "f3")}
    filled = []
    for n in R.NAMES:
        for s in ("f1", "f2", "f3"):
            if (n, s) in lib:
                continue
            if s == "f2" and (n, "f1") in lib:
                w = lib[(n, "f1")] * rat[("f1", "f2")]
            elif s == "f3" and (n, "f2") in lib:
                w = lib[(n, "f2")] * rat[("f2", "f3")]
            else:
                w = law[s] * (R.CAND[n]["nelec"] / 3328) ** 2
            lib[(n, s)] = w
            src[(n, s)] = "filled"
            filled.append(f"{n}.{s}")
    for n in R.NAMES:        # compounds with no 8x8 gap: folded 1x1 gap
        if n not in gaps and R.CAND[n].get("gap_1x1_ev") is not None:
            gaps[n] = R.CAND[n]["gap_1x1_ev"]
    return lib, gaps, filled, src


LOGBOOK = json.load(open(HERE.parent / "paired_comparison_3" / "parallel" /
                        "ctde_logbook_seed.json"))["max_job_gb"]


def reservation(arm, name, stage, routed):
    r = R.CAND[name]
    if arm == "CTDE_P2":
        b = "large" if r["nelec"] > 2000 else "small"
        worst = round(1.10 * R.CLASS_MAX * R.STAGE_RAM[stage], 1)
        rec = LOGBOOK.get(f"{b}:{stage}")
        if stage == "f3" and f"{b}:f2" in LOGBOOK:
            rec = max(rec or 0.0, LOGBOOK[f"{b}:f2"] * 1.05)
        return worst if rec is None else min(worst, round(1.10 * rec, 1))
    if arm == "CTCE":
        base = r["ram_est_gb"]
    elif routed:
        base = R.CLASS_MAX if r["mem_bit"] else R.BIT0_MAX
    else:
        base = R.CLASS_MAX
    return round(1.10 * base * R.STAGE_RAM[stage], 1)


def routed_of(arm, seed, name, stage):
    if arm in ("CEDT_P4",):
        return True
    if arm == "MIX50":
        return random.Random(f"{seed}:{name}:{stage}").random() < 0.5
    return False


def simulate(arm, seed, lib, gaps, mask, max_calls):
    order = R.NAMES[:]
    random.Random(2000 + seed).shuffle(order)
    camp = {"billed": 0.0, "labels_f2": 0, "first": None, "quals": [],
            "held_s": 0.0, "wire": []}
    lad = {n: {"next": None} for n in order}
    t, launched, idx = 0.0, 0, 0
    opened, running, pending = [], [], []

    def vis(j, now):
        if not j["routed"] or arm == "CTCE" or mask == "none":
            return now
        if mask == "fixed600":
            return math.ceil(now / 600) * 600
        q = max(60.0, 0.25 * EST_H16[j["stage"]] * 3600 *
                (R.CAND[j["name"]]["nelec"] / 3328.0) ** 2)
        return j["t0"] + math.ceil((now - j["t0"]) / q) * q

    while True:
        for j in running[:]:
            if j["end"] <= t:
                j["t_vis"] = vis(j, t)
                camp["held_s"] += j["t_vis"] - t
                running.remove(j); pending.append(j)
        for j in pending[:]:
            if t >= j["t_vis"]:
                pending.remove(j)
                b = (j["t_vis"] - j["t0"]) / 3600 * R.frac(j["res"])
                camp["billed"] += b
                n, s = j["name"], j["stage"]
                camp["wire"].append((n, s, j["t_vis"] - j["t0"], j["routed"]))
                if s == "f2":
                    camp["labels_f2"] += 1
                if s == "f3":
                    g = gaps.get(n)
                    if g is not None and R.GAP_LO <= g <= R.GAP_HI:
                        camp["quals"].append(n)
                        if camp["first"] is None:
                            camp["first"] = camp["billed"]
                lad[n]["next"] = {"f1": "f2", "f2": "f3", "f3": None}[s]
        held = running + pending
        while launched < max_calls and camp["billed"] < R.CAMPAIGN_CAP:
            used = sum(j["res"] for j in held)
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
                    < R.MAX_LADDERS and idx < len(order):
                job = (order[idx], "f1")
            if job is None:
                break
            n, s = job
            ro = routed_of(arm, seed, n, s)
            res = reservation(arm, n, s, ro)
            if used + res > R.PACK_GB or \
               (len(running) + 1) * R.RANKS > R.NODE_CORES:
                break
            if s == "f1":
                lad[n] = {"next": None}; opened.append(n)
                idx = order.index(n) + 1
            else:
                lad[n]["next"] = None
            running.append({"name": n, "stage": s, "t0": t,
                            "end": t + lib[(n, s)], "res": res,
                            "routed": ro})
            held = running + pending
            launched += 1
        if not running and not pending:
            break
        nxt = min([j["end"] for j in running] +
                  [j["t_vis"] for j in pending])
        t += max(R.POLL, math.ceil((nxt - t) / R.POLL) * R.POLL)
    camp["makespan_h"] = t / 3600
    return camp


# Timing attacker (in grade): knows every compound's recorded run time
# per stage (the candidates are public CC0) and sees (stage, visible
# duration) of each broker-routed job; guesses the nearest compound.
# Reported as the exact identification rate (limit about 0.087).


def grade(lib, gaps, arms, masks, seeds, max_calls):
    out = {}
    for mask in masks:
        runs = {a: [simulate(a, s, lib, gaps, mask, max_calls)
                    for s in seeds] for a in arms}
        base = runs["DTDE"]
        dl = sum(c["labels_f2"] for c in base)
        db = sum(c["billed"] for c in base)
        for a in arms:
            if a == "DTDE" or (mask != "none" and a == "CTCE"):
                continue
            cs = runs[a]
            h = (sum(c["labels_f2"] for c in cs) / sum(c["billed"] for c in cs)) / (dl / db)
            wins = ties = 0
            for c, d in zip(cs, base):
                fa, fd = c["first"], d["first"]
                if fa is None and fd is None:
                    ties += 1
                elif fd is None or (fa is not None and fa < fd):
                    wins += 1
            # timing attacker on broker-routed wire rows
            hit = tot = 0
            for c in cs:
                for n, s, dur, ro in c["wire"]:
                    if not ro and a != "CTDE_P2":   # only routed jobs cross the wire
                        continue
                    tot += 1
                    pool = R.NAMES
                    if a == "CTDE_P2":    # attacker also sees the P2 size bin
                        big = R.CAND[n]["nelec"] > 2000
                        pool = [m for m in R.NAMES
                                if (R.CAND[m]["nelec"] > 2000) == big]
                    guess = min(pool, key=lambda m: abs(lib[(m, s)] - dur))
                    hit += guess == n
            out[f"{a}|{mask}"] = {
                "H_ratio_labels_per_pcnh": round(h, 3),
                "PW60_wins": f"{wins}/{len(seeds)}",
                "PW60_pass": wins >= math.ceil(0.6 * len(seeds)),
                "pairs_neither_found": ties,
                "billed_median": round(st.median(c["billed"] for c in cs), 2),
                "billed_total": round(sum(c["billed"] for c in cs), 1),
                "makespan_median_h": round(st.median(c["makespan_h"] for c in cs), 1),
                "mask_held_h_total": round(sum(c["held_s"] for c in cs) / 3600, 1),
                "timing_identity_rate": round(hit / tot, 3) if tot else None,
                "qualifiers_per_campaign": round(st.mean(len(c["quals"]) for c in cs), 2)}
        out[f"DTDE|{mask}"] = {
            "billed_total": round(db, 1),
            "timing_identity_rate_if_visible": round(
                sum(min(R.NAMES, key=lambda m: abs(lib[(m, s)] - dur)) == n
                    for c in base for n, s, dur, _ in c["wire"]) /
                sum(len(c["wire"]) for c in base), 3),
            "makespan_median_h": round(st.median(c["makespan_h"] for c in base), 1)}
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lib3", default=str(HERE / "results_lib3"))
    ap.add_argument("--calls", type=int, default=16)
    ap.add_argument("--seeds", type=int, default=15)
    ap.add_argument("--out", default=str(HERE / "results" / "option_replay.json"))
    a = ap.parse_args()
    lib, gaps, filled, src = build(a.lib3)
    res = {"status": "final" if not filled else "provisional",
           "filled_entries": filled, "calls": a.calls, "seeds": a.seeds,
           "grades": grade(lib, gaps, ["DTDE", "CTDE", "CTDE_P2", "MIX50", "CEDT_P4", "CTCE"],
                           ["none", "fixed600", "prop25"],
                           list(range(a.seeds)), a.calls)}
    json.dump(res, open(a.out, "w"), indent=1)
    print(res["status"], len(filled), "filled")
    for k, v in res["grades"].items():
        print(k, v)

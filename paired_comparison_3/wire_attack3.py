#!/usr/bin/env python3
"""Timing attack on comparison No. 3, registered in
TIMING_ATTACK_PLAN.md (2026-10-12) and parallel/OPTION_C.md
(P-2026-10-01 item 3). Adapted from ../paired_comparison_2/wire_attack2.py.

Data: collected_2026-10-14/<ARM>_s<seed>/ (60 campaigns, seeds 0-14) and
site_bridge_2026-10-14/<ARM>_s<seed>/ (12 notchpeak copies of granite
campaigns, same seed and compound order). Older snapshots are not read.

Attacker view per job: the wire_log.jsonl row (arm, seed, opaque_id, cls,
mem_bit, size_bin, t_start, t_end, wall_s, ok). CEDT_P4 and the routed
half of MIX50 carry the proportional mask (run time rounded up to 25 % of
the expected run time); a routed MIX50 job is visible as mem_bit not null.
CTDE_P2 carries true times plus the size bin. DTDE carries true times; its
wire rows equal its scheduler records (checked below). Ground truth is
recovered offline from the salted hash and never enters the features.

Attack 1 (identity): leave-one-seed-out; reference = median wall_s per
(compound, cls) from the other seeds' labelled jobs (plus mem_bit and
size_bin where disclosed, used as hard constraints); held-out ids matched
by mean |log wall| distance over their successful f1/f2 jobs. Limit
1/29 + 0.05. Attack 2 (membership): per held-out campaign, score each
reference compound by -min distance to any observed fingerprint; AUC limit
0.60. Failed jobs (ok false) are excluded.

T1: notchpeak DTDE site-bridge copies, references only from granite DTDE
campaigns (other seeds). T2: T1 with every wall divided by the campaign's
median ok-F1 wall. T3: CEDT_P4 vs DTDE (same seeds 0-14). T4: median
std of log wall over repeated (compound, stage) within one cluster, DTDE
scheduler records, as computed for the timing-leakage article Fig. 2 (np.std, ddof 0).
"""
import glob
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
MAIN = HERE / "collected_2026-10-14"
BRIDGE = HERE / "site_bridge_2026-10-14"
L2 = HERE.parent / "paired_comparison_2"
SALT = "mpt-live2-2026-09-11"          # live2_campaign.py, used unchanged
NAMES = [c["name"] for c in
         json.load(open(L2 / "inputs" / "manifest2.json"))["candidates"]]
PRIOR = 1.0 / len(NAMES)
ID_LIMIT = PRIOR + 0.05
AUC_LIMIT = 0.60


def opaque(name, seed):
    return hashlib.sha1(f"{SALT}:{seed}:{name}".encode()).hexdigest()[:10]


REV = {(s, opaque(n, s)): n for s in range(64) for n in NAMES}


def cluster(host):
    return ("granite" if host.startswith("grn") else
            "notchpeak" if host.startswith("notch") else "?")


def load(root, tag):
    out = []
    for d in sorted(glob.glob(str(root / "*_s*"))):
        d = Path(d)
        camp = [json.loads(x) for x in open(d / "campaigns.jsonl")
                if x.strip()][-1]
        wire = [json.loads(x) for x in open(d / "wire_log.jsonl")
                if x.strip()]
        host = camp["node"]["host"]
        out.append({"arm": camp["arm"], "seed": camp["seed"], "src": tag,
                    "host": host, "cluster": cluster(host),
                    "cpu": camp["node"].get("cpu_model"),
                    "camp": camp, "wire": wire})
    return out


def auc(labels, scores):
    s = np.asarray(scores, float)
    lab = np.asarray(labels, bool)
    ranks = np.empty(len(s))
    ranks[np.argsort(s)] = np.arange(1, len(s) + 1)
    for v in np.unique(s):
        m = s == v
        ranks[m] = ranks[m].mean()
    n1, n0 = lab.sum(), (~lab).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    return float((ranks[lab].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def rows_of(c, routed_only=False, norm=False):
    """Successful f1/f2 wire rows of campaign c, as attacker features."""
    rows = [w for w in c["wire"] if w["ok"] and w["cls"] in ("f1", "f2")]
    if routed_only:
        rows = [w for w in rows if w["mem_bit"] is not None]
    scale = 1.0
    if norm:
        f1 = [w["wall_s"] for w in c["wire"] if w["ok"] and w["cls"] == "f1"]
        scale = float(np.median(f1))
    out = []
    for w in rows:
        # key separates masked (routed) from unmasked jobs in MIX50
        key = w["cls"] + ("_m" if (c["arm"] == "MIX50"
                                   and w["mem_bit"] is not None) else "")
        out.append({"cand": REV[(c["seed"], w["opaque_id"])],
                    "oid": w["opaque_id"], "key": key,
                    "wall": w["wall_s"] / scale, "bit": w["mem_bit"],
                    "bin": w.get("size_bin")})
    return out


def attack(targets, refs_for, routed_only=False, norm=False,
           keep_scores=False):
    """targets: campaigns attacked one at a time; refs_for(t) -> list of
    reference campaigns (never containing t). keep_scores adds each
    target's membership labels and scores to its per_campaign entry
    (used by ../bootstrap_ci/seed_bootstrap3.py)."""
    idc = idn = 0
    ml, ms = [], []
    per = []
    for t in targets:
        ref = defaultdict(lambda: defaultdict(list))
        disc = {}
        for r in refs_for(t):
            for w in rows_of(r, routed_only, norm):
                ref[w["cand"]][w["key"]].append(w["wall"])
                if w["bit"] is not None:
                    disc.setdefault(w["cand"], {})["bit"] = w["bit"]
                if w["bin"] is not None:
                    disc.setdefault(w["cand"], {})["bin"] = w["bin"]
        ref = {c: {k: float(np.median(v)) for k, v in d.items()}
               for c, d in ref.items()}
        fps, fdisc, truth = defaultdict(dict), {}, {}
        for w in rows_of(t, routed_only, norm):
            fps[w["oid"]][w["key"]] = w["wall"]
            fd = fdisc.setdefault(w["oid"], {})
            if w["bit"] is not None:
                fd["bit"] = w["bit"]
            if w["bin"] is not None:
                fd["bin"] = w["bin"]
            truth[w["oid"]] = w["cand"]
        if not fps or not ref:
            continue

        def dist(oid, cand):
            for f, v in fdisc[oid].items():
                if f in disc.get(cand, {}) and disc[cand][f] != v:
                    return float("inf")
            d = [abs(math.log(fps[oid][k]) - math.log(ref[cand][k]))
                 for k in fps[oid] if k in ref[cand]]
            return float(np.mean(d)) if d else float("inf")
        ran = set(truth.values())
        c_ok = 0
        for oid in fps:
            g = min(sorted(ref), key=lambda c: dist(oid, c))
            c_ok += g == truth[oid]
        idc += c_ok
        idn += len(fps)
        entry = {"arm": t["arm"], "seed": t["seed"], "src": t["src"],
                 "host": t["host"], "correct": c_ok, "n": len(fps)}
        per.append(entry)
        lab, sc = [], []
        for cand in ref:
            lab.append(cand in ran)
            v = -min(dist(o, cand) for o in fps)
            sc.append(v if np.isfinite(v) else -1e9)
        ml += lab
        ms += sc
        if keep_scores:
            entry["lab"], entry["sc"] = lab, sc
    acc = idc / idn if idn else float("nan")
    a = auc(ml, ms)
    return {"identity_acc": round(acc, 4), "identity_correct": idc,
            "identity_n": idn, "identity_breach": bool(acc > ID_LIMIT),
            "membership_auc": round(a, 4),
            "membership_breach": bool(a > AUC_LIMIT),
            "n_targets": len(per), "per_campaign": per}


def loso(camps):
    return lambda t: [c for c in camps if c["seed"] != t["seed"]]


def check_dtde_view(camps):
    """DTDE wire rows equal its scheduler records (true wall times)."""
    bad = 0
    for c in camps:
        if c["arm"] != "DTDE":
            continue
        jobs = [j for j in c["camp"]["jobs"]]
        for w, j in zip(c["wire"], jobs):
            if (REV[(c["seed"], w["opaque_id"])] != j["candidate"]
                    or w["cls"] != j["cls"]
                    or abs(w["wall_s"] - j["wall_s"]) > 0.11):
                bad += 1
    return bad


def spread(camps, arms=("DTDE",), ok_only=True):
    """Median within-(cluster, compound, stage) std of log true wall."""
    g = defaultdict(list)
    for c in camps:
        if c["arm"] not in arms:
            continue
        for j in c["camp"]["jobs"]:
            if ok_only and not (j["rc"] == 0
                                and j.get("outcome") == "converged"):
                continue
            g[(c["cluster"], j["candidate"], j["cls"])].append(j["wall_s"])
    res = {}
    for cl in ("granite", "notchpeak", "pooled"):
        sd = [float(np.std(np.log(v))) for k, v in g.items()
              if len(v) >= 2 and (cl == "pooled" or k[0] == cl)]
        res[cl] = {"n_pairs": len(sd),
                   "median_sd": round(float(np.median(sd)), 4) if sd else None,
                   "max_sd": round(float(np.max(sd)), 4) if sd else None}
    return res


def strip(r):
    return {k: v for k, v in r.items() if k != "per_campaign"}


def main():
    main_c = load(MAIN, "main")
    br = load(BRIDGE, "bridge")
    assert len(main_c) == 60, len(main_c)
    unresolved = sum((c["seed"], w["opaque_id"]) not in REV
                     for c in main_c + br for w in c["wire"])
    out = {"n_candidates": len(NAMES), "prior_identity_acc": round(PRIOR, 4),
           "identity_limit": round(ID_LIMIT, 4),
           "membership_auc_limit": AUC_LIMIT, "unresolved_ids": unresolved,
           "dtde_wire_vs_scheduler_mismatches": check_dtde_view(main_c + br),
           "failed_wire_rows_excluded": sum(not w["ok"] for c in main_c + br
                                            for w in c["wire"]),
           "arms": {}, "tests": {}}
    by = defaultdict(list)
    for c in main_c:
        by[c["arm"]].append(c)

    # per-arm leave-one-seed-out attacks (main 60 campaigns)
    for arm in ("CTDE_P2", "DTDE", "CEDT_P4", "MIX50"):
        r = attack(by[arm], loso(by[arm]), routed_only=(arm == "MIX50"))
        out["arms"][arm if arm != "MIX50" else "MIX50_routed"] = r
    out["arms"]["MIX50_all_jobs"] = attack(by["MIX50"], loso(by["MIX50"]))
    for arm in ("CTDE_P2", "DTDE", "CEDT_P4", "MIX50_routed",
                "MIX50_all_jobs"):
        print(arm, strip(out["arms"][arm]))

    # T1/T2: bridge DTDE copies on notchpeak, granite DTDE references
    gran = [c for c in by["DTDE"] if c["cluster"] == "granite"]
    bdt = [c for c in br if c["arm"] == "DTDE"]
    t1 = attack(bdt, loso(gran))
    t2 = attack(bdt, loso(gran), norm=True)
    # sensitivity (not the registered statistic): same-seed granite twin
    # included in the references
    t1_twin = attack(bdt, lambda t: gran)
    t2_twin = attack(bdt, lambda t: gran, norm=True)
    # sensitivity: granite references from all unmasked arms
    gran_unm = [c for c in main_c if c["cluster"] == "granite"
                and c["arm"] in ("DTDE", "CTDE_P2")]
    gran_unm_v = [dict(c, arm="DTDE") for c in gran_unm]  # no size bin used
    for c in gran_unm_v:
        c["wire"] = [dict(w, size_bin=None) for w in c["wire"]]
    t1_unm = attack(bdt, loso(gran_unm_v))
    # within-cluster baseline: notchpeak bridge copies attacked with
    # references from notchpeak DTDE campaigns (main + other bridge seeds)
    notch = [c for c in by["DTDE"] if c["cluster"] == "notchpeak"] + bdt
    t1_notch = attack(bdt, loso(notch))

    # T4
    t4 = spread(main_c + br)
    t4_main = spread(main_c)
    t4_all = spread(main_c + br, arms=("DTDE", "CTDE_P2", "CEDT_P4",
                                       "MIX50"))
    t4_allfail = spread(main_c + br, ok_only=False)

    acc = lambda k: out["arms"][k]["identity_acc"]
    ctde, mixr, cedt, dtde = (acc("CTDE_P2"), acc("MIX50_routed"),
                              acc("CEDT_P4"), acc("DTDE"))
    out["tests"]["P-2026-10-01_item3"] = {
        "condition": "CTDE_P2 > 0.80; MIX50 (routed) and CEDT_P4 in "
                     "[0.15, 0.40]",
        "CTDE_P2": ctde, "MIX50_routed": mixr, "CEDT_P4": cedt,
        "parts": {"CTDE_P2>0.80": ctde > 0.80,
                  "MIX50_routed_in_band": 0.15 <= mixr <= 0.40,
                  "CEDT_P4_in_band": 0.15 <= cedt <= 0.40},
    }
    p = out["tests"]["P-2026-10-01_item3"]
    p["pass"] = all(p["parts"].values())
    out["tests"]["T1"] = {"condition": "identity on notchpeak DTDE copies, "
                          "granite references, > 0.084",
                          "value": t1["identity_acc"],
                          "pass": t1["identity_acc"] > ID_LIMIT,
                          "result": t1}
    out["tests"]["T2"] = {"condition": "T1 attack on walls / campaign "
                          "median F1 wall reaches >= T1 accuracy",
                          "value": t2["identity_acc"],
                          "t1_value": t1["identity_acc"],
                          "pass": t2["identity_acc"] >= t1["identity_acc"],
                          "result": t2}
    out["tests"]["T3"] = {"condition": "CEDT_P4 identity < DTDE identity "
                          "(same seeds) and > 0.084; CEDT_P4 AUC > 0.60",
                          "CEDT_P4_identity": cedt, "DTDE_identity": dtde,
                          "CEDT_P4_auc":
                              out["arms"]["CEDT_P4"]["membership_auc"],
                          "parts": {
                              "below_DTDE": cedt < dtde,
                              "above_limit": cedt > ID_LIMIT,
                              "auc_above_0.60":
                                  out["arms"]["CEDT_P4"]["membership_auc"]
                                  > AUC_LIMIT}}
    out["tests"]["T3"]["pass"] = all(out["tests"]["T3"]["parts"].values())
    v4 = t4["pooled"]["median_sd"]
    out["tests"]["T4"] = {"condition": "median within-cluster repeat sd of "
                          "log wall per (compound, stage) > 0.0030",
                          "value": v4, "pass": v4 > 0.0030,
                          "by_cluster": t4}
    out["sensitivity"] = {
        "T1_with_same_seed_twin": strip(t1_twin),
        "T2_with_same_seed_twin": strip(t2_twin),
        "T1_refs_granite_DTDE_plus_CTDE_P2": strip(t1_unm),
        "bridge_copies_with_notchpeak_refs": strip(t1_notch),
        "T4_main_campaigns_only": t4_main,
        "T4_all_arms_true_wall": t4_all,
        "T4_including_failed_jobs": t4_allfail,
        "granite_DTDE_refs_n": len(gran),
        "bridge_DTDE_targets_n": len(bdt),
    }
    for k in ("P-2026-10-01_item3", "T1", "T2", "T3", "T4"):
        print(k, {a: b for a, b in out["tests"][k].items()
                  if a not in ("result", "by_cluster")})
    print("T4 by cluster", t4)
    print(json.dumps(out["sensitivity"], indent=1))
    json.dump(out, open(HERE / "timing_attack3.json", "w"), indent=1)


if __name__ == "__main__":
    main()

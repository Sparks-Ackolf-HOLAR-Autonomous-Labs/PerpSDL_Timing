#!/usr/bin/env python3
"""Regenerate the timing-leakage article figures from committed data (no new computation).

Sources (paths relative to ):
  pilot/results/pilot_results.csv                  measured, 81-job pilot
  paired_comparison_1/results/campaigns.jsonl          measured, 3x3 supercells
  timing_masking/mask_results.json                 measured walls, re-attacked
  bootstrap_ci/seed_bootstrap.json                 seed-bootstrap intervals
  paired_comparison_2/results/wire_attack_results.json measured, 8x8 supercells
  measured_attacks/attack_results.json             simulated transcripts
  decision_maker_leakage/dm_leakage.json           simulated transcripts
  paired_comparison_2/results/campaigns.jsonl         measured, 8x8 supercells
  paired_comparison_3/{collected,site_bridge}_2026-10-14/DTDE_s*/campaigns.jsonl
                                                   measured, guest nodes

Figures are written at true print size for the ACM sigconf layout
(column width 3.33 in, text width 7.0 in) with 8-pt text.
Run: python make_figures.py  (numpy + matplotlib)
"""
import json
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]  # repository root

BLUE, ORANGE, AQUA, VIOLET = "#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#d9d8d4"

plt.rcParams.update({
    "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
    "font.family": "DejaVu Sans", "axes.edgecolor": INK2,
    "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5,
    "lines.linewidth": 1.5, "savefig.dpi": 300, "pdf.fonttype": 42,
})
COL, TXT = 3.33, 7.0


def pretty(name):
    m, ph = name.split("_")
    sub = m.replace("2", "$_2$")
    return f"{sub}-{ph}"


# ---------------------------------------------------------------- Fig. 2
def fig_fingerprint():
    camps = [json.loads(x) for x in
             open(ROOT / "paired_comparison_1/results/campaigns.jsonl")]
    walls = defaultdict(list)
    for c in camps:
        for j in c["jobs"]:
            if j["arm"] == "DTDE" and j["cls"] == "f2":
                walls[j["candidate"]].append(j["wall_s"])
    cands = sorted(walls, key=lambda k: np.median(walls[k]))

    # summary statistics quoted in the text (printed for provenance)
    rel = []
    allw = defaultdict(list)
    for c in camps:
        for j in c["jobs"]:
            if j["arm"] == "DTDE":
                allw[(j["candidate"], j["cls"])].append(j["wall_s"])
    for k, v in allw.items():
        if len(v) >= 2:
            rel.append(np.std(np.log(v)))
    meds = [np.median(walls[k]) for k in cands]
    gaps = np.diff(np.log(meds))
    print(f"[fig2] repeated (candidate, class) pairs: {len(rel)}; "
          f"median within-pair log-sd {np.median(rel):.4f}, "
          f"max {np.max(rel):.4f}")
    print(f"[fig2] F2 medians {min(meds):.1f}-{max(meds):.1f} s; "
          f"median adjacent log gap {np.median(gaps):.4f}; "
          f"min {np.min(gaps):.4f}")

    fig, ax = plt.subplots(figsize=(TXT, 2.15))
    for i, k in enumerate(cands):
        col = BLUE if k.endswith("1T") else ORANGE
        v = walls[k]
        ax.plot([i] * len(v), v, "o", ms=3.8, mfc=col, mec="white",
                mew=0.4, zorder=3)
    ax.set_yscale("log")
    ax.set_xticks(range(len(cands)))
    ax.set_xticklabels([pretty(k) for k in cands], rotation=60,
                       ha="right", fontsize=6.5)
    ax.set_ylabel("production SCF wall time (s)")
    ax.set_xlim(-0.7, len(cands) - 0.3)
    ax.set_yticks([60, 100, 200, 300])
    ax.set_yticklabels(["60", "100", "200", "300"])
    ax.minorticks_off()
    ax.grid(axis="x", visible=False)
    h1 = ax.plot([], [], "o", ms=4, mfc=BLUE, mec="white",
                 label="1T phase (27 atoms)")[0]
    h2 = ax.plot([], [], "o", ms=4, mfc=ORANGE, mec="white",
                 label="2H phase (54 atoms)")[0]
    ax.legend(handles=[h1, h2], loc="upper left", frameon=False)
    fig.tight_layout(pad=0.3)
    fig.savefig(HERE / "fig_fingerprint.pdf")
    plt.close(fig)


# ---------------------------------------------------------------- Fig. 3
def fig_masking():
    d = json.load(open(ROOT / "timing_masking/mask_results.json"))
    live2 = json.load(open(ROOT / "paired_comparison_2/results/"
                                  "wire_attack_results.json"))
    rows = d["sweep"]
    boot = json.load(open(ROOT / "bootstrap_ci/seed_bootstrap.json"))
    bs = {(m["mask"], m["param"]): m["worse_arm"] for m in boot["masking"]}
    fig, axes = plt.subplots(2, 1, figsize=(COL, 3.6), sharex=True)
    specs = [("identity_acc", "identity accuracy", d["identity_limit"]),
             ("membership_auc", "membership AUC", d["membership_auc_limit"])]
    for ax, (key, lab, lim) in zip(axes, specs):
        for mask, col, name, mk in [("quant", BLUE, "quantized returns", "o"),
                                    ("pad", ORANGE, "class padding", "s")]:
            rr = [r for r in rows if r["mask"] == mask]
            x = np.array([100 * r["cost_inflation"] for r in rr])
            bkey = "identity" if key == "identity_acc" else "auc"
            ci = [bs[(mask, r["param"])][bkey] for r in rr]
            lo = np.array([c["lo"] for c in ci])
            hi = np.array([c["hi"] for c in ci])
            y = np.array([r["worst_" + key] for r in rr])
            ax.fill_between(x, lo, hi, color=col, alpha=0.22, lw=0)
            ax.plot(x, y, "-", color=col, marker=mk, ms=3.5, label=name)
        # unmasked point, both arms
        none = [r for r in rows if r["mask"] == "none"][0]
        ax.plot([1.0], [none["worst_" + key]], marker="D", color=INK2,
                ms=4, ls="none", label="no masking (plotted at 1%)")
        # 8x8 campaign, 600-s quantum, billed-cost increase about 4%
        c2 = boot["comparison2"]["CEDT_P4"]["identity" if key == "identity_acc"
                                             else "auc"]
        yv = live2["CEDT_P4"][key]
        ax.errorbar([4.0], [yv], yerr=[[yv - c2["lo"]], [c2["hi"] - yv]],
                    marker="*", color=VIOLET, ms=8, ls="none", elinewidth=1,
                    capsize=2, label="8$\\times$8 cells, 600-s quantum")
        ax.axhline(lim, color=INK, lw=0.8, ls="--")
        ax.text(1.05, lim, " limit", va="bottom", ha="left", fontsize=6.5,
                color=INK)
        ax.set_ylabel(lab)
        ax.set_xscale("log")
    axes[0].set_ylim(0, 1.02)
    axes[1].set_ylim(0.45, 1.02)
    axes[1].set_xlabel("added compute time (% of unmasked campaign)")
    axes[1].set_xlim(0.8, 3000)
    axes[1].set_xticks([1, 10, 100, 1000])
    axes[1].set_xticklabels(["1", "10", "100", "1000"])
    axes[0].legend(loc="upper right", frameon=False, fontsize=6.3,
                   handlelength=1.6)
    fig.tight_layout(pad=0.3, h_pad=0.4)
    fig.savefig(HERE / "fig_masking.pdf")
    plt.close(fig)


# ---------------------------------------------------------------- Fig. 4
def fig_policy():
    att = json.load(open(ROOT / "measured_attacks/attack_results.json"))
    dm = json.load(open(ROOT / "decision_maker_leakage/dm_leakage.json"))
    fig, axes = plt.subplots(2, 1, figsize=(COL, 3.7))

    ax = axes[0]
    mechs = [("P2", "P2"), ("P3_eps2", "P3"), ("P3_eps2_rot", "P3 + ID\nrotation"),
             ("P4", "P4")]
    x = np.arange(len(mechs))
    w = 0.36
    for off, pol, col, name in [(-w / 2, "greedy", BLUE, "greedy"),
                                (w / 2, "depth_first", ORANGE, "depth-first")]:
        v = [att[f"{pol}/{m}"]["membership_auc"] for m, _ in mechs]
        ax.bar(x + off, np.array(v) - 0.5, w * 0.92, bottom=0.5, color=col,
               label=name)
    ax.text(3, 0.51, "both 0.50\n(chance)", ha="center", va="bottom",
            fontsize=6.5, color=INK2)
    ax.axhline(0.60, color=INK, lw=0.8, ls="--")
    ax.text(3.55, 0.605, "limit", fontsize=6.5, ha="right", va="bottom")
    ax.set_xticks(x)
    ax.set_xticklabels([m[1] for m in mechs])
    ax.set_ylim(0.45, 0.85)
    ax.set_ylabel("membership AUC\n(executed attack)")
    ax.legend(frameon=False, loc="upper right", ncol=2)
    ax.grid(axis="x", visible=False)
    ax.set_title("(a) same contract, two decision styles", loc="left")

    ax = axes[1]
    pols = ["greedy", "eps_greedy", "thompson", "repeat_prone", "depth_first"]
    plab = ["greedy\n(audit)", "erratic", "Thompson", "repeat-\nprone",
            "depth-\nfirst"]
    x = np.arange(len(pols) + 1)
    for off, cond, col, name in [(-w / 2, "CEDT_P3_eps2", BLUE, "broker, P3"),
                                 (w / 2, "CTDE_P3_eps2", ORANGE,
                                  "shared model, P3")]:
        a = dm["audit"][cond]
        v = [a["single_policy"][p] for p in pols] + [a["policy_robust"]]
        ax.bar(x + off, v, w * 0.92, color=col, label=name)
    ax.set_xticks(x)
    ax.set_xticklabels(plab + ["policy-\nrobust"], fontsize=6.5)
    ax.set_ylabel("P(all six limits hold)")
    ax.set_ylim(0, 0.7)
    ax.legend(frameon=False, loc="upper right", ncol=1)
    ax.grid(axis="x", visible=False)
    ax.set_title("(b) certificate pass rate by audited policy", loc="left")
    fig.tight_layout(pad=0.3, h_pad=0.8)
    fig.savefig(HERE / "fig_policy.pdf")
    plt.close(fig)


# ---------------------------------------------------------------- Fig. 3
def fig_pilot():
    """Configuration pilot: per-job log wall-time residual after removing
    each compound's mean, grouped by execution configuration."""
    import csv
    rows = [r for r in csv.DictReader(
        open(ROOT / "pilot/results/pilot_results.csv")) if r["converged"] == "1"]
    y = np.log([float(r["pw_wall_s"].rstrip("s")) for r in rows])
    cand = np.array([r["cand"] for r in rows])
    res = y.copy()
    for c in set(cand):
        res[cand == c] -= y[cand == c].mean()
    groups = defaultdict(list)
    for r, v in zip(rows, res):
        groups[(int(r["npool"]), int(r["agg"]))].append(v)
    keys = sorted(groups, key=lambda k: np.median(groups[k]))
    lab = {k: f"{k[0]} pool{'s' if k[0] > 1 else ''}" +
           ("\naggressive" if k[1] else "") for k in keys}
    fig, ax = plt.subplots(figsize=(COL, 2.1))
    rng = np.random.default_rng(0)
    for i, k in enumerate(keys):
        v = 100 * (np.exp(np.array(groups[k])) - 1)
        x = i + rng.uniform(-0.18, 0.18, len(v))
        ax.plot(x, v, "o", ms=3.0, mfc=BLUE, mec="white", mew=0.3,
                alpha=0.9, zorder=3)
        ax.plot([i - 0.3, i + 0.3], [np.median(v)] * 2, color=INK, lw=1.2,
                zorder=4)
    ax.axhline(0, color=INK2, lw=0.6)
    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels([lab[k] for k in keys], fontsize=6.5)
    ax.set_ylabel("wall time vs compound\nmean (%)")
    ax.grid(axis="x", visible=False)
    fig.tight_layout(pad=0.3)
    fig.savefig(HERE / "fig_pilot.pdf")
    plt.close(fig)


# ---------------------------------------------------------------- Fig. A1
def fig_8x8():
    """Comparison 2 (8x8 supercells): true F1 wall times of the no-sharing
    arm, with the width of one 600-s quantum drawn for scale."""
    camps = [json.loads(x) for x in
             open(ROOT / "paired_comparison_2/results/campaigns.jsonl")]
    walls = defaultdict(list)
    for c in camps:
        for j in c["jobs"]:
            if (c["arm"] == "DTDE" and j["cls"] == "f1" and j["rc"] == 0
                    and j["converged"]):
                walls[j["candidate"]].append(j["wall_s"] / 3600.0)
    cands = sorted(walls, key=lambda k: np.median(walls[k]))
    fig, ax = plt.subplots(figsize=(COL, 2.5))
    q = 600 / 3600.0
    for i, k in enumerate(cands):
        col = BLUE if k.endswith("1T") else ORANGE
        m = np.median(walls[k])
        ax.add_patch(plt.Rectangle((i - 0.38, m - q / 2), 0.76, q,
                                   color=GRID, lw=0, zorder=1))
        ax.plot([i] * len(walls[k]), walls[k], "o", ms=3.4, mfc=col,
                mec="white", mew=0.4, zorder=3)
    ax.set_xticks(range(len(cands)))
    ax.set_xticklabels([pretty(k) for k in cands], rotation=70,
                       ha="right", fontsize=5.8)
    ax.set_ylabel("coarse SCF wall time (h)")
    ax.set_xlim(-0.7, len(cands) - 0.3)
    ax.set_ylim(0, 9.2)
    ax.grid(axis="x", visible=False)
    h1 = ax.plot([], [], "o", ms=4, mfc=BLUE, mec="white", label="1T")[0]
    h2 = ax.plot([], [], "o", ms=4, mfc=ORANGE, mec="white", label="2H")[0]
    h3 = plt.Rectangle((0, 0), 1, 1, color=GRID, label="one 600-s quantum")
    ax.legend(handles=[h1, h2, h3], loc="upper left", frameon=False)
    fig.tight_layout(pad=0.3)
    fig.savefig(HERE / "fig_8x8.pdf")
    plt.close(fig)


# ---------------------------------------------------------------- Fig. 5
def fig_guest():
    """Comparison 3 (8x8 supercells, guest nodes of two clusters): true F1
    wall times of the no-sharing arm, main campaigns plus the cross-cluster
    repeats, coloured by the cluster the job ran on."""
    lc3 = ROOT / "paired_comparison_3"
    walls = {"granite": defaultdict(list), "notchpeak": defaultdict(list)}
    for root in ("collected_2026-10-14", "site_bridge_2026-10-14"):
        for p in sorted((lc3 / root).glob("DTDE_s*/campaigns.jsonl")):
            c = [json.loads(x) for x in open(p) if x.strip()][-1]
            host = c["node"]["host"]
            cl = "granite" if host.startswith("grn") else "notchpeak"
            for j in c["jobs"]:
                if (j["cls"] == "f1" and j["rc"] == 0
                        and j.get("outcome") == "converged"):
                    walls[cl][j["candidate"]].append(j["wall_s"] / 3600.0)
    allc = set(walls["granite"]) | set(walls["notchpeak"])
    med = {k: np.median(walls["granite"].get(k) or walls["notchpeak"][k])
           for k in allc}
    cands = sorted(allc, key=lambda k: med[k])
    n = {cl: sum(len(v) for v in walls[cl].values()) for cl in walls}
    print(f"[fig5] compounds {len(cands)}; F1 jobs granite {n['granite']}, "
          f"notchpeak {n['notchpeak']}")
    fig, ax = plt.subplots(figsize=(COL, 2.5))
    for cl, col, dx in [("granite", BLUE, -0.15), ("notchpeak", ORANGE, 0.15)]:
        for i, k in enumerate(cands):
            v = walls[cl].get(k, [])
            ax.plot([i + dx] * len(v), v, "o", ms=3.2, mfc=col, mec="white",
                    mew=0.4, zorder=3)
    ax.set_yscale("log")
    ax.set_xticks(range(len(cands)))
    ax.set_xticklabels([pretty(k) for k in cands], rotation=70,
                       ha="right", fontsize=5.8)
    ax.set_ylabel("coarse SCF wall time (h)")
    ax.set_xlim(-0.7, len(cands) - 0.3)
    ax.set_yticks([1, 2, 5, 10])
    ax.set_yticklabels(["1", "2", "5", "10"])
    ax.minorticks_off()
    ax.grid(axis="x", visible=False)
    h1 = ax.plot([], [], "o", ms=4, mfc=BLUE, mec="white",
                 label="first cluster")[0]
    h2 = ax.plot([], [], "o", ms=4, mfc=ORANGE, mec="white",
                 label="second cluster")[0]
    ax.legend(handles=[h1, h2], loc="upper left", frameon=False)
    fig.tight_layout(pad=0.3)
    fig.savefig(HERE / "fig_guest.pdf")
    plt.close(fig)


if __name__ == "__main__":
    fig_fingerprint()
    fig_masking()
    fig_policy()
    fig_8x8()
    fig_pilot()
    fig_guest()

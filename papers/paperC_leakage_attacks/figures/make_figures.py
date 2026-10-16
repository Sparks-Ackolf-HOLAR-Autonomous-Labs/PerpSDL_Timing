#!/usr/bin/env python3
"""Regenerate the timing-leakage article figures from committed data (no new computation).

Sources (paths relative to ):
  pilot/results/pilot_results.csv, pilot/job_matrix.csv
                                                   measured, 81-job pilot
  paired_comparison_1/results/campaigns.jsonl          measured, 3x3 supercells
  paired_comparison_2/results/campaigns.jsonl         measured, 8x8 supercells
  paired_comparison_3/{collected,site_bridge}_2026-10-14/DTDE_s*/campaigns.jsonl
                                                   measured, guest nodes
  paired_comparison_2/results/wire_attack_results.json measured, 8x8 supercells
  bootstrap_ci/seed_bootstrap.json                 seed-bootstrap intervals,
                                                   comparisons 1 and 2, masking
  bootstrap_ci/seed_bootstrap3.json                seed-bootstrap intervals,
                                                   comparison 3
  measured_attacks/pilot_attack_results.json       configuration-rank attack
  timing_masking/mask_results.json                 measured walls, re-attacked
  measured_attacks/attack_results.json             simulated transcripts
  decision_maker_leakage/dm_leakage.json           simulated transcripts

Colour code used in every figure: blue = 1T phase, orange = 2H phase.
Other encodings (arm, cluster, clause, policy) use black, grey, violet and
green or marker shape, never blue or orange.

Figures are written at true print size for the ACM sigconf layout
(column width 3.33 in, text width 7.0 in), with text of 7 pt or larger.
Run: python make_figures.py  (numpy + matplotlib)
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]  # repository root

BLUE, ORANGE = "#2a78d6", "#eb6834"          # 1T, 2H only
AQUA, VIOLET = "#1baf7a", "#4a3aa7"
INK, INK2, GREY, GRID = "#0b0b0b", "#52514e", "#9a9893", "#d9d8d4"

plt.rcParams.update({
    "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
    "font.family": "DejaVu Sans", "axes.edgecolor": INK2,
    "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5,
    "lines.linewidth": 1.2, "savefig.dpi": 300, "pdf.fonttype": 42,
})
COL, TXT = 3.33, 7.0


def pretty(name):
    m, ph = name.split("_")
    return f"{m.replace('2', '$_2$')}-{ph}"


def phase_col(name):
    return BLUE if name.endswith("1T") else ORANGE


def panel(ax, letter, x=-0.02, y=1.02):
    ax.text(x, y, f"({letter})", transform=ax.transAxes, fontsize=8,
            fontweight="bold", ha="right", va="bottom")


def wilson(p, n, z=1.96):
    """Wilson score interval for a proportion p observed in n trials."""
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)


# ------------------------------------------------------------ wall times
def walls_comparison1():
    """Production SCF (F2) wall times, no-sharing arm, 3x3 supercells."""
    camps = [json.loads(x) for x in
             open(ROOT / "paired_comparison_1/results/campaigns.jsonl")]
    walls, allw = defaultdict(list), defaultdict(list)
    for c in camps:
        for j in c["jobs"]:
            if j["arm"] == "DTDE":
                allw[(j["candidate"], j["cls"])].append(j["wall_s"])
                if j["cls"] == "f2":
                    walls[j["candidate"]].append(j["wall_s"])
    rel = [np.std(np.log(v)) for v in allw.values() if len(v) >= 2]
    meds = sorted(np.median(v) for v in walls.values())
    gaps = np.diff(np.log(meds))
    print(f"[walls] comparison 1: repeated (compound, stage) pairs {len(rel)}; "
          f"median log-sd {np.median(rel):.4f}, max {np.max(rel):.4f}; "
          f"F2 medians {meds[0]:.1f}-{meds[-1]:.1f} s; median adjacent "
          f"log gap {np.median(gaps):.4f}")
    return walls


def walls_comparison2():
    """Coarse SCF (F1) wall times, no-sharing arm, 8x8, dedicated node."""
    camps = [json.loads(x) for x in
             open(ROOT / "paired_comparison_2/results/campaigns.jsonl")]
    walls = defaultdict(list)
    for c in camps:
        for j in c["jobs"]:
            if (c["arm"] == "DTDE" and j["cls"] == "f1" and j["rc"] == 0
                    and j["converged"]):
                walls[j["candidate"]].append(j["wall_s"])
    return walls


def walls_comparison3():
    """Coarse SCF (F1) wall times, no-sharing arm, 8x8, shared guest nodes
    of two clusters (main campaigns and cross-cluster repeats)."""
    lc3 = ROOT / "paired_comparison_3"
    walls = {"granite": defaultdict(list), "notchpeak": defaultdict(list)}
    for root in ("collected_2026-10-14", "site_bridge_2026-10-14"):
        for p in sorted((lc3 / root).glob("DTDE_s*/campaigns.jsonl")):
            c = [json.loads(x) for x in open(p) if x.strip()][-1]
            cl = "granite" if c["node"]["host"].startswith("grn") \
                else "notchpeak"
            for j in c["jobs"]:
                if (j["cls"] == "f1" and j["rc"] == 0
                        and j.get("outcome") == "converged"):
                    walls[cl][j["candidate"]].append(j["wall_s"])
    n = {cl: sum(len(v) for v in walls[cl].values()) for cl in walls}
    print(f"[walls] comparison 3: F1 jobs granite {n['granite']}, "
          f"notchpeak {n['notchpeak']}")
    return walls


def spread_and_gaps(walls):
    """Per-compound repeat spread (sd of log time, %) for compounds with at
    least two repeats, and the gap between neighbouring compound medians
    on the sorted axis (log difference, %)."""
    sp = [100 * np.std(np.log(v)) for v in walls.values() if len(v) >= 2]
    meds = np.sort([np.median(v) for v in walls.values() if len(v)])
    gp = 100 * np.diff(np.log(meds))
    return np.array(sp), gp


def fig_walltimes():
    w1, w2, w3 = walls_comparison1(), walls_comparison2(), walls_comparison3()
    allc = set(w3["granite"]) | set(w3["notchpeak"])
    pooled = {k: w3["granite"].get(k, []) + w3["notchpeak"].get(k, [])
              for k in allc}
    cands = sorted(allc, key=lambda k: np.median(pooled[k]))

    fig = plt.figure(figsize=(TXT, 4.75))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.45, 1.0],
                          width_ratios=[1.0, 1.0], hspace=0.62, wspace=0.28,
                          left=0.085, right=0.99, top=0.965, bottom=0.085)
    ax = fig.add_subplot(gs[0, :])
    series = [  # (walls, dx, marker, filled, summary)
        (w1, -0.27, "o", True, False),
        (w2, -0.09, "s", True, False),
        (w3["granite"], 0.09, "D", True, True),
        (w3["notchpeak"], 0.27, "D", False, True)]
    for i, k in enumerate(cands):
        col = phase_col(k)
        for wd, dx, mk, filled, summ in series:
            v = wd.get(k, [])
            if not v:
                continue
            fc = col if filled else "white"
            if summ:
                ax.plot([i + dx] * 2, [min(v), max(v)], color=col, lw=0.9,
                        zorder=2)
                ax.plot(i + dx, np.median(v), mk, ms=3.2, mfc=fc, mec=col,
                        mew=0.8, zorder=3)
            else:
                ax.plot([i + dx] * len(v), v, mk, ms=3.6, mfc=fc,
                        mec="white", mew=0.3, zorder=3)
    ax.set_yscale("log")
    ax.set_ylim(40, 60000)
    ax.set_yticks([60, 600, 3600, 36000])
    ax.set_yticklabels(["1 min", "10 min", "1 h", "10 h"])
    ax.minorticks_off()
    ax.set_ylabel("wall time")
    ax.set_xticks(range(len(cands)))
    ax.set_xticklabels([pretty(k) for k in cands], rotation=60, ha="right",
                       rotation_mode="anchor", fontsize=7)
    ax.set_xlim(-0.6, len(cands) - 0.4)
    ax.grid(axis="x", visible=False)
    hs = [Line2D([], [], ls="none", marker="o", ms=4, mfc=INK2, mec="white",
                 label="3$\\times$3 cells, dedicated node, production SCF"),
          Line2D([], [], ls="none", marker="s", ms=4, mfc=INK2, mec="white",
                 label="8$\\times$8 cells, dedicated node, coarse SCF"),
          Line2D([], [], ls="-", marker="D", ms=3.5, color=INK2, mfc=INK2,
                 lw=0.9, label="8$\\times$8 cells, shared nodes (granite), "
                 "median and range"),
          Line2D([], [], ls="-", marker="D", ms=3.5, color=INK2, mfc="white",
                 lw=0.9, label="8$\\times$8 cells, shared nodes (notchpeak), "
                 "median and range")]
    hp = [Line2D([], [], ls="none", marker="o", ms=4, mfc=BLUE, mec=BLUE,
                 label="1T phase"),
          Line2D([], [], ls="none", marker="o", ms=4, mfc=ORANGE, mec=ORANGE,
                 label="2H phase")]
    l1 = ax.legend(handles=hs, loc="upper left", frameon=False, ncol=1,
                   bbox_to_anchor=(0.0, 0.57), handletextpad=0.4,
                   borderaxespad=0.1, labelspacing=0.3)
    ax.add_artist(l1)
    ax.legend(handles=hp, loc="lower right", frameon=False, ncol=2,
              handletextpad=0.3, borderaxespad=0.1)
    panel(ax, "a", x=-0.01)

    # (b) repeat spread against neighbour spacing, per log
    ax = fig.add_subplot(gs[1, 0])
    logs = [("3$\\times$3\ndedicated", w1),
            ("8$\\times$8\ndedicated", w2),
            ("8$\\times$8 shared\ngranite", w3["granite"]),
            ("8$\\times$8 shared\nnotchpeak", w3["notchpeak"])]
    rng = np.random.default_rng(1)
    for i, (lab, wd) in enumerate(logs):
        sp, gp = spread_and_gaps(wd)
        gp = gp[gp > 0]
        for vals, dx, fc in [(sp, -0.19, INK2), (gp, 0.19, "white")]:
            x = i + dx + rng.uniform(-0.07, 0.07, len(vals))
            ax.plot(x, vals, "o", ms=2.6, mfc=fc, mec=INK2, mew=0.5,
                    alpha=0.9, zorder=3)
            m = np.median(vals)
            ax.plot([i + dx - 0.14, i + dx + 0.14], [m, m], color=INK,
                    lw=1.4, zorder=4)
            # median value printed in a row above the points
            ax.text(i + dx, 250, f"{m:.1f}", ha="center", va="center",
                    fontsize=7, color=INK)
        print(f"[walls] {lab.replace(chr(10), ' ')}: compounds with repeats "
              f"{len(sp)}, median repeat spread {np.median(sp):.2f}%; "
              f"neighbour gaps {len(gp)}, median {np.median(gp):.2f}%")
    ax.set_yscale("log")
    ax.set_ylim(0.01, 40000)
    ax.set_yticks([0.01, 0.1, 1, 10, 100])
    ax.set_yticklabels(["0.01", "0.1", "1", "10", "100"])
    ax.minorticks_off()
    ax.set_ylabel("per cent of wall time")
    ax.set_xticks(range(len(logs)))
    ax.set_xticklabels([lg[0] for lg in logs], fontsize=7)
    ax.set_xlim(-0.5, len(logs) - 0.5)
    ax.grid(axis="x", visible=False)
    ax.legend(handles=[
        Line2D([], [], ls="none", marker="o", ms=3.5, mfc=INK2, mec=INK2,
               label="repeat spread of one compound"),
        Line2D([], [], ls="none", marker="o", ms=3.5, mfc="white", mec=INK2,
               label="gap to neighbouring compound")],
        loc="upper left", frameon=False, ncol=1, borderaxespad=0.1,
        handletextpad=0.3)
    panel(ax, "b")

    # (c) gap between neighbouring medians at 8x8 against a 600-s quantum
    ax = fig.add_subplot(gs[1, 1])
    c2 = sorted(w2, key=lambda k: np.median(w2[k]))
    meds = np.array([np.median(w2[k]) for k in c2])
    gaps = np.diff(meds)
    for r, g in enumerate(gaps):
        a, b = c2[r], c2[r + 1]
        col = phase_col(a) if a[-2:] == b[-2:] else INK2
        mfc = col if a[-2:] == b[-2:] else "white"
        ax.plot(r + 1, g, "o", ms=3.4, mfc=mfc, mec=col, mew=0.8, zorder=3)
    ax.axhline(600, color=INK, lw=0.9, ls="--")
    ax.text(0.6, 640, "one 600-s quantum", fontsize=7, va="bottom",
            ha="left", color=INK)
    ax.set_yscale("log")
    ax.set_ylim(5, 30000)
    ax.set_yticks([10, 100, 1000, 10000])
    ax.set_yticklabels(["10 s", "100 s", "1000 s", "10$^4$ s"])
    ax.minorticks_off()
    ax.set_xlim(0, len(gaps) + 1)
    ax.set_xlabel("pair rank (8$\\times$8 cells, dedicated node)")
    ax.set_ylabel("gap between medians")
    ax.legend(handles=[
        Line2D([], [], ls="none", marker="o", ms=3.5, mfc=BLUE, mec=BLUE,
               label="1T pair"),
        Line2D([], [], ls="none", marker="o", ms=3.5, mfc="white", mec=INK2,
               label="1T to 2H"),
        Line2D([], [], ls="none", marker="o", ms=3.5, mfc=ORANGE, mec=ORANGE,
               label="2H pair")],
        loc="upper left", frameon=False, ncol=3, borderaxespad=0.1,
        handletextpad=0.2, columnspacing=0.8)
    panel(ax, "c")
    t1 = [g for r, g in enumerate(gaps)
          if c2[r].endswith("1T") and c2[r + 1].endswith("1T")]
    t2 = [g for r, g in enumerate(gaps)
          if c2[r].endswith("2H") and c2[r + 1].endswith("2H")]
    print(f"[walls] comparison 2: {len(c2)} compounds; 1T pairs below 600 s: "
          f"{sum(g < 600 for g in t1)}/{len(t1)} (median {np.median(t1):.0f} s);"
          f" 2H pairs above 600 s: {sum(g > 600 for g in t2)}/{len(t2)} "
          f"(median {np.median(t2):.0f} s); medians {meds[0]/3600:.2f}-"
          f"{meds[-1]/3600:.2f} h")
    print(f"[walls] panel (a): {len(cands)} compounds; comparison 1 "
          f"{len(w1)}, comparison 2 {len(w2)}")
    fig.savefig(HERE / "fig_walltimes.pdf")
    plt.close(fig)


# ---------------------------------------------------------- forest plot
def fig_forest():
    """Every executed timing attack on measured logs (Table 3), with its
    95% interval and limit."""
    b1 = json.load(open(ROOT / "bootstrap_ci/seed_bootstrap.json"))
    b3 = json.load(open(ROOT / "bootstrap_ci/seed_bootstrap3.json"))
    pil = json.load(open(ROOT / "measured_attacks/pilot_attack_results.json"))
    a3 = b3["arms"]
    # (label, identity dict, auc dict, identity limit) ; None = header
    rows = [
        ("Dedicated node, 3$\\times$3 cells", None),
        ("no sharing", b1["comparison1"]["DTDE"], 0.087),
        ("broker, every descriptor redacted", b1["comparison1"]["CEDT_P4"],
         0.087),
        ("Dedicated node, 8$\\times$8 cells", None),
        ("no sharing, true times", b1["comparison2"]["DTDE"], 0.0845),
        ("broker, 600-s quantum", b1["comparison2"]["CEDT_P4"], 0.0845),
        ("Shared nodes, 8$\\times$8 cells", None),
        ("no sharing, true times", a3["DTDE"], 0.0845),
        ("broker, proportional mask", a3["CEDT_P4"], 0.0845),
        ("half of jobs via the broker", a3["MIX50_routed"], 0.0845),
        ("shared model, true times", a3["CTDE_P2"], 0.0845),
        ("reference table from other cluster", b3["T1_cross_cluster"],
         0.0845),
        ("Configuration pilot, 81 jobs", None),
        ("configuration visible", "p1_style_config_visible", None),
        ("timing only", "p4_style_timing_only", None),
    ]
    n = len(rows)
    fig, axes = plt.subplots(1, 3, figsize=(TXT, 2.75), sharey=True,
                             gridspec_kw=dict(wspace=0.12))
    fig.subplots_adjust(left=0.305, right=0.985, top=0.93, bottom=0.15)
    ylab = []
    for i, row in enumerate(rows):
        y = n - 1 - i
        ylab.append((y, row[0], row[1] is None))
        if row[1] is None:
            continue
        if isinstance(row[1], str):
            d = pil[row[1]]
            ax = axes[2]
            ax.plot([d["q05"], d["q95"]], [y, y], color=INK, lw=1.2)
            ax.plot(d["mean"], y, "o", ms=4, color=INK, zorder=3)
            continue
        for ax, key in [(axes[0], "identity"), (axes[1], "auc")]:
            d = row[1][key]
            ax.plot([d["lo"], d["hi"]], [y, y], color=INK, lw=1.2)
            ax.plot(d["point"], y, "o", ms=4, color=INK, zorder=3)
        # identity limit as a short segment per row
        axes[0].plot([row[2]] * 2, [y - 0.45, y + 0.45], color=INK2, lw=0.9,
                     ls="--")
    for ax, lim, lab, xl in [
            (axes[1], 0.60, "membership AUC", (0.45, 1.02)),
            (axes[2], 0.20, "rank correlation", (0, 1.02))]:
        ax.axvline(lim, color=INK2, lw=0.9, ls="--")
        ax.axvspan(xl[0], lim, color=GRID, alpha=0.5, lw=0)
        ax.set_xlim(*xl)
        ax.set_xlabel(lab)
    axes[0].set_xlim(0, 1.02)
    axes[0].axvspan(0, 0.086, color=GRID, alpha=0.5, lw=0)
    axes[0].set_xlabel("identity accuracy")
    axes[0].set_yticks([y for y, _, _ in ylab])
    axes[0].set_yticklabels([t for _, t, _ in ylab])
    for tl, (_, _, hdr) in zip(axes[0].get_yticklabels(), ylab):
        if hdr:
            tl.set_fontweight("bold")
            tl.set_color(INK)
    for ax in axes:
        ax.set_ylim(-0.7, n - 0.3)
        ax.grid(axis="y", visible=False)
        ax.tick_params(axis="y", length=0)
    for ax, letter in zip(axes, "abc"):
        panel(ax, letter, x=0.0, y=1.0)
    fig.savefig(HERE / "fig_forest.pdf")
    plt.close(fig)


# ---------------------------------------------------------------- masking
def fig_masking():
    d = json.load(open(ROOT / "timing_masking/mask_results.json"))
    live2 = json.load(open(ROOT / "paired_comparison_2/results/"
                                  "wire_attack_results.json"))
    rows = d["sweep"]
    boot = json.load(open(ROOT / "bootstrap_ci/seed_bootstrap.json"))
    bs = {(m["mask"], m["param"]): m["worse_arm"] for m in boot["masking"]}
    fig, axes = plt.subplots(2, 1, figsize=(COL, 4.3), sharex=True)
    specs = [("identity_acc", "identity accuracy", d["identity_limit"]),
             ("membership_auc", "membership AUC", d["membership_auc_limit"])]
    # clause labels: quantum length in panel (a), padding percentile in
    # panel (b); text positions in data coordinates, joined by thin leaders
    lab_at = {("identity_acc", "quant", 60): ("60 s", (30, 0.62)),
              ("identity_acc", "quant", 300): ("300 s", (95, -0.025)),
              ("identity_acc", "quant", 600): ("600 s", (520, 0.19)),
              ("membership_auc", "pad", 90): ("90th", (40, 0.535)),
              ("membership_auc", "pad", 95): ("95th", (62, 0.468)),
              ("membership_auc", "pad", 99): ("99th", (250, 0.585)),
              ("membership_auc", "pad", 100): ("max", (230, 0.465))}
    for ax, (key, lab, lim) in zip(axes, specs):
        for mask, col, name, mk in [
                ("quant", VIOLET, "quantised returns", "o"),
                ("pad", AQUA, "class padding", "s")]:
            rr = [r for r in rows if r["mask"] == mask]
            x = np.array([100 * r["cost_inflation"] for r in rr])
            bkey = "identity" if key == "identity_acc" else "auc"
            ci = [bs[(mask, r["param"])][bkey] for r in rr]
            lo = np.array([c["lo"] for c in ci])
            hi = np.array([c["hi"] for c in ci])
            y = np.array([r["worst_" + key] for r in rr])
            ax.fill_between(x, lo, hi, color=col, alpha=0.2, lw=0)
            ax.plot(x, y, "-", color=col, marker=mk, ms=3.2, label=name)
            for r, xv, yv in zip(rr, x, y):
                t = lab_at.get((key, mask, r["param"]))
                if t:
                    ax.annotate(t[0], (xv, yv), xytext=t[1], fontsize=7,
                                color=col, ha="center", va="center",
                                arrowprops=dict(arrowstyle="-", color=col,
                                                lw=0.6, shrinkA=1,
                                                shrinkB=2))
        none = [r for r in rows if r["mask"] == "none"][0]
        ax.plot([1.0], [none["worst_" + key]], marker="D", color=INK2,
                ms=4, ls="none", label="no masking")
        c2 = boot["comparison2"]["CEDT_P4"]["identity" if key == "identity_acc"
                                             else "auc"]
        yv = live2["CEDT_P4"][key]
        ax.errorbar([4.0], [yv], yerr=[[yv - c2["lo"]], [c2["hi"] - yv]],
                    marker="*", color=INK, ms=8, ls="none", elinewidth=1,
                    capsize=2, label="8$\\times$8 cells, 600-s quantum")
        ax.axhline(lim, color=INK, lw=0.8, ls="--")
        ax.text(1800, lim, "limit", va="bottom", ha="center", fontsize=7,
                color=INK)
        ax.set_ylabel(lab)
        ax.set_xscale("log")
        # axis break between the unmasked point and the masked clauses
        for xb in (1.32, 1.42):
            ax.plot([xb / 1.04, xb * 1.04], [-0.02, 0.02],
                    transform=ax.get_xaxis_transform(), color=INK2, lw=0.8,
                    clip_on=False)
    # phase-stratified padding (timing_masking/RESULTS.md and make_figure.py):
    # cost +62.1%, identity at chance within a (class, phase) stratum of
    # about 14 compounds, but the phase is read off the padded duration
    axes[0].plot([62.1], [1 / 14], marker="X", color=INK, ms=5, ls="none")
    axes[0].annotate("padded by class\nand phase:\nphase revealed",
                     (62.1, 1 / 14), xytext=(30, 0.21), fontsize=7,
                     color=INK, ha="right", va="center",
                     arrowprops=dict(arrowstyle="-", color=INK2, lw=0.6))
    axes[0].set_ylim(-0.07, 1.02)
    axes[0].set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    axes[1].set_ylim(0.45, 1.02)
    axes[1].set_xlabel("added compute time (% of unmasked campaign)")
    axes[1].set_xlim(0.8, 3500)
    axes[1].set_xticks([1, 10, 100, 1000])
    axes[1].set_xticklabels(["none", "10", "100", "1000"])
    axes[1].minorticks_off()
    axes[0].legend(loc="upper right", frameon=False, fontsize=7,
                   handlelength=1.6, borderaxespad=0.1)
    panel(axes[0], "a", x=-0.13)
    panel(axes[1], "b", x=-0.13)
    fig.tight_layout(pad=0.3, h_pad=0.6)
    fig.savefig(HERE / "fig_masking.pdf")
    plt.close(fig)


# ----------------------------------------------------------------- policy
def fig_policy():
    att = json.load(open(ROOT / "measured_attacks/attack_results.json"))
    dm = json.load(open(ROOT / "decision_maker_leakage/dm_leakage.json"))
    nw = dm["worlds"]
    fig, axes = plt.subplots(2, 1, figsize=(COL, 3.9),
                             gridspec_kw=dict(height_ratios=[1.0, 1.35]))

    ax = axes[0]
    mechs = [("P2", "coarse bins"), ("P3_eps2", "noisy aggregates"),
             ("P3_eps2_rot", "noisy aggregates,\nIDs rotated"),
             ("P4", "class only")]
    ys = np.arange(len(mechs))[::-1]
    for pol, mfc, dy, name in [("greedy", INK2, 0.12, "greedy"),
                               ("depth_first", "white", -0.12,
                                "depth-first")]:
        v = [att[f"{pol}/{m}"]["membership_auc"] for m, _ in mechs]
        ax.plot(v, ys + dy, "o", ms=4.2, mfc=mfc, mec=INK, mew=0.9,
                ls="none", label=name)
    ax.axvline(0.60, color=INK, lw=0.8, ls="--")
    ax.text(0.605, ys[0] + 0.45, "limit", fontsize=7, ha="left",
            va="bottom")
    ax.set_yticks(ys)
    ax.set_yticklabels([m[1] for m in mechs])
    ax.set_xlim(0.48, 1.0)
    ax.set_ylim(-0.6, len(mechs) - 0.2)
    ax.set_xlabel("membership AUC (0.5 = chance)")
    ax.legend(frameon=False, loc="lower right", ncol=1, borderaxespad=0.1,
              handletextpad=0.3)
    ax.grid(axis="y", visible=False)
    panel(ax, "a", x=-0.28)

    ax = axes[1]
    pols = ["greedy", "eps_greedy", "thompson", "repeat_prone", "depth_first"]
    plab = ["greedy (audit)", "erratic", "Thompson", "repeat-prone",
            "depth-first", "worst of all five"]
    ys = np.arange(len(pols) + 1)[::-1]
    for cond, mfc, dy, name in [("CEDT_P3_eps2", INK2, 0.13, "broker"),
                                ("CTDE_P3_eps2", "white", -0.13,
                                 "shared model")]:
        a = dm["audit"][cond]
        v = [a["single_policy"][p] for p in pols] + [a["policy_robust"]]
        for y, p in zip(ys + dy, v):
            lo, hi = wilson(p, nw)
            ax.plot([lo, hi], [y, y], color=INK, lw=0.9, zorder=2)
        ax.plot(v, ys + dy, "o", ms=4.2, mfc=mfc, mec=INK, mew=0.9,
                ls="none", label=name, zorder=3)
    ax.set_yticks(ys)
    ax.set_yticklabels(plab)
    ax.set_xlim(0, 0.8)
    ax.set_ylim(-0.6, len(pols) + 0.5)
    ax.set_xlabel("fraction of worlds with all six limits met")
    ax.legend(frameon=False, loc="lower right", ncol=1, borderaxespad=0.1,
              handletextpad=0.3)
    ax.grid(axis="y", visible=False)
    panel(ax, "b", x=-0.28)
    fig.tight_layout(pad=0.3, h_pad=0.9)
    fig.savefig(HERE / "fig_policy.pdf")
    plt.close(fig)


# ------------------------------------------------------------------ pilot
def fig_pilot():
    """Configuration pilot: per-job wall time relative to the compound mean
    (log scale, compound fixed effect removed), grouped by the pool count
    and SCF convergence setting the centre chose."""
    rows = [r for r in csv.DictReader(
        open(ROOT / "pilot/results/pilot_results.csv")) if r["converged"] == "1"]
    jm = {r["job_id"]: r for r in csv.DictReader(
        open(ROOT / "pilot/job_matrix.csv"))}
    y = np.log([float(r["pw_wall_s"].rstrip("s")) for r in rows])
    cand = np.array([r["cand"] for r in rows])
    res = y.copy()
    for c in set(cand):
        res[cand == c] -= y[cand == c].mean()
    groups = defaultdict(list)
    for r, v in zip(rows, res):
        ranks = 16 * int(jm[r["pilot_id"]]["nodes"])
        groups[(int(r["npool"]), int(r["agg"]))].append((r["cand"], v, ranks))
    keys = sorted(groups, key=lambda k: np.median([g[1] for g in groups[k]]))
    fig, ax = plt.subplots(figsize=(COL, 2.55))
    style = {"TiS2_1T": (BLUE, "^", -0.22), "MoSe2_2H": (ORANGE, "o", 0.0),
             "WTe2_2H": (ORANGE, "s", 0.22)}
    labels = []
    for i, k in enumerate(keys):
        allv = 100 * (np.exp(np.array([g[1] for g in groups[k]])) - 1)
        for c, (col, mk, dx) in style.items():
            v = [100 * (np.exp(g[1]) - 1) for g in groups[k] if g[0] == c]
            ax.plot([i + dx] * len(v), v, mk, ms=3.2, mfc=col, mec="white",
                    mew=0.3, zorder=3)
        ax.plot([i - 0.34, i + 0.34], [np.median(allv)] * 2, color=INK,
                lw=1.3, zorder=4)
        rk = sorted({g[2] for g in groups[k]})
        lab = f"{k[0]} pool{'s' if k[0] > 1 else ''}"
        lab += ",\nloose SCF" if k[1] else ""
        labels.append(f"{lab}\nn = {len(allv)}")
        print(f"[pilot] {lab.replace(chr(10), ' ')}: n {len(allv)}, ranks {rk}, "
              f"median {np.median(allv):+.1f}%, range {allv.min():+.0f} to "
              f"{allv.max():+.0f}%")
    ax.axhline(0, color=INK2, lw=0.6)
    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylabel("wall time relative to\ncompound mean (%)")
    ax.set_xlim(-0.5, len(keys) - 0.5)
    ax.grid(axis="x", visible=False)
    ax.legend(handles=[Line2D([], [], ls="none", marker=mk, ms=4, mfc=col,
                              mec=col, label=pretty(c))
                       for c, (col, mk, _) in style.items()],
              loc="upper left", frameon=False, ncol=3, handletextpad=0.2,
              columnspacing=0.8, borderaxespad=0.1)
    ax.set_ylim(-55, 85)
    fig.tight_layout(pad=0.3)
    fig.savefig(HERE / "fig_pilot.pdf")
    plt.close(fig)


if __name__ == "__main__":
    fig_walltimes()
    fig_forest()
    fig_pilot()
    fig_masking()
    fig_policy()

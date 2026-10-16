#!/usr/bin/env python3
"""Renegotiated R reservation gain.

This script re-runs the win-win grid with g_R relaxed from a
20% to a 10% reduction in simulated node-hours to the first qualifying
candidate (the +1-qualifier alternative, the validity guard, and every
other threshold stay frozen). Because raw_results.json.gz stores the
per-world paired campaign means for every condition, this is a pure
re-analysis of the existing 1,000-world dataset — no re-simulation, and
the g_R factor is also swept over {5,10,15,20}% as sensitivity.

Writes results/gR_renegotiation.json and results/gR_renegotiation.png.
"""
import gzip
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
RES = HERE / "results"

C_BLUE, C_ORANGE, C_AQUA, C_YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, INK2, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"

REDUCTIONS = [0.05, 0.10, 0.15, 0.20]   # g_R candidate values; 0.20 = frozen
PRIMARY = 0.10                           # renegotiated primary value
CARDS = ["base", "strong_coupling", "adversarial"]


def load():
    with gzip.open(RES / "raw_results.json.gz", "rt") as fh:
        recs = json.load(fh)
    for r in recs:
        r["chunk"] = "sweep" if r["world"] >= 100000 else "main"
    return recs


def regrade(recs, reduction):
    """Recompute r_gain / win_win at a g_R node-hour reduction threshold."""
    factor = 1.0 - reduction
    by_world = defaultdict(dict)
    for r in recs:
        by_world[(r["card"], r["world"])][r["condition"]] = r
    rows = []
    for key, conds in by_world.items():
        base = conds.get("DTDE_P4")
        if base is None:
            continue
        for cond, r in conds.items():
            gainA = (r["mean_nh_first"] <= factor * base["mean_nh_first"]
                     and r["found_rate"] >= base["found_rate"] - 1e-9)
            gainB = r["mean_qual"] >= base["mean_qual"] + 1.0
            ok_val = r["validity"] >= base["validity"] - 0.01
            r_gain = float((gainA or gainB) and ok_val)
            rows.append(dict(card=r["card"], world=r["world"], chunk=r["chunk"],
                             condition=cond, r_gain=r_gain,
                             h_gain=r["h_gain"], leak_ok=r["leak_ok"],
                             win_win=float(r_gain and r["h_gain"]
                                           and r["leak_ok"])))
    return rows


def cond_probs(rows, cond):
    rs = [r for r in rows if r["condition"] == cond]
    if not rs:
        return None
    d = {k: float(np.mean([r[k] for r in rs]))
         for k in ("win_win", "r_gain", "h_gain", "leak_ok")}
    d["n_worlds"] = len(rs)
    d["per_card"] = {c: float(np.mean([r["win_win"] for r in rs
                                       if r["card"] == c]) if any(
        r["card"] == c for r in rs) else np.nan) for c in CARDS}
    d["worst_card"] = float(min(v for v in d["per_card"].values()
                                if not np.isnan(v)))
    return d


def main():
    recs = load()
    main_recs = [r for r in recs if r["chunk"] == "main"]
    sweep_recs = [r for r in recs if r["chunk"] == "sweep"]
    main_conds = sorted({r["condition"] for r in main_recs})
    sweep_conds = sorted({r["condition"] for r in sweep_recs}
                         - {"DTDE_P4"})

    out = {"primary_g_R": PRIMARY, "frozen_g_R": 0.20, "sweep": {}}
    for red in REDUCTIONS:
        rows_m = regrade(main_recs, red)
        rows_s = regrade(sweep_recs, red)
        entry = {}
        for c in main_conds:
            entry[c] = cond_probs(rows_m, c)
        for c in sweep_conds:
            entry[c] = cond_probs(rows_s, c)
        out["sweep"][f"{int(red*100)}pct"] = entry

    prim = out["sweep"][f"{int(PRIMARY*100)}pct"]
    ranked = sorted(((c, v["win_win"]) for c, v in prim.items()
                     if v and c not in ("CTCE_P0", "DTDE_P4")),
                    key=lambda t: -t[1])
    out["primary_ranking"] = ranked[:6]
    out["verdict_thresholds"] = {
        "0.80": [c for c, v in ranked if v >= 0.80],
        "0.90": [c for c, v in ranked if v >= 0.90]}
    with open(RES / "gR_renegotiation.json", "w") as fh:
        json.dump(out, fh, indent=2)

    # ---- figure: win-win vs g_R for the leading contracts ----------------
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "axes.edgecolor": INK2, "axes.labelcolor": INK, "text.color": INK,
        "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False,
        "axes.spines.right": False, "font.size": 9, "axes.grid": True,
        "grid.color": "#e8e7e3", "grid.linewidth": 0.6})
    show = ["CEDT_P4", "CEDT_P3", "CEDT_P3_eps2", "CEDT_P3_eps1",
            "CTDE_P4", "CTDE_P3", "CTCE_P0"]
    cols = {"CEDT_P4": C_AQUA, "CEDT_P3": "#0e7a54",
            "CEDT_P3_eps2": "#79c9ab", "CEDT_P3_eps1": "#b5e0d0",
            "CTDE_P4": C_ORANGE, "CTDE_P3": "#f2a181", "CTCE_P0": C_BLUE}
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.9), sharex=True)
    xs = [int(r * 100) for r in REDUCTIONS]
    for ax, key, title in [(axes[0], "win_win", "P(win-win)"),
                           (axes[1], "r_gain", "P(R reservation gain)")]:
        for c in show:
            ys = [out["sweep"][f"{x}pct"].get(c, {}).get(key) for x in xs]
            if any(y is None for y in ys):
                continue
            ax.plot(xs, ys, "-o", color=cols[c], lw=2, ms=4.5, label=c)
        ax.set_xlabel("g_R: required node-hour reduction to first "
                      "qualifier (%)")
        ax.set_xticks(xs)
        ax.set_title(title, loc="left")
        ax.invert_xaxis()   # easier requirement to the right? keep left→right lax→strict
    axes[0].axhline(0.90, color=C_YELLOW, lw=1.2, ls="--")
    axes[0].text(19.5, 0.905, "preregistered 0.90", color=INK2, fontsize=8)
    axes[0].set_ylabel("probability over prior worlds")
    axes[0].legend(frameon=False, fontsize=7.5, ncol=2)
    fig.suptitle("Renegotiated R reservation gain: win-win vs g_R "
                 "(all other thresholds frozen; simulated units)",
                 fontsize=9, x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(RES / "gR_renegotiation.png", dpi=160)

    print("g_R =", PRIMARY, "ranking:", ranked[:5])
    print("crosses 0.80:", out["verdict_thresholds"]["0.80"])
    print("crosses 0.90:", out["verdict_thresholds"]["0.90"])


if __name__ == "__main__":
    main()

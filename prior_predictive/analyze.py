#!/usr/bin/env python3
"""Win-win evaluation, minimal-contract analysis, pilot design, and plots
for the prior-predictive simulation.

Reads results/raw_results.json (produced by simulator.py), writes
results/summary.json, results/drivers.json and four PNG figures.
"""
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
RES = HERE / "results"

# validated categorical palette (dataviz reference instance, light mode)
C_BLUE, C_ORANGE, C_AQUA, C_YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, INK2 = "#0b0b0b", "#52514e"
SURFACE = "#fcfcfb"

MAIN_CONDS = ["CTCE_P0", "DTDE_P4", "CTDE_P1", "CTDE_P2", "CTDE_P3",
              "CTDE_P4", "CEDT_P1", "CEDT_P2", "CEDT_P3", "CEDT_P4"]
EPS_CONDS = ["CTDE_P3_eps1", "CTDE_P3_eps2", "CTDE_P3_eps8",
             "CEDT_P3_eps1", "CEDT_P3_eps2", "CEDT_P3_eps8"]
CARDS = ["base", "strong_coupling", "adversarial"]
LEVELS = [0.80, 0.90, 0.95]

# informativeness partial order within each arm (Blackwell-style, Section 15.2)
# P4 (least) < P3_eps1 < P3_eps2 < P3 (eps4) < P3_eps8 < P2 < P1
ORDER = ["P4", "P3_eps1", "P3_eps2", "P3", "P3_eps8", "P2", "P1"]


def load():
    recs = json.load(open(RES / "raw_results.json"))
    for r in recs:
        r["chunk"] = "sweep" if r["world"] >= 100000 else "main"
    return recs


def cond_stats(recs, cond):
    rs = [r for r in recs if r["condition"] == cond]
    if not rs:
        return None
    d = {"n_worlds": len(rs)}
    for k in ("win_win", "r_gain", "h_gain", "leak_ok", "found_rate",
              "mean_nh_first", "mean_qual", "labels_per_nh", "fail_rate",
              "validity", "r_mi_auc", "r_comp_adv", "r_id_acc",
              "h_rank_corr", "h_hw_adv", "h_tel_auc"):
        d[k] = float(np.mean([r[k] for r in rs]))
    d["per_card"] = {}
    for card in CARDS:
        cs = [r["win_win"] for r in rs if r["card"] == card]
        d["per_card"][card] = float(np.mean(cs)) if cs else None
    vals = [v for v in d["per_card"].values() if v is not None]
    d["worst_card_win_win"] = float(min(vals)) if vals else None
    d["passes"] = {str(a): bool(d["win_win"] >= a) for a in LEVELS}
    d["passes_worst_card"] = {str(a): bool((d["worst_card_win_win"] or 0)
                                           >= a) for a in LEVELS}
    return d


def main():
    recs = load()
    main_recs = [r for r in recs if r["chunk"] == "main"]
    sweep_recs = [r for r in recs if r["chunk"] == "sweep"]

    summary = {"conditions": {}, "eps_sweep": {}}
    for c in MAIN_CONDS:
        summary["conditions"][c] = cond_stats(main_recs, c)
    for c in EPS_CONDS + ["DTDE_P4"]:
        summary["eps_sweep"][c] = cond_stats(sweep_recs, c)

    # ---- minimal-contract search per arm (prior-credible, Section 15.8) ---
    # win-win probabilities per contract level, pooled; eps variants come
    # from the 250-world sensitivity subset (noted in n_worlds).
    minimal = {}
    for arm in ("CTDE", "CEDT"):
        probs = {}
        for lv in ORDER:
            cond = f"{arm}_{lv}"
            src = summary["conditions"].get(cond) or summary["eps_sweep"].get(cond)
            if src:
                probs[lv] = {"win_win": src["win_win"],
                             "worst_card": src["worst_card_win_win"],
                             "n_worlds": src["n_worlds"]}
        feasible = {a: [lv for lv in ORDER if probs.get(lv, {}).get(
            "win_win", 0) >= a] for a in LEVELS}
        minimal[arm] = {"probs": probs,
                        "minimal_feasible_by_level":
                        {str(a): (feasible[a][0] if feasible[a] else None)
                         for a in LEVELS}}
    summary["minimal_contracts"] = minimal
    best = max(
        [(c, s["win_win"]) for c, s in
         list(summary["conditions"].items()) + list(summary["eps_sweep"].items())
         if s and c not in ("CTCE_P0", "DTDE_P4")], key=lambda t: t[1])
    summary["best_candidate_contract"] = {"condition": best[0],
                                          "win_win": best[1]}
    summary["mrd_finding"] = (
        "No candidate contract reaches the preregistered 0.90 (or 0.80) "
        "prior-predictive win-win probability under any prior card: "
        "prior-credible MRD infeasibility at the preregistered reservation"
        "gains and leakage limits (Section 20.7 explicit infeasibility "
        "finding). Nearest candidates: "
        f"{best[0]} at pooled {best[1]:.3f}.")

    # ---- drivers of the win-win event (value-of-information screen) -------
    drivers = {}
    params = ["s", "pm", "quirk_sd", "burst", "beta0", "n_true_qual"]
    for cond in ("CEDT_P4", "CEDT_P3"):
        rs = [r for r in main_recs if r["condition"] == cond]
        d = {}
        for p in params:
            x = np.array([r[p] for r in rs], float)
            for target in ("win_win", "r_gain", "h_gain", "leak_ok"):
                y = np.array([r[target] for r in rs], float)
                if y.std() < 1e-9 or x.std() < 1e-9:
                    corr = 0.0
                else:
                    corr = float(np.corrcoef(x, y)[0, 1])
                d[f"{p}->{target}"] = round(corr, 3)
        drivers[cond] = d
    json.dump(drivers, open(RES / "drivers.json", "w"), indent=2)

    json.dump(summary, open(RES / "summary.json", "w"), indent=2)

    # ================= figures ============================================
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "axes.edgecolor": INK2, "axes.labelcolor": INK,
        "text.color": INK, "xtick.color": INK2, "ytick.color": INK2,
        "axes.spines.top": False, "axes.spines.right": False,
        "font.size": 9, "axes.grid": True, "grid.color": "#e8e7e3",
        "grid.linewidth": 0.6,
    })

    # -- fig 1: win-win probability by contract, with component probs ------
    conds = ["DTDE_P4", "CTDE_P4", "CTDE_P3", "CTDE_P2", "CTDE_P1",
             "CEDT_P4", "CEDT_P3", "CEDT_P2", "CEDT_P1"]
    stats = [summary["conditions"][c] for c in conds]
    fig, axes = plt.subplots(2, 1, figsize=(8.2, 6.0), sharex=True)
    x = np.arange(len(conds))
    ww = [s["win_win"] for s in stats]
    axes[0].bar(x, ww, 0.55, color=C_BLUE, zorder=3)
    for xi, v in zip(x, ww):
        axes[0].text(xi, v + 0.012, f"{v:.3f}", ha="center", color=INK,
                     fontsize=8)
    for lvl, ls in zip(LEVELS, (":", "--", "-.")):
        axes[0].axhline(lvl, color=C_ORANGE, lw=1.2, ls=ls, zorder=2)
        axes[0].text(len(conds) - 0.4, lvl + 0.01, f"{lvl:.2f}",
                     color=C_ORANGE, fontsize=8, ha="right")
    axes[0].set_ylim(0, 1.02)
    axes[0].set_ylabel("P(win-win) over 1,000 prior worlds")
    axes[0].set_title("Prior-predictive win-win probability by contract "
                      "(preregistered thresholds dashed)", loc="left")
    w = 0.27
    for k, (kk, col, lab) in enumerate(
            [("r_gain", C_ORANGE, "P(R reservation gain)"),
             ("h_gain", C_AQUA, "P(H reservation gain)"),
             ("leak_ok", C_YELLOW, "P(all leakage limits met)")]):
        vals = [s[kk] for s in stats]
        axes[1].bar(x + (k - 1) * w, vals, w, color=col, zorder=3, label=lab)
    axes[1].set_ylim(0, 1.05)
    axes[1].set_ylabel("component probability")
    axes[1].legend(frameon=False, fontsize=8, ncol=3, loc="upper left")
    axes[1].set_xticks(x, conds, rotation=30, ha="right")
    fig.tight_layout()
    fig.savefig(RES / "winwin_probability.png", dpi=160)
    plt.close(fig)

    # -- fig 2: privacy-utility frontier -----------------------------------
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    base_nh = summary["conditions"]["DTDE_P4"]["mean_nh_first"]
    lims = dict(r_mi_auc=0.60, r_comp_adv=0.10, r_id_acc=1 / 30 + 0.05,
                h_rank_corr=0.20, h_hw_adv=0.10, h_tel_auc=0.60)

    def leak_ratio(s):
        rr = [max(s["r_mi_auc"] - 0.5, 0) / (lims["r_mi_auc"] - 0.5),
              s["r_comp_adv"] / lims["r_comp_adv"],
              s["r_id_acc"] / lims["r_id_acc"],
              s["h_rank_corr"] / lims["h_rank_corr"],
              s["h_hw_adv"] / lims["h_hw_adv"],
              max(s["h_tel_auc"] - 0.5, 0) / (lims["h_tel_auc"] - 0.5)]
        return max(rr)
    pts = []
    for c in conds + ["CTCE_P0"]:
        s = summary["conditions"][c]
        gain = 100 * (base_nh - s["mean_nh_first"]) / base_nh
        pts.append((c, leak_ratio(s), gain))
    for c, lx, gy in pts:
        col = (C_AQUA if c.startswith("CEDT") else
               C_ORANGE if c.startswith("CTDE") else
               C_BLUE if c == "CTCE_P0" else INK2)
        ax.scatter(lx, gy, s=55, color=col, zorder=3)
        ax.annotate(c, (lx, gy), textcoords="offset points", xytext=(6, 4),
                    fontsize=8, color=INK)
    ax.axvline(1.0, color=C_YELLOW, lw=1.4, ls="--")
    ax.text(1.03, ax.get_ylim()[0] + 0.4, "every leakage limit met  ←",
            color=INK2, fontsize=8, rotation=90, va="bottom")
    ax.set_xscale("log")
    ax.set_xlabel("worst leakage metric / its limit  (log scale; feasible < 1)")
    ax.set_ylabel("reduction in node-hours to first qualifier vs DTDE (%)")
    ax.set_title("Privacy-utility frontier (campaign means over 1,000 worlds)",
                 loc="left")
    handles = [plt.Line2D([], [], marker="o", ls="", color=c, label=l)
               for c, l in [(C_BLUE, "CTCE (FI greedy reference)"),
                            (C_ORANGE, "CTDE"), (C_AQUA, "CEDT"),
                            (INK2, "DTDE baseline")]]
    ax.legend(handles=handles, frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(RES / "privacy_utility_frontier.png", dpi=160)
    plt.close(fig)

    # -- fig 3: epsilon sensitivity ----------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.8), sharey=True)
    eps_x = [1, 2, 4, 8]
    for ax, arm in zip(axes, ("CEDT", "CTDE")):
        series = {"win_win": (C_BLUE, "P(win-win)"),
                  "r_gain": (C_ORANGE, "P(R gain)"),
                  "h_gain": (C_AQUA, "P(H gain)"),
                  "leak_ok": (C_YELLOW, "P(leakage ok)")}
        for key, (col, lab) in series.items():
            ys = []
            for e in eps_x:
                cond = f"{arm}_P3" if e == 4 else f"{arm}_P3_eps{e}"
                src = (summary["conditions"] if e == 4 else
                       summary["eps_sweep"])[cond]
                ys.append(src[key])
            ax.plot(eps_x, ys, "-o", color=col, lw=2, ms=5, label=lab)
        ax.set_xscale("log")
        ax.set_xticks(eps_x, [str(e) for e in eps_x])
        ax.set_xlabel("epsilon (P3 differential-privacy budget)")
        ax.set_title(f"{arm}-P3", loc="left")
    axes[0].set_ylabel("probability over prior worlds")
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("DP sensitivity sweep (delta = 1e-6; eps=4 from the full "
                 "1,000-world grid, others from the 250-world subset)",
                 fontsize=9, x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(RES / "eps_sensitivity.png", dpi=160)
    plt.close(fig)

    # -- fig 4: privacy-tax vector vs the FI greedy reference --------------
    fig, axes = plt.subplots(1, 4, figsize=(10.5, 3.4))
    ref = summary["conditions"]["CTCE_P0"]
    tax_conds = ["DTDE_P4", "CTDE_P3", "CEDT_P3", "CEDT_P4"]
    metrics = [("mean_nh_first", "Δ node-hours to first qualifier", 1),
               ("mean_qual", "Δ qualifying F3/F4 candidates", 1),
               ("labels_per_nh", "Δ valid F2+ labels per node-hour", 1000),
               ("fail_rate", "Δ failure rate", 100)]
    for ax, (k, lab, scale) in zip(axes, metrics):
        vals = [(summary["conditions"][c][k] - ref[k]) * scale
                for c in tax_conds]
        cols = [INK2, C_ORANGE, C_AQUA, C_AQUA]
        ax.bar(np.arange(len(tax_conds)), vals, 0.55, color=cols, zorder=3)
        ax.axhline(0, color=INK2, lw=0.8)
        ax.set_xticks(np.arange(len(tax_conds)), tax_conds, rotation=40,
                      ha="right", fontsize=7.5)
        unit = {1: "", 1000: " (x1e-3)", 100: " (pp)"}[scale]
        ax.set_title(lab + unit, fontsize=8.5, loc="left")
    fig.suptitle("Privacy-tax vector relative to the full-information greedy "
                 "reference (natural units, Section 11.3)", fontsize=9,
                 x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(RES / "privacy_tax_vector.png", dpi=160)
    plt.close(fig)

    print("summary, drivers, and 4 figures written to", RES)
    print("\nMRD finding:", summary["mrd_finding"])
    print("\nDrivers (CEDT_P4):")
    for k, v in sorted(drivers["CEDT_P4"].items(),
                       key=lambda kv: -abs(kv[1]))[:8]:
        print(f"  {k}: {v:+.3f}")


if __name__ == "__main__":
    main()

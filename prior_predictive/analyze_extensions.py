#!/usr/bin/env python3
"""Analysis of the extension grid (extensions.py): education axis Q0-Q3
and the Section 13.2 ablations. Writes results/ext_summary.json,
results/fig_education.png, results/fig_ablations.png.

kappa_S (minimum student competency) and b_E (educator budget cap) were
not fixed by the study design, so both are swept: competency is reported
as P(K_S >= kappa_S) over prior worlds for a kappa_S grid, with educator
effort listed so any cap can be applied by the reader.
"""
import gzip
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
RES = HERE / "results"
C_BLUE, C_ORANGE, C_AQUA, C_YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, INK2, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"

EDU_CONDS = ["EDU_Q0", "EDU_Q1", "EDU_Q2_h0", "EDU_Q2_h2", "EDU_Q2_h8",
             "EDU_Q3"]
KAPPA_GRID = [0.60, 0.70, 0.80, 0.90, 0.95, 0.99]
CUR_LIMITS = dict(rank=0.20, hw=0.10)   # original bilateral H limits (4.7)


def load(name):
    with gzip.open(RES / name, "rt") as fh:
        return json.load(fh)


def by_cond(recs):
    d = {}
    for r in recs:
        d.setdefault(r["condition"], []).append(r)
    return d


def arr(rs, k, default=None):
    return np.array([r.get(k, default) for r in rs], float)


def main():
    recs = load("ext_raw.json.gz")
    bc = by_cond(recs)
    summary = {}

    # ================= education axis =====================================
    edu = {}
    for c in EDU_CONDS:
        rs = bc[c]
        ks = arr(rs, "labels_per_nh_ratio")          # K_S per world
        d = dict(n_worlds=len(rs),
                 K_S_mean=float(ks.mean()),
                 K_S_q10=float(np.quantile(ks, 0.10)),
                 K_S_q90=float(np.quantile(ks, 0.90)),
                 fail_rate=float(arr(rs, "fail_rate").mean()),
                 memfail_p95=float(arr(rs, "memfail_p95").mean()),
                 found_ratio=float(arr(rs, "found_ratio").mean()),
                 educator_effort=float(arr(rs, "educator_effort", 0).mean()),
                 cur_rank_corr=float(arr(rs, "cur_rank_corr", 0).mean()),
                 cur_hw_adv=float(arr(rs, "cur_hw_adv", 0).mean()))
        d["curriculum_leak_ok"] = bool(
            d["cur_rank_corr"] <= CUR_LIMITS["rank"]
            and d["cur_hw_adv"] <= CUR_LIMITS["hw"])
        if "cur_rank_corr_if_released" in rs[0]:
            d["cur_rank_corr_if_released"] = float(
                arr(rs, "cur_rank_corr_if_released").mean())
            d["cur_hw_adv_if_released"] = float(
                arr(rs, "cur_hw_adv_if_released").mean())
        d["P_KS_ge_kappa"] = {str(k): float((ks >= k).mean())
                              for k in KAPPA_GRID}
        edu[c] = d
    # minimal Q per (kappa_S, b_E): cheapest curriculum with
    # P(K_S >= kappa_S) >= 0.9, curriculum leakage within limits, and
    # educator effort <= b_E
    minimal_q = {}
    releasable = [c for c in EDU_CONDS if c != "EDU_Q3"]  # Q3 = oracle
    # ceiling; its materials are not automatically releasable (spec 4.5/8)
    for k in KAPPA_GRID:
        row = {}
        for b_E in (0, 6, 10, 12, 16, 20, 99):
            ok = [c for c in releasable
                  if edu[c]["P_KS_ge_kappa"][str(k)] >= 0.90
                  and edu[c]["curriculum_leak_ok"]
                  and edu[c]["educator_effort"] <= b_E]
            row[str(b_E)] = min(ok, key=lambda c: edu[c]["educator_effort"]) \
                if ok else None
        minimal_q[str(k)] = row
    summary["education"] = edu
    summary["minimal_curriculum_by_kappa_and_budget"] = minimal_q

    # ================= ablation 13.2-2: score granularity =================
    gran = {}
    for c in ("CEDT_P2x", "CEDT_RANK", "CEDT_BIT", "CEDT_P4x"):
        rs = bc[c]
        gran[c] = dict(
            labels_ratio=float(arr(rs, "labels_per_nh_ratio").mean()),
            nh_first=float(arr(rs, "mean_nh_first").mean()),
            h_rank_corr=float(arr(rs, "h_rank_corr").mean()),
            win_win=float(arr(rs, "win_win").mean()),
            leak_ok=float(arr(rs, "leak_ok").mean()))
    summary["ablation_2_score_granularity"] = gran

    # ================= ablation 13.2-4: transcript history ================
    hist = {}
    for c in ("CEDT_P2x", "CEDT_P3x", "CEDT_P4x", "CTDE_P3x"):
        rs = bc[c]
        cum = arr(rs, "r_mi_auc")
        rec = arr(rs, "r_mi_auc_recent")
        hist[c] = dict(
            mi_auc_cumulative=float(cum.mean()),
            mi_auc_windowed=float(rec.mean()),
            composition_risk=float((cum - rec).mean()),
            frac_breach_only_cumulative=float(
                ((cum > 0.60) & (rec <= 0.60)).mean()))
    summary["ablation_4_transcript_history"] = hist

    # ================= ablation 13.2-7: knob-control swap =================
    swap = {}
    for c in ("CEDT_P2x", "CEDT_P2_RCTL"):
        rs = bc[c]
        swap[c] = dict(
            labels_ratio=float(arr(rs, "labels_per_nh_ratio").mean()),
            fail_rate=float(arr(rs, "fail_rate").mean()),
            memfail_p95=float(arr(rs, "memfail_p95").mean()),
            nh_first=float(arr(rs, "mean_nh_first").mean()),
            win_win=float(arr(rs, "win_win").mean()))
    summary["ablation_7_knob_control_swap"] = swap

    # ================= ablation 13.2-8: contention shift ==================
    shift = {}
    pairs = [("DTDE_P4", "DTDE_SHIFT"), ("CTDE_P3x", None),
             ("CTDE_P2_SHIFT", None), ("CEDT_P4x", "CEDT_P4_SHIFT"),
             ("CEDT_P3x", "CEDT_P3_SHIFT")]
    for c in ("DTDE_SHIFT", "CTDE_P2_SHIFT", "CEDT_P4_SHIFT",
              "CEDT_P3_SHIFT"):
        rs = bc[c]
        shift[c] = dict(
            labels_per_nh=float(arr(rs, "labels_per_nh").mean()),
            fail_rate=float(arr(rs, "fail_rate").mean()),
            win_win_vs_shifted_dtde=float(arr(rs, "win_win").mean()),
            h_gain=float(arr(rs, "h_gain").mean()),
            r_gain=float(arr(rs, "r_gain").mean()))
    for base_c in ("DTDE_P4", "CEDT_P4x", "CEDT_P3x"):
        rs = bc[base_c]
        shift[f"{base_c}_noshift_ref"] = dict(
            labels_per_nh=float(arr(rs, "labels_per_nh").mean()),
            fail_rate=float(arr(rs, "fail_rate").mean()))
    summary["ablation_8_contention_shift"] = shift

    # ====== ablation 13.2-6 (post hoc leakage matching, exploratory) ======
    # from the original main grid: pair CTDE/CEDT conditions with the
    # closest worst-leakage ratio and compare utility at matched leakage.
    try:
        orig = json.load(open(RES / "summary.json"))["conditions"]
        lims = dict(r_mi_auc=0.60, r_comp_adv=0.10, r_id_acc=1 / 30 + 0.05,
                    h_rank_corr=0.20, h_hw_adv=0.10, h_tel_auc=0.60)

        def worst(s):
            return max(max(s["r_mi_auc"] - 0.5, 0) / 0.1,
                       s["r_comp_adv"] / lims["r_comp_adv"],
                       s["r_id_acc"] / lims["r_id_acc"],
                       s["h_rank_corr"] / lims["h_rank_corr"],
                       s["h_hw_adv"] / lims["h_hw_adv"],
                       max(s["h_tel_auc"] - 0.5, 0) / 0.1)
        match = {}
        for ct in ("CTDE_P4", "CTDE_P3", "CTDE_P2"):
            lc = worst(orig[ct])
            best = min(("CEDT_P4", "CEDT_P3", "CEDT_P2"),
                       key=lambda ce: abs(worst(orig[ce]) - lc))
            match[ct] = dict(matched_cedt=best,
                             ctde_leak=round(lc, 3),
                             cedt_leak=round(worst(orig[best]), 3),
                             ctde_labels=orig[ct]["labels_per_nh"],
                             cedt_labels=orig[best]["labels_per_nh"],
                             ctde_nh_first=orig[ct]["mean_nh_first"],
                             cedt_nh_first=orig[best]["mean_nh_first"])
        summary["ablation_6_posthoc_leakage_matching"] = match
    except FileNotFoundError:
        pass

    json.dump(summary, open(RES / "ext_summary.json", "w"), indent=2)

    # ================= figures ============================================
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "axes.edgecolor": INK2, "axes.labelcolor": INK, "text.color": INK,
        "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False,
        "axes.spines.right": False, "font.size": 9, "axes.grid": True,
        "grid.color": "#e8e7e3", "grid.linewidth": 0.6})

    # -- education figure --------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 3.9))
    labels = ["Q0", "Q1", "Q2 h=0", "Q2 h=2", "Q2 h=8", "Q3 (oracle)"]
    x = np.arange(len(EDU_CONDS))
    ks_m = [edu[c]["K_S_mean"] for c in EDU_CONDS]
    lo = [edu[c]["K_S_mean"] - edu[c]["K_S_q10"] for c in EDU_CONDS]
    hi = [edu[c]["K_S_q90"] - edu[c]["K_S_mean"] for c in EDU_CONDS]
    cols = ["#b8b7b3", C_BLUE, C_AQUA, C_AQUA, C_AQUA, C_YELLOW]
    axes[0].bar(x, ks_m, 0.55, color=cols, zorder=3,
                yerr=[lo, hi], ecolor=INK2, capsize=3)
    for xi, c in zip(x, EDU_CONDS):
        axes[0].text(xi, 0.04, f"effort\n{edu[c]['educator_effort']:.1f}",
                     ha="center", fontsize=7, color=INK)
    axes[0].axhline(1.0, color=INK2, lw=1.0, ls="--")
    axes[0].text(-0.4, 1.015, "expert H operator", fontsize=7.5, color=INK2)
    axes[0].set_xticks(x, labels, rotation=20, ha="right")
    axes[0].set_ylabel("student competency K_S\n(valid F2+ labels per "
                       "node-hour vs expert, same worlds)")
    axes[0].set_title("Education ladder (student operates H's configs, "
                      "DTDE regime)", loc="left", fontsize=9)
    for c, col in zip(EDU_CONDS, cols):
        ks = arr(bc[c], "labels_per_nh_ratio")
        kx = np.array(KAPPA_GRID)
        py = [(ks >= k).mean() for k in kx]
        axes[1].plot(kx, py, "-o", color=col, lw=2, ms=4,
                     label=labels[EDU_CONDS.index(c)])
    axes[1].axhline(0.90, color=C_ORANGE, lw=1.2, ls="--")
    axes[1].set_xlabel("kappa_S (minimum acceptable competency)")
    axes[1].set_ylabel("P(K_S >= kappa_S) over prior worlds")
    axes[1].set_title("Competency threshold sweep (kappa_S not frozen "
                      "in advance)", loc="left", fontsize=9)
    axes[1].legend(frameon=False, fontsize=7.5)
    fig.tight_layout()
    fig.savefig(RES / "fig_education.png", dpi=160)
    plt.close(fig)

    # -- ablations figure --------------------------------------------------
    fig, axes = plt.subplots(1, 4, figsize=(12.6, 3.6))
    # 13.2-2
    g_conds = ["CEDT_P2x", "CEDT_RANK", "CEDT_BIT", "CEDT_P4x"]
    g_lab = ["bins\n(P2)", "rank\nonly", "one\nbit", "none\n(P4)"]
    ax = axes[0]
    xg = np.arange(len(g_conds))
    ax.bar(xg - 0.18, [gran[c]["labels_ratio"] for c in g_conds], 0.34,
           color=C_AQUA, zorder=3, label="labels/nh vs DTDE")
    ax.bar(xg + 0.18, [gran[c]["h_rank_corr"] / CUR_LIMITS["rank"]
                       for c in g_conds], 0.34, color=C_ORANGE, zorder=3,
           label="config-rank leak / limit")
    ax.axhline(1.0, color=INK2, lw=0.9, ls="--")
    ax.set_xticks(xg, g_lab)
    ax.legend(frameon=False, fontsize=7)
    ax.set_title("13.2-2 score granularity\n(H→R cost channel, CEDT)",
                 loc="left", fontsize=8.5)
    # 13.2-4
    ax = axes[1]
    h_conds = ["CEDT_P2x", "CEDT_P3x", "CEDT_P4x", "CTDE_P3x"]
    xh = np.arange(len(h_conds))
    ax.bar(xh - 0.18, [hist[c]["mi_auc_cumulative"] for c in h_conds],
           0.34, color=C_BLUE, zorder=3, label="cumulative transcript")
    ax.bar(xh + 0.18, [hist[c]["mi_auc_windowed"] for c in h_conds],
           0.34, color="#9ec8f0", zorder=3, label="last 10 rounds only")
    ax.axhline(0.60, color=C_ORANGE, lw=1.1, ls="--")
    ax.set_ylim(0.45, 1.0)
    ax.set_xticks(xh, [c.replace("x", "").replace("_", "\n")
                       for c in h_conds], fontsize=7.5)
    ax.set_ylabel("R membership-inference AUC")
    ax.legend(frameon=False, fontsize=7)
    ax.set_title("13.2-4 transcript history\n(composition/linkability risk)",
                 loc="left", fontsize=8.5)
    # 13.2-7
    ax = axes[2]
    s_conds = ["CEDT_P2x", "CEDT_P2_RCTL"]
    xs = np.arange(2)
    ax.bar(xs - 0.18, [swap[c]["labels_ratio"] for c in s_conds], 0.34,
           color=C_AQUA, zorder=3, label="labels/nh vs DTDE")
    ax.bar(xs + 0.18, [swap[c]["fail_rate"] * 10 for c in s_conds], 0.34,
           color=C_ORANGE, zorder=3, label="failure rate (x10)")
    ax.set_xticks(xs, ["H controls\n(default)", "R controls\n(swap)"],
                  fontsize=8)
    ax.legend(frameon=False, fontsize=7)
    ax.set_title("13.2-7 numerical-knob control\n(CEDT-P2)", loc="left",
                 fontsize=8.5)
    # 13.2-8
    ax = axes[3]
    pairs8 = [("DTDE", "DTDE_P4_noshift_ref", "DTDE_SHIFT"),
              ("CEDT_P4", "CEDT_P4x_noshift_ref", "CEDT_P4_SHIFT"),
              ("CEDT_P3", "CEDT_P3x_noshift_ref", "CEDT_P3_SHIFT")]
    xp = np.arange(len(pairs8))
    ax.bar(xp - 0.18, [shift[r]["labels_per_nh"] * 1e3
                       for _, r, _ in pairs8], 0.34, color=C_BLUE,
           zorder=3, label="stationary contention")
    ax.bar(xp + 0.18, [shift[s]["labels_per_nh"] * 1e3
                       for _, _, s in pairs8], 0.34, color="#9ec8f0",
           zorder=3, label="shift +0.35 at t=12")
    ax.set_xticks(xp, [p[0] for p in pairs8], fontsize=8)
    ax.set_ylabel("valid F2+ labels per nh (x1e-3)")
    ax.legend(frameon=False, fontsize=7)
    ax.set_title("13.2-8 contention-regime shift", loc="left", fontsize=8.5)
    fig.suptitle("Section 13.2 ablations (1,000 prior worlds x 30 paired "
                 "seeds; simulated units)", fontsize=9, x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(RES / "fig_ablations.png", dpi=160)
    plt.close(fig)

    print("education:", {c: round(edu[c]["K_S_mean"], 3) for c in EDU_CONDS})
    print("minimal Q at kappa=0.9:", minimal_q["0.9"])
    print("granularity:", {c: round(gran[c]["labels_ratio"], 3)
                           for c in gran})
    print("history risk:", {c: round(hist[c]["composition_risk"], 3)
                            for c in hist})
    print("swap:", {c: (round(swap[c]["labels_ratio"], 3),
                        round(swap[c]["fail_rate"], 3)) for c in swap})
    print("shift ww:", {c: round(shift[c]["win_win_vs_shifted_dtde"], 3)
                        for c in shift if "SHIFT" in c})


if __name__ == "__main__":
    main()

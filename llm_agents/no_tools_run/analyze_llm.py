#!/usr/bin/env python3
"""Analysis + figures for the LLM-agents-as-decision-makers run.

Reads results/llm_results_v2.json (paired LLM vs scripted campaigns on
identical worlds/seeds/noise) and writes two figures plus a markdown
summary fragment. All node-hours are simulated units.
"""
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
RES = HERE / "results"
COL = {"scripted": "#2a78d6", "llm": "#eb6834"}
INK, MUTED = "#1a1f24", "#6b7480"
CONDS = ["CTCE_P0", "DTDE_P4", "CEDT_P4", "CEDT_P3_eps2"]
LABELS = {"CTCE_P0": "CTCE-P0\n(ceiling)", "DTDE_P4": "DTDE-P4\n(baseline)",
          "CEDT_P4": "CEDT-P4", "CEDT_P3_eps2": "CEDT-P3\n(eps=2)"}

d = json.load(open(RES / "llm_results_v2.json"))
recs, meta = d["records"], d["meta"]


def sel(pol, cond):
    return [r for r in recs if r["policy"] == pol and r["condition"] == cond]


def mean(pol, cond, key):
    return float(np.mean([r[key] for r in sel(pol, cond)]))


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#d5dae0")
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.yaxis.grid(True, color="#eceff2", lw=0.8)
    ax.set_axisbelow(True)


# ---- figure 1: outcome metrics, small multiples --------------------------
METRICS = [("mean_nh_first", "Node-hours to first qualifier (mean)", 1),
           ("mean_qual", "Qualifying candidates found (mean)", 1),
           ("labels_per_nh", "Valid F2+ labels per node-hour", 1000),
           ("fail_rate", "Job failure rate", 100)]
UNITS = {1: "", 1000: " (x1e-3)", 100: " (%)"}

def fmt(v):
    return f"{v:.0f}" if v >= 20 else f"{v:.2g}"


fig, axes = plt.subplots(2, 2, figsize=(9.2, 6.6), facecolor="white")
x = np.arange(len(CONDS))
for ax, (key, title, scale) in zip(axes.flat, METRICS):
    style(ax)
    for k, pol in enumerate(("scripted", "llm")):
        vals = [mean(pol, c, key) * scale for c in CONDS]
        b = ax.bar(x + (k - 0.5) * 0.32, vals, width=0.28, color=COL[pol],
                   label="Scripted policy" if pol == "scripted"
                   else "LLM agents", zorder=3)
        for rect, v in zip(b, vals):
            ax.annotate(fmt(v), (rect.get_x() + rect.get_width() / 2, v),
                        ha="center", va="bottom", fontsize=7, color=MUTED)
    ax.margins(y=0.14)
    ax.set_title(title + UNITS[scale], fontsize=9.5, color=INK, pad=8)
    ax.set_xticks(x, [LABELS[c] for c in CONDS], fontsize=8, color=INK)
h, l = axes[0, 0].get_legend_handles_labels()
fig.legend(h, l, frameon=False, fontsize=9, ncol=2,
           loc="upper center", bbox_to_anchor=(0.5, 0.965))
fig.suptitle("LLM agents vs scripted policies — paired worlds and seeds "
             "(simulated node-hours)", fontsize=11, color=INK, y=0.995)
fig.tight_layout(rect=(0, 0, 1, 0.93))
fig.savefig(RES / "fig_llm_vs_scripted.png", dpi=150)
plt.close(fig)

# ---- figure 2: behavior — pace and paired first-qualifier scatter --------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.2, 3.8), facecolor="white")
style(ax1)
for k, pol in enumerate(("scripted", "llm")):
    vals = [mean(pol, c, "rounds") for c in CONDS]
    b = ax1.bar(x + (k - 0.5) * 0.32, vals, width=0.28, color=COL[pol],
                label="Scripted policy" if pol == "scripted"
                else "LLM agents", zorder=3)
    for rect, v in zip(b, vals):
        ax1.annotate(f"{v:.0f}", (rect.get_x() + rect.get_width() / 2, v),
                     ha="center", va="bottom", fontsize=7.5, color=MUTED)
ax1.set_xticks(x, [LABELS[c] for c in CONDS], fontsize=8, color=INK)
ax1.set_title("Job attempts per campaign: LLM agents run fewer,\n"
              "bigger jobs at the same budget", fontsize=9.5, color=INK)
ax1.legend(frameon=False, fontsize=8.5)

style(ax2)
for cond in ("DTDE_P4",):
    s = {(r["card"], r["world"]): r["mean_nh_first"] for r in sel("scripted",
                                                                  cond)}
    l = {(r["card"], r["world"]): r["mean_nh_first"] for r in sel("llm",
                                                                  cond)}
    ks = sorted(s)
    ax2.scatter([s[k] for k in ks], [l[k] for k in ks], s=42,
                color=COL["llm"], edgecolors="white", linewidths=1.2,
                zorder=3)
lim = (0, 660)
ax2.plot(lim, lim, color="#c3c9d1", lw=1.2, ls="--", zorder=2)
ax2.set_xlim(lim)
ax2.set_ylim(lim)
ax2.set_xlabel("Scripted: nh to first qualifier", fontsize=8.5, color=INK)
ax2.set_ylabel("LLM agents: nh to first qualifier", fontsize=8.5, color=INK)
ax2.set_title("Paired per-world comparison (DTDE-P4): below the\n"
              "diagonal = LLM agents found a qualifier sooner",
              fontsize=9.5, color=INK)
fig.tight_layout()
fig.savefig(RES / "fig_llm_behavior.png", dpi=150)
plt.close(fig)

# ---- markdown summary -----------------------------------------------------
lines = ["| condition | policy | nh to 1st qual | found rate | mean quals | "
         "labels/nh | fail rate | validity | R-gain | H-gain | leak ok | "
         "win-win |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"
         "---:|---:|"]
for c in CONDS:
    for pol in ("scripted", "llm"):
        lines.append(
            f"| {c} | {pol} | {mean(pol, c, 'mean_nh_first'):.0f} | "
            f"{mean(pol, c, 'found_rate'):.2f} | {mean(pol, c, 'mean_qual'):.2f} | "
            f"{mean(pol, c, 'labels_per_nh'):.4f} | "
            f"{mean(pol, c, 'fail_rate'):.3f} | {mean(pol, c, 'validity'):.3f} | "
            f"{mean(pol, c, 'r_gain'):.2f} | {mean(pol, c, 'h_gain'):.2f} | "
            f"{mean(pol, c, 'leak_ok'):.2f} | {mean(pol, c, 'win_win'):.2f} |")

llm_recs = [r for r in recs if r["policy"] == "llm"]
agr = (sum(r["agree_r"] for r in llm_recs)
       / max(sum(r["n_r"] for r in llm_recs), 1),
       sum(r["agree_h"] for r in llm_recs)
       / max(sum(r["n_h"] for r in llm_recs), 1))
leak = {k: (mean("llm", "CEDT_P3_eps2", k), mean("scripted", "CEDT_P3_eps2", k))
        for k in ("r_mi_auc", "r_id_acc", "h_tel_auc", "h_rank_corr")}
lines += ["", f"Decision agreement with the scripted policy: "
          f"R seat {agr[0]:.1%}, H seat {agr[1]:.1%}.",
          f"Calls: R {meta['r_calls']} (fallbacks {meta['r_fallbacks']}), "
          f"H {meta['h_calls']} (fallbacks {meta['h_fallbacks']}); "
          f"wall {meta['wall_s']:.0f} s.",
          "Leakage at CEDT-P3 (llm vs scripted): " + ", ".join(
              f"{k} {v[0]:.3f}/{v[1]:.3f}" for k, v in leak.items())]
(RES / "summary_fragment.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))

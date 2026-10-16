#!/usr/bin/env python3
"""Figure for the hybrid/ALT/collusion arm study: P(win-win, redesigned
metrics) and P(leakage ok) per arm on the measurement-informed posterior
at x100 scale, with the wide-prior x1 values as reference dots."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).parent
d = json.load(open(HERE / "hybrid_results.json"))
ORDER = ["CTCE_P0", "DTDE_P4", "CTDE_P2", "CTDE_P3_eps2", "CTDE_P4",
         "CEDT_P2", "CEDT_P3_eps2", "CEDT_P4", "HYB_P2", "HYB_P3_eps2",
         "ALT_P4", "CEDT_P3_eps2_collude", "HYB_P3_eps2_collude"]
LAB = [c.replace("_eps2", " (ε=2)").replace("_collude", "\ncollude")
       .replace("_", "-") for c in ORDER]
C1, C2 = "#2a78d6", "#eb6834"
SURF, INK, MUT = "#fcfcfb", "#222222", "#6b6b6b"


def agg(setting, cond, key):
    return float(np.mean([r[cond][key] for r in d[setting]]))


fig, axes = plt.subplots(2, 1, figsize=(9.2, 6.4), dpi=150, sharex=True)
fig.patch.set_facecolor(SURF)
x = np.arange(len(ORDER))
for ax, key, ttl in ((axes[0], "win_win_redesigned",
                      "P(win-win) — redesigned metrics (PW60 + package)"),
                     (axes[1], "leak_ok", "P(all six leakage limits hold)")):
    ax.set_facecolor(SURF)
    post = [agg("posterior_x100", c, key) for c in ORDER]
    wide = [agg("wide_prior_x1", c, key) for c in ORDER]
    b = ax.bar(x, post, 0.62, color=C2,
               label="posterior, ×100 scale")
    ax.scatter(x, wide, color=C1, s=22, zorder=3,
               label="wide prior, ×1 scale")
    for r, v in zip(b, post):
        ax.text(r.get_x() + r.get_width() / 2, v + 0.02, f"{v:.2f}",
                ha="center", va="bottom", fontsize=7, color=INK)
    if key == "win_win_redesigned":
        ax.axhline(0.90, color=MUT, lw=1, ls="--", zorder=0)
        ax.text(len(ORDER) - 0.4, 0.92, "0.90", color=MUT, fontsize=8,
                ha="right")
    ax.set_ylim(0, 1.1)
    ax.set_ylabel(ttl, fontsize=8.5, color=INK)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(MUT)
    ax.tick_params(colors=MUT, labelcolor=INK)
    ax.yaxis.grid(True, color="#e6e6e3", lw=0.7, zorder=0)
    ax.set_axisbelow(True)
axes[0].legend(frameon=False, fontsize=8.5, loc="upper left")
axes[0].set_title("All topologies + hybrid-mix + ALT + collusion "
                  "(300 worlds, 30 paired seeds, CRN)",
                  fontsize=11, color=INK, pad=10)
axes[1].set_xticks(x, LAB, fontsize=7, color=INK, rotation=28, ha="right")
fig.tight_layout()
fig.savefig(HERE / "fig_hybrid_arms.png")
print("wrote fig_hybrid_arms.png")

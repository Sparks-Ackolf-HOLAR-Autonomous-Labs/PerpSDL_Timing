#!/usr/bin/env python3
"""Figure for the task-scale sweep of the centralization surface.
SIMULATED UNITS (posterior twin anchored to Stage-2 + pilot + scale fits)."""
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
R = HERE / "results"

d = json.load(open(R / "surface_scale.json"))
cells = d["cells"].values()
scales = d["meta"]["scales"]


def grid_at(scale, level, metric):
    pts = [c for c in cells if c["scale"] == scale and c["level"] == level
           and c["tau"] != "ceiling"]
    taus = sorted({c["tau"] for c in pts})
    epss = sorted({c["eps"] for c in pts})
    Z = np.full((len(epss), len(taus)), np.nan)
    for c in pts:
        Z[epss.index(c["eps"]), taus.index(c["tau"])] = c[metric]
    return np.array(taus), np.array(epss), Z


def point(scale, level, tau, eps, metric):
    for c in cells:
        if (c["scale"] == scale and c["level"] == level
                and c["tau"] == tau and c["eps"] == eps):
            return c[metric]
    return np.nan


fig = plt.figure(figsize=(15, 8.6))
gs = fig.add_gridspec(2, 6, height_ratios=[1.15, 1],
                      width_ratios=[1, 1, 1, 1, 1, 0.07])

zmax = max(max(c["win_win"] for c in cells if c["level"] == "P4"), 0.25)
for col, scale in enumerate(scales):
    ax = fig.add_subplot(gs[0, col])
    taus, epss, Z = grid_at(scale, "P4", "win_win")
    im = ax.imshow(Z, origin="lower", aspect="auto", cmap="viridis",
                   vmin=0, vmax=zmax,
                   extent=[taus.min(), taus.max(), epss.min(), epss.max()])
    for name, (t, e) in {"DTDE": (0, 0), "CTDE": (1, 0),
                         "CEDT": (0, 1), "CTCE@P4": (1, 1)}.items():
        ax.text(t, e, name, ha="center", va="center", fontsize=7,
                color="white", weight="bold",
                bbox=dict(boxstyle="round", fc="black", alpha=0.35, pad=0.12))
    ax.set_title(f"×{scale} task scale\n"
                 f"ridge (ε=1) = {Z[-1, :].mean():.2f}", fontsize=9)
    ax.set_xlabel("τ", fontsize=8)
    if col == 0:
        ax.set_ylabel("ε (execution centralization)", fontsize=8)
cax = fig.add_subplot(gs[0, 5])
fig.colorbar(im, cax=cax, label="P(win-win), disclosure P4")

# --- bottom row: how the corners move with scale ---
# overlapping curves (CEDT==CTCE@P4, DTDE==CTDE==ceiling at 0) get distinct
# widths/styles so every arm stays visible
corner_pts = [("DTDE (0,0)", "P4", 0.0, 0.0, "tab:gray", "-", 5.0, 9),
              ("CTDE (1,0)", "P4", 1.0, 0.0, "tab:orange", "--", 3.0, 7),
              ("CEDT (0,1)", "P4", 0.0, 1.0, "tab:blue", "-", 4.5, 9),
              ("CTCE@P4 (1,1)", "P4", 1.0, 1.0, "tab:green", "--", 2.0, 5)]

axA = fig.add_subplot(gs[1, 0:2])
for name, lvl, t, e, colr, ls, lw, ms in corner_pts:
    y = [point(s, lvl, t, e, "win_win") for s in scales]
    axA.plot(scales, y, ls, marker="o", label=name, color=colr, lw=lw, ms=ms)
yc = [point(s, "P0", "ceiling", "ceiling", "win_win") for s in scales]
axA.plot(scales, yc, ":", marker="s", label="CTCE@P0 ceiling (unfiltered)",
         color="crimson", lw=1.5, ms=4)
axA.annotate("CEDT = CTCE@P4 (τ adds nothing, every scale)",
             xy=(30, 0.942), xytext=(3, 0.80), fontsize=8,
             arrowprops=dict(arrowstyle="->", lw=0.8))
axA.annotate("DTDE = CTDE = CTCE@P0 ceiling = 0",
             xy=(30, 0.0), xytext=(3, 0.12), fontsize=8,
             arrowprops=dict(arrowstyle="->", lw=0.8))
axA.set_xscale("log")
axA.set_xlabel("task-scale multiplier (measured ×1 campaign cost)", fontsize=9)
axA.set_ylabel("P(win-win)", fontsize=9)
axA.set_title("Corner arms vs task scale (P4)", fontsize=10)
axA.grid(alpha=0.3)
axA.legend(fontsize=7)

axB = fig.add_subplot(gs[1, 2:4])
for m, lab, colr in [("r_gain_pw60", "P(R gain: PW60)", "tab:blue"),
                     ("h_gain_package", "P(H gain: ≥+5% package)",
                      "tab:green"),
                     ("leak_ok", "P(leakage limits hold)", "tab:red")]:
    y = [point(s, "P4", 0.0, 1.0, m) for s in scales]
    axB.plot(scales, y, "o-", label=lab, color=colr, lw=2, ms=5)
axB.set_xscale("log")
axB.set_xlabel("task-scale multiplier", fontsize=9)
axB.set_ylabel("probability", fontsize=9)
axB.set_title("What drives the CEDT-P4 ridge as tasks grow", fontsize=10)
axB.grid(alpha=0.3)
axB.legend(fontsize=7)

axC = fig.add_subplot(gs[1, 4])
p2_scales = sorted({c["scale"] for c in cells if c["level"] == "P2"})
w = 0.35
for k, s in enumerate(p2_scales):
    corner = point(s, "P2", 0.0, 1.0, "win_win")
    interior = max(c["win_win"] for c in cells
                   if c["scale"] == s and c["level"] == "P2"
                   and c["tau"] != "ceiling")
    axC.bar(k - w / 2, corner, w, color="tab:red",
            label="CEDT-P2 corner (ε=1)" if k == 0 else None)
    axC.bar(k + w / 2, interior, w, color="tab:blue",
            label="best interior (ε=τ=0.25)" if k == 0 else None)
    axC.text(k - w / 2, corner + 0.03, f"{corner:.2f}",
             ha="center", fontsize=8)
    axC.text(k + w / 2, interior + 0.03, f"{interior:.2f}",
             ha="center", fontsize=8)
axC.set_xticks(range(len(p2_scales)))
axC.set_xticklabels([f"×{s}" for s in p2_scales], fontsize=8)
axC.set_ylim(0, 1.05)
axC.set_ylabel("P(win-win)", fontsize=8)
axC.set_title("P2: corner leak-dead, but a\nlow-dose corridor opens", fontsize=9)
axC.grid(alpha=0.3, axis="y")
axC.legend(fontsize=6.5)

fig.suptitle("Centralization surface vs task scale — SIMULATED UNITS "
             "(posterior twin anchored to Stage-2 / pilot / scale-validation "
             "measurements; P4 disclosure unless noted)", fontsize=11)
fig.tight_layout(rect=[0, 0, 1, 0.95])
fig.savefig(R / "fig_surface_vs_scale.png", dpi=135)
print("wrote fig_surface_vs_scale.png")

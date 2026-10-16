#!/usr/bin/env python3
"""Figures for the centralization surface + multi-party scaling.
SIMULATED UNITS.

Terminology: the name "HYB" is retired. The (1,1)
corner IS the CTCE topology (both decisions fully centralized); what
distinguishes it from the classic CTCE ceiling is only the disclosure dial.
We therefore write the corner as CTCE@Pk (full centralization under the
panel's contract filter) and reserve plain CTCE / CTCE@P0 for the unfiltered
merged-seat ceiling reference.

Throughput is displayed as PERCENT GAIN vs the DTDE baseline
((ratio - 1) x 100), not as a ratio.
"""
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

HERE = Path(__file__).parent
R = HERE / "results"

# richest disclosure last so P4 (the recommended contract) leads
LEVELS = [l for l in ("P4", "P3", "P2", "P1")
          if (R / f"surface_{l}.json").exists()]


def corner_labels(level):
    return {"DTDE": (0, 0), "CTDE": (1, 0), "CEDT": (0, 1),
            f"CTCE@{level}": (1, 1)}


def load_surface(level):
    d = json.load(open(R / f"surface_{level}.json"))["surface"]
    pts = {k: v for k, v in d.items() if "|P0" not in k}
    taus = sorted({v["tau"] for v in pts.values()})
    epss = sorted({v["eps"] for v in pts.values()})
    Z = {m: np.full((len(epss), len(taus)), np.nan)
         for m in ("win_win", "labels_ratio", "leak_ok")}
    for v in pts.values():
        ti, ei = taus.index(v["tau"]), epss.index(v["eps"])
        for m in Z:
            Z[m][ei, ti] = v[m]
    ceil = d.get("ceiling|P0")
    return np.array(taus), np.array(epss), Z, ceil


def fig_surface():
    n = len(LEVELS)
    ncol = 2
    nrow = (n + ncol - 1) // ncol
    fig = plt.figure(figsize=(7.6 * ncol, 6.0 * nrow))
    zmax = 0.01
    for level in LEVELS:
        _, _, Z, _ = load_surface(level)
        zmax = max(zmax, np.nanmax(Z["win_win"]))
    zmax = max(0.26, zmax + 0.02)
    for k, level in enumerate(LEVELS):
        taus, epss, Z, ceil = load_surface(level)
        TT, EE = np.meshgrid(taus, epss)
        ax = fig.add_subplot(nrow, ncol, k + 1, projection="3d")
        z = Z["win_win"]
        ax.plot_surface(TT, EE, z, cmap="viridis", vmin=0, vmax=zmax,
                        edgecolor="k", linewidth=0.3, alpha=0.9)
        for name, (t, e) in corner_labels(level).items():
            zi = z[epss.tolist().index(e), taus.tolist().index(t)]
            ax.scatter([t], [e], [zi], s=55, color="crimson", depthshade=False)
            ax.text(t, e, zi + 0.012, f"{name}\n{zi:.3f}", fontsize=8,
                    ha="center", weight="bold")
        ax.set_xlabel("training centralization  τ", fontsize=9, labelpad=8)
        ax.set_ylabel("execution centralization  ε", fontsize=9, labelpad=8)
        ax.set_zlabel("P(win-win)", fontsize=9)
        ax.set_zlim(0, zmax)
        ax.set_title(f"Disclosure {level}   "
                     f"(CTCE@P0 ceiling: leak-fails, P(win-win)=0)",
                     fontsize=10)
        ax.view_init(elev=24, azim=-125)
    fig.suptitle("Centralization surface: (training × execution) "
                 "→ win-win probability  —  SIMULATED UNITS "
                 "(twin from simulator.py; corners reproduce native arms; "
                 "(1,1) = CTCE topology under the panel's contract filter)",
                 fontsize=12, y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(R / "fig_centralization_surface.png", dpi=135)
    print("wrote fig_centralization_surface.png")


def fig_heatmaps():
    nrow = len(LEVELS)
    fig, axes = plt.subplots(nrow, 3, figsize=(14, 4.2 * nrow))
    if nrow == 1:
        axes = axes[None, :]
    gain_max = 5.0
    for level in LEVELS:
        _, _, Z, _ = load_surface(level)
        gain_max = max(gain_max, np.nanmax((Z["labels_ratio"] - 1) * 100))
    gain_max = float(np.ceil(gain_max / 5) * 5)
    for row, level in enumerate(LEVELS):
        taus, epss, Z, _ = load_surface(level)
        for col, (m, ttl, vmin, vmax) in enumerate([
                ("win_win", "P(win-win)", 0.0, 0.25),
                ("labels_ratio", "throughput gain vs DTDE (%)", 0.0, gain_max),
                ("leak_ok", "P(all leakage limits hold)", 0.0, 1.0)]):
            ax = axes[row, col]
            data = Z[m]
            if m == "labels_ratio":
                data = (data - 1.0) * 100.0
            im = ax.imshow(data, origin="lower", aspect="auto", cmap="viridis",
                           vmin=vmin, vmax=vmax,
                           extent=[taus.min(), taus.max(), epss.min(), epss.max()])
            for name, (t, e) in corner_labels(level).items():
                ax.text(0.03 + 0.94 * t, 0.05 + 0.90 * e, name,
                        ha=("left" if t == 0 else "right"), va="center",
                        fontsize=7.5, color="white", weight="bold",
                        bbox=dict(boxstyle="round", fc="black", alpha=0.35, pad=0.15))
            ax.set_xlabel("τ (training centralization)", fontsize=8)
            ax.set_ylabel("ε (execution centralization)", fontsize=8)
            ax.set_title(f"{level}: {ttl}", fontsize=9)
            cb = fig.colorbar(im, ax=ax, fraction=0.046)
            if m == "labels_ratio":
                cb.set_label("%", fontsize=8)
    fig.suptitle("Centralization surface, all disclosure levels × three "
                 "metrics  —  SIMULATED UNITS  (throughput as % gain vs "
                 "DTDE; (1,1) = CTCE@Pk, filtered full centralization)",
                 fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.975])
    fig.savefig(R / "fig_centralization_heatmaps.png", dpi=135)
    print("wrote fig_centralization_heatmaps.png")


def fig_scaling():
    s = json.load(open(R / "scaling.json"))["summary"]
    N = [1, 2, 3, 5]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    arms = ["DTDE", "CTDE-P4", "CEDT-P4", "CEDT-P2", "MIX-P4(.5,.5)"]
    colors = dict(zip(arms, plt.cm.tab10(np.linspace(0, 0.5, len(arms)))))
    for ax, (m, ttl) in zip(axes, [
            ("win_win", "P(win-win)"),
            ("leak_ok", "P(all leakage limits hold)"),
            ("labels_ratio", "throughput gain vs DTDE (%)")]):
        for arm in arms:
            y = np.array([s[arm][str(n)][m] for n in N], float)
            if m == "labels_ratio":
                y = (y - 1.0) * 100.0
            ax.plot(N, y, "o-", label=arm, color=colors[arm], lw=2, ms=6)
        ax.set_xlabel("number of research parties  N", fontsize=9)
        ax.set_ylabel(ttl, fontsize=9)
        ax.set_title(ttl, fontsize=10)
        ax.set_xticks(N)
        ax.grid(alpha=0.3)
        if m == "labels_ratio":
            ax.axhline(5.0, ls="--", color="grey", lw=1)
            ax.annotate("H margin (+5%)", xy=(N[-1], 5.0), fontsize=7,
                        ha="right", va="bottom", color="grey")
    axes[0].legend(fontsize=8, loc="upper right")
    fig.suptitle("Multi-party scaling: throughput is flat in N; leakage "
                 "crowding hits richer disclosure, not the P4 contract  —  "
                 "SIMULATED UNITS", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(R / "fig_multiparty_scaling.png", dpi=135)
    print("wrote fig_multiparty_scaling.png")


def fig_schedules():
    s = json.load(open(R / "schedules.json"))["summary"]
    order = ["static", "ramp_up", "ramp_down", "mid_pulse"]
    keys = list(s.keys())
    fig, axes = plt.subplots(1, len(keys), figsize=(5.4 * len(keys), 4.4))
    if len(keys) == 1:
        axes = [axes]
    for ax, key in zip(axes, keys):
        names = [n for n in order if n in s[key]]
        ww = [s[key][n]["win_win"] for n in names]
        gain = [(s[key][n]["labels_ratio"] - 1.0) * 100.0 for n in names]
        x = np.arange(len(names))
        b1 = ax.bar(x - 0.2, ww, 0.4, label="P(win-win)", color="#3b6")
        ax2 = ax.twinx()
        b2 = ax2.bar(x + 0.2, gain, 0.4,
                     label="throughput gain vs DTDE (%)", color="#69c")
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=20, fontsize=8)
        ax.axhline(0, color="k", lw=0.6)
        ax.set_ylabel("P(win-win)", fontsize=8, color="#3b6")
        ax2.set_ylabel("throughput gain (%)", fontsize=8, color="#69c")
        ax.set_title(key, fontsize=10)
        ax.grid(alpha=0.3, axis="y")
        if ax is axes[0]:
            ax.legend(handles=[b1, b2], fontsize=8, loc="upper left")
    fig.suptitle("Adaptive schedules at fixed time-mean: timing matters on the "
                 "execution axis (eps@P4), not the cumulative training axis "
                 "(tau@P2)  —  SIMULATED UNITS", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(R / "fig_schedules.png", dpi=135)
    print("wrote fig_schedules.png")


if __name__ == "__main__":
    fig_surface()
    fig_heatmaps()
    fig_scaling()
    fig_schedules()

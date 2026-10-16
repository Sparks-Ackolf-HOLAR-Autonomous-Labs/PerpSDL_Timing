#!/usr/bin/env python3
"""Figure for the tau (training-centralization) flatness diagnostic.
SIMULATED UNITS."""
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
R = HERE / "results"

d = json.load(open(R / "tau_diagnostic.json"))
tr = d["transects"]
epss = sorted({v["eps"] for v in tr.values()})
colors = {0.0: "#4477aa", 0.5: "#ee6677", 1.0: "#228833"}

fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))

# A: utility vs tau (dense transects, P2)
ax = axes[0]
for eps in epss:
    pts = sorted([v for v in tr.values() if v["eps"] == eps],
                 key=lambda v: v["tau"])
    taus = [v["tau"] for v in pts]
    ax.plot(taus, [(v["labels_ratio"] - 1.0) * 100.0 for v in pts], "-o", ms=3,
            color=colors[eps], label=f"ε = {eps:g}")
ax.axhline(0, color="k", lw=0.6)
ax.set_xlabel("training centralization  τ")
ax.set_ylabel("throughput gain vs DTDE-P4 (%)")
ax.set_title("A. Utility vs τ at P2 (21-point transects)\n"
             "the τ direction moves throughput by <1% at every ε")
ax.legend(fontsize=8)
ax.grid(alpha=0.3)

# B: leakage vs tau — where tau DOES act
ax = axes[1]
for eps in epss:
    pts = sorted([v for v in tr.values() if v["eps"] == eps],
                 key=lambda v: v["tau"])
    taus = [v["tau"] for v in pts]
    ax.plot(taus, [v["r_id_acc"] for v in pts], "-o", ms=3,
            color=colors[eps], label=f"identity acc, ε = {eps:g}")
    ax.plot(taus, [v["leak_ok"] for v in pts], "--s", ms=3,
            color=colors[eps], alpha=0.5, label=f"P(leak ok), ε = {eps:g}")
ax.axhline(1 / 30 + 0.05, color="k", lw=0.8, ls=":", label="identity limit")
ax.set_xlabel("training centralization  τ")
ax.set_ylabel("attacker identity accuracy  /  P(leak ok)")
ax.set_title("B. Leakage vs τ at P2\n"
             "τ buys leakage exposure without buying utility")
ax.legend(fontsize=7)
ax.grid(alpha=0.3)

# C: information-redundancy probe
ax = axes[2]
r2 = d["info_r2"]
names = ["own\n(R's own bills,\nfree in every arm)",
         "surrogate\n(P2 shared logbook,\nasymptotic best)",
         "broker\n(H's runtime view\nat P2 precision)"]
vals = [r2["own"]["mean"], r2["surrogate"]["mean"], r2["broker"]["mean"]]
errs = [r2["own"]["sd"], r2["surrogate"]["sd"], r2["broker"]["sd"]]
bars = ax.bar(names, vals, yerr=errs, capsize=4,
              color=["#4477aa", "#ee6677", "#228833"])
for b, v in zip(bars, vals):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.015, f"{v:.3f}",
            ha="center", fontsize=9, weight="bold")
ax.set_ylim(0, 1.12)
ax.set_ylabel("cross-candidate cost variance explained (R²)")
ax.set_title("C. Why: the shared logbook is redundant\n"
             "R's free information already beats the logbook's ceiling")
ax.grid(alpha=0.3, axis="y")

fig.suptitle("Why the training-centralization axis is flat — SIMULATED UNITS. "
             "At P4 the τ channel is empty by contract (γ(P4)=0: no descriptor "
             "crosses the boundary; verified bit-identical outputs); at P2 it "
             "carries only redundant information plus leakage.",
             fontsize=10, y=1.02)
fig.tight_layout()
fig.savefig(R / "fig_tau_answer.png", dpi=135, bbox_inches="tight")
print("wrote fig_tau_answer.png")

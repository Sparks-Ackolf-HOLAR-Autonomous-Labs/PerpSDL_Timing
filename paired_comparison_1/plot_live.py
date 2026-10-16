#!/usr/bin/env python3
"""Figure for the live CEDT-P4 vs DTDE comparison + wire attacks + bench."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).parent
RES = HERE / "results"
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, MUTED = "#333333", "#777777"

camps = [json.loads(x) for x in open(RES / "campaigns.jsonl")]
by = {(c["arm"], c["seed"]): c for c in camps}
seeds = sorted({s for (_, s) in by})
grading = json.load(open(RES / "live_grading.json"))
attack = json.load(open(RES / "wire_attack_results.json"))
bench = json.load(open(HERE.parent / "contention_transfer_bench" / "results" /
                       "bench_analysis.json"))

fig, axes = plt.subplots(1, 4, figsize=(16, 3.8))
for ax in axes:
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(colors=MUTED)
    ax.grid(axis="y", color="#e8e8e8", lw=0.7, zorder=0)

# A: paired nh-to-first-qualifier
ax = axes[0]
d = [by[("DTDE", s)]["nh_first_qual"] for s in seeds]
c = [by[("CEDT_P4", s)]["nh_first_qual"] for s in seeds]
lim = [0, max(d + c) * 1.12]
ax.plot(lim, lim, color=MUTED, lw=1, ls="--", zorder=1)
ax.scatter(d, c, s=55, color=BLUE, edgecolor="white", lw=1.5, zorder=3)
ax.set_xlabel("DTDE node-hours to first qualifier", color=INK)
ax.set_ylabel("CEDT-P4 node-hours", color=INK)
ax.set_title("A  Paired campaigns (10 seeds, real QE)",
             loc="left", color=INK, fontsize=11)
ax.text(0.05, 0.9, f"CEDT wins {int(grading['pw_rate']*10)}/10 pairs\n"
        f"sign test p = {grading['sign_test_p']:.2f}",
        transform=ax.transAxes, fontsize=9, color=INK)

# B: H metric — labels per node-hour
ax = axes[1]
dl = sum(by[("DTDE", s)]["labels_f2"] for s in seeds)
dn = sum(by[("DTDE", s)]["nh"] for s in seeds)
cl = sum(by[("CEDT_P4", s)]["labels_f2"] for s in seeds)
cn = sum(by[("CEDT_P4", s)]["nh"] for s in seeds)
vals = [dl / dn, cl / cn]
bars = ax.bar(["DTDE", "CEDT-P4"], vals, width=0.55,
              color=[BLUE, ORANGE], zorder=3)
req = vals[0] * 1.05
ax.axhline(req, color=INK, lw=1.2, ls=":")
ax.text(1.02, req, "required\n1.05 × DTDE", fontsize=8, color=INK,
        va="center", transform=ax.get_yaxis_transform())
for b, v in zip(bars, vals):
    ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.2f}",
            ha="center", va="bottom", fontsize=9, color=INK)
ax.set_ylabel("valid F2+ labels / node-hour", color=INK)
ax.set_title(f"B  H margin fails ({grading['labels_per_nh_ratio']:.3f}×"
             " vs 1.05×)", loc="left", color=INK, fontsize=11)
ax.set_ylim(0, max(vals) * 1.25)

# C: executed timing attacks
ax = axes[2]
x = np.arange(2)
w = 0.32
idv = [attack["DTDE"]["identity_acc"], attack["CEDT_P4"]["identity_acc"]]
mem = [attack["DTDE"]["membership_auc"],
       attack["CEDT_P4"]["membership_auc"]]
ax.bar(x - w / 2, idv, w, color=BLUE, zorder=3, label="identity acc.")
ax.bar(x + w / 2, mem, w, color=ORANGE, zorder=3, label="membership AUC")
ax.axhline(attack["identity_limit"], color=BLUE, lw=1.2, ls=":")
ax.axhline(attack["membership_auc_limit"], color=ORANGE, lw=1.2, ls=":")
ax.text(1.02, attack["identity_limit"], "id limit", fontsize=8,
        color=BLUE, va="center", transform=ax.get_yaxis_transform())
ax.text(1.02, attack["membership_auc_limit"], "AUC limit", fontsize=8,
        color=ORANGE, va="center", transform=ax.get_yaxis_transform())
ax.set_xticks(x, ["DTDE", "CEDT-P4"])
ax.set_ylim(0, 1.12)
ax.legend(frameon=False, fontsize=8, loc="center right")
ax.set_title("C  Timing channel breaches both limits",
             loc="left", color=INK, fontsize=11)

# D: measured co-tenant contention
ax = axes[3]
scales = ["s1\n(3 at.)", "s2\n(12 at.)", "s3\n(27 at.)"]
f = [bench["contention"][s]["factor"] for s in ("s1", "s2", "s3")]
bars = ax.bar(scales, f, width=0.55, color=BLUE, zorder=3)
ax.axhline(1.0, color=INK, lw=1.2, ls=":")
for b, v in zip(bars, f):
    ax.text(b.get_x() + b.get_width() / 2, v, f"+{(v-1)*100:.0f}%",
            ha="center", va="bottom", fontsize=9, color=INK)
ax.set_ylabel("co-tenant / solo wall time", color=INK)
ax.set_ylim(0.95, 1.18)
ax.set_title("D  Contention 6–11%, not growing with size",
             loc="left", color=INK, fontsize=11)

fig.tight_layout()
fig.savefig(RES / "fig_live_comparison.png", dpi=150,
            facecolor="white", bbox_inches="tight")
print("wrote", RES / "fig_live_comparison.png")

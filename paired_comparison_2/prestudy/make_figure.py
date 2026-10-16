#!/usr/bin/env python3
"""Figure for the comparison No. 2 pre-study. Colors follow the entity
across panels: DTDE blue, CEDT-bit orange, CEDT-full aqua."""
import json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "prestudy_results.json")))
VAR = {t: json.load(open(os.path.join(HERE, f"prestudy_results{t}.json")))
       for t in ("_c8p20", "_c12p15", "_c8p15")}

C_DTDE, C_BIT, C_FULL = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, SURF = "#0b0b0b", "#52514e", "#fcfcfb"
plt.rcParams.update({"font.size": 9, "text.color": INK,
                     "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK2, "ytick.color": INK2,
                     "figure.facecolor": SURF, "axes.facecolor": SURF})
scales = [6, 7, 8]
fig, ax = plt.subplots(1, 4, figsize=(13.6, 3.4))
fig.subplots_adjust(left=0.05, right=0.99, top=0.82, bottom=0.16, wspace=0.28)

# A — H gain distribution by scale
a = ax[0]
for i, s in enumerate(scales):
    st = R["scales"][str(s)]
    hr, hf = np.array(st["h_ratios"]), np.array(st["h_fulls"])
    for off, arr, col in ((-0.13, hr, C_BIT), (0.13, hf, C_FULL)):
        lo, mid, hi = np.percentile(arr, [10, 50, 90])
        a.plot([i + off] * 2, [lo, hi], color=col, lw=2, solid_capstyle="round")
        a.plot(i + off, mid, "o", color=col, ms=7,
               markeredgecolor=SURF, markeredgewidth=1.5)
a.axhline(1.05, color=INK2, lw=1, ls=":")
a.text(2.35, 1.052, "H margin 1.05×", color=INK2, fontsize=8, va="bottom",
       ha="right")
a.text(1.62, 1.115, "memory bit", color=C_BIT, fontsize=8)
a.text(2.2, 1.30, "full RAM\n(ceiling)", color=C_FULL, fontsize=8,
       ha="center", va="center")
a.set_xticks(range(3)); a.set_xticklabels([f"{s}×{s}" for s in scales])
a.set_ylabel("H labels per charge, vs DTDE (×)")
a.set_title("A  H-side gain vs task scale\n(median, 80% interval)",
            loc="left", fontsize=9)

# B — billed fraction: the mechanism
b = ax[1]
w = 0.38
for i, s in enumerate(scales):
    st = R["scales"][str(s)]["summary"]
    b.bar(i - w / 2, st["memfrac_dtde"], w * 0.92, color=C_DTDE)
    b.bar(i + w / 2, st["memfrac_bit"], w * 0.92, color=C_BIT)
b.axhline(0.25, color=INK2, lw=1, ls=":")
b.text(-0.42, 0.256, "core floor 16/64", color=INK2, fontsize=8, va="bottom")
b.text(2 - w / 2, R["scales"]["8"]["summary"]["memfrac_dtde"] + 0.008,
       "DTDE", color=C_DTDE, ha="center", fontsize=8)
b.text(2 + w / 2, R["scales"]["8"]["summary"]["memfrac_bit"] + 0.008,
       "CEDT-bit", color=C_BIT, ha="center", fontsize=8)
b.set_xticks(range(3)); b.set_xticklabels([f"{s}×{s}" for s in scales])
b.set_ylim(0, 0.5)
b.set_ylabel("mean billed node fraction per job")
b.set_title("B  Why: reserved-memory billing\n(TRES max(cores, mem))",
            loc="left", fontsize=9)

# C — cofit gate prediction (registered before probe collection)
c = ax[2]
gs = 100 * np.array(R["gate_savings"])
c.hist(gs, bins=24, color=C_BIT, edgecolor=SURF, linewidth=0.6)
c.axvline(0, color=INK2, lw=1)
med = np.median(gs)
c.axvline(med, color=INK, lw=1.2, ls="--")
c.text(med + 0.5, c.get_ylim()[1] * 0.92, f"median {med:.0f}%", fontsize=8)
c.text(0.5, c.get_ylim()[1] * 0.5, "gate:\nsaving > 0", color=INK2,
       fontsize=8)
c.set_xlabel("predicted node-time saving, concurrent 16+16 vs sequential (%)")
c.set_ylabel("worlds")
c.set_title("C  Cofit-probe gate prediction\n(registered pre-collection)",
            loc="left", fontsize=9)

# D — budget vs design at 8×8
d = ax[3]
names = ["12 calls\n20 pairs", "8 calls\n20 pairs", "12 calls\n15 pairs",
         "8 calls\n15 pairs"]
summ = [R["scales"]["8"]["summary"], VAR["_c8p20"]["scales"]["8"]["summary"],
        VAR["_c12p15"]["scales"]["8"]["summary"],
        VAR["_c8p15"]["scales"]["8"]["summary"]]
d.axhspan(250, 450, color="#cde2fb", alpha=0.55, lw=0)
d.text(-0.38, 262, "sketch window\n250–450 nh", color=INK2, fontsize=8,
       ha="left", va="bottom")
d.set_xlim(-0.6, 3.6)
for i, (nm, st) in enumerate(zip(names, summ)):
    lo, hi = st["budget_ci80"]
    d.plot([i, i], [lo, hi], color=C_BIT, lw=2, solid_capstyle="round")
    d.plot(i, st["budget_med_nh"], "o", color=C_BIT, ms=7,
           markeredgecolor=SURF, markeredgewidth=1.5)
    d.text(i, hi + 18, f"P(pass)\n{st['p_joint']:.2f}", ha="center",
           fontsize=7.5, color=INK2)
d.set_xticks(range(4)); d.set_xticklabels(names, fontsize=7.5)
d.set_ylim(0, 900)
d.set_ylabel("total per-core node-hours (median, 80% int.)")
d.set_title("D  Budget vs design at 8×8\n(20-pair power is flat — worlds limit)",
            loc="left", fontsize=9)

for x in ax:
    x.spines[["top", "right"]].set_visible(False)
fig.savefig(os.path.join(HERE, "fig_prestudy.png"), dpi=160)
print("wrote fig_prestudy.png")

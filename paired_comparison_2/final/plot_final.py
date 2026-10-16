#!/usr/bin/env python3
"""Figure for the attempt-2 verdict of comparison No. 2."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

H = Path(__file__).resolve().parent.parent
rep = json.load(open(H / "f3_repair/results/repair_graded.json"))
gaps = json.load(open(H / "f3_repair/results_raw/repair_gaps.json"))["gaps"]
man = {c.get("name", c.get("id")): c
       for c in json.load(open(H / "inputs/manifest2.json"))["candidates"]}
att = json.load(open(H / "results/wire_attack_results.json"))
C_D, C_C = "#4C72B0", "#DD8452"
plt.rcParams.update({"font.size": 8})
fig, ax = plt.subplots(1, 4, figsize=(7.2, 2.1), constrained_layout=True)

a = ax[0]
for p in rep["pairs"]:
    d, c = p["dtde_first"], p["cedt_first"]
    if d is None and c is None:
        continue
    top = 11
    d = top if d is None else d
    c = top if c is None else c
    a.scatter(d, c, s=14, color=C_C if p["cedt_win"] else C_D)
a.plot([0, 11], [0, 11], color="0.6", lw=0.8)
a.set_xlabel("no sharing (DTDE)"); a.set_ylabel("broker (CEDT-P4)")
a.set_title("A  pc-nh to first qualifier", fontsize=8)
a.text(0.5, 10.2, "none found", fontsize=6, color="0.4")

a = ax[1]
for n, g in gaps.items():
    g1 = man[n].get("gap_1x1_ev")
    if g1 is None:
        continue
    a.scatter(g1, g["gap_ev"], s=14,
              color=C_C if "2H" in n and g["gap_ev"] - g1 > 0.1 else C_D)
a.plot([0, 2], [0, 2], color="0.6", lw=0.8)
a.axhspan(1, 2, color="0.9", zorder=0)
a.set_xlabel("1x1 PBE gap (eV)"); a.set_ylabel("8x8 PBE gap (eV)")
a.set_title("B  gap check", fontsize=8)

a = ax[2]
a.bar([0, 1], [rep["h_ratio_asrun"], rep["h_ratio_corrected"]], color=C_C,
      width=0.6)
a.axhline(1.05, color="k", lw=0.8, ls="--")
a.set_xticks([0, 1], ["as run", "F3 costs\nadded"]); a.set_ylim(0.9, 1.25)
a.set_title("C  labels per pc-nh ratio", fontsize=8)

a = ax[3]
arms = ["DTDE", "CEDT_P4"]
x = range(len(arms))
a.bar([i - 0.2 for i in x], [att[k]["identity_acc"] for k in arms],
      width=0.4, color=C_D, label="identity acc.")
a.bar([i + 0.2 for i in x], [att[k]["membership_auc"] for k in arms],
      width=0.4, color=C_C, label="membership AUC")
a.hlines(att["identity_limit"], -0.45, 1.0, color="k", lw=0.8, ls="--", zorder=3)
a.hlines(0.60, -0.05, 1.45, color=C_C, lw=0.8, ls="--")
a.set_xticks(list(x), ["DTDE", "CEDT-P4\n(masked)"])
a.set_ylim(0, 1.5); a.set_yticks([0, 0.5, 1.0]); a.legend(fontsize=6, frameon=False, loc="upper left", ncol=1, handlelength=1)
a.set_title("D  timing attack", fontsize=8)
fig.savefig(H / "final/fig_attempt2_verdict.png", dpi=200)

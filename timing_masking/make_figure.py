#!/usr/bin/env python3
"""Figure: leakage vs cost for the timing-masking clauses (real data)."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
d = json.load(open(HERE / "mask_results.json"))
sweep = d["sweep"]
q = [r for r in sweep if r["mask"] == "quant"]
p = [r for r in sweep if r["mask"] == "pad"]
base = [r for r in sweep if r["mask"] == "none"][0]

fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))

ax = axes[0]
qq = [r["param"] for r in q]
ax.plot(qq, [r["worst_identity_acc"] for r in q], "o-", color="#1f77b4",
        label="identity accuracy (worst arm)")
ax.plot(qq, [r["worst_membership_auc"] for r in q], "s-", color="#d62728",
        label="membership AUC (worst arm)")
ax.axhline(d["identity_limit"], ls="--", color="#1f77b4", lw=1,
           label=f"identity limit {d['identity_limit']:.3f}")
ax.axhline(d["membership_auc_limit"], ls="--", color="#d62728", lw=1,
           label="membership limit 0.60")
ax2 = ax.twinx()
ax2.plot(qq, [100 * r["cost_inflation"] for r in q], "^:", color="gray",
         label="cost inflation %")
ax2.set_ylabel("compute/latency inflation (%)", color="gray")
ax2.set_yscale("log")
ax.set_xscale("log")
ax.set_xlabel("quantization / batching period q (s)")
ax.set_ylabel("attack success")
ax.set_title("Quantized durations (= batched returns)")
ax.legend(fontsize=7, loc="center left")

ax = axes[1]
pts = [(base, "none")] + [(r, f"p{r['param']}") for r in p]
for r, lab in pts:
    ok = r["identity_pass"] and r["membership_pass"]
    ax.scatter(100 * r["cost_inflation"], r["worst_identity_acc"],
               c="#2ca02c" if ok else "#d62728", s=60, zorder=3)
    ax.annotate(lab, (100 * r["cost_inflation"], r["worst_identity_acc"]),
                textcoords="offset points", xytext=(6, 4), fontsize=8)
# stratified padding reference point (computed in RESULTS.md):
ax.scatter(62.1, 1 / 14, c="orange", marker="x", s=70, zorder=3)
ax.annotate("stratified p99\n(breaches phase limit)", (62.1, 1 / 14),
            textcoords="offset points", xytext=(6, 4), fontsize=7,
            color="orange")
ax.axhline(d["identity_limit"], ls="--", color="#1f77b4", lw=1)
ax.set_xlabel("real node-time inflation (%)")
ax.set_ylabel("identity accuracy (worst arm)")
ax.set_title("Class-constant padding")
fig.suptitle("Pricing timing-masking clauses on the real 480-call wire log"
             " (jobs 1919944/1919945)", fontsize=11)
fig.tight_layout()
fig.savefig(HERE / "fig_timing_masking.png", dpi=140)
print("wrote fig_timing_masking.png")

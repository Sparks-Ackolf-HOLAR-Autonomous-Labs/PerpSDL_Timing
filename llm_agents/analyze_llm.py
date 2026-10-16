#!/usr/bin/env python3
"""Analyze the LLM-agents-with-tools grid vs the scripted control.

Paired per (card, world, seed, condition): delta = llm - scripted on each
utility metric. Also aggregates the tool-usage telemetry: which algorithms
the agents invoked/delegated to (and with what parameters), how often they
overrode a tool's suggestion, and the parse-fallback rate.
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
METRICS = ["qual_count", "found", "nh_first", "labels_per_nh", "fail_rate",
           "memfail_rate", "validity", "nh_used", "rounds"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="results/llm_grid_raw.json")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    suffix = f"_{args.tag}" if args.tag else ""
    d = json.load(open(HERE / args.raw))
    recs = d["records"]
    by_key = defaultdict(dict)
    for r in recs:
        by_key[(r["card"], r["world"], r["seed"], r["condition"])][r["arm"]] = r

    conds = sorted({k[3] for k in by_key})
    summary = {}
    for cond in conds:
        pairs = [(v["scripted"], v["llm"]) for k, v in by_key.items()
                 if k[3] == cond and "scripted" in v and "llm" in v]
        row = {"n_pairs": len(pairs)}
        for m in METRICS:
            s = np.array([p[0][m] for p in pairs])
            l = np.array([p[1][m] for p in pairs])
            delta = l - s
            row[m] = dict(scripted=float(s.mean()), llm=float(l.mean()),
                          delta_mean=float(delta.mean()),
                          delta_se=float(delta.std(ddof=1)
                                         / np.sqrt(max(len(delta), 2))),
                          llm_wins=int((delta > 0).sum()),
                          ties=int((delta == 0).sum()))
        summary[cond] = row

    # telemetry aggregation
    tel_tot = defaultdict(Counter)
    deleg_choices = {"R": Counter(), "H": Counter()}
    n_camp = 0
    for r in recs:
        if r["arm"] != "llm":
            continue
        n_camp += 1
        t = r["telemetry"]
        for role in ("R", "H"):
            tel_tot["llm_calls"][role] += t["llm_calls"][role]
            for k in ("delegated", "fallbacks", "auto_accepts", "overrides",
                      "tool_informed", "direct"):
                tel_tot[k][role] += t[k][role]
            deleg_choices[role].update(t["delegate_choices"][role])
        tel_tot["tool_calls"].update(t["tool_calls"])

    decisions = {r: tel_tot["tool_informed"][r] + tel_tot["direct"][r]
                 + tel_tot["fallbacks"][r] + tel_tot["auto_accepts"][r]
                 for r in ("R", "H")}
    telemetry = dict(
        n_llm_campaigns=n_camp,
        llm_calls=dict(tel_tot["llm_calls"]),
        interactive_tool_calls=dict(tel_tot["tool_calls"]),
        delegated_rounds=dict(tel_tot["delegated"]),
        llm_decisions=decisions,
        tool_informed=dict(tel_tot["tool_informed"]),
        direct_decisions=dict(tel_tot["direct"]),
        overrides=dict(tel_tot["overrides"]),
        fallbacks=dict(tel_tot["fallbacks"]),
        auto_accepts=dict(tel_tot["auto_accepts"]),
        delegate_choices={r: dict(c.most_common()) for r, c in
                          deleg_choices.items()})

    out = dict(config=dict(budget=d["budget"], rounds=d["rounds"],
                           model=d["model"]),
               summary=summary, telemetry=telemetry)
    with open(HERE / "results" / f"llm_grid_summary{suffix}.json", "w") as fh:
        json.dump(out, fh, indent=1)

    for cond in conds:
        row = summary[cond]
        print(f"\n== {cond} (n={row['n_pairs']} pairs)")
        for m in METRICS:
            r = row[m]
            print(f"  {m:14s} scripted={r['scripted']:8.3f} "
                  f"llm={r['llm']:8.3f} delta={r['delta_mean']:+8.3f} "
                  f"(se {r['delta_se']:.3f})")
    print("\n== telemetry")
    print(json.dumps(telemetry, indent=1))

    # figure
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 3, figsize=(13, 4))
        show = [("labels_per_nh", "valid F2+ labels / nh"),
                ("nh_first", "nh to first qualifier"),
                ("fail_rate", "failure rate")]
        x = np.arange(len(conds))
        for ax, (m, title) in zip(axes, show):
            sv = [summary[c][m]["scripted"] for c in conds]
            lv = [summary[c][m]["llm"] for c in conds]
            se = [summary[c][m]["delta_se"] for c in conds]
            ax.bar(x - 0.18, sv, 0.36, label="scripted", color="#888")
            ax.bar(x + 0.18, lv, 0.36, yerr=se, label="LLM+tools",
                   color="#2b7bba")
            ax.set_xticks(x)
            ax.set_xticklabels(conds, rotation=20)
            ax.set_title(title)
        axes[0].legend()
        fig.suptitle("LLM agents with tools vs scripted policies "
                     "(paired worlds/seeds, simulated units)")
        fig.tight_layout()
        fig.savefig(HERE / "results" / f"llm_vs_scripted{suffix}.png", dpi=140)
        print("figure written")
    except ImportError:
        print("matplotlib unavailable; skipped figure")


if __name__ == "__main__":
    main()

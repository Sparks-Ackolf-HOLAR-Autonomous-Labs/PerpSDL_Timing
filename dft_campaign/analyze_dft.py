#!/usr/bin/env python3
"""Summarize actual-DFT campaign outcomes (results/outcomes.jsonl).

Produces results/DFT_RESULTS.md: per-candidate table (relaxed a, max
force, screening gap, qualifier flag, phonon check, cost columns), the
1T-2H energy difference per composition (E per formula unit, only within
a composition — never across), and campaign cost totals.
"""
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
RES = HERE / "results"
RY_EV = 13.605693122994


def load():
    recs = {}
    with open(RES / "outcomes.jsonl") as fh:
        for line in fh:
            r = json.loads(line)
            recs[r["candidate"]] = r  # later lines override (F4 update)
    return list(recs.values())


def fu_energy(rec):
    f2 = rec["stages"].get("F2", {})
    e = f2.get("etot_ry")
    if e is None:
        return None
    nfu = 2 if rec["phase"] == "2H" else 1
    return e / nfu


def main():
    recs = load()
    recs.sort(key=lambda r: (r["metal"], r["chalcogen"], r["phase"]))
    lines = ["# Actual-DFT campaign results (auto-generated)", "",
             "PBE screening quantities only; Gamma phonons are not a",
             "dynamical-stability proof; energies are never compared",
             "across compositions.", "",
             "| candidate | F2 conv | a_rel (Å) | max |F| (Ry/au) | gap (eV) | qualifier | Γ-phonon min (cm⁻¹) | restarts | fails | node-h |",
             "| --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |"]
    tot_nh = tot_calls = 0.0
    for r in recs:
        f2 = r["stages"].get("F2", {})
        f3 = r["stages"].get("F3", {})
        f4 = r["stages"].get("F4", {})
        nh = sum(s.get("node_hours", 0) or 0 for s in r["stages"].values()
                 if isinstance(s, dict))
        tot_nh += nh
        gap = f3.get("gap_ev")
        gap_s = ("metallic" if f3.get("metallic")
                 else (f"{gap:.3f}" if gap is not None else "—"))
        minf = f4.get("min_freq_cm1")
        ph_s = (f"{minf:.1f}" + (" ⚠️unstable" if f4.get("gamma_unstable")
                                 else "")) if minf is not None else "—"
        lines.append(
            f"| {r['candidate']} | {'✓' if f2.get('relax_converged') else '✗'} "
            f"| {r.get('a_relaxed_angstrom', '—')} "
            f"| {f2.get('total_force_ry_au', '—')} | {gap_s} "
            f"| {'**yes**' if r.get('qualifier') else 'no'} | {ph_s} "
            f"| {r['restarts']} | {r['failures']} | {nh:.2f} |")

    lines += ["", "## 1T–2H energy difference per composition", "",
              "E(1T) − E(2H) per MX2 formula unit, in eV (negative = 1T",
              "favored at PBE with these GBRV pseudos):", "",
              "| composition | ΔE(1T−2H) (eV/f.u.) |", "| --- | ---: |"]
    comp = defaultdict(dict)
    for r in recs:
        e = fu_energy(r)
        if e is not None:
            comp[r["metal"] + r["chalcogen"] + "2"][r["phase"]] = e
    for c in sorted(comp):
        d = comp[c]
        if "1T" in d and "2H" in d:
            lines.append(f"| {c} | {(d['1T'] - d['2H']) * RY_EV:+.3f} |")

    summ = {}
    sp = RES / "campaign_summary.json"
    if sp.exists():
        summ = json.load(open(sp))
    lines += ["", "## Campaign cost (measured, real node-hours)", "",
              f"- candidates completed: {len(recs)} / 30",
              f"- qualifiers (gap 1.0–2.0 eV): "
              f"{[r['candidate'] for r in recs if r.get('qualifier')]}",
              f"- total node-hours (Σ wall × cores/64): {tot_nh:.2f}"
              + (f" (driver total {summ.get('total_node_hours')})" if summ else ""),
              f"- QE calls: {summ.get('qe_calls', '—')}, "
              f"budget cap hit: {summ.get('budget_cap_hit', '—')}, "
              f"wall hours: {summ.get('wall_hours', '—')}"]
    (RES / "DFT_RESULTS.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[-6:]))


if __name__ == "__main__":
    main()

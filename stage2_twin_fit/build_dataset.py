#!/usr/bin/env python3
"""Build the Stage-2 twin-fit dataset from the measured DFT campaign.

One row per QE call (the deduplicated final record per candidate/stage,
plus retry calls are not separately recoverable — outcomes.jsonl keeps
the *last* call per stage, so restart-inflated walls are flagged via the
record's restart count). Adds SOC calls when soc_outcomes.jsonl exists.

Columns: candidate, stage, exe, nelec, nat, kgrid, nk (=kgrid^2),
ecut_ry, soc, restarts_at_stage, wall_s, node_hours, mem_gb.
"""
import csv
import json
from pathlib import Path

HERE = Path(__file__).parent
MPT = HERE.parent

STAGE_META = {   # stage -> (exe, kgrid, ecut)
    "F1": ("pw_scf", 6, 40.0), "F2": ("pw_vcrelax", 12, 45.0),
    "F3": ("pw_nscf", 18, 45.0), "F4SCF": ("pw_scf", 12, 45.0),
    "F4": ("ph_gamma", 1, 45.0),
    "SOC_SCF": ("pw_scf_soc", 12, 60.0), "SOC_NSCF": ("pw_nscf_soc", 18, 60.0),
}


def latest_records(path):
    latest = {}
    for line in open(path):
        r = json.loads(line)
        latest[r["candidate"]] = r
    return latest


def main():
    cands = {m["name"]: m for m in json.load(
        open(MPT / "prior_predictive" / "candidates" / "candidates.json"))}
    rows = []

    def add(recs, soc):
        for name, r in sorted(recs.items()):
            nat = cands[name]["atoms_per_cell"]
            nelec = None
            for st in ("F2", "F1", "SOC_SCF"):
                v = r["stages"].get(st, {}).get("nelec")
                if v:
                    nelec = v
                    break
            for st, d in r["stages"].items():
                if d.get("skipped") or "wall_s" not in d:
                    continue
                exe, kgrid, ecut = STAGE_META[st]
                if st == "F4":   # ph.x record may embed the pre-SCF
                    pass
                rows.append(dict(
                    candidate=name, stage=st, exe=exe,
                    nelec=d.get("nelec") or nelec, nat=nat,
                    kgrid=kgrid, nk=kgrid * kgrid, ecut_ry=ecut,
                    soc=int(soc or st.startswith("SOC")),
                    restarts=r.get("restarts", 0),
                    wall_s=d["wall_s"], node_hours=d["node_hours"],
                    mem_gb=d.get("peak_rank_rss_gb")))

    add(latest_records(MPT / "dft_campaign" / "results" / "outcomes.jsonl"),
        soc=False)
    socf = MPT / "dft_campaign" / "soc" / "results" / "soc_outcomes.jsonl"
    if socf.exists():
        add(latest_records(socf), soc=True)

    out = HERE / "qe_calls.csv"
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Backfill F4 Gamma-phonon frequencies into results/ from the fetched raw
ph.x outputs (results/f4_outputs/*_f4.out).

The launching run's parser missed the '[THz] =' segment of QE's freq lines,
so F4 records carried freqs_cm1: null despite ph.x completing. This re-parses
with the fixed regex from run_campaign.py and rewrites outcomes.jsonl,
campaign_summary.json, and each record's gamma fields in place.
"""
import json, re
from pathlib import Path

HERE = Path(__file__).parent
RES = HERE / "results"
FREQ_RE = re.compile(
    r"freq \(\s*\d+\) =\s*-?[\d.]+\s*\[THz\] =\s*(-?[\d.]+)\s*\[cm-1\]")

f4 = {}
for out in sorted((RES / "f4_outputs").glob("*_f4.out")):
    cand = out.name[: -len("_f4.out")]
    freqs = [float(x) for x in FREQ_RE.findall(out.read_text(errors="replace"))]
    if freqs:
        f4[cand] = {
            "freqs_cm1": freqs,
            "min_freq_cm1": min(freqs),
            # tolerance: acoustic modes at Gamma sit near 0 numerically
            "gamma_unstable": min(freqs) < -30.0,
        }

def patch(rec):
    st = rec.get("stages", {}).get("F4")
    if st and rec["candidate"] in f4:
        st.update(f4[rec["candidate"]])
        return True
    return False

n = 0
lines = []
for line in (RES / "outcomes.jsonl").read_text().splitlines():
    rec = json.loads(line)
    n += patch(rec)
    lines.append(json.dumps(rec))
(RES / "outcomes.jsonl").write_text("\n".join(lines) + "\n")

summ = json.loads((RES / "campaign_summary.json").read_text())
m = sum(patch(rec) for rec in summ.get("records", []))
(RES / "campaign_summary.json").write_text(json.dumps(summ, indent=1))
print(f"patched {n} outcome lines, {m} summary records; "
      f"unstable: {[c for c, d in f4.items() if d['gamma_unstable']] or 'none'}")

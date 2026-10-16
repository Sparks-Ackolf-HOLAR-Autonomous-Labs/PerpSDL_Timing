#!/usr/bin/env python3
"""Preregistered analysis for the live CEDT-P4 vs DTDE comparison
(committed BEFORE submission per the stopping rule; no post-hoc metric
changes).

Inputs: results/campaigns.jsonl (one row per campaign) fetched from
granite. Grading, frozen 2026-09-09:

  R (PW60): CEDT-P4 beats DTDE on nh-to-first-qualifier in >= 0.60 of
     the paired seeds (a campaign that finds no qualifier scores its
     total nh spend as nh_first, i.e. worst case); one-sided sign test
     p-value reported at alpha = 0.05.
  H (package): valid F2+ labels per node-hour >= 1.05x DTDE (pooled);
     failure rate <= DTDE + 0.04.

Timing-channel and membership attacks run separately on
results/wire_log.jsonl via ../measured_attacks/ (accept-and-measure).
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).parent


def load():
    rows = [json.loads(x) for x in
            open(HERE / "results" / "campaigns.jsonl")]
    by = {}
    for r in rows:
        by[(r["arm"], r["seed"])] = r
    return by


def main():
    by = load()
    seeds = sorted({s for (_, s) in by})
    pairs = [(by[("DTDE", s)], by[("CEDT_P4", s)]) for s in seeds
             if ("DTDE", s) in by and ("CEDT_P4", s) in by]
    if not pairs:
        sys.exit("no complete pairs")
    wins = 0
    print(f"{'seed':>4} {'DTDE nh_first':>13} {'CEDT nh_first':>13} "
          f"{'winner':>8}")
    for d, c in pairs:
        nd = d["nh_first_qual"] if d["nh_first_qual"] is not None else d["nh"]
        nc = c["nh_first_qual"] if c["nh_first_qual"] is not None else c["nh"]
        win = nc < nd
        wins += win
        print(f"{d['seed']:>4} {nd:>13.3f} {nc:>13.3f} "
              f"{'CEDT' if win else 'DTDE':>8}")
    n = len(pairs)
    pw = wins / n
    # one-sided sign test P(X >= wins | p=0.5)
    p = sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n
    dl = sum(d["labels_f2"] for d, _ in pairs)
    dn = sum(d["nh"] for d, _ in pairs)
    cl = sum(c["labels_f2"] for _, c in pairs)
    cn = sum(c["nh"] for _, c in pairs)
    lr = (cl / cn) / (dl / dn) if dl and cn else float("nan")
    df = sum(d["fails"] for d, _ in pairs) / max(
        sum(d["calls"] for d, _ in pairs), 1)
    cf = sum(c["fails"] for _, c in pairs) / max(
        sum(c["calls"] for _, c in pairs), 1)
    r_pass = pw >= 0.60
    h_pass = lr >= 1.05 and cf <= df + 0.04
    out = dict(n_pairs=n, pw_rate=pw, sign_test_p=p, r_pass=bool(r_pass),
               labels_per_nh_ratio=lr, fail_dtde=df, fail_cedt=cf,
               h_pass=bool(h_pass),
               preregistered_success=bool(r_pass and h_pass))
    print(json.dumps(out, indent=1))
    json.dump(out, open(HERE / "results" / "live_grading.json", "w"),
              indent=1)


if __name__ == "__main__":
    main()

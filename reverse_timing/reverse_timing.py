"""Reverse of the timing attack: predict a job's wall time from the compound.

Forward attack (measured): wall time -> compound identity (96 % on comparison No. 1).
Reverse question: compound -> expected wall time, before the job runs.
Three predictors, all graded on the 480 real QE calls of live comparison No. 1
(3x3 supercells, granite grn061), per (stage, ranks, pools) execution setting:
  A. repeat:      the compound was run before; predict its mean from other seeds.
  B. 1x1 probe:   only the low-cost 1x1 campaign (dft_campaign) was run for it;
                  log-linear transfer fitted on the other compounds.
  C. descriptors: never run; log-linear in electron count, atom count, phase,
                  metal row and chalcogen, fitted leave-one-compound-out.
"""
import json, collections, statistics as st, math, sys
import numpy as np

HERE = sys.argv[1] if len(sys.argv) > 1 else "."
BASE = HERE + "/.."
rows = []
for l in open(BASE + "/paired_comparison_1/results/campaigns.jsonl"):
    rows += [j for j in json.loads(l)["jobs"] if j["ok"] and j.get("converged")]
d = collections.defaultdict(list)
for j in rows:
    d[(j["cls"], j["ranks"], j["npool"], j["candidate"])].append(j["wall_s"])

probe = {}
for l in open(BASE + "/dft_campaign/results/outcomes.jsonl"):
    o = json.loads(l)
    f1 = o["stages"].get("F1", {})
    if f1.get("ok") and f1.get("wall_s"):
        probe[o["candidate"]] = (f1["wall_s"], f1.get("nelec"))

VAL = {"S": 6, "Se": 6, "Te": 6, "Ti": 4, "Zr": 12, "Hf": 26, "Mo": 14, "W": 28}  # GBRV valence
ROW = {"Ti": 4, "Zr": 5, "Hf": 6, "Mo": 5, "W": 6}
def desc(c):
    m, rest = c.split("_")[0], c.split("_")[1]
    met = m[:2] if m[:2] in ROW else m[:1]
    ch = m[len(met):-1]
    nat = 27 if rest == "1T" else 54
    ne = (nat // 3) * (VAL[met] + 2 * VAL[ch])
    return [1.0, math.log(ne), float(rest == "2H"), ROW[met] - 5.0,
            float(ch == "Se"), float(ch == "Te"), float(met in ("Mo", "W"))]

def loo(X, y):
    X, y = np.array(X), np.array(y); out = []
    for i in range(len(y)):
        m = np.arange(len(y)) != i
        b, *_ = np.linalg.lstsq(X[m], y[m], rcond=None)
        out.append(float(X[i] @ b))
    return np.array(out)

res = {}
settings = sorted({k[:3] for k in d})
for s in settings:
    cands = sorted(c for (a, b, e, c) in d if (a, b, e) == s)
    mean = {c: st.mean(d[s + (c,)]) for c in cands}
    # A: repeat-run error (each run predicted by the mean of the others)
    errA = [abs(x - st.mean([z for k, z in enumerate(v) if k != i])) / x
            for c in cands for v in [d[s + (c,)]] if len(v) > 1 for i, x in enumerate(v)]
    y = np.log([mean[c] for c in cands])
    pc = [c for c in cands if c in probe]
    errB = np.abs(np.exp(loo([[1, math.log(probe[c][0])] for c in pc],
                             np.log([mean[c] for c in pc]))) / np.array([mean[c] for c in pc]) - 1)
    errC = np.abs(np.exp(loo([desc(c) for c in cands], y)) / np.exp(y) - 1)
    # how many compounds sit within the repeat scatter of each other (timing collisions)
    srt = sorted(mean.values()); gaps = np.diff(np.log(srt))
    res["%s_r%d_nk%d" % s] = dict(
        n_compounds=len(cands), range_s=[round(srt[0], 1), round(srt[-1], 1)],
        A_repeat_median_pct=round(100 * st.median(errA), 2),
        B_probe_median_pct=round(100 * float(np.median(errB)), 1),
        C_descriptor_median_pct=round(100 * float(np.median(errC)), 1),
        C_descriptor_p90_pct=round(100 * float(np.percentile(errC, 90)), 1),
        median_neighbour_gap_pct=round(100 * float(np.median(gaps)), 2),
        per_compound_mean_s={c: round(mean[c], 1) for c in cands})
json.dump(res, open(HERE + "/reverse_timing_results.json", "w"), indent=1)
for k, v in res.items():
    print(k, {a: b for a, b in v.items() if a != "per_compound_mean_s"})

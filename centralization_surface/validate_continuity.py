import sys, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path("../prior_predictive").resolve())); sys.path.insert(0, ".")
import simulator as S
import surface as SF

# Validate corners vs native arms + interior smoothness, P4 level.
LEVEL = "P4"
cards = ["base","strong_coupling","adversarial"]
NW = 40
def agg_native(topo, level):
    lp=[]; ww=[]
    for i in range(NW):
        w = S.sample_world(cards[i%3], i)
        c = S.Contract(level, 4.0)
        r = S.run_campaign(w, topo, c)
        lp.append(r["labels_per_nh"].mean())
    return np.mean(lp)
def agg_mix(tau, eps, level):
    lp=[]
    for i in range(NW):
        w = S.sample_world(cards[i%3], i)
        r = SF.run_mix(w, tau, eps, level)
        lp.append(r["labels_per_nh"].mean())
    return np.mean(lp)

print("=== corner reproduction (labels/nh, P4) ===")
for name,(tau,eps),topo in [("DTDE",(0,0),"DTDE"),("CEDT",(0,1),"CEDT"),("CTDE",(1,0),"CTDE")]:
    m = agg_mix(tau,eps,LEVEL); n = agg_native(topo,LEVEL)
    d = 100*abs(m-n)/max(abs(n),1e-9)
    print(f"  {name:5s} mix={m:.4f} native={n:.4f}  diff={d:.2f}%")

print("=== interior gradient in eps at tau=0 (P4 labels_ratio proxy) ===")
base4 = None
row=[]
for eps in np.linspace(0,1,6):
    lp=[]
    for i in range(NW):
        w=S.sample_world(cards[i%3],i)
        r=SF.run_mix(w,0.0,round(float(eps),3),LEVEL)
        lp.append(r["labels_per_nh"].mean())
    row.append(np.mean(lp))
print("  eps:", [f"{e:.1f}" for e in np.linspace(0,1,6)])
print("  lpnh:", [f"{v:.4f}" for v in row])
# check monotone-ish & no single dominating jump
diffs=np.diff(row)
print("  step diffs:", [f"{d:+.4f}" for d in diffs])

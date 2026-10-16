"""Grade station_raw.json against the registered predictions S1-S7.

python analyze.py results/station_raw.json results/
"""
import json, sys, os
import numpy as np

raw = json.load(open(sys.argv[1]))
out = sys.argv[2]
res, conds, grid = raw['res'], raw['conds'], raw['grid']
W = len(res)
BASE = 'P2_t0.0_e0.0'
ABS_ID = 0.125 + 0.05


def arr(cond, key):
    return np.array([[s[key] for s in r['conds'][cond]] for r in res], dtype=float)


delta = np.array([r['delta'] for r in res])
gtrue = np.array([r['g'] for r in res])
b_first = arr(BASE, 'first0')
b_fur = arr(BASE, 'films').sum(1) / arr(BASE, 'fur_h').sum(1)
b_dep = arr(BASE, 'good_dep').sum(1) / arr(BASE, 'dep_h').sum(1)
b_id = {k: np.nanmean(arr(BASE, k), 1) for k in ('id_f', 'id_d', 'id_join')}


def corr(a, b):
    if np.std(a) < 1e-9 or np.std(b) < 1e-9:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def grade(cond):
    f = arr(cond, 'first0')
    win = np.where(f < b_first, 1.0, np.where(f == b_first, 0.5, 0.0)).mean(1)
    hf = (arr(cond, 'films').sum(1) / arr(cond, 'fur_h').sum(1)) / b_fur
    hd = (arr(cond, 'good_dep').sum(1) / arr(cond, 'dep_h').sum(1)) / b_dep
    ids = {k: np.nanmean(arr(cond, k), 1) for k in ('id_f', 'id_d', 'id_join')}
    dh = np.array([np.mean([s['d_hat0'] for s in r['conds'][cond]]) for r in res])
    gh = np.array([np.mean([s['g_hat0'] for s in r['conds'][cond]], 0) for r in res])
    c_delta, c_g = corr(dh, delta), corr(gh.ravel(), gtrue.ravel())
    gains = (win >= 0.6) & (hf >= 1.05) & (hd >= 1.05)
    reb = np.all([ids[k] - b_id[k] <= 0.05 for k in ids], 0)
    ab = np.all([ids[k] <= ABS_ID for k in ids], 0)
    ext_ok = (abs(c_delta) <= 0.2) and (abs(c_g) <= 0.2)
    fin = np.isfinite(f).mean(1)
    med_first = float(np.median(np.where(np.isfinite(f), f, np.nan)[np.isfinite(f)]))
    return dict(
        pw60=float((win >= 0.6).mean()), mean_win=float(win.mean()),
        h_fur_ratio=float(np.median(hf)), p_hfur=float((hf >= 1.05).mean()),
        h_dep_ratio=float(np.median(hd)), p_hdep=float((hd >= 1.05).mean()),
        id_f=float(ids['id_f'].mean()), id_d=float(ids['id_d'].mean()), id_join=float(ids['id_join'].mean()),
        p_idf_over_abs=float((ids['id_f'] > ABS_ID).mean()),
        corr_delta=c_delta, corr_g=c_g,
        med_first_h=med_first, p_film=float(fin.mean()),
        winwin_rebased=float((gains & reb).mean()) * ext_ok,
        winwin_rebased_no_extraction=float((gains & reb).mean()),
        winwin_absolute=float((gains & ab).mean()) * ext_ok,
        films_per_campaign=float(arr(cond, 'films').mean()))


G = {c: grade(c) for c in conds}
json.dump(dict(worlds=W, seeds=raw['seeds'], grid=grid, graded=G), open(os.path.join(out, 'station_summary.json'), 'w'), indent=1)

g = lambda P, t, e: G[f'{P}_t{t:.1f}_e{e:.1f}']
pred = {}
s1 = 1 - g('P2', 1, 0)['med_first_h'] / g('P2', 0, 0)['med_first_h']
pred['S1'] = dict(value=round(s1, 3), rule='>= 0.10', pass_=bool(s1 >= 0.10))
pred['S2'] = dict(value=g('P3', 0, 1)['p_hfur'], rule='>= 0.80', pass_=g('P3', 0, 1)['p_hfur'] >= 0.8)
mn = min(v['p_idf_over_abs'] for v in G.values())
pred['S3'] = dict(value=round(mn, 3), rule='min over arms of P(id_f > 0.175) >= 0.95', pass_=mn >= 0.95)
d_id = g('P2', 0, 0)['id_f'] - G['var_amp1_menu0_e0']['id_f']
gain_open = G['var_amp0_menu50_e1']['h_fur_ratio'] if False else g('P2', 0, 1)['h_fur_ratio']
gain_amp = G['var_amp1_menu0_e1']['h_fur_ratio'] / G['var_amp1_menu0_e0']['h_fur_ratio']
pred['S4'] = dict(value=dict(id_drop=round(d_id, 3), cofire_gain_open=round(gain_open, 3), cofire_gain_ampoule=round(gain_amp, 3)),
                  rule='id drop >= 0.15 and ampoule gain > open gain', pass_=bool(d_id >= 0.15 and gain_amp > gain_open))
b = G[BASE]
pred['S5'] = dict(value=dict(furnace=round(b['id_f'], 3), deposition=round(b['id_d'], 3), join=round(b['id_join'], 3)),
                  rule='each alone <= 0.60, join >= 0.85', pass_=bool(b['id_f'] <= 0.6 and b['id_d'] <= 0.6 and b['id_join'] >= 0.85))
c2, c3 = g('P2', 1, 0)['corr_delta'], g('P3', 1, 0)['corr_delta']
pred['S6'] = dict(value=dict(P2=round(c2, 3), P3=round(c3, 3), DTDE=round(b['corr_delta'], 3)),
                  rule='P2 >= 0.5 and P3 >= 0.2', pass_=bool(c2 >= 0.5 and c3 >= 0.2))
mx_abs = max(v['winwin_absolute'] for v in G.values())
mx_reb0 = max(G[c]['winwin_rebased'] for c in conds if '_t0.0_' in c)
pred['S7'] = dict(value=dict(max_absolute=mx_abs, max_rebased_tau0=mx_reb0),
                  rule='absolute = 0 everywhere and rebased tau=0 max >= 0.5', pass_=bool(mx_abs == 0 and mx_reb0 >= 0.5))
for k in pred:
    pred[k]['pass_'] = bool(pred[k]['pass_'])
json.dump(pred, open(os.path.join(out, 'predictions_graded.json'), 'w'), indent=1)
print(json.dumps(pred, indent=1))

"""Shared growth stations (sputter deposition line + tube furnace), simulated.

Registered 14 Oct 2026. Design and registered predictions:
DESIGN_AND_PREDICTION.md (committed before this file). All station parameters
are assumed values; only the gap-window composition list is measured.

Run:  python station_sim.py --worlds 80 --seeds 10 --procs 6 --out results/
"""
import argparse, json, os, time
from multiprocessing import Pool
import numpy as np

COMPS = ['MoS2', 'WS2', 'MoSe2', 'WSe2', 'MoTe2', 'WTe2', 'ZrS2', 'HfS2']
M_OF = {'MoS2': 'Mo', 'WS2': 'W', 'MoSe2': 'Mo', 'WSe2': 'W', 'MoTe2': 'Mo',
        'WTe2': 'W', 'ZrS2': 'Zr', 'HfS2': 'Hf'}
X_OF = {c: c[len(M_OF[c]):-1] for c in COMPS}
METALS = ['Mo', 'W', 'Zr', 'Hf']
BASE = {'S': 850.0, 'Se': 750.0, 'Te': 600.0}
SHIFT = {'Mo': 0.0, 'W': 60.0, 'Zr': -30.0, 'Hf': -10.0}
LIT = np.array([BASE[X_OF[c]] + SHIFT[M_OF[c]] for c in COMPS])
WIN = np.array([25.0 if X_OF[c] == 'Te' else 40.0 for c in COMPS])
CI = np.array([METALS.index(M_OF[c]) for c in COMPS])
XI = np.array([['S', 'Se', 'Te'].index(X_OF[c]) for c in COMPS])
K_X = np.array([np.sum(XI == XI[i]) for i in range(8)])
K_M = np.array([np.sum(CI == CI[i]) for i in range(8)])

SD_TSTAR, SD_DELTA, SD_G = 40.0, 25.0, 0.12
P_FUR, P_DEP, TOL_DEP, MEAS = 0.9, 0.95, 0.08, 0.02
CAP, COFIRE_TOL = 4, 20.0
CHANGE_H, DEP_H, SEAL_H = 2.0, 0.5, 0.5
N_G, BOATS, ROUNDS, BUDGET, MAX_FAIL, LIST_LEN = 4, 2, 30, 250.0, 6, 5
TOFF = np.arange(-160.0, 161.0, 5.0)          # T* grid offsets from LIT
DG = np.arange(-80.0, 81.0, 5.0)              # delta grid
LOG_PT0 = -0.5 * (TOFF / SD_TSTAR) ** 2
LOG_PD0 = -0.5 * (DG / SD_DELTA) ** 2
ATT_SD = 50.0                                 # attacker's spread around LIT


def run_hours(T):
    return T / 300.0 + 1.0 + T / 150.0


def p_fur(diff, w):
    return P_FUR * np.exp(-0.5 * (diff / w) ** 2)


def p_dep(ratio):
    return P_DEP * np.exp(-0.5 * ((ratio - 1.0) / TOL_DEP) ** 2)


def norm_log(v):
    v = v - v.max()
    return v - np.log(np.exp(v).sum())


def draw_world(w):
    r = np.random.default_rng([w, 999])
    tstar = LIT + r.normal(0, SD_TSTAR, 8)
    delta = r.normal(0, SD_DELTA)
    g = 1.0 + r.normal(0, SD_G, 4)
    lists = [list(r.permutation(8)[:LIST_LEN]) for _ in range(N_G)]
    return dict(tstar=tstar, delta=delta, g=g, lists=lists)


class Group:
    def __init__(self, ctce=False, world=None):
        self.logT = np.tile(LOG_PT0, (8, 1))
        self.logD = LOG_PD0.copy()
        self.gm = np.ones(4)
        self.gp = np.full(4, 1.0 / SD_G ** 2)
        if ctce:
            self.logD = np.where(np.abs(DG - world['delta']) == np.abs(DG - world['delta']).min(), 0.0, -1e9)
            self.gm = world['g'].copy(); self.gp[:] = 1e9

    def obs_self(self, c, s, y, wt=1.0):
        Tact = s + DG[None, :] - (LIT[c] + TOFF)[:, None]
        p = p_fur(Tact, WIN[c])
        L = np.log(np.clip(p if y else 1 - p, 1e-12, None)) * wt
        J = self.logT[c][:, None] + self.logD[None, :] + L
        J = np.exp(J - J.max())
        self.logT[c] = norm_log(np.log(J.sum(1) + 1e-300))
        self.logD = norm_log(np.log(J.sum(0) + 1e-300))

    def obs_brok(self, c, Tact, y, wt=1.0):
        p = p_fur(Tact - (LIT[c] + TOFF), WIN[c])
        self.logT[c] = norm_log(self.logT[c] + wt * np.log(np.clip(p if y else 1 - p, 1e-12, None)))

    def obs_g(self, m, gobs, sd):
        prec = 1.0 / sd ** 2
        self.gm[m] = (self.gm[m] * self.gp[m] + gobs * prec) / (self.gp[m] + prec)
        self.gp[m] += prec

    def sample(self, c, uT, uD):
        pT = np.exp(self.logT[c]); pD = np.exp(self.logD)
        t = LIT[c] + TOFF[min(np.searchsorted(np.cumsum(pT), uT), len(TOFF) - 1)]
        d = DG[min(np.searchsorted(np.cumsum(pD), uD), len(DG) - 1)]
        return t, d

    def delta_hat(self):
        return float((np.exp(self.logD) * DG).sum())


def campaign(world, w, seed, tau, eps, P, ampoule=False, menu=0, ctce=False):
    r = np.random.default_rng([w, seed, 7])
    sh = (ROUNDS, N_G, BOATS)
    U = {k: r.random(sh) for k in ('eps', 'tau', 'uT', 'uD', 'dep', 'fur')}
    NM = r.normal(0, 1, sh)
    ORD = np.array([r.permutation(N_G) for _ in range(ROUNDS)])
    if ctce:
        tau, eps, P = 1.0, 1.0, 'P2'
    G = [Group(ctce, world) for _ in range(N_G)]
    ptr = [0] * N_G; fails = [0] * N_G; spend = np.zeros(N_G)
    first = np.full(N_G, np.inf); films = np.zeros(N_G)
    fur_h = dep_h = 0.0; good_dep = 0; mounted = -1
    flog, dlog = [], []          # (true c, X key, temp seen by operator) / (true c)
    delta, g, ts = world['delta'], world['g'], world['tstar']
    for rd in range(ROUNDS):
        jobs = []
        for gi in range(N_G):
            L = world['lists'][gi]
            if ptr[gi] >= len(L) or spend[gi] >= BUDGET:
                continue
            c = L[ptr[gi]]
            for b in range(BOATS):
                brok = U['eps'][rd, gi, b] < eps
                tS, dS = G[gi].sample(c, U['uT'][rd, gi, b], U['uD'][rd, gi, b])
                jobs.append(dict(g=gi, b=b, c=c, brok=brok, treq=tS, sp=tS - dS))
        if not jobs:
            break
        # ---- deposition line ----
        selfj = [j for o in ORD[rd] for j in jobs if j['g'] == o and not j['brok']]
        bj = sorted([j for j in jobs if j['brok']], key=lambda j: (CI[j['c']] != mounted, CI[j['c']]))
        for j in selfj + bj:
            m = CI[j['c']]; cost = DEP_H
            if m != mounted:
                cost += CHANGE_H; mounted = m
            dep_h += cost; spend[j['g']] += cost
            ratio = 1.0 if j['brok'] else g[m] / G[j['g']].gm[m]
            j['film'] = U['dep'][rd, j['g'], j['b']] < p_dep(ratio)
            dlog.append(j['c'])
            if not j['brok']:          # own time + measured thickness -> rate factor
                gobs = g[m] * (1 + MEAS * NM[rd, j['g'], j['b']])
                G[j['g']].obs_g(m, gobs, MEAS)
                j['gobs'] = gobs
            good_dep += int(j['film'])
        # ---- furnace ----
        fire = [j for j in jobs if j['film']]
        runs = []
        for gi in range(N_G):        # self-service: own boats only
            own = sorted([j for j in fire if j['g'] == gi and not j['brok']], key=lambda j: j['sp'])
            if not own:
                continue
            if len(own) == 2 and abs(own[0]['sp'] - own[1]['sp']) <= COFIRE_TOL:
                runs.append((own, 'self'))
            else:
                runs += [([j], 'self') for j in own]
        bf = sorted([j for j in fire if j['brok']], key=lambda j: (0 if ampoule else XI[j['c']], j['treq']))
        cl = []
        for j in bf:
            if cl and len(cl) < CAP and (ampoule or XI[cl[0]['c']] == XI[j['c']]) and j['treq'] - cl[0]['treq'] <= COFIRE_TOL:
                cl.append(j)
            else:
                if cl: runs.append((cl, 'brok'))
                cl = [j]
        if cl: runs.append((cl, 'brok'))
        for boats, kind in runs:
            if kind == 'self':
                sp = np.mean([j['sp'] for j in boats])
            else:
                sp = np.mean([j['treq'] for j in boats]) - delta
            if menu:
                sp = menu * np.round(sp / menu)
            Tact = sp + delta
            h = run_hours(sp)
            fur_h += h
            for j in boats:
                spend[j['g']] += h / len(boats) + (SEAL_H if ampoule else 0.0)
                j['Tact'], j['sp_run'] = Tact, sp
                j['ok'] = U['fur'][rd, j['g'], j['b']] < p_fur(Tact - ts[j['c']], WIN[j['c']])
                seen = j['treq'] if (kind == 'brok' and not menu) else sp + delta
                flog.append((j['c'], -1 if ampoule else XI[j['c']], seen))
        # ---- learning, records, progress ----
        done = set()
        for j in jobs:
            gi, c = j['g'], j['c']
            if j['film']:
                if j['brok']:
                    G[gi].obs_brok(c, j['Tact'], j['ok'])
                else:
                    G[gi].obs_self(c, j['sp_run'], j['ok'])
                if j['ok'] and gi not in done:
                    done.add(gi); films[gi] += 1
                    if not np.isfinite(first[gi]):
                        first[gi] = spend[gi]
            if U['tau'][rd, gi, j['b']] < tau and P != 'P4':
                for gk in range(N_G):
                    if gk == gi:
                        continue
                    if 'gobs' in j:
                        G[gk].obs_g(CI[c], j['gobs'] if P == 'P2' else round(j['gobs'] / 0.1) * 0.1,
                                    MEAS if P == 'P2' else 0.03)
                    if not j['film']:
                        continue
                    if P == 'P2':
                        if j['brok']:
                            G[gk].obs_brok(c, j['Tact'], j['ok'])
                        else:
                            G[gk].obs_self(c, j['sp_run'], j['ok'])
                    else:   # P3: chalcogen tube + 50 C band, compound unknown
                        fam = [k for k in range(8) if XI[k] == XI[c]]
                        for k in fam:
                            if j['brok']:
                                G[gk].obs_brok(k, 50 * round(j['Tact'] / 50), j['ok'], 1.0 / K_X[c])
                            else:
                                G[gk].obs_self(k, 50 * round(j['sp_run'] / 50), j['ok'], 1.0 / K_X[c])
        for gi in range(N_G):
            L = world['lists'][gi]
            if ptr[gi] >= len(L):
                continue
            if gi in done:
                ptr[gi] += 1; fails[gi] = 0
            else:
                nb = sum(1 for j in jobs if j['g'] == gi)
                fails[gi] += nb
                if fails[gi] >= MAX_FAIL:
                    ptr[gi] += 1; fails[gi] = 0
    # ---- log attacks (operator reading its own logs) ----
    msd = np.sqrt(ATT_SD ** 2 + (menu ** 2 / 12.0 if menu else 0.0))
    id_f = id_j = 0.0
    for c, xk, T in flog:
        ll = -0.5 * ((T + (0 if False else 0) - LIT) / msd) ** 2
        llx = np.where((XI == xk) | (xk < 0), ll, -np.inf)
        id_f += float(np.argmax(llx) == c)
        llj = np.where(CI == CI[c], llx, -np.inf)
        id_j += float(np.argmax(llj) == c)
    nfired = len(flog)
    id_d = float(np.mean([1.0 / K_M[c] for c in dlog])) if dlog else np.nan
    # join: fired boats use both logs, unfired boats only the target
    id_join = (id_j + sum(1.0 / K_M[c] for c in dlog) - sum(1.0 / K_M[c] for c, _, _ in flog)) / max(len(dlog), 1)
    return dict(first0=float(first[0]), films=float(films.sum()), films0=float(films[0]),
                fur_h=fur_h, dep_h=dep_h, good_dep=good_dep,
                id_f=id_f / nfired if nfired else np.nan, id_d=id_d, id_join=id_join,
                d_hat0=G[0].delta_hat(), g_hat0=G[0].gm.tolist(), g_prec0=G[0].gp.tolist())


def world_job(args):
    w, seeds, conds = args
    world = draw_world(w)
    out = {'w': w, 'delta': world['delta'], 'g': world['g'].tolist(), 'conds': {}}
    for name, kw in conds:
        out['conds'][name] = [campaign(world, w, s, **kw) for s in range(seeds)]
    return out


def conditions(grid, ps):
    conds = []
    for P in ps:
        for t in grid:
            for e in grid:
                conds.append((f'{P}_t{t:.1f}_e{e:.1f}', dict(tau=t, eps=e, P=P)))
    for amp in (False, True):
        for menu in (0, 50, 100):
            for e in (0.0, 1.0):
                if not amp and not menu:
                    continue
                conds.append((f'var_amp{int(amp)}_menu{menu}_e{e:.0f}',
                              dict(tau=0.0, eps=e, P='P4', ampoule=amp, menu=menu)))
    conds.append(('CTCE', dict(tau=1.0, eps=1.0, P='P2', ctce=True)))
    return conds


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--worlds', type=int, default=80)
    ap.add_argument('--seeds', type=int, default=10)
    ap.add_argument('--procs', type=int, default=6)
    ap.add_argument('--grid', type=int, default=6)
    ap.add_argument('--ps', default='P2,P3')
    ap.add_argument('--out', default='results')
    a = ap.parse_args()
    grid = list(np.round(np.linspace(0, 1, a.grid), 2))
    conds = conditions(grid, a.ps.split(','))
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    with Pool(a.procs) as pool:
        res = pool.map(world_job, [(w, a.seeds, conds) for w in range(a.worlds)])
    json.dump(dict(worlds=a.worlds, seeds=a.seeds, grid=grid, ps=a.ps.split(','),
                   conds=[c for c, _ in conds], res=res, wall_s=time.time() - t0),
              open(os.path.join(a.out, 'station_raw.json'), 'w'))
    print('done', time.time() - t0)

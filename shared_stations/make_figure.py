"""Figure for RESULTS.md: python make_figure.py results/station_summary.json results/"""
import json, sys, os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

S = json.load(open(sys.argv[1])); G, grid = S['graded'], S['grid']
plt.rcParams.update({'font.size': 8})
fig, ax = plt.subplots(1, 4, figsize=(7.2, 2.5), gridspec_kw={'width_ratios': [1, 1, 1, 1.1]})
def surf(P, key):
    return np.array([[G[f'{P}_t{t:.1f}_e{e:.1f}'][key] for e in grid] for t in grid])
for a, key, title, cm, vr in [(ax[0], 'h_fur_ratio', '(a) films per furnace-hour\n vs self-service (P2)', 'viridis', (0.9, 1.6)),
                             (ax[1], 'winwin_rebased', '(b) all-party win-win\n probability (P2)', 'magma', (0, 0.4))]:
    im = a.imshow(surf('P2', key), origin='lower', extent=[-0.1, 1.1, -0.1, 1.1], cmap=cm, vmin=vr[0], vmax=vr[1], aspect='auto')
    a.set_xlabel('execution centralization'); a.set_ylabel('training centralization'); a.set_title(title)
    fig.colorbar(im, ax=a, fraction=0.046, pad=0.03)
eps = grid
for P, ls in (('P2', '-'), ('P3', '--')):
    ax[2].plot(eps, [G[f'{P}_t0.0_e{e:.1f}']['corr_delta'] for e in eps], ls, color='C0', label=f'shared logbook off ({P})' if P == 'P2' else None)
    ax[2].plot(eps, [G[f'{P}_t1.0_e{e:.1f}']['corr_delta'] for e in eps], ls, color='C3', label=f'shared logbook on, {P}')
ax[2].axhline(0.2, color='k', lw=0.8, ls=':'); ax[2].set_ylim(-0.05, 1)
ax[2].set_xlabel('execution centralization'); ax[2].set_ylabel('correlation with true offset')
ax[2].set_title('(c) thermocouple offset\n recovered by a user'); ax[2].legend(fontsize=6, loc='center left')
labs = ['fur.', 'dep.', 'join']
o = [G['P2_t0.0_e0.0'][k] for k in ('id_f', 'id_d', 'id_join')]
s = [G['var_amp1_menu0_e0'][k] for k in ('id_f', 'id_d', 'id_join')]
x = np.arange(3)
ax[3].bar(x - 0.2, o, 0.4, label='open tube'); ax[3].bar(x + 0.2, s, 0.4, label='sealed ampoules')
ax[3].axhline(0.125, color='gray', lw=0.8); ax[3].axhline(0.175, color='k', lw=0.8, ls=':')
ax[3].set_xticks(x); ax[3].set_xticklabels(labs); ax[3].set_ylim(0, 1)
ax[3].set_ylabel('identification accuracy'); ax[3].set_title('(d) compound named\n from logs'); ax[3].legend(fontsize=6)
fig.tight_layout()
fig.savefig(os.path.join(sys.argv[2], 'fig_shared_stations.png'), dpi=200)

#!/usr/bin/env python3
"""Executed attacks on campaign transcripts (future-work items 3 and 6).

Every leakage number graded before this study came from *constructed*
attacker beliefs (Bayes-style score accumulators inside the simulator).
This study replaces them with attacks that are actually EXECUTED: a
message-level wire log is recorded for each campaign, an attacker model
is trained on transcripts from training worlds, and its success is
measured on transcripts from held-out worlds it has never seen.

Attacks
-------
1. Membership inference (H attacks R): given the wire log of one
   campaign, decide for each of the 30 public candidates whether R ever
   queried it. Logistic regression on transcript features; reported as
   held-out ROC AUC (limit 0.60).
2. Config-rank extraction (R attacks H): from the fields R legitimately
   sees (its own jobs' realized durations, plus whatever the contract
   discloses about execution), recover H's protected config-quality
   ordering; reported as held-out Spearman correlation (limit 0.20).

Mechanism variants: P2 (exact bins), P3 eps=2 with persistent opaque
IDs, P3 eps=2 with per-epoch ID rotation (the item-6 contract clause,
epoch = 10 rounds), P4. R decision policy: greedy and depth_first (the
policy class that broke the constructed P3 certificates).

All campaigns are SIMULATED (prior worlds, base card); the attacks are
real trained models. Run:  python3 attack_study.py
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "prior_predictive"))
import simulator as sim  # noqa: E402
sys.path.insert(0, str(HERE.parent / "decision_maker_leakage"))
from dm_leakage import make_policy  # noqa: E402

RNG = np.random.default_rng(41)
N_TRAIN_WORLDS = 120
N_TEST_WORLDS = 60
EPOCH = 10           # rounds per opaque-ID epoch when rotation is on
CARD = "base"
TOPO = "CEDT"

MECHS = [  # (label, level, eps, rotate_ids)
    ("P2", "P2", None, False),
    ("P3_eps2", "P3", 2.0, False),
    ("P3_eps2_rot", "P3", 2.0, True),
    ("P4", "P4", None, False),
]
POLICIES = ["greedy", "depth_first"]


class Recorder:
    """Collects the per-message wire log for S parallel seeds."""

    def __init__(self):
        self.rows = {s: [] for s in range(sim.S)}

    def __call__(self, t, m, i, f, j, failed, charge, nh_real, cls):
        for s in np.where(m)[0]:
            self.rows[s].append((t, int(i[s]), int(f[s]), int(j[s]),
                                 int(failed[s]), float(charge[s]),
                                 float(nh_real[s]), int(cls[i[s]])))


def rr_message_class(true_cls, gamma, nclasses, rng):
    """What the P3 secure-aggregate abstraction releases per message:
    the true class with probability gamma, else a uniform class."""
    keep = rng.random() < gamma
    return true_cls if keep else int(rng.integers(nclasses))


def build_membership_rows(recorder, contract, level, rotate, rng):
    """Per (seed, candidate) feature rows for the membership attacker.

    Attacker-visible fields per message: disclosure class (exact at P2,
    randomized-response at P3, absent at P4), an opaque per-candidate ID
    (persistent, or rotated every EPOCH rounds), fidelity, success bit.
    """
    csize = np.array([(contract.classes == b).sum()
                      for b in range(contract.nclasses)], float)
    feats, labels, groups = [], [], []
    gid = 0
    for s, msgs in recorder.rows.items():
        if not msgs:
            continue
        n_msgs = len(msgs)
        queried_s = np.zeros(sim.C, bool)
        for (_, i, *_rest) in msgs:
            queried_s[i] = True
        # observed (possibly noised) class counts + per-ID repeat counts
        obs_count = np.zeros(contract.nclasses)
        id_repeats = {}          # pseudonymous ID -> (count, obs class)
        for (t, i, f, j, fail, chg, nh, cl) in msgs:
            if level == "P2":
                ocl = cl
            elif level == "P3":
                ocl = rr_message_class(cl, contract.gamma,
                                       contract.nclasses, rng)
            else:                # P4: no per-candidate field at all
                ocl = -1
            if ocl >= 0:
                obs_count[ocl] += 1
            if level in ("P3", "P4"):
                pid = (i, t // EPOCH) if rotate else i
                k, _ = id_repeats.get(pid, (0, ocl))
                id_repeats[pid] = (k + 1, ocl)
        # debiased class-count estimate under randomized response
        if level == "P3":
            g, B = contract.gamma, contract.nclasses
            est = (obs_count - (1 - g) * n_msgs / B) / max(g, 1e-6)
        else:
            est = obs_count
        # max repeat count of any single opaque ID whose observed class
        # matches the candidate's class (the query-concentration signal)
        max_rep = np.zeros(contract.nclasses)
        for (k, ocl) in id_repeats.values():
            if ocl >= 0:
                max_rep[ocl] = max(max_rep[ocl], k)
        for c in range(sim.C):
            b = contract.classes[c]
            if level == "P4":
                x = [n_msgs / 40.0, 0.0, 0.0]
            else:
                x = [n_msgs / 40.0,
                     est[b] / csize[b],
                     max_rep[b] / max(csize[b], 1.0)]
            feats.append(x)
            labels.append(float(queried_s[c]))
            groups.append(gid)
        gid += 1
    return np.array(feats), np.array(labels), np.array(groups)


def build_rank_rows(recorder, level, w):
    """R-side rank-extraction data. R always observes its own jobs'
    realized duration (a timing side channel no billing contract can
    hide); the contract controls whether the config identity is also
    visible (P0/P1 yes; P2+ no). Truth: H's config ordering by mean
    log cost at F2 across candidates."""
    eff = sim.eff_matrix(w, 2)
    true_cost = (sim.base_work(w, 2)[:, None] / eff).mean(0)
    true_rank = np.argsort(np.argsort(true_cost))     # 0 = cheapest
    rows = []
    for s, msgs in recorder.rows.items():
        for (t, i, f, j, fail, chg, nh, cl) in msgs:
            if fail:
                continue
            rows.append((s, i, f, j, np.log(max(nh, 1e-3))))
    return rows, true_rank


def rank_extraction_corr(rows, true_rank, config_visible):
    """Executed extraction: regress out candidate+fidelity fixed effects
    from observed log durations; if config IDs are visible, rank configs
    by residual means (train half) and score Spearman vs truth; if not,
    score the per-job timing residual against the job's true config rank
    (the pure timing side channel)."""
    from scipy.stats import spearmanr
    if not rows:
        return 0.0
    arr = np.array(rows)
    s_, i_, f_, j_, y = arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3], arr[:, 4]
    # candidate x fidelity fixed effects (what R knows about its own jobs)
    resid = y.copy()
    for key in set(zip(i_.astype(int), f_.astype(int))):
        mask = (i_ == key[0]) & (f_ == key[1])
        resid[mask] -= y[mask].mean()
    half = np.arange(len(y)) % 2 == 0
    if config_visible:
        means = np.full(sim.J, np.nan)
        for j in range(sim.J):
            mask = half & (j_ == j)
            if mask.any():
                means[j] = resid[mask].mean()
        seen = ~np.isnan(means)
        if seen.sum() < 3:
            return 0.0
        r = spearmanr(means[seen], true_rank[seen]).statistic
    else:
        jr = true_rank[j_[~half].astype(int)]
        if len(set(jr)) < 2 or resid[~half].std() < 1e-9:
            return 0.0
        r = spearmanr(resid[~half], jr).statistic
    return float(0.0 if np.isnan(r) else abs(r))


def fit_logreg(X, y, l2=1e-3, iters=400, lr=0.5):
    Xb = np.hstack([X, np.ones((len(X), 1))])
    wgt = np.zeros(Xb.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-Xb @ wgt))
        grad = Xb.T @ (p - y) / len(y) + l2 * wgt
        wgt -= lr * grad
    return wgt


def auc(scores, y):
    pos, neg = scores[y == 1], scores[y == 0]
    if not len(pos) or not len(neg):
        return 0.5
    return float((pos[:, None] > neg[None, :]).mean()
                 + 0.5 * (pos[:, None] == neg[None, :]).mean())


def macro_auc(scores, y, groups):
    """Within-campaign AUC, averaged over campaigns: can the attacker
    tell WHICH candidates were queried inside one campaign transcript
    (the question the audit limit is about), as opposed to predicting
    how busy a campaign was overall (which pooled AUC also rewards)."""
    vals = []
    for g in np.unique(groups):
        m = groups == g
        vals.append(auc(scores[m], y[m]))
    return float(np.mean(vals))


def collect(worlds, policy, level, eps, rotate, rng):
    Xs, ys, gs, rank_corrs_vis, rank_corrs_blind = [], [], [], [], []
    contract = sim.Contract(level, eps)
    for wid in worlds:
        w = sim.sample_world(CARD, wid)
        rec = Recorder()
        sim.TRANSCRIPT_HOOK = rec
        sim.R_PICK_POLICY = None if policy == "greedy" \
            else make_policy(policy)
        cview = sim.ContractView(contract, sim.world_classes(w, level))
        sim.run_campaign(w, TOPO, contract)
        sim.TRANSCRIPT_HOOK = None
        sim.R_PICK_POLICY = None
        X, y, g = build_membership_rows(rec, cview, level, rotate, rng)
        if len(X):
            Xs.append(X)
            ys.append(y)
            gs.append(g + 1000 * wid)
        rrows, trank = build_rank_rows(rec, level, w)
        rank_corrs_vis.append(rank_extraction_corr(rrows, trank, True))
        rank_corrs_blind.append(rank_extraction_corr(rrows, trank, False))
    return (np.vstack(Xs), np.concatenate(ys), np.concatenate(gs),
            float(np.mean(rank_corrs_vis)), float(np.mean(rank_corrs_blind)))


def main():
    train_w = list(range(N_TRAIN_WORLDS))
    test_w = list(range(5000, 5000 + N_TEST_WORLDS))
    out = {}
    for policy in POLICIES:
        for (label, level, eps, rotate) in MECHS:
            rng = np.random.default_rng(hash((policy, label)) % 2**32)
            Xtr, ytr, _, _, _ = collect(train_w, policy, level, eps,
                                        rotate, rng)
            Xte, yte, gte, rv, rb = collect(test_w, policy, level, eps,
                                            rotate, rng)
            wgt = fit_logreg(Xtr, ytr)
            scores = np.hstack([Xte, np.ones((len(Xte), 1))]) @ wgt
            key = f"{policy}/{label}"
            out[key] = dict(membership_auc=round(macro_auc(scores, yte,
                                                           gte), 3),
                            membership_auc_pooled=round(auc(scores, yte), 3),
                            rank_corr_config_visible=round(rv, 3),
                            rank_corr_timing_only=round(rb, 3),
                            n_test_rows=int(len(yte)),
                            base_rate=round(float(yte.mean()), 3))
            print(key, out[key], flush=True)
    (HERE / "attack_results.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

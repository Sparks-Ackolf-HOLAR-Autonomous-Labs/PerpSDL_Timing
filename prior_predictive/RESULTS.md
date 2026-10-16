# Prior-predictive simulation — results

**Mode:** `prior_predictive_simulation` (frozen manifest: `../case_manifest.yaml`).
**Every node-hour below is a simulated unit. Nothing here is a CHPC measurement,
and nothing here is a materials-discovery claim (spec §20.8).**

Run: 1,000 prior worlds (334 `base` / 333 `strong_coupling` / 333 `adversarial`
prior cards, Axiom A7 ambiguity set) × 10 conditions × 30 paired seeds, plus a
250-world DP sensitivity subset for ε ∈ {1, 2, 8} (ε = 4 is the P3 default in
the main grid). 11,750 world-condition records; computed on the DGX Spark
(18 processes, ~45 s); raw output `results/raw_results.json`.

## Headline finding: prior-credible MRD infeasibility at the preregistered thresholds

**No candidate contract reaches the preregistered 0.90 win-win probability —
nor even 0.80 — under any prior card.** Per §20.7 this is reported as an
explicit MRD infeasibility finding, not forced into a winner:

| Contract | P(win-win), pooled | base / strong / adversarial card | P(R gain) | P(H gain) | P(leakage ok) |
| --- | ---: | :---: | ---: | ---: | ---: |
| **CEDT-P4** (best) | **0.051** | .057 / .072 / .024 | 0.059 | 0.274 | 1.000 |
| CEDT-P3 (ε=2)¹ | 0.048 | — | 0.244 | 0.300 | 0.448 |
| CEDT-P3 (ε=1)¹ | 0.040 | — | 0.272 | 0.320 | 0.388 |
| CEDT-P3 (ε=4) | 0.014 | .030 / .012 / .000 | 0.224 | 0.343 | 0.213 |
| CTDE-P3 (ε=4) | 0.005 | .012 / .003 / .000 | 0.083 | 0.059 | 0.231 |
| every other condition | 0.000 | 0 everywhere | | | |

¹ 250-world sensitivity subset. Worst accepted prior card: 0.024 (CEDT-P4,
adversarial); every other contract's worst card is ≤ 0.012.

![win-win probabilities](results/winwin_probability.png)

### Why it fails — the three components

1. **The R reservation gain is the binding constraint everywhere.** Even the
   full-information greedy reference (CTCE/P0) achieves "20 % fewer node-hours
   to first qualifier, or +1 qualifying candidate, without validity loss" in
   only **14.6 %** of prior worlds. The preregistered participation threshold
   `g_R` demands more coordination value than the prior says full information
   itself delivers; under Axiom A1 that caps every contract. The single most
   useful renegotiation lever is `g_R`, not the privacy mechanism: at a 10 %
   node-hour threshold the R-gain probability for CEDT-P3 roughly doubles
   (0.22 → ~0.45 by inspection of the paired distributions).
2. **Leakage limits eliminate P1 and P2 outright.** At P2 the disclosed
   size/memory bins put exact-identity accuracy at 0.147 (limit 1/30 + 0.05 =
   0.083), configuration-rank extraction at 0.234 (limit 0.20) and
   hardware/build inference advantage at 0.179 (limit 0.10). At P1 every limit
   is breached. Only P4 (always) and P3 with small ε (partially) survive:
   P(all limits met) = 0.39–0.58 at ε ≤ 2 but 0 at ε = 8.
3. **CEDT dominates CTDE across the whole grid** — the workload has fresh
   per-job cross-party coupling (candidate-specific memory demand ρ that H
   cannot see without disclosure), and single-campaign centralized training
   cannot compensate: exactly the regime Proposition 15.10 predicts favors
   execution-time coordination. CTDE never exceeds P(win-win) = 0.008.

![privacy-utility frontier](results/privacy_utility_frontier.png)

## The privacy-tax vector (natural units, §11.3)

Paired campaign means relative to the full-information greedy reference:

| Condition | Δ nh to first qualifier | Δ qualifying F3/F4 | Δ valid F2+ labels/nh | Δ failure rate |
| --- | ---: | ---: | ---: | ---: |
| DTDE-P4 (outside option) | +28.9 (+9.1 %) | −0.38 | −6.0×10⁻³ (−18 %) | +0.0 pp |
| CTDE-P3 | +32.2 | −0.38 | −5.5×10⁻³ | −0.1 pp |
| CEDT-P3 | **−13.4** | −0.06 | −2.5×10⁻³ | −0.1 pp |
| CEDT-P4 | +4.5 | −0.14 | −2.8×10⁻³ | +0.2 pp |

Negative components are valid per §11.3 — and CEDT-P3's *negative* time-to-first
tax against the "ceiling" is a policy-class artifact worth stating plainly: all
arms use the same deterministic greedy acquisition, and CEDT's noisy cost views
act as exploration, which beats deterministic greedy in some worlds. The CTCE
column is therefore a **full-information greedy reference, not a true ceiling**;
CEDT-vs-CTCE contrasts measure exploration as well as information.

![tax vector](results/privacy_tax_vector.png)

## DP sensitivity (ε ∈ {1,2,4,8}, δ = 10⁻⁶ — experimental sweep only)

Leakage feasibility falls steeply with ε (CEDT: 0.39 / 0.45 / 0.21 / 0.00)
while R/H gains are nearly flat in ε — the utility of P3 disclosures saturates
at low fidelity, so **there is no reason to spend more than ε = 2 per party per
campaign** under this prior. These values remain unapproved policy limits.

![epsilon sensitivity](results/eps_sensitivity.png)

## Smallest potentially win-win contract (§15.8 answer)

Within the tested finite contract family, ordered P4 ≺ P3(ε1) ≺ P3(ε2) ≺
P3(ε4) ≺ P3(ε8) ≺ P2 ≺ P1 per arm:

- **No contract is prior-credible at α = 0.20/0.10/0.05.** The *reported
  minimal set* (§20.4 item 12) of nearest candidates contains two incomparable
  contracts: **CEDT-P4** — opaque job IDs, calculation class, success bit,
  rate-card ("fixed-price") charges, broker-side execution matching with joint
  validation of aggressive configurations (highest pooled probability, all
  leakage limits met by an order of magnitude) — and **CEDT-P3 (ε ≤ 2)** —
  P4 plus low-ε secure-aggregate size/memory-demand bins (4× the R-gain
  probability, but leakage-marginal: hardware-inference advantage 0.108 vs the
  0.10 limit and membership-inference AUC 0.587 vs 0.60 at ε = 4).
- P2 and P1 are **MRD-excluded**: their leakage violations are structural
  (identity accuracy from exact bins), not noise that a pilot could dissolve.

## Smallest useful pilot

The value-of-information screen (`results/drivers.json`) shows the win-win
event is driven by, in order: contention burstiness (`burst` → leakage-ok
r = −0.32), pool-mismatch coupling (`pm` → +0.25), scaling exponent (`s` →
−0.16), failure base rate (`beta0` → −0.15), and config quirk spread
(`quirk_sd` → +0.15 on leakage-ok, +0.08 on R-gain). All five are **H-side
physical parameters measurable on public structures** — no R IP is involved,
because the 30 MX₂ candidates are CC0 by design.

**Recommended pilot** (the smallest run that can change the contract
decision, §20.4 step 7): a randomized QE microbenchmark on CHPC —
**3 candidate sizes × 9 configurations × 3 repeats = 81 F1-class jobs plus
peak-memory profiling across the 30 public candidates, ≈ 120–160 node-hours**
(< ⅓ of one campaign budget). It measures `s`, `pm`, `quirk` spread, `beta0`,
contention variability, and the ρ memory-demand spread — i.e., it collapses
the prior ambiguity behind both the leakage-marginality of CEDT-P3(ε≤2) and
the coordination value itself, and it doubles as the Stage-2 twin-fitting
dataset (§5.4 stage 2). It requires the live-mode CHPC fields in the manifest
to be verified first; they remain `REQUIRED`.

However, the pilot cannot rescue a 0.90 target by itself: with P(R gain) ≤
0.27 under every tested contract, **the reservation thresholds are the
dominant infeasibility source.** The actionable sequence is: renegotiate
`g_R` (or budget) → run the 81-job pilot → refit the twin → re-run this
grid before any comparative live campaign.

## Deviations and simplifications (recorded per §20.6/§22)

- **Policy class:** all arms share one deterministic greedy acquisition
  (P(window)²·P(stable)/(cost+overhead)) and a myopic config policy; no RL or
  lookahead. The CTCE column is a greedy reference, not an optimal ceiling.
- **Attack models:** R-side attacks (membership AUC, composition, identity)
  are computed from descriptor equivalence classes — a Bayes-style upper
  bound; H-side attacks (rank extraction, build inference, telemetry MI) are
  analytic models whose power constants are prior beliefs (scaled ×1.3 in the
  adversarial card). They are *part of the prior*, not measurements.
- **DP accounting:** P3 fidelity uses a secure-aggregation abstraction
  (γ = ε/(ε+3)); naive per-message randomized response under linear
  composition would make every P3 identical to P4 — itself a finding about
  mechanism design worth carrying to Stage 2.
- **Billing contract:** P2–P4 assume rate-card (fixed-price) charging;
  realized node-hours are billed only at P0/P1. Without this, H's build class
  leaks through exact charges in every arm including DTDE.
- **Not modeled this round:** educator/student roles (Q0 only), the ALT arm,
  collusion variants, §13.2 ablations, and symbolic-regression refitting of
  the twin (the twin's expression *forms* are carried from Stage 1; constants
  are prior draws). F0 validation is folded into the first F1 job.
- Campaigns are censored at 500 simulated nh; censored first-qualifier times
  enter restricted-mean comparisons at the budget value, and R-gain
  additionally requires a non-inferior found-rate so censoring cannot
  fabricate a gain.

## Reproduction

```
python3 make_candidates.py                     # 30 CC0 prototypes
python3 simulator.py --worlds 1000 --sweep-worlds 250 --procs 18 \
        --out results/raw_results.json         # ~13 core-minutes
python3 analyze.py                             # summary + figures
```

---

# Second round (2026-09-02): g_R renegotiation, CHPC verification, education axis, and Section 13.2 ablations

All node-hours remain SIMULATED UNITS. Raw data: `results/ext_raw.json.gz`
(18,000 records: 1,000 worlds x 18 conditions x 30 paired seeds, run on the
DGX), `results/gR_renegotiation.json` (pure re-analysis of
`results/raw_results.json.gz`), `results/ext_summary.json`.

## 1. Renegotiated R reservation gain (g_R 20% -> 10%)

Because the raw dataset stores per-world paired campaign means, the g_R
renegotiation is a re-grading, not a re-simulation. Sweep over required
node-hour reductions {5, 10, 15, 20}%, everything else frozen
(`results/gR_renegotiation.png`):

| Contract | win-win @20% | @10% | @5% | P(R gain) @10% |
| --- | ---: | ---: | ---: | ---: |
| CEDT-P4 | 0.051 | **0.097** | 0.114 | 0.150 |
| CEDT-P3 (eps=2) | 0.048 | 0.056 | 0.056 | 0.316 |
| CEDT-P3 (eps=4) | 0.014 | 0.016 | 0.017 | 0.324 |
| CTCE-P0 (FI reference) | 0 (leakage) | 0 | 0 | 0.224 |

Verdict: relaxing g_R to 10% roughly doubles CEDT-P4's win-win probability
but nothing crosses 0.80, let alone the preregistered 0.90. Even the
full-information greedy reference achieves a 10% reduction in only 22% of
prior worlds: after the renegotiation the binding constraints are (i) the
task itself (in most worlds the DTDE baseline is not 10% improvable on
time-to-first-qualifier at this budget) and (ii) the conjunction with the
H gain. The MRD infeasibility finding therefore survives g_R renegotiation;
further relaxation should target the H labels-per-node-hour margin or the
win-win probability threshold itself, which are governance decisions.

(Consistent with the earlier caveat: CEDT-P3's DP noise sometimes beats the
greedy FI reference via exploration, so CTCE-P0 is a greedy reference, not
a true ceiling.)

## 2. Education axis (Q0-Q3; kappa_S and b_E swept, not invented)

Model: the student stands in for a novice H operator choosing job configs
in the DTDE regime; execution truth is unchanged. Competency
K_S = student valid-F2+ labels per node-hour / expert's, same worlds and
seeds. Educator-effort constants and curriculum-attack precisions are
declared model beliefs (`extensions.py` EDU table). Figure:
`results/fig_education.png`.

| Curriculum | K_S mean | K_S q10 | educator effort | curriculum leakage (rank-corr / hw-adv) | within H limits? |
| --- | ---: | ---: | ---: | --- | --- |
| Q0 none | 0.913 | 0.600 | 0 | none | yes |
| Q1 public-only | 0.897 | 0.700 | 6 | none | yes |
| Q2 redacted aggregates, 0 hints | 0.987 | 0.947 | 10 | 0.563 / 0.116 | **no** |
| Q2 + 2 hints | 0.994 | 0.984 | 11.5 | 0.687 / 0.142 | **no** |
| Q2 + 8 hints | 0.995 | 0.985 | 16 | 0.838 / 0.199 | **no** |
| Q3 oracle (ceiling, not releasable) | 1.000 | 1.000 | 20 | n/a (if released: ~0.95 / ~0.67) | n/a |

Findings:

1. **Education-axis MRD infeasibility, mirroring the operational one.**
   Q2 is the only curriculum that reaches high competency, and its whole
   advantage comes from teaching the student H's system-specific
   config-performance surface — exactly the protected asset. Under the
   modeled adversarial student, every Q2 variant breaches the original
   H leakage limits (config-rank extraction 0.56-0.84 vs limit 0.20), so
   the minimal *releasable* curriculum is Q1 for kappa_S <= 0.7, and for
   kappa_S >= 0.8 **no releasable curriculum passes at any swept budget**
   (`ext_summary.json: minimal_curriculum_by_kappa_and_budget`).
2. **Hints buy leakage, not competency.** 0 -> 8 hints: K_S 0.987 -> 0.995
   while rank-corr leakage 0.563 -> 0.838. Diminishing returns set in
   after the first two hints (memory factor, scaling exponent); later
   hints rarely change the chosen config.
3. **The reckless-novice paradox.** Q0's *mean* K_S (0.913) slightly
   exceeds Q1's (0.897): the untaught student right-sizes jobs on average
   (it assumes median job size) and outruns the safety-provisioned expert
   in benign worlds, but its q10 is 0.60 with an 11% loss in discovery
   rate. Q1's public curriculum buys tail safety (q10 0.70), not mean
   throughput — the correct reading of "competency" here is a quantile,
   which is why kappa_S should be preregistered as one.

## 3. Section 13.2 ablations (figure: `results/fig_ablations.png`)

**13.2-2 score granularity (H->R cost channel, CEDT-P2 base).** Replacing
calibrated cost bins with rank-only or one-bit disclosures is dominated:
labels/nh drops below even the no-channel P4 arm (bins 1.17, P4 1.13,
rank 0.92, one-bit 0.89 vs DTDE) because mis-scaled cost estimates corrupt
R's acquisition denominator more than no estimates at all — and rank-only
*raises* config-rank leakage (0.37) above the binned channel (0.24), since
exact ordering is precisely what the rank-extraction attacker wants.
Coarsening a score is not automatically privacy-cheap.

**13.2-4 transcript history (composition/linkability).** Restricting the
R membership attacker to the last 10 rounds pushes MI AUC to chance
(CEDT-P2 0.580 -> 0.493; CTDE-P3 0.585 -> 0.483). 37-41% of worlds breach
the 0.60 limit only because the full transcript is retained. Cheapest
leakage intervention found so far: per-epoch opaque-ID rotation /
transcript expiry, worth adding to the P3/P4 contract text.

**13.2-7 numerical-knob control swap (CEDT-P2).** Giving R the config
knobs (R knows its own memory factor rho exactly, but not H's quirks,
memory calibration, or scaling) triples the failure rate (0.021 -> 0.064)
and costs 7% throughput. H's private system knowledge matters more for
config safety than R's private structure knowledge — supporting the
memory-bit-to-H direction of the Theorem-3-style threshold statistic
rather than menu-to-R designs.

**13.2-8 contention-regime shift (+0.35 at round 12, unanticipated).**
All arms lose throughput, but relative gains over the equally-shifted DTDE
baseline *grow* (CEDT-P4 h-gain 0.207 under shift; CTDE-P2 only 0.055):
adaptive execution-time coordination is worth most in turbulent regimes,
and CTDE's in-campaign surrogate (trained pre-shift) goes stale — a
robustness argument for CEDT beyond the stationary analysis.

**13.2-6 post-hoc leakage matching (exploratory, from the main grid).**
At matched worst-leakage ratios, CEDT beats CTDE on both labels/nh
(+12-14%) and node-hours to first qualifier at every contract level:
CEDT dominance is not an artifact of comparing at different leakage.

Not run this round (recorded per §20.6): 13.2-1 (grammar ablation — needs
the twin-fit stage), 13.2-3 (menu size K — no explicit menu machinery),
13.2-5 (payload-byte equalization), 13.2-9/10/11-full/12 (need the full
educational-loop and role-splitting machinery; 13.2-11 is partially
covered by the honest-vs-adversarial student scoring above).

## 4. CHPC live-mode fields: verified and frozen

Verified live on 2026-09-02 over two authenticated logins (SSH to
notchpeak login node): account `sparks`; general allocations on kingspeak
and lonepeak (notchpeak: freecycle/preemptable + `notchpeak-shared-short`
8h/cpu=32/mem=128G + owner coe-np); `quantum-espresso/7.4` with
`openmpi/5.0.3`; scratch `/scratch/general/vast/$USER`. Frozen in
`../case_manifest.yaml` (chpc block). Still REQUIRED and set by the authors:
`live_node_hour_cap` and `authorized_chpc_pilot: true`. The 81-job pilot
is packaged as a guarded SLURM bundle in `../pilot/` and submits nothing
without both.

## 5. Hard budget cap re-run (2026-09-08)

Budget rule: `simulated_node_hour_cap_per_campaign_condition:
500` across 30 paired seeds — a strict maximum of 15,000 simulated
node-hours per condition (a simulation budget, not live CHPC
authorization).

Audit of the 2026-09-02 grid found the engine used *soft-stop*
semantics: a campaign stopped once spend reached 500, but the final job
could overshoot (worst case observed: mean 555 nh for CTCE-P0). Fix:
`MPT_HARD_CAP=1` in `simulator.py` refuses any job whose spend would
push the campaign past 500 and ends the campaign there, so no campaign
can exceed 500 and no condition can exceed 15,000 over the 30 paired
seeds. Verified on the re-run: max campaign spend 496.5 nh -> max
14,896 nh per condition.

Full 1,000-world x 10-condition x 30-paired-seed grid (+ 250-world
eps-sweep) re-run under the hard cap on the DGX (18 procs). Effect:
every condition loses a little utility (strictly less budget), so
win-win probabilities drop slightly and uniformly — CEDT-P4 0.051 ->
0.041, CEDT-P3 0.014 -> 0.006, CTDE-P3 0.005 -> 0.001; leakage-pass
rates are essentially unchanged. **The prior-credible MRD infeasibility
finding survives and is marginally strengthened; the minimal-contract
set (CEDT-P4, CEDT-P3 eps<=2) is unchanged.**

Files: `results/raw_results_hardcap.json.gz` is the new dataset of
record (hard cap; `results/summary.json` and the four figures now grade
it); the 2026-09-02 soft-stop grading is preserved in
`results/summary_pre_hardcap.json` and `results/raw_results.json.gz`.

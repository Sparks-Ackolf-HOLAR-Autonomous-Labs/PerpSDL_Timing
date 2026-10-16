# Centralization surface + multi-party scaling

Aim: a graph whose x and y axes are the degree of centralization (0 to 1) of
training and of execution, so that DTDE, CTDE, CEDT and CTCE are all covered,
with the performance metric on the z axis; plus a two-party versus three-party
(or more) comparison, because the theme is multi-party scalability of
autonomous materials discovery and research.

**All numbers here are SIMULATED UNITS.** The twin physics (cost/memory/failure
expressions, three prior cards, paired noise fields, 30 paired seeds) are
imported unchanged from [`../prior_predictive/simulator.py`](../prior_predictive/simulator.py);
nothing here is a CHPC measurement.

> **Conventions.** (i) Throughput is reported as
> **percent gain vs the DTDE baseline** ((ratio − 1) × 100); the raw
> `labels_ratio` stays in the JSONs unchanged. (ii) The name **"HYB" is
> retired**: the (1,1) corner *is* the CTCE topology (both decisions fully
> centralized) run under the panel's contract filter, written **CTCE@Pk**;
> plain **CTCE@P0** is the unfiltered merged-seat ceiling. One topology, one
> name — what varies is the disclosure dial. See §4.

## 1. The two axes and why the corners are the named arms

Every campaign round has two decisions: **which candidate to run next** (the
research party R) and **how to run it** — cores, k-point pools, aggressive
settings (the HPC party H). The four topologies in this study differ only in
*where those two decisions are centralized*, so they are literally the corners
of a unit square:

| | execution decentralized (ε=0) | execution centralized (ε=1) |
|---|---|---|
| **training decentralized (τ=0)** | **DTDE** (no sharing) | **CEDT** (broker matches at run time) |
| **training centralized (τ=1)** | **CTDE** (shared surrogate, local execution) | **CTCE** (both centralized; "shared everything" only in its P0 form — see §4) |

- **τ (training centralization)** blends R's cost model and H's job-size belief
  between the DTDE self-estimate and a shared surrogate trained on
  contract-coarsened records.
- **ε (execution centralization)** blends H's execution policy between the
  local worst-case reservation and the broker's class-matched config, and opens
  the broker's per-round runtime channel to R.

The interior `MIX(τ, ε)` is a genuinely continuous arm. Validated against the
native `run_campaign` arms on identical worlds at disclosure P2 (30 seeds ×
30 worlds): **DTDE and CEDT reproduce exactly, CTDE within 1.7%** on
labels/node-hour — so the surface is one consistent object, not four glued
patches.

## 2. The surface: `fig_centralization_surface.png` / `fig_centralization_heatmaps.png`

z-axis = **P(win-win)** = prior-predictive probability that R's redesigned
paired-win-rate gain (PW60), H's package throughput gain (≥1.05× labels/nh,
failure ≤ +0.04, p95 memory no worse), **and** all six leakage limits hold at
once. Run at 200 worlds × a 6×6 (τ,ε) grid, at two disclosure levels.

> **Continuity fix (2026-09-22).** An earlier version of this surface showed a
> *step* at ε≈0.6 and was flat in τ because three quantities were wrongly
> binary: `aggressive_ok = ε > 0.5` (a hard execution switch at the grid
> midpoint), `open_frac = max(τ, ε)` (flat in the smaller coordinate), and a
> surrogate warm-up `records ≥ 5` cliff. These are fixed: ε is now a genuine
> **per-round delegation fraction** (a CRN-paired Bernoulli threshold, so ε is
> the fraction of rounds execution is delegated to the broker), leakage exposure
> is the **per-channel union** 1−(1−a_ε)(1−a_τ), and surrogate confidence is a
> smooth `n/(n+n₀)` blend. Corners still reproduce native DTDE/CEDT/CTDE to
> 0.00%; the interior now carries real gradients. Numbers below are the
> re-run (200 worlds × 6×6).

**At minimal disclosure (P4) the win-win surface rises smoothly along the
execution axis, with an interior optimum:**

| ε (execution centralization), at τ=0 | 0.0 | 0.2 | 0.4 | 0.6 | 0.8 | 1.0 |
|---|---|---|---|---|---|---|
| P(win-win) | 0.000 | 0.075 | 0.225 | 0.245 | **0.250** | 0.215 |
| throughput gain vs DTDE (%) | 0.0 | +2.1 | +4.3 | +7.0 | +10.1 | +13.4 |

- **The execution axis is a genuine gradient, not a switch.** As the fraction of
  rounds delegated to the broker rises, throughput climbs smoothly (0% → +13%)
  and win-win rises with it. There is no cliff at ε≈0.6 any more — that was the
  binary artifact.
- **Partial delegation beats full delegation.** The interior optimum is at
  **ε≈0.8 (win-win 0.250), which beats the CEDT corner at ε=1.0 (0.215)**. Full
  delegation over-commits to the broker's class-matched config even on the
  rounds where the local conservative choice would have been safer; delegating
  ~80% of rounds captures most of the throughput gain while keeping a fraction
  of exploratory local control. This is a new, actionable finding the binary
  surface could not express: the best contract is a *mostly-but-not-fully*
  broker-coordinated one.
- **Training centralization still adds nothing at P4.** Holding ε=1 and sweeping
  τ from 0→1 leaves P(win-win) flat at 0.215 — correct, because at P4 there is
  nothing candidate-specific to write into a shared logbook (the τ channel is
  informationless at minimal disclosure). This is the "hybrid buys nothing over
  CEDT" result, and it is a true flat, not a hidden binary.

**At richer disclosure (P2) the entire surface collapses to ~0** — every
sharing point leaks past at least one limit (identity accuracy 0.143 vs the
0.083 limit; config-rank extraction 0.23 vs 0.20), so no corner or interior
point is win-win. Privacy, not throughput, is binding here.

**The CTCE@P0 ceiling is the cautionary corner.** Full sharing gives the
highest throughput of anything on the board (+26% vs DTDE) but leaks completely
(identity accuracy 1.00, rank correlation 1.00, leakage-pass 0.00), so its
P(win-win) is **0.000**. Maximum centralization is the worst privacy outcome,
not the best performance outcome — the surface makes the whole thesis visible
in one picture: **the only feasible ridge is centralize-execution /
decentralize-training / disclose-minimally (CEDT-P4), and it is a modest
plateau at ~0.2, not a peak at 0.9.**

## 3. Multi-party scaling: `fig_multiparty_scaling.png`

Sweeps the number of **research parties N ∈ {1,2,3,5}** sharing one HPC
provider, each corner arm graded against an N-matched DTDE baseline. Three
reduced-form N-party effects are applied inside `run_mix` (documented at its
docstring): shared-node **contention** (κ scaled ×[1+0.10(N−1)]), a **pooled
surrogate** (centralized training ingests N samples per observed job), and
**leakage crowding** (the attacker aggregates across parties, exposure ×
[1+0.35·ln N]).

| vs N (P4 unless noted) | N=1 | N=2 | N=3 | N=5 |
|---|---|---|---|---|
| CEDT-P4 P(win-win) | 0.215 | 0.220 | 0.235 | 0.205 |
| CEDT-P4 P(leakage limits hold) | 1.00 | 1.00 | 1.00 | 1.00 |
| CEDT-P4 throughput gain vs DTDE | +13% | +13% | +13% | +13% |
| CEDT-**P2** identity-inference accuracy | 0.143 | 0.169 | 0.185 | 0.205 |
| CEDT-**P2** telemetry MI-AUC | 0.579 | 0.597 | 0.607 | 0.617 |

**The corrected scaling result (fixed engine): coordination throughput is
N-invariant, and leakage crowding is real but lives at the disclosure levels
that actually share candidate-specific detail — not at P4.** Two facts:

- **At P4, adding parties changes nothing.** CEDT-P4's throughput gain stays
  +13% and its leakage-pass stays 1.00 across N=1…5, so its win-win is flat (~0.21,
  N-to-N wobble is Monte-Carlo noise). Why: P4 discloses only an opaque ID,
  calculation class, success bit and charge — nothing candidate-specific — so a
  cross-party attacker aggregating P4 transcripts has nothing extra to
  aggregate. The many-party privacy fear does **not** bite the one contract that
  actually passes.
- **At P2, crowding is exactly the effect predicted.** As parties are added the
  shared attacker's identity-inference accuracy climbs 0.143 → 0.205 and its
  telemetry membership-AUC climbs 0.579 → 0.617 — the leakage budget tightens
  with N. But P2 already fails its limits at N=1 (leakage-pass ≡ 0), so this
  crowding pushes an already-illegal contract further out of bounds rather than
  breaking a good one.

> This corrects the earlier (binary-engine) claim that CEDT-P4's win-win eroded
> 0.215→0.075 with a leakage-pass falling 1.00→0.58. That erosion was an
> artifact: the old `max(τ,ε)` leakage scaling let the crowding factor bleed
> into the P4 point even though P4 has nothing candidate-specific to leak. With
> the per-channel union it does not.

Consequences for scalability:

- **CTDE-P4 is pure downside at every N** (throughput gain ≡ 0%): centralized
  training never pays at P4, because there is nothing candidate-specific to pool.
- **CEDT-P2 leaks at every N** and worsens with N — richer disclosure is not
  rescued by more parties, it is punished by them.
- **`MIX-P4(½,½)` tracks CEDT-P4** (win-win ~0.24, leakage-clean at every N):
  partial delegation stays a viable multi-party contract, consistent with the
  interior-optimum finding on the surface.

**Design implication for multi-party autonomous discovery:** the coordination
mechanism scales (throughput is N-invariant). Whether the *privacy contract*
scales depends on what it discloses: a minimal-disclosure (P4) contract is
N-robust because a crowd of attackers has nothing extra to pool, whereas any
candidate-specific disclosure (P2/P3) tightens the leakage budget as parties are
added. The scaling lesson is therefore **stay at P4 as the consortium grows** —
richer contracts that might be tolerable bilaterally degrade with N.

## 4. The (1,1) corner: "HYB" is retired — it is CTCE@Pk

Keeping a separate name for the (1,1) corner invites confusion, because there is **no topological difference between "HYB"
and CTCE** — both mean *training and execution fully centralized*. What
distinguished them was never the centralization; it was a **third dial the
surface holds fixed per panel: the disclosure level**. So the terminology is
now:

| point | τ | ε | disclosure | decision seats | name (new) | name (old, retired) |
|---|---|---|---|---|---|---|
| plotted surface corner | 1 | 1 | Pk, contract enforced | two parties, filtered | **CTCE@Pk** | ~~HYB~~ |
| ceiling reference | 1 | 1 | **P0** (no filter) | **one merged decision maker** | **CTCE@P0** (plain "CTCE") | CTCE |

One topology, one name (CTCE), indexed by the contract level it runs under.
`MIX(1,1)` at a privacy-preserving level is CTCE@Pk: both channels fully open
but everything crossing the boundary still passes the Pk filter, and the two
parties keep separate decision seats. `run_mix(w, 1, 1, "P0")` takes a special
branch in [`surface.py`](surface.py) — a single optimizer sees true costs and
picks candidate + config jointly, no contract left to enforce — and that is
the classic CTCE ceiling, now written CTCE@P0.

The study's main point survives the rename unchanged and gets easier to say:
at (1,1) the *centralization* is identical, and the entire difference between
CTCE@P4 (win-win 0.215, leakage-clean) and CTCE@P0 (win-win 0.000, leaks
everything) is the disclosure dial. All figures, the native-arm engine
(`hybrid_arms/`), and older documents that say "HYB" refer to what is now
CTCE@Pk; the finding "HYB adds nothing over CEDT" reads "CTCE@Pk adds nothing
over CEDT — τ is dead weight at every disclosure level" (§7).

## 5. How the surface changes with workload / task complexity: `fig_surface_vs_scale.png`

`surface_scale.py` re-runs the surface on the **measurement-anchored posterior
twin** (Stage-2 campaign fit × task-scale multiplier, p_e rising with scale per
the measured curve 1.20→2.5, memory channel growing as scale^0.5, pilot-fitted
scheduler priors, measured 0.02 nh per-sbatch overhead — identical patching to
`scale_experiment_grid/grid_study.py`). 120 worlds × 5×5 (τ,ε) grid × task
scales ×1…×300 at P4, with P2 re-checked at ×1 and ×100. Still simulated
units; the ×1 cell is the measured 1×1-supercell campaign cost, ×30–×100 ≈ the
3×3-supercell regime of the live comparisons.

> **Re-run on the fixed continuous engine (2026-09-22).** The numbers below
> replace the earlier binary-engine sweep. The ridge heights are unchanged
> (corners were always computed by the native arms), but the *interior* is
> different everywhere: the ε-cliff is gone, and the P2 panel gains a finding
> the binary engine could not express.

| task scale | DTDE / CTDE | CEDT-P4 = CTCE@P4 ridge | CEDT-P4 throughput gain | P2 corner / P2 best interior | CTCE@P0 ceiling |
|---|---|---|---|---|---|
| ×1 | 0.000 | **0.450** | +5.0% | 0.00 / 0.13 | 0.000 |
| ×10 | 0.000 | **0.942** | +15.0% | – | 0.000 |
| ×30 | 0.000 | **0.942** | +17.6% | – | 0.000 |
| ×100 | 0.000 | **0.950** | +18.7% | 0.00 / **0.93** | 0.000 |
| ×300 | 0.000 | **0.950** | +19.2% | – | 0.000 |

P(win-win) along the execution axis (τ=0), showing the gradient the binary
engine hid:

| ε at τ=0 | 0.00 | 0.25 | 0.50 | 0.75 | 1.00 |
|---|---|---|---|---|---|
| ×1 | 0.000 | 0.000 | 0.033 | 0.200 | **0.450** |
| ×10 | 0.000 | 0.150 | 0.700 | 0.883 | **0.942** |
| ×100 | 0.000 | 0.300 | 0.825 | 0.925 | **0.950** |

Findings:

1. **The geometry is scale-invariant, and it is now a smooth slope, not a
   step.** At every scale the surface is flat in τ (training centralization
   adds nothing at ×300 just as at ×1 — even where the memory channel binds,
   the broker's class-level placement already carries the decision-relevant
   information) and rises monotonically in ε. On this posterior twin the
   maximum always sits at the CEDT corner (ε=1) — the wide-prior interior
   optimum of §2 (ε≈0.8 beating the corner) does not persist under the
   measurement-anchored priors, where the broker's class-matched configs are
   reliably right and every skipped delegation is a small loss.
2. **Scale steepens the value of *partial* delegation.** At ×1, half-hearted
   coordination is worthless (ε=0.5 → 0.033): margins are so thin that only
   full delegation clears the H package. From ×10 up, ε=0.5 already captures
   ~75–87% of the ridge and even ε=0.25 is worth 0.15–0.33. Practically:
   heavy-task consortia can start with a cautious fractional contract and
   still capture most of the value; light-task ones must commit fully or not
   bother.
3. **What scale changes numerically is the H-side margin.** The R-gain (PW60
   sign test) sits at ≈0.97 and P4 leakage-pass at 1.00 at every scale; the
   mover is P(H package ≥+5%): borderline at ×1 (gain +5.0%, exactly at
   the margin → 0.45) and comfortable from ×10 up (+15% to +19% → 0.94–0.95),
   saturating by ×10 in this twin.
4. **New: richer disclosure has a low-dose corridor the binary engine could
   not see.** The CEDT-P2 *corner* stays leakage-dead at every scale
   (leak-pass 0.00). But because leakage exposure now scales with the
   delegation/sharing fractions — the attacker only sees the rounds that
   actually crossed the boundary — the **(τ≤0.25, ε=0.25) cells hold every
   leakage limit** (identity accuracy 0.077 vs the 0.083 limit; rank
   extraction 0.13 vs 0.20), and at ×100 that corridor reaches **win-win
   0.93, essentially matching CEDT-P4's 0.95**. At ε=0.5 or τ=0.5 the limits
   break again (leak-pass ≤ 0.04). So a P2-rich contract *used sparingly* is
   viable at heavy scale — but the corridor is one grid cell wide and sits a
   hair under the identity limit, while CEDT-P4 passes leakage with margin
   at *every* dose. P4-at-full-delegation remains the robust recommendation;
   the corridor matters as a fallback when a partner insists on richer
   fields.
5. **No scale rescues full centralization.** The CTCE@P0 ceiling has the best
   throughput on the board at every scale (+53% at ×300) with win-win
   identically 0 (identity accuracy 1.00) — the "leakage price is
   scale-invariant, value is scale-dependent" sociability-map result, on the
   surface.
6. **Caveats.** (i) PW60 ≈ 0.97 even at ×1 shows the sign test counts
   epsilon-sized wins — the live No. 1 result (6/10, coin flip) says real
   paired wins are far noisier than this twin's; (ii) the throughput gains
   assume accounting where right-sizing saves money (per-core/TRES) — under
   whole-node billing the live No. 1 measured +0.5%, and comparison No. 2 on
   granite is the running test of exactly this column; (iii) saturation by ×10
   reflects the 1.05× package margin — the earlier ×30–×100 "window" claims
   were against the stiffer frozen 1.15× margin; (iv) the P2 corridor is
   resolved only at the 0.25 grid step and sits 0.006 under the identity
   limit — treat it as a direction, not a certified operating point, until a
   finer-grid (and ideally live-attacked) check.

## 6. Adaptive schedules: does the *timing* of centralization matter? (`fig_schedules.png`)

The surface maps *static* (τ,ε) points; this section tests an
**adaptive policy that changes centralization before or during a campaign**.
`schedules.py` runs four per-round profiles over the T=80 rounds — `static`,
`ramp_up` (0→2m), `ramp_down` (2m→0), `mid_pulse` (a central window) — each
**normalized to the same time-mean m=0.5**, so any difference is pure timing,
not total amount. Two settings: an ε-schedule at P4 (execution axis, where the
ridge lives) and a τ-schedule at P2 (training axis, where the logbook channel
is live). 200 worlds.

| ε-schedule @ P4 (mean 0.5) | static | ramp_up | ramp_down | mid_pulse |
|---|---|---|---|---|
| P(win-win) | 0.250 | 0.120 | **0.270** | 0.230 |
| throughput gain vs DTDE (%) | +5.7 | +3.1 | **+8.5** | +5.3 |

- **On the execution axis, timing matters.** At the same average delegation,
  `ramp_down` — delegate heavily early, pull back late — beats `static`
  (win-win 0.270 vs 0.250) and both crush `ramp_up` (0.120). Early delegation
  wins because the first rounds are when the campaign is still seeding its cost
  models and the broker's right-sizing pays the most; delegating late wastes the
  exploratory early budget on conservative local configs. **So an adaptive
  contract that front-loads execution coordination and relaxes it later beats
  any fixed policy at the same total.**
- **On the training axis, timing does not matter.** Every τ-schedule at P2 gives
  identical leakage and utility, because the leakage aggregate is *cumulative* —
  the attacker sees the whole campaign, so only the total logbook disclosure
  matters, not when it happens. For a cumulative-exposure channel, scheduling
  buys nothing.

The design takeaway: **schedule the execution channel (delegate early), but
there is no clever schedule for the disclosure channel — its budget is set by
the total, so spend it minimally, full stop.**

## 7. Why the training axis is flat — and the 11×11 high-resolution surface

Why does the degree of training centralization show no difference? This section
answers that question and replaces the 5 to 6 points per axis with a finer grid,
in two parts (`tau_diagnostic.py`, `results/tau_diagnostic.json`,
`results/fig_tau_answer.png`; grids re-run at **11×11**, 150 worlds).

### 7.1 At P4 the τ axis is dead *by contract*, not by a wiring accident

The shared logbook (the training channel) is keyed by **descriptor classes** —
what the contract lets R's job descriptions look like from the other side. At
P4 the contract discloses *no descriptor at all* (`Contract.gamma = 0` for P4,
`simulator.py:288`): every job is an opaque ID plus a calculation class, and
P4 charges are flat rate-card values carrying zero performance information by
construction. A logbook keyed on nothing, filled with constants, cannot train
anything — so on the P4 panel, `MIX(τ, ε) ≡ MIX(0, ε)` identically. This
matches the native engine, whose CTDE-P4 ingest is likewise gated off
(`gam > 0`, `simulator.py:575`). Verified operationally, not assumed: campaigns
at τ ∈ {0, 0.5, 1} with everything else fixed produce **bit-identical outcome
vectors** (max abs diff 0.0 across all metrics, part A of the diagnostic), and
every τ-row of the 11-point P4 grid is exactly constant. Since P4 is the panel
that carries the win-win ridge, this is what makes the surface *look* τ-flat.

### 7.2 At P2 the logbook has content — but it is informationally redundant

Where τ *can* act (P2), the diagnostic measures how much cross-candidate cost
information each channel carries (R² of log ideal-config cost, 60 worlds,
F1–F3):

| channel | what it is | R² |
|---|---|---|
| **own** | R's own bills + the public size law (`nelec`), free in **every** arm incl. DTDE | **0.986** |
| **surrogate** | the P2 class-keyed shared logbook at its asymptotic best (class-mean of true cost) | 0.975 |
| broker | H's per-job runtime view at P2 precision | 0.759 |

The logbook's *ceiling* is strictly below what R already knows for free: the
twin's costs (like the measured ones — the 1×1 campaign's per-candidate
multipliers predicted the 6×6 walls to 2.8%) are dominated by candidate size,
which R knows exactly and the P2 classes only coarsen. On the H seat the same
redundancy holds one level up: the logbook tells H the size mix R sends, but
the broker channel (ε) already carries the per-job class, and at ε = 0 H's
conservative policy converges to worst-case provisioning as soon as R queries
one large candidate. The 21-point transects quantify the leftover: full τ
moves throughput by **+2.4 % at ε = 0, +1.3 % at ε = 0.5, +0.4 % at ε = 1** —
while the attacker's identity accuracy climbs 0.033 → 0.143 (limit 0.083),
collapsing P(leakage ok) from 1.0 to 0 by τ ≈ 0.5. **τ is not exactly zero at
P2 — it is a channel that buys ~1–2 % throughput at the price of the entire
leakage certificate**, which is why it never shows up in win-win.

### 7.3 What the 11×11 grid adds (and one more bug the audit caught)

- **A real interpolation bug, fixed**: for τ + ε > 1 the R-cost blend put
  *negative* weight on R's own estimate (extrapolating past the channels
  instead of mixing them). The fix caps the channel weight sum at 1; corners
  are unaffected (DTDE/CEDT exact, CTDE 1.6 %) and the (1,1) corner (CTCE@P2)
  *improves* to 0.44 % vs the native arm. Only the upper-right triangle of prior grids was
  distorted, and none of the corner/ridge conclusions change.
- **P4 at 11×11**: the ridge is still pure ε-banding; the interior ε-optimum
  persists (win-win 0.26 at ε = 0.6 vs 0.21 at the CEDT corner on this run —
  wide-prior cards; the measurement-anchored §5 sweep still peaks at the
  corner).
- **P2 at 11×11**: the finer grid *relocates the low-dose corridor* the 6-point
  grid could only straddle: the peak is **win-win 0.20 at (τ = 0, ε = 0.3)**
  with P(leakage ok) = 0.99, tolerating τ up to ~0.1 (0.20 at (0.1, 0.3));
  by (0, 0.4) it is already 0.17 and falling. The leakage boundary is an
  **anti-diagonal dose frontier** (roughly τ + ε ≲ 0.5 survives) — visible as
  the yellow triangle in the P2 leakage heatmap — exactly the in-between-region
  structure a coarse grid steps over.

Bottom line: the τ axis is flat because at the
disclosure level that wins (P4) the training channel is *contractually empty*,
and at the level where it isn't empty (P2) it is *informationally redundant* —
its content is already in R's own bills — so it contributes leakage exposure
with no compensating utility. That is a finding about this workload's physics
(size-predictable costs), not an artifact: a workload whose per-candidate costs
were **not** predictable from public descriptors would give the logbook real
marginal value, and §7.2's R² probe is the cheap test to run before assuming
either way.

## 8. P1 and P3: the full disclosure ladder on the surface

P1 and P3 are the other two
rungs of the contract ladder the program has always carried (P0 = raw
descriptors, P1 = realized costs + fine bins, P2 = coarse calibrated bins,
P3 = differentially-private aggregates, P4 = class + success bit + rate-card
charge). The earlier surface panels showed only the two *decision-relevant*
levels (P4 = the recommended contract, P2 = the cautionary rich one) because
the 1,000-world prior-predictive grid had already excluded P1 structurally and
found P3 dominated by P4. Both are now run on the same fixed continuous engine
(11×11 × 150 worlds, DGX; `results/surface_P1.json`, `results/surface_P3.json`;
P3 at the sweep's default DP budget ε_DP = 4) so the ladder is complete in
`fig_centralization_heatmaps.png`. Along the execution axis at τ = 0:

| ε at τ=0 | 0.1 | 0.2 | 0.3 | 0.4 | 0.5 | 0.6 | 0.8 | 1.0 |
|---|---|---|---|---|---|---|---|---|
| **P1** win-win | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| **P1** P(leak ok) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| **P1** throughput gain | +2.1% | +4.6% | +7.2% | +9.3% | +11.8% | +14.8% | +20.7% | +25.3% |
| **P3** win-win | 0.02 | 0.12 | 0.15 | **0.19** | 0.18 | 0.17 | 0.05 | 0.03 |
| **P3** P(leak ok) | 1.00 | 1.00 | 0.99 | 0.95 | 0.86 | 0.79 | 0.49 | 0.23 |
| **P3** throughput gain | +1.2% | +2.5% | +3.6% | +4.6% | +5.9% | +7.4% | +11.4% | +14.2% |

- **P1 exists and is the sharpest statement of the whole thesis.** It carries
  the *largest* raw throughput gain of any level (+25.3% at full delegation —
  realized costs and fine bins are genuinely the most useful information), and
  it is **leakage-illegal at every nonzero dose**: even ε = 0.1 pushes identity
  accuracy to 0.117 against the 0.083 limit, and every one of the 121 grid
  cells has win-win exactly 0. There is no P1 corridor. The most valuable
  disclosure is the most illegal one, at any fraction.
- **P3 exists and has the widest safe corridor of the rich levels.** DP noise
  makes its leakage frontier *gentle* instead of a cliff: limits hold through
  ε ≈ 0.4–0.5 and win-win peaks at **0.19 at (τ=0, ε=0.4)** — wider than P2's
  one-cell corridor (peak 0.20 at ε = 0.3) but a similar height, and both sit
  below P4's interior optimum (0.26 at ε = 0.6, wide-prior cards). The
  full-delegation corner CTCE@P3 breaches the limits (leak-pass 0.23), which
  is the surface view of the old grid finding "campaign-level DP cannot
  protect a fully-open channel".
- **τ hurts at P3 just like everywhere else:** at ε = 0.4, raising τ 0 → 0.6
  drops win-win 0.19 → 0.10 while adding ≤ +0.8% throughput — the logbook
  channel spends leakage budget on redundant information (§7.2) at every
  disclosure level where it is live.
- **The ladder ordering on the surface is therefore:** P4 (best, robust at
  every dose) > P3-corridor ≈ P2-corridor (viable only at low dose; P3's
  corridor is wider, P2's slightly higher-peaked) > P1 (never legal). Caveat:
  the P3 row is at ε_DP = 4 only; smaller DP budgets would widen its corridor
  and lower its gain — the ε_DP sweep exists in the original grid study, not
  here.

## Reproduce

```bash
python surface.py    --worlds 150 --grid 11 --level P4  # results/surface_P4.json
python surface.py    --worlds 150 --grid 11 --level P3  # results/surface_P3.json
python surface.py    --worlds 150 --grid 11 --level P2  # results/surface_P2.json
python surface.py    --worlds 150 --grid 11 --level P1  # results/surface_P1.json
python tau_diagnostic.py --worlds 120 --npts 21         # results/tau_diagnostic.json
python make_tau_figure.py                               # fig_tau_answer.png
python scaling.py    --worlds 200                       # results/scaling.json
python schedules.py  --worlds 200                       # results/schedules.json
python make_figures.py                                  # four PNGs
python surface_scale.py --worlds 120 --grid 5           # results/surface_scale.json
python make_scale_figure.py                             # fig_surface_vs_scale.png
python validate_continuity.py                           # corner + gradient check
```

Corner-validation of the MIX interpolation against the native arms is a 30-world
check (DTDE/CEDT exact, CTDE within 1.7%); rerun with the snippet in the commit
message or `run_mix(w,τ,ε,level)` vs `run_campaign(w,topology,contract)`.

## Limitations

- The N-party effects are **reduced-form modifiers on the single-party engine**,
  not a full N-party co-simulation with explicit per-party candidate slices and
  a shared queue. The three modifiers (contention, pooling, crowding) are
  plausible functional forms, not measured couplings; the *direction* (win-win
  falls with N via leakage) is robust to their magnitudes, the exact decay rate
  is not.
- Leakage exposure at interior points is scaled from the native-arm attacker
  models by channel openness — a monotone interpolation, not an independently
  derived attacker per (τ,ε).
- Disclosure level is held fixed per surface panel (P1–P4); the privacy axis is
  deliberately *not* folded into the centralization axes, so the classic
  full-disclosure ceiling (CTCE@P0) is shown as a separate reference point.
- Same twin caveats as the rest of the program: the win-win probabilities are
  prior-predictive simulation, and the live comparison (No. 2, running on
  granite) is the only test that can confirm the positive claims.

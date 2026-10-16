# Shared stations beyond the computing node: a tube furnace and a sputter deposition line (simulated)

This study widens the scope of the disclosure study to another kind of
shared station, such as the logs of a furnace or a deposition line, in
simulation.

Registered 14 Oct 2026, before `station_sim.py` was written or run. Every
number below that describes the stations (temperatures, rates, run times,
calibration errors) is an assumed value chosen to be physically plausible; none
is a measurement. The only measured input is which MX2 compositions have a PBE
gap in the 1.0 to 2.0 eV window (`dft_campaign/results/outcomes.jsonl`).

## Why a furnace and a deposition line differ from a computing node

On the computing node the station's private knowledge (which settings run a
job fastest) changes only the cost of a job, and the result (a band gap) does
not depend on it. Two consequences followed: sharing a logbook of past jobs
added almost nothing (the training axis of the centralization surface was
flat), and the timing side channel could be closed by padding, because run time
is a by-product of the calculation.

At a growth station both statements change:

1. **The station's private state changes the scientific outcome.** A tube
   furnace whose thermocouple reads 25 C low grows a different film from the
   one the recipe asked for; a sputter target that has eroded deposits a
   thinner metal film than the nominal rate predicts. The operator knows these
   corrections from calibration runs (its settings book); the user does not.
2. **The log is the recipe.** The furnace controller records the setpoint,
   ramp, dwell and atmosphere tube; the deposition line records which target
   was mounted and for how long. Unlike run time on a node, these entries
   cannot be padded without changing the material that is made.

## The campaign

- **Goal of each research group (R).** Grow a phase-pure few-layer film of a
  compound from its own list. Lists hold 5 compositions drawn per world from
  the 8 compositions whose measured PBE gap lies in the window (MoS2, WS2,
  MoSe2, WSe2, MoTe2, WTe2, ZrS2, HfS2). N = 4 groups share both stations.
- **Route per attempt.** (i) Sputter a metal film of target thickness 2 nm on
  the shared deposition line, measure its thickness (2 % error); (ii) if the
  thickness is within tolerance, convert it to MX2 in the shared tube furnace
  under chalcogen vapour; (iii) the film counts when the conversion succeeds.
- **Deposition line (operator H_dep).** One target mounted at a time; a target
  change (vent, swap, pump-down, pre-sputter) costs 2 h; a deposition costs
  0.5 h. True rate = nominal rate x g_M, with g_M ~ N(1, 0.12) per target and
  world, known to H_dep from its quartz-crystal calibration. Film success
  probability 0.95 exp(-((d/d0 - 1)/0.08)^2 / 2).
- **Tube furnace (operator H_fur).** Open-tube flow with one tube per chalcogen
  (standard practice against cross-contamination); 4 boats per run; run time
  T/300 (5 C/min ramp) + 1 h dwell + T/150 (cooling) hours, about 9 h at
  800 C. The run is billed per run and split among the boats in it. Optimum
  sample temperature T*_c = base_X + shift_M + N(0, 40) per world, with base S
  850, Se 750, Te 600 C and shift Mo 0, W +60, Zr -30, Hf -10 C; window width
  40 C (25 C for tellurides); success probability 0.9 exp(-((T - T*)/w)^2 / 2).
  Thermocouple offset delta ~ N(0, 25 C) per world, known to H_fur from its
  calibration; the sample sees setpoint + delta.
- **Group decisions.** Each round a group submits 2 boats for its current
  compound at temperatures drawn from its posterior (Thompson sampling) and
  moves to its next compound after a success or 6 failed boats; budget 250
  station-hours per group, 30 rounds at most.

## Coordination arms (same two continuous dials as the centralization surface)

- **Execution centralization eps** (fraction of a group's jobs handed to the
  operator's broker): a brokered job states the sample temperature or film
  thickness wanted, and the operator applies its private correction (delta,
  g_M) without revealing it. The furnace broker also co-fires compatible boats
  from different groups (same tube, requested temperatures within 20 C, run at
  their mean); the deposition broker orders the round's jobs by target to cut
  target changes. A self-service job uses the group's own estimates and its
  own boats only.
- **Training centralization tau** (fraction of finished-attempt records placed
  in a logbook shared by all groups). Disclosure P2: a record names the
  compound, the setpoint or requested value, and the outcome. P3: a record
  names only the station key (chalcogen tube or metal target) and a 50 C or
  10 % band. P4: no record content (the channel is empty, as on the node).
- Corners: (0,0) DTDE, (1,0) CTDE, (0,1) CEDT, (1,1) hybrid at the stated
  disclosure; CTCE = one merged decision maker with the operators' corrections
  and all records (reference only).

Variants: **sealed ampoules** (each boat sealed with its own chalcogen; tube no
longer reveals X; co-firing across chalcogens allowed; +0.5 h sealing per
boat); **programme menu** masking (the furnace offers only fixed programmes at
50 C or 100 C steps, so the log shows a programme number, not a setpoint).

## Grading

Paired: every arm runs on the same worlds and seeds as DTDE. Per world:

- R gain: paired win rate PW60 on station-hours to the first film (group 0).
- H gains: films per furnace-hour and good films per deposition-hour, each
  at least 1.05 x DTDE.
- Leakage (attacker = the station operator reading its own logs, or a group
  reading the shared logbook):
  - L1 compound identity from the furnace log (tube, setpoint, plus the
    operator's own delta); L2 from the deposition log (target); L3 from the
    two logs joined by billing account. Prior accuracy 1/8; absolute limit
    prior + 0.05 = 0.175. Because the operator must see the recipe to run it,
    the contract can only govern the *added* identity: rebased limit = DTDE
    identity + 0.05.
  - L4 extraction of the furnace offset delta (and L5 of target factors g_M)
    by a group from the shared logbook: correlation of the estimate with the
    truth across worlds at most 0.20.
- All-party win-win: R gain, both H gains, rebased L1 to L3, and L4/L5.

## Registered predictions

- **S1 (the training axis gains slope).** At P2, eps = 0, moving tau from 0 to
  1 shortens group 0's median hours to first film by at least 10 % (on the
  node it moved throughput by at most 2.4 %).
- **S2 (co-firing carries the operator gain).** At P3, CEDT (eps = 1) gives at
  least 1.05 x DTDE films per furnace-hour in at least 80 % of worlds.
- **S3 (the log is the recipe).** Furnace-log identity (L1) exceeds the
  absolute limit 0.175 in at least 95 % of worlds in every arm, including the
  100 C programme menu.
- **S4 (sealed ampoules).** Sealed ampoules lower L1 by at least 0.15 against
  the open tube and raise the furnace co-firing gain.
- **S5 (join).** The deposition log alone and the furnace log alone each give
  identity at most 0.60, and the account-linked join gives at least 0.85.
- **S6 (the logbook leaks the operator's settings book).** At P2, tau = 1,
  the correlation of a group's estimate of delta with the true delta is at
  least 0.5 (limit 0.20); at P3 it is still at least 0.20.
- **S7 (win-win).** With the absolute identity limit no cell of any surface
  reaches all-party win-win; with the rebased limit, at least one cell with
  tau = 0 reaches at least 0.5.

Any prediction that fails is reported as failed; no threshold is moved after
the run.

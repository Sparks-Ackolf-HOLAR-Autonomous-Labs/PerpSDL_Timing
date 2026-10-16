# Reverse of the timing attack: from compound to expected job time

Question (12 Oct 2026): the timing attack reads a job's wall time and
names the compound. Can the map run the other way: given the compound we want
to compute, how long should its job take?

Data: the 480 measured Quantum ESPRESSO calls of live comparison No. 1
(29 MX2 monolayers as 3x3 supercells, PBE, granite node grn061), grouped by
stage (F1 coarse SCF, F2 production SCF) and execution setting (MPI ranks, k-point
pools). Script: `reverse_timing.py`; numbers: `reverse_timing_results.json`.

## Three ways to predict the time before the job runs

| setting | compounds | time range (s) | A: compound run before | B: only the 1x1 run known | C: never run (composition and phase only) | spacing between neighbouring compounds |
|---|---:|---|---:|---:|---:|---:|
| F1, 16 ranks | 27 | 43 to 198 | 0.3 % | 24 % | 7.8 % (p90 21 %) | 3.8 % |
| F1, 32 ranks | 27 | 26 to 117 | 0.4 % | 21 % | 8.9 % (p90 20 %) | 3.0 % |
| F2, 32 ranks, 1 pool | 27 | 60 to 344 | 0.3 % | 29 % | 7.8 % (p90 16 %) | 3.6 % |
| F2, 32 ranks, 2 pools | 27 | 61 to 341 | 0.5 % | 27 % | 7.2 % (p90 20 %) | 4.3 % |

Entries are median absolute prediction errors. C is a log-linear fit on electron
count, phase (1T or 2H), metal row, chalcogen and group-6 metal, graded
leave-one-compound-out. B transfers the 1x1-cell F1 time with a log-linear fit,
also leave-one-out.

## Reading

1. **Yes, the reverse map exists, and it is the same map.** A compound that has
   been run once repeats its time to 0.3 to 0.5 %. A compound never run is
   predicted from composition and phase to about 8 % (worst tenth about 20 %).
2. **Why the attack works but the reverse prediction cannot replace it.**
   Repeat scatter (0.3 %) is ten times smaller than the spacing between
   neighbouring compounds on the time axis (3 to 4 %), so one measured time picks
   out one compound. The composition-only prediction (8 %) is wider than that
   spacing, so it gives a time window holding two or three compounds, not one.
   Identification needs a measured reference; planning does not.
3. **The 1x1 run is a poor predictor of the 3x3 time** (21 to 29 %): 1x1 jobs
   last seconds and are dominated by start-up overhead, not by the electronic
   problem. Composition descriptors are four times better.

## Uses

- **Scheduling and reservation sizing:** request walltime and memory per
  compound from the composition fit plus a 20 % margin (the p90 error).
- **Timing masking:** the masking clause can pad every job to the upper end of
  its class window predicted here, so the reported time no longer separates
  compounds whose predicted windows overlap.
- **Budget-first screening:** given a time budget per job, the fit lists which
  compositions and phases fit inside it before any job is queued.

Limits: one code (QE 7.4), one functional (PBE), one node type, one family
(MX2); times move with hardware and settings, so the fit is refitted per machine.

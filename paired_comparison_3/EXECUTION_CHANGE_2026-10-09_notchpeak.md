# Execution change, 9 Oct 2026: waiting campaigns moved to notchpeak-guest

Decision (9 Oct 2026 22:01 UTC): apply option 1, add options 3 and 2 if
needed; no out-of-memory guard unless jobs return with failure results.

## What changed

- All 50 jobs waiting on granite-guest (comparison No. 3 options A and C,
  the No. 3 out-of-memory repair pass, and No. 3b seeds 5-14) were
  resubmitted on notchpeak-guest (`-M notchpeak`, account `owner-guest`,
  QoS `notchpeak-guest`, `--constraint=gen`) and the granite copies were
  cancelled. None had started, so no compute was lost. Old to new job ids:
  [`move_2026-10-09/JOBMAP.txt`](move_2026-10-09/JOBMAP.txt).
- Same batch scripts, driver, inputs, scratch folders and `--export`
  settings as the original submissions (16 calls, campaign cap 25,
  window cap 30, proportional mask 25%). Only the scheduler request changed.
- Option 3 applied: DTDE jobs request 372000M, so any Genoa node with
  384 GB or more can take them. DTDE reserves the worst case for every job
  and never runs more than two streams, so the three-stream 2H case that
  caused the out-of-memory kills cannot occur in this arm.
- CEDT_P4, MIX50, CTDE_P2 and the repair pass request 500000M (Genoa
  nodes with 768 GB or 1.5 TB), as under the 6 Oct rule.
- Option 2 (Intel Emerald Rapids nodes) not applied. It would split the
  cost analysis by CPU type; held in reserve.
- The out-of-memory guard was not restarted. If a campaign returns an
  out-of-memory kill or `ok:false`, it is repaired by hand.

## Not moved

- `l3_CEDT_P4_s13` (granite 2089159) was already running on grn021.
  Its DTDE partner now runs on notchpeak.
- No. 3b seeds 0-4 stay on grn061 (`sparks-gpu-grn`, 8 Oct change).

## Effect on the analysis

- The granite-guest Genoa nodes (96 cores) and the notchpeak-guest Genoa
  nodes (64 to 192 cores) both run 64-rank campaigns with other jobs on
  the remaining cores, so co-tenant conditions are of the same kind as
  before. The grading must record the cluster and node of each campaign.
  Pairs whose two arms ran on different clusters (No. 3 seeds 0, 10, 13
  and the option C arms whose DTDE or CEDT partner ran on granite) are to
  be reported as such, with a sensitivity check that drops them.
- Gaps and qualifier decisions do not depend on hardware.

#!/bin/bash
# Guarded submission of the 81-job F1 pilot (see README.md).
# Refuses to run without explicit authorization and a node-hour
# cap; stops before the projected spend would exceed the cap.
set -euo pipefail
cd "$(dirname "$0")"

if [ "${PILOT_AUTHORIZED:-0}" != "1" ]; then
  echo "REFUSING: set PILOT_AUTHORIZED=1 only after case_manifest.yaml" >&2
  echo "records authorized_chpc_pilot: true (set by the authors)." >&2
  exit 2
fi
if [ -z "${MAX_NODE_HOURS:-}" ]; then
  echo "REFUSING: set MAX_NODE_HOURS (live_node_hour_cap, allocation owner)." >&2
  exit 2
fi
if ! ls pseudos/*.[Uu][Pp][Ff] >/dev/null 2>&1; then
  echo "REFUSING: pseudos/ is empty — see README.md step 3." >&2
  exit 2
fi

# Target selection:
# granite partition sparks-gpu-grn (node grn061, 64 cores) by default;
# kingspeak general allocation only if more than one node is needed.
# CAUTION (verified live via sbatch --test-only): sparks-gpu-grn has
# PreemptMode=CANCEL — submissions cancel running granite-gpu-guest jobs
# on grn061. Check `squeue -p sparks-gpu-grn` before authorizing.
TARGET="${PILOT_TARGET:-granite}"

# worst case per job: nodes * 0.5 h (30-min wall); on granite a "node" is
# recast as 16 cores of grn061, so the same accounting stays conservative
projected=0
submitted=0
while IFS=, read -r order jid cand nodes npool agg rep; do
  cost=$(awk "BEGIN{print $nodes*0.5}")
  projected=$(awk "BEGIN{print $projected+$cost}")
  over=$(awk "BEGIN{print ($projected>$MAX_NODE_HOURS)?1:0}")
  if [ "$over" = "1" ]; then
    echo "STOP: projected worst-case spend ${projected} nh would exceed cap ${MAX_NODE_HOURS} nh after ${submitted} jobs." >&2
    exit 3
  fi
  ntasks=$((nodes * 16))
  if [ "$TARGET" = "granite" ]; then
    # single-node partition: recast N former nodes as N*16 tasks (max 64)
    sbatch --partition=sparks-gpu-grn --qos=sparks-gpu-grn \
           --nodes=1 --ntasks="$ntasks" \
           --export=ALL,PILOT_CAND="$cand",PILOT_NPOOL="$npool",PILOT_AGG="$agg",PILOT_JOBID="$jid" \
           job_template.sbatch
  else
    # fallback: kingspeak general allocation (16+ cores/node)
    sbatch --partition=kingspeak --qos=kingspeak \
           --nodes="$nodes" --ntasks="$ntasks" \
           --export=ALL,PILOT_CAND="$cand",PILOT_NPOOL="$npool",PILOT_AGG="$agg",PILOT_JOBID="$jid" \
           job_template.sbatch
  fi
  submitted=$((submitted + 1))
done < <(tail -n +2 job_matrix.csv)
echo "submitted all ${submitted:-0} jobs within cap (target=${TARGET})."

#!/bin/bash
# Stage and submit the F3 repair pass on granite grn061, dependent on
# window B (job 1973176) finishing. Requires an established SSH
# connection (an authenticated login):
#   ssh -fNM -o ControlPath=~/.ssh/cm/%r@%h:%p "$CHPC_USERNAME@granite1.chpc.utah.edu"
# Never prints credentials.
set -euo pipefail
cd "$(dirname "$0")"
: "${CHPC_USERNAME:?}"
WINB="${MPT_WINB_JOBID:-1973176}"
SSHOPT="-o ControlPath=$HOME/.ssh/cm/%r@%h:%p"
G="$CHPC_USERNAME@granite1.chpc.utah.edu"
R() { ssh $SSHOPT "$G" "bash -lc '$*'"; }

SCR=$(R 'echo /scratch/general/vast/$USER')
L2="$SCR/mpt_live2"

echo "== stage =="
R "mkdir -p $L2/f3_repair"
scp -q $SSHOPT repair_driver.py repair.sbatch "$G:$L2/f3_repair/"
R "cd $L2 && python3 -m py_compile f3_repair/repair_driver.py && echo COMPILE_OK" \
  || { echo "remote compile failed"; exit 1; }

echo "== submit (afterany:$WINB) =="
JR=$(R "cd $L2 && sbatch --dependency=afterany:$WINB \
  --export=ALL,MPT_LIVE2_ROOT=$L2,MPT_REPAIR_CAP=80 \
  f3_repair/repair.sbatch" | grep -o '[0-9]*')
echo "SUBMITTED repair=$JR (afterany:$WINB)"
echo "$JR" > .repair_jobid
R "squeue -u \$USER -o '%.10i %.14j %.2t %.10M %.12E %R'"

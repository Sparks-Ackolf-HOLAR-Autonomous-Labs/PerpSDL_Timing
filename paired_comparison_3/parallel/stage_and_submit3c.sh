#!/bin/bash
# Comparison No. 3 option C (2026-10-01): adds the two arms
# option A lacks, on the same 15 seeds, as one campaign per job on the
# free granite-guest partition:
#   MIX50    half delegation, proportional timing mask (25%) on the
#            broker-routed half
#   CTDE_P2  shared training logbook (ctde_logbook_seed.json), no mask
# Staged in a separate scratch dir (mpt_live3c) so the pending option-A
# jobs in mpt_live3 keep the driver they were submitted with.
# Needs an open SSH connection to granite1 (never prints secrets).
set -euo pipefail
cd "$(dirname "$0")"
: "${CHPC_USERNAME:?}"
SSHOPT="-o ControlPath=$HOME/.ssh/cm/%r@%h:%p -o BatchMode=yes"
G="$CHPC_USERNAME@granite1.chpc.utah.edu"
R() { ssh $SSHOPT "$G" "bash -lc '$*'"; }
SCR=$(R 'echo /scratch/general/vast/$USER')
A="$SCR/mpt_live3"
B="$SCR/mpt_live3c"
R "mkdir -p $B/logs $B/results && cp -r $A/pseudos $A/inputs $B/ && ls $B/inputs | wc -l"
scp -q $SSHOPT ../../paired_comparison_2/live2_campaign.py ../../qe_retry.py \
    live3_guest.sbatch ctde_logbook_seed.json "$G:$B/"
R "cd $B && python3 -m py_compile live2_campaign.py && echo COMPILE_OK"
: > .live3c_jobids
for s in $(seq 0 14); do
  for arm in MIX50 CTDE_P2; do
    RD="$B/results/${arm}_s$s"
    J=$(R "mkdir -p $RD && cd $B && sbatch -J l3_${arm}_s$s --export=ALL,MPT_LIVE2_ROOT=$B,MPT_RESULTS=$RD,MPT_WORK=$B/work,MPT_CAMPAIGN=$arm:$s,MPT_MAX_CALLS=16,MPT_CAMP_CAP=25,MPT_W_CAP=30,MPT_MASK=prop,MPT_MASK_FRAC=0.25 live3_guest.sbatch" | grep -o '[0-9]*')
    echo "$arm $s $J" | tee -a .live3c_jobids
  done
done
R "squeue -u \$USER -h | wc -l"

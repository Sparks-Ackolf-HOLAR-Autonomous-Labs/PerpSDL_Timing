#!/bin/bash
# Stage and submit comparison No. 3b on the free granite-guest partition
# (5 Oct 2026). Same design as No. 3 option A: 15 seeds x
# {DTDE, CEDT_P4}, one job per campaign, 16 calls, proportional timing
# mask (25 %), 25 pc-nh per campaign; only the inputs differ (single
# layers, inputs/ from build_live3b_inputs.py). Separate scratch tree
# mpt_live3b so No. 3 (mpt_live3, mpt_live3c) is untouched.
# Needs an open SSH connection (never prints secrets). Default login
# host is notchpeak with sbatch -M granite (scratch is shared).
set -euo pipefail
cd "$(dirname "$0")"
: "${CHPC_USERNAME:?}"
HOST=${CHPC_HOST:-notchpeak.chpc.utah.edu}
SSHOPT="-o ControlPath=$HOME/.ssh/cm/%r@%h:%p -o BatchMode=yes"
G="$CHPC_USERNAME@$HOST"
R() { ssh $SSHOPT "$G" "bash -lc '$*'"; }
L2=../paired_comparison_2
SCR=$(R 'echo /scratch/general/vast/$USER')
B="$SCR/mpt_live3b"
R "mkdir -p $B/pseudos $B/inputs $B/logs $B/results && cp -n $SCR/mpt_live3/pseudos/*.UPF $B/pseudos/ && ls $B/pseudos/*.UPF | wc -l"
scp -q $SSHOPT inputs/*.in inputs/manifest2.json "$G:$B/inputs/"
scp -q $SSHOPT ../qe_retry.py $L2/live2_campaign.py live3b_guest.sbatch "$G:$B/"
R "cd $B && module load python/3.10.3 && python3 -m py_compile live2_campaign.py && ls inputs/*.in | wc -l && echo COMPILE_OK"
: > .live3b_jobids
for s in $(seq 0 14); do
  for arm in DTDE CEDT_P4; do
    RD="$B/results/${arm}_s$s"
    J=$(R "mkdir -p $RD && cd $B && sbatch -M granite -J l3b_${arm}_s$s --export=ALL,MPT_LIVE2_ROOT=$B,MPT_RESULTS=$RD,MPT_WORK=$B/work,MPT_CAMPAIGN=$arm:$s,MPT_MAX_CALLS=16,MPT_CAMP_CAP=25,MPT_W_CAP=30,MPT_MASK=prop,MPT_MASK_FRAC=0.25 live3b_guest.sbatch" | grep -o '[0-9]*' | head -1)
    echo "$arm $s $J" | tee -a .live3b_jobids
  done
done
R "squeue -M granite -u \$USER -h -o %j | grep -c l3b_"

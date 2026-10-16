#!/bin/bash
# Stage and submit live comparison No. 2 on granite grn061 as two
# sequential windows (each inside the 14-day node limit):
#   window A: seeds 0-7  (8 pairs),  cap 280 billed pc-nh
#   window B: seeds 8-14 (7 pairs) + masked-vs-unmasked CEDT replay of
#             seeds 0-2 (the live timing-masking price), cap 240
# B is submitted with --dependency=afterany:A. Total cap 520 = the
# frozen max_per_core_node_hours.
#
# Requires an established SSH connection (an authenticated login):
#   ssh -fNM -o ControlPath=~/.ssh/cm/%r@%h:%p "$CHPC_USERNAME@granite1.chpc.utah.edu"
# Never prints credentials.
set -euo pipefail
cd "$(dirname "$0")"
: "${CHPC_USERNAME:?}"
SSHOPT="-o ControlPath=$HOME/.ssh/cm/%r@%h:%p"
G="$CHPC_USERNAME@granite1.chpc.utah.edu"
R() { ssh $SSHOPT "$G" "bash -lc '$*'"; }

SCR=$(R 'echo /scratch/general/vast/$USER')
L2="$SCR/mpt_live2"

echo "== occupancy check on grn061 (preemption courtesy) =="
R 'squeue -p sparks-gpu-grn -o "%.10i %.9P %.14j %.8u %.2t %.10M"' || true

echo "== pseudos =="
R "mkdir -p $L2/pseudos && cd $L2/pseudos && \
   for f in ti_pbe_v1.4.uspp.F.UPF zr_pbe_v1.uspp.F.UPF \
            hf_pbe_v1.uspp.F.UPF mo_pbe_v1.uspp.F.UPF \
            w_pbe_v1.2.uspp.F.UPF s_pbe_v1.4.uspp.F.UPF \
            se_pbe_v1.uspp.F.UPF te_pbe_v1.uspp.F.UPF; do \
     [ -f \$f ] || wget -q https://www.physics.rutgers.edu/gbrv/\$f; \
   done && ls *.UPF | wc -l"

echo "== stage =="
R "mkdir -p $L2/inputs $L2/results"
scp -q $SSHOPT ../qe_retry.py live2_campaign.py live2.sbatch analyze_live2.py "$G:$L2/"
scp -q $SSHOPT inputs/*.in inputs/manifest2.json "$G:$L2/inputs/"
R "cd $L2 && python3 -m py_compile live2_campaign.py && echo COMPILE_OK" \
  || { echo "remote compile failed"; exit 1; }

echo "== submit window A then B (afterany) =="
JA=$(R "cd $L2 && sbatch --export=ALL,MPT_LIVE2_ROOT=$L2,MPT_SEED_LO=0,MPT_SEED_HI=7,MPT_W_CAP=280,MPT_QUANT=600 live2.sbatch" | grep -o '[0-9]*')
JB=$(R "cd $L2 && sbatch --dependency=afterany:$JA --export=ALL,MPT_LIVE2_ROOT=$L2,MPT_SEED_LO=8,MPT_SEED_HI=14,MPT_W_CAP=240,MPT_QUANT=600,MPT_REPLAY_SEEDS=0:1:2 live2.sbatch" | grep -o '[0-9]*')
echo "SUBMITTED windowA=$JA windowB=$JB"
echo "$JA $JB" > .live2_jobids
R "squeue -u \$USER -o '%.10i %.14j %.2t %.10M %R'"

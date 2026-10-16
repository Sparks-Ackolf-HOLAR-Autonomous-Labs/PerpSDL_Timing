#!/bin/bash
# Stage and submit routes 2 and 3 for comparison No. 3 on the free
# granite-guest partition (2026-09-30).
#   route 3 step 1: library array (fast_path/library.sbatch, 14 tasks)
#   route 2:        option A, 15 seeds x {DTDE, CEDT_P4}, one job per
#                   campaign, 16 calls, proportional timing mask (25%)
# Needs an open SSH connection to granite1 (never prints secrets).
set -euo pipefail
cd "$(dirname "$0")"
: "${CHPC_USERNAME:?}"
SSHOPT="-o ControlPath=$HOME/.ssh/cm/%r@%h:%p -o BatchMode=yes"
G="$CHPC_USERNAME@granite1.chpc.utah.edu"
R() { ssh $SSHOPT "$G" "bash -lc '$*'"; }
L2=../../paired_comparison_2
FP=../../fast_path
SCR=$(R 'echo /scratch/general/vast/$USER')
B="$SCR/mpt_live3"
LIB="$SCR/mpt_lib3"

for D in "$B" "$LIB"; do
  R "mkdir -p $D/pseudos $D/inputs $D/logs $D/results && cd $D/pseudos && \
     for f in ti_pbe_v1.4.uspp.F.UPF zr_pbe_v1.uspp.F.UPF \
              hf_pbe_v1.uspp.F.UPF mo_pbe_v1.uspp.F.UPF \
              w_pbe_v1.2.uspp.F.UPF s_pbe_v1.4.uspp.F.UPF \
              se_pbe_v1.uspp.F.UPF te_pbe_v1.uspp.F.UPF; do \
       [ -f \$f ] || wget -q https://www.physics.rutgers.edu/gbrv/\$f; \
     done && ls *.UPF | wc -l"
  scp -q $SSHOPT $L2/inputs/*.in $L2/inputs/manifest2.json "$G:$D/inputs/"
  scp -q $SSHOPT ../../qe_retry.py "$G:$D/"
done
scp -q $SSHOPT $L2/live2_campaign.py live3_guest.sbatch "$G:$B/"
scp -q $SSHOPT $FP/library_ladder.py $FP/library.sbatch $FP/compounds.txt "$G:$LIB/"
R "cd $B && python3 -m py_compile live2_campaign.py && cd $LIB && python3 -m py_compile library_ladder.py && echo COMPILE_OK"

echo "== route 3 step 1: library array =="
JL=$(R "cd $LIB && sbatch --export=ALL,MPT_LIB_ROOT=$LIB library.sbatch" | grep -o '[0-9]*')
echo "library array $JL"

echo "== route 2: 30 campaigns =="
: > .live3_jobids
for s in $(seq 0 14); do
  for arm in DTDE CEDT_P4; do
    RD="$B/results/${arm}_s$s"
    J=$(R "mkdir -p $RD && cd $B && sbatch -J l3_${arm}_s$s --export=ALL,MPT_LIVE2_ROOT=$B,MPT_RESULTS=$RD,MPT_WORK=$B/work,MPT_CAMPAIGN=$arm:$s,MPT_MAX_CALLS=16,MPT_CAMP_CAP=25,MPT_W_CAP=30,MPT_MASK=prop,MPT_MASK_FRAC=0.25 live3_guest.sbatch" | grep -o '[0-9]*')
    echo "$arm $s $J" | tee -a .live3_jobids
  done
done
echo "library $JL" >> .live3_jobids
R "squeue -u \$USER -o \"%.10i %.14j %.2t %.10M %R\""

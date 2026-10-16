#!/bin/bash
# Stage and submit the 2H geometry check on the free granite-guest
# partition. Requires an authenticated SSH connection to the cluster
# (CHPC uses Duo two-factor login), opened with:
#   ssh -fNM -o ControlPath=~/.ssh/cm/%r@%h:%p "$CHPC_USERNAME@granite1.chpc.utah.edu"
# Set MPT_STACK_SUBMIT=1 to submit after the --test-only check.
set -euo pipefail
cd "$(dirname "$0")"
: "${CHPC_USERNAME:?}"
SSHOPT="-o ControlPath=$HOME/.ssh/cm/%r@%h:%p"
G="$CHPC_USERNAME@granite1.chpc.utah.edu"
R() { ssh $SSHOPT "$G" "bash -lc '$*'"; }
SCR=$(R 'echo /scratch/general/vast/$USER')
LS="$SCR/mpt_stack"
GPART="${MPT_GUEST_PART:-granite-guest}"
GACCT="${MPT_GUEST_ACCT:-sparks}"
GQOS="${MPT_GUEST_QOS:-granite-guest}"
R "mkdir -p $LS/pseudos $LS/results && cd $LS/pseudos && \
   for f in ti_pbe_v1.4.uspp.F.UPF zr_pbe_v1.uspp.F.UPF \
            hf_pbe_v1.uspp.F.UPF mo_pbe_v1.uspp.F.UPF \
            w_pbe_v1.2.uspp.F.UPF s_pbe_v1.4.uspp.F.UPF \
            se_pbe_v1.uspp.F.UPF te_pbe_v1.uspp.F.UPF; do \
     [ -f \$f ] || wget -q https://www.physics.rutgers.edu/gbrv/\$f; \
   done && echo pseudos=\$(ls *.UPF | wc -l)"
scp -q $SSHOPT run_stacking.py stacking.sbatch ../dft_campaign/run_campaign.py "$G:$LS/"
R "cd $LS && module load python/3.10.3 && python3 -m py_compile run_stacking.py run_campaign.py && echo COMPILE_OK"
R "cd $LS && sbatch --test-only --account=$GACCT --partition=$GPART --qos=$GQOS \
   --export=ALL,MPT_DFT_ROOT=$LS stacking.sbatch" || true
if [ "${MPT_STACK_SUBMIT:-0}" = "1" ]; then
  JID=$(R "cd $LS && sbatch --account=$GACCT --partition=$GPART --qos=$GQOS \
        --export=ALL,MPT_DFT_ROOT=$LS stacking.sbatch" | grep -o '[0-9]*')
  echo "SUBMITTED stacking job=$JID part=$GPART"
  echo "$JID $GPART" > .stack_jobid
  R "squeue -u \$USER -o '%.12i %.14j %.14P %.2t %.10M %R'"
fi

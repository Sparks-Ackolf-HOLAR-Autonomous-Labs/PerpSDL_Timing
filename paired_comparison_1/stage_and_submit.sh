#!/bin/bash
# Stage and submit the live comparison (item 1) and the contention/
# transfer bench (items 2+5) on granite grn061.
#
# Requires an established SSH connection (an authenticated login):
#   ssh -fNM -o ControlPath=~/.ssh/cm/%r@%h:%p "$CHPC_USERNAME@granite1.chpc.utah.edu"
# Never prints credentials. Estimated spend: bench ~1 nh, live 20-40 nh
# (guards: bench 5 nh, live 100 nh, SLURM --time hard stops).
set -euo pipefail
cd "$(dirname "$0")"
: "${CHPC_USERNAME:?}"
SSHOPT="-o ControlPath=$HOME/.ssh/cm/%r@%h:%p"
H="$CHPC_USERNAME@granite1.chpc.utah.edu"
R() { ssh $SSHOPT "$H" "bash -lc '$*'"; }

SCR=$(R 'echo /scratch/general/vast/$USER')
LIVE="$SCR/mpt_live"
BENCH="$SCR/mpt_bench"

echo "== occupancy check (preemption courtesy) =="
R 'squeue -p sparks-gpu-grn -o "%.10i %.9P %.14j %.8u %.2t %.10M"' || true

echo "== locate pseudopotentials on granite =="
PSEUDIR=""
for cand in "$SCR/mpt_dft/pseudos" "$SCR/mpt_pilot/pseudos" \
            "\$HOME/mpt_dft_results/pseudos"; do
  if R "ls $cand/*.UPF >/dev/null 2>&1"; then PSEUDIR="$cand"; break; fi
done
if [ -z "$PSEUDIR" ]; then
  echo "no pseudos found on granite; downloading GBRV set remotely"
  R "mkdir -p $LIVE/pseudos && cd $LIVE/pseudos && \
     for f in ti_pbe_v1.4.uspp.F.UPF zr_pbe_v1.uspp.F.UPF \
              hf_pbe_v1.uspp.F.UPF mo_pbe_v1.uspp.F.UPF \
              w_pbe_v1.2.uspp.F.UPF s_pbe_v1.4.uspp.F.UPF \
              se_pbe_v1.uspp.F.UPF te_pbe_v1.uspp.F.UPF; do \
       [ -f \$f ] || wget -q https://www.physics.rutgers.edu/gbrv/\$f; \
     done && ls *.UPF | wc -l"
  PSEUDIR="$LIVE/pseudos"
fi
echo "pseudos: $PSEUDIR"

echo "== stage live comparison =="
R "mkdir -p $LIVE"
scp -q $SSHOPT live_campaign.py live.sbatch analyze_live.py "$H:$LIVE/"
scp -qr $SSHOPT inputs "$H:$LIVE/"
[ "$PSEUDIR" = "$LIVE/pseudos" ] || R "rm -rf $LIVE/pseudos && cp -r $PSEUDIR $LIVE/pseudos"

echo "== stage bench =="
R "mkdir -p $BENCH/inputs"
scp -q $SSHOPT ../contention_transfer_bench/bench.py ../contention_transfer_bench/bench.sbatch "$H:$BENCH/"
scp -q $SSHOPT ../contention_transfer_bench/inputs/*.pw.in ../scale_validation/inputs/*.pw.in "$H:$BENCH/inputs/"
R "rm -rf $BENCH/pseudos && cp -r $LIVE/pseudos $BENCH/pseudos"

echo "== submit (bench first, then live) =="
BJ=$(R "cd $BENCH && sbatch --export=ALL,MPT_BENCH_ROOT=$BENCH bench.sbatch" | grep -o '[0-9]*')
LJ=$(R "cd $LIVE && sbatch --export=ALL,MPT_LIVE_ROOT=$LIVE,MPT_LIVE_NH_CAP=100 live.sbatch" | grep -o '[0-9]*')
echo "SUBMITTED bench=$BJ live=$LJ"
echo "$BJ" > .bench_jobid
echo "$LJ" > .live_jobid
R "squeue -u \$USER -o '%.10i %.14j %.2t %.10M %R'"

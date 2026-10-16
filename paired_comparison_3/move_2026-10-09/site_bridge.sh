#!/bin/bash -l
# 9 Oct 2026: bridge copies and same-site baselines on notchpeak-guest.
# Part 1 (bridge): No. 3 A CEDT_P4 s0, DTDE s10, CEDT_P4 s13 (granite copies exist).
# Part 2 (same-site baselines for No. 3 C): DTDE s3-9, 11, 14 (s10 is already in part 1).
# Copies write to results_notchpeak/ and work_notchpeak/ so they never touch the
# granite results or the running granite CEDT s13 work folder.
set -u
MODE=${1:-test}
SCR=/scratch/general/vast/$USER
B=$SCR/mpt_live3
EXP="MPT_MAX_CALLS=16,MPT_CAMP_CAP=25,MPT_W_CAP=30,MPT_MASK=prop,MPT_MASK_FRAC=0.25"
NP="-M notchpeak -p notchpeak-guest --account=owner-guest --qos=notchpeak-guest --constraint=gen"
TO=""; [ "$MODE" = test ] && TO="--test-only"
cd $B; mkdir -p results_notchpeak work_notchpeak logs
for c in CEDT_P4:0:bridge DTDE:10:bridge CEDT_P4:13:bridge DTDE:3:base DTDE:4:base DTDE:5:base DTDE:6:base DTDE:7:base DTDE:8:base DTDE:9:base DTDE:11:base DTDE:14:base; do
  arm=${c%%:*}; rest=${c#*:}; s=${rest%%:*}; tag=${rest#*:}
  if [ $arm = DTDE ]; then mem=372000M; else mem=500000M; fi
  name=l3np_${arm}_s$s
  out=$(sbatch $TO $NP --mem=$mem -J $name --export=ALL,MPT_LIVE2_ROOT=$B,MPT_RESULTS=$B/results_notchpeak/${arm}_s$s,MPT_WORK=$B/work_notchpeak,MPT_CAMPAIGN=$arm:$s,$EXP live3_guest.sbatch 2>&1 | tr '\n' ' ')
  echo "$MODE $tag $name $mem: $out"
done

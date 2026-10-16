#!/bin/bash
#SBATCH --account=sparks
#SBATCH --partition=sparks-gpu-grn
#SBATCH --qos=sparks-gpu-grn
#SBATCH --nodes=1
#SBATCH --ntasks=32
#SBATCH --time=08:00:00
#SBATCH --job-name=mpt-scale
#SBATCH -o slurm-%j.out
# Win-win-scale validation: 8 sequential real SCF runs, 1x..16x electron
# counts. Per-run timeout 4 h; job wall 8 h caps total spend at 8 node-h
# (32/64 cores). GPU untouched.
set -uo pipefail
module load openmpi/5.0.3 quantum-espresso/7.4
export OMP_NUM_THREADS=1

WORK=/scratch/general/vast/$USER/mpt_scale
mkdir -p "$WORK/out" "$WORK/pseudos"
cp "$SLURM_SUBMIT_DIR"/pseudos/*.UPF "$WORK/pseudos/" 2>/dev/null || true
cd "$WORK"
: > results.jsonl
for inp in "$SLURM_SUBMIT_DIR"/inputs/*.pw.in; do
  name=$(basename "$inp" .pw.in)
  cp "$inp" pw.in
  npool=2
  case "$name" in *_k3) npool=1;; *_k12) npool=4;; esac
  t0=$(date +%s)
  timeout 4h mpirun -np "$SLURM_NTASKS" --bind-to none \
    pw.x -npool "$npool" -in pw.in > "${name}.out" 2>&1
  rc=$?
  t1=$(date +%s)
  wall=$((t1 - t0))
  conv=$(grep -c "convergence has been achieved" "${name}.out" || true)
  nelec=$(grep "number of electrons" "${name}.out" | head -1 | awk '{print $NF}')
  nk=$(grep "number of k points" "${name}.out" | head -1 | awk '{print $5}')
  echo "{\"name\": \"$name\", \"rc\": $rc, \"wall_s\": $wall, \"converged\": $conv, \"nelec\": \"${nelec:-null}\", \"nk\": \"${nk:-null}\", \"ranks\": $SLURM_NTASKS, \"npool\": $npool}" >> results.jsonl
  echo "done $name rc=$rc wall=${wall}s"
done
mkdir -p ~/mpt_scale_results && cp results.jsonl *.out ~/mpt_scale_results/ 2>/dev/null || true
echo ALL_DONE

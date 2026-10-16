#!/bin/bash
#SBATCH --account=sparks
#SBATCH --partition=sparks-gpu-grn
#SBATCH --qos=sparks-gpu-grn
#SBATCH --nodes=1
#SBATCH --ntasks=32
#SBATCH --time=02:00:00
#SBATCH --job-name=mpt-layers
#SBATCH -o slurm-%j.out
# Layers/N-axis scale-validation extension: 17 sequential SCFs (z-stacks x
# in-plane supercells x strained setups x 3 materials). Per-run timeout
# 30 min; 2 h wall caps total spend at 2 node-hours. CPU only, GPU untouched.
set -uo pipefail
module load openmpi/5.0.3 quantum-espresso/7.4
export OMP_NUM_THREADS=1

WORK=/scratch/general/vast/$USER/mpt_layers
mkdir -p "$WORK/out" "$WORK/pseudos"
cp "$SLURM_SUBMIT_DIR"/pseudos/*.UPF "$WORK/pseudos/" 2>/dev/null || true
cd "$WORK"
: > results.jsonl
for inp in "$SLURM_SUBMIT_DIR"/inputs/*.pw.in; do
  name=$(basename "$inp" .pw.in)
  cp "$inp" pw.in
  t0=$(date +%s)
  timeout 30m mpirun -np "$SLURM_NTASKS" --bind-to none \
    pw.x -npool 2 -in pw.in > "${name}.out" 2>&1
  rc=$?
  t1=$(date +%s)
  wall=$((t1 - t0))
  conv=$(grep -c "convergence has been achieved" "${name}.out" || true)
  nelec=$(grep "number of electrons" "${name}.out" | head -1 | awk '{print $NF}')
  nat=$(grep "number of atoms/cell" "${name}.out" | head -1 | awk '{print $NF}')
  iters=$(grep -c "iteration #" "${name}.out" || true)
  etot=$(grep "^!" "${name}.out" | tail -1 | awk '{print $(NF-1)}')
  echo "{\"name\": \"$name\", \"rc\": $rc, \"wall_s\": $wall, \"converged\": $conv, \"nelec\": \"${nelec:-null}\", \"nat\": \"${nat:-null}\", \"scf_iters\": $iters, \"etot_ry\": \"${etot:-null}\", \"ranks\": $SLURM_NTASKS, \"npool\": 2}" >> results.jsonl
  echo "done $name rc=$rc wall=${wall}s"
done
mkdir -p ~/mpt_layers_results && cp results.jsonl *.out ~/mpt_layers_results/ 2>/dev/null || true
echo ALL_DONE

#!/bin/bash
#SBATCH --job-name=mpt_soc
#SBATCH --account=sparks
#SBATCH --partition=sparks-gpu-grn
#SBATCH --qos=sparks-gpu-grn
#SBATCH --nodelist=grn061
#SBATCH --nodes=1
#SBATCH --ntasks=48
#SBATCH --mem=180G
#SBATCH --time=4:00:00
#SBATCH --output=soc_%j.log
# SOC band gaps for the 9 finalists (optional manifest item).
# CPU-only pw.x; leaves the resident GPU job untouched (same QoS, no
# preemption). Soft node-hour guard well under the SLURM --time.
set -euo pipefail
module load openmpi/5.0.3 quantum-espresso/7.4
# without this, each rank spawns one OpenMP thread per hardware thread
# (96) and 16 ranks oversubscribe the node ~30x — job 1914220 was
# cancelled for exactly that; 1914274 is the corrected resubmission
export OMP_NUM_THREADS=1

export MPT_SOC_ROOT="/scratch/general/vast/$USER/mpt_soc"
export MPT_NPROC_PER_RUN=16
export MPT_NPOOL=4
export MPT_WORKERS=3
export MPT_NODE_HOUR_CAP=10

cd "$MPT_SOC_ROOT"
python3 soc_campaign.py
cp -r results ~/mpt_soc_results_$SLURM_JOB_ID
echo "results parked at ~/mpt_soc_results_$SLURM_JOB_ID"

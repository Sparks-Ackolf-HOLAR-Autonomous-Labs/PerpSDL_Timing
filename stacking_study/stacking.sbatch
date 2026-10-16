#!/bin/bash
#SBATCH --job-name=mpt_stack
#SBATCH --nodes=1
#SBATCH --ntasks=32
#SBATCH --mem=120G
#SBATCH --time=24:00:00
#SBATCH --output=stack_%j.log
# 2H geometry check: 15 compositions x {2H monolayer,
# 2H bilayer + D3, 3R bilayer + D3}, PBE/GBRV F1-F3 ladder. Free
# granite-guest partition; account/partition/qos supplied at submission.
set -euo pipefail
module load openmpi/5.0.3 quantum-espresso/7.4 python/3.10.3
export OMP_NUM_THREADS=1 MPT_NPROC_PER_RUN=16 MPT_NPOOL=4 MPT_WORKERS=2
export MPT_NODE_HOUR_CAP=12
cd "${MPT_DFT_ROOT:?}"
python3 run_stacking.py
mkdir -p "$HOME/mpt_stack_results"
cp -r results "$HOME/mpt_stack_results/results_$SLURM_JOB_ID"

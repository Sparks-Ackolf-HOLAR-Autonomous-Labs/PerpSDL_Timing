#!/bin/bash
#SBATCH --job-name=mpt_dft_campaign
#SBATCH --account=sparks
#SBATCH --partition=sparks-gpu-grn
#SBATCH --qos=sparks-gpu-grn
#SBATCH --nodes=1
#SBATCH --ntasks=48
#SBATCH --mem=180G
#SBATCH --time=20160
#SBATCH --output=campaign_%j.log
# Actual-DFT fidelity-ladder campaign on the 30 CC0 MX2 candidates
# --time=20160 minutes is the node time
# limit for the entire run; the driver's soft cap stops earlier.
# 48 of 64 cores + 180G leaves room for the resident GPU job on grn061.
set -euo pipefail
module load openmpi/5.0.3 quantum-espresso/7.4
export OMP_NUM_THREADS=1
export MPT_DFT_ROOT="${MPT_DFT_ROOT:-/scratch/general/vast/$USER/mpt_dft}"
cd "$MPT_DFT_ROOT"
python3 run_campaign.py
# keep a copy of the results off scratch (purge policy)
mkdir -p "$HOME/mpt_dft_results"
cp -r results "$HOME/mpt_dft_results/results_$SLURM_JOB_ID"

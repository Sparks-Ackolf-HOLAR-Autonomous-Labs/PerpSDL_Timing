#!/bin/bash
#SBATCH --job-name=mpt_lib3
#SBATCH --account=sparks
#SBATCH --partition=granite-guest
#SBATCH --qos=granite-guest
#SBATCH --constraint=gen
#SBATCH --nodes=1
#SBATCH --ntasks=16
#SBATCH --mem=180G
#SBATCH --time=72:00:00
#SBATCH --requeue
#SBATCH --array=0-13
#SBATCH --output=logs/lib3_%A_%a.log
# Route 3, step 1: one compound's F1-F3 ladder per array
# task on the free granite-guest partition, pinned to the AMD node
# family of grn061 (feature gen). See library_ladder.py.
set -euo pipefail
module load openmpi/5.0.3 quantum-espresso/7.4 python/3.10.3
cd "${MPT_LIB_ROOT:?set MPT_LIB_ROOT}"
python3 library_ladder.py

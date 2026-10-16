#!/bin/bash
#SBATCH --job-name=mpt_live3b
#SBATCH --account=sparks
#SBATCH --partition=granite-guest
#SBATCH --qos=granite-guest
#SBATCH --constraint=gen
#SBATCH --nodes=1
#SBATCH --ntasks=64
#SBATCH --mem=372000M
#SBATCH --time=72:00:00
#SBATCH --requeue
#SBATCH --output=logs/live3b_%x_%j.log
# Comparison No. 3b (single layers), option A design: ONE
# campaign per job on the free, preemptible granite-guest partition.
# --constraint=gen pins the AMD node family of grn061 so run times stay
# comparable with the No. 2 records; 64 ranks x 372000M reproduces the
# 64-core / 380-GB node the driver's packing and billing assume. A
# cancelled job is requeued and restarts its campaign (driver discards
# the lost attempt). Campaign, seed, mask and call budget come from
# --export (stage_and_submit3b.sh).
set -euo pipefail
module load openmpi/5.0.3 quantum-espresso/7.4 python/3.10.3
cd "${MPT_LIVE2_ROOT:?set MPT_LIVE2_ROOT}"
python3 live2_campaign.py

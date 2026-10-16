#!/bin/bash
#SBATCH --job-name=mpt_f3repair
#SBATCH --account=sparks
#SBATCH --partition=sparks-gpu-grn
#SBATCH --qos=sparks-gpu-grn
#SBATCH --nodes=1
#SBATCH --ntasks=64
#SBATCH --mem=0
#SBATCH --time=144:00:00
#SBATCH --output=f3repair_%j.log
# F3 repair pass for comparison No. 2 attempt 2.
# Submitted with --dependency=afterany:<windowB> so it starts only when
# job 1973176 has finished and results/campaigns.jsonl is complete.
# --mem=0 (whole node) per the attempt-1 void-run lesson. CPU-only
# pw.x; the H100 is untouched. Budget guard: MPT_REPAIR_CAP billed
# pc-nh inside the driver; --time 144 h is the hard stop.
set -euo pipefail
module load openmpi/5.0.3 quantum-espresso/7.4 python/3.10.3
cd "${MPT_LIVE2_ROOT:?set MPT_LIVE2_ROOT}"
python3 f3_repair/repair_driver.py

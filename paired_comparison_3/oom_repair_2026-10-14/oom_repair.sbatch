#!/bin/bash -l
#SBATCH --job-name=l3_oom_repair
#SBATCH --account=sparks
#SBATCH --partition=granite-guest
#SBATCH --qos=granite-guest
#SBATCH --constraint=gen&m768
#SBATCH --nodes=1
#SBATCH --ntasks=64
#SBATCH --mem=500000M
#SBATCH --time=36:00:00
#SBATCH --requeue
#SBATCH --output=oom_repair_%j.log
# Repair pass for the three OOM-killed calls of comparison No. 3
# (decision of 6 Oct 2026). Same AMD node family as
# the campaigns (gen), but a 768-GB node and 500 GB requested so the
# three co-resident 2H streams (368-387 GB measured) fit. 3 x 16 ranks
# of the 64 requested cores. Free, preemptible guest partition; a
# requeue restarts the pass from the beginning.
set -euo pipefail
module load openmpi/5.0.3 quantum-espresso/7.4 python/3.10.3
cd "${MPT_REPAIR_DIR:?set MPT_REPAIR_DIR}"
python3 oom_repair_driver.py

#!/bin/bash
#SBATCH --job-name=mpt_live_cmp
#SBATCH --account=sparks
#SBATCH --partition=sparks-gpu-grn
#SBATCH --qos=sparks-gpu-grn
#SBATCH --nodes=1
#SBATCH --ntasks=64
#SBATCH --time=120:00:00
#SBATCH --output=live_%j.log
# Live paired CEDT-P4 vs DTDE comparison (preregistered;
# future-work item 1). CPU-only pw.x on grn061; the H100 is untouched.
# Guards: MPT_LIVE_NH_CAP refuses new QE calls past the cap; --time is
# the hard stop (node limit is 20160 min; we use far less).
set -euo pipefail
# python/3.10.3: granite's default python3 is 3.6.8, which lacks the
# walrus operator and time.time_ns these drivers use (jobs 1919941/2
# failed on this).
module load openmpi/5.0.3 quantum-espresso/7.4 python/3.10.3
cd "${MPT_LIVE_ROOT:?set MPT_LIVE_ROOT to the staged paired_comparison_1 dir}"
export MPT_LIVE_NH_CAP="${MPT_LIVE_NH_CAP:-100}"
export MPT_LIVE_SEEDS=10
export MPT_LIVE_MAX_CALLS=24
export MPT_LIVE_CAMPAIGN_NH=5.0
python3 live_campaign.py

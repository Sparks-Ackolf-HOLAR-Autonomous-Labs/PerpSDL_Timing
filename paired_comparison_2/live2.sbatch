#!/bin/bash
#SBATCH --job-name=mpt_live2
#SBATCH --account=sparks
#SBATCH --partition=sparks-gpu-grn
#SBATCH --qos=sparks-gpu-grn
#SBATCH --nodes=1
#SBATCH --ntasks=64
#SBATCH --mem=0
#SBATCH --time=320:00:00
#SBATCH --output=live2_%j.log
# Live comparison No. 2 window. CPU-only pw.x on grn061;
# the H100 is untouched. Budget guard: MPT_W_CAP billed pc-nh (launch
# refused beyond it); --time 320 h is the hard stop, inside the
# 20160-min node limit. Window/seed range and masking come from the
# environment set by stage_and_submit2.sh.
set -euo pipefail
module load openmpi/5.0.3 quantum-espresso/7.4 python/3.10.3
cd "${MPT_LIVE2_ROOT:?set MPT_LIVE2_ROOT}"
python3 live2_campaign.py

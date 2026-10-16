#!/bin/bash
#SBATCH --job-name=mpt_bench
#SBATCH --account=sparks
#SBATCH --partition=sparks-gpu-grn
#SBATCH --qos=sparks-gpu-grn
#SBATCH --nodes=1
#SBATCH --ntasks=64
#SBATCH --time=04:00:00
#SBATCH --output=bench_%j.log
# Contention-vs-scale + transfer benchmark (items 2 + 5).
# CPU-only pw.x; the H100 is untouched. ~1 node-hour expected, 5 nh guard.
set -euo pipefail
# python/3.10.3: granite's default python3 is 3.6.8 (job 1919941 failed
# on time.time_ns).
module load openmpi/5.0.3 quantum-espresso/7.4 python/3.10.3
cd "${MPT_BENCH_ROOT:?set MPT_BENCH_ROOT to the staged bench dir}"
export MPT_BENCH_NH_CAP=5.0
python3 bench.py

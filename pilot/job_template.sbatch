#!/bin/bash
#SBATCH --account=sparks
#SBATCH --partition=sparks-gpu-grn
#SBATCH --qos=sparks-gpu-grn
#SBATCH --time=00:30:00
#SBATCH --job-name=mpt-pilot-f1
#SBATCH -o slurm-%j.out
# nodes/ntasks are set by submit.sh via sbatch flags; the job payload is
# parametrized entirely by --export variables:
#   PILOT_CAND (e.g. TiS2_1T), PILOT_NPOOL, PILOT_AGG (0/1), PILOT_JOBID
set -euo pipefail

module load openmpi/5.0.3 quantum-espresso/7.4   # verified 2026-09-02

WORK=/scratch/general/vast/$USER/mpt_pilot/job_${PILOT_JOBID}
mkdir -p "$WORK/out" "$WORK/pseudos"
cd "$WORK"
SUFFIX=""; [ "${PILOT_AGG}" = "1" ] && SUFFIX="_agg"
cp "$SLURM_SUBMIT_DIR/inputs/${PILOT_CAND}${SUFFIX}.pw.in" pw.in
cp "$SLURM_SUBMIT_DIR"/pseudos/*.UPF "$SLURM_SUBMIT_DIR"/pseudos/*.upf \
   pseudos/ 2>/dev/null || true

echo "pilot job ${PILOT_JOBID}: ${PILOT_CAND} nodes=$SLURM_JOB_NUM_NODES npool=${PILOT_NPOOL} agg=${PILOT_AGG}"
srun pw.x -npool "${PILOT_NPOOL}" -in pw.in > pw.out
rc=$?
grep -E "!.*total energy|convergence has been achieved|Exit code" pw.out | tail -3 || true
echo "exit=$rc" > status
exit $rc

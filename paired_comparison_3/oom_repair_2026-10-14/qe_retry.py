"""Solver-retry rule for live Quantum ESPRESSO campaign drivers.

Adopted 2026-09-30, after the granite-guest
screen: four band (NSCF) steps died in QE's default Davidson eigensolver
("cdiaghg: S matrix not positive definite" / Cholesky failure) and all four
completed with the conjugate-gradient solver. One of the four (ZrS2-1T,
PBE gap 1.20 eV) is a qualifier, so without the retry an unattended screen
reports eight hits instead of nine for a numerical, not physical, reason.

The rule every live driver applies:

1. A pw.x call whose output shows an eigensolver failure is rerun once with
   the next solver on SOLVER_LADDER (Davidson -> cg), same input otherwise.
2. The retry is recorded (solver_retry, solver used) and is billed like any
   other call; it is never silently merged into the first attempt.
3. Outcomes are reported in three separate classes, never pooled:
   'converged' (ran, result usable), 'ran_not_converged' (ran to the end
   but SCF or relaxation did not converge: a numerical miss), and 'crashed'
   (did not finish: solver, memory, missing files, wall time). A compound
   that crashed is not a compound that missed the band-gap window.

Only eigensolver failures trigger the solver retry. Memory kills, missing
restart files and wall-time stops are infrastructure faults: a different
solver does not fix them, so they are classified and left to the driver.
"""
import re
from pathlib import Path

SOLVER_LADDER = ["david", "cg"]

# pw.x messages that mean the iterative eigensolver itself failed
_SOLVER_PATTERNS = [
    r"S matrix not positive definite",
    r"cdiaghg",
    r"rdiaghg",
    r"problems computing cholesky",
    r"cegterg",
    r"regterg",
    r"too many bands are not converged",
]
_OOM_PATTERNS = [r"oom-kill", r"Out Of Memory", r"Killed", r"std::bad_alloc",
                 r"cannot allocate"]
_MISSING_PATTERNS = [r"needed files are missing", r"file .* not found",
                     r"cannot open file"]
_TIME_PATTERNS = [r"Maximum CPU time exceeded", r"DUE TO TIME LIMIT"]


def _any(patterns, txt):
    return any(re.search(p, txt, re.IGNORECASE) for p in patterns)


def classify(out, rc=0):
    """Classify one pw.x output file (path or text) into
    'converged' | 'ran_not_converged' | 'crashed', with a failure kind
    ('solver' | 'oom' | 'missing_files' | 'walltime' | 'other' | None)."""
    txt = out if "\n" in str(out) else Path(out).read_text(errors="replace")
    done = "JOB DONE" in txt
    if _any(_SOLVER_PATTERNS, txt) and not done:
        return "crashed", "solver"
    if _any(_OOM_PATTERNS, txt) or rc in (137, -9):
        return "crashed", "oom"
    if _any(_MISSING_PATTERNS, txt) and not done:
        return "crashed", "missing_files"
    if _any(_TIME_PATTERNS, txt):
        return "crashed", "walltime"
    if not done or (rc not in (0, None)):
        return "crashed", "other"
    scf_like = "Self-consistent Calculation" in txt or "End of self-consistent" in txt
    if scf_like and "convergence NOT achieved" in txt:
        return "ran_not_converged", None
    if "bfgs" in txt.lower() and "bfgs converged" not in txt.lower() \
            and "End final coordinates" not in txt \
            and re.search(r"calculation\s*=\s*'?(vc-)?relax", txt):
        return "ran_not_converged", None
    return "converged", None


def next_solver(current):
    """Solver to retry with, or None when the ladder is exhausted."""
    cur = (current or "david").lower()
    if cur not in SOLVER_LADDER:
        return None
    i = SOLVER_LADDER.index(cur)
    return SOLVER_LADDER[i + 1] if i + 1 < len(SOLVER_LADDER) else None


def current_solver(inp_text):
    m = re.search(r"diagonalization\s*=\s*'(\w+)'", inp_text)
    return m.group(1) if m else "david"


def with_solver(inp_text, solver):
    """Return the pw.x input with &ELECTRONS diagonalization set to solver."""
    if re.search(r"diagonalization\s*=", inp_text):
        return re.sub(r"diagonalization\s*=\s*'\w+'",
                      f"diagonalization = '{solver}'", inp_text)
    return re.sub(r"(&ELECTRONS[^\n]*\n)",
                  rf"\1  diagonalization = '{solver}'\n", inp_text,
                  count=1, flags=re.IGNORECASE)


def retry_input(inp_path, out_dir):
    """If the input can move one step down the solver ladder, write the
    retry input next to the job and return (path, solver); else None."""
    txt = Path(inp_path).read_text()
    nxt = next_solver(current_solver(txt))
    if nxt is None:
        return None
    p = Path(out_dir) / (Path(inp_path).stem + f".{nxt}.in")
    p.write_text(with_solver(txt, nxt))
    return p, nxt

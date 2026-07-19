#!/usr/bin/env python3
"""Phase gate verifier (Implementation Plan - MVP 2.md, Phase MVP2-0, Task C).

Accepts only a completed phase number, runs every required check through
that phase (cumulative - phase N implies phases 0..N-1 already passed and
re-runs their checks too, since section 1.4's No-regression Rule requires
every earlier phase to keep passing), writes no source files, and exits
non-zero on any failure.

Usage:
    python scripts/verify_mvp2_phase.py --phase 0

This script intentionally does not try to guess or infer what a later,
not-yet-implemented phase's checks should be - `PHASE_CHECKS` only has an
entry for phases whose Implementation Plan section is actually done. Running
it for an undefined phase number is a hard error, not a silent no-op, so a
typo (or asking it to verify a phase that hasn't been built yet) cannot be
mistaken for a pass.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _mypy_targets() -> list:
    targets = ["utils", "agents"]
    if (REPO_ROOT / "mvp2").exists():
        targets.insert(0, "mvp2")
    return targets


# Each phase's checks are the exact commands from Implementation Plan -
# MVP 2.md, section 2.3, "Required verification commands", scoped to what
# actually exists in the repository at that phase (e.g. `mvp2` is only
# passed to mypy once Phase MVP2-1 creates the package).
PHASE_CHECKS = {
    0: [
        ("full test suite", [sys.executable, "-m", "pytest", "-q"]),
        ("mvp2 test suite", [sys.executable, "-m", "pytest", "-q", "tests/mvp2"]),
        (
            "golden + MVP1 regression suite",
            [sys.executable, "-m", "pytest", "-q", "tests/test_golden.py", "tests/mvp2/test_mvp1_regression.py"],
        ),
        ("ruff", [sys.executable, "-m", "ruff", "check", "."]),
        ("mypy", [sys.executable, "-m", "mypy", *_mypy_targets()]),
        ("git diff --check", ["git", "diff", "--check"]),
    ],
}


def run_phase_checks(phase: int) -> int:
    if phase not in PHASE_CHECKS:
        defined = sorted(PHASE_CHECKS)
        print(
            f"error: no checks defined for phase {phase}. "
            f"Defined phases: {defined}. "
            "Add this phase's checks to PHASE_CHECKS in this script when its "
            "Implementation Plan - MVP 2.md section actually lands - do not "
            "guess at them ahead of the phase being implemented.",
            file=sys.stderr,
        )
        return 2

    # Cumulative: every completed phase up to and including the requested
    # one must still pass (section 1.4's No-regression Rule).
    failures = []
    for earlier_phase in range(phase + 1):
        checks = PHASE_CHECKS.get(earlier_phase, [])
        for name, command in checks:
            print(f"--- phase {earlier_phase}: {name} ---", flush=True)
            result = subprocess.run(command, cwd=REPO_ROOT)
            if result.returncode != 0:
                failures.append(f"phase {earlier_phase}: {name} (exit {result.returncode})")

    if failures:
        print("\nFAILED checks:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print(f"\nAll checks passed through phase {phase}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", type=int, required=True, help="Completed MVP2 phase number to verify (0-8).")
    args = parser.parse_args()

    if args.phase < 0:
        print("error: --phase must be >= 0", file=sys.stderr)
        return 2

    return run_phase_checks(args.phase)


if __name__ == "__main__":
    raise SystemExit(main())

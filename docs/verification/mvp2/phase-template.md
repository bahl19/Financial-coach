# MVP 2 Phase Verification Evidence — Phase MVP2-{N}: {phase name}

Copy this file to `phase-{N}.md` and fill in every section before treating
the phase as complete (Implementation Plan - MVP 2.md, section 1.2). Do not
delete a section because it feels redundant with another - each one answers
a different exit-gate question.

## Environment

- Date (UTC):
- Verifier (name/handle):
- OS / Python version:
- Commit SHA under test:
- Clean virtual environment used (yes/no, describe if reused):

## Entry criterion

- Prior phase tag verified on `main`: `mvp2-phase-{N-1}-done` at commit ___
  (for Phase MVP2-0, this is MVP 1's `phase11-done` instead)

## Commands run and results

Paste the exact commands and their pass/fail outcome (full output may live
in a linked CI run instead of inline, but the pass/fail summary must be
here):

```text
python -m pytest -q
python -m pytest -q tests/mvp2
python -m pytest -q tests/test_golden.py tests/mvp2/test_mvp1_regression.py
python -m ruff check .
python -m mypy mvp2 utils agents
python scripts/verify_mvp2_phase.py --phase {N}
git diff --check
```

## Fixture review

- Fixtures added/changed this phase:
- Who reviewed them and how (manual recomputation, second reviewer, etc.):
- Any fixture whose expected value changed: cite the documented defect,
  two-person review, and architecture decision required by section 1.4.

## Security review

- Secrets/API keys: confirmed absent from logs, fixtures, and diffs (how
  checked):
- New dependencies: justified, version-bounded, added to `requirements.txt`:
- New network/file/tool surface introduced this phase, if any:

## Regression result

- Frozen MVP 1 goldens: pass/fail, count:
- Cumulative MVP 2 suite (all completed phases): pass/fail, count:
- Deliberate-break checks (allocation cent / score / severity / priority /
  ID) confirmed to fail as expected:

## Known limitations

- Disclose anything left incomplete, deferred, or verified with a caveat
  (e.g. "no second human reviewer available") rather than omitting it.

## Sign-off

- [ ] Every task and required test in this phase's Implementation Plan
      section is checked off.
- [ ] This file is complete and committed.
- [ ] PR merged to `main` (pending explicit user request, per this
      project's established convention - not performed unilaterally).
- [ ] Merged commit tagged `mvp2-phase-{N}-done` (pending explicit user
      request).
- [ ] Phase Status Tracker in Implementation Plan - MVP 2.md updated only
      after verifying the merged commit, not the feature branch.

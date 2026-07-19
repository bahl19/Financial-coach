# Phase Prompts — MVP 2

Use one phase at a time. Replace `{N}` with `0`–`8`. The implementation plan is authoritative; these prompts deliberately do not repeat its instructions or gates.

## Phase Implementation and Verification

```text
Read the authoritative project documents and execute Phase MVP2-{0} from `Implementation Plan - MVP 2.md` exactly as written. Continue until its exit gate is verified. Then report the implementation, verification evidence, and any blocker.
```

## Resume an Incomplete Phase

```text
Resume Phase MVP2-{N} from its current state. Follow `Implementation Plan - MVP 2.md` exactly, complete its remaining work, and continue until its exit gate is verified. Report the result and any blocker.
```

## Final MVP 2 Verification

Use this once, after Phases MVP2-0 through MVP2-8 have individually passed.

```text
Perform the final MVP 2 verification exactly as specified in `Implementation Plan - MVP 2.md`. Resolve all in-scope failures, rerun affected gates, and return a READY or NOT READY verdict with evidence and exact blockers.
```

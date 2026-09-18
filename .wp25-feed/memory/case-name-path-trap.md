---
name: case-name-path-trap
description: 'Test/bench harness case names flowing into log paths: a slash kills the runner silently at redirect; verdicts must fold rc'
metadata:
  node_type: memory
  type: reference
  originSessionId: 79a1f342-0c47-43c3-bc69-b513f06e89fc
  modified: 2026-09-16T22:11:58.680Z
---

Two adjacent harness traps, both from the WP2.5 playbook (a786cf61), both silent-failure shape:

1. **Human-readable case names must never reach a path unsanitized.** `$LOGDIR/$NAME.log` with NAME=`x2-reexport(models/alert)` → redirect target under a nonexistent dir → dash dies rc=2 _before the runner starts_, no log file, and the case table still prints a row. Fix pattern: `SAFE=$(printf '%s' "$NAME" | tr / _)` for paths, keep NAME for the table. Symptom to recognize: wall ≈ 0s + rc=2 + no-selection-line + zero log file.
2. **A verdict that grades only wall/assertion launders red as green.** The same run printed `OK` at rc=1 because the fold never looked at rc. Fold rc+wall+assertion and print `FAILED-rcN` — it is what made trap 1 loud in later runs.

Corollary trap: per-run temp files (selection lists) must be wiped at case boundaries, or a case that writes none grades the PREVIOUS case's file (stale-list false pass).

Related: [[monitor-lines-are-not-truth]], [[pytest-quiet-traps]].

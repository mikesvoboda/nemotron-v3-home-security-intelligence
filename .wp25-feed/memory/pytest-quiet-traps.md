---
name: pytest-quiet-traps
description: "pytest quoting + double -q silently destroy measurement data — addopts inner quotes load-bearing, -q twice kills node IDs and the count line"
metadata:
  node_type: memory
  type: reference
  originSessionId: 79a1f342-0c47-43c3-bc69-b513f06e89fc
  modified: 2026-09-16T16:17:22.702Z
---

Two silent-data-loss traps that cost a full bake-off re-derivation:

1. **`-o addopts="-m not gpu ..."` needs inner single quotes** —
   `-o addopts="-m 'not gpu' --timeout=60"`. Unquoted, pytest's tokenizer
   takes `not` as the marker expression and `gpu` as a stray PATH arg:
   0 tests collected, rc=5, in ~2s. Looks exactly like a transient
   collection death; it is deterministic. Proved on one commit: quoted →
   27,556 nodes rc=0; unquoted → 0 nodes rc=5.
2. **`-q` in addopts AND `-q` on the CLI = double-quiet**: `--collect-only`
   prints `file.py: <count>` instead of node IDs (selection code parsing
   node IDs then sees "selected 0"), and the final `N failed … in Xs` count
   line is suppressed entirely (log-liveness checks keyed on it false-negative).
   Carry exactly one `-q`.

And the parser-order corollary: when extracting node IDs, strip the line
PREFIX (`^FAILED ` / `^ERROR `) BEFORE tail-truncating at whitespace — the
reverse order collapses every id to the literal word `FAILED`, which parses
as a plausible non-empty set while making every diff vacuous.

Related: [[comm-tab-prefix-trap]]

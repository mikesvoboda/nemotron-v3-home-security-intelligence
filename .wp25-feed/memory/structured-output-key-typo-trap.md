---
name: structured-output-key-typo-trap
description: "A workflow agent's StructuredOutput can carry a misspelled key with a plausible value, silently zeroing downstream aggregates"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 79a1f342-0c47-43c3-bc69-b513f06e89fc
  modified: 2026-09-17T21:47:44.889Z
---

Workflow agents forced through a schema can still emit a **misspelled key** whose value is valid JSON — wave-20 triage returned `draftedd_tests: "[]"` instead of `drafted_tests: [...]`, and the aggregate recomputed from journals silently showed 0 drafts while the dossier's own `## Drafted tests` section held all six tests.

**Why:** schema validation checks the schema's own keys; extra/typo'd keys are simply ignored (or in this case slipped through a lax schema), so the error is silent at write time and only shows as a missing count much later.

**How to apply:** when an aggregate derived from structured journal data contradicts a human-readable artifact (dossier notes citing "drafted T1–T5" vs drafts=0), trust the artifact and audit the raw field (`sorted(r.keys())`, print the unexplained key's repr). Fold-in scripts should treat the dossier as canonical for drafts and reconcile counts, not re-type them. Same family as [[monitor-lines-are-not-truth]]: the derived channel lies, the primary artifact doesn't. Cross-check [[parallel-triage-serial-verify]].

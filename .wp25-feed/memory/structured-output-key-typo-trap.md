---
name: structured-output-key-typo-trap
description: "Derived channels (StructuredOutput keys, dossier Totals lines) can lie while the primary artifact is right — reconcile against the table, never the summary"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 79a1f342-0c47-43c3-bc69-b513f06e89fc
  modified: 2026-09-18T03:33:47.077Z
---

Workflow agents forced through a schema can still emit a **misspelled key** whose value is valid JSON — wave-20 triage returned `draftedd_tests: "[]"` instead of `drafted_tests: [...]`, and the aggregate recomputed from journals silently showed 0 drafts while the dossier's own `## Drafted tests` section held all six tests.

**Why:** schema validation checks the schema's own keys; extra/typo'd keys are simply ignored (or in this case slipped through a lax schema), so the error is silent at write time and only shows as a missing count much later.

**How to apply:** when an aggregate derived from structured journal data contradicts a human-readable artifact (dossier notes citing "drafted T1–T5" vs drafts=0), trust the artifact and audit the raw field (`sorted(r.keys())`, print the unexplained key's repr). Fold-in scripts should treat the dossier as canonical for drafts and reconcile counts, not re-type them. Same family as [[monitor-lines-are-not-truth]]: the derived channel lies, the primary artifact doesn't. **The principle nests:** "the dossier" is not monolithically canonical — within one, the enumerated cluster TABLE (and its own printed per-cluster count-check) is the primary artifact, and the narrative `Totals:`/`Class totals:` LINE is a derived summary that can typo independently. Seen 3× (waves 26/29/31): a dossier whose Totals line said 57/41/3 while its own table rows + `= 101 ✓` check summed to 73/25/3 — and the StructuredOutput journal agreed with the TABLE, not the line. When a dossier's stated class totals contradict its table, fold the table, flag the line. **But the table is canonical only when it is internally consistent** — the ultimate arbiter is the PHYSICAL count (live meta survivors). Seen inverse 1× (wave 37, smoke_fire_loader): the cluster table double-counted example keys shared between clusters (F9's `_43` also listed in F10), table grand 143 > physical 135 — there the dedup'd Totals line (66/66/3=135) was right and the table's GAP column was inflated. Fold procedure: reconcile table, journal, Totals line AND live meta; when table ≠ physical, the dedup'd line wins and the overlap is a dossier-quality note. Cross-check [[parallel-triage-serial-verify]].

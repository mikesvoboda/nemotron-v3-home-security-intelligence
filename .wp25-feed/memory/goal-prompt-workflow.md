---
name: goal-prompt-workflow
description: The user drives M1/M2/M3 work by pasting a under-4000-char prompt into the /goal command; one lives per session
metadata:
  node_type: memory
  type: project
  originSessionId: a4bfff8c-fd38-45e3-bf4d-045ba7d1b435
  modified: 2026-09-15T04:24:23.878Z
---

Work on the `feat/context-map-2026-09-12` branch is driven by a **goal prompt** the user
pastes into the `/goal` command. Convention: under 4000 characters, sections `S1..S5` for
sequenced steps, plus `Hard rules`, `STOP AND ASK`, and `DONE =` blocks. Prior copies are kept
at `/home/agent/goal-prompt-*.txt` (the newest is the format to imitate) and the in-repo variant
at `docs/goal-prompt-m1-m2-m3-2026-09-14.md`.

**Why:** the prompt is the whole instruction set for a fresh session — it has to re-establish
ground truth in one shot, so it always points at the LEDGER as the authority rather than
restating state.

**How to apply:** when asked for a new goal prompt, write to `/home/agent/goal-prompt-<topic>-<date>.txt`,
verify with `wc -c` it is under 4000 chars, and keep it pointer-heavy (paths + task ids + exact
commands) rather than narrative. Related: [[ledger-is-ground-truth]], [[gate-protocol]].

---
name: ci-merge-gate-and-retrigger-quirks
description: "What actually blocks merges on mikesvoboda/nemotron-v3-home-security-intelligence, and the CI retrigger/queue gotchas that waste hours"
metadata:
  node_type: memory
  type: project
  originSessionId: a4bfff8c-fd38-45e3-bf4d-045ba7d1b435
  modified: 2026-09-15T20:01:03.058Z
---

On `mikesvoboda/nemotron-v3-home-security-intelligence`, branch protection requires exactly one check context: **`CI Gate (Required Checks)`** (ci-gate job, needs: detect-changes, lint, typecheck, unit/integration summaries, frontend lint/typecheck/tests/e2e summaries, api-types-check; `check_job` passes on success **or skipped** — path-filter skips don't block). Everything else is advisory and can stay red: Trivy ×4, npm Audit, Python Dependency Audit, SAST, Test Coverage Gate. #6539 merged under a full set of advisory reds.

Gotchas that burn time (all hit during the #6540/#6541 sequence, 2026-09-15):
- Retargeting a stacked PR (`base_ref_changed`) and `ready_for_review` do **not** fire `pull_request` workflows (default types are opened/synchronize/reopened) → close + reopen the PR to fire CI.
- Close/reopen **clears auto-merge** — re-enable it after the cycle if you want the merge to land unattended.
- Free tier = ~1 concurrent runner slot: a `gh run rerun` fired on a superseded head SHA sits on the slot for 30+ min and leaves the real head's run `pending` with 0 jobs allocated. Cancel stale reruns (`gh api -X POST .../actions/runs/<id>/cancel`, needs the long run id, not run_number).
- Two green PRs merged via squash make the *content* of cherry-picked fixes appear in a stacked child's diff even when the child was rebased on the pre-merge base — rebase the child onto the post-merge main so GitHub's diff stays honest.

Related: [[github-free-tier-boundaries-2026]], [[github-push-one-shot-helper]]

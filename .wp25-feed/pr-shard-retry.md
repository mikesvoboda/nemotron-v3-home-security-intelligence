# Slow-runner retry for the integration API tier + cancelled-is-not-a-verdict summary

## Why (measured, not theorized)

Run 35353201418 (PR #6552, commit `4805d98d`), three full attempts of the
**same commit**:

| Attempt        | Result                                                                   |
| -------------- | ------------------------------------------------------------------------ |
| 1 (12:17 UTC)  | shard 1/2 **passed in 23m54s** — 20% margin under GitHub's 30m0s job cap |
| 3 (full rerun) | per-test 30s `pytest-timeout` reds, ~10s uniform teardowns               |
| 4              | shard 1/2 **CANCELLED at the 30m job cap** (30m19s)                      |

Same tree passed earlier the same day; `main` hadn't moved. Runner
degradation, not code. **The worse half:** on attempt 4, **Test Performance
Audit: SUCCESS and CI Gate: SUCCESS** — because `integration-tests-summary`
turns red only on the literal string `failure`, so the cancelled shard fell
through to "All integration tests passed". Branch protection requires exactly
one context (`required_status_checks` = `[CI Gate (Required Checks)]`) — the
merge box's other ~50 rows are non-required. The repo's only gate reported
green with the integration API tier dead.

## Ruling encoded (owner, 2026-09-18)

Extends WP0.5's pre-authorized clause: _"if slow-runner reds recur as a
pattern, the mitigation is runner-job retry of the AUDIT step's inputs,
decided then."_

- Retry **only** `cancelled` — **never** `failure`. Retrying genuine test
  failures is the retry-mask class this repo has ruled against twice. A
  slow-runner _failure_ is indistinguishable from a regression: stays red,
  comes back to the owner.
- The 30-min job cap and 10s/30s timing ceilings stay **UNRAISED** — raising
  a ceiling to pass is widening a gate. The new gate test fails any edit that
  moves the cap, so a future change is a ruling, not a drift.
- A retry _inside_ the job can't recover the observed terminal mode (the cap
  is what the first attempt exhausted), and Actions has no step-level job
  retry — so recovery is a **fresh job with a fresh budget**: caller +
  sibling-retry both calling one reusable workflow.

## How

- **`.github/workflows/integration-shard.yml` (new):** the API shard tier
  moved **verbatim** (pytest cmdline, `--timeout=30`, `--splits 2`,
  flake-allowlist pre-rerun, pg/redis services, coverage/junit uploads) with
  `inputs.shard` / `inputs.artifact-suffix` threaded through. Primary and
  retry are ONE definition — WP4.3's mutmut 2.x flag rot is what N
  independent copies of one procedure fester into. Reusable workflows
  inherit **no** top-level env, so `UV_VERSION` is mirrored inside — and
  pinned equal to ci.yml's by the gate test.
- **ci.yml:** `integration-tests-api` becomes the caller;
  `integration-tests-api-retry` is the same call gated on
  `needs.integration-tests-api.result == 'cancelled'`. The `-retry` suffix
  keeps `upload-artifact` names unique per run (suffix stays on the tail, so
  TPA's `test-results-*` and the coverage merge's `coverage-integration-*`
  globs still match — asserted). `test-performance-audit` and
  `integration-coverage-merge` now also `need` the retry, so their
  pattern-downloads see the retry's fresh junit/coverage instead of a
  cancelled parent's partial uploads (today's `--failed`-rerun stale-artifact
  trap, encoded).
- **Summary job:** a cancelled API shard is red **unless** the retry ran and
  passed. Every other job's non-success stays red exactly as before.
- **`scripts/test_shard_retry_wiring.py` (new gate test, wired into the
  anti-rot steps):** red-first (12 failures before the wiring, 0 after).
  Pins: uses/matrix/`secrets: inherit`; retry fires on `'cancelled'` with
  `always()` and must NOT contain `'failure'`; suffix threading + glob
  survival; reusable job keeps the UNRAISED 30-min cap, services, and the
  flake-governance cmdline; `UV_VERSION` mirror equality; summary reads the
  retry result AND handles `cancelled`; coverage-merge needs the retry.
  `scripts/test_ci_job_graph.py` (WP0.6) stays green — the summary reads both
  results, so api tier and retry both remain GATE-reachable.

## Deliberately NOT here

- No unit-tier retry (15-min cap, pattern never observed there —
  speculative gate-shaping).
- No `failure` retry, no ceiling/cap moves, no allowlist/quarantine changes.
- No merge with #6553 or #6552: ci.yml is exactly where #6553 collides;
  gate-semantics changes get their own review unit. This branch carries one
  ci.yml hunk region.

## Known residual (stated, not hidden)

The retry keys on the _aggregated_ matrix result. If GitHub's aggregation
ever reported `success` despite one cancelled leg, the failure mode is
today's status quo (invisible cancellation), not a new one — the next real
cancelled attempt is the empirical check.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

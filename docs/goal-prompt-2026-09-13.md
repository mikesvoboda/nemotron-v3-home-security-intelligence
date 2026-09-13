# Goal: close the two stacked workstreams on feat/context-map-2026-09-12

Repo: /agents/agent-nemo2/workspace (AI home-security dashboard; see CLAUDE.md + AGENTS.md).
Branch is 79 ahead / 0 behind origin/main, with 40 commits unpushed to its own remote. Work only on this branch.

## Authoritative docs — read before acting
- docs/superpowers/specs/2026-09-12-arm64-gb300-milestone1-design.md — M1 authority (§6 exit criteria, §8 GPU out of scope)
- docs/superpowers/plans/2026-09-12-arm64-gb300-milestone1.md — M1 Tasks 1-8
- docs/superpowers/specs/2026-09-12-fast-confidence-loop-design.md — FCL authority; §9 sequencing is BINDING
- docs/superpowers/plans/2026-09-12-fast-confidence-loop.md — FCL Tasks 1-15
- .superpowers/sdd/2026-09-12-*/progress.md — run ledgers (runs 1-5). These, not plan checkboxes, are ground truth.

## Do NOT trust the plan checkboxes
The FCL plan shows 0/73 boxes checked yet Task 1 already landed, and several M1 steps marked unchecked are done. Re-derive state from the filesystem and ledgers before touching anything. Verified current state:

M1: Tasks 1-7 landed (gb300 compose overlay, env template, .env port vars, bootstrap-gb300.sh, D14 gate split, 85.17% combined coverage at run-4). REMAINING: Task 8 — exercise bootstrap idempotency, reproduce every spec §6 exit-criteria bullet, get /platform-healthcheck to PASS, record the final no-flag validate.sh run green in the M1 ledger, commit.

FCL: Task 1 landed (scripts/check-test-collection.py + collection-sanity-allowlist.txt + ci.yml collection-sanity job). Tasks 2-15 NOT STARTED — confirmed absent: .github/workflows/flake-allowlist.yml, scripts/fast_select.py, scripts/fast-frontend-runner.sh, validate.sh --fast, nightly full-gate workflow.

## Sequencing (spec §9 is binding)
Finish M1 Task 8 and record green validate.sh in the M1 ledger BEFORE starting FCL Task 2. Then FCL 2→15 in plan order.

## Non-negotiables
- One change per step, verified before the next. No drive-by refactors, no batching fixes.
- Never bypass pre-commit hooks. No --no-verify.
- Rebuild containers with --no-cache (cached layers hold stale code).
- All ports via .env variables, never hardcoded in docker-compose.prod.yml.
- Before running the gate, export TEST_DATABASE_URL/TEST_REDIS_URL at a real server — otherwise the integration tier spawns a testcontainer per worker and DiskFull-cascades 377 setup ERRORs (run-5 root cause).
- Use podman, never bare docker. This host runs a co-resident rootful dockerd holding dgx-inference-* containers: never touch those.
- The 16 frontend files quarantined in frontend/vite.config.ts (62 pre-existing deterministic failures + 3 zero-byte suites) are DEBT, not green. Do not treat the frontend gate as clean, do not widen the exclude list, and remove entries as FCL repairs them.
- Every scope-out or allowlist entry needs a tracking ref and queued remediation. Waivers are never silent.
- Append findings to the ledger as you go (root cause + evidence + ref), matching existing ledger style.

## Definition of done
M1: every spec §6 bullet reproduced and passing; bootstrap idempotent; /platform-healthcheck PASS; final no-flag validate.sh green recorded in the ledger.
FCL: Tasks 2-15 landed per their specs; validate.sh --fast meets the §4.1 output contract; the §6.3 playbook (5 changes × ≤10 min) demonstrated; nightly full-gate workflow committed; quarantine list empty or measurably shrunk with reasons; Task 15 measurements recorded.
Then: ./scripts/validate.sh green, commit, push to origin, close the matching Linear tasks via the /linear-python skill.

Stop and ask me before: any production-behavior change outside a documented F1/F2-class bug; widening a quarantine or allowlist; or scoping another test tree out of the gate.

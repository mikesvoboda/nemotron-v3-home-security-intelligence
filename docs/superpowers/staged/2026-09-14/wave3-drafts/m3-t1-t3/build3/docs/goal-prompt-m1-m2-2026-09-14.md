# Goal: complete M1 (arm64/GB300) and M2 (Fast Confidence Loop) on feat/context-map-2026-09-12

Repo: /agents/agent-nemo2/workspace. Work only on this branch. One fix per commit, root-cause message citing its ledger ref, Co-Authored-By trailer.

## Authoritative docs — read before acting
- docs/superpowers/specs/2026-09-12-arm64-gb300-milestone1-design.md — M1 authority (§6 exit criteria)
- docs/superpowers/plans/2026-09-12-arm64-gb300-milestone1.md — M1 Tasks 1–8
- docs/superpowers/specs/2026-09-12-fast-confidence-loop-design.md — M2 authority; §9 sequencing is BINDING
- docs/superpowers/plans/2026-09-12-fast-confidence-loop.md — M2 Tasks 1–15
- docs/plans/2026-09-12-context-map-doc-updates.md — the running ledger; ground truth over plan checkboxes
- docs/discoveries/pytest-oom-asyncmock-worker-loop.md — worker-OOM root cause

Re-derive state from ledger + filesystem; older status claims (incl. "Task 7 landed") were premature.

## M1 state (2026-09-14)
Tasks 1–6 landed. Task 7 (validate.sh green on aarch64) mid-convergence: WS-mock OOM leak fixed (fbb2f4ee), jobs_api fixed 20/20, auth_flow rewritten to the shipped cookie-session contract (26/26 serial-green, uncommitted — verify + land first), cursor_pagination 3 drift fixes applied but unverified. Remaining known reds are class-(c) test-vs-shipped-contract drift: event_search (~25), backup_api (~7), tracks/idempotency (~9), polygon_zone (~7), entity_persistence (~9). Triage from the newest trustworthy summary (driver /tmp/run8-driver.sh + plugins /tmp/timeout_stamp_plugin.py, /tmp/disk-guard.sh — if gone, reconstruct from ledger R-T7-* entries).
Then Task 8: bootstrap-gb300.sh idempotency, every spec §6 bullet reproduced, /platform-healthcheck PASS, record the final no-flag validate.sh green in the M1 ledger.

## Gate protocol (runs 1–8 lessons)
- EXACTLY ONE heavy pytest job on the machine at a time; a second job poisons DB contention and voids the summary.
- TEST_DATABASE_URL/TEST_REDIS_URL persist in /etc/sandbox-persistent.sh — never unset (missing → testcontainer-per-worker → DiskFull).
- Integration tier under ulimit -v 20971520; disk-guard + RSS trace armed; coverage combine across tiers then --fail-under=80.
- conftest stamps timeout(5) on unmarked integration items, OVERRIDING CLI --timeout=30 — keep the timeout-stamp plugin in the run protocol until the owner rules on the repo fix.

## M2 (FCL) — begin only after M1's green run is recorded (spec §9 binding)
Task 1 landed. Tasks 2–15 in plan order: flake allowlist + retry-mask teardown, frontend parallelism envs, CI honesty (exit-0 hack), per-worker PG/Redis hygiene, fast selectors, validate.sh --fast per §4.1 contract, nightly full gate, §6.3 playbook (5 changes × ≤10 min), measurements. Full-gate strictness byte-identical except the two sanctioned deltas; no coverage-bar moves, no deletions, no skips.

## Non-negotiables
- Align tests to the SHIPPED contract; never bend production behavior. Stop and ask the owner before touching: pipeline_workers unthrottled `if not messages: continue` (P1), pyproject timeout config/marker-override (P2), fake frame-buffer memory asserts (P3), DB-created API keys authenticating nothing — verify_api_key is settings-only (R-T7-APIKEY-DEAD), and /api/events risk_level column-filter vs computed-field serialize mismatch.
- Never bypass pre-commit. Rebuild --no-cache. Podman for compose; gate containers live in docker; never touch dgx-inference-*.
- Frontend quarantine list in vite.config.ts is debt — shrink with tracking refs, never widen silently.
- Append every finding to the ledger (root cause + evidence + ref) as you go.

## Definition of done
M1: no-flag validate.sh green recorded in ledger; Task 8 items landed; committed + pushed.
M2: Tasks 2–15 landed per spec; --fast meets §4.1; playbook demonstrated; nightly workflow committed; Task 15 recorded; final full validate.sh green.
Then: push, close matching Linear tasks via /linear-python.

Stop and ask me before: any production-behavior change, widening any quarantine/allowlist, or scoping a test tree out of the gate.

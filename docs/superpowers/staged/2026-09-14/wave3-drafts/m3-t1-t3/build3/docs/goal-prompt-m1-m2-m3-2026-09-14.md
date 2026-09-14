# Goal: finish M1 (arm64/GB300), M2 (Fast Confidence Loop), M3 (Test Suite Hygiene) on feat/context-map-2026-09-12

Repo /agents/agent-nemo2/workspace; branch only. One fix per commit; message cites its ledger ref; trailer `Co-Authored-By: Claude Code <noreply@anthropic.com>`.

## Docs — read first (under docs/)
specs/…arm64-gb300-milestone1-design.md (§6 exit); specs/…fast-confidence-loop-design.md (§9 sequencing BINDING); plans/…arm64-gb300-milestone1.md (T1–8); plans/…fast-confidence-loop.md (T1–15); plans/2026-09-14-test-suite-hygiene-milestone3.md (T1–11; T4 gates T5); development/test-suite-audit-2026-09-13.md ([VERIFIED] act, [REPORTED] re-verify, [ESTIMATE] MEASURE; Part 7 Do-NOT binding); plans/2026-09-12-context-map-doc-updates.md (LEDGER = ground truth); discoveries/pytest-oom-asyncmock-worker-loop.md. Re-derive state from ledger + filesystem; older claims may be stale.

## State 2026-09-14
M1 T1–6 landed; all BACKEND tiers green (gate 10). First-ever frontend tier then failed 18 tests/10 files + 2 fork crashes — 6 classes root-caused, fixed TEST-SIDE, verified, pushed (tip a1358d21). M1 §6 record BLOCKED on no-flag validate.sh exit 0. M2: T1 landed; T2 assets staged /tmp/t2. M3: T4 landed + measured (919.75→618.53s, −33%; teardown p50 1.043→0.224s; audit's 18–21min [ESTIMATE] REFUTED); T1–3, T5–11 open.

## Next, in order
(1) FULL frontend vitest on a quiet box; re-assess the 2 fork crashes + CleanupRow leaked-timer; never widen the 16-file R-T7-VITEST quarantine (frontend/vite.config.ts). (2) BARE full gate (box idle) → on exit 0 record M1 §6 (healthcheck, API-health, compose AFTER gate). (3) M2 T2→T15 per plan; strictness byte-identical except the two sanctioned deltas; no coverage-bar moves, deletions, skips. (4) M3 T5 (ruling-gated; retire /tmp/timeout_stamp_plugin.py), then T1–3, T6–11 with measurement rows; commits B (drop client PRE-test sweep) + C (coalesce TRUNCATEs) logged candidates. (5) Final full gate green ×2, zero node-downs; push; close Linear via /linear-python.

## Gate protocol
EXACTLY ONE heavy pytest job at a time (ps census first) — a second run voids the summary AND collides on worker-DB names (security_test_gwN), dropping the live gate's DBs (run-9 postmortem). NEVER integration-tier pytest on shared postgres while a tier is live; `-n0` only, ideally none. vitest only when no pytest owns the box. .env ABSENT during gates (backup /tmp/env-backup-gb300.env). Never unset TEST_DATABASE_URL/TEST_REDIS_URL (/etc/sandbox-persistent.sh; else DiskFull). ulimit -v 20971520 for integration tier/drivers only; never wrap validate.sh. Coverage combine then --fail-under=80. Tooling: /tmp/dur/durations_plugin.py (DURATIONS_DIR) + /tmp/dur-runs/analyze_run.py <dir>. Report a tier verdict ONLY from a summary line actually in the log — never mid-run percentages.

## Non-negotiables
Align tests to the SHIPPED contract; never bend production. M3 touches backend/tests/, scripts/, docs only; pyproject ONLY via T5 owner ruling. STOP AND ASK the owner before: workers busy-loop (P1); pyproject timeout/marker-override (P2); fake frame-buffer asserts (P3); API keys authenticating nothing (R-T7-APIKEY-DEAD); /api/events risk_level column-vs-computed (P4); chaos vacuous-test direction; ~102 uncategorized integration files; frontend logout shipped-gap; DetectionStreamService singleton hazard. Never bypass pre-commit; never widen any quarantine/allowlist; never scope a test tree out of the gate. Podman for compose; gate containers in docker; never touch dgx-inference-*. Append every finding to the ledger (root cause + evidence + ref).

## Done means
M1: no-flag validate.sh green recorded + T8 landed. M2: T2–15 per spec; --fast meets §4.1; playbook; nightly workflow; T15 recorded. M3: T1–11 landed with measurement rows; timeout change only with ruling; every [ESTIMATE] confirmed/refuted with its number. Then push + Linear closed.

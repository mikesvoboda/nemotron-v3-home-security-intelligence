# Goal: finish M1 (arm64/GB300), M2 (Fast Confidence Loop), M3 (Test Suite Hygiene) on feat/context-map-2026-09-12

Repo /agents/agent-nemo2/workspace; branch only. One fix per commit citing its ledger ref; trailer Co-Authored-By: Claude Code <noreply@anthropic.com>.

## Docs — read first (under docs/)
specs/…arm64-gb300-milestone1-design.md (§6 exit); specs/…fast-confidence-loop-design.md (§9 sequencing BINDING); plans/…arm64-gb300-milestone1.md (T1–8); plans/…fast-confidence-loop.md (T1–15); plans/2026-09-14-test-suite-hygiene-milestone3.md (T1–11; T4 gates T5); development/test-suite-audit-2026-09-13.md ([VERIFIED] act, [REPORTED] re-verify, [ESTIMATE] MEASURE; Part 7 Do-NOT binding); plans/2026-09-12-context-map-doc-updates.md (LEDGER = ground truth); discoveries/pytest-oom-asyncmock-worker-loop.md. Re-derive state from ledger+filesystem; older claims may be stale.

## State 2026-09-14 (post-96GiB-restart resume)
M1: gate-14 VERIFIED 777 files/20220 tests passed 0 failed, cov 87.96%; both queued errors root-caused+fixed (358942dd useLocalStorage inline-literal render-loop OOM; 9eb02b3e tremor real-timer afterAll flush). §6 record PENDING gate-16 exit 0. Box now 96 GiB/16 cores. M2: T1+T2 landed; T3-T14 patches apply-clean under docs/superpowers/staged/2026-09-14/. M3: T4 landed −33%; T5 APPROVED as-written; harness staged; T1/T3 drafted; memo docs/superpowers/rulings/2026-09-14-wave2-owner-ruling-memo.md (T3 threshold moot at 96GiB; init_db seam + chaos + other rulings OPEN).

## Next, in order
(1) Post-restart verify: MemTotal ~96GiB, TEST_DATABASE_URL/TEST_REDIS_URL intact, .env ABSENT. (2) BARE full gate (gate 16, /tmp/validate-full-16.log) → exit 0 → record M1 §6 via staged w0-runbook (healthcheck/compose AFTER gate). (3) M2 T3 apply+MEASURE (auto-arms at 96GiB; 8x8192 vs 2981.18s anchor; RSS-sample) → T4 → T5-T7 → T10-T15; strictness byte-identical except sanctioned deltas. (4) M3 T5 execute (conftest fix + retire /tmp/timeout_stamp_plugin.py, swap, smoke, gate×2), then T1-T3, T6-T11 with measurement rows. (5) Full gate green ×2, zero node-downs; push; close Linear via /linear-python.

## Gate protocol
EXACTLY ONE heavy pytest job at a time (ps census first) — a second run voids the summary AND collides on worker-DB names (security_test_gwN), dropping the live gate's DBs (run-9 postmortem). NEVER integration-tier pytest on shared postgres while a tier is live; `-n0` only. vitest only when no pytest owns the box. .env ABSENT during gates (backup /tmp/env-backup-gb300.env). Never unset TEST_DATABASE_URL/TEST_REDIS_URL (/etc/sandbox-persistent.sh; else DiskFull). ulimit -v 20971520 for integration tier/drivers only; never wrap validate.sh. Coverage combine then --fail-under=80. Tooling: /tmp/dur/durations_plugin.py (DURATIONS_DIR) + /tmp/dur-runs/analyze_run.py <dir>. Tier verdicts ONLY from summary lines actually in the log — never mid-run percentages.

## Non-negotiables
Align tests to the SHIPPED contract; never bend production. M3 touches backend/tests/, scripts/, docs only; pyproject ONLY via T5 owner ruling. STOP AND ASK the owner before: workers busy-loop (P1); pyproject timeout/marker-override (P2); fake frame-buffer asserts (P3); API keys authenticating nothing (R-T7-APIKEY-DEAD); /api/events risk_level column-vs-computed (P4); chaos vacuous-test direction; ~102 uncategorized integration files; frontend logout shipped-gap; DetectionStreamService singleton hazard. Never bypass pre-commit; never widen any quarantine/allowlist; never scope a test tree out of the gate. Podman for compose; gate containers in docker; never touch dgx-inference-*. Append every finding to the ledger (root cause + evidence + ref).

## Done means
M1: no-flag validate.sh green recorded + T8 landed. M2: T2–15 per spec; --fast meets §4.1; playbook; nightly workflow; T15 recorded. M3: T1–11 landed with measurement rows; timeout change only with ruling; every [ESTIMATE] confirmed/refuted with its number. Then push + Linear closed.

# Goal: finish M1 (arm64/GB300), M2 (Fast Confidence Loop), M3 (Test Suite Hygiene) on feat/context-map-2026-09-12

Repo /agents/agent-nemo2/workspace; branch only. One fix per commit citing its ledger ref; trailer Co-Authored-By: Claude Code <noreply@anthropic.com>.

## Docs — read first (under docs/)
specs/…arm64-gb300-milestone1-design.md (§6 exit); specs/…fast-confidence-loop-design.md (§9 BINDING; M1-constraint: validate.sh/addopts/vite.config frozen until M1 §6 recorded, inert additive files allowed); plans/…arm64-gb300-milestone1.md (T1–8); plans/…fast-confidence-loop.md (T1–15); plans/2026-09-14-test-suite-hygiene-milestone3.md (T1–11; rule 1: M3 repo changes wait M2-green — T5 covered by owner ruling, T1/T2 stay STAGED for critic slots [10]/[12]); development/test-suite-audit-2026-09-13.md ([VERIFIED] act, [REPORTED] re-verify, [ESTIMATE] MEASURE; Part 7 Do-NOT); plans/2026-09-12-context-map-doc-updates.md (LEDGER = ground truth; wave-3 critic apply-order there). Re-derive from it+fs.

## State 2026-09-14 (pre-96GiB-restart)
M1: gate-14 VERIFIED 20220 tests 0 failed, cov 87.96%, frontend 2990.68s anchor; queued errors fixed (358942dd, 9eb02b3e). §6 record PENDING gate 16. M2: T1+T2 landed; T3-T14 patches re-verified apply-clean at post-T5 tip; t10 applied (§9 additive). M3: T4 landed −33%; T5 steps 1-3 LANDED (c1e10c2b conftest honors CLI --timeout; ed237d99 pyproject signal+func_only=false; smoke verdicts in ledger); T1 measured (−134) then reverted out-of-turn (21a710dc); T2: 9 DEAD fixtures, patch staged, unit-green acceptance in scratch worktree.

## Next, in order
(1) Post-restart verify MemTotal ~96GiB, TEST_DATABASE_URL/TEST_REDIS_URL intact, .env ABSENT (/tmp wiped; backup /home/agent/env-backup-gb300.env; tooling staged/2026-09-14/dur/ + /home/agent/dur-runs-backup). (2) BARE gate 16 → exit 0 → record M1 §6 via staged w0-runbook (ledger-anchor rebase; compose/healthcheck AFTER gate). (3) M2 T3 apply+MEASURE (8x8192 vs 2981.18s; RSS-sample) → T4 → t5→t6→t7 → T10 self-test+commit → T13 → T14 (owner A/B OPEN, A rec) → T15. (4) M3 re-apply T1 + T2 + T3, then T6-T11 with measurement rows; gate ×2 zero-node-down completes T5. (5) Push; Linear via /linear-python.

## Gate protocol
EXACTLY ONE heavy pytest job at a time (ps census first) — a second voids the summary AND collides worker-DB names (security_test_gwN). NEVER integration pytest on shared postgres while a tier is live; -n0 only. vitest only when no pytest owns the box. .env ABSENT during gates. Never unset TEST_DATABASE_URL/TEST_REDIS_URL (else DiskFull). ulimit -v 20971520 integration/drivers only; never wrap validate.sh. Coverage combine then --fail-under=80. Standalone pytest: pass --randomly-seed=N (pytest-randomly TypeError-crashes on unset seed; -p no:randomly loses to addopts). Tier verdicts ONLY from summary lines actually in the log.

## Non-negotiables
Align tests to the SHIPPED contract; never bend production. M3 touches backend/tests/, scripts/, docs only; pyproject ONLY via T5 owner ruling (already exercised once — any further pyproject change needs a NEW ruling). STOP AND ASK before: worker busy-loop (P1); further pyproject (P2); fake frame-buffer asserts (P3); API keys authenticating nothing; /api/events risk_level; chaos direction (18 fixtures, 0 consumers — census confirms dead, still owner's call); ~102 uncategorized integration files; frontend logout gap; DetectionStreamService singleton. Never bypass pre-commit; never widen quarantine/allowlists; never scope a tree out of the gate. Podman compose, docker gate containers, never touch dgx-inference-*. Append every finding to the ledger.

## Done means
M1: no-flag validate.sh green recorded + T8 landed. M2: T2–15 per spec; --fast meets §4.1; playbook; nightly; T15 recorded. M3: T1–11 landed with measurement rows; timeout change only with ruling; every [ESTIMATE] confirmed/refuted with its number. Then push + Linear closed.

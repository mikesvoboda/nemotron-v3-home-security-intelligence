---
name: wp25-resume-pack-2026-09-16
description: 'WP2.5 complete + Phase 2 close-out resume order (validate → push → auto-squash → R-T9 → Phase 3)'
metadata:
  node_type: memory
  type: project
  originSessionId: 79a1f342-0c47-43c3-bc69-b513f06e89fc
  modified: 2026-09-17T04:24:10.243Z
---

WP2.5 LANDED 2026-09-16 (a786cf61: playbook 12 cases + 900s bound, Row F3, 4 ledger rows). Defect chain before it: e4414bca (deleted-test phantom), 97153cbb (schemathesis stub delete), fe646612 (test*utils→testing_utils rename). Run 3 quotable: 12/12 green, max 484s, counts reproduce probes with exactly −1 stub on api-touching cases. CORRECTION to earlier note: Run-1/Run-2 x2 "0s rc=2" was NOT a pkill artifact — slash-in-case-NAME log-path death (fixed via tr / *, pinned in-file).

Resume order from here: (1) full ./scripts/validate.sh on a786cf61 (running at pause; log /tmp/wp25/validate-full.log) — if green, (2) `git push` ~17 commits on feat/phase2 (self-updates PR #6549; exercises the WP2.4 fast-tier pre-push hook — no backend/api files touched in the stack, stub not tripped; expected tier runtime: merge-base base = wide diff, budget 900s, may print staged-tree NOTICE — honest paths), (3) re-arm auto-squash: `gh api repos/mikesvoboda/nemotron-v3-home-security-intelligence/pulls/6549/auto-merge -f merge_method=squash`, (4) R-T9 per owner ruling: EXPORTDEFER→MQTTPUMP→MVSOURCE(RETIRE), plans /tmp/wp24/rt9/ (red test first each; MVSOURCE deletes test_materialized_views.py — pushable since e4414bca), (5) Phase 3 (WP3.1 concurrency cap via Settings→Billing BEFORE sizing; queue vs compute separate; WP3.6 DEFERRED), then Phase 4. Linear close via /linear-python ABSENT in sandbox — disclose in final report.

Housekeeping: disk 84% (3.1G free) — sweep before any big run; stale .claude/worktrees/wf\__; /tmp/wp25clone + /tmp/wp24 kept for R-T9. Registry workflow if it changes again: FULL regen + CI's semantic --check, then adopt the hook's prettier output and re-commit (flip-flops otherwise; commits A/B/WP2.5 each needed the adopt-then-commit cycle). ROOT CAUSE FOUND 2026-09-17: the hook's prettier re-escapes BARE markdown-ambiguous tokens in prose (`\*\*/_.xml`, `.test_durations`, `duration_based_chunks`) on every pass, and npx-prettier output ≠ hook output — write such tokens backticked in the first draft and they converge (verify with `.venv/bin/pre-commit run prettier --files <f>`before committing; note uv sync prunes pre-commit from .venv —`uv pip install pre-commit`). Detect silent commit failures by exit-code check or `git log -1`, NOT `| tail -2` (hid two failed WP3.7-row commits).

Monitor lesson still live: filesystem beats monitor lines.

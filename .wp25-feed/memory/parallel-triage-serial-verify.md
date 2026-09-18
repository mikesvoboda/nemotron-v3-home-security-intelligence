---
name: parallel-triage-serial-verify
description: 'While a long pytest/mutmut tier owns the box, dispatch read-only triage+drafting agent waves; fixes enter the tree only via one serial red→green lane'
metadata:
  node_type: memory
  type: feedback
  originSessionId: 79a1f342-0c47-43c3-bc69-b513f06e89fc
  modified: 2026-09-17T15:18:49.274Z
---

User asked (WP4.3, run5, 2026-09-17) whether subagents should fix discovered issues as they surface instead of letting findings pile up. Agreed shape: **drafting waves parallel, verification serial**.

**Why:** A "fix" is only real after red-on-mutant → green-on-original → killed, and each step is pytest — concurrent pytest violates the one-heavy-job rule (security_test_gwN collisions) and load can flip survivor→timeout→counted-killed (inflation bias). But triage (parse verdict metas, diff mutant copies, read covering tests, draft pytest code) needs zero CPU and survivors never flip once checked, so it parallelizes freely.

**How to apply:** Read-only agents write dossiers under /tmp (never the tree), mark drafts UNVERIFIED, and cluster survivors by pattern (100-200 survivors ≈ 5-10 recurring patterns). Gate waves on statistical stability (e.g. ≥150 checked & ≥100 survivors) so early-rate noise isn't "fixed". Detector script + dispatched.txt dedupe ledger + cron wake made it self-driving; the cron pattern died with the session — rebuild via [[monitor-lines-are-not-truth]] disk checks. Fixes land in the NEXT WP's commit, keeping one-WP-per-commit. Related: [[goal-prompt-workflow]].

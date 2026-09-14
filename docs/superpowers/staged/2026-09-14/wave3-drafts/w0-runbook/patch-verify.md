# W0 patch verification (draft-time, repo root /agents/agent-nemo2/workspace @ fa6521ea, 2026-09-14)

W0's ONLY repo-write is the ledger addition. Everything else in this dir is /tmp-local.

## ledger-addition.patch

- Target: `docs/plans/2026-09-12-context-map-doc-updates.md` — append-only hunk `@@ -2181,3 +2181,41 @@` (3 context lines + 38 added lines: 1 staged-draft HTML comment + the §6 close-out entry TEMPLATE with [PLACEHOLDER] slots).
- **`git apply --check /tmp/wave3-drafts/w0-runbook/ledger-addition.patch` → rc=0** (verified from repo root at fa6521ea).
- Content check: no newlines mangled (file ends with `\n`; template ends with `\n` — no `\ No newline` marker needed).

## Stacking vs queued drafts (disjoint-file proof + git previews)

| patch | files touched | check @ fa6521ea (repo root) |
|---|---|---|
| /tmp/t3-draft/t3.patch | frontend/vite.config.ts, frontend/package.json, scripts/validate.sh | `git apply --check` **rc=0** (plain form; note: `--directory=.` form errors "invalid path ./frontend/..." — always use the plain form) |
| /tmp/wave2-drafts/t4/ci-frontend-honesty.patch | .github/workflows/ci.yml only (+54/−30) | `git apply --check` **rc=0** |
| /tmp/wave3-drafts/w0-runbook/ledger-addition.patch | docs/plans/2026-09-12-context-map-doc-updates.md only | **rc=0** |
| m3-static/, owner-memo | drafts only, no patch | n/a |

File sets are pairwise DISJOINT ⇒ order-insensitive stack. Preview verification (check-only, applied nothing):

```
git apply --check --exclude='frontend/*' --exclude='scripts/validate.sh' /tmp/t3-draft/t3.patch                        → ok  (t3 preview)
git apply --check --exclude='frontend/*' --exclude='scripts/validate.sh' .../ledger-addition.patch                     → ok  (W0 stacks after t3)
git apply --check --exclude='frontend/*' --exclude='scripts/validate.sh' --exclude='.github/*' /tmp/wave2-drafts/t4/ci-frontend-honesty.patch → ok (t4 preview)
git apply --check --exclude='frontend/*' --exclude='scripts/validate.sh' --exclude='.github/*' .../ledger-addition.patch → ok  (W0 stacks after t3+t4)
```

(Ordered `--exclude` previews emulate "their patch applied first" on files W0 never touches; a real ordered `git apply --check` chain is impossible without applying, which the lease forbids.)

## Important executor nuance

The ledger entry must be committed AFTER placeholders are filled with real captures —
the raw patch is the SKELETON; apply it, edit in place, `git diff` review, then commit (Task 8 Step 4 spellings, plan:543-549). Do not commit [PLACEHOLDER] text.

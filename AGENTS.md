# Agent Instructions

This project uses **bd** (beads) for issue tracking. Run `bd onboard` to get started.

## Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --status in_progress  # Claim work
bd close <id>         # Complete work
bd sync               # Sync with git
```

## Task Execution Order

Tasks are organized into **8 execution phases**. Complete phases in order.

| Phase | Priority | Focus | Tasks |
|-------|----------|-------|-------|
| 1 | P0 | Project Setup | 7 |
| 2 | P1 | Database & Layout | 6 |
| 3 | P2 | Core APIs & Components | 11 |
| 4 | P3/P4 | AI Pipeline | 13 |
| 5 | P4 | Events & Real-time | 9 |
| 6 | P3 | Dashboard Components | 7 |
| 7 | P4 | Pages & Modals | 6 |
| 8 | P4 | Integration & E2E | 8 |

**Find work by phase:**
```bash
bd list --label phase-1   # Start here
bd list --label phase-2   # After phase-1 complete
# ... and so on
```

**TDD tasks** (labeled `tdd`) should be completed alongside their feature tasks:
```bash
bd list --label tdd
```

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds

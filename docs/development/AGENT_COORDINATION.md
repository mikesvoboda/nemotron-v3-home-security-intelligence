---
title: Agent Coordination Protocol
source_refs:
  - CLAUDE.md:1
  - docs/development/contributing.md:66
  - docs/development/testing.md:405
---

# Agent Coordination Protocol

This document establishes protocols for coordinating parallel Claude Code agents to prevent conflicts, duplicated work, and merge failures. Following these guidelines ensures efficient parallel development without stepping on each other's changes.

## Pre-Dispatch Checklist

Before dispatching parallel agents, complete this verification checklist:

### 1. Verify No Overlapping Work

```bash
# Check what files each task will likely touch
# Use Linear MCP tools to view task details:
# mcp__linear__get_issue(issueId="NEM-123")
# mcp__linear__get_issue(issueId="NEM-124")

# Review recent changes to target areas
git log --oneline --stat -10 -- backend/services/
git log --oneline --stat -10 -- frontend/src/hooks/
```

### 2. Define Explicit File Boundaries

Each agent MUST have a clearly defined scope. Document this BEFORE dispatching:

```
Agent 1 Scope:
- ALLOWED: backend/services/event_broadcaster.py
- ALLOWED: backend/tests/unit/services/test_event_broadcaster.py
- FORBIDDEN: All other files

Agent 2 Scope:
- ALLOWED: frontend/src/hooks/useWebSocket.ts
- ALLOWED: frontend/src/hooks/useWebSocket.test.ts
- FORBIDDEN: All other files
```

### 3. Check for Interdependencies

Ask these questions:

- Does Agent 1's work depend on Agent 2's output?
- Do both tasks modify the same API contracts?
- Do both tasks touch shared configuration files?
- Will changes require coordinated testing?

If any answer is YES, use **sequential execution** instead.

### 4. Confirm Tasks Are Truly Independent

Independent tasks must satisfy ALL of these criteria:

- [ ] No shared file modifications
- [ ] No shared API contract changes
- [ ] No shared database schema changes
- [ ] No shared configuration files (`.env`, `pyproject.toml`, `package.json`)
- [ ] No interdependent test fixtures
- [ ] Output of one is NOT input to another

## File Scope Declaration

### Declaration Format

Before each agent begins work, declare scope explicitly:

```markdown
## Agent Scope Declaration

**Agent ID:** agent-1-websocket-backend
**Task:** Implement WebSocket event deduplication
**Linear Issue:** NEM-123

### Files I WILL Modify

- `backend/services/event_broadcaster.py`
- `backend/tests/unit/services/test_event_broadcaster.py`
- `backend/tests/integration/test_websocket.py`

### Files I WILL NOT Touch

- Frontend files (any `frontend/` path)
- Database models (`backend/models/`)
- API routes (`backend/api/routes/`)
- Configuration files (`.env`, `pyproject.toml`)

### Shared Resources

- None - isolated to event broadcasting service
```

### Scope Categories

| Category     | Examples                                    | Parallel Risk |
| ------------ | ------------------------------------------- | ------------- |
| **Isolated** | Single service file + its tests             | LOW           |
| **Bounded**  | One API route + schema + tests              | MEDIUM        |
| **Shared**   | Config files, models, shared hooks          | HIGH          |
| **Global**   | `CLAUDE.md`, `pyproject.toml`, CI workflows | SEQUENTIAL    |

### Forbidden Parallel Modifications

These files should NEVER be modified by parallel agents:

- `CLAUDE.md` - Project instructions (single agent only)
- `pyproject.toml` - Python dependencies and config
- `package.json` / `package-lock.json` - Node dependencies
- `.pre-commit-config.yaml` - Pre-commit hooks
- `.github/workflows/*.yml` - CI/CD pipelines
- `docker-compose*.yml` - Container configuration
- `backend/core/config.py` - Settings class
- `backend/core/database.py` - Database connection
- `frontend/src/services/api.ts` - API client

## Anti-Patterns (MUST AVOID)

### 1. Two Agents on Same Feature Branch

**WRONG:**

```bash
# Agent 1 and Agent 2 both working on feature/websocket-improvements
git checkout feature/websocket-improvements  # Agent 1
git checkout feature/websocket-improvements  # Agent 2 - CONFLICT!
```

**CORRECT:**

```bash
# Each agent gets its own branch
git checkout -b feature/websocket-backend-dedup   # Agent 1
git checkout -b feature/websocket-frontend-hooks  # Agent 2
```

### 2. Modifying Shared Configuration Files

**WRONG:**

```
Agent 1: Adds new pytest marker to pyproject.toml
Agent 2: Updates coverage threshold in pyproject.toml
# Result: Merge conflict, one change lost
```

**CORRECT:**

```
Single Agent: Make all pyproject.toml changes in one task
```

### 3. Batch Fixes Spanning Unrelated Subsystems

**WRONG:**

```
Agent 1: "fix: resolve 9 issues - WebSocket, tests, AI model improvements"
# Touches: backend/services/, frontend/src/, ai/rtdetr/, tests/
# This is a recipe for conflicts if another agent is working anywhere
```

**CORRECT:**

```
Agent 1: "fix(websocket): resolve 403 error handling"  # Only touches WebSocket
Agent 2: "fix(ai): update RT-DETR for Transformers API"  # Only touches AI
Agent 3: "test(redis): add cache integration tests"  # Only touches tests
```

### 4. Agents Working on Interdependent Components

**WRONG:**

```
Agent 1: Modifies API response schema
Agent 2: Updates frontend hook that consumes that API
# Agent 2's work breaks when Agent 1's changes are merged
```

**CORRECT:**

```
Sequential:
1. Agent 1: Update API schema, merge, and deploy
2. Agent 2: Update frontend hook to match new schema
```

### 5. Touching Test Fixtures Used by Other Tests

**WRONG:**

```
Agent 1: Modifies conftest.py shared fixtures
Agent 2: Uses those fixtures in new integration tests
# Agent 2's tests may break when Agent 1's changes merge
```

**CORRECT:**

```
Single Agent: All conftest.py changes
Then: Other agents can write tests using updated fixtures
```

## When to Use Sequential Instead

Use **sequential execution** when ANY of these apply:

### Shared State or Dependencies

```
Task A: Create new database model Camera
Task B: Add API endpoint using Camera model
-> Task B depends on Task A's model. Run SEQUENTIALLY.
```

### Both Tasks Modify Same File

```
Task A: Add new function to utils.py
Task B: Refactor existing function in utils.py
-> Same file. Run SEQUENTIALLY.
```

### Output of One Task Needed by Another

```
Task A: Generate TypeScript types from API schemas
Task B: Create React hooks using those types
-> Task B needs Task A's output. Run SEQUENTIALLY.
```

### Tasks Require Coordinated Testing

```
Task A: Modify WebSocket backend
Task B: Modify WebSocket frontend
-> Integration tests need both changes. Run SEQUENTIALLY.
```

### Decision Matrix

| Scenario                             | Execution   |
| ------------------------------------ | ----------- |
| Backend service + unrelated frontend | PARALLEL OK |
| Two unrelated API endpoints          | PARALLEL OK |
| API endpoint + its frontend consumer | SEQUENTIAL  |
| Database migration + code using it   | SEQUENTIAL  |
| Two different test suites            | PARALLEL OK |
| Shared fixture + tests using it      | SEQUENTIAL  |
| Config change + code depending on it | SEQUENTIAL  |

## During Parallel Work Guidelines

### Each Agent Works Only in Declared Scope

Once scope is declared, agents MUST NOT deviate:

```python
# Agent working on event_broadcaster.py

# ALLOWED: Modify the service
class EventBroadcaster:
    async def broadcast(self, event: Event) -> None:
        # Implementation changes allowed

# FORBIDDEN: "While I'm here, let me also fix this..."
# backend/services/detector_client.py  # NO! Out of scope
# backend/api/routes/events.py         # NO! Out of scope
```

### No New Files Outside Scope Without Agreement

If an agent discovers they need a new file outside their scope:

1. **STOP** work on that file
2. **Document** the need in task notes
3. **Communicate** with orchestrating agent
4. **Wait** for scope expansion approval

```markdown
## Scope Expansion Request

**Original Scope:** backend/services/event_broadcaster.py
**Requested Addition:** backend/services/event_deduplicator.py

**Reason:** Deduplication logic is complex enough to warrant separate module.
**Impact:** New file, no conflicts expected.

**Awaiting approval before creating file.**
```

### Complete One Logical Change Before Moving

Agents should work in atomic units:

```
GOOD:
1. Implement feature in service file
2. Write unit tests for feature
3. Commit: "feat(service): add event deduplication"
4. Move to next logical unit

BAD:
1. Start implementing feature
2. Notice unrelated bug, start fixing it
3. Remember need tests, start writing them
4. Commit everything together as "misc changes"
```

### Commit Frequently with Clear Messages

```bash
# Good: Small, focused commits
git commit -m "feat(broadcaster): add message deduplication logic"
git commit -m "test(broadcaster): add deduplication unit tests"
git commit -m "docs(broadcaster): add docstrings for dedup methods"

# Bad: Large, unfocused commits
git commit -m "various fixes and improvements"
```

## Post-Completion Verification

### 1. Verify No Merge Conflicts

Before claiming completion, verify clean merge:

```bash
# Fetch latest main
git fetch origin main

# Check for conflicts
git merge-tree $(git merge-base HEAD origin/main) HEAD origin/main

# Or attempt merge (can abort if conflicts)
git merge origin/main --no-commit --no-ff
git merge --abort  # If conflicts exist
```

### 2. Combined Changes Pass Full Test Suite

After all parallel agents complete, run full validation:

```bash
# Full validation suite
./scripts/validate.sh

# Or manual steps:
# Backend
uv run pytest backend/tests/unit/ -n auto --dist=worksteal
uv run pytest backend/tests/integration/ -n0

# Frontend
cd frontend && npm test
cd frontend && npx playwright test
```

### 3. No Duplicate Implementations

Check for accidentally duplicated code:

```bash
# Search for similar function names
grep -r "def deduplicate" backend/
grep -r "function deduplicate" frontend/

# Check for duplicate test names
grep -r "def test_event_dedup" backend/tests/
```

### 4. Review Combined Output

Before merging, review all changes together:

```bash
# View all changes from parallel branches
git log --oneline main..feature-branch-1
git log --oneline main..feature-branch-2

# View combined diff
git diff main...feature-branch-1
git diff main...feature-branch-2
```

### Post-Merge Checklist

- [ ] All branches merged without conflicts
- [ ] Full test suite passes
- [ ] No duplicate code or implementations
- [ ] Documentation updated if needed
- [ ] Linear issues closed for all completed tasks

## Common Coordination Patterns

### Pattern 1: Independent Features (PARALLEL OK)

Two features touching completely different parts of the codebase:

```
Feature A: Add camera health monitoring
  Files: backend/services/camera_health.py
         backend/tests/unit/services/test_camera_health.py
         frontend/src/components/CameraHealth.tsx

Feature B: Implement alert rules editor
  Files: backend/services/alert_rules.py
         backend/tests/unit/services/test_alert_rules.py
         frontend/src/components/AlertRulesEditor.tsx

-> No overlap. PARALLEL OK.
```

### Pattern 2: Dependent Features (SEQUENTIAL REQUIRED)

Features with data or API dependencies:

```
Feature A: Create Event database model
  Files: backend/models/event.py
         backend/core/database.py (model registration)
         migrations/

Feature B: Create Events API endpoints
  Files: backend/api/routes/events.py
         backend/api/schemas/events.py
  Depends: Feature A's Event model

-> Feature B cannot work without Feature A. SEQUENTIAL.
```

### Pattern 3: Shared Infrastructure (SINGLE AGENT)

Changes to shared infrastructure that affect multiple systems:

```
Task: Update WebSocket message format
  Files: backend/services/event_broadcaster.py
         backend/api/schemas/websocket.py
         frontend/src/hooks/useWebSocket.ts
         frontend/src/types/websocket.ts

-> All files are coupled. SINGLE AGENT handles entire change.
```

### Pattern 4: Test Suite Expansion (PARALLEL with Care)

Multiple agents adding tests to different areas:

```
Agent 1: Add unit tests for services
  Scope: backend/tests/unit/services/

Agent 2: Add integration tests for API
  Scope: backend/tests/integration/api/

Agent 3: Add E2E tests for dashboard
  Scope: frontend/tests/e2e/dashboard/

-> Different test directories. PARALLEL OK.
-> BUT: Do NOT modify shared conftest.py in parallel!
```

### Pattern 5: Documentation Updates (PARALLEL OK)

Multiple agents updating different documentation:

```
Agent 1: Update API reference docs
  Scope: docs/api-reference/

Agent 2: Update developer guides
  Scope: docs/development/

Agent 3: Update operator guides
  Scope: docs/operator/

-> Different doc directories. PARALLEL OK.
-> BUT: Do NOT modify CLAUDE.md or root README.md in parallel!
```

## Skills and Tools Reference

Use these superpowers skills for coordination:

### `/dispatching-parallel-agents`

Use when facing 2+ independent tasks. This skill helps:

- Verify task independence
- Assign file scopes
- Coordinate parallel execution
- Merge results

```
/dispatching-parallel-agents
```

### `/using-git-worktrees`

Use for isolated development environments:

```
/using-git-worktrees
```

Benefits:

- Each agent gets isolated workspace
- No branch switching conflicts
- Clean separation of work
- Easy cleanup after completion

### `/requesting-code-review`

Use after parallel work completes to verify combined output:

```
/requesting-code-review
```

Review checks:

- No conflicting changes
- Combined tests pass
- No duplicate implementations
- Architecture consistency

### `/verification-before-completion`

Use before claiming any task complete:

```
/verification-before-completion
```

Ensures:

- Tests actually pass
- No regressions introduced
- Changes work as claimed

## Lessons from Git History

These anti-patterns have caused real issues in this repository:

### Issue: Batch Fixes Across Subsystems

**Commit:** `cbebedc fix: resolve 9 issues - WebSocket, tests, AI model improvements`

**Problem:** Single commit touched:

- AI (RT-DETR tests, logging)
- Backend (WebSocket tests, Redis tests)
- Frontend (E2E fixtures, page objects)

**Why it's problematic:**

- Difficult to review (too many unrelated changes)
- Hard to bisect if something breaks
- Blocks parallel work across all touched areas
- One failing test blocks all changes

**Solution:** One task, one PR, one logical change.

### Issue: Shared File Modifications

**Pattern:** Multiple commits touching `pyproject.toml` or `conftest.py`

**Problem:** When two agents modify shared config:

- Merge conflicts are likely
- Changes may be incompatible
- Testing becomes complex

**Solution:** Config changes are ALWAYS single-agent tasks.

### Issue: Test Isolation Failures

**Pattern:** Tests failing when run in parallel but passing alone

**Example from testing.md:**

```
"Parallel test conflicts - use unique_id() for test data IDs"
```

**Problem:** Multiple tests creating same test data (camera IDs, event IDs)

**Solution:**

- Use `unique_id("camera_")` fixture for unique IDs
- Use `xdist_group` marker for tests that must run sequentially
- Never use hardcoded IDs in parallel-safe tests

### Issue: Frontend/Backend Desync

**Pattern:** Backend API changes without coordinated frontend updates

**Problem:**

- Frontend tests fail
- Type mismatches
- Runtime errors in production

**Solution:**

- API contract changes are sequential tasks
- Update backend, merge, then update frontend
- Or single agent handles both sides

## Quick Reference

### Parallel Work Checklist

```markdown
## Pre-Dispatch

- [ ] Tasks are truly independent
- [ ] File scopes declared for each agent
- [ ] No shared config files modified
- [ ] No API contract changes requiring coordination

## During Work

- [ ] Each agent stays in declared scope
- [ ] Commits are small and focused
- [ ] No scope creep into other areas

## Post-Completion

- [ ] No merge conflicts
- [ ] Full test suite passes
- [ ] No duplicate implementations
- [ ] Combined changes reviewed
```

### When in Doubt

If unsure whether to run tasks in parallel:

1. **Default to SEQUENTIAL** - Slower but safer
2. **Ask for clarification** - Verify task boundaries
3. **Start with smallest scope** - Expand if needed
4. **Review git history** - Learn from past conflicts

## Related Documentation

- [Contributing Guide](contributing.md) - PR process and code standards
- [Testing Guide](testing.md) - Test infrastructure and patterns
- [CLAUDE.md](../../CLAUDE.md) - Project instructions and rules

# Git Workflow and Pre-commit Rules

This document covers git safety protocols, pre-commit hook configuration, and the critical testing policy. For detailed hook documentation, see [hooks.md](hooks.md).

## Development Workflow Overview

```mermaid
%%{init: {
  'theme': 'dark',
  'themeVariables': {
    'primaryColor': '#3B82F6',
    'primaryTextColor': '#FFFFFF',
    'primaryBorderColor': '#60A5FA',
    'secondaryColor': '#A855F7',
    'tertiaryColor': '#009688',
    'background': '#121212',
    'mainBkg': '#1a1a2e',
    'lineColor': '#666666'
  }
}}%%
flowchart LR
    subgraph Local["Local Development"]
        BRANCH["Create branch"]
        CODE["Write code"]
        COMMIT["git commit"]
        PUSH["git push"]
    end

    subgraph Hooks["Automated Checks"]
        PRECOMMIT["Pre-commit hooks<br/>lint, format, types"]
        PREPUSH["Pre-push hooks<br/>unit tests, rebase"]
    end

    subgraph Remote["Remote Repository"]
        CI["CI Pipeline<br/>full test suite"]
        REVIEW["Code Review"]
        MERGE["Merge to main"]
    end

    BRANCH --> CODE --> COMMIT
    COMMIT --> PRECOMMIT
    PRECOMMIT -->|"pass"| PUSH
    PRECOMMIT -->|"fail"| CODE
    PUSH --> PREPUSH
    PREPUSH -->|"pass"| CI
    PREPUSH -->|"fail"| CODE
    CI -->|"pass"| REVIEW
    CI -->|"fail"| CODE
    REVIEW -->|"approved"| MERGE
    REVIEW -->|"changes requested"| CODE

    style BRANCH fill:#3B82F6,stroke:#60A5FA
    style PRECOMMIT fill:#A855F7,stroke:#C084FC
    style PREPUSH fill:#A855F7,stroke:#C084FC
    style CI fill:#009688,stroke:#14B8A6
    style MERGE fill:#16A34A,stroke:#22C55E
```

## PR Workflow (Branch to Merge)

```mermaid
%%{init: {
  'theme': 'dark',
  'themeVariables': {
    'primaryColor': '#3B82F6',
    'primaryTextColor': '#FFFFFF',
    'primaryBorderColor': '#60A5FA',
    'secondaryColor': '#A855F7',
    'tertiaryColor': '#009688',
    'background': '#121212',
    'mainBkg': '#1a1a2e',
    'lineColor': '#666666'
  }
}}%%
sequenceDiagram
    participant DEV as Developer
    participant LOCAL as Local Repo
    participant HOOKS as Pre-commit/Push
    participant REMOTE as GitHub
    participant CI as CI Pipeline
    participant REVIEWER as Reviewer

    DEV->>LOCAL: git checkout -b feature/name
    DEV->>LOCAL: Write code + tests
    DEV->>LOCAL: git add <files>
    DEV->>HOOKS: git commit -m "feat: ..."

    alt Pre-commit fails
        HOOKS-->>DEV: Lint/format/type errors
        DEV->>DEV: Fix issues
        DEV->>HOOKS: git commit (retry)
    end

    HOOKS-->>LOCAL: Commit created

    DEV->>HOOKS: git push -u origin feature/name

    alt Pre-push fails
        HOOKS-->>DEV: Test failures / rebase needed
        DEV->>DEV: Fix issues
        DEV->>HOOKS: git push (retry)
    end

    HOOKS-->>REMOTE: Push successful

    DEV->>REMOTE: gh pr create
    REMOTE->>CI: Trigger CI pipeline

    alt CI fails
        CI-->>DEV: Test/build failures
        DEV->>DEV: Fix issues
        DEV->>REMOTE: git push (updates PR)
    end

    CI-->>REMOTE: All checks pass
    REMOTE->>REVIEWER: Request review

    alt Changes requested
        REVIEWER-->>DEV: Feedback
        DEV->>DEV: Address feedback
        DEV->>REMOTE: git push (updates PR)
        REMOTE->>REVIEWER: Re-request review
    end

    REVIEWER-->>REMOTE: Approve PR
    REMOTE->>REMOTE: Merge to main
    Note right of REMOTE: Squash and merge
```

## Git Safety Protocol

**CRITICAL: Never bypass git pre-commit hooks.** All commits must pass pre-commit checks including:

- `ruff check` - Python linting
- `ruff format` - Python formatting
- `mypy` - Python type checking
- `eslint` - TypeScript/JavaScript linting
- `prettier` - Code formatting

### Test Strategy (optimized for performance)

| Stage      | What Runs                          | Runtime   |
| ---------- | ---------------------------------- | --------- |
| Pre-commit | Fast lint/format/type checks only  | ~10-30s   |
| Pre-push   | Unit tests (install separately)    | ~30-60s   |
| CI         | Full test suite with 95% coverage  | ~5-10 min |
| Manual     | `./scripts/validate.sh` before PRs | ~2-3 min  |

### Forbidden Commands

**Do NOT use:**

- `git commit --no-verify`
- `git push --no-verify`
- Any flags that skip pre-commit hooks

### Branch Protection (GitHub enforced)

- All CI jobs must pass before merge
- Admin bypass is disabled
- CODEOWNERS review required

## NEVER DISABLE TESTING

> **ABSOLUTE RULE: Unit and integration tests must NEVER be disabled, removed, or bypassed.**

This rule is non-negotiable. Previous agents have violated this rule by:

- Moving test hooks from `pre-commit` to `pre-push` stage (reducing test frequency)
- Lowering coverage thresholds to pass CI
- Commenting out or skipping failing tests
- Removing test assertions to make tests pass

**If tests are failing, FIX THE CODE or FIX THE TESTS. Do not:**

1. Disable the test hook
2. Change the hook stage to run less frequently
3. Lower coverage thresholds
4. Skip tests with `@pytest.skip` without a documented reason
5. Remove test files or test functions
6. Use `--no-verify` flags

### Required Hooks That Must Remain Active

| Hook                      | Stage    | Purpose                            |
| ------------------------- | -------- | ---------------------------------- |
| `fast-test`               | pre-push | Runs unit tests before every push  |
| Backend Unit Tests        | CI       | Full unit test suite with coverage |
| Backend Integration Tests | CI       | API and service integration tests  |
| Frontend Tests            | CI       | Component and hook tests           |
| E2E Tests                 | CI       | End-to-end browser tests           |

## Pre-commit Setup

**Run once per clone:**

```bash
pre-commit install                       # Install pre-commit hooks
pre-commit install --hook-type pre-push  # Install pre-push hooks
```

If you encounter test failures, your job is to investigate and fix them, not to disable the safety net.

## Running Hooks Manually

If pre-commit checks fail, fix the issues before committing:

```bash
# Backend
uv run pytest backend/tests/ -v

# Frontend
cd frontend && npm test

# Full validation (recommended before PRs)
./scripts/validate.sh

# Pre-commit (runs lint/format checks)
pre-commit run --all-files
```

## Hook Skip (Emergency Only)

In emergencies, you can skip specific hooks (CI will still catch issues):

```bash
# Skip specific hook
SKIP=hadolint,semgrep git commit -m "message"

# Skip pre-push hooks
SKIP=fast-test git push
```

**WARNING:** Skipping hooks should only be done when absolutely necessary. All changes will still be validated in CI.

## Related Documentation

- [Pre-commit Hooks](hooks.md) - Detailed hook documentation
- [Code Quality Tools](code-quality.md) - Tool configuration
- [Testing Guide](testing.md) - Test infrastructure
- [TDD Workflow](testing-workflow.md) - Test-driven development process

# Testing Documentation - Agent Guide

## Purpose

This directory contains testing-specific documentation and analysis reports for the Home Security Intelligence project.

## Directory Contents

```
testing/
  AGENTS.md                                # This file
  INTEGRATION_TEST_COVERAGE_ANALYSIS.md    # Integration test coverage analysis report
```

## Key Files

### INTEGRATION_TEST_COVERAGE_ANALYSIS.md

**Purpose:** Comprehensive analysis of integration test coverage across the codebase.

**Topics Covered:**

- Current integration test coverage metrics
- Coverage gaps and areas needing additional tests
- Test distribution across modules
- Recommendations for improving coverage
- Priority areas for test development

**When to use:** Planning integration test development, identifying coverage gaps, prioritizing testing efforts.

## Related Documentation

| Resource                               | Description                         |
| -------------------------------------- | ----------------------------------- |
| `docs/development/testing.md`          | Comprehensive testing guide         |
| `docs/development/testing-workflow.md` | TDD workflow and RED-GREEN-REFACTOR |
| `docs/development/coverage.md`         | Coverage reporting and analysis     |
| `docs/developer/patterns/AGENTS.md`    | Testing patterns documentation      |
| `backend/tests/AGENTS.md`              | Backend test infrastructure         |
| `frontend/src/__tests__/`              | Frontend test files                 |

## Testing Resources

### Quick Test Commands

```bash
# Backend unit tests (parallel)
uv run pytest backend/tests/unit/ -n auto --dist=worksteal

# Backend integration tests (serial)
uv run pytest backend/tests/integration/ -n0

# Frontend tests
cd frontend && npm test

# Full validation
./scripts/validate.sh
```

### Coverage Requirements

| Test Type        | Minimum Coverage |
| ---------------- | ---------------- |
| Backend Unit     | 85%              |
| Backend Combined | 95%              |
| Frontend         | 83%/77%/81%/84%  |

## Entry Points for Agents

1. **Understanding test coverage:** Read `INTEGRATION_TEST_COVERAGE_ANALYSIS.md`
2. **Writing tests:** See `docs/development/testing.md`
3. **Following TDD:** See `docs/development/testing-workflow.md`
4. **Test patterns:** See `docs/developer/patterns/AGENTS.md`

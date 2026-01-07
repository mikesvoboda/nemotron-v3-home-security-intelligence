# Testing Directory - Agent Guide

## Purpose

This directory contains testing guides, workflows, and patterns for the Home Security Intelligence project. It provides comprehensive documentation for Test-Driven Development (TDD), property-based testing, and common testing patterns used throughout the codebase.

## Directory Contents

```
docs/testing/
  AGENTS.md              # This file
  TDD_WORKFLOW.md        # Test-Driven Development workflow guide
  TESTING_PATTERNS.md    # Common testing patterns and best practices
  HYPOTHESIS_GUIDE.md    # Property-based testing with Hypothesis
```

## Key Files

### TDD_WORKFLOW.md

**Purpose:** Step-by-step guide for implementing features using Test-Driven Development.

**Status:** Placeholder (empty file - needs content)

**Planned Content:**

- RED-GREEN-REFACTOR cycle
- Writing failing tests first
- Minimum implementation to pass
- Refactoring while keeping tests green
- Integration with Linear issues labeled `tdd`
- Examples from backend (pytest) and frontend (Vitest)

### TESTING_PATTERNS.md

**Purpose:** Common testing patterns used across the project.

**Status:** Placeholder (empty file - needs content)

**Planned Content:**

- **Backend Patterns:**

  - FastAPI route testing with TestClient
  - Async service testing with pytest-asyncio
  - Database testing with fixtures
  - Mock patterns for external services (Redis, AI models)
  - WebSocket testing patterns

- **Frontend Patterns:**

  - Component testing with React Testing Library
  - Hook testing patterns
  - Mock API responses with MSW
  - WebSocket mock patterns
  - Accessibility testing

- **E2E Patterns:**
  - Page Object Model
  - Test fixtures and data factories
  - API mocking in Playwright
  - Screenshot comparison

### HYPOTHESIS_GUIDE.md

**Purpose:** Guide to property-based testing using Hypothesis for Python tests.

**Status:** Placeholder (empty file - needs content)

**Planned Content:**

- Introduction to property-based testing
- Setting up Hypothesis strategies
- Writing property tests for models
- Common strategies for this project:
  - Camera configurations
  - Detection results
  - Risk scores (0-100 range)
  - Timestamps and date ranges
- Shrinking and debugging failures
- Integration with pytest
- Coverage vs property testing

## Testing Philosophy

This project follows strict testing practices:

1. **TDD Approach:** Tests written before implementation (especially for tasks labeled `tdd`)
2. **Coverage Requirements:**
   - Backend: 85% unit, 95% combined
   - Frontend: 83%/77%/81%/84% (statements/branches/functions/lines)
3. **Never Disable Testing:** Tests must never be skipped, disabled, or removed without fixing the underlying issue

## Related Documentation

- `/CLAUDE.md` - Testing requirements and TDD approach
- `/docs/development/testing.md` - Comprehensive testing guide
- `/docs/TEST_PERFORMANCE_METRICS.md` - Test suite performance baselines
- `/backend/tests/AGENTS.md` - Backend test infrastructure
- `/frontend/tests/AGENTS.md` - Frontend test architecture

## Entry Points for Agents

### Understanding Testing Strategy

1. **Start with CLAUDE.md** - Read the "TDD Approach" and "Testing Requirements" sections
2. **Review this directory** - Understand the testing philosophy and patterns
3. **Check actual tests:**
   - Backend: `/backend/tests/unit/` and `/backend/tests/integration/`
   - Frontend: `/frontend/src/**/*.test.ts` and `/frontend/tests/e2e/`

### Writing Tests

1. **For backend features:**

   - Read `TDD_WORKFLOW.md` (when populated)
   - Check existing test patterns in `/backend/tests/unit/`
   - Use fixtures from `/backend/tests/conftest.py`

2. **For frontend features:**

   - Read `TESTING_PATTERNS.md` (when populated)
   - Check component tests in `/frontend/src/components/**/*.test.tsx`
   - Use test utilities from `/frontend/src/test/`

3. **For property testing:**
   - Read `HYPOTHESIS_GUIDE.md` (when populated)
   - Check examples in backend unit tests with `@given` decorator

## Notes for AI Agents

- These placeholder files should be populated with actual content when implementing testing-focused tasks
- The testing strategy is already well-documented in CLAUDE.md and enforced via CI
- This directory provides a centralized location for testing documentation
- When adding content, ensure it aligns with existing practices in the codebase
- Cross-reference with actual test files to keep documentation accurate

## TODO: Content Needed

The following files are empty placeholders and need content:

- [ ] `TDD_WORKFLOW.md` - Add RED-GREEN-REFACTOR workflow with examples
- [ ] `TESTING_PATTERNS.md` - Document common testing patterns from codebase
- [ ] `HYPOTHESIS_GUIDE.md` - Add property-based testing guide with project-specific strategies

When populating these files, extract patterns from:

- Existing test files in `/backend/tests/`
- Frontend tests in `/frontend/src/**/*.test.ts`
- E2E tests in `/frontend/tests/e2e/`
- CLAUDE.md TDD section

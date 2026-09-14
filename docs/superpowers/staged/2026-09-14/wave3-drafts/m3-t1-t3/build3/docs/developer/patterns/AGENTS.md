# Testing and Code Patterns - Agent Guide

## Purpose

This directory contains documentation for testing patterns and code patterns used in the Home Security Intelligence project. These guides help developers write consistent, effective tests and follow established coding conventions.

## Directory Contents

```
patterns/
  AGENTS.md                    # This file
  form-validation.md           # Frontend/backend validation alignment audit
  frontend.md                  # JavaScript/TypeScript code patterns
  mutation-testing.md          # Mutation testing guide and configuration
  test-optimization-guide.md   # Frontend test optimization patterns
  test-performance.md          # Test performance metrics and CI configuration
```

## Quick Navigation

| File                         | Purpose                                             | When to Use                                                    |
| ---------------------------- | --------------------------------------------------- | -------------------------------------------------------------- |
| `form-validation.md`         | Audit of frontend/backend validation alignment      | When adding form fields, ensuring validation consistency       |
| `frontend.md`                | JS/TS patterns (Result type, AbortController, etc.) | When writing frontend code, understanding established patterns |
| `mutation-testing.md`        | Mutation testing guide and configuration            | When evaluating test quality, running mutation tests           |
| `test-optimization-guide.md` | Frontend test optimization patterns                 | When optimizing test execution time, reducing CI duration      |
| `test-performance.md`        | Test suite metrics and CI parallelization config    | When debugging slow tests, understanding CI configuration      |

## Key Patterns

### Form Validation (`form-validation.md`)

**Topics Covered:**

- Camera, Zone, Alert Rules form validation
- Centralized validation constants (`VALIDATION_LIMITS`)
- Backend Pydantic schema alignment
- Validation architecture and best practices

**When to use:** Adding new form fields, modifying validation constraints, ensuring frontend/backend consistency.

### Frontend Patterns (`frontend.md`)

**Topics Covered:**

- Result type for error handling (inspired by Rust)
- AbortController for request cancellation
- usePolling hook for interval-based data fetching
- Typed event emitter for WebSocket messages
- Promise.allSettled for partial failure handling
- Functional utilities (pipe, compose, curry, debounce, throttle)

**When to use:** Writing new frontend code, refactoring error handling, implementing request cancellation.

### Mutation Testing (`mutation-testing.md`)

**Topics Covered:**

- What is mutation testing and why use it
- Running mutation tests (mutmut for Python, Stryker for TypeScript)
- Target modules and mutation scores
- Understanding and improving mutation score
- CI integration (non-blocking)
- Troubleshooting surviving mutants

**When to use:** Evaluating test suite effectiveness, improving test quality, investigating test gaps.

### Test Performance (`test-performance.md`)

**Topics Covered:**

- Test suite overview and counts
- CI parallelization strategy (backend/frontend)
- Performance thresholds and slow test patterns
- Caching strategy for CI
- Baseline metrics and expected CI duration

**When to use:** Debugging slow tests, understanding CI configuration, updating test baselines.

### Test Optimization Guide (`test-optimization-guide.md`)

**Topics Covered:**

- waitFor() timeout optimization (FAST_TIMEOUT vs STANDARD_TIMEOUT)
- Fake timers best practices with Vitest
- Shared mock utilities (router, API, WebSocket, React Query)
- Component testing strategies and isolation
- Route testing without full app rendering
- Lazy loading test patterns
- Performance metrics and migration checklist

**When to use:** Optimizing frontend test execution time, reducing CI duration, migrating tests to use optimized patterns.

## Related Resources

| Topic            | Location                               | Notes                           |
| ---------------- | -------------------------------------- | ------------------------------- |
| TDD Workflow     | `docs/development/testing-workflow.md` | RED-GREEN-REFACTOR cycle        |
| Testing Guide    | `docs/development/testing.md`          | Test infrastructure, fixtures   |
| Code Quality     | `docs/development/code-quality.md`     | Linting, formatting, analysis   |
| Backend Patterns | `docs/developer/backend-patterns.md`   | Repository pattern, Result type |
| Testing Guide    | `docs/development/testing.md`          | Comprehensive testing examples  |

## Target Audience

| Audience           | Needs                              | Primary Documents               |
| ------------------ | ---------------------------------- | ------------------------------- |
| **Developers**     | Writing tests, code patterns       | frontend.md, form-validation.md |
| **QA Engineers**   | Test quality evaluation            | mutation-testing.md             |
| **CI Maintainers** | Test performance, parallelization  | test-performance.md             |
| **New Members**    | Understanding established patterns | frontend.md                     |

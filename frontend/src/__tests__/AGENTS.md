# Frontend Configuration Tests Directory

## Purpose

Specialized test directory for configuration file validation and infrastructure tests. Unlike component tests (co-located with source files), this directory contains tests that validate build configurations, CI/CD settings, and project-level configurations.

## Key Files

### `lighthouserc.test.ts`

Tests for Lighthouse CI configuration validation. Ensures the `lighthouserc.js` config file has correct structure and reasonable threshold values for performance monitoring.

**Test Categories:**

| Category               | Description                                                  |
| ---------------------- | ------------------------------------------------------------ |
| Config Structure       | Validates `ci.collect`, `ci.assert`, `ci.upload` properties  |
| Collect Configuration  | Verifies `staticDistDir`, `numberOfRuns` settings            |
| Assert Configuration   | Checks for Core Web Vitals assertions                        |
| Assertion Thresholds   | Validates performance score and metric thresholds            |
| Threshold Value Ranges | Ensures exact threshold values match project requirements    |
| Upload Configuration   | Verifies upload target configuration                         |

**Core Web Vitals Thresholds Tested:**

| Metric                     | Threshold | Level |
| -------------------------- | --------- | ----- |
| Performance Score          | 80%       | warn  |
| First Contentful Paint     | 2000ms    | warn  |
| Largest Contentful Paint   | 4000ms    | warn  |
| Cumulative Layout Shift    | 0.1       | warn  |
| Total Blocking Time        | 300ms     | warn  |

## Test Framework

Uses **Vitest** with the following imports:

```typescript
import { beforeAll, describe, expect, it } from 'vitest';
```

## Running Tests

```bash
# Run all tests (includes this directory)
cd frontend && npm test

# Run only configuration tests
npm test -- lighthouserc.test.ts

# Run tests once (CI mode)
npm test -- --run

# Run with coverage
npm run test:coverage
```

## Test Organization

### Why This Directory Exists

This directory separates **infrastructure/configuration tests** from **component/feature tests**:

- **`src/__tests__/`**: Configuration validation, build tool tests, CI/CD config tests
- **`src/**/*.test.tsx`**: Component and feature tests (co-located with source)
- **`tests/integration/`**: Multi-component integration tests
- **`tests/e2e/`**: End-to-end browser tests

### When to Add Tests Here

Add tests to this directory when:

1. Testing project configuration files (`.js`, `.json`, `.yaml` configs)
2. Validating build tool settings (Vite, ESLint, Prettier, etc.)
3. Testing CI/CD pipeline configurations
4. Validating performance budgets and thresholds
5. Testing infrastructure-level concerns

### When NOT to Add Tests Here

Do NOT add tests here for:

- React components (co-locate with component file)
- Hooks (co-locate in `src/hooks/`)
- Services (co-locate in `src/services/`)
- Utilities (co-locate in `src/utils/`)

## Coverage Requirements

Tests in this directory are included in overall coverage metrics:

- **Statements**: 95%
- **Branches**: 94%
- **Functions**: 95%
- **Lines**: 95%

## Type Definitions

The `lighthouserc.test.ts` file includes TypeScript interfaces for Lighthouse CI config validation:

```typescript
interface LighthouseCIConfig {
  ci: {
    collect: LighthouseCollect;
    assert: LighthouseAssert;
    upload: LighthouseUpload;
  };
}
```

These types ensure type-safe validation of configuration structures.

## Related Files

- `/frontend/lighthouserc.js` - Lighthouse CI configuration (source of truth)
- `/frontend/vite.config.ts` - Vitest configuration
- `/frontend/src/test/setup.ts` - Global test setup

## Notes for AI Agents

- This directory is for **configuration tests only**, not feature tests
- Tests validate config structure and values, not runtime behavior
- Use TypeScript interfaces to define expected config shapes
- Keep threshold values in sync with actual config files
- Run `npm test -- lighthouserc.test.ts` to validate changes to performance configs

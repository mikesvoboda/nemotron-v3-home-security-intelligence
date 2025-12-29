# Frontend Configuration Tests Directory

## Purpose

Specialized test directory for configuration file validation and infrastructure tests. Unlike component tests (co-located with source files), this directory contains tests that validate build configurations and project-level settings.

## Directory Contents

```
frontend/src/__tests__/
├── AGENTS.md              # This documentation file
└── lighthouserc.test.ts   # Lighthouse CI configuration validation tests
```

## Key Files

### lighthouserc.test.ts

Validates the Lighthouse CI configuration structure and threshold values. Tests ensure performance monitoring is correctly configured.

**Test Suites (6 suites, 20 tests):**

| Suite                  | Tests                                         |
| ---------------------- | --------------------------------------------- |
| Config Structure       | ci property, collect, assert, upload sections |
| Collect Configuration  | staticDistDir, numberOfRuns validation        |
| Assert Configuration   | assertions object, Core Web Vitals presence   |
| Assertion Thresholds   | Performance score, FCP, LCP, CLS, TBT ranges  |
| Threshold Value Ranges | Exact threshold value verification            |
| Upload Configuration   | Valid upload target                           |

**Expected Thresholds:**

| Metric                   | Threshold | Level |
| ------------------------ | --------- | ----- |
| Performance Score        | 80%       | warn  |
| First Contentful Paint   | 2000ms    | warn  |
| Largest Contentful Paint | 4000ms    | warn  |
| Cumulative Layout Shift  | 0.1       | warn  |
| Total Blocking Time      | 300ms     | warn  |

## Test Framework

Uses Vitest with TypeScript interfaces for config validation:

```typescript
interface LighthouseCIConfig {
  ci: {
    collect: LighthouseCollect;
    assert: LighthouseAssert;
    upload: LighthouseUpload;
  };
}
```

## Running Tests

```bash
# From frontend/ directory
npm test                              # Run all tests (includes this)
npm test -- lighthouserc.test.ts      # Run only this test
npm test -- --run                     # Single run (CI mode)
```

## When to Add Tests Here

Add tests to this directory when:

1. Testing project configuration files (`.js`, `.json`, `.yaml` configs)
2. Validating build tool settings (Vite, ESLint, Prettier, etc.)
3. Testing CI/CD pipeline configurations
4. Validating performance budgets and thresholds

**Do NOT add tests here for:**

- React components (co-locate with component file)
- Hooks (co-locate in `src/hooks/`)
- Services (co-locate in `src/services/`)
- Utilities (co-locate in `src/utils/`)

## Related Files

- `/frontend/lighthouserc.js` - Lighthouse CI configuration (source of truth)
- `/frontend/vite.config.ts` - Vitest configuration
- `/frontend/src/test/setup.ts` - Global test setup

## Notes for AI Agents

- This directory is for **configuration tests only**, not feature tests
- Tests validate config structure and values, not runtime behavior
- TypeScript interfaces ensure type-safe validation
- Keep threshold values in sync with actual config files
- Tests are automatically discovered by Vitest

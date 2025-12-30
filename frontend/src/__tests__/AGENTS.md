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

**Test Suites (6 suites, 21 tests):**

| Suite                      | Tests                                                                                            |
| -------------------------- | ------------------------------------------------------------------------------------------------ |
| Config Structure (4)       | ci property, collect, assert, upload sections                                                    |
| Collect Configuration (3)  | staticDistDir, numberOfRuns defined, numberOfRuns between 1-10                                   |
| Assert Configuration (3)   | assertions object, performance category, Core Web Vitals presence                                |
| Assertion Thresholds (6)   | Performance score >= 0.5, FCP < 5000ms, LCP < 8000ms, CLS < 0.5, TBT < 1000ms, warn/error levels |
| Threshold Value Ranges (5) | Exact threshold values: 0.8 perf, 2000ms FCP, 4000ms LCP, 0.1 CLS, 300ms TBT                     |
| Upload Configuration (1)   | Valid upload target (temporary-public-storage, lhci, filesystem)                                 |

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

# Frontend Testing Quick Start

## Installation

```bash
cd frontend
npm ci        # deterministic install from package-lock.json (what CI uses)
```

Key testing dependencies:

- `vitest` - unit test runner (Vite-native)
- `@testing-library/react` - React component testing utilities
- `@testing-library/jest-dom` - Custom matchers for DOM testing
- `@testing-library/user-event` - User interaction simulation
- `jsdom` - DOM implementation for Node.js
- `msw` - HTTP mocking for integration-style tests
- `@playwright/test` - browser E2E tests

## Running Unit Tests

```bash
# Run all tests once (what CI runs)
npm test -- --run

# Watch mode (auto-rerun on changes) — the default `npm test` behavior
npm test

# Run tests with UI dashboard
npm run test:ui

# Run tests with coverage report
npm run test:coverage

# Run a specific test file
npm test -- Header.test.tsx

# Run tests matching a test-name pattern
npm test -- --run --grep "renders"
```

Bun works too (`bun run test`), but never run bare `bun test` — it uses Bun's
native runner, not Vitest. See `README-TESTING.md`.

## Test Scale

The suite is far larger than the handful of smoke tests this file originally
described. Measured 2026-09-22:

- ~800 Vitest unit/integration test files under `src/` (co-located `*.test.ts[x]`)
- 68 Playwright spec files under `tests/e2e/`

Run them sharded in CI; locally, point Vitest at one path to get fast feedback:

```bash
npm test -- src/components/dashboard/
```

## Coverage Floors

`vite.config.ts` sets coverage thresholds at the measured values (R-1 ruling:
a floor that has never held is not a floor):

| Metric     | Floor |
| ---------- | ----- |
| statements | 80    |
| branches   | 74.6  |
| functions  | 78.4  |
| lines      | 80.9  |

CI enforces these on the **merged** shard data (`merge-shard-coverage.mjs
--enforce`), only when every Vitest shard passed. Locally
`npm run test:coverage` enforces them against the single-run numbers.

## Configuration Files

- `vite.config.ts` - Vitest configuration (pool, thresholds, jsdom)
- `src/test/setup.ts` - Test environment setup (matchers, mocks)
- `src/test/factories/` - Test data factories
- `package.json` - Testing dependencies and scripts

## E2E Tests

```bash
npm run test:e2e                 # all Playwright projects
npm run test:e2e -- --project=chromium
npm run test:e2e:headed          # watch it run
```

Playwright starts its own Vite server (`npm run dev:e2e`, HTTP on port 8444,
no API proxy — specs mock APIs with `page.route()`). See
`tests/e2e/AGENTS.md`.

## Next Steps

1. Install dependencies: `npm ci`
2. Run tests: `npm test -- --run`
3. Review coverage: `npm run test:coverage`
4. Read detailed docs: `TESTING.md` for comprehensive documentation

## Troubleshooting

If tests fail to run:

1. Ensure all dependencies are installed: `npm ci`
2. Clear cache: `rm -rf node_modules && npm ci`
3. Check Node.js version: `node --version` (needs ^22.12 or >=24; `.nvmrc` pins 24)
4. Out-of-memory during a full run: the test script already sets
   `NODE_OPTIONS=--max-old-space-size` from `VITEST_HEAP_MB` (default 8192);
   raise it if your box allows

## CI/CD Integration

Mirror what this repo's own workflows do:

```yaml
- name: Install dependencies
  run: cd frontend && npm ci

- name: Run tests
  run: cd frontend && npm test -- --run

- name: Generate coverage
  run: cd frontend && npm run test:coverage
```

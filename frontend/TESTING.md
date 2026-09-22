# Frontend Testing Documentation

## Overview

This document describes the testing infrastructure and test coverage for the frontend React application.

## Testing Stack

### Unit/Integration Tests

- **Test Runner**: Vitest
- **Testing Library**: React Testing Library (@testing-library/react)
- **User Interactions**: @testing-library/user-event
- **DOM Matchers**: @testing-library/jest-dom
- **Environment**: jsdom

### E2E Tests

- **Test Framework**: Playwright
- **Browsers**: Chromium, Firefox, WebKit, plus mobile/tablet viewports (see `playwright.config.ts` projects)
- **Test Location**: `tests/e2e/`

## Installation

Before running tests, install the required dependencies:

```bash
cd frontend
npm ci        # deterministic install from package-lock.json (what CI uses)
```

This installs all testing dependencies listed in `package.json`:

- `@testing-library/react`
- `@testing-library/jest-dom`
- `@testing-library/user-event`
- `jsdom`
- `vitest`
- `msw`
- `@playwright/test`

For E2E tests, also install the Chromium browser:

```bash
npx playwright install chromium
```

## Running Tests

### Important: Bun Compatibility

This project uses **Vitest** as the test runner, not Bun's native test runner.

**✅ Correct Commands:**

```bash
npm test              # Run Vitest (recommended)
bun run test          # Also runs Vitest via package.json script
```

**❌ Do NOT Use:**

```bash
bun test              # This invokes Bun's native test runner (incompatible!)
```

**Why not `bun test`?**

- Tests use Vitest-specific APIs (`vi.mock`, `vi.spyOn`, etc.)
- jsdom environment is configured in `vite.config.ts` (Vitest-specific)
- Tests use Vitest's `setupFiles` and custom matchers
- Bun's native test runner has different APIs and cannot run these tests

A `bunfig.toml` file exists to document this limitation.

### Unit Tests (Vitest)

```bash
# Run all unit tests
npm test

# Run tests in watch mode
npm test -- --watch

# Run tests with coverage
npm test -- --coverage

# Run a specific test file
npm test -- Layout.test.tsx

# Using bun (calls Vitest via npm script)
bun run test
bun run test:coverage
```

### E2E Tests (Playwright)

```bash
# Run all E2E tests (headless)
npm run test:e2e

# Run E2E tests with browser visible
npm run test:e2e:headed

# Run E2E tests in debug mode
npm run test:e2e:debug

# View the HTML test report
npm run test:e2e:report

# Run a specific E2E test file
npx playwright test smoke.spec.ts

# Run tests with specific browser
npx playwright test --project=chromium
```

## Test Suite Scale

Measured 2026-09-22 by counting files and `it(`/`test(` declarations under `src/`:

| Area                            | Unit test files |
| ------------------------------- | --------------- |
| `components/`                   | 445             |
| `hooks/`                        | 227             |
| `services/`                     | 33              |
| `utils/`                        | 23              |
| `pages/`                        | 14              |
| `stores/`                       | 10              |
| other (`src/test`, `lib`, root) | 8               |
| **total**                       | **796**         |

Roughly 20,000 individual test cases live in those files. E2E adds 43 specs in
`tests/e2e/specs/`, 13 visual-regression specs in `tests/e2e/visual/`, and the
user-journey specs in `tests/e2e/specs/user-journeys/`.

Tests are co-located with their subject (`Foo.tsx` next to `Foo.test.tsx`);
there is no separate `__tests__` mirror tree except for shared fixtures.

## Coverage Floors

`vite.config.ts` declares the floors, and CI (`merge-shard-coverage.mjs
--enforce`, run only when every Vitest shard passed) enforces them on merged
shard data:

| Metric     | Floor |
| ---------- | ----- |
| statements | 80    |
| branches   | 74.6  |
| functions  | 78.4  |
| lines      | 80.9  |

These are **measured** values, not wish-values (R-1, WP2.3): the earlier
declared 83/77/81/84 sat above every observed run, so they could never fail a
build. Do not raise a floor without a measured run supporting it.

## Test Coverage

### Coverage Areas

Each test file covers:

- **Rendering**: Component renders without crashing
- **Content**: Expected text and elements are displayed
- **Interactions**: User clicks and navigation work correctly
- **Props**: Props are passed and handled correctly
- **Styling**: CSS classes are applied correctly
- **Accessibility**: Proper semantic HTML and ARIA attributes

### Representative Files

These are the entry-point tests for the app shell. Run
`npm run test:coverage` (or read the Vitest summary) for current per-file
counts — enumerating counts here goes stale on the next commit.

- `src/App.test.tsx` - root App renders inside its error boundaries
- `src/components/layout/Layout.test.tsx` - app shell: sidebar, header, content outlet
- `src/components/layout/Header.test.tsx` - branding, system status, GPU stats display
- `src/components/layout/Sidebar.test.tsx` - navigation items, active state, click handling
- `src/components/dashboard/DashboardPage.test.tsx` - dashboard widgets and their states

## Testing Best Practices

### Following React Testing Library Principles

1. **Query by Accessibility**: Use `getByRole`, `getByLabelText`, etc.
2. **Avoid Implementation Details**: Don't test internal state or methods
3. **Test User Behavior**: Focus on what users see and do
4. **Use `screen`**: Import queries from `screen` for better error messages
5. **User Events**: Use `userEvent` instead of `fireEvent` for realistic interactions

### Example Test Pattern

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import MyComponent from './MyComponent';

describe('MyComponent', () => {
  it('handles user interaction', async () => {
    const user = userEvent.setup();
    render(<MyComponent />);

    const button = screen.getByRole('button', { name: /click me/i });
    await user.click(button);

    expect(screen.getByText('Clicked!')).toBeInTheDocument();
  });
});
```

## Configuration

### Vite Config (`vite.config.ts`)

```typescript
test: {
  globals: true,
  environment: 'jsdom',
  setupFiles: './src/test/setup.ts',
  css: true,
}
```

### Test Setup (`src/test/setup.ts`)

- Extends Vitest's expect with jest-dom matchers
- Automatic cleanup after each test
- Global test utilities

## Troubleshooting

### Common Issues

1. **Module not found errors**: Run `npm install` to ensure all dependencies are installed

2. **Tests fail with CSS errors**: The `css: true` option in vite.config.ts should handle this

3. **Mock not working**: Ensure mocks are defined before the component import using `vi.mock()`

4. **Async tests timing out**: Use `await` with userEvent interactions and increase timeout if needed

## E2E Test Files

E2E tests are located in `tests/e2e/`:

### smoke.spec.ts

- Dashboard page loads successfully
- Dashboard displays key components (Risk Level, Camera Status, Live Activity)
- Dashboard shows real-time monitoring subtitle
- Dashboard has correct dark theme styling
- Header displays NVIDIA branding
- Sidebar navigation is visible

### navigation.spec.ts

- Can navigate to dashboard from root
- Can navigate to timeline page
- Can navigate to logs page
- Can navigate to settings page
- Sidebar navigation works for dashboard
- URL reflects current page
- Page transitions preserve layout

### realtime.spec.ts

- Dashboard shows disconnected state when WebSocket fails
- Activity feed shows empty state when no events
- Dashboard can handle simulated event injection
- Header shows system status indicator
- GPU stats display updates from API
- Dashboard shows error state when API fails

## E2E Test Configuration

E2E tests are configured in `playwright.config.ts`:

- **Test Directory**: `./tests/e2e`
- **Base URL**: `http://localhost:8444` (plain HTTP so self-signed dev certs don't break the run)
- **Projects**: `smoke`, `critical`, `visual-chromium`, `chromium`, `firefox`, `webkit`, `mobile-chrome` (Pixel 5), `mobile-safari` (iPhone 12), `tablet` (iPad gen 7)
- **Retries**: 2 in CI, 0 locally
- **Timeouts**: 15s per test, 3s expect, 5s action, 15s navigation (Firefox/WebKit get longer)
- **Artifacts**: Screenshots on failure, video on failure, trace on first retry
- **Web Server**: `npm run dev:e2e` starts automatically; it runs Vite **without the API proxy** so `page.route()` interception is not shadowed by a proxied request to `localhost:8000`
- **CI sharding**: Chromium runs across 3 shards (`--shard=1/3` .. `3/3`)

`tests/e2e/AGENTS.md` documents the fixtures, page objects, and utilities in
detail.

### API Mocking

E2E tests mock all backend API endpoints using Playwright's route interception:

```typescript
await page.route('**/api/cameras', async (route) => {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify([/* mock data */]),
  });
});
```

This ensures tests are reliable and don't require a running backend.

## What Already Exists Beyond These Basics

Older drafts of this file listed the items below as "future enhancements".
They shipped:

- **Visual regression** - `tests/e2e/visual/*.visual.spec.ts` with committed
  snapshot baselines, run under the `visual-chromium` project
- **Accessibility** - `tests/e2e/specs/accessibility.spec.ts` using
  `@axe-core/playwright` (skipped in CI for axe timing flakiness; run locally)
- **Mobile viewports** - `mobile-chrome`, `mobile-safari`, and `tablet` projects
- **WebSocket behaviour** - `tests/integration/websocket-*.test.ts` and the
  realtime E2E specs

## References

- [Vitest Documentation](https://vitest.dev/)
- [React Testing Library](https://testing-library.com/react)
- [Testing Library Best Practices](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)
- [Playwright Documentation](https://playwright.dev/docs/intro)
- [Playwright API Mocking](https://playwright.dev/docs/mock)

# Frontend E2E Tests Directory

## Purpose

End-to-end test suite using Playwright for full browser-based testing. Tests verify that the application renders correctly and responds to user interactions with mocked backend APIs.

## Directory Contents

```
frontend/tests/e2e/
├── AGENTS.md           # This documentation file
├── smoke.spec.ts       # Dashboard loading and component visibility tests
├── navigation.spec.ts  # Page navigation and routing tests
├── realtime.spec.ts    # Real-time updates and error handling tests
└── .gitkeep            # Git placeholder
```

## Test Files

### smoke.spec.ts

Dashboard smoke tests (2 test suites, 6 tests):

**Dashboard Smoke Tests:**

- `dashboard page loads successfully` - Verifies page loads with correct title
- `dashboard displays key components` - Checks Risk Level, Camera Status, Live Activity
- `dashboard shows real-time monitoring subtitle` - Verifies subtitle text
- `dashboard has correct page title` - Validates browser title

**Layout Smoke Tests:**

- `header displays branding` - Checks NVIDIA/SECURITY branding
- `sidebar navigation is visible` - Verifies sidebar presence

### navigation.spec.ts

Navigation tests (1 test suite, 6 tests):

- `can navigate to dashboard from root` - Default page is dashboard
- `can navigate to timeline page` - Timeline page loads
- `can navigate to logs page` - Logs page loads
- `can navigate to settings page` - Settings page loads
- `URL reflects current page` - URL changes with navigation
- `page transitions preserve layout` - Header/sidebar persist

### realtime.spec.ts

Real-time feature tests (3 test suites, 5 tests):

**Real-time Updates:**

- `dashboard shows disconnected state when WebSocket fails` - Disconnected indicator
- `activity feed shows empty state when no events` - Empty state message
- `dashboard displays GPU stats from API` - GPU utilization display

**Connection Status Indicators:**

- `header shows system status indicator` - System status in header

**Error Handling:**

- `dashboard shows error state when API fails` - Error page with reload button

## API Mocking Pattern

All tests mock backend endpoints using Playwright's `page.route()`:

```typescript
async function setupApiMocks(page: Page) {
  // Mock cameras endpoint
  await page.route('**/api/cameras', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ cameras: [...] }),
    });
  });

  // Mock WebSocket to simulate disconnection
  await page.route('**/ws/**', async (route) => {
    await route.abort('connectionfailed');
  });
}
```

**Mocked Endpoints:**

- `GET /api/cameras` - Camera list
- `GET /api/system/gpu` - GPU statistics
- `GET /api/system/health` - System health
- `GET /api/events*` - Events with pagination
- `GET /api/system/stats` - System statistics
- `GET /api/system/config` - System configuration
- `GET /api/logs` - Log entries
- `GET /api/logs/stats` - Log statistics
- `WS /ws/**` - WebSocket (aborted to test disconnection)

## Running E2E Tests

```bash
# From frontend/ directory
npm run test:e2e            # Run all E2E tests (headless)
npm run test:e2e:headed     # Run with browser visible
npm run test:e2e:debug      # Run in debug mode
npm run test:e2e:report     # View HTML report

# Run specific test file
npx playwright test smoke.spec.ts
npx playwright test navigation.spec.ts
npx playwright test realtime.spec.ts
```

## Playwright Configuration

From `frontend/playwright.config.ts`:

| Setting          | Value                     |
| ---------------- | ------------------------- |
| `testDir`        | `./tests/e2e`             |
| `baseURL`        | `http://localhost:5173`   |
| `browser`        | Chromium only             |
| `timeout`        | 30 seconds                |
| `expect.timeout` | 5 seconds                 |
| `retries`        | 2 (CI only)               |
| `workers`        | 1 (CI), unlimited (local) |

**Artifacts on Failure:**

- Screenshots saved to `test-results/`
- Traces collected on retry
- Videos retained on failure

## CI Integration

E2E tests run in GitHub Actions:

```yaml
- name: Install Playwright Chromium
  run: cd frontend && npx playwright install chromium --with-deps

- name: Run E2E tests
  run: cd frontend && npm run test:e2e
```

## Notes for AI Agents

- Tests use **mocked backend** - no real backend required
- Each test file has a `setupApiMocks()` function in `beforeEach`
- WebSocket connections are aborted to test disconnection handling
- Use `timeout: 15000` for initial page loads
- Tests verify **UI behavior**, not implementation details
- Response shapes must match actual API schemas
- E2E tests are excluded from Vitest via `vite.config.ts`
- Some tests are marked `test.skip` due to CI ECONNREFUSED issues

## Entry Points

1. **smoke.spec.ts** - Start here for basic page loading tests
2. **navigation.spec.ts** - Page routing and transitions
3. **realtime.spec.ts** - WebSocket and real-time features
4. **Mock pattern**: Look at `setupApiMocks()` in any test file

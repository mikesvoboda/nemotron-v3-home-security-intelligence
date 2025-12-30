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

**Dashboard Smoke Tests (4 tests):**

- `dashboard page loads successfully` - Verifies page loads with correct title
- `dashboard displays key components` - Checks Current Risk Level, Camera Status, Live Activity sections
- `dashboard shows real-time monitoring subtitle` - Verifies "Real-time AI-powered home security monitoring" text
- `dashboard has correct page title` - Validates browser title contains "Home Security"

**Layout Smoke Tests (2 tests):**

- `header displays branding` - Checks NVIDIA/SECURITY branding in header
- `sidebar navigation is visible` - Verifies aside element is present

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

**Real-time Updates (3 tests):**

- `dashboard shows disconnected state when WebSocket fails` - Checks "(Disconnected)" text appears
- `activity feed shows empty state when no events` - Verifies "No activity" message in Live Activity section
- `dashboard displays GPU stats from API` - Checks "Utilization" text is visible

**Connection Status Indicators (1 test):**

- `header shows system status indicator` - Verifies "System" text in header

**Error Handling (1 test):**

- `dashboard shows error state when API fails` - Checks "Error Loading Dashboard" heading and "Reload Page" button

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

- `GET /api/cameras/*/snapshot*` - Camera snapshot images (transparent PNG)
- `GET /api/cameras` - Camera list with status
- `GET /api/system/gpu/history*` - GPU history samples (must be registered before /api/system/gpu)
- `GET /api/system/gpu` - Current GPU statistics
- `GET /api/system/health` - System health status
- `GET /api/health` - Basic health check
- `GET /api/events/stats*` - Event statistics (must be registered before /api/events)
- `GET /api/events*` - Events with pagination
- `GET /api/system/stats` - System statistics
- `GET /api/system/config` - System configuration
- `GET /api/logs/stats` - Log statistics (must be registered before /api/logs)
- `GET /api/logs*` - Log entries
- `WS /ws/**` - WebSocket (aborted to test disconnection)

**Important:** Route handlers are matched in registration order. More specific routes must be registered BEFORE more general routes (e.g., `/api/system/gpu/history` before `/api/system/gpu`).

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

| Setting             | Value                     |
| ------------------- | ------------------------- |
| `testDir`           | `./tests/e2e`             |
| `baseURL`           | `http://localhost:5173`   |
| `browser`           | Chromium only             |
| `timeout`           | 30 seconds                |
| `expect.timeout`    | 5 seconds                 |
| `navigationTimeout` | 10 seconds                |
| `retries`           | 2 (CI only)               |
| `workers`           | 1 (CI), unlimited (local) |
| `fullyParallel`     | true                      |
| `webServer.command` | `npm run dev:e2e`         |
| `webServer.timeout` | 120 seconds               |

**Artifacts on Failure:**

- Screenshots saved to `test-results/`
- Traces collected on first retry
- Videos retained on failure

**Web Server:** Uses `npm run dev:e2e` which runs Vite without API proxy, allowing Playwright's `page.route()` to intercept API requests directly.

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
- **Route registration order matters** - more specific routes must be registered first
- WebSocket connections are aborted to test disconnection handling
- Use `timeout: 15000` for initial page loads in `expect()` calls
- Tests verify **UI behavior**, not implementation details
- Response shapes must match actual API schemas
- E2E tests are excluded from Vitest via `vite.config.ts` exclude pattern
- Camera snapshots return a transparent 1x1 PNG to avoid missing image errors

## Entry Points

1. **smoke.spec.ts** - Start here for basic page loading tests
2. **navigation.spec.ts** - Page routing and transitions
3. **realtime.spec.ts** - WebSocket and real-time features
4. **Mock pattern**: Look at `setupApiMocks()` in any test file

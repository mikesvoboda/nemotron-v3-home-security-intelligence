# Frontend E2E Tests Directory

## Purpose

End-to-end test suite for full user workflows using a real browser environment. E2E tests verify the application UI renders correctly and responds to user interactions.

## Current Status

**Status**: Implemented (Phase 8)

This directory contains minimal Playwright smoke tests for the Home Security Dashboard.

## Directory Contents

```
frontend/tests/e2e/
├── smoke.spec.ts      # Dashboard loading and component visibility tests
├── navigation.spec.ts # Page navigation and routing tests
├── realtime.spec.ts   # Real-time updates and WebSocket tests
├── AGENTS.md          # This documentation file
└── .gitkeep           # Placeholder file to maintain directory in git
```

## Test Files

### smoke.spec.ts

Dashboard smoke tests that verify:
- Dashboard page loads successfully
- Dashboard displays key components (Risk Level, Camera Status, Live Activity)
- Dashboard shows real-time monitoring subtitle
- Dashboard has correct dark theme styling
- Header displays NVIDIA branding
- Sidebar navigation is visible

### navigation.spec.ts

Navigation tests that verify:
- Can navigate to dashboard from root
- Can navigate to timeline page
- Can navigate to logs page
- Can navigate to settings page
- Sidebar navigation works
- URL reflects current page
- Page transitions preserve layout

### realtime.spec.ts

Real-time feature tests that verify:
- Dashboard shows disconnected state when WebSocket fails
- Activity feed shows empty state when no events
- System status indicator is visible
- GPU stats display updates from API
- Dashboard shows error state when API fails

## E2E Framework

**Playwright** is used for E2E testing with the following configuration:

- **Browser**: Chromium only (for minimal smoke tests)
- **Mode**: Headless in CI, headed locally (optional)
- **API Mocking**: All backend endpoints are mocked using route interception
- **Web Server**: Dev server auto-starts before tests

## Running Tests

```bash
# Run all E2E tests (headless)
npm run test:e2e

# Run E2E tests with browser visible
npm run test:e2e:headed

# Run E2E tests in debug mode
npm run test:e2e:debug

# View the HTML test report
npm run test:e2e:report

# Run a specific test file
npx playwright test smoke.spec.ts
```

## Configuration

The Playwright configuration is in `frontend/playwright.config.ts`:

```typescript
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
});
```

## API Mocking Pattern

All tests mock backend API endpoints using Playwright's route interception:

```typescript
test.beforeEach(async ({ page }) => {
  // Mock the cameras endpoint
  await page.route('**/api/cameras', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'cam-1',
          name: 'Front Door',
          folder_path: '/export/foscam/front_door',
          status: 'online',
          created_at: new Date().toISOString(),
          last_seen_at: new Date().toISOString(),
        },
      ]),
    });
  });

  // Mock WebSocket connections to prevent errors
  await page.route('**/ws/**', async (route) => {
    await route.abort('connectionfailed');
  });
});
```

This approach:
- Makes tests reliable and independent of backend state
- Allows testing error scenarios (API failures, disconnections)
- Runs faster without needing a real backend

## CI Integration

E2E tests run in GitHub Actions CI:

```yaml
frontend-e2e:
  name: Frontend E2E Tests (Playwright)
  runs-on: ubuntu-latest
  steps:
    - name: Checkout
      uses: actions/checkout@v4

    - name: Set up Node.js
      uses: actions/setup-node@v4
      with:
        node-version: '20'
        cache: 'npm'
        cache-dependency-path: frontend/package-lock.json

    - name: Install dependencies
      run: cd frontend && npm ci

    - name: Install Playwright Chromium
      run: cd frontend && npx playwright install chromium --with-deps

    - name: Run E2E tests
      run: cd frontend && npm run test:e2e

    - name: Upload Playwright report
      if: always()
      uses: actions/upload-artifact@v4
      with:
        name: playwright-report
        path: frontend/playwright-report/
        retention-days: 7
```

## Best Practices

1. **Mock all backend endpoints**: Ensures tests are reliable and fast
2. **Use semantic queries**: `getByRole`, `getByText` for accessibility-friendly selectors
3. **Wait for conditions**: Use `toBeVisible()` with timeout instead of hard-coded waits
4. **Test isolation**: Each test should be independent
5. **Screenshots on failure**: Automatic via Playwright config
6. **Keep tests minimal**: Focus on smoke tests, not comprehensive coverage

## Test Output

- **Console output**: Test results during run
- **HTML report**: `frontend/playwright-report/` (view with `npm run test:e2e:report`)
- **Test artifacts**: `frontend/test-results/` (screenshots, videos, traces on failure)

## Notes for AI Agents

- E2E tests use **mocked backend** - no real backend required
- Tests verify **UI behavior**, not implementation details
- All API mocking is done in `test.beforeEach` hooks
- WebSocket connections are aborted to test disconnection handling
- Focus is on **smoke testing** critical paths
- Tests should pass in under 60 seconds total

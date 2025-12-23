# Frontend E2E Tests Directory

## Purpose

End-to-end test suite for full user workflows using a real browser environment.

## Current Status

Directory contains only `.gitkeep` file. E2E tests are planned but not yet implemented.

## Planned E2E Framework

### Options

- **Playwright** (recommended): Multi-browser, fast, reliable
- **Cypress**: Developer-friendly, time-travel debugging
- **Puppeteer**: Chrome-focused, lightweight

### Recommended: Playwright

```bash
npm install -D @playwright/test
npx playwright install
```

## Planned Test Structure

```
frontend/tests/e2e/
├── fixtures/              # Page objects and helpers
│   ├── pages/
│   │   ├── DashboardPage.ts
│   │   ├── CameraPage.ts
│   │   └── EventsPage.ts
│   └── api/
│       └── mockServer.ts
├── specs/                 # Test specifications
│   ├── dashboard.spec.ts
│   ├── cameras.spec.ts
│   ├── events.spec.ts
│   └── websocket.spec.ts
├── playwright.config.ts   # Playwright configuration
└── AGENTS.md             # This file
```

## Planned Test Scenarios

### Dashboard Workflow

```typescript
// specs/dashboard.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Dashboard', () => {
  test('displays system status on load', async ({ page }) => {
    await page.goto('/');

    // System health visible
    await expect(page.getByText('System Status')).toBeVisible();

    // Camera grid visible
    await expect(page.getByRole('heading', { name: /cameras/i })).toBeVisible();

    // Risk gauge visible
    await expect(page.getByText(/risk level/i)).toBeVisible();
  });

  test('updates risk score in real-time', async ({ page }) => {
    await page.goto('/');

    // Mock WebSocket message
    await page.evaluate(() => {
      window.dispatchEvent(
        new MessageEvent('message', {
          data: JSON.stringify({
            id: 'evt-1',
            risk_score: 85,
            risk_level: 'critical',
            summary: 'Intrusion detected',
          }),
        })
      );
    });

    // Risk score updates
    await expect(page.getByText('85')).toBeVisible();
    await expect(page.getByText('Critical')).toBeVisible();
  });
});
```

### Camera Management

```typescript
// specs/cameras.spec.ts
test.describe('Camera Management', () => {
  test('creates new camera', async ({ page }) => {
    await page.goto('/cameras');
    await page.click('button:has-text("Add Camera")');

    await page.fill('input[name="name"]', 'Back Yard');
    await page.fill('input[name="folder_path"]', '/export/foscam/back_yard');
    await page.click('button:has-text("Save")');

    await expect(page.getByText('Back Yard')).toBeVisible();
  });

  test('deletes camera', async ({ page }) => {
    await page.goto('/cameras');
    await page.click('[data-testid="camera-1-menu"]');
    await page.click('text=Delete');
    await page.click('button:has-text("Confirm")');

    await expect(page.getByText('Front Door')).not.toBeVisible();
  });
});
```

### Event Timeline

```typescript
// specs/events.spec.ts
test.describe('Event Timeline', () => {
  test('filters events by risk level', async ({ page }) => {
    await page.goto('/events');

    // Select high risk filter
    await page.selectOption('select[name="risk_filter"]', 'high');

    // Only high-risk events visible
    await expect(page.getByText('High')).toHaveCount(5);
    await expect(page.getByText('Low')).not.toBeVisible();
  });

  test('opens event detail modal', async ({ page }) => {
    await page.goto('/events');
    await page.click('[data-testid="event-evt-1"]');

    // Modal visible with details
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByText('Detection Details')).toBeVisible();
    await expect(page.getByText('Risk Score: 75')).toBeVisible();
  });
});
```

### WebSocket Connection

```typescript
// specs/websocket.spec.ts
test.describe('Real-time Updates', () => {
  test('maintains WebSocket connection', async ({ page }) => {
    await page.goto('/');

    // Connection indicator shows connected
    await expect(page.getByTestId('ws-status')).toHaveClass(/connected/);

    // Receives live events
    await page.waitForSelector('[data-testid="live-event"]', { timeout: 30000 });
  });

  test('reconnects after disconnect', async ({ page }) => {
    await page.goto('/');

    // Simulate disconnect
    await page.evaluate(() => {
      // Close WebSocket connection
      window.dispatchEvent(new Event('offline'));
    });

    await expect(page.getByTestId('ws-status')).toHaveClass(/disconnected/);

    // Auto-reconnects
    await page.waitForTimeout(3000);
    await expect(page.getByTestId('ws-status')).toHaveClass(/connected/);
  });
});
```

## Page Object Pattern

```typescript
// fixtures/pages/DashboardPage.ts
export class DashboardPage {
  constructor(private page: Page) {}

  async goto() {
    await this.page.goto('/');
  }

  async waitForLoad() {
    await this.page.waitForSelector('[data-testid="dashboard"]');
  }

  async getRiskScore() {
    const text = await this.page.textContent('[data-testid="risk-score"]');
    return parseInt(text || '0', 10);
  }

  async getCameraCount() {
    return await this.page.locator('[data-testid="camera-card"]').count();
  }

  async clickCamera(name: string) {
    await this.page.click(`[data-testid="camera-${name}"]`);
  }
}

// Usage in test
test('dashboard displays cameras', async ({ page }) => {
  const dashboard = new DashboardPage(page);
  await dashboard.goto();
  await dashboard.waitForLoad();

  const count = await dashboard.getCameraCount();
  expect(count).toBeGreaterThan(0);
});
```

## Configuration

```typescript
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test';

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
  },

  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  ],

  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
  },
});
```

## Running E2E Tests

```bash
# Run all tests
npx playwright test

# Run specific test file
npx playwright test dashboard.spec.ts

# Run in headed mode (see browser)
npx playwright test --headed

# Run in debug mode
npx playwright test --debug

# Run specific browser
npx playwright test --project=chromium

# Generate code (record actions)
npx playwright codegen http://localhost:5173
```

## Best Practices

1. **Use data-testid attributes**: Stable selectors immune to style changes
2. **Page Object Pattern**: Encapsulate page interactions
3. **Wait for conditions**: Use `waitFor*` methods, avoid fixed timeouts
4. **Test isolation**: Each test should be independent
5. **Mock external APIs**: Use MSW or Playwright's route interception
6. **Screenshots on failure**: Automatic in config above
7. **Parallel execution**: Speeds up test runs

## Notes

- E2E tests require backend server running
- Tests should work with both development and production builds
- Use `test.beforeEach` for common setup (login, navigation)
- CI/CD should run E2E tests before deployment
- Consider visual regression testing with Playwright's screenshot comparison

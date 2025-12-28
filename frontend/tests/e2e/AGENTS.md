# Frontend E2E Tests Directory

## Purpose

End-to-end test suite for full user workflows using a real browser environment. E2E tests verify the entire application stack from frontend to backend, including real API calls, WebSocket connections, and database interactions.

## Current Status

**Status**: Planned (Phase 8)

Directory currently contains:

- `.gitkeep` - Placeholder file to maintain directory in git
- `AGENTS.md` - This documentation file

E2E tests will be implemented in **Phase 8 (Integration & E2E)** of the project roadmap.

### Prerequisites

1. All Phase 1-7 tasks complete
2. Backend API fully operational
3. WebSocket channels working
4. Database with test data available

## Recommended Framework: Playwright

```bash
npm install -D @playwright/test
npx playwright install
```

### Why Playwright

- Multi-browser support (Chromium, Firefox, WebKit)
- Fast and reliable execution
- Built-in test isolation
- Screenshot and video on failure
- Network interception
- Mobile viewport testing

## Planned Structure

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

    await expect(page.getByText('System Status')).toBeVisible();
    await expect(page.getByRole('heading', { name: /cameras/i })).toBeVisible();
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

    await page.selectOption('select[name="risk_filter"]', 'high');

    await expect(page.getByText('High')).toHaveCount(5);
    await expect(page.getByText('Low')).not.toBeVisible();
  });

  test('opens event detail modal', async ({ page }) => {
    await page.goto('/events');
    await page.click('[data-testid="event-evt-1"]');

    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByText('Detection Details')).toBeVisible();
  });
});
```

### WebSocket Connection

```typescript
// specs/websocket.spec.ts
test.describe('Real-time Updates', () => {
  test('maintains WebSocket connection', async ({ page }) => {
    await page.goto('/');

    await expect(page.getByTestId('ws-status')).toHaveClass(/connected/);
    await page.waitForSelector('[data-testid="live-event"]', { timeout: 30000 });
  });

  test('reconnects after disconnect', async ({ page }) => {
    await page.goto('/');

    await page.evaluate(() => {
      window.dispatchEvent(new Event('offline'));
    });

    await expect(page.getByTestId('ws-status')).toHaveClass(/disconnected/);
    await page.waitForTimeout(3000);
    await expect(page.getByTestId('ws-status')).toHaveClass(/connected/);
  });
});
```

## Page Object Pattern

```typescript
// fixtures/pages/DashboardPage.ts
import { Page } from '@playwright/test';

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
// playwright.config.ts (place in frontend root)
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e/specs',
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
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  ],

  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
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

# View test report
npx playwright show-report
```

## Best Practices

### Selectors

1. **Use data-testid** - Stable selectors immune to style changes
2. **Use semantic queries** - `getByRole`, `getByLabel` for accessibility
3. **Avoid CSS selectors** - Fragile, break with style changes

```typescript
// Good
await page.getByRole('button', { name: 'Submit' });
await page.getByTestId('camera-card');

// Avoid
await page.click('.btn-primary');
await page.click('#submit-button');
```

### Assertions

```typescript
// Use web-first assertions (auto-wait)
await expect(page.getByText('Success')).toBeVisible();

// NOT
const text = await page.textContent('.message');
expect(text).toBe('Success');
```

### Test Isolation

```typescript
test.beforeEach(async ({ page }) => {
  // Reset to known state
  await page.goto('/');
});

test.afterEach(async ({ page }) => {
  // Cleanup if needed
});
```

## Prerequisites for E2E Tests

### Backend Setup

- FastAPI backend on port 8000
- SQLite database initialized
- Redis for WebSocket support and caching

### Test Data

- Sample cameras (matching `/export/foscam/{camera_name}/` structure)
- Sample events with various risk levels (low, medium, high, critical)
- Known detection patterns from RT-DETRv2

### Environment Variables

- `VITE_API_BASE_URL` (defaults to empty for proxy mode)
- Backend configured for test mode

### Docker Services

```bash
docker-compose up -d backend redis
```

## Integration with CI/CD

```yaml
# .github/workflows/test.yml
- name: Install Playwright
  run: npx playwright install --with-deps

- name: Start backend
  run: docker-compose up -d backend redis

- name: Run E2E tests
  run: npm run test:e2e

- name: Upload test results
  if: always()
  uses: actions/upload-artifact@v3
  with:
    name: playwright-report
    path: playwright-report/
```

## Related Files

- `/frontend/tests/AGENTS.md` - Tests directory overview
- `/frontend/src/test/AGENTS.md` - Unit test setup
- `/frontend/vite.config.ts` - Vitest configuration

## Notes for AI Agents

- E2E tests require **full system setup** (frontend + backend + database + Redis)
- Tests verify **user workflows**, not implementation details
- Use **Page Object Pattern** to avoid duplication and improve maintainability
- E2E tests are **slower** than unit/integration tests - use sparingly for critical paths
- Focus on **happy paths** and **critical error scenarios**
- Consider **visual regression testing** with Playwright's screenshot comparison
- E2E tests should work with both development and production builds
- Use `test.beforeEach` for common setup (navigation, authentication)
- Backend server should be in "test mode" to avoid side effects
- Add `data-testid` attributes to components that need E2E testing

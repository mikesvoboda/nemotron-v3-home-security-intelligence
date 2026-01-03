# E2E Test Specs Directory

## Purpose

Playwright test specification files that verify end-to-end application behavior. Each spec file focuses on a specific feature area or page, using fixtures for mock data and page objects for DOM interactions.

## Test Files

| File                     | Tests | Focus Area                       |
| ------------------------ | ----- | -------------------------------- |
| `smoke.spec.ts`          | 14    | Basic loading and visibility     |
| `dashboard.spec.ts`      | 22    | Dashboard components and states  |
| `navigation.spec.ts`     | 10    | Route navigation and transitions |
| `realtime.spec.ts`       | 8     | WebSocket and live updates       |
| `events.spec.ts`         | 16    | Event timeline and details       |
| `alerts.spec.ts`         | 12    | Alert management and filtering   |
| `entities.spec.ts`       | 8     | Entity tracking                  |
| `logs.spec.ts`           | 14    | Application logs viewer          |
| `audit.spec.ts`          | 12    | Audit log viewer                 |
| `system.spec.ts`         | 18    | System monitoring panels         |
| `settings.spec.ts`       | 10    | Application settings             |
| `responsive.spec.ts`     | 20    | Mobile/tablet viewports          |
| `error-handling.spec.ts` | 14    | Error states and recovery        |

## Test Structure Pattern

All spec files follow a consistent pattern:

```typescript
import { test, expect } from '@playwright/test';
import { DashboardPage } from '../pages';
import { setupApiMocks, defaultMockConfig, emptyMockConfig } from '../fixtures';

test.describe('Feature Area', () => {
  let page: DashboardPage;

  test.beforeEach(async ({ page: playwrightPage }) => {
    await setupApiMocks(playwrightPage, defaultMockConfig);
    page = new DashboardPage(playwrightPage);
  });

  test('specific behavior', async () => {
    await page.goto();
    await page.waitForDashboardLoad();
    await expect(page.someElement).toBeVisible();
  });
});

// Tests with different mock config
test.describe('Empty State', () => {
  let page: DashboardPage;

  test.beforeEach(async ({ page: playwrightPage }) => {
    await setupApiMocks(playwrightPage, emptyMockConfig);
    page = new DashboardPage(playwrightPage);
  });

  test('shows empty message', async () => {
    await page.goto();
    await expect(page.noDataMessage).toBeVisible();
  });
});
```

## Spec File Details

### smoke.spec.ts

Basic application loading tests:

- Dashboard page loads successfully
- Page title is correct
- Key sections are visible (Risk Gauge, Camera Status, Live Activity)
- Layout elements present (header, sidebar)
- NVIDIA branding visible

### dashboard.spec.ts

Dashboard component tests:

- Stats row displays all metrics
- Risk gauge section visible
- Camera grid shows all cameras
- Activity feed displays events
- Empty state handling
- Error state with reload button
- High alert state styling

### navigation.spec.ts

Route navigation tests:

- Navigate to each page via sidebar
- URL reflects current page
- Layout persists across navigation
- Back/forward browser navigation
- Direct URL access

### realtime.spec.ts

Real-time update tests:

- Disconnected state indicator
- Activity feed updates (simulated)
- GPU stats live updates
- Camera status changes
- System alert notifications

### events.spec.ts

Event timeline tests:

- Event list rendering
- Risk level filtering
- Event detail modal
- Thumbnail strip display
- Event search
- Export panel functionality

### alerts.spec.ts

Alert management tests:

- Alert list with filtering
- Risk level badge colors
- Alert statistics display
- Alert detail modal
- Alert acknowledgment
- High-risk alert highlighting

### entities.spec.ts

Entity tracking tests:

- Entity grid display
- Entity filtering
- Entity detail modal
- Empty state handling

### logs.spec.ts

Application logs tests:

- Log table rendering
- Log level filtering
- Log search
- Time range selection
- Log statistics cards
- Log detail modal
- Log export

### audit.spec.ts

Audit log tests:

- Audit table rendering
- Action type filtering
- Resource type filtering
- Audit statistics
- Audit detail modal
- Actor filtering

### system.spec.ts

System monitoring tests:

- GPU stats panel
- AI models panel
- Database status panel
- Host system metrics
- Container status
- Worker status panel
- Performance alerts display
- Time range selector

### settings.spec.ts

Settings page tests:

- Tab navigation
- Camera settings section
- AI models settings
- Processing settings
- Notification settings
- Storage dashboard
- DLQ monitor

### responsive.spec.ts

Responsive design tests:

- Mobile viewport (375x667)
- Tablet viewport (768x1024)
- Sidebar collapse behavior
- Header mobile menu
- Grid layout changes
- Touch-friendly targets

### error-handling.spec.ts

Error state tests:

- API failure handling
- Network error recovery
- Error boundary display
- Reload functionality
- Partial data loading
- Graceful degradation

## Mock Configurations

Tests use different mock configs for different scenarios:

| Config                | Use Case                          |
| --------------------- | --------------------------------- |
| `defaultMockConfig`   | Normal happy path testing         |
| `emptyMockConfig`     | Empty state / no data scenarios   |
| `errorMockConfig`     | API failure / error state testing |
| `highAlertMockConfig` | High-risk alert state testing     |

## Running Specific Tests

```bash
# Run all tests in a spec file
npx playwright test specs/dashboard.spec.ts

# Run tests matching a name pattern
npx playwright test -g "camera grid"

# Run tests with specific tag
npx playwright test --grep "@smoke"

# Run in headed mode for debugging
npx playwright test specs/dashboard.spec.ts --headed

# Run with trace enabled
npx playwright test specs/dashboard.spec.ts --trace on
```

## Test Organization

### Describe Blocks

Each spec file is organized into logical describe blocks:

```typescript
test.describe('Dashboard Stats Row', () => {
  /* stats tests */
});
test.describe('Dashboard Risk Gauge', () => {
  /* risk gauge tests */
});
test.describe('Dashboard Camera Grid', () => {
  /* camera tests */
});
test.describe('Dashboard Activity Feed', () => {
  /* activity tests */
});
test.describe('Dashboard Empty State', () => {
  /* empty state tests */
});
test.describe('Dashboard Error State', () => {
  /* error tests */
});
```

### Test Naming

Tests use descriptive names that read like sentences:

- `dashboard page loads successfully`
- `displays active cameras stat`
- `shows no activity message when no events`
- `shows error heading when API fails`

## Best Practices

1. **One assertion per test** (when practical)
2. **Descriptive test names** that explain the expected behavior
3. **Independent tests** - each test sets up its own state
4. **Appropriate timeouts** - use 15000ms for initial loads in CI
5. **Page objects** - never use raw selectors in specs
6. **Mock configs** - use appropriate config for each scenario

## Notes for AI Agents

- Each describe block has its own `beforeEach` with mock setup
- Use page object methods, not raw Playwright selectors
- Tests verify UI behavior, not implementation details
- Response timing varies - use appropriate waits
- Some tests may need longer timeouts in CI (use 15000ms)
- Error state tests need time for API retries to fail

## Entry Points

1. **Start here**: `smoke.spec.ts` - Simplest test patterns
2. **Comprehensive**: `dashboard.spec.ts` - Multiple scenarios
3. **State testing**: `error-handling.spec.ts` - Error states
4. **Viewports**: `responsive.spec.ts` - Responsive testing

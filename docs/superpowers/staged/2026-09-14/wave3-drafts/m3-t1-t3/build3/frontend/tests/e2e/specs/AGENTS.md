# E2E Test Specs Directory

## Purpose

Playwright test specification files that verify end-to-end application behavior. Each spec file focuses on a specific feature area or page, using fixtures for mock data and page objects for DOM interactions.

## Test Files

| File                           | Focus Area                                    |
| ------------------------------ | --------------------------------------------- |
| `accessibility.spec.ts`        | WCAG 2.1 AA compliance testing                |
| `ai-audit.spec.ts`             | AI pipeline audit page                        |
| `ai-error-handling.spec.ts`    | AI-specific error handling scenarios          |
| `ai-performance.spec.ts`       | AI performance metrics and monitoring         |
| `alert-rules.spec.ts`          | Alert rule configuration and management       |
| `alerts.spec.ts`               | Alert management and filtering                |
| `alerts-workflow.spec.ts`      | Alert workflow end-to-end scenarios           |
| `analytics-advanced.spec.ts`   | Advanced analytics features                   |
| `analytics.spec.ts`            | Analytics page and charts                     |
| `audit.spec.ts`                | Audit log viewer                              |
| `batch-operations.spec.ts`     | Batch operations and bulk actions             |
| `calibration.spec.ts`          | Camera calibration features                   |
| `concurrent-operations.spec.ts`| Concurrent operation handling                 |
| `dashboard.spec.ts`            | Dashboard components and states               |
| `entities.spec.ts`             | Entity tracking                               |
| `entity-trust.spec.ts`         | Entity trust and verification features        |
| `error-handling.spec.ts`       | Error states and recovery                     |
| `event-detail.spec.ts`         | Event detail modal and interactions           |
| `event-export.spec.ts`         | Event export functionality                    |
| `events.spec.ts`               | Event timeline and details                    |
| `feedback.spec.ts`             | User feedback system                          |
| `forms-validation.spec.ts`     | Form validation across the application        |
| `jobs.spec.ts`                 | Background jobs monitoring                    |
| `logs.spec.ts`                 | Application logs viewer                       |
| `mobile-optimization.spec.ts`  | Mobile-specific optimizations                 |
| `navigation.spec.ts`           | Route navigation and transitions              |
| `network-conditions.spec.ts`   | Network condition simulation tests            |
| `performance.spec.ts`          | Performance metrics and monitoring            |
| `realtime.spec.ts`             | WebSocket and live updates                    |
| `realtime-updates.spec.ts`     | Real-time update scenarios                    |
| `responsive.spec.ts`           | Mobile/tablet viewports                       |
| `retry-isolation.spec.ts`      | Retry mechanism isolation tests               |
| `settings.spec.ts`             | Application settings                          |
| `smoke.spec.ts`                | Basic loading and visibility                  |
| `system.spec.ts`               | System monitoring panels                      |
| `test-tagging.spec.ts`         | Test tagging demonstration                    |
| `trash.spec.ts`                | Trash/deleted items management                |
| `user-journeys/`               | User journey test subdirectory                |
| `utils-demo.spec.ts`           | Utility demonstration tests                   |
| `video-playback.spec.ts`       | Video playback features                       |
| `websocket.spec.ts`            | WebSocket connection tests                    |
| `zones.spec.ts`                | Camera zone configuration                     |

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

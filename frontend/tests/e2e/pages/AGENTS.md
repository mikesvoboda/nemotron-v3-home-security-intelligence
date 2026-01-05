# E2E Page Objects Directory

## Purpose

Page Object Model (POM) classes that encapsulate page selectors and interactions for E2E tests. Page objects provide a maintainable abstraction layer between tests and the DOM, making tests more readable and easier to maintain when UI changes.

## Key Files

| File               | Purpose                                 |
| ------------------ | --------------------------------------- |
| `index.ts`         | Central exports for all page objects    |
| `BasePage.ts`      | Base class with common layout selectors |
| `DashboardPage.ts` | Main dashboard page selectors/actions   |
| `TimelinePage.ts`  | Event timeline page                     |
| `AlertsPage.ts`    | Alerts management page                  |
| `AlertRulesPage.ts`| Alert rules configuration page          |
| `EntitiesPage.ts`  | Entity tracking page                    |
| `LogsPage.ts`      | Application logs page                   |
| `AuditPage.ts`     | Audit log viewer page                   |
| `AIAuditPage.ts`   | AI pipeline audit page                  |
| `SystemPage.ts`    | System monitoring page                  |
| `SettingsPage.ts`  | Application settings page               |
| `ZonesPage.ts`     | Camera zone configuration page          |

## BasePage - Base Class

All page objects extend `BasePage`, which provides common layout elements and utilities:

### Common Selectors

```typescript
// Layout elements
readonly header: Locator;          // <header> element
readonly sidebar: Locator;         // <aside> element
readonly mainContent: Locator;     // <main> element

// Header elements
readonly brandingLogo: Locator;
readonly systemStatusIndicator: Locator;

// Navigation links
readonly navDashboard: Locator;
readonly navTimeline: Locator;
readonly navAlerts: Locator;
readonly navEntities: Locator;
readonly navLogs: Locator;
readonly navAudit: Locator;
readonly navSystem: Locator;
readonly navSettings: Locator;
```

### Common Methods

| Method                       | Description                           |
| ---------------------------- | ------------------------------------- |
| `goto(path)`                 | Navigate to a URL path                |
| `waitForPageLoad()`          | Wait for networkidle state            |
| `expectHeaderVisible()`      | Assert header is visible              |
| `expectSidebarVisible()`     | Assert sidebar is visible             |
| `expectLayoutLoaded()`       | Assert full layout is rendered        |
| `navigateToDashboard()`      | Navigate to dashboard                 |
| `navigateToTimeline()`       | Navigate to timeline                  |
| `navigateToAlerts()`         | Navigate to alerts                    |
| `navigateToEntities()`       | Navigate to entities                  |
| `navigateToLogs()`           | Navigate to logs                      |
| `navigateToAudit()`          | Navigate to audit                     |
| `navigateToSystem()`         | Navigate to system                    |
| `navigateToSettings()`       | Navigate to settings                  |
| `getCurrentPath()`           | Get current URL pathname              |
| `waitForHeading(text)`       | Wait for heading with text            |
| `waitForLoadingComplete()`   | Wait for loading indicators to clear  |
| `isDisconnected()`           | Check if disconnected indicator shown |
| `clickButton(name)`          | Click button by accessible name       |
| `fillInput(label, value)`    | Fill input by label                   |
| `selectOption(label, value)` | Select dropdown option                |
| `hasText(text)`              | Check if text is visible              |
| `waitForText(text)`          | Wait for text to appear               |
| `screenshot(name)`           | Take screenshot for debugging         |

## DashboardPage

Page object for the main dashboard (`/`):

### Selectors

```typescript
// Page heading
readonly pageTitle: Locator;         // "Security Dashboard"
readonly pageSubtitle: Locator;      // "Real-time AI-powered..."

// Stats Row
readonly statsRow: Locator;
readonly activeCamerasStat: Locator;
readonly eventsTodayStat: Locator;
readonly riskScoreStat: Locator;
readonly systemStatusStat: Locator;

// Risk Gauge Section
readonly riskGaugeSection: Locator;
readonly riskGaugeHeading: Locator;  // "Current Risk Level"
readonly riskGauge: Locator;

// Camera Grid Section
readonly cameraGridSection: Locator;
readonly cameraGridHeading: Locator; // "Camera Status"
readonly cameraCards: Locator;

// Activity Feed Section
readonly activityFeedSection: Locator;
readonly activityFeedHeading: Locator; // "Live Activity"
readonly activityItems: Locator;
readonly noActivityMessage: Locator;

// Error State
readonly errorContainer: Locator;
readonly errorHeading: Locator;      // "Error Loading Dashboard"
readonly reloadButton: Locator;

// Loading State
readonly loadingSkeleton: Locator;

// Disconnected Indicator
readonly disconnectedIndicator: Locator;
```

### Methods

| Method                       | Description                        |
| ---------------------------- | ---------------------------------- |
| `goto()`                     | Navigate to dashboard              |
| `waitForDashboardLoad()`     | Wait for dashboard content         |
| `isLoading()`                | Check if loading skeleton visible  |
| `isInErrorState()`           | Check if error state visible       |
| `clickReload()`              | Click reload button in error state |
| `expectAllSectionsVisible()` | Verify all sections visible        |
| `getCameraCount()`           | Get number of camera cards         |
| `getActivityItemCount()`     | Get number of activity items       |
| `hasNoActivityMessage()`     | Check for empty state message      |
| `expectDisconnected()`       | Assert disconnected indicator      |
| `clickCamera(name)`          | Click camera by name               |
| `clickActivityItem(index)`   | Click activity item by index       |
| `hasCameraByName(name)`      | Check if camera name visible       |
| `getRiskScoreText()`         | Get risk score display text        |
| `expectGpuStatsVisible()`    | Verify GPU stats section           |
| `expectHeaderVisible()`      | Verify header with navigation      |

## Other Page Objects

### TimelinePage

- Event list with filtering
- Event detail modal
- Export panel

### AlertsPage

- Alert list with risk level filtering
- Alert statistics cards
- Alert detail modal
- Alert acknowledgment actions

### EntitiesPage

- Entity grid/list view
- Entity filtering
- Entity detail modal

### LogsPage

- Log table with filtering
- Log level statistics
- Log detail modal
- Time range selection

### AuditPage

- Audit log table
- Action type filtering
- Audit statistics
- Audit detail modal

### SystemPage

- GPU statistics panel
- AI models status panel
- Database status panel
- Host system metrics
- Container status
- Performance alerts

### SettingsPage

- Camera settings section
- AI models settings
- Processing settings
- Notification settings
- Storage dashboard
- DLQ monitor

### AlertRulesPage

- Alert rules table
- Rule creation modal
- Rule editing
- Rule enable/disable
- Rule deletion
- Rule test functionality

### AIAuditPage

- AI pipeline audit table
- Quality score display
- Model contributions view
- Evaluation triggers
- Event drill-down

### ZonesPage

- Zone list for cameras
- Zone editor modal
- Zone drawing canvas
- Zone form
- Zone deletion

## Usage Pattern

```typescript
import { DashboardPage, TimelinePage } from '../pages';
import { setupApiMocks, defaultMockConfig } from '../fixtures';

test.describe('Dashboard Tests', () => {
  let dashboardPage: DashboardPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    dashboardPage = new DashboardPage(page);
  });

  test('displays all sections', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await dashboardPage.expectAllSectionsVisible();
  });

  test('shows cameras from API', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    const hasFrontDoor = await dashboardPage.hasCameraByName('Front Door');
    expect(hasFrontDoor).toBe(true);
  });

  test('can navigate to timeline', async ({ page }) => {
    await dashboardPage.goto();
    await dashboardPage.navigateToTimeline();
    const timeline = new TimelinePage(page);
    await timeline.expectPageLoaded();
  });
});
```

## Best Practices

1. **Selector Strategy**

   - Prefer role-based selectors (`getByRole`, `getByLabel`)
   - Use text matchers with regex for flexibility
   - Avoid implementation-specific selectors (class names, IDs)

2. **Wait Strategies**

   - Use page-specific wait methods (e.g., `waitForDashboardLoad`)
   - Prefer `waitFor` over fixed delays
   - Set appropriate timeouts for CI environments

3. **Method Organization**

   - Keep selectors as readonly properties
   - Group related methods (navigation, assertions, actions)
   - Return meaningful values from query methods

4. **Maintainability**
   - Update selectors here when UI changes
   - Don't duplicate selectors in test specs
   - Add new methods for common test patterns

## Notes for AI Agents

- All page objects extend `BasePage`
- Selectors use Playwright's recommended locator strategies
- Methods handle async/await properly
- Use `expect()` from `@playwright/test` for assertions
- Page load timeout is 5000ms by default
- Error handling uses `.catch(() => false)` for boolean checks
- Screenshots go to `test-results/` directory

## Entry Points

1. **Start here**: `BasePage.ts` - Understand common patterns
2. **Main page**: `DashboardPage.ts` - Most comprehensive example
3. **Simple page**: `EntitiesPage.ts` - Minimal implementation
4. **Complex page**: `SystemPage.ts` - Multiple panels/sections

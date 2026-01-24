# E2E User Journeys Test Directory

## Purpose

End-to-end tests that simulate complete user workflows across multiple pages and interactions. These tests verify critical user paths through the application, from navigation to configuration to feedback loops. Unlike individual page specs, user journey tests focus on real-world usage scenarios that span multiple features.

## Important Note

**All tests in this directory are skipped in CI** due to timing complexity and flakiness in parallel execution environments. These tests are designed to be run locally for validation before major releases.

```typescript
test.skip(() => !!process.env.CI, 'User journey tests flaky in CI - run locally');
```

## Test Files

| File                             | Linear Issue | Journey Focus                                        |
| -------------------------------- | ------------ | ---------------------------------------------------- |
| `alert-lifecycle.spec.ts`        | NEM-1664     | Alert navigation, filtering, acknowledgment          |
| `alert-rule-workflows.spec.ts`   | NEM-2049     | Advanced rule creation with schedules and channels   |
| `camera-configuration.spec.ts`   | NEM-2049     | Camera setup, settings modification, persistence     |
| `camera-management.spec.ts`      | NEM-1664     | Dashboard camera grid, status, detail navigation     |
| `detection-workflow.spec.ts`     | NEM-1664     | Detection to AI analysis review workflow             |
| `event-filtering-search.spec.ts` | NEM-2049     | Event discovery with multi-filter combinations       |
| `feedback-calibration-loop.spec.ts` | NEM-2322  | Complete feedback to threshold calibration loop      |
| `investigation-workflow.spec.ts` | NEM-1664     | Event investigation and review marking               |
| `settings-configuration.spec.ts` | NEM-1664     | System and camera configuration persistence          |
| `settings-navigation.spec.ts`    | NEM-2049     | Settings tabs navigation and form interactions       |

## User Journeys Covered

### Alert Management

**Alert Lifecycle Journey** (`alert-lifecycle.spec.ts`)
- Navigate from dashboard to alerts page
- Filter alerts by severity level
- Acknowledge individual alerts
- View detailed alert information
- Batch acknowledge multiple alerts
- Visual severity distinction

**Alert Rule Workflows** (`alert-rule-workflows.spec.ts`)
- Create rules with time-based schedule constraints
- Create rules targeting multiple object types (person, vehicle)
- Configure multiple notification channels (email, webhook)
- Test rules against historical events
- Edit rules while preserving existing configuration
- Bulk enable/disable rules
- View rule test results with match details

### Camera Operations

**Camera Management Journey** (`camera-management.spec.ts`)
- View all cameras in dashboard grid
- Verify status indicators (online/offline/recording)
- Open camera detail view via card click
- Navigate to filtered timeline by camera
- WebSocket real-time status updates
- Responsive grid layout across viewports

**Camera Configuration Journey** (`camera-configuration.spec.ts`)
- Navigate to cameras settings tab
- View all configured cameras in table
- Modify camera name and settings
- Enable/disable camera via toggle
- Configure FTP path settings
- Save configuration with success feedback
- Validation errors for invalid configuration
- Configuration persistence after reload

### Event Investigation

**Detection Workflow** (`detection-workflow.spec.ts`)
- View recent detections on dashboard
- Click detection to open detail modal
- Navigate through multiple detections sequentially
- View comprehensive AI analysis (risk score, reasoning)
- Detection cards show preview information

**Investigation Workflow** (`investigation-workflow.spec.ts`)
- Navigate to timeline from dashboard
- Search events by date range
- Search events by keyword
- Open event details from timeline
- Mark events as reviewed
- Visual indicator for reviewed events
- Filter to show only unreviewed events
- Chronological event ordering

**Event Filtering and Search** (`event-filtering-search.spec.ts`)
- Apply single filter (risk level)
- Combine multiple filters (camera + risk + object type)
- Full-text search with results
- Combine search with filters
- Clear all filters and reset view
- Date range filtering
- Sort by different criteria
- Clear search while keeping browse filters
- Results count updates

### Feedback and Calibration

**Feedback-Calibration Loop** (`feedback-calibration-loop.spec.ts`)
- Submit false positive feedback on high-risk event
- Verify threshold adjustment from feedback
- Observe event reclassification after calibration
- Visual indicator for calibrated events
- Multiple feedback submissions with progressive adjustment
- Different calibration effects for different feedback types

### Settings and Configuration

**Settings Configuration** (`settings-configuration.spec.ts`)
- Navigate to settings from dashboard
- View all configuration sections
- Modify camera settings with immediate UI feedback
- Save camera configuration changes
- Settings persistence after page reload
- Configure alert threshold settings
- Error feedback for invalid configuration
- Reset settings to defaults
- View current system information

**Settings Navigation** (`settings-navigation.spec.ts`)
- Navigate between all settings tabs (Cameras, Rules, Processing, Notifications, Prompts)
- Configure processing settings (batch window, retention)
- Configure notification channels and webhook URL
- View alert rules management interface
- Keyboard navigation between tabs
- Tab state persistence during navigation
- Validation errors for invalid settings
- Descriptive help text for each section

## Test Patterns

### Given-When-Then Structure

All tests follow explicit BDD-style documentation:

```typescript
test('user can filter alerts by severity level', async ({ page }) => {
  /**
   * Given: User is on the alerts page with multiple alerts
   * When: User selects a severity filter (high/medium/low)
   * Then: Alert list updates to show only alerts of that severity
   */
  // Test implementation...
});
```

### Graceful Degradation

Tests handle missing UI elements gracefully since some features may not be implemented:

```typescript
if (await filterButton.count() > 0) {
  await filterButton.click();
  // Continue test...
}
```

### Modal Handling

Custom helper for HeadlessUI transition issues:

```typescript
async function waitForModalContent(page: Page) {
  const modal = page.locator('[data-testid="event-detail-modal"]');
  await modal.waitFor({ state: 'attached', timeout: 10000 });
  await expect(modal).toBeVisible({ timeout: 5000 });
  // Wait for key content to be stable...
}
```

### Browser-Specific Timeouts

Longer timeouts for Firefox and WebKit:

```typescript
const timeout = browserName === 'chromium' ? 10000 : 20000;
await page.waitForSelector('[data-testid="dashboard-container"]', {
  state: 'visible',
  timeout
});
```

## Dependencies

Tests use shared fixtures and page objects:

```typescript
import { test, expect } from '../../fixtures';
import { TimelinePage } from '../../pages';
import { mockEvents, mockUserCalibration } from '../../fixtures/test-data';
import { waitForAnimation } from '../../utils/wait-helpers';
import { waitForElementStable } from '../../utils/test-helpers';
```

## Running User Journey Tests

```bash
# Run all user journey tests (locally only)
cd frontend
npx playwright test specs/user-journeys/

# Run specific journey
npx playwright test specs/user-journeys/alert-lifecycle.spec.ts

# Run with browser visible
npx playwright test specs/user-journeys/ --headed

# Run with debug mode
npx playwright test specs/user-journeys/camera-management.spec.ts --debug

# Force run in CI-like environment (will skip)
CI=true npx playwright test specs/user-journeys/
```

## Known Limitations

### Skipped Tests

Several tests are marked as `test.skip` due to specific issues:

| Test | Reason | Tracking |
| ---- | ------ | -------- |
| Modal loading timeout | HeadlessUI transition timing | NEM-2748 |
| Feedback calibration loop | CI timeout in parallel execution | - |
| Multiple feedback submissions | DOM detachment during re-renders | - |
| Filter persistence | Modal navigation causing state issues | - |

### API Mocking

Tests use route interception for API mocking. Mock state can be modified during tests:

```typescript
let currentCalibration = { ...mockUserCalibration.default };

await page.route('**/api/calibration', async (route) => {
  if (route.request().method() === 'GET') {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(currentCalibration),
    });
  }
});
```

## Notes for AI Agents

- These tests simulate **real user workflows**, not isolated component behavior
- Tests may span multiple pages and require navigation
- Use `waitForTimeout` sparingly - prefer explicit waits for elements/network
- HeadlessUI modals require special handling due to CSS transitions
- Mock API state can be mutated during tests for stateful workflows
- Tests verify **user-visible outcomes**, not internal state
- Browser-specific behavior varies - test on Chromium primarily
- Clean up state modifications (toggle back, restore values) when possible

## Entry Points

1. **Simple journey**: `alert-lifecycle.spec.ts` - Navigation and basic interactions
2. **Complex workflow**: `feedback-calibration-loop.spec.ts` - Multi-step stateful journey
3. **Settings patterns**: `settings-navigation.spec.ts` - Tab navigation and form handling
4. **Search patterns**: `event-filtering-search.spec.ts` - Filter combinations and search

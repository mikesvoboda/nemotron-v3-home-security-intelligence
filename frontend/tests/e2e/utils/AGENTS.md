# E2E Test Utilities Directory

## Purpose

Comprehensive utility functions and helpers for E2E tests. These utilities provide reusable patterns for page interactions, data generation, async operations, and browser-level controls. All utilities are designed to work seamlessly with Playwright and the existing test infrastructure.

## Key Files

| File                 | Purpose                                          |
| -------------------- | ------------------------------------------------ |
| `index.ts`           | Central exports for all utilities                |
| `accessibility.ts`   | Accessibility (a11y) testing with axe-core       |
| `test-helpers.ts`    | Common test helper functions                     |
| `data-generators.ts` | Test data factory functions                      |
| `wait-helpers.ts`    | Wait utilities for async operations              |
| `browser-helpers.ts` | Browser-level utilities (viewport, theme, etc.)  |

## accessibility.ts - Accessibility Testing

Provides helper functions for WCAG 2.1 AA compliance testing using axe-core.

### Exports

| Export                        | Type     | Purpose                                        |
| ----------------------------- | -------- | ---------------------------------------------- |
| `checkAccessibility`          | Function | Run basic accessibility check on page          |
| `checkAccessibilityWithDetails` | Function | Run check and return formatted violations    |
| `assertNoA11yViolations`      | Function | Assert no violations (throws on failure)       |
| `getViolationsByImpact`       | Function | Group violations by impact level               |
| `hasNoCriticalA11yViolations` | Function | Check only for critical violations             |
| `filterViolationsByImpact`    | Function | Filter violations by impact level              |
| `A11yCheckOptions`            | Type     | Configuration options for checks               |
| `FormattedViolation`          | Type     | Formatted violation for error messages         |

### A11yCheckOptions Interface

```typescript
interface A11yCheckOptions {
  /** Tags to check (e.g., 'wcag2a', 'wcag2aa', 'wcag21aa') */
  tags?: string[];
  /** Rules to disable (document reasoning) */
  disableRules?: string[];
  /** CSS selector to limit check scope */
  include?: string;
  /** CSS selectors to exclude from check */
  exclude?: string[];
}
```

### FormattedViolation Interface

```typescript
interface FormattedViolation {
  id: string;
  impact: string;
  description: string;
  help: string;
  helpUrl: string;
  nodes: {
    html: string;
    target: string[];
    failureSummary: string;
  }[];
}
```

### Usage Examples

```typescript
import { checkAccessibility, assertNoA11yViolations } from '../utils';

// Basic accessibility check
test('page is accessible', async ({ page }) => {
  await page.goto('/');
  await assertNoA11yViolations(page);
});

// Check specific region
test('modal is accessible', async ({ page }) => {
  await page.goto('/');
  await page.click('[data-testid="open-modal"]');
  await assertNoA11yViolations(page, {
    include: '[role="dialog"]',
  });
});

// Allow certain violations
test('page with known issues', async ({ page }) => {
  await page.goto('/');
  await assertNoA11yViolations(page, {
    disableRules: ['color-contrast'], // Document why this is disabled
  });
});

// Get detailed violation report
test('check with details', async ({ page }) => {
  await page.goto('/');
  const { violations, summary } = await checkAccessibilityWithDetails(page);
  if (violations.length > 0) {
    console.log(summary);
  }
});

// Check for critical only
test('no critical violations', async ({ page }) => {
  await page.goto('/');
  const hasCritical = await hasNoCriticalA11yViolations(page);
  expect(hasCritical).toBe(true);
});
```

## WCAG 2.1 AA Standards

The utilities default to WCAG 2.1 AA compliance, which includes:

### Perceivable
- Text alternatives for non-text content
- Captions and alternatives for audio/video
- Adaptable content presentation
- Distinguishable content (color contrast 4.5:1)

### Operable
- Keyboard accessible (all functionality)
- Enough time to read and use content
- No content that causes seizures
- Navigable (skip links, focus order, link purpose)

### Understandable
- Readable text content
- Predictable web page operation
- Input assistance (error identification, labels)

### Robust
- Compatible with assistive technologies
- Valid HTML/ARIA usage

## Impact Levels

Violations are categorized by impact:

| Impact   | Description                                 |
| -------- | ------------------------------------------- |
| critical | Users cannot use the functionality at all   |
| serious  | Users have significant difficulty           |
| moderate | Users may have some difficulty              |
| minor    | Users may be inconvenienced                 |

## Dependencies

- `@axe-core/playwright` - Axe accessibility testing integration
- `axe-core` - Core accessibility rules engine

## Integration with Test Specs

The `accessibility.spec.ts` in `specs/` uses these utilities:

```typescript
import { test } from '@playwright/test';
import { assertNoA11yViolations } from '../utils';
import { DashboardPage } from '../pages';

test.describe('Accessibility', () => {
  test('dashboard is WCAG 2.1 AA compliant', async ({ page }) => {
    const dashboard = new DashboardPage(page);
    await dashboard.goto();
    await dashboard.waitForDashboardLoad();
    await assertNoA11yViolations(page);
  });
});
```

## test-helpers.ts - Common Test Helpers

Reusable helper functions for page load verification, API mocking, state management, and screenshot capture.

### Key Functions

| Function                    | Purpose                                           |
| --------------------------- | ------------------------------------------------- |
| `waitForPageLoad`           | Wait for React hydration and page load            |
| `mockApiResponse`           | Mock specific API endpoint responses              |
| `clearTestState`            | Reset browser state between tests                 |
| `takeScreenshotOnFailure`   | Auto-screenshot on test failure                   |
| `waitForElementStable`      | Wait for element to stop animating                |
| `fillFormField`             | Fill form field and wait for validation           |
| `retryAction`               | Retry operation with exponential backoff          |
| `getBrowserName`            | Get current browser (chromium/firefox/webkit)     |
| `waitForConsoleMessage`     | Wait for console message matching pattern         |

### Usage Examples

```typescript
import { waitForPageLoad, mockApiResponse, clearTestState } from '../utils';

test('loads correctly', async ({ page }) => {
  // Mock API before navigation
  await mockApiResponse(page, '/api/cameras', { cameras: [] });

  await page.goto('/');
  await waitForPageLoad(page);

  // Page is now fully loaded and interactive
});

test.beforeEach(async ({ page }) => {
  // Clear state before each test
  await clearTestState(page);
});

test.afterEach(async ({ page }, testInfo) => {
  // Auto-screenshot on failure
  await takeScreenshotOnFailure(page, testInfo);
});
```

## data-generators.ts - Test Data Factories

Factory functions for generating realistic test data with randomization and deterministic seeding support.

### Key Functions

| Function              | Purpose                                      |
| --------------------- | -------------------------------------------- |
| `generateCamera`      | Generate camera test data                    |
| `generateCameras`     | Generate multiple cameras                    |
| `generateEvent`       | Generate security event data                 |
| `generateEvents`      | Generate multiple events with risk filtering |
| `generateDetection`   | Generate object detection data               |
| `generateAlert`       | Generate alert notification data             |
| `generateGpuStats`    | Generate GPU statistics                      |
| `generateEmail`       | Generate realistic email address             |
| `generateTimestamp`   | Generate timestamp within age range          |

### Usage Examples

```typescript
import { generateCamera, generateEvents, generateGpuStats } from '../utils';

test('displays camera data', async ({ page }) => {
  // Generate realistic camera with overrides
  const camera = generateCamera({
    status: 'offline',
    name: 'Front Door',
  });

  await mockApiResponse(page, '/api/cameras', { cameras: [camera] });
  await page.goto('/');

  await expect(page.getByText('Front Door')).toBeVisible();
  await expect(page.getByText('Offline')).toBeVisible();
});

test('filters high-risk events', async ({ page }) => {
  // Generate 10 events with risk scores 70-100
  const events = generateEvents(10, { minRiskScore: 70, maxRiskScore: 100 });

  await mockApiResponse(page, '/api/events', { events });
  await page.goto('/timeline');

  await expect(page.locator('.event-card')).toHaveCount(10);
});

test('deterministic data with seed', async ({ page }) => {
  // Same seed produces same data (useful for snapshot tests)
  const camera1 = generateCamera({}, 123);
  const camera2 = generateCamera({}, 123);

  expect(camera1).toEqual(camera2);
});
```

## wait-helpers.ts - Wait Utilities

Specialized wait functions for async operations including WebSocket connections, API calls, animations, and element states.

### Key Functions

| Function                   | Purpose                                         |
| -------------------------- | ----------------------------------------------- |
| `waitForWebSocket`         | Wait for WebSocket connection                   |
| `waitForWebSocketDisconnect` | Wait for WebSocket disconnection              |
| `waitForElement`           | Wait for element with retry logic               |
| `waitForApiCall`           | Wait for specific API call to complete          |
| `waitForApiCalls`          | Wait for multiple API calls                     |
| `waitForAnimation`         | Wait for CSS animations to complete             |
| `waitForLoadingToComplete` | Wait for loading indicators to disappear        |
| `waitForTextChange`        | Wait for element text to change                 |
| `waitForElementCount`      | Wait for element count to change                |
| `waitForNetworkIdle`       | Wait for all network requests to complete       |
| `waitWithBackoff`          | Retry with exponential backoff                  |

### Usage Examples

```typescript
import { waitForWebSocket, waitForApiCall, waitForAnimation } from '../utils';

test('real-time updates', async ({ page }) => {
  await page.goto('/');
  await waitForWebSocket(page);

  // WebSocket is now connected, safe to test real-time features
  await expect(page.getByText('Connected')).toBeVisible();
});

test('data refreshes', async ({ page }) => {
  await page.goto('/');

  // Wait for specific API call triggered by action
  const responsePromise = waitForApiCall(page, '/api/events');
  await page.click('button.refresh');
  const response = await responsePromise;

  expect(response.status()).toBe(200);
});

test('modal animation', async ({ page }) => {
  await page.click('button.open-modal');
  await waitForAnimation(page, '.modal');

  // Animation complete, safe to interact
  await page.click('.modal button.submit');
});
```

## browser-helpers.ts - Browser Utilities

Browser-level utilities for viewport management, theme switching, network throttling, and storage manipulation.

### Key Functions

| Function                    | Purpose                                      |
| --------------------------- | -------------------------------------------- |
| `setViewport`               | Set viewport size (preset or custom)         |
| `enableDarkMode`            | Enable dark mode theme                       |
| `disableDarkMode`           | Disable dark mode (enable light mode)        |
| `toggleDarkMode`            | Toggle theme and return current state        |
| `simulateSlowNetwork`       | Throttle network (2g/3g/4g presets)          |
| `disableNetworkThrottling`  | Restore normal network speed                 |
| `simulateOfflineMode`       | Simulate offline connection                  |
| `clearStorage`              | Clear localStorage/sessionStorage/cookies    |
| `setLocalStorage`           | Set localStorage item                        |
| `getLocalStorage`           | Get localStorage item                        |
| `setCookie`                 | Set cookie with options                      |
| `getCookie`                 | Get cookie by name                           |
| `blockResources`            | Block resources by type (images, fonts, etc.)|
| `takeFullPageScreenshot`    | Capture full page screenshot                 |
| `getConsoleLogs`            | Collect browser console messages             |

### Viewport Presets

```typescript
VIEWPORT_PRESETS = {
  // Desktop
  desktop: { width: 1920, height: 1080 },
  laptop: { width: 1440, height: 900 },

  // Tablet
  tablet: { width: 1024, height: 768 },
  ipadPro: { width: 1024, height: 1366 },

  // Mobile
  mobile: { width: 375, height: 667 },
  mobileLarge: { width: 414, height: 896 },
}
```

### Network Presets

```typescript
NETWORK_PRESETS = {
  '2g': { downloadThroughput: 50 KB/s, latency: 300ms },
  '3g': { downloadThroughput: 1.5 MB/s, latency: 100ms },
  '4g': { downloadThroughput: 10 MB/s, latency: 20ms },
  slow: { downloadThroughput: 500 KB/s, latency: 200ms },
}
```

### Usage Examples

```typescript
import {
  setViewport,
  enableDarkMode,
  simulateSlowNetwork,
  clearStorage,
} from '../utils';

test('responsive layout', async ({ page }) => {
  // Test tablet viewport
  await setViewport(page, 'tablet');
  await page.goto('/');

  await expect(page.locator('.mobile-menu')).toBeVisible();
});

test('dark mode styling', async ({ page }) => {
  await page.goto('/');
  await enableDarkMode(page);

  // Verify dark theme styles
  const bg = await page.locator('body').evaluate(el =>
    window.getComputedStyle(el).backgroundColor
  );
  expect(bg).toContain('rgb(0, 0, 0)');
});

test('loading on slow network', async ({ page }) => {
  await simulateSlowNetwork(page, '3g');
  await page.goto('/');

  // Loading indicator should appear
  await expect(page.locator('.loading-spinner')).toBeVisible();
});

test.beforeEach(async ({ page }) => {
  // Clear storage but preserve auth
  await clearStorage(page, {
    preserveCookies: ['session_id'],
  });
});
```

## Notes for AI Agents

### General Guidelines

- All utilities support TypeScript with full type definitions
- Functions use Playwright's native APIs for maximum compatibility
- Utilities are designed to be composable and chainable
- Errors include helpful messages with context

### Test Helper Best Practices

- Always call `waitForPageLoad` after navigation for stability
- Use `clearTestState` in `beforeEach` to ensure test isolation
- Add `takeScreenshotOnFailure` in `afterEach` for debugging
- Prefer `waitForElementStable` over `page.waitForTimeout` for animations

### Data Generator Best Practices

- Use overrides for specific test scenarios
- Use seeded generation for deterministic snapshot tests
- Generate data instead of hardcoding for better coverage
- Combine generators to create complex test scenarios

### Wait Helper Best Practices

- Prefer semantic waits (`waitForWebSocket`) over generic timeouts
- Use `waitForApiCall` instead of `page.waitForResponse` for clarity
- Chain waits for complex async sequences
- Use `waitWithBackoff` for eventually consistent operations

### Browser Helper Best Practices

- Use viewport presets for consistency across tests
- Test both light and dark themes for complete coverage
- Use network throttling to test loading states
- Clear storage between tests to prevent flakiness
- Block unnecessary resources to speed up tests

### Accessibility Best Practices

- Always use `assertNoA11yViolations` for strict compliance testing
- Use `hasNoCriticalA11yViolations` for less strict checks
- Document any `disableRules` with reasoning in comments
- Use `include` option to scope checks to specific components
- Violations include helpful URLs for remediation guidance
- Impact levels help prioritize fixes
- Tests run against rendered DOM, not source code

## Entry Points

1. **Start here:** `index.ts` - See all available exports
2. **Test helpers:** `test-helpers.ts` - Page load, mocking, state management
3. **Data generation:** `data-generators.ts` - Factory functions for test data
4. **Wait utilities:** `wait-helpers.ts` - Async operation helpers
5. **Browser controls:** `browser-helpers.ts` - Viewport, theme, network, storage
6. **Accessibility:** `accessibility.ts` - WCAG 2.1 AA compliance checking
7. **Usage examples:** `../specs/*.spec.ts` - See utilities in action

## Integration with Existing Infrastructure

These utilities are designed to work seamlessly with:

- **Page Objects** (`../pages/`) - Use utilities in Page Object methods
- **Fixtures** (`../fixtures/`) - Combine with API mocks and WebSocket mocks
- **Specs** (`../specs/`) - Import and use in test files
- **Global Setup** (`../global-setup.ts`) - Compatible with shared state
- **Playwright Config** (`../../playwright.config.ts`) - Respects timeouts and settings

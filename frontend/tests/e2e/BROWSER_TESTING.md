# Cross-Browser Testing Guide

This document describes browser-specific testing considerations and setup requirements for E2E tests.

## Browser Support

| Browser  | Status  | CI Priority | Notes                              |
| -------- | ------- | ----------- | ---------------------------------- |
| Chromium | Primary | Required    | Fast, stable, primary test target  |
| Firefox  | Secondary | Non-blocking | Slower, needs longer timeouts     |
| WebKit   | Secondary | Non-blocking | Requires system dependencies      |

## Browser Installation

### Chromium
Chromium is installed automatically by Playwright and requires no additional setup.

### Firefox
Firefox is installed automatically by Playwright and requires no additional setup.

### WebKit (Safari)

WebKit requires system dependencies on Linux. If you see errors like:

```
Host system is missing dependencies to run browsers.
Please install them with the following command:

    sudo npx playwright install-deps

Alternatively, use apt:
    sudo apt-get install libicu74 libjpeg-turbo8
```

**Fix:**
```bash
# Option 1: Install all Playwright dependencies (recommended)
sudo npx playwright install-deps

# Option 2: Install only required packages
sudo apt-get install libicu74 libjpeg-turbo8

# Option 3: On macOS (no additional deps needed)
# WebKit is Safari's rendering engine and works out of the box
```

## Browser-Specific Timeouts

Different browsers have different performance characteristics:

| Browser  | Action Timeout | Navigation Timeout | Test Timeout  |
| -------- | -------------- | ------------------ | ------------- |
| Chromium | 5s             | 10s                | 30s (default) |
| Firefox  | 8s             | 20s                | 30s (default) |
| WebKit   | 8s             | 10s                | 30s (default) |

These are configured in `playwright.config.ts`.

### Why Firefox Needs Longer Timeouts

Firefox has longer timeouts because:
1. **WebSocket connections** take longer to establish (especially in CI)
2. **Page loads** are slightly slower due to different rendering engine
3. **CSS animations** may take longer to stabilize
4. **Network stack** behaves differently than Chromium

Reference: NEM-1807, NEM-1486

## Known Browser Differences

### WebSocket Status Indicator
- **Issue:** WebSocket status indicator takes longer to appear in Firefox/WebKit
- **Solution:** Use 20s timeout instead of 10s for `websocket-status` element
- **Files affected:** `user-journeys/*.spec.ts`

```typescript
// Good: Browser-aware timeout
const timeout = browserName === 'chromium' ? 10000 : 20000;
await page.waitForSelector('[data-testid="websocket-status"]', {
  state: 'visible',
  timeout
});

// Bad: Fixed timeout that fails in Firefox
await page.waitForSelector('[data-testid="websocket-status"]', {
  state: 'visible',
  timeout: 10000
});
```

### Touch Target Sizing
- **Issue:** CSS rendering differences cause button dimensions to vary by 1-2px
- **Solution:** Allow 2px variance (42px instead of 44px) and tolerate 20% failure rate
- **Files affected:** `mobile-optimization.spec.ts`

### Empty State Rendering
- **Issue:** Null values may render as "N/A", "0", or "No data" depending on browser
- **Solution:** Check for multiple possible empty state indicators
- **Files affected:** `ai-audit.spec.ts`

### Multi-Page Navigation
- **Issue:** Sequential navigation through many pages can exceed navigation timeout
- **Solution:** Increase test timeout for `@slow` tests to 90s for Firefox/WebKit
- **Files affected:** `test-tagging.spec.ts`

## Writing Browser-Compatible Tests

### Use `browserName` Parameter

Access the browser name in tests:

```typescript
test('my test', async ({ page, browserName }) => {
  if (browserName === 'firefox') {
    // Firefox-specific handling
  }

  const timeout = browserName === 'chromium' ? 5000 : 8000;
  await expect(element).toBeVisible({ timeout });
});
```

### Skip Tests for Specific Browsers

```typescript
test('webkit-incompatible feature', async ({ page, browserName }) => {
  test.skip(browserName === 'webkit', 'Feature not supported in WebKit');

  // Test implementation
});
```

### Use Flexible Assertions

Instead of exact text matches, use flexible patterns:

```typescript
// Good: Flexible
await expect(page.getByText(/connected|online/i)).toBeVisible();

// Bad: Brittle
await expect(page.getByText('Connected')).toBeVisible();
```

### Check for Multiple Possible States

```typescript
// Good: Handle browser differences
const indicator = page.getByText('N/A')
  .or(page.getByText('—'))
  .or(page.getByText(/no data/i));
await expect(indicator.first()).toBeVisible();

// Bad: Assumes single rendering
await expect(page.getByText('N/A')).toBeVisible();
```

## CI Configuration

### GitHub Actions Matrix

CI runs browsers in parallel jobs:

```yaml
matrix:
  project: [chromium, firefox, webkit]
  continue-on-error:
    - chromium: false  # Chromium failures block merge
    - firefox: true    # Firefox failures are warnings
    - webkit: true     # WebKit failures are warnings
```

### Retry Strategy

All browsers get 2 retries in CI:

```typescript
// playwright.config.ts
retries: process.env.CI ? 2 : 0
```

This catches flaky tests while allowing real failures to surface.

## Debugging Browser-Specific Failures

### Run Specific Browser Locally

```bash
# Run Firefox tests
npx playwright test --project=firefox

# Run WebKit tests
npx playwright test --project=webkit

# Run with headed browser
npx playwright test --project=firefox --headed

# Debug mode
npx playwright test --project=firefox --debug
```

### Compare Browser Behavior

Run the same test across all browsers to see differences:

```bash
npx playwright test specs/my-test.spec.ts
```

### Check Actual vs Expected

Use `--trace on` to record execution:

```bash
npx playwright test --project=firefox --trace on
npx playwright show-report
```

## Performance Benchmarks

Based on full test suite (546 tests):

| Browser  | Duration | Parallel Workers | Sharding |
| -------- | -------- | ---------------- | -------- |
| Chromium | ~8 min   | 4                | Yes (4)  |
| Firefox  | ~12 min  | 4                | No       |
| WebKit   | ~10 min  | 4                | No       |

## References

- Linear Issues: NEM-1486 (WebKit), NEM-1807 (Firefox)
- Playwright Config: `frontend/playwright.config.ts`
- Test Fixtures: `frontend/tests/e2e/fixtures/`
- Page Objects: `frontend/tests/e2e/pages/`

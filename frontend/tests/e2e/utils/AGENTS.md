# E2E Test Utilities Directory

## Purpose

Reusable helper functions for the Playwright E2E suites: page interactions,
API mocking, test-data factories, async waits, and browser-level controls
(viewport, theme, network, storage). Everything is exported from `index.ts`;
import from `'../utils'`.

Note: most specs do **not** import from here - they use the page objects
(`../pages/`) and fixtures (`../fixtures/`) instead. The one spec that
exercises these helpers directly is `../specs/utils-demo.spec.ts`.

## Key Files

| File                 | Purpose                                        |
| -------------------- | ---------------------------------------------- |
| `index.ts`           | Central exports for all utilities              |
| `test-helpers.ts`    | Page load, API mocking, state, screenshots     |
| `data-generators.ts` | Seeded test-data factory functions             |
| `wait-helpers.ts`    | Wait utilities (WebSocket, API, animation)     |
| `browser-helpers.ts` | Viewport, theme, network, storage, geolocation |

There is no `accessibility.ts` here (older revisions of this doc described
one). Axe-core checks are written inline in the specs themselves - see
"Accessibility checks" below.

## test-helpers.ts - Common Test Helpers

| Export                    | Purpose                                                                         |
| ------------------------- | ------------------------------------------------------------------------------- |
| `waitForPageLoad`         | Wait for React hydration / page load                                            |
| `mockApiResponse`         | `page.route()` mock: `(page, endpoint, response, { status?, delay?, method? })` |
| `clearTestState`          | Reset browser state between tests                                               |
| `takeScreenshotOnFailure` | Screenshot wired to `testInfo` on failure                                       |
| `waitForElementStable`    | Wait until an element stops animating                                           |
| `fillFormField`           | Fill a field and wait for validation                                            |
| `retryAction`             | Retry a callback with exponential backoff                                       |
| `isHeadedMode`            | True when running with a visible browser                                        |
| `getBrowserName`          | `chromium` / `firefox` / `webkit`                                               |
| `waitForConsoleMessage`   | Wait for a console message matching a pattern                                   |

## data-generators.ts - Test Data Factories

Deterministic-friendly generators (optional numeric `seed` argument; same
seed => same data).

| Export                                     | Purpose                                                          |
| ------------------------------------------ | ---------------------------------------------------------------- |
| `generateCamera`                           | One camera: `generateCamera(overrides?, seed?)`                  |
| `generateCameras`                          | `generateCameras(count, seed?)`                                  |
| `generateEvent`                            | One event: `generateEvent(overrides?, seed?)`                    |
| `generateEvents`                           | `generateEvents(count, { seed?, minRiskScore?, maxRiskScore? })` |
| `generateDetection` / `generateDetections` | Detection data (single / list)                                   |
| `generateAlert` / `generateAlerts`         | Alert data (single / list)                                       |
| `generateGpuStats`                         | GPU stats with overrides (utilization, memory, temp, fps...)     |
| `generateEmail`                            | Realistic email address (`generateEmail(seed?)`)                 |
| `generateTimestamp`                        | ISO timestamp within `{ minAgeMs?, maxAgeMs?, seed? }`           |

Exported types: `CameraData`, `EventData`, `DetectionData`, `AlertData`.

## wait-helpers.ts - Wait Utilities

| Export                               | Purpose                                                                                                                 |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| `waitForWebSocket`                   | `waitForWebSocket(page, channel = 'events', { timeout?, checkIndicator? })`; checks the `window.__wsMock` fixture state |
| `waitForWebSocketDisconnect`         | Wait for the socket to close                                                                                            |
| `waitForElement`                     | Element wait with retry logic                                                                                           |
| `waitForApiCall` / `waitForApiCalls` | Wait for specific request(s) to finish                                                                                  |
| `waitForAnimation`                   | Wait for CSS animation to complete                                                                                      |
| `waitForLoadingToComplete`           | Wait for loading indicators to disappear                                                                                |
| `waitForTextChange`                  | Wait for an element's text to change                                                                                    |
| `waitForElementCount`                | Wait for locator count to change                                                                                        |
| `waitForNetworkIdle`                 | Wait for network to quiet down                                                                                          |
| `waitWithBackoff`                    | Generic retry with exponential backoff                                                                                  |

Type: `WebSocketChannel = 'events' | 'system'`.

## browser-helpers.ts - Browser Utilities

| Export                                                  | Purpose                                       |
| ------------------------------------------------------- | --------------------------------------------- |
| `VIEWPORT_PRESETS`, `setViewport`                       | Preset name or `{ width, height }`            |
| `enableDarkMode` / `disableDarkMode` / `toggleDarkMode` | Emulate color scheme                          |
| `NETWORK_PRESETS`, `simulateSlowNetwork`                | Throttle CDP network to a preset              |
| `disableNetworkThrottling`                              | Restore normal network                        |
| `simulateOfflineMode` / `restoreOnlineMode`             | Toggle offline                                |
| `clearStorage`                                          | `{ preserveCookies?, preserveLocalStorage? }` |
| `setLocalStorage` / `getLocalStorage`                   | localStorage item get/set                     |
| `setSessionStorage` / `getSessionStorage`               | sessionStorage item get/set                   |
| `setCookie` / `getCookie`                               | Cookie helpers (`getCookie` takes a context)  |
| `blockResources`                                        | Abort requests by resource type               |
| `setGeolocation` / `setTimezone`                        | Emulate location / timezone                   |
| `takeFullPageScreenshot`                                | Full-page screenshot to a path                |
| `getConsoleLogs`                                        | Collect console messages                      |

```typescript
VIEWPORT_PRESETS = {
  desktop: 1920x1080, desktopSmall: 1366x768, desktopLarge: 2560x1440,
  laptop: 1440x900, laptopSmall: 1280x800,
  tablet: 1024x768, tabletPortrait: 768x1024, ipadPro: 1024x1366,
  mobile: 375x667, mobileLarge: 414x896, mobileSmall: 320x568,
}

NETWORK_PRESETS = { '2g', '3g', '4g', dsl, cable, slow, offline }
// throughputs are bytes/sec as Playwright expects
```

## Accessibility checks

There is no shared a11y helper module. Axe-core runs are defined inline in
two specs, each using `AxeBuilder` from `@axe-core/playwright` with tags
`['wcag2a', 'wcag2aa', 'wcag21aa']`:

- `../specs/smoke.spec.ts` - "Accessibility Smoke Tests" describe block
  (dashboard, timeline, ...): asserts `results.violations` is empty; runs in
  normal CI smoke/critical jobs.
- `../specs/accessibility.spec.ts` - comprehensive page-by-page suite with a
  file-local `runA11yCheck(page)` helper. The whole file self-skips when
  `process.env.CI` is set ("axe-core tests are flaky due to page load timing
  issues - run locally"), and a few tests are permanently skipped.
  `.github/workflows/accessibility-tests.yml` runs it on push to main as a
  `continue-on-error: true` (non-blocking) job.

Practical rules when touching a11y tests: prefer scoping an `AxeBuilder` with
`.include()` over disabling rules; if a rule must be disabled, comment the
reason (color-contrast was fixed under NEM-1481 rather than disabled); check
violations against the rendered DOM, not source.

### Impact levels (axe)

| Impact   | Meaning                |
| -------- | ---------------------- |
| critical | functionality unusable |
| serious  | significant difficulty |
| moderate | some difficulty        |
| minor    | inconvenience          |

## Notes for AI Agents

- Always call `waitForPageLoad` after navigation; prefer the semantic waits in
  `wait-helpers.ts` over `page.waitForTimeout`
- Use `clearTestState` / `clearStorage` in `beforeEach` for isolation
- Use seeded generators for deterministic data; overrides for scenario detail
- `waitForWebSocket` depends on the WS mock in `../fixtures/` (`window.__wsMock`)
- Page objects (`../pages/`) and fixtures (`../fixtures/`) are the primary
  test infrastructure; these utilities supplement them

## Entry Points

1. **Start here:** `index.ts` - the complete export list
2. **Reference usage:** `../specs/utils-demo.spec.ts` - every helper in action
3. **Main infrastructure:** `../pages/` (page objects) and `../fixtures/`
   (API/WebSocket mocks) - used by nearly all specs

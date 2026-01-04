# Frontend E2E Tests Directory

## Purpose

End-to-end test suite using Playwright for full browser-based testing. Tests verify that the application renders correctly and responds to user interactions with mocked backend APIs.

## Directory Structure

```
frontend/tests/e2e/
├── AGENTS.md           # This documentation file
├── fixtures/           # Test fixtures and API mocking
│   ├── AGENTS.md       # Fixtures documentation
│   ├── index.ts        # Central fixture exports with custom test function
│   ├── api-mocks.ts    # Configurable API mock setup
│   ├── test-data.ts    # Mock data for all entities
│   └── websocket-mock.ts  # WebSocket simulation utilities
├── pages/              # Page Object Model classes
│   ├── AGENTS.md       # Page objects documentation
│   ├── index.ts        # Central page object exports
│   ├── BasePage.ts     # Base class with common selectors/methods
│   ├── DashboardPage.ts
│   ├── TimelinePage.ts
│   ├── AlertsPage.ts
│   ├── AlertRulesPage.ts
│   ├── EntitiesPage.ts
│   ├── LogsPage.ts
│   ├── AuditPage.ts
│   ├── AIAuditPage.ts
│   ├── SystemPage.ts
│   ├── SettingsPage.ts
│   └── ZonesPage.ts
├── specs/              # Test specification files
│   ├── AGENTS.md       # Specs documentation
│   ├── smoke.spec.ts   # Basic loading and visibility tests
│   ├── dashboard.spec.ts   # Dashboard component tests
│   ├── navigation.spec.ts  # Route navigation tests
│   ├── realtime.spec.ts    # WebSocket and real-time tests
│   ├── events.spec.ts      # Events/timeline tests
│   ├── alerts.spec.ts      # Alerts page tests
│   ├── alert-rules.spec.ts # Alert rules configuration tests
│   ├── entities.spec.ts    # Entities page tests
│   ├── logs.spec.ts        # Logs page tests
│   ├── audit.spec.ts       # Audit log tests
│   ├── ai-audit.spec.ts    # AI pipeline audit tests
│   ├── system.spec.ts      # System monitoring tests
│   ├── settings.spec.ts    # Settings page tests
│   ├── zones.spec.ts       # Camera zones configuration tests
│   ├── responsive.spec.ts  # Responsive design tests
│   ├── accessibility.spec.ts # WCAG 2.1 AA compliance tests
│   └── error-handling.spec.ts  # Error state tests
├── utils/              # Test utility functions
│   ├── AGENTS.md       # Utils documentation
│   ├── index.ts        # Central utility exports
│   └── accessibility.ts  # Accessibility testing helpers (axe-core)
└── .gitkeep            # Git placeholder
```

## Architecture

### Page Object Model (POM)

Tests follow the Page Object Model pattern for maintainability:

```typescript
// In test spec:
import { DashboardPage } from '../pages';
import { setupApiMocks, defaultMockConfig } from '../fixtures';

test('dashboard loads', async ({ page }) => {
  await setupApiMocks(page, defaultMockConfig);
  const dashboard = new DashboardPage(page);
  await dashboard.goto();
  await dashboard.expectAllSectionsVisible();
});
```

### Fixture System

Fixtures provide configurable mock data and API setup:

```typescript
// Default configuration
import { test, expect } from '../fixtures';

test('auto-mocked test', async ({ page }) => {
  // API mocks automatically set up via fixture
  await page.goto('/');
});

// Custom configuration
import { errorMockConfig } from '../fixtures';

test.use({ mockConfig: errorMockConfig });

test('error state test', async ({ page }) => {
  await page.goto('/');
  // Will use error mock config
});
```

## Mock Configurations

| Configuration         | Purpose                            |
| --------------------- | ---------------------------------- |
| `defaultMockConfig`   | Normal operation with healthy data |
| `emptyMockConfig`     | No data scenarios (empty lists)    |
| `errorMockConfig`     | API failure scenarios (500 errors) |
| `highAlertMockConfig` | High-risk state with many alerts   |

## Mocked API Endpoints

All backend endpoints are mocked to enable testing without a real backend:

| Endpoint                       | Purpose                |
| ------------------------------ | ---------------------- |
| `GET /api/cameras`             | Camera list            |
| `GET /api/cameras/*/snapshot*` | Camera snapshot images |
| `GET /api/events*`             | Events with pagination |
| `GET /api/events/stats*`       | Event statistics       |
| `GET /api/system/gpu`          | Current GPU stats      |
| `GET /api/system/gpu/history*` | GPU history samples    |
| `GET /api/system/health`       | System health status   |
| `GET /api/system/stats`        | System statistics      |
| `GET /api/system/config`       | System configuration   |
| `GET /api/system/telemetry`    | Pipeline telemetry     |
| `GET /api/system/workers`      | Worker status          |
| `GET /api/system/performance`  | Performance metrics    |
| `GET /api/logs*`               | Log entries            |
| `GET /api/logs/stats`          | Log statistics         |
| `GET /api/audit*`              | Audit log entries      |
| `GET /api/audit/stats`         | Audit statistics       |
| `GET /api/search*`             | Search results         |
| `GET /api/health`              | Basic health check     |
| `WS /ws/**`                    | WebSocket connections  |

**Important**: Route handlers are matched in registration order. More specific routes (e.g., `/api/system/gpu/history`) must be registered BEFORE more general routes (e.g., `/api/system/gpu`).

## Running Tests

```bash
# From frontend/ directory
npm run test:e2e            # Run all E2E tests (headless)
npm run test:e2e:headed     # Run with browser visible
npm run test:e2e:debug      # Run in debug mode
npm run test:e2e:report     # View HTML report

# Run specific test file
npx playwright test specs/smoke.spec.ts
npx playwright test specs/dashboard.spec.ts

# Run tests matching a pattern
npx playwright test -g "dashboard"
```

## Playwright Configuration

From `frontend/playwright.config.ts`:

| Setting             | Value                                      |
| ------------------- | ------------------------------------------ |
| `testDir`           | `./tests/e2e/specs`                        |
| `baseURL`           | `http://localhost:5173`                    |
| `browsers`          | Chromium, Firefox, WebKit                  |
| `timeout`           | 15 seconds                                 |
| `expect.timeout`    | 3 seconds                                  |
| `navigationTimeout` | 10 seconds                                 |
| `actionTimeout`     | 5s (Chromium), 8s (Firefox/WebKit)         |
| `retries`           | 2 (CI only)                                |
| `workers`           | 4 (CI), unlimited (local)                  |
| `fullyParallel`     | true                                       |
| `webServer.command` | `npm run dev:e2e`                          |

**Artifacts on Failure:**

- Screenshots saved to `test-results/`
- Traces collected on first retry
- Videos retained on failure

## Test Categories

| Category   | Spec File                | Description                        |
| ---------- | ------------------------ | ---------------------------------- |
| Smoke      | `smoke.spec.ts`          | Basic loading and visibility       |
| Dashboard  | `dashboard.spec.ts`      | Dashboard-specific functionality   |
| Navigation | `navigation.spec.ts`     | Route transitions and URL handling |
| Real-time  | `realtime.spec.ts`       | WebSocket and live updates         |
| Events     | `events.spec.ts`         | Event timeline and details         |
| Alerts     | `alerts.spec.ts`         | Alert management                   |
| Entities   | `entities.spec.ts`       | Entity tracking                    |
| Logs       | `logs.spec.ts`           | Application logs                   |
| Audit      | `audit.spec.ts`          | Audit log viewer                   |
| System     | `system.spec.ts`         | System monitoring                  |
| Settings   | `settings.spec.ts`       | Application settings               |
| Responsive | `responsive.spec.ts`     | Mobile/tablet viewports            |
| Errors     | `error-handling.spec.ts` | Error states and recovery          |

## Notes for AI Agents

- Tests use **mocked backend** - no real backend required
- Use `setupApiMocks()` or the auto-mocking fixture in `beforeEach`
- **Route registration order matters** - specific routes before general
- WebSocket connections are aborted by default to test disconnection
- Use `timeout: 15000` for initial page loads in CI environments
- Tests verify **UI behavior**, not implementation details
- Response shapes must match actual API schemas
- Camera snapshots return a transparent 1x1 PNG
- Page objects encapsulate all selectors - update there, not in specs

## Cross-Browser Testing

**Chromium** is the primary browser, with **Firefox** and **WebKit** as secondary:

- Secondary browsers run with `continue-on-error: true` in CI
- Firefox and WebKit have longer action timeouts (8s vs 5s)
- All browsers get 2 retries in CI to handle flaky tests
- Use `test.skip(browserName === 'webkit', 'reason')` for browser-specific skips
- Example skip pattern: `navigation.spec.ts` skips the 8-route sequential test on secondary browsers

**Known differences:**
- WebKit may render certain CSS differently
- Firefox has slightly different timing for animations
- WebSocket behavior may vary slightly between browsers

## Entry Points

1. **Fixtures**: `fixtures/index.ts` - Auto-mocking test function
2. **Page Objects**: `pages/BasePage.ts` - Common selectors/methods
3. **Simple Tests**: `specs/smoke.spec.ts` - Understand test patterns
4. **Configuration**: `/frontend/playwright.config.ts`

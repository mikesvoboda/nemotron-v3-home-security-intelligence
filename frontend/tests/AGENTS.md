# Frontend Tests Directory

## Purpose

Test suite directory for end-to-end (E2E) tests using Playwright and integration tests using Vitest. Unit tests are co-located with source files in `../src/`, not in this directory.

## Directory Structure

```
frontend/tests/
├── AGENTS.md           # This documentation file
├── contract/           # Contract tests for API validation
│   └── api-contract.spec.ts  # API contract validation tests
├── e2e/                # End-to-end Playwright tests
│   ├── AGENTS.md       # E2E test documentation
│   ├── fixtures/       # Test fixtures and mock configurations
│   │   ├── AGENTS.md   # Fixtures documentation
│   │   ├── index.ts    # Central fixture exports with auto-mocking
│   │   ├── api-mocks.ts    # API mock setup functions
│   │   ├── performance.ts  # Performance testing fixtures
│   │   ├── test-data.ts    # Mock data for cameras, events, GPU, etc.
│   │   └── websocket-mock.ts  # WebSocket simulation helpers
│   ├── pages/          # Page Object Model classes
│   │   ├── AGENTS.md   # Page objects documentation
│   │   ├── index.ts    # Central page object exports
│   │   ├── BasePage.ts # Base class for all page objects
│   │   ├── AIAuditPage.ts
│   │   ├── AIPerformancePage.ts
│   │   ├── AlertRulesPage.ts
│   │   ├── AlertsPage.ts
│   │   ├── AnalyticsPage.ts
│   │   ├── AuditPage.ts
│   │   ├── DashboardPage.ts
│   │   ├── EntitiesPage.ts
│   │   ├── JobsPage.ts
│   │   ├── LogsPage.ts
│   │   ├── SettingsPage.ts
│   │   ├── SystemPage.ts
│   │   ├── TimelinePage.ts
│   │   ├── TrashPage.ts
│   │   └── ZonesPage.ts
│   ├── specs/          # Test specification files (see AGENTS.md for full list)
│   │   ├── AGENTS.md   # Specs documentation
│   │   ├── smoke.spec.ts       # Dashboard loading and smoke tests
│   │   ├── dashboard.spec.ts   # Dashboard component tests
│   │   ├── ... (40+ spec files)
│   │   └── user-journeys/      # User journey subdirectory
│   ├── utils/          # Test utility functions
│   │   ├── AGENTS.md   # Utils documentation
│   │   ├── index.ts    # Central utility exports
│   │   ├── browser-helpers.ts
│   │   ├── data-generators.ts
│   │   ├── test-helpers.ts
│   │   └── wait-helpers.ts
│   ├── visual/         # Visual regression tests
│   │   ├── AGENTS.md   # Visual tests documentation
│   │   └── *.visual.spec.ts  # Visual regression specs
│   └── .gitkeep        # Git placeholder
└── integration/        # Integration tests (WebSocket, cross-component)
    ├── AGENTS.md       # Integration tests documentation
    └── websocket-performance.test.ts  # WebSocket performance metrics tests
```

## Test Organization

| Test Type       | Location             | Framework    | Purpose                          |
| --------------- | -------------------- | ------------ | -------------------------------- |
| **Unit**        | `../src/**/*.test.tsx` | Vitest + RTL | Component/function isolation     |
| **Integration** | `integration/`         | Vitest       | Cross-component, WebSocket tests |
| **E2E**         | `e2e/specs/`           | Playwright   | Full browser workflows           |

**Important**: Unit tests are NOT in this directory. They are co-located with source files (e.g., `../src/components/events/EventCard.test.tsx`).

## E2E Test Architecture

The E2E test suite follows the **Page Object Model** pattern:

1. **Fixtures** (`e2e/fixtures/`) - Reusable mock data and API mocking utilities
2. **Page Objects** (`e2e/pages/`) - Encapsulate page selectors and interactions
3. **Specs** (`e2e/specs/`) - Test specifications that use fixtures and page objects

### Benefits of This Architecture

- **Maintainability**: Selectors are centralized in page objects
- **Reusability**: Fixtures can be shared across tests
- **Readability**: Tests read like user stories
- **Isolation**: Mock configurations are configurable per test

## Integration Tests

The `integration/` directory contains tests that verify interactions between multiple components or systems:

| File                            | Description                                                 |
| ------------------------------- | ----------------------------------------------------------- |
| `websocket-performance.test.ts` | WebSocket message handling, performance metrics integration |

These tests use Vitest but test more complex scenarios than unit tests, such as WebSocket message flow and state management across components.

## Running Tests

```bash
# Unit tests (from frontend/)
npm test                    # Watch mode
npm test -- --run           # Single run (CI)
npm run test:coverage       # With coverage

# E2E tests (from frontend/)
npm run test:e2e            # Headless
npm run test:e2e:headed     # With browser visible
npm run test:e2e:debug      # Debug mode
npm run test:e2e:report     # View HTML report

# Run specific E2E spec
npx playwright test specs/dashboard.spec.ts
npx playwright test specs/smoke.spec.ts
```

## Coverage Requirements

Coverage thresholds are configured in `vite.config.ts`:

| Metric     | Threshold |
| ---------- | --------- |
| Statements | 83%       |
| Branches   | 77%       |
| Functions  | 81%       |
| Lines      | 84%       |

## Related Documentation

- `/frontend/tests/e2e/AGENTS.md` - E2E test overview
- `/frontend/tests/e2e/fixtures/AGENTS.md` - Fixture documentation
- `/frontend/tests/e2e/pages/AGENTS.md` - Page object documentation
- `/frontend/tests/e2e/specs/AGENTS.md` - Test spec documentation
- `/frontend/tests/integration/AGENTS.md` - Integration test documentation
- `/frontend/src/test/AGENTS.md` - Test setup configuration
- `/frontend/vite.config.ts` - Vitest configuration
- `/frontend/playwright.config.ts` - Playwright configuration

## Notes for AI Agents

- Unit tests are co-located with source files, not here
- E2E tests follow the Page Object Model pattern
- All E2E tests mock backend endpoints via Playwright route interception
- Test setup is in `../src/test/setup.ts`
- E2E tests are excluded from Vitest runs via `vite.config.ts` exclude pattern
- Use fixtures from `e2e/fixtures/` instead of duplicating mock data
- Use page objects from `e2e/pages/` for consistent selectors

## Entry Points

1. **E2E Fixtures**: `e2e/fixtures/` - Start here to understand mock data
2. **Page Objects**: `e2e/pages/BasePage.ts` - Base class for page interactions
3. **Test Specs**: `e2e/specs/smoke.spec.ts` - Simple tests to understand patterns
4. **Integration**: `integration/websocket-performance.test.ts` - WebSocket flow tests
5. **Configuration**: `playwright.config.ts` in frontend root
6. **Unit tests**: Look in `src/**/*.test.ts` (co-located with source)

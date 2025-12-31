# Frontend Tests Directory

## Purpose

Test suite directory for end-to-end (E2E) tests using Playwright. Unit tests are co-located with source files in `src/`, not in this directory.

## Directory Structure

```
frontend/tests/
├── AGENTS.md        # This documentation file
├── e2e/             # End-to-end Playwright tests
│   ├── AGENTS.md    # E2E test documentation
│   ├── smoke.spec.ts       # Dashboard loading and smoke tests
│   ├── navigation.spec.ts  # Page navigation tests
│   ├── realtime.spec.ts    # Real-time/WebSocket tests
│   └── .gitkeep            # Git placeholder
└── integration/     # Integration tests (WebSocket, cross-component)
    └── websocket-performance.test.ts  # WebSocket performance metrics tests
```

## Test Organization

| Test Type       | Location             | Framework    | Purpose                          |
| --------------- | -------------------- | ------------ | -------------------------------- |
| **Unit**        | `src/**/*.test.tsx`  | Vitest + RTL | Component/function isolation     |
| **Integration** | `tests/integration/` | Vitest       | Cross-component, WebSocket tests |
| **E2E**         | `tests/e2e/`         | Playwright   | Full browser workflows           |

**Important**: Unit tests are NOT in this directory. They are co-located with source files (e.g., `src/components/events/EventCard.test.tsx`).

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
```

## Coverage Requirements

Coverage thresholds are configured in `vite.config.ts`:

| Metric     | Threshold |
| ---------- | --------- |
| Statements | 89%       |
| Branches   | 86%       |
| Functions  | 85%       |
| Lines      | 90%       |

Note: Thresholds temporarily lowered due to SearchBar test isolation issue. See `vite.config.ts` for details.

## Related Documentation

- `/frontend/tests/e2e/AGENTS.md` - E2E test details
- `/frontend/src/test/AGENTS.md` - Test setup configuration
- `/frontend/vite.config.ts` - Vitest configuration
- `/frontend/playwright.config.ts` - Playwright configuration

## Notes for AI Agents

- Unit tests are co-located with source files, not here
- This directory is specifically for E2E browser tests
- E2E tests mock all backend endpoints via Playwright route interception
- Test setup is in `src/test/setup.ts`
- E2E tests are excluded from Vitest runs via `vite.config.ts`

## Entry Points

1. **E2E tests**: `e2e/` directory contains Playwright browser tests
2. **Integration tests**: `integration/` directory contains cross-component tests
3. **Configuration**: `playwright.config.ts` in frontend root
4. **Unit tests**: Look in `src/**/*.test.ts` (co-located with source)

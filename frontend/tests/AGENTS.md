# Frontend Tests Directory

## Purpose

Test suite directory for integration and end-to-end tests. This directory complements the co-located unit tests that live alongside source files in `src/`.

## Current Status

**Status**: Placeholder for future test organization

Currently contains:

- `AGENTS.md` - This documentation file
- `e2e/` - End-to-end test directory (see `e2e/AGENTS.md`)

**Important**: Unit tests are co-located with source files (e.g., `src/components/events/EventCard.test.tsx`), NOT in this directory. This directory is reserved for integration and E2E tests that require multi-component or full-stack setups.

## Intended Structure

This directory is planned for integration and E2E tests that require full system setup:

## Planned Organization

```
frontend/tests/
├── integration/       # Integration tests
│   ├── api/          # API integration tests
│   ├── components/   # Multi-component tests
│   └── workflows/    # User workflow tests
├── fixtures/         # Test data and mocks
│   ├── cameras.json
│   ├── events.json
│   └── system.json
├── helpers/          # Test utilities
│   ├── render.ts     # Custom render functions
│   ├── mocks.ts      # Mock factories
│   └── server.ts     # MSW server setup
└── e2e/              # End-to-end tests (see e2e/AGENTS.md)
```

## Integration Tests

### Purpose

Test interactions between multiple components or modules:

- API client + React hooks
- Component compositions
- State management flows
- WebSocket + UI updates

### Example Integration Test

```typescript
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

describe('Camera List Integration', () => {
  const server = setupServer(
    http.get('/api/cameras', () => {
      return HttpResponse.json([
        { id: '1', name: 'Front Door', status: 'active' },
      ]);
    })
  );

  beforeAll(() => server.listen());
  afterAll(() => server.close());

  it('fetches and displays cameras', async () => {
    render(<CameraListPage />);

    await waitFor(() => {
      expect(screen.getByText('Front Door')).toBeInTheDocument();
    });
  });
});
```

## Test Fixtures

### Purpose

Reusable test data matching API response shapes:

```typescript
// fixtures/cameras.ts
export const mockCameras: Camera[] = [
  {
    id: '1',
    name: 'Front Door',
    folder_path: '/export/foscam/front_door',
    status: 'active',
    created_at: '2024-01-01T00:00:00Z',
    last_seen_at: '2024-01-01T12:00:00Z',
  },
  // ...
];

// fixtures/events.ts
export const mockEvents: SecurityEvent[] = [
  {
    id: 'evt-1',
    camera_id: '1',
    camera_name: 'Front Door',
    risk_score: 75,
    risk_level: 'high',
    summary: 'Unknown person detected',
    timestamp: '2024-01-01T12:00:00Z',
  },
  // ...
];
```

## Test Helpers

### Custom Render Functions

```typescript
// helpers/render.tsx
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

export function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  );
}
```

### Mock Factories

```typescript
// helpers/mocks.ts
export function createMockCamera(overrides?: Partial): Camera {
  return {
    id: 'cam-1',
    name: 'Test Camera',
    folder_path: '/test',
    status: 'active',
    created_at: new Date().toISOString(),
    last_seen_at: new Date().toISOString(),
    ...overrides,
  };
}
```

## Running Tests

```bash
# Unit tests (co-located in src/)
npm test

# Specific test file
npm test -- Layout.test.tsx

# Integration tests (when implemented)
npm test tests/integration

# All tests with coverage
npm run test:coverage

# Watch mode (default)
npm test

# Single run (for CI)
npm test -- --run
```

## Test Types Comparison

| Test Type       | Location             | Purpose                        | Status         |
| --------------- | -------------------- | ------------------------------ | -------------- |
| **Unit**        | `src/**/*.test.tsx`  | Component/function isolation   | Implemented    |
| **Integration** | `tests/integration/` | Multi-component interactions   | Planned        |
| **E2E**         | `tests/e2e/`         | Full user workflows in browser | Planned        |

### Current Unit Test Coverage

The project has extensive unit test coverage for:

- **Components**: All major components have co-located test files
  - Dashboard: `DashboardPage`, `RiskGauge`, `CameraGrid`, `ActivityFeed`, `GpuStats`, `StatsRow`
  - Events: `EventCard`, `EventTimeline`, `EventDetailModal`, `ThumbnailStrip`
  - Logs: `LogsDashboard`, `LogsTable`, `LogFilters`, `LogDetailModal`, `LogStatsCards`
  - Settings: `SettingsPage`, `CamerasSettings`, `AIModelsSettings`, `ProcessingSettings`
  - Common: `RiskBadge`, `ObjectTypeBadge`
  - Layout: `Header`, `Layout`, `Sidebar`
- **Hooks**: `useWebSocket`, `useEventStream`, `useSystemStatus`
- **Services**: `api.ts` API client
- **Utilities**: `risk.ts`, `time.ts`

## When to Use This Directory

- **DON'T** put unit tests here - they belong alongside source files in `src/`
- **DO** put integration tests that span multiple modules
- **DO** put shared test fixtures and helpers
- **DO** put E2E tests in `tests/e2e/` subdirectory

## Related Documentation

- See `../TESTING.md` for comprehensive testing documentation
- See `../src/test/AGENTS.md` for test setup configuration
- See `e2e/AGENTS.md` for E2E test planning

## Notes for AI Agents

- Unit tests are NOT in this directory - they're co-located with source files
- This directory is for future integration and E2E test organization
- MSW (Mock Service Worker) should be used for API mocking in integration tests
- Fixtures should match backend API response shapes exactly
- Global test setup is in `src/test/setup.ts`, not here
- Current test coverage is focused on unit tests in `src/`

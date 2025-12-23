# Frontend Tests Directory

## Purpose

Test suite directory for integration and end-to-end tests.

## Structure

This directory is currently a placeholder for future test organization. It's intended for:

1. **Integration Tests**: Multi-component interactions
2. **End-to-End Tests**: Full user flows
3. **Test Fixtures**: Shared test data and mocks
4. **Test Helpers**: Reusable test utilities

## Current Status

Directory contains only `.gitkeep` file to maintain directory structure in version control.

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
# Unit tests (in src/)
npm test

# Integration tests (when implemented)
npm test tests/integration

# All tests
npm test

# With coverage
npm test -- --coverage
```

## Notes

- Unit tests live alongside source files (`src/**/*.test.ts`)
- Integration tests live in this directory (`tests/integration/`)
- E2E tests have dedicated subdirectory (`tests/e2e/`)
- Use MSW (Mock Service Worker) for API mocking
- Fixtures should match backend API response shapes
- Test setup from `src/test/setup.ts` applies globally

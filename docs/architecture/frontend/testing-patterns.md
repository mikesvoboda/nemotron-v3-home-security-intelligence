# Testing Patterns

> Vitest configuration, React Testing Library patterns, and MSW mock handlers

## Key Files

- `frontend/vite.config.ts:182-230` - Vitest configuration
- `frontend/src/test/setup.ts:1-177` - Test environment setup
- `frontend/src/test/common-mocks.ts:1-168` - Shared mock utilities
- `frontend/src/mocks/handlers.ts:1-150` - MSW mock handlers
- `frontend/src/test-utils/renderWithProviders.tsx:1-80` - Test render helpers

## Overview

The frontend testing infrastructure uses Vitest for unit and integration tests, React Testing Library for component testing, and MSW (Mock Service Worker) for API mocking. The test setup emphasizes memory safety, proper cleanup, and maintainability through standardized patterns.

## Test Configuration

### Vitest Configuration

From `frontend/vite.config.ts:182-236`:

```typescript
test: {
  globals: true,
  environment: 'jsdom',
  setupFiles: './src/test/setup.ts',
  css: true,
  exclude: ['**/node_modules/**', '**/dist/**', 'tests/e2e/**', 'tests/contract/**'],

  // Fork-based parallelization for memory isolation
  pool: 'forks',
  fileParallelism: false, // Sequential within shards
  isolate: true, // Restart worker per file

  // Timeouts
  testTimeout: 30000,
  hookTimeout: 30000,
  teardownTimeout: 3000,

  coverage: {
    provider: 'v8',
    reporter: ['text', 'json', 'html'],
    thresholds: {
      statements: 83,
      branches: 77,
      functions: 81,
      lines: 84,
    },
  },
},
```

### Coverage Thresholds

| Metric     | Threshold | CI Enforcement |
| ---------- | --------- | -------------- |
| Statements | 83%       | Gate           |
| Branches   | 77%       | Gate           |
| Functions  | 81%       | Gate           |
| Lines      | 84%       | Gate           |

## Test Setup

### Global Setup (`frontend/src/test/setup.ts`)

```typescript
// frontend/src/test/setup.ts:1-24
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterAll, afterEach, beforeAll, vi } from 'vitest';

import { resetCounter } from './factories';
import { server } from '../mocks/server';

// Re-export mock utilities for test files
export {
  createRouterMock,
  createApiMock,
  createWebSocketMock,
  testQueryClientOptions,
  FAST_TIMEOUT,
  STANDARD_TIMEOUT,
} from './common-mocks';
```

### Browser API Mocks

```typescript
// frontend/src/test/setup.ts:44-88
beforeAll(() => {
  // Mock ResizeObserver (required by Headless UI)
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };

  // Mock matchMedia (required for responsive components)
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });

  // Mock IntersectionObserver (required for infinite scroll)
  globalThis.IntersectionObserver = class IntersectionObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords() {
      return [];
    }
  };

  // Start MSW server
  server.listen({ onUnhandledRequest: 'bypass' });
});
```

### Cleanup After Each Test

```typescript
// frontend/src/test/setup.ts:119-154
afterEach(() => {
  // Clean up React Testing Library
  cleanup();

  // Clear localStorage
  localStorage.clear();

  // Reset MSW handlers
  server.resetHandlers();

  // Clear all mocks
  vi.clearAllMocks();
  vi.clearAllTimers();
  vi.useRealTimers();
  vi.unstubAllGlobals();

  // Reset factory counter
  resetCounter();

  // Force garbage collection if available
  if (typeof globalThis.gc === 'function') {
    globalThis.gc();
  }
});
```

## Mock Utilities

### Router Mock

```typescript
// frontend/src/test/common-mocks.ts:26-36
export const createRouterMock = (mockNavigate = vi.fn()) => ({
  useNavigate: () => mockNavigate,
  useLocation: () => ({ pathname: '/', search: '', hash: '', state: null }),
  useParams: () => ({}),
  BrowserRouter: ({ children }) => children,
  Routes: ({ children }) => children,
  Route: ({ element }) => element,
  Link: ({ children }) => children,
  NavLink: ({ children }) => children,
  Outlet: () => null,
});
```

### API Mock

```typescript
// frontend/src/test/common-mocks.ts:54-63
export const createApiMock = (overrides = {}) => ({
  fetchCameras: vi.fn().mockResolvedValue([]),
  fetchEvents: vi.fn().mockResolvedValue([]),
  fetchAlerts: vi.fn().mockResolvedValue([]),
  fetchDetections: vi.fn().mockResolvedValue([]),
  fetchEntities: vi.fn().mockResolvedValue([]),
  fetchSystemHealth: vi.fn().mockResolvedValue({ status: 'healthy' }),
  fetchGpuStats: vi.fn().mockResolvedValue({ utilization: 0 }),
  ...overrides,
});
```

### WebSocket Mock

```typescript
// frontend/src/test/common-mocks.ts:81-90
export const createWebSocketMock = (overrides = {}) => ({
  connect: vi.fn(),
  disconnect: vi.fn(),
  subscribe: vi.fn(),
  unsubscribe: vi.fn(),
  send: vi.fn(),
  on: vi.fn(),
  off: vi.fn(),
  ...overrides,
});
```

### Query Client Options

```typescript
// frontend/src/test/common-mocks.ts:98-109
export const testQueryClientOptions = {
  defaultOptions: {
    queries: {
      retry: false, // Disable retries for faster tests
      staleTime: 0,
      gcTime: 0,
    },
    mutations: {
      retry: false,
    },
  },
};
```

## Component Testing Patterns

### renderWithProviders

Custom render function that wraps components with necessary providers:

```typescript
// frontend/src/test-utils/renderWithProviders.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, RenderOptions } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';

export function renderWithProviders(
  ui: React.ReactElement,
  options?: RenderOptions
) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: 0 },
      mutations: { retry: false },
    },
  });

  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {children}
      </BrowserRouter>
    </QueryClientProvider>
  );

  return {
    user: userEvent.setup(),
    ...render(ui, { wrapper: Wrapper, ...options }),
  };
}
```

### Component Test Structure

```typescript
// frontend/src/components/dashboard/DashboardPage.test.tsx:276-290
describe('DashboardPage', () => {
  const mockCameras = [/* test data */];

  beforeEach(() => {
    vi.clearAllMocks();
    // Setup default mock implementations
    (api.fetchCameras as Mock).mockResolvedValue(mockCameras);
    (useEventStreamHook.useEventStream as Mock).mockReturnValue({
      events: [],
      isConnected: true,
    });
  });

  describe('Loading State', () => {
    it('renders loading skeletons while fetching data', () => {
      (api.fetchCameras as Mock).mockImplementation(() => new Promise(() => {}));
      renderWithProviders(<DashboardPage />);
      expect(screen.getAllByTestId('stats-card-skeleton')).toHaveLength(4);
    });
  });

  describe('Successful Render', () => {
    it('renders dashboard header', async () => {
      renderWithProviders(<DashboardPage />);
      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /security dashboard/i }))
          .toBeInTheDocument();
      });
    });
  });
});
```

### Mocking Child Components

```typescript
// frontend/src/components/dashboard/DashboardPage.test.tsx:42-67
vi.mock('./StatsRow', () => ({
  default: ({
    activeCameras,
    eventsToday,
    currentRiskScore,
    systemStatus,
  }: Props) => (
    <div
      data-testid="stats-row"
      data-active-cameras={activeCameras}
      data-events-today={eventsToday}
      data-risk-score={currentRiskScore}
      data-system-status={systemStatus}
    >
      Stats Row
    </div>
  ),
}));
```

### Mocking Hooks

```typescript
// frontend/src/components/dashboard/DashboardPage.test.tsx:28-39
vi.mock('../../hooks/useEventStream', () => ({
  useEventStream: vi.fn(),
}));

// In test setup
(useEventStreamHook.useEventStream as Mock).mockReturnValue({
  events: mockWsEvents,
  isConnected: true,
  latestEvent: mockWsEvents[0],
  clearEvents: vi.fn(),
});
```

## Testing Hooks

### Hook Test Pattern

```typescript
import { renderHook, waitFor } from '@testing-library/react';
import { useEventStream } from './useEventStream';

// Wrapper with providers
const wrapper = ({ children }) => (
  <QueryClientProvider client={queryClient}>
    {children}
  </QueryClientProvider>
);

describe('useEventStream', () => {
  it('returns initial state', () => {
    const { result } = renderHook(() => useEventStream(), { wrapper });

    expect(result.current.events).toEqual([]);
    expect(result.current.isConnected).toBe(false);
  });

  it('updates state on WebSocket message', async () => {
    const { result } = renderHook(() => useEventStream(), { wrapper });

    // Trigger WebSocket message
    act(() => {
      mockWebSocket.emit('message', { type: 'event', data: mockEvent });
    });

    await waitFor(() => {
      expect(result.current.events).toHaveLength(1);
    });
  });
});
```

## MSW (Mock Service Worker)

### Handler Setup

```typescript
// frontend/src/mocks/handlers.ts
import { http, HttpResponse } from 'msw';

export const handlers = [
  // Health endpoint
  http.get('/api/health', () => {
    return HttpResponse.json({
      status: 'healthy',
      services: { database: 'ok', redis: 'ok', gpu: 'ok' },
    });
  }),

  // Cameras endpoint
  http.get('/api/cameras', () => {
    return HttpResponse.json([
      { id: 'cam-1', name: 'Front Door', status: 'online' },
      { id: 'cam-2', name: 'Back Yard', status: 'online' },
    ]);
  }),

  // Events with pagination
  http.get('/api/events', ({ request }) => {
    const url = new URL(request.url);
    const limit = parseInt(url.searchParams.get('limit') || '20');

    return HttpResponse.json({
      items: mockEvents.slice(0, limit),
      pagination: { total: mockEvents.length, limit, offset: 0 },
    });
  }),
];
```

### Per-Test Handler Override

```typescript
import { server } from '../mocks/server';
import { http, HttpResponse } from 'msw';

it('handles API error gracefully', async () => {
  // Override handler for this test only
  server.use(
    http.get('/api/cameras', () => {
      return HttpResponse.json(
        { error: 'Server error' },
        { status: 500 }
      );
    })
  );

  renderWithProviders(<CameraList />);

  await waitFor(() => {
    expect(screen.getByText(/error loading cameras/i)).toBeInTheDocument();
  });
});
```

## Testing User Interactions

### userEvent Setup

```typescript
// Using userEvent from renderWithProviders
it('navigates on camera click', async () => {
  const { user } = renderWithProviders(<DashboardPage />);

  await waitFor(() => {
    expect(screen.getByTestId('camera-grid')).toBeInTheDocument();
  });

  // Click camera card
  const cameraButton = screen.getByRole('button', { name: 'Front Door' });
  await user.click(cameraButton);

  expect(mockNavigate).toHaveBeenCalledWith('/timeline?camera=cam-1');
});
```

### Keyboard Interaction

```typescript
it('opens command palette with Cmd+K', async () => {
  const { user } = renderWithProviders(<App />);

  await user.keyboard('{Meta>}k{/Meta}');

  await waitFor(() => {
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });
});
```

## Async Testing Patterns

### waitFor Usage

```typescript
// Wait for element to appear
await waitFor(() => {
  expect(screen.getByTestId('stats-row')).toBeInTheDocument();
});

// Wait with custom timeout
await waitFor(() => expect(screen.getByText('Loaded')).toBeInTheDocument(), { timeout: 3000 });

// Wait for element to disappear
await waitFor(() => {
  expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
});
```

### findBy Queries

```typescript
// findBy = getBy + waitFor
const header = await screen.findByRole('heading', { name: /dashboard/i });
expect(header).toBeInTheDocument();
```

## Timeout Constants

```typescript
// frontend/src/test/common-mocks.ts:152-168
// Fast timeout for fully mocked components
export const FAST_TIMEOUT = { timeout: 300 };

// Standard timeout for real async operations
export const STANDARD_TIMEOUT = { timeout: 1000 };
```

## Best Practices

### Test Organization

```
Component.test.tsx
  describe('ComponentName')
    describe('Loading State')
    describe('Error State')
    describe('Successful Render')
    describe('User Interactions')
    describe('Edge Cases')
```

### Naming Conventions

- Test files: `*.test.tsx` or `*.test.ts`
- Test IDs: `data-testid="component-name"` or `data-testid="component-name-action"`
- Mock files: `*.mock.ts`

### Avoiding Common Pitfalls

1. **Always clean up**: Use `afterEach` cleanup
2. **Reset mocks**: Call `vi.clearAllMocks()` between tests
3. **Avoid act warnings**: Use `userEvent` instead of `fireEvent`
4. **Memory management**: Use fork-based pool, not threads
5. **Deterministic tests**: Mock timers and dates when needed

### Testing Accessibility

```typescript
it('has accessible heading structure', async () => {
  renderWithProviders(<DashboardPage />);

  const h1 = await screen.findByRole('heading', { level: 1 });
  expect(h1).toHaveTextContent('Security Dashboard');

  const h2s = screen.getAllByRole('heading', { level: 2 });
  expect(h2s.length).toBeGreaterThan(0);
});

it('has accessible labels for interactive elements', () => {
  renderWithProviders(<CameraCard camera={mockCamera} />);

  const button = screen.getByRole('button');
  expect(button).toHaveAccessibleName();
});
```

## Running Tests

```bash
# Run all tests
cd frontend && npm test

# Run with coverage
cd frontend && npm test -- --coverage

# Run specific file
cd frontend && npm test -- DashboardPage

# Run in watch mode
cd frontend && npm test -- --watch

# Run with verbose output
cd frontend && npm test -- --reporter=verbose
```

## Related Documentation

- [Custom Hooks](./custom-hooks.md) - Hook testing patterns
- [Component Hierarchy](./component-hierarchy.md) - Component structure
- [Testing Guide](../../development/testing.md) - Project-wide testing docs

---

_Last updated: 2026-01-24 - Initial testing patterns documentation for NEM-3462_

# Frontend Test Optimization Guide

This guide documents patterns and techniques for optimizing frontend unit test execution time in CI/CD.

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [waitFor() Timeout Optimization](#waitfor-timeout-optimization)
3. [Fake Timers Best Practices](#fake-timers-best-practices)
4. [Shared Mock Utilities](#shared-mock-utilities)
5. [Component Testing Strategies](#component-testing-strategies)

## Quick Reference

### Common Optimizations

```typescript
// ✅ GOOD: Fast timeout for mocked components
import { FAST_TIMEOUT } from '@/test/setup';

await waitFor(
  () => expect(screen.getByTestId('mock-component')).toBeInTheDocument(),
  FAST_TIMEOUT // 300ms instead of 1000ms default
);

// ❌ BAD: Using default 1000ms timeout for mocked components
await waitFor(() => {
  expect(screen.getByTestId('mock-component')).toBeInTheDocument();
});

// ✅ GOOD: Standard timeout for real async operations
import { STANDARD_TIMEOUT } from '@/test/setup';

await waitFor(
  () => expect(screen.getByText('Data loaded')).toBeInTheDocument(),
  STANDARD_TIMEOUT // 1000ms for real network/async operations
);
```

### Fake Timers Setup

```typescript
beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  vi.useRealTimers();
});
```

## waitFor() Timeout Optimization

### Problem

The default `waitFor()` timeout is 1000ms (1 second). When testing components with mocked dependencies that resolve synchronously or near-instantly, this timeout is excessive and adds unnecessary wait time to test execution.

**Impact**: With 176+ files using `waitFor()` and ~5-10 calls per file, reducing timeout from 1000ms to 300ms can save **10-20+ seconds per test suite** in CI.

### Solution

Use `FAST_TIMEOUT` for mocked components and `STANDARD_TIMEOUT` for real async operations.

### When to Use FAST_TIMEOUT (300ms)

- Component renders with mocked dependencies
- API calls mocked with `vi.mock()` or MSW handlers
- Lazy-loaded components that are mocked
- State updates triggered by mocked timers
- Form validation with synchronous validators
- UI elements that appear after mocked async operations

**Examples**:

```typescript
// Mocked component rendering
await waitFor(
  () => expect(screen.getByTestId('mock-layout')).toBeInTheDocument(),
  FAST_TIMEOUT
);

// Mocked API response
vi.mocked(api.fetchCameras).mockResolvedValue([mockCamera]);
render(<CameraList />);
await waitFor(
  () => expect(screen.getByText('Camera 1')).toBeInTheDocument(),
  FAST_TIMEOUT
);

// Lazy component with mocked import
vi.mock('./DashboardPage', () => ({
  default: () => <div data-testid="mock-dashboard">Dashboard</div>
}));
await waitFor(
  () => expect(screen.getByTestId('mock-dashboard')).toBeInTheDocument(),
  FAST_TIMEOUT
);
```

### When to Use STANDARD_TIMEOUT (1000ms)

- Real network requests (not mocked)
- Integration tests with actual async operations
- Tests involving debounced/throttled operations
- Tests with complex React render cycles
- Tests using `act()` with multiple state updates

**Examples**:

```typescript
// Real API call (integration test)
render(<DataFetcher />);
await waitFor(
  () => expect(screen.getByText('Real data')).toBeInTheDocument(),
  STANDARD_TIMEOUT
);

// Debounced input (500ms debounce)
await user.type(input, 'search query');
await waitFor(
  () => expect(api.search).toHaveBeenCalledWith('search query'),
  STANDARD_TIMEOUT
);

// Complex state updates with multiple useEffects
render(<ComplexStatefulComponent />);
await waitFor(
  () => expect(screen.getByText('Final state')).toBeInTheDocument(),
  STANDARD_TIMEOUT
);
```

### Migration Pattern

Before:

```typescript
await waitFor(() => {
  expect(screen.getByText('Loaded')).toBeInTheDocument();
});
```

After:

```typescript
import { FAST_TIMEOUT } from '@/test/setup';

await waitFor(() => expect(screen.getByText('Loaded')).toBeInTheDocument(), FAST_TIMEOUT);
```

## Fake Timers Best Practices

### Problem

Tests using `setTimeout`, `setInterval`, or other timer APIs can cause:

- Slow test execution (waiting for real timers)
- Flaky tests (race conditions with real timers)
- Memory leaks (timers not cleaned up)

### Solution

Use Vitest fake timers with proper setup and cleanup.

### Standard Pattern

```typescript
import { describe, it, beforeEach, afterEach, vi } from 'vitest';

describe('Component with timers', () => {
  beforeEach(() => {
    // Enable fake timers before each test
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    // Restore real timers after each test
    vi.useRealTimers();
  });

  it('handles timer-based logic', () => {
    render(<TimerComponent />);

    // Advance time by 1000ms
    vi.advanceTimersByTime(1000);

    expect(screen.getByText('Timer fired')).toBeInTheDocument();
  });
});
```

### With userEvent

```typescript
const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

await user.click(button);
// Timers advance automatically with userEvent interactions
```

### Common Timer Patterns

```typescript
// Debounced input
it('debounces search input', async () => {
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  render(<SearchInput />);

  await user.type(input, 'query');
  vi.advanceTimersByTime(500); // Advance past debounce

  await waitFor(
    () => expect(api.search).toHaveBeenCalledWith('query'),
    FAST_TIMEOUT
  );
});

// Polling interval
it('polls for updates', async () => {
  render(<PollingComponent />);

  vi.advanceTimersByTime(5000); // Advance 5 seconds

  await waitFor(
    () => expect(api.fetchUpdates).toHaveBeenCalledTimes(2),
    FAST_TIMEOUT
  );
});

// Auto-refresh
it('auto-refreshes after timeout', async () => {
  render(<AutoRefreshComponent />);

  vi.advanceTimersByTime(60000); // Advance 1 minute

  await waitFor(
    () => expect(screen.getByText('Refreshed')).toBeInTheDocument(),
    FAST_TIMEOUT
  );
});
```

## Shared Mock Utilities

### Available Utilities

```typescript
import {
  createRouterMock,
  createApiMock,
  createWebSocketMock,
  createQueryClientMock,
  createLayoutMock,
  FAST_TIMEOUT,
  STANDARD_TIMEOUT,
} from '@/test/setup';
```

### Router Mocking

```typescript
// Basic router mock
vi.mock('react-router-dom', () => createRouterMock());

// Custom navigate function
const mockNavigate = vi.fn();
vi.mock('react-router-dom', () => createRouterMock(mockNavigate));

// In test
await user.click(button);
expect(mockNavigate).toHaveBeenCalledWith('/dashboard');
```

### API Mocking

```typescript
// Basic API mock
const api = createApiMock();

// Partial override
const api = createApiMock({
  fetchCameras: vi.fn().mockResolvedValue([mockCamera]),
});

// Test-specific behavior
it('handles API error', async () => {
  const api = createApiMock({
    fetchCameras: vi.fn().mockRejectedValue(new Error('Network error')),
  });

  render(<CameraList api={api} />);

  await waitFor(
    () => expect(screen.getByText('Network error')).toBeInTheDocument(),
    FAST_TIMEOUT
  );
});
```

### WebSocket Mocking

```typescript
const ws = createWebSocketMock();

// Test connection
it('connects to WebSocket', () => {
  render(<RealtimeComponent ws={ws} />);
  expect(ws.connect).toHaveBeenCalled();
});

// Test message handling
it('handles WebSocket messages', () => {
  const ws = createWebSocketMock();
  const onMessage = vi.fn();

  render(<RealtimeComponent ws={ws} onMessage={onMessage} />);

  // Simulate incoming message
  ws.on.mock.calls[0][1]({ type: 'update', data: { value: 42 } });

  expect(onMessage).toHaveBeenCalledWith({ value: 42 });
});
```

### React Query Mocking

```typescript
import { QueryClientProvider } from '@tanstack/react-query';

const queryClient = createQueryClientMock();

render(
  <QueryClientProvider client={queryClient}>
    <MyComponent />
  </QueryClientProvider>
);
```

## Component Testing Strategies

### Test Isolation

**Prefer**: Testing components in isolation with mocked dependencies
**Avoid**: Full app integration in unit tests (use E2E tests instead)

```typescript
// ✅ GOOD: Isolated component test
describe('DashboardPage', () => {
  it('renders dashboard content', async () => {
    vi.mock('@/services/api', () => createApiMock({
      fetchStats: vi.fn().mockResolvedValue(mockStats),
    }));

    render(<DashboardPage />);

    await waitFor(
      () => expect(screen.getByText('Total Events: 42')).toBeInTheDocument(),
      FAST_TIMEOUT
    );
  });
});

// ❌ BAD: Full app render in unit test
describe('DashboardPage', () => {
  it('renders dashboard content', async () => {
    render(<App />); // Renders entire app, slows down test

    await user.click(screen.getByText('Dashboard'));

    await waitFor(() => {
      expect(screen.getByText('Total Events: 42')).toBeInTheDocument();
    }); // Default 1000ms timeout
  });
});
```

### Route Testing

Instead of rendering `<App />` multiple times, test routes in isolation:

```typescript
// ❌ BAD: Rendering full app 5 times
describe('App routing', () => {
  it('shows dashboard page', async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByTestId('dashboard')).toBeInTheDocument());
  });

  it('shows settings page', async () => {
    render(<App />);
    await user.click(screen.getByText('Settings'));
    await waitFor(() => expect(screen.getByTestId('settings')).toBeInTheDocument());
  });

  // ... 3 more similar tests
});

// ✅ GOOD: Test route behavior, not full app rendering
describe('Dashboard route', () => {
  it('renders dashboard content', async () => {
    renderWithProviders(<DashboardPage />, {
      route: '/dashboard',
    });

    await waitFor(
      () => expect(screen.getByTestId('dashboard')).toBeInTheDocument(),
      FAST_TIMEOUT
    );
  });
});

describe('Settings route', () => {
  it('renders settings content', async () => {
    renderWithProviders(<SettingsPage />, {
      route: '/settings',
    });

    await waitFor(
      () => expect(screen.getByTestId('settings')).toBeInTheDocument(),
      FAST_TIMEOUT
    );
  });
});
```

### Lazy Loading Tests

```typescript
// Test lazy loading behavior separately from app routing
describe('Lazy component loading', () => {
  it('shows loading fallback during import', async () => {
    let resolveImport: (value: any) => void;
    const LazyComponent = lazy(() => new Promise(resolve => {
      resolveImport = resolve;
    }));

    render(
      <Suspense fallback={<div>Loading...</div>}>
        <LazyComponent />
      </Suspense>
    );

    expect(screen.getByText('Loading...')).toBeInTheDocument();

    resolveImport!({ default: () => <div>Loaded</div> });

    await waitFor(
      () => expect(screen.getByText('Loaded')).toBeInTheDocument(),
      FAST_TIMEOUT
    );
  });
});
```

## Performance Metrics

### Expected Improvements

After applying these optimizations:

| Optimization    | Files Affected | Time Saved per File | Total Impact  |
| --------------- | -------------- | ------------------- | ------------- |
| FAST_TIMEOUT    | 176+           | ~0.5-1s per file    | 88-176s total |
| Fake timers     | 67+            | ~0.2-0.5s per file  | 13-34s total  |
| Route isolation | App tests      | ~2-3s per test      | 10-15s total  |

**Total estimated CI time reduction: 111-225 seconds (1.8-3.7 minutes)**

### Measuring Impact

```bash
# Before optimization
npm test -- --run | grep "Duration"
# Duration 4.20s

# After optimization (expected)
npm test -- --run | grep "Duration"
# Duration 2.50s (40% faster)
```

## Migration Checklist

### For Each Test File

- [ ] Add `import { FAST_TIMEOUT } from '@/test/setup';`
- [ ] Review each `waitFor()` call:
  - [ ] Mocked components/APIs → `FAST_TIMEOUT`
  - [ ] Real async operations → `STANDARD_TIMEOUT`
- [ ] Check for timer usage (`setTimeout`, `setInterval`)
  - [ ] Add `beforeEach(() => vi.useFakeTimers())`
  - [ ] Add `afterEach(() => vi.useRealTimers())`
- [ ] Replace custom mocks with shared utilities
  - [ ] Router mocks → `createRouterMock()`
  - [ ] API mocks → `createApiMock()`
  - [ ] WebSocket mocks → `createWebSocketMock()`
- [ ] Run tests to verify optimization doesn't break behavior
- [ ] Commit with clear message: `test: optimize [component] test execution time`

## Troubleshooting

### Test Fails with FAST_TIMEOUT

If a test fails after adding `FAST_TIMEOUT`, it may indicate:

1. **Component not fully mocked**: Check for unmocked dependencies
2. **Real async operation**: Use `STANDARD_TIMEOUT` instead
3. **Complex render cycle**: Component may need more time to settle

**Solution**: Use `STANDARD_TIMEOUT` or increase timeout for specific test.

### Timer-based Test Flakes

If fake timers cause flaky tests:

1. **Verify `shouldAdvanceTime: true`** is set in `vi.useFakeTimers()`
2. **Check cleanup**: Ensure `vi.useRealTimers()` is called in `afterEach()`
3. **Advance timers correctly**: Use `vi.advanceTimersByTime()` instead of `vi.runAllTimers()`

### Memory Leaks After Fake Timers

If tests hang or memory grows:

1. **Always restore timers**: Add `vi.useRealTimers()` in `afterEach()`
2. **Clear pending timers**: Call `vi.clearAllTimers()` in `afterEach()`
3. **Verify cleanup**: Check `setup.ts` has comprehensive cleanup

## References

- [Vitest Fake Timers](https://vitest.dev/api/vi.html#vi-usefaketimers)
- [React Testing Library waitFor](https://testing-library.com/docs/dom-testing-library/api-async/#waitfor)
- [Testing Library Best Practices](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)
- [Project Testing Guide](../../development/testing.md)
- [TDD Workflow](../../development/testing-workflow.md)

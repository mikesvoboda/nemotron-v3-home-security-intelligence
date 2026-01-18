# Frontend Testing Utilities

Comprehensive testing utilities for the Home Security Intelligence frontend. This directory contains custom render functions, test data factories, mock helpers, and assertion utilities.

## Directory Structure

```
src/test/
├── README.md           # This file
├── setup.ts            # Test setup and global configuration
├── utils.tsx           # Custom render functions and wrappers
├── factories/          # Test data factories
│   └── index.ts
├── mocks/              # Reusable mock helpers
│   └── index.ts
└── matchers.ts         # Custom assertion helpers
```

## Quick Start

### Basic Component Test

```typescript
import { render, screen, waitFor } from '@/test/utils';
import { cameraFactory } from '@/test/factories';
import { CameraCard } from './CameraCard';

it('renders camera card', () => {
  const camera = cameraFactory({ name: 'Front Door' });
  render(<CameraCard camera={camera} />);

  expect(screen.getByText('Front Door')).toBeInTheDocument();
  expect(screen.getByText('online')).toBeInTheDocument();
});
```

### Hook Test with QueryClient

```typescript
import { renderHook, waitFor } from '@testing-library/react';
import { createWrapper } from '@/test/utils';
import { useCamerasQuery } from './useCamerasQuery';

it('fetches cameras', async () => {
  const { result } = renderHook(() => useCamerasQuery(), {
    wrapper: createWrapper(),
  });

  await waitFor(() => {
    expect(result.current.isLoading).toBe(false);
  });

  expect(result.current.data).toBeDefined();
});
```

### MSW Override

```typescript
import { render, screen } from '@/test/utils';
import { mockApiError } from '@/test/mocks';
import { server } from '@/mocks/server';
import { CameraList } from './CameraList';

it('handles API error', async () => {
  server.use(mockApiError('/api/cameras', 'Failed to load cameras'));

  render(<CameraList />);

  await screen.findByText(/failed to load/i);
});
```

## Test Utilities (`utils.tsx`)

### `renderWithProviders(ui, options?)`

Custom render function that wraps components with QueryClientProvider and other necessary providers.

**Parameters:**
- `ui` - React element to render
- `options` - Render options
  - `queryClientOptions` - Options for QueryClient constructor

**Returns:** Render result from React Testing Library

**Example:**

```typescript
import { renderWithProviders } from '@/test/utils';

const { getByText } = renderWithProviders(<MyComponent />);
```

### `createWrapper(queryClientOptions?)`

Create a wrapper component with all providers. Useful for `renderHook`.

**Example:**

```typescript
import { renderHook } from '@testing-library/react';
import { createWrapper } from '@/test/utils';

const wrapper = createWrapper();
const { result } = renderHook(() => useMyHook(), { wrapper });
```

### `createTestQueryClient(options?)`

Create a QueryClient optimized for testing with:
- No retries (fail fast)
- No automatic refetch on window focus/reconnect
- Short cache times (0ms)
- Errors thrown immediately

**Example:**

```typescript
import { createTestQueryClient } from '@/test/utils';

const queryClient = createTestQueryClient({
  defaultOptions: {
    queries: { retry: 3 } // Override default
  }
});
```

## Test Data Factories (`factories/`)

Factories create test data with sensible defaults while allowing specific fields to be overridden.

### Camera Factory

```typescript
import { cameraFactory, cameraFactoryList } from '@/test/factories';

// Single camera
const camera = cameraFactory({ name: 'Back Door' });

// Multiple cameras
const cameras = cameraFactoryList(3, (i) => ({
  name: `Camera ${i}`
}));
```

### Event Factory

```typescript
import { eventFactory, eventFactoryList } from '@/test/factories';

// High-risk event
const event = eventFactory({
  risk_score: 85,
  risk_level: 'high',
  summary: 'Suspicious activity detected'
});

// Multiple events
const events = eventFactoryList(5);
```

### Detection Factory

```typescript
import { detectionFactory, detectionFactoryList } from '@/test/factories';

// Person detection
const detection = detectionFactory({
  object_type: 'person',
  confidence: 0.95,
  bbox: [100, 100, 300, 400]
});

// Multiple detections
const detections = detectionFactoryList(10);
```

### Other Factories

- `gpuStatsFactory()` - GPU statistics
- `healthResponseFactory()` - Health check response
- `systemStatsFactory()` - System statistics

### Unique IDs

All factories use `uniqueId()` to generate unique IDs. The counter resets between tests.

```typescript
import { uniqueId } from '@/test/factories';

const id1 = uniqueId('camera'); // "camera-1"
const id2 = uniqueId('camera'); // "camera-2"
```

## Mock Helpers (`mocks/`)

Reusable mock factories for common testing scenarios.

### MSW Handler Factories

```typescript
import { mockApiSuccess, mockApiError, mockApiLoading } from '@/test/mocks';
import { server } from '@/mocks/server';

// Success response
server.use(mockApiSuccess('/api/cameras', [camera1, camera2]));

// Error response
server.use(mockApiError('/api/cameras', 'Server error', 500));

// Loading state (infinite delay)
server.use(mockApiLoading('/api/cameras'));
```

### HTTP Method Handlers

```typescript
import { mockApiPost, mockApiPut, mockApiDelete } from '@/test/mocks';

// POST request
server.use(mockApiPost('/api/cameras', { id: 'new-camera' }, 201));

// PUT request
server.use(mockApiPut('/api/cameras/1', { id: '1', name: 'Updated' }));

// DELETE request
server.use(mockApiDelete('/api/cameras/1'));
```

### WebSocket Mock

```typescript
import { createMockWebSocket } from '@/test/mocks';

const mockWs = createMockWebSocket();

// Simulate connection
mockWs.simulateOpen();

// Simulate message
mockWs.simulateMessage({ type: 'event', data: event });

// Simulate error
mockWs.simulateError(new Error('Connection failed'));

// Simulate close
mockWs.simulateClose(1000, 'Normal closure');
```

### QueryClient Mock

```typescript
import { createMockQueryClient } from '@/test/mocks';

const mockQueryClient = createMockQueryClient();

// Verify calls
expect(mockQueryClient.invalidateQueries).toHaveBeenCalledWith(['cameras']);
```

## Custom Assertions (`matchers.ts`)

Domain-specific assertion helpers that make tests more expressive.

### Risk Level Assertions

```typescript
import { expectRiskLevel } from '@/test/matchers';

expectRiskLevel(25).toBeLow();
expectRiskLevel(50).toBeMedium();
expectRiskLevel(85).toBeHigh();
expectRiskLevel(score).toBeValid(); // 0-100
```

### API Response Assertions

```typescript
import { expectApiSuccess, expectApiError } from '@/test/matchers';

expectApiSuccess(response, 200);
expectApiError(response, 404, 'Not found');
```

### Data Structure Assertions

```typescript
import {
  expectValidCamera,
  expectValidEvent,
  expectValidDetection
} from '@/test/matchers';

expectValidCamera(camera);
expectValidEvent(event);
expectValidDetection(detection);
```

### Bounding Box Assertions

```typescript
import { expectValidBoundingBox } from '@/test/matchers';

expectValidBoundingBox([100, 100, 200, 200]);
```

### Timestamp Assertions

```typescript
import {
  expectRecentTimestamp,
  expectPastTimestamp,
  expectTimestampBefore
} from '@/test/matchers';

expectRecentTimestamp(event.started_at, 30); // Within 30 seconds
expectPastTimestamp(event.ended_at);
expectTimestampBefore(event.started_at, event.ended_at);
```

### Array Assertions

```typescript
import { expectSortedBy, expectUniqueBy } from '@/test/matchers';

expectSortedBy(events, 'started_at', 'desc');
expectUniqueBy(cameras, 'id');
```

### Loading State Assertions

```typescript
import { expectLoading, expectLoaded, expectError } from '@/test/matchers';

expectLoading(query);
expectLoaded(query);
expectError(query, 'Failed to fetch');
```

## Common Patterns

### Testing with MSW

MSW (Mock Service Worker) is configured globally in `setup.ts` and intercepts all HTTP requests.

**Default handlers:** See `src/mocks/handlers.ts`

**Override for specific test:**

```typescript
import { server } from '@/mocks/server';
import { http, HttpResponse } from 'msw';

it('handles error', async () => {
  server.use(
    http.get('/api/cameras', () => {
      return HttpResponse.json(
        { detail: 'Server error' },
        { status: 500 }
      );
    })
  );

  // Test error handling...
});
```

**Request inspection:**

```typescript
server.use(
  http.post('/api/cameras', async ({ request }) => {
    const body = await request.json();
    expect(body.name).toBe('New Camera');
    return HttpResponse.json({ id: 'new-camera' }, { status: 201 });
  })
);
```

### Testing Async Queries

```typescript
import { render, waitFor, screen } from '@/test/utils';
import { mockApiSuccess } from '@/test/mocks';
import { cameraFactory } from '@/test/factories';
import { server } from '@/mocks/server';

it('loads and displays data', async () => {
  const cameras = [
    cameraFactory({ name: 'Camera 1' }),
    cameraFactory({ name: 'Camera 2' }),
  ];

  server.use(mockApiSuccess('/api/cameras', cameras));

  render(<CameraList />);

  // Wait for loading to complete
  await waitFor(() => {
    expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
  });

  // Verify data rendered
  expect(screen.getByText('Camera 1')).toBeInTheDocument();
  expect(screen.getByText('Camera 2')).toBeInTheDocument();
});
```

### Testing User Interactions

```typescript
import { render, screen, fireEvent } from '@/test/utils';

it('handles click', () => {
  const handleClick = vi.fn();
  render(<Button onClick={handleClick}>Click me</Button>);

  fireEvent.click(screen.getByText('Click me'));

  expect(handleClick).toHaveBeenCalledTimes(1);
});
```

### Testing Forms

```typescript
import { render, screen, fireEvent, waitFor } from '@/test/utils';
import { mockApiPost } from '@/test/mocks';
import { server } from '@/mocks/server';

it('submits form', async () => {
  server.use(
    mockApiPost('/api/cameras', { id: 'new-camera', name: 'Test' }, 201)
  );

  render(<CameraForm />);

  fireEvent.change(screen.getByLabelText(/name/i), {
    target: { value: 'Test Camera' }
  });

  fireEvent.click(screen.getByText(/submit/i));

  await waitFor(() => {
    expect(screen.getByText(/success/i)).toBeInTheDocument();
  });
});
```

### Testing Error States

```typescript
import { render, screen } from '@/test/utils';
import { mockApiError } from '@/test/mocks';
import { server } from '@/mocks/server';

it('displays error message', async () => {
  server.use(mockApiError('/api/cameras', 'Failed to load'));

  render(<CameraList />);

  await screen.findByText(/failed to load/i);
});
```

## Best Practices

### 1. Use Factories for Test Data

**Good:**

```typescript
const camera = cameraFactory({ name: 'Front Door' });
```

**Bad:**

```typescript
const camera = {
  id: 'camera-1',
  name: 'Front Door',
  folder_path: '/export/foscam/front_door',
  status: 'online',
  created_at: '2024-01-01T00:00:00Z',
  last_seen_at: '2024-01-01T12:00:00Z',
};
```

### 2. Use Custom Assertions

**Good:**

```typescript
expectValidCamera(camera);
expectRiskLevel(event.risk_score).toBeHigh();
```

**Bad:**

```typescript
expect(camera).toHaveProperty('id');
expect(camera).toHaveProperty('name');
expect(event.risk_score).toBeGreaterThanOrEqual(70);
```

### 3. Use Mock Helpers

**Good:**

```typescript
server.use(mockApiError('/api/cameras', 'Server error', 500));
```

**Bad:**

```typescript
server.use(
  http.get('/api/cameras', () => {
    return HttpResponse.json({ detail: 'Server error' }, { status: 500 });
  })
);
```

### 4. Use Custom Render

**Good:**

```typescript
import { render } from '@/test/utils';
render(<MyComponent />);
```

**Bad:**

```typescript
import { render } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';

const Wrapper = ({ children }) => (
  <QueryClientProvider client={queryClient}>
    {children}
  </QueryClientProvider>
);

render(<MyComponent />, { wrapper: Wrapper });
```

### 5. Wait for Async Operations

**Good:**

```typescript
await waitFor(() => {
  expect(screen.getByText('Data loaded')).toBeInTheDocument();
});
```

**Bad:**

```typescript
await new Promise(resolve => setTimeout(resolve, 100));
expect(screen.getByText('Data loaded')).toBeInTheDocument();
```

## Related Documentation

- [Testing Guide](/docs/development/testing.md) - Comprehensive testing patterns
- [CLAUDE.md](/CLAUDE.md) - TDD approach and workflow
- [MSW Documentation](https://mswjs.io/docs/) - API mocking library
- [Testing Library](https://testing-library.com/docs/react-testing-library/intro/) - React testing utilities
- [Vitest](https://vitest.dev/) - Test runner

## Troubleshooting

### "Cannot find module '@/test/utils'"

Ensure TypeScript path aliases are configured in `tsconfig.json`:

```json
{
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

### "MSW handlers not being called"

1. Check handler is registered: `server.use(handler)`
2. Check endpoint path matches exactly
3. Check request method (GET, POST, etc.)
4. Check if request is bypassed (see console warnings)

### "QueryClient cache interference"

The test setup automatically creates a fresh QueryClient with zero cache time. If you're still seeing interference:

1. Verify you're using `renderWithProviders` or `createWrapper`
2. Check that `afterEach` cleanup is running
3. Manually invalidate queries if needed:

```typescript
queryClient.clear();
```

### "Factory IDs not unique"

The counter is automatically reset in `afterEach`. If you need manual reset:

```typescript
import { resetCounter } from '@/test/factories';
resetCounter();
```

# MSW (Mock Service Worker) Mocking Infrastructure

This directory contains the MSW setup for API mocking in unit tests. MSW intercepts HTTP requests at the network level, providing more realistic test coverage than vi.mock().

## Directory Structure

```
frontend/src/mocks/
  handlers.ts     - API mock handlers for all endpoints
  server.ts       - Node server setup for tests
  AGENTS.md       - This documentation
```

## Why MSW Over vi.mock()?

1. **Realistic request flow**: Requests go through actual fetch implementation
2. **Production-like behavior**: Request/response handling matches production
3. **Request validation**: Handlers can inspect request params, body, headers
4. **Test isolation**: Handler overrides reset automatically between tests
5. **Gradual migration**: Can coexist with vi.mock() during migration

## Quick Start

MSW is automatically started by the test setup (in the test directory). Most tests can use the default handlers from `handlers.ts`. For test-specific responses:

```typescript
import { server } from '../mocks/server';
import { http, HttpResponse } from 'msw';

it('handles error response', async () => {
  // Override handler for this test only
  server.use(
    http.get('/api/system/storage', () => {
      return HttpResponse.json({ detail: 'Server error' }, { status: 400 });
    })
  );

  // Test error handling...
});
```

## Handler Patterns

### Basic GET Handler

```typescript
http.get('/api/cameras', () => {
  return HttpResponse.json({
    cameras: mockCameras,
    count: mockCameras.length,
  });
})
```

### Path Parameters

```typescript
http.get('/api/cameras/:id', ({ params }) => {
  const camera = mockCameras.find(c => c.id === params.id);
  if (!camera) {
    return HttpResponse.json({ detail: 'Not found' }, { status: 404 });
  }
  return HttpResponse.json(camera);
})
```

### Query Parameters

```typescript
http.get('/api/events', ({ request }) => {
  const url = new URL(request.url);
  const limit = parseInt(url.searchParams.get('limit') || '50', 10);
  const offset = parseInt(url.searchParams.get('offset') || '0', 10);

  const events = mockEvents.slice(offset, offset + limit);
  return HttpResponse.json({ events, count: events.length, limit, offset });
})
```

### POST with Request Body

```typescript
http.post('/api/system/cleanup', async ({ request }) => {
  const body = await request.json();
  // Process body...
  return HttpResponse.json({ success: true });
})
```

### DELETE Requests

```typescript
http.delete('/api/dlq/:queueName', () => {
  return HttpResponse.json({
    success: true,
    message: 'Queue cleared',
  });
})
```

### Delayed Responses (for Loading States)

```typescript
import { delay } from 'msw';

http.get('/api/system/storage', async () => {
  await delay(100); // 100ms delay
  return HttpResponse.json(mockStorageStats);
})

// Or infinite delay for testing loading states
http.get('/api/system/storage', async () => {
  await delay('infinite');
  return HttpResponse.json(mockStorageStats);
})
```

## Error Handling Patterns

### Non-Retriable Errors (400)

Use 400 status to avoid API client retry backoff:

```typescript
http.get('/api/system/storage', () => {
  return HttpResponse.json(
    { detail: 'Bad request' },
    { status: 400 }
  );
})
```

### Retriable Errors (500)

Note: 500 errors trigger retry logic with exponential backoff. Use sparingly in tests as they add delay.

```typescript
http.get('/api/system/storage', () => {
  return HttpResponse.json(
    { detail: 'Server error' },
    { status: 500 }
  );
})
```

### Sequential Responses

```typescript
let callCount = 0;
server.use(
  http.get('/api/cameras', () => {
    callCount++;
    if (callCount === 1) {
      return HttpResponse.json({ detail: 'Error' }, { status: 400 });
    }
    return HttpResponse.json({ cameras: mockCameras });
  })
);
```

## Test Setup Requirements

When using MSW with the API client's request deduplication:

```typescript
import { clearInFlightRequests } from '../services/api';

describe('MyComponent (MSW)', () => {
  beforeEach(() => {
    // Clear in-flight request cache to prevent test interference
    clearInFlightRequests();
  });

  // ... tests
});
```

## Converting Existing Tests

1. Replace `vi.mock('../services/api')` with MSW imports
2. Add `clearInFlightRequests()` in beforeEach
3. Replace `vi.mocked(api.fetchXxx).mockResolvedValue()` with `server.use(http.get(...))`
4. Use 400 status instead of 500 to avoid retry delays

### Before (vi.mock)

```typescript
vi.mock('../../services/api');

beforeEach(() => {
  vi.mocked(api.fetchStorageStats).mockResolvedValue(mockStats);
});

it('shows error', async () => {
  vi.mocked(api.fetchStorageStats).mockRejectedValue(new Error('Network error'));
  // ...
});
```

### After (MSW)

```typescript
import { server } from '../../mocks/server';
import { clearInFlightRequests } from '../../services/api';
import { http, HttpResponse } from 'msw';

beforeEach(() => {
  clearInFlightRequests();
  server.use(
    http.get('/api/system/storage', () => HttpResponse.json(mockStats))
  );
});

it('shows error', async () => {
  server.use(
    http.get('/api/system/storage', () => {
      return HttpResponse.json({ detail: 'Network error' }, { status: 400 });
    })
  );
  // ...
});
```

## Naming Convention

MSW test files use the `.msw.test.{ts,tsx}` suffix:

- `StorageDashboard.test.tsx` - Original with vi.mock
- `StorageDashboard.msw.test.tsx` - Converted to MSW

## Available Default Handlers

See `handlers.ts` for the full list. Key endpoints include:

- `/api/cameras` - Camera CRUD
- `/api/events` - Event listing with pagination
- `/api/system/health` - Health check
- `/api/system/storage` - Storage stats
- `/api/system/gpu` - GPU stats
- `/api/system/telemetry` - Pipeline telemetry
- `/api/dlq/*` - Dead letter queue management

## Resources

- [MSW Documentation](https://mswjs.io/docs/)
- [MSW Handler Reference](https://mswjs.io/docs/api/http)
- [MSW Node Integration](https://mswjs.io/docs/integrations/node)

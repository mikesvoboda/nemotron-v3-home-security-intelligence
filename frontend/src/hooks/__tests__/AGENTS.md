# Hooks Unit Tests

This directory contains unit tests for custom React hooks in the frontend application.

## Purpose

Test the behavior of individual hooks in isolation, covering:

- TanStack Query integration (mutations, cache invalidation)
- Form validation with API error mapping
- WebSocket event handling
- State management and URL persistence
- Pagination patterns

## Test Files

| File                                  | Hook Under Test              | Key Coverage                                                   |
| ------------------------------------- | ---------------------------- | -------------------------------------------------------------- |
| `useAdminMutations.test.tsx`          | `useAdminMutations`          | Admin API mutations (seed, clear, cleanup), cache invalidation |
| `useEntityHistory.test.tsx`           | `useEntityHistory`           | Entity history tracking with undo/redo                         |
| `useFormWithApiErrors.test.ts`        | `useFormWithApiErrors`       | API validation errors to react-hook-form mapping               |
| `useHouseholdApi.test.ts`             | `useHouseholdApi`            | Household member CRUD operations                               |
| `useNotificationPreferences.test.tsx` | `useNotificationPreferences` | Notification settings persistence                              |
| `usePaginationState.test.tsx`         | `usePaginationState`         | Cursor and offset pagination with URL sync                     |
| `usePromptQueries.test.tsx`           | `usePromptQueries`           | Prompt configuration CRUD, history, testing                    |
| `usePullToRefresh.test.ts`            | `usePullToRefresh`           | Touch gesture handling for mobile refresh                      |
| `useSettingsApi.test.tsx`             | `useSettingsApi`             | Application settings queries and mutations                     |
| `useSummaries.test.ts`                | `useSummaries`               | Event summary generation and caching                           |
| `useZoneAlerts.test.tsx`              | `useZoneAlerts`              | Zone-based anomaly and trust violation alerts                  |

## Test Patterns

### TanStack Query Testing

Tests use a fresh `QueryClient` per test to ensure isolation:

```typescript
function createTestWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
  return ({ children }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

const { result } = renderHook(() => useCamerasQuery(), {
  wrapper: createTestWrapper(),
});
```

### Mock Fetch Pattern

```typescript
let mockFetch: ReturnType<typeof vi.fn>;

beforeEach(() => {
  mockFetch = vi.fn();
  globalThis.fetch = mockFetch;
});

// Success response
mockFetch.mockResolvedValue({
  ok: true,
  json: () => Promise.resolve({ data: [...] }),
});

// Error response
mockFetch.mockResolvedValue({
  ok: false,
  status: 422,
  json: () => Promise.resolve({ detail: 'Validation error' }),
});
```

### Form + API Error Testing

```typescript
const { result } = renderHook(
  () => {
    const form = useForm<TestFormData>({ defaultValues });
    const mutation = useApiMutation({
      mutationFn: mockMutationFn,
      form,
    });
    return { form, mutation };
  },
  { wrapper: createQueryWrapper() }
);

// Simulate API validation error
mockMutationFn.mockRejectedValue(
  new ApiError(422, 'Validation failed', {
    validation_errors: [{ field: 'email', message: 'Invalid' }],
  })
);

await act(async () => {
  try {
    await result.current.mutation.mutateAsync(formData);
  } catch {
    /* Expected */
  }
});

expect(result.current.form.formState.errors.email?.message).toBe('Invalid');
```

### URL Parameter Testing (Pagination)

```typescript
function createRouterWrapper(initialUrl = '/') {
  return ({ children }) => (
    <MemoryRouter initialEntries={[initialUrl]}>{children}</MemoryRouter>
  );
}

const { result } = renderHook(
  () => usePaginationState({ type: 'offset' }),
  { wrapper: createRouterWrapper('/?page=3&limit=25') }
);

expect(result.current.page).toBe(3);
expect(result.current.offset).toBe(50);  // (3-1) * 25
```

### WebSocket Event Handling

```typescript
// Capture WebSocket event handler
let lastSubscriber: Subscriber | null = null;

(webSocketManager.subscribe as Mock).mockImplementation((_url, subscriber) => {
  lastSubscriber = subscriber;
  setTimeout(() => subscriber.onOpen?.(), 0);
  return mockUnsubscribe;
});

// Simulate message
act(() => {
  lastSubscriber?.onMessage?.({
    type: 'event',
    data: { risk_score: 85, ... },
  });
});

await waitFor(() => {
  expect(result.current.events).toHaveLength(1);
});
```

## Coverage Targets

| Test Category  | Minimum Coverage |
| -------------- | ---------------- |
| Hook logic     | 85%              |
| Error handling | 80%              |
| Edge cases     | 80%              |

## Key Testing Scenarios

### Mutation Lifecycle

1. Success with cache invalidation
2. Error handling and state
3. Loading state transitions
4. Retry on failure (if configured)

### Form Validation

1. FastAPI HTTPValidationError format (`detail[].loc`)
2. Custom `validation_errors[]` format
3. Nested field paths (`profile.firstName`)
4. Unknown field handling

### Pagination

1. Initial state from URL
2. Navigation (next, previous, first, last)
3. Limit changes reset to page 1
4. Custom parameter names
5. Multiple independent instances

## Subdirectories

- `integration/` - Integration tests for cross-hook and cross-component scenarios

## Related Files

- `/frontend/src/hooks/__mocks__/` - Mock implementations for hooks
- `/frontend/src/test-utils/renderWithProviders.tsx` - Test utilities
- `/frontend/src/services/api.ts` - API client being mocked

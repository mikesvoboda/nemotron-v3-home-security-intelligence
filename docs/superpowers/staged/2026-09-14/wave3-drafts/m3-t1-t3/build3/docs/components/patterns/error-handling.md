# Error Handling Patterns

> Patterns for handling, displaying, and recovering from errors.

---

## Overview

This document covers patterns for error handling at the component level, including error boundaries, API error handling, user feedback, and recovery strategies.

---

## Error Hierarchy

```
Application
├── Global Error Boundary (crashes)
│   └── Full-page error with reload option
├── Route Error Boundary (navigation errors)
│   └── Page-level error with navigation
├── Feature Error Boundary (widget errors)
│   └── Component-level error with retry
└── API Error Handling (data errors)
    └── Inline errors with retry
```

---

## Component Error Handling

### Error Boundary Wrapper

```tsx
import { FeatureErrorBoundary } from '@/components/common';

function Dashboard() {
  return (
    <div className="grid grid-cols-2 gap-4">
      <FeatureErrorBoundary featureName="Camera Grid">
        <CameraGrid />
      </FeatureErrorBoundary>

      <FeatureErrorBoundary featureName="Activity Feed">
        <ActivityFeed />
      </FeatureErrorBoundary>

      <FeatureErrorBoundary featureName="Stats">
        <StatsRow />
      </FeatureErrorBoundary>
    </div>
  );
}
```

### Error State Component

```tsx
import { ErrorState } from '@/components/common';

function ErrorState({
  title = 'Something went wrong',
  message,
  onRetry,
  showSupport = false,
}: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center">
      <AlertTriangle className="h-12 w-12 text-red-500 mb-4" />
      <h3 className="text-lg font-medium text-white mb-2">{title}</h3>
      {message && <p className="text-gray-400 mb-4">{message}</p>}
      <div className="flex gap-2">
        {onRetry && (
          <Button onClick={onRetry}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Try Again
          </Button>
        )}
        {showSupport && (
          <Button variant="secondary" onClick={() => window.open('/support')}>
            Contact Support
          </Button>
        )}
      </div>
    </div>
  );
}
```

---

## API Error Handling

### Query Error Handling

```tsx
import { useQuery } from '@tanstack/react-query';

function EventsList() {
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ['events'],
    queryFn: fetchEvents,
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });

  if (isLoading) return <LoadingSpinner />;

  if (error) {
    return (
      <ErrorState
        title="Failed to load events"
        message={getErrorMessage(error)}
        onRetry={refetch}
      />
    );
  }

  return <EventList events={data} />;
}
```

### Mutation Error Handling

```tsx
import { useMutation } from '@tanstack/react-query';
import { useToast } from '@/hooks/useToast';

function SaveButton({ data }: { data: FormData }) {
  const { toast } = useToast();

  const mutation = useMutation({
    mutationFn: saveData,
    onSuccess: () => {
      toast.success('Saved successfully');
    },
    onError: (error) => {
      toast.error(getErrorMessage(error));
    },
  });

  return (
    <Button
      onClick={() => mutation.mutate(data)}
      loading={mutation.isPending}
      disabled={mutation.isPending}
    >
      Save
    </Button>
  );
}
```

### Error Message Extraction

```tsx
function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }

  if (typeof error === 'object' && error !== null) {
    // API error response
    if ('message' in error) {
      return String(error.message);
    }
    if ('error' in error) {
      return String(error.error);
    }
  }

  return 'An unexpected error occurred';
}

function getHttpErrorMessage(status: number): string {
  switch (status) {
    case 400:
      return 'Invalid request. Please check your input.';
    case 401:
      return 'Session expired. Please refresh the page.';
    case 403:
      return 'You do not have permission to perform this action.';
    case 404:
      return 'The requested resource was not found.';
    case 429:
      return 'Too many requests. Please wait a moment.';
    case 500:
      return 'Server error. Please try again later.';
    case 503:
      return 'Service temporarily unavailable.';
    default:
      return 'An unexpected error occurred.';
  }
}
```

---

## Form Error Handling

### Validation Errors

```tsx
function FormWithErrors() {
  const {
    handleSubmit,
    formState: { errors },
    setError,
  } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const onSubmit = async (data: FormData) => {
    try {
      const result = await submitForm(data);

      if (!result.success) {
        // Server-side validation errors
        result.errors.forEach(({ field, message }) => {
          setError(field, { type: 'server', message });
        });
        return;
      }

      // Success handling
    } catch (error) {
      // Network/unexpected errors
      setError('root', {
        type: 'submit',
        message: getErrorMessage(error),
      });
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      {errors.root && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg mb-4">
          <p className="text-red-400">{errors.root.message}</p>
        </div>
      )}
      {/* Form fields */}
    </form>
  );
}
```

### Inline Field Errors

```tsx
function FormField({ name, label, error, children }: FormFieldProps) {
  const hasError = !!error;

  return (
    <div className="space-y-1">
      <label
        htmlFor={name}
        className={clsx('text-sm font-medium', hasError ? 'text-red-400' : 'text-gray-300')}
      >
        {label}
      </label>
      <div className={clsx(hasError && 'ring-1 ring-red-500 rounded-lg')}>{children}</div>
      {error && (
        <p className="text-sm text-red-400" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
```

---

## Recovery Patterns

### Auto-Retry with Backoff

```tsx
function useRetryableQuery<T>(
  queryKey: string[],
  queryFn: () => Promise<T>,
  options?: { maxRetries?: number; initialDelay?: number }
) {
  const { maxRetries = 3, initialDelay = 1000 } = options ?? {};

  return useQuery({
    queryKey,
    queryFn,
    retry: maxRetries,
    retryDelay: (attemptIndex) => {
      const delay = Math.min(initialDelay * 2 ** attemptIndex, 30000);
      // Add jitter to prevent thundering herd
      return delay + Math.random() * 1000;
    },
  });
}
```

### Manual Retry UI

```tsx
function RetryableContent({ onRetry, error }: RetryableContentProps) {
  const [isRetrying, setIsRetrying] = useState(false);

  const handleRetry = async () => {
    setIsRetrying(true);
    try {
      await onRetry();
    } finally {
      setIsRetrying(false);
    }
  };

  return (
    <div className="text-center p-8">
      <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
      <p className="text-gray-400 mb-4">{getErrorMessage(error)}</p>
      <Button onClick={handleRetry} loading={isRetrying}>
        <RefreshCw className="h-4 w-4 mr-2" />
        Retry
      </Button>
    </div>
  );
}
```

### Graceful Degradation

```tsx
function WidgetWithFallback() {
  const { data, error, isLoading } = useWidgetData();

  if (error) {
    // Show cached data if available
    const cachedData = getCachedWidgetData();
    if (cachedData) {
      return (
        <>
          <div className="text-amber-500 text-sm mb-2">
            <AlertTriangle className="h-4 w-4 inline mr-1" />
            Showing cached data (last updated: {cachedData.timestamp})
          </div>
          <WidgetContent data={cachedData.data} />
        </>
      );
    }

    // No cached data, show error
    return <ErrorState message={error.message} />;
  }

  return <WidgetContent data={data} />;
}
```

---

## Error Reporting

```tsx
// Error reporting utility
function reportError(error: Error, context?: Record<string, unknown>) {
  console.error('Error:', error, context);

  // In production, send to error tracking service
  if (import.meta.env.PROD) {
    // Example: Sentry, LogRocket, etc.
    // errorTracker.captureException(error, { extra: context });
  }
}

// Usage in error boundary
class ErrorBoundary extends React.Component {
  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    reportError(error, {
      componentStack: errorInfo.componentStack,
      url: window.location.href,
    });
  }
}
```

---

## Testing Error Handling

```tsx
describe('Error Handling', () => {
  it('shows error state on API failure', async () => {
    server.use(
      rest.get('/api/events', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<EventsList />);

    await waitFor(() => {
      expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
    });
  });

  it('allows retry on error', async () => {
    let calls = 0;
    server.use(
      rest.get('/api/events', (req, res, ctx) => {
        calls++;
        if (calls === 1) return res(ctx.status(500));
        return res(ctx.json({ events: [] }));
      })
    );

    render(<EventsList />);

    await waitFor(() => {
      expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole('button', { name: /retry/i }));

    await waitFor(() => {
      expect(screen.queryByText(/failed to load/i)).not.toBeInTheDocument();
    });
  });
});
```

# Error Boundary Components

React error boundaries for catching and handling errors gracefully.

## ErrorBoundary

General-purpose error boundary that catches JavaScript errors in child components.

**Location:** `frontend/src/components/common/ErrorBoundary.tsx`

### Props

```typescript
interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  title?: string;
  description?: string;
  componentName?: string;
  boundaryName?: string;
}
```

### Usage Examples

```tsx
import { ErrorBoundary } from '@/components/common';

// Basic usage
<ErrorBoundary>
  <MyComponent />
</ErrorBoundary>

// With custom fallback
<ErrorBoundary fallback={<div>Something went wrong</div>}>
  <MyComponent />
</ErrorBoundary>

// With error callback for analytics
<ErrorBoundary
  onError={(error, info) => analytics.trackError(error)}
  componentName="CameraGrid"
>
  <CameraGrid />
</ErrorBoundary>
```

### Features

- GitHub issue pre-fill for bug reports
- Error deduplication (prevents log flooding)
- Backend error logging (NEM-2725)
- Sentry integration (when enabled)
- "Try Again" and "Refresh Page" recovery options
- Component stack display in development mode

---

## FeatureErrorBoundary

Granular error boundary for feature isolation - prevents one broken feature from crashing the entire app.

**Location:** `frontend/src/components/common/FeatureErrorBoundary.tsx`

### Props

```typescript
interface FeatureErrorBoundaryProps {
  children: ReactNode;
  feature: string; // Required - name for error messages
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  compact?: boolean; // default: false
}
```

### Usage Examples

```tsx
import { FeatureErrorBoundary } from '@/components/common';

// Basic usage - wraps individual features
<FeatureErrorBoundary feature="Camera Grid">
  <CameraGrid />
</FeatureErrorBoundary>

// With custom fallback
<FeatureErrorBoundary
  feature="Risk Gauge"
  fallback={<div>Risk data unavailable</div>}
>
  <RiskGauge />
</FeatureErrorBoundary>

// Compact mode for inline displays
<FeatureErrorBoundary feature="Activity Feed" compact>
  <ActivityFeed />
</FeatureErrorBoundary>
```

### Modes

| Mode    | Use Case                          | Display                           |
| ------- | --------------------------------- | --------------------------------- |
| Default | Dashboard widgets, cards          | Full error card with retry button |
| Compact | Inline displays, small components | Single-line error with retry link |

---

## ApiErrorBoundary

Specialized error boundary for API errors with RFC 7807 problem details support.

**Location:** `frontend/src/components/common/ApiErrorBoundary.tsx`

### Props

```typescript
interface ApiErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode | ((error: Error, reset: () => void) => ReactNode);
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  onRetry?: () => void;
  componentName?: string;
  showToast?: boolean; // default: false
}
```

### Error Classification

| Type      | HTTP Codes         | Display        | Actions      |
| --------- | ------------------ | -------------- | ------------ |
| Transient | 429, 502, 503, 504 | Yellow warning | Retry button |
| Permanent | 400, 401, 403, 404 | Red error      | Refresh only |

### Usage Examples

```tsx
import { ApiErrorBoundary, useApiErrorHandler } from '@/components/common';

// Basic usage
<ApiErrorBoundary>
  <DataFetchingComponent />
</ApiErrorBoundary>

// With custom fallback render function
<ApiErrorBoundary
  fallback={(error, reset) => (
    <div>
      <p>Error: {error.message}</p>
      <button onClick={reset}>Try Again</button>
    </div>
  )}
>
  <MyComponent />
</ApiErrorBoundary>

// Using the error handler hook in mutations
function MyComponent() {
  const handleError = useApiErrorHandler();

  const mutation = useMutation({
    mutationFn: api.updateCamera,
    onError: (error) => {
      const config = handleError(error);
      if (config.retryable) {
        // Schedule retry
      }
    },
  });
}
```

---

## ChunkLoadErrorBoundary

Handles dynamic import failures from React.lazy() and code splitting.

**Location:** `frontend/src/components/common/ChunkLoadErrorBoundary.tsx`

### Props

```typescript
interface ChunkLoadErrorBoundaryProps {
  children: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}
```

### Usage Example

```tsx
import { ChunkLoadErrorBoundary, RouteLoadingFallback } from '@/components/common';

const LazyPage = lazy(() => import('./pages/Dashboard'));

<ChunkLoadErrorBoundary>
  <Suspense fallback={<RouteLoadingFallback />}>
    <LazyPage />
  </Suspense>
</ChunkLoadErrorBoundary>;
```

### Features

- Only catches chunk/module loading errors
- Re-throws other errors to parent boundaries
- Provides "Reload Page" recovery button
- Shows error details in development mode

---

## ActionErrorBoundary

Error boundary that integrates with React 19 form actions and useActionState.

**Location:** `frontend/src/components/common/ActionErrorBoundary.tsx`

### Props

```typescript
interface ActionErrorBoundaryProps {
  children: ReactNode;
  actionState?: FormActionState;
  feature: string;
  renderErrorFallback?: ReactNode;
  actionErrorFallback?: (state: FormActionState, onRetry: () => void) => ReactNode;
  onRetry?: () => void;
  onError?: (error: Error | string, type: 'render' | 'action') => void;
  compact?: boolean;
  className?: string;
}
```

### Usage Example

```tsx
import { useActionState } from 'react';
import { ActionErrorBoundary } from '@/components/common';

function SettingsForm() {
  const [state, action, isPending] = useActionState(submitAction, { status: 'idle' });

  return (
    <ActionErrorBoundary
      actionState={state}
      feature="Settings Form"
      onRetry={() => window.location.reload()}
    >
      <form action={action}>
        <input name="name" />
        <button type="submit" disabled={isPending}>
          Save
        </button>
      </form>
    </ActionErrorBoundary>
  );
}
```

---

## Recommended Boundary Structure

```tsx
// App.tsx - Nested error boundaries from general to specific
<ErrorBoundary>
  {' '}
  {/* Catch-all */}
  <ChunkLoadErrorBoundary>
    {' '}
    {/* Code splitting errors */}
    <ApiErrorBoundary>
      {' '}
      {/* API-level errors */}
      <Layout>
        <FeatureErrorBoundary feature="Navigation">
          <Navigation />
        </FeatureErrorBoundary>

        <FeatureErrorBoundary feature="Dashboard">
          <Dashboard />
        </FeatureErrorBoundary>
      </Layout>
    </ApiErrorBoundary>
  </ChunkLoadErrorBoundary>
</ErrorBoundary>
```

## Best Practices

1. **Wrap features individually** with `FeatureErrorBoundary` for graceful degradation
2. **Use `ChunkLoadErrorBoundary`** around lazy-loaded routes
3. **Provide meaningful feature names** for error messages
4. **Always offer recovery options** (retry, refresh, report issue)
5. **Log errors appropriately** for debugging and monitoring

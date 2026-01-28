# Loading State Components

Components for displaying loading states and progress indicators.

## LoadingSpinner

Full-page loading spinner used as a fallback for React.lazy Suspense boundaries.

**Location:** `frontend/src/components/common/LoadingSpinner.tsx`

### Features

- Full-screen centered layout
- Dark background matching app theme
- Animated spinner with NVIDIA green accent
- Respects prefers-reduced-motion

---

## RouteLoadingFallback

Compact loading indicator for lazy-loaded routes.

**Location:** `frontend/src/components/common/RouteLoadingFallback.tsx`

### Props

```typescript
interface RouteLoadingFallbackProps {
  message?: string; // default: "Loading..."
}
```

---

## Skeleton

Loading placeholder component for content that is being fetched.

**Location:** `frontend/src/components/common/Skeleton.tsx`

### Props

```typescript
interface SkeletonProps {
  variant?: 'text' | 'circular' | 'rectangular';
  width?: number | string;
  height?: number | string;
  lines?: number;
  animation?: 'pulse' | 'shimmer' | 'none';
}
```

### Variants

| Variant     | Shape                 | Default Dimensions      |
| ----------- | --------------------- | ----------------------- |
| text        | Small rounded corners | 100% width, 1em height  |
| circular    | Fully rounded (pill)  | Must specify dimensions |
| rectangular | Large rounded corners | Must specify dimensions |

---

## InfiniteScrollStatus

Loading and end-of-list indicators for infinite scroll lists.

**Location:** `frontend/src/components/common/InfiniteScrollStatus.tsx`

### States

| State    | Display                                |
| -------- | -------------------------------------- |
| Loading  | Spinner with "Loading more..." message |
| Error    | Error message with retry button        |
| Has More | Invisible sentinel element             |
| End      | "You reached the end" with checkmark   |

## Best Practices

1. Use appropriate component for context
2. Match skeleton shapes to actual content
3. Provide loading context with messages
4. Include error handling with retry mechanisms

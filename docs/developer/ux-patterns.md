# UX Enhancement Patterns

> Frontend patterns for toast notifications, page transitions, and skeleton loaders.

This document covers the UX enhancement patterns implemented in the frontend to provide visual feedback during loading states, navigation, and user actions.

---

## Toast Notifications

The application uses [sonner](https://sonner.emilkowal.ski/) for toast notifications, wrapped in custom hooks and providers for NVIDIA-themed styling and consistent usage across the codebase.

### Architecture

```
ToastProvider (sonner Toaster)
        │
        ├── useToast hook (sonner direct API)
        │     └── success, error, warning, info, loading, promise
        │
        └── ToastContext (React Context - alternative API)
              └── showToast, dismissToast
```

Two toast APIs are available:

- **`useToast` hook** (`frontend/src/hooks/useToast.ts`) - Direct sonner wrapper with full feature support
- **`ToastContext`** (`frontend/src/contexts/ToastContext.tsx`) - React Context for simpler use cases

### Setup

The `ToastProvider` is configured in `App.tsx`:

```tsx
// frontend/src/App.tsx
import { ToastProvider } from './components/common';

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BrowserRouter>{/* ... */}</BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}
```

### Toast Types

| Type      | Color                  | Duration        | Use Case                         |
| --------- | ---------------------- | --------------- | -------------------------------- |
| `success` | NVIDIA Green (#76B900) | 4 seconds       | Operation completed successfully |
| `error`   | Red (#EF4444)          | 8 seconds       | Operation failed                 |
| `warning` | Amber (#F59E0B)        | 4 seconds       | Caution needed                   |
| `info`    | Blue (#3B82F6)         | 4 seconds       | Informational message            |
| `loading` | NVIDIA Green spinner   | Until dismissed | Async operation in progress      |

### Using the useToast Hook

```tsx
import { useToast } from '../../hooks';

function MyComponent() {
  const { success, error, warning, info, loading, dismiss, promise } = useToast();

  // Basic usage
  const handleSave = async () => {
    try {
      await saveData();
      success('Settings saved');
    } catch (err) {
      error('Failed to save settings');
    }
  };

  // With description
  const handleUpload = () => {
    success('File uploaded', {
      description: 'Your file has been processed',
    });
  };

  // With action button
  const handleDelete = () => {
    success('Item deleted', {
      action: {
        label: 'Undo',
        onClick: () => undoDelete(),
      },
    });
  };

  // Promise-based toast (shows loading, then success/error)
  const handleAsync = () => {
    promise(fetchData(), {
      loading: 'Loading data...',
      success: 'Data loaded!',
      error: 'Failed to load data',
    });
  };

  // Manual loading toast
  const handleLongOperation = async () => {
    const toastId = loading('Processing...');
    await longOperation();
    dismiss(toastId);
    success('Complete!');
  };

  return <button onClick={handleSave}>Save</button>;
}
```

### Toast Options

```typescript
interface ToastOptions {
  /** Additional description text below the title */
  description?: string;
  /** Duration in milliseconds (default: 4000, error: 8000) */
  duration?: number;
  /** Unique ID for deduplication and programmatic dismissal */
  id?: string | number;
  /** Whether the toast can be manually dismissed (default: true) */
  dismissible?: boolean;
  /** Primary action button */
  action?: ToastAction;
  /** Cancel/secondary action button */
  cancel?: ToastAction;
  /** Callback when toast is dismissed */
  onDismiss?: (toast: ExternalToast) => void;
  /** Callback when toast auto-closes */
  onAutoClose?: (toast: ExternalToast) => void;
}

interface ToastAction {
  label: string;
  onClick: () => void;
  variant?: 'primary' | 'secondary' | 'ghost';
}
```

### ToastProvider Configuration

```tsx
import { ToastProvider } from './components/common';

// Default configuration
<ToastProvider
  position="bottom-right" // Toast container position
  theme="dark" // Color theme
  richColors={true} // Enable colored variants
  closeButton={true} // Show close button
  gap={12} // Gap between toasts (px)
  visibleToasts={4} // Max visible toasts
  expand={true} // Expand on hover
  duration={4000} // Default auto-dismiss (ms)
/>;
```

### Position Options

| Position        | Description                   |
| --------------- | ----------------------------- |
| `top-left`      | Top left corner               |
| `top-center`    | Top center                    |
| `top-right`     | Top right corner              |
| `bottom-left`   | Bottom left corner            |
| `bottom-center` | Bottom center                 |
| `bottom-right`  | Bottom right corner (default) |

### Styling

Toast styles are defined in `frontend/src/styles/toast.css` with NVIDIA dark theme:

- **Background**: `#1a1a1a` with gradient for variants
- **Border**: Colored accent matching toast type
- **Left accent bar**: 4px solid color indicator
- **Animations**: Slide in/out with reduced motion support
- **Stacking**: Visual depth effect for multiple toasts

### Accessibility

- Toasts use ARIA live regions for screen readers
- Close buttons appear on hover/focus
- Reduced motion preference is respected (instant transitions)
- High contrast mode support with thicker borders

---

## Page Transitions

The application uses [Framer Motion](https://www.framer.com/motion/) for smooth page transitions between routes.

### Architecture

```
PageTransition (wrapper)
    │
    ├── AnimatePresence (exit animations)
    │
    └── motion.div (animated container)
          ├── Variants (initial, animate, exit)
          └── Location-keyed animations
```

### Setup

Routes are wrapped with `PageTransition` in `App.tsx`:

```tsx
// frontend/src/App.tsx
import { PageTransition } from './components/common';

<Suspense fallback={<RouteLoadingFallback />}>
  <PageTransition>
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/timeline" element={<EventTimeline />} />
      {/* ... */}
    </Routes>
  </PageTransition>
</Suspense>;
```

### Available Variants

| Variant      | Effect                         | Best For           |
| ------------ | ------------------------------ | ------------------ |
| `fade`       | Opacity 0 to 1                 | Subtle transitions |
| `slideUp`    | Fade + slide up 20px (default) | Main content       |
| `slideRight` | Fade + slide from left         | Lateral navigation |
| `scale`      | Fade + scale from 95%          | Modal-like content |

### Using PageTransition

```tsx
import PageTransition from './components/common/PageTransition';

// Basic usage (uses slideUp default)
<PageTransition>
  <MyPage />
</PageTransition>

// Custom variant and duration
<PageTransition variant="fade" duration={0.3}>
  <MyPage />
</PageTransition>
```

### Props

```typescript
interface PageTransitionProps {
  /** Content to animate */
  children: ReactNode;
  /** Animation variant to use */
  variant?: 'fade' | 'slideUp' | 'slideRight' | 'scale';
  /** Animation duration in seconds */
  duration?: number;
  /** Additional CSS classes */
  className?: string;
}
```

### Animation Variants Reference

Defined in `frontend/src/components/common/animations/index.ts`:

```typescript
// Page transitions
const pageTransitionVariants = {
  fade: {
    initial: { opacity: 0 },
    animate: { opacity: 1 },
    exit: { opacity: 0 },
  },
  slideUp: {
    initial: { opacity: 0, y: 20 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -20 },
  },
  slideRight: {
    initial: { opacity: 0, x: -20 },
    animate: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: 20 },
  },
  scale: {
    initial: { opacity: 0, scale: 0.95 },
    animate: { opacity: 1, scale: 1 },
    exit: { opacity: 0, scale: 0.95 },
  },
};

// Modal transitions
const modalTransitionVariants = {
  scale: {
    /* ... */
  },
  slideUp: {
    /* ... */
  },
  slideDown: {
    /* ... */
  },
  fade: {
    /* ... */
  },
};

// List item transitions (staggered)
const listItemVariants = {
  fadeIn: {
    /* ... */
  },
  slideIn: {
    /* ... */
  },
  scaleIn: {
    /* ... */
  },
};
```

### Transition Configuration

```typescript
// Default smooth transition
const defaultTransition = {
  duration: 0.2,
  ease: [0.4, 0, 0.2, 1], // cubic-bezier
};

// Reduced motion (instant)
const reducedMotionTransition = {
  duration: 0,
};

// Spring for bouncy effects
const springTransition = {
  type: 'spring',
  stiffness: 300,
  damping: 30,
};
```

### Accessibility

- Respects `prefers-reduced-motion` preference
- When reduced motion is preferred, transitions are instant (duration: 0)
- Components add `motion-reduce` CSS class for styling hooks

---

## Animated Components

### AnimatedModal

Modal dialog with open/close animations:

```tsx
import { AnimatedModal } from './components/common';

function MyComponent() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <AnimatedModal
      isOpen={isOpen}
      onClose={() => setIsOpen(false)}
      variant="scale" // scale, slideUp, slideDown, fade
      size="md" // sm, md, lg, xl, full
      closeOnBackdropClick // Close when clicking backdrop
      closeOnEscape // Close on Escape key
    >
      <h2>Modal Title</h2>
      <p>Modal content here</p>
    </AnimatedModal>
  );
}
```

### AnimatedList

List with staggered entrance animations:

```tsx
import { AnimatedList } from './components/common';

function EventsList({ events }) {
  return (
    <AnimatedList
      items={events}
      renderItem={(event) => <EventCard event={event} />}
      keyExtractor={(event) => event.id}
      variant="fadeIn" // fadeIn, slideIn, scaleIn
      staggerDelay={0.05} // Delay between items (seconds)
      emptyState={<EmptyState />}
    />
  );
}
```

---

## Skeleton Loaders

Skeleton loaders provide visual placeholders while content is loading. They match the layout of the actual content to reduce perceived loading time.

### Base Skeleton Component

```tsx
import Skeleton from './components/common/Skeleton';

// Text placeholder
<Skeleton variant="text" width={200} height={20} />

// Avatar/circular placeholder
<Skeleton variant="circular" width={48} height={48} />

// Card/rectangular placeholder
<Skeleton variant="rectangular" width="100%" height={200} />

// Multiple lines of text
<Skeleton variant="text" lines={3} />
```

### Skeleton Props

```typescript
interface SkeletonProps {
  /** Shape variant: text, circular, rectangular */
  variant?: SkeletonVariant;
  /** Width (number for px, or string like '100%') */
  width?: number | string;
  /** Height (number for px, or string like '100%') */
  height?: number | string;
  /** Number of lines (for text variant) */
  lines?: number;
  /** Additional CSS classes */
  className?: string;
  /** Data test ID for testing */
  'data-testid'?: string;
}
```

### Pre-built Skeleton Components

Located in `frontend/src/components/common/skeletons/`:

| Component            | Matches          | Use Case                |
| -------------------- | ---------------- | ----------------------- |
| `EventCardSkeleton`  | `EventCard`      | Event timeline loading  |
| `CameraCardSkeleton` | `CameraCard`     | Camera grid loading     |
| `StatsCardSkeleton`  | Stats cards      | Dashboard stats loading |
| `TableRowSkeleton`   | Table rows       | Table data loading      |
| `ChartSkeleton`      | Chart components | Analytics chart loading |
| `EntityCardSkeleton` | `EntityCard`     | Entity list loading     |

### Using Skeleton Components

```tsx
import {
  EventCardSkeleton,
  CameraCardSkeleton,
  ChartSkeleton,
} from './components/common/skeletons';

// In a component with loading state
function EventTimeline() {
  const { data, isLoading } = useEvents();

  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <EventCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  return <EventList events={data} />;
}
```

### Route Loading Fallback

`RouteLoadingFallback` is displayed during lazy-loaded route chunk fetching:

```tsx
import { RouteLoadingFallback } from './components/common';

// Used automatically in App.tsx Suspense
<Suspense fallback={<RouteLoadingFallback />}>
  <Routes>...</Routes>
</Suspense>

// Custom message
<RouteLoadingFallback message="Loading dashboard..." />
```

### Creating Custom Skeletons

Match your component's layout structure:

```tsx
import { clsx } from 'clsx';

interface MyCardSkeletonProps {
  className?: string;
}

export default function MyCardSkeleton({ className }: MyCardSkeletonProps) {
  return (
    <div
      className={clsx('rounded-lg border border-gray-800 bg-[#1F1F1F] p-4', className)}
      data-testid="my-card-skeleton"
      aria-hidden="true"
      role="presentation"
    >
      {/* Header */}
      <div className="mb-3 flex items-center gap-3">
        <div className="h-10 w-10 animate-pulse rounded-full bg-gray-800" />
        <div className="h-5 w-32 animate-pulse rounded bg-gray-800" />
      </div>

      {/* Body */}
      <div className="space-y-2">
        <div className="h-4 w-full animate-pulse rounded bg-gray-800" />
        <div className="h-4 w-4/5 animate-pulse rounded bg-gray-800" />
      </div>
    </div>
  );
}
```

### Skeleton Styling Guidelines

1. **Match dimensions**: Skeletons should match the actual content size
2. **Use `animate-pulse`**: Tailwind's pulse animation for shimmer effect
3. **Background color**: Use `bg-gray-800` on dark theme
4. **Accessibility**: Add `aria-hidden="true"` and `role="presentation"`
5. **Test IDs**: Include `data-testid` for E2E testing

---

## Loading State Patterns

### Component-Level Loading

```tsx
function CameraGrid() {
  const { cameras, isLoading, error } = useCameras();

  if (error) return <ErrorState error={error} />;

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <CameraCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
      {cameras.map((camera) => (
        <CameraCard key={camera.id} camera={camera} />
      ))}
    </div>
  );
}
```

### React Query Integration

```tsx
import { useQuery } from '@tanstack/react-query';
import { EventCardSkeleton } from './components/common/skeletons';

function EventTimeline() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['events'],
    queryFn: fetchEvents,
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <EventCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (isError) {
    return <ErrorMessage error={error} />;
  }

  return <EventList events={data} />;
}
```

### Suspense + Lazy Loading

```tsx
import { lazy, Suspense } from 'react';
import { RouteLoadingFallback } from './components/common';

const HeavyComponent = lazy(() => import('./HeavyComponent'));

function Page() {
  return (
    <Suspense fallback={<RouteLoadingFallback message="Loading..." />}>
      <HeavyComponent />
    </Suspense>
  );
}
```

---

## Key Files

| File                                                      | Purpose                              |
| --------------------------------------------------------- | ------------------------------------ |
| `frontend/src/hooks/useToast.ts`                          | Toast notification hook              |
| `frontend/src/contexts/ToastContext.tsx`                  | Toast context provider (alternative) |
| `frontend/src/components/common/ToastProvider.tsx`        | Sonner Toaster wrapper               |
| `frontend/src/styles/toast.css`                           | NVIDIA-themed toast styles           |
| `frontend/src/components/common/PageTransition.tsx`       | Page transition wrapper              |
| `frontend/src/components/common/animations/index.ts`      | Animation variants                   |
| `frontend/src/components/common/AnimatedModal.tsx`        | Animated modal dialog                |
| `frontend/src/components/common/AnimatedList.tsx`         | Animated list container              |
| `frontend/src/components/common/Skeleton.tsx`             | Base skeleton component              |
| `frontend/src/components/common/skeletons/`               | Pre-built skeleton components        |
| `frontend/src/components/common/RouteLoadingFallback.tsx` | Route loading indicator              |

---

## Related Documentation

- [Frontend Hooks](../architecture/frontend-hooks.md) - Custom React hooks
- [Development Patterns](../development/patterns.md) - Code patterns
- [Codebase Tour](codebase-tour.md) - Directory structure overview
- [Interface Guide](../user-guide/interface-guide.md) - End-user visual feedback guide

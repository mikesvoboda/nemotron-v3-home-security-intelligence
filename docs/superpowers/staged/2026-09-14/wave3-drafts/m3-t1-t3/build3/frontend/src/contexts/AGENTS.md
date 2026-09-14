# Frontend Contexts Directory

## Purpose

React Context providers for global state management across the application. Currently contains toast notification context for centralized user feedback.

## Directory Contents

```
frontend/src/contexts/
├── AGENTS.md                     # This documentation file
├── index.ts                      # Central export point
├── AnnouncementContext.tsx       # Live region announcements provider
├── AnnouncementContext.test.tsx  # Tests for announcement context
├── DebugModeContext.tsx          # Debug mode state provider
├── DebugModeContext.test.tsx     # Tests for debug mode context
├── SystemDataContext.tsx         # System data state provider
├── SystemDataContext.test.tsx    # Tests for system data context
├── ToastContext.tsx              # Toast notification provider and hook
└── ToastContext.test.tsx         # Tests for toast context
```

## Key Files

| File                           | Purpose                                               |
| ------------------------------ | ----------------------------------------------------- |
| `index.ts`                     | Re-exports all contexts for clean imports             |
| `AnnouncementContext.tsx`      | ARIA live region announcements for accessibility      |
| `AnnouncementContext.test.tsx` | Tests for announcement context                        |
| `DebugModeContext.tsx`         | Debug mode state provider with localStorage           |
| `DebugModeContext.test.tsx`    | Tests for debug mode context                          |
| `SystemDataContext.tsx`        | System data provider for shared system state          |
| `SystemDataContext.test.tsx`   | Tests for system data context                         |
| `ToastContext.tsx`             | Toast notification provider with auto-dismiss         |
| `ToastContext.test.tsx`        | Comprehensive tests for toast functionality           |

## Toast Context (`ToastContext.tsx`)

Centralized notification system for displaying user feedback messages (success, error, info).

### Features

- Auto-dismiss with configurable duration (default: 5000ms)
- Toast stacking with maximum limit (default: 5 toasts)
- Type-safe toast types: `success`, `error`, `info`
- Automatic oldest-toast removal when limit is exceeded
- Manual dismiss capability
- Unique ID generation for each toast

### Types

```typescript
export type ToastType = 'success' | 'error' | 'info';

export interface Toast {
  id: string;
  message: string;
  type: ToastType;
  createdAt: number;
}

export interface ToastContextType {
  showToast: (message: string, type: ToastType, duration?: number) => string;
  dismissToast: (id: string) => void;
}

export interface ToastProviderContextType extends ToastContextType {
  toasts: Toast[];
}
```

### Constants

```typescript
export const DEFAULT_TOAST_DURATION = 5000; // 5 seconds
export const MAX_TOASTS = 5;
```

### Provider Props

```typescript
export interface ToastProviderProps {
  children: ReactNode;
  defaultDuration?: number; // Override default 5s duration
  maxToasts?: number; // Override max 5 toasts
}
```

### Hook: `useToast()`

Custom hook for accessing toast functionality. Must be used within `ToastProvider`.

**Returns:**

```typescript
{
  toasts: Toast[];           // Array of active toasts
  showToast: Function;       // Display a new toast
  dismissToast: Function;    // Manually dismiss a toast
}
```

**Throws:** Error if used outside of `ToastProvider`

## Usage Examples

### App Setup

Wrap your application with the provider in `App.tsx`:

```tsx
import { ToastProvider } from './contexts';

function App() {
  return (
    <ToastProvider defaultDuration={3000} maxToasts={3}>
      {/* App content */}
    </ToastProvider>
  );
}
```

### Showing Toasts in Components

```tsx
import { useToast } from './contexts';

function MyComponent() {
  const { showToast } = useToast();

  const handleSave = async () => {
    try {
      await saveData();
      showToast('Data saved successfully!', 'success');
    } catch (error) {
      showToast('Failed to save data', 'error');
    }
  };

  const handleProcessing = () => {
    // Custom duration (10 seconds)
    const id = showToast('Processing...', 'info', 10000);
    // Can dismiss manually later: dismissToast(id);
  };

  return (
    <>
      <button onClick={handleSave}>Save</button>
      <button onClick={handleProcessing}>Process</button>
    </>
  );
}
```

### Displaying Toasts (Toast Container Component)

The toast container reads from context to render toasts:

```tsx
import { useToast } from './contexts';

function ToastContainer() {
  const { toasts, dismissToast } = useToast();

  return (
    <div className="fixed top-4 right-4 z-50 space-y-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`toast toast-${toast.type}`}
          onClick={() => dismissToast(toast.id)}
        >
          {toast.message}
        </div>
      ))}
    </div>
  );
}
```

## Testing

### Test Coverage (`ToastContext.test.tsx`)

Comprehensive test suite covering:

- Provider rendering with children
- `showToast()` creates toast with correct properties
- Auto-dismiss after default duration (5s)
- Custom duration support
- Toast stacking (oldest removed when limit exceeded)
- Manual dismiss via `dismissToast()`
- Hook throws error when used outside provider
- Re-exports `ToastType` as `ToastNotificationType`

**Example Test:**

```typescript
import { renderHook, act, waitFor } from '@testing-library/react';
import { ToastProvider, useToast } from './ToastContext';

describe('ToastContext', () => {
  it('shows and auto-dismisses toast', async () => {
    const { result } = renderHook(() => useToast(), {
      wrapper: ToastProvider,
    });

    act(() => {
      result.current.showToast('Success!', 'success', 100);
    });

    expect(result.current.toasts).toHaveLength(1);

    await waitFor(() => {
      expect(result.current.toasts).toHaveLength(0);
    }, { timeout: 150 });
  });
});
```

## Design Patterns

### Context + Provider Pattern

Standard React context pattern with:
- Context creation: `createContext()`
- Provider component: `ToastProvider`
- Hook for consumption: `useToast()`
- Throws error if used outside provider (prevents bugs)

### Memoization

`useMemo()` used for context value to prevent unnecessary re-renders when toast state changes.

### Functional Updates

State updates use functional form: `setToasts((prev) => ...)` to ensure correct state transitions.

### ID Generation

Unique IDs combine timestamp and random string: `toast-${Date.now()}-${Math.random()...}`.

## Future Enhancements

Potential additions for other contexts:
- **ThemeContext** - Light/dark mode toggle (currently dark-only)
- **AuthContext** - User authentication state (no auth in MVP)
- **SettingsContext** - User preferences and settings
- **WebSocketContext** - Centralized WebSocket connection management

## Related Files

- `/frontend/src/App.tsx` - Provider setup
- `/frontend/src/components/ToastContainer.tsx` - Toast rendering (if implemented)

## Notes for AI Agents

- Only one context currently exists (ToastContext)
- Toast provider should wrap the entire app
- `useToast()` is the primary API - don't access context directly
- Toast IDs are opaque strings - don't rely on format
- Default duration balances visibility with screen clutter
- Maximum toast limit prevents UI overload

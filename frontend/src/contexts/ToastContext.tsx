
/**
 * ToastContext - Centralized notification management for the React frontend.
 *
 * Provides a context and hook for displaying toast notifications throughout
 * the application. Supports success, error, and info toast types with
 * configurable auto-dismiss duration.
 *
 * @example
 * // Wrap your app with the provider
 * <ToastProvider>
 *   <App />
 * </ToastProvider>
 *
 * @example
 * // Use the hook in components
 * const { showToast, dismissToast } = useToast();
 * showToast('Operation successful!', 'success');
 * showToast('Something went wrong', 'error');
 * showToast('Processing...', 'info', 10000); // Custom 10s duration
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

/**
 * Toast notification types.
 */
export type ToastType = 'success' | 'error' | 'info';

/**
 * Individual toast notification data.
 */
export interface Toast {
  /** Unique identifier for the toast */
  id: string;
  /** Message to display */
  message: string;
  /** Type of toast (determines styling) */
  type: ToastType;
  /** Timestamp when the toast was created */
  createdAt: number;
}

/**
 * Context value interface for toast management.
 */
export interface ToastContextType {
  /**
   * Display a new toast notification.
   * @param message - The message to display
   * @param type - The toast type ('success' | 'error' | 'info')
   * @param duration - Optional auto-dismiss duration in milliseconds (default: 5000)
   * @returns The unique ID of the created toast
   */
  showToast: (message: string, type: ToastType, duration?: number) => string;
  /**
   * Dismiss a specific toast by ID.
   * @param id - The unique ID of the toast to dismiss
   */
  dismissToast: (id: string) => void;
}

/**
 * Extended context type including internal toast state (for provider).
 */
export interface ToastProviderContextType extends ToastContextType {
  /** Array of currently active toasts */
  toasts: Toast[];
}

/**
 * Default auto-dismiss duration in milliseconds.
 */
export const DEFAULT_TOAST_DURATION = 5000;

/**
 * Maximum number of simultaneous toasts.
 * Older toasts are dismissed when this limit is exceeded.
 */
export const MAX_TOASTS = 5;

/**
 * The Toast context - null when accessed outside of provider.
 */
export const ToastContext = createContext<ToastProviderContextType | null>(null);

/**
 * Generate a unique ID for toast notifications.
 * Uses a combination of timestamp and random string for uniqueness.
 */
function generateToastId(): string {
  return `toast-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * Props for the ToastProvider component.
 */
export interface ToastProviderProps {
  /** Child components that can access the toast context */
  children: ReactNode;
  /** Default duration for auto-dismiss (can be overridden per toast) */
  defaultDuration?: number;
  /** Maximum number of toasts to display simultaneously */
  maxToasts?: number;
}

/**
 * ToastProvider component - wraps the application to provide toast functionality.
 *
 * Manages the toast state and provides methods to show and dismiss toasts.
 * Supports stacking multiple toasts and auto-dismisses them after a configurable duration.
 *
 * @example
 * <ToastProvider defaultDuration={3000} maxToasts={3}>
 *   <App />
 * </ToastProvider>
 */
export function ToastProvider({
  children,
  defaultDuration = DEFAULT_TOAST_DURATION,
  maxToasts = MAX_TOASTS,
}: ToastProviderProps) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  /**
   * Map to track timer IDs for each toast.
   * Used for cleanup on dismiss and unmount.
   */
  const timerRefs = useRef<Map<string, NodeJS.Timeout>>(new Map());

  /**
   * Dismiss a specific toast by ID.
   * Also clears the associated timer to prevent memory leaks.
   */
  const dismissToast = useCallback((id: string) => {
    // Clear the timer if it exists
    const timerId = timerRefs.current.get(id);
    if (timerId) {
      clearTimeout(timerId);
      timerRefs.current.delete(id);
    }
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  /**
   * Cleanup all timers on unmount to prevent memory leaks.
   */
  useEffect(() => {
    const timers = timerRefs.current;
    return () => {
      timers.forEach((timerId) => clearTimeout(timerId));
      timers.clear();
    };
  }, []);

  /**
   * Show a new toast notification.
   * If maxToasts is exceeded, the oldest toast is removed.
   */
  const showToast = useCallback(
    (message: string, type: ToastType, duration?: number) => {
      const id = generateToastId();
      const newToast: Toast = {
        id,
        message,
        type,
        createdAt: Date.now(),
      };

      setToasts((prev) => {
        // If at max capacity, remove the oldest toast and its timer
        if (prev.length >= maxToasts && prev[0]) {
          const oldestId = prev[0].id;
          const oldTimerId = timerRefs.current.get(oldestId);
          if (oldTimerId) {
            clearTimeout(oldTimerId);
            timerRefs.current.delete(oldestId);
          }
          return [...prev.slice(1), newToast];
        }
        return [...prev, newToast];
      });

      // Set up auto-dismiss timer and track it
      const dismissDuration = duration ?? defaultDuration;
      if (dismissDuration > 0) {
        const timerId = setTimeout(() => {
          timerRefs.current.delete(id);
          dismissToast(id);
        }, dismissDuration);
        timerRefs.current.set(id, timerId);
      }

      return id;
    },
    [defaultDuration, maxToasts, dismissToast]
  );

  /**
   * Memoized context value to prevent unnecessary re-renders.
   */
  const contextValue = useMemo<ToastProviderContextType>(
    () => ({
      toasts,
      showToast,
      dismissToast,
    }),
    [toasts, showToast, dismissToast]
  );

  return <ToastContext.Provider value={contextValue}>{children}</ToastContext.Provider>;
}

/**
 * Hook to access the toast context.
 *
 * Must be used within a ToastProvider. Throws an error if used outside.
 *
 * @returns The toast context with showToast, dismissToast methods and toasts array
 * @throws Error if used outside of ToastProvider
 *
 * @example
 * function MyComponent() {
 *   const { showToast, dismissToast, toasts } = useToast();
 *
 *   const handleSave = async () => {
 *     try {
 *       await saveData();
 *       showToast('Data saved successfully!', 'success');
 *     } catch (error) {
 *       showToast('Failed to save data', 'error');
 *     }
 *   };
 *
 *   return <button onClick={handleSave}>Save</button>;
 * }
 */
export function useToast(): ToastProviderContextType {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}

/**
 * Re-export types for external consumers.
 */
export type { ToastType as ToastNotificationType };

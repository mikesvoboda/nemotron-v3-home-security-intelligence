/**
 * useToast - Hook for managing toast notifications
 *
 * Provides a convenient API for displaying toast notifications with various
 * styles (success, error, warning, info) and supports action buttons.
 *
 * Uses sonner under the hood for the actual toast implementation.
 *
 * @example
 * ```tsx
 * const { success, error, warning, info, loading, dismiss, promise } = useToast();
 *
 * // Basic usage
 * success('Settings saved');
 * error('Failed to save settings');
 *
 * // With description
 * success('File uploaded', { description: 'Your file has been processed' });
 *
 * // With action button
 * success('Item deleted', {
 *   action: { label: 'Undo', onClick: () => undoDelete() },
 * });
 *
 * // Promise-based toast
 * promise(saveData(), {
 *   loading: 'Saving...',
 *   success: 'Saved!',
 *   error: 'Failed to save',
 * });
 * ```
 */

import { useCallback, useMemo } from 'react';
import { toast } from 'sonner';

import type { ExternalToast } from 'sonner';

/**
 * Action button configuration for toasts
 */
export interface ToastAction {
  /** Button label text */
  label: string;
  /** Click handler */
  onClick: () => void;
  /** Visual variant for the button */
  variant?: 'primary' | 'secondary' | 'ghost';
}

/**
 * Options for toast notifications
 */
export interface ToastOptions {
  /** Additional description text below the title */
  description?: string;
  /** Duration in milliseconds before auto-dismiss (default: 4000, error: 8000) */
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

/**
 * Messages for promise-based toasts
 */
export interface PromiseMessages<T> {
  /** Message shown while promise is pending */
  loading: string;
  /** Message shown on success (can be a function that receives the resolved value) */
  success: string | ((data: T) => string);
  /** Message shown on error (can be a function that receives the error) */
  error: string | ((error: unknown) => string);
}

/**
 * Return type for the useToast hook
 */
export interface UseToastReturn {
  /** Show a success toast */
  success: (message: string, options?: ToastOptions) => string | number;
  /** Show an error toast */
  error: (message: string, options?: ToastOptions) => string | number;
  /** Show a warning toast */
  warning: (message: string, options?: ToastOptions) => string | number;
  /** Show an info toast */
  info: (message: string, options?: ToastOptions) => string | number;
  /** Show a loading toast */
  loading: (message: string, options?: ToastOptions) => string | number;
  /** Dismiss a specific toast or all toasts */
  dismiss: (toastId?: string | number) => void;
  /** Show a toast that tracks a promise */
  promise: <T>(promise: Promise<T>, messages: PromiseMessages<T>) => Promise<T>;
}

/** Default duration for regular toasts (ms) */
const DEFAULT_DURATION = 4000;

/** Default duration for error toasts (ms) - longer to ensure user sees the error */
const ERROR_DURATION = 8000;

/**
 * Convert ToastAction to sonner's expected format
 */
function toSonnerAction(action: ToastAction): { label: string; onClick: () => void } {
  return {
    label: action.label,
    onClick: action.onClick,
  };
}

/**
 * Build sonner options from our ToastOptions
 */
function buildSonnerOptions(options: ToastOptions = {}, defaultDuration: number): ExternalToast {
  const sonnerOptions: ExternalToast = {
    duration: options.dismissible === false ? Infinity : (options.duration ?? defaultDuration),
    description: options.description,
    id: options.id,
    onDismiss: options.onDismiss,
    onAutoClose: options.onAutoClose,
  };

  if (options.action) {
    sonnerOptions.action = toSonnerAction(options.action);
  }

  if (options.cancel) {
    sonnerOptions.cancel = toSonnerAction(options.cancel);
  }

  return sonnerOptions;
}

/**
 * Hook for managing toast notifications
 *
 * @returns Object with methods to show and dismiss toasts
 */
export function useToast(): UseToastReturn {
  const success = useCallback(
    (message: string, options?: ToastOptions): string | number => {
      return toast.success(message, buildSonnerOptions(options, DEFAULT_DURATION));
    },
    []
  );

  const error = useCallback(
    (message: string, options?: ToastOptions): string | number => {
      return toast.error(message, buildSonnerOptions(options, ERROR_DURATION));
    },
    []
  );

  const warning = useCallback(
    (message: string, options?: ToastOptions): string | number => {
      return toast.warning(message, buildSonnerOptions(options, DEFAULT_DURATION));
    },
    []
  );

  const info = useCallback(
    (message: string, options?: ToastOptions): string | number => {
      return toast.info(message, buildSonnerOptions(options, DEFAULT_DURATION));
    },
    []
  );

  const loading = useCallback(
    (message: string, options?: ToastOptions): string | number => {
      return toast.loading(message, buildSonnerOptions(options, DEFAULT_DURATION));
    },
    []
  );

  const dismiss = useCallback((toastId?: string | number): void => {
    toast.dismiss(toastId);
  }, []);

  const promiseFn = useCallback(
    <T>(promise: Promise<T>, messages: PromiseMessages<T>): Promise<T> => {
      toast.promise(promise, {
        loading: messages.loading,
        success: messages.success as string | ((data: T) => string),
        error: messages.error as string | ((error: unknown) => string),
      });
      return promise;
    },
    []
  );

  // Memoize the return object to ensure stable references
  return useMemo(
    () => ({
      success,
      error,
      warning,
      info,
      loading,
      dismiss,
      promise: promiseFn,
    }),
    [success, error, warning, info, loading, dismiss, promiseFn]
  );
}

export default useToast;

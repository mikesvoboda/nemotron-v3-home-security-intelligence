/**
 * React 19 Form Action Utilities
 *
 * This module provides utilities for working with React 19's new form patterns:
 * - useActionState: Manages form state with async actions
 * - useFormStatus: Shows pending states without prop drilling
 *
 * These patterns enable the "Server Actions" paradigm on the client-side,
 * providing better UX with automatic pending states and error handling.
 *
 * @see NEM-3356 - Implement useActionState and useFormStatus for forms
 *
 * @example
 * ```tsx
 * import { useActionState } from 'react';
 * import { createFormAction, type FormActionState } from './useFormAction';
 *
 * const submitSettings = createFormAction(
 *   async (formData) => {
 *     const name = formData.get('name') as string;
 *     await api.updateSettings({ name });
 *     return { success: true };
 *   },
 *   {
 *     onSuccess: () => toast.success('Settings saved'),
 *     onError: (error) => toast.error(error.message),
 *   }
 * );
 *
 * function SettingsForm() {
 *   const [state, formAction, isPending] = useActionState(submitSettings, { status: 'idle' });
 *
 *   return (
 *     <form action={formAction}>
 *       <input name="name" required />
 *       <SubmitButton>Save</SubmitButton>
 *       {state.status === 'error' && <p>{state.error}</p>}
 *     </form>
 *   );
 * }
 * ```
 */

import { useCallback } from 'react';

import { ApiError } from '../services/api';
import { logger } from '../services/logger';

// ============================================================================
// Type Definitions
// ============================================================================

/**
 * Status of a form action.
 */
export type FormActionStatus = 'idle' | 'pending' | 'success' | 'error';

/**
 * Base state for form actions.
 */
export interface FormActionState<TData = unknown> {
  /** Current status of the action */
  status: FormActionStatus;
  /** Result data on success */
  data?: TData;
  /** Error message on failure */
  error?: string;
  /** Field-level validation errors */
  fieldErrors?: Record<string, string>;
  /** Timestamp of last state change */
  timestamp?: number;
}

/**
 * Options for creating a form action.
 */
export interface FormActionOptions<TData> {
  /** Called on successful completion */
  onSuccess?: (data: TData) => void;
  /** Called on error */
  onError?: (error: Error) => void;
  /** Whether to reset form on success (default: false) */
  resetOnSuccess?: boolean;
  /** Custom error message transformer */
  transformError?: (error: Error) => string;
}

/**
 * Type for a form action function compatible with useActionState.
 */
export type FormActionFn<TState> = (
  prevState: TState,
  formData: FormData
) => TState | Promise<TState>;

/**
 * Extracts field-level validation errors from an ApiError.
 */
export interface ValidationError {
  field: string;
  message: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Extract validation errors from an ApiError response.
 *
 * Supports multiple formats:
 * - Custom: { validation_errors: { field, message }[] }
 * - FastAPI: { detail: { loc: string[], msg: string }[] }
 *
 * @param error - The error to extract validation errors from
 * @returns Record of field names to error messages
 */
export function extractValidationErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError)) {
    return {};
  }

  const data = error.data as Record<string, unknown> | undefined;
  if (!data) {
    return {};
  }

  const fieldErrors: Record<string, string> = {};

  // Check for custom validation_errors format
  if (Array.isArray(data.validation_errors)) {
    for (const err of data.validation_errors as ValidationError[]) {
      if (err.field && err.message) {
        fieldErrors[err.field] = err.message;
      }
    }
    return fieldErrors;
  }

  // Check for FastAPI HTTPValidationError format
  if (Array.isArray(data.detail)) {
    for (const err of data.detail as { loc: (string | number)[]; msg: string }[]) {
      if (Array.isArray(err.loc) && err.msg) {
        // Skip 'body', 'query', 'path' prefixes
        const prefixes = ['body', 'query', 'path'];
        const startIndex = prefixes.includes(err.loc[0] as string) ? 1 : 0;
        const fieldPath = err.loc.slice(startIndex).join('.');
        if (fieldPath) {
          fieldErrors[fieldPath] = err.msg;
        }
      }
    }
  }

  return fieldErrors;
}

/**
 * Get a user-friendly error message from an error.
 *
 * @param error - The error to extract a message from
 * @param transformer - Optional custom message transformer
 * @returns User-friendly error message
 */
export function getErrorMessage(error: unknown, transformer?: (error: Error) => string): string {
  if (error instanceof Error) {
    if (transformer) {
      return transformer(error);
    }

    // Use RFC 7807 detail if available
    if (error instanceof ApiError && error.problemDetails?.detail) {
      return error.problemDetails.detail;
    }

    return error.message;
  }

  return 'An unexpected error occurred';
}

// ============================================================================
// Form Action Factory
// ============================================================================

/**
 * Creates a form action function compatible with React 19's useActionState.
 *
 * This factory wraps an async handler with proper error handling, logging,
 * and state management. The returned function can be used directly with
 * useActionState or as a form action.
 *
 * @param handler - Async function that processes the form data
 * @param options - Configuration options for the action
 * @returns Form action function for use with useActionState
 *
 * @example
 * ```tsx
 * const submitAction = createFormAction(
 *   async (formData) => {
 *     const email = formData.get('email') as string;
 *     const result = await api.subscribe(email);
 *     return result;
 *   },
 *   {
 *     onSuccess: (data) => console.log('Subscribed:', data),
 *     onError: (error) => console.error('Failed:', error),
 *   }
 * );
 *
 * const [state, action, isPending] = useActionState(submitAction, { status: 'idle' });
 * ```
 */
export function createFormAction<TData = unknown>(
  handler: (formData: FormData) => Promise<TData>,
  options: FormActionOptions<TData> = {}
): FormActionFn<FormActionState<TData>> {
  const { onSuccess, onError, transformError } = options;

  return async (
    _prevState: FormActionState<TData>,
    formData: FormData
  ): Promise<FormActionState<TData>> => {
    try {
      const data = await handler(formData);

      // Call success callback
      if (onSuccess) {
        onSuccess(data);
      }

      return {
        status: 'success',
        data,
        timestamp: Date.now(),
      };
    } catch (error) {
      // Log the error
      logger.error('Form action failed', {
        error: error instanceof Error ? error.message : 'Unknown error',
        stack: error instanceof Error ? error.stack : undefined,
      });

      // Extract field-level errors if available
      const fieldErrors = extractValidationErrors(error);
      const hasFieldErrors = Object.keys(fieldErrors).length > 0;

      // Get user-friendly error message
      const errorMessage = getErrorMessage(error, transformError);

      // Call error callback
      if (onError && error instanceof Error) {
        onError(error);
      }

      return {
        status: 'error',
        error: errorMessage,
        fieldErrors: hasFieldErrors ? fieldErrors : undefined,
        timestamp: Date.now(),
      };
    }
  };
}

// ============================================================================
// useFormAction Hook
// ============================================================================

/**
 * Hook that creates a memoized form action with callbacks.
 *
 * This is a convenience wrapper around createFormAction that ensures
 * the action is memoized and callbacks are stable.
 *
 * @param handler - Async function that processes the form data
 * @param options - Configuration options for the action
 * @returns Memoized form action function
 *
 * @example
 * ```tsx
 * function ContactForm() {
 *   const submitAction = useFormAction(
 *     async (formData) => {
 *       const name = formData.get('name') as string;
 *       const email = formData.get('email') as string;
 *       await api.submitContact({ name, email });
 *       return { submitted: true };
 *     },
 *     {
 *       onSuccess: () => toast.success('Message sent!'),
 *       onError: (err) => toast.error(err.message),
 *     }
 *   );
 *
 *   const [state, action, isPending] = useActionState(submitAction, { status: 'idle' });
 *
 *   return (
 *     <form action={action}>
 *       <input name="name" required />
 *       <input name="email" type="email" required />
 *       <SubmitButton>Send</SubmitButton>
 *     </form>
 *   );
 * }
 * ```
 */
export function useFormAction<TData = unknown>(
  handler: (formData: FormData) => Promise<TData>,
  options: FormActionOptions<TData> = {}
): FormActionFn<FormActionState<TData>> {
  const { onSuccess, onError, transformError } = options;

  return useCallback(
    async (
      _prevState: FormActionState<TData>,
      formData: FormData
    ): Promise<FormActionState<TData>> => {
      try {
        const data = await handler(formData);

        if (onSuccess) {
          onSuccess(data);
        }

        return {
          status: 'success',
          data,
          timestamp: Date.now(),
        };
      } catch (error) {
        logger.error('Form action failed', {
          error: error instanceof Error ? error.message : 'Unknown error',
          stack: error instanceof Error ? error.stack : undefined,
        });

        const fieldErrors = extractValidationErrors(error);
        const hasFieldErrors = Object.keys(fieldErrors).length > 0;
        const errorMessage = getErrorMessage(error, transformError);

        if (onError && error instanceof Error) {
          onError(error);
        }

        return {
          status: 'error',
          error: errorMessage,
          fieldErrors: hasFieldErrors ? fieldErrors : undefined,
          timestamp: Date.now(),
        };
      }
    },
    [handler, onSuccess, onError, transformError]
  );
}

// ============================================================================
// Initial State Factory
// ============================================================================

/**
 * Creates an initial state object for form actions.
 *
 * @param overrides - Optional state overrides
 * @returns Initial form action state
 *
 * @example
 * ```tsx
 * const [state, action, isPending] = useActionState(
 *   submitAction,
 *   createInitialState({ data: { name: 'Default' } })
 * );
 * ```
 */
export function createInitialState<TData = unknown>(
  overrides?: Partial<FormActionState<TData>>
): FormActionState<TData> {
  return {
    status: 'idle',
    ...overrides,
  };
}

// ============================================================================
// State Helpers
// ============================================================================

/**
 * Check if a form action state indicates loading/pending.
 */
export function isActionPending(state: FormActionState): boolean {
  return state.status === 'pending';
}

/**
 * Check if a form action state indicates success.
 */
export function isActionSuccess(state: FormActionState): boolean {
  return state.status === 'success';
}

/**
 * Check if a form action state indicates an error.
 */
export function isActionError(state: FormActionState): boolean {
  return state.status === 'error';
}

/**
 * Check if a form action state has field-level errors.
 */
export function hasFieldErrors(state: FormActionState): boolean {
  return (
    state.status === 'error' && !!state.fieldErrors && Object.keys(state.fieldErrors).length > 0
  );
}

/**
 * Get the error message for a specific field from action state.
 */
export function getFieldError(state: FormActionState, field: string): string | undefined {
  return state.fieldErrors?.[field];
}

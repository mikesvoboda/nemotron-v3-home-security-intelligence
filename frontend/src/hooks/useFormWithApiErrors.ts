/**
 * @fileoverview Hook for mapping API validation errors to react-hook-form field errors.
 *
 * This module provides utilities for handling validation errors returned by the backend
 * and displaying them at the field level in forms using react-hook-form.
 *
 * Supports:
 * - Custom validation_errors format: { field: string, message: string }[]
 * - FastAPI HTTPValidationError format: { detail: { loc: (string|number)[], msg: string }[] }
 *
 * @example
 * ```tsx
 * import { useForm } from 'react-hook-form';
 * import { useApiMutation, applyApiValidationErrors } from './useFormWithApiErrors';
 *
 * function MyForm() {
 *   const form = useForm<FormData>();
 *   const mutation = useApiMutation({
 *     mutationFn: submitForm,
 *     form,
 *   });
 *
 *   return (
 *     <form onSubmit={form.handleSubmit((data) => mutation.mutate(data))}>
 *       <input {...form.register('email')} />
 *       {form.formState.errors.email && (
 *         <span className="text-red-500">{form.formState.errors.email.message}</span>
 *       )}
 *       <button type="submit" disabled={mutation.isPending}>Submit</button>
 *     </form>
 *   );
 * }
 * ```
 */
import { useMutation, UseMutationOptions, UseMutationResult } from '@tanstack/react-query';
import { useState, useCallback } from 'react';
import { UseFormReturn, FieldValues, Path } from 'react-hook-form';

import { ApiError, ProblemDetails } from '../services/api';

// ============================================================================
// Type Definitions
// ============================================================================

/**
 * Represents a single field-level validation error.
 * Used in the custom validation_errors format.
 */
export interface ValidationFieldError {
  /** The field name or path (e.g., 'email' or 'profile.firstName') */
  field: string;
  /** The validation error message to display */
  message: string;
}

/**
 * FastAPI ValidationError item from HTTPValidationError.detail array.
 * @see https://fastapi.tiangolo.com/tutorial/handling-errors/#validation-errors
 */
export interface FastAPIValidationError {
  /** Location of the error (e.g., ['body', 'email']) */
  loc: (string | number)[];
  /** Error message */
  msg: string;
  /** Error type identifier */
  type: string;
}

/**
 * API exception with validation errors attached.
 * Extends the base ApiError structure with validation-specific data.
 */
export interface ApiValidationException {
  /** HTTP status code (typically 422 for validation errors) */
  status: number;
  /** General error message */
  message: string;
  /** Array of field-level validation errors */
  validation_errors: ValidationFieldError[];
  /** Optional RFC 7807 Problem Details */
  problemDetails?: ProblemDetails;
}

/**
 * Options for useApiMutation hook.
 */
export interface UseApiMutationOptions<TVariables extends FieldValues, TData, TError = ApiError>
  extends Omit<UseMutationOptions<TData, TError, TVariables>, 'mutationFn'> {
  /** The mutation function to execute */
  mutationFn: (variables: TVariables) => Promise<TData>;
  /** React-hook-form instance to apply field errors to */
  form: UseFormReturn<TVariables>;
}

/**
 * Extended mutation result with field error helpers.
 */
export type UseApiMutationResult<TData, TVariables, TError = ApiError> = UseMutationResult<
  TData,
  TError,
  TVariables
> & {
  /** Whether field-level errors were applied from the last error */
  hasFieldErrors: boolean;
};

// ============================================================================
// Type Guards and Utilities
// ============================================================================

/**
 * Type guard to check if error data contains validation_errors array.
 */
function hasValidationErrors(data: unknown): data is { validation_errors: ValidationFieldError[] } {
  if (typeof data !== 'object' || data === null) {
    return false;
  }
  const obj = data as Record<string, unknown>;
  return Array.isArray(obj.validation_errors);
}

/**
 * Type guard to check if error data contains FastAPI HTTPValidationError detail.
 */
function hasFastAPIValidationDetail(data: unknown): data is { detail: FastAPIValidationError[] } {
  if (typeof data !== 'object' || data === null) {
    return false;
  }
  const obj = data as Record<string, unknown>;
  if (!Array.isArray(obj.detail)) {
    return false;
  }
  // Check if first item looks like FastAPI validation error
  const firstItem = obj.detail[0] as Record<string, unknown> | undefined;
  return firstItem !== undefined && Array.isArray(firstItem.loc) && typeof firstItem.msg === 'string';
}

/**
 * Checks if an error is an ApiValidationException (has validation errors).
 *
 * Supports both:
 * - Custom format: { validation_errors: ValidationFieldError[] }
 * - FastAPI format: { detail: FastAPIValidationError[] }
 *
 * @param error - The error to check
 * @returns True if the error contains validation errors
 *
 * @example
 * ```ts
 * if (isApiValidationException(error)) {
 *   applyApiValidationErrors(form, error);
 * }
 * ```
 */
export function isApiValidationException(error: unknown): boolean {
  if (!(error instanceof ApiError)) {
    return false;
  }

  // Check for 422 status (standard validation error status)
  if (error.status !== 422) {
    return false;
  }

  // Check for validation_errors in data
  if (hasValidationErrors(error.data)) {
    return true;
  }

  // Check for FastAPI HTTPValidationError format
  if (hasFastAPIValidationDetail(error.data)) {
    return true;
  }

  return false;
}

/**
 * Extracts the field path from FastAPI validation error loc array.
 *
 * FastAPI includes 'body', 'query', 'path' prefixes that we need to skip.
 *
 * @param loc - The location array from FastAPI validation error
 * @returns Dot-notation field path (e.g., 'profile.firstName')
 *
 * @example
 * ```ts
 * extractFieldPath(['body', 'email']) // => 'email'
 * extractFieldPath(['body', 'profile', 'firstName']) // => 'profile.firstName'
 * extractFieldPath(['body', 'items', 0, 'name']) // => 'items.0.name'
 * ```
 */
export function extractFieldPath(loc: (string | number)[]): string {
  if (loc.length === 0) {
    return '';
  }

  // Skip common prefixes (body, query, path)
  const prefixes = ['body', 'query', 'path'];
  const startIndex = prefixes.includes(loc[0] as string) ? 1 : 0;

  // Join remaining parts with dots
  return loc.slice(startIndex).join('.');
}

/**
 * Extracts validation errors from an ApiError, supporting multiple formats.
 *
 * @param error - The ApiError to extract validation errors from
 * @returns Array of ValidationFieldError objects
 */
function extractValidationErrors(error: ApiError): ValidationFieldError[] {
  const data = error.data;

  // Check for custom validation_errors format
  if (hasValidationErrors(data)) {
    return data.validation_errors;
  }

  // Check for FastAPI HTTPValidationError format
  if (hasFastAPIValidationDetail(data)) {
    return data.detail.map((item) => ({
      field: extractFieldPath(item.loc),
      message: item.msg,
    }));
  }

  return [];
}

// ============================================================================
// Core Functions
// ============================================================================

/**
 * Applies API validation errors to a react-hook-form instance.
 *
 * Maps each validation error to the corresponding form field using
 * form.setError(). Supports both simple field names and nested paths
 * (e.g., 'profile.firstName').
 *
 * @param form - The react-hook-form instance
 * @param error - The API error containing validation errors
 * @returns Number of field errors applied
 *
 * @example
 * ```ts
 * const form = useForm<FormData>();
 *
 * try {
 *   await submitForm(data);
 * } catch (error) {
 *   if (error instanceof ApiError) {
 *     const count = applyApiValidationErrors(form, error);
 *     console.log(`Applied ${count} field errors`);
 *   }
 * }
 * ```
 */
export function applyApiValidationErrors<T extends FieldValues>(
  form: UseFormReturn<T>,
  error: ApiError | ApiValidationException
): number {
  let validationErrors: ValidationFieldError[] = [];

  // Extract validation errors based on error type
  if (error instanceof ApiError) {
    validationErrors = extractValidationErrors(error);
  } else if ('validation_errors' in error) {
    validationErrors = error.validation_errors;
  }

  // Apply each error to the form
  let appliedCount = 0;
  for (const fieldError of validationErrors) {
    try {
      // Use type assertion since we're dynamically setting field paths
      form.setError(fieldError.field as Path<T>, {
        type: 'server',
        message: fieldError.message,
      });
      appliedCount++;
    } catch {
      // Field path might not exist in form, silently ignore
      // This allows backend to return errors for fields that may not be rendered
      appliedCount++;
    }
  }

  return appliedCount;
}

// ============================================================================
// Hooks
// ============================================================================

/**
 * A hook that wraps useMutation with automatic field error mapping.
 *
 * When the mutation fails with a validation error (422), this hook
 * automatically applies the field-level errors to the provided form.
 *
 * @param options - Configuration options including mutationFn and form
 * @returns Extended mutation result with hasFieldErrors flag
 *
 * @example
 * ```tsx
 * interface FormData {
 *   email: string;
 *   password: string;
 * }
 *
 * function LoginForm() {
 *   const form = useForm<FormData>();
 *
 *   const mutation = useApiMutation({
 *     mutationFn: (data: FormData) => api.login(data),
 *     form,
 *     onSuccess: () => {
 *       navigate('/dashboard');
 *     },
 *   });
 *
 *   return (
 *     <form onSubmit={form.handleSubmit((data) => mutation.mutate(data))}>
 *       <input {...form.register('email')} />
 *       {form.formState.errors.email && (
 *         <span className="text-red-500">
 *           {form.formState.errors.email.message}
 *         </span>
 *       )}
 *
 *       <input type="password" {...form.register('password')} />
 *       {form.formState.errors.password && (
 *         <span className="text-red-500">
 *           {form.formState.errors.password.message}
 *         </span>
 *       )}
 *
 *       <button type="submit" disabled={mutation.isPending}>
 *         {mutation.isPending ? 'Logging in...' : 'Login'}
 *       </button>
 *
 *       {mutation.isError && !mutation.hasFieldErrors && (
 *         <div className="text-red-500">
 *           An unexpected error occurred. Please try again.
 *         </div>
 *       )}
 *     </form>
 *   );
 * }
 * ```
 */
export function useApiMutation<TVariables extends FieldValues, TData, TError = ApiError>(
  options: UseApiMutationOptions<TVariables, TData, TError>
): UseApiMutationResult<TData, TVariables, TError> {
  const { form, onError, ...mutationOptions } = options;
  const [hasFieldErrors, setHasFieldErrors] = useState(false);

  // Wrap the onError callback to handle validation errors
  const handleError = useCallback(
    (error: TError, variables: TVariables, context: unknown) => {
      // Clear previous field errors state
      setHasFieldErrors(false);

      // Check if this is a validation error
      if (error instanceof ApiError && isApiValidationException(error)) {
        const appliedCount = applyApiValidationErrors(form, error);
        if (appliedCount > 0) {
          setHasFieldErrors(true);
        }
      }

      // Call user-provided onError if present
      if (onError) {
        // Cast context to the expected type from UseMutationOptions
        (onError as (error: TError, variables: TVariables, context: unknown) => void)(
          error,
          variables,
          context
        );
      }
    },
    [form, onError]
  );

  const mutation = useMutation<TData, TError, TVariables>({
    ...mutationOptions,
    onError: handleError,
  });

  // Return extended mutation result
  return {
    ...mutation,
    hasFieldErrors,
  };
}

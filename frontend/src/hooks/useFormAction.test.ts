/**
 * Tests for useFormAction hook and utilities.
 *
 * @see NEM-3356 - Implement useActionState and useFormStatus for forms
 */

import { renderHook, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
  createFormAction,
  useFormAction,
  createInitialState,
  extractValidationErrors,
  getErrorMessage,
  isActionPending,
  isActionSuccess,
  isActionError,
  hasFieldErrors,
  getFieldError,
  type FormActionState,
} from './useFormAction';
import { ApiError } from '../services/api';

// Mock the logger
vi.mock('../services/logger', () => ({
  logger: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
  },
}));

describe('useFormAction', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('createInitialState', () => {
    it('creates default initial state with idle status', () => {
      const state = createInitialState();

      expect(state).toEqual({
        status: 'idle',
      });
    });

    it('allows overriding initial state', () => {
      const state = createInitialState({
        data: { name: 'Test' },
        status: 'success',
      });

      expect(state).toEqual({
        status: 'success',
        data: { name: 'Test' },
      });
    });
  });

  describe('extractValidationErrors', () => {
    it('returns empty object for non-ApiError', () => {
      const errors = extractValidationErrors(new Error('Test'));
      expect(errors).toEqual({});
    });

    it('returns empty object for ApiError without data', () => {
      const error = new ApiError(422, 'Validation error');
      const errors = extractValidationErrors(error);
      expect(errors).toEqual({});
    });

    it('extracts validation_errors format', () => {
      const error = new ApiError(422, 'Validation error', {
        validation_errors: [
          { field: 'email', message: 'Invalid email' },
          { field: 'name', message: 'Name is required' },
        ],
      });

      const errors = extractValidationErrors(error);

      expect(errors).toEqual({
        email: 'Invalid email',
        name: 'Name is required',
      });
    });

    it('extracts FastAPI HTTPValidationError format', () => {
      const error = new ApiError(422, 'Validation error', {
        detail: [
          { loc: ['body', 'email'], msg: 'Invalid email format', type: 'value_error' },
          { loc: ['body', 'profile', 'name'], msg: 'Too short', type: 'value_error' },
        ],
      });

      const errors = extractValidationErrors(error);

      expect(errors).toEqual({
        email: 'Invalid email format',
        'profile.name': 'Too short',
      });
    });

    it('handles array indices in FastAPI format', () => {
      const error = new ApiError(422, 'Validation error', {
        detail: [
          { loc: ['body', 'items', 0, 'name'], msg: 'Required', type: 'value_error' },
        ],
      });

      const errors = extractValidationErrors(error);

      expect(errors).toEqual({
        'items.0.name': 'Required',
      });
    });
  });

  describe('getErrorMessage', () => {
    it('returns message from standard Error', () => {
      const error = new Error('Something went wrong');
      expect(getErrorMessage(error)).toBe('Something went wrong');
    });

    it('returns RFC 7807 detail from ApiError', () => {
      const error = new ApiError(400, 'Bad Request', undefined, {
        type: 'about:blank',
        title: 'Bad Request',
        status: 400,
        detail: 'The request body is invalid.',
      });

      expect(getErrorMessage(error)).toBe('The request body is invalid.');
    });

    it('returns default message for non-Error', () => {
      expect(getErrorMessage('string error')).toBe('An unexpected error occurred');
      expect(getErrorMessage(null)).toBe('An unexpected error occurred');
      expect(getErrorMessage(undefined)).toBe('An unexpected error occurred');
    });

    it('uses custom transformer when provided', () => {
      const error = new Error('Internal error: DB_CONN_FAIL');
      const transformer = (err: Error) => `Custom: ${err.message}`;

      expect(getErrorMessage(error, transformer)).toBe('Custom: Internal error: DB_CONN_FAIL');
    });
  });

  describe('state helper functions', () => {
    it('isActionPending returns true for pending status', () => {
      expect(isActionPending({ status: 'pending' })).toBe(true);
      expect(isActionPending({ status: 'idle' })).toBe(false);
      expect(isActionPending({ status: 'success' })).toBe(false);
      expect(isActionPending({ status: 'error' })).toBe(false);
    });

    it('isActionSuccess returns true for success status', () => {
      expect(isActionSuccess({ status: 'success' })).toBe(true);
      expect(isActionSuccess({ status: 'idle' })).toBe(false);
      expect(isActionSuccess({ status: 'pending' })).toBe(false);
      expect(isActionSuccess({ status: 'error' })).toBe(false);
    });

    it('isActionError returns true for error status', () => {
      expect(isActionError({ status: 'error' })).toBe(true);
      expect(isActionError({ status: 'idle' })).toBe(false);
      expect(isActionError({ status: 'pending' })).toBe(false);
      expect(isActionError({ status: 'success' })).toBe(false);
    });

    it('hasFieldErrors returns true when error state has field errors', () => {
      expect(hasFieldErrors({ status: 'error', fieldErrors: { email: 'Invalid' } })).toBe(true);
      expect(hasFieldErrors({ status: 'error' })).toBe(false);
      expect(hasFieldErrors({ status: 'error', fieldErrors: {} })).toBe(false);
      expect(hasFieldErrors({ status: 'success', fieldErrors: { email: 'Invalid' } })).toBe(false);
    });

    it('getFieldError returns error for specific field', () => {
      const state: FormActionState = {
        status: 'error',
        fieldErrors: {
          email: 'Invalid email',
          name: 'Required',
        },
      };

      expect(getFieldError(state, 'email')).toBe('Invalid email');
      expect(getFieldError(state, 'name')).toBe('Required');
      expect(getFieldError(state, 'missing')).toBeUndefined();
    });
  });

  describe('createFormAction', () => {
    it('returns success state on successful handler execution', async () => {
      const handler = vi.fn().mockResolvedValue({ id: 1, name: 'Test' });
      const action = createFormAction(handler);

      const formData = new FormData();
      formData.append('name', 'Test');

      const result = await action({ status: 'idle' }, formData);

      expect(result.status).toBe('success');
      expect(result.data).toEqual({ id: 1, name: 'Test' });
      expect(result.timestamp).toBeDefined();
      expect(handler).toHaveBeenCalledWith(formData);
    });

    it('calls onSuccess callback on success', async () => {
      const onSuccess = vi.fn();
      const handler = vi.fn().mockResolvedValue({ saved: true });
      const action = createFormAction(handler, { onSuccess });

      await action({ status: 'idle' }, new FormData());

      expect(onSuccess).toHaveBeenCalledWith({ saved: true });
    });

    it('returns error state on handler failure', async () => {
      const handler = vi.fn().mockRejectedValue(new Error('Network error'));
      const action = createFormAction(handler);

      const result = await action({ status: 'idle' }, new FormData());

      expect(result.status).toBe('error');
      expect(result.error).toBe('Network error');
      expect(result.timestamp).toBeDefined();
    });

    it('extracts field errors from ApiError', async () => {
      const apiError = new ApiError(422, 'Validation failed', {
        validation_errors: [
          { field: 'email', message: 'Invalid format' },
        ],
      });
      const handler = vi.fn().mockRejectedValue(apiError);
      const action = createFormAction(handler);

      const result = await action({ status: 'idle' }, new FormData());

      expect(result.status).toBe('error');
      expect(result.fieldErrors).toEqual({ email: 'Invalid format' });
    });

    it('calls onError callback on failure', async () => {
      const onError = vi.fn();
      const error = new Error('Failed');
      const handler = vi.fn().mockRejectedValue(error);
      const action = createFormAction(handler, { onError });

      await action({ status: 'idle' }, new FormData());

      expect(onError).toHaveBeenCalledWith(error);
    });

    it('uses custom error transformer', async () => {
      const handler = vi.fn().mockRejectedValue(new Error('DB_ERROR'));
      const action = createFormAction(handler, {
        transformError: (err) => `Custom: ${err.message}`,
      });

      const result = await action({ status: 'idle' }, new FormData());

      expect(result.error).toBe('Custom: DB_ERROR');
    });
  });

  describe('useFormAction hook', () => {
    it('returns a memoized action function', () => {
      const handler = vi.fn().mockResolvedValue({});

      const { result, rerender } = renderHook(
        ({ handler }) => useFormAction(handler),
        { initialProps: { handler } }
      );

      const firstAction = result.current;
      rerender({ handler });
      const secondAction = result.current;

      // Action should be stable when handler reference is stable
      expect(firstAction).toBe(secondAction);
    });

    it('executes handler and returns success state', async () => {
      const handler = vi.fn().mockResolvedValue({ result: 'ok' });

      const { result } = renderHook(() => useFormAction(handler));

      let actionResult: FormActionState<{ result: string }> | undefined;
      await act(async () => {
        actionResult = await result.current({ status: 'idle' }, new FormData()) as FormActionState<{ result: string }>;
      });

      expect(actionResult!.status).toBe('success');
      expect(actionResult!.data).toEqual({ result: 'ok' });
    });

    it('handles errors and returns error state', async () => {
      const handler = vi.fn().mockRejectedValue(new Error('Action failed'));

      const { result } = renderHook(() => useFormAction(handler));

      let actionResult: FormActionState;
      await act(async () => {
        actionResult = await result.current({ status: 'idle' }, new FormData());
      });

      expect(actionResult!.status).toBe('error');
      expect(actionResult!.error).toBe('Action failed');
    });

    it('calls callbacks when provided', async () => {
      const onSuccess = vi.fn();
      const onError = vi.fn();
      const handler = vi.fn().mockResolvedValue({ ok: true });

      const { result } = renderHook(() =>
        useFormAction(handler, { onSuccess, onError })
      );

      await act(async () => {
        await result.current({ status: 'idle' }, new FormData());
      });

      expect(onSuccess).toHaveBeenCalledWith({ ok: true });
      expect(onError).not.toHaveBeenCalled();
    });
  });
});

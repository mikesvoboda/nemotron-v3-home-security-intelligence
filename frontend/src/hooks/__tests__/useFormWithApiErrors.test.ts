/**
 * @fileoverview Tests for useFormWithApiErrors hook.
 *
 * This hook provides utilities for mapping API validation errors to
 * react-hook-form field-level errors.
 *
 * Tests follow TDD approach - written before implementation.
 */
import { renderHook, act, waitFor } from '@testing-library/react';
import { useForm, FieldValues } from 'react-hook-form';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { ApiError } from '../../services/api';
import { createQueryWrapper } from '../../test-utils/renderWithProviders';
import {
  ValidationFieldError,
  ApiValidationException,
  applyApiValidationErrors,
  useApiMutation,
  isApiValidationException,
  extractFieldPath,
} from '../useFormWithApiErrors';

// Test form data type with index signature for TypeScript compatibility
interface TestFormData extends FieldValues {
  username: string;
  email: string;
  password: string;
  profile: {
    firstName: string;
    lastName: string;
  };
}

/**
 * Helper hook that wraps useForm and subscribes to formState.errors.
 * This is needed because react-hook-form uses a Proxy for formState
 * that requires subscription to track changes.
 */
function useTestForm(defaultValues: TestFormData) {
  const form = useForm<TestFormData>({ defaultValues });
  // Subscribe to errors by accessing them - this enables reactivity
  // We need to read this value to trigger react-hook-form's proxy subscription
  void form.formState.errors;
  return form;
}

describe('ValidationFieldError interface', () => {
  it('should define field and message properties', () => {
    const error: ValidationFieldError = {
      field: 'email',
      message: 'Invalid email format',
    };

    expect(error.field).toBe('email');
    expect(error.message).toBe('Invalid email format');
  });
});

describe('ApiValidationException', () => {
  it('should extend ApiError with validation_errors array', () => {
    const validationErrors: ValidationFieldError[] = [
      { field: 'email', message: 'Email is required' },
      { field: 'password', message: 'Password too short' },
    ];

    const exception: ApiValidationException = {
      status: 422,
      message: 'Validation failed',
      validation_errors: validationErrors,
    };

    expect(exception.status).toBe(422);
    expect(exception.validation_errors).toHaveLength(2);
    expect(exception.validation_errors[0].field).toBe('email');
  });

  it('should support RFC 7807 problemDetails', () => {
    const exception: ApiValidationException = {
      status: 422,
      message: 'Validation failed',
      validation_errors: [{ field: 'name', message: 'Name is required' }],
      problemDetails: {
        type: 'https://api.example.com/errors/validation',
        title: 'Validation Error',
        status: 422,
        detail: 'One or more fields failed validation',
      },
    };

    expect(exception.problemDetails?.type).toBe('https://api.example.com/errors/validation');
  });
});

describe('isApiValidationException', () => {
  it('should return true for valid ApiValidationException', () => {
    const error = new ApiError(422, 'Validation failed', {
      validation_errors: [{ field: 'email', message: 'Invalid email' }],
    });

    expect(isApiValidationException(error)).toBe(true);
  });

  it('should return false for ApiError without validation_errors', () => {
    const error = new ApiError(500, 'Internal server error');

    expect(isApiValidationException(error)).toBe(false);
  });

  it('should return false for non-ApiError', () => {
    const error = new Error('Generic error');

    expect(isApiValidationException(error)).toBe(false);
  });

  it('should return false for null/undefined', () => {
    expect(isApiValidationException(null)).toBe(false);
    expect(isApiValidationException(undefined)).toBe(false);
  });

  it('should handle FastAPI HTTPValidationError format', () => {
    const error = new ApiError(422, 'Validation failed', {
      detail: [
        { loc: ['body', 'email'], msg: 'Invalid email format', type: 'value_error' },
        { loc: ['body', 'password'], msg: 'Password too short', type: 'string_too_short' },
      ],
    });

    expect(isApiValidationException(error)).toBe(true);
  });
});

describe('extractFieldPath', () => {
  it('should extract field name from simple path', () => {
    expect(extractFieldPath(['body', 'email'])).toBe('email');
  });

  it('should extract nested field path', () => {
    expect(extractFieldPath(['body', 'profile', 'firstName'])).toBe('profile.firstName');
  });

  it('should handle array indices in path', () => {
    expect(extractFieldPath(['body', 'items', 0, 'name'])).toBe('items.0.name');
  });

  it('should return last element if no body prefix', () => {
    expect(extractFieldPath(['email'])).toBe('email');
  });

  it('should handle empty array', () => {
    expect(extractFieldPath([])).toBe('');
  });

  it('should skip query prefix like body', () => {
    expect(extractFieldPath(['query', 'page'])).toBe('page');
  });
});

describe('applyApiValidationErrors', () => {
  const defaultTestFormData: TestFormData = {
    username: '',
    email: '',
    password: '',
    profile: { firstName: '', lastName: '' },
  };

  it('should set field errors from validation_errors array', async () => {
    const { result } = renderHook(() => useTestForm(defaultTestFormData), {
      wrapper: createQueryWrapper(),
    });

    const error: ApiValidationException = {
      status: 422,
      message: 'Validation failed',
      validation_errors: [
        { field: 'email', message: 'Invalid email format' },
        { field: 'password', message: 'Password must be at least 8 characters' },
      ],
    };

    act(() => {
      applyApiValidationErrors(result.current, error);
    });

    await waitFor(() => {
      expect(result.current.formState.errors.email?.message).toBe('Invalid email format');
      expect(result.current.formState.errors.password?.message).toBe(
        'Password must be at least 8 characters'
      );
    });
  });

  it('should handle nested field paths', async () => {
    const { result } = renderHook(() => useTestForm(defaultTestFormData), {
      wrapper: createQueryWrapper(),
    });

    const error: ApiValidationException = {
      status: 422,
      message: 'Validation failed',
      validation_errors: [{ field: 'profile.firstName', message: 'First name is required' }],
    };

    act(() => {
      applyApiValidationErrors(result.current, error);
    });

    await waitFor(() => {
      expect(result.current.formState.errors.profile?.firstName?.message).toBe(
        'First name is required'
      );
    });
  });

  it('should handle FastAPI HTTPValidationError format with loc array', async () => {
    const { result } = renderHook(() => useTestForm(defaultTestFormData), {
      wrapper: createQueryWrapper(),
    });

    // Simulate FastAPI's HTTPValidationError via ApiError.data
    const apiError = new ApiError(422, 'Validation failed', {
      detail: [
        { loc: ['body', 'email'], msg: 'Invalid email format', type: 'value_error' },
        { loc: ['body', 'profile', 'firstName'], msg: 'First name required', type: 'missing' },
      ],
    });

    act(() => {
      applyApiValidationErrors(result.current, apiError);
    });

    await waitFor(() => {
      expect(result.current.formState.errors.email?.message).toBe('Invalid email format');
      expect(result.current.formState.errors.profile?.firstName?.message).toBe(
        'First name required'
      );
    });
  });

  it('should set multiple field errors simultaneously', async () => {
    const { result } = renderHook(() => useTestForm(defaultTestFormData), {
      wrapper: createQueryWrapper(),
    });

    const error: ApiValidationException = {
      status: 422,
      message: 'Validation failed',
      validation_errors: [
        { field: 'username', message: 'Username already taken' },
        { field: 'email', message: 'Invalid email' },
        { field: 'password', message: 'Password too weak' },
      ],
    };

    act(() => {
      applyApiValidationErrors(result.current, error);
    });

    await waitFor(() => {
      const errors = result.current.formState.errors;
      expect(errors.username?.message).toBe('Username already taken');
      expect(errors.email?.message).toBe('Invalid email');
      expect(errors.password?.message).toBe('Password too weak');
    });
  });

  it('should not throw for unknown field names', () => {
    const { result } = renderHook(() => useTestForm(defaultTestFormData), {
      wrapper: createQueryWrapper(),
    });

    const error: ApiValidationException = {
      status: 422,
      message: 'Validation failed',
      validation_errors: [{ field: 'unknownField', message: 'Some error' }],
    };

    expect(() => {
      act(() => {
        applyApiValidationErrors(result.current, error);
      });
    }).not.toThrow();
  });

  it('should handle empty validation_errors array', () => {
    const { result } = renderHook(() => useTestForm(defaultTestFormData), {
      wrapper: createQueryWrapper(),
    });

    const error: ApiValidationException = {
      status: 422,
      message: 'Validation failed',
      validation_errors: [],
    };

    expect(() => {
      act(() => {
        applyApiValidationErrors(result.current, error);
      });
    }).not.toThrow();

    expect(Object.keys(result.current.formState.errors)).toHaveLength(0);
  });

  it('should return count of applied errors', () => {
    const { result } = renderHook(() => useTestForm(defaultTestFormData), {
      wrapper: createQueryWrapper(),
    });

    const error: ApiValidationException = {
      status: 422,
      message: 'Validation failed',
      validation_errors: [
        { field: 'email', message: 'Invalid email' },
        { field: 'password', message: 'Too short' },
      ],
    };

    let appliedCount: number = 0;
    act(() => {
      appliedCount = applyApiValidationErrors(result.current, error);
    });

    expect(appliedCount).toBe(2);
  });
});

describe('useApiMutation', () => {
  const mockMutationFn = vi.fn();
  const defaultTestFormData: TestFormData = {
    username: '',
    email: '',
    password: '',
    profile: { firstName: '', lastName: '' },
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should return mutation state and helpers', () => {
    const { result } = renderHook(
      () => {
        const form = useTestForm(defaultTestFormData);
        const mutation = useApiMutation({
          mutationFn: mockMutationFn,
          form,
        });
        return { form, mutation };
      },
      { wrapper: createQueryWrapper() }
    );

    expect(result.current.mutation.isPending).toBe(false);
    expect(result.current.mutation.isError).toBe(false);
    expect(result.current.mutation.isSuccess).toBe(false);
    expect(typeof result.current.mutation.mutate).toBe('function');
    expect(typeof result.current.mutation.mutateAsync).toBe('function');
  });

  it('should apply field errors on validation failure', async () => {
    const validationError = new ApiError(422, 'Validation failed', {
      validation_errors: [{ field: 'email', message: 'Email already exists' }],
    });

    mockMutationFn.mockRejectedValue(validationError);

    const { result } = renderHook(
      () => {
        const form = useTestForm(defaultTestFormData);
        const mutation = useApiMutation({
          mutationFn: mockMutationFn,
          form,
        });
        return { form, mutation };
      },
      { wrapper: createQueryWrapper() }
    );

    await act(async () => {
      try {
        await result.current.mutation.mutateAsync({
          username: 'test',
          email: 'test@example.com',
          password: 'pass123', // pragma: allowlist secret
          profile: { firstName: 'Test', lastName: 'User' },
        });
      } catch {
        // Expected to throw
      }
    });

    await waitFor(() => {
      expect(result.current.form.formState.errors.email?.message).toBe('Email already exists');
    });
  });

  it('should apply field errors from FastAPI HTTPValidationError', async () => {
    const validationError = new ApiError(422, 'Validation failed', {
      detail: [
        { loc: ['body', 'email'], msg: 'Invalid email format', type: 'value_error' },
        { loc: ['body', 'password'], msg: 'Password too short', type: 'string_too_short' },
      ],
    });

    mockMutationFn.mockRejectedValue(validationError);

    const { result } = renderHook(
      () => {
        const form = useTestForm(defaultTestFormData);
        const mutation = useApiMutation({
          mutationFn: mockMutationFn,
          form,
        });
        return { form, mutation };
      },
      { wrapper: createQueryWrapper() }
    );

    await act(async () => {
      try {
        await result.current.mutation.mutateAsync({
          username: 'test',
          email: 'invalid',
          password: 'short', // pragma: allowlist secret
          profile: { firstName: 'Test', lastName: 'User' },
        });
      } catch {
        // Expected to throw
      }
    });

    await waitFor(() => {
      expect(result.current.form.formState.errors.email?.message).toBe('Invalid email format');
      expect(result.current.form.formState.errors.password?.message).toBe('Password too short');
    });
  });

  it('should not set field errors for non-validation errors', async () => {
    const serverError = new ApiError(500, 'Internal server error');
    mockMutationFn.mockRejectedValue(serverError);

    const { result } = renderHook(
      () => {
        const form = useTestForm(defaultTestFormData);
        const mutation = useApiMutation({
          mutationFn: mockMutationFn,
          form,
        });
        return { form, mutation };
      },
      { wrapper: createQueryWrapper() }
    );

    await act(async () => {
      try {
        await result.current.mutation.mutateAsync({
          username: 'test',
          email: 'test@example.com',
          password: 'pass123', // pragma: allowlist secret
          profile: { firstName: 'Test', lastName: 'User' },
        });
      } catch {
        // Expected to throw
      }
    });

    await waitFor(() => {
      expect(result.current.mutation.isError).toBe(true);
    });

    expect(Object.keys(result.current.form.formState.errors)).toHaveLength(0);
  });

  it('should call onSuccess callback on successful mutation', async () => {
    const onSuccess = vi.fn();
    mockMutationFn.mockResolvedValue({ success: true });

    const { result } = renderHook(
      () => {
        const form = useTestForm(defaultTestFormData);
        const mutation = useApiMutation({
          mutationFn: mockMutationFn,
          form,
          onSuccess,
        });
        return { form, mutation };
      },
      { wrapper: createQueryWrapper() }
    );

    await act(async () => {
      await result.current.mutation.mutateAsync({
        username: 'test',
        email: 'test@example.com',
        password: 'pass123', // pragma: allowlist secret
        profile: { firstName: 'Test', lastName: 'User' },
      });
    });

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalled();
    });

    // Verify the first argument (data) matches
    expect(onSuccess.mock.calls[0][0]).toEqual({ success: true });
  });

  it('should call onError callback on mutation error', async () => {
    const onError = vi.fn();
    const error = new ApiError(500, 'Server error');
    mockMutationFn.mockRejectedValue(error);

    const { result } = renderHook(
      () => {
        const form = useTestForm(defaultTestFormData);
        const mutation = useApiMutation({
          mutationFn: mockMutationFn,
          form,
          onError,
        });
        return { form, mutation };
      },
      { wrapper: createQueryWrapper() }
    );

    await act(async () => {
      try {
        await result.current.mutation.mutateAsync({
          username: 'test',
          email: 'test@example.com',
          password: 'pass123', // pragma: allowlist secret
          profile: { firstName: 'Test', lastName: 'User' },
        });
      } catch {
        // Expected to throw
      }
    });

    await waitFor(() => {
      expect(onError).toHaveBeenCalled();
    });

    // Verify the first argument (error) matches
    expect(onError.mock.calls[0][0]).toBe(error);
  });

  it('should clear previous form errors before applying new ones', async () => {
    const { result } = renderHook(
      () => {
        const form = useTestForm(defaultTestFormData);
        const mutation = useApiMutation({
          mutationFn: mockMutationFn,
          form,
        });
        return { form, mutation };
      },
      { wrapper: createQueryWrapper() }
    );

    // First mutation with email error
    const firstError = new ApiError(422, 'Validation failed', {
      validation_errors: [{ field: 'email', message: 'Email error' }],
    });
    mockMutationFn.mockRejectedValue(firstError);

    await act(async () => {
      try {
        await result.current.mutation.mutateAsync({
          username: 'test',
          email: 'bad',
          password: 'pass', // pragma: allowlist secret
          profile: { firstName: 'Test', lastName: 'User' },
        });
      } catch {
        // Expected
      }
    });

    await waitFor(() => {
      expect(result.current.form.formState.errors.email?.message).toBe('Email error');
    });

    // Second mutation with password error (email should be cleared)
    const secondError = new ApiError(422, 'Validation failed', {
      validation_errors: [{ field: 'password', message: 'Password error' }],
    });
    mockMutationFn.mockRejectedValue(secondError);

    await act(async () => {
      try {
        await result.current.mutation.mutateAsync({
          username: 'test',
          email: 'good@example.com',
          password: 'bad', // pragma: allowlist secret
          profile: { firstName: 'Test', lastName: 'User' },
        });
      } catch {
        // Expected
      }
    });

    await waitFor(() => {
      expect(result.current.form.formState.errors.password?.message).toBe('Password error');
    });
  });

  it('should expose hasFieldErrors helper', async () => {
    const validationError = new ApiError(422, 'Validation failed', {
      validation_errors: [{ field: 'email', message: 'Invalid' }],
    });
    mockMutationFn.mockRejectedValue(validationError);

    const { result } = renderHook(
      () => {
        const form = useTestForm(defaultTestFormData);
        const mutation = useApiMutation({
          mutationFn: mockMutationFn,
          form,
        });
        return { form, mutation };
      },
      { wrapper: createQueryWrapper() }
    );

    expect(result.current.mutation.hasFieldErrors).toBe(false);

    await act(async () => {
      try {
        await result.current.mutation.mutateAsync({
          username: 'test',
          email: 'invalid',
          password: 'pass', // pragma: allowlist secret
          profile: { firstName: 'Test', lastName: 'User' },
        });
      } catch {
        // Expected
      }
    });

    await waitFor(() => {
      expect(result.current.mutation.hasFieldErrors).toBe(true);
    });
  });
});

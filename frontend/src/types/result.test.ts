/**
 * Tests for Result Type Pattern
 *
 * This module tests the Result type for explicit success/failure handling,
 * providing a type-safe alternative to try/catch for error propagation.
 */

import { describe, it, expect } from 'vitest';

import {
  Ok,
  Err,
  isOk,
  isErr,
  unwrap,
  unwrapOr,
  unwrapErr,
  map,
  mapErr,
  andThen,
  orElse,
  match,
  type Result,
} from './result';

// ============================================================================
// Test Data Types
// ============================================================================

interface User {
  id: number;
  name: string;
}

class ValidationError extends Error {
  constructor(
    message: string,
    public field: string
  ) {
    super(message);
    this.name = 'ValidationError';
  }
}

class NetworkError extends Error {
  constructor(
    message: string,
    public statusCode: number
  ) {
    super(message);
    this.name = 'NetworkError';
  }
}

// ============================================================================
// Factory Function Tests
// ============================================================================

describe('Result Factory Functions', () => {
  describe('Ok', () => {
    it('creates a success result with value', () => {
      const result = Ok(42);
      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.value).toBe(42);
      }
    });

    it('creates a success result with complex object', () => {
      const user: User = { id: 1, name: 'John' };
      const result = Ok(user);
      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.value).toEqual(user);
      }
    });

    it('creates a success result with null value', () => {
      const result = Ok(null);
      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.value).toBeNull();
      }
    });

    it('creates a success result with undefined value', () => {
      const result = Ok(undefined);
      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.value).toBeUndefined();
      }
    });

    it('creates a success result with array', () => {
      const items = [1, 2, 3];
      const result = Ok(items);
      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.value).toEqual([1, 2, 3]);
      }
    });
  });

  describe('Err', () => {
    it('creates an error result with Error object', () => {
      const error = new Error('Something went wrong');
      const result = Err(error);
      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error).toBe(error);
      }
    });

    it('creates an error result with custom error type', () => {
      const error = new ValidationError('Invalid email', 'email');
      const result = Err(error);
      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error).toBeInstanceOf(ValidationError);
        expect(result.error.field).toBe('email');
      }
    });

    it('creates an error result with string error', () => {
      const result: Result<number, string> = Err('Not found');
      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error).toBe('Not found');
      }
    });

    it('creates an error result with error object', () => {
      const errorInfo = { code: 'ERR_001', message: 'Invalid input' };
      const result: Result<number, typeof errorInfo> = Err(errorInfo);
      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error).toEqual(errorInfo);
      }
    });
  });
});

// ============================================================================
// Type Guard Tests
// ============================================================================

describe('Result Type Guards', () => {
  const successResult = Ok(42);
  const errorResult: Result<number, Error> = Err(new Error('Failed'));

  describe('isOk', () => {
    it('returns true for Ok result', () => {
      expect(isOk(successResult)).toBe(true);
    });

    it('returns false for Err result', () => {
      expect(isOk(errorResult)).toBe(false);
    });

    it('narrows type correctly', () => {
      const result: Result<User, Error> = Ok({ id: 1, name: 'John' });
      if (isOk(result)) {
        // TypeScript should know result.value is User
        expect(result.value.name).toBe('John');
      }
    });
  });

  describe('isErr', () => {
    it('returns true for Err result', () => {
      expect(isErr(errorResult)).toBe(true);
    });

    it('returns false for Ok result', () => {
      expect(isErr(successResult)).toBe(false);
    });

    it('narrows type correctly', () => {
      const result: Result<User, ValidationError> = Err(new ValidationError('Invalid', 'email'));
      if (isErr(result)) {
        // TypeScript should know result.error is ValidationError
        expect(result.error.field).toBe('email');
      }
    });
  });
});

// ============================================================================
// Unwrap Function Tests
// ============================================================================

describe('Result Unwrap Functions', () => {
  describe('unwrap', () => {
    it('returns value for Ok result', () => {
      const result = Ok(42);
      expect(unwrap(result)).toBe(42);
    });

    it('returns complex value for Ok result', () => {
      const user: User = { id: 1, name: 'John' };
      const result = Ok(user);
      expect(unwrap(result)).toEqual(user);
    });

    it('throws error for Err result', () => {
      const error = new Error('Failed');
      const result: Result<number, Error> = Err(error);
      expect(() => unwrap(result)).toThrow('Failed');
    });

    it('throws with Error type message for Err result', () => {
      const result: Result<number, Error> = Err(new Error('Custom message'));
      expect(() => unwrap(result)).toThrow('Custom message');
    });

    it('throws with string error for non-Error type', () => {
      const result: Result<number, string> = Err('String error');
      expect(() => unwrap(result)).toThrow('String error');
    });
  });

  describe('unwrapOr', () => {
    it('returns value for Ok result', () => {
      const result = Ok(42);
      expect(unwrapOr(result, 0)).toBe(42);
    });

    it('returns default for Err result', () => {
      const result: Result<number, Error> = Err(new Error('Failed'));
      expect(unwrapOr(result, 0)).toBe(0);
    });

    it('returns default with complex type', () => {
      const defaultUser: User = { id: 0, name: 'Default' };
      const result: Result<User, Error> = Err(new Error('Not found'));
      expect(unwrapOr(result, defaultUser)).toEqual(defaultUser);
    });

    it('does not evaluate default lazily', () => {
      const result = Ok(42);
      // Default value is passed but not used
      expect(unwrapOr(result, 999)).toBe(42);
    });
  });

  describe('unwrapErr', () => {
    it('returns error for Err result', () => {
      const error = new Error('Failed');
      const result: Result<number, Error> = Err(error);
      expect(unwrapErr(result)).toBe(error);
    });

    it('throws for Ok result', () => {
      const result = Ok(42);
      expect(() => unwrapErr(result)).toThrow('Called unwrapErr on an Ok result');
    });

    it('returns custom error type', () => {
      const error = new ValidationError('Invalid', 'email');
      const result: Result<User, ValidationError> = Err(error);
      const unwrapped = unwrapErr(result);
      expect(unwrapped).toBeInstanceOf(ValidationError);
      expect(unwrapped.field).toBe('email');
    });
  });
});

// ============================================================================
// Map Function Tests
// ============================================================================

describe('Result Map Functions', () => {
  describe('map', () => {
    it('transforms value for Ok result', () => {
      const result = Ok(5);
      const mapped = map(result, (x) => x * 2);
      expect(isOk(mapped)).toBe(true);
      if (isOk(mapped)) {
        expect(mapped.value).toBe(10);
      }
    });

    it('transforms to different type', () => {
      const result = Ok({ id: 1, name: 'John' });
      const mapped = map(result, (user) => user.name);
      expect(isOk(mapped)).toBe(true);
      if (isOk(mapped)) {
        expect(mapped.value).toBe('John');
      }
    });

    it('does not call function for Err result', () => {
      const error = new Error('Failed');
      const result: Result<number, Error> = Err(error);
      let called = false;
      const mapped = map(result, (x: number) => {
        called = true;
        return x * 2;
      });
      expect(isErr(mapped)).toBe(true);
      expect(called).toBe(false);
      if (isErr(mapped)) {
        expect(mapped.error).toBe(error);
      }
    });

    it('preserves error type', () => {
      const error = new ValidationError('Invalid', 'email');
      const result: Result<number, ValidationError> = Err(error);
      const mapped = map(result, (x: number) => x.toString());
      if (isErr(mapped)) {
        expect(mapped.error).toBeInstanceOf(ValidationError);
      }
    });
  });

  describe('mapErr', () => {
    it('transforms error for Err result', () => {
      const result: Result<number, string> = Err('Not found');
      const mapped = mapErr(result, (e) => new Error(e));
      expect(isErr(mapped)).toBe(true);
      if (isErr(mapped)) {
        expect(mapped.error).toBeInstanceOf(Error);
        expect(mapped.error.message).toBe('Not found');
      }
    });

    it('does not call function for Ok result', () => {
      const result = Ok(42);
      let called = false;
      const mapped = mapErr(result, (e: Error) => {
        called = true;
        return new Error(e.message);
      });
      expect(isOk(mapped)).toBe(true);
      expect(called).toBe(false);
      if (isOk(mapped)) {
        expect(mapped.value).toBe(42);
      }
    });

    it('transforms error type', () => {
      const result: Result<number, string> = Err('ERR_001');
      const mapped = mapErr(result, (code) => ({
        code,
        message: 'Error occurred',
      }));
      if (isErr(mapped)) {
        expect(mapped.error).toEqual({ code: 'ERR_001', message: 'Error occurred' });
      }
    });
  });
});

// ============================================================================
// Chaining Function Tests
// ============================================================================

describe('Result Chaining Functions', () => {
  describe('andThen', () => {
    it('chains Ok results', () => {
      const result = Ok(5);
      const chained = andThen(result, (x) => Ok(x * 2));
      expect(isOk(chained)).toBe(true);
      if (isOk(chained)) {
        expect(chained.value).toBe(10);
      }
    });

    it('short-circuits on Err', () => {
      const error = new Error('First error');
      const result: Result<number, Error> = Err(error);
      let called = false;
      const chained = andThen(result, (x: number) => {
        called = true;
        return Ok(x * 2);
      });
      expect(isErr(chained)).toBe(true);
      expect(called).toBe(false);
      if (isErr(chained)) {
        expect(chained.error).toBe(error);
      }
    });

    it('can return Err from function', () => {
      const result = Ok(5);
      const chained = andThen(result, (x) => (x > 10 ? Ok(x) : Err(new Error('Too small'))));
      expect(isErr(chained)).toBe(true);
      if (isErr(chained)) {
        expect(chained.error.message).toBe('Too small');
      }
    });

    it('chains multiple operations', () => {
      const parseNumber = (s: string): Result<number, Error> => {
        const n = parseInt(s, 10);
        return isNaN(n) ? Err(new Error('Not a number')) : Ok(n);
      };

      const double = (n: number): Result<number, Error> => Ok(n * 2);

      const result = andThen(parseNumber('21'), double);
      expect(isOk(result)).toBe(true);
      if (isOk(result)) {
        expect(result.value).toBe(42);
      }
    });
  });

  describe('orElse', () => {
    it('returns Ok unchanged', () => {
      const result = Ok(42);
      const recovered = orElse(result, () => Ok(0));
      expect(isOk(recovered)).toBe(true);
      if (isOk(recovered)) {
        expect(recovered.value).toBe(42);
      }
    });

    it('recovers from Err', () => {
      const result: Result<number, Error> = Err(new Error('Failed'));
      const recovered = orElse(result, () => Ok(0));
      expect(isOk(recovered)).toBe(true);
      if (isOk(recovered)) {
        expect(recovered.value).toBe(0);
      }
    });

    it('can return different error', () => {
      const result: Result<number, string> = Err('First error');
      const recovered = orElse(result, (e) => Err(new Error(`Wrapped: ${e}`)));
      expect(isErr(recovered)).toBe(true);
      if (isErr(recovered)) {
        expect(recovered.error.message).toBe('Wrapped: First error');
      }
    });

    it('receives error in recovery function', () => {
      const error = new NetworkError('Connection failed', 503);
      const result: Result<string, NetworkError> = Err(error);
      const recovered = orElse(result, (e) => {
        if (e.statusCode === 503) {
          return Ok('Service temporarily unavailable');
        }
        return Err(e);
      });
      expect(isOk(recovered)).toBe(true);
      if (isOk(recovered)) {
        expect(recovered.value).toBe('Service temporarily unavailable');
      }
    });
  });
});

// ============================================================================
// Pattern Matching Tests
// ============================================================================

describe('Result Pattern Matching', () => {
  describe('match', () => {
    it('calls ok handler for Ok result', () => {
      const result: Result<number, string> = Ok(42);
      const matched = match(result, {
        ok: (value: number) => `Success: ${String(value)}`,
        err: (error: string) => `Error: ${error}`,
      });
      expect(matched).toBe('Success: 42');
    });

    it('calls err handler for Err result', () => {
      const result: Result<number, Error> = Err(new Error('Failed'));
      const matched = match(result, {
        ok: (value: number) => `Success: ${String(value)}`,
        err: (error: Error) => `Error: ${error.message}`,
      });
      expect(matched).toBe('Error: Failed');
    });

    it('can return different types', () => {
      const okResult: Result<User, Error> = Ok({ id: 1, name: 'John' });
      const matchedOk = match(okResult, {
        ok: (user: User) => user.id,
        err: () => -1,
      });
      expect(matchedOk).toBe(1);

      const errResult: Result<User, Error> = Err(new Error('Not found'));
      const matchedErr = match(errResult, {
        ok: (user: User) => user.id,
        err: () => -1,
      });
      expect(matchedErr).toBe(-1);
    });

    it('works with complex transformations', () => {
      type ApiResponse = { status: 'success'; data: User } | { status: 'error'; message: string };

      const result: Result<User, ValidationError> = Ok({ id: 1, name: 'John' });
      const response: ApiResponse = match(result, {
        ok: (user: User): ApiResponse => ({ status: 'success' as const, data: user }),
        err: (e: ValidationError): ApiResponse => ({
          status: 'error' as const,
          message: e.message,
        }),
      });

      expect(response.status).toBe('success');
      if (response.status === 'success') {
        expect(response.data.name).toBe('John');
      }
    });

    it('handles void return type', () => {
      let okCalled = false;
      let errCalled = false;

      const okResult = Ok(42);
      match(okResult, {
        ok: () => {
          okCalled = true;
        },
        err: () => {
          errCalled = true;
        },
      });
      expect(okCalled).toBe(true);
      expect(errCalled).toBe(false);

      okCalled = false;
      const errResult: Result<number, Error> = Err(new Error('Failed'));
      match(errResult, {
        ok: () => {
          okCalled = true;
        },
        err: () => {
          errCalled = true;
        },
      });
      expect(okCalled).toBe(false);
      expect(errCalled).toBe(true);
    });
  });
});

// ============================================================================
// Type Inference Tests (Compile-time Verification)
// ============================================================================

describe('Result Type Inference', () => {
  it('infers value type from Ok', () => {
    const result = Ok({ id: 1, name: 'John' });
    // TypeScript should infer Result<{ id: number; name: string }, never>
    if (result.ok) {
      expect(result.value.id).toBe(1);
      expect(result.value.name).toBe('John');
    }
  });

  it('infers error type from Err', () => {
    const error = new ValidationError('Invalid', 'email');
    const result = Err(error);
    // TypeScript should infer Result<never, ValidationError>
    if (!result.ok) {
      expect(result.error.field).toBe('email');
    }
  });

  it('allows explicit type annotation', () => {
    const result: Result<number, string> = Math.random() > 0.5 ? Ok(42) : Err('Failed');
    // Both branches must be compatible with Result<number, string>
    expect(typeof result.ok).toBe('boolean');
  });

  it('narrows correctly in if/else', () => {
    // Test both branches with separate results
    const okResult: Result<User, Error> = Ok({ id: 1, name: 'John' });
    const errResult: Result<User, Error> = Err(new Error('Not found'));

    // Test Ok branch narrowing
    if (okResult.ok) {
      // result.value is User
      expect(okResult.value.name).toBe('John');
    }

    // Test Err branch narrowing
    if (!errResult.ok) {
      // result.error is Error
      expect(errResult.error.message).toBe('Not found');
    }
  });

  it('works with generic functions', () => {
    function processResult<T, E>(result: Result<T, E>): string {
      return result.ok ? 'success' : 'failure';
    }

    expect(processResult(Ok(42))).toBe('success');
    expect(processResult(Err(new Error('Failed')))).toBe('failure');
  });
});

// ============================================================================
// Edge Cases
// ============================================================================

describe('Result Edge Cases', () => {
  it('handles falsy values in Ok', () => {
    expect(isOk(Ok(0))).toBe(true);
    expect(unwrap(Ok(0))).toBe(0);

    expect(isOk(Ok(''))).toBe(true);
    expect(unwrap(Ok(''))).toBe('');

    expect(isOk(Ok(false))).toBe(true);
    expect(unwrap(Ok(false))).toBe(false);
  });

  it('handles null and undefined in Ok', () => {
    const nullResult = Ok(null);
    expect(isOk(nullResult)).toBe(true);
    expect(unwrap(nullResult)).toBeNull();

    const undefinedResult = Ok(undefined);
    expect(isOk(undefinedResult)).toBe(true);
    expect(unwrap(undefinedResult)).toBeUndefined();
  });

  it('handles nested Results', () => {
    const nested = Ok(Ok(42));
    expect(isOk(nested)).toBe(true);
    if (isOk(nested)) {
      const inner = nested.value;
      expect(isOk(inner)).toBe(true);
      if (isOk(inner)) {
        expect(inner.value).toBe(42);
      }
    }
  });

  it('handles Result with union error types', () => {
    type AppError = ValidationError | NetworkError;

    const validateUser = (name: string): Result<User, AppError> => {
      if (name.length === 0) {
        return Err(new ValidationError('Name is required', 'name'));
      }
      return Ok({ id: 1, name });
    };

    const result = validateUser('');
    if (isErr(result)) {
      if (result.error instanceof ValidationError) {
        expect(result.error.field).toBe('name');
      }
    }
  });
});

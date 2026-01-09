/**
 * Tests for Result Type
 *
 * Comprehensive tests for the Result type and all associated utilities.
 */

import { describe, it, expect, vi } from 'vitest';

import {
  ok,
  err,
  isOk,
  isErr,
  map,
  mapErr,
  flatMap,
  andThen,
  unwrap,
  unwrapOr,
  unwrapOrElse,
  unwrapErr,
  match,
  fromPromise,
  toPromise,
  all,
  allTuple,
} from './result';

import type { Result, Ok, Err } from './result';

// ============================================================================
// Factory Functions Tests
// ============================================================================

describe('ok', () => {
  it('creates an Ok result with the given value', () => {
    const result = ok(42);

    expect(result).toEqual({ _tag: 'Ok', value: 42 });
  });

  it('works with different types', () => {
    expect(ok('hello')).toEqual({ _tag: 'Ok', value: 'hello' });
    expect(ok({ name: 'test' })).toEqual({ _tag: 'Ok', value: { name: 'test' } });
    expect(ok([1, 2, 3])).toEqual({ _tag: 'Ok', value: [1, 2, 3] });
    expect(ok(null)).toEqual({ _tag: 'Ok', value: null });
    expect(ok(undefined)).toEqual({ _tag: 'Ok', value: undefined });
  });

  it('preserves the type of the value', () => {
    const result: Ok<number> = ok(42);
    expect(result.value).toBe(42);

    const stringResult: Ok<string> = ok('test');
    expect(stringResult.value).toBe('test');
  });
});

describe('err', () => {
  it('creates an Err result with the given error', () => {
    const result = err('something went wrong');

    expect(result).toEqual({ _tag: 'Err', error: 'something went wrong' });
  });

  it('works with Error objects', () => {
    const error = new Error('test error');
    const result = err(error);

    expect(result._tag).toBe('Err');
    expect(result.error).toBe(error);
    expect(result.error.message).toBe('test error');
  });

  it('works with different error types', () => {
    expect(err('string error')).toEqual({ _tag: 'Err', error: 'string error' });
    expect(err({ code: 404 })).toEqual({ _tag: 'Err', error: { code: 404 } });
    expect(err(500)).toEqual({ _tag: 'Err', error: 500 });
  });

  it('preserves the type of the error', () => {
    const result: Err<string> = err('error');
    expect(result.error).toBe('error');

    interface ValidationError {
      field: string;
      message: string;
    }

    const validationResult: Err<ValidationError> = err({ field: 'email', message: 'Invalid' });
    expect(validationResult.error.field).toBe('email');
  });
});

// ============================================================================
// Type Guards Tests
// ============================================================================

describe('isOk', () => {
  it('returns true for Ok results', () => {
    expect(isOk(ok(42))).toBe(true);
    expect(isOk(ok('test'))).toBe(true);
    expect(isOk(ok(null))).toBe(true);
  });

  it('returns false for Err results', () => {
    expect(isOk(err('error'))).toBe(false);
    expect(isOk(err(new Error()))).toBe(false);
  });

  it('narrows the type correctly', () => {
    const result: Result<number, string> = ok(42);

    if (isOk(result)) {
      // TypeScript should know this is Ok<number>
      const value: number = result.value;
      expect(value).toBe(42);
    }
  });
});

describe('isErr', () => {
  it('returns true for Err results', () => {
    expect(isErr(err('error'))).toBe(true);
    expect(isErr(err(new Error()))).toBe(true);
  });

  it('returns false for Ok results', () => {
    expect(isErr(ok(42))).toBe(false);
    expect(isErr(ok('test'))).toBe(false);
  });

  it('narrows the type correctly', () => {
    const result: Result<number, string> = err('oops');

    if (isErr(result)) {
      // TypeScript should know this is Err<string>
      const error: string = result.error;
      expect(error).toBe('oops');
    }
  });
});

// ============================================================================
// Transformation Functions Tests
// ============================================================================

describe('map', () => {
  it('transforms Ok values', () => {
    const result = ok(10);
    const doubled = map(result, (n) => n * 2);

    expect(doubled).toEqual({ _tag: 'Ok', value: 20 });
  });

  it('does not transform Err values', () => {
    const result: Result<number, string> = err('error');
    const doubled = map(result, (n: number) => n * 2);

    expect(doubled).toEqual({ _tag: 'Err', error: 'error' });
  });

  it('can change the value type', () => {
    const result = ok(42);
    const stringified = map(result, (n) => n.toString());

    expect(stringified).toEqual({ _tag: 'Ok', value: '42' });
  });

  it('chains multiple maps', () => {
    const result = ok(5);
    const final = map(map(result, (n) => n * 2), (n) => n + 1);

    expect(final).toEqual({ _tag: 'Ok', value: 11 });
  });
});

describe('mapErr', () => {
  it('transforms Err values', () => {
    const result: Result<number, string> = err('error');
    const mapped = mapErr(result, (e) => new Error(e));

    expect(isErr(mapped)).toBe(true);
    if (isErr(mapped)) {
      expect(mapped.error).toBeInstanceOf(Error);
      expect(mapped.error.message).toBe('error');
    }
  });

  it('does not transform Ok values', () => {
    const result: Result<number, string> = ok(42);
    const mapped = mapErr(result, (e: string) => new Error(e));

    expect(mapped).toEqual({ _tag: 'Ok', value: 42 });
  });

  it('can change the error type', () => {
    const result: Result<number, string> = err('404');
    const mapped = mapErr(result, (e) => parseInt(e, 10));

    expect(mapped).toEqual({ _tag: 'Err', error: 404 });
  });
});

describe('flatMap', () => {
  const validatePositive = (n: number): Result<number, string> =>
    n > 0 ? ok(n) : err('Must be positive');

  const validateEven = (n: number): Result<number, string> =>
    n % 2 === 0 ? ok(n) : err('Must be even');

  it('chains successful results', () => {
    const result = flatMap(ok(4), validatePositive);

    expect(result).toEqual({ _tag: 'Ok', value: 4 });
  });

  it('short-circuits on error', () => {
    const result = flatMap(ok(-2), validatePositive);

    expect(result).toEqual({ _tag: 'Err', error: 'Must be positive' });
  });

  it('does not call fn on Err input', () => {
    const fn = vi.fn(validatePositive);
    const result = flatMap(err('already failed'), fn);

    expect(fn).not.toHaveBeenCalled();
    expect(result).toEqual({ _tag: 'Err', error: 'already failed' });
  });

  it('chains multiple validations', () => {
    const result = flatMap(flatMap(ok(4), validatePositive), validateEven);

    expect(result).toEqual({ _tag: 'Ok', value: 4 });
  });

  it('fails on first invalid validation', () => {
    const result = flatMap(flatMap(ok(-4), validatePositive), validateEven);

    expect(result).toEqual({ _tag: 'Err', error: 'Must be positive' });
  });
});

describe('andThen', () => {
  it('is an alias for flatMap', () => {
    expect(andThen).toBe(flatMap);
  });
});

// ============================================================================
// Extraction Functions Tests
// ============================================================================

describe('unwrap', () => {
  it('returns the value for Ok results', () => {
    expect(unwrap(ok(42))).toBe(42);
    expect(unwrap(ok('test'))).toBe('test');
  });

  it('throws the error for Err results', () => {
    const error = new Error('test error');
    expect(() => unwrap(err(error))).toThrow(error);
  });

  it('throws string errors directly', () => {
    expect(() => unwrap(err('string error'))).toThrow('string error');
  });
});

describe('unwrapOr', () => {
  it('returns the value for Ok results', () => {
    expect(unwrapOr(ok(42), 0)).toBe(42);
  });

  it('returns the default for Err results', () => {
    expect(unwrapOr(err('error'), 0)).toBe(0);
  });

  it('works with different types', () => {
    expect(unwrapOr(err('error'), 'default')).toBe('default');
    expect(unwrapOr(err('error'), null)).toBe(null);
  });
});

describe('unwrapOrElse', () => {
  it('returns the value for Ok results', () => {
    const fn = vi.fn(() => 0);
    expect(unwrapOrElse(ok(42), fn)).toBe(42);
    expect(fn).not.toHaveBeenCalled();
  });

  it('calls the function for Err results', () => {
    const fn = vi.fn((e: string) => e.length);
    expect(unwrapOrElse(err('error'), fn)).toBe(5);
    expect(fn).toHaveBeenCalledWith('error');
  });

  it('passes the error to the function', () => {
    const result = unwrapOrElse(err({ code: 404 }), (e) => `Error code: ${e.code}`);
    expect(result).toBe('Error code: 404');
  });
});

describe('unwrapErr', () => {
  it('returns the error for Err results', () => {
    expect(unwrapErr(err('test error'))).toBe('test error');
    expect(unwrapErr(err(404))).toBe(404);
  });

  it('throws for Ok results', () => {
    expect(() => unwrapErr(ok(42))).toThrow('Called unwrapErr on Ok value');
  });
});

// ============================================================================
// Pattern Matching Tests
// ============================================================================

describe('match', () => {
  it('calls onOk handler for Ok results', () => {
    const result = match(ok(42), {
      onOk: (value) => `Value: ${value}`,
      onErr: (error) => `Error: ${String(error)}`,
    });

    expect(result).toBe('Value: 42');
  });

  it('calls onErr handler for Err results', () => {
    const result = match(err('oops'), {
      onOk: (value) => `Value: ${String(value)}`,
      onErr: (error) => `Error: ${String(error)}`,
    });

    expect(result).toBe('Error: oops');
  });

  it('supports different return types', () => {
    const numberResult = match(ok(5), {
      onOk: (v) => v * 2,
      onErr: () => 0,
    });

    expect(numberResult).toBe(10);
  });

  it('enables exhaustive handling', () => {
    const processResult = (r: Result<number, string>): string =>
      match(r, {
        onOk: (value) => `Got ${value}`,
        onErr: (error) => `Failed with ${error}`,
      });

    expect(processResult(ok(42))).toBe('Got 42');
    expect(processResult(err('bad'))).toBe('Failed with bad');
  });
});

// ============================================================================
// Async Utilities Tests
// ============================================================================

describe('fromPromise', () => {
  it('converts resolved promises to Ok', async () => {
    const result = await fromPromise(Promise.resolve(42));

    expect(result).toEqual({ _tag: 'Ok', value: 42 });
  });

  it('converts rejected promises to Err', async () => {
    const error = new Error('test error');
    const result = await fromPromise(Promise.reject(error));

    expect(isErr(result)).toBe(true);
    if (isErr(result)) {
      expect(result.error).toBe(error);
    }
  });

  it('handles string rejections', async () => {
    // eslint-disable-next-line @typescript-eslint/prefer-promise-reject-errors -- Testing non-Error rejection handling
    const result = await fromPromise(Promise.reject('string error'));

    expect(result).toEqual({ _tag: 'Err', error: 'string error' });
  });

  it('works with async functions', async () => {
    const asyncFn = async () => {
      await new Promise((resolve) => setTimeout(resolve, 1));
      return 'done';
    };

    const result = await fromPromise(asyncFn());

    expect(result).toEqual({ _tag: 'Ok', value: 'done' });
  });
});

describe('toPromise', () => {
  it('resolves for Ok results', async () => {
    const value = await toPromise(ok(42));

    expect(value).toBe(42);
  });

  it('rejects for Err results', async () => {
    const error = new Error('test error');

    await expect(toPromise(err(error))).rejects.toBe(error);
  });

  it('rejects with string errors', async () => {
    await expect(toPromise(err('string error'))).rejects.toBe('string error');
  });
});

// ============================================================================
// Combining Results Tests
// ============================================================================

describe('all', () => {
  it('combines all Ok results into an array', () => {
    const results = [ok(1), ok(2), ok(3)];
    const combined = all(results);

    expect(combined).toEqual({ _tag: 'Ok', value: [1, 2, 3] });
  });

  it('returns the first Err encountered', () => {
    const results: Result<number, string>[] = [ok(1), err('first error'), ok(3), err('second')];
    const combined = all(results);

    expect(combined).toEqual({ _tag: 'Err', error: 'first error' });
  });

  it('handles empty arrays', () => {
    const combined = all([]);

    expect(combined).toEqual({ _tag: 'Ok', value: [] });
  });

  it('works with single element arrays', () => {
    expect(all([ok(42)])).toEqual({ _tag: 'Ok', value: [42] });
    expect(all([err('error')])).toEqual({ _tag: 'Err', error: 'error' });
  });

  it('preserves order of values', () => {
    const results = [ok('a'), ok('b'), ok('c')];
    const combined = all(results);

    expect(combined).toEqual({ _tag: 'Ok', value: ['a', 'b', 'c'] });
  });
});

describe('allTuple', () => {
  it('combines a tuple of Results into a Result of a tuple', () => {
    const result = allTuple([ok(42), ok('hello'), ok(true)] as const);

    expect(isOk(result)).toBe(true);
    if (isOk(result)) {
      expect(result.value).toEqual([42, 'hello', true]);
    }
  });

  it('returns first error if any result is Err', () => {
    const result = allTuple([ok(1), err('oops'), ok(3)] as const);

    expect(isErr(result)).toBe(true);
    if (isErr(result)) {
      expect(result.error).toBe('oops');
    }
  });

  it('handles empty tuples', () => {
    const result = allTuple([] as const);

    expect(result).toEqual({ _tag: 'Ok', value: [] });
  });

  it('preserves types in the resulting tuple', () => {
    const result = allTuple([ok(42 as number), ok('test' as string)] as const);

    if (isOk(result)) {
      // This is a compile-time type check
      const [num, str] = result.value;
      expect(typeof num).toBe('number');
      expect(typeof str).toBe('string');
    }
  });
});

// ============================================================================
// Type Safety Tests
// ============================================================================

describe('type safety', () => {
  it('Result type discriminates correctly', () => {
    const result: Result<number, string> = Math.random() > 0.5 ? ok(42) : err('error');

    // This tests that TypeScript narrows types correctly
    if (result._tag === 'Ok') {
      expect(typeof result.value).toBe('number');
    } else {
      expect(typeof result.error).toBe('string');
    }
  });

  it('map preserves error type', () => {
    interface CustomError {
      code: number;
      message: string;
    }

    const result: Result<number, CustomError> = ok(42);
    const mapped: Result<string, CustomError> = map(result, (n) => n.toString());

    expect(isOk(mapped)).toBe(true);
  });

  it('flatMap requires compatible error types', () => {
    const validate = (n: number): Result<number, string> => (n > 0 ? ok(n) : err('invalid'));

    const result: Result<number, string> = ok(5);
    const validated: Result<number, string> = flatMap(result, validate);

    expect(validated).toEqual({ _tag: 'Ok', value: 5 });
  });
});

// ============================================================================
// Integration Tests
// ============================================================================

describe('integration scenarios', () => {
  it('handles a validation pipeline', () => {
    interface User {
      name: string;
      email: string;
      age: number;
    }

    const validateName = (user: Partial<User>): Result<Partial<User>, string> =>
      user.name && user.name.length > 0 ? ok(user) : err('Name is required');

    const validateEmail = (user: Partial<User>): Result<Partial<User>, string> =>
      user.email && user.email.includes('@') ? ok(user) : err('Invalid email');

    const validateAge = (user: Partial<User>): Result<User, string> =>
      user.age && user.age >= 18 ? ok(user as User) : err('Must be 18 or older');

    const validateUser = (input: Partial<User>): Result<User, string> =>
      flatMap(flatMap(validateName(input), validateEmail), validateAge);

    // Valid user
    const validResult = validateUser({ name: 'Alice', email: 'alice@example.com', age: 25 });
    expect(isOk(validResult)).toBe(true);

    // Invalid email
    const invalidEmail = validateUser({ name: 'Bob', email: 'invalid', age: 25 });
    expect(invalidEmail).toEqual({ _tag: 'Err', error: 'Invalid email' });

    // Under age
    const underAge = validateUser({ name: 'Charlie', email: 'charlie@test.com', age: 16 });
    expect(underAge).toEqual({ _tag: 'Err', error: 'Must be 18 or older' });
  });

  it('handles async operations with fromPromise', async () => {
    const fetchUser = async (id: number) => {
      await Promise.resolve(); // Simulate async operation
      if (id < 0) {
        throw new Error('Invalid ID');
      }
      return { id, name: 'Test User' };
    };

    const validResult = await fromPromise(fetchUser(1));
    expect(isOk(validResult)).toBe(true);
    if (isOk(validResult)) {
      expect(validResult.value.name).toBe('Test User');
    }

    const invalidResult = await fromPromise(fetchUser(-1));
    expect(isErr(invalidResult)).toBe(true);
    if (isErr(invalidResult)) {
      expect(invalidResult.error.message).toBe('Invalid ID');
    }
  });

  it('handles parallel operations with all', async () => {
    const fetchItem = async (id: number): Promise<Result<{ id: number }, string>> => {
      await new Promise((resolve) => setTimeout(resolve, 1));
      if (id === 3) {
        return err(`Item ${id} not found`);
      }
      return ok({ id });
    };

    // All succeed
    const results = await Promise.all([fetchItem(1), fetchItem(2)]);
    const combined = all(results);
    expect(isOk(combined)).toBe(true);
    if (isOk(combined)) {
      expect(combined.value).toEqual([{ id: 1 }, { id: 2 }]);
    }

    // One fails
    const resultsWithError = await Promise.all([fetchItem(1), fetchItem(3), fetchItem(2)]);
    const combinedWithError = all(resultsWithError);
    expect(combinedWithError).toEqual({ _tag: 'Err', error: 'Item 3 not found' });
  });
});

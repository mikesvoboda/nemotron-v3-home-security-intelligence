/**
 * Tests for tryCatch Utility
 *
 * This module tests the tryCatch utility for safely wrapping async operations
 * and converting exceptions into Result types.
 */

import { describe, it, expect, vi } from 'vitest';

import { tryCatch, tryCatchSync } from './tryCatch';
import { isOk, isErr } from '../types/result';

// ============================================================================
// Test Data Types
// ============================================================================

interface User {
  id: number;
  name: string;
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
// Async tryCatch Tests
// ============================================================================

describe('tryCatch (async)', () => {
  describe('success cases', () => {
    it('wraps successful async function in Ok', async () => {
      const result = await tryCatch(() => Promise.resolve(42));
      expect(isOk(result)).toBe(true);
      if (isOk(result)) {
        expect(result.value).toBe(42);
      }
    });

    it('wraps successful async function returning object', async () => {
      const user: User = { id: 1, name: 'John' };
      const result = await tryCatch(() => Promise.resolve(user));
      expect(isOk(result)).toBe(true);
      if (isOk(result)) {
        expect(result.value).toEqual(user);
      }
    });

    it('wraps successful async function returning null', async () => {
      const result = await tryCatch(() => Promise.resolve(null));
      expect(isOk(result)).toBe(true);
      if (isOk(result)) {
        expect(result.value).toBeNull();
      }
    });

    it('wraps successful async function returning undefined', async () => {
      const result = await tryCatch(() => Promise.resolve(undefined));
      expect(isOk(result)).toBe(true);
      if (isOk(result)) {
        expect(result.value).toBeUndefined();
      }
    });

    it('wraps successful async function returning array', async () => {
      const items = [1, 2, 3];
      const result = await tryCatch(() => Promise.resolve(items));
      expect(isOk(result)).toBe(true);
      if (isOk(result)) {
        expect(result.value).toEqual([1, 2, 3]);
      }
    });

    it('handles Promise.resolve', async () => {
      const result = await tryCatch(() => Promise.resolve('hello'));
      expect(isOk(result)).toBe(true);
      if (isOk(result)) {
        expect(result.value).toBe('hello');
      }
    });

    it('handles fetch-like async operations', async () => {
      const mockFetch = vi.fn().mockResolvedValue({ data: 'response' });
      const result = await tryCatch(() => mockFetch());
      expect(isOk(result)).toBe(true);
      expect(mockFetch).toHaveBeenCalled();
    });
  });

  describe('error cases', () => {
    it('wraps thrown Error in Err', async () => {
      const error = new Error('Something went wrong');
      const result = await tryCatch(() => Promise.reject(error));
      expect(isErr(result)).toBe(true);
      if (isErr(result)) {
        expect(result.error).toBe(error);
        expect(result.error.message).toBe('Something went wrong');
      }
    });

    it('wraps rejected Promise in Err', async () => {
      const error = new Error('Promise rejected');
      const result = await tryCatch(() => Promise.reject(error));
      expect(isErr(result)).toBe(true);
      if (isErr(result)) {
        expect(result.error).toBe(error);
      }
    });

    it('converts string error to Error object', async () => {
      // eslint-disable-next-line @typescript-eslint/prefer-promise-reject-errors
      const result = await tryCatch(() => Promise.reject('String error message'));
      expect(isErr(result)).toBe(true);
      if (isErr(result)) {
        expect(result.error).toBeInstanceOf(Error);
        expect(result.error.message).toBe('String error message');
      }
    });

    it('converts number error to Error object', async () => {
      // eslint-disable-next-line @typescript-eslint/prefer-promise-reject-errors
      const result = await tryCatch(() => Promise.reject(404));
      expect(isErr(result)).toBe(true);
      if (isErr(result)) {
        expect(result.error).toBeInstanceOf(Error);
        expect(result.error.message).toBe('404');
      }
    });

    it('converts null error to Error object', async () => {
      // eslint-disable-next-line @typescript-eslint/prefer-promise-reject-errors
      const result = await tryCatch(() => Promise.reject(null));
      expect(isErr(result)).toBe(true);
      if (isErr(result)) {
        expect(result.error).toBeInstanceOf(Error);
        expect(result.error.message).toBe('null');
      }
    });

    it('converts undefined error to Error object', async () => {
      // eslint-disable-next-line @typescript-eslint/prefer-promise-reject-errors
      const result = await tryCatch(() => Promise.reject(undefined));
      expect(isErr(result)).toBe(true);
      if (isErr(result)) {
        expect(result.error).toBeInstanceOf(Error);
        expect(result.error.message).toBe('undefined');
      }
    });

    it('converts object error to Error object', async () => {
      const errorObj = { code: 'ERR_001', message: 'Failed' };
      // eslint-disable-next-line @typescript-eslint/prefer-promise-reject-errors
      const result = await tryCatch(() => Promise.reject(errorObj));
      expect(isErr(result)).toBe(true);
      if (isErr(result)) {
        expect(result.error).toBeInstanceOf(Error);
        // String representation of object
        expect(result.error.message).toBe('[object Object]');
      }
    });

    it('preserves custom error types', async () => {
      const error = new NetworkError('Connection failed', 503);
      const result = await tryCatch(() => Promise.reject(error));
      expect(isErr(result)).toBe(true);
      if (isErr(result)) {
        expect(result.error).toBeInstanceOf(NetworkError);
        expect(result.error).toBeInstanceOf(Error);
        expect((result.error as NetworkError).statusCode).toBe(503);
      }
    });

    it('handles TypeError', async () => {
      const result = await tryCatch(() => {
        const obj: { method?: () => void } = {};
        // This will throw TypeError
        obj.method!();
        return Promise.resolve();
      });
      expect(isErr(result)).toBe(true);
      if (isErr(result)) {
        expect(result.error).toBeInstanceOf(TypeError);
      }
    });

    it('handles RangeError', async () => {
      const result = await tryCatch(() => {
        const arr = new Array(-1);
        return Promise.resolve(arr);
      });
      expect(isErr(result)).toBe(true);
      if (isErr(result)) {
        expect(result.error).toBeInstanceOf(RangeError);
      }
    });
  });

  describe('practical use cases', () => {
    it('handles async/await pattern', async () => {
      const fetchUser = (id: number): Promise<User> => {
        if (id <= 0) {
          return Promise.reject(new Error('Invalid user ID'));
        }
        return Promise.resolve({ id, name: 'John' });
      };

      const successResult = await tryCatch(() => fetchUser(1));
      expect(isOk(successResult)).toBe(true);
      if (isOk(successResult)) {
        expect(successResult.value.name).toBe('John');
      }

      const errorResult = await tryCatch(() => fetchUser(-1));
      expect(isErr(errorResult)).toBe(true);
      if (isErr(errorResult)) {
        expect(errorResult.error.message).toBe('Invalid user ID');
      }
    });

    it('handles chained promises', async () => {
      const result = await tryCatch(async () => {
        const step1 = await Promise.resolve(5);
        const step2 = await Promise.resolve(step1 * 2);
        return step2;
      });
      expect(isOk(result)).toBe(true);
      if (isOk(result)) {
        expect(result.value).toBe(10);
      }
    });

    it('handles JSON parsing', async () => {
      const validJson = '{"name": "John", "age": 30}';
      const invalidJson = '{invalid json}';

      const successResult = await tryCatch(() => Promise.resolve(JSON.parse(validJson) as unknown));
      expect(isOk(successResult)).toBe(true);
      if (isOk(successResult)) {
        expect((successResult.value as { name: string }).name).toBe('John');
      }

      const errorResult = await tryCatch(() => {
        JSON.parse(invalidJson);
        return Promise.resolve();
      });
      expect(isErr(errorResult)).toBe(true);
      if (isErr(errorResult)) {
        expect(errorResult.error).toBeInstanceOf(SyntaxError);
      }
    });

    it('handles timeout-like scenarios', async () => {
      const delay = (ms: number): Promise<void> =>
        new Promise((resolve) => setTimeout(resolve, ms));

      const result = await tryCatch(async () => {
        await delay(1);
        return 'completed';
      });
      expect(isOk(result)).toBe(true);
      if (isOk(result)) {
        expect(result.value).toBe('completed');
      }
    });
  });

  describe('type safety', () => {
    it('infers return type correctly', async () => {
      const result = await tryCatch(() => Promise.resolve({ id: 1, name: 'John' }));
      if (isOk(result)) {
        // TypeScript should know value has id and name properties
        const { id, name } = result.value;
        expect(id).toBe(1);
        expect(name).toBe('John');
      }
    });

    it('allows explicit type parameter', async () => {
      const result = await tryCatch<User>(() => Promise.resolve({ id: 1, name: 'John' }));
      if (isOk(result)) {
        const user: User = result.value;
        expect(user.id).toBe(1);
      }
    });
  });
});

// ============================================================================
// Synchronous tryCatchSync Tests
// ============================================================================

describe('tryCatchSync', () => {
  describe('success cases', () => {
    it('wraps successful sync function in Ok', () => {
      const result = tryCatchSync(() => 42);
      expect(isOk(result)).toBe(true);
      if (isOk(result)) {
        expect(result.value).toBe(42);
      }
    });

    it('wraps successful sync function returning object', () => {
      const user: User = { id: 1, name: 'John' };
      const result = tryCatchSync(() => user);
      expect(isOk(result)).toBe(true);
      if (isOk(result)) {
        expect(result.value).toEqual(user);
      }
    });

    it('wraps successful sync function returning null', () => {
      const result = tryCatchSync(() => null);
      expect(isOk(result)).toBe(true);
      if (isOk(result)) {
        expect(result.value).toBeNull();
      }
    });

    it('handles computation', () => {
      const result = tryCatchSync(() => {
        const a = 5;
        const b = 10;
        return a + b;
      });
      expect(isOk(result)).toBe(true);
      if (isOk(result)) {
        expect(result.value).toBe(15);
      }
    });
  });

  describe('error cases', () => {
    it('wraps thrown Error in Err', () => {
      const error = new Error('Sync error');
      const result = tryCatchSync(() => {
        throw error;
      });
      expect(isErr(result)).toBe(true);
      if (isErr(result)) {
        expect(result.error).toBe(error);
      }
    });

    it('converts string error to Error object', () => {
      const result = tryCatchSync(() => {
        // eslint-disable-next-line @typescript-eslint/only-throw-error
        throw 'String error';
      });
      expect(isErr(result)).toBe(true);
      if (isErr(result)) {
        expect(result.error).toBeInstanceOf(Error);
        expect(result.error.message).toBe('String error');
      }
    });

    it('preserves custom error types', () => {
      const error = new NetworkError('Failed', 500);
      const result = tryCatchSync(() => {
        throw error;
      });
      expect(isErr(result)).toBe(true);
      if (isErr(result)) {
        expect(result.error).toBeInstanceOf(NetworkError);
        expect((result.error as NetworkError).statusCode).toBe(500);
      }
    });
  });

  describe('practical use cases', () => {
    it('handles JSON parsing', () => {
      const validJson = '{"value": 42}';
      const invalidJson = 'not json';

      const successResult = tryCatchSync(() => JSON.parse(validJson));
      expect(isOk(successResult)).toBe(true);
      if (isOk(successResult)) {
        expect(successResult.value.value).toBe(42);
      }

      const errorResult = tryCatchSync(() => JSON.parse(invalidJson));
      expect(isErr(errorResult)).toBe(true);
    });

    it('handles array operations', () => {
      const arr = [1, 2, 3];

      const successResult = tryCatchSync(() => {
        const [first] = arr;
        if (first === undefined) throw new Error('Empty array');
        return first;
      });
      expect(isOk(successResult)).toBe(true);
      if (isOk(successResult)) {
        expect(successResult.value).toBe(1);
      }

      const errorResult = tryCatchSync(() => {
        const emptyArr: number[] = [];
        const [first] = emptyArr;
        if (first === undefined) throw new Error('Empty array');
        return first;
      });
      expect(isErr(errorResult)).toBe(true);
    });

    it('handles division operations', () => {
      const safeDivide = (a: number, b: number) =>
        tryCatchSync(() => {
          if (b === 0) throw new Error('Division by zero');
          return a / b;
        });

      const successResult = safeDivide(10, 2);
      expect(isOk(successResult)).toBe(true);
      if (isOk(successResult)) {
        expect(successResult.value).toBe(5);
      }

      const errorResult = safeDivide(10, 0);
      expect(isErr(errorResult)).toBe(true);
      if (isErr(errorResult)) {
        expect(errorResult.error.message).toBe('Division by zero');
      }
    });
  });

  describe('type safety', () => {
    it('infers return type correctly', () => {
      const result = tryCatchSync(() => ({ id: 1, name: 'John' }));
      if (isOk(result)) {
        const { id, name } = result.value;
        expect(id).toBe(1);
        expect(name).toBe('John');
      }
    });

    it('allows explicit type parameter', () => {
      const result = tryCatchSync<User>(() => ({ id: 1, name: 'John' }));
      if (isOk(result)) {
        const user: User = result.value;
        expect(user.id).toBe(1);
      }
    });
  });
});

// ============================================================================
// Edge Cases
// ============================================================================

describe('tryCatch Edge Cases', () => {
  it('handles nested tryCatch calls', async () => {
    const inner = await tryCatch(async () => {
      const result = await tryCatch(() => Promise.resolve(42));
      if (isOk(result)) {
        return result.value * 2;
      }
      throw new Error('Inner failed');
    });
    expect(isOk(inner)).toBe(true);
    if (isOk(inner)) {
      expect(inner.value).toBe(84);
    }
  });

  it('handles error in error handler (async)', async () => {
    // The function itself throws, but tryCatch catches it
    const result = await tryCatch(() => Promise.reject(new Error('Original error')));

    expect(isErr(result)).toBe(true);
    if (isErr(result)) {
      expect(result.error.message).toBe('Original error');
    }
  });

  it('handles falsy return values correctly', async () => {
    const zeroResult = await tryCatch(() => Promise.resolve(0));
    expect(isOk(zeroResult)).toBe(true);
    if (isOk(zeroResult)) {
      expect(zeroResult.value).toBe(0);
    }

    const emptyStringResult = await tryCatch(() => Promise.resolve(''));
    expect(isOk(emptyStringResult)).toBe(true);
    if (isOk(emptyStringResult)) {
      expect(emptyStringResult.value).toBe('');
    }

    const falseResult = await tryCatch(() => Promise.resolve(false));
    expect(isOk(falseResult)).toBe(true);
    if (isOk(falseResult)) {
      expect(falseResult.value).toBe(false);
    }
  });

  it('handles void-returning functions', async () => {
    let sideEffect = 0;
    const result = await tryCatch(() => {
      sideEffect = 1;
      return Promise.resolve();
    });
    expect(isOk(result)).toBe(true);
    expect(sideEffect).toBe(1);
    if (isOk(result)) {
      expect(result.value).toBeUndefined();
    }
  });

  it('handles generator-based async (async iterators)', async () => {
    function* generateNumbers() {
      yield 1;
      yield 2;
      yield 3;
    }

    const result = await tryCatch(() => {
      const numbers: number[] = [];
      for (const num of generateNumbers()) {
        numbers.push(num);
      }
      return Promise.resolve(numbers);
    });

    expect(isOk(result)).toBe(true);
    if (isOk(result)) {
      expect(result.value).toEqual([1, 2, 3]);
    }
  });
});

// ============================================================================
// Integration with Result Type
// ============================================================================

describe('tryCatch Integration with Result', () => {
  it('works with Result type guards', async () => {
    const result = await tryCatch(() => Promise.resolve(42));

    // Using type guards
    if (isOk(result)) {
      expect(result.value).toBe(42);
    } else {
      // This branch should not execute
      expect.fail('Expected Ok result');
    }
  });

  it('can be used with map from Result', async () => {
    const { map } = await import('../types/result');

    const result = await tryCatch(() => Promise.resolve(5));
    const mapped = map(result, (x: number) => x * 2);

    expect(isOk(mapped)).toBe(true);
    if (isOk(mapped)) {
      expect(mapped.value).toBe(10);
    }
  });

  it('can be used with match from Result', async () => {
    const { match } = await import('../types/result');

    const okResult = await tryCatch(() => Promise.resolve(42));
    const okMessage = match(okResult, {
      ok: (value: number) => `Success: ${String(value)}`,
      err: (error: Error) => `Error: ${error.message}`,
    });
    expect(okMessage).toBe('Success: 42');

    const errResult = await tryCatch(() => Promise.reject(new Error('Failed')));
    const errMessage = match(errResult, {
      ok: (value: unknown) => `Success: ${String(value)}`,
      err: (error: Error) => `Error: ${error.message}`,
    });
    expect(errMessage).toBe('Error: Failed');
  });

  it('can be used with unwrapOr from Result', async () => {
    const { unwrapOr } = await import('../types/result');

    const okResult = await tryCatch(() => Promise.resolve(42));
    expect(unwrapOr(okResult, 0)).toBe(42);

    const errResult = await tryCatch((): Promise<number> => Promise.reject(new Error('Failed')));
    expect(unwrapOr(errResult, 0)).toBe(0);
  });
});

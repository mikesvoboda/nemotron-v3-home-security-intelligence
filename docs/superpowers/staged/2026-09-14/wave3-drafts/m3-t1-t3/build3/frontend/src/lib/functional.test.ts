/**
 * Tests for Functional Programming Utilities
 *
 * Comprehensive tests for pipe, compose, curry, debounce, throttle, and other utilities.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  pipe,
  compose,
  curry,
  curry3,
  debounce,
  throttle,
  once,
  memoize,
  negate,
  constant,
  identity,
} from './functional';

// ============================================================================
// Function Composition Tests
// ============================================================================

describe('pipe', () => {
  it('composes a single function', () => {
    const double = (x: number) => x * 2;
    const piped = pipe(double);

    expect(piped(5)).toBe(10);
  });

  it('composes two functions left-to-right', () => {
    const double = (x: number) => x * 2;
    const addOne = (x: number) => x + 1;
    const piped = pipe(double, addOne);

    // 5 * 2 = 10, 10 + 1 = 11
    expect(piped(5)).toBe(11);
  });

  it('composes three functions left-to-right', () => {
    const double = (x: number) => x * 2;
    const addOne = (x: number) => x + 1;
    const toString = (x: number) => x.toString();
    const piped = pipe(double, addOne, toString);

    expect(piped(5)).toBe('11');
  });

  it('composes functions with different types', () => {
    const parse = (s: string) => parseInt(s, 10);
    const double = (n: number) => n * 2;
    const isPositive = (n: number) => n > 0;
    const piped = pipe(parse, double, isPositive);

    expect(piped('5')).toBe(true);
    expect(piped('-5')).toBe(false);
  });

  it('composes up to six functions', () => {
    const add1 = (x: number) => x + 1;
    const add2 = (x: number) => x + 2;
    const add3 = (x: number) => x + 3;
    const add4 = (x: number) => x + 4;
    const add5 = (x: number) => x + 5;
    const add6 = (x: number) => x + 6;
    const piped = pipe(add1, add2, add3, add4, add5, add6);

    // 0 + 1 + 2 + 3 + 4 + 5 + 6 = 21
    expect(piped(0)).toBe(21);
  });

  it('preserves this context', () => {
    const obj = {
      value: 10,
      getValue(this: { value: number }) {
        return this.value;
      },
    };

    const piped = pipe((x: number) => x * 2);
    expect(piped(obj.getValue())).toBe(20);
  });
});

describe('compose', () => {
  it('composes a single function', () => {
    const double = (x: number) => x * 2;
    const composed = compose(double);

    expect(composed(5)).toBe(10);
  });

  it('composes two functions right-to-left', () => {
    const double = (x: number) => x * 2;
    const addOne = (x: number) => x + 1;
    // compose(f, g) = f(g(x))
    const composed = compose(addOne, double);

    // double(5) = 10, addOne(10) = 11
    expect(composed(5)).toBe(11);
  });

  it('composes three functions right-to-left', () => {
    const double = (x: number) => x * 2;
    const addOne = (x: number) => x + 1;
    const toString = (x: number) => x.toString();
    // compose(f, g, h) = f(g(h(x)))
    const composed = compose(toString, addOne, double);

    // double(5) = 10, addOne(10) = 11, toString(11) = "11"
    expect(composed(5)).toBe('11');
  });

  it('composes functions with different types', () => {
    const parse = (s: string) => parseInt(s, 10);
    const double = (n: number) => n * 2;
    const isPositive = (n: number) => n > 0;
    // Right to left: parse -> double -> isPositive
    const composed = compose(isPositive, double, parse);

    expect(composed('5')).toBe(true);
    expect(composed('-5')).toBe(false);
  });

  it('composes up to six functions', () => {
    const add1 = (x: number) => x + 1;
    const add2 = (x: number) => x + 2;
    const add3 = (x: number) => x + 3;
    const add4 = (x: number) => x + 4;
    const add5 = (x: number) => x + 5;
    const add6 = (x: number) => x + 6;
    // Rightmost is executed first
    const composed = compose(add6, add5, add4, add3, add2, add1);

    // 0 + 1 + 2 + 3 + 4 + 5 + 6 = 21
    expect(composed(0)).toBe(21);
  });

  it('is the reverse of pipe', () => {
    const f = (x: number) => x * 2;
    const g = (x: number) => x + 1;
    const h = (x: number) => x - 3;

    const piped = pipe(f, g, h);
    const composed = compose(h, g, f);

    expect(piped(5)).toBe(composed(5));
  });
});

// ============================================================================
// Currying Tests
// ============================================================================

describe('curry', () => {
  it('curries a function of two arguments', () => {
    const add = curry((a: number, b: number) => a + b);

    // Full application
    expect(add(1, 2)).toBe(3);
  });

  it('allows partial application', () => {
    const add = curry((a: number, b: number) => a + b);

    const add5 = add(5);
    expect(add5(3)).toBe(8);
    expect(add5(10)).toBe(15);
  });

  it('works with different types', () => {
    const greet = curry((greeting: string, name: string) => `${greeting}, ${name}!`);

    expect(greet('Hello', 'World')).toBe('Hello, World!');

    const sayHello = greet('Hello');
    expect(sayHello('Alice')).toBe('Hello, Alice!');
    expect(sayHello('Bob')).toBe('Hello, Bob!');
  });

  it('is useful with array methods', () => {
    const multiply = curry((factor: number, x: number) => x * factor);

    const numbers = [1, 2, 3, 4];
    expect(numbers.map(multiply(2))).toEqual([2, 4, 6, 8]);
    expect(numbers.map(multiply(3))).toEqual([3, 6, 9, 12]);
  });

  it('preserves function behavior', () => {
    const original = (a: number, b: number) => a * b + a;
    const curried = curry(original);

    for (let a = 0; a < 5; a++) {
      for (let b = 0; b < 5; b++) {
        expect(curried(a, b)).toBe(original(a, b));
        expect(curried(a)(b)).toBe(original(a, b));
      }
    }
  });
});

describe('curry3', () => {
  it('curries a function of three arguments', () => {
    const add3 = curry3((a: number, b: number, c: number) => a + b + c);

    // Full application
    expect(add3(1, 2, 3)).toBe(6);
  });

  it('allows partial application with one argument', () => {
    const add3 = curry3((a: number, b: number, c: number) => a + b + c);

    const add10 = add3(10);
    expect(add10(2, 3)).toBe(15);
    expect(add10(5)(5)).toBe(20);
  });

  it('allows partial application with two arguments', () => {
    const add3 = curry3((a: number, b: number, c: number) => a + b + c);

    const add12 = add3(10, 2);
    expect(add12(3)).toBe(15);
    expect(add12(8)).toBe(20);
  });

  it('works with the replace example', () => {
    const replace = curry3((search: string, replacement: string, str: string) =>
      str.replace(search, replacement)
    );

    // Full application
    expect(replace('a', 'b', 'abc')).toBe('bbc');

    // Partial application
    const replaceA = replace('a');
    const replaceAWithB = replaceA('b');
    expect(replaceAWithB('aaa')).toBe('baa');

    // Two-arg partial
    const sanitizeLT = replace('<', '&lt;');
    expect(sanitizeLT('<script>')).toBe('&lt;script>');
  });
});

// ============================================================================
// Debounce Tests
// ============================================================================

describe('debounce', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('delays function execution', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);

    debounced();
    expect(fn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('only calls once for rapid successive calls', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);

    debounced();
    debounced();
    debounced();

    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('passes the last arguments', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);

    debounced('first');
    debounced('second');
    debounced('third');

    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledWith('third');
  });

  it('resets timer on each call', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);

    debounced();
    vi.advanceTimersByTime(50);
    debounced();
    vi.advanceTimersByTime(50);
    debounced();
    vi.advanceTimersByTime(50);

    expect(fn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(50);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('can be cancelled', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);

    debounced();
    debounced.cancel();

    vi.advanceTimersByTime(100);
    expect(fn).not.toHaveBeenCalled();
  });

  it('reports pending status', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);

    expect(debounced.pending()).toBe(false);

    debounced();
    expect(debounced.pending()).toBe(true);

    vi.advanceTimersByTime(100);
    expect(debounced.pending()).toBe(false);
  });

  it('can be flushed', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);

    debounced('flushed');
    debounced.flush();

    expect(fn).toHaveBeenCalledWith('flushed');
  });

  it('supports leading option', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100, { leading: true });

    debounced();
    expect(fn).toHaveBeenCalledTimes(1);

    debounced();
    debounced();
    expect(fn).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(2); // Trailing call
  });

  it('supports trailing: false option', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100, { leading: true, trailing: false });

    debounced();
    expect(fn).toHaveBeenCalledTimes(1);

    debounced();
    debounced();

    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(1); // No trailing call
  });
});

// ============================================================================
// Throttle Tests
// ============================================================================

describe('throttle', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('calls immediately by default (leading)', () => {
    const fn = vi.fn();
    const throttled = throttle(fn, 100);

    throttled();
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('limits calls to once per wait period', () => {
    const fn = vi.fn();
    const throttled = throttle(fn, 100);

    throttled();
    throttled();
    throttled();

    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('allows another call after wait period', () => {
    const fn = vi.fn();
    const throttled = throttle(fn, 100);

    throttled();
    vi.advanceTimersByTime(100);
    throttled();

    expect(fn).toHaveBeenCalledTimes(2);
  });

  it('calls trailing by default', () => {
    const fn = vi.fn();
    const throttled = throttle(fn, 100);

    throttled('first');
    throttled('second');
    throttled('third');

    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn).toHaveBeenCalledWith('first');

    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(2);
    expect(fn).toHaveBeenLastCalledWith('third');
  });

  it('can disable leading', () => {
    const fn = vi.fn();
    const throttled = throttle(fn, 100, { leading: false });

    throttled();
    expect(fn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('can disable trailing', () => {
    const fn = vi.fn();
    const throttled = throttle(fn, 100, { trailing: false });

    throttled('first');
    throttled('second');
    throttled('third');

    expect(fn).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(1); // No trailing call
  });

  it('can be cancelled', () => {
    const fn = vi.fn();
    const throttled = throttle(fn, 100);

    throttled();
    throttled();
    throttled.cancel();

    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(1); // Only the leading call
  });

  it('reports pending status', () => {
    const fn = vi.fn();
    const throttled = throttle(fn, 100);

    expect(throttled.pending()).toBe(false);

    throttled();
    throttled(); // This schedules a trailing call
    expect(throttled.pending()).toBe(true);

    vi.advanceTimersByTime(100);
    expect(throttled.pending()).toBe(false);
  });

  it('can be flushed', () => {
    const fn = vi.fn();
    const throttled = throttle(fn, 100);

    throttled('first');
    throttled('last');

    expect(fn).toHaveBeenCalledTimes(1);

    throttled.flush();
    expect(fn).toHaveBeenCalledTimes(2);
    expect(fn).toHaveBeenLastCalledWith('last');
  });
});

// ============================================================================
// Additional Utilities Tests
// ============================================================================

describe('once', () => {
  it('calls the function only once', () => {
    const fn = vi.fn(() => 'result');
    const onceFn = once(fn);

    expect(onceFn()).toBe('result');
    expect(onceFn()).toBe('result');
    expect(onceFn()).toBe('result');

    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('returns the same result on subsequent calls', () => {
    let counter = 0;
    const onceFn = once(() => ++counter);

    expect(onceFn()).toBe(1);
    expect(onceFn()).toBe(1);
    expect(onceFn()).toBe(1);
    expect(counter).toBe(1);
  });

  it('passes arguments to the first call', () => {
    const fn = vi.fn((a: number, b: number) => a + b);
    const onceFn = once(fn);

    expect(onceFn(1, 2)).toBe(3);
    expect(onceFn(10, 20)).toBe(3); // Returns cached result

    expect(fn).toHaveBeenCalledWith(1, 2);
    expect(fn).toHaveBeenCalledTimes(1);
  });
});

describe('memoize', () => {
  it('caches results based on first argument', () => {
    const fn = vi.fn((x: number) => x * 2);
    const memoized = memoize(fn);

    expect(memoized(5)).toBe(10);
    expect(memoized(5)).toBe(10);
    expect(memoized(3)).toBe(6);
    expect(memoized(5)).toBe(10);

    expect(fn).toHaveBeenCalledTimes(2); // 5 and 3
  });

  it('accepts custom key function', () => {
    const fn = vi.fn((a: number, b: number) => a + b);
    const memoized = memoize(fn, (a, b) => `${a}-${b}`);

    expect(memoized(1, 2)).toBe(3);
    expect(memoized(1, 2)).toBe(3);
    expect(memoized(2, 1)).toBe(3);

    expect(fn).toHaveBeenCalledTimes(2); // Different keys
  });

  it('handles objects with custom key', () => {
    interface Request {
      id: number;
      includeDetails: boolean;
    }

    const fn = vi.fn((req: Request) => `data-${req.id}-${req.includeDetails}`);
    const memoized = memoize(fn, (req) => `${req.id}-${req.includeDetails}`);

    expect(memoized({ id: 1, includeDetails: true })).toBe('data-1-true');
    expect(memoized({ id: 1, includeDetails: true })).toBe('data-1-true');
    expect(memoized({ id: 1, includeDetails: false })).toBe('data-1-false');

    expect(fn).toHaveBeenCalledTimes(2);
  });
});

describe('negate', () => {
  it('negates a predicate', () => {
    const isEven = (n: number) => n % 2 === 0;
    const isOdd = negate(isEven);

    expect(isOdd(1)).toBe(true);
    expect(isOdd(2)).toBe(false);
    expect(isOdd(3)).toBe(true);
    expect(isOdd(4)).toBe(false);
  });

  it('works with filter', () => {
    const isPositive = (n: number) => n > 0;
    const numbers = [-2, -1, 0, 1, 2];

    expect(numbers.filter(isPositive)).toEqual([1, 2]);
    expect(numbers.filter(negate(isPositive))).toEqual([-2, -1, 0]);
  });

  it('works with string predicates', () => {
    const isEmpty = (s: string) => s.length === 0;
    const isNotEmpty = negate(isEmpty);

    expect(isNotEmpty('')).toBe(false);
    expect(isNotEmpty('hello')).toBe(true);
  });
});

describe('constant', () => {
  it('returns a function that always returns the value', () => {
    const always42 = constant(42);

    expect(always42()).toBe(42);
    expect(always42()).toBe(42);
  });

  it('ignores arguments', () => {
    const alwaysHello = constant('hello');

    // @ts-expect-error - Testing that arguments are ignored
    expect(alwaysHello(1, 2, 3)).toBe('hello');
  });

  it('works with objects', () => {
    const obj = { a: 1 };
    const alwaysObj = constant(obj);

    expect(alwaysObj()).toBe(obj);
    expect(alwaysObj()).toBe(obj); // Same reference
  });

  it('works with null and undefined', () => {
    expect(constant(null)()).toBe(null);
    expect(constant(undefined)()).toBe(undefined);
  });
});

describe('identity', () => {
  it('returns the input unchanged', () => {
    expect(identity(42)).toBe(42);
    expect(identity('hello')).toBe('hello');
    expect(identity(null)).toBe(null);
    expect(identity(undefined)).toBe(undefined);
  });

  it('preserves object references', () => {
    const obj = { a: 1 };
    expect(identity(obj)).toBe(obj);
  });

  it('is useful as a default transformer', () => {
    const maybeTransform = <T>(value: T, shouldTransform: boolean, transform: (v: T) => T) => {
      const fn = shouldTransform ? transform : identity;
      return fn(value);
    };

    expect(maybeTransform(5, true, (x) => x * 2)).toBe(10);
    expect(maybeTransform(5, false, (x) => x * 2)).toBe(5);
  });

  it('is useful with array methods', () => {
    const values = [1, null, 2, undefined, 3];
    // Filter out falsy values while preserving types
    const filtered = values.filter((x): x is number => x !== null && x !== undefined);

    expect(filtered.map(identity)).toEqual([1, 2, 3]);
  });
});

// ============================================================================
// Integration Tests
// ============================================================================

describe('integration', () => {
  it('pipe and curry work together', () => {
    const add = curry((a: number, b: number) => a + b);
    const multiply = curry((a: number, b: number) => a * b);

    const transform = pipe(add(5), multiply(2));

    // (5 + 5) * 2 = 20
    expect(transform(5)).toBe(20);
  });

  it('compose and curry work together', () => {
    const add = curry((a: number, b: number) => a + b);
    const multiply = curry((a: number, b: number) => a * b);

    // Read right to left: multiply by 2, then add 5
    const transform = compose(add(5), multiply(2));

    // (5 * 2) + 5 = 15
    expect(transform(5)).toBe(15);
  });

  it('debounce and memoize work together', () => {
    vi.useFakeTimers();

    const expensive = vi.fn((x: number) => x * 2);
    const memoized = memoize(expensive);
    const debounced = debounce(memoized, 100);

    debounced(5);
    debounced(5);
    debounced(5);

    vi.advanceTimersByTime(100);

    expect(expensive).toHaveBeenCalledTimes(1);

    vi.useRealTimers();
  });

  it('creates a processing pipeline with error handling', () => {
    const parseNumber = (s: string) => {
      const n = parseInt(s, 10);
      if (isNaN(n)) throw new Error('Not a number');
      return n;
    };

    const safeParseNumber = (s: string) => {
      try {
        return parseNumber(s);
      } catch {
        return 0;
      }
    };

    const process = pipe(
      safeParseNumber,
      (n: number) => n * 2,
      (n: number) => n + 1
    );

    expect(process('5')).toBe(11);
    expect(process('invalid')).toBe(1); // 0 * 2 + 1
  });
});

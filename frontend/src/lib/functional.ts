/**
 * Functional Programming Utilities
 *
 * A collection of utility functions for functional programming patterns in TypeScript.
 * These utilities enable point-free composition, currying, and controlled execution timing.
 *
 * @example
 * ```ts
 * // Function composition
 * const processData = pipe(
 *   (x: number) => x * 2,
 *   (x: number) => x + 1,
 *   (x: number) => x.toString(),
 * );
 * processData(5); // "11"
 *
 * // Currying
 * const add = curry((a: number, b: number) => a + b);
 * const add5 = add(5);
 * add5(3); // 8
 *
 * // Debouncing
 * const debouncedSearch = debounce((query: string) => {
 *   console.log('Searching:', query);
 * }, 300);
 * ```
 *
 * @module
 */

// ============================================================================
// Type Definitions
// ============================================================================

/**
 * A function that takes a single argument and returns a value.
 * Used as the building block for function composition.
 */
type UnaryFunction<A, B> = (arg: A) => B;

// Note: ParamOf and ReturnOf are available but currently unused
// They can be useful for advanced type manipulations if needed in the future
// type ParamOf<F> = F extends (arg: infer A) => unknown ? A : never;
// type ReturnOf<F> = F extends (arg: unknown) => infer R ? R : never;

// ============================================================================
// Function Composition
// ============================================================================

/**
 * Composes functions left-to-right (pipe).
 * The output of each function is passed as input to the next.
 *
 * @param fns - Functions to compose, executed left to right
 * @returns A function that passes its input through all composed functions
 *
 * @example
 * ```ts
 * const double = (x: number) => x * 2;
 * const addOne = (x: number) => x + 1;
 * const toString = (x: number) => x.toString();
 *
 * const process = pipe(double, addOne, toString);
 * process(5); // "11" (5 * 2 = 10, 10 + 1 = 11, "11")
 *
 * // Single function works
 * const identity = pipe((x: number) => x);
 * identity(42); // 42
 *
 * // Type-safe chaining
 * const pipeline = pipe(
 *   (s: string) => s.length,
 *   (n: number) => n > 5,
 *   (b: boolean) => b ? "long" : "short"
 * );
 * pipeline("hello world"); // "long"
 * ```
 */
export function pipe<A, B>(fn1: UnaryFunction<A, B>): UnaryFunction<A, B>;
export function pipe<A, B, C>(
  fn1: UnaryFunction<A, B>,
  fn2: UnaryFunction<B, C>
): UnaryFunction<A, C>;
export function pipe<A, B, C, D>(
  fn1: UnaryFunction<A, B>,
  fn2: UnaryFunction<B, C>,
  fn3: UnaryFunction<C, D>
): UnaryFunction<A, D>;
export function pipe<A, B, C, D, E>(
  fn1: UnaryFunction<A, B>,
  fn2: UnaryFunction<B, C>,
  fn3: UnaryFunction<C, D>,
  fn4: UnaryFunction<D, E>
): UnaryFunction<A, E>;
export function pipe<A, B, C, D, E, F>(
  fn1: UnaryFunction<A, B>,
  fn2: UnaryFunction<B, C>,
  fn3: UnaryFunction<C, D>,
  fn4: UnaryFunction<D, E>,
  fn5: UnaryFunction<E, F>
): UnaryFunction<A, F>;
export function pipe<A, B, C, D, E, F, G>(
  fn1: UnaryFunction<A, B>,
  fn2: UnaryFunction<B, C>,
  fn3: UnaryFunction<C, D>,
  fn4: UnaryFunction<D, E>,
  fn5: UnaryFunction<E, F>,
  fn6: UnaryFunction<F, G>
): UnaryFunction<A, G>;
export function pipe(...fns: UnaryFunction<unknown, unknown>[]): UnaryFunction<unknown, unknown> {
  return (arg: unknown) => fns.reduce((acc, fn) => fn(acc), arg);
}

/**
 * Composes functions right-to-left (mathematical composition).
 * The rightmost function is applied first, then its output is passed left.
 *
 * @param fns - Functions to compose, executed right to left
 * @returns A function that passes its input through all composed functions
 *
 * @example
 * ```ts
 * const double = (x: number) => x * 2;
 * const addOne = (x: number) => x + 1;
 * const toString = (x: number) => x.toString();
 *
 * // Read right-to-left: toString(addOne(double(x)))
 * const process = compose(toString, addOne, double);
 * process(5); // "11" (5 * 2 = 10, 10 + 1 = 11, "11")
 *
 * // Mathematical notation: f . g = f(g(x))
 * const f = (x: number) => x + 1;
 * const g = (x: number) => x * 2;
 * const fg = compose(f, g);
 * fg(5); // 11 (f(g(5)) = f(10) = 11)
 * ```
 */
export function compose<A, B>(fn1: UnaryFunction<A, B>): UnaryFunction<A, B>;
export function compose<A, B, C>(
  fn2: UnaryFunction<B, C>,
  fn1: UnaryFunction<A, B>
): UnaryFunction<A, C>;
export function compose<A, B, C, D>(
  fn3: UnaryFunction<C, D>,
  fn2: UnaryFunction<B, C>,
  fn1: UnaryFunction<A, B>
): UnaryFunction<A, D>;
export function compose<A, B, C, D, E>(
  fn4: UnaryFunction<D, E>,
  fn3: UnaryFunction<C, D>,
  fn2: UnaryFunction<B, C>,
  fn1: UnaryFunction<A, B>
): UnaryFunction<A, E>;
export function compose<A, B, C, D, E, F>(
  fn5: UnaryFunction<E, F>,
  fn4: UnaryFunction<D, E>,
  fn3: UnaryFunction<C, D>,
  fn2: UnaryFunction<B, C>,
  fn1: UnaryFunction<A, B>
): UnaryFunction<A, F>;
export function compose<A, B, C, D, E, F, G>(
  fn6: UnaryFunction<F, G>,
  fn5: UnaryFunction<E, F>,
  fn4: UnaryFunction<D, E>,
  fn3: UnaryFunction<C, D>,
  fn2: UnaryFunction<B, C>,
  fn1: UnaryFunction<A, B>
): UnaryFunction<A, G>;
export function compose(
  ...fns: UnaryFunction<unknown, unknown>[]
): UnaryFunction<unknown, unknown> {
  return (arg: unknown) => fns.reduceRight((acc, fn) => fn(acc), arg);
}

// ============================================================================
// Currying
// ============================================================================

/**
 * Curries a function of 2 arguments.
 * Allows partial application of the first argument.
 *
 * @template A - Type of first argument
 * @template B - Type of second argument
 * @template R - Return type
 * @param fn - Function to curry
 * @returns Curried version of the function
 *
 * @example
 * ```ts
 * const add = curry((a: number, b: number) => a + b);
 *
 * // Full application
 * add(1, 2); // 3
 *
 * // Partial application
 * const add5 = add(5);
 * add5(3); // 8
 * add5(10); // 15
 *
 * // Useful for map/filter
 * const numbers = [1, 2, 3];
 * const multiply = curry((factor: number, x: number) => x * factor);
 * numbers.map(multiply(2)); // [2, 4, 6]
 * ```
 */
export function curry<A, B, R>(
  fn: (a: A, b: B) => R
): {
  (a: A): (b: B) => R;
  (a: A, b: B): R;
} {
  function curried(a: A): (b: B) => R;
  function curried(a: A, b: B): R;
  function curried(a: A, b?: B): R | ((b: B) => R) {
    if (arguments.length === 1) {
      return (b: B) => fn(a, b);
    }
    return fn(a, b as B);
  }
  return curried;
}

/**
 * Curries a function of 3 arguments.
 * Allows partial application of arguments one at a time.
 *
 * @template A - Type of first argument
 * @template B - Type of second argument
 * @template C - Type of third argument
 * @template R - Return type
 * @param fn - Function to curry
 * @returns Curried version of the function
 *
 * @example
 * ```ts
 * const replace = curry3((search: string, replacement: string, str: string) =>
 *   str.replace(search, replacement)
 * );
 *
 * // All at once
 * replace('a', 'b', 'abc'); // 'bbc'
 *
 * // Partial application
 * const replaceA = replace('a');
 * const replaceAWithB = replaceA('b');
 * replaceAWithB('aaa'); // 'baa'
 *
 * // Create reusable transformers
 * const sanitize = replace('<', '&lt;');
 * sanitize('script>'); // 'script>'
 * ```
 */
export function curry3<A, B, C, R>(
  fn: (a: A, b: B, c: C) => R
): {
  (a: A): {
    (b: B): (c: C) => R;
    (b: B, c: C): R;
  };
  (a: A, b: B): (c: C) => R;
  (a: A, b: B, c: C): R;
} {
  function curried(a: A): {
    (b: B): (c: C) => R;
    (b: B, c: C): R;
  };
  function curried(a: A, b: B): (c: C) => R;
  function curried(a: A, b: B, c: C): R;
  function curried(
    a: A,
    b?: B,
    c?: C
  ): R | ((c: C) => R) | { (b: B): (c: C) => R; (b: B, c: C): R } {
    if (arguments.length === 1) {
      // Return a function that takes 1 or 2 remaining arguments
      // Use rest parameters instead of arguments object for ES5 compatibility
      const partial = (...args: [B] | [B, C]): R | ((c: C) => R) => {
        if (args.length === 1) {
          return (cArg: C) => fn(a, args[0], cArg);
        }
        return fn(a, args[0], args[1]);
      };
      return partial as unknown as { (b: B): (c: C) => R; (b: B, c: C): R };
    }
    if (arguments.length === 2) {
      return (c: C) => fn(a, b as B, c);
    }
    return fn(a, b as B, c as C);
  }
  return curried;
}

// ============================================================================
// Timing Control
// ============================================================================

/**
 * Return type for debounced functions.
 * Includes methods to cancel pending calls and check status.
 */
export interface DebouncedFunction<Args extends unknown[], R> {
  /** Call the debounced function */
  (...args: Args): void;
  /** Cancel any pending invocation */
  cancel(): void;
  /** Immediately invoke if there's a pending call */
  flush(): R | undefined;
  /** Check if there's a pending invocation */
  pending(): boolean;
}

/**
 * Creates a debounced version of a function that delays execution
 * until after the specified wait time has elapsed since the last call.
 *
 * Useful for rate-limiting expensive operations like search input handling,
 * window resize handlers, or save operations.
 *
 * @template Args - Tuple type of function arguments
 * @template R - Return type of the function
 * @param fn - Function to debounce
 * @param wait - Wait time in milliseconds
 * @param options - Configuration options
 * @returns Debounced function with cancel, flush, and pending methods
 *
 * @example
 * ```ts
 * // Basic usage
 * const debouncedSearch = debounce((query: string) => {
 *   console.log('Searching:', query);
 * }, 300);
 *
 * // Only logs once, 300ms after last call
 * debouncedSearch('a');
 * debouncedSearch('ab');
 * debouncedSearch('abc');
 *
 * // With leading: true, fires immediately on first call
 * const leadingDebounce = debounce(fn, 300, { leading: true });
 *
 * // Cancel pending calls
 * debouncedSearch('test');
 * debouncedSearch.cancel(); // Won't log anything
 *
 * // Check if there's a pending call
 * debouncedSearch('query');
 * console.log(debouncedSearch.pending()); // true
 * ```
 */
export function debounce<Args extends unknown[], R>(
  fn: (...args: Args) => R,
  wait: number,
  options: { leading?: boolean; trailing?: boolean } = {}
): DebouncedFunction<Args, R> {
  const { leading = false, trailing = true } = options;

  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  let lastArgs: Args | undefined;
  let lastThis: unknown;
  let result: R | undefined;
  let leadingInvoked = false;

  const invokeFunc = (clearArgs: boolean = true): R => {
    const args = lastArgs;
    const thisArg = lastThis;

    if (clearArgs) {
      lastArgs = undefined;
      lastThis = undefined;
    }
    result = fn.apply(thisArg, args as Args);
    return result;
  };

  const timerExpired = (): void => {
    timeoutId = undefined;
    leadingInvoked = false;

    // Only invoke trailing if we have lastArgs and trailing is enabled
    if (trailing && lastArgs) {
      invokeFunc();
    }

    lastArgs = undefined;
    lastThis = undefined;
  };

  const cancel = (): void => {
    if (timeoutId !== undefined) {
      clearTimeout(timeoutId);
    }
    timeoutId = undefined;
    lastArgs = undefined;
    lastThis = undefined;
    leadingInvoked = false;
  };

  const flush = (): R | undefined => {
    if (timeoutId !== undefined && lastArgs) {
      clearTimeout(timeoutId);
      timeoutId = undefined;
      leadingInvoked = false;
      return invokeFunc();
    }
    return result;
  };

  const pending = (): boolean => {
    return timeoutId !== undefined;
  };

  const debounced = function (this: unknown, ...args: Args): void {
    lastArgs = args;
    // eslint-disable-next-line @typescript-eslint/no-this-alias -- Intentionally capturing 'this' to preserve context for fn.apply
    lastThis = this;

    // Clear any existing timer - this is key for debounce
    if (timeoutId !== undefined) {
      clearTimeout(timeoutId);
    }

    // Handle leading edge - don't clear args so trailing can still fire
    if (leading && !leadingInvoked) {
      leadingInvoked = true;
      invokeFunc(false);
    }

    // Always set a new timer (restart the wait period)
    timeoutId = setTimeout(timerExpired, wait);
  } as DebouncedFunction<Args, R>;

  debounced.cancel = cancel;
  debounced.flush = flush;
  debounced.pending = pending;

  return debounced;
}

/**
 * Return type for throttled functions.
 * Includes methods to cancel pending calls and check status.
 */
export interface ThrottledFunction<Args extends unknown[], R> {
  /** Call the throttled function */
  (...args: Args): R | undefined;
  /** Cancel any pending trailing invocation */
  cancel(): void;
  /** Immediately invoke if there's a pending call */
  flush(): R | undefined;
  /** Check if there's a pending invocation */
  pending(): boolean;
}

/**
 * Creates a throttled version of a function that only invokes at most
 * once per every `wait` milliseconds.
 *
 * Useful for rate-limiting continuous events like scroll or mousemove
 * where you want regular updates but not on every single event.
 *
 * @template Args - Tuple type of function arguments
 * @template R - Return type of the function
 * @param fn - Function to throttle
 * @param wait - Minimum time between invocations in milliseconds
 * @param options - Configuration options
 * @returns Throttled function with cancel, flush, and pending methods
 *
 * @example
 * ```ts
 * // Basic usage - fires at most once per 100ms
 * const throttledScroll = throttle(() => {
 *   console.log('Scroll position:', window.scrollY);
 * }, 100);
 *
 * window.addEventListener('scroll', throttledScroll);
 *
 * // Options
 * // leading: true (default) - invoke on first call
 * // trailing: true (default) - invoke after wait if called during wait
 *
 * // No trailing call
 * const noTrailing = throttle(fn, 100, { trailing: false });
 *
 * // No leading call (delay first execution)
 * const noLeading = throttle(fn, 100, { leading: false });
 *
 * // Cancel throttle
 * throttledScroll.cancel();
 * ```
 */
export function throttle<Args extends unknown[], R>(
  fn: (...args: Args) => R,
  wait: number,
  options: { leading?: boolean; trailing?: boolean } = {}
): ThrottledFunction<Args, R> {
  const { leading = true, trailing = true } = options;

  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  let lastArgs: Args | undefined;
  let lastThis: unknown;
  let result: R | undefined;
  let lastInvokeTime: number | undefined;

  const invokeFunc = (): R => {
    const args = lastArgs;
    const thisArg = lastThis;

    lastArgs = undefined;
    lastThis = undefined;
    lastInvokeTime = Date.now();
    result = fn.apply(thisArg, args as Args);
    return result;
  };

  const remainingWait = (): number => {
    const now = Date.now();
    const timeSinceLastInvoke = lastInvokeTime ? now - lastInvokeTime : wait;
    return Math.max(0, wait - timeSinceLastInvoke);
  };

  const trailingEdge = (): void => {
    timeoutId = undefined;

    if (trailing && lastArgs) {
      invokeFunc();
    } else {
      lastArgs = undefined;
      lastThis = undefined;
    }
  };

  const cancel = (): void => {
    if (timeoutId !== undefined) {
      clearTimeout(timeoutId);
    }
    lastArgs = undefined;
    lastThis = undefined;
    lastInvokeTime = undefined;
    timeoutId = undefined;
  };

  const flush = (): R | undefined => {
    if (timeoutId !== undefined && lastArgs) {
      return invokeFunc();
    }
    return result;
  };

  const pending = (): boolean => {
    return timeoutId !== undefined;
  };

  const throttled = function (this: unknown, ...args: Args): R | undefined {
    const now = Date.now();
    const timeSinceLastInvoke = lastInvokeTime ? now - lastInvokeTime : wait;

    lastArgs = args;
    // eslint-disable-next-line @typescript-eslint/no-this-alias -- Intentionally capturing 'this' to preserve context for fn.apply
    lastThis = this;

    // Should we invoke now?
    if (timeSinceLastInvoke >= wait) {
      // Cancel any existing timeout
      if (timeoutId !== undefined) {
        clearTimeout(timeoutId);
        timeoutId = undefined;
      }

      if (leading) {
        return invokeFunc();
      } else {
        // If no leading, start the trailing timer
        lastInvokeTime = now;
        if (trailing) {
          timeoutId = setTimeout(trailingEdge, wait);
        }
        return result;
      }
    }

    // We're within the wait period
    if (timeoutId === undefined && trailing) {
      // Schedule trailing call
      timeoutId = setTimeout(trailingEdge, remainingWait());
    }

    return result;
  } as ThrottledFunction<Args, R>;

  throttled.cancel = cancel;
  throttled.flush = flush;
  throttled.pending = pending;

  return throttled;
}

// ============================================================================
// Additional Utilities
// ============================================================================

/**
 * Creates a function that is called at most once.
 * Subsequent calls return the result of the first invocation.
 *
 * @template Args - Tuple type of function arguments
 * @template R - Return type of the function
 * @param fn - Function to wrap
 * @returns A function that invokes fn at most once
 *
 * @example
 * ```ts
 * let counter = 0;
 * const initialize = once(() => {
 *   counter++;
 *   return counter;
 * });
 *
 * initialize(); // 1
 * initialize(); // 1 (returns cached result)
 * initialize(); // 1
 * console.log(counter); // 1 (function only ran once)
 * ```
 */
export function once<Args extends unknown[], R>(fn: (...args: Args) => R): (...args: Args) => R {
  let called = false;
  let result: R;

  return function (this: unknown, ...args: Args): R {
    if (!called) {
      called = true;
      result = fn.apply(this, args);
    }
    return result;
  };
}

/**
 * Creates a memoized version of a function.
 * Caches results based on the first argument (or all arguments with a key function).
 *
 * @template Args - Tuple type of function arguments
 * @template R - Return type of the function
 * @param fn - Function to memoize
 * @param getKey - Optional function to generate cache key from arguments
 * @returns Memoized version of the function
 *
 * @example
 * ```ts
 * let calls = 0;
 * const expensive = memoize((n: number) => {
 *   calls++;
 *   return n * 2;
 * });
 *
 * expensive(5); // 10, calls = 1
 * expensive(5); // 10, calls = 1 (cached)
 * expensive(3); // 6, calls = 2
 *
 * // With custom key function
 * const fetchUser = memoize(
 *   (id: number, options: { includeDetails: boolean }) => {
 *     return `user-${id}-${options.includeDetails}`;
 *   },
 *   (id, options) => `${id}-${options.includeDetails}`
 * );
 * ```
 */
export function memoize<Args extends unknown[], R>(
  fn: (...args: Args) => R,
  getKey: (...args: Args) => string = (...args) => String(args[0])
): (...args: Args) => R {
  const cache = new Map<string, R>();

  return function (this: unknown, ...args: Args): R {
    const key = getKey(...args);

    if (cache.has(key)) {
      return cache.get(key) as R;
    }

    const result = fn.apply(this, args);
    cache.set(key, result);
    return result;
  };
}

/**
 * Negates a predicate function.
 *
 * @template T - Type of the predicate argument
 * @param predicate - Predicate function to negate
 * @returns A function that returns the logical NOT of the predicate
 *
 * @example
 * ```ts
 * const isEven = (n: number) => n % 2 === 0;
 * const isOdd = negate(isEven);
 *
 * isOdd(3); // true
 * isOdd(4); // false
 *
 * // Use with filter
 * [1, 2, 3, 4].filter(negate(isEven)); // [1, 3]
 * ```
 */
export function negate<T>(predicate: (value: T) => boolean): (value: T) => boolean {
  return (value: T) => !predicate(value);
}

/**
 * Returns a function that always returns the same value.
 *
 * @template T - Type of the constant value
 * @param value - Value to return
 * @returns A function that always returns the value
 *
 * @example
 * ```ts
 * const always42 = constant(42);
 * always42(); // 42
 * always42('ignored'); // 42
 *
 * // Useful as default handlers
 * const handleError = catchError(constant(null));
 * ```
 */
export function constant<T>(value: T): () => T {
  return () => value;
}

/**
 * Identity function - returns its argument unchanged.
 *
 * @template T - Type of the value
 * @param value - Value to return
 * @returns The same value
 *
 * @example
 * ```ts
 * identity(42); // 42
 * identity('hello'); // 'hello'
 *
 * // Useful as default transformer
 * const transform = shouldTransform ? someTransform : identity;
 *
 * // Useful with flatMap to "flatten" Result<Result<T, E>, E>
 * const nested = ok(ok(42));
 * flatMap(nested, identity); // ok(42)
 * ```
 */
export function identity<T>(value: T): T {
  return value;
}

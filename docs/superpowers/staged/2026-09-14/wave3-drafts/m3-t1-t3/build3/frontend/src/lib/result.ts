/**
 * Result Type for Type-Safe Error Handling
 *
 * A discriminated union type that represents either success (Ok) or failure (Err).
 * This pattern, inspired by Rust's Result type, enables explicit error handling
 * without exceptions, making error cases visible in the type system.
 *
 * @example
 * ```ts
 * // Function that returns a Result
 * function divide(a: number, b: number): Result<number, string> {
 *   if (b === 0) {
 *     return err('Division by zero');
 *   }
 *   return ok(a / b);
 * }
 *
 * // Using the Result
 * const result = divide(10, 2);
 *
 * if (isOk(result)) {
 *   console.log(result.value); // 5
 * } else {
 *   console.error(result.error); // Won't reach here
 * }
 *
 * // Or use pattern matching utilities
 * const doubled = map(result, (n) => n * 2);
 * const withDefault = unwrapOr(result, 0);
 * ```
 *
 * @module
 */

// ============================================================================
// Core Types
// ============================================================================

/**
 * Represents a successful result containing a value.
 *
 * @template T - The type of the success value
 */
export interface Ok<T> {
  readonly _tag: 'Ok';
  readonly value: T;
}

/**
 * Represents a failed result containing an error.
 *
 * @template E - The type of the error
 */
export interface Err<E> {
  readonly _tag: 'Err';
  readonly error: E;
}

/**
 * A Result is either Ok (success) or Err (failure).
 * This is a discriminated union that enables exhaustive type checking.
 *
 * @template T - The type of the success value
 * @template E - The type of the error (defaults to Error)
 *
 * @example
 * ```ts
 * // Type annotation for a function returning Result
 * function parseJSON<T>(json: string): Result<T, SyntaxError> {
 *   try {
 *     return ok(JSON.parse(json) as T);
 *   } catch (e) {
 *     return err(e as SyntaxError);
 *   }
 * }
 * ```
 */
export type Result<T, E = Error> = Ok<T> | Err<E>;

// ============================================================================
// Factory Functions
// ============================================================================

/**
 * Creates a successful Result containing the given value.
 *
 * @template T - The type of the success value
 * @param value - The success value to wrap
 * @returns An Ok Result containing the value
 *
 * @example
 * ```ts
 * const result = ok(42);
 * // result: Ok<number> = { _tag: 'Ok', value: 42 }
 *
 * // With explicit type
 * const user = ok<User>({ id: 1, name: 'Alice' });
 * ```
 */
export function ok<T>(value: T): Ok<T> {
  return { _tag: 'Ok', value };
}

/**
 * Creates a failed Result containing the given error.
 *
 * @template E - The type of the error
 * @param error - The error value to wrap
 * @returns An Err Result containing the error
 *
 * @example
 * ```ts
 * const result = err(new Error('Something went wrong'));
 * // result: Err<Error> = { _tag: 'Err', error: Error(...) }
 *
 * // With string error
 * const validation = err<string>('Invalid input');
 * ```
 */
export function err<E>(error: E): Err<E> {
  return { _tag: 'Err', error };
}

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard that checks if a Result is Ok (successful).
 *
 * @template T - The type of the success value
 * @template E - The type of the error
 * @param result - The Result to check
 * @returns true if the Result is Ok, false if Err
 *
 * @example
 * ```ts
 * const result: Result<number, string> = ok(42);
 *
 * if (isOk(result)) {
 *   // TypeScript knows result.value is number here
 *   console.log(result.value * 2);
 * }
 * ```
 */
export function isOk<T, E>(result: Result<T, E>): result is Ok<T> {
  return result._tag === 'Ok';
}

/**
 * Type guard that checks if a Result is Err (failed).
 *
 * @template T - The type of the success value
 * @template E - The type of the error
 * @param result - The Result to check
 * @returns true if the Result is Err, false if Ok
 *
 * @example
 * ```ts
 * const result: Result<number, string> = err('failed');
 *
 * if (isErr(result)) {
 *   // TypeScript knows result.error is string here
 *   console.error(result.error.toUpperCase());
 * }
 * ```
 */
export function isErr<T, E>(result: Result<T, E>): result is Err<E> {
  return result._tag === 'Err';
}

// ============================================================================
// Transformation Functions
// ============================================================================

/**
 * Transforms the success value of a Result using the provided function.
 * If the Result is Err, returns the Err unchanged.
 *
 * @template T - The type of the original success value
 * @template U - The type of the transformed success value
 * @template E - The type of the error
 * @param result - The Result to transform
 * @param fn - Function to apply to the success value
 * @returns A new Result with the transformed value or the original error
 *
 * @example
 * ```ts
 * const result = ok(10);
 * const doubled = map(result, (n) => n * 2);
 * // doubled: Ok<number> = { _tag: 'Ok', value: 20 }
 *
 * const failed = err<string>('oops');
 * const stillFailed = map(failed, (n: number) => n * 2);
 * // stillFailed: Err<string> = { _tag: 'Err', error: 'oops' }
 * ```
 */
export function map<T, U, E>(result: Result<T, E>, fn: (value: T) => U): Result<U, E> {
  if (isOk(result)) {
    return ok(fn(result.value));
  }
  return result;
}

/**
 * Transforms the error value of a Result using the provided function.
 * If the Result is Ok, returns the Ok unchanged.
 *
 * @template T - The type of the success value
 * @template E - The type of the original error
 * @template F - The type of the transformed error
 * @param result - The Result to transform
 * @param fn - Function to apply to the error value
 * @returns A new Result with the original value or the transformed error
 *
 * @example
 * ```ts
 * const result = err('network error');
 * const mapped = mapErr(result, (e) => new Error(e));
 * // mapped: Err<Error> = { _tag: 'Err', error: Error('network error') }
 *
 * const success = ok(42);
 * const stillSuccess = mapErr(success, (e: string) => new Error(e));
 * // stillSuccess: Ok<number> = { _tag: 'Ok', value: 42 }
 * ```
 */
export function mapErr<T, E, F>(result: Result<T, E>, fn: (error: E) => F): Result<T, F> {
  if (isErr(result)) {
    return err(fn(result.error));
  }
  return result;
}

/**
 * Chains Result-returning functions together (flatMap/bind).
 * If the Result is Ok, applies fn and returns the new Result.
 * If the Result is Err, returns the Err unchanged.
 *
 * @template T - The type of the original success value
 * @template U - The type of the new success value
 * @template E - The type of the error
 * @param result - The Result to chain from
 * @param fn - Function that returns a new Result
 * @returns The Result from fn, or the original error
 *
 * @example
 * ```ts
 * function validatePositive(n: number): Result<number, string> {
 *   return n > 0 ? ok(n) : err('Must be positive');
 * }
 *
 * function validateEven(n: number): Result<number, string> {
 *   return n % 2 === 0 ? ok(n) : err('Must be even');
 * }
 *
 * const result = flatMap(
 *   flatMap(ok(4), validatePositive),
 *   validateEven
 * );
 * // result: Ok<number> = { _tag: 'Ok', value: 4 }
 *
 * const failed = flatMap(
 *   flatMap(ok(-2), validatePositive),
 *   validateEven
 * );
 * // failed: Err<string> = { _tag: 'Err', error: 'Must be positive' }
 * ```
 */
export function flatMap<T, U, E>(
  result: Result<T, E>,
  fn: (value: T) => Result<U, E>
): Result<U, E> {
  if (isOk(result)) {
    return fn(result.value);
  }
  return result;
}

/**
 * Alias for flatMap, commonly used name in functional programming.
 *
 * @see flatMap
 */
export const andThen = flatMap;

// ============================================================================
// Extraction Functions
// ============================================================================

/**
 * Extracts the value from an Ok Result, or throws if Err.
 * Use this only when you are certain the Result is Ok,
 * or when you want to convert Err to an exception.
 *
 * @template T - The type of the success value
 * @template E - The type of the error
 * @param result - The Result to unwrap
 * @returns The success value
 * @throws The error value if the Result is Err
 *
 * @example
 * ```ts
 * const result = ok(42);
 * const value = unwrap(result); // 42
 *
 * const failed = err(new Error('oops'));
 * const value2 = unwrap(failed); // throws Error('oops')
 * ```
 */
export function unwrap<T, E>(result: Result<T, E>): T {
  if (isOk(result)) {
    return result.value;
  }
  // Intentionally throw the error value - this is the expected behavior of unwrap
  // eslint-disable-next-line @typescript-eslint/only-throw-error
  throw result.error;
}

/**
 * Extracts the value from an Ok Result, or returns the default value if Err.
 *
 * @template T - The type of the success value
 * @template E - The type of the error
 * @param result - The Result to unwrap
 * @param defaultValue - The value to return if the Result is Err
 * @returns The success value or the default value
 *
 * @example
 * ```ts
 * const result = ok(42);
 * const value = unwrapOr(result, 0); // 42
 *
 * const failed = err('oops');
 * const value2 = unwrapOr(failed, 0); // 0
 * ```
 */
export function unwrapOr<T, E>(result: Result<T, E>, defaultValue: T): T {
  if (isOk(result)) {
    return result.value;
  }
  return defaultValue;
}

/**
 * Extracts the value from an Ok Result, or computes a default from the error.
 *
 * @template T - The type of the success value
 * @template E - The type of the error
 * @param result - The Result to unwrap
 * @param fn - Function to compute default value from the error
 * @returns The success value or the computed default
 *
 * @example
 * ```ts
 * const result = err('not found');
 * const value = unwrapOrElse(result, (e) => {
 *   console.warn(e);
 *   return 'default';
 * });
 * // Logs: 'not found'
 * // value: 'default'
 * ```
 */
export function unwrapOrElse<T, E>(result: Result<T, E>, fn: (error: E) => T): T {
  if (isOk(result)) {
    return result.value;
  }
  return fn(result.error);
}

/**
 * Extracts the error from an Err Result, or throws if Ok.
 * Useful for testing error conditions.
 *
 * @template T - The type of the success value
 * @template E - The type of the error
 * @param result - The Result to unwrap
 * @returns The error value
 * @throws Error if the Result is Ok
 *
 * @example
 * ```ts
 * const failed = err('validation failed');
 * const error = unwrapErr(failed); // 'validation failed'
 *
 * const success = ok(42);
 * const error2 = unwrapErr(success); // throws Error
 * ```
 */
export function unwrapErr<T, E>(result: Result<T, E>): E {
  if (isErr(result)) {
    return result.error;
  }
  throw new Error('Called unwrapErr on Ok value');
}

// ============================================================================
// Pattern Matching
// ============================================================================

/**
 * Pattern matches on a Result, handling both Ok and Err cases.
 * This is the most flexible way to handle a Result.
 *
 * @template T - The type of the success value
 * @template E - The type of the error
 * @template U - The return type
 * @param result - The Result to match on
 * @param handlers - Object containing onOk and onErr handlers
 * @returns The result of the matching handler
 *
 * @example
 * ```ts
 * const result: Result<number, string> = ok(42);
 *
 * const message = match(result, {
 *   onOk: (value) => `Success: ${value}`,
 *   onErr: (error) => `Error: ${error}`,
 * });
 * // message: 'Success: 42'
 * ```
 */
export function match<T, E, U>(
  result: Result<T, E>,
  handlers: {
    onOk: (value: T) => U;
    onErr: (error: E) => U;
  }
): U {
  if (isOk(result)) {
    return handlers.onOk(result.value);
  }
  return handlers.onErr(result.error);
}

// ============================================================================
// Async Utilities
// ============================================================================

/**
 * Wraps a Promise in a Result, catching any errors.
 * Converts Promise-based code to Result-based code.
 *
 * @template T - The type of the resolved value
 * @template E - The type of the error (defaults to Error)
 * @param promise - The Promise to wrap
 * @returns A Promise that resolves to a Result
 *
 * @example
 * ```ts
 * const result = await fromPromise(fetch('/api/data'));
 *
 * if (isOk(result)) {
 *   const response = result.value;
 *   // Handle response
 * } else {
 *   const error = result.error;
 *   // Handle error
 * }
 * ```
 */
export async function fromPromise<T, E = Error>(promise: Promise<T>): Promise<Result<T, E>> {
  try {
    const value = await promise;
    return ok(value);
  } catch (error) {
    return err(error as E);
  }
}

/**
 * Converts a Result to a Promise.
 * Ok values resolve, Err values reject.
 *
 * @template T - The type of the success value
 * @template E - The type of the error
 * @param result - The Result to convert
 * @returns A Promise that resolves with the value or rejects with the error
 *
 * @example
 * ```ts
 * const result = ok(42);
 * const value = await toPromise(result); // 42
 *
 * const failed = err(new Error('oops'));
 * await toPromise(failed); // throws Error('oops')
 * ```
 */
export function toPromise<T, E>(result: Result<T, E>): Promise<T> {
  if (isOk(result)) {
    return Promise.resolve(result.value);
  }
  // Intentionally reject with the error value - this matches unwrap behavior
  // eslint-disable-next-line @typescript-eslint/prefer-promise-reject-errors
  return Promise.reject(result.error);
}

// ============================================================================
// Combining Results
// ============================================================================

/**
 * Combines an array of Results into a single Result containing an array.
 * If all Results are Ok, returns Ok with array of values.
 * If any Result is Err, returns the first Err encountered.
 *
 * @template T - The type of the success values
 * @template E - The type of the error
 * @param results - Array of Results to combine
 * @returns A single Result containing all values or the first error
 *
 * @example
 * ```ts
 * const results = [ok(1), ok(2), ok(3)];
 * const combined = all(results);
 * // combined: Ok<number[]> = { _tag: 'Ok', value: [1, 2, 3] }
 *
 * const withError = [ok(1), err('oops'), ok(3)];
 * const failed = all(withError);
 * // failed: Err<string> = { _tag: 'Err', error: 'oops' }
 * ```
 */
export function all<T, E>(results: Result<T, E>[]): Result<T[], E> {
  const values: T[] = [];

  for (const result of results) {
    if (isErr(result)) {
      return result;
    }
    values.push(result.value);
  }

  return ok(values);
}

/**
 * Type helper for extracting success type from a Result tuple.
 */
type ExtractOk<R> = R extends Result<infer T, unknown> ? T : never;

/**
 * Type helper for extracting error type from a Result tuple.
 */
type ExtractErr<R> = R extends Result<unknown, infer E> ? E : never;

/**
 * Combines a tuple of Results into a Result of a tuple.
 * Preserves the types of each position in the tuple.
 *
 * @template T - Tuple of Results
 * @param results - Tuple of Results to combine
 * @returns A single Result containing a tuple of values or the first error
 *
 * @example
 * ```ts
 * const result = allTuple([
 *   ok(42),
 *   ok('hello'),
 *   ok(true),
 * ] as const);
 * // result: Result<[number, string, boolean], never>
 *
 * if (isOk(result)) {
 *   const [num, str, bool] = result.value;
 *   // Types are preserved: number, string, boolean
 * }
 * ```
 */
export function allTuple<T extends readonly Result<unknown, unknown>[]>(
  results: T
): Result<{ [K in keyof T]: ExtractOk<T[K]> }, ExtractErr<T[number]>> {
  const values: unknown[] = [];

  for (const result of results) {
    if (isErr(result)) {
      return result as Err<ExtractErr<T[number]>>;
    }
    // TypeScript narrows to Ok after isErr check, but we need to access .value
    values.push(result.value);
  }

  return ok(values) as Result<{ [K in keyof T]: ExtractOk<T[K]> }, ExtractErr<T[number]>>;
}

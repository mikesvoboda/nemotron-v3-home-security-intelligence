/**
 * Result Type for Explicit Success/Failure Handling
 *
 * This module provides a Result type pattern for TypeScript, offering a type-safe
 * alternative to try/catch for explicit error handling and propagation.
 *
 * Benefits:
 * - Errors are values, not exceptions - they must be handled explicitly
 * - Type system enforces error handling at compile time
 * - Enables functional composition with map, andThen, orElse
 * - Clear distinction between success and failure paths
 * - No hidden control flow from thrown exceptions
 *
 * @example
 * ```typescript
 * // Basic usage
 * function divide(a: number, b: number): Result<number, Error> {
 *   if (b === 0) {
 *     return Err(new Error('Division by zero'));
 *   }
 *   return Ok(a / b);
 * }
 *
 * const result = divide(10, 2);
 * if (isOk(result)) {
 *   console.log('Result:', result.value);
 * } else {
 *   console.error('Error:', result.error.message);
 * }
 *
 * // Pattern matching
 * const message = match(result, {
 *   ok: (value) => `Result: ${value}`,
 *   err: (error) => `Error: ${error.message}`,
 * });
 *
 * // Chaining operations
 * const processed = andThen(parseNumber(input), (n) =>
 *   n >= 0 ? Ok(Math.sqrt(n)) : Err(new Error('Negative number'))
 * );
 * ```
 */

// ============================================================================
// Core Result Type
// ============================================================================

/**
 * Success variant of the Result type.
 */
export interface OkResult<T> {
  readonly ok: true;
  readonly value: T;
}

/**
 * Error variant of the Result type.
 */
export interface ErrResult<E> {
  readonly ok: false;
  readonly error: E;
}

/**
 * A discriminated union representing either success (Ok) or failure (Err).
 *
 * @typeParam T - The type of the success value
 * @typeParam E - The type of the error (defaults to Error)
 *
 * @example
 * ```typescript
 * type ParseResult = Result<number, Error>;
 * type FetchResult = Result<User, NetworkError>;
 * type ValidationResult = Result<Form, string[]>;
 * ```
 */
export type Result<T, E = Error> = OkResult<T> | ErrResult<E>;

// ============================================================================
// Factory Functions
// ============================================================================

/**
 * Creates a success Result containing the given value.
 *
 * @param value - The success value to wrap
 * @returns A Result in the Ok state
 *
 * @example
 * ```typescript
 * const result = Ok(42);
 * // result: Result<number, never>
 *
 * const user = Ok({ id: 1, name: 'John' });
 * // user: Result<{ id: number; name: string }, never>
 * ```
 */
export function Ok<T>(value: T): OkResult<T> {
  return { ok: true, value };
}

/**
 * Creates a failure Result containing the given error.
 *
 * @param error - The error to wrap
 * @returns A Result in the Err state
 *
 * @example
 * ```typescript
 * const error = Err(new Error('Not found'));
 * // error: Result<never, Error>
 *
 * const validationError = Err({ field: 'email', message: 'Invalid email' });
 * // validationError: Result<never, { field: string; message: string }>
 * ```
 */
export function Err<E>(error: E): ErrResult<E> {
  return { ok: false, error };
}

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard that checks if a Result is in the Ok state.
 *
 * @param result - The Result to check
 * @returns true if the Result is Ok, false otherwise
 *
 * @example
 * ```typescript
 * const result: Result<number, Error> = Ok(42);
 *
 * if (isOk(result)) {
 *   console.log(result.value); // TypeScript knows this is number
 * }
 * ```
 */
export function isOk<T, E>(result: Result<T, E>): result is OkResult<T> {
  return result.ok === true;
}

/**
 * Type guard that checks if a Result is in the Err state.
 *
 * @param result - The Result to check
 * @returns true if the Result is Err, false otherwise
 *
 * @example
 * ```typescript
 * const result: Result<number, ValidationError> = Err(new ValidationError('Invalid'));
 *
 * if (isErr(result)) {
 *   console.error(result.error); // TypeScript knows this is ValidationError
 * }
 * ```
 */
export function isErr<T, E>(result: Result<T, E>): result is ErrResult<E> {
  return result.ok === false;
}

// ============================================================================
// Unwrap Functions
// ============================================================================

/**
 * Extracts the value from an Ok Result, or throws if Err.
 *
 * Use this when you are certain the Result is Ok, or when you want
 * to convert the error to an exception. Prefer pattern matching or
 * unwrapOr for safer error handling.
 *
 * @param result - The Result to unwrap
 * @returns The contained value
 * @throws The error if the Result is Err
 *
 * @example
 * ```typescript
 * const result = Ok(42);
 * const value = unwrap(result); // 42
 *
 * const error = Err(new Error('Failed'));
 * unwrap(error); // throws Error('Failed')
 * ```
 */
export function unwrap<T, E>(result: Result<T, E>): T {
  if (result.ok === true) {
    return result.value;
  }
  const error = result.error;
  if (error instanceof Error) {
    throw error;
  }
  throw new Error(String(error));
}

/**
 * Extracts the value from an Ok Result, or returns a default if Err.
 *
 * This is a safe way to extract a value with a fallback.
 *
 * @param result - The Result to unwrap
 * @param defaultValue - The value to return if Result is Err
 * @returns The contained value or the default
 *
 * @example
 * ```typescript
 * const ok = Ok(42);
 * unwrapOr(ok, 0); // 42
 *
 * const err: Result<number, Error> = Err(new Error('Failed'));
 * unwrapOr(err, 0); // 0
 * ```
 */
export function unwrapOr<T, E>(result: Result<T, E>, defaultValue: T): T {
  if (result.ok === true) {
    return result.value;
  }
  return defaultValue;
}

/**
 * Extracts the error from an Err Result, or throws if Ok.
 *
 * Primarily useful for testing error cases.
 *
 * @param result - The Result to unwrap
 * @returns The contained error
 * @throws If the Result is Ok
 *
 * @example
 * ```typescript
 * const error = Err(new ValidationError('Invalid'));
 * const err = unwrapErr(error); // ValidationError('Invalid')
 *
 * const ok = Ok(42);
 * unwrapErr(ok); // throws Error('Called unwrapErr on an Ok result')
 * ```
 */
export function unwrapErr<T, E>(result: Result<T, E>): E {
  if (result.ok === true) {
    throw new Error('Called unwrapErr on an Ok result');
  }
  return result.error;
}

// ============================================================================
// Transformation Functions
// ============================================================================

/**
 * Transforms the value in an Ok Result using the provided function.
 * If the Result is Err, returns the Err unchanged.
 *
 * @param result - The Result to transform
 * @param fn - The function to apply to the Ok value
 * @returns A new Result with the transformed value
 *
 * @example
 * ```typescript
 * const result = Ok(5);
 * const doubled = map(result, x => x * 2); // Ok(10)
 *
 * const error: Result<number, Error> = Err(new Error('Failed'));
 * const mapped = map(error, x => x * 2); // Err(Error('Failed'))
 * ```
 */
export function map<T, U, E>(result: Result<T, E>, fn: (value: T) => U): Result<U, E> {
  if (result.ok === true) {
    return Ok(fn(result.value));
  }
  return Err(result.error);
}

/**
 * Transforms the error in an Err Result using the provided function.
 * If the Result is Ok, returns the Ok unchanged.
 *
 * @param result - The Result to transform
 * @param fn - The function to apply to the Err value
 * @returns A new Result with the transformed error
 *
 * @example
 * ```typescript
 * const error: Result<number, string> = Err('Not found');
 * const wrapped = mapErr(error, e => new Error(e)); // Err(Error('Not found'))
 *
 * const ok = Ok(42);
 * const mapped = mapErr(ok, e => new Error(e)); // Ok(42)
 * ```
 */
export function mapErr<T, E, F>(result: Result<T, E>, fn: (error: E) => F): Result<T, F> {
  if (result.ok === true) {
    return Ok(result.value);
  }
  return Err(fn(result.error));
}

// ============================================================================
// Chaining Functions
// ============================================================================

/**
 * Chains a function that returns a Result onto an existing Result.
 * If the input is Ok, applies the function. If Err, returns the Err unchanged.
 *
 * Also known as "flatMap" or "bind" in other languages.
 *
 * @param result - The Result to chain from
 * @param fn - The function to apply if Ok
 * @returns The Result from the function or the original Err
 *
 * @example
 * ```typescript
 * const parseNumber = (s: string): Result<number, Error> => {
 *   const n = parseInt(s, 10);
 *   return isNaN(n) ? Err(new Error('Not a number')) : Ok(n);
 * };
 *
 * const validatePositive = (n: number): Result<number, Error> =>
 *   n > 0 ? Ok(n) : Err(new Error('Not positive'));
 *
 * // Chain parsing and validation
 * const result = andThen(parseNumber('42'), validatePositive);
 * // Ok(42)
 *
 * const invalid = andThen(parseNumber('-5'), validatePositive);
 * // Err(Error('Not positive'))
 * ```
 */
export function andThen<T, U, E>(
  result: Result<T, E>,
  fn: (value: T) => Result<U, E>
): Result<U, E> {
  if (result.ok === true) {
    return fn(result.value);
  }
  return Err(result.error);
}

/**
 * Recovers from an Err by applying a function that returns a new Result.
 * If the input is Ok, returns it unchanged.
 *
 * @param result - The Result to potentially recover from
 * @param fn - The recovery function to apply if Err
 * @returns The original Ok or the recovered Result
 *
 * @example
 * ```typescript
 * const fetchRemote = (): Result<Data, NetworkError> => Err(new NetworkError('Offline'));
 * const loadCache = (e: NetworkError): Result<Data, CacheError> => Ok(cachedData);
 *
 * // Try remote, fall back to cache
 * const data = orElse(fetchRemote(), loadCache);
 * ```
 */
export function orElse<T, E, F>(
  result: Result<T, E>,
  fn: (error: E) => Result<T, F>
): Result<T, F> {
  if (result.ok === true) {
    return Ok(result.value);
  }
  return fn(result.error);
}

// ============================================================================
// Pattern Matching
// ============================================================================

/**
 * Pattern matches on a Result, calling the appropriate handler for Ok or Err.
 *
 * This ensures exhaustive handling of both cases and provides a clean
 * functional style for processing Results.
 *
 * @param result - The Result to match on
 * @param handlers - Object with ok and err handler functions
 * @returns The value returned by the matched handler
 *
 * @example
 * ```typescript
 * const result: Result<User, Error> = fetchUser(id);
 *
 * const message = match(result, {
 *   ok: (user) => `Hello, ${user.name}!`,
 *   err: (error) => `Error: ${error.message}`,
 * });
 *
 * // With JSX-like returns
 * return match(state, {
 *   ok: (data) => <DataView data={data} />,
 *   err: (error) => <ErrorMessage error={error} />,
 * });
 * ```
 */
export function match<T, E, R>(
  result: Result<T, E>,
  handlers: {
    ok: (value: T) => R;
    err: (error: E) => R;
  }
): R {
  if (result.ok === true) {
    return handlers.ok(result.value);
  }
  return handlers.err(result.error);
}

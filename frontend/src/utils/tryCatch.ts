/**
 * tryCatch Utility for Async Error Handling
 *
 * This module provides utilities for safely executing functions that may throw,
 * converting exceptions into Result types for explicit error handling.
 *
 * Benefits:
 * - Transforms thrown exceptions into typed Result values
 * - Prevents uncaught promise rejections
 * - Enables functional composition with Result utilities
 * - Provides both async and sync variants
 *
 * @example
 * ```typescript
 * // Async usage with fetch
 * const result = await tryCatch(async () => {
 *   const response = await fetch('/api/users');
 *   if (!response.ok) throw new Error('Failed to fetch');
 *   return response.json();
 * });
 *
 * if (isOk(result)) {
 *   console.log('Users:', result.value);
 * } else {
 *   console.error('Error:', result.error.message);
 * }
 *
 * // Sync usage with JSON parsing
 * const parsed = tryCatchSync(() => JSON.parse(jsonString));
 *
 * // Chaining with Result utilities
 * const processed = map(
 *   await tryCatch(() => fetchUser(id)),
 *   user => user.name
 * );
 * ```
 */

import { type Result, Ok, Err } from '../types/result';

// ============================================================================
// Error Conversion Utility
// ============================================================================

/**
 * Converts an unknown thrown value into an Error object.
 *
 * JavaScript allows throwing any value, but for consistent error handling,
 * this function normalizes all thrown values to Error instances.
 *
 * @param err - The caught value (could be Error, string, or anything)
 * @returns An Error instance
 *
 * @internal
 */
function toError(err: unknown): Error {
  if (err instanceof Error) {
    return err;
  }
  return new Error(String(err));
}

// ============================================================================
// Async tryCatch
// ============================================================================

/**
 * Safely executes an async function, catching any thrown exceptions
 * and converting them to a Result type.
 *
 * This is the primary utility for wrapping async operations that may fail,
 * converting exception-based error handling to explicit Result-based handling.
 *
 * @typeParam T - The return type of the async function
 * @param fn - The async function to execute
 * @returns A Promise that resolves to Ok(value) on success or Err(error) on failure
 *
 * @example
 * ```typescript
 * // Basic usage
 * const result = await tryCatch(async () => {
 *   const response = await fetch('/api/data');
 *   return response.json();
 * });
 *
 * // With explicit type
 * const result = await tryCatch<User>(async () => {
 *   const response = await fetch('/api/user/1');
 *   return response.json();
 * });
 *
 * // Handling the result
 * if (isOk(result)) {
 *   console.log('Data:', result.value);
 * } else {
 *   console.error('Failed:', result.error.message);
 * }
 *
 * // With match
 * const message = match(await tryCatch(() => fetchData()), {
 *   ok: (data) => `Loaded ${data.length} items`,
 *   err: (error) => `Error: ${error.message}`,
 * });
 * ```
 */
export async function tryCatch<T>(fn: () => Promise<T>): Promise<Result<T, Error>> {
  try {
    const value = await fn();
    return Ok(value);
  } catch (err) {
    return Err(toError(err));
  }
}

// ============================================================================
// Sync tryCatchSync
// ============================================================================

/**
 * Safely executes a synchronous function, catching any thrown exceptions
 * and converting them to a Result type.
 *
 * Use this for synchronous operations that may throw, such as JSON parsing,
 * array operations with potential failures, or validation logic.
 *
 * @typeParam T - The return type of the function
 * @param fn - The synchronous function to execute
 * @returns Ok(value) on success or Err(error) on failure
 *
 * @example
 * ```typescript
 * // JSON parsing
 * const result = tryCatchSync(() => JSON.parse(jsonString));
 * if (isOk(result)) {
 *   console.log('Parsed:', result.value);
 * } else {
 *   console.error('Invalid JSON:', result.error.message);
 * }
 *
 * // Safe division
 * function safeDivide(a: number, b: number): Result<number, Error> {
 *   return tryCatchSync(() => {
 *     if (b === 0) throw new Error('Division by zero');
 *     return a / b;
 *   });
 * }
 *
 * // Array operations
 * const firstItem = tryCatchSync(() => {
 *   const [first] = items;
 *   if (first === undefined) throw new Error('Array is empty');
 *   return first;
 * });
 *
 * // With match
 * const value = match(tryCatchSync(() => JSON.parse(input)), {
 *   ok: (data) => data,
 *   err: () => defaultValue,
 * });
 * ```
 */
export function tryCatchSync<T>(fn: () => T): Result<T, Error> {
  try {
    const value = fn();
    return Ok(value);
  } catch (err) {
    return Err(toError(err));
  }
}

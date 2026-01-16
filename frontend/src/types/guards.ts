/**
 * Type Guards and Type Narrowing Utilities
 *
 * This module provides type-safe alternatives to `Record<string, unknown>` casts
 * and `as` assertions. Type guards allow TypeScript to narrow types safely
 * at runtime, ensuring type safety without unsafe casts.
 *
 * Benefits:
 * - Runtime validation of data shapes
 * - TypeScript automatically narrows types after guard passes
 * - Catches data shape issues at boundaries (API, WebSocket, localStorage)
 * - Self-documenting code - guards specify expected shape
 *
 * @example
 * ```ts
 * // Instead of:
 * const obj = data as Record<string, unknown>;
 * if (obj.type === 'event') { ... }
 *
 * // Use:
 * if (isPlainObject(data) && hasProperty(data, 'type')) {
 *   // data is now typed as { type: unknown } & Record<string, unknown>
 *   if (data.type === 'event') { ... }
 * }
 * ```
 */

// ============================================================================
// Primitive Type Guards
// ============================================================================

/**
 * Type guard for string values.
 */
export function isString(value: unknown): value is string {
  return typeof value === 'string';
}

/**
 * Type guard for number values.
 * Excludes NaN and Infinity.
 */
export function isNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

/**
 * Type guard for boolean values.
 */
export function isBoolean(value: unknown): value is boolean {
  return typeof value === 'boolean';
}

/**
 * Type guard for null values.
 */
export function isNull(value: unknown): value is null {
  return value === null;
}

/**
 * Type guard for undefined values.
 */
export function isUndefined(value: unknown): value is undefined {
  return value === undefined;
}

/**
 * Type guard for null or undefined.
 */
export function isNullish(value: unknown): value is null | undefined {
  return value === null || value === undefined;
}

/**
 * Type guard for non-null, non-undefined values.
 */
export function isDefined<T>(value: T | null | undefined): value is T {
  return value !== null && value !== undefined;
}

// ============================================================================
// Object Type Guards
// ============================================================================

/**
 * Type guard for plain objects (excludes arrays, null, Date, etc.).
 *
 * @example
 * ```ts
 * if (isPlainObject(data)) {
 *   // data is now Record<string, unknown>
 *   console.log(Object.keys(data));
 * }
 * ```
 */
export function isPlainObject(value: unknown): value is Record<string, unknown> {
  if (typeof value !== 'object' || value === null) {
    return false;
  }
  const proto = Object.getPrototypeOf(value) as unknown;
  return proto === Object.prototype || proto === null;
}

/**
 * Type guard for arrays.
 */
export function isArray(value: unknown): value is unknown[] {
  return Array.isArray(value);
}

/**
 * Type guard for arrays of a specific type.
 *
 * @example
 * ```ts
 * if (isArrayOf(data, isString)) {
 *   // data is now string[]
 *   data.forEach(s => console.log(s.toUpperCase()));
 * }
 * ```
 */
export function isArrayOf<T>(value: unknown, guard: (item: unknown) => item is T): value is T[] {
  return Array.isArray(value) && value.every(guard);
}

/**
 * Type guard for non-empty arrays.
 */
export function isNonEmptyArray<T>(value: T[]): value is [T, ...T[]] {
  return value.length > 0;
}

// ============================================================================
// Property Type Guards
// ============================================================================

/**
 * Type guard to check if an object has a specific property.
 * Returns a type predicate that narrows the object type to include the property.
 *
 * @example
 * ```ts
 * if (isPlainObject(data) && hasProperty(data, 'id')) {
 *   // data is now { id: unknown } & Record<string, unknown>
 *   console.log(data.id);
 * }
 * ```
 */
export function hasProperty<K extends string>(
  obj: Record<string, unknown>,
  key: K
): obj is Record<string, unknown> & Record<K, unknown> {
  return key in obj;
}

/**
 * Type guard to check if an object has a property of a specific type.
 *
 * @example
 * ```ts
 * if (isPlainObject(data) && hasPropertyOfType(data, 'id', isNumber)) {
 *   // data is now { id: number } & Record<string, unknown>
 *   console.log(data.id * 2);
 * }
 * ```
 */
export function hasPropertyOfType<K extends string, T>(
  obj: Record<string, unknown>,
  key: K,
  guard: (value: unknown) => value is T
): obj is Record<string, unknown> & Record<K, T> {
  return key in obj && guard(obj[key]);
}

/**
 * Type guard to check if an object has multiple properties.
 *
 * @example
 * ```ts
 * if (isPlainObject(data) && hasProperties(data, ['id', 'name', 'email'])) {
 *   // data has all three properties
 * }
 * ```
 */
export function hasProperties<K extends string>(
  obj: Record<string, unknown>,
  keys: K[]
): obj is Record<string, unknown> & Record<K, unknown> {
  return keys.every((key) => key in obj);
}

// ============================================================================
// Optional Property Guards
// ============================================================================

/**
 * Type guard for optional property - checks if property exists and is of type OR is undefined.
 *
 * @example
 * ```ts
 * if (hasOptionalPropertyOfType(data, 'name', isString)) {
 *   // data.name is string | undefined
 * }
 * ```
 */
export function hasOptionalPropertyOfType<K extends string, T>(
  obj: Record<string, unknown>,
  key: K,
  guard: (value: unknown) => value is T
): obj is Record<string, unknown> & Record<K, T | undefined> {
  return !(key in obj) || obj[key] === undefined || guard(obj[key]);
}

// ============================================================================
// Compound Type Guards
// ============================================================================

/**
 * Creates a type guard that checks if a value matches one of multiple guards.
 *
 * @example
 * ```ts
 * const isStringOrNumber = oneOf(isString, isNumber);
 * if (isStringOrNumber(value)) {
 *   // value is string | number
 * }
 * ```
 */
export function oneOf<T extends unknown[]>(
  ...guards: { [K in keyof T]: (value: unknown) => value is T[K] }
): (value: unknown) => value is T[number] {
  return (value: unknown): value is T[number] => {
    return guards.some((guard) => guard(value));
  };
}

/**
 * Type guard for string or number.
 * Useful for ID fields that may be either type.
 */
export const isStringOrNumber = oneOf(isString, isNumber);

// ============================================================================
// API Response Guards
// ============================================================================

/**
 * Type guard for API error response shape.
 */
export interface ApiErrorShape {
  detail: string;
  status_code?: number;
}

/**
 * Type guard for API error responses.
 */
export function isApiError(value: unknown): value is ApiErrorShape {
  if (!isPlainObject(value)) return false;
  return hasPropertyOfType(value, 'detail', isString);
}

/**
 * Type guard for paginated response shape.
 */
export interface PaginatedResponseShape<T> {
  items: T[];
  total: number;
  page?: number;
  limit?: number;
}

/**
 * Creates a type guard for paginated responses with a specific item type.
 *
 * @example
 * ```ts
 * const isEventList = isPaginatedResponse(isEvent);
 * if (isEventList(data)) {
 *   // data is PaginatedResponseShape<Event>
 *   data.items.forEach(event => console.log(event.id));
 * }
 * ```
 */
export function isPaginatedResponse<T>(
  itemGuard: (value: unknown) => value is T
): (value: unknown) => value is PaginatedResponseShape<T> {
  return (value: unknown): value is PaginatedResponseShape<T> => {
    if (!isPlainObject(value)) return false;
    if (!hasPropertyOfType(value, 'total', isNumber)) return false;
    if (!hasProperty(value, 'items')) return false;
    return isArrayOf(value.items, itemGuard);
  };
}

// ============================================================================
// Utility Types
// ============================================================================

/**
 * Type for a type guard function.
 */
export type TypeGuard<T> = (value: unknown) => value is T;

/**
 * Extract the guarded type from a type guard.
 *
 * @example
 * ```ts
 * type Guarded = GuardedType<typeof isString>; // string
 * ```
 */
export type GuardedType<T> = T extends TypeGuard<infer U> ? U : never;

// ============================================================================
// Safe Property Access
// ============================================================================

/**
 * Safely get a property from an unknown value.
 * Returns undefined if the value is not an object or doesn't have the property.
 *
 * @example
 * ```ts
 * const id = getProperty(data, 'id');
 * if (isNumber(id)) {
 *   // id is number
 * }
 * ```
 */
export function getProperty<K extends string>(value: unknown, key: K): unknown {
  if (!isPlainObject(value)) return undefined;
  return value[key];
}

/**
 * Safely get a typed property from an unknown value.
 *
 * @example
 * ```ts
 * const id = getTypedProperty(data, 'id', isNumber);
 * // id is number | undefined
 * ```
 */
export function getTypedProperty<K extends string, T>(
  value: unknown,
  key: K,
  guard: TypeGuard<T>
): T | undefined {
  const prop = getProperty(value, key);
  return guard(prop) ? prop : undefined;
}

/**
 * Safely get a required typed property, throwing if not found or wrong type.
 *
 * @example
 * ```ts
 * const id = getRequiredProperty(data, 'id', isNumber);
 * // id is number (throws if missing or wrong type)
 * ```
 */
export function getRequiredProperty<K extends string, T>(
  value: unknown,
  key: K,
  guard: TypeGuard<T>,
  errorMessage?: string
): T {
  const prop = getProperty(value, key);
  if (!guard(prop)) {
    throw new Error(errorMessage ?? `Expected property '${key}' to exist and be of correct type`);
  }
  return prop;
}

// ============================================================================
// Object Validation
// ============================================================================

/**
 * Schema definition for object validation.
 */
export type ObjectSchema<T> = {
  [K in keyof T]-?: TypeGuard<T[K]>;
};

/**
 * Validate an object against a schema.
 * Returns true if all properties match their guards.
 *
 * @example
 * ```ts
 * interface User {
 *   id: number;
 *   name: string;
 *   email: string;
 * }
 *
 * const userSchema: ObjectSchema<User> = {
 *   id: isNumber,
 *   name: isString,
 *   email: isString,
 * };
 *
 * if (validateObject(data, userSchema)) {
 *   // data is User
 * }
 * ```
 */
export function validateObject<T extends Record<string, unknown>>(
  value: unknown,
  schema: ObjectSchema<T>
): value is T {
  if (!isPlainObject(value)) return false;

  for (const key of Object.keys(schema) as Array<keyof T>) {
    const guard = schema[key];
    if (!(key in value) || !guard(value[key as string])) {
      return false;
    }
  }

  return true;
}

/**
 * Create a type guard from an object schema.
 *
 * @example
 * ```ts
 * const isUser = createObjectGuard({
 *   id: isNumber,
 *   name: isString,
 *   email: isString,
 * });
 *
 * if (isUser(data)) {
 *   // data is { id: number; name: string; email: string }
 * }
 * ```
 */
export function createObjectGuard<T extends Record<string, unknown>>(
  schema: ObjectSchema<T>
): TypeGuard<T> {
  return (value: unknown): value is T => validateObject(value, schema);
}

// ============================================================================
// Special Value Guards
// ============================================================================

/**
 * Type guard for Date objects.
 */
export function isDate(value: unknown): value is Date {
  return value instanceof Date && !isNaN(value.getTime());
}

/**
 * Type guard for valid ISO date strings.
 */
export function isISODateString(value: unknown): value is string {
  if (!isString(value)) return false;
  const date = new Date(value);
  return !isNaN(date.getTime()) && date.toISOString().startsWith(value.slice(0, 10));
}

/**
 * Type guard for positive numbers (> 0).
 */
export function isPositiveNumber(value: unknown): value is number {
  return isNumber(value) && value > 0;
}

/**
 * Type guard for non-negative numbers (>= 0).
 */
export function isNonNegativeNumber(value: unknown): value is number {
  return isNumber(value) && value >= 0;
}

/**
 * Type guard for integers.
 */
export function isInteger(value: unknown): value is number {
  return isNumber(value) && Number.isInteger(value);
}

/**
 * Type guard for positive integers.
 */
export function isPositiveInteger(value: unknown): value is number {
  return isInteger(value) && value > 0;
}

/**
 * Type guard for non-empty strings.
 */
export function isNonEmptyString(value: unknown): value is string {
  return isString(value) && value.length > 0;
}

/**
 * Type guard for UUID strings.
 */
export function isUUID(value: unknown): value is string {
  if (!isString(value)) return false;
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  return uuidRegex.test(value);
}

// ============================================================================
// Literal Type Guards
// ============================================================================

/**
 * Create a type guard for literal string values.
 *
 * @example
 * ```ts
 * const isRiskLevel = literalUnion('low', 'medium', 'high', 'critical');
 * if (isRiskLevel(value)) {
 *   // value is 'low' | 'medium' | 'high' | 'critical'
 * }
 * ```
 */
export function literalUnion<T extends string>(...values: T[]): TypeGuard<T> {
  const set = new Set<string>(values);
  return (value: unknown): value is T => isString(value) && set.has(value);
}

/**
 * Create a type guard for literal number values.
 */
export function numericLiteralUnion<T extends number>(...values: T[]): TypeGuard<T> {
  const set = new Set<number>(values);
  return (value: unknown): value is T => isNumber(value) && set.has(value);
}

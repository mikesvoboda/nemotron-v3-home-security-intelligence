/**
 * Type guard utilities for runtime type validation.
 *
 * These utilities provide safe runtime type checking as an alternative
 * to unsafe type casts like `as Record<string, unknown>`. They enable
 * TypeScript's type narrowing while validating data at runtime.
 *
 * @example
 * ```typescript
 * // Instead of:
 * const data = response as Record<string, unknown>;
 * const name = data.name as string; // Unsafe!
 *
 * // Use:
 * if (isNonNullObject(response) && hasStringProperty(response, 'name')) {
 *   const name = response.name; // Safe and type-narrowed
 * }
 * ```
 */

/**
 * Type guard that checks if a value is a non-null object (not an array).
 *
 * This is the foundation for other type guards. It validates that a value
 * is a proper object that can have properties checked.
 *
 * @param value - The value to check
 * @returns True if value is a non-null, non-array object
 *
 * @example
 * ```typescript
 * const data: unknown = JSON.parse(jsonString);
 * if (isNonNullObject(data)) {
 *   // data is now typed as Record<string, unknown>
 *   console.log(Object.keys(data));
 * }
 * ```
 */
export function isNonNullObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/**
 * Type guard that checks if an object has a specific property.
 *
 * Uses Object.prototype.hasOwnProperty to check own properties only,
 * not inherited properties from the prototype chain.
 *
 * @param obj - The object to check (unknown type accepted)
 * @param key - The property key to look for
 * @returns True if obj is a non-null object with the specified own property
 *
 * @example
 * ```typescript
 * const data: unknown = { id: 123 };
 * if (hasProperty(data, 'id')) {
 *   // data is now typed as Record<string, unknown> & Record<'id', unknown>
 *   console.log(data.id); // Safe access
 * }
 * ```
 */
export function hasProperty<K extends PropertyKey>(
  obj: unknown,
  key: K
): obj is Record<string, unknown> & Record<K, unknown> {
  return isNonNullObject(obj) && Object.prototype.hasOwnProperty.call(obj, key);
}

/**
 * Type guard that checks if an object has a string property.
 *
 * Validates both that the property exists and that its value is a string.
 *
 * @param obj - The object to check
 * @param key - The property key to look for
 * @returns True if obj has the specified property with a string value
 *
 * @example
 * ```typescript
 * const data: unknown = { name: 'John' };
 * if (hasStringProperty(data, 'name')) {
 *   // data.name is typed as string
 *   console.log(data.name.toUpperCase()); // Safe!
 * }
 * ```
 */
export function hasStringProperty<K extends string>(
  obj: unknown,
  key: K
): obj is Record<string, unknown> & Record<K, string> {
  return hasProperty(obj, key) && typeof obj[key] === 'string';
}

/**
 * Type guard that checks if an object has a number property.
 *
 * Validates that the property exists, is a number, and is not NaN.
 * Infinity and -Infinity are considered valid numbers.
 *
 * @param obj - The object to check
 * @param key - The property key to look for
 * @returns True if obj has the specified property with a valid number value
 *
 * @example
 * ```typescript
 * const data: unknown = { count: 42 };
 * if (hasNumberProperty(data, 'count')) {
 *   // data.count is typed as number
 *   console.log(data.count * 2); // Safe!
 * }
 * ```
 */
export function hasNumberProperty<K extends string>(
  obj: unknown,
  key: K
): obj is Record<string, unknown> & Record<K, number> {
  return hasProperty(obj, key) && typeof obj[key] === 'number' && !Number.isNaN(obj[key]);
}

/**
 * Type guard that checks if an object has a boolean property.
 *
 * Validates that the property exists and is a boolean (true or false).
 * Does not accept truthy/falsy values like 0, '', null, or undefined.
 *
 * @param obj - The object to check
 * @param key - The property key to look for
 * @returns True if obj has the specified property with a boolean value
 *
 * @example
 * ```typescript
 * const data: unknown = { enabled: true };
 * if (hasBooleanProperty(data, 'enabled')) {
 *   // data.enabled is typed as boolean
 *   if (data.enabled) {
 *     console.log('Feature is enabled');
 *   }
 * }
 * ```
 */
export function hasBooleanProperty<K extends string>(
  obj: unknown,
  key: K
): obj is Record<string, unknown> & Record<K, boolean> {
  return hasProperty(obj, key) && typeof obj[key] === 'boolean';
}

/**
 * Type guard that checks if an object has an array property.
 *
 * Validates that the property exists and is a standard Array.
 * TypedArrays (Uint8Array, etc.) are not considered arrays.
 *
 * @param obj - The object to check
 * @param key - The property key to look for
 * @returns True if obj has the specified property with an array value
 *
 * @example
 * ```typescript
 * const data: unknown = { tags: ['typescript', 'react'] };
 * if (hasArrayProperty(data, 'tags')) {
 *   // data.tags is typed as unknown[]
 *   data.tags.forEach(tag => console.log(tag));
 * }
 * ```
 */
export function hasArrayProperty<K extends string>(
  obj: unknown,
  key: K
): obj is Record<string, unknown> & Record<K, unknown[]> {
  return hasProperty(obj, key) && Array.isArray(obj[key]);
}

/**
 * Type guard that checks if a value is one of the allowed values.
 *
 * Uses strict equality (===) for comparison. Useful for validating
 * union types, enum values, or discriminated unions at runtime.
 *
 * @param value - The value to check
 * @param allowedValues - Array of allowed values (use `as const` for best type narrowing)
 * @returns True if value is strictly equal to one of the allowed values
 *
 * @example
 * ```typescript
 * const statuses = ['pending', 'active', 'completed'] as const;
 * const input: string = getUserInput();
 *
 * if (isOneOf(input, statuses)) {
 *   // input is now typed as 'pending' | 'active' | 'completed'
 *   handleStatus(input);
 * }
 * ```
 *
 * @example
 * ```typescript
 * // With discriminated unions
 * type EventType = 'click' | 'hover' | 'focus';
 * const validTypes: EventType[] = ['click', 'hover', 'focus'];
 *
 * function processEvent(type: string) {
 *   if (isOneOf(type, validTypes)) {
 *     // type is now EventType
 *     return handleEvent(type);
 *   }
 *   throw new Error(`Invalid event type: ${type}`);
 * }
 * ```
 */
export function isOneOf<T>(value: unknown, allowedValues: readonly T[]): value is T {
  return allowedValues.includes(value as T);
}

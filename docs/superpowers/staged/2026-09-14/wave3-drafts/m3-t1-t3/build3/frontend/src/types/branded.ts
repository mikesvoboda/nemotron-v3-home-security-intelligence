/**
 * Branded Types for Type-Safe Entity Identifiers
 *
 * Branded types (also known as nominal types or tagged types) prevent accidental
 * misuse of different ID types that share the same underlying primitive type.
 *
 * For example, without branded types, you could accidentally pass an EventId
 * where a CameraId is expected, and TypeScript wouldn't catch the error.
 * With branded types, TypeScript ensures you're using the correct ID type.
 *
 * @example
 * ```ts
 * // This will compile
 * const cameraId: CameraId = 'abc-123' as CameraId;
 * fetchCamera(cameraId); // OK
 *
 * // This won't compile - type mismatch
 * const eventId: EventId = 456 as EventId;
 * fetchCamera(eventId); // Error: EventId is not assignable to CameraId
 * ```
 *
 * @see https://egghead.io/blog/using-branded-types-in-typescript
 */

// ============================================================================
// Brand Symbol
// ============================================================================

/**
 * Unique symbol used for branding types.
 * Using a symbol ensures the brand cannot be accidentally created.
 */
declare const brand: unique symbol;

/**
 * Base branded type that adds a phantom type parameter to the underlying type.
 * The brand is purely a compile-time construct and has no runtime overhead.
 */
export type Brand<T, TBrand extends string> = T & { readonly [brand]: TBrand };

// ============================================================================
// Entity ID Types
// ============================================================================

/**
 * Branded type for Camera IDs (UUID strings).
 *
 * Cameras are identified by UUID strings like 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'.
 * This type ensures you can't accidentally use an EventId or DetectionId
 * where a CameraId is expected.
 *
 * @example
 * ```ts
 * const id = createCameraId('abc-123');
 * fetchCamera(id); // OK - type-safe
 * ```
 */
export type CameraId = Brand<string, 'CameraId'>;

/**
 * Branded type for Event IDs (numeric).
 *
 * Events are identified by auto-incrementing integers from the database.
 * This type prevents accidentally passing a DetectionId where an EventId
 * is expected (both are numbers).
 *
 * @example
 * ```ts
 * const id = createEventId(123);
 * fetchEvent(id); // OK - type-safe
 * ```
 */
export type EventId = Brand<number, 'EventId'>;

/**
 * Branded type for Detection IDs (numeric).
 *
 * Detections are identified by auto-incrementing integers from the database.
 * A single Event can have multiple Detections.
 *
 * @example
 * ```ts
 * const id = createDetectionId(456);
 * fetchDetectionEnrichment(id); // OK - type-safe
 * ```
 */
export type DetectionId = Brand<number, 'DetectionId'>;

/**
 * Branded type for Zone IDs (UUID strings).
 *
 * Zones are spatial regions defined on camera feeds.
 */
export type ZoneId = Brand<string, 'ZoneId'>;

/**
 * Branded type for Alert Rule IDs (UUID strings).
 *
 * Alert rules define conditions that trigger notifications.
 */
export type AlertRuleId = Brand<string, 'AlertRuleId'>;

/**
 * Branded type for Entity IDs (UUID strings).
 *
 * Entities are re-identified persons or vehicles tracked across cameras.
 */
export type EntityId = Brand<string, 'EntityId'>;

/**
 * Branded type for Batch IDs (UUID strings).
 *
 * Batches group related detections from the same time window.
 */
export type BatchId = Brand<string, 'BatchId'>;

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard to check if a value is a valid string for ID purposes.
 */
function isValidStringId(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0;
}

/**
 * Type guard to check if a value is a valid number for ID purposes.
 */
function isValidNumberId(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0;
}

// ============================================================================
// Factory Functions
// ============================================================================

/**
 * Creates a branded CameraId from a string.
 * Validates that the input is a non-empty string.
 *
 * @param id - The camera UUID string
 * @returns A branded CameraId
 * @throws Error if the input is not a valid string
 */
export function createCameraId(id: string): CameraId {
  if (!isValidStringId(id)) {
    throw new Error(`Invalid CameraId: expected non-empty string, got ${typeof id}`);
  }
  return id as CameraId;
}

/**
 * Creates a branded EventId from a number.
 * Validates that the input is a non-negative finite number.
 *
 * @param id - The event ID number
 * @returns A branded EventId
 * @throws Error if the input is not a valid number
 */
export function createEventId(id: number): EventId {
  if (!isValidNumberId(id)) {
    throw new Error(`Invalid EventId: expected non-negative number, got ${typeof id}`);
  }
  return id as EventId;
}

/**
 * Creates a branded DetectionId from a number.
 * Validates that the input is a non-negative finite number.
 *
 * @param id - The detection ID number
 * @returns A branded DetectionId
 * @throws Error if the input is not a valid number
 */
export function createDetectionId(id: number): DetectionId {
  if (!isValidNumberId(id)) {
    throw new Error(`Invalid DetectionId: expected non-negative number, got ${typeof id}`);
  }
  return id as DetectionId;
}

/**
 * Creates a branded ZoneId from a string.
 *
 * @param id - The zone UUID string
 * @returns A branded ZoneId
 * @throws Error if the input is not a valid string
 */
export function createZoneId(id: string): ZoneId {
  if (!isValidStringId(id)) {
    throw new Error(`Invalid ZoneId: expected non-empty string, got ${typeof id}`);
  }
  return id as ZoneId;
}

/**
 * Creates a branded AlertRuleId from a string.
 *
 * @param id - The alert rule UUID string
 * @returns A branded AlertRuleId
 * @throws Error if the input is not a valid string
 */
export function createAlertRuleId(id: string): AlertRuleId {
  if (!isValidStringId(id)) {
    throw new Error(`Invalid AlertRuleId: expected non-empty string, got ${typeof id}`);
  }
  return id as AlertRuleId;
}

/**
 * Creates a branded EntityId from a string.
 *
 * @param id - The entity UUID string
 * @returns A branded EntityId
 * @throws Error if the input is not a valid string
 */
export function createEntityId(id: string): EntityId {
  if (!isValidStringId(id)) {
    throw new Error(`Invalid EntityId: expected non-empty string, got ${typeof id}`);
  }
  return id as EntityId;
}

/**
 * Creates a branded BatchId from a string.
 *
 * @param id - The batch UUID string
 * @returns A branded BatchId
 * @throws Error if the input is not a valid string
 */
export function createBatchId(id: string): BatchId {
  if (!isValidStringId(id)) {
    throw new Error(`Invalid BatchId: expected non-empty string, got ${typeof id}`);
  }
  return id as BatchId;
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Extracts the raw string value from a string-branded type.
 * This is useful when you need to pass the ID to an external API or serialize it.
 *
 * @param id - A branded string ID (CameraId, ZoneId, AlertRuleId, EntityId, or BatchId)
 * @returns The underlying string value
 */
export function unwrapStringId<T extends CameraId | ZoneId | AlertRuleId | EntityId | BatchId>(
  id: T
): string {
  return id as unknown as string;
}

/**
 * Extracts the raw number value from a number-branded type.
 * This is useful when you need to pass the ID to an external API or serialize it.
 *
 * @param id - A branded number ID (EventId or DetectionId)
 * @returns The underlying number value
 */
export function unwrapNumberId<T extends EventId | DetectionId>(id: T): number {
  return id as unknown as number;
}

/**
 * Type-safe comparison for branded IDs.
 * Ensures you only compare IDs of the same type.
 *
 * @param a - First ID
 * @param b - Second ID
 * @returns True if the IDs are equal
 */
export function isSameId<T extends CameraId | ZoneId | AlertRuleId | EntityId | BatchId>(
  a: T,
  b: T
): boolean {
  return a === b;
}

/**
 * Type-safe comparison for numeric branded IDs.
 *
 * @param a - First ID
 * @param b - Second ID
 * @returns True if the IDs are equal
 */
export function isSameNumericId<T extends EventId | DetectionId>(a: T, b: T): boolean {
  return a === b;
}

// ============================================================================
// Utility Types for Working with Branded Types
// ============================================================================

/**
 * Extracts the base type from a branded type.
 *
 * @example
 * ```ts
 * type BaseType = Unbrand<CameraId>; // string
 * type BaseType2 = Unbrand<EventId>; // number
 * ```
 */
export type Unbrand<T> = T extends Brand<infer U, string> ? U : T;

/**
 * Type representing any string-based entity ID.
 */
export type StringEntityId = CameraId | ZoneId | AlertRuleId | EntityId | BatchId;

/**
 * Type representing any numeric entity ID.
 */
export type NumericEntityId = EventId | DetectionId;

/**
 * Type representing any entity ID.
 */
export type AnyEntityId = StringEntityId | NumericEntityId;

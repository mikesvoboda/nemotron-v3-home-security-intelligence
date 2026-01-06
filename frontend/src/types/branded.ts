/**
 * Branded Types for Entity IDs
 *
 * This module provides compile-time nominal typing for entity IDs using the
 * "branded types" pattern (also known as "opaque types" or "newtype pattern").
 *
 * Why branded types?
 * - Prevents accidental mixing of different ID types (e.g., passing EventId where CameraId expected)
 * - Provides compile-time safety without runtime overhead
 * - Makes code more self-documenting by expressing intent through types
 *
 * Usage:
 * ```typescript
 * // Creating branded IDs
 * const cameraId = asCameraId('camera-123');
 * const eventId = asEventId(456);
 *
 * // Type error - cannot assign CameraId to EventId
 * const wrongId: EventId = cameraId; // Error!
 *
 * // Type guards for runtime validation
 * if (isCameraId(unknownValue)) {
 *   // TypeScript knows this is CameraId
 * }
 * ```
 *
 * @see https://egghead.io/blog/using-branded-types-in-typescript
 */

// ============================================================================
// Branded Type Infrastructure
// ============================================================================

/**
 * Brand symbol for nominal typing.
 * Using a unique symbol ensures type-level distinction without runtime impact.
 */
declare const BrandSymbol: unique symbol;

/**
 * Brand type that adds a nominal type tag to a base type.
 * The brand is purely compile-time and has no runtime representation.
 *
 * @template T - The base type (usually string or number)
 * @template BrandTag - A unique string literal that identifies the brand
 */
export type Brand<T, BrandTag extends string> = T & {
  readonly [BrandSymbol]: BrandTag;
};

// ============================================================================
// Entity ID Branded Types
// ============================================================================

/**
 * Branded type for Camera entity IDs.
 * Cameras use string identifiers (e.g., 'front_door', 'backyard').
 */
export type CameraId = Brand<string, 'CameraId'>;

/**
 * Branded type for Event entity IDs.
 * Events use numeric identifiers from the database.
 */
export type EventId = Brand<number, 'EventId'>;

/**
 * Branded type for Detection entity IDs.
 * Detections use numeric identifiers from the database.
 */
export type DetectionId = Brand<number, 'DetectionId'>;

/**
 * Branded type for Zone entity IDs.
 * Zones use numeric identifiers from the database.
 */
export type ZoneId = Brand<number, 'ZoneId'>;

/**
 * Branded type for AlertRule entity IDs.
 * Alert rules use numeric identifiers from the database.
 */
export type AlertRuleId = Brand<number, 'AlertRuleId'>;

/**
 * Branded type for generic Entity IDs (polymorphic).
 * Used when the specific entity type is not known at compile time.
 * Can be either string or number based on the entity type.
 */
export type EntityId = Brand<string | number, 'EntityId'>;

/**
 * Branded type for AuditLog entity IDs.
 * Audit logs use numeric identifiers from the database.
 */
export type AuditLogId = Brand<number, 'AuditLogId'>;

// ============================================================================
// Constructor Functions
// ============================================================================

/**
 * Creates a CameraId from a string value.
 * Use this to explicitly brand a string as a CameraId.
 *
 * @param id - The string identifier for the camera
 * @returns The branded CameraId
 *
 * @example
 * const id = asCameraId('front_door');
 */
export function asCameraId(id: string): CameraId {
  return id as CameraId;
}

/**
 * Creates an EventId from a numeric value.
 * Use this to explicitly brand a number as an EventId.
 *
 * @param id - The numeric identifier for the event
 * @returns The branded EventId
 *
 * @example
 * const id = asEventId(123);
 */
export function asEventId(id: number): EventId {
  return id as EventId;
}

/**
 * Creates a DetectionId from a numeric value.
 * Use this to explicitly brand a number as a DetectionId.
 *
 * @param id - The numeric identifier for the detection
 * @returns The branded DetectionId
 *
 * @example
 * const id = asDetectionId(456);
 */
export function asDetectionId(id: number): DetectionId {
  return id as DetectionId;
}

/**
 * Creates a ZoneId from a numeric value.
 * Use this to explicitly brand a number as a ZoneId.
 *
 * @param id - The numeric identifier for the zone
 * @returns The branded ZoneId
 *
 * @example
 * const id = asZoneId(789);
 */
export function asZoneId(id: number): ZoneId {
  return id as ZoneId;
}

/**
 * Creates an AlertRuleId from a numeric value.
 * Use this to explicitly brand a number as an AlertRuleId.
 *
 * @param id - The numeric identifier for the alert rule
 * @returns The branded AlertRuleId
 *
 * @example
 * const id = asAlertRuleId(42);
 */
export function asAlertRuleId(id: number): AlertRuleId {
  return id as AlertRuleId;
}

/**
 * Creates an EntityId from a string or numeric value.
 * Use this for polymorphic ID handling when the entity type is not known.
 *
 * @param id - The string or numeric identifier
 * @returns The branded EntityId
 *
 * @example
 * const id = asEntityId('camera-123');
 * const numId = asEntityId(456);
 */
export function asEntityId(id: string | number): EntityId {
  return id as EntityId;
}

/**
 * Creates an AuditLogId from a numeric value.
 * Use this to explicitly brand a number as an AuditLogId.
 *
 * @param id - The numeric identifier for the audit log
 * @returns The branded AuditLogId
 *
 * @example
 * const id = asAuditLogId(999);
 */
export function asAuditLogId(id: number): AuditLogId {
  return id as AuditLogId;
}

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard to check if a value is a valid CameraId.
 * Validates that the value is a non-empty string.
 *
 * @param value - The value to check
 * @returns True if the value is a valid CameraId
 *
 * @example
 * if (isCameraId(unknownValue)) {
 *   // TypeScript knows this is CameraId
 *   fetchCamera(unknownValue);
 * }
 */
export function isCameraId(value: unknown): value is CameraId {
  return typeof value === 'string' && value.length > 0;
}

/**
 * Type guard to check if a value is a valid EventId.
 * Validates that the value is a non-negative integer.
 *
 * @param value - The value to check
 * @returns True if the value is a valid EventId
 *
 * @example
 * if (isEventId(unknownValue)) {
 *   fetchEvent(unknownValue);
 * }
 */
export function isEventId(value: unknown): value is EventId {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0;
}

/**
 * Type guard to check if a value is a valid DetectionId.
 * Validates that the value is a non-negative integer.
 *
 * @param value - The value to check
 * @returns True if the value is a valid DetectionId
 */
export function isDetectionId(value: unknown): value is DetectionId {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0;
}

/**
 * Type guard to check if a value is a valid ZoneId.
 * Validates that the value is a non-negative integer.
 *
 * @param value - The value to check
 * @returns True if the value is a valid ZoneId
 */
export function isZoneId(value: unknown): value is ZoneId {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0;
}

/**
 * Type guard to check if a value is a valid AlertRuleId.
 * Validates that the value is a non-negative integer.
 *
 * @param value - The value to check
 * @returns True if the value is a valid AlertRuleId
 */
export function isAlertRuleId(value: unknown): value is AlertRuleId {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0;
}

/**
 * Type guard to check if a value is a valid EntityId.
 * Validates that the value is either a non-empty string or a non-negative integer.
 *
 * @param value - The value to check
 * @returns True if the value is a valid EntityId
 */
export function isEntityId(value: unknown): value is EntityId {
  if (typeof value === 'string') {
    return value.length > 0;
  }
  if (typeof value === 'number') {
    return Number.isInteger(value) && value >= 0;
  }
  return false;
}

/**
 * Type guard to check if a value is a valid AuditLogId.
 * Validates that the value is a non-negative integer.
 *
 * @param value - The value to check
 * @returns True if the value is a valid AuditLogId
 */
export function isAuditLogId(value: unknown): value is AuditLogId {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0;
}

// ============================================================================
// Utility Types
// ============================================================================

/**
 * Extracts the base type from a branded type.
 * Useful when you need to work with the underlying value.
 *
 * @example
 * type BaseCameraId = Unbrand<CameraId>; // string
 * type BaseEventId = Unbrand<EventId>; // number
 */
export type Unbrand<T> = T extends Brand<infer U, string> ? U : T;

/**
 * Union of all entity ID types.
 * Useful for generic handlers that accept any entity ID.
 */
export type AnyEntityId =
  | CameraId
  | EventId
  | DetectionId
  | ZoneId
  | AlertRuleId
  | AuditLogId
  | EntityId;

/**
 * Maps entity type names to their corresponding ID types.
 * Useful for creating generic functions that operate on entities.
 */
export interface EntityIdMap {
  camera: CameraId;
  event: EventId;
  detection: DetectionId;
  zone: ZoneId;
  alertRule: AlertRuleId;
  auditLog: AuditLogId;
}

/**
 * Type-safe lookup of entity ID type by entity name.
 *
 * @example
 * type MyId = EntityIdType<'camera'>; // CameraId
 */
export type EntityIdType<K extends keyof EntityIdMap> = EntityIdMap[K];

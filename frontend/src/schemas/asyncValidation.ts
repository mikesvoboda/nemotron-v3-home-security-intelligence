/**
 * Async Zod validation utilities for unique constraint checking (NEM-3825).
 *
 * Provides async refinements that validate uniqueness against the backend API.
 * These are used in forms to provide real-time feedback about duplicate names
 * before submitting to the server.
 *
 * IMPORTANT: Backend validation is authoritative; these async validators provide
 * UX feedback to catch duplicates early and avoid server round-trips for validation.
 *
 * Usage:
 *   import { createUniqueNameValidator, uniqueNameRefinement } from '@/schemas/asyncValidation';
 *
 *   // Create a schema with async uniqueness validation
 *   const cameraNameSchemaWithUnique = cameraNameSchema.superRefine(
 *     uniqueNameRefinement(fetchCameras, 'name', 'Camera')
 *   );
 *
 *   // Or use the validator directly
 *   const validator = createUniqueNameValidator(fetchCameras, 'name', 'Camera');
 *   const isUnique = await validator.isUnique('Front Door', 'existing-id');
 */

import { z } from 'zod';

// =============================================================================
// Types
// =============================================================================

/**
 * Result of a uniqueness check.
 */
export interface UniqueCheckResult {
  /** Whether the value is unique */
  isUnique: boolean;
  /** Optional error message if not unique */
  message?: string;
  /** The conflicting item's ID if not unique */
  conflictingId?: string;
}

/**
 * Function type for fetching entities from the API.
 * Should return a list of items with at least 'id' and the field being checked.
 */
export type FetchEntitiesFunction<T extends { id: string }> = () => Promise<T[]>;

/**
 * Cached uniqueness validation to avoid redundant API calls.
 * Key format: "entityType:field:value:excludeId?"
 */
const validationCache = new Map<
  string,
  { result: UniqueCheckResult; timestamp: number }
>();

/**
 * Cache TTL in milliseconds (5 seconds).
 * Short TTL because data can change quickly in multi-user scenarios.
 */
const CACHE_TTL_MS = 5000;

// =============================================================================
// Cache Utilities
// =============================================================================

/**
 * Generate a cache key for a uniqueness check.
 */
function getCacheKey(
  entityType: string,
  field: string,
  value: string,
  excludeId?: string
): string {
  return `${entityType}:${field}:${value.toLowerCase()}:${excludeId || ''}`;
}

/**
 * Get a cached result if it exists and is not expired.
 */
function getCachedResult(cacheKey: string): UniqueCheckResult | null {
  const cached = validationCache.get(cacheKey);
  if (cached && Date.now() - cached.timestamp < CACHE_TTL_MS) {
    return cached.result;
  }
  // Clean up expired entry
  if (cached) {
    validationCache.delete(cacheKey);
  }
  return null;
}

/**
 * Cache a uniqueness check result.
 */
function setCachedResult(cacheKey: string, result: UniqueCheckResult): void {
  validationCache.set(cacheKey, { result, timestamp: Date.now() });
}

/**
 * Clear the validation cache.
 * Useful for testing or after mutations that change entity names.
 */
export function clearValidationCache(): void {
  validationCache.clear();
}

/**
 * Invalidate cache entries for a specific entity type.
 * Call this after creating, updating, or deleting an entity.
 */
export function invalidateCacheForEntity(entityType: string): void {
  const prefix = `${entityType}:`;
  for (const key of validationCache.keys()) {
    if (key.startsWith(prefix)) {
      validationCache.delete(key);
    }
  }
}

// =============================================================================
// Unique Name Validator
// =============================================================================

/**
 * Creates a uniqueness validator for an entity type.
 *
 * @param fetchEntities - Function to fetch all entities of this type
 * @param field - The field to check for uniqueness (usually 'name')
 * @param entityType - Human-readable entity type name (e.g., 'Camera', 'Zone')
 * @returns Validator with isUnique method
 *
 * @example
 * ```typescript
 * const cameraValidator = createUniqueNameValidator(fetchCameras, 'name', 'Camera');
 * const result = await cameraValidator.isUnique('Front Door', 'existing-camera-id');
 * if (!result.isUnique) {
 *   console.log(result.message); // "Camera name 'Front Door' already exists"
 * }
 * ```
 */
export function createUniqueNameValidator<T extends { id: string }>(
  fetchEntities: FetchEntitiesFunction<T>,
  field: keyof T & string,
  entityType: string
) {
  return {
    /**
     * Check if a value is unique among existing entities.
     *
     * @param value - The value to check for uniqueness
     * @param excludeId - Optional ID to exclude (for updates)
     * @returns Promise<UniqueCheckResult>
     */
    async isUnique(value: string, excludeId?: string): Promise<UniqueCheckResult> {
      // Normalize value for comparison
      const normalizedValue = value.trim().toLowerCase();
      if (!normalizedValue) {
        // Empty values are handled by required validators
        return { isUnique: true };
      }

      // Check cache first
      const cacheKey = getCacheKey(entityType, field, normalizedValue, excludeId);
      const cached = getCachedResult(cacheKey);
      if (cached) {
        return cached;
      }

      try {
        const entities = await fetchEntities();
        const fieldValue = field as keyof T;

        // Find any entity with matching name (case-insensitive)
        const conflict = entities.find((entity) => {
          // Skip the entity being edited
          if (excludeId && entity.id === excludeId) {
            return false;
          }
          const entityFieldValue = entity[fieldValue];
          if (typeof entityFieldValue !== 'string') {
            return false;
          }
          return entityFieldValue.toLowerCase() === normalizedValue;
        });

        const result: UniqueCheckResult = conflict
          ? {
              isUnique: false,
              message: `${entityType} name '${value}' already exists`,
              conflictingId: conflict.id,
            }
          : { isUnique: true };

        // Cache the result
        setCachedResult(cacheKey, result);

        return result;
      } catch (error) {
        // On API error, allow the value (backend will validate)
        console.warn(`Failed to validate unique ${entityType} name:`, error);
        return { isUnique: true };
      }
    },
  };
}

// =============================================================================
// Zod Async Refinement
// =============================================================================

/**
 * Context passed to async validation for entity updates.
 * Used to exclude the current entity from uniqueness checks.
 */
export interface AsyncValidationContext {
  /** ID of the entity being edited (undefined for creates) */
  excludeId?: string;
}

/**
 * Creates a Zod superRefine function for uniqueness validation.
 *
 * @param fetchEntities - Function to fetch all entities of this type
 * @param field - The field to check for uniqueness (usually 'name')
 * @param entityType - Human-readable entity type name (e.g., 'Camera', 'Zone')
 * @returns Zod superRefine function
 *
 * @example
 * ```typescript
 * // Basic usage (for creates)
 * const cameraNameSchema = z.string().superRefine(
 *   uniqueNameRefinement(fetchCameras, 'name', 'Camera')
 * );
 *
 * // With context for updates
 * const schema = cameraNameSchema;
 * const result = await schema.parseAsync(name, { context: { excludeId: 'existing-id' } });
 * ```
 */
export function uniqueNameRefinement<T extends { id: string }>(
  fetchEntities: FetchEntitiesFunction<T>,
  field: keyof T & string,
  entityType: string
): (
  value: string,
  ctx: z.RefinementCtx
) => Promise<void> {
  const validator = createUniqueNameValidator(fetchEntities, field, entityType);

  return async (value: string, ctx: z.RefinementCtx) => {
    // Get context from Zod's path meta (set during parseAsync)
    // Note: Zod 4.x doesn't directly support custom context, so we check
    // if ctx has any attached metadata for excludeId
    const excludeId = (ctx as unknown as { excludeId?: string }).excludeId;

    const result = await validator.isUnique(value, excludeId);

    if (!result.isUnique && result.message) {
      ctx.addIssue({
        code: 'custom',
        message: result.message,
        params: { conflictingId: result.conflictingId },
      });
    }
  };
}

/**
 * Creates an async schema that validates uniqueness.
 * This wraps a base string schema with async uniqueness validation.
 *
 * @param baseSchema - The base Zod string schema to extend
 * @param fetchEntities - Function to fetch all entities of this type
 * @param field - The field to check for uniqueness (usually 'name')
 * @param entityType - Human-readable entity type name (e.g., 'Camera', 'Zone')
 * @returns Async Zod schema with uniqueness validation
 *
 * @example
 * ```typescript
 * import { cameraNameSchema } from '@/schemas/camera';
 *
 * // Create async schema for camera name with uniqueness check
 * const uniqueCameraNameSchema = createAsyncUniqueSchema(
 *   cameraNameSchema,
 *   fetchCameras,
 *   'name',
 *   'Camera'
 * );
 *
 * // Validate (must use parseAsync for async validation)
 * const result = await uniqueCameraNameSchema.safeParseAsync('Front Door');
 * ```
 */
export function createAsyncUniqueSchema<T extends { id: string }>(
  baseSchema: z.ZodString,
  fetchEntities: FetchEntitiesFunction<T>,
  field: keyof T & string,
  entityType: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
): any {
  return baseSchema.superRefine(uniqueNameRefinement(fetchEntities, field, entityType));
}

// =============================================================================
// Debounced Validation Helper
// =============================================================================

/**
 * Creates a debounced uniqueness checker for use in form inputs.
 * Useful for real-time validation as the user types.
 *
 * @param fetchEntities - Function to fetch all entities of this type
 * @param field - The field to check for uniqueness
 * @param entityType - Human-readable entity type name
 * @param debounceMs - Debounce delay in milliseconds (default: 300ms)
 * @returns Object with check method and cancel method
 *
 * @example
 * ```typescript
 * const debouncedCheck = createDebouncedUniqueChecker(
 *   fetchCameras,
 *   'name',
 *   'Camera',
 *   300
 * );
 *
 * // In input onChange handler
 * const handleNameChange = (name: string) => {
 *   setName(name);
 *   debouncedCheck.check(name, excludeId).then(result => {
 *     if (!result.isUnique) {
 *       setNameError(result.message);
 *     } else {
 *       setNameError(undefined);
 *     }
 *   });
 * };
 *
 * // Cleanup on unmount
 * useEffect(() => () => debouncedCheck.cancel(), []);
 * ```
 */
export function createDebouncedUniqueChecker<T extends { id: string }>(
  fetchEntities: FetchEntitiesFunction<T>,
  field: keyof T & string,
  entityType: string,
  debounceMs: number = 300
) {
  const validator = createUniqueNameValidator(fetchEntities, field, entityType);
  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  let pendingResolve: ((result: UniqueCheckResult) => void) | null = null;

  return {
    /**
     * Check uniqueness with debouncing.
     * Multiple rapid calls will only execute the last one.
     */
    check(value: string, excludeId?: string): Promise<UniqueCheckResult> {
      // Cancel any pending check
      if (timeoutId) {
        clearTimeout(timeoutId);
        // Resolve pending promise with "unique" to avoid hanging
        if (pendingResolve) {
          pendingResolve({ isUnique: true });
          pendingResolve = null;
        }
      }

      return new Promise((resolve) => {
        pendingResolve = resolve;
        timeoutId = setTimeout(async () => {
          const result = await validator.isUnique(value, excludeId);
          pendingResolve = null;
          timeoutId = null;
          resolve(result);
        }, debounceMs);
      });
    },

    /**
     * Cancel any pending check.
     */
    cancel(): void {
      if (timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = null;
      }
      if (pendingResolve) {
        pendingResolve({ isUnique: true });
        pendingResolve = null;
      }
    },
  };
}

// =============================================================================
// Pre-built Validators for Common Entities
// =============================================================================

// These are factory functions that create validators when the fetch function is available.
// This allows the validators to be used without circular imports.

/**
 * Factory to create a camera name uniqueness validator.
 * @param fetchCameras - Function to fetch all cameras
 */
export function createCameraNameValidator(
  fetchCameras: FetchEntitiesFunction<{ id: string; name: string }>
) {
  return createUniqueNameValidator(fetchCameras, 'name', 'Camera');
}

/**
 * Factory to create a zone name uniqueness validator.
 * @param fetchZones - Function to fetch all zones
 */
export function createZoneNameValidator(
  fetchZones: FetchEntitiesFunction<{ id: string; name: string }>
) {
  return createUniqueNameValidator(fetchZones, 'name', 'Zone');
}

/**
 * Factory to create an alert rule name uniqueness validator.
 * @param fetchAlertRules - Function to fetch all alert rules
 */
export function createAlertRuleNameValidator(
  fetchAlertRules: FetchEntitiesFunction<{ id: string; name: string }>
) {
  return createUniqueNameValidator(fetchAlertRules, 'name', 'Alert rule');
}

/**
 * Tests for async Zod validation utilities (NEM-3825).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { z } from 'zod';

import {
  createUniqueNameValidator,
  uniqueNameRefinement,
  createAsyncUniqueSchema,
  createDebouncedUniqueChecker,
  clearValidationCache,
  invalidateCacheForEntity,
  createCameraNameValidator,
  createZoneNameValidator,
  createAlertRuleNameValidator,
} from './asyncValidation';

// =============================================================================
// Test Fixtures
// =============================================================================

interface TestEntity {
  id: string;
  name: string;
}

const mockEntities: TestEntity[] = [
  { id: '1', name: 'Front Door' },
  { id: '2', name: 'Back Yard' },
  { id: '3', name: 'Garage' },
];

const mockFetchEntities = vi.fn<() => Promise<TestEntity[]>>();

// =============================================================================
// Setup/Teardown
// =============================================================================

beforeEach(() => {
  vi.clearAllMocks();
  clearValidationCache();
  mockFetchEntities.mockResolvedValue(mockEntities);
});

afterEach(() => {
  clearValidationCache();
});

// =============================================================================
// createUniqueNameValidator Tests
// =============================================================================

describe('createUniqueNameValidator', () => {
  it('should return isUnique=true for unique name', async () => {
    const validator = createUniqueNameValidator(mockFetchEntities, 'name', 'Camera');
    const result = await validator.isUnique('New Camera');

    expect(result.isUnique).toBe(true);
    expect(result.message).toBeUndefined();
  });

  it('should return isUnique=false for duplicate name', async () => {
    const validator = createUniqueNameValidator(mockFetchEntities, 'name', 'Camera');
    const result = await validator.isUnique('Front Door');

    expect(result.isUnique).toBe(false);
    expect(result.message).toBe("Camera name 'Front Door' already exists");
    expect(result.conflictingId).toBe('1');
  });

  it('should be case-insensitive', async () => {
    const validator = createUniqueNameValidator(mockFetchEntities, 'name', 'Camera');
    const result = await validator.isUnique('FRONT DOOR');

    expect(result.isUnique).toBe(false);
    expect(result.message).toBe("Camera name 'FRONT DOOR' already exists");
  });

  it('should exclude specified ID for updates', async () => {
    const validator = createUniqueNameValidator(mockFetchEntities, 'name', 'Camera');
    // Updating entity with id='1' which has name='Front Door'
    const result = await validator.isUnique('Front Door', '1');

    // Should be unique because we're excluding the entity being edited
    expect(result.isUnique).toBe(true);
  });

  it('should return isUnique=true for empty value', async () => {
    const validator = createUniqueNameValidator(mockFetchEntities, 'name', 'Camera');
    const result = await validator.isUnique('');

    expect(result.isUnique).toBe(true);
    // Should not call fetch for empty values
    expect(mockFetchEntities).not.toHaveBeenCalled();
  });

  it('should return isUnique=true for whitespace-only value', async () => {
    const validator = createUniqueNameValidator(mockFetchEntities, 'name', 'Camera');
    const result = await validator.isUnique('   ');

    expect(result.isUnique).toBe(true);
    expect(mockFetchEntities).not.toHaveBeenCalled();
  });

  it('should trim values before comparison', async () => {
    const validator = createUniqueNameValidator(mockFetchEntities, 'name', 'Camera');
    const result = await validator.isUnique('  Front Door  ');

    expect(result.isUnique).toBe(false);
  });

  it('should handle API errors gracefully', async () => {
    mockFetchEntities.mockRejectedValueOnce(new Error('Network error'));
    const validator = createUniqueNameValidator(mockFetchEntities, 'name', 'Camera');

    // Should not throw, instead allow the value (backend will validate)
    const result = await validator.isUnique('Any Name');
    expect(result.isUnique).toBe(true);
  });
});

// =============================================================================
// Cache Tests
// =============================================================================

describe('Validation Cache', () => {
  it('should cache validation results', async () => {
    const validator = createUniqueNameValidator(mockFetchEntities, 'name', 'Camera');

    // First call
    await validator.isUnique('New Camera');
    expect(mockFetchEntities).toHaveBeenCalledTimes(1);

    // Second call with same value should use cache
    await validator.isUnique('New Camera');
    expect(mockFetchEntities).toHaveBeenCalledTimes(1);
  });

  it('should cache unique and duplicate results separately', async () => {
    const validator = createUniqueNameValidator(mockFetchEntities, 'name', 'Camera');

    await validator.isUnique('New Camera');
    await validator.isUnique('Front Door');

    // Both should be called separately
    expect(mockFetchEntities).toHaveBeenCalledTimes(2);

    // Calling again should use cache
    await validator.isUnique('New Camera');
    await validator.isUnique('Front Door');
    expect(mockFetchEntities).toHaveBeenCalledTimes(2);
  });

  it('should use different cache entries for different excludeIds', async () => {
    const validator = createUniqueNameValidator(mockFetchEntities, 'name', 'Camera');

    await validator.isUnique('Front Door'); // No excludeId
    await validator.isUnique('Front Door', '1'); // With excludeId

    // Both calls should hit the API
    expect(mockFetchEntities).toHaveBeenCalledTimes(2);
  });

  it('should clear cache with clearValidationCache()', async () => {
    const validator = createUniqueNameValidator(mockFetchEntities, 'name', 'Camera');

    await validator.isUnique('New Camera');
    expect(mockFetchEntities).toHaveBeenCalledTimes(1);

    clearValidationCache();

    await validator.isUnique('New Camera');
    expect(mockFetchEntities).toHaveBeenCalledTimes(2);
  });

  it('should invalidate cache for specific entity type', async () => {
    const cameraValidator = createUniqueNameValidator(mockFetchEntities, 'name', 'Camera');
    const zoneValidator = createUniqueNameValidator(mockFetchEntities, 'name', 'Zone');

    await cameraValidator.isUnique('Test');
    await zoneValidator.isUnique('Test');
    expect(mockFetchEntities).toHaveBeenCalledTimes(2);

    // Invalidate only Camera cache
    invalidateCacheForEntity('Camera');

    await cameraValidator.isUnique('Test'); // Should fetch
    await zoneValidator.isUnique('Test'); // Should use cache
    expect(mockFetchEntities).toHaveBeenCalledTimes(3);
  });
});

// =============================================================================
// uniqueNameRefinement Tests
// =============================================================================

describe('uniqueNameRefinement', () => {
  it('should work with Zod superRefine', async () => {
    const schema = z.string().superRefine(uniqueNameRefinement(mockFetchEntities, 'name', 'Camera'));

    // Valid unique name
    const result1 = await schema.safeParseAsync('New Camera');
    expect(result1.success).toBe(true);

    // Duplicate name
    clearValidationCache(); // Clear cache between tests
    const result2 = await schema.safeParseAsync('Front Door');
    expect(result2.success).toBe(false);
    if (!result2.success) {
      expect(result2.error.issues[0].message).toBe("Camera name 'Front Door' already exists");
    }
  });
});

// =============================================================================
// createAsyncUniqueSchema Tests
// =============================================================================

describe('createAsyncUniqueSchema', () => {
  it('should create async schema with uniqueness validation', async () => {
    const baseSchema = z.string().min(1);
    const schema = createAsyncUniqueSchema(baseSchema, mockFetchEntities, 'name', 'Zone');

    // Valid and unique
    const result1 = await schema.safeParseAsync('New Zone');
    expect(result1.success).toBe(true);

    // Clear cache before next test
    clearValidationCache();

    // Valid but duplicate
    const result2 = await schema.safeParseAsync('Front Door');
    expect(result2.success).toBe(false);
  });

  it('should preserve base schema validation', async () => {
    const baseSchema = z.string().min(3);
    const schema = createAsyncUniqueSchema(baseSchema, mockFetchEntities, 'name', 'Zone');

    // Fails base schema validation (too short)
    const result = await schema.safeParseAsync('AB');
    expect(result.success).toBe(false);
    if (!result.success) {
      // Zod 4.x uses different message format: "Too small: expected string to have >=3 characters"
      expect(result.error.issues[0].message).toMatch(/3/);
    }
  });
});

// =============================================================================
// createDebouncedUniqueChecker Tests
// =============================================================================

describe('createDebouncedUniqueChecker', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should debounce multiple rapid calls', async () => {
    const checker = createDebouncedUniqueChecker(mockFetchEntities, 'name', 'Camera', 300);

    // Make multiple rapid calls
    const promise1 = checker.check('First');
    const promise2 = checker.check('Second');
    const promise3 = checker.check('Third');

    // Advance time past debounce
    vi.advanceTimersByTime(350);

    // Wait for all promises
    await Promise.all([promise1, promise2, promise3]);

    // Only the last call should have triggered the API
    expect(mockFetchEntities).toHaveBeenCalledTimes(1);
  });

  it('should cancel pending check on cancel()', async () => {
    const checker = createDebouncedUniqueChecker(mockFetchEntities, 'name', 'Camera', 300);

    const promise = checker.check('Test');
    checker.cancel();

    // Advance time
    vi.advanceTimersByTime(350);

    const result = await promise;
    expect(result.isUnique).toBe(true);
    // API should not have been called because we cancelled
    expect(mockFetchEntities).not.toHaveBeenCalled();
  });

  it('should resolve intermediate promises with isUnique=true', async () => {
    const checker = createDebouncedUniqueChecker(mockFetchEntities, 'name', 'Camera', 300);

    const promise1 = checker.check('First');
    vi.advanceTimersByTime(100);

    const promise2 = checker.check('Second');
    vi.advanceTimersByTime(350);

    const [result1, result2] = await Promise.all([promise1, promise2]);

    // First promise was cancelled, should return isUnique=true
    expect(result1.isUnique).toBe(true);
    // Second promise completed normally
    expect(result2.isUnique).toBe(true);
    // Only one API call for the second check
    expect(mockFetchEntities).toHaveBeenCalledTimes(1);
  });
});

// =============================================================================
// Pre-built Validator Factory Tests
// =============================================================================

describe('Pre-built Validator Factories', () => {
  it('should create camera name validator', async () => {
    const validator = createCameraNameValidator(mockFetchEntities);
    const result = await validator.isUnique('Front Door');

    expect(result.isUnique).toBe(false);
    expect(result.message).toContain('Camera');
  });

  it('should create zone name validator', async () => {
    clearValidationCache();
    const validator = createZoneNameValidator(mockFetchEntities);
    const result = await validator.isUnique('Front Door');

    expect(result.isUnique).toBe(false);
    expect(result.message).toContain('Zone');
  });

  it('should create alert rule name validator', async () => {
    clearValidationCache();
    const validator = createAlertRuleNameValidator(mockFetchEntities);
    const result = await validator.isUnique('Front Door');

    expect(result.isUnique).toBe(false);
    expect(result.message).toContain('Alert rule');
  });
});

/**
 * Tests for Type Guards and Type Narrowing Utilities
 */

import { describe, it, expect } from 'vitest';

import {
  // Primitives
  isString,
  isNumber,
  isBoolean,
  isNull,
  isUndefined,
  isNullish,
  isDefined,
  // Objects
  isPlainObject,
  isArray,
  isArrayOf,
  isNonEmptyArray,
  // Properties
  hasProperty,
  hasPropertyOfType,
  hasProperties,
  hasOptionalPropertyOfType,
  // Compound
  oneOf,
  isStringOrNumber,
  // API
  isApiError,
  isPaginatedResponse,
  // Safe access
  getProperty,
  getTypedProperty,
  getRequiredProperty,
  // Object validation
  validateObject,
  createObjectGuard,
  // Special values
  isDate,
  isISODateString,
  isPositiveNumber,
  isNonNegativeNumber,
  isInteger,
  isPositiveInteger,
  isNonEmptyString,
  isUUID,
  // Literal unions
  literalUnion,
  numericLiteralUnion,
} from './guards';

// ============================================================================
// Primitive Type Guard Tests
// ============================================================================

describe('Primitive Type Guards', () => {
  describe('isString', () => {
    it('returns true for strings', () => {
      expect(isString('')).toBe(true);
      expect(isString('hello')).toBe(true);
      expect(isString(`template`)).toBe(true);
    });

    it('returns false for non-strings', () => {
      expect(isString(123)).toBe(false);
      expect(isString(null)).toBe(false);
      expect(isString(undefined)).toBe(false);
      expect(isString({})).toBe(false);
      expect(isString([])).toBe(false);
    });
  });

  describe('isNumber', () => {
    it('returns true for finite numbers', () => {
      expect(isNumber(0)).toBe(true);
      expect(isNumber(123)).toBe(true);
      expect(isNumber(-456)).toBe(true);
      expect(isNumber(3.14)).toBe(true);
    });

    it('returns false for NaN and Infinity', () => {
      expect(isNumber(NaN)).toBe(false);
      expect(isNumber(Infinity)).toBe(false);
      expect(isNumber(-Infinity)).toBe(false);
    });

    it('returns false for non-numbers', () => {
      expect(isNumber('123')).toBe(false);
      expect(isNumber(null)).toBe(false);
    });
  });

  describe('isBoolean', () => {
    it('returns true for booleans', () => {
      expect(isBoolean(true)).toBe(true);
      expect(isBoolean(false)).toBe(true);
    });

    it('returns false for non-booleans', () => {
      expect(isBoolean(0)).toBe(false);
      expect(isBoolean(1)).toBe(false);
      expect(isBoolean('true')).toBe(false);
    });
  });

  describe('isNull', () => {
    it('returns true for null', () => {
      expect(isNull(null)).toBe(true);
    });

    it('returns false for non-null', () => {
      expect(isNull(undefined)).toBe(false);
      expect(isNull(0)).toBe(false);
      expect(isNull('')).toBe(false);
    });
  });

  describe('isUndefined', () => {
    it('returns true for undefined', () => {
      expect(isUndefined(undefined)).toBe(true);
    });

    it('returns false for non-undefined', () => {
      expect(isUndefined(null)).toBe(false);
      expect(isUndefined(0)).toBe(false);
    });
  });

  describe('isNullish', () => {
    it('returns true for null and undefined', () => {
      expect(isNullish(null)).toBe(true);
      expect(isNullish(undefined)).toBe(true);
    });

    it('returns false for other falsy values', () => {
      expect(isNullish(0)).toBe(false);
      expect(isNullish('')).toBe(false);
      expect(isNullish(false)).toBe(false);
    });
  });

  describe('isDefined', () => {
    it('returns true for defined values', () => {
      expect(isDefined(0)).toBe(true);
      expect(isDefined('')).toBe(true);
      expect(isDefined(false)).toBe(true);
      expect(isDefined({})).toBe(true);
    });

    it('returns false for null and undefined', () => {
      expect(isDefined(null)).toBe(false);
      expect(isDefined(undefined)).toBe(false);
    });
  });
});

// ============================================================================
// Object Type Guard Tests
// ============================================================================

describe('Object Type Guards', () => {
  describe('isPlainObject', () => {
    it('returns true for plain objects', () => {
      expect(isPlainObject({})).toBe(true);
      expect(isPlainObject({ key: 'value' })).toBe(true);
      expect(isPlainObject(Object.create(null))).toBe(true);
    });

    it('returns false for arrays', () => {
      expect(isPlainObject([])).toBe(false);
      expect(isPlainObject([1, 2, 3])).toBe(false);
    });

    it('returns false for null', () => {
      expect(isPlainObject(null)).toBe(false);
    });

    it('returns false for class instances', () => {
      expect(isPlainObject(new Date())).toBe(false);
      expect(isPlainObject(new Map())).toBe(false);
      expect(isPlainObject(new Set())).toBe(false);
    });

    it('returns false for primitives', () => {
      expect(isPlainObject('string')).toBe(false);
      expect(isPlainObject(123)).toBe(false);
      expect(isPlainObject(true)).toBe(false);
    });
  });

  describe('isArray', () => {
    it('returns true for arrays', () => {
      expect(isArray([])).toBe(true);
      expect(isArray([1, 2, 3])).toBe(true);
      expect(isArray(['a', 'b'])).toBe(true);
    });

    it('returns false for non-arrays', () => {
      expect(isArray({})).toBe(false);
      expect(isArray('string')).toBe(false);
      expect(isArray(null)).toBe(false);
    });
  });

  describe('isArrayOf', () => {
    it('returns true for arrays of correct type', () => {
      expect(isArrayOf(['a', 'b', 'c'], isString)).toBe(true);
      expect(isArrayOf([1, 2, 3], isNumber)).toBe(true);
      expect(isArrayOf([], isString)).toBe(true); // empty array
    });

    it('returns false for arrays with wrong type', () => {
      expect(isArrayOf([1, 2, 'three'], isNumber)).toBe(false);
      expect(isArrayOf(['a', null, 'c'], isString)).toBe(false);
    });

    it('returns false for non-arrays', () => {
      expect(isArrayOf('not an array', isString)).toBe(false);
    });
  });

  describe('isNonEmptyArray', () => {
    it('returns true for non-empty arrays', () => {
      expect(isNonEmptyArray([1])).toBe(true);
      expect(isNonEmptyArray([1, 2, 3])).toBe(true);
    });

    it('returns false for empty arrays', () => {
      expect(isNonEmptyArray([])).toBe(false);
    });
  });
});

// ============================================================================
// Property Type Guard Tests
// ============================================================================

describe('Property Type Guards', () => {
  describe('hasProperty', () => {
    it('returns true when property exists', () => {
      expect(hasProperty({ id: 1 }, 'id')).toBe(true);
      expect(hasProperty({ name: undefined }, 'name')).toBe(true);
    });

    it('returns false when property does not exist', () => {
      expect(hasProperty({}, 'id')).toBe(false);
      expect(hasProperty({ name: 'test' }, 'id')).toBe(false);
    });
  });

  describe('hasPropertyOfType', () => {
    it('returns true when property exists and matches type', () => {
      expect(hasPropertyOfType({ id: 1 }, 'id', isNumber)).toBe(true);
      expect(hasPropertyOfType({ name: 'test' }, 'name', isString)).toBe(true);
    });

    it('returns false when property has wrong type', () => {
      expect(hasPropertyOfType({ id: '1' }, 'id', isNumber)).toBe(false);
    });

    it('returns false when property does not exist', () => {
      expect(hasPropertyOfType({}, 'id', isNumber)).toBe(false);
    });
  });

  describe('hasProperties', () => {
    it('returns true when all properties exist', () => {
      expect(hasProperties({ id: 1, name: 'test', email: 'a@b.com' }, ['id', 'name', 'email'])).toBe(
        true
      );
    });

    it('returns false when any property is missing', () => {
      expect(hasProperties({ id: 1, name: 'test' }, ['id', 'name', 'email'])).toBe(false);
    });

    it('returns true for empty property list', () => {
      expect(hasProperties({}, [])).toBe(true);
    });
  });

  describe('hasOptionalPropertyOfType', () => {
    it('returns true when property exists with correct type', () => {
      expect(hasOptionalPropertyOfType({ name: 'test' }, 'name', isString)).toBe(true);
    });

    it('returns true when property is undefined', () => {
      expect(hasOptionalPropertyOfType({ name: undefined }, 'name', isString)).toBe(true);
    });

    it('returns true when property does not exist', () => {
      expect(hasOptionalPropertyOfType({}, 'name', isString)).toBe(true);
    });

    it('returns false when property has wrong type', () => {
      expect(hasOptionalPropertyOfType({ name: 123 }, 'name', isString)).toBe(false);
    });
  });
});

// ============================================================================
// Compound Type Guard Tests
// ============================================================================

describe('Compound Type Guards', () => {
  describe('oneOf', () => {
    it('creates a guard that matches any of the provided guards', () => {
      const isStringOrNumber = oneOf(isString, isNumber);
      expect(isStringOrNumber('test')).toBe(true);
      expect(isStringOrNumber(123)).toBe(true);
      expect(isStringOrNumber(null)).toBe(false);
    });
  });

  describe('isStringOrNumber', () => {
    it('returns true for strings and numbers', () => {
      expect(isStringOrNumber('test')).toBe(true);
      expect(isStringOrNumber(123)).toBe(true);
    });

    it('returns false for other types', () => {
      expect(isStringOrNumber(null)).toBe(false);
      expect(isStringOrNumber({})).toBe(false);
    });
  });
});

// ============================================================================
// API Response Guard Tests
// ============================================================================

describe('API Response Guards', () => {
  describe('isApiError', () => {
    it('returns true for valid API errors', () => {
      expect(isApiError({ detail: 'Not found' })).toBe(true);
      expect(isApiError({ detail: 'Error', status_code: 404 })).toBe(true);
    });

    it('returns false for invalid API errors', () => {
      expect(isApiError({})).toBe(false);
      expect(isApiError({ message: 'Error' })).toBe(false);
      expect(isApiError({ detail: 123 })).toBe(false);
    });
  });

  describe('isPaginatedResponse', () => {
    it('returns true for valid paginated responses', () => {
      const isPaginatedStrings = isPaginatedResponse(isString);
      expect(isPaginatedStrings({ items: ['a', 'b'], total: 2 })).toBe(true);
      expect(isPaginatedStrings({ items: [], total: 0 })).toBe(true);
    });

    it('returns false for invalid responses', () => {
      const isPaginatedStrings = isPaginatedResponse(isString);
      expect(isPaginatedStrings({ items: [1, 2], total: 2 })).toBe(false);
      expect(isPaginatedStrings({ items: ['a'], total: 'many' })).toBe(false);
      expect(isPaginatedStrings({ total: 5 })).toBe(false);
    });
  });
});

// ============================================================================
// Safe Access Tests
// ============================================================================

describe('Safe Property Access', () => {
  describe('getProperty', () => {
    it('returns property value when exists', () => {
      expect(getProperty({ id: 123 }, 'id')).toBe(123);
      expect(getProperty({ name: 'test' }, 'name')).toBe('test');
    });

    it('returns undefined for missing property', () => {
      expect(getProperty({}, 'id')).toBeUndefined();
    });

    it('returns undefined for non-objects', () => {
      expect(getProperty(null, 'id')).toBeUndefined();
      expect(getProperty('string', 'id')).toBeUndefined();
    });
  });

  describe('getTypedProperty', () => {
    it('returns typed value when property matches', () => {
      expect(getTypedProperty({ id: 123 }, 'id', isNumber)).toBe(123);
    });

    it('returns undefined when type does not match', () => {
      expect(getTypedProperty({ id: '123' }, 'id', isNumber)).toBeUndefined();
    });

    it('returns undefined for missing property', () => {
      expect(getTypedProperty({}, 'id', isNumber)).toBeUndefined();
    });
  });

  describe('getRequiredProperty', () => {
    it('returns typed value when property matches', () => {
      expect(getRequiredProperty({ id: 123 }, 'id', isNumber)).toBe(123);
    });

    it('throws when property is missing', () => {
      expect(() => getRequiredProperty({}, 'id', isNumber)).toThrow();
    });

    it('throws when type does not match', () => {
      expect(() => getRequiredProperty({ id: '123' }, 'id', isNumber)).toThrow();
    });

    it('uses custom error message when provided', () => {
      expect(() =>
        getRequiredProperty({}, 'id', isNumber, 'ID is required')
      ).toThrow('ID is required');
    });
  });
});

// ============================================================================
// Object Validation Tests
// ============================================================================

describe('Object Validation', () => {
  describe('validateObject', () => {
    // Schema validates: { id: number; name: string }
    const userSchema = {
      id: isNumber,
      name: isString,
    };

    it('returns true for valid objects', () => {
      expect(validateObject({ id: 1, name: 'John' }, userSchema)).toBe(true);
    });

    it('returns false for missing properties', () => {
      expect(validateObject({ id: 1 }, userSchema)).toBe(false);
    });

    it('returns false for wrong types', () => {
      expect(validateObject({ id: '1', name: 'John' }, userSchema)).toBe(false);
    });

    it('returns false for non-objects', () => {
      expect(validateObject(null, userSchema)).toBe(false);
      expect(validateObject([], userSchema)).toBe(false);
    });
  });

  describe('createObjectGuard', () => {
    it('creates a reusable type guard', () => {
      const isUser = createObjectGuard({
        id: isNumber,
        name: isString,
      });

      expect(isUser({ id: 1, name: 'John' })).toBe(true);
      expect(isUser({ id: '1', name: 'John' })).toBe(false);
      expect(isUser(null)).toBe(false);
    });
  });
});

// ============================================================================
// Special Value Guard Tests
// ============================================================================

describe('Special Value Guards', () => {
  describe('isDate', () => {
    it('returns true for valid Date objects', () => {
      expect(isDate(new Date())).toBe(true);
      expect(isDate(new Date('2024-01-15'))).toBe(true);
    });

    it('returns false for invalid Date objects', () => {
      expect(isDate(new Date('invalid'))).toBe(false);
    });

    it('returns false for non-Date values', () => {
      expect(isDate('2024-01-15')).toBe(false);
      expect(isDate(Date.now())).toBe(false);
    });
  });

  describe('isISODateString', () => {
    it('returns true for valid ISO date strings', () => {
      expect(isISODateString('2024-01-15')).toBe(true);
      expect(isISODateString('2024-01-15T10:30:00Z')).toBe(true);
      expect(isISODateString('2024-01-15T10:30:00.000Z')).toBe(true);
    });

    it('returns false for invalid date strings', () => {
      expect(isISODateString('invalid')).toBe(false);
      expect(isISODateString('01-15-2024')).toBe(false);
    });

    it('returns false for non-strings', () => {
      expect(isISODateString(new Date())).toBe(false);
      expect(isISODateString(123)).toBe(false);
    });
  });

  describe('isPositiveNumber', () => {
    it('returns true for positive numbers', () => {
      expect(isPositiveNumber(1)).toBe(true);
      expect(isPositiveNumber(0.5)).toBe(true);
      expect(isPositiveNumber(1000)).toBe(true);
    });

    it('returns false for zero and negative numbers', () => {
      expect(isPositiveNumber(0)).toBe(false);
      expect(isPositiveNumber(-1)).toBe(false);
    });
  });

  describe('isNonNegativeNumber', () => {
    it('returns true for zero and positive numbers', () => {
      expect(isNonNegativeNumber(0)).toBe(true);
      expect(isNonNegativeNumber(1)).toBe(true);
    });

    it('returns false for negative numbers', () => {
      expect(isNonNegativeNumber(-1)).toBe(false);
    });
  });

  describe('isInteger', () => {
    it('returns true for integers', () => {
      expect(isInteger(0)).toBe(true);
      expect(isInteger(1)).toBe(true);
      expect(isInteger(-5)).toBe(true);
    });

    it('returns false for non-integers', () => {
      expect(isInteger(1.5)).toBe(false);
      expect(isInteger(NaN)).toBe(false);
    });
  });

  describe('isPositiveInteger', () => {
    it('returns true for positive integers', () => {
      expect(isPositiveInteger(1)).toBe(true);
      expect(isPositiveInteger(100)).toBe(true);
    });

    it('returns false for zero and negative integers', () => {
      expect(isPositiveInteger(0)).toBe(false);
      expect(isPositiveInteger(-1)).toBe(false);
    });

    it('returns false for non-integers', () => {
      expect(isPositiveInteger(1.5)).toBe(false);
    });
  });

  describe('isNonEmptyString', () => {
    it('returns true for non-empty strings', () => {
      expect(isNonEmptyString('hello')).toBe(true);
      expect(isNonEmptyString(' ')).toBe(true);
    });

    it('returns false for empty strings', () => {
      expect(isNonEmptyString('')).toBe(false);
    });

    it('returns false for non-strings', () => {
      expect(isNonEmptyString(null)).toBe(false);
    });
  });

  describe('isUUID', () => {
    it('returns true for valid UUIDs', () => {
      expect(isUUID('a1b2c3d4-e5f6-7890-abcd-ef1234567890')).toBe(true);
      expect(isUUID('00000000-0000-0000-0000-000000000000')).toBe(true);
      expect(isUUID('FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF')).toBe(true);
    });

    it('returns false for invalid UUIDs', () => {
      expect(isUUID('not-a-uuid')).toBe(false);
      expect(isUUID('a1b2c3d4-e5f6-7890-abcd-ef123456789')).toBe(false); // too short
      expect(isUUID('12345678901234567890123456789012')).toBe(false); // no dashes, just digits
    });

    it('returns false for non-strings', () => {
      expect(isUUID(null)).toBe(false);
      expect(isUUID(123)).toBe(false);
    });
  });
});

// ============================================================================
// Literal Union Tests
// ============================================================================

describe('Literal Union Guards', () => {
  describe('literalUnion', () => {
    it('creates a guard for string literals', () => {
      const isRiskLevel = literalUnion('low', 'medium', 'high', 'critical');

      expect(isRiskLevel('low')).toBe(true);
      expect(isRiskLevel('medium')).toBe(true);
      expect(isRiskLevel('invalid')).toBe(false);
      expect(isRiskLevel(123)).toBe(false);
    });
  });

  describe('numericLiteralUnion', () => {
    it('creates a guard for number literals', () => {
      const isPriority = numericLiteralUnion(0, 1, 2, 3, 4);

      expect(isPriority(0)).toBe(true);
      expect(isPriority(2)).toBe(true);
      expect(isPriority(5)).toBe(false);
      expect(isPriority('1')).toBe(false);
    });
  });
});

// ============================================================================
// Type Inference Tests
// ============================================================================

describe('Type Inference', () => {
  it('narrows type after guard passes', () => {
    const data: unknown = { id: 123, name: 'John' };

    if (isPlainObject(data) && hasPropertyOfType(data, 'id', isNumber)) {
      // TypeScript knows data.id is number
      const id: number = data.id;
      expect(id).toBe(123);
    }
  });

  it('narrows array types', () => {
    const data: unknown = ['a', 'b', 'c'];

    if (isArrayOf(data, isString)) {
      // TypeScript knows data is string[]
      const first: string = data[0];
      expect(first).toBe('a');
    }
  });

  it('narrows with custom object guard', () => {
    const isUser = createObjectGuard({
      id: isNumber,
      name: isString,
    });

    const data: unknown = { id: 1, name: 'John' };

    if (isUser(data)) {
      // TypeScript knows data has id: number and name: string
      const combined = `${data.name} (${data.id})`;
      expect(combined).toBe('John (1)');
    }
  });
});

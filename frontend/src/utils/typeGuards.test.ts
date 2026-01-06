import { describe, expect, it } from 'vitest';

import {
  hasArrayProperty,
  hasBooleanProperty,
  hasNumberProperty,
  hasProperty,
  hasStringProperty,
  isNonNullObject,
  isOneOf,
} from './typeGuards';

describe('typeGuards', () => {
  describe('isNonNullObject', () => {
    it('returns true for plain objects', () => {
      expect(isNonNullObject({})).toBe(true);
      expect(isNonNullObject({ key: 'value' })).toBe(true);
    });

    it('returns true for objects created with Object.create', () => {
      expect(isNonNullObject(Object.create(null))).toBe(true);
      expect(isNonNullObject(Object.create({}))).toBe(true);
    });

    it('returns false for null', () => {
      expect(isNonNullObject(null)).toBe(false);
    });

    it('returns false for undefined', () => {
      expect(isNonNullObject(undefined)).toBe(false);
    });

    it('returns false for arrays', () => {
      expect(isNonNullObject([])).toBe(false);
      expect(isNonNullObject([1, 2, 3])).toBe(false);
    });

    it('returns false for primitive types', () => {
      expect(isNonNullObject('string')).toBe(false);
      expect(isNonNullObject(42)).toBe(false);
      expect(isNonNullObject(true)).toBe(false);
      expect(isNonNullObject(Symbol('test'))).toBe(false);
      expect(isNonNullObject(BigInt(123))).toBe(false);
    });

    it('returns false for functions', () => {
      expect(isNonNullObject(() => {})).toBe(false);
      expect(isNonNullObject(function test() {})).toBe(false);
    });

    it('returns true for class instances', () => {
      class TestClass {
        value = 1;
      }
      expect(isNonNullObject(new TestClass())).toBe(true);
    });

    it('returns true for Date objects', () => {
      expect(isNonNullObject(new Date())).toBe(true);
    });

    it('returns true for Map and Set objects', () => {
      expect(isNonNullObject(new Map())).toBe(true);
      expect(isNonNullObject(new Set())).toBe(true);
    });
  });

  describe('hasProperty', () => {
    it('returns true when property exists', () => {
      const obj = { name: 'test', value: 123 };
      expect(hasProperty(obj, 'name')).toBe(true);
      expect(hasProperty(obj, 'value')).toBe(true);
    });

    it('returns false when property does not exist', () => {
      const obj = { name: 'test' };
      expect(hasProperty(obj, 'missing')).toBe(false);
    });

    it('returns true for properties with undefined value', () => {
      const obj = { name: undefined };
      expect(hasProperty(obj, 'name')).toBe(true);
    });

    it('returns true for properties with null value', () => {
      const obj = { name: null };
      expect(hasProperty(obj, 'name')).toBe(true);
    });

    it('returns false for non-objects', () => {
      expect(hasProperty(null, 'prop')).toBe(false);
      expect(hasProperty(undefined, 'prop')).toBe(false);
      expect(hasProperty('string', 'length')).toBe(false);
      expect(hasProperty(42, 'toString')).toBe(false);
    });

    it('returns false for arrays', () => {
      expect(hasProperty([1, 2, 3], 'length')).toBe(false);
      expect(hasProperty([], '0')).toBe(false);
    });

    it('works with symbol keys', () => {
      const sym = Symbol('test');
      const obj = { [sym]: 'value' };
      expect(hasProperty(obj, sym)).toBe(true);
    });

    it('does not check prototype chain', () => {
      const obj = Object.create({ inherited: true });
      expect(hasProperty(obj, 'inherited')).toBe(false);
    });
  });

  describe('hasStringProperty', () => {
    it('returns true when property is a string', () => {
      const obj = { name: 'test', empty: '' };
      expect(hasStringProperty(obj, 'name')).toBe(true);
      expect(hasStringProperty(obj, 'empty')).toBe(true);
    });

    it('returns false when property is not a string', () => {
      const obj = { num: 42, bool: true, arr: [], obj: {} };
      expect(hasStringProperty(obj, 'num')).toBe(false);
      expect(hasStringProperty(obj, 'bool')).toBe(false);
      expect(hasStringProperty(obj, 'arr')).toBe(false);
      expect(hasStringProperty(obj, 'obj')).toBe(false);
    });

    it('returns false when property does not exist', () => {
      const obj = { name: 'test' };
      expect(hasStringProperty(obj, 'missing')).toBe(false);
    });

    it('returns false when property is null or undefined', () => {
      const obj = { nullProp: null, undefinedProp: undefined };
      expect(hasStringProperty(obj, 'nullProp')).toBe(false);
      expect(hasStringProperty(obj, 'undefinedProp')).toBe(false);
    });

    it('returns false for non-objects', () => {
      expect(hasStringProperty(null, 'prop')).toBe(false);
      expect(hasStringProperty(undefined, 'prop')).toBe(false);
    });

    it('narrows type correctly in TypeScript', () => {
      const obj: unknown = { name: 'test' };
      if (hasStringProperty(obj, 'name')) {
        // TypeScript should allow this without error
        const value: string = obj.name;
        expect(value).toBe('test');
      }
    });
  });

  describe('hasNumberProperty', () => {
    it('returns true when property is a number', () => {
      const obj = { value: 42, zero: 0, negative: -1, decimal: 3.14 };
      expect(hasNumberProperty(obj, 'value')).toBe(true);
      expect(hasNumberProperty(obj, 'zero')).toBe(true);
      expect(hasNumberProperty(obj, 'negative')).toBe(true);
      expect(hasNumberProperty(obj, 'decimal')).toBe(true);
    });

    it('returns false when property is NaN', () => {
      const obj = { nan: NaN };
      expect(hasNumberProperty(obj, 'nan')).toBe(false);
    });

    it('returns true when property is Infinity', () => {
      const obj = { inf: Infinity, negInf: -Infinity };
      expect(hasNumberProperty(obj, 'inf')).toBe(true);
      expect(hasNumberProperty(obj, 'negInf')).toBe(true);
    });

    it('returns false when property is not a number', () => {
      const obj = { str: '42', bool: true, arr: [1] };
      expect(hasNumberProperty(obj, 'str')).toBe(false);
      expect(hasNumberProperty(obj, 'bool')).toBe(false);
      expect(hasNumberProperty(obj, 'arr')).toBe(false);
    });

    it('returns false when property does not exist', () => {
      const obj = { value: 42 };
      expect(hasNumberProperty(obj, 'missing')).toBe(false);
    });

    it('returns false when property is null or undefined', () => {
      const obj = { nullProp: null, undefinedProp: undefined };
      expect(hasNumberProperty(obj, 'nullProp')).toBe(false);
      expect(hasNumberProperty(obj, 'undefinedProp')).toBe(false);
    });

    it('returns false for non-objects', () => {
      expect(hasNumberProperty(null, 'prop')).toBe(false);
      expect(hasNumberProperty(undefined, 'prop')).toBe(false);
    });

    it('narrows type correctly in TypeScript', () => {
      const obj: unknown = { count: 42 };
      if (hasNumberProperty(obj, 'count')) {
        // TypeScript should allow this without error
        const value: number = obj.count;
        expect(value).toBe(42);
      }
    });
  });

  describe('hasBooleanProperty', () => {
    it('returns true when property is a boolean', () => {
      const obj = { enabled: true, disabled: false };
      expect(hasBooleanProperty(obj, 'enabled')).toBe(true);
      expect(hasBooleanProperty(obj, 'disabled')).toBe(true);
    });

    it('returns false when property is not a boolean', () => {
      const obj = { num: 0, str: '', arr: [] };
      expect(hasBooleanProperty(obj, 'num')).toBe(false);
      expect(hasBooleanProperty(obj, 'str')).toBe(false);
      expect(hasBooleanProperty(obj, 'arr')).toBe(false);
    });

    it('returns false when property does not exist', () => {
      const obj = { enabled: true };
      expect(hasBooleanProperty(obj, 'missing')).toBe(false);
    });

    it('returns false when property is null or undefined', () => {
      const obj = { nullProp: null, undefinedProp: undefined };
      expect(hasBooleanProperty(obj, 'nullProp')).toBe(false);
      expect(hasBooleanProperty(obj, 'undefinedProp')).toBe(false);
    });

    it('returns false for non-objects', () => {
      expect(hasBooleanProperty(null, 'prop')).toBe(false);
      expect(hasBooleanProperty(undefined, 'prop')).toBe(false);
    });

    it('narrows type correctly in TypeScript', () => {
      const obj: unknown = { active: true };
      if (hasBooleanProperty(obj, 'active')) {
        // TypeScript should allow this without error
        const value: boolean = obj.active;
        expect(value).toBe(true);
      }
    });
  });

  describe('hasArrayProperty', () => {
    it('returns true when property is an array', () => {
      const obj = { items: [1, 2, 3], empty: [] };
      expect(hasArrayProperty(obj, 'items')).toBe(true);
      expect(hasArrayProperty(obj, 'empty')).toBe(true);
    });

    it('returns false when property is not an array', () => {
      const obj = { str: 'not array', num: 42, obj: {} };
      expect(hasArrayProperty(obj, 'str')).toBe(false);
      expect(hasArrayProperty(obj, 'num')).toBe(false);
      expect(hasArrayProperty(obj, 'obj')).toBe(false);
    });

    it('returns false when property does not exist', () => {
      const obj = { items: [1, 2, 3] };
      expect(hasArrayProperty(obj, 'missing')).toBe(false);
    });

    it('returns false when property is null or undefined', () => {
      const obj = { nullProp: null, undefinedProp: undefined };
      expect(hasArrayProperty(obj, 'nullProp')).toBe(false);
      expect(hasArrayProperty(obj, 'undefinedProp')).toBe(false);
    });

    it('returns false for non-objects', () => {
      expect(hasArrayProperty(null, 'prop')).toBe(false);
      expect(hasArrayProperty(undefined, 'prop')).toBe(false);
    });

    it('narrows type correctly in TypeScript', () => {
      const obj: unknown = { tags: ['a', 'b', 'c'] };
      if (hasArrayProperty(obj, 'tags')) {
        // TypeScript should allow this without error
        const value: unknown[] = obj.tags;
        expect(value.length).toBe(3);
      }
    });

    it('works with typed arrays', () => {
      const obj = { buffer: new Uint8Array([1, 2, 3]) };
      // TypedArrays are not regular arrays, so this should return false
      expect(hasArrayProperty(obj, 'buffer')).toBe(false);
    });
  });

  describe('isOneOf', () => {
    it('returns true when value is in allowed values', () => {
      expect(isOneOf('a', ['a', 'b', 'c'])).toBe(true);
      expect(isOneOf('b', ['a', 'b', 'c'])).toBe(true);
      expect(isOneOf(1, [1, 2, 3])).toBe(true);
    });

    it('returns false when value is not in allowed values', () => {
      expect(isOneOf('d', ['a', 'b', 'c'])).toBe(false);
      expect(isOneOf(4, [1, 2, 3])).toBe(false);
    });

    it('works with mixed type arrays', () => {
      const allowed = ['a', 1, true] as const;
      expect(isOneOf('a', allowed)).toBe(true);
      expect(isOneOf(1, allowed)).toBe(true);
      expect(isOneOf(true, allowed)).toBe(true);
      expect(isOneOf('b', allowed)).toBe(false);
    });

    it('handles empty array', () => {
      expect(isOneOf('any', [])).toBe(false);
    });

    it('handles null and undefined', () => {
      expect(isOneOf(null, [null, undefined])).toBe(true);
      expect(isOneOf(undefined, [null, undefined])).toBe(true);
      expect(isOneOf(null, ['a', 'b'])).toBe(false);
    });

    it('uses strict equality', () => {
      expect(isOneOf('1', [1, 2, 3])).toBe(false);
      expect(isOneOf(0, [false, null, undefined])).toBe(false);
    });

    it('narrows type correctly in TypeScript', () => {
      const status: string = 'active';
      const validStatuses = ['active', 'inactive', 'pending'] as const;
      if (isOneOf(status, validStatuses)) {
        // TypeScript should narrow type to 'active' | 'inactive' | 'pending'
        const narrowed: (typeof validStatuses)[number] = status;
        expect(narrowed).toBe('active');
      }
    });

    it('works with object values using reference equality', () => {
      const obj1 = { id: 1 };
      const obj2 = { id: 2 };
      const allowed = [obj1, obj2];
      expect(isOneOf(obj1, allowed)).toBe(true);
      expect(isOneOf({ id: 1 }, allowed)).toBe(false); // Different reference
    });
  });
});

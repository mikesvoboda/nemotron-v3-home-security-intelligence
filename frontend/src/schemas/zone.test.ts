/**
 * Tests for Zone Zod validation schemas.
 *
 * @see NEM-3821 Migrate ZoneForm to useForm with Zod
 */

import { describe, expect, it } from 'vitest';

import {
  zoneFormSchema,
  zoneNameSchema,
  zonePrioritySchema,
  zoneColorSchema,
  zoneTypeSchema,
  zoneShapeSchema,
  ZONE_NAME_CONSTRAINTS,
  ZONE_TYPE_VALUES,
  ZONE_SHAPE_VALUES,
} from './zone';

describe('Zone Schema Validation', () => {
  describe('zoneNameSchema', () => {
    it('should accept valid zone names', () => {
      const result = zoneNameSchema.safeParse('Front Door');
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toBe('Front Door');
      }
    });

    it('should accept single character name (aligned with backend min_length=1)', () => {
      const result = zoneNameSchema.safeParse('A');
      expect(result.success).toBe(true);
    });

    it('should reject empty name', () => {
      const result = zoneNameSchema.safeParse('');
      expect(result.success).toBe(false);
    });

    it('should reject whitespace-only name', () => {
      const result = zoneNameSchema.safeParse('   ');
      expect(result.success).toBe(false);
    });

    it('should trim whitespace from valid name', () => {
      const result = zoneNameSchema.safeParse('  Front Door  ');
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toBe('Front Door');
      }
    });

    it('should accept maximum length name (255 chars)', () => {
      const maxLengthName = 'A'.repeat(ZONE_NAME_CONSTRAINTS.maxLength);
      const result = zoneNameSchema.safeParse(maxLengthName);
      expect(result.success).toBe(true);
    });

    it('should reject name exceeding maximum length', () => {
      const tooLongName = 'A'.repeat(ZONE_NAME_CONSTRAINTS.maxLength + 1);
      const result = zoneNameSchema.safeParse(tooLongName);
      expect(result.success).toBe(false);
    });
  });

  describe('zonePrioritySchema', () => {
    it('should accept valid priority (0)', () => {
      const result = zonePrioritySchema.safeParse(0);
      expect(result.success).toBe(true);
    });

    it('should accept valid priority (100)', () => {
      const result = zonePrioritySchema.safeParse(100);
      expect(result.success).toBe(true);
    });

    it('should accept mid-range priority', () => {
      const result = zonePrioritySchema.safeParse(50);
      expect(result.success).toBe(true);
    });

    it('should reject negative priority', () => {
      const result = zonePrioritySchema.safeParse(-1);
      expect(result.success).toBe(false);
    });

    it('should reject priority above 100', () => {
      const result = zonePrioritySchema.safeParse(101);
      expect(result.success).toBe(false);
    });

    it('should reject non-integer priority', () => {
      const result = zonePrioritySchema.safeParse(50.5);
      expect(result.success).toBe(false);
    });
  });

  describe('zoneColorSchema', () => {
    it('should accept valid hex color', () => {
      const result = zoneColorSchema.safeParse('#3B82F6');
      expect(result.success).toBe(true);
    });

    it('should accept lowercase hex color', () => {
      const result = zoneColorSchema.safeParse('#3b82f6');
      expect(result.success).toBe(true);
    });

    it('should reject invalid hex color (missing #)', () => {
      const result = zoneColorSchema.safeParse('3B82F6');
      expect(result.success).toBe(false);
    });

    it('should reject short hex color', () => {
      const result = zoneColorSchema.safeParse('#FFF');
      expect(result.success).toBe(false);
    });

    it('should reject invalid hex characters', () => {
      const result = zoneColorSchema.safeParse('#GGGGGG');
      expect(result.success).toBe(false);
    });

    it('should reject rgb format', () => {
      const result = zoneColorSchema.safeParse('rgb(59, 130, 246)');
      expect(result.success).toBe(false);
    });
  });

  describe('zoneTypeSchema', () => {
    it.each(ZONE_TYPE_VALUES)('should accept valid zone type: %s', (type) => {
      const result = zoneTypeSchema.safeParse(type);
      expect(result.success).toBe(true);
    });

    it('should reject invalid zone type', () => {
      const result = zoneTypeSchema.safeParse('invalid_type');
      expect(result.success).toBe(false);
    });
  });

  describe('zoneShapeSchema', () => {
    it.each(ZONE_SHAPE_VALUES)('should accept valid zone shape: %s', (shape) => {
      const result = zoneShapeSchema.safeParse(shape);
      expect(result.success).toBe(true);
    });

    it('should reject invalid zone shape', () => {
      const result = zoneShapeSchema.safeParse('circle');
      expect(result.success).toBe(false);
    });
  });

  describe('zoneFormSchema', () => {
    it('should accept valid complete form data', () => {
      const data = {
        name: 'Front Door',
        zone_type: 'entry_point',
        shape: 'rectangle',
        color: '#3B82F6',
        enabled: true,
        priority: 50,
      };
      const result = zoneFormSchema.safeParse(data);
      expect(result.success).toBe(true);
    });

    it('should apply default values for missing optional fields', () => {
      const data = {
        name: 'Test Zone',
      };
      const result = zoneFormSchema.safeParse(data);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.zone_type).toBe('other');
        expect(result.data.shape).toBe('rectangle');
        expect(result.data.color).toBe('#3B82F6');
        expect(result.data.enabled).toBe(true);
        expect(result.data.priority).toBe(0);
      }
    });

    it('should reject form with invalid name', () => {
      const data = {
        name: '',
        zone_type: 'entry_point',
        shape: 'rectangle',
        color: '#3B82F6',
        enabled: true,
        priority: 50,
      };
      const result = zoneFormSchema.safeParse(data);
      expect(result.success).toBe(false);
    });

    it('should reject form with invalid priority', () => {
      const data = {
        name: 'Test Zone',
        zone_type: 'entry_point',
        shape: 'rectangle',
        color: '#3B82F6',
        enabled: true,
        priority: 150, // Invalid: exceeds 100
      };
      const result = zoneFormSchema.safeParse(data);
      expect(result.success).toBe(false);
    });

    it('should reject form with invalid color', () => {
      const data = {
        name: 'Test Zone',
        zone_type: 'entry_point',
        shape: 'rectangle',
        color: 'invalid', // Invalid color
        enabled: true,
        priority: 50,
      };
      const result = zoneFormSchema.safeParse(data);
      expect(result.success).toBe(false);
    });
  });
});

/**
 * Tests for Alert Form Zod validation schemas.
 *
 * @see NEM-3820 Migrate AlertForm to useForm with Zod
 */

import { describe, expect, it } from 'vitest';

import {
  alertFormSchema,
  alertFormNameSchema,
  alertFormSeveritySchema,
  alertFormDayOfWeekSchema,
  alertFormRiskThresholdSchema,
  alertFormMinConfidenceSchema,
  alertFormCooldownSecondsSchema,
  ALERT_FORM_NAME_CONSTRAINTS,
  ALERT_FORM_SEVERITY_VALUES,
  ALERT_FORM_VALID_DAYS,
} from './alert';

describe('Alert Form Schema Validation', () => {
  describe('alertFormNameSchema', () => {
    it('should accept valid alert name', () => {
      const result = alertFormNameSchema.safeParse('Night Intruder Alert');
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toBe('Night Intruder Alert');
      }
    });

    it('should accept single character name (aligned with backend min_length=1)', () => {
      const result = alertFormNameSchema.safeParse('A');
      expect(result.success).toBe(true);
    });

    it('should reject empty name', () => {
      const result = alertFormNameSchema.safeParse('');
      expect(result.success).toBe(false);
    });

    it('should reject whitespace-only name', () => {
      const result = alertFormNameSchema.safeParse('   ');
      expect(result.success).toBe(false);
    });

    it('should trim whitespace from valid name', () => {
      const result = alertFormNameSchema.safeParse('  Alert Name  ');
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toBe('Alert Name');
      }
    });

    it('should accept maximum length name (255 chars)', () => {
      const maxLengthName = 'A'.repeat(ALERT_FORM_NAME_CONSTRAINTS.maxLength);
      const result = alertFormNameSchema.safeParse(maxLengthName);
      expect(result.success).toBe(true);
    });

    it('should reject name exceeding maximum length', () => {
      const tooLongName = 'A'.repeat(ALERT_FORM_NAME_CONSTRAINTS.maxLength + 1);
      const result = alertFormNameSchema.safeParse(tooLongName);
      expect(result.success).toBe(false);
    });
  });

  describe('alertFormSeveritySchema', () => {
    it.each(ALERT_FORM_SEVERITY_VALUES)('should accept valid severity: %s', (severity) => {
      const result = alertFormSeveritySchema.safeParse(severity);
      expect(result.success).toBe(true);
    });

    it('should reject invalid severity', () => {
      const result = alertFormSeveritySchema.safeParse('urgent');
      expect(result.success).toBe(false);
    });
  });

  describe('alertFormDayOfWeekSchema', () => {
    it.each(ALERT_FORM_VALID_DAYS)('should accept valid day: %s', (day) => {
      const result = alertFormDayOfWeekSchema.safeParse(day);
      expect(result.success).toBe(true);
    });

    it('should reject invalid day', () => {
      const result = alertFormDayOfWeekSchema.safeParse('funday');
      expect(result.success).toBe(false);
    });
  });

  describe('alertFormRiskThresholdSchema', () => {
    it('should accept valid risk threshold (0)', () => {
      const result = alertFormRiskThresholdSchema.safeParse(0);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toBe(0);
      }
    });

    it('should accept valid risk threshold (100)', () => {
      const result = alertFormRiskThresholdSchema.safeParse(100);
      expect(result.success).toBe(true);
    });

    it('should accept null risk threshold', () => {
      const result = alertFormRiskThresholdSchema.safeParse(null);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toBe(null);
      }
    });

    it('should transform empty string to null', () => {
      const result = alertFormRiskThresholdSchema.safeParse('');
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toBe(null);
      }
    });

    it('should reject negative risk threshold', () => {
      const result = alertFormRiskThresholdSchema.safeParse(-1);
      expect(result.success).toBe(false);
    });

    it('should reject risk threshold above 100', () => {
      const result = alertFormRiskThresholdSchema.safeParse(101);
      expect(result.success).toBe(false);
    });

    it('should reject non-integer risk threshold', () => {
      const result = alertFormRiskThresholdSchema.safeParse(50.5);
      expect(result.success).toBe(false);
    });
  });

  describe('alertFormMinConfidenceSchema', () => {
    it('should accept valid min confidence (0)', () => {
      const result = alertFormMinConfidenceSchema.safeParse(0);
      expect(result.success).toBe(true);
    });

    it('should accept valid min confidence (1)', () => {
      const result = alertFormMinConfidenceSchema.safeParse(1);
      expect(result.success).toBe(true);
    });

    it('should accept decimal min confidence', () => {
      const result = alertFormMinConfidenceSchema.safeParse(0.8);
      expect(result.success).toBe(true);
    });

    it('should accept null min confidence', () => {
      const result = alertFormMinConfidenceSchema.safeParse(null);
      expect(result.success).toBe(true);
    });

    it('should transform empty string to null', () => {
      const result = alertFormMinConfidenceSchema.safeParse('');
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toBe(null);
      }
    });

    it('should reject negative min confidence', () => {
      const result = alertFormMinConfidenceSchema.safeParse(-0.1);
      expect(result.success).toBe(false);
    });

    it('should reject min confidence above 1', () => {
      const result = alertFormMinConfidenceSchema.safeParse(1.1);
      expect(result.success).toBe(false);
    });
  });

  describe('alertFormCooldownSecondsSchema', () => {
    it('should accept valid cooldown (0)', () => {
      const result = alertFormCooldownSecondsSchema.safeParse(0);
      expect(result.success).toBe(true);
    });

    it('should accept positive cooldown', () => {
      const result = alertFormCooldownSecondsSchema.safeParse(300);
      expect(result.success).toBe(true);
    });

    it('should reject negative cooldown', () => {
      const result = alertFormCooldownSecondsSchema.safeParse(-1);
      expect(result.success).toBe(false);
    });

    it('should reject non-integer cooldown', () => {
      const result = alertFormCooldownSecondsSchema.safeParse(300.5);
      expect(result.success).toBe(false);
    });
  });

  describe('alertFormSchema', () => {
    it('should accept valid complete form data', () => {
      const data = {
        name: 'Night Alert',
        description: 'Alert for night time',
        enabled: true,
        severity: 'high',
        risk_threshold: 70,
        object_types: ['person'],
        camera_ids: ['cam1'],
        min_confidence: 0.8,
        schedule_enabled: true,
        schedule_days: ['monday', 'tuesday'],
        schedule_start_time: '22:00',
        schedule_end_time: '06:00',
        schedule_timezone: 'UTC',
        cooldown_seconds: 300,
        channels: ['email'],
      };
      const result = alertFormSchema.safeParse(data);
      expect(result.success).toBe(true);
    });

    it('should apply default values for missing optional fields', () => {
      const data = {
        name: 'Test Alert',
      };
      const result = alertFormSchema.safeParse(data);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.enabled).toBe(true);
        expect(result.data.severity).toBe('medium');
        expect(result.data.object_types).toEqual([]);
        expect(result.data.camera_ids).toEqual([]);
        expect(result.data.schedule_enabled).toBe(false);
        expect(result.data.schedule_days).toEqual([]);
        expect(result.data.cooldown_seconds).toBe(300);
        expect(result.data.channels).toEqual([]);
      }
    });

    it('should trim description whitespace', () => {
      const data = {
        name: 'Test Alert',
        description: '  Alert description  ',
      };
      const result = alertFormSchema.safeParse(data);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.description).toBe('Alert description');
      }
    });

    it('should reject form with invalid name', () => {
      const data = {
        name: '',
        enabled: true,
        severity: 'high',
      };
      const result = alertFormSchema.safeParse(data);
      expect(result.success).toBe(false);
    });

    it('should reject form with invalid severity', () => {
      const data = {
        name: 'Test Alert',
        severity: 'urgent', // Invalid
      };
      const result = alertFormSchema.safeParse(data);
      expect(result.success).toBe(false);
    });

    it('should reject form with invalid risk threshold', () => {
      const data = {
        name: 'Test Alert',
        risk_threshold: 150, // Invalid: exceeds 100
      };
      const result = alertFormSchema.safeParse(data);
      expect(result.success).toBe(false);
    });

    it('should reject form with invalid cooldown', () => {
      const data = {
        name: 'Test Alert',
        cooldown_seconds: -100, // Invalid: negative
      };
      const result = alertFormSchema.safeParse(data);
      expect(result.success).toBe(false);
    });

    it('should reject form with invalid schedule day', () => {
      const data = {
        name: 'Test Alert',
        schedule_enabled: true,
        schedule_days: ['funday'], // Invalid day
      };
      const result = alertFormSchema.safeParse(data);
      expect(result.success).toBe(false);
    });
  });
});

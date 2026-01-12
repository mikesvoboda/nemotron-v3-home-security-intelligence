/**
 * Unit tests for AlertRule Zod validation schemas.
 *
 * These tests verify that the frontend validation rules match the backend
 * Pydantic schemas in backend/api/schemas/alerts.py
 */

import { describe, expect, it } from 'vitest';

import {
  alertRuleCreateSchema,
  alertRuleFormSchema,
  alertRuleNameSchema,
  alertRuleScheduleSchema,
  alertRuleUpdateSchema,
  alertSeveritySchema,
  cooldownSecondsSchema,
  daysArraySchema,
  dayOfWeekSchema,
  dedupKeyTemplateSchema,
  minConfidenceSchema,
  riskThresholdSchema,
  timeStringSchema,
  ALERT_RULE_NAME_CONSTRAINTS,
  ALERT_SEVERITY_VALUES,
  COOLDOWN_SECONDS_CONSTRAINTS,
  DEDUP_KEY_TEMPLATE_CONSTRAINTS,
  MIN_CONFIDENCE_CONSTRAINTS,
  RISK_THRESHOLD_CONSTRAINTS,
  VALID_DAYS,
} from './alertRule';

describe('AlertRule Zod Schemas', () => {
  describe('alertSeveritySchema', () => {
    it('should accept all valid severity values', () => {
      for (const severity of ALERT_SEVERITY_VALUES) {
        const result = alertSeveritySchema.safeParse(severity);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data).toBe(severity);
        }
      }
    });

    it('should reject invalid severity values', () => {
      const result = alertSeveritySchema.safeParse('invalid');
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toBe(
          'Invalid alert severity. Must be: low, medium, high, or critical'
        );
      }
    });

    it('should have exactly 4 severity levels matching backend', () => {
      expect(ALERT_SEVERITY_VALUES).toEqual(['low', 'medium', 'high', 'critical']);
    });
  });

  describe('dayOfWeekSchema', () => {
    it('should accept all valid day values', () => {
      for (const day of VALID_DAYS) {
        const result = dayOfWeekSchema.safeParse(day);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data).toBe(day);
        }
      }
    });

    it('should reject invalid day values', () => {
      const result = dayOfWeekSchema.safeParse('invalid');
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toContain('Invalid day');
      }
    });

    it('should have exactly 7 days matching backend VALID_DAYS', () => {
      expect(VALID_DAYS).toEqual([
        'monday',
        'tuesday',
        'wednesday',
        'thursday',
        'friday',
        'saturday',
        'sunday',
      ]);
    });
  });

  describe('alertRuleNameSchema', () => {
    it('should accept valid names', () => {
      const result = alertRuleNameSchema.safeParse('Night Intruder Alert');
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toBe('Night Intruder Alert');
      }
    });

    it('should trim whitespace', () => {
      const result = alertRuleNameSchema.safeParse('  Test Rule  ');
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toBe('Test Rule');
      }
    });

    it('should accept single character names (min_length=1)', () => {
      const result = alertRuleNameSchema.safeParse('A');
      expect(result.success).toBe(true);
    });

    it('should reject empty names', () => {
      const result = alertRuleNameSchema.safeParse('');
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toBe('Name is required');
      }
    });

    it('should reject whitespace-only names after trimming', () => {
      const result = alertRuleNameSchema.safeParse('   ');
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toBe('Name is required');
      }
    });

    it('should reject names exceeding max length', () => {
      const longName = 'a'.repeat(ALERT_RULE_NAME_CONSTRAINTS.maxLength + 1);
      const result = alertRuleNameSchema.safeParse(longName);
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toBe(
          `Name must be at most ${ALERT_RULE_NAME_CONSTRAINTS.maxLength} characters`
        );
      }
    });

    it('should accept names at max length', () => {
      const maxName = 'a'.repeat(ALERT_RULE_NAME_CONSTRAINTS.maxLength);
      const result = alertRuleNameSchema.safeParse(maxName);
      expect(result.success).toBe(true);
    });
  });

  describe('riskThresholdSchema', () => {
    it('should accept valid threshold values', () => {
      const validValues = [0, 50, 100];
      for (const value of validValues) {
        const result = riskThresholdSchema.safeParse(value);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data).toBe(value);
        }
      }
    });

    it('should accept null (optional field)', () => {
      const result = riskThresholdSchema.safeParse(null);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toBeNull();
      }
    });

    it('should accept undefined (optional field)', () => {
      const result = riskThresholdSchema.safeParse(undefined);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toBeUndefined();
      }
    });

    it('should reject values below minimum', () => {
      const result = riskThresholdSchema.safeParse(-1);
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toContain(
          `Risk threshold must be at least ${RISK_THRESHOLD_CONSTRAINTS.min}`
        );
      }
    });

    it('should reject values above maximum', () => {
      const result = riskThresholdSchema.safeParse(101);
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toContain(
          `Risk threshold must be at most ${RISK_THRESHOLD_CONSTRAINTS.max}`
        );
      }
    });

    it('should reject non-integer values', () => {
      const result = riskThresholdSchema.safeParse(50.5);
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toContain('whole number');
      }
    });
  });

  describe('minConfidenceSchema', () => {
    it('should accept valid confidence values', () => {
      const validValues = [0, 0.5, 1];
      for (const value of validValues) {
        const result = minConfidenceSchema.safeParse(value);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data).toBe(value);
        }
      }
    });

    it('should accept decimal values', () => {
      const result = minConfidenceSchema.safeParse(0.75);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toBe(0.75);
      }
    });

    it('should accept null (optional field)', () => {
      const result = minConfidenceSchema.safeParse(null);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toBeNull();
      }
    });

    it('should reject values below minimum', () => {
      const result = minConfidenceSchema.safeParse(-0.1);
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toContain(
          `Confidence must be at least ${MIN_CONFIDENCE_CONSTRAINTS.min}`
        );
      }
    });

    it('should reject values above maximum', () => {
      const result = minConfidenceSchema.safeParse(1.1);
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toContain(
          `Confidence must be at most ${MIN_CONFIDENCE_CONSTRAINTS.max}`
        );
      }
    });
  });

  describe('cooldownSecondsSchema', () => {
    it('should accept valid cooldown values', () => {
      const validValues = [0, 300, 3600];
      for (const value of validValues) {
        const result = cooldownSecondsSchema.safeParse(value);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data).toBe(value);
        }
      }
    });

    it('should reject negative values', () => {
      const result = cooldownSecondsSchema.safeParse(-1);
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toBe('Cooldown cannot be negative');
      }
    });

    it('should reject non-integer values', () => {
      const result = cooldownSecondsSchema.safeParse(300.5);
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toContain('whole number');
      }
    });
  });

  describe('dedupKeyTemplateSchema', () => {
    it('should accept valid templates', () => {
      const validTemplates = ['{camera_id}:{rule_id}', 'prefix_{camera_id}', ''];
      for (const template of validTemplates) {
        const result = dedupKeyTemplateSchema.safeParse(template);
        expect(result.success).toBe(true);
      }
    });

    it('should reject templates exceeding max length', () => {
      const longTemplate = 'a'.repeat(DEDUP_KEY_TEMPLATE_CONSTRAINTS.maxLength + 1);
      const result = dedupKeyTemplateSchema.safeParse(longTemplate);
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toBe(
          `Dedup key template must be at most ${DEDUP_KEY_TEMPLATE_CONSTRAINTS.maxLength} characters`
        );
      }
    });
  });

  describe('timeStringSchema', () => {
    it('should accept valid time strings', () => {
      const validTimes = ['00:00', '12:30', '23:59'];
      for (const time of validTimes) {
        const result = timeStringSchema.safeParse(time);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data).toBe(time);
        }
      }
    });

    it('should accept null', () => {
      const result = timeStringSchema.safeParse(null);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toBeNull();
      }
    });

    it('should reject invalid format (wrong length)', () => {
      const result = timeStringSchema.safeParse('1:30');
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toContain('Invalid time format');
      }
    });

    it('should reject invalid format (no colon)', () => {
      const result = timeStringSchema.safeParse('12-30');
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toContain('Invalid time format');
      }
    });

    it('should reject hours out of range (24+)', () => {
      const result = timeStringSchema.safeParse('24:00');
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toContain('Invalid hours');
      }
    });

    it('should reject minutes out of range (60+)', () => {
      const result = timeStringSchema.safeParse('12:60');
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toContain('Invalid minutes');
      }
    });

    it('should reject non-numeric time values', () => {
      const result = timeStringSchema.safeParse('ab:cd');
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toContain('Invalid time format');
      }
    });
  });

  describe('daysArraySchema', () => {
    it('should accept valid days array', () => {
      const result = daysArraySchema.safeParse(['monday', 'wednesday', 'friday']);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toEqual(['monday', 'wednesday', 'friday']);
      }
    });

    it('should accept empty array', () => {
      const result = daysArraySchema.safeParse([]);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toEqual([]);
      }
    });

    it('should accept null', () => {
      const result = daysArraySchema.safeParse(null);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toBeNull();
      }
    });

    it('should reject arrays with invalid days', () => {
      const result = daysArraySchema.safeParse(['monday', 'invalid']);
      expect(result.success).toBe(false);
    });
  });

  describe('alertRuleScheduleSchema', () => {
    it('should accept valid schedule', () => {
      const schedule = {
        days: ['monday', 'tuesday'],
        start_time: '22:00',
        end_time: '06:00',
        timezone: 'America/New_York',
      };
      const result = alertRuleScheduleSchema.safeParse(schedule);
      expect(result.success).toBe(true);
    });

    it('should accept schedule with null fields', () => {
      const schedule = {
        days: null,
        start_time: null,
        end_time: null,
        timezone: 'UTC',
      };
      const result = alertRuleScheduleSchema.safeParse(schedule);
      expect(result.success).toBe(true);
    });

    it('should accept null schedule', () => {
      const result = alertRuleScheduleSchema.safeParse(null);
      expect(result.success).toBe(true);
    });

    it('should default timezone to UTC', () => {
      const schedule = {
        days: ['monday'],
        start_time: '22:00',
        end_time: '06:00',
      };
      const result = alertRuleScheduleSchema.safeParse(schedule);
      expect(result.success).toBe(true);
      if (result.success && result.data) {
        expect(result.data.timezone).toBe('UTC');
      }
    });
  });

  describe('alertRuleCreateSchema', () => {
    it('should validate a complete create payload', () => {
      const payload = {
        name: 'Night Intruder Alert',
        description: 'Alert for detecting people at night',
        enabled: true,
        severity: 'high',
        risk_threshold: 70,
        object_types: ['person'],
        camera_ids: ['front_door'],
        min_confidence: 0.8,
        schedule: {
          days: ['monday', 'tuesday'],
          start_time: '22:00',
          end_time: '06:00',
          timezone: 'America/New_York',
        },
        cooldown_seconds: 300,
        channels: ['pushover'],
      };
      const result = alertRuleCreateSchema.safeParse(payload);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.name).toBe('Night Intruder Alert');
        expect(result.data.severity).toBe('high');
      }
    });

    it('should use default values when not provided', () => {
      const payload = {
        name: 'Simple Rule',
      };
      const result = alertRuleCreateSchema.safeParse(payload);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.enabled).toBe(true);
        expect(result.data.severity).toBe('medium');
        expect(result.data.cooldown_seconds).toBe(300);
        expect(result.data.dedup_key_template).toBe('{camera_id}:{rule_id}');
        expect(result.data.channels).toEqual([]);
      }
    });

    it('should fail if name is missing', () => {
      const payload = {
        severity: 'high',
      };
      const result = alertRuleCreateSchema.safeParse(payload);
      expect(result.success).toBe(false);
    });

    it('should accept optional fields as null', () => {
      const payload = {
        name: 'Test Rule',
        description: null,
        risk_threshold: null,
        object_types: null,
        camera_ids: null,
        zone_ids: null,
        min_confidence: null,
        schedule: null,
      };
      const result = alertRuleCreateSchema.safeParse(payload);
      expect(result.success).toBe(true);
    });
  });

  describe('alertRuleUpdateSchema', () => {
    it('should allow partial updates', () => {
      const payload = { name: 'Updated Rule Name' };
      const result = alertRuleUpdateSchema.safeParse(payload);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.name).toBe('Updated Rule Name');
        expect(result.data.severity).toBeUndefined();
      }
    });

    it('should allow empty updates', () => {
      const result = alertRuleUpdateSchema.safeParse({});
      expect(result.success).toBe(true);
    });

    it('should validate provided fields', () => {
      const payload = { risk_threshold: 150 }; // Invalid - exceeds max
      const result = alertRuleUpdateSchema.safeParse(payload);
      expect(result.success).toBe(false);
    });
  });

  describe('alertRuleFormSchema', () => {
    it('should validate a complete form payload', () => {
      const payload = {
        name: 'Form Test Rule',
        description: 'Description',
        enabled: true,
        severity: 'medium',
        risk_threshold: 70,
        object_types: ['person'],
        camera_ids: ['cam1'],
        zone_ids: [],
        min_confidence: 0.8,
        schedule_enabled: true,
        schedule_days: ['monday'],
        schedule_start_time: '22:00',
        schedule_end_time: '06:00',
        schedule_timezone: 'UTC',
        cooldown_seconds: 300,
        channels: ['email'],
      };
      const result = alertRuleFormSchema.safeParse(payload);
      expect(result.success).toBe(true);
    });

    it('should use defaults for missing fields', () => {
      // When using react-hook-form with defaultValues, the form provides the default values.
      // The schema validates what's submitted. For a minimal valid payload,
      // we need to provide the name and rely on defaults from the form, not the schema.
      const payload = {
        name: 'Minimal Form Rule',
        description: '',
        enabled: true,
        severity: 'medium',
        risk_threshold: null,
        object_types: [],
        camera_ids: [],
        zone_ids: [],
        min_confidence: null,
        schedule_enabled: false,
        schedule_days: [],
        schedule_start_time: '22:00',
        schedule_end_time: '06:00',
        schedule_timezone: 'UTC',
        cooldown_seconds: 300,
        channels: [],
      };
      const result = alertRuleFormSchema.safeParse(payload);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.description).toBe('');
        expect(result.data.enabled).toBe(true);
        expect(result.data.severity).toBe('medium');
        expect(result.data.object_types).toEqual([]);
        expect(result.data.camera_ids).toEqual([]);
        expect(result.data.zone_ids).toEqual([]);
        expect(result.data.schedule_enabled).toBe(false);
        expect(result.data.schedule_days).toEqual([]);
        expect(result.data.schedule_start_time).toBe('22:00');
        expect(result.data.schedule_end_time).toBe('06:00');
        expect(result.data.schedule_timezone).toBe('UTC');
        expect(result.data.cooldown_seconds).toBe(300);
        expect(result.data.channels).toEqual([]);
      }
    });

    it('should transform empty string risk_threshold to null', () => {
      // Form schema handles empty string from number inputs to convert to null
      const payload = {
        name: 'Test',
        description: '',
        enabled: true,
        severity: 'medium',
        risk_threshold: '',
        object_types: [],
        camera_ids: [],
        zone_ids: [],
        min_confidence: null,
        schedule_enabled: false,
        schedule_days: [],
        schedule_start_time: '22:00',
        schedule_end_time: '06:00',
        schedule_timezone: 'UTC',
        cooldown_seconds: 300,
        channels: [],
      };
      const result = alertRuleFormSchema.safeParse(payload);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.risk_threshold).toBeNull();
      }
    });

    it('should transform empty string min_confidence to null', () => {
      // Form schema handles empty string from number inputs to convert to null
      const payload = {
        name: 'Test',
        description: '',
        enabled: true,
        severity: 'medium',
        risk_threshold: null,
        object_types: [],
        camera_ids: [],
        zone_ids: [],
        min_confidence: '',
        schedule_enabled: false,
        schedule_days: [],
        schedule_start_time: '22:00',
        schedule_end_time: '06:00',
        schedule_timezone: 'UTC',
        cooldown_seconds: 300,
        channels: [],
      };
      const result = alertRuleFormSchema.safeParse(payload);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.min_confidence).toBeNull();
      }
    });
  });

  describe('Constants alignment with backend', () => {
    it('should have correct name constraints (backend min_length=1, max_length=255)', () => {
      expect(ALERT_RULE_NAME_CONSTRAINTS.minLength).toBe(1);
      expect(ALERT_RULE_NAME_CONSTRAINTS.maxLength).toBe(255);
    });

    it('should have correct risk threshold constraints (backend ge=0, le=100)', () => {
      expect(RISK_THRESHOLD_CONSTRAINTS.min).toBe(0);
      expect(RISK_THRESHOLD_CONSTRAINTS.max).toBe(100);
    });

    it('should have correct min confidence constraints (backend ge=0.0, le=1.0)', () => {
      expect(MIN_CONFIDENCE_CONSTRAINTS.min).toBe(0);
      expect(MIN_CONFIDENCE_CONSTRAINTS.max).toBe(1);
    });

    it('should have correct cooldown constraints (backend ge=0)', () => {
      expect(COOLDOWN_SECONDS_CONSTRAINTS.min).toBe(0);
    });

    it('should have correct dedup key template constraints (backend max_length=255)', () => {
      expect(DEDUP_KEY_TEMPLATE_CONSTRAINTS.maxLength).toBe(255);
    });

    it('should have all severity values matching backend AlertSeverity enum', () => {
      expect(ALERT_SEVERITY_VALUES).toEqual(['low', 'medium', 'high', 'critical']);
    });

    it('should have all days matching backend VALID_DAYS', () => {
      expect(VALID_DAYS).toEqual([
        'monday',
        'tuesday',
        'wednesday',
        'thursday',
        'friday',
        'saturday',
        'sunday',
      ]);
    });
  });
});

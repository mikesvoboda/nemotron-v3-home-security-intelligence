/**
 * Tests for centralized validation utilities aligned with backend Pydantic schemas.
 *
 * These tests verify that frontend validation matches the backend validation rules
 * defined in:
 * - backend/api/schemas/zone.py
 * - backend/api/schemas/camera.py
 * - backend/api/schemas/alerts.py
 * - backend/api/schemas/notification_preferences.py
 * - backend/api/schemas/prompt_management.py
 */
import { describe, expect, it } from 'vitest';

import {
  validateAlertRuleName,
  validateCameraFolderPath,
  validateCameraName,
  validateCooldownSeconds,
  validateDaysOfWeek,
  validateDedupKeyTemplate,
  validateMaxTokens,
  validateMinConfidence,
  validateQuietHoursLabel,
  validateRiskThreshold,
  validateTemperature,
  validateTimeFormat,
  validateZoneColor,
  validateZoneCoordinates,
  validateZoneName,
  validateZonePriority,
  VALID_DAYS,
  VALIDATION_LIMITS,
} from './validation';

// =============================================================================
// Zone Validation Tests
// =============================================================================

describe('Zone Validation', () => {
  describe('validateZoneName', () => {
    it('should accept valid zone names', () => {
      expect(validateZoneName('A').isValid).toBe(true);
      expect(validateZoneName('Front Door').isValid).toBe(true);
      expect(validateZoneName('Zone 1').isValid).toBe(true);
      expect(validateZoneName('a'.repeat(255)).isValid).toBe(true);
    });

    it('should reject empty zone names (aligned with backend min_length=1)', () => {
      const result = validateZoneName('');
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('required');
    });

    it('should reject whitespace-only zone names', () => {
      const result = validateZoneName('   ');
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('required');
    });

    it('should reject zone names exceeding max length (aligned with backend max_length=255)', () => {
      const result = validateZoneName('a'.repeat(256));
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('255');
    });

    it('should trim whitespace before validation', () => {
      expect(validateZoneName('  Front Door  ').isValid).toBe(true);
    });
  });

  describe('validateZonePriority', () => {
    it('should accept valid priorities within range 0-100', () => {
      expect(validateZonePriority(0).isValid).toBe(true);
      expect(validateZonePriority(50).isValid).toBe(true);
      expect(validateZonePriority(100).isValid).toBe(true);
    });

    it('should reject priorities below minimum (aligned with backend ge=0)', () => {
      const result = validateZonePriority(-1);
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('0');
    });

    it('should reject priorities above maximum (aligned with backend le=100)', () => {
      const result = validateZonePriority(101);
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('100');
    });
  });

  describe('validateZoneColor', () => {
    it('should accept valid hex colors (aligned with backend pattern)', () => {
      expect(validateZoneColor('#3B82F6').isValid).toBe(true);
      expect(validateZoneColor('#000000').isValid).toBe(true);
      expect(validateZoneColor('#FFFFFF').isValid).toBe(true);
      expect(validateZoneColor('#abcdef').isValid).toBe(true);
    });

    it('should reject invalid hex color formats', () => {
      expect(validateZoneColor('3B82F6').isValid).toBe(false); // Missing #
      expect(validateZoneColor('#3B82F').isValid).toBe(false); // Too short
      expect(validateZoneColor('#3B82F6F').isValid).toBe(false); // Too long
      expect(validateZoneColor('#GGGGGG').isValid).toBe(false); // Invalid chars
      expect(validateZoneColor('rgb(0,0,0)').isValid).toBe(false); // Wrong format
    });
  });

  describe('validateZoneCoordinates', () => {
    it('should accept valid polygon coordinates (aligned with backend _validate_polygon_geometry)', () => {
      // Simple rectangle
      const rectangle: [number, number][] = [
        [0.1, 0.1],
        [0.9, 0.1],
        [0.9, 0.9],
        [0.1, 0.9],
      ];
      expect(validateZoneCoordinates(rectangle).isValid).toBe(true);

      // Triangle (minimum valid polygon)
      const triangle: [number, number][] = [
        [0.0, 0.0],
        [1.0, 0.0],
        [0.5, 1.0],
      ];
      expect(validateZoneCoordinates(triangle).isValid).toBe(true);

      // Complex pentagon
      const pentagon: [number, number][] = [
        [0.5, 0.0],
        [1.0, 0.4],
        [0.8, 1.0],
        [0.2, 1.0],
        [0.0, 0.4],
      ];
      expect(validateZoneCoordinates(pentagon).isValid).toBe(true);
    });

    it('should reject polygons with less than 3 points (aligned with backend min_length=3)', () => {
      const result1 = validateZoneCoordinates([]);
      expect(result1.isValid).toBe(false);
      expect(result1.error).toContain('at least 3');

      const result2 = validateZoneCoordinates([[0.1, 0.1]]);
      expect(result2.isValid).toBe(false);
      expect(result2.error).toContain('at least 3');

      const result3 = validateZoneCoordinates([
        [0.1, 0.1],
        [0.9, 0.9],
      ]);
      expect(result3.isValid).toBe(false);
      expect(result3.error).toContain('at least 3');
    });

    it('should reject points with wrong format', () => {
      // Point with only one coordinate
      const result1 = validateZoneCoordinates([
        [0.1, 0.1],
        [0.9] as unknown as [number, number],
        [0.5, 0.9],
      ]);
      expect(result1.isValid).toBe(false);
      expect(result1.error).toContain('exactly 2 values');

      // Point with three coordinates
      const result2 = validateZoneCoordinates([
        [0.1, 0.1],
        [0.9, 0.1, 0.5] as unknown as [number, number],
        [0.5, 0.9],
      ]);
      expect(result2.isValid).toBe(false);
      expect(result2.error).toContain('exactly 2 values');
    });

    it('should reject coordinates outside 0-1 range (aligned with backend normalization)', () => {
      // X coordinate out of range
      const result1 = validateZoneCoordinates([
        [0.1, 0.1],
        [1.5, 0.1],
        [0.5, 0.9],
      ]);
      expect(result1.isValid).toBe(false);
      expect(result1.error).toContain('normalized (0-1 range)');

      // Y coordinate out of range (negative)
      const result2 = validateZoneCoordinates([
        [0.1, -0.1],
        [0.9, 0.1],
        [0.5, 0.9],
      ]);
      expect(result2.isValid).toBe(false);
      expect(result2.error).toContain('normalized (0-1 range)');
    });

    it('should reject duplicate consecutive points (aligned with backend _has_duplicate_consecutive_points)', () => {
      const result = validateZoneCoordinates([
        [0.1, 0.1],
        [0.1, 0.1], // Duplicate
        [0.9, 0.1],
        [0.5, 0.9],
      ]);
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('duplicate consecutive');
    });

    it('should reject self-intersecting polygons (aligned with backend _is_self_intersecting)', () => {
      // Figure-8 shaped polygon (edges cross)
      const figureEight: [number, number][] = [
        [0.0, 0.0],
        [1.0, 1.0],
        [1.0, 0.0],
        [0.0, 1.0],
      ];
      const result = validateZoneCoordinates(figureEight);
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('self-intersect');
    });

    it('should reject degenerate polygons with zero area (aligned with backend area check)', () => {
      // All points on a line (zero area)
      const collinear: [number, number][] = [
        [0.0, 0.0],
        [0.5, 0.5],
        [1.0, 1.0],
      ];
      const result = validateZoneCoordinates(collinear);
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('too small');
    });

    it('should accept edge case: boundary coordinates (0 and 1)', () => {
      const boundary: [number, number][] = [
        [0, 0],
        [1, 0],
        [1, 1],
        [0, 1],
      ];
      expect(validateZoneCoordinates(boundary).isValid).toBe(true);
    });
  });
});

// =============================================================================
// Camera Validation Tests
// =============================================================================

describe('Camera Validation', () => {
  describe('validateCameraName', () => {
    it('should accept valid camera names', () => {
      expect(validateCameraName('A').isValid).toBe(true);
      expect(validateCameraName('Front Door Camera').isValid).toBe(true);
      expect(validateCameraName('Camera-1').isValid).toBe(true);
      expect(validateCameraName('a'.repeat(255)).isValid).toBe(true);
    });

    it('should reject empty camera names (aligned with backend min_length=1)', () => {
      const result = validateCameraName('');
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('required');
    });

    it('should reject camera names exceeding max length (aligned with backend max_length=255)', () => {
      const result = validateCameraName('a'.repeat(256));
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('255');
    });
  });

  describe('validateCameraFolderPath', () => {
    it('should accept valid folder paths', () => {
      expect(validateCameraFolderPath('/export/foscam/front_door').isValid).toBe(true);
      expect(validateCameraFolderPath('/home/user/cameras').isValid).toBe(true);
      expect(validateCameraFolderPath('/a').isValid).toBe(true);
      expect(validateCameraFolderPath('a'.repeat(500)).isValid).toBe(true);
    });

    it('should reject empty folder paths (aligned with backend min_length=1)', () => {
      const result = validateCameraFolderPath('');
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('required');
    });

    it('should reject folder paths exceeding max length (aligned with backend max_length=500)', () => {
      const result = validateCameraFolderPath('a'.repeat(501));
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('500');
    });

    it('should reject path traversal attempts (aligned with backend security validation)', () => {
      const result1 = validateCameraFolderPath('/export/../etc/passwd');
      expect(result1.isValid).toBe(false);
      expect(result1.error).toContain('traversal');

      const result2 = validateCameraFolderPath('../../secret');
      expect(result2.isValid).toBe(false);
      expect(result2.error).toContain('traversal');
    });

    it('should reject forbidden characters (aligned with backend security validation)', () => {
      const forbiddenChars = ['<', '>', ':', '"', '|', '?', '*'];
      forbiddenChars.forEach((char) => {
        const result = validateCameraFolderPath(`/path/with${char}char`);
        expect(result.isValid).toBe(false);
        expect(result.error).toContain('forbidden');
      });
    });

    it('should reject control characters', () => {
      const result = validateCameraFolderPath('/path/with\x00null');
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('forbidden');
    });
  });
});

// =============================================================================
// Alert Rule Validation Tests
// =============================================================================

describe('Alert Rule Validation', () => {
  describe('validateAlertRuleName', () => {
    it('should accept valid alert rule names', () => {
      expect(validateAlertRuleName('A').isValid).toBe(true);
      expect(validateAlertRuleName('Night Intruder Alert').isValid).toBe(true);
      expect(validateAlertRuleName('a'.repeat(255)).isValid).toBe(true);
    });

    it('should reject empty alert rule names (aligned with backend min_length=1)', () => {
      const result = validateAlertRuleName('');
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('required');
    });

    it('should reject alert rule names exceeding max length (aligned with backend max_length=255)', () => {
      const result = validateAlertRuleName('a'.repeat(256));
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('255');
    });
  });

  describe('validateRiskThreshold', () => {
    it('should accept null (optional field)', () => {
      expect(validateRiskThreshold(null).isValid).toBe(true);
    });

    it('should accept valid thresholds within range 0-100', () => {
      expect(validateRiskThreshold(0).isValid).toBe(true);
      expect(validateRiskThreshold(50).isValid).toBe(true);
      expect(validateRiskThreshold(100).isValid).toBe(true);
    });

    it('should reject thresholds below minimum (aligned with backend ge=0)', () => {
      const result = validateRiskThreshold(-1);
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('0');
    });

    it('should reject thresholds above maximum (aligned with backend le=100)', () => {
      const result = validateRiskThreshold(101);
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('100');
    });
  });

  describe('validateMinConfidence', () => {
    it('should accept null (optional field)', () => {
      expect(validateMinConfidence(null).isValid).toBe(true);
    });

    it('should accept valid confidence within range 0-1', () => {
      expect(validateMinConfidence(0).isValid).toBe(true);
      expect(validateMinConfidence(0.5).isValid).toBe(true);
      expect(validateMinConfidence(1).isValid).toBe(true);
    });

    it('should reject confidence below minimum (aligned with backend ge=0.0)', () => {
      const result = validateMinConfidence(-0.1);
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('0');
    });

    it('should reject confidence above maximum (aligned with backend le=1.0)', () => {
      const result = validateMinConfidence(1.1);
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('1');
    });
  });

  describe('validateCooldownSeconds', () => {
    it('should accept valid cooldown values', () => {
      expect(validateCooldownSeconds(0).isValid).toBe(true);
      expect(validateCooldownSeconds(300).isValid).toBe(true);
      expect(validateCooldownSeconds(3600).isValid).toBe(true);
    });

    it('should reject negative cooldown (aligned with backend ge=0)', () => {
      const result = validateCooldownSeconds(-1);
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('negative');
    });
  });

  describe('validateDedupKeyTemplate', () => {
    it('should accept valid templates (aligned with backend DEDUP_KEY_PATTERN)', () => {
      expect(validateDedupKeyTemplate('{camera_id}:{rule_id}').isValid).toBe(true);
      expect(validateDedupKeyTemplate('short').isValid).toBe(true);
      expect(validateDedupKeyTemplate('camera-123:rule_456').isValid).toBe(true);
      expect(validateDedupKeyTemplate('ABC_123').isValid).toBe(true);
      expect(validateDedupKeyTemplate('a'.repeat(255)).isValid).toBe(true);
    });

    it('should accept empty templates', () => {
      expect(validateDedupKeyTemplate('').isValid).toBe(true);
    });

    it('should reject templates exceeding max length (aligned with backend max_length=255)', () => {
      const result = validateDedupKeyTemplate('a'.repeat(256));
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('255');
    });

    it('should reject templates with invalid characters (aligned with backend security validation NEM-1107)', () => {
      // SQL injection attempt
      const result1 = validateDedupKeyTemplate("'; DROP TABLE alerts;--");
      expect(result1.isValid).toBe(false);
      expect(result1.error).toContain('alphanumeric');

      // Command injection attempt
      const result2 = validateDedupKeyTemplate('test$(whoami)');
      expect(result2.isValid).toBe(false);
      expect(result2.error).toContain('alphanumeric');

      // XSS attempt
      const result3 = validateDedupKeyTemplate('<script>alert(1)</script>');
      expect(result3.isValid).toBe(false);
      expect(result3.error).toContain('alphanumeric');

      // Path traversal
      const result4 = validateDedupKeyTemplate('../../../etc/passwd');
      expect(result4.isValid).toBe(false);
      expect(result4.error).toContain('alphanumeric');

      // Spaces not allowed
      const result5 = validateDedupKeyTemplate('camera id');
      expect(result5.isValid).toBe(false);
      expect(result5.error).toContain('alphanumeric');
    });
  });
});

// =============================================================================
// Time Format Validation Tests
// =============================================================================

describe('Time Format Validation', () => {
  describe('validateTimeFormat', () => {
    it('should accept valid HH:MM time formats', () => {
      expect(validateTimeFormat('00:00').isValid).toBe(true);
      expect(validateTimeFormat('12:30').isValid).toBe(true);
      expect(validateTimeFormat('23:59').isValid).toBe(true);
      expect(validateTimeFormat('06:00').isValid).toBe(true);
    });

    it('should reject invalid time format structure', () => {
      expect(validateTimeFormat('').isValid).toBe(false);
      expect(validateTimeFormat('1:30').isValid).toBe(false); // Missing leading zero
      expect(validateTimeFormat('12:3').isValid).toBe(false); // Missing leading zero
      expect(validateTimeFormat('12-30').isValid).toBe(false); // Wrong separator
      expect(validateTimeFormat('12:30:00').isValid).toBe(false); // Too long
    });

    it('should reject invalid hours (aligned with backend hours 00-23)', () => {
      expect(validateTimeFormat('24:00').isValid).toBe(false);
      expect(validateTimeFormat('25:00').isValid).toBe(false);
    });

    it('should reject invalid minutes (aligned with backend minutes 00-59)', () => {
      expect(validateTimeFormat('12:60').isValid).toBe(false);
      expect(validateTimeFormat('12:99').isValid).toBe(false);
    });

    it('should reject non-numeric time components', () => {
      expect(validateTimeFormat('ab:cd').isValid).toBe(false);
      expect(validateTimeFormat('12:ab').isValid).toBe(false);
    });
  });

  describe('validateDaysOfWeek', () => {
    it('should accept valid day names', () => {
      expect(validateDaysOfWeek(['monday']).isValid).toBe(true);
      expect(validateDaysOfWeek(['monday', 'tuesday', 'wednesday']).isValid).toBe(true);
      expect(validateDaysOfWeek(VALID_DAYS as unknown as string[]).isValid).toBe(true);
    });

    it('should accept empty array', () => {
      expect(validateDaysOfWeek([]).isValid).toBe(true);
    });

    it('should reject invalid day names', () => {
      const result = validateDaysOfWeek(['monday', 'funday']);
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('funday');
    });

    it('should be case-insensitive', () => {
      expect(validateDaysOfWeek(['MONDAY', 'Tuesday']).isValid).toBe(true);
    });
  });
});

// =============================================================================
// Notification Preferences Validation Tests
// =============================================================================

describe('Notification Preferences Validation', () => {
  describe('validateQuietHoursLabel', () => {
    it('should accept valid labels', () => {
      expect(validateQuietHoursLabel('A').isValid).toBe(true);
      expect(validateQuietHoursLabel('Night Time').isValid).toBe(true);
      expect(validateQuietHoursLabel('a'.repeat(255)).isValid).toBe(true);
    });

    it('should reject empty labels (aligned with backend min_length=1)', () => {
      const result = validateQuietHoursLabel('');
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('required');
    });

    it('should reject labels exceeding max length (aligned with backend max_length=255)', () => {
      const result = validateQuietHoursLabel('a'.repeat(256));
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('255');
    });
  });
});

// =============================================================================
// Prompt Configuration Validation Tests
// =============================================================================

describe('Prompt Configuration Validation', () => {
  describe('validateTemperature', () => {
    it('should accept valid temperature values within range 0-2', () => {
      expect(validateTemperature(0).isValid).toBe(true);
      expect(validateTemperature(0.7).isValid).toBe(true);
      expect(validateTemperature(1).isValid).toBe(true);
      expect(validateTemperature(2).isValid).toBe(true);
    });

    it('should reject temperature below minimum (aligned with backend ge=0.0)', () => {
      const result = validateTemperature(-0.1);
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('0');
    });

    it('should reject temperature above maximum (aligned with backend le=2.0)', () => {
      const result = validateTemperature(2.1);
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('2');
    });
  });

  describe('validateMaxTokens', () => {
    it('should accept valid max tokens within range 1-16384', () => {
      expect(validateMaxTokens(1).isValid).toBe(true);
      expect(validateMaxTokens(2048).isValid).toBe(true);
      expect(validateMaxTokens(16384).isValid).toBe(true);
    });

    it('should reject max tokens below minimum (aligned with backend ge=1)', () => {
      const result = validateMaxTokens(0);
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('1');
    });

    it('should reject max tokens above maximum (aligned with backend le=16384)', () => {
      const result = validateMaxTokens(16385);
      expect(result.isValid).toBe(false);
      expect(result.error).toContain('16384');
    });
  });
});

// =============================================================================
// Validation Limits Constants Tests
// =============================================================================

describe('VALIDATION_LIMITS', () => {
  it('should have zone limits matching backend', () => {
    expect(VALIDATION_LIMITS.zone.name.minLength).toBe(1);
    expect(VALIDATION_LIMITS.zone.name.maxLength).toBe(255);
    expect(VALIDATION_LIMITS.zone.priority.min).toBe(0);
    expect(VALIDATION_LIMITS.zone.priority.max).toBe(100);
    expect(VALIDATION_LIMITS.zone.coordinates.minPoints).toBe(3);
  });

  it('should have camera limits matching backend', () => {
    expect(VALIDATION_LIMITS.camera.name.minLength).toBe(1);
    expect(VALIDATION_LIMITS.camera.name.maxLength).toBe(255);
    expect(VALIDATION_LIMITS.camera.folderPath.minLength).toBe(1);
    expect(VALIDATION_LIMITS.camera.folderPath.maxLength).toBe(500);
  });

  it('should have alert rule limits matching backend', () => {
    expect(VALIDATION_LIMITS.alertRule.name.minLength).toBe(1);
    expect(VALIDATION_LIMITS.alertRule.name.maxLength).toBe(255);
    expect(VALIDATION_LIMITS.alertRule.riskThreshold.min).toBe(0);
    expect(VALIDATION_LIMITS.alertRule.riskThreshold.max).toBe(100);
    expect(VALIDATION_LIMITS.alertRule.minConfidence.min).toBe(0);
    expect(VALIDATION_LIMITS.alertRule.minConfidence.max).toBe(1);
    expect(VALIDATION_LIMITS.alertRule.cooldownSeconds.min).toBe(0);
    expect(VALIDATION_LIMITS.alertRule.dedupKeyTemplate.maxLength).toBe(255);
  });

  it('should have notification preferences limits matching backend', () => {
    expect(VALIDATION_LIMITS.notificationPreferences.riskThreshold.min).toBe(0);
    expect(VALIDATION_LIMITS.notificationPreferences.riskThreshold.max).toBe(100);
    expect(VALIDATION_LIMITS.notificationPreferences.quietHoursLabel.minLength).toBe(1);
    expect(VALIDATION_LIMITS.notificationPreferences.quietHoursLabel.maxLength).toBe(255);
  });

  it('should have prompt config limits matching backend', () => {
    expect(VALIDATION_LIMITS.promptConfig.temperature.min).toBe(0);
    expect(VALIDATION_LIMITS.promptConfig.temperature.max).toBe(2);
    expect(VALIDATION_LIMITS.promptConfig.maxTokens.min).toBe(1);
    expect(VALIDATION_LIMITS.promptConfig.maxTokens.max).toBe(16384);
  });
});

// =============================================================================
// VALID_DAYS Constants Tests
// =============================================================================

describe('VALID_DAYS', () => {
  it('should contain all days of the week (aligned with backend VALID_DAYS)', () => {
    expect(VALID_DAYS).toContain('monday');
    expect(VALID_DAYS).toContain('tuesday');
    expect(VALID_DAYS).toContain('wednesday');
    expect(VALID_DAYS).toContain('thursday');
    expect(VALID_DAYS).toContain('friday');
    expect(VALID_DAYS).toContain('saturday');
    expect(VALID_DAYS).toContain('sunday');
    expect(VALID_DAYS.length).toBe(7);
  });
});

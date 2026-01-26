/**
 * Tests for batch settings validation utility
 *
 * @see NEM-3873 - Batch Config Validation
 */

import { describe, expect, it } from 'vitest';

import {
  BATCH_PRESETS,
  calculateLatencyImpact,
  detectCurrentPreset,
  validateBatchSettings,
  type BatchPreset,
  type BatchSettingsValidation,
  type LatencyImpact,
} from './batchSettingsValidation';

describe('batchSettingsValidation', () => {
  describe('validateBatchSettings', () => {
    it('returns no warnings for valid balanced settings', () => {
      const result = validateBatchSettings(90, 30);

      expect(result.isValid).toBe(true);
      expect(result.warnings).toHaveLength(0);
      expect(result.errors).toHaveLength(0);
    });

    it('warns when idle_timeout >= window_seconds', () => {
      const result = validateBatchSettings(60, 60);

      expect(result.isValid).toBe(true); // Still valid, just a warning
      expect(result.warnings).toContain(
        'Idle timeout should be less than batch window for optimal performance'
      );
    });

    it('warns when idle_timeout > window_seconds', () => {
      const result = validateBatchSettings(60, 90);

      expect(result.isValid).toBe(true);
      expect(result.warnings).toContain(
        'Idle timeout should be less than batch window for optimal performance'
      );
    });

    it('warns when window < 30s (too aggressive)', () => {
      const result = validateBatchSettings(20, 10);

      expect(result.isValid).toBe(true);
      expect(result.warnings).toContain(
        'Batch window under 30 seconds may cause excessive processing overhead'
      );
    });

    it('warns when window > 180s (too slow)', () => {
      const result = validateBatchSettings(200, 60);

      expect(result.isValid).toBe(true);
      expect(result.warnings).toContain(
        'Batch window over 180 seconds may delay event notifications significantly'
      );
    });

    it('returns multiple warnings when multiple conditions are violated', () => {
      const result = validateBatchSettings(20, 25);

      expect(result.isValid).toBe(true);
      expect(result.warnings.length).toBeGreaterThanOrEqual(2);
      expect(result.warnings).toContain(
        'Batch window under 30 seconds may cause excessive processing overhead'
      );
      expect(result.warnings).toContain(
        'Idle timeout should be less than batch window for optimal performance'
      );
    });

    it('returns error when window_seconds is 0 or negative', () => {
      const result = validateBatchSettings(0, 30);

      expect(result.isValid).toBe(false);
      expect(result.errors).toContain('Batch window must be greater than 0');
    });

    it('returns error when idle_timeout is 0 or negative', () => {
      const result = validateBatchSettings(90, 0);

      expect(result.isValid).toBe(false);
      expect(result.errors).toContain('Idle timeout must be greater than 0');
    });

    it('returns error when window exceeds maximum (600s)', () => {
      const result = validateBatchSettings(700, 30);

      expect(result.isValid).toBe(false);
      expect(result.errors).toContain('Batch window cannot exceed 600 seconds');
    });

    it('returns error when idle_timeout exceeds maximum (300s)', () => {
      const result = validateBatchSettings(90, 350);

      expect(result.isValid).toBe(false);
      expect(result.errors).toContain('Idle timeout cannot exceed 300 seconds');
    });
  });

  describe('calculateLatencyImpact', () => {
    it('calculates correct latency impact for real-time preset', () => {
      const impact = calculateLatencyImpact(30, 10);

      expect(impact.minLatencySeconds).toBe(10);
      expect(impact.maxLatencySeconds).toBe(30);
      expect(impact.typicalLatencySeconds).toBe(20);
      expect(impact.description).toContain('Real-time');
    });

    it('calculates correct latency impact for balanced preset', () => {
      const impact = calculateLatencyImpact(90, 30);

      expect(impact.minLatencySeconds).toBe(30);
      expect(impact.maxLatencySeconds).toBe(90);
      expect(impact.typicalLatencySeconds).toBe(60);
      expect(impact.description).toContain('Balanced');
    });

    it('calculates correct latency impact for efficient preset', () => {
      const impact = calculateLatencyImpact(180, 60);

      expect(impact.minLatencySeconds).toBe(60);
      expect(impact.maxLatencySeconds).toBe(180);
      expect(impact.typicalLatencySeconds).toBe(120);
      expect(impact.description).toContain('Efficient');
    });

    it('calculates custom latency impact for non-preset values', () => {
      const impact = calculateLatencyImpact(120, 45);

      expect(impact.minLatencySeconds).toBe(45);
      expect(impact.maxLatencySeconds).toBe(120);
      expect(impact.typicalLatencySeconds).toBe(82.5);
      expect(impact.description).toContain('Custom');
    });
  });

  describe('BATCH_PRESETS', () => {
    it('contains real-time preset with correct values', () => {
      const realtime = BATCH_PRESETS.find((p) => p.id === 'realtime');

      expect(realtime).toBeDefined();
      expect(realtime?.windowSeconds).toBe(30);
      expect(realtime?.idleTimeoutSeconds).toBe(10);
      expect(realtime?.name).toBe('Real-time');
    });

    it('contains balanced preset with correct values', () => {
      const balanced = BATCH_PRESETS.find((p) => p.id === 'balanced');

      expect(balanced).toBeDefined();
      expect(balanced?.windowSeconds).toBe(90);
      expect(balanced?.idleTimeoutSeconds).toBe(30);
      expect(balanced?.name).toBe('Balanced');
    });

    it('contains efficient preset with correct values', () => {
      const efficient = BATCH_PRESETS.find((p) => p.id === 'efficient');

      expect(efficient).toBeDefined();
      expect(efficient?.windowSeconds).toBe(180);
      expect(efficient?.idleTimeoutSeconds).toBe(60);
      expect(efficient?.name).toBe('Efficient');
    });

    it('has exactly 3 presets', () => {
      expect(BATCH_PRESETS).toHaveLength(3);
    });

    it('all presets have descriptions', () => {
      BATCH_PRESETS.forEach((preset) => {
        expect(preset.description).toBeTruthy();
        expect(preset.description.length).toBeGreaterThan(10);
      });
    });
  });

  describe('detectCurrentPreset', () => {
    it('detects real-time preset', () => {
      const preset = detectCurrentPreset(30, 10);

      expect(preset).toBe('realtime');
    });

    it('detects balanced preset', () => {
      const preset = detectCurrentPreset(90, 30);

      expect(preset).toBe('balanced');
    });

    it('detects efficient preset', () => {
      const preset = detectCurrentPreset(180, 60);

      expect(preset).toBe('efficient');
    });

    it('returns null for custom values', () => {
      const preset = detectCurrentPreset(120, 45);

      expect(preset).toBeNull();
    });

    it('returns null when window matches but idle does not', () => {
      const preset = detectCurrentPreset(90, 45);

      expect(preset).toBeNull();
    });
  });

  describe('type exports', () => {
    it('BatchSettingsValidation type is properly structured', () => {
      const validation: BatchSettingsValidation = {
        isValid: true,
        warnings: ['test warning'],
        errors: [],
      };

      expect(validation.isValid).toBe(true);
      expect(validation.warnings).toHaveLength(1);
      expect(validation.errors).toHaveLength(0);
    });

    it('LatencyImpact type is properly structured', () => {
      const impact: LatencyImpact = {
        minLatencySeconds: 10,
        maxLatencySeconds: 30,
        typicalLatencySeconds: 20,
        description: 'Test description',
      };

      expect(impact.minLatencySeconds).toBe(10);
      expect(impact.maxLatencySeconds).toBe(30);
      expect(impact.typicalLatencySeconds).toBe(20);
      expect(impact.description).toBe('Test description');
    });

    it('BatchPreset type is properly structured', () => {
      const preset: BatchPreset = {
        id: 'test',
        name: 'Test Preset',
        windowSeconds: 60,
        idleTimeoutSeconds: 20,
        description: 'A test preset',
      };

      expect(preset.id).toBe('test');
      expect(preset.name).toBe('Test Preset');
      expect(preset.windowSeconds).toBe(60);
      expect(preset.idleTimeoutSeconds).toBe(20);
      expect(preset.description).toBe('A test preset');
    });
  });
});

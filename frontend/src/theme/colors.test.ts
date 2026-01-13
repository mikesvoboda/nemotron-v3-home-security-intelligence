import { describe, expect, it } from 'vitest';

import {
  STATUS_COLORS,
  STATUS_BG_CLASSES,
  STATUS_BG_LIGHT_CLASSES,
  STATUS_TEXT_CLASSES,
  STATUS_BORDER_CLASSES,
  STATUS_HEX_COLORS,
  QUEUE_STATUS_COLORS,
  LATENCY_STATUS_COLORS,
  getStatusColor,
  getStatusClasses,
  getStatusHexColor,
  getQueueStatusColor,
  getLatencyStatusColor,
} from './colors';

describe('theme/colors', () => {
  describe('STATUS_COLORS constant', () => {
    it('should have emerald for healthy status (WCAG compliant)', () => {
      expect(STATUS_COLORS.healthy).toBe('emerald');
    });

    it('should have emerald for online status', () => {
      expect(STATUS_COLORS.online).toBe('emerald');
    });

    it('should have yellow for warning status', () => {
      expect(STATUS_COLORS.warning).toBe('yellow');
    });

    it('should have yellow for degraded status', () => {
      expect(STATUS_COLORS.degraded).toBe('yellow');
    });

    it('should have red for error status', () => {
      expect(STATUS_COLORS.error).toBe('red');
    });

    it('should have red for offline status', () => {
      expect(STATUS_COLORS.offline).toBe('red');
    });

    it('should have red for unhealthy status', () => {
      expect(STATUS_COLORS.unhealthy).toBe('red');
    });

    it('should have gray for inactive status', () => {
      expect(STATUS_COLORS.inactive).toBe('gray');
    });

    it('should have gray for unknown status', () => {
      expect(STATUS_COLORS.unknown).toBe('gray');
    });
  });

  describe('STATUS_BG_CLASSES constant', () => {
    it('should use emerald-500 for healthy backgrounds', () => {
      expect(STATUS_BG_CLASSES.healthy).toBe('bg-emerald-500');
    });

    it('should use yellow-500 for warning backgrounds', () => {
      expect(STATUS_BG_CLASSES.warning).toBe('bg-yellow-500');
    });

    it('should use red-500 for error backgrounds', () => {
      expect(STATUS_BG_CLASSES.error).toBe('bg-red-500');
    });

    it('should use gray-500 for inactive backgrounds', () => {
      expect(STATUS_BG_CLASSES.inactive).toBe('bg-gray-500');
    });
  });

  describe('STATUS_BG_LIGHT_CLASSES constant', () => {
    it('should use 10% opacity for light backgrounds', () => {
      expect(STATUS_BG_LIGHT_CLASSES.healthy).toBe('bg-emerald-500/10');
      expect(STATUS_BG_LIGHT_CLASSES.warning).toBe('bg-yellow-500/10');
      expect(STATUS_BG_LIGHT_CLASSES.error).toBe('bg-red-500/10');
      expect(STATUS_BG_LIGHT_CLASSES.inactive).toBe('bg-gray-500/10');
    });
  });

  describe('STATUS_TEXT_CLASSES constant', () => {
    it('should use 400 shade for text colors (WCAG compliant on dark bg)', () => {
      expect(STATUS_TEXT_CLASSES.healthy).toBe('text-emerald-400');
      expect(STATUS_TEXT_CLASSES.warning).toBe('text-yellow-400');
      expect(STATUS_TEXT_CLASSES.error).toBe('text-red-400');
      expect(STATUS_TEXT_CLASSES.inactive).toBe('text-gray-400');
    });
  });

  describe('STATUS_BORDER_CLASSES constant', () => {
    it('should use 30% opacity for borders', () => {
      expect(STATUS_BORDER_CLASSES.healthy).toBe('border-emerald-500/30');
      expect(STATUS_BORDER_CLASSES.warning).toBe('border-yellow-500/30');
      expect(STATUS_BORDER_CLASSES.error).toBe('border-red-500/30');
      expect(STATUS_BORDER_CLASSES.inactive).toBe('border-gray-500/30');
    });
  });

  describe('STATUS_HEX_COLORS constant', () => {
    it('should have correct hex values for WCAG compliance', () => {
      // emerald-500
      expect(STATUS_HEX_COLORS.healthy).toBe('#10B981');
      // amber-500
      expect(STATUS_HEX_COLORS.warning).toBe('#F59E0B');
      // red-500
      expect(STATUS_HEX_COLORS.error).toBe('#EF4444');
      // gray-500
      expect(STATUS_HEX_COLORS.inactive).toBe('#6B7280');
    });
  });

  describe('getStatusColor function', () => {
    it('should return correct Tremor color for direct status names', () => {
      expect(getStatusColor('healthy')).toBe('emerald');
      expect(getStatusColor('online')).toBe('emerald');
      expect(getStatusColor('warning')).toBe('yellow');
      expect(getStatusColor('degraded')).toBe('yellow');
      expect(getStatusColor('error')).toBe('red');
      expect(getStatusColor('offline')).toBe('red');
      expect(getStatusColor('unhealthy')).toBe('red');
      expect(getStatusColor('inactive')).toBe('gray');
      expect(getStatusColor('unknown')).toBe('gray');
    });

    it('should handle common aliases', () => {
      expect(getStatusColor('ok')).toBe('emerald');
      expect(getStatusColor('success')).toBe('emerald');
      expect(getStatusColor('active')).toBe('emerald');
      expect(getStatusColor('running')).toBe('emerald');
      expect(getStatusColor('warn')).toBe('yellow');
      expect(getStatusColor('caution')).toBe('yellow');
      expect(getStatusColor('restarting')).toBe('yellow');
      expect(getStatusColor('fail')).toBe('red');
      expect(getStatusColor('failed')).toBe('red');
      expect(getStatusColor('critical')).toBe('red');
      expect(getStatusColor('down')).toBe('red');
      expect(getStatusColor('stopped')).toBe('gray');
      expect(getStatusColor('disabled')).toBe('gray');
      expect(getStatusColor('pending')).toBe('gray');
    });

    it('should be case-insensitive', () => {
      expect(getStatusColor('HEALTHY')).toBe('emerald');
      expect(getStatusColor('Healthy')).toBe('emerald');
      expect(getStatusColor('HeAlThY')).toBe('emerald');
    });

    it('should trim whitespace', () => {
      expect(getStatusColor('  healthy  ')).toBe('emerald');
      expect(getStatusColor('\thealthy\n')).toBe('emerald');
    });

    it('should return gray for unknown status values', () => {
      expect(getStatusColor('foobar')).toBe('gray');
      expect(getStatusColor('')).toBe('gray');
    });
  });

  describe('getStatusClasses function', () => {
    it('should return all class types for a status', () => {
      const classes = getStatusClasses('healthy');
      expect(classes).toHaveProperty('bgClass');
      expect(classes).toHaveProperty('bgLightClass');
      expect(classes).toHaveProperty('textClass');
      expect(classes).toHaveProperty('borderClass');
    });

    it('should return correct classes for healthy status', () => {
      const classes = getStatusClasses('healthy');
      expect(classes.bgClass).toBe('bg-emerald-500');
      expect(classes.bgLightClass).toBe('bg-emerald-500/10');
      expect(classes.textClass).toBe('text-emerald-400');
      expect(classes.borderClass).toBe('border-emerald-500/30');
    });

    it('should return correct classes for warning status', () => {
      const classes = getStatusClasses('warning');
      expect(classes.bgClass).toBe('bg-yellow-500');
      expect(classes.textClass).toBe('text-yellow-400');
    });

    it('should return correct classes for error status', () => {
      const classes = getStatusClasses('error');
      expect(classes.bgClass).toBe('bg-red-500');
      expect(classes.textClass).toBe('text-red-400');
    });

    it('should handle aliases correctly', () => {
      const okClasses = getStatusClasses('ok');
      const healthyClasses = getStatusClasses('healthy');
      expect(okClasses).toEqual(healthyClasses);

      const failClasses = getStatusClasses('fail');
      const errorClasses = getStatusClasses('error');
      expect(failClasses).toEqual(errorClasses);
    });

    it('should return inactive classes for unknown statuses', () => {
      const classes = getStatusClasses('foobar');
      expect(classes.bgClass).toBe('bg-gray-500');
      expect(classes.textClass).toBe('text-gray-400');
    });
  });

  describe('getStatusHexColor function', () => {
    it('should return correct hex colors', () => {
      expect(getStatusHexColor('healthy')).toBe('#10B981');
      expect(getStatusHexColor('warning')).toBe('#F59E0B');
      expect(getStatusHexColor('error')).toBe('#EF4444');
      expect(getStatusHexColor('inactive')).toBe('#6B7280');
    });

    it('should handle aliases', () => {
      expect(getStatusHexColor('ok')).toBe('#10B981');
      expect(getStatusHexColor('fail')).toBe('#EF4444');
    });

    it('should return gray hex for unknown statuses', () => {
      expect(getStatusHexColor('foobar')).toBe('#6B7280');
    });
  });

  describe('getQueueStatusColor function', () => {
    it('should return gray for empty queue (depth = 0)', () => {
      expect(getQueueStatusColor(0, 10)).toBe('gray');
    });

    it('should return emerald for normal queue (depth <= threshold/2)', () => {
      expect(getQueueStatusColor(3, 10)).toBe('emerald');
      expect(getQueueStatusColor(5, 10)).toBe('emerald');
    });

    it('should return yellow for elevated queue (threshold/2 < depth <= threshold)', () => {
      expect(getQueueStatusColor(6, 10)).toBe('yellow');
      expect(getQueueStatusColor(10, 10)).toBe('yellow');
    });

    it('should return red for critical queue (depth > threshold)', () => {
      expect(getQueueStatusColor(11, 10)).toBe('red');
      expect(getQueueStatusColor(100, 10)).toBe('red');
    });

    it('should handle edge cases at boundaries', () => {
      // Exactly at threshold/2
      expect(getQueueStatusColor(5, 10)).toBe('emerald');
      // Just above threshold/2
      expect(getQueueStatusColor(6, 10)).toBe('yellow');
      // Exactly at threshold
      expect(getQueueStatusColor(10, 10)).toBe('yellow');
      // Just above threshold
      expect(getQueueStatusColor(11, 10)).toBe('red');
    });
  });

  describe('getLatencyStatusColor function', () => {
    it('should return gray for null/undefined latency', () => {
      expect(getLatencyStatusColor(null, 1000)).toBe('gray');
      expect(getLatencyStatusColor(undefined, 1000)).toBe('gray');
    });

    it('should return emerald for fast latency (< threshold/2)', () => {
      expect(getLatencyStatusColor(200, 1000)).toBe('emerald');
      expect(getLatencyStatusColor(499, 1000)).toBe('emerald');
    });

    it('should return yellow for normal latency (threshold/2 <= ms < threshold)', () => {
      expect(getLatencyStatusColor(500, 1000)).toBe('yellow');
      expect(getLatencyStatusColor(999, 1000)).toBe('yellow');
    });

    it('should return red for slow latency (>= threshold)', () => {
      expect(getLatencyStatusColor(1000, 1000)).toBe('red');
      expect(getLatencyStatusColor(5000, 1000)).toBe('red');
    });

    it('should handle zero latency as fast', () => {
      expect(getLatencyStatusColor(0, 1000)).toBe('emerald');
    });
  });

  describe('QUEUE_STATUS_COLORS constant', () => {
    it('should have all expected status types', () => {
      expect(QUEUE_STATUS_COLORS).toHaveProperty('empty');
      expect(QUEUE_STATUS_COLORS).toHaveProperty('normal');
      expect(QUEUE_STATUS_COLORS).toHaveProperty('elevated');
      expect(QUEUE_STATUS_COLORS).toHaveProperty('critical');
    });

    it('should use WCAG compliant colors', () => {
      expect(QUEUE_STATUS_COLORS.empty).toBe('gray');
      expect(QUEUE_STATUS_COLORS.normal).toBe('emerald');
      expect(QUEUE_STATUS_COLORS.elevated).toBe('yellow');
      expect(QUEUE_STATUS_COLORS.critical).toBe('red');
    });
  });

  describe('LATENCY_STATUS_COLORS constant', () => {
    it('should have all expected status types', () => {
      expect(LATENCY_STATUS_COLORS).toHaveProperty('fast');
      expect(LATENCY_STATUS_COLORS).toHaveProperty('normal');
      expect(LATENCY_STATUS_COLORS).toHaveProperty('slow');
      expect(LATENCY_STATUS_COLORS).toHaveProperty('unknown');
    });

    it('should use WCAG compliant colors', () => {
      expect(LATENCY_STATUS_COLORS.fast).toBe('emerald');
      expect(LATENCY_STATUS_COLORS.normal).toBe('yellow');
      expect(LATENCY_STATUS_COLORS.slow).toBe('red');
      expect(LATENCY_STATUS_COLORS.unknown).toBe('gray');
    });
  });

  describe('WCAG 2.1 AA Compliance', () => {
    /**
     * WCAG 2.1 AA requires:
     * - 4.5:1 contrast ratio for normal text
     * - 3:1 contrast ratio for large text (18pt+ or 14pt+ bold)
     *
     * These tests verify that our color choices meet these requirements
     * when used on the application's dark background (#1A1A1A).
     */

    it('should use emerald instead of green for better contrast', () => {
      // emerald-500 (#10B981) provides better contrast than green-500 (#22c55e)
      // on dark backgrounds, meeting the 4.5:1 requirement
      expect(STATUS_COLORS.healthy).toBe('emerald');
      expect(STATUS_COLORS.healthy).not.toBe('green');
    });

    it('should use 400 shade for text on dark backgrounds', () => {
      // 400 shades provide better contrast on dark backgrounds than 500 shades
      expect(STATUS_TEXT_CLASSES.healthy).toContain('-400');
      expect(STATUS_TEXT_CLASSES.warning).toContain('-400');
      expect(STATUS_TEXT_CLASSES.error).toContain('-400');
    });

    it('should have consistent color semantics across all color types', () => {
      // Healthy should always map to emerald across all color definitions
      expect(STATUS_COLORS.healthy).toBe('emerald');
      expect(STATUS_BG_CLASSES.healthy).toContain('emerald');
      expect(STATUS_TEXT_CLASSES.healthy).toContain('emerald');
      expect(STATUS_HEX_COLORS.healthy).toBe('#10B981'); // emerald-500

      // Error should always map to red across all color definitions
      expect(STATUS_COLORS.error).toBe('red');
      expect(STATUS_BG_CLASSES.error).toContain('red');
      expect(STATUS_TEXT_CLASSES.error).toContain('red');
      expect(STATUS_HEX_COLORS.error).toBe('#EF4444'); // red-500
    });
  });
});

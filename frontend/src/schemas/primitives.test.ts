/**
 * Unit tests for Zod Schema Primitives.
 *
 * These tests verify that the reusable schema primitives work correctly
 * and provide consistent validation across the application.
 */

import { describe, expect, it } from 'vitest';

import {
  // ID Primitives
  uuid,
  cameraId,
  eventId,
  detectionId,
  zoneId,
  alertRuleId,
  entityId,
  batchId,
  // Risk Assessment
  riskScore,
  optionalRiskScore,
  riskLevel,
  optionalRiskLevel,
  RISK_SCORE_CONSTRAINTS,
  RISK_LEVEL_VALUES,
  // Confidence
  confidence,
  optionalConfidence,
  CONFIDENCE_CONSTRAINTS,
  // Timestamp
  timestamp,
  optionalTimestamp,
  isoDateString,
  // Object Types
  objectType,
  objectTypes,
  OBJECT_TYPE_VALUES,
  // Camera Status
  cameraStatus,
  CAMERA_STATUS_VALUES,
  // Alert Severity
  alertSeverity,
  ALERT_SEVERITY_VALUES,
  // Day of Week
  dayOfWeek,
  daysOfWeek,
  DAY_OF_WEEK_VALUES,
  // String Primitives
  nonEmptyString,
  stringWithLength,
  // Bounding Box
  boundingBox,
  normalizedCoordinate,
  // Pagination
  pageNumber,
  pageSize,
  totalCount,
  paginationCursor,
  // Time String
  timeString,
  optionalTimeString,
} from './primitives';

describe('Schema Primitives', () => {
  // ==========================================================================
  // ID Primitives
  // ==========================================================================
  describe('ID Primitives', () => {
    const validUuid = '550e8400-e29b-41d4-a716-446655440000';
    const invalidUuids = ['not-a-uuid', '123', '', '550e8400-e29b-41d4-a716'];

    describe('uuid', () => {
      it('should accept valid UUID', () => {
        const result = uuid.safeParse(validUuid);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data).toBe(validUuid);
        }
      });

      it('should reject invalid UUIDs', () => {
        for (const invalid of invalidUuids) {
          const result = uuid.safeParse(invalid);
          expect(result.success).toBe(false);
        }
      });
    });

    describe('cameraId', () => {
      it('should accept valid camera ID', () => {
        const result = cameraId.safeParse(validUuid);
        expect(result.success).toBe(true);
      });

      it('should reject invalid camera ID with proper error', () => {
        const result = cameraId.safeParse('invalid');
        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toBe('Invalid camera ID format');
        }
      });
    });

    describe('other ID schemas', () => {
      it('should validate eventId', () => {
        expect(eventId.safeParse(validUuid).success).toBe(true);
        expect(eventId.safeParse('invalid').success).toBe(false);
      });

      it('should validate detectionId', () => {
        expect(detectionId.safeParse(validUuid).success).toBe(true);
        expect(detectionId.safeParse('invalid').success).toBe(false);
      });

      it('should validate zoneId', () => {
        expect(zoneId.safeParse(validUuid).success).toBe(true);
        expect(zoneId.safeParse('invalid').success).toBe(false);
      });

      it('should validate alertRuleId', () => {
        expect(alertRuleId.safeParse(validUuid).success).toBe(true);
        expect(alertRuleId.safeParse('invalid').success).toBe(false);
      });

      it('should validate entityId', () => {
        expect(entityId.safeParse(validUuid).success).toBe(true);
        expect(entityId.safeParse('invalid').success).toBe(false);
      });

      it('should validate batchId', () => {
        expect(batchId.safeParse(validUuid).success).toBe(true);
        expect(batchId.safeParse('invalid').success).toBe(false);
      });
    });
  });

  // ==========================================================================
  // Risk Assessment Primitives
  // ==========================================================================
  describe('Risk Assessment Primitives', () => {
    describe('riskScore', () => {
      it('should accept valid scores (0-100)', () => {
        const validScores = [0, 1, 50, 99, 100];
        for (const score of validScores) {
          const result = riskScore.safeParse(score);
          expect(result.success).toBe(true);
          if (result.success) {
            expect(result.data).toBe(score);
          }
        }
      });

      it('should reject scores below minimum', () => {
        const result = riskScore.safeParse(-1);
        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toContain(String(RISK_SCORE_CONSTRAINTS.min));
        }
      });

      it('should reject scores above maximum', () => {
        const result = riskScore.safeParse(101);
        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toContain(String(RISK_SCORE_CONSTRAINTS.max));
        }
      });

      it('should reject non-integer values', () => {
        const result = riskScore.safeParse(50.5);
        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toContain('whole number');
        }
      });
    });

    describe('optionalRiskScore', () => {
      it('should accept valid scores', () => {
        expect(optionalRiskScore.safeParse(50).success).toBe(true);
      });

      it('should accept null', () => {
        const result = optionalRiskScore.safeParse(null);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data).toBeNull();
        }
      });

      it('should accept undefined', () => {
        const result = optionalRiskScore.safeParse(undefined);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data).toBeUndefined();
        }
      });
    });

    describe('riskLevel', () => {
      it('should accept all valid risk levels', () => {
        for (const level of RISK_LEVEL_VALUES) {
          const result = riskLevel.safeParse(level);
          expect(result.success).toBe(true);
          if (result.success) {
            expect(result.data).toBe(level);
          }
        }
      });

      it('should reject invalid risk levels', () => {
        const result = riskLevel.safeParse('invalid');
        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toContain('Invalid risk level');
        }
      });

      it('should have exactly 4 risk levels', () => {
        expect(RISK_LEVEL_VALUES).toEqual(['low', 'medium', 'high', 'critical']);
      });
    });

    describe('optionalRiskLevel', () => {
      it('should accept valid levels', () => {
        expect(optionalRiskLevel.safeParse('high').success).toBe(true);
      });

      it('should accept null', () => {
        const result = optionalRiskLevel.safeParse(null);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data).toBeNull();
        }
      });
    });
  });

  // ==========================================================================
  // Confidence Primitives
  // ==========================================================================
  describe('Confidence Primitives', () => {
    describe('confidence', () => {
      it('should accept valid confidence values (0-1)', () => {
        const validValues = [0, 0.5, 0.75, 1];
        for (const value of validValues) {
          const result = confidence.safeParse(value);
          expect(result.success).toBe(true);
          if (result.success) {
            expect(result.data).toBe(value);
          }
        }
      });

      it('should accept decimal values', () => {
        const result = confidence.safeParse(0.876);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data).toBe(0.876);
        }
      });

      it('should reject values below minimum', () => {
        const result = confidence.safeParse(-0.1);
        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toContain(String(CONFIDENCE_CONSTRAINTS.min));
        }
      });

      it('should reject values above maximum', () => {
        const result = confidence.safeParse(1.1);
        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toContain(String(CONFIDENCE_CONSTRAINTS.max));
        }
      });
    });

    describe('optionalConfidence', () => {
      it('should accept valid confidence', () => {
        expect(optionalConfidence.safeParse(0.8).success).toBe(true);
      });

      it('should accept null', () => {
        const result = optionalConfidence.safeParse(null);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data).toBeNull();
        }
      });
    });
  });

  // ==========================================================================
  // Timestamp Primitives
  // ==========================================================================
  describe('Timestamp Primitives', () => {
    describe('timestamp', () => {
      it('should accept Date objects', () => {
        const date = new Date();
        const result = timestamp.safeParse(date);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data).toEqual(date);
        }
      });

      it('should coerce ISO date strings to Date', () => {
        const isoString = '2024-01-15T10:30:00Z';
        const result = timestamp.safeParse(isoString);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data).toBeInstanceOf(Date);
          // Note: toISOString() always includes milliseconds (.000), so we compare getTime()
          expect(result.data.getTime()).toBe(new Date(isoString).getTime());
        }
      });

      it('should coerce Unix timestamps to Date', () => {
        const unixMs = 1705316400000;
        const result = timestamp.safeParse(unixMs);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data).toBeInstanceOf(Date);
        }
      });

      it('should reject invalid date strings', () => {
        const result = timestamp.safeParse('not-a-date');
        expect(result.success).toBe(false);
      });
    });

    describe('optionalTimestamp', () => {
      it('should accept valid timestamps', () => {
        expect(optionalTimestamp.safeParse(new Date()).success).toBe(true);
      });

      it('should accept null', () => {
        const result = optionalTimestamp.safeParse(null);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data).toBeNull();
        }
      });
    });

    describe('isoDateString', () => {
      it('should accept valid ISO date strings with Z suffix', () => {
        // Zod's datetime() is strict about format - requires timezone
        const validStrings = [
          '2024-01-15T10:30:00Z',
          '2024-01-15T10:30:00.000Z',
        ];
        for (const str of validStrings) {
          const result = isoDateString.safeParse(str);
          expect(result.success).toBe(true);
        }
      });

      it('should reject invalid ISO date strings', () => {
        const result = isoDateString.safeParse('2024-01-15');
        expect(result.success).toBe(false);
      });

      it('should reject date strings with offset format', () => {
        // Zod's datetime() with default options doesn't accept offset format like +00:00
        const result = isoDateString.safeParse('2024-01-15T10:30:00+00:00');
        expect(result.success).toBe(false);
      });
    });
  });

  // ==========================================================================
  // Object Type Primitives
  // ==========================================================================
  describe('Object Type Primitives', () => {
    describe('objectType', () => {
      it('should accept all valid object types', () => {
        for (const type of OBJECT_TYPE_VALUES) {
          const result = objectType.safeParse(type);
          expect(result.success).toBe(true);
          if (result.success) {
            expect(result.data).toBe(type);
          }
        }
      });

      it('should reject invalid object types', () => {
        const result = objectType.safeParse('invalid');
        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toContain('Invalid object type');
        }
      });

      it('should have exactly 4 object types', () => {
        expect(OBJECT_TYPE_VALUES).toEqual(['person', 'vehicle', 'animal', 'package']);
      });
    });

    describe('objectTypes', () => {
      it('should accept array of valid object types', () => {
        const result = objectTypes.safeParse(['person', 'vehicle']);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data).toEqual(['person', 'vehicle']);
        }
      });

      it('should accept empty array', () => {
        const result = objectTypes.safeParse([]);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data).toEqual([]);
        }
      });

      it('should reject array with invalid types', () => {
        const result = objectTypes.safeParse(['person', 'invalid']);
        expect(result.success).toBe(false);
      });
    });
  });

  // ==========================================================================
  // Camera Status Primitives
  // ==========================================================================
  describe('Camera Status Primitives', () => {
    describe('cameraStatus', () => {
      it('should accept all valid camera statuses', () => {
        for (const status of CAMERA_STATUS_VALUES) {
          const result = cameraStatus.safeParse(status);
          expect(result.success).toBe(true);
          if (result.success) {
            expect(result.data).toBe(status);
          }
        }
      });

      it('should reject invalid camera status', () => {
        const result = cameraStatus.safeParse('invalid');
        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toContain('Invalid camera status');
        }
      });

      it('should have exactly 4 camera statuses', () => {
        expect(CAMERA_STATUS_VALUES).toEqual(['online', 'offline', 'error', 'unknown']);
      });
    });
  });

  // ==========================================================================
  // Alert Severity Primitives
  // ==========================================================================
  describe('Alert Severity Primitives', () => {
    describe('alertSeverity', () => {
      it('should accept all valid alert severities', () => {
        for (const severity of ALERT_SEVERITY_VALUES) {
          const result = alertSeverity.safeParse(severity);
          expect(result.success).toBe(true);
          if (result.success) {
            expect(result.data).toBe(severity);
          }
        }
      });

      it('should reject invalid alert severity', () => {
        const result = alertSeverity.safeParse('invalid');
        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toContain('Invalid alert severity');
        }
      });

      it('should have exactly 4 alert severities', () => {
        expect(ALERT_SEVERITY_VALUES).toEqual(['low', 'medium', 'high', 'critical']);
      });
    });
  });

  // ==========================================================================
  // Day of Week Primitives
  // ==========================================================================
  describe('Day of Week Primitives', () => {
    describe('dayOfWeek', () => {
      it('should accept all valid days', () => {
        for (const day of DAY_OF_WEEK_VALUES) {
          const result = dayOfWeek.safeParse(day);
          expect(result.success).toBe(true);
          if (result.success) {
            expect(result.data).toBe(day);
          }
        }
      });

      it('should reject invalid days', () => {
        const result = dayOfWeek.safeParse('invalid');
        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toContain('Invalid day');
        }
      });

      it('should have exactly 7 days', () => {
        expect(DAY_OF_WEEK_VALUES).toEqual([
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

    describe('daysOfWeek', () => {
      it('should accept array of valid days', () => {
        const result = daysOfWeek.safeParse(['monday', 'wednesday', 'friday']);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data).toEqual(['monday', 'wednesday', 'friday']);
        }
      });

      it('should accept empty array', () => {
        const result = daysOfWeek.safeParse([]);
        expect(result.success).toBe(true);
      });

      it('should reject array with invalid days', () => {
        const result = daysOfWeek.safeParse(['monday', 'invalid']);
        expect(result.success).toBe(false);
      });
    });
  });

  // ==========================================================================
  // String Primitives
  // ==========================================================================
  describe('String Primitives', () => {
    describe('nonEmptyString', () => {
      it('should accept non-empty strings', () => {
        const result = nonEmptyString.safeParse('hello');
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data).toBe('hello');
        }
      });

      it('should reject empty strings', () => {
        const result = nonEmptyString.safeParse('');
        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toBe('This field is required');
        }
      });
    });

    describe('stringWithLength', () => {
      it('should create schema with min length constraint', () => {
        const schema = stringWithLength({ minLength: 5 }, 'Name');
        expect(schema.safeParse('hello').success).toBe(true);
        expect(schema.safeParse('hi').success).toBe(false);
      });

      it('should create schema with max length constraint', () => {
        const schema = stringWithLength({ maxLength: 10 }, 'Name');
        expect(schema.safeParse('hello').success).toBe(true);
        expect(schema.safeParse('hello world!').success).toBe(false);
      });

      it('should create schema with both constraints', () => {
        const schema = stringWithLength({ minLength: 3, maxLength: 10 }, 'Name');
        expect(schema.safeParse('ab').success).toBe(false);
        expect(schema.safeParse('abc').success).toBe(true);
        expect(schema.safeParse('hello').success).toBe(true);
        expect(schema.safeParse('hello world!').success).toBe(false);
      });

      it('should use "required" message for minLength=1', () => {
        const schema = stringWithLength({ minLength: 1 }, 'Name');
        const result = schema.safeParse('');
        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toBe('Name is required');
        }
      });
    });
  });

  // ==========================================================================
  // Bounding Box Primitives
  // ==========================================================================
  describe('Bounding Box Primitives', () => {
    describe('normalizedCoordinate', () => {
      it('should accept values between 0 and 1', () => {
        const validValues = [0, 0.5, 1];
        for (const value of validValues) {
          expect(normalizedCoordinate.safeParse(value).success).toBe(true);
        }
      });

      it('should reject values outside range', () => {
        expect(normalizedCoordinate.safeParse(-0.1).success).toBe(false);
        expect(normalizedCoordinate.safeParse(1.1).success).toBe(false);
      });
    });

    describe('boundingBox', () => {
      it('should accept valid bounding box', () => {
        const result = boundingBox.safeParse([0.1, 0.2, 0.5, 0.8]);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data).toEqual([0.1, 0.2, 0.5, 0.8]);
        }
      });

      it('should reject bounding box with wrong number of elements', () => {
        expect(boundingBox.safeParse([0.1, 0.2, 0.5]).success).toBe(false);
        expect(boundingBox.safeParse([0.1, 0.2, 0.5, 0.8, 0.9]).success).toBe(false);
      });

      it('should reject bounding box with out-of-range values', () => {
        expect(boundingBox.safeParse([0.1, 0.2, 1.5, 0.8]).success).toBe(false);
      });
    });
  });

  // ==========================================================================
  // Pagination Primitives
  // ==========================================================================
  describe('Pagination Primitives', () => {
    describe('pageNumber', () => {
      it('should accept valid page numbers', () => {
        const result = pageNumber.safeParse(1);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data).toBe(1);
        }
      });

      it('should reject page number less than 1', () => {
        expect(pageNumber.safeParse(0).success).toBe(false);
        expect(pageNumber.safeParse(-1).success).toBe(false);
      });

      it('should reject non-integer page numbers', () => {
        expect(pageNumber.safeParse(1.5).success).toBe(false);
      });
    });

    describe('pageSize', () => {
      it('should accept valid page sizes', () => {
        const validSizes = [1, 10, 50, 100];
        for (const size of validSizes) {
          expect(pageSize.safeParse(size).success).toBe(true);
        }
      });

      it('should reject page size less than 1', () => {
        expect(pageSize.safeParse(0).success).toBe(false);
      });

      it('should reject page size greater than 100', () => {
        expect(pageSize.safeParse(101).success).toBe(false);
      });
    });

    describe('totalCount', () => {
      it('should accept non-negative integers', () => {
        expect(totalCount.safeParse(0).success).toBe(true);
        expect(totalCount.safeParse(100).success).toBe(true);
      });

      it('should reject negative values', () => {
        expect(totalCount.safeParse(-1).success).toBe(false);
      });
    });

    describe('paginationCursor', () => {
      it('should accept string cursor', () => {
        expect(paginationCursor.safeParse('cursor123').success).toBe(true);
      });

      it('should accept null', () => {
        expect(paginationCursor.safeParse(null).success).toBe(true);
      });

      it('should accept undefined', () => {
        expect(paginationCursor.safeParse(undefined).success).toBe(true);
      });
    });
  });

  // ==========================================================================
  // Time String Primitives
  // ==========================================================================
  describe('Time String Primitives', () => {
    describe('timeString', () => {
      it('should accept valid time strings', () => {
        const validTimes = ['00:00', '12:30', '23:59', '06:00'];
        for (const time of validTimes) {
          const result = timeString.safeParse(time);
          expect(result.success).toBe(true);
          if (result.success) {
            expect(result.data).toBe(time);
          }
        }
      });

      it('should reject invalid format (wrong length)', () => {
        const result = timeString.safeParse('1:30');
        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toContain('Invalid time format');
        }
      });

      it('should reject invalid format (no colon)', () => {
        const result = timeString.safeParse('12-30');
        expect(result.success).toBe(false);
      });

      it('should reject hours out of range (24+)', () => {
        const result = timeString.safeParse('24:00');
        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toContain('Invalid hours');
        }
      });

      it('should reject minutes out of range (60+)', () => {
        const result = timeString.safeParse('12:60');
        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toContain('Invalid minutes');
        }
      });

      it('should reject non-numeric time values', () => {
        const result = timeString.safeParse('ab:cd');
        expect(result.success).toBe(false);
      });
    });

    describe('optionalTimeString', () => {
      it('should accept valid time strings', () => {
        expect(optionalTimeString.safeParse('12:30').success).toBe(true);
      });

      it('should accept null', () => {
        const result = optionalTimeString.safeParse(null);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data).toBeNull();
        }
      });
    });
  });

  // ==========================================================================
  // Constants Alignment
  // ==========================================================================
  describe('Constants Alignment', () => {
    it('should have correct risk score constraints', () => {
      expect(RISK_SCORE_CONSTRAINTS.min).toBe(0);
      expect(RISK_SCORE_CONSTRAINTS.max).toBe(100);
    });

    it('should have correct confidence constraints', () => {
      expect(CONFIDENCE_CONSTRAINTS.min).toBe(0);
      expect(CONFIDENCE_CONSTRAINTS.max).toBe(1);
    });
  });
});

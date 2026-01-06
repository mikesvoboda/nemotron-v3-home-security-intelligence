/**
 * Tests for Branded Types
 *
 * These tests validate the runtime behavior of branded type utilities.
 * Note: Compile-time type safety is tested implicitly by TypeScript's type checker.
 */

import { describe, expect, it } from 'vitest';

import {
  type AlertRuleId,
  type AuditLogId,
  type CameraId,
  type DetectionId,
  type EntityId,
  type EntityIdType,
  type EventId,
  type Unbrand,
  type ZoneId,
  asAlertRuleId,
  asAuditLogId,
  asCameraId,
  asDetectionId,
  asEntityId,
  asEventId,
  asZoneId,
  isAlertRuleId,
  isAuditLogId,
  isCameraId,
  isDetectionId,
  isEntityId,
  isEventId,
  isZoneId,
} from './branded';

describe('Branded Types', () => {
  describe('Constructor Functions', () => {
    describe('asCameraId', () => {
      it('should create a CameraId from a string', () => {
        const id = asCameraId('front_door');
        expect(id).toBe('front_door');
      });

      it('should preserve the original string value', () => {
        const original = 'backyard_camera';
        const id = asCameraId(original);
        expect(id).toBe(original);
        expect(typeof id).toBe('string');
      });
    });

    describe('asEventId', () => {
      it('should create an EventId from a number', () => {
        const id = asEventId(123);
        expect(id).toBe(123);
      });

      it('should preserve the original numeric value', () => {
        const original = 456;
        const id = asEventId(original);
        expect(id).toBe(original);
        expect(typeof id).toBe('number');
      });
    });

    describe('asDetectionId', () => {
      it('should create a DetectionId from a number', () => {
        const id = asDetectionId(789);
        expect(id).toBe(789);
      });

      it('should preserve the original numeric value', () => {
        const original = 101112;
        const id = asDetectionId(original);
        expect(id).toBe(original);
        expect(typeof id).toBe('number');
      });
    });

    describe('asZoneId', () => {
      it('should create a ZoneId from a number', () => {
        const id = asZoneId(42);
        expect(id).toBe(42);
      });

      it('should preserve the original numeric value', () => {
        const original = 999;
        const id = asZoneId(original);
        expect(id).toBe(original);
        expect(typeof id).toBe('number');
      });
    });

    describe('asAlertRuleId', () => {
      it('should create an AlertRuleId from a number', () => {
        const id = asAlertRuleId(55);
        expect(id).toBe(55);
      });

      it('should preserve the original numeric value', () => {
        const original = 77;
        const id = asAlertRuleId(original);
        expect(id).toBe(original);
        expect(typeof id).toBe('number');
      });
    });

    describe('asEntityId', () => {
      it('should create an EntityId from a string', () => {
        const id = asEntityId('camera-123');
        expect(id).toBe('camera-123');
      });

      it('should create an EntityId from a number', () => {
        const id = asEntityId(456);
        expect(id).toBe(456);
      });

      it('should preserve the original value type for strings', () => {
        const original = 'entity-abc';
        const id = asEntityId(original);
        expect(id).toBe(original);
        expect(typeof id).toBe('string');
      });

      it('should preserve the original value type for numbers', () => {
        const original = 789;
        const id = asEntityId(original);
        expect(id).toBe(original);
        expect(typeof id).toBe('number');
      });
    });

    describe('asAuditLogId', () => {
      it('should create an AuditLogId from a number', () => {
        const id = asAuditLogId(888);
        expect(id).toBe(888);
      });

      it('should preserve the original numeric value', () => {
        const original = 1234567;
        const id = asAuditLogId(original);
        expect(id).toBe(original);
        expect(typeof id).toBe('number');
      });
    });
  });

  describe('Type Guards', () => {
    describe('isCameraId', () => {
      it('should return true for non-empty strings', () => {
        expect(isCameraId('front_door')).toBe(true);
        expect(isCameraId('a')).toBe(true);
        expect(isCameraId('camera-with-dashes')).toBe(true);
      });

      it('should return false for empty strings', () => {
        expect(isCameraId('')).toBe(false);
      });

      it('should return false for non-string values', () => {
        expect(isCameraId(123)).toBe(false);
        expect(isCameraId(null)).toBe(false);
        expect(isCameraId(undefined)).toBe(false);
        expect(isCameraId({})).toBe(false);
        expect(isCameraId([])).toBe(false);
        expect(isCameraId(true)).toBe(false);
      });

      it('should narrow type when used as type guard', () => {
        const value: unknown = 'test-camera';
        if (isCameraId(value)) {
          // TypeScript should recognize this as CameraId
          const _cameraId: CameraId = value;
          expect(_cameraId).toBe('test-camera');
        }
      });
    });

    describe('isEventId', () => {
      it('should return true for non-negative integers', () => {
        expect(isEventId(0)).toBe(true);
        expect(isEventId(1)).toBe(true);
        expect(isEventId(123)).toBe(true);
        expect(isEventId(1000000)).toBe(true);
      });

      it('should return false for negative numbers', () => {
        expect(isEventId(-1)).toBe(false);
        expect(isEventId(-100)).toBe(false);
      });

      it('should return false for non-integers', () => {
        expect(isEventId(1.5)).toBe(false);
        expect(isEventId(3.14159)).toBe(false);
        expect(isEventId(NaN)).toBe(false);
        expect(isEventId(Infinity)).toBe(false);
      });

      it('should return false for non-number values', () => {
        expect(isEventId('123')).toBe(false);
        expect(isEventId(null)).toBe(false);
        expect(isEventId(undefined)).toBe(false);
        expect(isEventId({})).toBe(false);
      });

      it('should narrow type when used as type guard', () => {
        const value: unknown = 42;
        if (isEventId(value)) {
          const _eventId: EventId = value;
          expect(_eventId).toBe(42);
        }
      });
    });

    describe('isDetectionId', () => {
      it('should return true for non-negative integers', () => {
        expect(isDetectionId(0)).toBe(true);
        expect(isDetectionId(1)).toBe(true);
        expect(isDetectionId(456)).toBe(true);
      });

      it('should return false for negative numbers', () => {
        expect(isDetectionId(-1)).toBe(false);
      });

      it('should return false for non-integers', () => {
        expect(isDetectionId(1.5)).toBe(false);
        expect(isDetectionId(NaN)).toBe(false);
      });

      it('should return false for non-number values', () => {
        expect(isDetectionId('456')).toBe(false);
        expect(isDetectionId(null)).toBe(false);
      });

      it('should narrow type when used as type guard', () => {
        const value: unknown = 789;
        if (isDetectionId(value)) {
          const _detectionId: DetectionId = value;
          expect(_detectionId).toBe(789);
        }
      });
    });

    describe('isZoneId', () => {
      it('should return true for non-negative integers', () => {
        expect(isZoneId(0)).toBe(true);
        expect(isZoneId(99)).toBe(true);
      });

      it('should return false for negative numbers', () => {
        expect(isZoneId(-1)).toBe(false);
      });

      it('should return false for non-integers', () => {
        expect(isZoneId(1.1)).toBe(false);
      });

      it('should return false for non-number values', () => {
        expect(isZoneId('zone-1')).toBe(false);
      });

      it('should narrow type when used as type guard', () => {
        const value: unknown = 42;
        if (isZoneId(value)) {
          const _zoneId: ZoneId = value;
          expect(_zoneId).toBe(42);
        }
      });
    });

    describe('isAlertRuleId', () => {
      it('should return true for non-negative integers', () => {
        expect(isAlertRuleId(0)).toBe(true);
        expect(isAlertRuleId(55)).toBe(true);
      });

      it('should return false for negative numbers', () => {
        expect(isAlertRuleId(-5)).toBe(false);
      });

      it('should return false for non-integers', () => {
        expect(isAlertRuleId(5.5)).toBe(false);
      });

      it('should return false for non-number values', () => {
        expect(isAlertRuleId('rule-1')).toBe(false);
      });

      it('should narrow type when used as type guard', () => {
        const value: unknown = 77;
        if (isAlertRuleId(value)) {
          const _alertRuleId: AlertRuleId = value;
          expect(_alertRuleId).toBe(77);
        }
      });
    });

    describe('isEntityId', () => {
      it('should return true for non-empty strings', () => {
        expect(isEntityId('camera-123')).toBe(true);
        expect(isEntityId('x')).toBe(true);
      });

      it('should return true for non-negative integers', () => {
        expect(isEntityId(0)).toBe(true);
        expect(isEntityId(123)).toBe(true);
      });

      it('should return false for empty strings', () => {
        expect(isEntityId('')).toBe(false);
      });

      it('should return false for negative numbers', () => {
        expect(isEntityId(-1)).toBe(false);
      });

      it('should return false for non-integers', () => {
        expect(isEntityId(1.5)).toBe(false);
      });

      it('should return false for other types', () => {
        expect(isEntityId(null)).toBe(false);
        expect(isEntityId(undefined)).toBe(false);
        expect(isEntityId({})).toBe(false);
        expect(isEntityId([])).toBe(false);
        expect(isEntityId(true)).toBe(false);
      });

      it('should narrow type when used as type guard', () => {
        const stringValue: unknown = 'entity-abc';
        if (isEntityId(stringValue)) {
          const _entityId: EntityId = stringValue;
          expect(_entityId).toBe('entity-abc');
        }

        const numberValue: unknown = 456;
        if (isEntityId(numberValue)) {
          const _entityId: EntityId = numberValue;
          expect(_entityId).toBe(456);
        }
      });
    });

    describe('isAuditLogId', () => {
      it('should return true for non-negative integers', () => {
        expect(isAuditLogId(0)).toBe(true);
        expect(isAuditLogId(888)).toBe(true);
      });

      it('should return false for negative numbers', () => {
        expect(isAuditLogId(-100)).toBe(false);
      });

      it('should return false for non-integers', () => {
        expect(isAuditLogId(8.88)).toBe(false);
      });

      it('should return false for non-number values', () => {
        expect(isAuditLogId('audit-1')).toBe(false);
      });

      it('should narrow type when used as type guard', () => {
        const value: unknown = 999;
        if (isAuditLogId(value)) {
          const _auditLogId: AuditLogId = value;
          expect(_auditLogId).toBe(999);
        }
      });
    });
  });

  describe('Type Compatibility', () => {
    // These tests verify that branded types behave correctly at runtime
    // while providing compile-time safety

    it('should allow using branded types in operations that accept their base type', () => {
      const cameraId = asCameraId('test');
      const eventId = asEventId(123);

      // String operations should work on CameraId
      expect(cameraId.toUpperCase()).toBe('TEST');
      expect(cameraId.length).toBe(4);

      // Number operations should work on EventId
      expect(eventId + 1).toBe(124);
      expect(eventId * 2).toBe(246);
    });

    it('should work with array methods', () => {
      const cameraIds = [
        asCameraId('cam1'),
        asCameraId('cam2'),
        asCameraId('cam3'),
      ];
      const eventIds = [asEventId(1), asEventId(2), asEventId(3)];

      expect(cameraIds.includes(asCameraId('cam2'))).toBe(true);
      expect(eventIds.includes(asEventId(2))).toBe(true);
    });

    it('should work with Map and Set collections', () => {
      const cameraMap = new Map<CameraId, string>();
      const cameraId = asCameraId('front_door');
      cameraMap.set(cameraId, 'Front Door Camera');

      expect(cameraMap.get(cameraId)).toBe('Front Door Camera');

      const eventSet = new Set<EventId>();
      const eventId = asEventId(123);
      eventSet.add(eventId);

      expect(eventSet.has(eventId)).toBe(true);
    });

    it('should serialize correctly to JSON', () => {
      const data = {
        cameraId: asCameraId('test-camera'),
        eventId: asEventId(456),
      };

      const json = JSON.stringify(data);
      const parsed = JSON.parse(json) as { cameraId: string; eventId: number };

      expect(parsed.cameraId).toBe('test-camera');
      expect(parsed.eventId).toBe(456);
    });
  });

  describe('Utility Types', () => {
    // These are compile-time checks - if they compile, they pass
    // We include runtime assertions for completeness

    it('Unbrand should extract the base type', () => {
      // These type assertions verify that Unbrand works correctly
      // If the types are wrong, TypeScript will fail to compile

      // Test string-based ID
      const cameraId = asCameraId('test');
      const unbranded: Unbrand<CameraId> = cameraId;
      expect(typeof unbranded).toBe('string');

      // Test number-based ID
      const eventId = asEventId(123);
      const unbrandedNum: Unbrand<EventId> = eventId;
      expect(typeof unbrandedNum).toBe('number');
    });

    it('EntityIdType should map entity names to ID types', () => {
      // These compile-time checks verify the EntityIdMap works
      const _camera: EntityIdType<'camera'> = asCameraId('test');
      const _event: EntityIdType<'event'> = asEventId(1);
      const _detection: EntityIdType<'detection'> = asDetectionId(2);
      const _zone: EntityIdType<'zone'> = asZoneId(3);
      const _alertRule: EntityIdType<'alertRule'> = asAlertRuleId(4);
      const _auditLog: EntityIdType<'auditLog'> = asAuditLogId(5);

      // Runtime check that values are correct
      expect(_camera).toBe('test');
      expect(_event).toBe(1);
      expect(_detection).toBe(2);
      expect(_zone).toBe(3);
      expect(_alertRule).toBe(4);
      expect(_auditLog).toBe(5);
    });
  });

  describe('Edge Cases', () => {
    it('should handle zero as valid ID for numeric types', () => {
      expect(isEventId(0)).toBe(true);
      expect(isDetectionId(0)).toBe(true);
      expect(isZoneId(0)).toBe(true);
      expect(isAlertRuleId(0)).toBe(true);
      expect(isAuditLogId(0)).toBe(true);
      expect(isEntityId(0)).toBe(true);
    });

    it('should handle very large numbers', () => {
      const largeId = Number.MAX_SAFE_INTEGER;
      expect(isEventId(largeId)).toBe(true);
      expect(asEventId(largeId)).toBe(largeId);
    });

    it('should handle special string characters in CameraId', () => {
      const specialIds = [
        'camera-with-dashes',
        'camera_with_underscores',
        'camera.with.dots',
        'camera:with:colons',
        'CamelCaseCamera',
        'camera/with/slashes',
      ];

      specialIds.forEach((id) => {
        expect(isCameraId(id)).toBe(true);
        expect(asCameraId(id)).toBe(id);
      });
    });

    it('should handle unicode strings in CameraId', () => {
      const unicodeId = asCameraId('camera-\u4E2D\u6587');
      expect(unicodeId).toBe('camera-\u4E2D\u6587');
      expect(isCameraId(unicodeId)).toBe(true);
    });
  });
});

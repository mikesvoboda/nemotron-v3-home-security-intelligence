/**
 * Tests for Branded Types
 *
 * These tests verify the runtime behavior of branded type factory functions
 * and utility functions. Type safety is verified at compile time.
 */

import { describe, it, expect } from 'vitest';

import {
  createCameraId,
  createEventId,
  createDetectionId,
  createZoneId,
  createAlertRuleId,
  createEntityId,
  createBatchId,
  unwrapStringId,
  unwrapNumberId,
  isSameId,
  isSameNumericId,
  type CameraId,
  type EventId,
  type DetectionId,
  type ZoneId,
  type AlertRuleId,
  type EntityId,
  type BatchId,
} from './branded';

describe('Branded Types', () => {
  describe('createCameraId', () => {
    it('creates a branded CameraId from a valid string', () => {
      const id = createCameraId('abc-123-def');
      expect(id).toBe('abc-123-def');
    });

    it('creates a CameraId from a UUID', () => {
      const uuid = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890';
      const id = createCameraId(uuid);
      expect(id).toBe(uuid);
    });

    it('throws for empty string', () => {
      expect(() => createCameraId('')).toThrow('Invalid CameraId');
    });

    it('throws for non-string input', () => {
      expect(() => createCameraId(123 as unknown as string)).toThrow('Invalid CameraId');
      expect(() => createCameraId(null as unknown as string)).toThrow('Invalid CameraId');
      expect(() => createCameraId(undefined as unknown as string)).toThrow('Invalid CameraId');
    });
  });

  describe('createEventId', () => {
    it('creates a branded EventId from a valid number', () => {
      const id = createEventId(123);
      expect(id).toBe(123);
    });

    it('creates an EventId from zero', () => {
      const id = createEventId(0);
      expect(id).toBe(0);
    });

    it('creates an EventId from a large number', () => {
      const id = createEventId(999999);
      expect(id).toBe(999999);
    });

    it('throws for negative number', () => {
      expect(() => createEventId(-1)).toThrow('Invalid EventId');
    });

    it('throws for NaN', () => {
      expect(() => createEventId(NaN)).toThrow('Invalid EventId');
    });

    it('throws for Infinity', () => {
      expect(() => createEventId(Infinity)).toThrow('Invalid EventId');
    });

    it('throws for non-number input', () => {
      expect(() => createEventId('123' as unknown as number)).toThrow('Invalid EventId');
      expect(() => createEventId(null as unknown as number)).toThrow('Invalid EventId');
    });
  });

  describe('createDetectionId', () => {
    it('creates a branded DetectionId from a valid number', () => {
      const id = createDetectionId(456);
      expect(id).toBe(456);
    });

    it('creates a DetectionId from zero', () => {
      const id = createDetectionId(0);
      expect(id).toBe(0);
    });

    it('throws for negative number', () => {
      expect(() => createDetectionId(-1)).toThrow('Invalid DetectionId');
    });

    it('throws for NaN', () => {
      expect(() => createDetectionId(NaN)).toThrow('Invalid DetectionId');
    });
  });

  describe('createZoneId', () => {
    it('creates a branded ZoneId from a valid string', () => {
      const id = createZoneId('zone-uuid-123');
      expect(id).toBe('zone-uuid-123');
    });

    it('throws for empty string', () => {
      expect(() => createZoneId('')).toThrow('Invalid ZoneId');
    });
  });

  describe('createAlertRuleId', () => {
    it('creates a branded AlertRuleId from a valid string', () => {
      const id = createAlertRuleId('alert-rule-uuid');
      expect(id).toBe('alert-rule-uuid');
    });

    it('throws for empty string', () => {
      expect(() => createAlertRuleId('')).toThrow('Invalid AlertRuleId');
    });
  });

  describe('createEntityId', () => {
    it('creates a branded EntityId from a valid string', () => {
      const id = createEntityId('entity-uuid');
      expect(id).toBe('entity-uuid');
    });

    it('throws for empty string', () => {
      expect(() => createEntityId('')).toThrow('Invalid EntityId');
    });
  });

  describe('createBatchId', () => {
    it('creates a branded BatchId from a valid string', () => {
      const id = createBatchId('batch-uuid');
      expect(id).toBe('batch-uuid');
    });

    it('throws for empty string', () => {
      expect(() => createBatchId('')).toThrow('Invalid BatchId');
    });
  });

  describe('unwrapStringId', () => {
    it('extracts the raw string from a CameraId', () => {
      const id = createCameraId('camera-123');
      const raw: string = unwrapStringId(id);
      expect(raw).toBe('camera-123');
    });

    it('extracts the raw string from a ZoneId', () => {
      const id = createZoneId('zone-456');
      const raw: string = unwrapStringId(id);
      expect(raw).toBe('zone-456');
    });

    it('extracts the raw string from an AlertRuleId', () => {
      const id = createAlertRuleId('rule-789');
      const raw: string = unwrapStringId(id);
      expect(raw).toBe('rule-789');
    });

    it('extracts the raw string from an EntityId', () => {
      const id = createEntityId('entity-abc');
      const raw: string = unwrapStringId(id);
      expect(raw).toBe('entity-abc');
    });

    it('extracts the raw string from a BatchId', () => {
      const id = createBatchId('batch-def');
      const raw: string = unwrapStringId(id);
      expect(raw).toBe('batch-def');
    });
  });

  describe('unwrapNumberId', () => {
    it('extracts the raw number from an EventId', () => {
      const id = createEventId(123);
      const raw: number = unwrapNumberId(id);
      expect(raw).toBe(123);
    });

    it('extracts the raw number from a DetectionId', () => {
      const id = createDetectionId(456);
      const raw: number = unwrapNumberId(id);
      expect(raw).toBe(456);
    });
  });

  describe('isSameId', () => {
    it('returns true for equal CameraIds', () => {
      const id1 = createCameraId('camera-123');
      const id2 = createCameraId('camera-123');
      expect(isSameId(id1, id2)).toBe(true);
    });

    it('returns false for different CameraIds', () => {
      const id1 = createCameraId('camera-123');
      const id2 = createCameraId('camera-456');
      expect(isSameId(id1, id2)).toBe(false);
    });

    it('returns true for equal ZoneIds', () => {
      const id1 = createZoneId('zone-abc');
      const id2 = createZoneId('zone-abc');
      expect(isSameId(id1, id2)).toBe(true);
    });
  });

  describe('isSameNumericId', () => {
    it('returns true for equal EventIds', () => {
      const id1 = createEventId(100);
      const id2 = createEventId(100);
      expect(isSameNumericId(id1, id2)).toBe(true);
    });

    it('returns false for different EventIds', () => {
      const id1 = createEventId(100);
      const id2 = createEventId(200);
      expect(isSameNumericId(id1, id2)).toBe(false);
    });

    it('returns true for equal DetectionIds', () => {
      const id1 = createDetectionId(500);
      const id2 = createDetectionId(500);
      expect(isSameNumericId(id1, id2)).toBe(true);
    });
  });

  describe('Type Safety (compile-time)', () => {
    /**
     * These tests verify that the types are correctly branded.
     * The actual type checking happens at compile time - if these tests
     * compile successfully, the type system is working correctly.
     */

    it('allows CameraId where string is expected via unwrap', () => {
      const id: CameraId = createCameraId('test');
      const str: string = unwrapStringId(id);
      expect(str).toBe('test');
    });

    it('allows EventId where number is expected via unwrap', () => {
      const id: EventId = createEventId(42);
      const num: number = unwrapNumberId(id);
      expect(num).toBe(42);
    });

    it('allows DetectionId where number is expected via unwrap', () => {
      const id: DetectionId = createDetectionId(99);
      const num: number = unwrapNumberId(id);
      expect(num).toBe(99);
    });

    // Type annotations verify compile-time type safety
    it('creates properly typed IDs', () => {
      const cameraId: CameraId = createCameraId('cam');
      const eventId: EventId = createEventId(1);
      const detectionId: DetectionId = createDetectionId(2);
      const zoneId: ZoneId = createZoneId('zone');
      const alertRuleId: AlertRuleId = createAlertRuleId('rule');
      const entityId: EntityId = createEntityId('entity');
      const batchId: BatchId = createBatchId('batch');

      // These should all be defined
      expect(cameraId).toBeDefined();
      expect(eventId).toBeDefined();
      expect(detectionId).toBeDefined();
      expect(zoneId).toBeDefined();
      expect(alertRuleId).toBeDefined();
      expect(entityId).toBeDefined();
      expect(batchId).toBeDefined();
    });
  });
});

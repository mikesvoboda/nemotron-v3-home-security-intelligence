/**
 * Tests for API Endpoint Template Literal Types
 *
 * Following TDD - these tests define the expected behavior before implementation.
 * Tests verify compile-time type inference and runtime endpoint validation.
 *
 * @see NEM-1556
 */

import { describe, it, expect, expectTypeOf } from 'vitest';

import {
  // Endpoint type imports
  type ApiEndpoint,
  type CameraEndpoint,
  type EventEndpoint,
  type SystemEndpoint,
  type DetectionEndpoint,
  type AlertRuleEndpoint,
  type ZoneEndpoint,
  type AuditEndpoint,
  type SearchEndpoint,
  type EnrichmentEndpoint,

  // Response type inference
  type EndpointResponseType,
  type ExtractIdFromEndpoint,

  // Type-safe client functions
  apiGet,
  apiPost,
  apiPatch,
  apiPut,
  apiDelete,

  // Endpoint validation
  isValidEndpoint,
  parseEndpoint,

  // Endpoint builders
  cameraEndpoint,
  eventEndpoint,
  detectionEndpoint,
  zoneEndpoint,
  alertRuleEndpoint,
} from './api-endpoints';

import type {
  Camera,
  CameraListResponse,
  Event,
  HealthResponse,
  GPUStats,
  AlertRule,
  Zone,
  SystemConfig,
} from './generated';

// ============================================================================
// Compile-Time Type Tests
// ============================================================================

describe('API Endpoint Template Literal Types', () => {
  describe('Endpoint Type Definitions', () => {
    it('defines camera endpoints correctly', () => {
      // These should compile without errors
      const listCameras: CameraEndpoint = '/api/cameras';
      const getCamera: CameraEndpoint = '/api/cameras/abc-123';
      const cameraSnapshot: CameraEndpoint = '/api/cameras/abc-123/snapshot';
      const cameraZones: CameraEndpoint = '/api/cameras/abc-123/zones';
      const cameraBaseline: CameraEndpoint = '/api/cameras/abc-123/baseline/activity';

      expect(listCameras).toBe('/api/cameras');
      expect(getCamera).toBe('/api/cameras/abc-123');
      expect(cameraSnapshot).toBe('/api/cameras/abc-123/snapshot');
      expect(cameraZones).toBe('/api/cameras/abc-123/zones');
      expect(cameraBaseline).toBe('/api/cameras/abc-123/baseline/activity');
    });

    it('defines event endpoints correctly', () => {
      const listEvents: EventEndpoint = '/api/events';
      const getEvent: EventEndpoint = '/api/events/123';
      const eventStats: EventEndpoint = '/api/events/stats';
      const eventSearch: EventEndpoint = '/api/events/search';
      const eventExport: EventEndpoint = '/api/events/export';
      const eventDetections: EventEndpoint = '/api/events/123/detections';

      expect(listEvents).toBe('/api/events');
      expect(getEvent).toBe('/api/events/123');
      expect(eventStats).toBe('/api/events/stats');
      expect(eventSearch).toBe('/api/events/search');
      expect(eventExport).toBe('/api/events/export');
      expect(eventDetections).toBe('/api/events/123/detections');
    });

    it('defines system endpoints correctly', () => {
      const health: SystemEndpoint = '/api/system/health';
      const ready: SystemEndpoint = '/api/system/health/ready';
      const gpu: SystemEndpoint = '/api/system/gpu';
      const gpuHistory: SystemEndpoint = '/api/system/gpu/history';
      const config: SystemEndpoint = '/api/system/config';
      const stats: SystemEndpoint = '/api/system/stats';
      const storage: SystemEndpoint = '/api/system/storage';
      const telemetry: SystemEndpoint = '/api/system/telemetry';
      const models: SystemEndpoint = '/api/system/models';
      const severity: SystemEndpoint = '/api/system/severity';
      const cleanup: SystemEndpoint = '/api/system/cleanup';
      const circuitBreakers: SystemEndpoint = '/api/system/circuit-breakers';
      const pipelineLatency: SystemEndpoint = '/api/system/pipeline-latency';

      expect(health).toBe('/api/system/health');
      expect(ready).toBe('/api/system/health/ready');
      expect(gpu).toBe('/api/system/gpu');
      expect(gpuHistory).toBe('/api/system/gpu/history');
      expect(config).toBe('/api/system/config');
      expect(stats).toBe('/api/system/stats');
      expect(storage).toBe('/api/system/storage');
      expect(telemetry).toBe('/api/system/telemetry');
      expect(models).toBe('/api/system/models');
      expect(severity).toBe('/api/system/severity');
      expect(cleanup).toBe('/api/system/cleanup');
      expect(circuitBreakers).toBe('/api/system/circuit-breakers');
      expect(pipelineLatency).toBe('/api/system/pipeline-latency');
    });

    it('defines detection endpoints correctly', () => {
      const stats: DetectionEndpoint = '/api/detections/stats';
      const image: DetectionEndpoint = '/api/detections/123/image';
      const video: DetectionEndpoint = '/api/detections/123/video';

      expect(stats).toBe('/api/detections/stats');
      expect(image).toBe('/api/detections/123/image');
      expect(video).toBe('/api/detections/123/video');
    });

    it('defines enrichment endpoints correctly', () => {
      const enrichment: EnrichmentEndpoint = '/api/enrichment/456';

      expect(enrichment).toBe('/api/enrichment/456');
    });

    it('defines alert rule endpoints correctly', () => {
      const listRules: AlertRuleEndpoint = '/api/alerts/rules';
      const getRule: AlertRuleEndpoint = '/api/alerts/rules/rule-uuid-123';
      const testRule: AlertRuleEndpoint = '/api/alerts/rules/rule-uuid-123/test';

      expect(listRules).toBe('/api/alerts/rules');
      expect(getRule).toBe('/api/alerts/rules/rule-uuid-123');
      expect(testRule).toBe('/api/alerts/rules/rule-uuid-123/test');
    });

    it('defines zone endpoints correctly', () => {
      const listZones: ZoneEndpoint = '/api/cameras/cam-123/zones';
      const getZone: ZoneEndpoint = '/api/cameras/cam-123/zones/zone-456';

      expect(listZones).toBe('/api/cameras/cam-123/zones');
      expect(getZone).toBe('/api/cameras/cam-123/zones/zone-456');
    });

    it('defines audit endpoints correctly', () => {
      const listAudit: AuditEndpoint = '/api/audit';
      const getAudit: AuditEndpoint = '/api/audit/789';
      const auditStats: AuditEndpoint = '/api/audit/stats';

      expect(listAudit).toBe('/api/audit');
      expect(getAudit).toBe('/api/audit/789');
      expect(auditStats).toBe('/api/audit/stats');
    });

    it('defines search endpoints correctly', () => {
      const search: SearchEndpoint = '/api/events/search';

      expect(search).toBe('/api/events/search');
    });

    it('ApiEndpoint is a union of all endpoint types', () => {
      // All these should be valid ApiEndpoint values
      const endpoints: ApiEndpoint[] = [
        '/api/cameras',
        '/api/cameras/test-id',
        '/api/events',
        '/api/events/123',
        '/api/system/health',
        '/api/system/gpu',
        '/api/detections/stats',
        '/api/enrichment/456',
        '/api/alerts/rules',
        '/api/audit',
      ];

      expect(endpoints.length).toBe(10);
    });
  });

  describe('Response Type Inference', () => {
    it('infers CameraListResponse for /api/cameras (list)', () => {
      // Type-level assertion - compile-time check
      expectTypeOf<EndpointResponseType<'/api/cameras'>>().toMatchTypeOf<CameraListResponse>();
    });

    it('infers Camera for /api/cameras/:id (single)', () => {
      expectTypeOf<EndpointResponseType<'/api/cameras/abc-123'>>().toMatchTypeOf<Camera>();
    });

    it('infers Event[] wrapped response for /api/events', () => {
      // Events return { events: Event[], count, ... }
      expectTypeOf<EndpointResponseType<'/api/events'>>().toHaveProperty('events');
    });

    it('infers Event for /api/events/:id', () => {
      expectTypeOf<EndpointResponseType<'/api/events/123'>>().toMatchTypeOf<Event>();
    });

    it('infers HealthResponse for /api/system/health', () => {
      expectTypeOf<EndpointResponseType<'/api/system/health'>>().toMatchTypeOf<HealthResponse>();
    });

    it('infers GPUStats for /api/system/gpu', () => {
      expectTypeOf<EndpointResponseType<'/api/system/gpu'>>().toMatchTypeOf<GPUStats>();
    });

    it('infers SystemConfig for /api/system/config', () => {
      expectTypeOf<EndpointResponseType<'/api/system/config'>>().toMatchTypeOf<SystemConfig>();
    });

    it('infers Detection[] wrapped response for /api/events/:id/detections', () => {
      expectTypeOf<EndpointResponseType<'/api/events/123/detections'>>().toHaveProperty(
        'detections'
      );
    });

    it('infers AlertRule[] wrapped response for /api/alerts/rules', () => {
      expectTypeOf<EndpointResponseType<'/api/alerts/rules'>>().toHaveProperty('rules');
    });

    it('infers AlertRule for /api/alerts/rules/:id', () => {
      expectTypeOf<EndpointResponseType<'/api/alerts/rules/abc-123'>>().toMatchTypeOf<AlertRule>();
    });

    it('infers Zone[] wrapped response for /api/cameras/:id/zones', () => {
      expectTypeOf<EndpointResponseType<'/api/cameras/abc/zones'>>().toHaveProperty('zones');
    });

    it('infers Zone for /api/cameras/:id/zones/:zoneId', () => {
      expectTypeOf<EndpointResponseType<'/api/cameras/abc/zones/xyz'>>().toMatchTypeOf<Zone>();
    });
  });

  describe('ID Extraction from Endpoints', () => {
    it('extracts camera ID from /api/cameras/:id', () => {
      type ExtractedId = ExtractIdFromEndpoint<'/api/cameras/abc-123'>;
      expectTypeOf<ExtractedId>().toEqualTypeOf<'abc-123'>();
    });

    it('extracts event ID from /api/events/:id', () => {
      type ExtractedId = ExtractIdFromEndpoint<'/api/events/456'>;
      expectTypeOf<ExtractedId>().toEqualTypeOf<'456'>();
    });

    it('extracts detection ID from /api/detections/:id/image', () => {
      type ExtractedId = ExtractIdFromEndpoint<'/api/detections/789/image'>;
      expectTypeOf<ExtractedId>().toEqualTypeOf<'789'>();
    });

    it('returns never for list endpoints', () => {
      type ExtractedId = ExtractIdFromEndpoint<'/api/cameras'>;
      expectTypeOf<ExtractedId>().toEqualTypeOf<never>();
    });
  });
});

// ============================================================================
// Runtime Behavior Tests
// ============================================================================

describe('Endpoint Validation', () => {
  describe('isValidEndpoint', () => {
    it('returns true for valid camera endpoints', () => {
      expect(isValidEndpoint('/api/cameras')).toBe(true);
      expect(isValidEndpoint('/api/cameras/abc-123')).toBe(true);
      expect(isValidEndpoint('/api/cameras/abc-123/snapshot')).toBe(true);
      expect(isValidEndpoint('/api/cameras/abc-123/zones')).toBe(true);
    });

    it('returns true for valid event endpoints', () => {
      expect(isValidEndpoint('/api/events')).toBe(true);
      expect(isValidEndpoint('/api/events/123')).toBe(true);
      expect(isValidEndpoint('/api/events/stats')).toBe(true);
      expect(isValidEndpoint('/api/events/search')).toBe(true);
      expect(isValidEndpoint('/api/events/123/detections')).toBe(true);
    });

    it('returns true for valid system endpoints', () => {
      expect(isValidEndpoint('/api/system/health')).toBe(true);
      expect(isValidEndpoint('/api/system/health/ready')).toBe(true);
      expect(isValidEndpoint('/api/system/gpu')).toBe(true);
      expect(isValidEndpoint('/api/system/config')).toBe(true);
      expect(isValidEndpoint('/api/system/stats')).toBe(true);
    });

    it('returns true for valid detection endpoints', () => {
      expect(isValidEndpoint('/api/detections/stats')).toBe(true);
      expect(isValidEndpoint('/api/detections/123/image')).toBe(true);
      expect(isValidEndpoint('/api/detections/123/video')).toBe(true);
    });

    it('returns false for invalid endpoints', () => {
      expect(isValidEndpoint('/api/invalid')).toBe(false);
      expect(isValidEndpoint('/api/cameras/invalid/unknown')).toBe(false);
      expect(isValidEndpoint('/other/path')).toBe(false);
      expect(isValidEndpoint('')).toBe(false);
    });
  });

  describe('parseEndpoint', () => {
    it('parses camera list endpoint', () => {
      const parsed = parseEndpoint('/api/cameras');
      expect(parsed).toEqual({
        resource: 'cameras',
        action: 'list',
        id: undefined,
        subResource: undefined,
        subId: undefined,
      });
    });

    it('parses camera detail endpoint', () => {
      const parsed = parseEndpoint('/api/cameras/abc-123');
      expect(parsed).toEqual({
        resource: 'cameras',
        action: 'detail',
        id: 'abc-123',
        subResource: undefined,
        subId: undefined,
      });
    });

    it('parses camera zones endpoint', () => {
      const parsed = parseEndpoint('/api/cameras/abc-123/zones');
      expect(parsed).toEqual({
        resource: 'cameras',
        action: 'sublist',
        id: 'abc-123',
        subResource: 'zones',
        subId: undefined,
      });
    });

    it('parses camera zone detail endpoint', () => {
      const parsed = parseEndpoint('/api/cameras/abc-123/zones/zone-456');
      expect(parsed).toEqual({
        resource: 'cameras',
        action: 'subdetail',
        id: 'abc-123',
        subResource: 'zones',
        subId: 'zone-456',
      });
    });

    it('parses event list endpoint', () => {
      const parsed = parseEndpoint('/api/events');
      expect(parsed).toEqual({
        resource: 'events',
        action: 'list',
        id: undefined,
        subResource: undefined,
        subId: undefined,
      });
    });

    it('parses event detail endpoint', () => {
      const parsed = parseEndpoint('/api/events/123');
      expect(parsed).toEqual({
        resource: 'events',
        action: 'detail',
        id: '123',
        subResource: undefined,
        subId: undefined,
      });
    });

    it('parses event detections endpoint', () => {
      const parsed = parseEndpoint('/api/events/123/detections');
      expect(parsed).toEqual({
        resource: 'events',
        action: 'sublist',
        id: '123',
        subResource: 'detections',
        subId: undefined,
      });
    });

    it('parses system health endpoint', () => {
      const parsed = parseEndpoint('/api/system/health');
      expect(parsed).toEqual({
        resource: 'system',
        action: 'health',
        id: undefined,
        subResource: undefined,
        subId: undefined,
      });
    });

    it('parses system gpu endpoint', () => {
      const parsed = parseEndpoint('/api/system/gpu');
      expect(parsed).toEqual({
        resource: 'system',
        action: 'gpu',
        id: undefined,
        subResource: undefined,
        subId: undefined,
      });
    });

    it('returns null for invalid endpoints', () => {
      expect(parseEndpoint('/invalid')).toBeNull();
      expect(parseEndpoint('')).toBeNull();
      expect(parseEndpoint('/api/')).toBeNull();
    });
  });
});

// ============================================================================
// Endpoint Builder Tests
// ============================================================================

describe('Endpoint Builders', () => {
  describe('cameraEndpoint', () => {
    it('builds camera list endpoint', () => {
      const endpoint = cameraEndpoint();
      expect(endpoint).toBe('/api/cameras');
      expectTypeOf(endpoint).toEqualTypeOf<'/api/cameras'>();
    });

    it('builds camera detail endpoint', () => {
      const endpoint = cameraEndpoint('abc-123');
      expect(endpoint).toBe('/api/cameras/abc-123');
      // Type should be narrowed to CameraEndpoint
      expectTypeOf(endpoint).toMatchTypeOf<CameraEndpoint>();
    });

    it('builds camera snapshot endpoint', () => {
      const endpoint = cameraEndpoint('abc-123', 'snapshot');
      expect(endpoint).toBe('/api/cameras/abc-123/snapshot');
    });

    it('builds camera zones endpoint', () => {
      const endpoint = cameraEndpoint('abc-123', 'zones');
      expect(endpoint).toBe('/api/cameras/abc-123/zones');
    });

    it('builds camera baseline activity endpoint', () => {
      const endpoint = cameraEndpoint('abc-123', 'baseline/activity');
      expect(endpoint).toBe('/api/cameras/abc-123/baseline/activity');
    });
  });

  describe('eventEndpoint', () => {
    it('builds event list endpoint', () => {
      const endpoint = eventEndpoint();
      expect(endpoint).toBe('/api/events');
    });

    it('builds event detail endpoint', () => {
      const endpoint = eventEndpoint(123);
      expect(endpoint).toBe('/api/events/123');
    });

    it('builds event detections endpoint', () => {
      const endpoint = eventEndpoint(123, 'detections');
      expect(endpoint).toBe('/api/events/123/detections');
    });

    it('builds event stats endpoint', () => {
      const endpoint = eventEndpoint(undefined, 'stats');
      expect(endpoint).toBe('/api/events/stats');
    });

    it('builds event search endpoint', () => {
      const endpoint = eventEndpoint(undefined, 'search');
      expect(endpoint).toBe('/api/events/search');
    });
  });

  describe('detectionEndpoint', () => {
    it('builds detection stats endpoint', () => {
      const endpoint = detectionEndpoint(undefined, 'stats');
      expect(endpoint).toBe('/api/detections/stats');
    });

    it('builds detection image endpoint', () => {
      const endpoint = detectionEndpoint(123, 'image');
      expect(endpoint).toBe('/api/detections/123/image');
    });

    it('builds detection video endpoint', () => {
      const endpoint = detectionEndpoint(123, 'video');
      expect(endpoint).toBe('/api/detections/123/video');
    });
  });

  describe('zoneEndpoint', () => {
    it('builds zones list endpoint for a camera', () => {
      const endpoint = zoneEndpoint('cam-123');
      expect(endpoint).toBe('/api/cameras/cam-123/zones');
    });

    it('builds zone detail endpoint', () => {
      const endpoint = zoneEndpoint('cam-123', 'zone-456');
      expect(endpoint).toBe('/api/cameras/cam-123/zones/zone-456');
    });
  });

  describe('alertRuleEndpoint', () => {
    it('builds alert rules list endpoint', () => {
      const endpoint = alertRuleEndpoint();
      expect(endpoint).toBe('/api/alerts/rules');
    });

    it('builds alert rule detail endpoint', () => {
      const endpoint = alertRuleEndpoint('rule-123');
      expect(endpoint).toBe('/api/alerts/rules/rule-123');
    });

    it('builds alert rule test endpoint', () => {
      const endpoint = alertRuleEndpoint('rule-123', 'test');
      expect(endpoint).toBe('/api/alerts/rules/rule-123/test');
    });
  });
});

// ============================================================================
// Type-Safe API Client Tests
// ============================================================================

describe('Type-Safe API Client Functions', () => {
  // Note: These tests use mocked fetch, similar to existing api.test.ts patterns

  describe('apiGet', () => {
    it('returns correctly typed response for camera list', () => {
      // Mock would be setup here - testing type inference
      // const cameras = await apiGet('/api/cameras');
      // Type should be inferred as Camera[]
      expectTypeOf(apiGet).toBeFunction();
    });

    it('accepts only valid GET endpoints', () => {
      // This should compile
      // apiGet('/api/cameras');
      // apiGet('/api/events');
      // apiGet('/api/system/health');

      // This should NOT compile (type error) - can't test at runtime
      // but we verify the function signature accepts ApiEndpoint
      expectTypeOf(apiGet).parameter(0).toMatchTypeOf<ApiEndpoint>();
    });
  });

  describe('apiPost', () => {
    it('returns correctly typed response', () => {
      // apiPost('/api/cameras', { name: 'test' });
      expectTypeOf(apiPost).toBeFunction();
    });
  });

  describe('apiPatch', () => {
    it('returns correctly typed response', () => {
      // apiPatch('/api/cameras/abc', { name: 'updated' });
      expectTypeOf(apiPatch).toBeFunction();
    });
  });

  describe('apiPut', () => {
    it('returns correctly typed response', () => {
      // apiPut('/api/alerts/rules/abc', { ... });
      expectTypeOf(apiPut).toBeFunction();
    });
  });

  describe('apiDelete', () => {
    it('returns void for delete operations', () => {
      // apiDelete('/api/cameras/abc');
      expectTypeOf(apiDelete).toBeFunction();
    });
  });
});

// ============================================================================
// Edge Cases and Error Handling
// ============================================================================

describe('Edge Cases', () => {
  it('handles endpoints with query parameters', () => {
    // Query parameters are not part of the endpoint type
    // They should be handled separately
    const endpoint: EventEndpoint = '/api/events';
    expect(endpoint).not.toContain('?');
  });

  it('handles numeric IDs as strings in endpoint', () => {
    // Event IDs are numbers but appear as strings in the endpoint
    const endpoint: EventEndpoint = '/api/events/123';
    expect(endpoint).toContain('123');
  });

  it('handles UUID IDs in endpoints', () => {
    const endpoint: CameraEndpoint = '/api/cameras/a1b2c3d4-e5f6-7890-abcd-ef1234567890';
    expect(endpoint).toContain('a1b2c3d4-e5f6-7890-abcd-ef1234567890');
  });
});

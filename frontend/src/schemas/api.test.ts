/**
 * Unit tests for API Response Schemas.
 *
 * These tests verify that the consolidated API response schemas correctly
 * validate data structures returned by the backend API.
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
  // Camera schemas
  cameraResponseSchema,
  cameraListResponseSchema,
  // Detection schemas
  detectionResponseSchema,
  // Event schemas
  eventResponseSchema,
  eventStatsResponseSchema,
  riskAnalysisSchema,
  // Alert rule schemas
  alertRuleResponseSchema,
  // Alert schemas
  alertResponseSchema,
  // Zone schemas
  zoneResponseSchema,
  // Entity schemas
  entityResponseSchema,
  // Health schemas
  healthResponseSchema,
  gpuStatsResponseSchema,
  // Error schemas
  validationErrorResponseSchema,
  apiErrorSchema,
  // Helpers
  paginatedResponse,
  cursorPaginatedResponse,
  parseApiResponse,
  safeParseApiResponse,
} from './api';

// Helper to generate valid UUIDs
const validUuid = () => '550e8400-e29b-41d4-a716-446655440000';
const validTimestamp = () => '2024-01-15T10:30:00Z';

describe('API Response Schemas', () => {
  // ==========================================================================
  // Camera Schemas
  // ==========================================================================
  describe('Camera Schemas', () => {
    describe('cameraResponseSchema', () => {
      const validCamera = {
        id: validUuid(),
        name: 'Front Door',
        folder_path: '/export/foscam/front_door',
        status: 'online',
        created_at: validTimestamp(),
        updated_at: null,
        thumbnail_url: null,
        stream_url: null,
        detection_count: 42,
        last_detection_at: validTimestamp(),
      };

      it('should accept valid camera response', () => {
        const result = cameraResponseSchema.safeParse(validCamera);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data.name).toBe('Front Door');
          expect(result.data.status).toBe('online');
        }
      });

      it('should accept minimal camera response', () => {
        const minimal = {
          id: validUuid(),
          name: 'Test',
          folder_path: '/test',
          status: 'offline',
          created_at: validTimestamp(),
        };
        const result = cameraResponseSchema.safeParse(minimal);
        expect(result.success).toBe(true);
      });

      it('should reject invalid camera status', () => {
        const invalid = { ...validCamera, status: 'invalid' };
        const result = cameraResponseSchema.safeParse(invalid);
        expect(result.success).toBe(false);
      });

      it('should reject invalid UUID for id', () => {
        const invalid = { ...validCamera, id: 'not-a-uuid' };
        const result = cameraResponseSchema.safeParse(invalid);
        expect(result.success).toBe(false);
      });
    });

    describe('cameraListResponseSchema', () => {
      it('should accept valid paginated camera list', () => {
        const listResponse = {
          items: [
            {
              id: validUuid(),
              name: 'Camera 1',
              folder_path: '/cam1',
              status: 'online',
              created_at: validTimestamp(),
            },
          ],
          total: 1,
          page: 1,
          size: 10,
          pages: 1,
        };
        const result = cameraListResponseSchema.safeParse(listResponse);
        expect(result.success).toBe(true);
      });

      it('should accept empty list', () => {
        const emptyResponse = {
          items: [],
          total: 0,
          page: 1,
          size: 10,
          pages: 0,
        };
        const result = cameraListResponseSchema.safeParse(emptyResponse);
        expect(result.success).toBe(true);
      });
    });
  });

  // ==========================================================================
  // Detection Schemas
  // ==========================================================================
  describe('Detection Schemas', () => {
    describe('detectionResponseSchema', () => {
      const validDetection = {
        id: validUuid(),
        event_id: validUuid(),
        label: 'person',
        confidence: 0.95,
        bbox: [0.1, 0.2, 0.5, 0.8],
        frame_number: 42,
        frame_timestamp: validTimestamp(),
        thumbnail_path: '/thumbnails/det1.jpg',
        created_at: validTimestamp(),
        entity_id: validUuid(),
        track_id: 1,
      };

      it('should accept valid detection response', () => {
        const result = detectionResponseSchema.safeParse(validDetection);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data.label).toBe('person');
          expect(result.data.confidence).toBe(0.95);
        }
      });

      it('should accept minimal detection response', () => {
        const minimal = {
          id: validUuid(),
          event_id: validUuid(),
          label: 'vehicle',
          confidence: 0.8,
          created_at: validTimestamp(),
        };
        const result = detectionResponseSchema.safeParse(minimal);
        expect(result.success).toBe(true);
      });

      it('should reject invalid confidence (>1)', () => {
        const invalid = { ...validDetection, confidence: 1.5 };
        const result = detectionResponseSchema.safeParse(invalid);
        expect(result.success).toBe(false);
      });

      it('should reject invalid bounding box', () => {
        const invalid = { ...validDetection, bbox: [0.1, 0.2, 0.5] };
        const result = detectionResponseSchema.safeParse(invalid);
        expect(result.success).toBe(false);
      });
    });
  });

  // ==========================================================================
  // Event Schemas
  // ==========================================================================
  describe('Event Schemas', () => {
    describe('riskAnalysisSchema', () => {
      it('should accept valid risk analysis', () => {
        const analysis = {
          risk_score: 75,
          risk_level: 'high',
          analysis_text: 'Suspicious activity detected',
          threat_summary: 'Unknown person at night',
          recommended_actions: ['Review footage', 'Check locks'],
          confidence_factors: { time_of_day: 0.8, location: 0.6 },
        };
        const result = riskAnalysisSchema.safeParse(analysis);
        expect(result.success).toBe(true);
      });

      it('should accept minimal risk analysis', () => {
        const minimal = {
          risk_score: 30,
          risk_level: 'low',
        };
        const result = riskAnalysisSchema.safeParse(minimal);
        expect(result.success).toBe(true);
      });
    });

    describe('eventResponseSchema', () => {
      const validEvent = {
        id: validUuid(),
        camera_id: validUuid(),
        started_at: validTimestamp(),
        ended_at: validTimestamp(),
        risk_score: 75,
        risk_level: 'high',
        status: 'analyzed',
        detection_count: 3,
        thumbnail_path: '/thumbnails/evt1.jpg',
        video_path: '/videos/evt1.mp4',
        created_at: validTimestamp(),
        updated_at: validTimestamp(),
        version: 1,
        flagged: false,
      };

      it('should accept valid event response', () => {
        const result = eventResponseSchema.safeParse(validEvent);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data.risk_score).toBe(75);
          expect(result.data.risk_level).toBe('high');
          expect(result.data.status).toBe('analyzed');
        }
      });

      it('should accept event with nested risk_analysis', () => {
        const eventWithAnalysis = {
          ...validEvent,
          risk_analysis: {
            risk_score: 75,
            risk_level: 'high',
            analysis_text: 'Test analysis',
          },
        };
        const result = eventResponseSchema.safeParse(eventWithAnalysis);
        expect(result.success).toBe(true);
      });

      it('should accept event with null risk fields', () => {
        const eventNoRisk = {
          ...validEvent,
          risk_score: null,
          risk_level: null,
        };
        const result = eventResponseSchema.safeParse(eventNoRisk);
        expect(result.success).toBe(true);
      });

      it('should reject invalid event status', () => {
        const invalid = { ...validEvent, status: 'invalid' };
        const result = eventResponseSchema.safeParse(invalid);
        expect(result.success).toBe(false);
      });

      it('should reject invalid risk level', () => {
        const invalid = { ...validEvent, risk_level: 'extreme' };
        const result = eventResponseSchema.safeParse(invalid);
        expect(result.success).toBe(false);
      });
    });

    describe('eventStatsResponseSchema', () => {
      it('should accept valid event stats', () => {
        const stats = {
          total_events: 100,
          events_by_risk_level: {
            low: 40,
            medium: 30,
            high: 20,
            critical: 10,
          },
          events_by_camera: {
            [validUuid()]: 50,
            [validUuid()]: 50,
          },
          average_risk_score: 45.5,
          time_range_start: validTimestamp(),
          time_range_end: validTimestamp(),
        };
        const result = eventStatsResponseSchema.safeParse(stats);
        expect(result.success).toBe(true);
      });
    });
  });

  // ==========================================================================
  // Alert Rule Schemas
  // ==========================================================================
  describe('Alert Rule Schemas', () => {
    describe('alertRuleResponseSchema', () => {
      const validRule = {
        id: validUuid(),
        name: 'Night Intruder Alert',
        description: 'Detect people at night',
        enabled: true,
        severity: 'high',
        risk_threshold: 70,
        object_types: ['person'],
        camera_ids: [validUuid()],
        zone_ids: null,
        min_confidence: 0.8,
        schedule: {
          days: ['monday', 'tuesday'],
          start_time: '22:00',
          end_time: '06:00',
          timezone: 'America/New_York',
        },
        dedup_key_template: '{camera_id}:{rule_id}',
        cooldown_seconds: 300,
        channels: ['email', 'pushover'],
        created_at: validTimestamp(),
        updated_at: validTimestamp(),
        last_triggered_at: validTimestamp(),
        trigger_count: 5,
      };

      it('should accept valid alert rule response', () => {
        const result = alertRuleResponseSchema.safeParse(validRule);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data.name).toBe('Night Intruder Alert');
          expect(result.data.severity).toBe('high');
        }
      });

      it('should accept minimal alert rule response', () => {
        const minimal = {
          id: validUuid(),
          name: 'Simple Rule',
          enabled: true,
          severity: 'medium',
          dedup_key_template: '{camera_id}',
          cooldown_seconds: 0,
          channels: [],
          created_at: validTimestamp(),
        };
        const result = alertRuleResponseSchema.safeParse(minimal);
        expect(result.success).toBe(true);
      });
    });
  });

  // ==========================================================================
  // Alert Schemas
  // ==========================================================================
  describe('Alert Schemas', () => {
    describe('alertResponseSchema', () => {
      const validAlert = {
        id: validUuid(),
        rule_id: validUuid(),
        event_id: validUuid(),
        camera_id: validUuid(),
        severity: 'critical',
        title: 'Person detected in restricted area',
        message: 'A person was detected in Zone A at night',
        risk_score: 85,
        acknowledged: false,
        acknowledged_at: null,
        acknowledged_by: null,
        resolved: false,
        resolved_at: null,
        resolved_by: null,
        dismissed: false,
        dismissed_at: null,
        dismissed_by: null,
        created_at: validTimestamp(),
        version: 1,
      };

      it('should accept valid alert response', () => {
        const result = alertResponseSchema.safeParse(validAlert);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data.severity).toBe('critical');
          expect(result.data.acknowledged).toBe(false);
        }
      });

      it('should accept acknowledged alert', () => {
        const acked = {
          ...validAlert,
          acknowledged: true,
          acknowledged_at: validTimestamp(),
          acknowledged_by: 'user@example.com',
        };
        const result = alertResponseSchema.safeParse(acked);
        expect(result.success).toBe(true);
      });
    });
  });

  // ==========================================================================
  // Zone Schemas
  // ==========================================================================
  describe('Zone Schemas', () => {
    describe('zoneResponseSchema', () => {
      const validZone = {
        id: validUuid(),
        camera_id: validUuid(),
        name: 'Entry Area',
        description: 'Front door entry zone',
        points: [
          { x: 0.1, y: 0.1 },
          { x: 0.9, y: 0.1 },
          { x: 0.9, y: 0.9 },
          { x: 0.1, y: 0.9 },
        ],
        color: '#ff0000',
        enabled: true,
        alert_on_entry: true,
        alert_on_exit: false,
        alert_on_loitering: true,
        loitering_threshold_seconds: 30,
        object_types: ['person'],
        created_at: validTimestamp(),
        updated_at: null,
      };

      it('should accept valid zone response', () => {
        const result = zoneResponseSchema.safeParse(validZone);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data.name).toBe('Entry Area');
          expect(result.data.points).toHaveLength(4);
        }
      });

      it('should reject zone with less than 3 points', () => {
        const invalid = {
          ...validZone,
          points: [
            { x: 0.1, y: 0.1 },
            { x: 0.9, y: 0.9 },
          ],
        };
        const result = zoneResponseSchema.safeParse(invalid);
        expect(result.success).toBe(false);
      });

      it('should reject zone with out-of-range coordinates', () => {
        const invalid = {
          ...validZone,
          points: [
            { x: 0.1, y: 0.1 },
            { x: 1.5, y: 0.1 },
            { x: 0.9, y: 0.9 },
          ],
        };
        const result = zoneResponseSchema.safeParse(invalid);
        expect(result.success).toBe(false);
      });
    });
  });

  // ==========================================================================
  // Entity Schemas
  // ==========================================================================
  describe('Entity Schemas', () => {
    describe('entityResponseSchema', () => {
      const validEntity = {
        id: validUuid(),
        label: 'Entity-001',
        object_type: 'person',
        first_seen_at: validTimestamp(),
        last_seen_at: validTimestamp(),
        camera_ids: [validUuid(), validUuid()],
        detection_count: 15,
        average_confidence: 0.92,
        embedding: null,
        metadata: { height_estimate: 175 },
        created_at: validTimestamp(),
        updated_at: validTimestamp(),
      };

      it('should accept valid entity response', () => {
        const result = entityResponseSchema.safeParse(validEntity);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data.object_type).toBe('person');
          expect(result.data.detection_count).toBe(15);
        }
      });

      it('should reject invalid object type', () => {
        const invalid = { ...validEntity, object_type: 'robot' };
        const result = entityResponseSchema.safeParse(invalid);
        expect(result.success).toBe(false);
      });
    });
  });

  // ==========================================================================
  // Health Schemas
  // ==========================================================================
  describe('Health Schemas', () => {
    describe('healthResponseSchema', () => {
      const validHealth = {
        status: 'healthy',
        version: '1.0.0',
        uptime_seconds: 3600,
        timestamp: validTimestamp(),
        services: {
          database: { status: 'healthy', message: 'Connected' },
          redis: { status: 'healthy' },
          detector: { status: 'degraded', message: 'High latency' },
        },
      };

      it('should accept valid health response', () => {
        const result = healthResponseSchema.safeParse(validHealth);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data.status).toBe('healthy');
          expect(result.data.services.database.status).toBe('healthy');
        }
      });

      it('should reject invalid status', () => {
        const invalid = { ...validHealth, status: 'unknown' };
        const result = healthResponseSchema.safeParse(invalid);
        expect(result.success).toBe(false);
      });
    });

    describe('gpuStatsResponseSchema', () => {
      const validGpuStats = {
        gpus: [
          {
            index: 0,
            name: 'NVIDIA GeForce RTX 4090',
            utilization_gpu: 45,
            utilization_memory: 30,
            memory_total_mb: 24576,
            memory_used_mb: 7373,
            memory_free_mb: 17203,
            temperature_c: 65,
            power_draw_w: 250,
            power_limit_w: 450,
          },
        ],
        timestamp: validTimestamp(),
      };

      it('should accept valid GPU stats response', () => {
        const result = gpuStatsResponseSchema.safeParse(validGpuStats);
        expect(result.success).toBe(true);
      });
    });
  });

  // ==========================================================================
  // Error Schemas
  // ==========================================================================
  describe('Error Schemas', () => {
    describe('validationErrorResponseSchema', () => {
      it('should accept valid validation error response', () => {
        const error = {
          detail: [
            {
              loc: ['body', 'name'],
              msg: 'field required',
              type: 'value_error.missing',
            },
          ],
        };
        const result = validationErrorResponseSchema.safeParse(error);
        expect(result.success).toBe(true);
      });
    });

    describe('apiErrorSchema', () => {
      it('should accept valid API error', () => {
        const error = {
          detail: 'Not found',
          status_code: 404,
          error_code: 'RESOURCE_NOT_FOUND',
        };
        const result = apiErrorSchema.safeParse(error);
        expect(result.success).toBe(true);
      });

      it('should accept minimal API error', () => {
        const error = { detail: 'Internal server error' };
        const result = apiErrorSchema.safeParse(error);
        expect(result.success).toBe(true);
      });
    });
  });

  // ==========================================================================
  // Helper Functions
  // ==========================================================================
  describe('Helper Functions', () => {
    describe('paginatedResponse', () => {
      it('should create paginated schema for any item type', () => {
        const itemSchema = zoneResponseSchema;
        const paginatedSchema = paginatedResponse(itemSchema);

        const data = {
          items: [],
          total: 0,
          page: 1,
          size: 10,
          pages: 0,
        };
        const result = paginatedSchema.safeParse(data);
        expect(result.success).toBe(true);
      });
    });

    describe('cursorPaginatedResponse', () => {
      it('should create cursor-paginated schema', () => {
        const itemSchema = cameraResponseSchema;
        const cursorSchema = cursorPaginatedResponse(itemSchema);

        const data = {
          items: [],
          next_cursor: 'abc123',
          has_more: true,
        };
        const result = cursorSchema.safeParse(data);
        expect(result.success).toBe(true);
      });
    });

    describe('parseApiResponse', () => {
      let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

      beforeEach(() => {
        consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      });

      afterEach(() => {
        consoleErrorSpy.mockRestore();
      });

      it('should return parsed data for valid input', () => {
        const data = {
          id: validUuid(),
          name: 'Test',
          folder_path: '/test',
          status: 'online',
          created_at: validTimestamp(),
        };
        const result = parseApiResponse(cameraResponseSchema, data, 'getCamera');
        expect(result.name).toBe('Test');
      });

      it('should throw for invalid input', () => {
        const invalidData = { id: 'not-uuid' };
        expect(() => parseApiResponse(cameraResponseSchema, invalidData, 'getCamera')).toThrow();
        expect(consoleErrorSpy).toHaveBeenCalled();
      });
    });

    describe('safeParseApiResponse', () => {
      let consoleWarnSpy: ReturnType<typeof vi.spyOn>;

      beforeEach(() => {
        consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      });

      afterEach(() => {
        consoleWarnSpy.mockRestore();
      });

      it('should return parsed data for valid input', () => {
        const data = {
          id: validUuid(),
          name: 'Test',
          folder_path: '/test',
          status: 'online',
          created_at: validTimestamp(),
        };
        const result = safeParseApiResponse(cameraResponseSchema, data);
        expect(result?.name).toBe('Test');
      });

      it('should return null for invalid input', () => {
        const invalidData = { id: 'not-uuid' };
        const result = safeParseApiResponse(cameraResponseSchema, invalidData, 'getCamera');
        expect(result).toBeNull();
        expect(consoleWarnSpy).toHaveBeenCalled();
      });
    });
  });
});

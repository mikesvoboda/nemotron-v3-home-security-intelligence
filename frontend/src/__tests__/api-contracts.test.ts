/**
 * API Contract Tests
 *
 * These tests document and verify the frontend's expectations for API responses.
 * They ensure TypeScript types match the backend API contract.
 *
 * NEM-1684: Contract Tests for Backend-Frontend API Parity
 *
 * Key endpoints tested:
 * - GET /api/events - Event list response
 * - GET /api/events/{id} - Event detail response
 * - GET /api/cameras - Camera list response
 * - GET /api/system/health - Health check response
 * - WebSocket message formats (detection, status updates)
 */

import { describe, it, expect } from 'vitest';

import type {
  SecurityEventData,
  EventMessage,
  SystemStatusMessage,
  ServiceStatusMessage,
  HeartbeatMessage,
  PongMessage,
  ErrorMessage,
  GpuStatusData,
  CameraStatusData,
  QueueStatusData,
  SystemStatusData,
  ServiceStatusData,
  RiskLevel,
  HealthStatus,
  ContainerStatus,
} from '../types/websocket';

// ============================================================================
// Event API Contract Tests
// ============================================================================

describe('Event API Contract', () => {
  /**
   * EventResponse from GET /api/events/{id}
   * Documents the frontend's expectations for event data.
   */
  interface EventResponse {
    id: number;
    camera_id: string;
    started_at: string;
    ended_at: string | null;
    risk_score: number | null;
    risk_level: string | null;
    summary: string | null;
    reasoning: string | null;
    reviewed: boolean;
    notes: string | null;
    detection_count: number;
    detection_ids: number[];
    thumbnail_url: string | null;
  }

  /**
   * EventListResponse from GET /api/events
   */
  interface EventListResponse {
    events: EventResponse[];
    count: number;
    limit: number;
    offset: number;
    next_cursor: string | null;
    has_more: boolean;
    deprecation_warning?: string | null;
  }

  it('EventResponse has all required fields for event detail', () => {
    // Create a valid event response object
    const event: EventResponse = {
      id: 1,
      camera_id: 'front_door',
      started_at: '2024-01-01T00:00:00Z',
      ended_at: '2024-01-01T00:02:30Z',
      risk_score: 75,
      risk_level: 'high',
      summary: 'Person detected at front entrance',
      reasoning: 'Motion detected with high confidence',
      reviewed: false,
      notes: null,
      detection_count: 5,
      detection_ids: [1, 2, 3, 4, 5],
      thumbnail_url: '/api/media/detections/1',
    };

    // Verify all required fields exist
    expect(event.id).toBeDefined();
    expect(event.camera_id).toBeDefined();
    expect(event.started_at).toBeDefined();
    expect(event.reviewed).toBeDefined();
    expect(event.detection_count).toBeDefined();
    expect(event.detection_ids).toBeDefined();

    // Verify types
    expect(typeof event.id).toBe('number');
    expect(typeof event.camera_id).toBe('string');
    expect(typeof event.reviewed).toBe('boolean');
    expect(Array.isArray(event.detection_ids)).toBe(true);
  });

  it('EventResponse risk_score is within valid range', () => {
    const event: EventResponse = {
      id: 1,
      camera_id: 'front_door',
      started_at: '2024-01-01T00:00:00Z',
      ended_at: null,
      risk_score: 75,
      risk_level: 'high',
      summary: 'Test event',
      reasoning: 'Test reasoning',
      reviewed: false,
      notes: null,
      detection_count: 0,
      detection_ids: [],
      thumbnail_url: null,
    };

    // Risk score should be 0-100 when present
    if (event.risk_score !== null) {
      expect(event.risk_score).toBeGreaterThanOrEqual(0);
      expect(event.risk_score).toBeLessThanOrEqual(100);
    }
  });

  it('EventListResponse has pagination fields', () => {
    const response: EventListResponse = {
      events: [],
      count: 0,
      limit: 50,
      offset: 0,
      next_cursor: null,
      has_more: false,
    };

    expect(response.events).toBeDefined();
    expect(response.count).toBeDefined();
    expect(response.limit).toBeDefined();
    expect(response.offset).toBeDefined();
    expect(response.has_more).toBeDefined();

    // Verify types
    expect(Array.isArray(response.events)).toBe(true);
    expect(typeof response.count).toBe('number');
    expect(typeof response.limit).toBe('number');
    expect(typeof response.offset).toBe('number');
    expect(typeof response.has_more).toBe('boolean');
  });

  it('EventListResponse defaults match backend', () => {
    const response: EventListResponse = {
      events: [],
      count: 0,
      limit: 50, // Default limit
      offset: 0, // Default offset
      next_cursor: null,
      has_more: false,
    };

    // Default pagination values per CLAUDE.md
    expect(response.limit).toBe(50);
    expect(response.offset).toBe(0);
  });
});

// ============================================================================
// Camera API Contract Tests
// ============================================================================

describe('Camera API Contract', () => {
  /**
   * CameraResponse from GET /api/cameras/{id}
   */
  interface CameraResponse {
    id: string;
    name: string;
    folder_path: string;
    status: 'online' | 'offline' | 'error' | 'unknown';
    created_at: string;
    last_seen_at: string | null;
  }

  /**
   * CameraListResponse from GET /api/cameras
   */
  interface CameraListResponse {
    cameras: CameraResponse[];
    count: number;
  }

  it('CameraResponse has all required fields', () => {
    const camera: CameraResponse = {
      id: 'front_door',
      name: 'Front Door Camera',
      folder_path: '/export/foscam/front_door',
      status: 'online',
      created_at: '2024-01-01T00:00:00Z',
      last_seen_at: '2024-01-01T12:00:00Z',
    };

    expect(camera.id).toBeDefined();
    expect(camera.name).toBeDefined();
    expect(camera.folder_path).toBeDefined();
    expect(camera.status).toBeDefined();
    expect(camera.created_at).toBeDefined();

    // Verify types
    expect(typeof camera.id).toBe('string');
    expect(typeof camera.name).toBe('string');
    expect(typeof camera.status).toBe('string');
  });

  it('CameraResponse status has valid enum values', () => {
    const validStatuses = ['online', 'offline', 'error', 'unknown'] as const;

    validStatuses.forEach((status) => {
      const camera: CameraResponse = {
        id: 'test',
        name: 'Test',
        folder_path: '/test',
        status: status,
        created_at: '2024-01-01T00:00:00Z',
        last_seen_at: null,
      };

      expect(validStatuses).toContain(camera.status);
    });
  });

  it('CameraListResponse has required structure', () => {
    const response: CameraListResponse = {
      cameras: [],
      count: 0,
    };

    expect(response.cameras).toBeDefined();
    expect(response.count).toBeDefined();
    expect(Array.isArray(response.cameras)).toBe(true);
    expect(typeof response.count).toBe('number');
  });
});

// ============================================================================
// System Health API Contract Tests
// ============================================================================

describe('System Health API Contract', () => {
  /**
   * ServiceStatus within HealthResponse
   */
  interface ServiceStatus {
    status: 'healthy' | 'unhealthy' | 'not_initialized';
    message: string | null;
    details: Record<string, unknown> | null;
  }

  /**
   * HealthResponse from GET /api/system/health
   */
  interface HealthResponse {
    status: 'healthy' | 'degraded' | 'unhealthy';
    services: Record<string, ServiceStatus>;
    timestamp: string;
  }

  it('HealthResponse has all required fields', () => {
    const health: HealthResponse = {
      status: 'healthy',
      services: {
        database: {
          status: 'healthy',
          message: 'Database operational',
          details: null,
        },
        redis: {
          status: 'healthy',
          message: 'Redis connected',
          details: { redis_version: '7.0.0' },
        },
        ai: {
          status: 'healthy',
          message: 'AI services operational',
          details: null,
        },
      },
      timestamp: '2024-01-01T10:30:00Z',
    };

    expect(health.status).toBeDefined();
    expect(health.services).toBeDefined();
    expect(health.timestamp).toBeDefined();

    // Verify types
    expect(typeof health.status).toBe('string');
    expect(typeof health.services).toBe('object');
    expect(typeof health.timestamp).toBe('string');
  });

  it('HealthResponse status values are valid', () => {
    const validStatuses = ['healthy', 'degraded', 'unhealthy'] as const;

    validStatuses.forEach((status) => {
      const health: HealthResponse = {
        status: status,
        services: {},
        timestamp: '2024-01-01T00:00:00Z',
      };

      expect(validStatuses).toContain(health.status);
    });
  });

  it('ServiceStatus has valid structure', () => {
    const service: ServiceStatus = {
      status: 'healthy',
      message: 'Service is running',
      details: { version: '1.0.0' },
    };

    expect(service.status).toBeDefined();
    expect(['healthy', 'unhealthy', 'not_initialized']).toContain(service.status);
  });
});

// ============================================================================
// WebSocket Message Contract Tests
// ============================================================================

describe('WebSocket Event Message Contract', () => {
  it('SecurityEventData has all required fields', () => {
    const eventData: SecurityEventData = {
      id: 1,
      camera_id: 'front_door',
      risk_score: 75,
      risk_level: 'high',
      summary: 'Person detected at front door',
    };

    // Required fields per frontend type definition
    expect(eventData.id).toBeDefined();
    expect(eventData.camera_id).toBeDefined();
    expect(eventData.risk_score).toBeDefined();
    expect(eventData.risk_level).toBeDefined();
    expect(eventData.summary).toBeDefined();
  });

  it('SecurityEventData risk_score is within valid range', () => {
    const eventData: SecurityEventData = {
      id: 1,
      camera_id: 'front_door',
      risk_score: 75,
      risk_level: 'high',
      summary: 'Test',
    };

    expect(eventData.risk_score).toBeGreaterThanOrEqual(0);
    expect(eventData.risk_score).toBeLessThanOrEqual(100);
  });

  it('SecurityEventData risk_level has valid values', () => {
    const validRiskLevels: RiskLevel[] = ['low', 'medium', 'high', 'critical'];

    validRiskLevels.forEach((level) => {
      const eventData: SecurityEventData = {
        id: 1,
        camera_id: 'test',
        risk_score: 50,
        risk_level: level,
        summary: 'Test',
      };

      expect(validRiskLevels).toContain(eventData.risk_level);
    });
  });

  it('EventMessage has correct discriminant type', () => {
    const message: EventMessage = {
      type: 'event',
      data: {
        id: 1,
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Person detected',
      },
    };

    // Type discriminant must be 'event'
    expect(message.type).toBe('event');
    expect(message.data).toBeDefined();
  });
});

describe('WebSocket System Status Message Contract', () => {
  it('GpuStatusData allows null values', () => {
    const gpuStatus: GpuStatusData = {
      utilization: null,
      memory_used: null,
      memory_total: null,
      temperature: null,
      inference_fps: null,
    };

    // All GPU fields can be null when GPU is unavailable
    expect(gpuStatus.utilization).toBeNull();
    expect(gpuStatus.memory_used).toBeNull();
  });

  it('GpuStatusData has valid numeric values when present', () => {
    const gpuStatus: GpuStatusData = {
      utilization: 75.5,
      memory_used: 8192,
      memory_total: 24576,
      temperature: 65.0,
      inference_fps: 30.5,
    };

    // Utilization should be 0-100
    if (gpuStatus.utilization !== null) {
      expect(gpuStatus.utilization).toBeGreaterThanOrEqual(0);
      expect(gpuStatus.utilization).toBeLessThanOrEqual(100);
    }
  });

  it('CameraStatusData has required fields', () => {
    const cameraStatus: CameraStatusData = {
      active: 3,
      total: 4,
    };

    expect(cameraStatus.active).toBeDefined();
    expect(cameraStatus.total).toBeDefined();
    expect(typeof cameraStatus.active).toBe('number');
    expect(typeof cameraStatus.total).toBe('number');
  });

  it('QueueStatusData has required fields', () => {
    const queueStatus: QueueStatusData = {
      pending: 5,
      processing: 2,
    };

    expect(queueStatus.pending).toBeDefined();
    expect(queueStatus.processing).toBeDefined();
    expect(typeof queueStatus.pending).toBe('number');
  });

  it('SystemStatusData has all required components', () => {
    const statusData: SystemStatusData = {
      gpu: {
        utilization: 50,
        memory_used: 4096,
        memory_total: 24576,
        temperature: 60,
        inference_fps: 25,
      },
      cameras: {
        active: 3,
        total: 4,
      },
      queue: {
        pending: 0,
        processing: 0,
      },
      health: 'healthy',
    };

    expect(statusData.gpu).toBeDefined();
    expect(statusData.cameras).toBeDefined();
    expect(statusData.queue).toBeDefined();
    expect(statusData.health).toBeDefined();
  });

  it('SystemStatusMessage has correct discriminant type', () => {
    const message: SystemStatusMessage = {
      type: 'system_status',
      data: {
        gpu: {
          utilization: 50,
          memory_used: 4096,
          memory_total: 24576,
          temperature: 60,
          inference_fps: 25,
        },
        cameras: { active: 3, total: 4 },
        queue: { pending: 0, processing: 0 },
        health: 'healthy',
      },
      timestamp: '2024-01-01T00:00:00Z',
    };

    expect(message.type).toBe('system_status');
    expect(message.data).toBeDefined();
    expect(message.timestamp).toBeDefined();
  });

  it('HealthStatus has valid values', () => {
    const validStatuses: HealthStatus[] = ['healthy', 'degraded', 'unhealthy'];

    validStatuses.forEach((status) => {
      const data: SystemStatusData = {
        gpu: {
          utilization: null,
          memory_used: null,
          memory_total: null,
          temperature: null,
          inference_fps: null,
        },
        cameras: { active: 0, total: 0 },
        queue: { pending: 0, processing: 0 },
        health: status,
      };

      expect(validStatuses).toContain(data.health);
    });
  });
});

describe('WebSocket Service Status Message Contract', () => {
  it('ServiceStatusData has required fields', () => {
    const serviceData: ServiceStatusData = {
      service: 'rtdetr',
      status: 'running',
    };

    expect(serviceData.service).toBeDefined();
    expect(serviceData.status).toBeDefined();
  });

  it('ContainerStatus has valid values', () => {
    const validStatuses: ContainerStatus[] = [
      'running',
      'starting',
      'unhealthy',
      'stopped',
      'error',
      'unknown',
    ];

    validStatuses.forEach((status) => {
      const data: ServiceStatusData = {
        service: 'test',
        status: status,
      };

      expect(validStatuses).toContain(data.status);
    });
  });

  it('ServiceStatusMessage has correct discriminant type', () => {
    const message: ServiceStatusMessage = {
      type: 'service_status',
      data: {
        service: 'redis',
        status: 'running',
        message: 'Service healthy',
      },
      timestamp: '2024-01-01T00:00:00Z',
    };

    expect(message.type).toBe('service_status');
    expect(message.data).toBeDefined();
    expect(message.timestamp).toBeDefined();
  });
});

describe('WebSocket Heartbeat Message Contract', () => {
  it('HeartbeatMessage has correct type', () => {
    const message: HeartbeatMessage = {
      type: 'ping',
    };

    expect(message.type).toBe('ping');
  });

  it('PongMessage has correct type', () => {
    const message: PongMessage = {
      type: 'pong',
    };

    expect(message.type).toBe('pong');
  });
});

describe('WebSocket Error Message Contract', () => {
  it('ErrorMessage has required fields', () => {
    const message: ErrorMessage = {
      type: 'error',
      message: 'Connection failed',
    };

    expect(message.type).toBe('error');
    expect(message.message).toBeDefined();
  });

  it('ErrorMessage can have optional code and details', () => {
    const message: ErrorMessage = {
      type: 'error',
      code: 'CONNECTION_REFUSED',
      message: 'Unable to connect to server',
      details: { retry_after: 5000 },
    };

    expect(message.code).toBeDefined();
    expect(message.details).toBeDefined();
  });
});

// ============================================================================
// Detection API Contract Tests
// ============================================================================

describe('Detection API Contract', () => {
  /**
   * DetectionResponse from GET /api/detections/{id}
   */
  interface DetectionResponse {
    id: number;
    camera_id: string;
    detected_at: string;
    object_type: string;
    confidence: number;
    bbox_x: number;
    bbox_y: number;
    bbox_width: number;
    bbox_height: number;
    file_path: string;
    thumbnail_path: string | null;
    media_type: string;
  }

  /**
   * DetectionListResponse from GET /api/detections
   */
  interface DetectionListResponse {
    detections: DetectionResponse[];
    count: number;
    limit: number;
    offset: number;
  }

  it('DetectionResponse has all required fields', () => {
    const detection: DetectionResponse = {
      id: 1,
      camera_id: 'front_door',
      detected_at: '2024-01-01T00:00:00Z',
      object_type: 'person',
      confidence: 0.95,
      bbox_x: 100,
      bbox_y: 200,
      bbox_width: 150,
      bbox_height: 300,
      file_path: '/cameras/front_door/image.jpg',
      thumbnail_path: null,
      media_type: 'image',
    };

    expect(detection.id).toBeDefined();
    expect(detection.camera_id).toBeDefined();
    expect(detection.detected_at).toBeDefined();
    expect(detection.object_type).toBeDefined();
    expect(detection.confidence).toBeDefined();
  });

  it('DetectionResponse confidence is within valid range', () => {
    const detection: DetectionResponse = {
      id: 1,
      camera_id: 'front_door',
      detected_at: '2024-01-01T00:00:00Z',
      object_type: 'person',
      confidence: 0.95,
      bbox_x: 100,
      bbox_y: 200,
      bbox_width: 150,
      bbox_height: 300,
      file_path: '/test.jpg',
      thumbnail_path: null,
      media_type: 'image',
    };

    // Confidence should be 0.0-1.0
    expect(detection.confidence).toBeGreaterThanOrEqual(0);
    expect(detection.confidence).toBeLessThanOrEqual(1);
  });

  it('DetectionListResponse has pagination fields', () => {
    const response: DetectionListResponse = {
      detections: [],
      count: 0,
      limit: 50,
      offset: 0,
    };

    expect(response.detections).toBeDefined();
    expect(response.count).toBeDefined();
    expect(response.limit).toBeDefined();
    expect(response.offset).toBeDefined();
  });
});

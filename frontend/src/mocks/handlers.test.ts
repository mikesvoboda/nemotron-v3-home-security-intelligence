/**
 * Test suite for MSW (Mock Service Worker) API handlers.
 *
 * Ensures all mock handlers produce valid API responses that match TypeScript schemas,
 * handle errors correctly, and respect query parameters for pagination/filtering.
 *
 * @see src/mocks/handlers.ts - Handler implementations
 * @see src/services/api.ts - API client and TypeScript types
 */

import { http, HttpResponse } from 'msw';
import { describe, it, expect, beforeEach } from 'vitest';

import {
  handlers,
  createMockCamera,
  createMockEvent,
  mockCameras,
  mockEvents,
  mockEventStats,
  mockGpuStats,
  mockHealthResponse,
  mockSystemStats,
  mockTelemetry,
  mockReadinessResponse,
} from './handlers';
import { server } from './server';

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Make a test request to the mock server
 */
async function makeRequest(url: string, options?: RequestInit): Promise<Response> {
  return fetch(url, options);
}

/**
 * Validate pagination response structure
 */
function expectPaginationFields(data: unknown, expectedCount: number) {
  expect(data).toHaveProperty('count', expectedCount);
  expect(data).toHaveProperty('limit');
  expect(data).toHaveProperty('offset');
}

// ============================================================================
// Factory Functions Tests
// ============================================================================

describe('Mock Data Factories', () => {
  describe('createMockCamera', () => {
    it('creates a camera with default values', () => {
      const camera = createMockCamera();

      expect(camera).toHaveProperty('id');
      expect(camera).toHaveProperty('name');
      expect(camera).toHaveProperty('folder_path');
      expect(camera).toHaveProperty('status');
      expect(camera).toHaveProperty('created_at');
      expect(camera).toHaveProperty('last_seen_at');
    });

    it('overrides specific fields', () => {
      const camera = createMockCamera({ name: 'Custom Camera', status: 'offline' });

      expect(camera.name).toBe('Custom Camera');
      expect(camera.status).toBe('offline');
      expect(camera.id).toBe('camera-1'); // Default value preserved
    });

    it('creates cameras with unique IDs when overridden', () => {
      const camera1 = createMockCamera({ id: 'cam-1' });
      const camera2 = createMockCamera({ id: 'cam-2' });

      expect(camera1.id).not.toBe(camera2.id);
    });
  });

  describe('createMockEvent', () => {
    it('creates an event with default values', () => {
      const event = createMockEvent();

      expect(event).toHaveProperty('id');
      expect(event).toHaveProperty('camera_id');
      expect(event).toHaveProperty('started_at');
      expect(event).toHaveProperty('ended_at');
      expect(event).toHaveProperty('risk_score');
      expect(event).toHaveProperty('risk_level');
      expect(event).toHaveProperty('summary');
      expect(event).toHaveProperty('reviewed');
      expect(event).toHaveProperty('detection_count');
      expect(event).toHaveProperty('notes');
    });

    it('overrides specific fields', () => {
      const event = createMockEvent({
        risk_score: 95,
        risk_level: 'critical',
        reviewed: true
      });

      expect(event.risk_score).toBe(95);
      expect(event.risk_level).toBe('critical');
      expect(event.reviewed).toBe(true);
    });

    it('creates events with different risk levels', () => {
      const lowEvent = createMockEvent({ risk_level: 'low', risk_score: 10 });
      const mediumEvent = createMockEvent({ risk_level: 'medium', risk_score: 50 });
      const highEvent = createMockEvent({ risk_level: 'high', risk_score: 75 });
      const criticalEvent = createMockEvent({ risk_level: 'critical', risk_score: 95 });

      expect(lowEvent.risk_level).toBe('low');
      expect(mediumEvent.risk_level).toBe('medium');
      expect(highEvent.risk_level).toBe('high');
      expect(criticalEvent.risk_level).toBe('critical');
    });
  });
});

// ============================================================================
// Default Mock Data Tests
// ============================================================================

describe('Default Mock Data', () => {
  it('provides multiple mock cameras', () => {
    expect(mockCameras.length).toBeGreaterThan(0);
    mockCameras.forEach((camera) => {
      expect(camera).toHaveProperty('id');
      expect(camera).toHaveProperty('name');
      expect(camera).toHaveProperty('folder_path');
      expect(camera).toHaveProperty('status');
    });
  });

  it('provides multiple mock events', () => {
    expect(mockEvents.length).toBeGreaterThan(0);
    mockEvents.forEach((event) => {
      expect(event).toHaveProperty('id');
      expect(event).toHaveProperty('camera_id');
      expect(event).toHaveProperty('risk_score');
      expect(event).toHaveProperty('risk_level');
    });
  });

  it('provides event statistics', () => {
    expect(mockEventStats).toHaveProperty('total_events');
    expect(mockEventStats).toHaveProperty('events_by_risk_level');
    expect(mockEventStats).toHaveProperty('events_by_camera');

    // Validate risk level breakdown
    expect(mockEventStats.events_by_risk_level).toHaveProperty('critical');
    expect(mockEventStats.events_by_risk_level).toHaveProperty('high');
    expect(mockEventStats.events_by_risk_level).toHaveProperty('medium');
    expect(mockEventStats.events_by_risk_level).toHaveProperty('low');

    // Validate camera breakdown
    expect(Array.isArray(mockEventStats.events_by_camera)).toBe(true);
    mockEventStats.events_by_camera.forEach((item) => {
      expect(item).toHaveProperty('camera_id');
      expect(item).toHaveProperty('camera_name');
      expect(item).toHaveProperty('event_count');
    });
  });

  it('provides GPU statistics', () => {
    expect(mockGpuStats).toHaveProperty('utilization');
    expect(mockGpuStats).toHaveProperty('memory_used');
    expect(mockGpuStats).toHaveProperty('memory_total');
    expect(mockGpuStats).toHaveProperty('temperature');
    expect(mockGpuStats).toHaveProperty('power_usage');

    // Validate ranges (with nullish coalescing for optional fields)
    expect(mockGpuStats.utilization ?? 0).toBeGreaterThanOrEqual(0);
    expect(mockGpuStats.utilization ?? 0).toBeLessThanOrEqual(100);
    expect(mockGpuStats.memory_used ?? 0).toBeLessThanOrEqual(
      mockGpuStats.memory_total ?? 0
    );
  });

  it('provides health response', () => {
    expect(mockHealthResponse).toHaveProperty('status');
    expect(mockHealthResponse).toHaveProperty('services');
    expect(mockHealthResponse).toHaveProperty('timestamp');

    // Validate services
    expect(mockHealthResponse.services).toHaveProperty('database');
    expect(mockHealthResponse.services).toHaveProperty('redis');
    expect(mockHealthResponse.services).toHaveProperty('ai');

    // Each service has status and message
    Object.values(mockHealthResponse.services).forEach((service) => {
      expect(service).toHaveProperty('status');
      expect(service).toHaveProperty('message');
    });
  });

  it('provides system statistics', () => {
    expect(mockSystemStats).toHaveProperty('total_cameras');
    expect(mockSystemStats).toHaveProperty('total_events');
    expect(mockSystemStats).toHaveProperty('total_detections');
    expect(mockSystemStats).toHaveProperty('uptime_seconds');

    expect(mockSystemStats.total_cameras).toBeGreaterThanOrEqual(0);
    expect(mockSystemStats.total_events).toBeGreaterThanOrEqual(0);
    expect(mockSystemStats.uptime_seconds).toBeGreaterThanOrEqual(0);
  });

  it('provides telemetry data', () => {
    expect(mockTelemetry).toHaveProperty('queues');
    expect(mockTelemetry).toHaveProperty('latencies');
    expect(mockTelemetry).toHaveProperty('timestamp');

    // Validate queues
    expect(mockTelemetry.queues).toHaveProperty('detection_queue');
    expect(mockTelemetry.queues).toHaveProperty('analysis_queue');

    // Validate latencies
    expect(mockTelemetry.latencies).toHaveProperty('watch');
    expect(mockTelemetry.latencies).toHaveProperty('detect');

    // Each latency has required fields
    if (mockTelemetry.latencies && typeof mockTelemetry.latencies === 'object') {
      Object.values(mockTelemetry.latencies as Record<string, unknown>).forEach((latency) => {
        if (latency) {
          expect(latency).toHaveProperty('avg_ms');
          expect(latency).toHaveProperty('min_ms');
          expect(latency).toHaveProperty('max_ms');
          expect(latency).toHaveProperty('p50_ms');
          expect(latency).toHaveProperty('p95_ms');
          expect(latency).toHaveProperty('p99_ms');
          expect(latency).toHaveProperty('sample_count');
        }
      });
    }
  });

  it('provides readiness response', () => {
    expect(mockReadinessResponse).toHaveProperty('ready');
    expect(mockReadinessResponse).toHaveProperty('status');
    expect(mockReadinessResponse).toHaveProperty('services');
    expect(mockReadinessResponse).toHaveProperty('workers');
    expect(mockReadinessResponse).toHaveProperty('timestamp');

    // Validate workers
    if (mockReadinessResponse.workers) {
      expect(Array.isArray(mockReadinessResponse.workers)).toBe(true);
      mockReadinessResponse.workers.forEach((worker) => {
        expect(worker).toHaveProperty('name');
        expect(worker).toHaveProperty('running');
        expect(typeof worker.running).toBe('boolean');
      });
    }
  });
});

// ============================================================================
// Camera Endpoints Tests
// ============================================================================

describe('Camera Endpoints', () => {
  describe('GET /api/cameras', () => {
    it('returns list of cameras', async () => {
      const response = await makeRequest('/api/cameras');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('cameras');
      expect(data).toHaveProperty('count');
      expect(Array.isArray(data.cameras)).toBe(true);
      expect(data.count).toBe(data.cameras.length);
    });

    it('returns cameras with required fields', async () => {
      const response = await makeRequest('/api/cameras');
      const data = await response.json();

      data.cameras.forEach((camera: unknown) => {
        expect(camera).toHaveProperty('id');
        expect(camera).toHaveProperty('name');
        expect(camera).toHaveProperty('folder_path');
        expect(camera).toHaveProperty('status');
        expect(camera).toHaveProperty('created_at');
        expect(camera).toHaveProperty('last_seen_at');
      });
    });
  });

  describe('GET /api/cameras/:id', () => {
    it('returns a specific camera', async () => {
      const response = await makeRequest('/api/cameras/camera-1');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('id', 'camera-1');
      expect(data).toHaveProperty('name');
      expect(data).toHaveProperty('folder_path');
    });

    it('returns 404 for non-existent camera', async () => {
      const response = await makeRequest('/api/cameras/nonexistent');
      const data = await response.json();

      expect(response.status).toBe(404);
      expect(data).toHaveProperty('detail');
      expect(data.detail).toMatch(/not found/i);
    });
  });

  describe('GET /api/cameras/:id/snapshot', () => {
    it('returns image with correct content type', async () => {
      const response = await makeRequest('/api/cameras/camera-1/snapshot');

      expect(response.status).toBe(200);
      expect(response.headers.get('Content-Type')).toBe('image/png');
    });

    it('returns valid PNG data', async () => {
      const response = await makeRequest('/api/cameras/camera-1/snapshot');
      const buffer = await response.arrayBuffer();
      const bytes = new Uint8Array(buffer);

      // Check PNG magic number (first 8 bytes)
      expect(bytes[0]).toBe(0x89);
      expect(bytes[1]).toBe(0x50); // 'P'
      expect(bytes[2]).toBe(0x4e); // 'N'
      expect(bytes[3]).toBe(0x47); // 'G'
    });
  });
});

// ============================================================================
// Event Endpoints Tests
// ============================================================================

describe('Event Endpoints', () => {
  describe('GET /api/events', () => {
    it('returns paginated list of events', async () => {
      const response = await makeRequest('/api/events');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('events');
      expect(Array.isArray(data.events)).toBe(true);
      expectPaginationFields(data, mockEvents.length);
    });

    it('respects limit parameter', async () => {
      const response = await makeRequest('/api/events?limit=2');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.events.length).toBeLessThanOrEqual(2);
      expect(data.limit).toBe(2);
    });

    it('respects offset parameter', async () => {
      const response = await makeRequest('/api/events?offset=1');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.offset).toBe(1);
    });

    it('filters by camera_id', async () => {
      const response = await makeRequest('/api/events?camera_id=camera-1');
      const data = await response.json();

      expect(response.status).toBe(200);
      data.events.forEach((event: { camera_id: string }) => {
        expect(event.camera_id).toBe('camera-1');
      });
    });

    it('filters by risk_level', async () => {
      const response = await makeRequest('/api/events?risk_level=high');
      const data = await response.json();

      expect(response.status).toBe(200);
      data.events.forEach((event: { risk_level: string }) => {
        expect(event.risk_level).toBe('high');
      });
    });

    it('combines camera_id and risk_level filters', async () => {
      const response = await makeRequest('/api/events?camera_id=camera-1&risk_level=high');
      const data = await response.json();

      expect(response.status).toBe(200);
      data.events.forEach((event: { camera_id: string; risk_level: string }) => {
        expect(event.camera_id).toBe('camera-1');
        expect(event.risk_level).toBe('high');
      });
    });

    it('returns empty array when no events match filters', async () => {
      const response = await makeRequest('/api/events?camera_id=nonexistent');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.events).toEqual([]);
      expect(data.count).toBe(0);
    });

    it('returns events with required fields', async () => {
      const response = await makeRequest('/api/events');
      const data = await response.json();

      data.events.forEach((event: unknown) => {
        expect(event).toHaveProperty('id');
        expect(event).toHaveProperty('camera_id');
        expect(event).toHaveProperty('started_at');
        expect(event).toHaveProperty('risk_score');
        expect(event).toHaveProperty('risk_level');
        expect(event).toHaveProperty('summary');
        expect(event).toHaveProperty('reviewed');
      });
    });
  });

  describe('GET /api/events/:id', () => {
    it('returns a specific event', async () => {
      const response = await makeRequest('/api/events/1');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('id', 1);
      expect(data).toHaveProperty('camera_id');
      expect(data).toHaveProperty('risk_score');
    });

    it('returns 404 for non-existent event', async () => {
      const response = await makeRequest('/api/events/99999');
      const data = await response.json();

      expect(response.status).toBe(404);
      expect(data).toHaveProperty('detail');
      expect(data.detail).toMatch(/not found/i);
    });
  });

  describe('PATCH /api/events/:id', () => {
    it('updates an event and returns updated data', async () => {
      const response = await makeRequest('/api/events/1', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reviewed: true, notes: 'Updated note' }),
      });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('id', 1);
      expect(data).toHaveProperty('reviewed', true);
      expect(data).toHaveProperty('notes', 'Updated note');
    });

    it('returns 404 for non-existent event', async () => {
      const response = await makeRequest('/api/events/99999', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reviewed: true }),
      });
      const data = await response.json();

      expect(response.status).toBe(404);
      expect(data).toHaveProperty('detail');
    });

    it('preserves unmodified fields', async () => {
      const response = await makeRequest('/api/events/1', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reviewed: true }),
      });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('camera_id'); // Original field preserved
      expect(data).toHaveProperty('risk_score'); // Original field preserved
    });
  });

  describe('GET /api/events/stats', () => {
    it('returns event statistics', async () => {
      const response = await makeRequest('/api/events/stats');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('total_events');
      expect(data).toHaveProperty('events_by_risk_level');
      expect(data).toHaveProperty('events_by_camera');
    });

    it('includes all risk levels in statistics', async () => {
      const response = await makeRequest('/api/events/stats');
      const data = await response.json();

      expect(data.events_by_risk_level).toHaveProperty('critical');
      expect(data.events_by_risk_level).toHaveProperty('high');
      expect(data.events_by_risk_level).toHaveProperty('medium');
      expect(data.events_by_risk_level).toHaveProperty('low');
    });

    it('includes camera breakdown', async () => {
      const response = await makeRequest('/api/events/stats');
      const data = await response.json();

      expect(Array.isArray(data.events_by_camera)).toBe(true);
      expect(data.events_by_camera.length).toBeGreaterThan(0);

      data.events_by_camera.forEach((item: unknown) => {
        expect(item).toHaveProperty('camera_id');
        expect(item).toHaveProperty('camera_name');
        expect(item).toHaveProperty('event_count');
      });
    });
  });

  describe('GET /api/events/:id/detections', () => {
    it('returns paginated detections for an event', async () => {
      const response = await makeRequest('/api/events/1/detections');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('detections');
      expect(Array.isArray(data.detections)).toBe(true);
      expectPaginationFields(data, 0);
    });

    it('respects limit parameter', async () => {
      const response = await makeRequest('/api/events/1/detections?limit=50');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.limit).toBe(50);
    });

    it('respects offset parameter', async () => {
      const response = await makeRequest('/api/events/1/detections?offset=10');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.offset).toBe(10);
    });
  });
});

// ============================================================================
// System Endpoints Tests
// ============================================================================

describe('System Endpoints', () => {
  describe('GET /api/system/health', () => {
    it('returns health status', async () => {
      const response = await makeRequest('/api/system/health');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('status');
      expect(data).toHaveProperty('services');
      expect(data).toHaveProperty('timestamp');
    });

    it('includes service statuses', async () => {
      const response = await makeRequest('/api/system/health');
      const data = (await response.json()) as {
        services: Record<string, { status: string; message: string }>;
      };

      expect(data.services).toHaveProperty('database');
      expect(data.services).toHaveProperty('redis');
      expect(data.services).toHaveProperty('ai');

      Object.values(
        data.services as Record<string, { status: string; message: string }>
      ).forEach((service) => {
        expect(service).toHaveProperty('status');
        expect(service).toHaveProperty('message');
      });
    });
  });

  describe('GET /api/system/health/ready', () => {
    it('returns readiness status', async () => {
      const response = await makeRequest('/api/system/health/ready');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('ready');
      expect(data).toHaveProperty('status');
      expect(data).toHaveProperty('services');
      expect(data).toHaveProperty('workers');
      expect(data).toHaveProperty('timestamp');
    });

    it('includes worker statuses', async () => {
      const response = await makeRequest('/api/system/health/ready');
      const data = await response.json();

      expect(Array.isArray(data.workers)).toBe(true);
      data.workers.forEach((worker: unknown) => {
        expect(worker).toHaveProperty('name');
        expect(worker).toHaveProperty('running');
      });
    });
  });

  describe('GET /api/system/gpu', () => {
    it('returns GPU statistics', async () => {
      const response = await makeRequest('/api/system/gpu');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('utilization');
      expect(data).toHaveProperty('memory_used');
      expect(data).toHaveProperty('memory_total');
      expect(data).toHaveProperty('temperature');
      expect(data).toHaveProperty('power_usage');
    });

    it('returns valid GPU utilization range', async () => {
      const response = await makeRequest('/api/system/gpu');
      const data = (await response.json()) as { utilization: number };

      expect(data.utilization).toBeGreaterThanOrEqual(0);
      expect(data.utilization).toBeLessThanOrEqual(100);
    });

    it('returns valid memory values', async () => {
      const response = await makeRequest('/api/system/gpu');
      const data = (await response.json()) as {
        memory_used: number;
        memory_total: number;
      };

      expect(data.memory_used).toBeGreaterThanOrEqual(0);
      expect(data.memory_total).toBeGreaterThan(0);
      expect(data.memory_used).toBeLessThanOrEqual(data.memory_total);
    });
  });

  describe('GET /api/system/stats', () => {
    it('returns system statistics', async () => {
      const response = await makeRequest('/api/system/stats');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('total_cameras');
      expect(data).toHaveProperty('total_events');
      expect(data).toHaveProperty('total_detections');
      expect(data).toHaveProperty('uptime_seconds');
    });

    it('returns valid system counts', async () => {
      const response = await makeRequest('/api/system/stats');
      const data = (await response.json()) as {
        total_cameras: number;
        total_events: number;
        total_detections: number;
        uptime_seconds: number;
      };

      expect(data.total_cameras).toBeGreaterThanOrEqual(0);
      expect(data.total_events).toBeGreaterThanOrEqual(0);
      expect(data.total_detections).toBeGreaterThanOrEqual(0);
      expect(data.uptime_seconds).toBeGreaterThanOrEqual(0);
    });
  });

  describe('GET /api/system/telemetry', () => {
    it('returns telemetry data', async () => {
      const response = await makeRequest('/api/system/telemetry');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('queues');
      expect(data).toHaveProperty('latencies');
      expect(data).toHaveProperty('timestamp');
    });

    it('includes queue depths', async () => {
      const response = await makeRequest('/api/system/telemetry');
      const data = await response.json();

      expect(data.queues).toHaveProperty('detection_queue');
      expect(data.queues).toHaveProperty('analysis_queue');
      expect(typeof data.queues.detection_queue).toBe('number');
      expect(typeof data.queues.analysis_queue).toBe('number');
    });

    it('includes latency metrics', async () => {
      const response = await makeRequest('/api/system/telemetry');
      const data = (await response.json()) as {
        latencies: Record<
          string,
          {
            avg_ms: number;
            min_ms: number;
            max_ms: number;
            p50_ms: number;
            p95_ms: number;
            p99_ms: number;
            sample_count: number;
          }
        >;
      };

      expect(data.latencies).toHaveProperty('watch');
      expect(data.latencies).toHaveProperty('detect');

      Object.values(
        data.latencies as Record<
          string,
          {
            avg_ms: number;
            min_ms: number;
            max_ms: number;
            p50_ms: number;
            p95_ms: number;
            p99_ms: number;
            sample_count: number;
          }
        >
      ).forEach((latency) => {
        expect(latency).toHaveProperty('avg_ms');
        expect(latency).toHaveProperty('min_ms');
        expect(latency).toHaveProperty('max_ms');
        expect(latency).toHaveProperty('p50_ms');
        expect(latency).toHaveProperty('p95_ms');
        expect(latency).toHaveProperty('p99_ms');
        expect(latency).toHaveProperty('sample_count');
      });
    });
  });

  describe('GET /api/system/config', () => {
    it('returns system configuration', async () => {
      const response = await makeRequest('/api/system/config');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('retention_days');
      expect(data).toHaveProperty('batch_timeout_seconds');
      expect(data).toHaveProperty('idle_timeout_seconds');
      expect(data).toHaveProperty('risk_threshold_high');
      expect(data).toHaveProperty('risk_threshold_critical');
    });

    it('returns valid configuration values', async () => {
      const response = await makeRequest('/api/system/config');
      const data = (await response.json()) as {
        retention_days: number;
        batch_timeout_seconds: number;
        idle_timeout_seconds: number;
        risk_threshold_high: number;
        risk_threshold_critical: number;
      };

      expect(data.retention_days).toBeGreaterThan(0);
      expect(data.batch_timeout_seconds).toBeGreaterThan(0);
      expect(data.idle_timeout_seconds).toBeGreaterThan(0);
      expect(data.risk_threshold_high).toBeGreaterThan(0);
      expect(data.risk_threshold_critical).toBeGreaterThan(data.risk_threshold_high);
    });
  });
});

// ============================================================================
// Storage Endpoints Tests
// ============================================================================

describe('Storage Endpoints', () => {
  describe('GET /api/system/storage', () => {
    it('returns storage statistics', async () => {
      const response = await makeRequest('/api/system/storage');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('disk_used_bytes');
      expect(data).toHaveProperty('disk_total_bytes');
      expect(data).toHaveProperty('disk_free_bytes');
      expect(data).toHaveProperty('disk_usage_percent');
      expect(data).toHaveProperty('timestamp');
    });

    it('includes file type breakdowns', async () => {
      const response = await makeRequest('/api/system/storage');
      const data = await response.json();

      expect(data).toHaveProperty('thumbnails');
      expect(data).toHaveProperty('images');
      expect(data).toHaveProperty('clips');

      [data.thumbnails, data.images, data.clips].forEach((category: unknown) => {
        expect(category).toHaveProperty('file_count');
        expect(category).toHaveProperty('size_bytes');
      });
    });

    it('includes database record counts', async () => {
      const response = await makeRequest('/api/system/storage');
      const data = await response.json();

      expect(data).toHaveProperty('events_count');
      expect(data).toHaveProperty('detections_count');
      expect(data).toHaveProperty('gpu_stats_count');
      expect(data).toHaveProperty('logs_count');
    });

    it('returns valid disk usage values', async () => {
      const response = await makeRequest('/api/system/storage');
      const data = (await response.json()) as {
        disk_used_bytes: number;
        disk_total_bytes: number;
        disk_free_bytes: number;
        disk_usage_percent: number;
      };

      expect(data.disk_used_bytes).toBeGreaterThanOrEqual(0);
      expect(data.disk_total_bytes).toBeGreaterThan(0);
      expect(data.disk_free_bytes).toBeGreaterThanOrEqual(0);
      expect(data.disk_usage_percent).toBeGreaterThanOrEqual(0);
      expect(data.disk_usage_percent).toBeLessThanOrEqual(100);
    });
  });
});

// ============================================================================
// DLQ Endpoints Tests
// ============================================================================

describe('DLQ Endpoints', () => {
  describe('GET /api/dlq/stats', () => {
    it('returns DLQ statistics', async () => {
      const response = await makeRequest('/api/dlq/stats');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('queues');
      expect(data).toHaveProperty('total');
    });

    it('includes queue depths', async () => {
      const response = await makeRequest('/api/dlq/stats');
      const data = await response.json();

      expect(data.queues).toHaveProperty('dlq:detection_queue');
      expect(data.queues).toHaveProperty('dlq:analysis_queue');
      expect(typeof data.queues['dlq:detection_queue']).toBe('number');
      expect(typeof data.queues['dlq:analysis_queue']).toBe('number');
    });

    it('returns valid total count', async () => {
      const response = await makeRequest('/api/dlq/stats');
      const data = await response.json();

      expect(typeof data.total).toBe('number');
      expect(data.total).toBeGreaterThanOrEqual(0);
    });
  });
});

// ============================================================================
// Audit Endpoints Tests
// ============================================================================

describe('Audit Endpoints', () => {
  describe('GET /api/audit', () => {
    it('returns paginated audit logs', async () => {
      const response = await makeRequest('/api/audit');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('logs');
      expect(Array.isArray(data.logs)).toBe(true);
      expectPaginationFields(data, 0);
    });

    it('respects limit parameter', async () => {
      const response = await makeRequest('/api/audit?limit=50');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.limit).toBe(50);
    });

    it('respects offset parameter', async () => {
      const response = await makeRequest('/api/audit?offset=20');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.offset).toBe(20);
    });
  });

  describe('GET /api/audit/stats', () => {
    it('returns audit log statistics', async () => {
      const response = await makeRequest('/api/audit/stats');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('total_logs');
      expect(data).toHaveProperty('logs_by_action');
      expect(data).toHaveProperty('logs_by_resource_type');
      expect(data).toHaveProperty('logs_last_24h');
    });

    it('returns valid statistics', async () => {
      const response = await makeRequest('/api/audit/stats');
      const data = await response.json();

      expect(typeof data.total_logs).toBe('number');
      expect(typeof data.logs_by_action).toBe('object');
      expect(typeof data.logs_by_resource_type).toBe('object');
      expect(typeof data.logs_last_24h).toBe('number');
    });
  });
});

// ============================================================================
// Model Zoo Endpoints Tests
// ============================================================================

describe('Model Zoo Endpoints', () => {
  describe('GET /api/system/models', () => {
    it('returns model zoo status', async () => {
      const response = await makeRequest('/api/system/models');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('models');
      expect(data).toHaveProperty('vram_budget_mb');
      expect(data).toHaveProperty('vram_used_mb');
      expect(data).toHaveProperty('vram_available_mb');
    });

    it('includes model details', async () => {
      const response = await makeRequest('/api/system/models');
      const data = await response.json();

      expect(Array.isArray(data.models)).toBe(true);
      data.models.forEach((model: unknown) => {
        expect(model).toHaveProperty('name');
        expect(model).toHaveProperty('display_name');
        expect(model).toHaveProperty('vram_mb');
        expect(model).toHaveProperty('status');
        expect(model).toHaveProperty('category');
        expect(model).toHaveProperty('enabled');
        expect(model).toHaveProperty('available');
      });
    });

    it('returns valid VRAM values', async () => {
      const response = await makeRequest('/api/system/models');
      const data = (await response.json()) as {
        vram_used_mb: number;
        vram_budget_mb: number;
      };

      expect(data.vram_used_mb).toBeGreaterThanOrEqual(0);
      expect(data.vram_budget_mb).toBeGreaterThan(0);
      expect(data.vram_used_mb).toBeLessThanOrEqual(data.vram_budget_mb);
    });
  });

  describe('GET /api/system/model-zoo/status', () => {
    it('returns compact model zoo status', async () => {
      const response = await makeRequest('/api/system/model-zoo/status');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('models');
      expect(data).toHaveProperty('total_models');
      expect(data).toHaveProperty('loaded_count');
      expect(data).toHaveProperty('disabled_count');
      expect(data).toHaveProperty('vram_budget_mb');
      expect(data).toHaveProperty('vram_used_mb');
      expect(data).toHaveProperty('timestamp');
    });

    it('includes compact model data', async () => {
      const response = await makeRequest('/api/system/model-zoo/status');
      const data = await response.json();

      expect(Array.isArray(data.models)).toBe(true);
      data.models.forEach((model: unknown) => {
        expect(model).toHaveProperty('name');
        expect(model).toHaveProperty('display_name');
        expect(model).toHaveProperty('category');
        expect(model).toHaveProperty('status');
        expect(model).toHaveProperty('vram_mb');
        expect(model).toHaveProperty('enabled');
      });
    });

    it('returns valid model counts', async () => {
      const response = await makeRequest('/api/system/model-zoo/status');
      const data = (await response.json()) as {
        total_models: number;
        loaded_count: number;
        disabled_count: number;
      };

      expect(data.total_models).toBeGreaterThanOrEqual(0);
      expect(data.loaded_count).toBeGreaterThanOrEqual(0);
      expect(data.disabled_count).toBeGreaterThanOrEqual(0);
      expect(data.loaded_count).toBeLessThanOrEqual(data.total_models);
    });
  });
});

// ============================================================================
// Circuit Breaker Endpoints Tests
// ============================================================================

describe('Circuit Breaker Endpoints', () => {
  describe('GET /api/system/circuit-breakers', () => {
    it('returns circuit breaker status', async () => {
      const response = await makeRequest('/api/system/circuit-breakers');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('circuit_breakers');
    });

    it('includes breaker details', async () => {
      const response = await makeRequest('/api/system/circuit-breakers');
      const data = (await response.json()) as {
        circuit_breakers: Record<
          string,
          { state: string; failure_count: number; last_failure_time: string | null }
        >;
      };

      expect(data.circuit_breakers).toHaveProperty('rtdetr');
      expect(data.circuit_breakers).toHaveProperty('nemotron');
      expect(data.circuit_breakers).toHaveProperty('redis');

      Object.values(
        data.circuit_breakers as Record<
          string,
          { state: string; failure_count: number; last_failure_time: string | null }
        >
      ).forEach((breaker) => {
        expect(breaker).toHaveProperty('state');
        expect(breaker).toHaveProperty('failure_count');
        expect(breaker).toHaveProperty('last_failure_time');
      });
    });

    it('returns valid circuit breaker states', async () => {
      const response = await makeRequest('/api/system/circuit-breakers');
      const data = (await response.json()) as {
        circuit_breakers: Record<string, { state: string }>;
      };

      const validStates = ['closed', 'open', 'half_open'];
      Object.values(
        data.circuit_breakers as Record<string, { state: string }>
      ).forEach((breaker) => {
        expect(validStates).toContain(breaker.state);
      });
    });
  });
});

// ============================================================================
// Severity Endpoints Tests
// ============================================================================

describe('Severity Endpoints', () => {
  describe('GET /api/system/severity', () => {
    it('returns severity metadata', async () => {
      const response = await makeRequest('/api/system/severity');
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('definitions');
      expect(data).toHaveProperty('thresholds');
    });

    it('includes severity definitions', async () => {
      const response = await makeRequest('/api/system/severity');
      const data = await response.json();

      expect(Array.isArray(data.definitions)).toBe(true);
      data.definitions.forEach((definition: unknown) => {
        expect(definition).toHaveProperty('level');
        expect(definition).toHaveProperty('label');
        expect(definition).toHaveProperty('color');
        expect(definition).toHaveProperty('min_score');
        expect(definition).toHaveProperty('max_score');
      });
    });

    it('includes all severity levels', async () => {
      const response = await makeRequest('/api/system/severity');
      const data = await response.json();

      const levels = data.definitions.map((d: { level: string }) => d.level);
      expect(levels).toContain('low');
      expect(levels).toContain('medium');
      expect(levels).toContain('high');
      expect(levels).toContain('critical');
    });

    it('includes threshold values', async () => {
      const response = await makeRequest('/api/system/severity');
      const data = (await response.json()) as {
        thresholds: {
          low_max: number;
          medium_max: number;
          high_max: number;
        };
      };

      expect(data.thresholds).toHaveProperty('low_max');
      expect(data.thresholds).toHaveProperty('medium_max');
      expect(data.thresholds).toHaveProperty('high_max');

      expect(data.thresholds.low_max).toBeLessThan(data.thresholds.medium_max);
      expect(data.thresholds.medium_max).toBeLessThan(data.thresholds.high_max);
    });
  });
});

// ============================================================================
// Error Handling Tests
// ============================================================================

describe('Error Handling', () => {
  beforeEach(() => {
    // Reset to default handlers before each test
    server.use(...handlers);
  });

  it('handles custom 404 error override', async () => {
    // Override handler to return 404
    server.use(
      http.get('/api/cameras', () => {
        return HttpResponse.json({ detail: 'Service unavailable' }, { status: 404 });
      })
    );

    const response = await makeRequest('/api/cameras');
    expect(response.status).toBe(404);
  });

  it('handles custom 500 error override', async () => {
    // Override handler to return 500
    server.use(
      http.get('/api/system/health', () => {
        return HttpResponse.json({ detail: 'Internal server error' }, { status: 500 });
      })
    );

    const response = await makeRequest('/api/system/health');
    expect(response.status).toBe(500);
  });

  it('error responses include detail field', async () => {
    const response = await makeRequest('/api/cameras/nonexistent');
    const data = await response.json();

    expect(data).toHaveProperty('detail');
    expect(typeof data.detail).toBe('string');
  });
});

// ============================================================================
// Handler Registration Tests
// ============================================================================

describe('Handler Registration', () => {
  it('exports handlers array', () => {
    expect(Array.isArray(handlers)).toBe(true);
    expect(handlers.length).toBeGreaterThan(0);
  });

  it('all handlers are MSW http handlers', () => {
    handlers.forEach((handler) => {
      // MSW handlers have an info property
      expect(handler).toHaveProperty('info');
    });
  });
});

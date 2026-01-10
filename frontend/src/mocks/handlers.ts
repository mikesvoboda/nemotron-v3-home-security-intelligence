/**
 * MSW (Mock Service Worker) API handlers for unit tests.
 *
 * These handlers intercept HTTP requests during testing and return mock responses,
 * providing a more realistic and maintainable approach to API mocking than vi.mock().
 *
 * ## Usage Patterns
 *
 * 1. **Default handlers**: Most common API responses are defined here and loaded
 *    automatically via the test setup. These provide sensible defaults.
 *
 * 2. **Test-specific overrides**: Individual tests can override default handlers
 *    using `server.use()` for specific test scenarios:
 *
 *    ```typescript
 *    import { server } from '../mocks/server';
 *    import { http, HttpResponse } from 'msw';
 *
 *    it('handles API error', async () => {
 *      server.use(
 *        http.get('/api/cameras', () => {
 *          return HttpResponse.json({ detail: 'Server error' }, { status: 500 });
 *        })
 *      );
 *      // ... test error handling
 *    });
 *    ```
 *
 * 3. **Request validation**: Handlers can inspect request parameters to
 *    return different responses based on query params, path params, or body.
 *
 * ## Adding New Handlers
 *
 * When adding a new API endpoint, add a corresponding handler here with:
 * - Realistic mock data matching the API schema
 * - Support for common query parameters (limit, offset, filters)
 * - Error scenarios (400, 404, 500) as separate test-specific handlers
 *
 * @see https://mswjs.io/docs/
 */

import { http, HttpResponse, type StrictRequest, type DefaultBodyType } from 'msw';

import type {
  Camera,
  Event,
  EventListResponse,
  EventStatsResponse,
  GPUStats,
  HealthResponse,
  SystemStats,
  TelemetryResponse,
  DetectionListResponse,
  ReadinessResponse,
} from '../services/api';

// Type for handlers with path parameters
interface IdParams {
  id: string;
}

// ============================================================================
// Mock Data Factories
// ============================================================================

/**
 * Create a mock camera object with default values.
 * Override specific fields as needed for your test.
 */
export function createMockCamera(overrides: Partial<Camera> = {}): Camera {
  return {
    id: 'camera-1',
    name: 'Front Door',
    folder_path: '/export/foscam/front_door',
    status: 'online',
    created_at: '2024-01-01T00:00:00Z',
    last_seen_at: '2024-01-01T12:00:00Z',
    ...overrides,
  };
}

/**
 * Create a mock event object with default values.
 */
export function createMockEvent(overrides: Partial<Event> = {}): Event {
  return {
    id: 1,
    camera_id: 'camera-1',
    started_at: '2024-01-01T10:00:00Z',
    ended_at: '2024-01-01T10:02:00Z',
    risk_score: 50,
    risk_level: 'medium',
    summary: 'Person detected at front door',
    reviewed: false,
    detection_count: 3,
    notes: null,
    ...overrides,
  };
}

// ============================================================================
// Default Mock Data
// ============================================================================

export const mockCameras: Camera[] = [
  createMockCamera({ id: 'camera-1', name: 'Front Door', status: 'online' }),
  createMockCamera({ id: 'camera-2', name: 'Back Yard', status: 'online', folder_path: '/export/foscam/back_yard' }),
  createMockCamera({ id: 'camera-3', name: 'Garage', status: 'offline', folder_path: '/export/foscam/garage' }),
];

export const mockEvents: Event[] = [
  createMockEvent({ id: 1, camera_id: 'camera-1', risk_score: 75, risk_level: 'high', summary: 'Person detected at front door' }),
  createMockEvent({ id: 2, camera_id: 'camera-2', risk_score: 30, risk_level: 'low', summary: 'Animal detected in yard' }),
  createMockEvent({ id: 3, camera_id: 'camera-1', risk_score: 90, risk_level: 'critical', summary: 'Unknown person at entrance' }),
];

export const mockEventStats: EventStatsResponse = {
  total_events: 150,
  events_by_risk_level: {
    critical: 5,
    high: 25,
    medium: 60,
    low: 60,
  },
  events_by_camera: [
    { camera_id: 'camera-1', camera_name: 'Front Door', event_count: 80 },
    { camera_id: 'camera-2', camera_name: 'Back Yard', event_count: 50 },
    { camera_id: 'camera-3', camera_name: 'Garage', event_count: 20 },
  ],
};

export const mockGpuStats: GPUStats = {
  utilization: 45,
  memory_used: 8192,
  memory_total: 24576,
  temperature: 65,
  power_usage: 120,
};

export const mockHealthResponse: HealthResponse = {
  status: 'healthy',
  services: {
    database: { status: 'healthy', message: 'Database operational' },
    redis: { status: 'healthy', message: 'Redis connected' },
    ai: { status: 'healthy', message: 'AI services operational' },
  },
  timestamp: '2024-01-01T12:00:00Z',
};

export const mockSystemStats: SystemStats = {
  total_cameras: 3,
  total_events: 150,
  total_detections: 500,
  uptime_seconds: 86400,
};

export const mockTelemetry: TelemetryResponse = {
  queues: {
    detection_queue: 0,
    analysis_queue: 2,
  },
  latencies: {
    watch: { avg_ms: 10, min_ms: 5, max_ms: 50, p50_ms: 8, p95_ms: 40, p99_ms: 48, sample_count: 500 },
    detect: { avg_ms: 45.5, min_ms: 20, max_ms: 200, p50_ms: 40, p95_ms: 120, p99_ms: 180, sample_count: 500 },
  },
  timestamp: '2024-01-01T12:00:00Z',
};

export const mockReadinessResponse: ReadinessResponse = {
  ready: true,
  status: 'ready',
  services: {
    database: { status: 'healthy', message: 'Database operational' },
    redis: { status: 'healthy', message: 'Redis connected' },
    ai: { status: 'healthy', message: 'AI services operational' },
  },
  workers: [
    { name: 'file_watcher', running: true },
    { name: 'detection_worker', running: true },
    { name: 'analysis_worker', running: true },
    { name: 'cleanup_worker', running: true },
  ],
  timestamp: '2024-01-01T12:00:00Z',
};

// ============================================================================
// API Handlers
// ============================================================================

/**
 * Default API handlers for common endpoints.
 * These handlers are loaded automatically in the test setup.
 * Override specific handlers in individual tests using server.use().
 */
export const handlers = [
  // -------------------------------------------------------------------------
  // Camera Endpoints
  // -------------------------------------------------------------------------

  /**
   * GET /api/cameras - List all cameras
   */
  http.get('/api/cameras', () => {
    return HttpResponse.json({
      items: mockCameras,
      pagination: {
        total: mockCameras.length,
        limit: 50,
        offset: 0,
        has_more: false,
      },
    });
  }),

  /**
   * GET /api/cameras/:id - Get a specific camera
   */
  http.get<IdParams>('/api/cameras/:id', ({ params }: { params: IdParams }) => {
    const camera = mockCameras.find((c) => c.id === params.id);
    if (!camera) {
      return HttpResponse.json({ detail: 'Camera not found' }, { status: 404 });
    }
    return HttpResponse.json(camera);
  }),

  /**
   * GET /api/cameras/:id/snapshot - Get camera snapshot (returns image placeholder)
   */
  http.get('/api/cameras/:id/snapshot', () => {
    // Return a minimal valid PNG (1x1 transparent pixel)
    const pngData = new Uint8Array([
      0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d,
      0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
      0x08, 0x06, 0x00, 0x00, 0x00, 0x1f, 0x15, 0xc4, 0x89, 0x00, 0x00, 0x00,
      0x0a, 0x49, 0x44, 0x41, 0x54, 0x78, 0x9c, 0x63, 0x00, 0x01, 0x00, 0x00,
      0x05, 0x00, 0x01, 0x0d, 0x0a, 0x2d, 0xb4, 0x00, 0x00, 0x00, 0x00, 0x49,
      0x45, 0x4e, 0x44, 0xae, 0x42, 0x60, 0x82,
    ]);
    return new HttpResponse(pngData, {
      headers: { 'Content-Type': 'image/png' },
    });
  }),

  // -------------------------------------------------------------------------
  // Event Endpoints
  // -------------------------------------------------------------------------

  /**
   * GET /api/events - List events with filtering and pagination
   */
  http.get('/api/events', ({ request }: { request: StrictRequest<DefaultBodyType> }) => {
    const url = new URL(request.url);
    const limit = parseInt(url.searchParams.get('limit') || '50', 10);
    const offset = parseInt(url.searchParams.get('offset') || '0', 10);
    const cameraId = url.searchParams.get('camera_id');
    const riskLevel = url.searchParams.get('risk_level');

    let filteredEvents = [...mockEvents];

    // Apply filters
    if (cameraId) {
      filteredEvents = filteredEvents.filter((e) => e.camera_id === cameraId);
    }
    if (riskLevel) {
      filteredEvents = filteredEvents.filter((e) => e.risk_level === riskLevel);
    }

    // Apply pagination
    const paginatedEvents = filteredEvents.slice(offset, offset + limit);

    const response: EventListResponse = {
      items: paginatedEvents,
      pagination: {
        total: filteredEvents.length,
        limit,
        offset,
        has_more: offset + paginatedEvents.length < filteredEvents.length,
      },
    };

    return HttpResponse.json(response);
  }),

  /**
   * GET /api/events/stats - Get event statistics
   * NOTE: Must be registered BEFORE /api/events/:id to avoid route matching conflicts
   */
  http.get('/api/events/stats', () => {
    return HttpResponse.json(mockEventStats);
  }),

  /**
   * GET /api/events/:id - Get a specific event
   */
  http.get<IdParams>('/api/events/:id', ({ params }: { params: IdParams }) => {
    const eventId = parseInt(params.id, 10);
    const event = mockEvents.find((e) => e.id === eventId);
    if (!event) {
      return HttpResponse.json({ detail: 'Event not found' }, { status: 404 });
    }
    return HttpResponse.json(event);
  }),

  /**
   * PATCH /api/events/:id - Update an event
   */
  http.patch<IdParams>('/api/events/:id', async ({ params, request }: { params: IdParams; request: StrictRequest<DefaultBodyType> }) => {
    const eventId = parseInt(params.id, 10);
    const event = mockEvents.find((e) => e.id === eventId);
    if (!event) {
      return HttpResponse.json({ detail: 'Event not found' }, { status: 404 });
    }
    const updates = await request.json() as Partial<Event>;
    const updatedEvent = { ...event, ...updates };
    return HttpResponse.json(updatedEvent);
  }),

  /**
   * GET /api/events/:id/detections - Get detections for an event
   */
  http.get<IdParams>('/api/events/:id/detections', ({ request }: { request: StrictRequest<DefaultBodyType> }) => {
    const url = new URL(request.url);
    const limit = parseInt(url.searchParams.get('limit') || '100', 10);
    const offset = parseInt(url.searchParams.get('offset') || '0', 10);

    const response: DetectionListResponse = {
      items: [],
      pagination: {
        total: 0,
        limit,
        offset,
        has_more: false,
      },
    };

    return HttpResponse.json(response);
  }),

  // -------------------------------------------------------------------------
  // System Endpoints
  // -------------------------------------------------------------------------

  /**
   * GET /api/system/health - System health check
   */
  http.get('/api/system/health', () => {
    return HttpResponse.json(mockHealthResponse);
  }),

  /**
   * GET /api/system/health/ready - System readiness check
   */
  http.get('/api/system/health/ready', () => {
    return HttpResponse.json(mockReadinessResponse);
  }),

  /**
   * GET /api/system/gpu - GPU statistics
   */
  http.get('/api/system/gpu', () => {
    return HttpResponse.json(mockGpuStats);
  }),

  /**
   * GET /api/system/stats - System statistics
   */
  http.get('/api/system/stats', () => {
    return HttpResponse.json(mockSystemStats);
  }),

  /**
   * GET /api/system/telemetry - Pipeline telemetry
   */
  http.get('/api/system/telemetry', () => {
    return HttpResponse.json(mockTelemetry);
  }),

  /**
   * GET /api/system/config - System configuration
   */
  http.get('/api/system/config', () => {
    return HttpResponse.json({
      retention_days: 30,
      batch_timeout_seconds: 90,
      idle_timeout_seconds: 30,
      risk_threshold_high: 70,
      risk_threshold_critical: 90,
    });
  }),

  // -------------------------------------------------------------------------
  // Storage Endpoints
  // -------------------------------------------------------------------------

  /**
   * GET /api/system/storage - Storage statistics
   */
  http.get('/api/system/storage', () => {
    return HttpResponse.json({
      disk_used_bytes: 1073741824,
      disk_total_bytes: 10737418240,
      disk_free_bytes: 9663676416,
      disk_usage_percent: 10,
      thumbnails: { file_count: 1000, size_bytes: 104857600 },
      images: { file_count: 5000, size_bytes: 524288000 },
      clips: { file_count: 100, size_bytes: 419430400 },
      events_count: 150,
      detections_count: 500,
      gpu_stats_count: 10000,
      logs_count: 50000,
      timestamp: '2024-01-01T12:00:00Z',
    });
  }),

  // -------------------------------------------------------------------------
  // DLQ Endpoints
  // -------------------------------------------------------------------------

  /**
   * GET /api/dlq/stats - DLQ statistics
   */
  http.get('/api/dlq/stats', () => {
    return HttpResponse.json({
      queues: {
        'dlq:detection_queue': 0,
        'dlq:analysis_queue': 2,
      },
      total: 2,
    });
  }),

  // -------------------------------------------------------------------------
  // Audit Endpoints
  // -------------------------------------------------------------------------

  /**
   * GET /api/audit - List audit logs
   */
  http.get('/api/audit', ({ request }: { request: StrictRequest<DefaultBodyType> }) => {
    const url = new URL(request.url);
    const limit = parseInt(url.searchParams.get('limit') || '100', 10);
    const offset = parseInt(url.searchParams.get('offset') || '0', 10);

    return HttpResponse.json({
      items: [],
      pagination: {
        total: 0,
        limit,
        offset,
        has_more: false,
      },
    });
  }),

  /**
   * GET /api/audit/stats - Audit log statistics
   */
  http.get('/api/audit/stats', () => {
    return HttpResponse.json({
      total_logs: 0,
      logs_by_action: {},
      logs_by_resource_type: {},
      logs_last_24h: 0,
    });
  }),

  // -------------------------------------------------------------------------
  // Model Zoo Endpoints
  // -------------------------------------------------------------------------

  /**
   * GET /api/system/models - Model zoo status
   */
  http.get('/api/system/models', () => {
    return HttpResponse.json({
      models: [
        { name: 'rtdetr', display_name: 'RT-DETR', vram_mb: 1024, status: 'loaded', category: 'detection', enabled: true, available: true },
        { name: 'nemotron', display_name: 'Nemotron', vram_mb: 4096, status: 'loaded', category: 'reasoning', enabled: true, available: true },
      ],
      vram_budget_mb: 20480,
      vram_used_mb: 5120,
      vram_available_mb: 15360,
    });
  }),

  /**
   * GET /api/system/model-zoo/status - Model zoo compact status
   */
  http.get('/api/system/model-zoo/status', () => {
    return HttpResponse.json({
      models: [
        { name: 'rtdetr', display_name: 'RT-DETR', category: 'detection', status: 'loaded', vram_mb: 1024, last_used_at: '2024-01-01T12:00:00Z', enabled: true },
        { name: 'nemotron', display_name: 'Nemotron', category: 'reasoning', status: 'loaded', vram_mb: 4096, last_used_at: '2024-01-01T12:00:00Z', enabled: true },
      ],
      total_models: 2,
      loaded_count: 2,
      disabled_count: 0,
      vram_budget_mb: 20480,
      vram_used_mb: 5120,
      timestamp: '2024-01-01T12:00:00Z',
    });
  }),

  // -------------------------------------------------------------------------
  // Circuit Breaker Endpoints
  // -------------------------------------------------------------------------

  /**
   * GET /api/system/circuit-breakers - Circuit breaker status
   */
  http.get('/api/system/circuit-breakers', () => {
    return HttpResponse.json({
      circuit_breakers: {
        rtdetr: { state: 'closed', failure_count: 0, last_failure_time: null },
        nemotron: { state: 'closed', failure_count: 0, last_failure_time: null },
        redis: { state: 'closed', failure_count: 0, last_failure_time: null },
      },
    });
  }),

  // -------------------------------------------------------------------------
  // Severity Endpoints
  // -------------------------------------------------------------------------

  /**
   * GET /api/system/severity - Severity metadata
   */
  http.get('/api/system/severity', () => {
    return HttpResponse.json({
      definitions: [
        { level: 'low', label: 'Low', color: 'green', min_score: 0, max_score: 30 },
        { level: 'medium', label: 'Medium', color: 'yellow', min_score: 31, max_score: 60 },
        { level: 'high', label: 'High', color: 'orange', min_score: 61, max_score: 85 },
        { level: 'critical', label: 'Critical', color: 'red', min_score: 86, max_score: 100 },
      ],
      thresholds: { low_max: 30, medium_max: 60, high_max: 85 },
    });
  }),
];

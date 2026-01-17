/**
 * Comprehensive API mock with factory functions.
 *
 * Provides configurable mock factories for all API endpoints in the application.
 * Follows the same patterns as backend/tests/mock_utils.py.
 *
 * Note: These mocks return flexible objects that can be used in tests without
 * needing to match every field of the generated types exactly. The mocks use
 * `unknown` casts to allow tests to add only the fields they need.
 *
 * @example
 * ```typescript
 * import { vi } from 'vitest';
 * import {
 *   createMockApi,
 *   createMockCamerasResponse,
 *   createMockHealthResponse,
 * } from '../__mocks__';
 *
 * vi.mock('../services/api', () => createMockApi());
 *
 * // Or mock specific functions
 * vi.mock('../services/api', async () => {
 *   const actual = await vi.importActual('../services/api');
 *   return {
 *     ...actual,
 *     fetchCameras: vi.fn().mockResolvedValue(createMockCamerasResponse()),
 *   };
 * });
 * ```
 */

import { vi } from 'vitest';

// =============================================================================
// Types - Using Record<string, unknown> for flexibility
// =============================================================================

/**
 * Generic mock data type.
 * Tests can cast to specific types as needed.
 */
export type MockData = Record<string, unknown>;

/**
 * Mock API interface with all endpoint functions.
 */
export interface MockApi {
  // Camera endpoints
  fetchCameras: ReturnType<typeof vi.fn>;
  fetchCamera: ReturnType<typeof vi.fn>;
  createCamera: ReturnType<typeof vi.fn>;
  updateCamera: ReturnType<typeof vi.fn>;
  deleteCamera: ReturnType<typeof vi.fn>;

  // Health endpoints
  fetchHealth: ReturnType<typeof vi.fn>;
  fetchFullHealth: ReturnType<typeof vi.fn>;
  fetchReadiness: ReturnType<typeof vi.fn>;

  // System endpoints
  fetchGPUStats: ReturnType<typeof vi.fn>;
  fetchGpuHistory: ReturnType<typeof vi.fn>;
  fetchConfig: ReturnType<typeof vi.fn>;
  updateConfig: ReturnType<typeof vi.fn>;
  fetchStats: ReturnType<typeof vi.fn>;
  triggerCleanup: ReturnType<typeof vi.fn>;
  fetchTelemetry: ReturnType<typeof vi.fn>;

  // Event endpoints
  fetchEvents: ReturnType<typeof vi.fn>;
  fetchEvent: ReturnType<typeof vi.fn>;
  fetchEventStats: ReturnType<typeof vi.fn>;
  updateEvent: ReturnType<typeof vi.fn>;
  bulkUpdateEvents: ReturnType<typeof vi.fn>;
  searchEvents: ReturnType<typeof vi.fn>;

  // Detection endpoints
  fetchEventDetections: ReturnType<typeof vi.fn>;
  fetchDetectionStats: ReturnType<typeof vi.fn>;
  fetchDetectionEnrichment: ReturnType<typeof vi.fn>;

  // Zone endpoints
  fetchZones: ReturnType<typeof vi.fn>;
  fetchZone: ReturnType<typeof vi.fn>;
  createZone: ReturnType<typeof vi.fn>;
  updateZone: ReturnType<typeof vi.fn>;
  deleteZone: ReturnType<typeof vi.fn>;

  // Alert Rule endpoints
  fetchAlertRules: ReturnType<typeof vi.fn>;
  fetchAlertRule: ReturnType<typeof vi.fn>;
  createAlertRule: ReturnType<typeof vi.fn>;
  updateAlertRule: ReturnType<typeof vi.fn>;
  deleteAlertRule: ReturnType<typeof vi.fn>;

  // Utility functions
  buildWebSocketUrl: ReturnType<typeof vi.fn>;
  buildWebSocketOptions: ReturnType<typeof vi.fn>;
  getApiKey: ReturnType<typeof vi.fn>;
  isAbortError: ReturnType<typeof vi.fn>;
  isTimeoutError: ReturnType<typeof vi.fn>;
}

// =============================================================================
// Camera Factories
// =============================================================================

/**
 * Configuration options for creating a mock camera.
 */
export interface MockCameraOptions {
  /** Camera ID. Default: auto-generated */
  id?: string;
  /** Camera name. Default: 'Test Camera' */
  name?: string;
  /** Folder path. Default: '/export/foscam/{id}/' */
  folder_path?: string;
  /** Camera status. Default: 'online' */
  status?: 'online' | 'offline' | 'error' | 'unknown';
  /** Last seen timestamp. Default: current ISO timestamp */
  last_seen_at?: string | null;
  /** Created timestamp. Default: current ISO timestamp */
  created_at?: string;
}

let cameraIdCounter = 1;

/**
 * Resets the camera ID counter.
 * Call this in beforeEach for consistent IDs.
 */
export function resetCameraIdCounter(): void {
  cameraIdCounter = 1;
}

/**
 * Creates a mock camera with configurable properties.
 *
 * @param options - Configuration options
 * @returns A mock Camera object
 *
 * @example
 * ```typescript
 * const camera = createMockCamera({ name: 'Front Door' });
 * const offlineCamera = createMockCamera({ status: 'offline' });
 * ```
 */
export function createMockCamera(options: MockCameraOptions = {}): MockData {
  const id = options.id ?? `camera_${cameraIdCounter++}`;
  const now = new Date().toISOString();

  return {
    id,
    name: options.name ?? 'Test Camera',
    folder_path: options.folder_path ?? `/export/foscam/${id}/`,
    status: options.status ?? 'online',
    last_seen_at: options.last_seen_at ?? now,
    created_at: options.created_at ?? now,
  };
}

/**
 * Creates a list of mock cameras.
 *
 * @param count - Number of cameras to create
 * @returns Array of mock Camera objects
 */
export function createMockCameraList(count: number = 4): MockData[] {
  const locations = ['Front Door', 'Backyard', 'Garage', 'Side Entrance'];
  return Array.from({ length: count }, (_, i) => {
    const name = locations[i % locations.length];
    const id = name.toLowerCase().replace(/\s+/g, '_');
    return createMockCamera({
      id,
      name,
      folder_path: `/export/foscam/${id}/`,
    });
  });
}

/**
 * Creates a mock cameras response.
 *
 * @param cameras - Optional cameras array
 * @returns Mock response with cameras array
 */
export function createMockCamerasResponse(cameras?: MockData[]): MockData[] {
  return cameras ?? createMockCameraList();
}

// =============================================================================
// Health Factories
// =============================================================================

/**
 * Configuration options for creating a mock health response.
 */
export interface MockHealthOptions {
  /** Overall status. Default: 'healthy' */
  status?: string;
  /** Services status map. Default: all healthy */
  services?: Record<
    string,
    { status: string; message?: string | null; details?: Record<string, unknown> | null }
  >;
}

/**
 * Creates a mock health response.
 *
 * @param options - Configuration options
 * @returns A mock HealthResponse object
 */
export function createMockHealthResponse(options: MockHealthOptions = {}): MockData {
  return {
    status: options.status ?? 'healthy',
    services: options.services ?? {
      database: { status: 'healthy', message: null, details: null },
      redis: { status: 'healthy', message: null, details: null },
      rtdetr: { status: 'healthy', message: null, details: null },
      nemotron: { status: 'healthy', message: null, details: null },
    },
    timestamp: new Date().toISOString(),
  };
}

/**
 * Creates a healthy response.
 */
export function createHealthyResponse(): MockData {
  return createMockHealthResponse({ status: 'healthy' });
}

/**
 * Creates a degraded health response.
 */
export function createDegradedHealthResponse(): MockData {
  return createMockHealthResponse({
    status: 'degraded',
    services: {
      database: { status: 'healthy', message: null, details: null },
      redis: { status: 'healthy', message: null, details: null },
      rtdetr: { status: 'unhealthy', message: 'Connection failed', details: null },
      nemotron: { status: 'healthy', message: null, details: null },
    },
  });
}

/**
 * Creates an unhealthy response.
 */
export function createUnhealthyHealthResponse(): MockData {
  return createMockHealthResponse({
    status: 'unhealthy',
    services: {
      database: { status: 'unhealthy', message: 'Connection failed', details: null },
      redis: { status: 'unhealthy', message: 'Connection refused', details: null },
      rtdetr: { status: 'unhealthy', message: 'Service unavailable', details: null },
      nemotron: { status: 'unhealthy', message: 'Service unavailable', details: null },
    },
  });
}

// =============================================================================
// GPU Stats Factories
// =============================================================================

/**
 * Configuration options for creating mock GPU stats.
 */
export interface MockGPUStatsOptions {
  /** GPU utilization percentage. Default: 45 */
  utilization?: number | null;
  /** GPU memory used in MB. Default: 8192 */
  memory_used_mb?: number | null;
  /** GPU memory total in MB. Default: 24576 */
  memory_total_mb?: number | null;
  /** GPU temperature in Celsius. Default: 65 */
  temperature?: number | null;
  /** GPU power usage in watts. Default: 150 */
  power_draw_watts?: number | null;
  /** GPU name. Default: 'NVIDIA RTX A5500' */
  gpu_name?: string | null;
}

/**
 * Creates mock GPU stats.
 *
 * @param options - Configuration options
 * @returns A mock GPUStats object
 */
export function createMockGPUStats(options: MockGPUStatsOptions = {}): MockData {
  return {
    gpu_name: options.gpu_name ?? 'NVIDIA RTX A5500',
    utilization_percent: options.utilization ?? 45,
    memory_used_mb: options.memory_used_mb ?? 8192,
    memory_total_mb: options.memory_total_mb ?? 24576,
    temperature_celsius: options.temperature ?? 65,
    power_draw_watts: options.power_draw_watts ?? 150,
    timestamp: new Date().toISOString(),
  };
}

// =============================================================================
// Event Factories
// =============================================================================

/**
 * Configuration options for creating a mock event.
 */
export interface MockEventOptions {
  /** Event ID. Default: auto-generated */
  id?: number;
  /** Camera ID. Default: 'front_door' */
  camera_id?: string;
  /** Risk score (0-100). Default: 50 */
  risk_score?: number;
  /** Risk level. Default: 'medium' */
  risk_level?: 'low' | 'medium' | 'high' | 'critical';
  /** Event summary. Default: 'Test event' */
  summary?: string;
  /** Whether event is reviewed. Default: false */
  reviewed?: boolean;
  /** Batch ID. Default: auto-generated */
  batch_id?: string;
  /** Detection count. Default: 3 */
  detection_count?: number;
}

let eventIdCounter = 1;

/**
 * Resets the event ID counter.
 */
export function resetEventIdCounter(): void {
  eventIdCounter = 1;
}

/**
 * Creates a mock event.
 *
 * @param options - Configuration options
 * @returns A mock Event object
 */
export function createMockEvent(options: MockEventOptions = {}): MockData {
  const id = options.id ?? eventIdCounter++;
  const now = new Date().toISOString();

  return {
    id,
    camera_id: options.camera_id ?? 'front_door',
    risk_score: options.risk_score ?? 50,
    risk_level: options.risk_level ?? 'medium',
    summary: options.summary ?? 'Test event',
    reviewed: options.reviewed ?? false,
    batch_id: options.batch_id ?? `batch-${id}`,
    detection_count: options.detection_count ?? 3,
    started_at: now,
    ended_at: now,
    created_at: now,
  };
}

/**
 * Creates a list of mock events.
 *
 * @param count - Number of events to create
 * @returns Array of mock Event objects
 */
export function createMockEventList(count: number = 10): MockData[] {
  const riskLevels: Array<'low' | 'medium' | 'high' | 'critical'> = [
    'low',
    'medium',
    'high',
    'critical',
  ];
  const riskScores = [15, 45, 75, 95];

  return Array.from({ length: count }, (_, i) => {
    const levelIndex = i % riskLevels.length;
    return createMockEvent({
      risk_level: riskLevels[levelIndex],
      risk_score: riskScores[levelIndex],
    });
  });
}

// =============================================================================
// Detection Factories
// =============================================================================

/**
 * Configuration options for creating a mock detection.
 */
export interface MockDetectionOptions {
  /** Detection ID. Default: auto-generated */
  id?: number;
  /** Event ID. Default: 1 */
  event_id?: number;
  /** Object label. Default: 'person' */
  label?: string;
  /** Confidence score (0-1). Default: 0.95 */
  confidence?: number;
  /** Bounding box [x, y, width, height]. Default: [100, 100, 200, 300] */
  bbox?: number[];
}

let detectionIdCounter = 1;

/**
 * Resets the detection ID counter.
 */
export function resetDetectionIdCounter(): void {
  detectionIdCounter = 1;
}

/**
 * Creates a mock detection.
 *
 * @param options - Configuration options
 * @returns A mock Detection object
 */
export function createMockDetection(options: MockDetectionOptions = {}): MockData {
  const id = options.id ?? detectionIdCounter++;

  return {
    id,
    event_id: options.event_id ?? 1,
    label: options.label ?? 'person',
    confidence: options.confidence ?? 0.95,
    bbox: options.bbox ?? [100, 100, 200, 300],
    created_at: new Date().toISOString(),
  };
}

/**
 * Creates a list of mock detections for an event.
 *
 * @param eventId - Event ID
 * @param count - Number of detections
 * @returns Array of mock Detection objects
 */
export function createMockDetectionList(eventId: number = 1, count: number = 3): MockData[] {
  const labels = ['person', 'vehicle', 'animal', 'package'];

  return Array.from({ length: count }, (_, i) =>
    createMockDetection({
      event_id: eventId,
      label: labels[i % labels.length],
      confidence: 0.9 - i * 0.1,
    })
  );
}

// =============================================================================
// Zone Factories
// =============================================================================

/**
 * Configuration options for creating a mock zone.
 */
export interface MockZoneOptions {
  /** Zone ID. Default: auto-generated */
  id?: string;
  /** Camera ID. Default: 'front_door' */
  camera_id?: string;
  /** Zone name. Default: 'Test Zone' */
  name?: string;
  /** Zone type. Default: 'entry_point' */
  zone_type?: string;
  /** Zone shape. Default: 'polygon' */
  shape?: 'polygon' | 'rectangle';
  /** Zone coordinates. Default: [[0,0], [100,0], [100,100], [0,100]] */
  coordinates?: number[][];
  /** Whether zone is enabled. Default: true */
  enabled?: boolean;
  /** Zone color. Default: '#ff0000' */
  color?: string;
  /** Zone priority. Default: 1 */
  priority?: number;
}

let zoneIdCounter = 1;

/**
 * Resets the zone ID counter.
 */
export function resetZoneIdCounter(): void {
  zoneIdCounter = 1;
}

/**
 * Creates a mock zone.
 *
 * @param options - Configuration options
 * @returns A mock Zone object
 */
export function createMockZone(options: MockZoneOptions = {}): MockData {
  const id = options.id ?? `zone_${zoneIdCounter++}`;

  return {
    id,
    camera_id: options.camera_id ?? 'front_door',
    name: options.name ?? 'Test Zone',
    zone_type: options.zone_type ?? 'entry_point',
    shape: options.shape ?? 'polygon',
    coordinates: options.coordinates ?? [
      [0, 0],
      [100, 0],
      [100, 100],
      [0, 100],
    ],
    enabled: options.enabled ?? true,
    color: options.color ?? '#ff0000',
    priority: options.priority ?? 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

// =============================================================================
// Alert Rule Factories
// =============================================================================

/**
 * Configuration options for creating a mock alert rule.
 */
export interface MockAlertRuleOptions {
  /** Rule ID. Default: auto-generated */
  id?: string;
  /** Rule name. Default: 'Test Rule' */
  name?: string;
  /** Rule description. Default: 'Test alert rule' */
  description?: string;
  /** Whether rule is enabled. Default: true */
  enabled?: boolean;
  /** Minimum risk score to trigger. Default: 70 */
  min_risk_score?: number;
  /** Object types to match. Default: ['person'] */
  object_types?: string[];
  /** Camera IDs to match. Default: [] (all cameras) */
  camera_ids?: string[];
}

let alertRuleIdCounter = 1;

/**
 * Resets the alert rule ID counter.
 */
export function resetAlertRuleIdCounter(): void {
  alertRuleIdCounter = 1;
}

/**
 * Creates a mock alert rule.
 *
 * @param options - Configuration options
 * @returns A mock AlertRule object
 */
export function createMockAlertRule(options: MockAlertRuleOptions = {}): MockData {
  const id = options.id ?? `rule_${alertRuleIdCounter++}`;

  return {
    id,
    name: options.name ?? 'Test Rule',
    description: options.description ?? 'Test alert rule',
    enabled: options.enabled ?? true,
    min_risk_score: options.min_risk_score ?? 70,
    object_types: options.object_types ?? ['person'],
    camera_ids: options.camera_ids ?? [],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

// =============================================================================
// System Config Factories
// =============================================================================

/**
 * Configuration options for creating a mock system config.
 */
export interface MockSystemConfigOptions {
  /** Retention days. Default: 30 */
  retention_days?: number;
  /** Batch window seconds. Default: 90 */
  batch_window_seconds?: number;
  /** Batch idle timeout seconds. Default: 30 */
  batch_idle_timeout_seconds?: number;
  /** Detection confidence threshold. Default: 0.5 */
  detection_confidence_threshold?: number;
  /** App name. Default: 'Home Security Intelligence' */
  app_name?: string;
  /** App version. Default: '1.0.0' */
  version?: string;
  /** Grafana URL. Default: 'http://localhost:3001' */
  grafana_url?: string;
}

/**
 * Creates a mock system config.
 *
 * @param options - Configuration options
 * @returns A mock SystemConfig object
 */
export function createMockSystemConfig(options: MockSystemConfigOptions = {}): MockData {
  return {
    retention_days: options.retention_days ?? 30,
    batch_window_seconds: options.batch_window_seconds ?? 90,
    batch_idle_timeout_seconds: options.batch_idle_timeout_seconds ?? 30,
    detection_confidence_threshold: options.detection_confidence_threshold ?? 0.5,
    app_name: options.app_name ?? 'Home Security Intelligence',
    version: options.version ?? '1.0.0',
    grafana_url: options.grafana_url ?? 'http://localhost:3001',
  };
}

// =============================================================================
// System Stats Factories
// =============================================================================

/**
 * Configuration options for creating mock system stats.
 */
export interface MockSystemStatsOptions {
  /** Total events count. Default: 1000 */
  total_events?: number;
  /** Total detections count. Default: 5000 */
  total_detections?: number;
  /** Total cameras count. Default: 4 */
  total_cameras?: number;
  /** Uptime seconds. Default: 86400 (1 day) */
  uptime_seconds?: number;
}

/**
 * Creates mock system stats.
 *
 * @param options - Configuration options
 * @returns A mock SystemStats object
 */
export function createMockSystemStats(options: MockSystemStatsOptions = {}): MockData {
  return {
    total_events: options.total_events ?? 1000,
    total_detections: options.total_detections ?? 5000,
    total_cameras: options.total_cameras ?? 4,
    uptime_seconds: options.uptime_seconds ?? 86400,
  };
}

// =============================================================================
// Telemetry Factories
// =============================================================================

/**
 * Creates mock telemetry response.
 *
 * @returns A mock TelemetryResponse object
 */
export function createMockTelemetry(): MockData {
  return {
    timestamp: new Date().toISOString(),
    queues: {
      detection: { pending: 5, processing: 2 },
      analysis: { pending: 2, processing: 1 },
    },
    latencies: {
      detection: { p50_ms: 45, p95_ms: 120, p99_ms: 200, sample_count: 100 },
      analysis: { p50_ms: 500, p95_ms: 1200, p99_ms: 2000, sample_count: 50 },
    },
  };
}

// =============================================================================
// Readiness Factories
// =============================================================================

/**
 * Creates mock readiness response.
 *
 * @param ready - Whether system is ready
 * @returns A mock ReadinessResponse object
 */
export function createMockReadiness(ready: boolean = true): MockData {
  return {
    ready,
    status: ready ? 'healthy' : 'unhealthy',
    timestamp: new Date().toISOString(),
    services: {
      database: { status: ready ? 'healthy' : 'unhealthy', message: null, details: null },
      redis: { status: ready ? 'healthy' : 'unhealthy', message: null, details: null },
      rtdetr: { status: ready ? 'healthy' : 'unhealthy', message: null, details: null },
      nemotron: { status: ready ? 'healthy' : 'unhealthy', message: null, details: null },
    },
  };
}

// =============================================================================
// Full API Mock Factory
// =============================================================================

/**
 * Creates a complete mock API object with all endpoints.
 *
 * @returns A MockApi object with all functions mocked
 *
 * @example
 * ```typescript
 * import { vi } from 'vitest';
 * import { createMockApi } from '../__mocks__';
 *
 * vi.mock('../services/api', () => createMockApi());
 * ```
 */
export function createMockApi(): MockApi {
  return {
    // Camera endpoints
    fetchCameras: vi.fn().mockResolvedValue(createMockCameraList()),
    fetchCamera: vi
      .fn()
      .mockImplementation((id: string) => Promise.resolve(createMockCamera({ id }))),
    createCamera: vi
      .fn()
      .mockImplementation((data: MockCameraOptions) => Promise.resolve(createMockCamera(data))),
    updateCamera: vi
      .fn()
      .mockImplementation((id: string, data: MockCameraOptions) =>
        Promise.resolve(createMockCamera({ id, ...data }))
      ),
    deleteCamera: vi.fn().mockResolvedValue(undefined),

    // Health endpoints
    fetchHealth: vi.fn().mockResolvedValue(createMockHealthResponse()),
    fetchFullHealth: vi.fn().mockResolvedValue(createMockHealthResponse()),
    fetchReadiness: vi.fn().mockResolvedValue(createMockReadiness()),

    // System endpoints
    fetchGPUStats: vi.fn().mockResolvedValue(createMockGPUStats()),
    fetchGpuHistory: vi.fn().mockResolvedValue({ samples: [] }),
    fetchConfig: vi.fn().mockResolvedValue(createMockSystemConfig()),
    updateConfig: vi
      .fn()
      .mockImplementation((data: MockData) =>
        Promise.resolve({ ...createMockSystemConfig(), ...data })
      ),
    fetchStats: vi.fn().mockResolvedValue(createMockSystemStats()),
    triggerCleanup: vi.fn().mockResolvedValue({ deleted_count: 0 }),
    fetchTelemetry: vi.fn().mockResolvedValue(createMockTelemetry()),

    // Event endpoints
    fetchEvents: vi.fn().mockResolvedValue({ events: createMockEventList(), total: 10 }),
    fetchEvent: vi
      .fn()
      .mockImplementation((id: number) => Promise.resolve(createMockEvent({ id }))),
    fetchEventStats: vi.fn().mockResolvedValue({
      total: 100,
      by_risk_level: { low: 40, medium: 35, high: 20, critical: 5 },
    }),
    updateEvent: vi
      .fn()
      .mockImplementation((id: number, data: MockData) =>
        Promise.resolve({ ...createMockEvent({ id }), ...data })
      ),
    bulkUpdateEvents: vi.fn().mockResolvedValue({ updated_count: 5 }),
    searchEvents: vi.fn().mockResolvedValue({ results: createMockEventList(5), total: 5 }),

    // Detection endpoints
    fetchEventDetections: vi
      .fn()
      .mockImplementation((eventId: number) =>
        Promise.resolve({ detections: createMockDetectionList(eventId), total: 3 })
      ),
    fetchDetectionStats: vi.fn().mockResolvedValue({
      total: 500,
      by_label: { person: 300, vehicle: 150, animal: 50 },
    }),
    fetchDetectionEnrichment: vi.fn().mockResolvedValue({
      license_plate: null,
      face: null,
      vehicle: null,
    }),

    // Zone endpoints
    fetchZones: vi.fn().mockResolvedValue({ zones: [createMockZone()], total: 1 }),
    fetchZone: vi
      .fn()
      .mockImplementation((cameraId: string, zoneId: string) =>
        Promise.resolve(createMockZone({ id: zoneId, camera_id: cameraId }))
      ),
    createZone: vi
      .fn()
      .mockImplementation((cameraId: string, data: MockZoneOptions) =>
        Promise.resolve(createMockZone({ camera_id: cameraId, ...data }))
      ),
    updateZone: vi
      .fn()
      .mockImplementation((cameraId: string, zoneId: string, data: MockZoneOptions) =>
        Promise.resolve(createMockZone({ id: zoneId, camera_id: cameraId, ...data }))
      ),
    deleteZone: vi.fn().mockResolvedValue(undefined),

    // Alert Rule endpoints
    fetchAlertRules: vi.fn().mockResolvedValue({ rules: [createMockAlertRule()], total: 1 }),
    fetchAlertRule: vi
      .fn()
      .mockImplementation((id: string) => Promise.resolve(createMockAlertRule({ id }))),
    createAlertRule: vi
      .fn()
      .mockImplementation((data: MockAlertRuleOptions) =>
        Promise.resolve(createMockAlertRule(data))
      ),
    updateAlertRule: vi
      .fn()
      .mockImplementation((id: string, data: MockAlertRuleOptions) =>
        Promise.resolve(createMockAlertRule({ id, ...data }))
      ),
    deleteAlertRule: vi.fn().mockResolvedValue(undefined),

    // Utility functions
    buildWebSocketUrl: vi.fn().mockReturnValue('ws://localhost:8000/ws/events'),
    buildWebSocketOptions: vi.fn().mockReturnValue({
      url: 'ws://localhost:8000/ws/events',
      protocols: [],
    }),
    getApiKey: vi.fn().mockReturnValue(undefined),
    isAbortError: vi.fn().mockReturnValue(false),
    isTimeoutError: vi.fn().mockReturnValue(false),
  };
}

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Resets all ID counters.
 * Call this in beforeEach for consistent test data.
 */
export function resetAllIdCounters(): void {
  resetCameraIdCounter();
  resetEventIdCounter();
  resetDetectionIdCounter();
  resetZoneIdCounter();
  resetAlertRuleIdCounter();
}

/**
 * Creates a mock fetch function that returns specified data.
 *
 * @param data - Data to return from fetch
 * @param status - HTTP status code. Default: 200
 * @returns A mock fetch function
 *
 * @example
 * ```typescript
 * const mockFetch = createMockFetch({ cameras: [] });
 * global.fetch = mockFetch;
 * ```
 */
export function createMockFetch<T>(data: T, status: number = 200): ReturnType<typeof vi.fn> {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  });
}

/**
 * Creates a mock fetch that rejects with an error.
 *
 * @param error - Error to reject with
 * @returns A mock fetch function that rejects
 */
export function createMockFetchError(error: Error): ReturnType<typeof vi.fn> {
  return vi.fn().mockRejectedValue(error);
}

/**
 * Creates a mock fetch that returns an HTTP error.
 *
 * @param status - HTTP status code
 * @param message - Error message
 * @returns A mock fetch function that returns an error response
 */
export function createMockFetchHttpError(
  status: number,
  message: string
): ReturnType<typeof vi.fn> {
  return vi.fn().mockResolvedValue({
    ok: false,
    status,
    json: () => Promise.resolve({ detail: message }),
    text: () => Promise.resolve(message),
  });
}

// =============================================================================
// Parameterized Test Helpers
// =============================================================================

/**
 * Test cases for object types.
 * Use with describe.each() for parameterized tests.
 */
export const OBJECT_TYPE_TEST_CASES: string[] = [
  'person',
  'vehicle',
  'animal',
  'package',
  'unknown',
];

/**
 * Test cases for HTTP status codes.
 * Use with describe.each() for parameterized tests.
 */
export const HTTP_STATUS_TEST_CASES: Array<{
  status: number;
  shouldRetry: boolean;
  description: string;
}> = [
  { status: 200, shouldRetry: false, description: 'Success' },
  { status: 201, shouldRetry: false, description: 'Created' },
  { status: 204, shouldRetry: false, description: 'No Content' },
  { status: 400, shouldRetry: false, description: 'Bad Request' },
  { status: 401, shouldRetry: false, description: 'Unauthorized' },
  { status: 403, shouldRetry: false, description: 'Forbidden' },
  { status: 404, shouldRetry: false, description: 'Not Found' },
  { status: 500, shouldRetry: true, description: 'Internal Server Error' },
  { status: 502, shouldRetry: true, description: 'Bad Gateway' },
  { status: 503, shouldRetry: true, description: 'Service Unavailable' },
  { status: 504, shouldRetry: true, description: 'Gateway Timeout' },
];

// =============================================================================
// Default Mock Exports
// These are used when tests call vi.mock('../../services/api') without a factory
// =============================================================================

// Camera endpoints
export const fetchCameras = vi.fn().mockResolvedValue([]);
export const fetchCamera = vi.fn().mockResolvedValue({});
export const createCamera = vi.fn().mockResolvedValue({});
export const updateCamera = vi.fn().mockResolvedValue({});
export const deleteCamera = vi.fn().mockResolvedValue(undefined);

// Health endpoints
export const fetchHealth = vi.fn().mockResolvedValue({ status: 'healthy' });
export const fetchFullHealth = vi.fn().mockResolvedValue({ status: 'healthy' });
export const fetchReadiness = vi.fn().mockResolvedValue({ ready: true });

// System endpoints
export const fetchGPUStats = vi.fn().mockResolvedValue({});
export const fetchGpuHistory = vi.fn().mockResolvedValue({ samples: [] });
export const fetchConfig = vi.fn().mockResolvedValue({});
export const updateConfig = vi.fn().mockResolvedValue({});
export const fetchStats = vi.fn().mockResolvedValue({});
export const triggerCleanup = vi.fn().mockResolvedValue({ deleted_count: 0 });
export const fetchTelemetry = vi.fn().mockResolvedValue({});

// Event endpoints
export const fetchEvents = vi.fn().mockResolvedValue({ events: [], total: 0 });
export const fetchEvent = vi.fn().mockResolvedValue({});
export const fetchEventStats = vi.fn().mockResolvedValue({});
export const updateEvent = vi.fn().mockResolvedValue({});
export const bulkUpdateEvents = vi.fn().mockResolvedValue({ updated_count: 0 });
export const searchEvents = vi.fn().mockResolvedValue({ results: [], total: 0 });

// Detection endpoints
export const fetchEventDetections = vi.fn().mockResolvedValue({ detections: [], total: 0 });
export const fetchDetectionStats = vi.fn().mockResolvedValue({});
export const fetchDetectionEnrichment = vi.fn().mockResolvedValue({});

// Zone endpoints
export const fetchZones = vi.fn().mockResolvedValue({ zones: [], total: 0 });
export const fetchZone = vi.fn().mockResolvedValue({});
export const createZone = vi.fn().mockResolvedValue({});
export const updateZone = vi.fn().mockResolvedValue({});
export const deleteZone = vi.fn().mockResolvedValue(undefined);

// Alert Rule endpoints
export const fetchAlertRules = vi.fn().mockResolvedValue({ rules: [], total: 0 });
export const fetchAlertRule = vi.fn().mockResolvedValue({});
export const createAlertRule = vi.fn().mockResolvedValue({});
export const updateAlertRule = vi.fn().mockResolvedValue({});
export const deleteAlertRule = vi.fn().mockResolvedValue(undefined);

// Utility functions
export const buildWebSocketUrl = vi.fn().mockReturnValue('ws://localhost:8000/ws/events');
export const buildWebSocketOptions = vi.fn().mockReturnValue({
  url: 'ws://localhost:8000/ws/events',
  protocols: [],
});
export const getApiKey = vi.fn().mockReturnValue(undefined);
export const isAbortError = vi.fn().mockReturnValue(false);
export const isTimeoutError = vi.fn().mockReturnValue(false);
export const getCameraSnapshotUrl = vi.fn().mockReturnValue('');
export const getMediaUrl = vi.fn().mockReturnValue('');
export const getThumbnailUrl = vi.fn().mockReturnValue('');
export const getDetectionImageUrl = vi.fn().mockReturnValue('');

// Circuit breaker endpoints
export const fetchCircuitBreakers = vi.fn().mockResolvedValue({ circuit_breakers: {} });
export const resetCircuitBreaker = vi.fn().mockResolvedValue({ success: true });

// Additional endpoints
export const fetchPipelineLatency = vi.fn().mockResolvedValue({});
export const fetchPipelineLatencyHistory = vi.fn().mockResolvedValue({ samples: [] });
export const fetchLogs = vi.fn().mockResolvedValue({
  items: [],
  pagination: { total: 0, limit: 50, offset: 0, has_more: false, next_cursor: null },
});
export const fetchLogStats = vi.fn().mockResolvedValue({});
export const submitFrontendLog = vi.fn().mockResolvedValue({ success: true });
export const fetchCameraActivityBaseline = vi.fn().mockResolvedValue({});
export const fetchCameraClassBaseline = vi.fn().mockResolvedValue({});
export const fetchAnomalyConfig = vi.fn().mockResolvedValue({});
export const updateAnomalyConfig = vi.fn().mockResolvedValue({});

// Storage endpoints
export const fetchStorageStats = vi.fn().mockResolvedValue({});
export const previewCleanup = vi.fn().mockResolvedValue({});

// DLQ endpoints
export const fetchDlqStats = vi.fn().mockResolvedValue({});
export const fetchDlqJobs = vi.fn().mockResolvedValue({ jobs: [] });
export const clearDlq = vi.fn().mockResolvedValue({ success: true });
export const requeueAllDlqJobs = vi.fn().mockResolvedValue({ success: true });

// Model Zoo endpoints
export const fetchModelZooStatus = vi.fn().mockResolvedValue({});
export const fetchModelZooCompactStatus = vi.fn().mockResolvedValue({});
export const fetchModelZooLatencyHistory = vi.fn().mockResolvedValue({ samples: [] });

// Notification endpoints
export const fetchNotificationConfig = vi.fn().mockResolvedValue({});
export const testNotification = vi.fn().mockResolvedValue({ success: true });

// Notification preferences endpoints
export const fetchNotificationPreferences = vi.fn().mockResolvedValue({
  id: 1,
  enabled: true,
  sound: 'default',
  risk_filters: ['critical', 'high', 'medium'],
});
export const updateNotificationPreferences = vi.fn().mockResolvedValue({
  id: 1,
  enabled: true,
  sound: 'default',
  risk_filters: ['critical', 'high', 'medium'],
});
export const fetchCameraNotificationSettings = vi.fn().mockResolvedValue({
  settings: [],
  count: 0,
});
export const fetchCameraNotificationSetting = vi.fn().mockResolvedValue({
  id: '1',
  camera_id: 'camera1',
  enabled: true,
  risk_threshold: 50,
});
export const updateCameraNotificationSetting = vi.fn().mockResolvedValue({
  id: '1',
  camera_id: 'camera1',
  enabled: true,
  risk_threshold: 50,
});
export const fetchQuietHoursPeriods = vi.fn().mockResolvedValue({
  periods: [],
  count: 0,
});
export const createQuietHoursPeriod = vi.fn().mockResolvedValue({
  id: '1',
  label: 'Night Time',
  start_time: '22:00:00',
  end_time: '06:00:00',
  days: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'],
});
export const deleteQuietHoursPeriod = vi.fn().mockResolvedValue(undefined);

// Severity endpoints
export const fetchSeverityConfig = vi.fn().mockResolvedValue({});
export const fetchSeverityMetadata = vi.fn().mockResolvedValue({});
export const updateSeverityThresholds = vi.fn().mockResolvedValue({});

// Scene change endpoints
export const fetchSceneChanges = vi.fn().mockResolvedValue({ changes: [] });
export const acknowledgeSceneChange = vi.fn().mockResolvedValue({ success: true });

// Entity endpoints (NEM-2075: pagination envelope format)
export const fetchEntities = vi.fn().mockResolvedValue({
  items: [],
  pagination: { total: 0, limit: 50, offset: 0, has_more: false },
});
export const fetchEntity = vi.fn().mockResolvedValue({});
export const fetchEntityHistory = vi.fn().mockResolvedValue({ history: [] });
export const fetchEventEntityMatches = vi
  .fn()
  .mockResolvedValue({ event_id: 0, person_matches: [], vehicle_matches: [], total_matches: 0 });

// Audit log endpoints
export const fetchAuditLogs = vi.fn().mockResolvedValue({
  items: [],
  pagination: { total: 0, limit: 50, offset: 0, has_more: false, next_cursor: null },
});
export const fetchAuditStats = vi.fn().mockResolvedValue({});

// AI Audit endpoints
export const fetchAiAuditStats = vi.fn().mockResolvedValue({});

// Event clip endpoints
export const fetchEventClipInfo = vi.fn().mockResolvedValue({});
export const generateEventClip = vi.fn().mockResolvedValue({});
export const exportEventsCSV = vi.fn().mockResolvedValue('');

// Alert Rule endpoints
export const testAlertRule = vi.fn().mockResolvedValue({ success: true });

// Media URL endpoints
export const getDetectionVideoThumbnailUrl = vi.fn().mockReturnValue('');

// Job endpoints
export const fetchJobs = vi.fn().mockResolvedValue({
  items: [],
  pagination: { total: 0, limit: 50, offset: 0, has_more: false },
});
export const fetchJob = vi.fn().mockResolvedValue({});
export const searchJobs = vi.fn().mockResolvedValue({
  data: [],
  meta: { total: 0, limit: 50, offset: 0, has_more: false },
  aggregations: { by_status: {}, by_type: {} },
});

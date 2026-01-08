/**
 * Centralized mock for API service.
 */

import { vi } from 'vitest';

import type {
  Camera,
  Event,
  EventListResponse,
  EventStatsResponse,
  GPUStats,
  HealthResponse,
  SystemStats,
  TelemetryResponse,
} from '../../types/generated';

// Default mock data
const defaultCameras: Camera[] = [
  {
    id: 'camera-1',
    name: 'Front Door',
    folder_path: '/export/foscam/front_door',
    status: 'online',
    created_at: '2024-01-01T00:00:00Z',
    last_seen_at: '2024-01-01T12:00:00Z',
  },
  {
    id: 'camera-2',
    name: 'Back Yard',
    folder_path: '/export/foscam/back_yard',
    status: 'online',
    created_at: '2024-01-01T00:00:00Z',
    last_seen_at: '2024-01-01T12:00:00Z',
  },
];

const defaultEvents: Event[] = [
  {
    id: 1,
    camera_id: 'camera-1',
    started_at: '2024-01-01T10:00:00Z',
    ended_at: '2024-01-01T10:02:00Z',
    risk_score: 75,
    risk_level: 'high',
    summary: 'Person detected at front door',
    reviewed: false,
    detection_count: 5,
    notes: null,
  },
];

const defaultEventStats: EventStatsResponse = {
  total_events: 150,
  events_by_risk_level: { critical: 5, high: 25, medium: 60, low: 60 },
  events_by_camera: [
    { camera_id: 'camera-1', camera_name: 'Front Door', event_count: 80 },
    { camera_id: 'camera-2', camera_name: 'Back Yard', event_count: 70 },
  ],
};

const defaultGpuStats: GPUStats = {
  utilization: 45,
  memory_used: 8192,
  memory_total: 24576,
  temperature: 65,
  power_usage: 120,
};

const defaultHealth: HealthResponse = {
  status: 'healthy',
  services: {
    database: { status: 'healthy', message: 'Database operational' },
    redis: { status: 'healthy', message: 'Redis connected' },
    ai: { status: 'healthy', message: 'AI services operational' },
  },
  timestamp: '2024-01-01T12:00:00Z',
};

// Mock state
let mockCameras: Camera[] = [...defaultCameras];
let mockEvents: Event[] = [...defaultEvents];
let mockEventStats: EventStatsResponse = { ...defaultEventStats };
let mockGpuStats: GPUStats = { ...defaultGpuStats };
let mockHealth: HealthResponse = { ...defaultHealth };

// Error states
let fetchCamerasError: Error | null = null;
let fetchEventsError: Error | null = null;
let fetchEventStatsError: Error | null = null;
let fetchGpuStatsError: Error | null = null;
let fetchHealthError: Error | null = null;

// Configuration functions
export function setMockCameras(cameras: Camera[]): void {
  mockCameras = [...cameras];
}

export function setMockEvents(events: Event[]): void {
  mockEvents = [...events];
}

export function setMockEventStats(stats: Partial<EventStatsResponse>): void {
  mockEventStats = { ...defaultEventStats, ...stats };
}

export function setMockGpuStats(stats: Partial<GPUStats>): void {
  mockGpuStats = { ...defaultGpuStats, ...stats };
}

export function setMockHealth(health: Partial<HealthResponse>): void {
  mockHealth = { ...defaultHealth, ...health };
}

export function setMockFetchCamerasError(error: Error | null): void {
  fetchCamerasError = error;
}

export function setMockFetchEventsError(error: Error | null): void {
  fetchEventsError = error;
}

export function setMockFetchEventStatsError(error: Error | null): void {
  fetchEventStatsError = error;
}

export function setMockFetchGpuStatsError(error: Error | null): void {
  fetchGpuStatsError = error;
}

export function setMockFetchHealthError(error: Error | null): void {
  fetchHealthError = error;
}

// Factory functions
export function createMockCamera(overrides: Partial<Camera> = {}): Camera {
  return {
    id: `camera-${Date.now()}`,
    name: 'Test Camera',
    folder_path: '/export/foscam/test',
    status: 'online',
    created_at: new Date().toISOString(),
    last_seen_at: new Date().toISOString(),
    ...overrides,
  };
}

export function createMockEvent(overrides: Partial<Event> = {}): Event {
  return {
    id: Math.floor(Math.random() * 10000),
    camera_id: 'camera-1',
    started_at: new Date().toISOString(),
    ended_at: new Date().toISOString(),
    risk_score: 50,
    risk_level: 'medium',
    summary: 'Test event',
    reviewed: false,
    detection_count: 3,
    notes: null,
    ...overrides,
  };
}

// ApiError class
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: unknown
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

// Mock API functions
export const fetchCameras = vi.fn((): Promise<Camera[]> => {
  if (fetchCamerasError) return Promise.reject(fetchCamerasError);
  return Promise.resolve(mockCameras);
});

export const fetchCamera = vi.fn((id: string): Promise<Camera> => {
  const camera = mockCameras.find((c) => c.id === id);
  if (!camera) return Promise.reject(new ApiError(404, 'Camera not found'));
  return Promise.resolve(camera);
});

export const createCamera = vi.fn((data: unknown): Promise<Camera> => {
  return Promise.resolve(createMockCamera(data as Partial<Camera>));
});

export const updateCamera = vi.fn((id: string, data: unknown): Promise<Camera> => {
  const camera = mockCameras.find((c) => c.id === id);
  if (!camera) return Promise.reject(new ApiError(404, 'Camera not found'));
  return Promise.resolve({ ...camera, ...(data as Partial<Camera>) });
});

export const deleteCamera = vi.fn((): Promise<void> => Promise.resolve());

export const getCameraSnapshotUrl = vi.fn((cameraId: string): string => {
  return `/api/cameras/${encodeURIComponent(cameraId)}/snapshot`;
});

export const fetchEvents = vi.fn((params?: unknown): Promise<EventListResponse> => {
  if (fetchEventsError) return Promise.reject(fetchEventsError);
  const p = params as { limit?: number; offset?: number } | undefined;
  const limit = p?.limit ?? 50;
  const offset = p?.offset ?? 0;
  const events = mockEvents.slice(offset, offset + limit);
  return Promise.resolve({
    events,
    count: mockEvents.length,
    limit,
    offset,
    has_more: offset + events.length < mockEvents.length,
  });
});

export const fetchEvent = vi.fn((id: number): Promise<Event> => {
  const event = mockEvents.find((e) => e.id === id);
  if (!event) return Promise.reject(new ApiError(404, 'Event not found'));
  return Promise.resolve(event);
});

export const fetchEventStats = vi.fn((): Promise<EventStatsResponse> => {
  if (fetchEventStatsError) return Promise.reject(fetchEventStatsError);
  return Promise.resolve(mockEventStats);
});

export const updateEvent = vi.fn((id: number, data: unknown): Promise<Event> => {
  const event = mockEvents.find((e) => e.id === id);
  if (!event) return Promise.reject(new ApiError(404, 'Event not found'));
  return Promise.resolve({ ...event, ...(data as Partial<Event>) });
});

export const fetchHealth = vi.fn((): Promise<HealthResponse> => {
  if (fetchHealthError) return Promise.reject(fetchHealthError);
  return Promise.resolve(mockHealth);
});

export const fetchGPUStats = vi.fn((): Promise<GPUStats> => {
  if (fetchGpuStatsError) return Promise.reject(fetchGpuStatsError);
  return Promise.resolve(mockGpuStats);
});

export const fetchGpuHistory = vi.fn(() => Promise.resolve({
  samples: [],
  count: 0,
  period_minutes: 60,
}));

export const fetchStats = vi.fn((): Promise<SystemStats> => Promise.resolve({
  total_cameras: mockCameras.length,
  total_events: mockEvents.length,
  total_detections: 500,
  uptime_seconds: 86400,
}));

export const fetchTelemetry = vi.fn((): Promise<TelemetryResponse> => Promise.resolve({
  queues: { detection_queue: 0, analysis_queue: 2 },
  latencies: {
    watch: { avg_ms: 10, min_ms: 5, max_ms: 50, p50_ms: 8, p95_ms: 40, p99_ms: 48, sample_count: 500 },
    detect: { avg_ms: 45.5, min_ms: 20, max_ms: 200, p50_ms: 40, p95_ms: 120, p99_ms: 180, sample_count: 500 },
  },
  timestamp: '2024-01-01T12:00:00Z',
}));

export const fetchReadiness = vi.fn(() => Promise.resolve({
  ready: true,
  status: 'ready',
  services: mockHealth.services,
  workers: [
    { name: 'file_watcher', running: true },
    { name: 'detection_worker', running: true },
  ],
  timestamp: new Date().toISOString(),
}));

export const fetchConfig = vi.fn(() => Promise.resolve({
  retention_days: 30,
  batch_timeout_seconds: 90,
  idle_timeout_seconds: 30,
  risk_threshold_high: 70,
  risk_threshold_critical: 90,
}));

export const updateConfig = vi.fn((data: unknown) => Promise.resolve({
  retention_days: 30,
  batch_timeout_seconds: 90,
  idle_timeout_seconds: 30,
  risk_threshold_high: 70,
  risk_threshold_critical: 90,
  ...(data as Record<string, unknown>),
}));

export const triggerCleanup = vi.fn(() => Promise.resolve({ deleted_count: 0 }));

export const buildWebSocketOptions = vi.fn((endpoint: string) => ({
  url: `ws://localhost:8000${endpoint}`,
  protocols: undefined,
}));

export const buildWebSocketUrl = vi.fn((endpoint: string): string => {
  return `ws://localhost:8000${endpoint}`;
});

export const getApiKey = vi.fn((): string | undefined => undefined);

export const getMediaUrl = vi.fn((cameraId: string, filename: string): string => {
  return `/api/media/${cameraId}/${filename}`;
});

export const getThumbnailUrl = vi.fn((filename: string): string => {
  return `/api/thumbnails/${filename}`;
});

export const getDetectionImageUrl = vi.fn((detectionId: number): string => {
  return `/api/detections/${detectionId}/image`;
});

export const getDetectionFullImageUrl = vi.fn((detectionId: number): string => {
  return `/api/detections/${detectionId}/full`;
});

export const getDetectionVideoUrl = vi.fn((detectionId: number): string => {
  return `/api/detections/${detectionId}/video`;
});

export const getDetectionVideoThumbnailUrl = vi.fn((detectionId: number): string => {
  return `/api/detections/${detectionId}/video/thumbnail`;
});

export const getEventClipUrl = vi.fn((clipFilename: string): string => {
  return `/api/clips/${clipFilename}`;
});

export const isAbortError = vi.fn((error: unknown): boolean => {
  if (error instanceof DOMException && error.name === 'AbortError') return true;
  if (error instanceof Error && error.name === 'AbortError') return true;
  return false;
});

export const shouldRetry = vi.fn((status: number): boolean => {
  return status === 0 || (status >= 500 && status < 600);
});

export const getRetryDelay = vi.fn((attempt: number): number => {
  return 1000 * Math.pow(2, attempt);
});

export const sleep = vi.fn((ms: number): Promise<void> => {
  return new Promise((resolve) => setTimeout(resolve, ms));
});

export const getRequestKey = vi.fn((method: string, url: string): string | null => {
  if (method.toUpperCase() !== 'GET') return null;
  return `${method.toUpperCase()}:${url}`;
});

export const getInFlightRequestCount = vi.fn((): number => 0);

export const clearInFlightRequests = vi.fn((): void => {});

// Stub functions for less commonly used endpoints
export const bulkUpdateEvents = vi.fn(() => Promise.resolve({ updated: 0 }));
export const fetchEventDetections = vi.fn(() => Promise.resolve({ detections: [], count: 0, limit: 100, offset: 0, has_more: false }));
export const fetchStorageStats = vi.fn(() => Promise.resolve({}));
export const previewCleanup = vi.fn(() => Promise.resolve({}));
export const fetchDlqStats = vi.fn(() => Promise.resolve({}));
export const fetchDlqJobs = vi.fn(() => Promise.resolve({}));
export const requeueDlqJob = vi.fn(() => Promise.resolve({}));
export const requeueAllDlqJobs = vi.fn(() => Promise.resolve({}));
export const clearDlq = vi.fn(() => Promise.resolve({}));
export const fetchLogStats = vi.fn(() => Promise.resolve({}));
export const fetchLogs = vi.fn(() => Promise.resolve({}));
export const searchEvents = vi.fn(() => Promise.resolve({}));
export const fetchAuditLogs = vi.fn(() => Promise.resolve({}));
export const fetchAuditStats = vi.fn(() => Promise.resolve({}));
export const fetchAuditLog = vi.fn(() => Promise.resolve({}));
export const fetchAlertRules = vi.fn(() => Promise.resolve({}));
export const fetchAlertRule = vi.fn(() => Promise.resolve({}));
export const createAlertRule = vi.fn(() => Promise.resolve({}));
export const updateAlertRule = vi.fn(() => Promise.resolve({}));
export const deleteAlertRule = vi.fn(() => Promise.resolve());
export const testAlertRule = vi.fn(() => Promise.resolve({}));
export const fetchZones = vi.fn(() => Promise.resolve({}));
export const fetchZone = vi.fn(() => Promise.resolve({}));
export const createZone = vi.fn(() => Promise.resolve({}));
export const updateZone = vi.fn(() => Promise.resolve({}));
export const deleteZone = vi.fn(() => Promise.resolve());
export const fetchAiAuditStats = vi.fn(() => Promise.resolve({}));
export const fetchModelLeaderboard = vi.fn(() => Promise.resolve({}));
export const fetchAuditRecommendations = vi.fn(() => Promise.resolve({}));
export const fetchEventAudit = vi.fn(() => Promise.resolve({}));
export const fetchCircuitBreakers = vi.fn(() => Promise.resolve({}));
export const resetCircuitBreaker = vi.fn(() => Promise.resolve({}));
export const restartService = vi.fn(() => Promise.resolve({}));
export const fetchSeverityMetadata = vi.fn(() => Promise.resolve({}));
export const fetchSeverityConfig = vi.fn(() => Promise.resolve({}));
export const updateSeverityThresholds = vi.fn(() => Promise.resolve({}));
export const fetchDetectionEnrichment = vi.fn(() => Promise.resolve({}));
export const fetchModelZooStatus = vi.fn(() => Promise.resolve({}));
export const fetchModelZooCompactStatus = vi.fn(() => Promise.resolve({}));
export const fetchModelZooLatencyHistory = vi.fn(() => Promise.resolve({}));
export const fetchAllPrompts = vi.fn(() => Promise.resolve({}));
export const fetchModelPrompt = vi.fn(() => Promise.resolve({}));
export const updateModelPrompt = vi.fn(() => Promise.resolve({}));
export const testPrompt = vi.fn(() => Promise.resolve({}));
export const fetchAllPromptsHistory = vi.fn(() => Promise.resolve({}));
export const fetchModelHistory = vi.fn(() => Promise.resolve({}));
export const restorePromptVersion = vi.fn(() => Promise.resolve({}));
export const exportPrompts = vi.fn(() => Promise.resolve({}));
export const importPrompts = vi.fn(() => Promise.resolve({}));
export const fetchEntities = vi.fn(() => Promise.resolve({}));
export const fetchEntity = vi.fn(() => Promise.resolve({}));
export const fetchEntityHistory = vi.fn(() => Promise.resolve({}));
export const fetchSceneChanges = vi.fn(() => Promise.resolve({}));
export const acknowledgeSceneChange = vi.fn(() => Promise.resolve({}));
export const fetchEventClipInfo = vi.fn(() => Promise.resolve({}));
export const generateEventClip = vi.fn(() => Promise.resolve({}));
export const fetchNotificationConfig = vi.fn(() => Promise.resolve({}));
export const testNotification = vi.fn(() => Promise.resolve({}));
export const fetchAnomalyConfig = vi.fn(() => Promise.resolve({}));
export const updateAnomalyConfig = vi.fn(() => Promise.resolve({}));
export const fetchCameraActivityBaseline = vi.fn(() => Promise.resolve({}));
export const fetchCameraClassBaseline = vi.fn(() => Promise.resolve({}));
export const fetchPipelineLatency = vi.fn(() => Promise.resolve({}));
export const fetchPipelineLatencyHistory = vi.fn(() => Promise.resolve({}));
export const fetchDetectionStats = vi.fn(() => Promise.resolve({}));
export const exportEventsCSV = vi.fn(() => Promise.resolve());

// Reset function
export function resetMocks(): void {
  mockCameras = [...defaultCameras];
  mockEvents = [...defaultEvents];
  mockEventStats = { ...defaultEventStats };
  mockGpuStats = { ...defaultGpuStats };
  mockHealth = { ...defaultHealth };

  fetchCamerasError = null;
  fetchEventsError = null;
  fetchEventStatsError = null;
  fetchGpuStatsError = null;
  fetchHealthError = null;

  // Reset all mock functions
  fetchCameras.mockClear();
  fetchCamera.mockClear();
  createCamera.mockClear();
  updateCamera.mockClear();
  deleteCamera.mockClear();
  getCameraSnapshotUrl.mockClear();
  fetchEvents.mockClear();
  fetchEvent.mockClear();
  fetchEventStats.mockClear();
  updateEvent.mockClear();
  fetchHealth.mockClear();
  fetchGPUStats.mockClear();
  fetchGpuHistory.mockClear();
  fetchStats.mockClear();
  fetchTelemetry.mockClear();
  fetchReadiness.mockClear();
  fetchConfig.mockClear();
  updateConfig.mockClear();
  triggerCleanup.mockClear();
  buildWebSocketOptions.mockClear();
  buildWebSocketUrl.mockClear();
  getApiKey.mockClear();
  clearInFlightRequests.mockClear();
}

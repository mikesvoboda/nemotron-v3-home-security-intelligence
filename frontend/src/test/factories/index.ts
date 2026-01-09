/**
 * Test data factories for creating mock entities.
 *
 * Factories provide a consistent way to create test data with sensible defaults
 * while allowing specific fields to be overridden for individual tests.
 *
 * ## Usage
 *
 * ### Basic Usage
 *
 * ```typescript
 * import { cameraFactory, eventFactory } from '@/test/factories';
 *
 * const camera = cameraFactory();
 * expect(camera.id).toBe('camera-1');
 *
 * const customCamera = cameraFactory({ name: 'Back Door' });
 * expect(customCamera.name).toBe('Back Door');
 * ```
 *
 * ### Creating Multiple Entities
 *
 * ```typescript
 * const cameras = cameraFactoryList(3);
 * expect(cameras).toHaveLength(3);
 *
 * const customCameras = cameraFactoryList(2, (i) => ({
 *   id: `custom-${i}`,
 *   name: `Camera ${i}`
 * }));
 * ```
 *
 * ### Creating Related Entities
 *
 * ```typescript
 * const camera = cameraFactory({ id: 'front-door' });
 * const event = eventFactory({ camera_id: camera.id });
 * const detection = detectionFactory({ camera_id: camera.id, event_id: event.id });
 * ```
 *
 * @module test/factories
 */

import type {
  Camera,
  Event,
  Detection,
  GPUStats,
  HealthResponse,
  SystemStats,
} from '@/services/api';

// ============================================================================
// Counter for Unique IDs
// ============================================================================

let counter = 0;

/**
 * Generate a unique ID for test entities.
 * Resets to 0 at the start of each test file.
 */
export function uniqueId(prefix = 'test'): string {
  counter++;
  return `${prefix}-${counter}`;
}

/**
 * Reset the counter (called automatically by test setup).
 */
export function resetCounter(): void {
  counter = 0;
}

// ============================================================================
// Camera Factory
// ============================================================================

/**
 * Create a mock Camera object with sensible defaults.
 *
 * @param overrides - Partial Camera object to override defaults
 * @returns Complete Camera object
 *
 * @example
 * ```typescript
 * const camera = cameraFactory({ name: 'Front Door' });
 * expect(camera.status).toBe('online');
 * ```
 */
export function cameraFactory(overrides: Partial<Camera> = {}): Camera {
  return {
    id: uniqueId('camera'),
    name: 'Test Camera',
    folder_path: '/export/foscam/test_camera',
    status: 'online',
    created_at: '2024-01-01T00:00:00Z',
    last_seen_at: new Date().toISOString(),
    ...overrides,
  };
}

/**
 * Create a list of Camera objects.
 *
 * @param count - Number of cameras to create
 * @param overrideFn - Optional function to customize each camera (receives index)
 * @returns Array of Camera objects
 *
 * @example
 * ```typescript
 * const cameras = cameraFactoryList(3, (i) => ({ name: `Camera ${i}` }));
 * ```
 */
export function cameraFactoryList(
  count: number,
  overrideFn?: (index: number) => Partial<Camera>
): Camera[] {
  return Array.from({ length: count }, (_, i) => {
    const overrides = overrideFn?.(i) || {};
    return cameraFactory(overrides);
  });
}

// ============================================================================
// Event Factory
// ============================================================================

/**
 * Create a mock Event object with sensible defaults.
 *
 * @param overrides - Partial Event object to override defaults
 * @returns Complete Event object
 *
 * @example
 * ```typescript
 * const event = eventFactory({ risk_score: 85, risk_level: 'high' });
 * ```
 */
export function eventFactory(overrides: Partial<Event> = {}): Event {
  const id = counter;
  return {
    id,
    camera_id: uniqueId('camera'),
    started_at: new Date(Date.now() - 60000).toISOString(), // 1 minute ago
    ended_at: new Date().toISOString(),
    risk_score: 50,
    risk_level: 'medium',
    summary: 'Test event summary',
    reviewed: false,
    detection_count: 1,
    notes: null,
    ...overrides,
  };
}

/**
 * Create a list of Event objects.
 *
 * @param count - Number of events to create
 * @param overrideFn - Optional function to customize each event (receives index)
 * @returns Array of Event objects
 */
export function eventFactoryList(
  count: number,
  overrideFn?: (index: number) => Partial<Event>
): Event[] {
  return Array.from({ length: count }, (_, i) => {
    const overrides = overrideFn?.(i) || {};
    return eventFactory(overrides);
  });
}

// ============================================================================
// Detection Factory
// ============================================================================

/**
 * Create a mock Detection object with sensible defaults.
 *
 * @param overrides - Partial Detection object to override defaults
 * @returns Complete Detection object
 *
 * @example
 * ```typescript
 * const detection = detectionFactory({ object_type: 'person', confidence: 0.95 });
 * ```
 */
export function detectionFactory(overrides: Partial<Detection> = {}): Detection {
  return {
    id: counter++,
    camera_id: uniqueId('camera'),
    event_id: counter,
    timestamp: new Date().toISOString(),
    object_type: 'person',
    confidence: 0.85,
    bbox: [100, 100, 200, 200],
    image_path: '/path/to/image.jpg',
    ...overrides,
  };
}

/**
 * Create a list of Detection objects.
 *
 * @param count - Number of detections to create
 * @param overrideFn - Optional function to customize each detection (receives index)
 * @returns Array of Detection objects
 */
export function detectionFactoryList(
  count: number,
  overrideFn?: (index: number) => Partial<Detection>
): Detection[] {
  return Array.from({ length: count }, (_, i) => {
    const overrides = overrideFn?.(i) || {};
    return detectionFactory(overrides);
  });
}

// ============================================================================
// GPU Stats Factory
// ============================================================================

/**
 * Create a mock GPUStats object with sensible defaults.
 *
 * @param overrides - Partial GPUStats object to override defaults
 * @returns Complete GPUStats object
 */
export function gpuStatsFactory(overrides: Partial<GPUStats> = {}): GPUStats {
  return {
    gpu_utilization: 45.5,
    memory_used: 8192,
    memory_total: 24576,
    memory_percent: 33.3,
    temperature: 65,
    power_draw: 150,
    power_limit: 300,
    timestamp: new Date().toISOString(),
    ...overrides,
  };
}

/**
 * Create a list of GPUStats objects (useful for history/charts).
 *
 * @param count - Number of stats to create
 * @param overrideFn - Optional function to customize each stat (receives index)
 * @returns Array of GPUStats objects
 */
export function gpuStatsFactoryList(
  count: number,
  overrideFn?: (index: number) => Partial<GPUStats>
): GPUStats[] {
  return Array.from({ length: count }, (_, i) => {
    const overrides = overrideFn?.(i) || {};
    return gpuStatsFactory(overrides);
  });
}

// ============================================================================
// Health Response Factory
// ============================================================================

/**
 * Create a mock HealthResponse object with sensible defaults.
 *
 * @param overrides - Partial HealthResponse object to override defaults
 * @returns Complete HealthResponse object
 */
export function healthResponseFactory(
  overrides: Partial<HealthResponse> = {}
): HealthResponse {
  return {
    status: 'healthy',
    services: {
      database: { status: 'healthy', message: 'Database operational' },
      redis: { status: 'healthy', message: 'Redis connected' },
      ai: { status: 'healthy', message: 'AI services operational' },
    },
    timestamp: new Date().toISOString(),
    ...overrides,
  };
}

// ============================================================================
// System Stats Factory
// ============================================================================

/**
 * Create a mock SystemStats object with sensible defaults.
 *
 * @param overrides - Partial SystemStats object to override defaults
 * @returns Complete SystemStats object
 */
export function systemStatsFactory(
  overrides: Partial<SystemStats> = {}
): SystemStats {
  return {
    total_cameras: 4,
    total_events: 150,
    total_detections: 450,
    high_risk_events: 12,
    unreviewed_events: 25,
    disk_usage_gb: 125.5,
    disk_total_gb: 500.0,
    ...overrides,
  };
}

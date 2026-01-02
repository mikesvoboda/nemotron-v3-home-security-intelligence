/**
 * Test data factories for creating mock data in tests.
 *
 * These factories generate consistent test data with sensible defaults
 * that can be easily overridden for specific test cases.
 *
 * @example
 * // Create event with defaults
 * const event = createEvent();
 *
 * @example
 * // Override specific fields
 * const highRiskEvent = createEvent({ risk_score: 95 });
 *
 * @example
 * // Create multiple events
 * const events = createEvents(5);
 */

// ============================================================================
// Detection Types and Factories
// ============================================================================

/**
 * Bounding box coordinates for detected objects.
 */
export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * Detection result from AI model.
 */
export interface Detection {
  label: string;
  confidence: number;
  bbox?: BoundingBox;
}

/**
 * Creates a mock detection with sensible defaults.
 *
 * @param overrides - Partial detection to override defaults
 * @returns Complete detection object
 *
 * @example
 * const detection = createDetection({ label: 'car', confidence: 0.92 });
 */
export function createDetection(overrides: Partial<Detection> = {}): Detection {
  return {
    label: 'person',
    confidence: 0.95,
    bbox: {
      x: 100,
      y: 100,
      width: 200,
      height: 300,
    },
    ...overrides,
  };
}

/**
 * Creates multiple detections with unique labels.
 *
 * @param count - Number of detections to create
 * @returns Array of detection objects
 *
 * @example
 * const detections = createDetections(3);
 * // Returns: [person, car, dog] with varying confidences
 */
export function createDetections(count: number): Detection[] {
  const labels = ['person', 'car', 'dog', 'cat', 'bicycle', 'motorcycle', 'truck', 'bird'];
  return Array.from({ length: count }, (_, i) => ({
    label: labels[i % labels.length],
    confidence: 0.95 - i * 0.1, // Decreasing confidence
    bbox: {
      x: 100 + i * 50,
      y: 100 + i * 30,
      width: 200,
      height: 300,
    },
  }));
}

// ============================================================================
// Event Types and Factories
// ============================================================================

/**
 * Security event data structure.
 * Matches the EventCard component props.
 */
export interface Event {
  id: string;
  timestamp: string;
  camera_name: string;
  risk_score: number;
  risk_label: string;
  summary: string;
  reasoning?: string;
  thumbnail_url?: string;
  detections: Detection[];
  started_at?: string;
  ended_at?: string | null;
}

/**
 * Creates a mock event with sensible defaults.
 *
 * @param overrides - Partial event to override defaults
 * @returns Complete event object
 *
 * @example
 * const event = createEvent();
 * const criticalEvent = createEvent({ risk_score: 95, risk_label: 'Critical' });
 */
export function createEvent(overrides: Partial<Event> = {}): Event {
  const id = overrides.id ?? `event-${crypto.randomUUID().slice(0, 8)}`;
  const timestamp = overrides.timestamp ?? new Date().toISOString();

  return {
    id,
    timestamp,
    camera_name: 'Front Door',
    risk_score: 45,
    risk_label: 'Medium',
    summary: 'Person detected approaching the front entrance',
    reasoning: 'The detected person is approaching the entrance during daytime hours.',
    thumbnail_url: 'https://example.com/thumbnail.jpg',
    detections: [createDetection()],
    ...overrides,
  };
}

/**
 * Creates multiple events with unique IDs and varied data.
 *
 * @param count - Number of events to create
 * @returns Array of event objects with varied risk scores and cameras
 *
 * @example
 * const events = createEvents(10);
 */
export function createEvents(count: number): Event[] {
  const cameras = ['Front Door', 'Back Door', 'Garage', 'Driveway', 'Side Gate'];
  const riskLevels = [
    { score: 15, label: 'Low' },
    { score: 45, label: 'Medium' },
    { score: 72, label: 'High' },
    { score: 92, label: 'Critical' },
  ];

  return Array.from({ length: count }, (_, i) => {
    const risk = riskLevels[i % riskLevels.length];
    return createEvent({
      id: `event-${i + 1}`,
      camera_name: cameras[i % cameras.length],
      risk_score: risk.score,
      risk_label: risk.label,
      timestamp: new Date(Date.now() - i * 60000).toISOString(), // Each event 1 min apart
    });
  });
}

// ============================================================================
// Camera Types and Factories
// ============================================================================

/**
 * Camera configuration and status.
 */
export interface Camera {
  id: string;
  name: string;
  location?: string;
  enabled: boolean;
  status: 'online' | 'offline' | 'error';
  last_seen?: string;
  snapshot_url?: string;
}

/**
 * Creates a mock camera with sensible defaults.
 *
 * @param overrides - Partial camera to override defaults
 * @returns Complete camera object
 *
 * @example
 * const camera = createCamera({ name: 'Kitchen', status: 'offline' });
 */
export function createCamera(overrides: Partial<Camera> = {}): Camera {
  const id = overrides.id ?? `cam-${crypto.randomUUID().slice(0, 8)}`;

  return {
    id,
    name: 'Front Door Camera',
    location: 'Front Entrance',
    enabled: true,
    status: 'online',
    last_seen: new Date().toISOString(),
    snapshot_url: `https://example.com/cameras/${id}/snapshot.jpg`,
    ...overrides,
  };
}

/**
 * Creates multiple cameras with unique names and locations.
 *
 * @param count - Number of cameras to create
 * @returns Array of camera objects
 */
export function createCameras(count: number): Camera[] {
  const names = [
    'Front Door',
    'Back Door',
    'Garage',
    'Driveway',
    'Side Gate',
    'Living Room',
    'Backyard',
    'Kitchen',
  ];

  return Array.from({ length: count }, (_, i) =>
    createCamera({
      id: `cam-${i + 1}`,
      name: names[i % names.length],
      location: `Location ${i + 1}`,
    })
  );
}

// ============================================================================
// Service Status Types and Factories
// ============================================================================

export type ServiceName = 'redis' | 'rtdetr' | 'nemotron';
export type ServiceStatusType = 'healthy' | 'unhealthy' | 'restarting' | 'restart_failed' | 'failed';

/**
 * Service health status.
 */
export interface ServiceStatus {
  service: ServiceName;
  status: ServiceStatusType;
  message?: string;
  timestamp: string;
}

/**
 * Creates a mock service status.
 *
 * @param service - The service name
 * @param status - The service status
 * @param message - Optional status message
 * @returns Service status object
 *
 * @example
 * const rtdetrStatus = createServiceStatus('rtdetr', 'healthy');
 * const failedStatus = createServiceStatus('nemotron', 'failed', 'Connection timeout');
 */
export function createServiceStatus(
  service: ServiceName,
  status: ServiceStatusType = 'healthy',
  message?: string
): ServiceStatus {
  return {
    service,
    status,
    message,
    timestamp: new Date().toISOString(),
  };
}

/**
 * Creates a complete set of service statuses (all services).
 *
 * @param overrides - Map of service names to their statuses
 * @returns Record of all service statuses
 *
 * @example
 * const services = createAllServiceStatuses({ nemotron: 'unhealthy' });
 */
export function createAllServiceStatuses(
  overrides: Partial<Record<ServiceName, ServiceStatusType>> = {}
): Record<ServiceName, ServiceStatus | null> {
  return {
    redis: createServiceStatus('redis', overrides.redis ?? 'healthy'),
    rtdetr: createServiceStatus('rtdetr', overrides.rtdetr ?? 'healthy'),
    nemotron: createServiceStatus('nemotron', overrides.nemotron ?? 'healthy'),
  };
}

// ============================================================================
// GPU Stats Types and Factories
// ============================================================================

/**
 * GPU statistics data.
 */
export interface GpuStats {
  gpu_name: string;
  gpu_utilization: number;
  memory_used_mb: number;
  memory_total_mb: number;
  memory_utilization: number;
  temperature_c: number;
  power_draw_w: number;
  power_limit_w: number;
}

/**
 * Creates mock GPU stats with sensible defaults.
 *
 * @param overrides - Partial GPU stats to override defaults
 * @returns Complete GPU stats object
 *
 * @example
 * const gpuStats = createGpuStats({ gpu_utilization: 95 });
 */
export function createGpuStats(overrides: Partial<GpuStats> = {}): GpuStats {
  return {
    gpu_name: 'NVIDIA RTX A5500',
    gpu_utilization: 45,
    memory_used_mb: 8192,
    memory_total_mb: 24576,
    memory_utilization: 33,
    temperature_c: 55,
    power_draw_w: 120,
    power_limit_w: 230,
    ...overrides,
  };
}

// ============================================================================
// System Health Types and Factories
// ============================================================================

export type HealthStatus = 'healthy' | 'degraded' | 'unhealthy';

/**
 * System health response.
 */
export interface SystemHealth {
  status: HealthStatus;
  timestamp: string;
  database: {
    status: string;
    connected: boolean;
  };
  redis: {
    status: string;
    connected: boolean;
  };
  ai_services: {
    rtdetr: string;
    nemotron: string;
  };
}

/**
 * Creates a mock system health response.
 *
 * @param overrides - Partial health data to override defaults
 * @returns Complete system health object
 *
 * @example
 * const healthy = createSystemHealth();
 * const degraded = createSystemHealth({
 *   status: 'degraded',
 *   ai_services: { rtdetr: 'healthy', nemotron: 'unhealthy' }
 * });
 */
export function createSystemHealth(overrides: Partial<SystemHealth> = {}): SystemHealth {
  return {
    status: 'healthy',
    timestamp: new Date().toISOString(),
    database: {
      status: 'healthy',
      connected: true,
    },
    redis: {
      status: 'healthy',
      connected: true,
    },
    ai_services: {
      rtdetr: 'healthy',
      nemotron: 'healthy',
    },
    ...overrides,
  };
}

// ============================================================================
// Timestamps and Dates
// ============================================================================

/**
 * Creates an ISO timestamp relative to now.
 *
 * @param minutesAgo - Minutes in the past (positive) or future (negative)
 * @returns ISO 8601 timestamp string
 *
 * @example
 * const fiveMinutesAgo = createTimestamp(5);
 * const inTenMinutes = createTimestamp(-10);
 */
export function createTimestamp(minutesAgo: number = 0): string {
  const date = new Date(Date.now() - minutesAgo * 60 * 1000);
  return date.toISOString();
}

/**
 * Creates a fixed timestamp for consistent testing.
 * Use this when tests need deterministic timestamps.
 *
 * @param dateString - ISO date string or Date-parseable string
 * @returns ISO 8601 timestamp string
 *
 * @example
 * const fixed = createFixedTimestamp('2024-01-15T10:00:00Z');
 */
export function createFixedTimestamp(dateString: string): string {
  return new Date(dateString).toISOString();
}

// ============================================================================
// WebSocket Message Factories
// ============================================================================

/**
 * Creates a mock WebSocket event message (new event notification).
 *
 * @param event - Event data to include in the message
 * @returns WebSocket message object
 */
export function createWsEventMessage(event: Partial<Event> = {}) {
  return {
    type: 'new_event',
    data: createEvent(event),
    timestamp: new Date().toISOString(),
  };
}

/**
 * Creates a mock WebSocket service status message.
 *
 * @param service - Service name
 * @param status - Service status
 * @param message - Optional message
 * @returns WebSocket message object
 */
export function createWsServiceStatusMessage(
  service: ServiceName,
  status: ServiceStatusType,
  message?: string
) {
  return {
    type: 'service_status',
    data: {
      service,
      status,
      message,
    },
    timestamp: new Date().toISOString(),
  };
}

/**
 * Creates a mock WebSocket GPU stats message.
 *
 * @param stats - GPU stats to include
 * @returns WebSocket message object
 */
export function createWsGpuStatsMessage(stats: Partial<GpuStats> = {}) {
  return {
    type: 'gpu_stats',
    data: createGpuStats(stats),
    timestamp: new Date().toISOString(),
  };
}

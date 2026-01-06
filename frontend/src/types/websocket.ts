/**
 * WebSocket Discriminated Union Types
 *
 * This module defines discriminated union types for all WebSocket messages
 * exchanged between the frontend and backend. Using a `type` field as the
 * discriminator enables exhaustive type checking and compile-time safety.
 *
 * @example
 * ```typescript
 * import {
 *   WebSocketMessage,
 *   isEventMessage,
 *   isSystemStatusMessage,
 *   assertNever
 * } from '@/types/websocket';
 *
 * function handleMessage(msg: WebSocketMessage): void {
 *   switch (msg.type) {
 *     case 'ping':
 *       // Handle heartbeat
 *       break;
 *     case 'event':
 *       // msg.data is typed as SecurityEventData
 *       console.log(msg.data.risk_score);
 *       break;
 *     // ... other cases
 *     default:
 *       assertNever(msg); // Compile-time exhaustiveness check
 *   }
 * }
 * ```
 *
 * @see backend/api/schemas/websocket.py - Backend WebSocket message schemas
 * @see frontend/src/hooks/useWebSocket.ts - WebSocket hook implementation
 */

// ============================================================================
// Service Status Types
// ============================================================================

/**
 * Service names monitored by the health system.
 */
export type ServiceName = 'redis' | 'rtdetr' | 'nemotron';

/**
 * Possible service status values.
 */
export type ServiceStatusType =
  | 'healthy'
  | 'unhealthy'
  | 'restarting'
  | 'restart_failed'
  | 'failed';

// ============================================================================
// Security Event Types
// ============================================================================

/**
 * Risk level classification for security events.
 */
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

/**
 * Security event data from the detection pipeline.
 * Matches the backend EventBroadcaster message format.
 */
export interface SecurityEventData {
  /** Unique identifier (string UUID or numeric ID) */
  id?: string | number;
  /** Numeric event ID from database */
  event_id?: number;
  /** Batch ID for grouped detections */
  batch_id?: string;
  /** Camera identifier */
  camera_id: string;
  /** Camera display name */
  camera_name?: string;
  /** Risk score (0-100) */
  risk_score: number;
  /** Risk level classification */
  risk_level: RiskLevel;
  /** AI-generated event summary */
  summary: string;
  /** Event timestamp */
  timestamp?: string;
  /** Event start time */
  started_at?: string;
}

// ============================================================================
// System Status Types
// ============================================================================

/**
 * Overall system health status.
 */
export type HealthStatus = 'healthy' | 'degraded' | 'unhealthy';

/**
 * GPU metrics data.
 */
export interface GpuStatusData {
  /** GPU utilization percentage (0-100) */
  utilization: number | null;
  /** GPU memory used in MB */
  memory_used: number | null;
  /** Total GPU memory in MB */
  memory_total: number | null;
  /** GPU temperature in Celsius */
  temperature: number | null;
  /** Inference frames per second */
  inference_fps: number | null;
}

/**
 * Camera status summary.
 */
export interface CameraStatusData {
  /** Number of active cameras */
  active: number;
  /** Total number of configured cameras */
  total: number;
}

/**
 * Processing queue status.
 */
export interface QueueStatusData {
  /** Number of items pending processing */
  pending: number;
  /** Number of items currently processing */
  processing: number;
}

/**
 * System status data from the SystemBroadcaster.
 */
export interface SystemStatusData {
  /** GPU metrics */
  gpu: GpuStatusData;
  /** Camera status */
  cameras: CameraStatusData;
  /** Processing queue status */
  queue: QueueStatusData;
  /** Overall health status */
  health: HealthStatus;
}

// ============================================================================
// Service Status Data Types
// ============================================================================

/**
 * Individual service status data.
 */
export interface ServiceStatusData {
  /** Service name */
  service: ServiceName;
  /** Service status */
  status: ServiceStatusType;
  /** Optional status message */
  message?: string;
}

// ============================================================================
// Performance Update Types
// ============================================================================

/**
 * GPU metrics for performance dashboard.
 */
export interface PerformanceGpuData {
  /** GPU model name */
  name: string;
  /** GPU utilization percentage */
  utilization: number;
  /** VRAM used in GB */
  vram_used_gb: number;
  /** Total VRAM in GB */
  vram_total_gb: number;
  /** Temperature in Celsius */
  temperature: number;
  /** Power consumption in watts */
  power_watts: number;
}

/**
 * AI model metrics.
 */
export interface AiModelMetricsData {
  /** Model status */
  status: string;
  /** VRAM usage in GB */
  vram_gb: number;
  /** Model name */
  model: string;
  /** CUDA device */
  device: string;
}

/**
 * Nemotron LLM metrics.
 */
export interface NemotronMetricsData {
  /** Model status */
  status: string;
  /** Active inference slots */
  slots_active: number;
  /** Total inference slots */
  slots_total: number;
  /** Context window size */
  context_size: number;
}

/**
 * Performance alert.
 */
export interface PerformanceAlertData {
  /** Alert severity */
  severity: 'warning' | 'critical';
  /** Metric name */
  metric: string;
  /** Current value */
  value: number;
  /** Threshold that was breached */
  threshold: number;
  /** Alert message */
  message: string;
}

/**
 * Inference latency metrics.
 */
export interface InferenceMetricsData {
  rtdetr_latency_ms: Record<string, number>;
  nemotron_latency_ms: Record<string, number>;
  pipeline_latency_ms: Record<string, number>;
  throughput: Record<string, number>;
  queues: Record<string, number>;
}

/**
 * Database metrics.
 */
export interface DatabaseMetricsData {
  status: string;
  connections_active: number;
  connections_max: number;
  cache_hit_ratio: number;
  transactions_per_min: number;
}

/**
 * Redis metrics.
 */
export interface RedisMetricsData {
  status: string;
  connected_clients: number;
  memory_mb: number;
  hit_ratio: number;
  blocked_clients: number;
}

/**
 * Host system metrics.
 */
export interface HostMetricsData {
  cpu_percent: number;
  ram_used_gb: number;
  ram_total_gb: number;
  disk_used_gb: number;
  disk_total_gb: number;
}

/**
 * Container health status.
 */
export interface ContainerMetricsData {
  name: string;
  status: string;
  health: string;
}

/**
 * Complete performance update data.
 */
export interface PerformanceUpdateData {
  /** Timestamp of the update */
  timestamp: string;
  /** GPU metrics (null if unavailable) */
  gpu: PerformanceGpuData | null;
  /** AI model metrics by model name */
  ai_models: Record<string, AiModelMetricsData | NemotronMetricsData>;
  /** Nemotron-specific metrics */
  nemotron: NemotronMetricsData | null;
  /** Inference latency metrics */
  inference: InferenceMetricsData | null;
  /** Database metrics by name */
  databases: Record<string, DatabaseMetricsData | RedisMetricsData>;
  /** Host system metrics */
  host: HostMetricsData | null;
  /** Container health statuses */
  containers: ContainerMetricsData[];
  /** Active performance alerts */
  alerts: PerformanceAlertData[];
}

// ============================================================================
// WebSocket Message Types (Discriminated Union)
// ============================================================================

/**
 * Heartbeat ping message from server.
 */
export interface PingMessage {
  type: 'ping';
}

/**
 * Heartbeat pong response to server.
 */
export interface PongMessage {
  type: 'pong';
}

/**
 * Security event notification message.
 */
export interface EventMessage {
  type: 'event';
  data: SecurityEventData;
}

/**
 * System status broadcast message.
 */
export interface SystemStatusMessage {
  type: 'system_status';
  data: SystemStatusData;
  timestamp: string;
}

/**
 * Individual service status change message.
 */
export interface ServiceStatusMessage {
  type: 'service_status';
  data: ServiceStatusData;
  timestamp: string;
}

/**
 * Performance metrics update message.
 */
export interface PerformanceUpdateMessage {
  type: 'performance_update';
  data: PerformanceUpdateData;
}

/**
 * Union type of all WebSocket messages.
 * The `type` field acts as the discriminator for type narrowing.
 */
export type WebSocketMessage =
  | PingMessage
  | PongMessage
  | EventMessage
  | SystemStatusMessage
  | ServiceStatusMessage
  | PerformanceUpdateMessage;

/**
 * All possible message type discriminator values.
 */
export type WebSocketMessageType = WebSocketMessage['type'];

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Valid service names for validation.
 */
const VALID_SERVICE_NAMES: readonly ServiceName[] = ['redis', 'rtdetr', 'nemotron'];

/**
 * Valid service status values for validation.
 */
const VALID_SERVICE_STATUSES: readonly ServiceStatusType[] = [
  'healthy',
  'unhealthy',
  'restarting',
  'restart_failed',
  'failed',
];

/**
 * Check if a value is a valid ServiceName.
 */
function isServiceName(value: unknown): value is ServiceName {
  return typeof value === 'string' && VALID_SERVICE_NAMES.includes(value as ServiceName);
}

/**
 * Check if a value is a valid ServiceStatusType.
 */
function isServiceStatusType(value: unknown): value is ServiceStatusType {
  return typeof value === 'string' && VALID_SERVICE_STATUSES.includes(value as ServiceStatusType);
}

/**
 * Type guard for PingMessage.
 *
 * @param data - Unknown data to check
 * @returns True if data is a valid PingMessage
 *
 * @example
 * ```typescript
 * if (isPingMessage(data)) {
 *   // data is typed as PingMessage
 *   console.log('Received heartbeat');
 * }
 * ```
 */
export function isPingMessage(data: unknown): data is PingMessage {
  if (!data || typeof data !== 'object') {
    return false;
  }
  const msg = data as Record<string, unknown>;
  return msg.type === 'ping';
}

/**
 * Type guard for PongMessage.
 *
 * @param data - Unknown data to check
 * @returns True if data is a valid PongMessage
 */
export function isPongMessage(data: unknown): data is PongMessage {
  if (!data || typeof data !== 'object') {
    return false;
  }
  const msg = data as Record<string, unknown>;
  return msg.type === 'pong';
}

/**
 * Check if data contains valid SecurityEventData.
 */
function isSecurityEventData(data: unknown): data is SecurityEventData {
  if (!data || typeof data !== 'object') {
    return false;
  }
  const obj = data as Record<string, unknown>;

  // Must have either id or event_id
  const hasId = 'id' in obj || 'event_id' in obj;

  return (
    hasId &&
    'camera_id' in obj &&
    'risk_score' in obj &&
    'risk_level' in obj &&
    'summary' in obj
  );
}

/**
 * Type guard for EventMessage.
 *
 * @param data - Unknown data to check
 * @returns True if data is a valid EventMessage
 *
 * @example
 * ```typescript
 * if (isEventMessage(data)) {
 *   // data is typed as EventMessage
 *   const riskScore = data.data.risk_score;
 *   const cameraId = data.data.camera_id;
 * }
 * ```
 */
export function isEventMessage(data: unknown): data is EventMessage {
  if (!data || typeof data !== 'object') {
    return false;
  }
  const msg = data as Record<string, unknown>;

  return msg.type === 'event' && isSecurityEventData(msg.data);
}

/**
 * Type guard for SystemStatusMessage.
 *
 * @param data - Unknown data to check
 * @returns True if data is a valid SystemStatusMessage
 */
export function isSystemStatusMessage(data: unknown): data is SystemStatusMessage {
  if (!data || typeof data !== 'object') {
    return false;
  }
  const msg = data as Record<string, unknown>;

  if (msg.type !== 'system_status' || typeof msg.timestamp !== 'string') {
    return false;
  }

  // Validate data structure
  if (!msg.data || typeof msg.data !== 'object') {
    return false;
  }

  const systemData = msg.data as Record<string, unknown>;

  return (
    'gpu' in systemData &&
    'cameras' in systemData &&
    'queue' in systemData &&
    'health' in systemData
  );
}

/**
 * Type guard for ServiceStatusMessage.
 *
 * @param data - Unknown data to check
 * @returns True if data is a valid ServiceStatusMessage
 */
export function isServiceStatusMessage(data: unknown): data is ServiceStatusMessage {
  if (!data || typeof data !== 'object') {
    return false;
  }
  const msg = data as Record<string, unknown>;

  if (msg.type !== 'service_status' || typeof msg.timestamp !== 'string') {
    return false;
  }

  // Validate data structure
  if (!msg.data || typeof msg.data !== 'object') {
    return false;
  }

  const serviceData = msg.data as Record<string, unknown>;

  // Validate service name and status
  if (!isServiceName(serviceData.service) || !isServiceStatusType(serviceData.status)) {
    return false;
  }

  // Message is optional but must be string if present
  if (serviceData.message !== undefined && typeof serviceData.message !== 'string') {
    return false;
  }

  return true;
}

/**
 * Check if data contains valid PerformanceUpdateData.
 */
function isPerformanceUpdateData(data: unknown): data is PerformanceUpdateData {
  if (!data || typeof data !== 'object') {
    return false;
  }
  const obj = data as Record<string, unknown>;

  // Timestamp is required
  return typeof obj.timestamp === 'string';
}

/**
 * Type guard for PerformanceUpdateMessage.
 *
 * @param data - Unknown data to check
 * @returns True if data is a valid PerformanceUpdateMessage
 */
export function isPerformanceUpdateMessage(data: unknown): data is PerformanceUpdateMessage {
  if (!data || typeof data !== 'object') {
    return false;
  }
  const msg = data as Record<string, unknown>;

  return msg.type === 'performance_update' && isPerformanceUpdateData(msg.data);
}

/**
 * Type guard for any valid WebSocketMessage.
 *
 * @param data - Unknown data to check
 * @returns True if data is a valid WebSocketMessage of any type
 *
 * @example
 * ```typescript
 * if (isWebSocketMessage(data)) {
 *   // data is typed as WebSocketMessage
 *   switch (data.type) {
 *     case 'ping': // ...
 *     case 'event': // ...
 *   }
 * }
 * ```
 */
export function isWebSocketMessage(data: unknown): data is WebSocketMessage {
  return (
    isPingMessage(data) ||
    isPongMessage(data) ||
    isEventMessage(data) ||
    isSystemStatusMessage(data) ||
    isServiceStatusMessage(data) ||
    isPerformanceUpdateMessage(data)
  );
}

// ============================================================================
// Exhaustiveness Helper
// ============================================================================

/**
 * Helper for exhaustive switch/if-else checks.
 * When used in the default case of a switch statement, TypeScript will
 * error if any case is not handled.
 *
 * @param value - Should be `never` if all cases are handled
 * @throws Error if called at runtime (indicates unhandled case)
 *
 * @example
 * ```typescript
 * function handleMessage(msg: WebSocketMessage): void {
 *   switch (msg.type) {
 *     case 'ping':
 *       return;
 *     case 'pong':
 *       return;
 *     // ... other cases
 *     default:
 *       // If you add a new message type but forget to handle it,
 *       // TypeScript will error here because msg is not `never`
 *       assertNever(msg);
 *   }
 * }
 * ```
 */
export function assertNever(value: never): never {
  throw new Error(`Unexpected value: ${JSON.stringify(value)}`);
}

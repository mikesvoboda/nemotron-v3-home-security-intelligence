/**
 * Type-safe Constants with Const Assertions
 *
 * This module provides runtime-immutable constant objects with derived union types
 * for risk levels, connection states, service statuses, and health statuses.
 *
 * Using `as const` assertions enables:
 * - Literal type inference (not just `string`)
 * - Derived union types from object values
 * - Compile-time exhaustiveness checking
 *
 * @example
 * ```typescript
 * import {
 *   RISK_LEVELS,
 *   RiskLevel,
 *   isRiskLevel,
 * } from '@/types/constants';
 *
 * // Type-safe usage
 * const level: RiskLevel = RISK_LEVELS.HIGH; // 'high'
 *
 * // Runtime validation
 * function processRisk(value: unknown): RiskLevel | null {
 *   return isRiskLevel(value) ? value : null;
 * }
 * ```
 *
 * @see frontend/src/types/websocket.ts - WebSocket message types that use these constants
 */

// ============================================================================
// Risk Levels
// ============================================================================

/**
 * Risk level constants for security events.
 * Immutable at runtime via Object.freeze().
 *
 * @example
 * ```typescript
 * import { RISK_LEVELS } from '@/types/constants';
 *
 * if (event.risk_level === RISK_LEVELS.CRITICAL) {
 *   sendAlert(event);
 * }
 * ```
 */
export const RISK_LEVELS = Object.freeze({
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high',
  CRITICAL: 'critical',
} as const);

/**
 * Union type of all valid risk level values.
 * Derived from RISK_LEVELS object values.
 *
 * @example
 * ```typescript
 * // Type is: 'low' | 'medium' | 'high' | 'critical'
 * const level: RiskLevel = 'high';
 * ```
 */
export type RiskLevel = (typeof RISK_LEVELS)[keyof typeof RISK_LEVELS];

/**
 * Array of all valid risk level values for iteration and validation.
 */
export const RISK_LEVEL_VALUES = Object.freeze(
  Object.values(RISK_LEVELS)
) as readonly RiskLevel[];

/**
 * Type guard to check if a value is a valid RiskLevel.
 *
 * @param value - Unknown value to check
 * @returns True if value is a valid RiskLevel
 *
 * @example
 * ```typescript
 * const userInput: unknown = 'high';
 * if (isRiskLevel(userInput)) {
 *   // userInput is now typed as RiskLevel
 *   processRiskLevel(userInput);
 * }
 * ```
 */
export function isRiskLevel(value: unknown): value is RiskLevel {
  return (
    typeof value === 'string' &&
    RISK_LEVEL_VALUES.includes(value as RiskLevel)
  );
}

// ============================================================================
// Connection States
// ============================================================================

/**
 * WebSocket connection state constants.
 * Immutable at runtime via Object.freeze().
 *
 * @example
 * ```typescript
 * import { CONNECTION_STATES } from '@/types/constants';
 *
 * const [connectionState, setConnectionState] = useState<ConnectionState>(
 *   CONNECTION_STATES.DISCONNECTED
 * );
 * ```
 */
export const CONNECTION_STATES = Object.freeze({
  CONNECTED: 'connected',
  DISCONNECTED: 'disconnected',
  RECONNECTING: 'reconnecting',
  FAILED: 'failed',
} as const);

/**
 * Union type of all valid connection state values.
 * Derived from CONNECTION_STATES object values.
 *
 * @example
 * ```typescript
 * // Type is: 'connected' | 'disconnected' | 'reconnecting' | 'failed'
 * const state: ConnectionState = 'connected';
 * ```
 */
export type ConnectionState =
  (typeof CONNECTION_STATES)[keyof typeof CONNECTION_STATES];

/**
 * Array of all valid connection state values for iteration and validation.
 */
export const CONNECTION_STATE_VALUES = Object.freeze(
  Object.values(CONNECTION_STATES)
) as readonly ConnectionState[];

/**
 * Type guard to check if a value is a valid ConnectionState.
 *
 * @param value - Unknown value to check
 * @returns True if value is a valid ConnectionState
 *
 * @example
 * ```typescript
 * function handleStateChange(state: unknown) {
 *   if (isConnectionState(state)) {
 *     updateConnectionUI(state);
 *   }
 * }
 * ```
 */
export function isConnectionState(value: unknown): value is ConnectionState {
  return (
    typeof value === 'string' &&
    CONNECTION_STATE_VALUES.includes(value as ConnectionState)
  );
}

// ============================================================================
// Service Statuses
// ============================================================================

/**
 * Service status constants for AI services (rtdetr, nemotron, redis).
 * Immutable at runtime via Object.freeze().
 *
 * @example
 * ```typescript
 * import { SERVICE_STATUSES } from '@/types/constants';
 *
 * if (service.status === SERVICE_STATUSES.UNHEALTHY) {
 *   triggerRestart(service.name);
 * }
 * ```
 */
export const SERVICE_STATUSES = Object.freeze({
  HEALTHY: 'healthy',
  UNHEALTHY: 'unhealthy',
  RESTARTING: 'restarting',
  RESTART_FAILED: 'restart_failed',
  FAILED: 'failed',
} as const);

/**
 * Union type of all valid service status values.
 * Derived from SERVICE_STATUSES object values.
 *
 * @example
 * ```typescript
 * // Type is: 'healthy' | 'unhealthy' | 'restarting' | 'restart_failed' | 'failed'
 * const status: ServiceStatus = 'healthy';
 * ```
 */
export type ServiceStatus =
  (typeof SERVICE_STATUSES)[keyof typeof SERVICE_STATUSES];

/**
 * Array of all valid service status values for iteration and validation.
 */
export const SERVICE_STATUS_VALUES = Object.freeze(
  Object.values(SERVICE_STATUSES)
) as readonly ServiceStatus[];

/**
 * Type guard to check if a value is a valid ServiceStatus.
 *
 * @param value - Unknown value to check
 * @returns True if value is a valid ServiceStatus
 *
 * @example
 * ```typescript
 * function updateServiceCard(status: unknown) {
 *   if (isServiceStatus(status)) {
 *     setCardColor(getStatusColor(status));
 *   }
 * }
 * ```
 */
export function isServiceStatus(value: unknown): value is ServiceStatus {
  return (
    typeof value === 'string' &&
    SERVICE_STATUS_VALUES.includes(value as ServiceStatus)
  );
}

// ============================================================================
// Health Statuses
// ============================================================================

/**
 * Overall system health status constants.
 * Immutable at runtime via Object.freeze().
 *
 * @example
 * ```typescript
 * import { HEALTH_STATUSES } from '@/types/constants';
 *
 * const healthColor = {
 *   [HEALTH_STATUSES.HEALTHY]: 'green',
 *   [HEALTH_STATUSES.DEGRADED]: 'yellow',
 *   [HEALTH_STATUSES.UNHEALTHY]: 'red',
 * };
 * ```
 */
export const HEALTH_STATUSES = Object.freeze({
  HEALTHY: 'healthy',
  DEGRADED: 'degraded',
  UNHEALTHY: 'unhealthy',
} as const);

/**
 * Union type of all valid health status values.
 * Derived from HEALTH_STATUSES object values.
 *
 * @example
 * ```typescript
 * // Type is: 'healthy' | 'degraded' | 'unhealthy'
 * const health: HealthStatus = 'healthy';
 * ```
 */
export type HealthStatus =
  (typeof HEALTH_STATUSES)[keyof typeof HEALTH_STATUSES];

/**
 * Array of all valid health status values for iteration and validation.
 */
export const HEALTH_STATUS_VALUES = Object.freeze(
  Object.values(HEALTH_STATUSES)
) as readonly HealthStatus[];

/**
 * Type guard to check if a value is a valid HealthStatus.
 *
 * @param value - Unknown value to check
 * @returns True if value is a valid HealthStatus
 *
 * @example
 * ```typescript
 * function getHealthIcon(health: unknown): string {
 *   if (isHealthStatus(health)) {
 *     return HEALTH_ICONS[health];
 *   }
 *   return HEALTH_ICONS.unknown;
 * }
 * ```
 */
export function isHealthStatus(value: unknown): value is HealthStatus {
  return (
    typeof value === 'string' &&
    HEALTH_STATUS_VALUES.includes(value as HealthStatus)
  );
}

// ============================================================================
// Utility Types
// ============================================================================

/**
 * Helper type to extract const object keys as a union type.
 *
 * @example
 * ```typescript
 * type RiskLevelKey = ConstKeys<typeof RISK_LEVELS>;
 * // Result: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
 * ```
 */
export type ConstKeys<T extends Record<string, unknown>> = keyof T;

/**
 * Helper type to extract const object values as a union type.
 *
 * @example
 * ```typescript
 * type RiskLevelValue = ConstValues<typeof RISK_LEVELS>;
 * // Result: 'low' | 'medium' | 'high' | 'critical'
 * ```
 */
export type ConstValues<T extends Record<string, unknown>> = T[keyof T];

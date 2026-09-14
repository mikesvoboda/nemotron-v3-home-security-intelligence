/**
 * Mock for useSystemStatus hook.
 *
 * Provides configurable factory functions for testing components that depend
 * on system status monitoring. Follows the same patterns as backend/tests/mock_utils.py.
 *
 * @example
 * ```typescript
 * import { vi } from 'vitest';
 * import { createMockSystemStatus, mockUseSystemStatus } from '../__mocks__';
 *
 * vi.mock('../hooks/useSystemStatus', () => ({
 *   useSystemStatus: mockUseSystemStatus,
 * }));
 *
 * // In test
 * mockUseSystemStatus.mockReturnValue(
 *   createMockSystemStatusReturn({
 *     status: createMockSystemStatus({ health: 'healthy' }),
 *     isConnected: true,
 *   })
 * );
 * ```
 */

import { vi } from 'vitest';

import type { HealthStatus } from '../../types/websocket';
import type { UseSystemStatusReturn, SystemStatus } from '../useSystemStatus';

// =============================================================================
// Types
// =============================================================================

/**
 * Configuration options for creating a mock system status.
 * All properties are optional and will fall back to sensible defaults.
 */
export interface MockSystemStatusOptions {
  /** Overall system health. Default: 'healthy' */
  health?: HealthStatus;
  /** GPU utilization percentage (0-100). Default: 45 */
  gpu_utilization?: number | null;
  /** GPU temperature in Celsius. Default: 65 */
  gpu_temperature?: number | null;
  /** GPU memory used in bytes. Default: 8589934592 (8GB) */
  gpu_memory_used?: number | null;
  /** Total GPU memory in bytes. Default: 25769803776 (24GB) */
  gpu_memory_total?: number | null;
  /** Current inference FPS. Default: 30 */
  inference_fps?: number | null;
  /** Number of active cameras. Default: 4 */
  active_cameras?: number;
  /** Last update timestamp. Default: current ISO timestamp */
  last_update?: string;
}

/**
 * Configuration options for creating a mock system status return value.
 * All properties are optional and will fall back to sensible defaults.
 */
export interface MockSystemStatusReturnOptions {
  /** System status data. Default: null */
  status?: SystemStatus | null;
  /** Whether the WebSocket is connected. Default: false */
  isConnected?: boolean;
}

// =============================================================================
// System Status Factory
// =============================================================================

/**
 * Creates a mock system status with configurable properties.
 *
 * @param options - Configuration options for the mock
 * @returns A mock SystemStatus object
 *
 * @example
 * ```typescript
 * // Default healthy status
 * const status = createMockSystemStatus();
 *
 * // Degraded status with high GPU usage
 * const degraded = createMockSystemStatus({
 *   health: 'degraded',
 *   gpu_utilization: 95,
 *   gpu_temperature: 85,
 * });
 *
 * // Status with no GPU data
 * const noGpu = createMockSystemStatus({
 *   gpu_utilization: null,
 *   gpu_temperature: null,
 *   gpu_memory_used: null,
 *   gpu_memory_total: null,
 * });
 * ```
 */
export function createMockSystemStatus(options: MockSystemStatusOptions = {}): SystemStatus {
  return {
    health: options.health ?? 'healthy',
    gpu_utilization: options.gpu_utilization ?? 45,
    gpu_temperature: options.gpu_temperature ?? 65,
    gpu_memory_used: options.gpu_memory_used ?? 8589934592, // 8GB
    gpu_memory_total: options.gpu_memory_total ?? 25769803776, // 24GB
    inference_fps: options.inference_fps ?? 30,
    active_cameras: options.active_cameras ?? 4,
    last_update: options.last_update ?? new Date().toISOString(),
  };
}

/**
 * Creates a mock system status in healthy state.
 * Convenience function for common test scenario.
 *
 * @param options - Additional options to override
 * @returns A mock SystemStatus in healthy state
 */
export function createHealthySystemStatus(
  options: Partial<MockSystemStatusOptions> = {}
): SystemStatus {
  return createMockSystemStatus({
    health: 'healthy',
    gpu_utilization: 45,
    gpu_temperature: 65,
    ...options,
  });
}

/**
 * Creates a mock system status in degraded state.
 * Convenience function for testing warning states.
 *
 * @param options - Additional options to override
 * @returns A mock SystemStatus in degraded state
 */
export function createDegradedSystemStatus(
  options: Partial<MockSystemStatusOptions> = {}
): SystemStatus {
  return createMockSystemStatus({
    health: 'degraded',
    gpu_utilization: 85,
    gpu_temperature: 78,
    ...options,
  });
}

/**
 * Creates a mock system status in unhealthy state.
 * Convenience function for testing error states.
 *
 * @param options - Additional options to override
 * @returns A mock SystemStatus in unhealthy state
 */
export function createUnhealthySystemStatus(
  options: Partial<MockSystemStatusOptions> = {}
): SystemStatus {
  return createMockSystemStatus({
    health: 'unhealthy',
    gpu_utilization: 98,
    gpu_temperature: 92,
    inference_fps: 5,
    ...options,
  });
}

/**
 * Creates a mock system status with GPU overheating.
 * Convenience function for testing thermal alerts.
 *
 * @param options - Additional options to override
 * @returns A mock SystemStatus with high GPU temperature
 */
export function createOverheatingSystemStatus(
  options: Partial<MockSystemStatusOptions> = {}
): SystemStatus {
  return createMockSystemStatus({
    health: 'degraded',
    gpu_temperature: 90,
    gpu_utilization: 95,
    ...options,
  });
}

/**
 * Creates a mock system status with low GPU memory.
 * Convenience function for testing memory pressure alerts.
 *
 * @param options - Additional options to override
 * @returns A mock SystemStatus with low GPU memory
 */
export function createLowMemorySystemStatus(
  options: Partial<MockSystemStatusOptions> = {}
): SystemStatus {
  return createMockSystemStatus({
    health: 'degraded',
    gpu_memory_used: 23622320128, // ~22GB
    gpu_memory_total: 25769803776, // 24GB (87% used)
    ...options,
  });
}

/**
 * Creates a mock system status with null GPU data.
 * Useful for testing when GPU is not available.
 *
 * @param options - Additional options to override
 * @returns A mock SystemStatus with null GPU metrics
 */
export function createNoGpuSystemStatus(
  options: Partial<MockSystemStatusOptions> = {}
): SystemStatus {
  return createMockSystemStatus({
    health: 'degraded',
    gpu_utilization: null,
    gpu_temperature: null,
    gpu_memory_used: null,
    gpu_memory_total: null,
    inference_fps: null,
    ...options,
  });
}

// =============================================================================
// System Status Return Factory
// =============================================================================

/**
 * Creates a mock system status return value with configurable properties.
 *
 * @param options - Configuration options for the mock
 * @returns A mock UseSystemStatusReturn object
 *
 * @example
 * ```typescript
 * // Connected with healthy status
 * const result = createMockSystemStatusReturn({
 *   status: createMockSystemStatus({ health: 'healthy' }),
 *   isConnected: true,
 * });
 *
 * // Disconnected state
 * const disconnected = createMockSystemStatusReturn({
 *   status: null,
 *   isConnected: false,
 * });
 * ```
 */
export function createMockSystemStatusReturn(
  options: MockSystemStatusReturnOptions = {}
): UseSystemStatusReturn {
  const { status = null, isConnected = false } = options;

  return {
    status,
    isConnected,
  };
}

/**
 * Creates a connected system status return with healthy status.
 * Convenience function for common test scenario.
 *
 * @param statusOptions - Options for the system status
 * @returns A mock UseSystemStatusReturn in healthy connected state
 */
export function createConnectedSystemStatus(
  statusOptions: MockSystemStatusOptions = {}
): UseSystemStatusReturn {
  return createMockSystemStatusReturn({
    status: createMockSystemStatus(statusOptions),
    isConnected: true,
  });
}

/**
 * Creates a disconnected system status return.
 * Convenience function for testing disconnection states.
 *
 * @returns A mock UseSystemStatusReturn in disconnected state
 */
export function createDisconnectedSystemStatus(): UseSystemStatusReturn {
  return createMockSystemStatusReturn({
    status: null,
    isConnected: false,
  });
}

// =============================================================================
// Mock Hook Implementation
// =============================================================================

/**
 * Mock implementation of useSystemStatus hook.
 * Use with vi.mock() to replace the actual hook in tests.
 *
 * @example
 * ```typescript
 * import { vi } from 'vitest';
 * import { mockUseSystemStatus, createConnectedSystemStatus } from '../__mocks__';
 *
 * vi.mock('../hooks/useSystemStatus', () => ({
 *   useSystemStatus: mockUseSystemStatus,
 * }));
 *
 * beforeEach(() => {
 *   mockUseSystemStatus.mockClear();
 *   mockUseSystemStatus.mockReturnValue(createDisconnectedSystemStatus());
 * });
 *
 * it('shows healthy status when connected', () => {
 *   mockUseSystemStatus.mockReturnValue(createConnectedSystemStatus());
 *   // ... test component
 * });
 * ```
 */
export const mockUseSystemStatus = vi.fn(
  (): UseSystemStatusReturn => createMockSystemStatusReturn()
);

// =============================================================================
// Test Utilities
// =============================================================================

/**
 * Updates the system status in a mock return value.
 * Returns a new mock with the updated status.
 *
 * @param mockReturn - The current mock system status return
 * @param statusUpdate - Partial status update to apply
 * @returns A new UseSystemStatusReturn with updated status
 *
 * @example
 * ```typescript
 * let result = createConnectedSystemStatus();
 * result = updateSystemStatus(result, { gpu_utilization: 90 });
 * expect(result.status?.gpu_utilization).toBe(90);
 * ```
 */
export function updateSystemStatus(
  mockReturn: UseSystemStatusReturn,
  statusUpdate: Partial<MockSystemStatusOptions>
): UseSystemStatusReturn {
  if (!mockReturn.status) {
    return {
      ...mockReturn,
      status: createMockSystemStatus(statusUpdate),
    };
  }

  return {
    ...mockReturn,
    status: {
      ...mockReturn.status,
      ...statusUpdate,
      last_update: statusUpdate.last_update ?? new Date().toISOString(),
    },
  };
}

// =============================================================================
// Parameterized Test Helpers
// =============================================================================

/**
 * Test cases for health status.
 * Use with describe.each() for parameterized tests.
 *
 * @example
 * ```typescript
 * describe.each(HEALTH_STATUS_TEST_CASES)(
 *   'Health status $health',
 *   ({ health, expectedColor }) => {
 *     it(`displays ${expectedColor} for ${health}`, () => {
 *       const status = createMockSystemStatus({ health });
 *       // ... test implementation
 *     });
 *   }
 * );
 * ```
 */
export const HEALTH_STATUS_TEST_CASES: Array<{
  health: HealthStatus;
  expectedColor: string;
  description: string;
}> = [
  { health: 'healthy', expectedColor: 'green', description: 'All systems operational' },
  { health: 'degraded', expectedColor: 'yellow', description: 'Some services impacted' },
  { health: 'unhealthy', expectedColor: 'red', description: 'Service outage' },
];

/**
 * Test cases for GPU utilization levels.
 * Use with describe.each() for parameterized tests.
 */
export const GPU_UTILIZATION_TEST_CASES: Array<{
  utilization: number;
  level: 'low' | 'medium' | 'high' | 'critical';
}> = [
  { utilization: 20, level: 'low' },
  { utilization: 50, level: 'medium' },
  { utilization: 75, level: 'high' },
  { utilization: 95, level: 'critical' },
];

/**
 * Test cases for GPU temperature levels.
 * Use with describe.each() for parameterized tests.
 */
export const GPU_TEMPERATURE_TEST_CASES: Array<{
  temperature: number;
  level: 'normal' | 'warm' | 'hot' | 'critical';
}> = [
  { temperature: 50, level: 'normal' },
  { temperature: 65, level: 'warm' },
  { temperature: 80, level: 'hot' },
  { temperature: 90, level: 'critical' },
];

// =============================================================================
// Re-exports for convenience
// =============================================================================

export type { UseSystemStatusReturn, SystemStatus, HealthStatus };

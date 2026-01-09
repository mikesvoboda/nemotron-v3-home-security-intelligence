/**
 * Central re-export hub for all frontend mocks.
 *
 * This module provides a single import point for all mock factories and utilities
 * used across the test suite. Import from here instead of individual mock files.
 *
 * @example
 * ```typescript
 * import {
 *   createMockWebSocket,
 *   createMockSecurityEvent,
 *   createMockSystemStatus,
 *   createMockCamera,
 *   createMockApi,
 *   RISK_LEVEL_TEST_CASES,
 * } from '../__mocks__';
 * ```
 */

// =============================================================================
// Hook Mocks - useWebSocket
// =============================================================================

export {
  // Factory functions
  createMockWebSocket,
  createConnectedWebSocket,
  createDisconnectedWebSocket,
  createReconnectingWebSocket,
  createMockWebSocketWithMessage,

  // Mock hook implementation
  mockUseWebSocket,

  // Test utilities
  simulateWebSocketMessage,
  resetWebSocketMock,

  // Types
  type MockWebSocketOptions,
  type MockWebSocketReturn,
  type UseWebSocketReturn,
  type WebSocketOptions,
} from '../hooks/__mocks__/useWebSocket';

// =============================================================================
// Hook Mocks - useEventStream
// =============================================================================

export {
  // Security event factories
  createMockSecurityEvent,
  createLowRiskEvent,
  createMediumRiskEvent,
  createHighRiskEvent,
  createCriticalRiskEvent,
  createMockEventList as createMockSecurityEventList,

  // Event stream factories
  createMockEventStream,
  createConnectedEventStream,
  createDisconnectedEventStream,

  // Mock hook implementation
  mockUseEventStream,

  // Test utilities
  resetEventIdCounter as resetSecurityEventIdCounter,
  addEventToStream,
  resetEventStreamMock,

  // Parameterized test helpers
  RISK_LEVEL_TEST_CASES,

  // Types
  type MockSecurityEventOptions,
  type MockEventStreamOptions,
  type MockEventStreamReturn,
  type UseEventStreamReturn,
  type SecurityEvent,
  type RiskLevel,
} from '../hooks/__mocks__/useEventStream';

// =============================================================================
// Hook Mocks - useSystemStatus
// =============================================================================

export {
  // System status factories
  createMockSystemStatus,
  createHealthySystemStatus,
  createDegradedSystemStatus,
  createUnhealthySystemStatus,
  createOverheatingSystemStatus,
  createLowMemorySystemStatus,
  createNoGpuSystemStatus,

  // System status return factories
  createMockSystemStatusReturn,
  createConnectedSystemStatus,
  createDisconnectedSystemStatus,

  // Mock hook implementation
  mockUseSystemStatus,

  // Test utilities
  updateSystemStatus,

  // Parameterized test helpers
  HEALTH_STATUS_TEST_CASES,
  GPU_UTILIZATION_TEST_CASES,
  GPU_TEMPERATURE_TEST_CASES,

  // Types
  type MockSystemStatusOptions,
  type MockSystemStatusReturnOptions,
  type UseSystemStatusReturn,
  type SystemStatus,
  type HealthStatus,
} from '../hooks/__mocks__/useSystemStatus';

// =============================================================================
// API Mocks
// =============================================================================

export {
  // Camera factories
  createMockCamera,
  createMockCameraList,
  createMockCamerasResponse,
  resetCameraIdCounter,

  // Health factories
  createMockHealthResponse,
  createHealthyResponse,
  createDegradedHealthResponse,
  createUnhealthyHealthResponse,

  // GPU stats factories
  createMockGPUStats,

  // Event factories
  createMockEvent,
  createMockEventList,
  resetEventIdCounter,

  // Detection factories
  createMockDetection,
  createMockDetectionList,
  resetDetectionIdCounter,

  // Zone factories
  createMockZone,
  resetZoneIdCounter,

  // Alert rule factories
  createMockAlertRule,
  resetAlertRuleIdCounter,

  // System config factories
  createMockSystemConfig,

  // System stats factories
  createMockSystemStats,

  // Telemetry factories
  createMockTelemetry,

  // Readiness factories
  createMockReadiness,

  // Full API mock
  createMockApi,

  // Utility functions
  resetAllIdCounters,
  createMockFetch,
  createMockFetchError,
  createMockFetchHttpError,

  // Parameterized test helpers
  OBJECT_TYPE_TEST_CASES,
  HTTP_STATUS_TEST_CASES,

  // Types
  type MockApi,
  type MockCameraOptions,
  type MockHealthOptions,
  type MockGPUStatsOptions,
  type MockEventOptions,
  type MockDetectionOptions,
  type MockZoneOptions,
  type MockAlertRuleOptions,
  type MockSystemConfigOptions,
  type MockSystemStatsOptions,
} from '../services/__mocks__/api';

// =============================================================================
// Convenience Type Re-exports
// =============================================================================

// Re-export MockData type for tests that need flexible typing
export type { MockData } from '../services/__mocks__/api';

// =============================================================================
// Helper Functions
// =============================================================================

// Import functions needed for resetAllMocks helper
import {
  resetEventIdCounter as _resetSecurityEventIdCounter,
} from '../hooks/__mocks__/useEventStream';
import {
  resetAllIdCounters as _resetAllIdCounters,
} from '../services/__mocks__/api';

/**
 * Resets all mocks and ID counters.
 * Call this in beforeEach for consistent test state.
 *
 * @example
 * ```typescript
 * import { resetAllMocks } from '../__mocks__';
 *
 * beforeEach(() => {
 *   resetAllMocks();
 * });
 * ```
 */
export function resetAllMocks(): void {
  // Reset API ID counters
  _resetAllIdCounters();
  // Reset security event ID counter (from event stream mocks)
  _resetSecurityEventIdCounter();
}

/**
 * Clears all Vitest mock functions.
 * Call this after each test to clean up mock state.
 *
 * @param mocks - Array of mock functions to clear
 *
 * @example
 * ```typescript
 * import { vi } from 'vitest';
 * import { clearMocks, mockUseWebSocket, mockUseEventStream } from '../__mocks__';
 *
 * afterEach(() => {
 *   clearMocks([mockUseWebSocket, mockUseEventStream]);
 * });
 * ```
 */
export function clearMocks(mocks: Array<ReturnType<typeof import('vitest').vi.fn>>): void {
  mocks.forEach((mock) => mock.mockClear());
}

/**
 * Restores all Vitest mock functions to their original implementation.
 *
 * @param mocks - Array of mock functions to restore
 */
export function restoreMocks(mocks: Array<ReturnType<typeof import('vitest').vi.fn>>): void {
  mocks.forEach((mock) => mock.mockRestore());
}

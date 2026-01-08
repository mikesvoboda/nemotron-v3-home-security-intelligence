/**
 * Centralized Mock Directory - Re-exports all mocks
 */

// Hook Mocks
export {
  useWebSocket,
  mockSend,
  mockConnect,
  mockDisconnect,
  setMockConnectionState as setWebSocketConnectionState,
  setMockLastMessage,
  triggerMessage,
  triggerOpen,
  triggerClose,
  triggerError,
  triggerHeartbeat,
  resetMocks as resetWebSocketMocks,
  isHeartbeatMessage,
  calculateBackoffDelay,
  type MockWebSocketState,
} from '../hooks/__mocks__/useWebSocket';

export {
  useEventStream,
  mockClearEvents,
  setMockEvents,
  addMockEvent,
  setMockConnectionState as setEventStreamConnectionState,
  getMockEvents,
  resetMocks as resetEventStreamMocks,
  createMockSecurityEvent,
  createMockSecurityEvents,
} from '../hooks/__mocks__/useEventStream';

export type { SecurityEvent } from '../hooks/__mocks__/useEventStream';

export {
  useSystemStatus,
  setMockSystemStatus,
  setMockConnectionState as setSystemStatusConnectionState,
  getMockStatus,
  resetMocks as resetSystemStatusMocks,
  createMockStatusWithHealth,
  createHighLoadStatus,
  createNoGpuStatus,
} from '../hooks/__mocks__/useSystemStatus';

export type { SystemStatus } from '../hooks/__mocks__/useSystemStatus';

// API Service Mocks
export {
  resetMocks as resetApiMocks,
  setMockCameras,
  setMockEvents as setMockApiEvents,
  setMockEventStats,
  setMockGpuStats,
  setMockHealth,
  setMockFetchCamerasError,
  setMockFetchEventsError,
  setMockFetchEventStatsError,
  setMockFetchGpuStatsError,
  setMockFetchHealthError,
  createMockCamera,
  createMockEvent,
  fetchCameras,
  fetchCamera,
  createCamera,
  updateCamera,
  deleteCamera,
  getCameraSnapshotUrl,
  fetchEvents,
  fetchEvent,
  fetchEventStats,
  updateEvent,
  fetchHealth,
  fetchGPUStats,
  fetchGpuHistory,
  fetchStats,
  fetchTelemetry,
  fetchReadiness,
  fetchConfig,
  updateConfig,
  triggerCleanup,
  buildWebSocketOptions,
  buildWebSocketUrl,
  getApiKey,
  clearInFlightRequests,
  ApiError,
} from '../services/__mocks__/api';

// Import reset functions for the resetAllMocks convenience function
import { resetMocks as resetEventStream } from '../hooks/__mocks__/useEventStream';
import { resetMocks as resetSystemStatus } from '../hooks/__mocks__/useSystemStatus';
import { resetMocks as resetWebSocket } from '../hooks/__mocks__/useWebSocket';
import { resetMocks as resetApi } from '../services/__mocks__/api';

/**
 * Reset all mocks to their default state.
 */
export function resetAllMocks(): void {
  resetWebSocket();
  resetEventStream();
  resetSystemStatus();
  resetApi();
}

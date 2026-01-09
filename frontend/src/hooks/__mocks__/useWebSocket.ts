/**
 * Mock for useWebSocket hook.
 *
 * Provides configurable factory functions for testing components that depend
 * on WebSocket connections. Follows the same patterns as backend/tests/mock_utils.py.
 *
 * @example
 * ```typescript
 * import { vi } from 'vitest';
 * import { createMockWebSocket, mockUseWebSocket } from '../__mocks__';
 *
 * vi.mock('../hooks/useWebSocket', () => ({
 *   useWebSocket: mockUseWebSocket,
 * }));
 *
 * // In test
 * mockUseWebSocket.mockReturnValue(createMockWebSocket({ isConnected: true }));
 * ```
 */

import { vi } from 'vitest';

import type { UseWebSocketReturn, WebSocketOptions } from '../useWebSocket';

// =============================================================================
// Types
// =============================================================================

/**
 * Configuration options for creating a mock WebSocket return value.
 * All properties are optional and will fall back to sensible defaults.
 */
export interface MockWebSocketOptions {
  /** Whether the WebSocket is currently connected. Default: false */
  isConnected?: boolean;
  /** The last message received from the WebSocket. Default: null */
  lastMessage?: unknown;
  /** Whether max reconnection attempts have been exhausted. Default: false */
  hasExhaustedRetries?: boolean;
  /** Current reconnection attempt count. Default: 0 */
  reconnectCount?: number;
  /** Timestamp of the last heartbeat received. Default: null */
  lastHeartbeat?: Date | null;
}

/**
 * Mock return type for useWebSocket hook.
 * Extends UseWebSocketReturn with vi.Mock types for function properties.
 */
export interface MockWebSocketReturn extends Omit<UseWebSocketReturn, 'send' | 'connect' | 'disconnect'> {
  /** Mock send function */
  send: ReturnType<typeof vi.fn>;
  /** Mock connect function */
  connect: ReturnType<typeof vi.fn>;
  /** Mock disconnect function */
  disconnect: ReturnType<typeof vi.fn>;
}

// =============================================================================
// Factory Functions
// =============================================================================

/**
 * Creates a mock WebSocket return value with configurable properties.
 *
 * @param options - Configuration options for the mock
 * @returns A mock UseWebSocketReturn object
 *
 * @example
 * ```typescript
 * // Default disconnected state
 * const mockWs = createMockWebSocket();
 *
 * // Connected state
 * const connectedWs = createMockWebSocket({ isConnected: true });
 *
 * // Reconnecting state
 * const reconnectingWs = createMockWebSocket({
 *   isConnected: false,
 *   reconnectCount: 3,
 * });
 *
 * // Exhausted retries
 * const exhaustedWs = createMockWebSocket({
 *   isConnected: false,
 *   hasExhaustedRetries: true,
 *   reconnectCount: 5,
 * });
 * ```
 */
export function createMockWebSocket(options: MockWebSocketOptions = {}): MockWebSocketReturn {
  const {
    isConnected = false,
    lastMessage = null,
    hasExhaustedRetries = false,
    reconnectCount = 0,
    lastHeartbeat = null,
  } = options;

  return {
    isConnected,
    lastMessage,
    send: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
    hasExhaustedRetries,
    reconnectCount,
    lastHeartbeat,
  };
}

/**
 * Creates a mock WebSocket in connected state with recent heartbeat.
 * Convenience function for common test scenario.
 *
 * @returns A mock UseWebSocketReturn object in healthy connected state
 *
 * @example
 * ```typescript
 * const mockWs = createConnectedWebSocket();
 * expect(mockWs.isConnected).toBe(true);
 * expect(mockWs.lastHeartbeat).not.toBeNull();
 * ```
 */
export function createConnectedWebSocket(): MockWebSocketReturn {
  return createMockWebSocket({
    isConnected: true,
    hasExhaustedRetries: false,
    reconnectCount: 0,
    lastHeartbeat: new Date(),
  });
}

/**
 * Creates a mock WebSocket in disconnected state with exhausted retries.
 * Convenience function for testing error states.
 *
 * @param reconnectCount - Number of reconnection attempts made. Default: 5
 * @returns A mock UseWebSocketReturn object in error state
 *
 * @example
 * ```typescript
 * const mockWs = createDisconnectedWebSocket();
 * expect(mockWs.isConnected).toBe(false);
 * expect(mockWs.hasExhaustedRetries).toBe(true);
 * ```
 */
export function createDisconnectedWebSocket(reconnectCount: number = 5): MockWebSocketReturn {
  return createMockWebSocket({
    isConnected: false,
    hasExhaustedRetries: true,
    reconnectCount,
    lastHeartbeat: null,
  });
}

/**
 * Creates a mock WebSocket in reconnecting state.
 * Convenience function for testing reconnection UI.
 *
 * @param reconnectCount - Current reconnection attempt count. Default: 2
 * @returns A mock UseWebSocketReturn object in reconnecting state
 *
 * @example
 * ```typescript
 * const mockWs = createReconnectingWebSocket(3);
 * expect(mockWs.isConnected).toBe(false);
 * expect(mockWs.reconnectCount).toBe(3);
 * expect(mockWs.hasExhaustedRetries).toBe(false);
 * ```
 */
export function createReconnectingWebSocket(reconnectCount: number = 2): MockWebSocketReturn {
  return createMockWebSocket({
    isConnected: false,
    hasExhaustedRetries: false,
    reconnectCount,
    lastHeartbeat: null,
  });
}

/**
 * Creates a mock WebSocket with a specific last message.
 * Useful for testing message handling.
 *
 * @param message - The message to set as lastMessage
 * @param isConnected - Whether the WebSocket is connected. Default: true
 * @returns A mock UseWebSocketReturn object with the specified message
 *
 * @example
 * ```typescript
 * const mockWs = createMockWebSocketWithMessage({
 *   type: 'event',
 *   data: { risk_score: 75 },
 * });
 * expect(mockWs.lastMessage).toEqual({ type: 'event', data: { risk_score: 75 } });
 * ```
 */
export function createMockWebSocketWithMessage(
  message: unknown,
  isConnected: boolean = true
): MockWebSocketReturn {
  return createMockWebSocket({
    isConnected,
    lastMessage: message,
    lastHeartbeat: new Date(),
  });
}

// =============================================================================
// Mock Hook Implementation
// =============================================================================

/**
 * Mock implementation of useWebSocket hook.
 * Use with vi.mock() to replace the actual hook in tests.
 *
 * @example
 * ```typescript
 * import { vi } from 'vitest';
 * import { mockUseWebSocket, createMockWebSocket } from '../__mocks__';
 *
 * vi.mock('../hooks/useWebSocket', () => ({
 *   useWebSocket: mockUseWebSocket,
 * }));
 *
 * beforeEach(() => {
 *   mockUseWebSocket.mockClear();
 *   mockUseWebSocket.mockReturnValue(createMockWebSocket());
 * });
 *
 * it('shows connected indicator when connected', () => {
 *   mockUseWebSocket.mockReturnValue(createMockWebSocket({ isConnected: true }));
 *   // ... test component
 * });
 * ```
 */
export const mockUseWebSocket = vi.fn((_options?: WebSocketOptions): MockWebSocketReturn =>
  createMockWebSocket()
);

// =============================================================================
// Test Utilities
// =============================================================================

/**
 * Simulates receiving a message through the WebSocket mock.
 * Updates the lastMessage and calls the onMessage callback if provided.
 *
 * @param mockReturn - The mock WebSocket return object
 * @param message - The message to simulate receiving
 * @param onMessage - Optional callback to invoke with the message
 *
 * @example
 * ```typescript
 * const mockWs = createConnectedWebSocket();
 * const onMessage = vi.fn();
 *
 * simulateWebSocketMessage(mockWs, { type: 'ping' }, onMessage);
 *
 * expect(onMessage).toHaveBeenCalledWith({ type: 'ping' });
 * ```
 */
export function simulateWebSocketMessage(
  mockReturn: MockWebSocketReturn,
  message: unknown,
  onMessage?: (data: unknown) => void
): void {
  // Update the lastMessage (in real tests, you'd update the mock's return value)
  Object.assign(mockReturn, { lastMessage: message });

  // Call the onMessage callback if provided
  if (onMessage) {
    onMessage(message);
  }
}

/**
 * Resets all mock functions in a MockWebSocketReturn object.
 * Call this in beforeEach to ensure clean state between tests.
 *
 * @param mockReturn - The mock WebSocket return object to reset
 *
 * @example
 * ```typescript
 * const mockWs = createMockWebSocket();
 *
 * beforeEach(() => {
 *   resetWebSocketMock(mockWs);
 * });
 * ```
 */
export function resetWebSocketMock(mockReturn: MockWebSocketReturn): void {
  mockReturn.send.mockClear();
  mockReturn.connect.mockClear();
  mockReturn.disconnect.mockClear();
}

// =============================================================================
// Re-exports for convenience
// =============================================================================

export type { UseWebSocketReturn, WebSocketOptions };

/**
 * Mock for webSocketManager module.
 *
 * Provides a lightweight mock that avoids importing the full webSocketManager
 * and its dependencies (typedEventEmitter, logger) which can cause memory issues.
 */

import { vi, type Mock } from 'vitest';

/**
 * vitest 5 moved `Procedure` (the bound of `vi.fn`'s inferred generic) into
 * a chunk file (vitest/dist/chunks/config.*.d.ts). Any export whose inferred
 * type mentions it is not nameable from a declaration file — TS2883, fatal
 * to stryker's typescript-checker, which compiles with declaration emit
 * (tsconfig.stryker.json keeps `references` to block project-following, and
 * stryker enables build mode whenever that key exists). Annotating these
 * mock declarations with the public `Mock` type fixes it at the root.
 */
interface MockSubscription {
  unsubscribe: () => void;
  on: Mock;
  off: Mock;
  once: Mock;
  send: Mock;
  getState: Mock;
  emitter: { on: Mock; off: Mock; once: Mock; emit: Mock; clear: Mock };
}

// Global storage for captured handlers (accessible from tests)
export const mockState = {
  capturedLifecycleHandlers: {} as {
    onOpen?: () => void;
    onClose?: () => void;
    onError?: () => void;
    onMaxRetriesExhausted?: () => void;
  },
  capturedCameraStatusHandler: undefined as ((event: unknown) => void) | undefined,
  unsubscribeCalled: false,
};

// Reset function for test cleanup
export const resetMockState = () => {
  mockState.capturedLifecycleHandlers = {};
  mockState.capturedCameraStatusHandler = undefined;
  mockState.unsubscribeCalled = false;
};

// Create mock subscription factory
const createMockSubscription = (
  options: {
    onOpen?: () => void;
    onClose?: () => void;
    onError?: () => void;
    onMaxRetriesExhausted?: () => void;
  } = {}
): MockSubscription => {
  mockState.capturedLifecycleHandlers = options;

  return {
    unsubscribe: () => {
      mockState.unsubscribeCalled = true;
    },
    on: vi.fn().mockImplementation((eventType: string, handler: unknown) => {
      if (eventType === 'camera_status') {
        mockState.capturedCameraStatusHandler =
          handler as typeof mockState.capturedCameraStatusHandler;
      }
      return vi.fn();
    }),
    off: vi.fn(),
    once: vi.fn(),
    send: vi.fn(),
    getState: vi.fn().mockReturnValue({
      isConnected: true,
      reconnectCount: 0,
      hasExhaustedRetries: false,
      lastHeartbeat: null,
    }),
    emitter: {
      on: vi.fn(),
      off: vi.fn(),
      once: vi.fn(),
      emit: vi.fn(),
      clear: vi.fn(),
    },
  };
};

// Mock createTypedSubscription function
export const createTypedSubscription: Mock = vi.fn(
  (_url: string, _config: unknown, options: unknown) =>
    createMockSubscription(options as Record<string, () => void>)
);

// Mock generateSubscriberId function
export const generateSubscriberId = () => 'mock-subscriber-id';

// Mock resetSubscriberCounter function
export const resetSubscriberCounter: Mock = vi.fn();

// Mock webSocketManager singleton
export const webSocketManager: {
  subscribe: Mock;
  send: Mock;
  getConnectionState: Mock;
  getSubscriberCount: Mock;
  hasConnection: Mock;
  reconnect: Mock;
  clearAll: Mock;
  reset: Mock;
} = {
  subscribe: vi.fn(),
  send: vi.fn(),
  getConnectionState: vi.fn(),
  getSubscriberCount: vi.fn(),
  hasConnection: vi.fn(),
  reconnect: vi.fn(),
  clearAll: vi.fn(),
  reset: vi.fn(),
};

// Export types that match the real module
export type ConnectionConfig = {
  reconnect: boolean;
  reconnectInterval: number;
  maxReconnectAttempts: number;
  connectionTimeout: number;
  autoRespondToHeartbeat: boolean;
};

export type TypedSubscription = ReturnType<typeof createMockSubscription>;

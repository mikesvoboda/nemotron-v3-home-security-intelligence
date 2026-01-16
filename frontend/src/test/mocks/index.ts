/**
 * Reusable mock factories and helpers.
 *
 * This module provides pre-configured mocks for common testing scenarios,
 * reducing boilerplate and ensuring consistency across tests.
 *
 * ## Usage
 *
 * ### MSW Handler Factories
 *
 * ```typescript
 * import { createMockHandler } from '@/test/mocks';
 * import { server } from '@/mocks/server';
 *
 * // Create a custom handler for a specific test
 * server.use(
 *   createMockHandler('/api/cameras', { status: 500 })
 * );
 * ```
 *
 * ### Pre-configured Scenarios
 *
 * ```typescript
 * import { mockApiError, mockApiSuccess, mockApiLoading } from '@/test/mocks';
 *
 * server.use(mockApiError('/api/cameras'));
 * server.use(mockApiSuccess('/api/cameras', [camera1, camera2]));
 * ```
 *
 * ### WebSocket Mocks
 *
 * ```typescript
 * import { createMockWebSocket } from '@/test/mocks';
 *
 * const mockWs = createMockWebSocket();
 * mockWs.simulateMessage({ type: 'event', data: event });
 * ```
 *
 * @module test/mocks
 */

import { http, HttpResponse, delay } from 'msw';
import { vi } from 'vitest';

// ============================================================================
// Types
// ============================================================================

export interface MockHandlerOptions {
  /**
   * HTTP status code for the response
   * @default 200
   */
  status?: number;

  /**
   * Delay in milliseconds before responding
   */
  delay?: number;

  /**
   * Response data (for success responses)
   */
  data?: unknown;

  /**
   * Error message (for error responses)
   */
  error?: string;
}

// ============================================================================
// MSW Handler Factories
// ============================================================================

/**
 * Create a generic mock handler for any endpoint.
 *
 * @param endpoint - API endpoint path (e.g., '/api/cameras')
 * @param options - Handler options
 * @returns MSW request handler
 *
 * @example
 * ```typescript
 * server.use(
 *   createMockHandler('/api/cameras', { status: 500, error: 'Server error' })
 * );
 * ```
 */
export function createMockHandler(endpoint: string, options: MockHandlerOptions = {}) {
  const { status = 200, delay: delayMs, data, error } = options;

  return http.get(endpoint, async () => {
    if (delayMs) {
      await delay(delayMs);
    }

    if (status >= 400) {
      return HttpResponse.json({ detail: error || 'Request failed' }, { status });
    }

    return HttpResponse.json(data || {}, { status });
  });
}

/**
 * Create a mock handler that returns a successful response.
 *
 * @param endpoint - API endpoint path
 * @param data - Response data
 * @param delayMs - Optional delay in milliseconds
 * @returns MSW request handler
 */
export function mockApiSuccess(endpoint: string, data: unknown, delayMs?: number) {
  return createMockHandler(endpoint, { status: 200, data, delay: delayMs });
}

/**
 * Create a mock handler that returns an error response.
 *
 * @param endpoint - API endpoint path
 * @param error - Error message
 * @param status - HTTP status code (default: 500)
 * @returns MSW request handler
 */
export function mockApiError(endpoint: string, error = 'Server error', status = 500) {
  return createMockHandler(endpoint, { status, error });
}

/**
 * Create a mock handler that simulates a loading state (infinite delay).
 *
 * @param endpoint - API endpoint path
 * @returns MSW request handler
 */
export function mockApiLoading(endpoint: string) {
  return http.get(endpoint, async () => {
    await delay('infinite');
    return HttpResponse.json({});
  });
}

/**
 * Create a mock handler that returns a 404 Not Found response.
 *
 * @param endpoint - API endpoint path
 * @returns MSW request handler
 */
export function mockApiNotFound(endpoint: string) {
  return createMockHandler(endpoint, {
    status: 404,
    error: 'Resource not found',
  });
}

// ============================================================================
// POST/PUT/DELETE Handler Factories
// ============================================================================

/**
 * Create a mock POST handler.
 *
 * @param endpoint - API endpoint path
 * @param responseData - Response data to return
 * @param status - HTTP status code (default: 201)
 * @returns MSW request handler
 */
export function mockApiPost<T>(endpoint: string, responseData: T, status = 201) {
  return http.post(endpoint, () => {
    return HttpResponse.json(responseData as object, { status });
  });
}

/**
 * Create a mock PUT handler.
 *
 * @param endpoint - API endpoint path
 * @param responseData - Response data to return
 * @returns MSW request handler
 */
export function mockApiPut<T>(endpoint: string, responseData: T) {
  return http.put(endpoint, () => {
    return HttpResponse.json(responseData as object, { status: 200 });
  });
}

/**
 * Create a mock DELETE handler.
 *
 * @param endpoint - API endpoint path
 * @returns MSW request handler
 */
export function mockApiDelete(endpoint: string) {
  return http.delete(endpoint, () => {
    return HttpResponse.json({ success: true }, { status: 204 });
  });
}

// ============================================================================
// WebSocket Mock
// ============================================================================

export interface MockWebSocketMessage {
  type: string;
  data?: unknown;
}

/**
 * Create a mock WebSocket for testing.
 *
 * @returns Mock WebSocket with helper methods
 *
 * @example
 * ```typescript
 * const mockWs = createMockWebSocket();
 *
 * // Simulate receiving a message
 * mockWs.simulateMessage({ type: 'event', data: event });
 *
 * // Simulate connection open
 * mockWs.simulateOpen();
 *
 * // Simulate connection close
 * mockWs.simulateClose();
 * ```
 */
export function createMockWebSocket() {
  const listeners: Map<string, Set<(event: Event) => void>> = new Map();

  const mockWs = {
    readyState: 0, // CONNECTING
    url: 'ws://localhost:8000/ws',

    addEventListener(event: string, handler: (event: Event) => void) {
      if (!listeners.has(event)) {
        listeners.set(event, new Set());
      }
      listeners.get(event)!.add(handler);
    },

    removeEventListener(event: string, handler: (event: Event) => void) {
      listeners.get(event)?.delete(handler);
    },

    send: vi.fn(),
    close: vi.fn(),

    // Helper methods for testing
    simulateOpen() {
      mockWs.readyState = 1; // OPEN
      const event = new Event('open');
      listeners.get('open')?.forEach((handler) => handler(event));
    },

    simulateMessage(message: MockWebSocketMessage) {
      const event = new MessageEvent('message', {
        data: JSON.stringify(message),
      });
      listeners.get('message')?.forEach((handler) => handler(event));
    },

    simulateError(error?: Error) {
      const event = new ErrorEvent('error', { error });
      listeners.get('error')?.forEach((handler) => handler(event));
    },

    simulateClose(code = 1000, reason = '') {
      mockWs.readyState = 3; // CLOSED
      const event = new CloseEvent('close', { code, reason });
      listeners.get('close')?.forEach((handler) => handler(event));
    },
  };

  return mockWs;
}

// ============================================================================
// Query Client Mock
// ============================================================================

/**
 * Create a mock QueryClient with spy methods.
 *
 * Useful for verifying that queries/mutations are called correctly.
 *
 * @returns Mock QueryClient with vitest spies
 */
export function createMockQueryClient() {
  return {
    getQueryData: vi.fn(),
    setQueryData: vi.fn(),
    invalidateQueries: vi.fn(),
    refetchQueries: vi.fn(),
    cancelQueries: vi.fn(),
    clear: vi.fn(),
    isFetching: vi.fn(() => 0),
    isMutating: vi.fn(() => 0),
  };
}

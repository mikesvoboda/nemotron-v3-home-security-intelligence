import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterAll, afterEach, beforeAll, vi } from 'vitest';

import { resetCounter } from './factories';
import { server } from '../mocks/server';

/**
 * Re-export common mock utilities for convenient importing in tests.
 *
 * Usage:
 *   import { createRouterMock, FAST_TIMEOUT } from '@/test/setup';
 *
 * @see common-mocks.ts - Detailed documentation for each utility
 */
export {
  createRouterMock,
  createApiMock,
  createWebSocketMock,
  testQueryClientOptions,
  FAST_TIMEOUT,
  STANDARD_TIMEOUT,
} from './common-mocks';

/**
 * Fix HeadlessUI focus issue with jsdom
 * HeadlessUI tries to set HTMLElement.prototype.focus which is getter-only in jsdom.
 * We need to make it configurable before HeadlessUI loads.
 */
// eslint-disable-next-line @typescript-eslint/unbound-method
const originalFocus = HTMLElement.prototype.focus;
Object.defineProperty(HTMLElement.prototype, 'focus', {
  configurable: true,
  enumerable: true,
  writable: true,
  value: originalFocus,
});

/**
 * Mock ResizeObserver for Headless UI Dialog component
 * Headless UI's Dialog component uses ResizeObserver to track viewport changes,
 * but jsdom doesn't provide this API, so we mock it for testing.
 */
beforeAll(() => {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };

  /**
   * Mock IntersectionObserver for Headless UI components
   * Some Headless UI components use IntersectionObserver for visibility detection.
   * jsdom doesn't provide this API, so we mock it for testing.
   */
  (globalThis as any).IntersectionObserver = class IntersectionObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords() {
      return [];
    }
    root = null;
    rootMargin = '';
    thresholds: number[] = [];
  };

  /**
   * Start MSW server for API mocking.
   *
   * MSW (Mock Service Worker) intercepts HTTP requests and returns mock responses
   * defined in src/mocks/handlers.ts. This provides more realistic API mocking
   * than vi.mock() because:
   *
   * 1. Requests go through the actual fetch implementation
   * 2. Request/response handling matches production behavior
   * 3. Handlers can be overridden per-test using server.use()
   * 4. Errors are thrown for unhandled requests (by default)
   *
   * @see src/mocks/handlers.ts - Default API handlers
   * @see src/mocks/server.ts - Server configuration
   */
  server.listen({
    onUnhandledRequest: 'bypass', // Allow unhandled requests to pass through (for gradual migration)
  });
});

/**
 * Comprehensive cleanup after each test to prevent zombie processes.
 * This addresses common causes of hanging tests:
 * - Unclosed mock timers (setTimeout/setInterval)
 * - Leftover mock state
 * - Uncleared global stubs
 * - React component cleanup
 * - MSW handler overrides from individual tests
 */
afterEach(() => {
  // Clean up React Testing Library rendered components
  cleanup();

  // Reset MSW handlers to their initial state (removes test-specific overrides)
  // This ensures each test starts with the default handlers from handlers.ts
  server.resetHandlers();

  // Clear all mock function calls and instances
  vi.clearAllMocks();

  // Clear all pending fake timers (setTimeout, setInterval, etc.)
  vi.clearAllTimers();

  // Reset timers to real timers if fake timers were used
  // This prevents timer state from leaking between tests
  vi.useRealTimers();

  // Unstub all global mocks (fetch, WebSocket, etc.)
  vi.unstubAllGlobals();

  // Reset factory counter to ensure unique IDs across tests
  resetCounter();

  // Force garbage collection if available (requires --expose-gc flag)
  // This helps prevent memory accumulation between tests
  if (typeof (globalThis as any).gc === 'function') {
    (globalThis as any).gc();
  }
});

/**
 * Final cleanup after all tests in a file complete.
 * Ensures any remaining state is properly cleaned up.
 */
afterAll(() => {
  // Stop MSW server - closes all request interception
  server.close();

  // Final reset of all mocks
  vi.resetAllMocks();

  // Ensure real timers are restored
  vi.useRealTimers();

  // Clear any remaining global stubs
  vi.unstubAllGlobals();

  // Force garbage collection after all tests complete
  if (typeof (globalThis as any).gc === 'function') {
    (globalThis as any).gc();
  }
});

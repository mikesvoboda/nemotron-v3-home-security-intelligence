import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterAll, afterEach, beforeAll, vi } from 'vitest';

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
});

/**
 * Comprehensive cleanup after each test to prevent zombie processes.
 * This addresses common causes of hanging tests:
 * - Unclosed mock timers (setTimeout/setInterval)
 * - Leftover mock state
 * - Uncleared global stubs
 * - React component cleanup
 */
afterEach(() => {
  // Clean up React Testing Library rendered components
  cleanup();

  // Clear all mock function calls and instances
  vi.clearAllMocks();

  // Clear all pending fake timers (setTimeout, setInterval, etc.)
  vi.clearAllTimers();

  // Reset timers to real timers if fake timers were used
  // This prevents timer state from leaking between tests
  vi.useRealTimers();

  // Unstub all global mocks (fetch, WebSocket, etc.)
  vi.unstubAllGlobals();
});

/**
 * Final cleanup after all tests in a file complete.
 * Ensures any remaining state is properly cleaned up.
 */
afterAll(() => {
  // Final reset of all mocks
  vi.resetAllMocks();

  // Ensure real timers are restored
  vi.useRealTimers();

  // Clear any remaining global stubs
  vi.unstubAllGlobals();
});

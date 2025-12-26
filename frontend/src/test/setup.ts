import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, beforeAll } from 'vitest';

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
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
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

// Cleanup after each test
afterEach(() => {
  cleanup();
});

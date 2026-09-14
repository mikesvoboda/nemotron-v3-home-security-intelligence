/**
 * E2E Test Fixtures - Central Export
 *
 * Re-exports all fixtures for convenient importing in test specs.
 */

import { test as base, expect } from '@playwright/test';
import { setupApiMocks, defaultMockConfig, type ApiMockConfig } from './api-mocks';

// Re-export all fixtures from submodules
export * from './test-data';
export * from './api-mocks';
export * from './websocket-mock';
export * from './performance';

/**
 * Custom test fixture with auto-mocking.
 *
 * Usage in spec files:
 * ```typescript
 * import { test, expect } from '../fixtures';
 *
 * test('my test', async ({ page }) => {
 *   // API mocks already set up!
 *   await page.goto('/');
 * });
 *
 * // Override mock config for specific test:
 * test.use({ mockConfig: errorMockConfig });
 *
 * // Or override for a specific describe block:
 * test.describe('error handling', () => {
 *   test.use({ mockConfig: errorMockConfig });
 *
 *   test('shows error state', async ({ page }) => {
 *     await page.goto('/');
 *     // Will use error mock config
 *   });
 * });
 * ```
 */
export const test = base.extend<{
  autoMock: void;
  mockConfig: ApiMockConfig;
}>({
  // Default mock config - can be overridden per test
  mockConfig: [defaultMockConfig, { option: true }],

  // Auto-setup mocks before each test
  autoMock: [
    async ({ page, mockConfig }, use) => {
      // Disable the product tour to prevent overlay from blocking interactions
      // The Joyride overlay intercepts pointer events and causes tests to fail
      await page.addInitScript(() => {
        localStorage.setItem('nemotron-tour-completed', 'true');
        localStorage.setItem('nemotron-tour-skipped', 'true');
      });

      await setupApiMocks(page, mockConfig);
      await use();
    },
    { auto: true },
  ],
});

// Re-export expect for convenience
export { expect };

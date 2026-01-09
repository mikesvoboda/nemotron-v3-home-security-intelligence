/**
 * E2E Test Utilities - Main Export
 *
 * Centralized export for all E2E test utility functions. Import from this file
 * to access test helpers, data generators, wait utilities, and browser helpers.
 *
 * @example
 * ```typescript
 * import {
 *   waitForPageLoad,
 *   generateCamera,
 *   waitForWebSocket,
 *   setViewport,
 * } from './utils';
 *
 * test('example test', async ({ page }) => {
 *   await setViewport(page, 'tablet');
 *   await page.goto('/');
 *   await waitForPageLoad(page);
 *   await waitForWebSocket(page);
 * });
 * ```
 */

// Test Helper Functions
export {
  waitForPageLoad,
  mockApiResponse,
  clearTestState,
  takeScreenshotOnFailure,
  waitForElementStable,
  fillFormField,
  retryAction,
  isHeadedMode,
  getBrowserName,
  waitForConsoleMessage,
} from './test-helpers';

// Data Generators
export {
  generateCamera,
  generateCameras,
  generateEvent,
  generateEvents,
  generateDetection,
  generateDetections,
  generateAlert,
  generateAlerts,
  generateGpuStats,
  generateEmail,
  generateTimestamp,
} from './data-generators';

export type { CameraData, EventData, DetectionData, AlertData } from './data-generators';

// Wait Helpers
export {
  waitForWebSocket,
  waitForWebSocketDisconnect,
  waitForElement,
  waitForApiCall,
  waitForApiCalls,
  waitForAnimation,
  waitForLoadingToComplete,
  waitForTextChange,
  waitForElementCount,
  waitForNetworkIdle,
  waitWithBackoff,
} from './wait-helpers';

export type { WebSocketChannel } from './wait-helpers';

// Browser Helpers
export {
  VIEWPORT_PRESETS,
  setViewport,
  enableDarkMode,
  disableDarkMode,
  toggleDarkMode,
  NETWORK_PRESETS,
  simulateSlowNetwork,
  disableNetworkThrottling,
  simulateOfflineMode,
  restoreOnlineMode,
  clearStorage,
  setLocalStorage,
  getLocalStorage,
  setSessionStorage,
  getSessionStorage,
  setCookie,
  getCookie,
  blockResources,
  setGeolocation,
  setTimezone,
  takeFullPageScreenshot,
  getConsoleLogs,
} from './browser-helpers';

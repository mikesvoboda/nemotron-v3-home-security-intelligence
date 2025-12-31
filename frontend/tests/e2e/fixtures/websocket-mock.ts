/**
 * WebSocket Simulation Helper for E2E Tests
 *
 * Provides utilities for simulating WebSocket events and behaviors
 * in E2E tests. Since Playwright cannot directly mock WebSocket connections,
 * these helpers work by:
 * 1. Setting up API route interceptors that block WS upgrades
 * 2. Simulating WebSocket-like behavior through API polling
 * 3. Providing test hooks to trigger simulated real-time updates
 */

import type { Page } from '@playwright/test';

/**
 * WebSocket event types that can be simulated
 */
export type WebSocketEventType =
  | 'event_created'
  | 'event_updated'
  | 'camera_status'
  | 'gpu_update'
  | 'system_alert'
  | 'performance_update';

/**
 * Simulated WebSocket message structure
 */
export interface SimulatedWebSocketMessage {
  type: WebSocketEventType;
  data: Record<string, unknown>;
  timestamp: string;
}

/**
 * Configuration for WebSocket mock behavior
 */
export interface WebSocketMockConfig {
  /** Whether to block all WebSocket connections (default: true) */
  blockConnections?: boolean;
  /** Simulated connection delay in ms (default: 0) */
  connectionDelay?: number;
  /** Whether to simulate connection failures (default: false) */
  simulateFailure?: boolean;
  /** Custom failure message */
  failureMessage?: string;
}

/**
 * Default WebSocket mock configuration
 */
export const defaultWebSocketConfig: WebSocketMockConfig = {
  blockConnections: true,
  connectionDelay: 0,
  simulateFailure: false,
};

/**
 * Sets up WebSocket mocking for a page
 *
 * @param page - Playwright page object
 * @param config - WebSocket mock configuration
 */
export async function setupWebSocketMock(
  page: Page,
  config: WebSocketMockConfig = defaultWebSocketConfig
): Promise<void> {
  const mergedConfig = { ...defaultWebSocketConfig, ...config };

  // Block WebSocket upgrade requests
  await page.route('**/ws/**', async (route) => {
    if (mergedConfig.blockConnections) {
      if (mergedConfig.connectionDelay > 0) {
        await new Promise((resolve) => setTimeout(resolve, mergedConfig.connectionDelay));
      }

      if (mergedConfig.simulateFailure) {
        await route.abort('connectionfailed');
      } else {
        // Block the upgrade but don't fail completely
        await route.abort('connectionrefused');
      }
    } else {
      await route.continue();
    }
  });
}

/**
 * Creates a simulated WebSocket message
 *
 * @param type - Event type
 * @param data - Event data
 * @returns Simulated message object
 */
export function createWebSocketMessage(
  type: WebSocketEventType,
  data: Record<string, unknown>
): SimulatedWebSocketMessage {
  return {
    type,
    data,
    timestamp: new Date().toISOString(),
  };
}

/**
 * Simulates a new event being created via WebSocket
 *
 * @param page - Playwright page
 * @param eventData - Event data to simulate
 */
export async function simulateNewEvent(
  page: Page,
  eventData: {
    id: number;
    camera_id: string;
    camera_name: string;
    risk_score: number;
    risk_level: 'low' | 'medium' | 'high' | 'critical';
    summary: string;
  }
): Promise<void> {
  // Inject the event into the page's state through evaluate
  await page.evaluate((event) => {
    // Dispatch a custom event that components can listen to
    window.dispatchEvent(
      new CustomEvent('ws-simulated-event', {
        detail: {
          type: 'event_created',
          data: event,
        },
      })
    );
  }, eventData);
}

/**
 * Simulates a camera status change via WebSocket
 *
 * @param page - Playwright page
 * @param cameraId - Camera ID
 * @param status - New status ('online' | 'offline')
 */
export async function simulateCameraStatusChange(
  page: Page,
  cameraId: string,
  status: 'online' | 'offline'
): Promise<void> {
  await page.evaluate(
    ({ id, newStatus }) => {
      window.dispatchEvent(
        new CustomEvent('ws-simulated-event', {
          detail: {
            type: 'camera_status',
            data: {
              camera_id: id,
              status: newStatus,
              timestamp: new Date().toISOString(),
            },
          },
        })
      );
    },
    { id: cameraId, newStatus: status }
  );
}

/**
 * Simulates a GPU stats update via WebSocket
 *
 * @param page - Playwright page
 * @param gpuStats - GPU statistics
 */
export async function simulateGpuUpdate(
  page: Page,
  gpuStats: {
    utilization: number;
    memory_used: number;
    memory_total: number;
    temperature: number;
  }
): Promise<void> {
  await page.evaluate((stats) => {
    window.dispatchEvent(
      new CustomEvent('ws-simulated-event', {
        detail: {
          type: 'gpu_update',
          data: stats,
        },
      })
    );
  }, gpuStats);
}

/**
 * Simulates a system alert via WebSocket
 *
 * @param page - Playwright page
 * @param alert - Alert data
 */
export async function simulateSystemAlert(
  page: Page,
  alert: {
    severity: 'info' | 'warning' | 'critical';
    message: string;
    component?: string;
  }
): Promise<void> {
  await page.evaluate((alertData) => {
    window.dispatchEvent(
      new CustomEvent('ws-simulated-event', {
        detail: {
          type: 'system_alert',
          data: alertData,
        },
      })
    );
  }, alert);
}

/**
 * Helper to verify that the page shows disconnected state
 * (useful when WebSocket is blocked)
 *
 * @param page - Playwright page
 * @returns true if disconnected indicator is visible
 */
export async function isShowingDisconnectedState(page: Page): Promise<boolean> {
  const disconnectedIndicator = page.getByText(/Disconnected/i);
  return disconnectedIndicator.isVisible().catch(() => false);
}

/**
 * Helper to wait for WebSocket connection attempt
 * (useful for testing connection timing)
 *
 * @param page - Playwright page
 * @param timeoutMs - Maximum time to wait
 * @returns true if connection was attempted
 */
export async function waitForConnectionAttempt(
  page: Page,
  timeoutMs: number = 5000
): Promise<boolean> {
  let connectionAttempted = false;

  const listener = (route: { request: () => { url: () => string } }) => {
    if (route.request().url().includes('/ws/')) {
      connectionAttempted = true;
    }
  };

  page.on('route', listener);

  await page.waitForTimeout(timeoutMs);

  return connectionAttempted;
}

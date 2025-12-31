/**
 * API Mocking Utilities for E2E Tests
 *
 * Provides configurable API mock setup functions that can be customized
 * per test scenario. Eliminates duplication across test files.
 *
 * IMPORTANT: Route handlers are matched in the order they are registered.
 * More specific routes must be registered BEFORE more general routes.
 */

import type { Page, Route } from '@playwright/test';
import {
  allCameras,
  allEvents,
  mockGPUStats,
  mockSystemHealth,
  mockSystemStats,
  mockSystemConfig,
  mockEventStats,
  mockLogs,
  mockLogStats,
  mockAuditLogs,
  mockAuditStats,
  mockTelemetry,
  generateGPUHistory,
  transparentPngBase64,
} from './test-data';

/**
 * Configuration options for API mocks
 */
export interface ApiMockConfig {
  // Camera data
  cameras?: typeof allCameras;
  camerasError?: boolean;

  // Event data
  events?: typeof allEvents;
  eventsError?: boolean;
  eventStats?: typeof mockEventStats.normal;

  // GPU data
  gpuStats?: typeof mockGPUStats.healthy;
  gpuError?: boolean;
  gpuHistory?: ReturnType<typeof generateGPUHistory>;

  // System health
  systemHealth?: typeof mockSystemHealth.healthy;
  systemHealthError?: boolean;

  // System stats
  systemStats?: typeof mockSystemStats.normal;
  systemStatsError?: boolean;

  // System config
  systemConfig?: typeof mockSystemConfig.default;

  // Logs
  logs?: typeof mockLogs.sample;
  logStats?: typeof mockLogStats.normal;
  logsError?: boolean;

  // Audit logs
  auditLogs?: typeof mockAuditLogs.sample;
  auditStats?: typeof mockAuditStats.normal;
  auditError?: boolean;

  // Telemetry
  telemetry?: typeof mockTelemetry.normal;
  telemetryError?: boolean;

  // WebSocket behavior
  wsConnectionFail?: boolean;
}

/**
 * Default configuration using normal/healthy mock data
 */
export const defaultMockConfig: ApiMockConfig = {
  cameras: allCameras,
  events: allEvents,
  eventStats: mockEventStats.normal,
  gpuStats: mockGPUStats.healthy,
  gpuHistory: generateGPUHistory(10),
  systemHealth: mockSystemHealth.healthy,
  systemStats: mockSystemStats.normal,
  systemConfig: mockSystemConfig.default,
  logs: mockLogs.sample,
  logStats: mockLogStats.normal,
  auditLogs: mockAuditLogs.sample,
  auditStats: mockAuditStats.normal,
  telemetry: mockTelemetry.normal,
  wsConnectionFail: true, // Default to failing WS in E2E tests
};

/**
 * Error configuration for testing error states
 */
export const errorMockConfig: ApiMockConfig = {
  camerasError: true,
  eventsError: true,
  gpuError: true,
  systemHealthError: true,
  logsError: true,
  auditError: true,
  telemetryError: true,
  wsConnectionFail: true,
};

/**
 * Empty data configuration for testing empty states
 */
export const emptyMockConfig: ApiMockConfig = {
  cameras: [],
  events: [],
  eventStats: mockEventStats.empty,
  gpuStats: mockGPUStats.idle,
  gpuHistory: [],
  systemHealth: mockSystemHealth.healthy,
  systemStats: mockSystemStats.empty,
  systemConfig: mockSystemConfig.default,
  logs: [],
  logStats: mockLogStats.empty,
  auditLogs: [],
  auditStats: { ...mockAuditStats.normal, total: 0 },
  telemetry: mockTelemetry.normal,
  wsConnectionFail: true,
};

/**
 * High alert configuration for testing high-risk scenarios
 */
export const highAlertMockConfig: ApiMockConfig = {
  cameras: allCameras,
  events: allEvents.filter((e) => e.risk_level === 'high' || e.risk_level === 'critical'),
  eventStats: mockEventStats.highAlert,
  gpuStats: mockGPUStats.highLoad,
  systemHealth: mockSystemHealth.degraded,
  systemStats: mockSystemStats.busy,
  telemetry: mockTelemetry.congested,
  wsConnectionFail: true,
};

/**
 * Sets up all API mocks with the given configuration
 * @param page - Playwright page object
 * @param config - Optional configuration to override defaults
 */
export async function setupApiMocks(
  page: Page,
  config: ApiMockConfig = defaultMockConfig
): Promise<void> {
  const mergedConfig = { ...defaultMockConfig, ...config };

  // GPU History endpoint (BEFORE /api/system/gpu)
  await page.route('**/api/system/gpu/history*', async (route) => {
    if (mergedConfig.gpuError) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'GPU service unavailable' }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          samples: mergedConfig.gpuHistory || [],
          total: mergedConfig.gpuHistory?.length || 0,
          limit: 100,
        }),
      });
    }
  });

  // Camera snapshot endpoint (BEFORE /api/cameras)
  await page.route('**/api/cameras/*/snapshot*', async (route) => {
    const transparentPng = Buffer.from(transparentPngBase64, 'base64');
    await route.fulfill({
      status: 200,
      contentType: 'image/png',
      body: transparentPng,
    });
  });

  // Cameras endpoint
  await page.route('**/api/cameras', async (route) => {
    if (mergedConfig.camerasError) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Failed to fetch cameras' }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          cameras: mergedConfig.cameras || [],
        }),
      });
    }
  });

  // GPU Stats endpoint
  await page.route('**/api/system/gpu', async (route) => {
    if (mergedConfig.gpuError) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'GPU service unavailable' }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mergedConfig.gpuStats || mockGPUStats.healthy),
      });
    }
  });

  // Health endpoint
  await page.route('**/api/health', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'healthy',
        version: '0.1.0',
        timestamp: new Date().toISOString(),
      }),
    });
  });

  // System Health endpoint
  await page.route('**/api/system/health', async (route) => {
    if (mergedConfig.systemHealthError) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Health check failed' }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mergedConfig.systemHealth || mockSystemHealth.healthy),
      });
    }
  });

  // Event Stats endpoint (BEFORE /api/events)
  await page.route('**/api/events/stats*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mergedConfig.eventStats || mockEventStats.normal),
    });
  });

  // Events endpoint
  await page.route('**/api/events*', async (route) => {
    if (mergedConfig.eventsError) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Failed to fetch events' }),
      });
    } else {
      // Parse query parameters for filtering
      const url = new URL(route.request().url());
      const riskLevel = url.searchParams.get('risk_level');
      let events = mergedConfig.events || [];

      if (riskLevel) {
        events = events.filter((e) => e.risk_level === riskLevel);
      }

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          events,
          total: events.length,
          count: events.length,
          limit: 20,
          offset: 0,
        }),
      });
    }
  });

  // System Stats endpoint
  await page.route('**/api/system/stats', async (route) => {
    if (mergedConfig.systemStatsError) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Failed to fetch stats' }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mergedConfig.systemStats || mockSystemStats.normal),
      });
    }
  });

  // System Config endpoint
  await page.route('**/api/system/config', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mergedConfig.systemConfig || mockSystemConfig.default),
    });
  });

  // Telemetry endpoint
  await page.route('**/api/system/telemetry', async (route) => {
    if (mergedConfig.telemetryError) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Telemetry unavailable' }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mergedConfig.telemetry || mockTelemetry.normal),
      });
    }
  });

  // Log Stats endpoint (BEFORE /api/logs)
  await page.route('**/api/logs/stats', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mergedConfig.logStats || mockLogStats.normal),
    });
  });

  // Logs endpoint
  await page.route('**/api/logs*', async (route) => {
    if (mergedConfig.logsError) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Failed to fetch logs' }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          logs: mergedConfig.logs || [],
          total: mergedConfig.logs?.length || 0,
          count: mergedConfig.logs?.length || 0,
          limit: 50,
          offset: 0,
        }),
      });
    }
  });

  // Audit Stats endpoint (BEFORE /api/audit)
  await page.route('**/api/audit/stats', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mergedConfig.auditStats || mockAuditStats.normal),
    });
  });

  // Audit Logs endpoint
  await page.route('**/api/audit*', async (route) => {
    if (mergedConfig.auditError) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Failed to fetch audit logs' }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          logs: mergedConfig.auditLogs || [],
          total: mergedConfig.auditLogs?.length || 0,
          count: mergedConfig.auditLogs?.length || 0,
          limit: 50,
          offset: 0,
        }),
      });
    }
  });

  // Search endpoint
  await page.route('**/api/search*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        results: [],
        total_count: 0,
        query: '',
      }),
    });
  });

  // Workers status endpoint
  await page.route('**/api/system/workers', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        workers: [
          { name: 'file_watcher', status: 'running', last_heartbeat: new Date().toISOString() },
          { name: 'detector', status: 'running', last_heartbeat: new Date().toISOString() },
          { name: 'analyzer', status: 'running', last_heartbeat: new Date().toISOString() },
          { name: 'cleanup', status: 'running', last_heartbeat: new Date().toISOString() },
        ],
      }),
    });
  });

  // Performance update endpoint
  await page.route('**/api/system/performance', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        gpu: mergedConfig.gpuStats,
        host: {
          cpu_percent: 25,
          ram_used_gb: 8,
          ram_total_gb: 32,
          disk_used_gb: 200,
          disk_total_gb: 1000,
        },
        databases: {
          postgresql: { status: 'healthy', connections_active: 5, connections_max: 100 },
          redis: { status: 'healthy', connected_clients: 3, memory_mb: 128 },
        },
        containers: [
          { name: 'backend', status: 'running', health: 'healthy' },
          { name: 'frontend', status: 'running', health: 'healthy' },
          { name: 'rtdetr', status: 'running', health: 'healthy' },
        ],
        timestamp: new Date().toISOString(),
      }),
    });
  });

  // WebSocket connections
  await page.route('**/ws/**', async (route) => {
    if (mergedConfig.wsConnectionFail) {
      await route.abort('connectionfailed');
    } else {
      // Let the connection proceed (for tests that need real WS)
      await route.continue();
    }
  });
}

/**
 * Intercepts and modifies a specific API response
 * Useful for testing specific scenarios without full mock setup
 */
export async function interceptApi(
  page: Page,
  urlPattern: string,
  responseOverride: (route: Route) => Promise<void>
): Promise<void> {
  await page.route(urlPattern, responseOverride);
}

/**
 * Creates a delayed response handler for testing loading states
 */
export function withDelay(delayMs: number, response: object): (route: Route) => Promise<void> {
  return async (route: Route) => {
    await new Promise((resolve) => setTimeout(resolve, delayMs));
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(response),
    });
  };
}

/**
 * Creates an error response handler
 */
export function withError(
  status: number = 500,
  message: string = 'Internal server error'
): (route: Route) => Promise<void> {
  return async (route: Route) => {
    await route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify({ detail: message }),
    });
  };
}

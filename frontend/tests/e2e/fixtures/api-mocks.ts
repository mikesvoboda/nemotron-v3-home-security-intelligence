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

/**
 * Sets up zone API mocks for E2E tests
 * This is used in addition to setupApiMocks for zone-specific tests
 * @param page - Playwright page object
 * @param zonesByCamera - Map of camera IDs to zone arrays
 */
export async function setupZoneApiMocks(
  page: Page,
  zonesByCamera: Record<string, object[]> = {}
): Promise<void> {
  // List zones for a camera
  await page.route('**/api/cameras/*/zones', async (route) => {
    const method = route.request().method();
    const url = route.request().url();

    // Extract camera_id from URL
    const cameraIdMatch = url.match(/\/api\/cameras\/([^/]+)\/zones/);
    const cameraId = cameraIdMatch ? cameraIdMatch[1] : null;

    if (method === 'GET') {
      const zones = cameraId && zonesByCamera[cameraId] ? zonesByCamera[cameraId] : [];
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          zones,
          count: zones.length,
        }),
      });
    } else if (method === 'POST') {
      // Create zone - return mock response with generated ID
      const requestBody = route.request().postDataJSON() as Record<string, unknown>;
      const newZone = {
        id: 'zone-' + String(Date.now()),
        camera_id: cameraId,
        ...requestBody,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(newZone),
      });
    } else {
      await route.continue();
    }
  });

  // Individual zone operations (get, update, delete)
  await page.route('**/api/cameras/*/zones/*', async (route) => {
    const method = route.request().method();
    const url = route.request().url();

    // Extract camera_id and zone_id from URL
    const match = url.match(/\/api\/cameras\/([^/]+)\/zones\/([^/?]+)/);
    const cameraId = match ? match[1] : null;
    const zoneId = match ? match[2] : null;

    if (!cameraId || !zoneId) {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Zone not found' }),
      });
      return;
    }

    const zones = zonesByCamera[cameraId] || [];
    const zone = zones.find((z: { id?: string }) => z.id === zoneId);

    if (method === 'GET') {
      if (zone) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(zone),
        });
      } else {
        await route.fulfill({
          status: 404,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Zone with id ' + zoneId + ' not found' }),
        });
      }
    } else if (method === 'PUT') {
      const requestBody = route.request().postDataJSON() as Record<string, unknown>;
      const updatedZone = {
        ...zone,
        ...requestBody,
        updated_at: new Date().toISOString(),
      };
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(updatedZone),
      });
    } else if (method === 'DELETE') {
      await route.fulfill({
        status: 204,
        body: '',
      });
    } else {
      await route.continue();
    }
  });
}

/**
 * Sets up zone API mocks that return errors
 * @param page - Playwright page object
 */
export async function setupZoneApiMocksWithError(page: Page): Promise<void> {
  await page.route('**/api/cameras/*/zones*', async (route) => {
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Zone service unavailable' }),
    });
  });
}

/**
 * Sets up alert rules API mocks for E2E tests
 * @param page - Playwright page object
 * @param rules - Array of alert rules to return
 * @param options - Additional options like error states
 */
export async function setupAlertRulesApiMocks(
  page: Page,
  rules: object[] = [],
  options: {
    listError?: boolean;
    createError?: boolean;
    updateError?: boolean;
    deleteError?: boolean;
    testError?: boolean;
  } = {}
): Promise<void> {
  // Track rules state for CRUD operations
  let currentRules = [...rules];

  // List alert rules - must be registered before individual rule routes
  await page.route('**/api/alerts/rules', async (route) => {
    const method = route.request().method();

    if (method === 'GET') {
      if (options.listError) {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Failed to fetch alert rules' }),
        });
        return;
      }

      // Parse query parameters for filtering
      const url = new URL(route.request().url());
      const enabledParam = url.searchParams.get('enabled');
      const severityParam = url.searchParams.get('severity');
      const limitParam = url.searchParams.get('limit');
      const offsetParam = url.searchParams.get('offset');

      let filteredRules = currentRules;

      // Filter by enabled status
      if (enabledParam !== null) {
        const enabled = enabledParam === 'true';
        filteredRules = filteredRules.filter((r: { enabled?: boolean }) => r.enabled === enabled);
      }

      // Filter by severity
      if (severityParam) {
        filteredRules = filteredRules.filter((r: { severity?: string }) => r.severity === severityParam);
      }

      // Apply pagination
      const limit = limitParam ? parseInt(limitParam, 10) : 50;
      const offset = offsetParam ? parseInt(offsetParam, 10) : 0;
      const paginatedRules = filteredRules.slice(offset, offset + limit);

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          rules: paginatedRules,
          count: filteredRules.length,
          limit,
          offset,
        }),
      });
    } else if (method === 'POST') {
      if (options.createError) {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Failed to create alert rule' }),
        });
        return;
      }

      const requestBody = route.request().postDataJSON() as Record<string, unknown>;

      // Validate required fields
      if (!requestBody.name) {
        await route.fulfill({
          status: 422,
          contentType: 'application/json',
          body: JSON.stringify({
            detail: [{ loc: ['body', 'name'], msg: 'field required', type: 'value_error.missing' }],
          }),
        });
        return;
      }

      const newRule = {
        id: 'rule-' + String(Date.now()),
        ...requestBody,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      currentRules.push(newRule);

      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(newRule),
      });
    } else {
      await route.continue();
    }
  });

  // Test rule endpoint - MUST be registered BEFORE individual rule routes
  await page.route('**/api/alerts/rules/*/test', async (route) => {
    if (options.testError) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Failed to test alert rule' }),
      });
      return;
    }

    const url = route.request().url();
    const ruleIdMatch = url.match(/\/api\/alerts\/rules\/([^/]+)\/test/);
    const ruleId = ruleIdMatch ? ruleIdMatch[1] : null;

    const rule = currentRules.find((r: { id?: string }) => r.id === ruleId);
    if (!rule) {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Alert rule with id ' + ruleId + ' not found' }),
      });
      return;
    }

    // Return mock test results
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        rule_id: ruleId,
        rule_name: (rule as { name?: string }).name || 'Unknown',
        events_tested: 10,
        events_matched: 4,
        match_rate: 0.4,
        results: [
          {
            event_id: 1,
            camera_id: 'cam-1',
            risk_score: 85,
            object_types: ['person'],
            matches: true,
            matched_conditions: ['risk_threshold', 'object_types'],
            started_at: new Date(Date.now() - 3600000).toISOString(),
          },
          {
            event_id: 2,
            camera_id: 'cam-2',
            risk_score: 55,
            object_types: ['person'],
            matches: false,
            matched_conditions: [],
            started_at: new Date(Date.now() - 7200000).toISOString(),
          },
        ],
      }),
    });
  });

  // Individual rule operations (get, update, delete)
  await page.route('**/api/alerts/rules/*', async (route) => {
    const method = route.request().method();
    const url = route.request().url();

    // Skip if this is a test endpoint (handled above)
    if (url.includes('/test')) {
      await route.continue();
      return;
    }

    // Extract rule_id from URL
    const ruleIdMatch = url.match(/\/api\/alerts\/rules\/([^/?]+)$/);
    const ruleId = ruleIdMatch ? ruleIdMatch[1] : null;

    if (!ruleId) {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Alert rule not found' }),
      });
      return;
    }

    const ruleIndex = currentRules.findIndex((r: { id?: string }) => r.id === ruleId);
    const rule = ruleIndex >= 0 ? currentRules[ruleIndex] : null;

    if (method === 'GET') {
      if (rule) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(rule),
        });
      } else {
        await route.fulfill({
          status: 404,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Alert rule with id ' + ruleId + ' not found' }),
        });
      }
    } else if (method === 'PUT') {
      if (options.updateError) {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Failed to update alert rule' }),
        });
        return;
      }

      if (!rule) {
        await route.fulfill({
          status: 404,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Alert rule with id ' + ruleId + ' not found' }),
        });
        return;
      }

      const requestBody = route.request().postDataJSON() as Record<string, unknown>;
      const updatedRule = {
        ...rule,
        ...requestBody,
        updated_at: new Date().toISOString(),
      };
      currentRules[ruleIndex] = updatedRule;

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(updatedRule),
      });
    } else if (method === 'DELETE') {
      if (options.deleteError) {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Failed to delete alert rule' }),
        });
        return;
      }

      if (!rule) {
        await route.fulfill({
          status: 404,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Alert rule with id ' + ruleId + ' not found' }),
        });
        return;
      }

      currentRules = currentRules.filter((r: { id?: string }) => r.id !== ruleId);

      await route.fulfill({
        status: 204,
        body: '',
      });
    } else {
      await route.continue();
    }
  });
}

/**
 * Sets up alert rules API mocks that return errors
 * @param page - Playwright page object
 */
export async function setupAlertRulesApiMocksWithError(page: Page): Promise<void> {
  await page.route('**/api/alerts/rules*', async (route) => {
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Alert rules service unavailable' }),
    });
  });
}

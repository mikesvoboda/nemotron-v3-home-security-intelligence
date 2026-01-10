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
  zonesByCamera,
  allAlertRules,
  mockRuleTestResults,
  mockAiAuditStats,
  mockAiAuditLeaderboard,
  mockAiAuditRecommendations,
  mockActivityBaseline,
  mockClassBaseline,
  mockAnomalyConfig,
  mockAIMetrics,
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
  eventStats?: (typeof mockEventStats)[keyof typeof mockEventStats];

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

  // Zones
  zones?: typeof zonesByCamera;
  zonesError?: boolean;

  // Alert rules
  alertRules?: typeof allAlertRules;
  alertRulesError?: boolean;
  ruleTestResults?: typeof mockRuleTestResults.withMatches;

  // AI Audit
  aiAuditStats?: typeof mockAiAuditStats.normal;
  aiAuditLeaderboard?: typeof mockAiAuditLeaderboard.normal;
  aiAuditRecommendations?: typeof mockAiAuditRecommendations.normal;
  aiAuditError?: boolean;

  // Analytics/Baseline
  activityBaseline?: typeof mockActivityBaseline.normal;
  classBaseline?: typeof mockClassBaseline.normal;
  anomalyConfig?: typeof mockAnomalyConfig.default;
  analyticsError?: boolean;

  // AI Metrics (for AI Performance page)
  aiMetrics?: typeof mockAIMetrics.normal;
  aiMetricsError?: boolean;

  // Entities
  entities?: Array<{
    id: string;
    entity_type: 'person' | 'vehicle';
    first_seen: string;
    last_seen: string;
    appearance_count: number;
    cameras_seen: string[];
    thumbnail_url?: string;
  }>;
  entitiesError?: boolean;

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
  zones: zonesByCamera,
  alertRules: allAlertRules,
  ruleTestResults: mockRuleTestResults.withMatches,
  aiAuditStats: mockAiAuditStats.normal,
  aiAuditLeaderboard: mockAiAuditLeaderboard.normal,
  aiAuditRecommendations: mockAiAuditRecommendations.normal,
  activityBaseline: mockActivityBaseline.normal,
  classBaseline: mockClassBaseline.normal,
  anomalyConfig: mockAnomalyConfig.default,
  aiMetrics: mockAIMetrics.normal,
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
  alertRulesError: true,
  aiAuditError: true,
  analyticsError: true,
  aiMetricsError: true,
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
  aiAuditStats: mockAiAuditStats.empty,
  aiAuditLeaderboard: mockAiAuditLeaderboard.empty,
  aiAuditRecommendations: mockAiAuditRecommendations.empty,
  activityBaseline: mockActivityBaseline.empty,
  classBaseline: mockClassBaseline.empty,
  anomalyConfig: mockAnomalyConfig.default,
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

  // Baseline Activity endpoint (BEFORE all other /api/cameras/* routes)
  await page.route('**/api/cameras/*/baseline/activity', async (route) => {
    if (mergedConfig.analyticsError) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Failed to fetch activity baseline' }),
      });
    } else {
      // Extract camera_id from URL
      const url = route.request().url();
      const match = url.match(/\/api\/cameras\/([^/]+)\/baseline\/activity/);
      const cameraId = match?.[1] || 'cam-1';
      const baseline = mergedConfig.activityBaseline || mockActivityBaseline.normal;

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ...baseline,
          camera_id: cameraId,
        }),
      });
    }
  });

  // Baseline Classes endpoint (BEFORE all other /api/cameras/* routes)
  await page.route('**/api/cameras/*/baseline/classes', async (route) => {
    if (mergedConfig.analyticsError) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Failed to fetch class baseline' }),
      });
    } else {
      // Extract camera_id from URL
      const url = route.request().url();
      const match = url.match(/\/api\/cameras\/([^/]+)\/baseline\/classes/);
      const cameraId = match?.[1] || 'cam-1';
      const baseline = mergedConfig.classBaseline || mockClassBaseline.normal;

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ...baseline,
          camera_id: cameraId,
        }),
      });
    }
  });

  // Camera snapshot endpoint (BEFORE /api/cameras)
  await page.route('**/api/cameras/*/snapshot*', async (route) => {
    // Convert base64 to binary using Uint8Array (works in both Node.js and browser)
    const binaryString = atob(transparentPngBase64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    await route.fulfill({
      status: 200,
      contentType: 'image/png',
      body: bytes,
    });
  });

  // Zone endpoints (BEFORE /api/cameras to match specific zone routes)
  // GET /api/cameras/:camera_id/zones
  await page.route('**/api/cameras/*/zones', async (route) => {
    if (route.request().method() === 'GET') {
      if (mergedConfig.zonesError) {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Failed to fetch zones' }),
        });
      } else {
        // Extract camera_id from URL
        const url = route.request().url();
        const match = url.match(/\/api\/cameras\/([^/]+)\/zones/);
        const cameraId = match?.[1] || '';
        const zonesData = mergedConfig.zones || zonesByCamera;
        const zones = zonesData[cameraId as keyof typeof zonesData] || [];

        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            items: zones,
            pagination: {
              total: zones.length,
              limit: 50,
              offset: null,
              cursor: null,
              next_cursor: null,
              has_more: false,
            },
          }),
        });
      }
    } else if (route.request().method() === 'POST') {
      // Create zone
      if (mergedConfig.zonesError) {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Failed to create zone' }),
        });
      } else {
        const body = route.request().postDataJSON();
        const newZone = {
          id: `zone-${Date.now()}`,
          camera_id: body.camera_id || 'cam-1',
          ...body,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify(newZone),
        });
      }
    } else {
      await route.continue();
    }
  });

  // Individual zone operations: GET/PUT/DELETE /api/cameras/:camera_id/zones/:zone_id
  await page.route('**/api/cameras/*/zones/*', async (route) => {
    const method = route.request().method();
    const url = route.request().url();

    // Skip if this is the zones list endpoint (handled above)
    if (url.endsWith('/zones')) {
      await route.continue();
      return;
    }

    if (mergedConfig.zonesError) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Zone operation failed' }),
      });
      return;
    }

    if (method === 'GET') {
      // Get single zone
      const match = url.match(/\/api\/cameras\/([^/]+)\/zones\/([^/]+)/);
      const cameraId = match?.[1] || '';
      const zoneId = match?.[2] || '';
      const zonesData = mergedConfig.zones || zonesByCamera;
      const zones = zonesData[cameraId as keyof typeof zonesData] || [];
      const zone = zones.find((z: { id: string }) => z.id === zoneId);

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
          body: JSON.stringify({ detail: 'Zone not found' }),
        });
      }
    } else if (method === 'PUT') {
      // Update zone
      const body = route.request().postDataJSON();
      const updatedZone = {
        id: 'zone-updated',
        ...body,
        updated_at: new Date().toISOString(),
      };
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(updatedZone),
      });
    } else if (method === 'DELETE') {
      // Delete zone
      await route.fulfill({
        status: 204,
        body: '',
      });
    } else {
      await route.continue();
    }
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
      const cameras = mergedConfig.cameras || [];
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: cameras,
          pagination: {
            total: cameras.length,
            limit: 50,
            offset: null,
            cursor: null,
            next_cursor: null,
            has_more: false,
          },
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

  // Event Detections endpoint (BEFORE /api/events)
  // Returns detections for a specific event - used by EventDetailModal
  await page.route('**/api/events/*/detections*', async (route) => {
    // Extract event ID from URL
    const url = new URL(route.request().url());
    const pathParts = url.pathname.split('/');
    const eventIdIndex = pathParts.indexOf('events') + 1;
    const eventId = parseInt(pathParts[eventIdIndex], 10);

    // Find the event and return its detections
    const events = mergedConfig.events || [];
    const event = events.find((e) => e.id === eventId);
    const detections = event?.detections || [];

    // Transform detections to API format with required fields
    const apiDetections = detections.map((d, idx) => ({
      id: idx + 1,
      event_id: eventId,
      label: d.label,
      confidence: d.confidence,
      bbox: d.bbox || null,
      image_path: null,
      created_at: new Date().toISOString(),
    }));

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: apiDetections,
        pagination: {
          total: apiDetections.length,
          limit: 100,
          offset: null,
          cursor: null,
          next_cursor: null,
          has_more: false,
        },
      }),
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
          items: events,
          pagination: {
            total: events.length,
            limit: 20,
            offset: null,
            cursor: null,
            next_cursor: null,
            has_more: false,
          },
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

  // Logs endpoint (uses pagination envelope format)
  await page.route('**/api/logs*', async (route) => {
    if (mergedConfig.logsError) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Failed to fetch logs' }),
      });
    } else {
      const logs = mergedConfig.logs || [];
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: logs,
          pagination: {
            total: logs.length,
            limit: 50,
            offset: null,
            cursor: null,
            next_cursor: null,
            has_more: false,
          },
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

  // AI Audit Stats endpoint (BEFORE /api/ai-audit)
  await page.route('**/api/ai-audit/stats*', async (route) => {
    if (mergedConfig.aiAuditError) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Failed to fetch AI audit stats' }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mergedConfig.aiAuditStats || mockAiAuditStats.normal),
      });
    }
  });

  // AI Audit Leaderboard endpoint
  await page.route('**/api/ai-audit/leaderboard*', async (route) => {
    if (mergedConfig.aiAuditError) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Failed to fetch AI audit leaderboard' }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mergedConfig.aiAuditLeaderboard || mockAiAuditLeaderboard.normal),
      });
    }
  });

  // AI Audit Recommendations endpoint
  await page.route('**/api/ai-audit/recommendations*', async (route) => {
    if (mergedConfig.aiAuditError) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Failed to fetch AI audit recommendations' }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mergedConfig.aiAuditRecommendations || mockAiAuditRecommendations.normal),
      });
    }
  });

  // AI Audit Event endpoint
  await page.route('**/api/ai-audit/events/*', async (route) => {
    if (mergedConfig.aiAuditError) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Failed to fetch event audit' }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 1,
          event_id: 1,
          audited_at: new Date().toISOString(),
          is_fully_evaluated: true,
          contributions: {
            rtdetr: true,
            florence: true,
            clip: false,
            violence: false,
            clothing: true,
            vehicle: false,
            pet: false,
            weather: false,
            image_quality: true,
            zones: true,
            baseline: true,
            cross_camera: false,
          },
          prompt_length: 5000,
          prompt_token_estimate: 1250,
          enrichment_utilization: 0.5,
          scores: {
            context_usage: 4.2,
            reasoning_coherence: 4.0,
            risk_justification: 3.8,
            consistency: 4.5,
            overall: 4.1,
          },
          consistency_risk_score: 75,
          consistency_diff: -5,
          self_eval_critique: 'Good overall analysis with room for improvement in risk justification.',
          improvements: {
            missing_context: ['Add time since last motion'],
            confusing_sections: [],
            unused_data: ['Weather data'],
            format_suggestions: [],
            model_gaps: [],
          },
        }),
      });
    }
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
      const auditLogs = mergedConfig.auditLogs || [];
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: auditLogs,
          pagination: {
            total: auditLogs.length,
            limit: 50,
            offset: null,
            cursor: null,
            next_cursor: null,
            has_more: false,
          },
        }),
      });
    }
  });

  // Entities endpoint (NEM-2075: uses pagination envelope format)
  await page.route('**/api/entities*', async (route) => {
    if (mergedConfig.entitiesError) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Failed to fetch entities' }),
      });
    } else {
      const entities = mergedConfig.entities || [];
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: entities,
          pagination: {
            total: entities.length,
            limit: 50,
            offset: 0,
            has_more: false,
          },
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

  // Alert Rules test endpoint (BEFORE /api/alerts/rules)
  await page.route('**/api/alerts/rules/*/test', async (route) => {
    if (mergedConfig.alertRulesError) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Failed to test rule' }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mergedConfig.ruleTestResults || mockRuleTestResults.withMatches),
      });
    }
  });

  // Individual Alert Rule operations: GET/PUT/DELETE /api/alerts/rules/:rule_id
  await page.route('**/api/alerts/rules/*', async (route) => {
    const method = route.request().method();
    const url = route.request().url();

    // Skip if this is the test endpoint or rules list endpoint
    if (url.includes('/test') || url.endsWith('/rules')) {
      await route.continue();
      return;
    }

    if (mergedConfig.alertRulesError) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Alert rule operation failed' }),
      });
      return;
    }

    if (method === 'GET') {
      // Get single rule
      const match = url.match(/\/api\/alerts\/rules\/([^/]+)/);
      const ruleId = match?.[1] || '';
      const rules = mergedConfig.alertRules || allAlertRules;
      const rule = rules.find((r: { id: string }) => r.id === ruleId);

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
          body: JSON.stringify({ detail: 'Alert rule not found' }),
        });
      }
    } else if (method === 'PUT') {
      // Update rule
      const body = route.request().postDataJSON();
      const match = url.match(/\/api\/alerts\/rules\/([^/]+)/);
      const ruleId = match?.[1] || '';
      const rules = mergedConfig.alertRules || allAlertRules;
      const existingRule = rules.find((r: { id: string }) => r.id === ruleId);

      const updatedRule = {
        ...(existingRule || {}),
        ...body,
        id: ruleId,
        updated_at: new Date().toISOString(),
      };
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(updatedRule),
      });
    } else if (method === 'DELETE') {
      // Delete rule
      await route.fulfill({
        status: 204,
        body: '',
      });
    } else {
      await route.continue();
    }
  });

  // Alert Rules list/create endpoint
  await page.route('**/api/alerts/rules', async (route) => {
    const method = route.request().method();

    if (method === 'GET') {
      if (mergedConfig.alertRulesError) {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Failed to fetch alert rules' }),
        });
      } else {
        const rules = mergedConfig.alertRules || allAlertRules;
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            items: rules,
            pagination: {
              total: rules.length,
              limit: 50,
              offset: null,
              cursor: null,
              next_cursor: null,
              has_more: false,
            },
          }),
        });
      }
    } else if (method === 'POST') {
      if (mergedConfig.alertRulesError) {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Failed to create alert rule' }),
        });
      } else {
        const body = route.request().postDataJSON();
        const newRule = {
          id: `rule-${Date.now()}`,
          ...body,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify(newRule),
        });
      }
    } else {
      await route.continue();
    }
  });

  // Anomaly Config endpoint
  await page.route('**/api/system/anomaly-config', async (route) => {
    const method = route.request().method();

    if (mergedConfig.analyticsError) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Failed to fetch anomaly config' }),
      });
    } else if (method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mergedConfig.anomalyConfig || mockAnomalyConfig.default),
      });
    } else if (method === 'PATCH') {
      const body = route.request().postDataJSON();
      const updatedConfig = {
        ...(mergedConfig.anomalyConfig || mockAnomalyConfig.default),
        ...body,
      };
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(updatedConfig),
      });
    } else {
      await route.continue();
    }
  });

  // AI Metrics endpoint (for AI Performance page telemetry)
  await page.route('**/api/system/ai-metrics', async (route) => {
    if (mergedConfig.aiMetricsError) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Failed to fetch AI metrics' }),
      });
    } else {
      const metrics = mergedConfig.aiMetrics || mockAIMetrics.normal;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(metrics),
      });
    }
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

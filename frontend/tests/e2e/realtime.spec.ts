import { test, expect } from '@playwright/test';

/**
 * Real-time Update Tests for Home Security Dashboard
 *
 * These tests verify that real-time features work correctly.
 * WebSocket connections are mocked to simulate real-time events.
 *
 * IMPORTANT: Route handlers are matched in the order they are registered.
 * More specific routes must be registered BEFORE more general routes.
 */

// Helper function to set up common API mocks
async function setupApiMocks(page: import('@playwright/test').Page) {
  // Mock the GPU history endpoint FIRST (more specific than /api/system/gpu)
  await page.route('**/api/system/gpu/history*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        samples: [
          {
            utilization: 45,
            memory_used: 8192,
            memory_total: 24576,
            temperature: 52,
            inference_fps: 12.5,
            recorded_at: new Date().toISOString(),
          },
        ],
        total: 1,
        limit: 100,
      }),
    });
  });

  // Mock camera snapshot endpoint BEFORE general cameras endpoint
  await page.route('**/api/cameras/*/snapshot*', async (route) => {
    // Return a 1x1 transparent PNG for camera snapshots
    const transparentPng = Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
      'base64'
    );
    await route.fulfill({
      status: 200,
      contentType: 'image/png',
      body: transparentPng,
    });
  });

  // Mock the cameras endpoint - returns { cameras: [...] }
  await page.route('**/api/cameras', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        cameras: [
          {
            id: 'cam-1',
            name: 'Front Door',
            folder_path: '/export/foscam/front_door',
            status: 'online',
            created_at: new Date().toISOString(),
            last_seen_at: new Date().toISOString(),
          },
        ],
      }),
    });
  });

  // Mock the GPU stats endpoint
  await page.route('**/api/system/gpu', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        utilization: 45,
        memory_used: 8192,
        memory_total: 24576,
        temperature: 52,
        inference_fps: 12.5,
      }),
    });
  });

  // Mock the events stats endpoint BEFORE general events endpoint
  await page.route('**/api/events/stats*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        total_events: 0,
        events_by_risk_level: { low: 0, medium: 0, high: 0, critical: 0 },
        events_by_camera: {},
        average_risk_score: 0,
      }),
    });
  });

  // Mock the events endpoint - returns { events: [...], total, ... }
  await page.route('**/api/events*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        events: [],
        total: 0,
        limit: 20,
        offset: 0,
      }),
    });
  });

  // Mock the system config endpoint
  await page.route('**/api/system/config', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        batch_window_seconds: 90,
        batch_idle_timeout_seconds: 30,
        retention_days: 30,
      }),
    });
  });

  // Mock the system health endpoint
  await page.route('**/api/system/health', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'healthy',
        version: '0.1.0',
        services: {},
      }),
    });
  });

  // Mock the health endpoint
  await page.route('**/api/health', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'healthy',
        version: '0.1.0',
      }),
    });
  });

  // Mock WebSocket connections to fail (simulating disconnected state)
  await page.route('**/ws/**', async (route) => {
    await route.abort('connectionfailed');
  });
}

test.describe('Real-time Updates', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  test('dashboard shows disconnected state when WebSocket fails', async ({ page }) => {
    await page.goto('/');

    // Wait for dashboard to load
    await expect(page.getByRole('heading', { name: /Security Dashboard/i })).toBeVisible({
      timeout: 15000,
    });

    // The dashboard should show a disconnected indicator when WS fails
    // This is indicated by the "(Disconnected)" text in the subtitle
    await expect(page.getByText(/Disconnected/i)).toBeVisible({ timeout: 10000 });
  });

  test('activity feed shows empty state when no events', async ({ page }) => {
    await page.goto('/');

    // Wait for dashboard to load
    await expect(page.getByRole('heading', { name: /Security Dashboard/i })).toBeVisible({
      timeout: 15000,
    });

    // Activity feed section should be present (use first() since there are multiple matching elements)
    await expect(page.getByRole('heading', { name: /Live Activity/i }).first()).toBeVisible();

    // With no events, the activity feed should show "No activity" message
    await expect(page.getByText(/No activity/i)).toBeVisible();
  });

  test('dashboard displays GPU stats from API', async ({ page }) => {
    await page.goto('/');

    // Wait for dashboard to load
    await expect(page.getByRole('heading', { name: /Security Dashboard/i })).toBeVisible({
      timeout: 15000,
    });

    // GPU stats should be displayed (look for GPU-related text)
    // The GpuStats component shows utilization percentage
    await expect(page.getByText(/Utilization/i).first()).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Connection Status Indicators', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  test('header shows system status indicator', async ({ page }) => {
    await page.goto('/');

    // Wait for dashboard to load
    await expect(page.getByRole('heading', { name: /Security Dashboard/i })).toBeVisible({
      timeout: 15000,
    });

    // The header should have a system status indicator
    const header = page.locator('header').first();
    await expect(header).toBeVisible();

    // System status text should be present in header
    await expect(page.getByText(/System/i).first()).toBeVisible();
  });
});

test.describe('Error Handling', () => {
  test('dashboard shows error state when API fails', async ({ page }) => {
    // Mock API endpoints to return errors
    await page.route('**/api/cameras', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' }),
      });
    });

    await page.route('**/api/system/gpu*', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' }),
      });
    });

    await page.route('**/api/events*', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' }),
      });
    });

    await page.route('**/ws/**', async (route) => {
      await route.abort('connectionfailed');
    });

    await page.goto('/');

    // Dashboard should show error state
    await expect(page.getByRole('heading', { name: /Error Loading Dashboard/i })).toBeVisible({
      timeout: 15000,
    });

    // Reload button should be present
    await expect(page.getByRole('button', { name: /Reload Page/i })).toBeVisible();
  });
});

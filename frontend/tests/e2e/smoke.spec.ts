import { test, expect } from '@playwright/test';

/**
 * Smoke Tests for Home Security Dashboard
 *
 * These tests verify that the application loads and renders correctly.
 * They run against a development server with mocked backend responses.
 */

// Helper function to set up common API mocks
async function setupApiMocks(page: import('@playwright/test').Page) {
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
          {
            id: 'cam-2',
            name: 'Back Yard',
            folder_path: '/export/foscam/back_yard',
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

  // Mock the health endpoint
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

  // Mock the events endpoint - returns { events: [...], total, ... }
  await page.route('**/api/events*', async (route) => {
    // Check if this is the stats endpoint
    if (route.request().url().includes('/stats')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total_events: 1,
          events_by_risk_level: { low: 1, medium: 0, high: 0, critical: 0 },
          events_by_camera: { 'cam-1': 1 },
          average_risk_score: 25,
        }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          events: [
            {
              id: 1,
              camera_id: 'cam-1',
              camera_name: 'Front Door',
              timestamp: new Date().toISOString(),
              risk_score: 25,
              risk_level: 'low',
              summary: 'Person detected at front door',
              reviewed: false,
            },
          ],
          total: 1,
          limit: 20,
          offset: 0,
        }),
      });
    }
  });

  // Mock the system stats endpoint
  await page.route('**/api/system/stats', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        total_events: 150,
        events_today: 12,
        high_risk_events: 3,
        active_cameras: 2,
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

  // Mock WebSocket connections to prevent errors
  await page.route('**/ws/**', async (route) => {
    // Let the WebSocket upgrade fail gracefully
    await route.abort('connectionfailed');
  });
}

test.describe('Dashboard Smoke Tests', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  test('dashboard page loads successfully', async ({ page }) => {
    await page.goto('/');

    // Wait for the page to load
    await expect(page).toHaveTitle(/Home Security/i);

    // Verify the main dashboard heading is visible
    await expect(page.getByRole('heading', { name: /Security Dashboard/i })).toBeVisible({
      timeout: 15000,
    });
  });

  test('dashboard displays key components', async ({ page }) => {
    await page.goto('/');

    // Wait for loading to complete (loading skeleton should disappear)
    await expect(page.getByRole('heading', { name: /Security Dashboard/i })).toBeVisible({
      timeout: 15000,
    });

    // Verify risk level section is present
    await expect(page.getByRole('heading', { name: /Current Risk Level/i })).toBeVisible();

    // Verify camera status section is present
    await expect(page.getByRole('heading', { name: /Camera Status/i })).toBeVisible();

    // Verify live activity section is present (use first() since there are multiple matching elements)
    await expect(page.getByRole('heading', { name: /Live Activity/i }).first()).toBeVisible();
  });

  test('dashboard shows real-time monitoring subtitle', async ({ page }) => {
    await page.goto('/');

    // Wait for main heading first
    await expect(page.getByRole('heading', { name: /Security Dashboard/i })).toBeVisible({
      timeout: 15000,
    });

    await expect(page.getByText(/Real-time AI-powered home security monitoring/i)).toBeVisible();
  });

  test('dashboard has correct page title', async ({ page }) => {
    await page.goto('/');

    // Wait for the page to load
    await expect(page.getByRole('heading', { name: /Security Dashboard/i })).toBeVisible({
      timeout: 15000,
    });

    // Verify page title
    await expect(page).toHaveTitle(/Home Security/i);
  });
});

test.describe('Layout Smoke Tests', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  test('header displays branding', async ({ page }) => {
    await page.goto('/');

    // Wait for dashboard to load
    await expect(page.getByRole('heading', { name: /Security Dashboard/i })).toBeVisible({
      timeout: 15000,
    });

    // Check for NVIDIA branding in header
    await expect(page.getByText(/NVIDIA/i).first()).toBeVisible();
    await expect(page.getByText(/SECURITY/i).first()).toBeVisible();
  });

  test('sidebar navigation is visible', async ({ page }) => {
    await page.goto('/');

    // Wait for dashboard to load
    await expect(page.getByRole('heading', { name: /Security Dashboard/i })).toBeVisible({
      timeout: 15000,
    });

    // The sidebar should have navigation buttons (look for aside element which is the sidebar)
    const sidebar = page.locator('aside').first();
    await expect(sidebar).toBeVisible();
  });
});

import { test, expect } from '@playwright/test';

/**
 * Navigation Tests for Home Security Dashboard
 *
 * These tests verify that navigation between pages works correctly.
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

  // Mock the events endpoint - returns { events: [...], total, ... }
  await page.route('**/api/events*', async (route) => {
    // Check if this is the stats endpoint
    if (route.request().url().includes('/stats')) {
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
    } else {
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
    }
  });

  // Mock the logs endpoint
  await page.route('**/api/logs', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        logs: [],
        total: 0,
        limit: 50,
        offset: 0,
      }),
    });
  });

  // Mock the logs stats endpoint
  await page.route('**/api/logs/stats', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        debug: 0,
        info: 0,
        warning: 0,
        error: 0,
        total: 0,
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

  // Mock WebSocket connections
  await page.route('**/ws/**', async (route) => {
    await route.abort('connectionfailed');
  });
}

test.describe('Navigation Tests', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  test('can navigate to dashboard from root', async ({ page }) => {
    await page.goto('/');

    // Dashboard should be the default page
    await expect(page.getByRole('heading', { name: /Security Dashboard/i })).toBeVisible({
      timeout: 15000,
    });
  });

  test('can navigate to timeline page', async ({ page }) => {
    await page.goto('/timeline');

    // Timeline page should show event timeline heading
    await expect(page.getByRole('heading', { name: /Event Timeline/i })).toBeVisible({
      timeout: 15000,
    });
  });

  test('can navigate to logs page', async ({ page }) => {
    await page.goto('/logs');

    // Logs page should show system logs heading
    await expect(page.getByRole('heading', { name: /System Logs/i })).toBeVisible({
      timeout: 15000,
    });
  });

  test('can navigate to settings page', async ({ page }) => {
    await page.goto('/settings');

    // Settings page should show settings heading
    await expect(page.getByRole('heading', { name: /Settings/i })).toBeVisible({
      timeout: 15000,
    });
  });

  test('URL reflects current page', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveURL(/\/$/);

    await page.goto('/timeline');
    await expect(page).toHaveURL(/\/timeline$/);

    await page.goto('/logs');
    await expect(page).toHaveURL(/\/logs$/);

    await page.goto('/settings');
    await expect(page).toHaveURL(/\/settings$/);
  });

  test('page transitions preserve layout', async ({ page }) => {
    await page.goto('/');

    // Wait for dashboard to load
    await expect(page.getByRole('heading', { name: /Security Dashboard/i })).toBeVisible({
      timeout: 15000,
    });

    // Verify header is present
    const header = page.locator('header').first();
    await expect(header).toBeVisible();

    // Navigate to another page
    await page.goto('/settings');

    // Wait for settings to load
    await expect(page.getByRole('heading', { name: /Settings/i })).toBeVisible({
      timeout: 15000,
    });

    // Header should still be present
    await expect(header).toBeVisible();
  });
});

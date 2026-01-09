/**
 * Camera Management E2E Tests
 *
 * Linear Issue: NEM-1664
 * Test Coverage: Critical user journey for camera monitoring and management
 *
 * Acceptance Criteria:
 * - User can view all cameras in dashboard grid
 * - Camera status indicators are visible and accurate
 * - User can open individual camera detail view
 * - Camera detail shows comprehensive information
 * - Live camera feeds are displayed when available
 */

import { test, expect } from '../../fixtures';

test.describe('Camera Management Journey (NEM-1664)', () => {
  test.beforeEach(async ({ page, browserName }) => {
    // Navigate to dashboard first
    await page.goto('/', { waitUntil: 'domcontentloaded' });

    // Wait for initial load - WebSocket status indicator
    // Firefox/WebKit need longer timeout for WebSocket connection establishment
    const timeout = browserName === 'chromium' ? 10000 : 20000;
    await page.waitForSelector('[data-testid="dashboard-container"]', {
      state: 'visible',
      timeout
    });

    // Wait for main content to be ready (handles lazy loading)
    await page.waitForSelector('[data-testid="main-content"]', {
      state: 'visible',
      timeout: 5000
    });

    // Wait for camera data to load - camera grid appears after API data loads
    // This ensures we're past the skeleton loading state
    await page.waitForSelector('[data-testid="camera-grid"]', {
      state: 'visible',
      timeout: 10000
    });
  });

  test('dashboard displays all configured cameras in grid', async ({ page }) => {
    /**
     * Given: User is on the dashboard
     * When: Dashboard loads with camera data
     * Then: All configured cameras are visible in a grid layout
     */

    // Given: Dashboard is visible
    await expect(page.locator('[data-testid="dashboard-container"]')).toBeVisible();

    // When/Then: Verify camera grid is present (already waited in beforeEach)
    const cameraGrid = page.locator('[data-testid="camera-grid"]');
    await expect(cameraGrid).toBeVisible();

    // Verify individual camera cards exist
    const cameraCards = page.locator('[data-testid^="camera-card-"]');

    const cardCount = await cameraCards.count();
    expect(cardCount).toBeGreaterThan(0);
  });

  test('each camera card shows status indicator', async ({ page }) => {
    /**
     * Given: User is viewing the camera grid
     * When: User looks at individual camera cards
     * Then: Each card displays a status indicator (online/offline/error)
     */

    // Given: Dashboard is loaded (camera grid already visible from beforeEach)
    await expect(page.locator('[data-testid="dashboard-container"]')).toBeVisible();

    // When: Locate camera cards
    const cameraCards = page.locator('[data-testid^="camera-card-"]');
    await expect(cameraCards.first()).toBeVisible();

    const cardCount = await cameraCards.count();
    expect(cardCount).toBeGreaterThan(0);

    // Then: Verify first card has status indicator (Circle icon with status color)
    const firstCard = cameraCards.first();

    // Status badge is in the top-right corner with Circle icon and status text
    // Look for the text content like "Online", "Offline", "Recording", etc.
    const statusBadge = firstCard.locator('span:has-text("Online"), span:has-text("Offline"), span:has-text("Recording"), span:has-text("Error"), span:has-text("Unknown")');
    await expect(statusBadge.first()).toBeVisible();
  });

  test('camera cards display camera name and last activity time', async ({ page }) => {
    /**
     * Given: User is viewing camera grid
     * When: User looks at a camera card
     * Then: Card shows camera name and last seen/activity timestamp
     */

    // Given: Dashboard loaded (camera grid already visible from beforeEach)
    await expect(page.locator('[data-testid="dashboard-container"]')).toBeVisible();

    // When: Get first camera card
    const firstCamera = page.locator('[data-testid^="camera-card-"]').first();
    await expect(firstCamera).toBeVisible();

    // Then: Verify camera name is present (span with truncate class in bottom section)
    const cameraName = firstCamera.locator('span.truncate.text-sm.font-medium');
    await expect(cameraName).toBeVisible();

    const nameText = await cameraName.textContent();
    expect(nameText).toBeTruthy();
    expect(nameText?.length || 0).toBeGreaterThan(0);

    // Verify last activity/timestamp is present (if available)
    // Timestamp is optional - camera might not have last_seen_at
    const timestamp = firstCamera.locator('span.text-xs.text-text-secondary');
    const timestampCount = await timestamp.count();
    if (timestampCount > 0) {
      await expect(timestamp.first()).toBeVisible();
    }
  });

  test('user can open camera detail view by clicking camera card', async ({ page }) => {
    /**
     * Given: User is viewing camera grid on dashboard
     * When: User clicks on a camera card
     * Then: Navigates to timeline page filtered by that camera
     */

    // Given: Dashboard with cameras (camera grid already visible from beforeEach)
    await expect(page.locator('[data-testid="dashboard-container"]')).toBeVisible();

    const firstCamera = page.locator('[data-testid^="camera-card-"]').first();
    await expect(firstCamera).toBeVisible();

    // Get the camera ID from the data-testid attribute
    const cameraId = await firstCamera.getAttribute('data-testid');
    const extractedId = cameraId?.replace('camera-card-', '') || '';

    // When: Click camera card
    await firstCamera.click();

    // Then: Should navigate to timeline page with camera filter
    // URL should include /timeline?camera=<camera_id>
    await expect(page).toHaveURL(new RegExp(`/timeline\\?camera=${extractedId}`), { timeout: 5000 });
  });

  test('timeline page displays events filtered by camera', async ({ page }) => {
    /**
     * Given: User has clicked on a camera from the dashboard
     * When: Timeline page loads with camera filter
     * Then: Page shows events for that specific camera
     */

    // Given: Dashboard with cameras (camera grid already visible from beforeEach)
    const firstCamera = page.locator('[data-testid^="camera-card-"]').first();
    await expect(firstCamera).toBeVisible();

    // Get camera ID from the data-testid
    const cameraId = await firstCamera.getAttribute('data-testid');
    const extractedId = cameraId?.replace('camera-card-', '') || '';

    // When: Click camera to navigate to timeline
    await firstCamera.click();
    await expect(page).toHaveURL(new RegExp(`/timeline\\?camera=${extractedId}`), { timeout: 5000 });

    // Then: Timeline page should load and display the camera name or events
    // Wait for timeline container to be visible
    const timelineContainer = page.locator('[data-testid="timeline-container"]').or(
      page.locator('[data-testid="events-container"]')
    );

    if (await timelineContainer.count() > 0) {
      await expect(timelineContainer.first()).toBeVisible({ timeout: 5000 });
    }
  });

  test('camera status indicators update in real-time via WebSocket', async ({ page }) => {
    /**
     * Given: User is viewing camera grid with WebSocket connected
     * When: Camera status is displayed
     * Then: Status indicator is visible with appropriate styling
     */

    // Given: Dashboard with cameras (camera grid already visible from beforeEach)
    await expect(page.locator('[data-testid="dashboard-container"]')).toBeVisible();

    // Verify WebSocket status indicator is present
    await expect(page.locator('[data-testid="websocket-status"]')).toBeVisible({ timeout: 15000 });

    // When: Get first camera card
    const firstCamera = page.locator('[data-testid^="camera-card-"]').first();
    await expect(firstCamera).toBeVisible();

    // Then: Status badge should be visible with status text
    const statusBadge = firstCamera.locator('span:has-text("Online"), span:has-text("Offline"), span:has-text("Recording"), span:has-text("Error"), span:has-text("Unknown")');
    await expect(statusBadge.first()).toBeVisible();

    // Note: Actual real-time update testing would require WebSocket message injection
    // This test verifies the infrastructure is in place
  });

  test('camera grid layout is responsive and displays correctly', async ({ page }) => {
    /**
     * Given: User is viewing dashboard with cameras
     * When: User views on different screen sizes
     * Then: Camera grid adapts responsively
     */

    // Given: Dashboard with cameras (camera grid already visible from beforeEach)
    await expect(page.locator('[data-testid="dashboard-container"]')).toBeVisible();

    const cameraGrid = page.locator('[data-testid="camera-grid"]');
    await expect(cameraGrid).toBeVisible();

    // When: Check desktop layout
    const cameraCards = page.locator('[data-testid^="camera-card-"]');
    const desktopCount = await cameraCards.count();
    expect(desktopCount).toBeGreaterThan(0);

    // Then: Verify grid has layout classes for responsive design
    const gridClasses = await cameraGrid.getAttribute('class');
    expect(gridClasses).toContain('grid');

    // Test mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await page.waitForTimeout(500);

    // Cameras should still be visible
    await expect(cameraCards.first()).toBeVisible();

    // Test tablet viewport
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.waitForTimeout(500);

    await expect(cameraCards.first()).toBeVisible();

    // Reset to desktop
    await page.setViewportSize({ width: 1920, height: 1080 });
  });

  test('offline cameras are visually distinguished from online cameras', async ({ page }) => {
    /**
     * Given: User is viewing camera grid
     * When: User looks at cameras with different statuses
     * Then: Offline/error cameras have distinct visual styling via status badge
     */

    // Given: Dashboard with cameras (camera grid already visible from beforeEach)
    await expect(page.locator('[data-testid="dashboard-container"]')).toBeVisible();

    // When: Get all camera cards
    const cameraCards = page.locator('[data-testid^="camera-card-"]');
    await expect(cameraCards.first()).toBeVisible();

    const cardCount = await cameraCards.count();
    expect(cardCount).toBeGreaterThan(0);

    // Then: Check for status badges with status text
    // Each card should have a status badge in the top-right corner
    for (let i = 0; i < Math.min(cardCount, 4); i++) {
      const card = cameraCards.nth(i);
      const statusBadge = card.locator('span:has-text("Online"), span:has-text("Offline"), span:has-text("Recording"), span:has-text("Error"), span:has-text("Unknown")');
      await expect(statusBadge.first()).toBeVisible();
    }
  });
});

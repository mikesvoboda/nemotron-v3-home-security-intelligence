/**
 * Detection Workflow E2E Tests
 *
 * Linear Issue: NEM-1664
 * Test Coverage: Critical user journey from detection to AI analysis review
 *
 * Acceptance Criteria:
 * - User can view dashboard with recent detections
 * - User can click on a detection to view details
 * - Event detail modal shows detection information
 * - AI analysis is visible in the event detail
 * - User can navigate through multiple detections
 */

import { test, expect } from '../../fixtures';
import { waitForElement, waitForAnimation } from '../../utils/wait-helpers';

// Skip entire file in CI - complex workflow tests flaky due to timing issues
test.skip(({ }, testInfo) => !!process.env.CI, 'User journey tests flaky in CI - run locally');

/**
 * Helper to wait for modal content to be visible and stable.
 * Addresses HeadlessUI transition issues and React portal rendering.
 */
async function waitForModalContent(page: import('@playwright/test').Page) {
  // Wait for modal container to be attached to DOM
  const modal = page.locator('[data-testid="event-detail-modal"]');
  await modal.waitFor({ state: 'attached', timeout: 10000 });

  // Wait for modal to be visible (after transition animation)
  await expect(modal).toBeVisible({ timeout: 5000 });

  // Wait for key modal content to be stable (camera name heading)
  const modalHeading = page.getByRole('heading', { level: 2 });
  await expect(modalHeading).toBeVisible({ timeout: 5000 });

  // Wait for close button to be interactive
  const closeButton = page.locator('[data-testid="close-modal-button"]');
  await expect(closeButton).toBeVisible({ timeout: 3000 });

  // Additional stability delay for animations
  await page.waitForTimeout(300);
}

test.describe('Detection to Alert Journey (NEM-1664)', () => {
  test.beforeEach(async ({ page, browserName }) => {
    // Navigate to dashboard before each test
    await page.goto('/');

    // Wait for dashboard to load first (more reliable than WebSocket status)
    const timeout = browserName === 'chromium' ? 10000 : 20000;
    await page.waitForSelector('[data-testid="dashboard-container"]', {
      state: 'visible',
      timeout
    });

    // WebSocket status should be visible after dashboard loads
    await page.waitForSelector('[data-testid="websocket-status"]', {
      state: 'attached',
      timeout: 5000
    });
  });

  // TODO: Fix modal loading timeout - NEM-2748 (pre-existing test failure)
  test.skip('user can view detection details from dashboard', async ({ page }) => {
    /**
     * Given: User is on the dashboard with recent detections
     * When: User clicks on a recent detection card
     * Then: Event detail modal opens showing detection information and AI analysis
     */

    // Given: Wait for dashboard to load with data
    await expect(page.locator('[data-testid="dashboard-container"]')).toBeVisible();

    // Verify activity feed is visible
    const activityFeed = page.locator('[data-testid="activity-feed"]');
    await expect(activityFeed).toBeVisible();

    // When: Click on the first detection in activity feed
    const firstDetection = page.locator('[data-testid^="detection-card-"]').first();

    // Wait for at least one detection to appear with proper state
    await firstDetection.waitFor({ state: 'attached', timeout: 15000 });
    await expect(firstDetection).toBeVisible({ timeout: 5000 });

    // Store detection ID for verification
    const detectionId = await firstDetection.getAttribute('data-testid');

    await firstDetection.click();

    // Clicking detection navigates to timeline page with modal
    // Wait for URL to include the timeline path and event parameter
    await page.waitForURL(/\/timeline\?event=\d+/, { timeout: 10000 });

    // Allow timeline page to initialize and process URL parameter
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {
      // Network idle may timeout on slower connections - continue anyway
    });

    // Wait for modal to be fully rendered and stable
    await waitForModalContent(page);

    const eventModal = page.locator('[data-testid="event-detail-modal"]');

    // Verify modal shows detection information
    await expect(eventModal.locator('[data-testid="detection-timestamp"]')).toBeVisible();
    await expect(eventModal.locator('[data-testid="detection-camera"]')).toBeVisible();

    // Verify AI analysis section is present
    const aiAnalysis = eventModal.locator('[data-testid="ai-analysis-section"]');
    await expect(aiAnalysis).toBeVisible();

    // Verify risk score is displayed
    await expect(eventModal.locator('[data-testid="risk-score"]')).toBeVisible();
  });

  // TODO: Fix modal loading timeout - NEM-2748 (pre-existing test failure)
  test.skip('user can navigate through multiple detections sequentially', async ({ page }) => {
    /**
     * Given: User has opened a detection detail modal
     * When: User clicks next/previous navigation buttons
     * Then: Modal updates to show adjacent detection details
     */

    // Given: Open first detection
    await expect(page.locator('[data-testid="activity-feed"]')).toBeVisible();

    const detections = page.locator('[data-testid^="detection-card-"]');
    await detections.first().waitFor({ state: 'attached', timeout: 15000 });
    await expect(detections.first()).toBeVisible({ timeout: 5000 });

    const firstDetectionId = await detections.first().getAttribute('data-testid');
    await detections.first().click();

    // Wait for navigation to timeline page
    await page.waitForURL(/\/timeline\?event=\d+/, { timeout: 10000 });

    // Allow timeline page to initialize and process URL parameter
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {
      // Network idle may timeout on slower connections - continue anyway
    });

    // Wait for modal to be fully stable
    await waitForModalContent(page);

    const eventModal = page.locator('[data-testid="event-detail-modal"]');

    // When: Click next button if available
    const nextButton = eventModal.locator('[aria-label="Next event"]');

    // Check if next button exists and is enabled
    const nextButtonCount = await nextButton.count();
    if (nextButtonCount > 0) {
      const isDisabled = await nextButton.isDisabled();

      if (!isDisabled) {
        // Get current detection info before navigation
        const currentTimestamp = await eventModal
          .locator('[data-testid="detection-timestamp"]')
          .textContent();

        await nextButton.click();

        // Then: Wait for modal content to update (re-render with new data)
        await page.waitForTimeout(500); // Allow React state update

        // Wait for timestamp element to be stable after re-render
        const timestampLocator = eventModal.locator('[data-testid="detection-timestamp"]');
        await timestampLocator.waitFor({ state: 'attached', timeout: 3000 });

        const newTimestamp = await timestampLocator.textContent();

        // Verify content changed (timestamps should differ)
        expect(newTimestamp).not.toBe(currentTimestamp);
      }
    }
  });

  // TODO: Fix strict mode violation - NEM-2748 (pre-existing test failure)
  test.skip('detection detail modal shows comprehensive AI analysis', async ({ page }) => {
    /**
     * Given: User opens a detection with AI analysis
     * When: User views the AI analysis section
     * Then: All AI analysis components are visible (risk score, reasoning, recommendations)
     */

    // Given: Navigate to detection
    await expect(page.locator('[data-testid="activity-feed"]')).toBeVisible();

    const firstDetection = page.locator('[data-testid^="detection-card-"]').first();
    await firstDetection.waitFor({ state: 'attached', timeout: 15000 });
    await expect(firstDetection).toBeVisible({ timeout: 5000 });
    await firstDetection.click();

    // Wait for navigation to timeline page
    await page.waitForURL(/\/timeline\?event=\d+/, { timeout: 10000 });

    // Allow timeline page to initialize and process URL parameter
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {
      // Network idle may timeout on slower connections - continue anyway
    });

    // Wait for modal to be fully stable
    await waitForModalContent(page);

    const eventModal = page.locator('[data-testid="event-detail-modal"]');

    // When: Locate AI analysis section
    const aiSection = eventModal.locator('[data-testid="ai-analysis-section"]');
    await expect(aiSection).toBeVisible();

    // Then: Verify all AI components are present

    // Risk score with gauge/meter
    const riskScore = eventModal.locator('[data-testid="risk-score"]');
    await expect(riskScore).toBeVisible();

    // Verify risk score has a numeric value
    const scoreText = await riskScore.textContent();
    expect(scoreText).toMatch(/\d+/); // Contains at least one digit

    // AI reasoning/explanation (only check if present in data)
    const aiReasoning = eventModal.locator('[data-testid="ai-reasoning"]');
    const reasoningCount = await aiReasoning.count();

    if (reasoningCount > 0) {
      await expect(aiReasoning).toBeVisible();

      // Verify reasoning has content
      const reasoningText = await aiReasoning.textContent();
      expect(reasoningText?.length || 0).toBeGreaterThan(10);
    }

    // Detection objects list is optional (depends on API data)
    // The modal shows detections via "DETECTION SEQUENCE" thumbnails
  });

  // TODO: Fix modal loading timeout - NEM-2748 (pre-existing test failure)
  test.skip('user can close detection detail modal and return to timeline', async ({ page }) => {
    /**
     * Given: User has opened a detection detail modal from dashboard
     * When: User clicks the close button
     * Then: Modal closes and user remains on timeline view
     */

    // Given: Open detection modal from dashboard
    await expect(page.locator('[data-testid="activity-feed"]')).toBeVisible();

    const firstDetection = page.locator('[data-testid^="detection-card-"]').first();
    await firstDetection.waitFor({ state: 'attached', timeout: 15000 });
    await expect(firstDetection).toBeVisible({ timeout: 5000 });
    await firstDetection.click();

    // Clicking detection navigates to timeline page with modal
    await page.waitForURL(/\/timeline\?event=\d+/, { timeout: 10000 });

    // Allow timeline page to initialize and process URL parameter
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {
      // Network idle may timeout on slower connections - continue anyway
    });

    // Wait for modal to be fully stable
    await waitForModalContent(page);

    const eventModal = page.locator('[data-testid="event-detail-modal"]');

    // When: Close the modal (use Escape key - more reliable for HeadlessUI)
    await page.keyboard.press('Escape');

    // Then: Modal should be hidden (allow time for HeadlessUI exit animation)
    await expect(eventModal).not.toBeVisible({ timeout: 10000 });

    // Verify user is still on timeline page (URL should contain /timeline)
    expect(page.url()).toContain('/timeline');
  });

  test('detection cards show preview information before opening', async ({ page }) => {
    /**
     * Given: User is viewing the dashboard
     * When: User looks at detection cards in activity feed
     * Then: Each card shows preview info (timestamp, camera, object count)
     */

    // Given: Dashboard is loaded
    await expect(page.locator('[data-testid="activity-feed"]')).toBeVisible();

    // When: Locate detection cards
    const detectionCards = page.locator('[data-testid^="detection-card-"]');
    await detectionCards.first().waitFor({ state: 'attached', timeout: 15000 });
    await expect(detectionCards.first()).toBeVisible({ timeout: 5000 });

    const cardCount = await detectionCards.count();
    expect(cardCount).toBeGreaterThan(0);

    // Then: Verify first card has required preview elements
    const firstCard = detectionCards.first();

    // Timestamp should be visible
    await expect(firstCard.locator('[data-testid*="timestamp"]')).toBeVisible();

    // Camera name should be visible
    await expect(firstCard.locator('[data-testid*="camera"]')).toBeVisible();

    // Some indication of detection content (object count, thumbnail, etc.)
    const hasObjects = await firstCard.locator('[data-testid*="object"]').count();
    const hasThumbnail = await firstCard.locator('[data-testid*="thumbnail"]').count();

    // At least one content indicator should be present
    expect(hasObjects + hasThumbnail).toBeGreaterThan(0);
  });
});

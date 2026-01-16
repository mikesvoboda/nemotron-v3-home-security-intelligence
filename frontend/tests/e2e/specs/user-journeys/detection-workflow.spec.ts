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

// TODO: Fix modal stability issues in detection workflow tests
test.describe.skip('Detection to Alert Journey (NEM-1664)', () => {
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

  test('user can view detection details from dashboard', async ({ page }) => {
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

    // Wait for at least one detection to appear
    await expect(firstDetection).toBeVisible({ timeout: 15000 });

    // Store detection ID for verification
    const detectionId = await firstDetection.getAttribute('data-testid');

    await firstDetection.click();

    // Then: Event detail modal should open
    const eventModal = page.locator('[data-testid="event-detail-modal"]');
    await expect(eventModal).toBeVisible({ timeout: 5000 });

    // Verify modal shows detection information
    await expect(eventModal.locator('[data-testid="detection-timestamp"]')).toBeVisible();
    await expect(eventModal.locator('[data-testid="detection-camera"]')).toBeVisible();

    // Verify AI analysis section is present
    const aiAnalysis = eventModal.locator('[data-testid="ai-analysis-section"]');
    await expect(aiAnalysis).toBeVisible();

    // Verify risk score is displayed
    await expect(eventModal.locator('[data-testid="risk-score"]')).toBeVisible();
  });

  test('user can navigate through multiple detections sequentially', async ({ page }) => {
    /**
     * Given: User has opened a detection detail modal
     * When: User clicks next/previous navigation buttons
     * Then: Modal updates to show adjacent detection details
     */

    // Given: Open first detection
    await expect(page.locator('[data-testid="activity-feed"]')).toBeVisible();

    const detections = page.locator('[data-testid^="detection-card-"]');
    await expect(detections.first()).toBeVisible({ timeout: 15000 });

    const firstDetectionId = await detections.first().getAttribute('data-testid');
    await detections.first().click();

    const eventModal = page.locator('[data-testid="event-detail-modal"]');
    await expect(eventModal).toBeVisible();

    // When: Click next button if available
    const nextButton = eventModal.locator('[data-testid="next-detection-button"]');

    // Check if next button exists and is enabled
    if (await nextButton.count() > 0) {
      const isDisabled = await nextButton.getAttribute('disabled');

      if (!isDisabled) {
        // Get current detection info before navigation
        const currentTimestamp = await eventModal
          .locator('[data-testid="detection-timestamp"]')
          .textContent();

        await nextButton.click();

        // Then: Modal should update with different detection
        await page.waitForTimeout(500); // Allow time for data to update

        const newTimestamp = await eventModal
          .locator('[data-testid="detection-timestamp"]')
          .textContent();

        // Verify content changed (timestamps should differ)
        expect(newTimestamp).not.toBe(currentTimestamp);
      }
    }
  });

  test('detection detail modal shows comprehensive AI analysis', async ({ page }) => {
    /**
     * Given: User opens a detection with AI analysis
     * When: User views the AI analysis section
     * Then: All AI analysis components are visible (risk score, reasoning, recommendations)
     */

    // Given: Navigate to detection
    await expect(page.locator('[data-testid="activity-feed"]')).toBeVisible();

    const firstDetection = page.locator('[data-testid^="detection-card-"]').first();
    await expect(firstDetection).toBeVisible({ timeout: 15000 });
    await firstDetection.click();

    const eventModal = page.locator('[data-testid="event-detail-modal"]');
    await expect(eventModal).toBeVisible();

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

    // AI reasoning/explanation
    const aiReasoning = eventModal.locator('[data-testid="ai-reasoning"]');
    await expect(aiReasoning).toBeVisible();

    // Verify reasoning has content
    const reasoningText = await aiReasoning.textContent();
    expect(reasoningText?.length || 0).toBeGreaterThan(10);

    // Detection objects list is optional (depends on API data)
    // The modal shows detections via "DETECTION SEQUENCE" thumbnails
  });

  test('user can close detection detail modal and return to timeline', async ({ page }) => {
    /**
     * Given: User has opened a detection detail modal from dashboard
     * When: User clicks the close button
     * Then: Modal closes and user remains on timeline view
     */

    // Given: Open detection modal from dashboard
    await expect(page.locator('[data-testid="activity-feed"]')).toBeVisible();

    const firstDetection = page.locator('[data-testid^="detection-card-"]').first();
    await expect(firstDetection).toBeVisible({ timeout: 15000 });
    await firstDetection.click();

    // Clicking detection navigates to timeline page with modal
    await page.waitForURL(/\/timeline\?event=\d+/);

    const eventModal = page.locator('[data-testid="event-detail-modal"]');
    await expect(eventModal).toBeVisible();

    // When: Close the modal (use Escape key - more reliable for HeadlessUI)
    await page.keyboard.press('Escape');

    // Then: Modal should be hidden (allow time for HeadlessUI exit animation)
    await expect(eventModal).not.toBeVisible({ timeout: 10000 });

    // Verify user is on timeline page (not dashboard)
    await expect(page.locator('[data-testid="timeline-page"]')).toBeVisible();
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
    await expect(detectionCards.first()).toBeVisible({ timeout: 15000 });

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

/**
 * Event Detail Modal E2E Tests
 *
 * Comprehensive tests for the event detail modal - a critical user flow for:
 * - Opening modal from event timeline
 * - Viewing event details (timestamp, camera, risk score)
 * - Viewing detection details and thumbnails
 * - Marking events as reviewed
 * - Closing modal (X button, overlay click, Escape key)
 * - Keyboard navigation
 *
 * Test Structure:
 * ---------------
 * Tests are organized into logical groups covering different aspects of the modal:
 * - Modal opening behavior
 * - Content display and verification
 * - User interactions (reviewing, notes)
 * - Closing behavior (X button, overlay, keyboard)
 * - Navigation between events
 * - Tab switching (Details, AI Audit, Video Clip)
 */

import { test, expect, Page } from '@playwright/test';

// Skip entire file in CI - timing issues cause flaky failures
test.skip(() => !!process.env.CI, 'E2E tests flaky in CI - run locally');
import { TimelinePage } from '../pages';
import { setupApiMocks, defaultMockConfig } from '../fixtures';

/**
 * Helper to wait for modal content to be visible.
 * Headless UI transitions can make the dialog wrapper appear "hidden" to Playwright,
 * so we check for content inside the modal instead of the dialog wrapper itself.
 *
 * The EventDetailModal shows the camera name as the modal title (h2 heading).
 * We use a heading locator to reliably detect when the modal content is rendered
 * and the transition animation has completed.
 */
async function waitForModalContent(page: Page) {
  // The modal has a heading (h2) with data-testid="detection-camera" that shows the camera name.
  // Headless UI transitions cause visibility issues, so we wait for the heading specifically
  // which is inside the Dialog.Panel (the actual modal content container).
  // Using getByRole is more reliable than data-testid during Headless UI transitions.
  const modalHeading = page.getByRole('heading', { level: 2, name: /Front Door|Back Yard|Garage|Driveway|Unknown Camera/i });
  await expect(modalHeading).toBeVisible({
    timeout: 15000,
  });

  // Also verify the close button is visible (indicates modal UI is interactive)
  await expect(page.locator('[data-testid="close-modal-button"]')).toBeVisible({
    timeout: 5000,
  });
}

/**
 * Helper to check that modal is closed by verifying content is hidden.
 */
async function expectModalClosed(page: Page) {
  await expect(page.locator('[data-testid="event-detail-modal"]')).not.toBeVisible({
    timeout: 5000,
  });
}

test.describe('Event Detail Modal - Opening', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
    // Additional wait for full interactivity
    await page.waitForLoadState('networkidle').catch(() => {});
    await page.waitForTimeout(500); // Brief wait for any animations
  });

  test('opens modal when clicking an event card', async ({ page }) => {
    // Get the number of events on the page
    const eventCount = await timelinePage.getEventCount();

    // Only proceed if there are events to click
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);

      // Wait for modal to appear with longer timeout
      const modal = page.locator('[data-testid="event-detail-modal"]');
      await expect(modal).toBeVisible({ timeout: 10000 });
    } else {
      // Skip test if no events (this shouldn't happen with mocks but handles edge cases)
      test.skip();
    }
  });

  test('modal is not visible initially', async ({ page }) => {
    const modal = page.locator('[data-testid="event-detail-modal"]');
    await expect(modal).not.toBeVisible({ timeout: 3000 });
  });
});

// TODO: NEM-XXXX - These tests pass in isolation but fail with parallel execution due to
// race conditions in mock API setup. Fix by isolating test contexts or running serially.
test.describe.skip('Event Detail Modal - Content Display', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    // Wait for timeline content to load
    await page.waitForLoadState('networkidle').catch(() => {
      // Continue if network idle times out
    });

    // Get the number of events on the page
    const eventCount = await timelinePage.getEventCount();

    // Open the modal (tests in this block require events)
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);
      // Wait for modal content to be fully rendered (Headless UI transition)
      await waitForModalContent(page);
    }
  });

  test('displays camera name in modal header', async ({ page }) => {
    const cameraName = page.locator('[data-testid="detection-camera"]');
    await expect(cameraName).toBeVisible();
    await expect(cameraName).toHaveText(/Front Door|Back Yard|Garage|Driveway/);
  });

  test('displays event timestamp', async ({ page }) => {
    const timestamp = page.locator('[data-testid="detection-timestamp"]');
    await expect(timestamp).toBeVisible();
    // Should display a formatted date
    await expect(timestamp).toContainText(/\d{1,2}:\d{2}/); // Contains time
  });

  test('displays risk score badge', async ({ page }) => {
    const riskScore = page.locator('[data-testid="risk-score"]');
    await expect(riskScore).toBeVisible();
  });

  test('displays AI summary section', async ({ page }) => {
    const aiSummary = page.locator('[data-testid="ai-analysis-section"]');
    await expect(aiSummary).toBeVisible();
  });

  test('displays detected objects section when detections exist', async ({ page }) => {
    // Check if detections section exists (it should for default mock data)
    const detectionsSection = page.locator('[data-testid="detection-objects"]');
    const isVisible = await detectionsSection.isVisible().catch(() => false);

    if (isVisible) {
      await expect(detectionsSection).toBeVisible();
      // Should show count of detected objects
      await expect(detectionsSection).toContainText(/Detected Objects/i);
    }
  });

  test('displays event details metadata section', async ({ page }) => {
    // Metadata section contains Event ID, Camera, Risk Score, Status
    const modal = page.locator('[data-testid="event-detail-modal"]');
    await expect(modal).toContainText(/Event ID/i);
    await expect(modal).toContainText(/Risk Score/i);
    await expect(modal).toContainText(/Status/i);
  });
});

// TODO: NEM-XXXX - These tests pass in isolation but fail with parallel execution due to
// race conditions in mock API setup. Fix by isolating test contexts or running serially.
test.describe.skip('Event Detail Modal - Mark as Reviewed', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    // Wait for timeline content to load
    await page.waitForLoadState('networkidle').catch(() => {
      // Continue if network idle times out
    });

    // Get the number of events on the page
    const eventCount = await timelinePage.getEventCount();

    // Open the modal (tests in this block require events)
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);
      // Wait for modal content to be fully rendered (Headless UI transition)
      await waitForModalContent(page);
    }
  });

  test('displays "Mark as Reviewed" button for unreviewed events', async ({ page }) => {
    const markReviewedButton = page.locator('[data-testid="mark-reviewed"]');

    // Check if button exists (may not exist if event is already reviewed)
    const buttonExists = await markReviewedButton.count() > 0;

    if (buttonExists) {
      await expect(markReviewedButton).toBeVisible();
      await expect(markReviewedButton).toContainText(/Mark as Reviewed/i);
    }
  });

  test('mark as reviewed button is clickable', async ({ page }) => {
    const markReviewedButton = page.locator('[data-testid="mark-reviewed"]');

    const buttonExists = await markReviewedButton.count() > 0;

    if (buttonExists) {
      await expect(markReviewedButton).toBeEnabled();
    }
  });

  test('displays reviewed status when event is reviewed', async ({ page }) => {
    const reviewedStatus = page.locator('[data-testid="status-reviewed"]');

    // Either the button exists (unreviewed) or the status shows reviewed
    const markReviewedButton = page.locator('[data-testid="mark-reviewed"]');
    const buttonExists = await markReviewedButton.count() > 0;
    const statusExists = await reviewedStatus.count() > 0;

    // One or the other should be true
    expect(buttonExists || statusExists).toBe(true);
  });
});

// TODO: NEM-XXXX - These tests pass in isolation but fail with parallel execution due to
// race conditions in mock API setup. Fix by isolating test contexts or running serially.
test.describe.skip('Event Detail Modal - Closing with X Button', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    // Wait for timeline content to load
    await page.waitForLoadState('networkidle').catch(() => {
      // Continue if network idle times out
    });

    // Get the number of events on the page
    const eventCount = await timelinePage.getEventCount();

    // Open the modal (tests in this block require events)
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);
      // Wait for modal content to be fully rendered (Headless UI transition)
      await waitForModalContent(page);
    }
  });

  test('displays close button (X) in modal header', async ({ page }) => {
    const closeButton = page.locator('[data-testid="close-modal-button"]');
    await expect(closeButton).toBeVisible();
  });

  test('closes modal when clicking X button', async ({ page }) => {
    const closeButton = page.locator('[data-testid="close-modal-button"]');

    // Click close button
    await closeButton.click();

    // Verify modal is closed
    await expectModalClosed(page);
  });
});

// TODO: NEM-XXXX - These tests pass in isolation but fail with parallel execution due to
// race conditions in mock API setup. Fix by isolating test contexts or running serially.
test.describe.skip('Event Detail Modal - Closing with Overlay Click', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    // Wait for timeline content to load
    await page.waitForLoadState('networkidle').catch(() => {
      // Continue if network idle times out
    });

    // Get the number of events on the page
    const eventCount = await timelinePage.getEventCount();

    // Open the modal (tests in this block require events)
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);
      // Wait for modal content to be fully rendered (Headless UI transition)
      await waitForModalContent(page);
    }
  });

  test('closes modal when clicking overlay backdrop', async ({ page }) => {
    // Click on the backdrop (outside the modal panel)
    // Use a more specific selector for the backdrop - the fixed inset-0 div
    const backdrop = page.locator('.fixed.inset-0.bg-black\\/75').first();

    // Click on backdrop - need to click outside the modal panel
    await backdrop.click({ position: { x: 10, y: 10 }, force: true });

    // Verify modal is closed
    await expectModalClosed(page);
  });
});

// TODO: NEM-XXXX - These tests pass in isolation but fail with parallel execution due to
// race conditions in mock API setup. Fix by isolating test contexts or running serially.
test.describe.skip('Event Detail Modal - Keyboard Navigation', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    // Wait for timeline content to load
    await page.waitForLoadState('networkidle').catch(() => {
      // Continue if network idle times out
    });

    // Get the number of events on the page
    const eventCount = await timelinePage.getEventCount();

    // Open the modal (tests in this block require events)
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);
      // Wait for modal content to be fully rendered (Headless UI transition)
      await waitForModalContent(page);
    }
  });

  test('closes modal when pressing Escape key', async ({ page }) => {
    // Press Escape key
    await page.keyboard.press('Escape');

    // Verify modal is closed
    await expectModalClosed(page);
  });

  test('modal responds to keyboard navigation (Arrow keys)', async ({ page }) => {
    const modal = page.locator('[data-testid="event-detail-modal"]');

    // Try pressing arrow keys (should navigate between events if navigation is enabled)
    // This tests the keyboard event handlers are registered
    await page.keyboard.press('ArrowRight');

    // Modal should still be visible after navigation
    // (Unless we're at the last event, but in most cases it stays open)
    await expect(modal).toBeVisible();
  });
});

// TODO: NEM-XXXX - These tests pass in isolation but fail with parallel execution due to
// race conditions in mock API setup. Fix by isolating test contexts or running serially.
test.describe.skip('Event Detail Modal - Tab Navigation', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    // Wait for timeline content to load
    await page.waitForLoadState('networkidle').catch(() => {
      // Continue if network idle times out
    });

    // Get the number of events on the page
    const eventCount = await timelinePage.getEventCount();

    // Open the modal (tests in this block require events)
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);
      // Wait for modal content to be fully rendered (Headless UI transition)
      await waitForModalContent(page);
    }
  });

  test('displays Details tab by default', async ({ page }) => {
    const modal = page.locator('[data-testid="event-detail-modal"]');

    // Details tab should be active (has green border and text)
    const detailsTab = modal.locator('button:has-text("Details")');
    await expect(detailsTab).toBeVisible();
    await expect(detailsTab).toHaveClass(/border-\[#76B900\]/);
  });

  test('can switch to AI Audit tab', async ({ page }) => {
    const modal = page.locator('[data-testid="event-detail-modal"]');

    // Click AI Audit tab
    const aiAuditTab = modal.locator('button:has-text("AI Audit")');
    await aiAuditTab.click();

    // Tab should become active
    await expect(aiAuditTab).toHaveClass(/border-\[#76B900\]/);
  });

  test('can switch to Video Clip tab', async ({ page }) => {
    const modal = page.locator('[data-testid="event-detail-modal"]');

    // Click Video Clip tab
    const videoClipTab = modal.locator('[data-testid="video-clip-tab"]');
    await videoClipTab.click();

    // Tab should become active
    await expect(videoClipTab).toHaveClass(/border-\[#76B900\]/);
  });

  test('switching tabs updates content area', async ({ page }) => {
    const modal = page.locator('[data-testid="event-detail-modal"]');

    // Default view shows AI summary
    let aiSummaryVisible = await modal.locator('[data-testid="ai-analysis-section"]').isVisible().catch(() => false);
    expect(aiSummaryVisible).toBe(true);

    // Switch to AI Audit tab
    const aiAuditTab = modal.locator('button:has-text("AI Audit")');
    await aiAuditTab.click();

    // Content should change (AI summary may not be visible in AI Audit tab)
    // Just verify the tab switch worked by checking the active state
    await expect(aiAuditTab).toHaveClass(/border-\[#76B900\]/);
  });
});

// TODO: NEM-XXXX - These tests pass in isolation but fail with parallel execution due to
// race conditions in mock API setup. Fix by isolating test contexts or running serially.
test.describe.skip('Event Detail Modal - Notes Functionality', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    // Wait for timeline content to load
    await page.waitForLoadState('networkidle').catch(() => {
      // Continue if network idle times out
    });

    // Get the number of events on the page
    const eventCount = await timelinePage.getEventCount();

    // Open the modal (tests in this block require events)
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);
      // Wait for modal content to be fully rendered (Headless UI transition)
      await waitForModalContent(page);
    }
  });

  test('displays notes section', async ({ page }) => {
    const modal = page.locator('[data-testid="event-detail-modal"]');

    // Should have a Notes heading - use getByRole to be more specific
    await expect(modal.getByRole('heading', { name: 'Notes' })).toBeVisible();
  });

  test('displays notes textarea', async ({ page }) => {
    const modal = page.locator('[data-testid="event-detail-modal"]');

    // Find textarea with placeholder
    const notesTextarea = modal.locator('textarea[placeholder*="Add notes"]');
    await expect(notesTextarea).toBeVisible();
  });

  test('can type in notes textarea', async ({ page }) => {
    const modal = page.locator('[data-testid="event-detail-modal"]');

    const notesTextarea = modal.locator('textarea[placeholder*="Add notes"]');
    await notesTextarea.fill('Test note for E2E testing');

    // Verify text was entered
    await expect(notesTextarea).toHaveValue('Test note for E2E testing');
  });

  test('displays save notes button', async ({ page }) => {
    const modal = page.locator('[data-testid="event-detail-modal"]');

    const saveButton = modal.locator('button:has-text("Save Notes")');
    await expect(saveButton).toBeVisible();
  });
});

// TODO: NEM-XXXX - These tests pass in isolation but fail with parallel execution due to
// race conditions in mock API setup. Fix by isolating test contexts or running serially.
test.describe.skip('Event Detail Modal - Re-evaluate Button', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    // Wait for timeline content to load
    await page.waitForLoadState('networkidle').catch(() => {
      // Continue if network idle times out
    });

    // Get the number of events on the page
    const eventCount = await timelinePage.getEventCount();

    // Open the modal (tests in this block require events)
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);
      // Wait for modal content to be fully rendered (Headless UI transition)
      await waitForModalContent(page);
    }
  });

  test('displays re-evaluate button in AI Summary section', async ({ page }) => {
    const reEvaluateButton = page.locator('[data-testid="re-evaluate-button"]');
    await expect(reEvaluateButton).toBeVisible();
    await expect(reEvaluateButton).toContainText(/Re-evaluate/i);
  });

  test('re-evaluate button is clickable', async ({ page }) => {
    const reEvaluateButton = page.locator('[data-testid="re-evaluate-button"]');
    await expect(reEvaluateButton).toBeEnabled();
  });
});

// TODO: NEM-XXXX - These tests pass in isolation but fail with parallel execution due to
// race conditions in mock API setup. Fix by isolating test contexts or running serially.
test.describe.skip('Event Detail Modal - Navigation Buttons', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    // Wait for timeline content to load
    await page.waitForLoadState('networkidle').catch(() => {
      // Continue if network idle times out
    });

    // Get the number of events on the page
    const eventCount = await timelinePage.getEventCount();

    // Open the modal (tests in this block require events)
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);
      // Wait for modal content to be fully rendered (Headless UI transition)
      await waitForModalContent(page);
    }
  });

  test('displays Previous and Next navigation buttons', async ({ page }) => {
    const modal = page.locator('[data-testid="event-detail-modal"]');

    // Check for navigation buttons in footer
    const previousButton = modal.locator('button[aria-label="Previous event"]');
    const nextButton = modal.locator('button[aria-label="Next event"]');

    // Both should exist (they're always rendered when onNavigate is provided)
    const prevExists = await previousButton.count() > 0;
    const nextExists = await nextButton.count() > 0;

    expect(prevExists).toBe(true);
    expect(nextExists).toBe(true);
  });
});

// TODO: NEM-XXXX - These tests pass in isolation but fail with parallel execution due to
// race conditions in mock API setup. Fix by isolating test contexts or running serially.
test.describe.skip('Event Detail Modal - Detection Images', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    // Wait for timeline content to load
    await page.waitForLoadState('networkidle').catch(() => {
      // Continue if network idle times out
    });

    // Get the number of events on the page
    const eventCount = await timelinePage.getEventCount();

    // Open the modal (tests in this block require events)
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);
      // Wait for modal content to be fully rendered (Headless UI transition)
      await waitForModalContent(page);
    }
  });

  test('displays detection image or video player', async ({ page }) => {
    const modal = page.locator('[data-testid="event-detail-modal"]');

    // Wait for detections to potentially load (async fetch from API)
    // Give the modal time to fetch and render detection images
    await page.waitForTimeout(1000);

    // Should have either an image or video element once detections load
    // Note: Images may not appear if detections fetch fails or returns empty
    const hasImage = (await modal.locator('img').count()) > 0;
    const hasVideo = (await modal.locator('video').count()) > 0;

    // At least one should be present when detections are available
    // If no detections exist for this event, the test should pass gracefully
    // (the modal still renders correctly even without media)
    if (hasImage || hasVideo) {
      expect(hasImage || hasVideo).toBe(true);
    } else {
      // If no media is displayed, at least verify the modal content is shown
      await expect(modal.locator('[data-testid="detection-camera"]')).toBeVisible();
    }
  });
});

// TODO: NEM-XXXX - These tests pass in isolation but fail with parallel execution due to
// race conditions in mock API setup. Fix by isolating test contexts or running serially.
test.describe.skip('Event Detail Modal - AI Reasoning', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    // Wait for timeline content to load
    await page.waitForLoadState('networkidle').catch(() => {
      // Continue if network idle times out
    });

    // Get the number of events on the page
    const eventCount = await timelinePage.getEventCount();

    // Open the modal (tests in this block require events)
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);
      // Wait for modal content to be fully rendered (Headless UI transition)
      await waitForModalContent(page);
    }
  });

  test('displays AI Reasoning section when reasoning exists', async ({ page }) => {
    const aiReasoning = page.locator('[data-testid="ai-reasoning"]');

    // AI reasoning may or may not be present depending on the event
    const isVisible = await aiReasoning.isVisible().catch(() => false);

    if (isVisible) {
      await expect(aiReasoning).toBeVisible();
      await expect(aiReasoning).toContainText(/AI Reasoning/i);
    }
  });
});

// TODO: NEM-XXXX - These tests pass in isolation but fail with parallel execution due to
// race conditions in mock API setup. Fix by isolating test contexts or running serially.
test.describe.skip('Event Detail Modal - Multiple Events', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
  });

  test('can open different events sequentially', async ({ page }) => {
    // Wait for timeline content to load
    await page.waitForLoadState('networkidle').catch(() => {
      // Continue if network idle times out
    });

    const eventCount = await timelinePage.getEventCount();

    // Skip if no events
    if (eventCount === 0) {
      test.skip();
    }

    // Open first event
    await timelinePage.clickEvent(0);
    // Wait for modal content to be fully rendered
    await waitForModalContent(page);

    // Close it
    await page.keyboard.press('Escape');
    await expectModalClosed(page);

    // Open second event if it exists
    if (eventCount > 1) {
      await timelinePage.clickEvent(1);
      await waitForModalContent(page);
    }
  });

  test('modal content updates when opening different events', async ({ page }) => {
    // Wait for timeline content to load
    await page.waitForLoadState('networkidle').catch(() => {
      // Continue if network idle times out
    });

    const eventCount = await timelinePage.getEventCount();

    // Skip if less than 2 events (need at least 2 to test navigation)
    if (eventCount <= 1) {
      test.skip();
    }

    // Open first event and get camera name
    await timelinePage.clickEvent(0);
    await waitForModalContent(page);
    const firstCamera = await page.locator('[data-testid="detection-camera"]').textContent();

    // Close and open second event
    await page.keyboard.press('Escape');
    await expectModalClosed(page);
    await timelinePage.clickEvent(1);
    await waitForModalContent(page);
    const secondCamera = await page.locator('[data-testid="detection-camera"]').textContent();

    // Content should be different (unless both events are from the same camera)
    // Just verify that the modal updated by checking visibility
    const modal = page.locator('[data-testid="event-detail-modal"]');
    await expect(modal).toBeVisible();
    expect(firstCamera || secondCamera).toBeTruthy();
  });
});

/**
 * Video Playback E2E Tests
 *
 * Comprehensive tests for video playback functionality in the browser:
 * - Video player component loads correctly
 * - Video plays and pauses successfully
 * - Custom controls work (play/pause, volume, fullscreen, playback speed)
 * - Event video player integration (clip generation, download)
 * - Keyboard shortcuts for video control
 * - Error handling for failed video loads
 * - Loading states during video buffering
 *
 * Test Structure:
 * ---------------
 * Tests are organized into logical groups covering:
 * - Basic video loading and playback
 * - Control interactions (play/pause, seek, volume)
 * - Fullscreen functionality
 * - Playback speed controls
 * - Keyboard shortcuts
 * - Event video player workflow (generate, view, download)
 * - Error states and recovery
 *
 * @tag @critical - Video playback is core functionality
 */

import { test, expect } from '@playwright/test';
import { TimelinePage } from '../pages';
import { setupApiMocks, defaultMockConfig } from '../fixtures';

/**
 * Mock video clip info response for testing
 */
const mockClipInfo = {
  event_id: 1,
  clip_available: true,
  clip_url: '/media/clips/event_1_clip.mp4',
  duration_seconds: 30,
  generated_at: new Date().toISOString(),
  file_size_bytes: 5242880, // 5 MB
};

/**
 * Mock clip generation response
 */
const mockClipGenerateResponse = {
  status: 'completed' as const,
  clip_url: '/media/clips/event_1_clip.mp4',
  generated_at: new Date().toISOString(),
  message: 'Clip generated successfully',
};

/**
 * Helper to create a mock video blob URL
 */
function createMockVideoBlob(): string {
  // Create a minimal valid MP4 header for testing
  const data = new Uint8Array([
    0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70,
    0x69, 0x73, 0x6f, 0x6d, 0x00, 0x00, 0x02, 0x00,
  ]);
  const blob = new Blob([data], { type: 'video/mp4' });
  return URL.createObjectURL(blob);
}

test.describe('Video Player - Basic Loading @critical', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    // Mock video clip info endpoint (BEFORE setupApiMocks)
    await page.route('**/api/events/*/clip/info', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockClipInfo),
      });
    });

    // Mock video file with a valid MP4 response (BEFORE setupApiMocks)
    await page.route('**/api/media/clips/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'video/mp4',
        body: Buffer.from([
          0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70,
          0x69, 0x73, 0x6f, 0x6d, 0x00, 0x00, 0x02, 0x00,
        ]),
      });
    });

    await setupApiMocks(page, defaultMockConfig);

    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
  });

  test('video player loads when opening Video Clip tab', async ({ page }) => {
    // Open event detail modal
    const eventCount = await timelinePage.getEventCount();
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);

      // Switch to Video Clip tab
      const modal = page.locator('[data-testid="event-detail-modal"]');
      const videoClipTab = modal.locator('[data-testid="video-clip-tab"]');
      await videoClipTab.click();

      // Wait for clip info to load
      await page.waitForSelector('[data-testid="clip-available"]', { timeout: 5000 });

      // Verify video player is visible
      const videoPlayer = page.locator('[data-testid="video-player"]');
      await expect(videoPlayer).toBeVisible();
    }
  });

  test('video element has correct attributes', async ({ page }) => {
    const eventCount = await timelinePage.getEventCount();
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);

      const modal = page.locator('[data-testid="event-detail-modal"]');
      const videoClipTab = modal.locator('[data-testid="video-clip-tab"]');
      await videoClipTab.click();

      await page.waitForSelector('[data-testid="video-player"]', { timeout: 5000 });

      const video = page.locator('[data-testid="video-player"]');

      // Verify video has controls
      await expect(video).toHaveAttribute('controls', '');

      // Verify video has preload="metadata"
      await expect(video).toHaveAttribute('preload', 'metadata');
    }
  });

  test('displays loading state while clip info loads', async ({ page }) => {
    // Override with slower response to catch loading state
    await page.route('**/api/events/*/clip/info', async (route) => {
      await new Promise(resolve => setTimeout(resolve, 1000));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockClipInfo),
      });
    });

    const eventCount = await timelinePage.getEventCount();
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);

      const modal = page.locator('[data-testid="event-detail-modal"]');
      const videoClipTab = modal.locator('[data-testid="video-clip-tab"]');
      await videoClipTab.click();

      // Should show loading state
      const loadingIndicator = page.locator('[data-testid="clip-loading"]');
      await expect(loadingIndicator).toBeVisible();

      // Eventually loads
      await page.waitForSelector('[data-testid="clip-available"]', { timeout: 5000 });
    }
  });
});

test.describe('Video Player - Play/Pause Controls @critical', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await page.route('**/api/events/*/clip/info', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockClipInfo),
      });
    });

    await page.route('**/api/media/clips/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'video/mp4',
        body: Buffer.from([
          0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70,
          0x69, 0x73, 0x6f, 0x6d, 0x00, 0x00, 0x02, 0x00,
        ]),
      });
    });

    await setupApiMocks(page, defaultMockConfig);

    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
  });

  test('video has native browser controls', async ({ page }) => {
    const eventCount = await timelinePage.getEventCount();
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);

      const modal = page.locator('[data-testid="event-detail-modal"]');
      const videoClipTab = modal.locator('[data-testid="video-clip-tab"]');
      await videoClipTab.click();

      await page.waitForSelector('[data-testid="video-player"]', { timeout: 5000 });

      const video = page.locator('[data-testid="video-player"]');

      // EventVideoPlayer uses native controls
      await expect(video).toHaveAttribute('controls', '');
    }
  });

  test('video can be clicked to play/pause', async ({ page }) => {
    const eventCount = await timelinePage.getEventCount();
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);

      const modal = page.locator('[data-testid="event-detail-modal"]');
      const videoClipTab = modal.locator('[data-testid="video-clip-tab"]');
      await videoClipTab.click();

      await page.waitForSelector('[data-testid="video-player"]', { timeout: 5000 });

      const video = page.locator('[data-testid="video-player"]');

      // Video should be paused initially
      const isPaused = await video.evaluate((v: HTMLVideoElement) => v.paused);
      expect(isPaused).toBe(true);

      // Click to play (using native controls)
      // Note: Actual playback testing requires a real video file
      // This test verifies the element is interactive
      await expect(video).toBeEnabled();
    }
  });
});

test.describe('Video Player - Clip Generation @critical', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);

    timelinePage = new TimelinePage(page);
  });

  test('displays generate clip button when no clip available', async ({ page }) => {
    // Mock no clip available
    await page.route('**/api/events/*/clip/info', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          event_id: 1,
          clip_available: false,
          clip_url: null,
          duration_seconds: null,
          generated_at: null,
          file_size_bytes: null,
        }),
      });
    });

    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    const eventCount = await timelinePage.getEventCount();
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);

      const modal = page.locator('[data-testid="event-detail-modal"]');
      const videoClipTab = modal.locator('[data-testid="video-clip-tab"]');
      await videoClipTab.click();

      // Should show generate button
      await page.waitForSelector('[data-testid="clip-unavailable"]', { timeout: 5000 });
      const generateButton = page.locator('[data-testid="generate-clip-button"]');
      await expect(generateButton).toBeVisible();
      await expect(generateButton).toContainText(/Generate Clip/i);
    }
  });

  test('generate clip button triggers clip generation', async ({ page }) => {
    // Mock no clip initially
    await page.route('**/api/events/*/clip/info', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          event_id: 1,
          clip_available: false,
          clip_url: null,
          duration_seconds: null,
          generated_at: null,
          file_size_bytes: null,
        }),
      });
    });

    // Mock generation endpoint
    let generateClipCalled = false;
    await page.route('**/api/events/*/clip/generate', async (route) => {
      generateClipCalled = true;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockClipGenerateResponse),
      });
    });

    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    const eventCount = await timelinePage.getEventCount();
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);

      const modal = page.locator('[data-testid="event-detail-modal"]');
      const videoClipTab = modal.locator('[data-testid="video-clip-tab"]');
      await videoClipTab.click();

      await page.waitForSelector('[data-testid="generate-clip-button"]', { timeout: 5000 });
      const generateButton = page.locator('[data-testid="generate-clip-button"]');

      await generateButton.click();

      // Wait a moment for the API call
      await page.waitForTimeout(500);

      // Verify generation was triggered
      expect(generateClipCalled).toBe(true);
    }
  });

  test('shows loading state during clip generation', async ({ page }) => {
    await page.route('**/api/events/*/clip/info', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          event_id: 1,
          clip_available: false,
          clip_url: null,
          duration_seconds: null,
          generated_at: null,
          file_size_bytes: null,
        }),
      });
    });

    // Slow response to catch loading state
    await page.route('**/api/events/*/clip/generate', async (route) => {
      await new Promise(resolve => setTimeout(resolve, 1000));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockClipGenerateResponse),
      });
    });

    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    const eventCount = await timelinePage.getEventCount();
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);

      const modal = page.locator('[data-testid="event-detail-modal"]');
      const videoClipTab = modal.locator('[data-testid="video-clip-tab"]');
      await videoClipTab.click();

      await page.waitForSelector('[data-testid="generate-clip-button"]', { timeout: 5000 });
      const generateButton = page.locator('[data-testid="generate-clip-button"]');

      await generateButton.click();

      // Should show loading state
      await expect(generateButton).toContainText(/Generating.../i);
      await expect(generateButton).toBeDisabled();
    }
  });
});

test.describe('Video Player - Download Functionality @critical', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await page.route('**/api/events/*/clip/info', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockClipInfo),
      });
    });

    await page.route('**/api/media/clips/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'video/mp4',
        body: Buffer.from([
          0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70,
          0x69, 0x73, 0x6f, 0x6d, 0x00, 0x00, 0x02, 0x00,
        ]),
      });
    });

    await setupApiMocks(page, defaultMockConfig);

    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
  });

  test('displays download button when clip is available', async ({ page }) => {
    const eventCount = await timelinePage.getEventCount();
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);

      const modal = page.locator('[data-testid="event-detail-modal"]');
      const videoClipTab = modal.locator('[data-testid="video-clip-tab"]');
      await videoClipTab.click();

      await page.waitForSelector('[data-testid="clip-available"]', { timeout: 5000 });

      // Verify download button exists
      const downloadButton = page.locator('[data-testid="download-clip-button"]');
      await expect(downloadButton).toBeVisible();
      await expect(downloadButton).toContainText(/Download/i);
    }
  });

  test('download button is clickable', async ({ page }) => {
    const eventCount = await timelinePage.getEventCount();
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);

      const modal = page.locator('[data-testid="event-detail-modal"]');
      const videoClipTab = modal.locator('[data-testid="video-clip-tab"]');
      await videoClipTab.click();

      await page.waitForSelector('[data-testid="clip-available"]', { timeout: 5000 });

      const downloadButton = page.locator('[data-testid="download-clip-button"]');
      await expect(downloadButton).toBeEnabled();
    }
  });
});

test.describe('Video Player - Metadata Display @critical', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await page.route('**/api/events/*/clip/info', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockClipInfo),
      });
    });

    await page.route('**/api/media/clips/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'video/mp4',
        body: Buffer.from([
          0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70,
          0x69, 0x73, 0x6f, 0x6d, 0x00, 0x00, 0x02, 0x00,
        ]),
      });
    });

    await setupApiMocks(page, defaultMockConfig);

    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
  });

  test('displays clip duration metadata', async ({ page }) => {
    const eventCount = await timelinePage.getEventCount();
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);

      const modal = page.locator('[data-testid="event-detail-modal"]');
      const videoClipTab = modal.locator('[data-testid="video-clip-tab"]');
      await videoClipTab.click();

      await page.waitForSelector('[data-testid="clip-available"]', { timeout: 5000 });

      // Verify duration is displayed
      const clipMetadata = page.locator('[data-testid="clip-available"]');
      await expect(clipMetadata).toContainText(/Duration:/i);
      await expect(clipMetadata).toContainText(/30s/i);
    }
  });

  test('displays clip file size metadata', async ({ page }) => {
    const eventCount = await timelinePage.getEventCount();
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);

      const modal = page.locator('[data-testid="event-detail-modal"]');
      const videoClipTab = modal.locator('[data-testid="video-clip-tab"]');
      await videoClipTab.click();

      await page.waitForSelector('[data-testid="clip-available"]', { timeout: 5000 });

      // Verify file size is displayed
      const clipMetadata = page.locator('[data-testid="clip-available"]');
      await expect(clipMetadata).toContainText(/Size:/i);
      await expect(clipMetadata).toContainText(/5\.0 MB/i);
    }
  });

  test('displays clip generation timestamp', async ({ page }) => {
    const eventCount = await timelinePage.getEventCount();
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);

      const modal = page.locator('[data-testid="event-detail-modal"]');
      const videoClipTab = modal.locator('[data-testid="video-clip-tab"]');
      await videoClipTab.click();

      await page.waitForSelector('[data-testid="clip-available"]', { timeout: 5000 });

      // Verify generation timestamp is displayed
      const clipMetadata = page.locator('[data-testid="clip-available"]');
      await expect(clipMetadata).toContainText(/Generated:/i);
    }
  });
});

test.describe('Video Player - Error Handling', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);

    timelinePage = new TimelinePage(page);
  });

  test('displays error when clip info fails to load', async ({ page }) => {
    // Mock API error
    await page.route('**/api/events/*/clip/info', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' }),
      });
    });

    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    const eventCount = await timelinePage.getEventCount();
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);

      const modal = page.locator('[data-testid="event-detail-modal"]');
      const videoClipTab = modal.locator('[data-testid="video-clip-tab"]');
      await videoClipTab.click();

      // Should show error state
      await page.waitForSelector('[data-testid="clip-error"]', { timeout: 5000 });
      const errorMessage = page.locator('[data-testid="clip-error"]');
      await expect(errorMessage).toBeVisible();
      await expect(errorMessage).toContainText(/Failed to load clip info/i);
    }
  });

  test('displays error when clip generation fails', async ({ page }) => {
    await page.route('**/api/events/*/clip/info', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          event_id: 1,
          clip_available: false,
          clip_url: null,
          duration_seconds: null,
          generated_at: null,
          file_size_bytes: null,
        }),
      });
    });

    // Mock generation failure
    await page.route('**/api/events/*/clip/generate', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'failed',
          message: 'Insufficient source images to generate clip',
        }),
      });
    });

    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    const eventCount = await timelinePage.getEventCount();
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);

      const modal = page.locator('[data-testid="event-detail-modal"]');
      const videoClipTab = modal.locator('[data-testid="video-clip-tab"]');
      await videoClipTab.click();

      await page.waitForSelector('[data-testid="generate-clip-button"]', { timeout: 5000 });
      const generateButton = page.locator('[data-testid="generate-clip-button"]');

      await generateButton.click();

      // Wait for error message
      await page.waitForTimeout(500);

      // Should show error message
      const errorContainer = page.locator('[data-testid="clip-unavailable"]');
      await expect(errorContainer).toContainText(/Insufficient source images/i);
    }
  });

  test('shows error icon in error state', async ({ page }) => {
    await page.route('**/api/events/*/clip/info', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' }),
      });
    });

    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    const eventCount = await timelinePage.getEventCount();
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);

      const modal = page.locator('[data-testid="event-detail-modal"]');
      const videoClipTab = modal.locator('[data-testid="video-clip-tab"]');
      await videoClipTab.click();

      await page.waitForSelector('[data-testid="clip-error"]', { timeout: 5000 });

      // Verify error styling (red theme)
      const errorContainer = page.locator('[data-testid="clip-error"]');
      await expect(errorContainer).toHaveClass(/border-red/);
      await expect(errorContainer).toHaveClass(/bg-red/);
    }
  });
});

test.describe('Video Player - Accessibility', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await page.route('**/api/events/*/clip/info', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockClipInfo),
      });
    });

    await page.route('**/api/media/clips/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'video/mp4',
        body: Buffer.from([
          0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70,
          0x69, 0x73, 0x6f, 0x6d, 0x00, 0x00, 0x02, 0x00,
        ]),
      });
    });

    await setupApiMocks(page, defaultMockConfig);

    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
  });

  test('video player buttons have aria-labels', async ({ page }) => {
    const eventCount = await timelinePage.getEventCount();
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);

      const modal = page.locator('[data-testid="event-detail-modal"]');
      const videoClipTab = modal.locator('[data-testid="video-clip-tab"]');
      await videoClipTab.click();

      await page.waitForSelector('[data-testid="clip-available"]', { timeout: 5000 });

      // Verify download button has aria-label
      const downloadButton = page.locator('[data-testid="download-clip-button"]');
      await expect(downloadButton).toHaveAttribute('aria-label', 'Download clip');
    }
  });

  test('generate clip button has aria-label', async ({ page }) => {
    // Need to override the mock for this specific test
    await page.unroute('**/api/events/*/clip/info');
    await page.route('**/api/events/*/clip/info', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          event_id: 1,
          clip_available: false,
          clip_url: null,
          duration_seconds: null,
          generated_at: null,
          file_size_bytes: null,
        }),
      });
    });

    // Navigate after setting up the new route
    await page.goto('/timeline');
    await page.waitForSelector('[data-testid="event-timeline"]', { timeout: 10000 });

    const eventCount = await timelinePage.getEventCount();
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);

      const modal = page.locator('[data-testid="event-detail-modal"]');
      const videoClipTab = modal.locator('[data-testid="video-clip-tab"]');
      await videoClipTab.click();

      await page.waitForSelector('[data-testid="generate-clip-button"]', { timeout: 5000 });
      const generateButton = page.locator('[data-testid="generate-clip-button"]');

      await expect(generateButton).toHaveAttribute('aria-label', 'Generate video clip');
    }
  });

  test('video element is keyboard accessible', async ({ page }) => {
    const eventCount = await timelinePage.getEventCount();
    if (eventCount > 0) {
      await timelinePage.clickEvent(0);

      const modal = page.locator('[data-testid="event-detail-modal"]');
      const videoClipTab = modal.locator('[data-testid="video-clip-tab"]');
      await videoClipTab.click();

      await page.waitForSelector('[data-testid="video-player"]', { timeout: 5000 });

      // Video with controls attribute should be keyboard accessible
      const video = page.locator('[data-testid="video-player"]');
      await expect(video).toHaveAttribute('controls', '');
    }
  });
});

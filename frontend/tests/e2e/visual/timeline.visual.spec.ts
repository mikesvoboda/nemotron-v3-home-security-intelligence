/**
 * Visual Regression Tests - Timeline Page
 *
 * These tests capture screenshots and compare against baseline images
 * to detect unintended visual changes in the Event Timeline page.
 *
 * Running visual tests:
 *   npx playwright test --project=visual-chromium
 *
 * Updating baselines:
 *   npx playwright test --project=visual-chromium --update-snapshots
 */

import { test, expect } from '@playwright/test';
import { TimelinePage } from '../pages';
import { setupApiMocks, defaultMockConfig, emptyMockConfig } from '../fixtures';

test.describe('Timeline Visual Regression', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('timeline full page matches snapshot', async ({ page }) => {
    const timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    // Wait for content to render
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('timeline-full-page.png', {
      fullPage: true,
      mask: [
        page.locator('[data-testid="timestamp"]'),
        page.locator('time'),
        page.locator('[data-testid="relative-time"]'),
      ],
    });
  });

  test('timeline event cards match snapshot', async ({ page }) => {
    const timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    await page.waitForLoadState('networkidle');

    // Get first event card for component screenshot
    const eventCard = timelinePage.eventCards.first();
    await expect(eventCard).toHaveScreenshot('timeline-event-card.png', {
      mask: [
        page.locator('time'),
        page.locator('[data-testid="event-time"]'),
      ],
    });
  });

  test('timeline filters panel matches snapshot', async ({ page }) => {
    const timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    // Show filters
    await timelinePage.showFilters();
    await page.waitForTimeout(300);

    await expect(page).toHaveScreenshot('timeline-filters-expanded.png', {
      fullPage: true,
      mask: [page.locator('time')],
    });
  });

  test('timeline search results match snapshot', async ({ page }) => {
    const timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    // Enter search query (mocked responses)
    await timelinePage.fullTextSearchInput.fill('person detected');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('timeline-search-results.png', {
      fullPage: true,
      mask: [page.locator('time')],
    });
  });
});

test.describe('Timeline Visual States', () => {
  test('timeline empty state matches snapshot', async ({ page }) => {
    await setupApiMocks(page, emptyMockConfig);
    const timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('timeline-empty-state.png', {
      fullPage: true,
    });
  });

  test('timeline pagination matches snapshot', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    await page.waitForLoadState('networkidle');

    // Focus on pagination area
    const paginationArea = page.locator('[class*="pagination"], [class*="Pagination"]').first();
    if (await paginationArea.isVisible()) {
      await expect(paginationArea).toHaveScreenshot('timeline-pagination.png');
    }
  });
});

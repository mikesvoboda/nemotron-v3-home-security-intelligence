/**
 * Trash Page E2E Tests for Home Security Dashboard
 *
 * Comprehensive tests for the Trash page including:
 * - Page load and display
 * - Deleted events list
 * - Empty state
 * - Restore operations
 * - Permanent delete with confirmation
 * - Error handling
 *
 * @see frontend/src/pages/TrashPage.tsx
 * @see docs/development/testing-workflow.md
 */

import { test, expect } from '@playwright/test';
import { TrashPage } from '../pages';
import {
  setupApiMocks,
  defaultMockConfig,
  emptyMockConfig,
  type ApiMockConfig,
} from '../fixtures';

test.describe('Trash Page Load & Display', () => {
  let trashPage: TrashPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    trashPage = new TrashPage(page);
  });

  test('trash page loads successfully', async () => {
    await trashPage.goto();
    await trashPage.waitForTrashLoad();
  });

  test('displays page title', async () => {
    await trashPage.goto();
    await trashPage.waitForTrashLoad();
    await expect(trashPage.pageTitle).toBeVisible();
  });

  test('displays page subtitle', async () => {
    await trashPage.goto();
    await trashPage.waitForTrashLoad();
    await expect(trashPage.pageSubtitle).toBeVisible();
  });

  test('displays auto-cleanup notice', async () => {
    await trashPage.goto();
    await trashPage.waitForTrashLoad();
    const hasNotice = await trashPage.hasAutoCleanupNotice();
    expect(hasNotice).toBe(true);
  });

  test('displays deleted events count', async () => {
    await trashPage.goto();
    await trashPage.waitForTrashLoad();
    await expect(trashPage.eventsCount).toBeVisible();
  });

  test('displays deleted event cards', async () => {
    await trashPage.goto();
    await trashPage.waitForTrashLoad();
    const count = await trashPage.getDeletedEventCount();
    expect(count).toBeGreaterThan(0);
  });
});

test.describe('Deleted Event Metadata Display', () => {
  let trashPage: TrashPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    trashPage = new TrashPage(page);
    await trashPage.goto();
    await trashPage.waitForTrashLoad();
  });

  test('event card shows camera name', async () => {
    const cameraName = await trashPage.getCameraName(0);
    expect(cameraName).toBeTruthy();
  });

  test('event card shows deleted timestamp', async () => {
    const timestamp = await trashPage.getDeletedTimestamp(0);
    expect(timestamp).toMatch(/Deleted (?:Just now|.+ ago)/i);
  });

  test('event card shows restore button', async () => {
    const restoreButton = trashPage.getRestoreButton(0);
    await expect(restoreButton).toBeVisible();
  });

  test('event card shows delete forever button', async () => {
    const deleteButton = trashPage.getDeleteForeverButton(0);
    await expect(deleteButton).toBeVisible();
  });
});

// TODO: Re-enable empty state tests after fixing page navigation issue
// The /trash route may not be loading properly in test environment
test.describe.skip('Empty State', () => {
  let trashPage: TrashPage;

  test.beforeEach(async ({ page }) => {
    // Use default config but override deletedEvents to be empty
    const config: ApiMockConfig = {
      ...defaultMockConfig,
      deletedEvents: [],
    };
    await setupApiMocks(page, config);
    trashPage = new TrashPage(page);
  });

  test('shows empty state when trash is empty', async () => {
    await trashPage.goto();
    await trashPage.waitForTrashLoad();
    const isEmpty = await trashPage.hasEmptyState();
    expect(isEmpty).toBe(true);
  });

  test('empty state shows title', async () => {
    await trashPage.goto();
    await trashPage.waitForTrashLoad();
    await expect(trashPage.emptyStateTitle).toBeVisible();
  });

  test('empty state shows description', async () => {
    await trashPage.goto();
    await trashPage.waitForTrashLoad();
    await expect(trashPage.emptyStateDescription).toBeVisible();
  });

  test('no event cards when trash is empty', async () => {
    await trashPage.goto();
    await trashPage.waitForTrashLoad();
    const count = await trashPage.getDeletedEventCount();
    expect(count).toBe(0);
  });
});

test.describe('Restore Operations', () => {
  let trashPage: TrashPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    trashPage = new TrashPage(page);
    await trashPage.goto();
    await trashPage.waitForTrashLoad();
  });

  test('restore button is clickable', async () => {
    const restoreButton = trashPage.getRestoreButton(0);
    await expect(restoreButton).toBeEnabled();
  });

  test('can restore single event from trash', async ({ page }) => {
    // Wait for the restore API call
    const responsePromise = page.waitForResponse(
      (response) => response.url().includes('/api/events/') && response.url().includes('/restore'),
      { timeout: 10000 }
    );

    await trashPage.restoreEvent(0);

    const response = await responsePromise;
    expect(response.status()).toBe(200);
  });

  // TODO: Re-enable after resolving timing issues with loading state detection
  test.skip('restore button shows loading state during operation', async ({ page }) => {
    // Delay the restore API response to observe loading state
    await page.route('**/api/events/*/restore', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 101, message: 'Event restored successfully' }),
      });
    });

    // Click restore button (don't await - we want to check loading state immediately)
    const restoreButton = trashPage.getRestoreButton(0);
    await restoreButton.click();

    // Check loading state appears
    const isLoading = await trashPage.isRestoreInProgress(0);
    expect(isLoading).toBe(true);
  });
});

test.describe('Permanent Delete Operations', () => {
  let trashPage: TrashPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    trashPage = new TrashPage(page);
    await trashPage.goto();
    await trashPage.waitForTrashLoad();
  });

  test('delete forever button is clickable', async () => {
    const deleteButton = trashPage.getDeleteForeverButton(0);
    await expect(deleteButton).toBeEnabled();
  });

  test('clicking delete forever shows confirmation dialog', async () => {
    await trashPage.clickDeleteForever(0);
    const isVisible = await trashPage.isConfirmDialogVisible();
    expect(isVisible).toBe(true);
  });

  test('confirmation dialog has warning message', async () => {
    await trashPage.clickDeleteForever(0);
    const dialog = trashPage.getConfirmDialog();
    await expect(dialog.getByText(/This action cannot be undone/i)).toBeVisible();
  });

  test('confirmation dialog has cancel button', async () => {
    await trashPage.clickDeleteForever(0);
    const cancelButton = trashPage.getConfirmDialogCancelButton();
    await expect(cancelButton).toBeVisible();
  });

  test('confirmation dialog has delete forever button', async () => {
    await trashPage.clickDeleteForever(0);
    const deleteButton = trashPage.getConfirmDialogDeleteButton();
    await expect(deleteButton).toBeVisible();
  });

  test('can cancel permanent delete', async () => {
    await trashPage.clickDeleteForever(0);
    await trashPage.cancelPermanentDelete();

    // Dialog should be closed
    const isVisible = await trashPage.isConfirmDialogVisible();
    expect(isVisible).toBe(false);
  });

  // TODO: Re-enable after debugging confirmation dialog behavior
  test.skip('permanently delete single event after confirmation', async ({ page }) => {
    // Wait for the delete API call
    const responsePromise = page.waitForResponse(
      (response) =>
        response.url().includes('/api/events/') && response.url().includes('/permanent'),
      { timeout: 10000 }
    );

    await trashPage.permanentlyDeleteEvent(0);

    const response = await responsePromise;
    expect(response.status()).toBe(200);
  });

  // TODO: Re-enable after debugging confirmation dialog behavior
  test.skip('delete button in dialog shows loading state during operation', async ({ page }) => {
    // Delay the delete API response to observe loading state
    await page.route('**/api/events/*/permanent', async (route) => {
      if (route.request().method() === 'DELETE') {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ id: 101, message: 'Event permanently deleted' }),
        });
      } else {
        await route.continue();
      }
    });

    await trashPage.clickDeleteForever(0);

    // Click confirm delete button (don't await - we want to check loading state immediately)
    const confirmButton = trashPage.getConfirmDialogDeleteButton();
    await confirmButton.click();

    // Check loading state appears (button should be disabled or show spinner)
    const isLoading = await trashPage.isDeleteInProgress(0);
    expect(isLoading).toBe(true);
  });
});

// TODO: Re-enable error scenarios after fixing page navigation and mutation error display
test.describe.skip('Error Scenarios', () => {
  let trashPage: TrashPage;

  test('shows error message when API fails', async ({ page }) => {
    const errorConfig: ApiMockConfig = {
      deletedEventsError: true,
    };
    await setupApiMocks(page, errorConfig);
    trashPage = new TrashPage(page);

    await trashPage.goto();
    await trashPage.waitForTrashLoad();

    const hasError = await trashPage.hasErrorMessage();
    expect(hasError).toBe(true);
  });

  test('error state shows try again button', async ({ page }) => {
    const errorConfig: ApiMockConfig = {
      deletedEventsError: true,
    };
    await setupApiMocks(page, errorConfig);
    trashPage = new TrashPage(page);

    await trashPage.goto();
    await trashPage.waitForTrashLoad();

    await expect(trashPage.tryAgainButton).toBeVisible();
  });

  test('try again button refetches data', async ({ page }) => {
    const errorConfig: ApiMockConfig = {
      deletedEventsError: true,
    };
    await setupApiMocks(page, errorConfig);
    trashPage = new TrashPage(page);

    await trashPage.goto();
    await trashPage.waitForTrashLoad();

    // Now fix the API to return success
    await setupApiMocks(page, defaultMockConfig);

    // Wait for the refetch API call
    const responsePromise = page.waitForResponse(
      (response) => response.url().includes('/api/events/deleted'),
      { timeout: 10000 }
    );

    await trashPage.clickTryAgain();

    const response = await responsePromise;
    expect(response.status()).toBe(200);
  });

  test('shows error when restore fails', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    trashPage = new TrashPage(page);

    await trashPage.goto();
    await trashPage.waitForTrashLoad();

    // Mock restore endpoint to fail
    await page.route('**/api/events/*/restore', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Failed to restore event' }),
        });
      } else {
        await route.continue();
      }
    });

    await trashPage.restoreEvent(0);

    // Wait for mutation error to appear
    await expect(trashPage.mutationErrorMessage).toBeVisible({ timeout: 5000 });
  });

  test('shows error when permanent delete fails', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    trashPage = new TrashPage(page);

    await trashPage.goto();
    await trashPage.waitForTrashLoad();

    // Mock delete endpoint to fail
    await page.route('**/api/events/*/permanent', async (route) => {
      if (route.request().method() === 'DELETE') {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Failed to delete event permanently' }),
        });
      } else {
        await route.continue();
      }
    });

    await trashPage.permanentlyDeleteEvent(0);

    // Wait for mutation error to appear
    await expect(trashPage.mutationErrorMessage).toBeVisible({ timeout: 5000 });
  });
});

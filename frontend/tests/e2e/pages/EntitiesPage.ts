/**
 * EntitiesPage - Page Object for the Entities page
 *
 * This page displays tracked people and vehicles with filtering capabilities.
 */

import type { Page, Locator } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class EntitiesPage extends BasePage {
  // Page heading
  readonly pageTitle: Locator;
  readonly pageSubtitle: Locator;
  readonly usersIcon: Locator;

  // Filter buttons
  readonly allFilterButton: Locator;
  readonly personFilterButton: Locator;
  readonly vehicleFilterButton: Locator;

  // Refresh button
  readonly refreshButton: Locator;

  // Empty state
  readonly emptyStateMessage: Locator;
  readonly emptyStateHeading: Locator;

  // Entity grid
  readonly entityGrid: Locator;
  readonly entityCards: Locator;

  // Loading state
  readonly loadingIndicator: Locator;

  constructor(page: Page) {
    super(page);

    // Page heading
    this.pageTitle = page.getByRole('heading', { name: /Entities/i }).first();
    this.pageSubtitle = page.getByText(/Track and identify people and vehicles/i);
    this.usersIcon = page.locator('svg.lucide-users').first();

    // Filter buttons - text content within buttons
    this.allFilterButton = page.locator('button').filter({ hasText: 'All' }).first();
    this.personFilterButton = page.locator('button').filter({ hasText: 'Persons' });
    this.vehicleFilterButton = page.locator('button').filter({ hasText: 'Vehicles' });

    // Refresh button - has aria-label
    this.refreshButton = page.getByRole('button', { name: /Refresh entities/i });

    // Empty state - matches EntitiesEmptyState component
    this.emptyStateMessage = page.getByText(
      /Entities are automatically created when the AI identifies/i
    );
    this.emptyStateHeading = page.getByRole('heading', { name: /No Entities Tracked Yet/i });

    // Entity grid
    this.entityGrid = page.locator('.grid');
    this.entityCards = page.locator('[data-testid="entity-card"]');

    // Loading state
    this.loadingIndicator = page.getByText(/Loading entities/i);
  }

  /**
   * Navigate to the Entities page
   */
  async goto(): Promise<void> {
    await this.page.goto('/entities');
  }

  /**
   * Wait for the entities page to fully load
   * This includes waiting for the API call to complete and entity cards to render
   */
  async waitForEntitiesLoad(): Promise<void> {
    await expect(this.pageTitle).toBeVisible({ timeout: this.pageLoadTimeout });
    // Wait for filter buttons to be visible (indicates page shell has loaded)
    await expect(this.allFilterButton).toBeVisible({ timeout: this.pageLoadTimeout });

    // Wait for either entity cards to appear OR empty state to appear
    // This ensures the API call has completed and data has been processed
    await this.page.waitForFunction(
      () => {
        const hasEntityCards =
          document.querySelectorAll('[data-testid="entity-card"]').length > 0;

        // Check for empty state - look for the specific heading text
        // EntitiesEmptyState renders <h2>No Entities Tracked Yet</h2>
        // Filtered empty state renders <h2>No Persons Found/No Vehicles Found/No Entities Found</h2>
        const h2Elements = document.querySelectorAll('h2');
        let hasEmptyState = false;
        for (const h2 of h2Elements) {
          const text = h2.textContent ?? '';
          if (
            text.includes('No Entities Tracked Yet') ||
            text.includes('No Persons Found') ||
            text.includes('No Vehicles Found') ||
            text.includes('No Entities Found')
          ) {
            hasEmptyState = true;
            break;
          }
        }

        // Only check for skeleton elements as loading indicator
        // Note: The empty state has animate-pulse on the Scan icon, so we can't use that
        const hasLoadingIndicator =
          document.querySelectorAll('[data-testid="entity-card-skeleton"]').length > 0;

        // Wait until we have entity cards or empty state, and loading is complete
        return (hasEntityCards || hasEmptyState) && !hasLoadingIndicator;
      },
      { timeout: this.pageLoadTimeout }
    );
  }

  /**
   * Get the number of entity cards displayed
   */
  async getEntityCount(): Promise<number> {
    return this.entityCards.count();
  }

  /**
   * Check if the page is in loading state
   */
  async isLoading(): Promise<boolean> {
    return this.loadingIndicator.isVisible().catch(() => false);
  }

  /**
   * Click refresh button
   */
  async refresh(): Promise<void> {
    await this.refreshButton.click();
  }

  /**
   * Filter by entity type
   */
  async filterByType(type: 'all' | 'person' | 'vehicle'): Promise<void> {
    switch (type) {
      case 'all':
        await this.allFilterButton.click();
        break;
      case 'person':
        await this.personFilterButton.click();
        break;
      case 'vehicle':
        await this.vehicleFilterButton.click();
        break;
    }
  }

  /**
   * Click on an entity card by index to open detail modal
   * @param index - Zero-based index of the entity card to click
   */
  async clickEntityCard(index: number): Promise<void> {
    const card = this.entityCards.nth(index);
    await expect(card).toBeVisible({ timeout: this.pageLoadTimeout });
    await card.click();
  }

  /**
   * Get entity card by index
   * @param index - Zero-based index of the entity card
   */
  getEntityCard(index: number): Locator {
    return this.entityCards.nth(index);
  }
}

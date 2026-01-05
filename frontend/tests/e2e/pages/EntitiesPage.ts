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

    // Empty state
    this.emptyStateMessage = page.getByText(/No tracked entities have been detected/i);
    this.emptyStateHeading = page.getByRole('heading', { name: /No Entities Found/i });

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
   */
  async waitForEntitiesLoad(): Promise<void> {
    await expect(this.pageTitle).toBeVisible({ timeout: this.pageLoadTimeout });
    // Wait for filter buttons to be visible (indicates page has loaded)
    await expect(this.allFilterButton).toBeVisible({ timeout: this.pageLoadTimeout });
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
}

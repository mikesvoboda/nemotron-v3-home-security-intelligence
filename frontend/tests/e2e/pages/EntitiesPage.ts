/**
 * EntitiesPage - Page Object for the Entities page
 *
 * Note: This page is a "Coming Soon" placeholder.
 * The page object provides selectors for the current placeholder content.
 */

import type { Page, Locator } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class EntitiesPage extends BasePage {
  // Page heading
  readonly pageTitle: Locator;
  readonly pageSubtitle: Locator;
  readonly usersIcon: Locator;

  // Coming Soon Section
  readonly comingSoonHeading: Locator;
  readonly comingSoonDescription: Locator;
  readonly featureList: Locator;
  readonly featureItems: Locator;
  readonly checkBackMessage: Locator;

  constructor(page: Page) {
    super(page);

    // Page heading
    this.pageTitle = page.getByRole('heading', { name: /Entities/i }).first();
    this.pageSubtitle = page.getByText(/Track and identify people and vehicles/i);
    this.usersIcon = page.locator('svg.lucide-users').first();

    // Coming Soon Section
    this.comingSoonHeading = page.getByRole('heading', { name: /Coming Soon/i });
    this.comingSoonDescription = page.getByText(/The Entities feature is currently under development/i);
    this.featureList = page.locator('ul');
    this.featureItems = page.locator('ul li');
    this.checkBackMessage = page.getByText(/Check back for updates/i);
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
  }

  /**
   * Check if coming soon message is displayed
   */
  async hasComingSoonMessage(): Promise<boolean> {
    return this.comingSoonHeading.isVisible().catch(() => false);
  }

  /**
   * Get the number of feature items listed
   */
  async getFeatureCount(): Promise<number> {
    return this.featureItems.count();
  }

  /**
   * Get feature item text by index
   */
  async getFeatureText(index: number): Promise<string | null> {
    return this.featureItems.nth(index).textContent();
  }
}

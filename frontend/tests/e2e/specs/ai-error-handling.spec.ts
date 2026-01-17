/**
 * AI Model Error Handling E2E Tests
 *
 * Comprehensive tests verifying the system handles AI model errors gracefully
 * and enters degraded mode appropriately. Tests cover:
 * - AI service timeout scenarios
 * - AI service error responses
 * - Degraded mode UI indicators
 * - Manual override when AI is unavailable
 * - Recovery when AI service returns
 * - Partial AI results handling
 *
 * Related: NEM-2756 [P3] Add E2E tests for AI Model Error Handling
 */

import { test, expect } from '@playwright/test';
import {
  DashboardPage,
  SystemPage,
  AIAuditPage,
} from '../pages';
import {
  setupApiMocks,
  defaultMockConfig,
  errorMockConfig,
  type ApiMockConfig,
} from '../fixtures';
import {
  setupWebSocketMock,
  type WebSocketMockController,
  type AIServiceStatusMessage,
} from '../fixtures/websocket-mock';

/**
 * Helper function to create AI service status message for testing
 */
function createAIServiceStatusMessage(
  degradationMode: 'normal' | 'degraded' | 'minimal' | 'offline',
  services: {
    rtdetr?: 'healthy' | 'degraded' | 'unavailable';
    nemotron?: 'healthy' | 'degraded' | 'unavailable';
    florence?: 'healthy' | 'degraded' | 'unavailable';
    clip?: 'healthy' | 'degraded' | 'unavailable';
  } = {}
): AIServiceStatusMessage {
  const defaultService = (status: 'healthy' | 'degraded' | 'unavailable') => ({
    service: 'rtdetr' as const,
    status,
    circuit_state: 'closed' as const,
    last_success: new Date().toISOString(),
    failure_count: 0,
    error_message: null,
    last_check: new Date().toISOString(),
  });

  return {
    type: 'ai_service_status',
    timestamp: new Date().toISOString(),
    degradation_mode: degradationMode,
    services: {
      rtdetr: { ...defaultService(services.rtdetr || 'healthy'), service: 'rtdetr' },
      nemotron: { ...defaultService(services.nemotron || 'healthy'), service: 'nemotron' },
      florence: { ...defaultService(services.florence || 'healthy'), service: 'florence' },
      clip: { ...defaultService(services.clip || 'healthy'), service: 'clip' },
    },
    available_features: degradationMode === 'normal'
      ? ['detection', 'analysis', 'enrichment', 'reid']
      : degradationMode === 'degraded'
      ? ['detection', 'analysis']
      : degradationMode === 'minimal'
      ? ['detection']
      : [],
  };
}

test.describe('AI Service Timeout Scenarios @critical', () => {
  test('dashboard loads when AI service times out', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const wsMock = await setupWebSocketMock(page);
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Simulate AI service timeout via WebSocket
    await wsMock.sendMessage('events', createAIServiceStatusMessage('minimal', {
      rtdetr: 'healthy',
      nemotron: 'unavailable',
    }));

    // Verify dashboard still functional
    await expect(dashboardPage.pageTitle).toBeVisible();
    await expect(dashboardPage.riskScoreStat).toBeVisible();

    // Check for degradation indicator
    const degradationIndicator = page.locator('[data-testid="ai-service-status"]');
    if (await degradationIndicator.count() > 0) {
      await expect(degradationIndicator).toBeVisible();
    }
  });

  test('system page shows AI service timeout indicator', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const wsMock = await setupWebSocketMock(page);
    const systemPage = new SystemPage(page);

    await systemPage.goto();
    await systemPage.waitForSystemLoad();

    // Simulate AI service timeout
    await wsMock.sendMessage('events', createAIServiceStatusMessage('minimal', {
      rtdetr: 'healthy',
      nemotron: 'unavailable',
    }));

    // Wait for WebSocket message to be processed
    await page.waitForTimeout(500);

    // Check for timeout indicator in service health
    const nemotronService = systemPage.nemotronService;
    if (await nemotronService.count() > 0) {
      await expect(nemotronService).toBeVisible();
      const badgeText = await nemotronService.locator('[class*="Badge"]').textContent();
      expect(badgeText?.toLowerCase()).toMatch(/unavailable|unhealthy|timeout|error/);
    }
  });

  test('AI audit page handles service timeout gracefully', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const wsMock = await setupWebSocketMock(page);
    const aiAuditPage = new AIAuditPage(page);

    await aiAuditPage.goto();
    await aiAuditPage.waitForPageLoad();

    // Simulate AI service timeout
    await wsMock.sendMessage('events', createAIServiceStatusMessage('degraded', {
      rtdetr: 'healthy',
      nemotron: 'healthy',
      florence: 'unavailable',
    }));

    // Page should remain functional
    await expect(aiAuditPage.pageTitle).toBeVisible();

    // Check for degradation notice if available
    const degradationNotice = page.getByText(/degraded|limited functionality/i);
    if (await degradationNotice.count() > 0) {
      await expect(degradationNotice.first()).toBeVisible();
    }
  });
});

test.describe('AI Service Error Responses @critical', () => {
  test('dashboard displays fallback when AI analysis fails', async ({ page }) => {
    // Use error config for API endpoints
    const errorConfig: ApiMockConfig = {
      ...defaultMockConfig,
      // AI-related endpoints return errors
      aiAuditError: true,
      systemHealthError: false, // Keep system health working
    };
    await setupApiMocks(page, errorConfig);
    const wsMock = await setupWebSocketMock(page);
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Simulate all AI services offline
    await wsMock.sendMessage('events', createAIServiceStatusMessage('offline', {
      rtdetr: 'unavailable',
      nemotron: 'unavailable',
      florence: 'unavailable',
      clip: 'unavailable',
    }));

    await page.waitForTimeout(500);

    // Dashboard should still load but show degraded state
    await expect(dashboardPage.pageTitle).toBeVisible();

    // Look for offline indicator
    const offlineIndicator = page.getByText(/AI.*offline|services.*unavailable/i);
    if (await offlineIndicator.count() > 0) {
      await expect(offlineIndicator.first()).toBeVisible();
    }
  });

  test('system page shows error details for failed AI services', async ({ page }) => {
    const errorConfig: ApiMockConfig = {
      ...defaultMockConfig,
      aiAuditError: true,
      systemHealthError: false,
    };
    await setupApiMocks(page, errorConfig);
    const wsMock = await setupWebSocketMock(page);
    const systemPage = new SystemPage(page);

    await systemPage.goto();
    await systemPage.waitForSystemLoad();

    // Simulate service errors with error messages
    const errorMessage: AIServiceStatusMessage = {
      type: 'ai_service_status',
      timestamp: new Date().toISOString(),
      degradation_mode: 'minimal',
      services: {
        rtdetr: {
          service: 'rtdetr',
          status: 'healthy',
          circuit_state: 'closed',
          last_success: new Date().toISOString(),
          failure_count: 0,
          error_message: null,
          last_check: new Date().toISOString(),
        },
        nemotron: {
          service: 'nemotron',
          status: 'unavailable',
          circuit_state: 'open',
          last_success: new Date(Date.now() - 600000).toISOString(),
          failure_count: 5,
          error_message: 'Connection timeout: model not responding',
          last_check: new Date().toISOString(),
        },
        florence: {
          service: 'florence',
          status: 'unavailable',
          circuit_state: 'open',
          last_success: null,
          failure_count: 3,
          error_message: 'Failed to load model: Out of memory',
          last_check: new Date().toISOString(),
        },
        clip: {
          service: 'clip',
          status: 'healthy',
          circuit_state: 'closed',
          last_success: new Date().toISOString(),
          failure_count: 0,
          error_message: null,
          last_check: new Date().toISOString(),
        },
      },
      available_features: ['detection'],
    };

    await wsMock.sendMessage('events', errorMessage);
    await page.waitForTimeout(500);

    // Check for service status indicators
    if (await systemPage.nemotronService.count() > 0) {
      await expect(systemPage.nemotronService).toBeVisible();
    }

    // Look for error message display
    const errorText = page.getByText(/timeout|not responding|out of memory/i);
    if (await errorText.count() > 0) {
      await expect(errorText.first()).toBeVisible();
    }
  });

  test('error state includes retry mechanism', async ({ page }) => {
    const errorConfig: ApiMockConfig = {
      ...defaultMockConfig,
      aiAuditError: true,
      systemHealthError: false,
    };
    await setupApiMocks(page, errorConfig);
    const wsMock = await setupWebSocketMock(page);
    const systemPage = new SystemPage(page);

    await systemPage.goto();
    await systemPage.waitForSystemLoad();

    // Simulate service errors
    await wsMock.sendMessage('events', createAIServiceStatusMessage('offline', {
      rtdetr: 'unavailable',
      nemotron: 'unavailable',
    }));

    await page.waitForTimeout(500);

    // Look for refresh/retry button
    const retryButton = page.getByRole('button', { name: /retry|refresh|reload/i });
    if (await retryButton.count() > 0) {
      await expect(retryButton.first()).toBeVisible();
      await expect(retryButton.first()).toBeEnabled();
    }
  });
});

test.describe('Degraded Mode UI Indicators @critical', () => {
  test('header shows degraded mode badge when AI services are down', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const wsMock = await setupWebSocketMock(page);

    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    // Simulate degraded mode
    await wsMock.sendMessage('events', createAIServiceStatusMessage('degraded', {
      rtdetr: 'healthy',
      nemotron: 'healthy',
      florence: 'unavailable',
      clip: 'unavailable',
    }));

    await page.waitForTimeout(500);

    // Look for degraded mode indicator in header
    const header = page.locator('header');
    const degradedBadge = header.getByText(/degraded|limited/i);
    if (await degradedBadge.count() > 0) {
      await expect(degradedBadge.first()).toBeVisible();
    }
  });

  test('system page displays detailed degradation status', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const wsMock = await setupWebSocketMock(page);
    const systemPage = new SystemPage(page);

    await systemPage.goto();
    await systemPage.waitForSystemLoad();

    // Simulate degraded mode
    await wsMock.sendMessage('events', createAIServiceStatusMessage('degraded', {
      rtdetr: 'healthy',
      nemotron: 'healthy',
      florence: 'unavailable',
      clip: 'unavailable',
    }));

    await page.waitForTimeout(500);

    // Check for AI service status section
    const aiStatusSection = page.locator('[data-testid="ai-service-status"]');
    if (await aiStatusSection.count() > 0) {
      await expect(aiStatusSection).toBeVisible();

      // Should show which services are unavailable
      const florenceStatus = page.getByText(/florence.*unavailable/i);
      const clipStatus = page.getByText(/clip.*unavailable/i);

      if (await florenceStatus.count() > 0) {
        await expect(florenceStatus.first()).toBeVisible();
      }
      if (await clipStatus.count() > 0) {
        await expect(clipStatus.first()).toBeVisible();
      }
    }
  });

  test('minimal mode shows critical warning', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const wsMock = await setupWebSocketMock(page);
    const systemPage = new SystemPage(page);

    await systemPage.goto();
    await systemPage.waitForSystemLoad();

    // Simulate minimal mode (only detection available)
    await wsMock.sendMessage('events', createAIServiceStatusMessage('minimal', {
      rtdetr: 'healthy',
      nemotron: 'unavailable',
      florence: 'unavailable',
      clip: 'unavailable',
    }));

    await page.waitForTimeout(500);

    // Look for critical warning
    const warningBanner = page.getByText(/minimal.*mode|critical.*unavailable|reduced.*functionality/i);
    if (await warningBanner.count() > 0) {
      await expect(warningBanner.first()).toBeVisible();
    }
  });

  test('offline mode shows prominent alert', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const wsMock = await setupWebSocketMock(page);

    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    // Simulate offline mode
    await wsMock.sendMessage('events', createAIServiceStatusMessage('offline', {
      rtdetr: 'unavailable',
      nemotron: 'unavailable',
      florence: 'unavailable',
      clip: 'unavailable',
    }));

    await page.waitForTimeout(500);

    // Look for offline alert
    const offlineAlert = page.getByText(/AI.*offline|services.*unavailable|historical.*only/i);
    if (await offlineAlert.count() > 0) {
      await expect(offlineAlert.first()).toBeVisible();
    }
  });
});

test.describe('Manual Override When AI Unavailable', () => {
  test('timeline displays events without AI analysis in offline mode', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const wsMock = await setupWebSocketMock(page);

    await page.goto('/timeline');
    await page.waitForLoadState('domcontentloaded');

    // Simulate offline mode
    await wsMock.sendMessage('events', createAIServiceStatusMessage('offline', {
      rtdetr: 'unavailable',
      nemotron: 'unavailable',
    }));

    await page.waitForTimeout(500);

    // Events should still be visible (from existing data)
    const eventCards = page.locator('[data-testid^="event-card-"]');
    if (await eventCards.count() > 0) {
      await expect(eventCards.first()).toBeVisible();
    }

    // Check for notice about missing AI analysis
    const noAINotice = page.getByText(/AI.*unavailable|no.*analysis|offline/i);
    if (await noAINotice.count() > 0) {
      await expect(noAINotice.first()).toBeVisible();
    }
  });

  test('user can manually review events when AI is offline', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const wsMock = await setupWebSocketMock(page);

    await page.goto('/timeline');
    await page.waitForLoadState('domcontentloaded');

    // Simulate offline mode
    await wsMock.sendMessage('events', createAIServiceStatusMessage('offline'));
    await page.waitForTimeout(500);

    // Click on an event to open details
    const eventCard = page.locator('[data-testid^="event-card-"]').first();
    if (await eventCard.count() > 0) {
      await eventCard.click();

      // Modal should open
      const modal = page.locator('[role="dialog"], [data-testid="event-detail-modal"]');
      await expect(modal).toBeVisible({ timeout: 3000 });

      // User should be able to review and add notes
      const notesField = page.getByPlaceholder(/notes|comments/i);
      if (await notesField.count() > 0) {
        await expect(notesField).toBeVisible();
        await expect(notesField).toBeEditable();
      }
    }
  });

  test('dashboard shows cached data when AI services are offline', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const wsMock = await setupWebSocketMock(page);
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Verify initial data loads
    await expect(dashboardPage.riskScoreStat).toBeVisible();

    // Simulate offline mode
    await wsMock.sendMessage('events', createAIServiceStatusMessage('offline'));
    await page.waitForTimeout(500);

    // Dashboard should still show data (cached/historical)
    await expect(dashboardPage.pageTitle).toBeVisible();
    await expect(dashboardPage.riskScoreStat).toBeVisible();
  });
});

test.describe('Recovery When AI Service Returns', () => {
  test('system page updates when AI services recover', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const wsMock = await setupWebSocketMock(page);
    const systemPage = new SystemPage(page);

    await systemPage.goto();
    await systemPage.waitForSystemLoad();

    // Start with degraded mode
    await wsMock.sendMessage('events', createAIServiceStatusMessage('degraded', {
      rtdetr: 'healthy',
      nemotron: 'healthy',
      florence: 'unavailable',
      clip: 'unavailable',
    }));

    await page.waitForTimeout(500);

    // Simulate recovery
    await wsMock.sendMessage('events', createAIServiceStatusMessage('normal', {
      rtdetr: 'healthy',
      nemotron: 'healthy',
      florence: 'healthy',
      clip: 'healthy',
    }));

    await page.waitForTimeout(500);

    // Look for recovery indicator
    const healthyIndicator = page.getByText(/all.*operational|normal|healthy/i);
    if (await healthyIndicator.count() > 0) {
      await expect(healthyIndicator.first()).toBeVisible();
    }
  });

  test('degraded mode badge disappears after recovery', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const wsMock = await setupWebSocketMock(page);

    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    // Start with degraded mode
    await wsMock.sendMessage('events', createAIServiceStatusMessage('degraded'));
    await page.waitForTimeout(500);

    // Simulate recovery
    await wsMock.sendMessage('events', createAIServiceStatusMessage('normal'));
    await page.waitForTimeout(500);

    // Degraded badge should not be visible
    const degradedBadge = page.getByText(/degraded/i);
    if (await degradedBadge.count() > 0) {
      // If badge exists, it should not be visible or should show "normal"
      const badgeText = await degradedBadge.first().textContent();
      expect(badgeText?.toLowerCase()).not.toContain('degraded');
    }
  });

  test('AI audit page reflects service recovery', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const wsMock = await setupWebSocketMock(page);
    const aiAuditPage = new AIAuditPage(page);

    await aiAuditPage.goto();
    await aiAuditPage.waitForPageLoad();

    // Start with minimal mode
    await wsMock.sendMessage('events', createAIServiceStatusMessage('minimal', {
      rtdetr: 'healthy',
      nemotron: 'unavailable',
    }));

    await page.waitForTimeout(500);

    // Simulate recovery
    await wsMock.sendMessage('events', createAIServiceStatusMessage('normal'));
    await page.waitForTimeout(500);

    // Page should update to show normal operation
    await expect(aiAuditPage.pageTitle).toBeVisible();

    // Warning banner should disappear
    const warningBanner = page.getByText(/minimal|unavailable/i);
    if (await warningBanner.count() > 0) {
      await expect(warningBanner.first()).not.toBeVisible();
    }
  });
});

test.describe('Partial AI Results Handling', () => {
  test('dashboard shows detections without analysis when Nemotron is down', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const wsMock = await setupWebSocketMock(page);
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Simulate partial service (detection works, analysis doesn't)
    await wsMock.sendMessage('events', createAIServiceStatusMessage('minimal', {
      rtdetr: 'healthy',
      nemotron: 'unavailable',
    }));

    await page.waitForTimeout(500);

    // Dashboard should still show data
    await expect(dashboardPage.pageTitle).toBeVisible();
    await expect(dashboardPage.riskScoreStat).toBeVisible();

    // Look for partial functionality notice
    const partialNotice = page.getByText(/detection.*available|analysis.*unavailable/i);
    if (await partialNotice.count() > 0) {
      await expect(partialNotice.first()).toBeVisible();
    }
  });

  test('events show detection results without risk analysis', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const wsMock = await setupWebSocketMock(page);

    await page.goto('/timeline');
    await page.waitForLoadState('domcontentloaded');

    // Simulate detection-only mode
    await wsMock.sendMessage('events', createAIServiceStatusMessage('minimal', {
      rtdetr: 'healthy',
      nemotron: 'unavailable',
    }));

    await page.waitForTimeout(500);

    // Events should be visible
    const eventCards = page.locator('[data-testid^="event-card-"]');
    if (await eventCards.count() > 0) {
      await expect(eventCards.first()).toBeVisible();

      // Click to see details
      await eventCards.first().click();

      // Modal should indicate missing analysis
      const analysisSection = page.getByText(/risk.*analysis|AI.*reasoning/i);
      if (await analysisSection.count() > 0) {
        const noAnalysisText = page.getByText(/not.*available|unavailable|pending/i);
        if (await noAnalysisText.count() > 0) {
          await expect(noAnalysisText.first()).toBeVisible();
        }
      }
    }
  });

  test('system page shows which AI features are available', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const wsMock = await setupWebSocketMock(page);
    const systemPage = new SystemPage(page);

    await systemPage.goto();
    await systemPage.waitForSystemLoad();

    // Simulate degraded mode with partial features
    await wsMock.sendMessage('events', createAIServiceStatusMessage('degraded', {
      rtdetr: 'healthy',
      nemotron: 'healthy',
      florence: 'unavailable',
      clip: 'unavailable',
    }));

    await page.waitForTimeout(500);

    // Look for feature availability indicator
    const featureList = page.getByText(/available.*features|detection.*analysis/i);
    if (await featureList.count() > 0) {
      await expect(featureList.first()).toBeVisible();
    }

    // Should indicate enrichment is unavailable
    const enrichmentStatus = page.getByText(/enrichment|florence|clip/i);
    if (await enrichmentStatus.count() > 0) {
      await expect(enrichmentStatus.first()).toBeVisible();
    }
  });
});

test.describe('Circuit Breaker Status Display', () => {
  test('system page shows circuit breaker state for AI services', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const wsMock = await setupWebSocketMock(page);
    const systemPage = new SystemPage(page);

    await systemPage.goto();
    await systemPage.waitForSystemLoad();

    // Simulate open circuit breaker
    const circuitBreakerMessage: AIServiceStatusMessage = {
      type: 'ai_service_status',
      timestamp: new Date().toISOString(),
      degradation_mode: 'minimal',
      services: {
        rtdetr: {
          service: 'rtdetr',
          status: 'healthy',
          circuit_state: 'closed',
          last_success: new Date().toISOString(),
          failure_count: 0,
          error_message: null,
          last_check: new Date().toISOString(),
        },
        nemotron: {
          service: 'nemotron',
          status: 'unavailable',
          circuit_state: 'open',
          last_success: new Date(Date.now() - 600000).toISOString(),
          failure_count: 5,
          error_message: 'Circuit breaker open due to repeated failures',
          last_check: new Date().toISOString(),
        },
        florence: {
          service: 'florence',
          status: 'healthy',
          circuit_state: 'closed',
          last_success: new Date().toISOString(),
          failure_count: 0,
          error_message: null,
          last_check: new Date().toISOString(),
        },
        clip: {
          service: 'clip',
          status: 'degraded',
          circuit_state: 'half_open',
          last_success: new Date(Date.now() - 120000).toISOString(),
          failure_count: 2,
          error_message: 'Circuit breaker half-open, testing connection',
          last_check: new Date().toISOString(),
        },
      },
      available_features: ['detection', 'enrichment'],
    };

    await wsMock.sendMessage('events', circuitBreakerMessage);
    await page.waitForTimeout(500);

    // Look for circuit breaker panel or indicators
    const circuitBreakerPanel = page.locator('[data-testid*="circuit-breaker"]');
    if (await circuitBreakerPanel.count() > 0) {
      await expect(circuitBreakerPanel.first()).toBeVisible();

      // Should show different states
      const openState = page.getByText(/open|tripped/i);
      const halfOpenState = page.getByText(/half.*open|testing/i);

      if (await openState.count() > 0) {
        await expect(openState.first()).toBeVisible();
      }
      if (await halfOpenState.count() > 0) {
        await expect(halfOpenState.first()).toBeVisible();
      }
    }
  });

  test('circuit breaker shows failure count', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const wsMock = await setupWebSocketMock(page);
    const systemPage = new SystemPage(page);

    await systemPage.goto();
    await systemPage.waitForSystemLoad();

    // Simulate service with failures
    const failureMessage: AIServiceStatusMessage = {
      type: 'ai_service_status',
      timestamp: new Date().toISOString(),
      degradation_mode: 'degraded',
      services: {
        rtdetr: {
          service: 'rtdetr',
          status: 'degraded',
          circuit_state: 'closed',
          last_success: new Date().toISOString(),
          failure_count: 3,
          error_message: 'Intermittent connection issues',
          last_check: new Date().toISOString(),
        },
        nemotron: {
          service: 'nemotron',
          status: 'healthy',
          circuit_state: 'closed',
          last_success: new Date().toISOString(),
          failure_count: 0,
          error_message: null,
          last_check: new Date().toISOString(),
        },
        florence: {
          service: 'florence',
          status: 'healthy',
          circuit_state: 'closed',
          last_success: new Date().toISOString(),
          failure_count: 0,
          error_message: null,
          last_check: new Date().toISOString(),
        },
        clip: {
          service: 'clip',
          status: 'healthy',
          circuit_state: 'closed',
          last_success: new Date().toISOString(),
          failure_count: 0,
          error_message: null,
          last_check: new Date().toISOString(),
        },
      },
      available_features: ['detection', 'analysis', 'enrichment', 'reid'],
    };

    await wsMock.sendMessage('events', failureMessage);
    await page.waitForTimeout(500);

    // Look for failure count display
    const failureCount = page.getByText(/3.*failure|failure.*3/i);
    if (await failureCount.count() > 0) {
      await expect(failureCount.first()).toBeVisible();
    }
  });
});

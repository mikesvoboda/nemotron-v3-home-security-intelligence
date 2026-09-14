/**
 * Model Zoo Admin Panel E2E Tests
 *
 * Linear Issue: NEM-4789
 * Test Coverage: Model Zoo admin panel in Settings > AI Models tab
 *
 * These tests are written in TDD RED phase - they will FAIL until the
 * Model Zoo panel implementation is complete.
 *
 * Acceptance Criteria:
 * - User can navigate to Settings > AI Models tab
 * - Model Zoo panel displays per-GPU VRAM usage bars
 * - Models are grouped by GPU (GPU 0 for heavy, GPU 1 for light)
 * - Status indicators show loaded/unloaded state
 * - Model categories are displayed as badges
 * - User can load/unload/reload models
 * - Error states are handled gracefully
 * - Auto-refresh updates model status every 5 seconds
 */

import { test, expect } from '@playwright/test';
import { SettingsPage } from '../pages';
import { setupApiMocks, defaultMockConfig, type ApiMockConfig } from '../fixtures';

// Mock data for Model Zoo API
const mockModelListResponse = {
  models: [
    {
      name: 'threat-detection-yolov8n',
      category: 'detection',
      estimated_vram_mb: 300,
      enabled: true,
      service: 'ai-enrichment-light',
      gpu_id: 1,
      runtime: {
        loaded: true,
        actual_vram_mb: 287,
        last_used: '2025-01-31T10:30:00Z',
        load_count: 5,
      },
    },
    {
      name: 'osnet-x0-25',
      category: 'embedding',
      estimated_vram_mb: 150,
      enabled: true,
      service: 'ai-enrichment-light',
      gpu_id: 1,
      runtime: {
        loaded: false,
        actual_vram_mb: null,
        last_used: null,
        load_count: 0,
      },
    },
    {
      name: 'vitpose-small',
      category: 'pose',
      estimated_vram_mb: 200,
      enabled: true,
      service: 'ai-enrichment-light',
      gpu_id: 1,
      runtime: {
        loaded: true,
        actual_vram_mb: 195,
        last_used: '2025-01-31T10:25:00Z',
        load_count: 3,
      },
    },
    {
      name: 'vehicle-segment-classification',
      category: 'classification',
      estimated_vram_mb: 1500,
      enabled: true,
      service: 'ai-enrichment',
      gpu_id: 0,
      runtime: {
        loaded: false,
        actual_vram_mb: null,
        last_used: null,
        load_count: 0,
      },
    },
    {
      name: 'fashion-clip',
      category: 'classification',
      estimated_vram_mb: 800,
      enabled: true,
      service: 'ai-enrichment',
      gpu_id: 0,
      runtime: {
        loaded: true,
        actual_vram_mb: 785,
        last_used: '2025-01-31T10:28:00Z',
        load_count: 2,
      },
    },
    {
      name: 'xclip-base',
      category: 'action',
      estimated_vram_mb: 1200,
      enabled: true,
      service: 'ai-enrichment',
      gpu_id: 0,
      runtime: {
        loaded: false,
        actual_vram_mb: null,
        last_used: null,
        load_count: 0,
      },
    },
  ],
  service_status: {
    'ai-enrichment': 'healthy',
    'ai-enrichment-light': 'healthy',
  },
};

const mockVramSummaryResponse = {
  gpus: [
    {
      gpu_id: 0,
      service: 'ai-enrichment',
      budget_mb: 6800,
      used_mb: 785,
      available_mb: 6015,
      utilization_percent: 11.5,
      loaded_models: ['fashion-clip'],
    },
    {
      gpu_id: 1,
      service: 'ai-enrichment-light',
      budget_mb: 1200,
      used_mb: 482,
      available_mb: 718,
      utilization_percent: 40.2,
      loaded_models: ['threat-detection-yolov8n', 'vitpose-small'],
    },
  ],
  totals: {
    budget_mb: 8000,
    used_mb: 1267,
    available_mb: 6733,
    model_count: 3,
  },
};

const mockLoadModelResponse = {
  success: true,
  model_name: 'osnet-x0-25',
  service: 'ai-enrichment-light',
  gpu_id: 1,
  load_time_ms: 1250,
  vram_mb: 145,
};

const mockUnloadModelResponse = {
  success: true,
  model_name: 'threat-detection-yolov8n',
  freed_vram_mb: 287,
};

const mockLoadErrorResponse = {
  detail: 'Insufficient VRAM available on GPU 1',
};

const mockServiceUnavailableResponse = {
  models: [],
  service_status: {
    'ai-enrichment': 'unavailable',
    'ai-enrichment-light': 'unavailable',
  },
};

/**
 * Sets up Model Zoo API mocks
 */
async function setupModelZooMocks(
  page: import('@playwright/test').Page,
  config: {
    models?: typeof mockModelListResponse;
    vram?: typeof mockVramSummaryResponse;
    loadError?: boolean;
    serviceUnavailable?: boolean;
  } = {}
): Promise<void> {
  // First set up default API mocks
  await setupApiMocks(page, defaultMockConfig);

  // Model list endpoint
  await page.route('**/api/system/models', async (route) => {
    if (route.request().method() === 'GET') {
      if (config.serviceUnavailable) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockServiceUnavailableResponse),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(config.models || mockModelListResponse),
        });
      }
    } else {
      await route.continue();
    }
  });

  // VRAM summary endpoint
  await page.route('**/api/system/models/vram-summary', async (route) => {
    if (config.serviceUnavailable) {
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Service unavailable' }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(config.vram || mockVramSummaryResponse),
      });
    }
  });

  // Load model endpoint
  await page.route('**/api/system/models/*/load', async (route) => {
    if (route.request().method() === 'POST') {
      if (config.loadError) {
        await route.fulfill({
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify(mockLoadErrorResponse),
        });
      } else {
        // Extract model name from URL
        const url = route.request().url();
        const match = url.match(/\/api\/system\/models\/([^/]+)\/load/);
        const modelName = match?.[1] || 'unknown';

        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ...mockLoadModelResponse,
            model_name: modelName,
          }),
        });
      }
    } else {
      await route.continue();
    }
  });

  // Unload model endpoint
  await page.route('**/api/system/models/*/unload', async (route) => {
    if (route.request().method() === 'POST') {
      // Extract model name from URL
      const url = route.request().url();
      const match = url.match(/\/api\/system\/models\/([^/]+)\/unload/);
      const modelName = match?.[1] || 'unknown';

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ...mockUnloadModelResponse,
          model_name: modelName,
        }),
      });
    } else {
      await route.continue();
    }
  });

  // Reload model endpoint
  await page.route('**/api/system/models/*/reload', async (route) => {
    if (route.request().method() === 'POST') {
      // Extract model name from URL
      const url = route.request().url();
      const match = url.match(/\/api\/system\/models\/([^/]+)\/reload/);
      const modelName = match?.[1] || 'unknown';

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ...mockLoadModelResponse,
          model_name: modelName,
        }),
      });
    } else {
      await route.continue();
    }
  });

  // Model status endpoint
  await page.route('**/api/system/models/*/status', async (route) => {
    const url = route.request().url();
    const match = url.match(/\/api\/system\/models\/([^/]+)\/status/);
    const modelName = match?.[1] || 'unknown';

    const models = config.models?.models || mockModelListResponse.models;
    const model = models.find((m) => m.name === modelName);

    if (model) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(model),
      });
    } else {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Model not found' }),
      });
    }
  });
}

// Skip entire file in CI - tests will fail until implementation is complete (TDD RED phase)
test.skip(() => !!process.env.CI, 'Model Zoo tests are TDD RED phase - run locally');

test.describe('Model Zoo Panel - Navigation', () => {
  test('navigates to Settings > AI Models tab', async ({ page }) => {
    await setupModelZooMocks(page);

    // Navigate to Settings page
    await page.goto('/settings');

    // Wait for settings page to load
    await expect(page.getByRole('heading', { name: /Settings/i })).toBeVisible();

    // Click on AI Models tab
    const aiModelsTab = page
      .getByRole('tab', { name: /AI Models/i })
      .or(page.locator('button').filter({ hasText: 'AI MODELS' }));

    await expect(aiModelsTab).toBeVisible();
    await aiModelsTab.click();

    // Verify tab is selected
    await expect(aiModelsTab).toHaveAttribute('aria-selected', 'true');
  });

  test('Model Zoo panel is visible in AI Models settings', async ({ page }) => {
    await setupModelZooMocks(page);

    await page.goto('/settings');
    await expect(page.getByRole('heading', { name: /Settings/i })).toBeVisible();

    // Navigate to AI Models tab
    const aiModelsTab = page
      .getByRole('tab', { name: /AI Models/i })
      .or(page.locator('button').filter({ hasText: 'AI MODELS' }));
    await aiModelsTab.click();

    // Verify Model Zoo panel is visible
    const modelZooPanel = page.getByTestId('model-zoo-panel');
    await expect(modelZooPanel).toBeVisible();

    // Verify panel has title
    await expect(page.getByText(/Model Zoo/i)).toBeVisible();
  });
});

test.describe('Model Zoo Panel - Display', () => {
  test.beforeEach(async ({ page }) => {
    await setupModelZooMocks(page);
    await page.goto('/settings');

    // Navigate to AI Models tab
    const aiModelsTab = page
      .getByRole('tab', { name: /AI Models/i })
      .or(page.locator('button').filter({ hasText: 'AI MODELS' }));
    await aiModelsTab.click();
  });

  test('displays per-GPU VRAM bars', async ({ page }) => {
    // Verify VRAM section exists
    const vramSection = page.getByTestId('vram-section');
    await expect(vramSection).toBeVisible();

    // Verify GPU 0 VRAM bar
    const gpu0VramBar = page.getByTestId('vram-bar-gpu-0');
    await expect(gpu0VramBar).toBeVisible();
    await expect(page.getByText(/GPU 0.*Heavy Models/i)).toBeVisible();

    // Verify GPU 1 VRAM bar
    const gpu1VramBar = page.getByTestId('vram-bar-gpu-1');
    await expect(gpu1VramBar).toBeVisible();
    await expect(page.getByText(/GPU 1.*Light Models/i)).toBeVisible();

    // Verify VRAM usage is displayed (from mock: GPU 0 = 11.5%, GPU 1 = 40.2%)
    await expect(page.getByText(/11\.5%/)).toBeVisible();
    await expect(page.getByText(/40\.2%/)).toBeVisible();
  });

  test('shows models grouped by GPU 0 and GPU 1', async ({ page }) => {
    // Verify GPU 0 section
    const gpu0Section = page.getByTestId('gpu-0-section');
    await expect(gpu0Section).toBeVisible();
    await expect(gpu0Section.getByText(/ai-enrichment/i)).toBeVisible();

    // GPU 0 models from mock: vehicle-segment-classification, fashion-clip, xclip-base
    await expect(gpu0Section.getByText('fashion-clip')).toBeVisible();
    await expect(gpu0Section.getByText('vehicle-segment-classification')).toBeVisible();
    await expect(gpu0Section.getByText('xclip-base')).toBeVisible();

    // Verify GPU 1 section
    const gpu1Section = page.getByTestId('gpu-1-section');
    await expect(gpu1Section).toBeVisible();
    await expect(gpu1Section.getByText(/ai-enrichment-light/i)).toBeVisible();

    // GPU 1 models from mock: threat-detection-yolov8n, osnet-x0-25, vitpose-small
    await expect(gpu1Section.getByText('threat-detection-yolov8n')).toBeVisible();
    await expect(gpu1Section.getByText('osnet-x0-25')).toBeVisible();
    await expect(gpu1Section.getByText('vitpose-small')).toBeVisible();
  });

  test('shows correct status indicators for loaded/unloaded models', async ({ page }) => {
    // Loaded models should have "Loaded" badge/indicator
    const gpu1Section = page.getByTestId('gpu-1-section');

    // threat-detection-yolov8n is loaded
    const threatModel = gpu1Section.locator('[data-testid="model-card-threat-detection-yolov8n"]');
    await expect(threatModel.getByText(/Loaded/i)).toBeVisible();

    // osnet-x0-25 is NOT loaded
    const osnetModel = gpu1Section.locator('[data-testid="model-card-osnet-x0-25"]');
    await expect(osnetModel.getByText(/Unloaded/i)).toBeVisible();

    // vitpose-small is loaded
    const vitposeModel = gpu1Section.locator('[data-testid="model-card-vitpose-small"]');
    await expect(vitposeModel.getByText(/Loaded/i)).toBeVisible();

    // GPU 0 models
    const gpu0Section = page.getByTestId('gpu-0-section');

    // fashion-clip is loaded
    const fashionModel = gpu0Section.locator('[data-testid="model-card-fashion-clip"]');
    await expect(fashionModel.getByText(/Loaded/i)).toBeVisible();

    // vehicle-segment-classification is NOT loaded
    const vehicleModel = gpu0Section.locator(
      '[data-testid="model-card-vehicle-segment-classification"]'
    );
    await expect(vehicleModel.getByText(/Unloaded/i)).toBeVisible();
  });

  test('displays model categories as badges', async ({ page }) => {
    // Each model card should display its category as a badge

    // threat-detection-yolov8n category: detection
    const threatModel = page.locator('[data-testid="model-card-threat-detection-yolov8n"]');
    await expect(threatModel.getByText('detection')).toBeVisible();

    // osnet-x0-25 category: embedding
    const osnetModel = page.locator('[data-testid="model-card-osnet-x0-25"]');
    await expect(osnetModel.getByText('embedding')).toBeVisible();

    // fashion-clip category: classification
    const fashionModel = page.locator('[data-testid="model-card-fashion-clip"]');
    await expect(fashionModel.getByText('classification')).toBeVisible();

    // xclip-base category: action
    const xclipModel = page.locator('[data-testid="model-card-xclip-base"]');
    await expect(xclipModel.getByText('action')).toBeVisible();

    // vitpose-small category: pose
    const vitposeModel = page.locator('[data-testid="model-card-vitpose-small"]');
    await expect(vitposeModel.getByText('pose')).toBeVisible();
  });

  test('displays VRAM usage for loaded models', async ({ page }) => {
    // Loaded models should show actual VRAM usage

    // threat-detection-yolov8n: 287 MB
    const threatModel = page.locator('[data-testid="model-card-threat-detection-yolov8n"]');
    await expect(threatModel.getByText(/287.*MB/i)).toBeVisible();

    // fashion-clip: 785 MB
    const fashionModel = page.locator('[data-testid="model-card-fashion-clip"]');
    await expect(fashionModel.getByText(/785.*MB/i)).toBeVisible();
  });
});

test.describe('Model Zoo Panel - Interactions', () => {
  test.beforeEach(async ({ page }) => {
    await setupModelZooMocks(page);
    await page.goto('/settings');

    // Navigate to AI Models tab
    const aiModelsTab = page
      .getByRole('tab', { name: /AI Models/i })
      .or(page.locator('button').filter({ hasText: 'AI MODELS' }));
    await aiModelsTab.click();
  });

  test('clicking Load button loads a model', async ({ page }) => {
    // Find an unloaded model (osnet-x0-25)
    const osnetModel = page.locator('[data-testid="model-card-osnet-x0-25"]');
    await expect(osnetModel).toBeVisible();

    // Click Load button
    const loadButton = osnetModel.getByRole('button', { name: /Load/i });
    await expect(loadButton).toBeVisible();

    // Intercept the API call
    const loadPromise = page.waitForRequest(
      (request) =>
        request.url().includes('/api/system/models/osnet-x0-25/load') &&
        request.method() === 'POST'
    );

    await loadButton.click();

    // Verify API was called
    const loadRequest = await loadPromise;
    expect(loadRequest).toBeTruthy();

    // Verify loading state is shown
    await expect(osnetModel.getByText(/Loading/i)).toBeVisible();
  });

  test('clicking Unload shows confirmation dialog', async ({ page }) => {
    // Find a loaded model (threat-detection-yolov8n)
    const threatModel = page.locator('[data-testid="model-card-threat-detection-yolov8n"]');
    await expect(threatModel).toBeVisible();

    // Click Unload button
    const unloadButton = threatModel.getByRole('button', { name: /Unload/i });
    await expect(unloadButton).toBeVisible();
    await unloadButton.click();

    // Verify confirmation dialog appears
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText(/Unload Model/i)).toBeVisible();
    await expect(dialog.getByText(/will need to reload/i)).toBeVisible();

    // Verify dialog has Cancel and Confirm buttons
    await expect(dialog.getByRole('button', { name: /Cancel/i })).toBeVisible();
    await expect(dialog.getByRole('button', { name: /Confirm|Unload/i })).toBeVisible();
  });

  test('confirming unload actually unloads the model', async ({ page }) => {
    // Find a loaded model (threat-detection-yolov8n)
    const threatModel = page.locator('[data-testid="model-card-threat-detection-yolov8n"]');

    // Click Unload button
    const unloadButton = threatModel.getByRole('button', { name: /Unload/i });
    await unloadButton.click();

    // Intercept the API call
    const unloadPromise = page.waitForRequest(
      (request) =>
        request.url().includes('/api/system/models/threat-detection-yolov8n/unload') &&
        request.method() === 'POST'
    );

    // Confirm unload in dialog
    const dialog = page.getByRole('dialog');
    const confirmButton = dialog.getByRole('button', { name: /Confirm|Unload/i });
    await confirmButton.click();

    // Verify API was called
    const unloadRequest = await unloadPromise;
    expect(unloadRequest).toBeTruthy();

    // Dialog should close
    await expect(dialog).not.toBeVisible();
  });

  test('canceling unload keeps model loaded', async ({ page }) => {
    // Find a loaded model (threat-detection-yolov8n)
    const threatModel = page.locator('[data-testid="model-card-threat-detection-yolov8n"]');

    // Click Unload button
    const unloadButton = threatModel.getByRole('button', { name: /Unload/i });
    await unloadButton.click();

    // Wait for dialog
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();

    // Click Cancel
    const cancelButton = dialog.getByRole('button', { name: /Cancel/i });
    await cancelButton.click();

    // Dialog should close
    await expect(dialog).not.toBeVisible();

    // Model should still show as loaded
    await expect(threatModel.getByText(/Loaded/i)).toBeVisible();
  });

  test('Reload button triggers unload then load', async ({ page }) => {
    // Find a loaded model (fashion-clip)
    const fashionModel = page.locator('[data-testid="model-card-fashion-clip"]');
    await expect(fashionModel).toBeVisible();

    // Click Reload button
    const reloadButton = fashionModel.getByRole('button', { name: /Reload/i });
    await expect(reloadButton).toBeVisible();

    // Intercept the reload API call
    const reloadPromise = page.waitForRequest(
      (request) =>
        request.url().includes('/api/system/models/fashion-clip/reload') &&
        request.method() === 'POST'
    );

    await reloadButton.click();

    // Verify API was called
    const reloadRequest = await reloadPromise;
    expect(reloadRequest).toBeTruthy();

    // Verify loading state is shown
    await expect(fashionModel.getByText(/Reloading|Loading/i)).toBeVisible();
  });
});

test.describe('Model Zoo Panel - Error Handling', () => {
  test('shows error toast when load fails', async ({ page }) => {
    await setupModelZooMocks(page, { loadError: true });
    await page.goto('/settings');

    // Navigate to AI Models tab
    const aiModelsTab = page
      .getByRole('tab', { name: /AI Models/i })
      .or(page.locator('button').filter({ hasText: 'AI MODELS' }));
    await aiModelsTab.click();

    // Find an unloaded model
    const osnetModel = page.locator('[data-testid="model-card-osnet-x0-25"]');
    await expect(osnetModel).toBeVisible();

    // Click Load button
    const loadButton = osnetModel.getByRole('button', { name: /Load/i });
    await loadButton.click();

    // Verify error toast appears
    const errorToast = page.getByRole('alert').or(page.locator('[data-testid="error-toast"]'));
    await expect(errorToast).toBeVisible();
    await expect(errorToast.getByText(/Insufficient VRAM|failed|error/i)).toBeVisible();
  });

  test('handles service unavailable gracefully', async ({ page }) => {
    await setupModelZooMocks(page, { serviceUnavailable: true });
    await page.goto('/settings');

    // Navigate to AI Models tab
    const aiModelsTab = page
      .getByRole('tab', { name: /AI Models/i })
      .or(page.locator('button').filter({ hasText: 'AI MODELS' }));
    await aiModelsTab.click();

    // Verify Model Zoo panel shows unavailable state
    const modelZooPanel = page.getByTestId('model-zoo-panel');
    await expect(modelZooPanel).toBeVisible();

    // Should show service unavailable message
    await expect(page.getByText(/Service Unavailable|unavailable|offline/i)).toBeVisible();

    // Load buttons should be disabled
    const loadButtons = page.getByRole('button', { name: /Load/i });
    const buttonCount = await loadButtons.count();

    // Either no load buttons, or they're all disabled
    if (buttonCount > 0) {
      for (let i = 0; i < buttonCount; i++) {
        await expect(loadButtons.nth(i)).toBeDisabled();
      }
    }
  });

  test('auto-refreshes model status every 5 seconds', async ({ page }) => {
    await setupModelZooMocks(page);
    await page.goto('/settings');

    // Navigate to AI Models tab
    const aiModelsTab = page
      .getByRole('tab', { name: /AI Models/i })
      .or(page.locator('button').filter({ hasText: 'AI MODELS' }));
    await aiModelsTab.click();

    // Track API calls to /api/system/models
    let modelApiCalls = 0;
    await page.route('**/api/system/models', async (route) => {
      modelApiCalls++;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockModelListResponse),
      });
    });

    // Wait for initial load
    await page.waitForTimeout(1000);
    const initialCalls = modelApiCalls;

    // Wait 6 seconds (one refresh cycle + buffer)
    await page.waitForTimeout(6000);

    // Should have at least one more API call (auto-refresh)
    expect(modelApiCalls).toBeGreaterThan(initialCalls);
  });
});

test.describe('Model Zoo Panel - VRAM Display', () => {
  test('VRAM bar color changes based on utilization', async ({ page }) => {
    // Set up with high VRAM usage
    const highVramMock = {
      ...mockVramSummaryResponse,
      gpus: [
        {
          gpu_id: 0,
          service: 'ai-enrichment',
          budget_mb: 6800,
          used_mb: 6500, // ~95% usage - should be red
          available_mb: 300,
          utilization_percent: 95.6,
          loaded_models: ['fashion-clip', 'vehicle-segment-classification', 'xclip-base'],
        },
        {
          gpu_id: 1,
          service: 'ai-enrichment-light',
          budget_mb: 1200,
          used_mb: 900, // 75% usage - should be yellow
          available_mb: 300,
          utilization_percent: 75.0,
          loaded_models: ['threat-detection-yolov8n', 'vitpose-small', 'osnet-x0-25'],
        },
      ],
    };

    await setupModelZooMocks(page, { vram: highVramMock });
    await page.goto('/settings');

    // Navigate to AI Models tab
    const aiModelsTab = page
      .getByRole('tab', { name: /AI Models/i })
      .or(page.locator('button').filter({ hasText: 'AI MODELS' }));
    await aiModelsTab.click();

    // GPU 0 VRAM bar should indicate high/critical usage (red)
    const gpu0VramBar = page.getByTestId('vram-bar-gpu-0');
    await expect(gpu0VramBar).toBeVisible();

    // Check for warning/critical color class or style
    // The actual implementation might use different approaches:
    // - CSS class like 'bg-red-500' or 'vram-critical'
    // - Inline style with color
    // - aria-label indicating status
    const gpu0BarFill = gpu0VramBar.locator('[data-testid="vram-bar-fill"]');
    await expect(gpu0BarFill).toHaveAttribute(
      'class',
      /red|danger|critical/i
    );

    // GPU 1 VRAM bar should indicate medium usage (yellow/orange)
    const gpu1VramBar = page.getByTestId('vram-bar-gpu-1');
    const gpu1BarFill = gpu1VramBar.locator('[data-testid="vram-bar-fill"]');
    await expect(gpu1BarFill).toHaveAttribute(
      'class',
      /yellow|orange|warning/i
    );
  });

  test('displays loaded model count in VRAM summary', async ({ page }) => {
    await setupModelZooMocks(page);
    await page.goto('/settings');

    // Navigate to AI Models tab
    const aiModelsTab = page
      .getByRole('tab', { name: /AI Models/i })
      .or(page.locator('button').filter({ hasText: 'AI MODELS' }));
    await aiModelsTab.click();

    // GPU 0 has 1 loaded model (fashion-clip)
    const gpu0Section = page.getByTestId('gpu-0-section');
    await expect(gpu0Section.getByText(/1.*loaded|loaded.*1/i)).toBeVisible();

    // GPU 1 has 2 loaded models (threat-detection-yolov8n, vitpose-small)
    const gpu1Section = page.getByTestId('gpu-1-section');
    await expect(gpu1Section.getByText(/2.*loaded|loaded.*2/i)).toBeVisible();

    // Total section shows 3 models loaded
    await expect(page.getByText(/3.*models.*loaded|Total.*3/i)).toBeVisible();
  });
});

test.describe('Model Zoo Panel - Model Card Details', () => {
  test.beforeEach(async ({ page }) => {
    await setupModelZooMocks(page);
    await page.goto('/settings');

    // Navigate to AI Models tab
    const aiModelsTab = page
      .getByRole('tab', { name: /AI Models/i })
      .or(page.locator('button').filter({ hasText: 'AI MODELS' }));
    await aiModelsTab.click();
  });

  test('shows estimated VRAM for unloaded models', async ({ page }) => {
    // osnet-x0-25 is unloaded - should show estimated VRAM
    const osnetModel = page.locator('[data-testid="model-card-osnet-x0-25"]');
    await expect(osnetModel).toBeVisible();

    // Should show estimated VRAM: ~150 MB
    await expect(osnetModel.getByText(/~?150.*MB|est/i)).toBeVisible();
  });

  test('shows last used time for loaded models', async ({ page }) => {
    // threat-detection-yolov8n was last used at 2025-01-31T10:30:00Z
    const threatModel = page.locator('[data-testid="model-card-threat-detection-yolov8n"]');
    await expect(threatModel).toBeVisible();

    // Should show last used time (format may vary: "Last used: X ago" or timestamp)
    await expect(threatModel.getByText(/last used|10:30/i)).toBeVisible();
  });

  test('shows service name on model cards', async ({ page }) => {
    // GPU 0 models should show ai-enrichment service
    const fashionModel = page.locator('[data-testid="model-card-fashion-clip"]');
    await expect(fashionModel.getByText(/ai-enrichment(?!-light)/)).toBeVisible();

    // GPU 1 models should show ai-enrichment-light service
    const threatModel = page.locator('[data-testid="model-card-threat-detection-yolov8n"]');
    await expect(threatModel.getByText(/ai-enrichment-light/)).toBeVisible();
  });
});

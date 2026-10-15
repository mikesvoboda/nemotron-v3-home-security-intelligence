/**
 * Uplevel F2.3 batch FE-4 — Processing Settings, Batch Status Monitor, Rate/Queue/Detection
 * Panels, and Severity Thresholds Editor (`F-221`, `F-222`, `F-225`, `F-226`, `/settings/processing`).
 *
 * Inventory rows covered:
 * - F-221: Processing › Processing settings form (`/settings/processing`,
 *          `GET /api/system/config`, `PATCH /api/system/config`)
 * - F-222: Processing › Batch status monitor (`/settings/processing`, `GET /api/system/pipeline`)
 * - F-225: Processing › Rate limiting, queue and detection-threshold panels (`/settings/processing`,
 *          `GET /api/v1/settings`, `PATCH /api/v1/settings`)
 * - F-226: Processing › Severity thresholds editor (`/settings/processing`,
 *          `GET /api/system/severity`, `PUT /api/system/severity`)
 *
 * Key architectural details verified against the tree:
 * - `system.py:_write_runtime_env` (`backend/api/routes/system.py:2563-2595`) and
 *   `settings_api.py:_write_runtime_env` (`backend/api/routes/settings_api.py:191-204`)
 *   both persist to `HSI_RUNTIME_ENV_PATH` (`/tmp/runtime.env` in `docker-compose.ci.yml:157`)
 *   and call `get_settings.cache_clear()`. Every test snapshots the backend state before
 *   mutating and restores it in `finally`.
 * - Both `DetectionThresholdsPanel.tsx:206,216` and `SeverityThresholds.tsx:490,500` use
 *   `data-testid="save-thresholds-button"` and `data-testid="reset-thresholds-button"`.
 *   All button locators are therefore scoped to `detection-thresholds-card` or
 *   `severity-thresholds-card`.
 */
import { expect, test } from '../guard';
import {
  apiPath,
  assertGuardSurvives,
  readHarness,
  settledGoto,
  signIn,
  type Harness,
} from './harness';

const harness = readHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

test.describe('FE-4 processing settings & thresholds golden path (F-221, F-222, F-225, F-226)', () => {
  test.setTimeout(90_000);

  test('F-221: Processing settings form loads GET /api/system/config, previews batch presets, resets, and saves via PATCH /api/system/config', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    // 1. API-first check: GET /api/system/config (backend/api/routes/system.py:2474-2526)
    const beforeRes = await api.getJson('/api/system/config');
    expect(beforeRes.status, 'GET /api/system/config answers 200').toBe(200);
    const before = {
      batch_window_seconds: Number(beforeRes.body?.batch_window_seconds),
      batch_idle_timeout_seconds: Number(beforeRes.body?.batch_idle_timeout_seconds),
      retention_days: Number(beforeRes.body?.retention_days),
      log_retention_days: Number(beforeRes.body?.log_retention_days),
      detection_confidence_threshold: Number(beforeRes.body?.detection_confidence_threshold),
      fast_path_confidence_threshold: Number(beforeRes.body?.fast_path_confidence_threshold),
      fast_path_enabled: Boolean(beforeRes.body?.fast_path_enabled),
    };

    // Pick a preset distinct from the current batch window (BatchPresetSelector.tsx:73-122)
    const targetPreset =
      before.batch_window_seconds === 180
        ? { name: /Real-time/i, window: 30, idle: 10 }
        : { name: /Efficient/i, window: 180, idle: 60 };

    try {
      await settledGoto(page, h, '/settings/processing', (p) =>
        p.getByTestId('batch-preset-selector')
      );

      // 2. Verify the sliders and preset/tooltip panels mirror GET /api/system/config
      const windowSlider = page.getByLabel('Batch window duration in seconds', { exact: true });
      const idleSlider = page.getByLabel('Batch idle timeout in seconds', { exact: true });
      const retentionSlider = page.getByLabel('Retention period in days', { exact: true });
      const logRetentionSlider = page.getByLabel('Log retention period in days', { exact: true });
      const detSlider = page.getByLabel('Detection confidence threshold', { exact: true });
      const fastPathSlider = page.getByLabel('Fast-path confidence threshold', { exact: true });

      await expect(windowSlider).toHaveValue(String(before.batch_window_seconds));
      await expect(idleSlider).toHaveValue(String(before.batch_idle_timeout_seconds));
      await expect(retentionSlider).toHaveValue(String(before.retention_days));
      await expect(logRetentionSlider).toHaveValue(String(before.log_retention_days));
      await expect(detSlider).toHaveValue(String(before.detection_confidence_threshold));

      // ruling 168: the fast-path threshold slider is gated on the switch. The
      // switch is a role=switch button (its testid lands on the real node), so it
      // is the anchor; the threshold's presence mirrors the fetched enable flag.
      const fastPathSwitch = page.getByTestId('switch-fast-path-enabled');
      await expect(fastPathSwitch).toHaveAttribute(
        'aria-checked',
        String(before.fast_path_enabled)
      );
      if (before.fast_path_enabled) {
        await expect(fastPathSlider).toHaveValue(String(before.fast_path_confidence_threshold));
      } else {
        // Anchor the absence: the switch is present (gate ran) yet the slider is not.
        await expect(fastPathSlider).toHaveCount(0);
      }

      await expect(page.getByTestId('batch-settings-tooltips')).toBeVisible();
      await expect(page.getByTestId('batch-latency-preview')).toBeVisible();

      const saveBtn = page.getByRole('button', { name: /Save Changes/i });
      const resetBtn = page.getByTestId('processing-settings-reset');
      await expect(saveBtn).toBeDisabled();
      await expect(resetBtn).toBeDisabled();

      // 3. Select target preset -> verify sliders update -> click Reset -> verify revert
      const presetSelector = page.getByTestId('batch-preset-selector');
      await presetSelector.getByRole('button', { name: targetPreset.name }).click();
      await expect(windowSlider).toHaveValue(String(targetPreset.window));
      await expect(idleSlider).toHaveValue(String(targetPreset.idle));
      await expect(saveBtn).toBeEnabled();
      await expect(resetBtn).toBeEnabled();

      await resetBtn.click();
      await expect(windowSlider).toHaveValue(String(before.batch_window_seconds));
      await expect(idleSlider).toHaveValue(String(before.batch_idle_timeout_seconds));
      await expect(saveBtn).toBeDisabled();
      await expect(resetBtn).toBeDisabled();

      // 4. Select target preset again and click Save Changes -> PATCH /api/system/config
      await presetSelector.getByRole('button', { name: targetPreset.name }).click();
      const patchPromise = page.waitForResponse(
        (res) => apiPath(res.url()) === '/api/system/config' && res.request().method() === 'PATCH'
      );
      await saveBtn.click();
      const patchRes = await patchPromise;
      expect(patchRes.status(), 'PATCH /api/system/config answers 200').toBe(200);

      await expect(page.getByText('Settings saved successfully!')).toBeVisible();

      const afterRes = await api.getJson('/api/system/config');
      expect(afterRes.status).toBe(200);
      expect(afterRes.body?.batch_window_seconds).toBe(targetPreset.window);
      expect(afterRes.body?.batch_idle_timeout_seconds).toBe(targetPreset.idle);

      await assertGuardSurvives(page, h);
    } finally {
      const restoreRes = await api.send('/api/system/config', 'PATCH', before);
      expect(restoreRes.status, 'restore /api/system/config answers 200').toBe(200);
    }
  });

  test('F-222: Batch status monitor expands and displays live metrics from GET /api/system/pipeline', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    // 1. API-first check: GET /api/system/pipeline (backend/api/routes/system.py:4207-4290)
    const pipeRes = await api.getJson('/api/system/pipeline');
    expect(pipeRes.status, 'GET /api/system/pipeline answers 200').toBe(200);
    const batchAgg = pipeRes.body?.batch_aggregator as {
      active_batches: number;
      batch_window_seconds: number;
      idle_timeout_seconds: number;
    };
    expect(typeof batchAgg?.active_batches).toBe('number');
    expect(batchAgg?.batch_window_seconds).toBeGreaterThan(0);

    // 2. Navigate to /settings/processing and inspect collapsed BatchStatusMonitor
    await settledGoto(page, h, '/settings/processing', (p) =>
      p.getByTestId('batch-status-monitor')
    );

    const monitor = page.getByTestId('batch-status-monitor');
    await expect(monitor).toBeVisible();
    await expect(page.getByTestId('batch-health-indicator')).toBeVisible();
    await expect(monitor.getByText('Active Batches')).toHaveCount(0);

    // 3. Expand disclosure -> triggers GET /api/system/pipeline (useBatchAggregatorStatus.ts:116)
    const pipelineFetchPromise = page.waitForResponse(
      (res) => apiPath(res.url()) === '/api/system/pipeline' && res.request().method() === 'GET'
    );
    await monitor.getByRole('button', { name: /Batch Status/i }).click();
    const browserPipeRes = await pipelineFetchPromise;
    expect(browserPipeRes.status()).toBe(200);

    // 4. Verify expanded stat cards and health status bar (BatchStatusMonitor.tsx:95-153)
    await expect(monitor.getByText('Active Batches')).toBeVisible();
    await expect(monitor.getByText('Avg Age')).toBeVisible();
    await expect(monitor.getByText('Detections')).toBeVisible();
    await expect(monitor.getByText('Window')).toBeVisible();
    await expect(monitor).toContainText(`${batchAgg.batch_window_seconds}s`);
    await expect(monitor.getByText('Health Status')).toBeVisible();

    await assertGuardSurvives(page, h);
  });

  test('F-225: Rate limiting, queue settings, and detection-thresholds panels mirror GET /api/v1/settings and persist via PATCH /api/v1/settings', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    // 1. API-first check: GET /api/v1/settings (backend/api/routes/settings_api.py:95-156)
    const beforeRes = await api.getJson('/api/v1/settings');
    expect(beforeRes.status, 'GET /api/v1/settings answers 200').toBe(200);

    const beforeRate = beforeRes.body?.rate_limiting as {
      enabled: boolean;
      requests_per_minute: number;
      burst_size: number;
    };
    const beforeQueue = beforeRes.body?.queue as {
      max_size: number;
      backpressure_threshold: number;
    };
    const beforeDet = beforeRes.body?.detection as {
      confidence_threshold: number;
      fast_path_enabled: boolean;
      fast_path_threshold: number;
    };

    try {
      await settledGoto(page, h, '/settings/processing', (p) =>
        p.getByTestId('rate-limiting-settings')
      );

      // 2. Verify RateLimitingSettings (RateLimitingSettings.tsx:56-126)
      const ratePanel = page.getByTestId('rate-limiting-settings');
      await expect(ratePanel).toBeVisible();
      await expect(page.getByTestId('input-requests-per-minute')).toHaveValue(
        String(beforeRate.requests_per_minute)
      );
      await expect(page.getByTestId('input-burst-size')).toHaveValue(String(beforeRate.burst_size));
      await expect(page.getByTestId('switch-rate-limit-enabled')).toHaveAttribute(
        'aria-checked',
        String(beforeRate.enabled)
      );

      // 3. Verify QueueSettings (QueueSettings.tsx:45-87)
      const queuePanel = page.getByTestId('queue-settings');
      await expect(queuePanel).toBeVisible();
      const maxQueueInput = page.getByTestId('input-max-queue-size');
      const backpressureInput = page.getByTestId('input-backpressure-threshold');
      await expect(maxQueueInput).toHaveValue(String(beforeQueue.max_size));
      await expect(backpressureInput).toHaveValue(
        String(Math.round(beforeQueue.backpressure_threshold * 100))
      );

      // Step burst_size by 1 via keyboard (ArrowUp/ArrowDown fires a single change event
      // without clearing the NumberInput to empty/NaN while updateSettingsMutation.isPending)
      const targetBurst =
        beforeRate.burst_size >= 100 ? beforeRate.burst_size - 1 : beforeRate.burst_size + 1;
      const burstStepKey = beforeRate.burst_size >= 100 ? 'ArrowDown' : 'ArrowUp';
      const burstPatchPromise = page.waitForResponse(
        (res) => apiPath(res.url()) === '/api/v1/settings' && res.request().method() === 'PATCH'
      );
      const burstInput = page.getByTestId('input-burst-size');
      await burstInput.focus();
      await page.keyboard.press(burstStepKey);
      const burstPatchRes = await burstPatchPromise;
      expect(burstPatchRes.status(), 'PATCH /api/v1/settings for rate_limiting answers 200').toBe(
        200
      );

      const afterBurst = await api.getJson('/api/v1/settings');
      expect(afterBurst.body?.rate_limiting?.burst_size).toBe(targetBurst);

      // 4. Verify & update DetectionThresholdsPanel (DetectionThresholdsPanel.tsx:86-205)
      const detCard = page.getByTestId('detection-thresholds-card');
      await expect(detCard).toBeVisible();
      const confSlider = detCard.getByTestId('confidence-slider');
      const confValue = detCard.getByTestId('confidence-value');
      const fastPathValue = detCard.getByTestId('fast-path-value');
      const detSaveBtn = detCard.getByTestId('save-thresholds-button');

      await expect(confValue).toHaveText(`${(beforeDet.confidence_threshold * 100).toFixed(0)}%`);
      await expect(fastPathValue).toHaveText(
        `${(beforeDet.fast_path_threshold * 100).toFixed(0)}%`
      );
      await expect(detSaveBtn).toBeDisabled();

      const stepKey = beforeDet.confidence_threshold >= 0.9 ? 'ArrowLeft' : 'ArrowRight';
      const expectedConf = Number(
        (
          beforeDet.confidence_threshold + (beforeDet.confidence_threshold >= 0.9 ? -0.05 : 0.05)
        ).toFixed(2)
      );

      await confSlider.focus();
      await page.keyboard.press(stepKey);
      await expect(confValue).toHaveText(`${(expectedConf * 100).toFixed(0)}%`);
      await expect(detSaveBtn).toBeEnabled();

      const detPatchPromise = page.waitForResponse(
        (res) => apiPath(res.url()) === '/api/v1/settings' && res.request().method() === 'PATCH'
      );
      await detSaveBtn.click();
      const detPatchRes = await detPatchPromise;
      expect(detPatchRes.status(), 'PATCH /api/v1/settings for detection answers 200').toBe(200);
      await expect(page.getByText('Detection thresholds saved successfully!')).toBeVisible();

      const afterDet = await api.getJson('/api/v1/settings');
      expect(afterDet.body?.detection?.confidence_threshold).toBeCloseTo(expectedConf, 2);

      await assertGuardSurvives(page, h);
    } finally {
      const restoreRes = await api.send('/api/v1/settings', 'PATCH', {
        rate_limiting: beforeRate,
        queue: beforeQueue,
        detection: {
          confidence_threshold: beforeDet.confidence_threshold,
          fast_path_threshold: beforeDet.fast_path_threshold,
        },
      });
      expect(restoreRes.status, 'restore /api/v1/settings answers 200').toBe(200);
    }
  });

  test('F-226: Severity thresholds editor loads GET /api/system/severity, resets edits, and persists via PUT /api/system/severity', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    // 1. API-first check: GET /api/system/severity (backend/api/routes/system.py:3506-3555)
    const beforeRes = await api.getJson('/api/system/severity');
    expect(beforeRes.status, 'GET /api/system/severity answers 200').toBe(200);
    const before = beforeRes.body?.thresholds as {
      low_max: number;
      medium_max: number;
      high_max: number;
    };
    expect(before.low_max).toBeLessThan(before.medium_max);
    expect(before.medium_max).toBeLessThan(before.high_max);

    const stepDown = before.low_max > 5;
    const targetLowMax = stepDown ? before.low_max - 1 : before.low_max + 1;
    const stepKey = stepDown ? 'ArrowLeft' : 'ArrowRight';

    try {
      await settledGoto(page, h, '/settings/processing', (p) =>
        p.getByTestId('severity-thresholds-card')
      );

      // Scope to severity-thresholds-card (SeverityThresholds.tsx:161-404)
      const card = page.getByTestId('severity-thresholds-card');
      await expect(card).toBeVisible();
      await expect(card.getByText('Risk Score Thresholds')).toBeVisible();

      const lowSlider = card.getByTestId('low-max-slider');
      const medSlider = card.getByTestId('medium-max-slider');
      const highSlider = card.getByTestId('high-max-slider');
      const saveBtn = card.getByTestId('save-thresholds-button');
      const resetBtn = card.getByTestId('reset-thresholds-button');

      await expect(lowSlider).toHaveValue(String(before.low_max));
      await expect(medSlider).toHaveValue(String(before.medium_max));
      await expect(highSlider).toHaveValue(String(before.high_max));
      await expect(saveBtn).toBeDisabled();
      await expect(resetBtn).toBeDisabled();

      // 2. Step low-max-slider and test Reset button
      await lowSlider.focus();
      await page.keyboard.press(stepKey);
      await expect(lowSlider).toHaveValue(String(targetLowMax));
      await expect(saveBtn).toBeEnabled();
      await expect(resetBtn).toBeEnabled();

      await resetBtn.click();
      await expect(lowSlider).toHaveValue(String(before.low_max));
      await expect(saveBtn).toBeDisabled();
      await expect(resetBtn).toBeDisabled();

      // 3. Step low-max-slider again and click Save Thresholds -> PUT /api/system/severity
      await lowSlider.focus();
      await page.keyboard.press(stepKey);
      await expect(lowSlider).toHaveValue(String(targetLowMax));

      const putPromise = page.waitForResponse(
        (res) => apiPath(res.url()) === '/api/system/severity' && res.request().method() === 'PUT'
      );
      await saveBtn.click();
      const putRes = await putPromise;
      expect(putRes.status(), 'PUT /api/system/severity answers 200').toBe(200);

      await expect(card.getByText('Thresholds saved successfully!')).toBeVisible();

      const afterRes = await api.getJson('/api/system/severity');
      expect(afterRes.status).toBe(200);
      expect(afterRes.body?.thresholds?.low_max).toBe(targetLowMax);
      expect(afterRes.body?.thresholds?.medium_max).toBe(before.medium_max);
      expect(afterRes.body?.thresholds?.high_max).toBe(before.high_max);

      await assertGuardSurvives(page, h);
    } finally {
      const restoreRes = await api.send('/api/system/severity', 'PUT', before);
      expect(restoreRes.status, 'restore /api/system/severity answers 200').toBe(200);
    }
  });
});

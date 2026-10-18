/**
 * Uplevel F2.3 batch FE-4 — Cameras › Activity baseline modal (`F-209`, `/settings/cameras`).
 *
 * Inventory row F-209:
 *   Surface: `/settings/cameras` (`frontend/src/components/settings/CamerasSettings.tsx:644-652`, `:1349-1413`)
 *   Component: `CameraBaselinePanel` (`frontend/src/components/analytics/CameraBaselinePanel.tsx:120-256`) +
 *              `ActivityHeatmap` (`frontend/src/components/analytics/ActivityHeatmap.tsx:125-263`)
 *   API: `GET /api/cameras/{camera_id}/baseline` (`backend/api/routes/cameras.py:1526-1575`),
 *        `GET /api/cameras/{camera_id}/baseline/activity` (`backend/api/routes/cameras.py:1616-1682`)
 *
 * Nuances verified against the tree:
 * 1. `feature_check.py:2082-2086` (`smoke()`) drops an image into `harness-smoke` before
 *    `golden()` runs, so `DetectorClient` (`backend/services/detector_client.py:1360-1365`)
 *    records `ActivityBaseline` + `ClassBaseline` rows for `harness_smoke` (`data_points >= 2`,
 *    `entries.length >= 1`). Untouched scenario cameras have `data_points === 0` and render
 *    the `"No Baseline Data Yet"` empty state (`CameraBaselinePanel.tsx:163-183`).
 * 2. `object_baselines` is returned by `GET /api/cameras/{camera_id}/baseline`
 *    (`BaselineSummaryResponse.object_baselines`, `backend/api/schemas/baseline.py:181-185`),
 *    and asserted in the API leg, though `CameraBaselinePanel.tsx:188-262` only renders
 *    `data_points`, `baseline_established`, `current_deviation`, and `ActivityHeatmap`.
 * 3. `get_camera_baseline` (`backend/api/routes/cameras.py:1554` ->
 *    `BaselineService.get_current_deviation`, `backend/services/baseline.py:827`) and
 *    `get_camera_activity_baseline` (`cameras.py:1659`) both read `baseline_service.min_samples`
 *    (default `10`). Temporarily lowering `min_samples: 1` on the global `BaselineService`
 *    via `PATCH /api/system/anomaly-config` (`backend/api/routes/system.py:2782-2825`) lets
 *    the single smoke detection satisfy `sample_count >= min_samples` so
 *    `data-testid="deviation-status"` (`CameraBaselinePanel.tsx:214`) and active heatmap cells
 *    (`ActivityHeatmap.tsx:168, 203-207`) render with `"average activity"`; `finally` restores
 *    the prior `min_samples` and `threshold_stdev` from `GET /api/system/anomaly-config`
 *    (`system.py:2747-2779`).
 */
import { expect, test } from '../guard';
import {
  apiPath,
  assertGuardSurvivesCameras as assertGuardSurvives,
  listCameras,
  readHarness,
  settledGoto,
  signIn,
  type CameraRecord,
  type Harness,
} from '../harness';

const harness = readHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

test.describe('FE-4 camera activity baseline modal golden path (F-209)', () => {
  test.setTimeout(120_000);

  test('F-209: Activity Baseline modal renders GET /api/cameras/{id}/baseline and /baseline/activity (populated + empty states)', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    const cameras = await listCameras(api);
    expect(cameras.length).toBeGreaterThan(0);

    // 1. Inspect baseline state across seeded cameras via GET /api/cameras/{id}/baseline
    let populatedCam: CameraRecord | null = null;
    let emptyCam: CameraRecord | null = null;

    for (const cam of cameras) {
      const baseRes = await api.getJson(`/api/cameras/${cam.id}/baseline`);
      expect(baseRes.status, `GET /api/cameras/${cam.id}/baseline answers 200`).toBe(200);
      const actRes = await api.getJson(`/api/cameras/${cam.id}/baseline/activity`);
      expect(actRes.status, `GET /api/cameras/${cam.id}/baseline/activity answers 200`).toBe(200);

      if (
        !populatedCam &&
        Number(baseRes.body?.data_points ?? 0) > 0 &&
        Array.isArray(actRes.body?.entries) &&
        actRes.body.entries.length > 0
      ) {
        populatedCam = cam;
      } else if (!emptyCam && Number(baseRes.body?.data_points ?? 0) === 0) {
        emptyCam = cam;
      }
    }

    const targetCam = populatedCam ?? cameras[0];
    let priorAnomalyCfg: { threshold_stdev: number; min_samples: number } | null = null;

    try {
      if (populatedCam) {
        // Read global BaselineService config (system.py:2747-2779) and temporarily lower
        // min_samples to 1 via PATCH /api/system/anomaly-config (system.py:2782-2825) so
        // get_camera_baseline and get_camera_activity_baseline treat the smoke detection
        // (sample_count >= 1) as sufficient samples.
        const beforeCfgRes = await api.getJson('/api/system/anomaly-config');
        expect(beforeCfgRes.status, 'GET /api/system/anomaly-config answers 200').toBe(200);
        priorAnomalyCfg = {
          threshold_stdev: Number(beforeCfgRes.body?.threshold_stdev ?? 2.0),
          min_samples: Number(beforeCfgRes.body?.min_samples ?? 10),
        };

        const cfgPatch = await api.send('/api/system/anomaly-config', 'PATCH', {
          min_samples: 1,
        });
        expect(cfgPatch.status, 'PATCH /api/system/anomaly-config answers 200').toBe(200);
        expect(cfgPatch.body?.min_samples).toBe(1);
      }

      // Re-read authoritative API payloads for targetCam
      const baselineRes = await api.getJson(`/api/cameras/${targetCam.id}/baseline`);
      expect(baselineRes.status).toBe(200);
      expect(baselineRes.body?.camera_id).toBe(targetCam.id);
      expect(typeof baselineRes.body?.hourly_patterns).toBe('object');
      expect(typeof baselineRes.body?.daily_patterns).toBe('object');
      expect(typeof baselineRes.body?.object_baselines).toBe('object');

      const activityRes = await api.getJson(`/api/cameras/${targetCam.id}/baseline/activity`);
      expect(activityRes.status).toBe(200);
      expect(activityRes.body?.camera_id).toBe(targetCam.id);
      expect(Array.isArray(activityRes.body?.entries)).toBe(true);

      // 2. Navigate to /settings/cameras and open Activity Baseline modal for targetCam
      await settledGoto(page, h, '/settings/cameras', (p) =>
        p.getByTestId(`baseline-${targetCam.id}`)
      );

      const baselineFetchPromise = page.waitForResponse(
        (res) =>
          apiPath(res.url()) === `/api/cameras/${targetCam.id}/baseline` &&
          res.request().method() === 'GET'
      );
      const activityFetchPromise = page.waitForResponse(
        (res) =>
          apiPath(res.url()) === `/api/cameras/${targetCam.id}/baseline/activity` &&
          res.request().method() === 'GET'
      );

      await page.getByTestId(`baseline-${targetCam.id}`).click();
      await Promise.all([baselineFetchPromise, activityFetchPromise]);

      const panel = page.getByTestId('camera-baseline-panel');
      await expect(panel).toBeVisible();
      await expect(panel).toContainText(targetCam.name);

      if (populatedCam) {
        const dataPoints = Number(baselineRes.body?.data_points);
        const entriesCount = (activityRes.body?.entries as unknown[]).length;

        // Header data points count (CameraBaselinePanel.tsx:198)
        await expect(panel).toContainText(`${dataPoints} data points`);

        // Deviation status card (CameraBaselinePanel.tsx:211-253) when current_deviation !== null
        if (baselineRes.body?.current_deviation !== null) {
          const devCard = page.getByTestId('deviation-status');
          await expect(devCard).toBeVisible();
          await expect(devCard).toContainText('Score:');
        }

        // Weekly Activity Pattern heatmap (ActivityHeatmap.tsx:125-226)
        await expect(panel).toContainText('Weekly Activity Pattern');
        if (!activityRes.body?.learning_complete) {
          await expect(panel).toContainText(`Learning (${entriesCount} / 168 slots)`);
        }

        // Verify 168 gridcells (7 days x 24 hours) and check the active slot's aria-label
        await expect(page.getByTestId('heatmap-cell-0-0')).toBeVisible();
        await expect(page.getByTestId('heatmap-cell-6-23')).toBeVisible();
        const firstEntry = activityRes.body.entries[0] as {
          day_of_week: number;
          hour: number;
          sample_count: number;
        };
        const activeCell = page.getByTestId(
          `heatmap-cell-${firstEntry.day_of_week}-${firstEntry.hour}`
        );
        await expect(activeCell).toBeVisible();
        await expect(activeCell).toHaveAttribute('aria-label', /average activity/);
      } else {
        // Empty state when no detections have been recorded (CameraBaselinePanel.tsx:163-183)
        await expect(panel).toContainText('No Baseline Data Yet');
      }

      // Close modal via header close button (CamerasSettings.tsx:1368-1374)
      await page.getByRole('button', { name: 'Close modal' }).click();
      await expect(panel).toHaveCount(0);

      // 3. Also verify empty baseline state on an untouched camera if both populated & empty exist
      if (populatedCam && emptyCam) {
        await page.getByTestId(`baseline-${emptyCam.id}`).click();
        const emptyPanel = page.getByTestId('camera-baseline-panel');
        await expect(emptyPanel).toBeVisible();
        await expect(emptyPanel).toContainText(emptyCam.name);
        await expect(emptyPanel).toContainText('No Baseline Data Yet');
        await page.getByRole('button', { name: 'Close modal' }).click();
        await expect(emptyPanel).toHaveCount(0);
      }

      await assertGuardSurvives(page, h);
    } finally {
      if (priorAnomalyCfg) {
        const restoreRes = await api.send('/api/system/anomaly-config', 'PATCH', priorAnomalyCfg);
        expect(restoreRes.status, 'restore /api/system/anomaly-config answers 200').toBe(200);
      }
    }
  });
});

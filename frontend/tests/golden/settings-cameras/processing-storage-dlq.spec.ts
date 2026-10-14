/**
 * Uplevel F2.3 batch FE-4 — Storage Dashboard, Cleanup Preview, Clear Old Data,
 * and Dead-Letter Queue Monitor / Actions (`F-223`, `F-224`, `F-228`, `F-229`, `/settings/processing`).
 *
 * Inventory rows covered:
 * - F-223: Processing › Storage dashboard and cleanup preview (`/settings/processing`,
 *          `GET /api/system/storage`, `POST /api/system/cleanup?dry_run=true`)
 * - F-224: Processing › Run cleanup / Clear old data (`/settings/processing`,
 *          `POST /api/system/cleanup`)
 * - F-228: Processing › Dead-letter queue monitor (`/settings/processing`,
 *          `GET /api/dlq/stats`, `GET /api/dlq/jobs/{queue_name}`)
 * - F-229: Processing › DLQ Requeue all / Clear (`/settings/processing`,
 *          `POST /api/dlq/requeue-all/{queue_name}`, `DELETE /api/dlq/{queue_name}`)
 *
 * Key architectural details verified against the tree:
 * - `/settings/processing` mounts TWO `'Preview Cleanup'` buttons: one inside
 *   `StorageDashboard.tsx:226` (`.first()`) and one inside `CleanupPreviewPanel.tsx:152`
 *   (`.nth(1)`). F-223 drives both and verifies both preview surfaces against
 *   `POST /api/system/cleanup?dry_run=true`.
 * - For F-224, `Clear Old Data` (`ProcessingSettings.tsx:459-486`) triggers
 *   `POST /api/system/cleanup` (`dry_run=false`, `backend/api/routes/system.py:3307-3414`),
 *   which deletes rows older than `retention_days` (default 30 days, leaving all current
 *   feature-check rows untouched) and renders the `'Cleanup Complete'` breakdown card.
 * - For F-228 and F-229, on the healthy fake-AI CI stack no jobs fail into Redis
 *   `dlq:detection_queue` or `dlq:analysis_queue`, and there is no HTTP API route to seed
 *   failed DLQ jobs (`guard.ts` forbids `page.route` mocking). In `DlqMonitor.tsx:261`,
 *   `if (count === 0 && !queueState.expanded) return null;` hides the per-queue rows and
 *   their `Requeue All` / `Clear All` buttons when `count === 0`. The spec therefore proves
 *   all 4 DLQ backend endpoints (`GET /api/dlq/stats`, `GET /api/dlq/jobs/{queue_name}`,
 *   `POST /api/dlq/requeue-all/{queue_name}`, `DELETE /api/dlq/{queue_name}`) directly via
 *   the API leg and verifies the `DlqMonitor` empty state + live refresh in the UI leg.
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

test.describe('FE-4 storage, cleanup & dead-letter queue golden path (F-223, F-224, F-228, F-229)', () => {
  test('F-223: StorageDashboard and CleanupPreviewPanel render GET /api/system/storage and run POST /api/system/cleanup?dry_run=true', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    // 1. API-first check: GET /api/system/storage & POST /api/system/cleanup?dry_run=true
    // (backend/api/routes/system.py:3725-3825, 3307-3414)
    const storageRes = await api.getJson('/api/system/storage');
    expect(storageRes.status, 'GET /api/system/storage answers 200').toBe(200);
    expect(Number(storageRes.body?.disk_total_bytes)).toBeGreaterThan(0);
    expect(typeof storageRes.body?.events_count).toBe('number');
    expect(typeof storageRes.body?.detections_count).toBe('number');

    const previewRes = await api.send('/api/system/cleanup?dry_run=true', 'POST');
    expect(previewRes.status, 'POST /api/system/cleanup?dry_run=true answers 200').toBe(200);
    expect(previewRes.body?.dry_run).toBe(true);
    const retentionDays = Number(previewRes.body?.retention_days);
    expect(retentionDays).toBeGreaterThan(0);

    // 2. Navigate to /settings/processing and verify StorageDashboard (StorageDashboard.tsx:46-260)
    await settledGoto(page, h, '/settings/processing', (p) =>
      p.getByText('Disk Usage', { exact: true })
    );

    await expect(page.getByText('Disk Usage', { exact: true })).toBeVisible();
    await expect(page.getByText('Thumbnails', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('Images', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('Clips', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('Database Records', { exact: true })).toBeVisible();

    // 3. Click first Preview Cleanup button inside StorageDashboard (StorageDashboard.tsx:226)
    const previewButtons = page.getByRole('button', { name: 'Preview Cleanup' });
    await expect(previewButtons).toHaveCount(2);

    const firstDryRunPromise = page.waitForResponse(
      (res) =>
        apiPath(res.url()) === '/api/system/cleanup' &&
        new URL(res.url()).searchParams.get('dry_run') === 'true' &&
        res.request().method() === 'POST'
    );
    await previewButtons.first().click();
    const firstDryRunRes = await firstDryRunPromise;
    expect(firstDryRunRes.status()).toBe(200);

    await expect(
      page.getByText(`Would be deleted (based on retention period of ${retentionDays} days):`)
    ).toBeVisible();
    await expect(page.getByText('Space to reclaim:')).toBeVisible();

    // 4. Click second Preview Cleanup button inside CleanupPreviewPanel (CleanupPreviewPanel.tsx:152)
    const secondDryRunPromise = page.waitForResponse(
      (res) =>
        apiPath(res.url()) === '/api/system/cleanup' &&
        new URL(res.url()).searchParams.get('dry_run') === 'true' &&
        res.request().method() === 'POST'
    );
    await previewButtons.nth(1).click();
    const secondDryRunRes = await secondDryRunPromise;
    expect(secondDryRunRes.status()).toBe(200);

    await expect(page.getByText('Preview Results')).toBeVisible();
    await expect(page.getByText(`Retention: ${retentionDays} days`)).toBeVisible();

    // Clear Preview collapses the results (CleanupPreviewPanel.tsx:156-159)
    await page.getByRole('button', { name: 'Clear Preview' }).click();
    await expect(page.getByText('Preview Results')).toHaveCount(0);

    await assertGuardSurvives(page, h);
  });

  test('F-224: Clear Old Data executes POST /api/system/cleanup (dry_run=false) and renders Cleanup Complete summary', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    // 1. Safety pre-check: ensure retention_days is at least 30 so active test rows are preserved
    const cfgRes = await api.getJson('/api/system/config');
    expect(cfgRes.status).toBe(200);
    expect(Number(cfgRes.body?.retention_days)).toBeGreaterThanOrEqual(30);

    // 2. Navigate to /settings/processing and click Clear Old Data (ProcessingSettings.tsx:459-486)
    await settledGoto(page, h, '/settings/processing', (p) =>
      p.getByRole('button', { name: 'Clear Old Data' })
    );

    const clearBtn = page.getByRole('button', { name: 'Clear Old Data' });
    await expect(clearBtn).toBeVisible();
    await expect(clearBtn).toBeEnabled();

    const cleanupPromise = page.waitForResponse(
      (res) =>
        apiPath(res.url()) === '/api/system/cleanup' &&
        new URL(res.url()).searchParams.get('dry_run') !== 'true' &&
        res.request().method() === 'POST'
    );
    await clearBtn.click();
    const cleanupRes = await cleanupPromise;
    expect(cleanupRes.status(), 'POST /api/system/cleanup answers 200').toBe(200);
    const cleanupBody = await cleanupRes.json();
    expect(cleanupBody.dry_run).toBe(false);

    // 3. Verify Cleanup Complete summary banner mirrors the response
    await expect(page.getByText('Cleanup Complete')).toBeVisible();
    await expect(page.getByText('Events deleted:')).toBeVisible();
    await expect(page.getByText('Detections deleted:')).toBeVisible();
    await expect(page.getByText('GPU stats deleted:')).toBeVisible();
    await expect(page.getByText('Logs deleted:')).toBeVisible();
    await expect(page.getByText('Thumbnails deleted:')).toBeVisible();
    await expect(page.getByText('Retention period:')).toBeVisible();
    await expect(page.getByText(`${cleanupBody.retention_days} days`).first()).toBeVisible();

    await assertGuardSurvives(page, h);
  });

  test('F-228 & F-229: Dead Letter Queue monitor and DLQ requeue-all / clear endpoints', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    // 1. API leg for F-228: GET /api/dlq/stats & GET /api/dlq/jobs/{queue_name}
    // (backend/api/routes/dlq.py:118-210)
    const statsRes = await api.getJson('/api/dlq/stats');
    expect(statsRes.status, 'GET /api/dlq/stats answers 200').toBe(200);
    expect(statsRes.body?.detection_queue_count).toBe(0);
    expect(statsRes.body?.analysis_queue_count).toBe(0);
    expect(statsRes.body?.total_count).toBe(0);

    for (const qName of ['dlq:detection_queue', 'dlq:analysis_queue'] as const) {
      const jobsRes = await api.getJson(
        `/api/dlq/jobs/${encodeURIComponent(qName)}?start=0&limit=100`
      );
      expect(jobsRes.status, `GET /api/dlq/jobs/${qName} answers 200`).toBe(200);
      expect(jobsRes.body?.queue_name).toBe(qName);
      expect(jobsRes.body?.items).toEqual([]);
      expect(jobsRes.body?.pagination?.total).toBe(0);
    }

    // Invalid queue name rejected with 422 by DLQName enum
    const invalidJobsRes = await api.getJson('/api/dlq/jobs/dlq%3Ainvalid_queue');
    expect(invalidJobsRes.status, 'invalid DLQ queue name rejected with 422').toBe(422);

    // 2. API leg for F-229: POST /api/dlq/requeue-all/{queue_name} & DELETE /api/dlq/{queue_name}
    // (backend/api/routes/dlq.py:275-387)
    for (const qName of ['dlq:detection_queue', 'dlq:analysis_queue'] as const) {
      const requeueAllRes = await api.send(
        `/api/dlq/requeue-all/${encodeURIComponent(qName)}`,
        'POST'
      );
      expect(requeueAllRes.status, `POST /api/dlq/requeue-all/${qName} answers 200`).toBe(200);
      expect(requeueAllRes.body?.success).toBe(false);
      expect(requeueAllRes.body?.message).toBe(`No jobs to requeue from ${qName}`);
      expect(requeueAllRes.body?.job).toBeNull();

      const clearRes = await api.send(`/api/dlq/${encodeURIComponent(qName)}`, 'DELETE');
      expect(clearRes.status, `DELETE /api/dlq/${qName} answers 200`).toBe(200);
      expect(clearRes.body?.queue_name).toBe(qName);
      expect(clearRes.body?.success).toBe(true);
      expect(clearRes.body?.message).toBe(`Cleared 0 jobs from ${qName}`);
    }

    // 3. UI leg for F-228 & F-229 on /settings/processing (DlqMonitor.tsx:206-417)
    await settledGoto(page, h, '/settings/processing', (p) =>
      p.getByText('Dead Letter Queue', { exact: true })
    );

    await expect(page.getByText('Dead Letter Queue', { exact: true })).toBeVisible();
    await expect(page.getByText('No failed jobs in queue')).toBeVisible();
    await expect(page.getByTestId('dlq-total-badge')).toHaveCount(0);

    // Per DlqMonitor.tsx:261 (`if (count === 0 && !queueState.expanded) return null;`),
    // queue rows and their Requeue All / Clear All buttons are unmounted when count === 0
    await expect(page.getByTestId('dlq-queue-dlq:detection_queue')).toHaveCount(0);
    await expect(page.getByTestId('dlq-queue-dlq:analysis_queue')).toHaveCount(0);

    // Clicking Refresh DLQ stats triggers GET /api/dlq/stats (DlqMonitor.tsx:223-232)
    const refreshPromise = page.waitForResponse(
      (res) => apiPath(res.url()) === '/api/dlq/stats' && res.request().method() === 'GET'
    );
    await page.getByRole('button', { name: 'Refresh DLQ stats' }).click();
    const refreshRes = await refreshPromise;
    expect(refreshRes.status()).toBe(200);
    await expect(page.getByText('No failed jobs in queue')).toBeVisible();

    await assertGuardSurvives(page, h);
  });
});

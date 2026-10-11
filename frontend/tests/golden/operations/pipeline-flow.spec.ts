/**
 * F-134 (inventory 3.8): the Files → Detect → Batch → Analyze flow
 * visualization renders its stages with live queue-depth / worker / latency
 * readouts.
 *
 * The numbers come from GET /api/system/telemetry (queue depths, per-stage
 * latency) and GET /api/system/pipeline (worker dots), both asserted from
 * Node first: a stage diagram pinned over a dead endpoint renders zeros just
 * as pretty. The stage and readout testids are the components' own
 * (PipelineFlowVisualization / QueueMetricsPanel), DOM-probed on the harness
 * stack. Zero values are the honest virgin-stack reading — the assertion is
 * "a number renders", and the drop-driven nonzero path is F2.1's job, not a
 * second spec racing the dedupe window.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, loginAsAdmin, readOpsHarness } from './harness';

const harness = readOpsHarness();

test.describe('golden path: pipeline flow visualization @critical', () => {
  test.setTimeout(60_000);

  test('four stages and live totals render over a real telemetry read', async ({ page }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    const telemetry = await api<{
      queues: Record<string, number>;
      latencies?: Record<string, unknown>;
    }>(h, session, '/api/system/telemetry');
    expect(telemetry.queues).toHaveProperty('detection_queue');
    const pipeline = await api<{ batch_aggregator?: { active_batches?: number } }>(
      h,
      session,
      '/api/system/pipeline',
    );
    expect(typeof pipeline.batch_aggregator?.active_batches).toBe('number');

    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('pipeline-flow-visualization')).toBeVisible();
    for (const stage of ['stage-files', 'stage-detect', 'stage-batch', 'stage-analyze']) {
      await expect(page.getByTestId(stage)).toBeVisible();
    }
    // Live totals fed by the endpoints asserted above.
    await expect(page.getByTestId('total-queue-depth')).toContainText(/\d/);
    await expect(page.getByTestId('total-workers')).toContainText(/\d/);
    await expect(page.getByTestId('total-pipeline-latency')).toContainText(/\d/);
    await expect(page.getByTestId('worker-dot-detector')).toBeVisible();
    await expect(page.getByTestId('worker-dot-analyzer')).toBeVisible();

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});

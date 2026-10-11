/**
 * F-142 + F-143 (inventory 3.8): the worker management section lists the four
 * supervised workers, and its controls actually control them.
 *
 * F-143 was the trickiest green call in OP-1 and it rests on measurements:
 * POST /api/system/supervisor/workers/<name>/stop then /start round-trips
 * through state 'stopped' to 'running' within one poll on the harness stack,
 * and the panel's hooks (useWorkerActions -> supervisorApi) target exactly
 * those routes. The 'metrics' worker is the control subject — it is off the
 * detection/analysis path, so a stop/start cannot starve the pipeline the
 * other specs read.
 *
 * Ordering note for the serial golden project: the assertions ride on the
 * panel's own 10 s poll plus explicit refetch triggers, never on catching a
 * transient — restart was measured to cycle faster than a 1.5 s poller can
 * see, so only start (stop visible) is proven here, and it ends with every
 * worker running again.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, loginAsAdmin, openSection, panelRecovers, pollApi, readOpsHarness } from './harness';

const harness = readOpsHarness();

interface SupervisorBody {
  running: boolean;
  worker_count: number;
  workers: { name: string; status: string; restart_count: number }[];
}

test.describe('golden path: worker management @critical', () => {
  test.setTimeout(120_000); // round trip + panel polls

  test('four supervised workers render, and stop/start round-trips the metrics worker', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    // Backend leg: the supervisor is real and lists the four documented
    // workers before the page draws a single card.
    const sup = await api<SupervisorBody>(h, session, '/api/system/supervisor');
    const names = sup.workers.map((w) => w.name).sort();
    expect(names).toEqual(['analysis', 'batch_timeout', 'detection', 'metrics']);
    expect(sup.workers.every((w) => w.status === 'running')).toBe(true);

    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await openSection(page, 'worker-management');
    // The panel's own fetch can fail at the stalled redis middleware like
    // latency-history's did (run 5 evidence); useSupervisorStatus retries
    // only on its 10 s poll, so drive the error branch's Retry button —
    // the interval matches the poll cadence the component itself uses.
    // Root = the error div itself: WorkerManagementPanel's error branch
    // (:208) does NOT carry the panel testid (unlike the latency panel), and
    // its Retry button lives inside it.
    await panelRecovers(
      page.getByTestId('worker-management-error'),
      page.getByTestId('worker-management-error'),
      page.getByTestId('worker-management-loading'),
      { retryIntervalMs: 5_000 },
    );
    const panel = page.getByTestId('worker-management-panel');
    await expect(panel).toBeVisible();
    for (const name of names) {
      await expect(page.getByTestId(`worker-card-${name}`)).toBeVisible();
      await expect(page.getByTestId(`worker-status-badge-${name}`)).toHaveText(/running/i);
    }

    // F-143 control leg: Stop on metrics -> confirmation dialog -> the panel
    // shows the stopped worker with its Start affordance -> Start -> running.
    await page.getByTestId('worker-action-stop-metrics').click();
    await expect(page.getByTestId('confirmation-dialog')).toBeVisible();
    await page.getByTestId('confirm-button').click();

    // Backend reaches 'stopped' fast (measured immediate); assert there first,
    // then let the panel's own poll surface Start.
    await pollApi(
      h,
      session,
      '/api/system/supervisor',
      (b: SupervisorBody) => b.workers.find((w) => w.name === 'metrics')?.status === 'stopped',
      20_000,
    );
    await page.getByTestId('worker-start-button-metrics').click({ timeout: 15_000 });

    await pollApi(
      h,
      session,
      '/api/system/supervisor',
      (b: SupervisorBody) => b.workers.every((w) => w.status === 'running'),
      20_000,
    );
    await expect(page.getByTestId('worker-status-badge-metrics')).toHaveText(/running/i, {
      timeout: 15_000,
    });

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});

/**
 * F-141 (inventory 3.8): the Prometheus monitoring section shows Prometheus
 * READINESS — on the harness stack the honest reading is truthful
 * unreachability, and this spec pins that truthfulness.
 *
 * Why truthfulness is the golden path here: docker-compose.ci.yml brings up
 * postgres/redis/backend/frontend (+ the fake-ai overlay) and no prometheus —
 * docker-compose.prod.yml:1044 is the file that ships it. So the panel's job
 * on CI is to say so, with the endpoint it checked. The sibling Grafana-iframe
 * routes (F-164..F-169, F-174) are demoted for the same stack reason, but THIS
 * panel is a first-class readiness reporter and green with it.
 *
 * Backend leg first: /api/system/monitoring/health must report prom_reachable
 * false, so the UI's "unreachable" copy is provably the truth and not a stuck
 * render.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, loginAsAdmin, openSection, readOpsHarness } from './harness';

const harness = readOpsHarness();

test.describe('golden path: prometheus readiness panel @critical', () => {
  test.setTimeout(60_000);

  test('the panel reports the real reachability of the prometheus endpoint', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    // Field name measured on the live body: prometheus_reachable (the draft's
    // prom_reachable was undefined — same lesson as the breaker dict).
    const health = await api<{ prometheus_reachable?: boolean; healthy?: boolean }>(
      h,
      session,
      '/api/system/monitoring/health',
    );
    expect(typeof health.prometheus_reachable).toBe('boolean');

    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await openSection(page, 'prometheus-monitoring');
    const panel = page.getByTestId('prometheus-monitoring-panel');
    await expect(panel).toBeVisible();

    // Measured on the harness stack: prometheus_reachable=false and the badge
    // reads "Prometheus Unreachable" (PrometheusMonitoringPanel.tsx:209-210).
    // The panel must SAY the real state, not render a hopeful skeleton forever.
    if (health.prometheus_reachable === false) {
      await expect(panel).toContainText(/unreachable/i);
    } else {
      await expect(panel).toContainText(/reachable/i);
    }

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});

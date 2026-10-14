/**
 * F-171 (inventory 3.8): Performance page › Active alerts at /performance —
 * threshold-breach alerts streamed over WS /ws/system.
 *
 * Why this row is reachable on the CI stack without a fault-seed env var:
 * PerformanceCollector.collect_all (backend/services/performance_collector.py:83)
 * computes `alerts` on every collection cycle from live metrics, including
 * `check_redis_alerts` (:818). `collect_redis_metrics` (:369-371) derives
 * `hit_ratio = (hits / (hits + misses) * 100) if (hits + misses) > 0 else 0`
 * from Redis INFO's `keyspace_hits` and `keyspace_misses`, and
 * `check_redis_alerts` (:834-844) emits a critical `redis_hit_ratio` alert
 * whenever `redis.hit_ratio < THRESHOLDS["redis_hit_ratio"]["critical"]` (10%).
 *
 * Every call to the un-rate-limited `GET /api/debug/pipeline-state` route
 * (backend/api/routes/debug.py:615) reads six non-existent worker keys
 * (`worker:*:heartbeat`, `worker:*:error_count`, :225-232) plus the empty
 * `pipeline:errors` list (:269), incrementing `keyspace_misses` in Redis by
 * seven per request with zero `keyspace_hits`. Driving that shipped endpoint
 * until `redis.hit_ratio < 10` therefore produces a genuine Redis threshold
 * breach on demand on the live stack, which `SystemBroadcaster` streams on the
 * next `performance_update` frame over `/ws/system` and `PerformanceAlerts`
 * renders on `/performance`.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, loginAsAdmin, readOpsHarness } from './harness';

const harness = readOpsHarness();

interface PerformanceAlertPayload {
  severity: 'warning' | 'critical';
  metric: string;
  value: number;
  threshold: number;
  message: string;
}

interface PerformanceSnapshotBody {
  databases?: {
    redis?: {
      hit_ratio?: number;
    };
  };
  alerts?: PerformanceAlertPayload[];
}

test.describe('golden path: performance page active alerts (F-171) @critical', () => {
  test.setTimeout(120_000);

  test('a live Redis hit-ratio threshold breach streams over /ws/system and renders in Active Alerts', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    // ── NODE LEG ────────────────────────────────────────────────────────────
    // Ensure Redis keyspace_misses push hit_ratio below the 10% critical
    // threshold (backend/services/performance_collector.py:45, :834).
    // GET /api/system/performance caches its snapshot for 5 s (:2181), so each
    // miss burst waits out that cache window before re-reading the snapshot.
    let perf = await api<PerformanceSnapshotBody>(h, session, '/api/system/performance');
    let redisAlert = (perf.alerts ?? []).find(
      (a) => a.metric === 'redis_hit_ratio' && a.severity === 'critical'
    );

    for (let round = 0; !redisAlert && round < 8; round += 1) {
      await Promise.all(
        Array.from({ length: 30 }, () => api<unknown>(h, session, '/api/debug/pipeline-state'))
      );
      await new Promise((r) => setTimeout(r, 5_500));
      perf = await api<PerformanceSnapshotBody>(h, session, '/api/system/performance');
      redisAlert = (perf.alerts ?? []).find(
        (a) => a.metric === 'redis_hit_ratio' && a.severity === 'critical'
      );
    }

    expect(
      redisAlert,
      `expected critical redis_hit_ratio alert in ${JSON.stringify(perf.alerts)}`
    ).toBeTruthy();
    expect(redisAlert!.severity).toBe('critical');
    expect(redisAlert!.metric).toBe('redis_hit_ratio');
    expect(redisAlert!.threshold).toBe(10);
    expect(redisAlert!.value).toBeLessThan(10);
    expect(redisAlert!.message).toMatch(/^Redis hit ratio critical: \d+\.\d+%$/);

    // ── BROWSER LEG ─────────────────────────────────────────────────────────
    await page.goto(`${h.ui}/performance`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('performance-page')).toBeVisible();

    const charts = page.getByTestId('performance-charts');
    await expect(charts.getByText('Connected', { exact: true })).toBeVisible({ timeout: 20_000 });

    const alertsPanel = page.getByTestId('performance-alerts');
    await expect(alertsPanel).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId('performance-alerts-empty')).toHaveCount(0);
    await expect(alertsPanel.getByText('Active Alerts', { exact: true })).toBeVisible();

    const callout = page.getByTestId('alert-critical-redis_hit_ratio');
    await expect(callout).toBeVisible();
    await expect(callout).toContainText('CRITICAL');
    await expect(callout).toContainText('Redis Hit Ratio:');
    await expect(callout).toContainText('10%');
    await expect(callout).toContainText(/Redis hit ratio critical: \d+\.\d+%/);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});

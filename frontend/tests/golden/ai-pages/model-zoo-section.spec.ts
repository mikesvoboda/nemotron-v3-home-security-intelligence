/**
 * F-104 (inventory 3.7): Model Zoo status cards on the AI Performance page.
 *
 * This is the ONE leg of /ai that lives on the CI stack. The page's other
 * content is the embedded `ai-services` Grafana dashboard (row F-102), and
 * docker-compose.ci.yml ships no grafana — measured through the CI frontend's
 * nginx, `GET /grafana/d/ai-services/ai-services?...` answers 502 — so F-102
 * demotes to half-built (same stack reason as OP-1's F-164..F-174 embed rows).
 * The Model Zoo section reads /api/system/model-zoo/status, which the backend
 * serves from its own registry, so it renders real data here.
 *
 * Backend leg first (the prometheus-panel idiom): every number the summary
 * rows print, every card the grids mount, and the latency chart's branch are
 * decided from the live API body, so the spec asserts the UI MIRRORS the API
 * rather than pinning a snapshot that ages the day a model ships.
 *
 * Product finding pinned by the count checks below: AIPerformancePage.tsx:137
 * passes `data-testid="ai-performance-model-zoo"` to <ModelZooSection />, but
 * ModelZooSectionProps (ModelZooSection.tsx:55-60) declares only className and
 * pollingInterval and the component destructures just those — unknown JSX
 * props are silently dropped without a rest-spread, so the passed id never
 * lands in the DOM and only the component's own `model-zoo-section` root
 * (:387) is queryable. A spec written against the passed id would wait forever
 * on an element the product cannot render.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, loginAsAdmin, readOpsHarness } from '../operations/harness';

const harness = readOpsHarness();

interface ZooModel {
  name: string;
  display_name: string;
  category: string;
  enabled: boolean;
  status: string;
  vram_mb: number;
}

interface ZooStatus {
  total_models: number;
  loaded_count: number;
  disabled_count: number;
  vram_used_mb: number;
  vram_budget_mb: number;
  models: ZooModel[];
}

interface LatencyHistory {
  model_name: string;
  display_name: string;
  has_data: boolean;
}

test.describe('golden path: model zoo status cards on /ai @critical', () => {
  // 90 s, not 60: the last assertion waits out the section's own 30 s poll
  // interval to prove the "polled" clause in the row text.
  test.setTimeout(90_000);

  test('the /ai Model Zoo mirrors the live compact status the API reports', async ({ page }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    // Observer only — page.on('response') reads traffic, never intercepts it
    // (the guard blocks route/routeFromHAR/routeWebSocket, not listeners).
    let statusFetches = 0;
    page.on('response', (res) => {
      try {
        if (new URL(res.url()).pathname === '/api/system/model-zoo/status') statusFetches += 1;
      } catch {
        /* non-URL-ish response (about:blank subresources) — not our endpoint */
      }
    });

    // Backend leg: the page polls this exact endpoint every 30 s.
    const status = await api<ZooStatus>(h, session, '/api/system/model-zoo/status');
    expect(status.models.length).toBe(status.total_models);
    const enabled = status.models.filter((m) => m.enabled);
    const disabled = status.models.filter((m) => !m.enabled);
    expect(enabled.length + disabled.length).toBe(status.total_models);

    // The component's default selection is 'yolo11-license-plate' and it keeps
    // it while that name exists (ModelZooSection.tsx:358-365 falls back to the
    // first enabled model only when the default is absent). The latency chart
    // renders the branch the history endpoint reports for THAT model.
    const selected =
      status.models.find((m) => m.name === 'yolo11-license-plate') ??
      enabled[0] ??
      status.models[0];
    const history = await api<LatencyHistory>(
      h,
      session,
      `/api/system/model-zoo/latency/history?model=${selected.name}&since=60&bucket_seconds=60`
    );

    await page.goto(`${h.ui}/ai`, { waitUntil: 'domcontentloaded' });
    // The root swaps ai-performance-loading → ai-performance-page once
    // /api/system/config resolves (AIPerformancePage.tsx:81); the Model Zoo
    // mounts only in the loaded root.
    await expect(page.getByTestId('ai-performance-page')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'AI Performance' })).toBeVisible();

    const section = page.getByTestId('model-zoo-section');
    await expect(section).toBeVisible();
    // The passed id never renders — see the header note on the dropped prop.
    await expect(page.getByTestId('ai-performance-model-zoo')).toHaveCount(0);

    // Summary rows are arithmetic on this same body (:400-417): unloaded is
    // total - loaded - disabled, computed in the browser from the API numbers.
    const summary = page.getByTestId('model-zoo-summary');
    await expect(summary).toContainText(new RegExp(`${status.loaded_count}\\s+loaded`));
    await expect(summary).toContainText(
      new RegExp(`${status.total_models - status.loaded_count - status.disabled_count}\\s+unloaded`)
    );
    await expect(summary).toContainText(new RegExp(`${status.disabled_count}\\s+disabled`));
    await expect(summary).toContainText(
      new RegExp(`${status.vram_used_mb}/${status.vram_budget_mb}MB VRAM`)
    );

    // One card per model, named by model name; the ACTIVE accordion is
    // defaultOpen={true} (:444), so enabled cards are mounted at load.
    const grid = page.getByTestId('enabled-models-grid');
    await expect(grid.locator('[data-testid^="model-card-"]')).toHaveCount(enabled.length);
    const firstCard = page.getByTestId(`model-card-${enabled[0].name}`);
    await expect(firstCard).toContainText(enabled[0].display_name);
    await expect(firstCard).toContainText(enabled[0].status === 'loaded' ? /Loaded/ : /Unloaded/);
    // The other three card fields the row names (ModelZooSection.tsx:158-188):
    // VRAM, last-used and the category badge. vram_mb/category come from the
    // registry's static config, so the pre-read body is the same data the card
    // rendered. last_used_at formats via formatTimeAgo (:79-92): 'Never' when
    // null, else Just now / Nm ago / Nh ago / Nd ago.
    const cardModel = status.models.find((m) => m.name === enabled[0].name)!;
    await expect(firstCard).toContainText(`${cardModel.vram_mb}MB`);
    await expect(firstCard).toContainText(cardModel.category);
    await expect(firstCard).toContainText(/Never|Just now|\d+[mhd] ago/);

    // The DISABLED accordion ships closed (defaultOpen={false}, :478); opening
    // it mounts the disabled card — the one model here is the measured
    // yolo26-general on the harness stack.
    if (disabled.length > 0) {
      await page.getByRole('button', { name: `Disabled Models (${disabled.length})` }).click();
      await expect(page.getByTestId(`model-card-${disabled[0].name}`)).toBeVisible();
      await expect(page.getByTestId(`model-card-${disabled[0].name}`)).toContainText('Disabled');
    }

    // Latency chart: truthful branch decided by the API's own has_data flag
    // (ModelZooSection.tsx:304-316 vs :318). On the fake stack every snapshot
    // carries stats:null and has_data is false — measured — so the honest
    // reading is the "No data available" state, and the spec fails if the UI
    // claims a chart the API says it has no data for.
    const chart = page.getByTestId('model-zoo-latency-chart');
    await expect(chart).toBeVisible();
    if (history.has_data) {
      await expect(page.getByTestId('model-latency-area-chart')).toBeVisible();
    } else {
      await expect(chart).toContainText(`No data available for ${selected.display_name}`);
    }

    // The row's final clause is "polled". /ai mounts <ModelZooSection /> with
    // no pollingInterval prop (:137), so it runs the component's default 30 s
    // setInterval (:375-379). Wait out one interval and require the BROWSER to
    // have asked the endpoint again — a page that fetched only on mount would
    // leave this counter at its mount value. (Node-side api() calls never touch
    // this counter; it only sees traffic the page itself makes.)
    const atAssert = statusFetches;
    expect(atAssert).toBeGreaterThanOrEqual(1);
    await expect
      .poll(() => statusFetches, { timeout: 40_000, intervals: [2_000] })
      .toBeGreaterThan(atAssert);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});

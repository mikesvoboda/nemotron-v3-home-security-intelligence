/**
 * F-125 + F-129 (inventory 3.7): the Model Management panel on
 * /settings/ai-models renders instead of crashing.
 *
 * Fresh pin, not a flip: no golden spec covered this route. F2.3's demotion
 * evidence recorded the crash it is meant to pin — measured in a browser on the
 * harness stack, a `pageerror` "Cannot destructure property 'icon' of 't[s]' as
 * it is undefined" with `ai-models-tab` absent, because ModelManagementPanel's
 * StatusIndicator did `config[status]` over a 5-key map and GET
 * /api/system/models sends no `status` field at all. The row's Done-when wants
 * that spec "flipped to assert the fix"; the premise that a pin already exists
 * fails here (census over tests/golden/ finds no /settings/ai-models spec), so
 * this is the spec written new, asserting the fixed behaviour.
 *
 * Backend leg first, the prometheus-panel idiom: the counts and the VRAM
 * figures the panel prints are recomputed from the live API body, so the spec
 * asserts the UI MIRRORS the API rather than pinning a model list that ages the
 * day a model ships. Two feeds, because the panel now reads two:
 * /api/system/models and /api/system/models/vram-summary.
 *
 * The crash guard is the `pageerror` assertion at the bottom, kept for the whole
 * run. F-129 is the sibling Model Zoo status cards on the SAME tab: they were
 * golden-green on /ai while absent here, which is what isolated the crash to
 * this panel; so the spec also requires those cards to mount on this route.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, loginAsAdmin, readOpsHarness } from '../operations/harness';

const harness = readOpsHarness();

interface ModelRuntime {
  loaded: boolean;
  actual_vram_mb: number | null;
  last_used: string | null;
  load_count: number;
}

interface ModelItem {
  name: string;
  category: string;
  estimated_vram_mb: number;
  enabled: boolean;
  service: string;
  gpu_id: number;
  runtime: ModelRuntime | null;
}

interface ModelList {
  models: ModelItem[];
  service_status: Record<string, string>;
}

interface VRAMSummary {
  gpus: { gpu_id: number; budget_mb: number; used_mb: number }[];
  totals: { budget_mb: number; used_mb: number; available_mb: number; model_count: number };
}

// Mirrors modelDisplayStatus in ModelManagementPanel.tsx: enabled is config,
// runtime.loaded is live state, and a null runtime is its own answer.
function derived(m: ModelItem): 'disabled' | 'unknown' | 'loaded' | 'unloaded' {
  if (!m.enabled) return 'disabled';
  if (m.runtime === null) return 'unknown';
  return m.runtime.loaded ? 'loaded' : 'unloaded';
}

test.describe('golden path: model management panel renders on /settings/ai-models @critical', () => {
  test.setTimeout(90_000);

  test('the AI Models tab mounts its panel and mirrors both live model feeds', async ({ page }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    // Observer only — reads traffic, never intercepts (the guard blocks route).
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(String(e)));

    // Backend leg: read the exact bodies the panel will fetch.
    const list = await api<ModelList>(h, session, '/api/system/models');
    expect(Object.keys(list.models[0]).sort()).toEqual([
      'category',
      'enabled',
      'estimated_vram_mb',
      'gpu_id',
      'name',
      'runtime',
      'service',
    ]);
    // The F-125 crash premise, re-asserted: no item carries a status field.
    expect(list.models.some((m) => 'status' in m)).toBe(false);
    const counts = {
      loaded: list.models.filter((m) => derived(m) === 'loaded').length,
      unloaded: list.models.filter((m) => derived(m) === 'unloaded').length,
      disabled: list.models.filter((m) => derived(m) === 'disabled').length,
      unknown: list.models.filter((m) => derived(m) === 'unknown').length,
    };
    const vram = await api<VRAMSummary>(h, session, '/api/system/models/vram-summary');
    expect(vram.totals.budget_mb).toBeGreaterThan(0);

    await page.goto(`${h.ui}/settings/ai-models`, { waitUntil: 'domcontentloaded' });

    // The crash showed here: the tab never mounted. Its testid is on AIModelsTab.
    await expect(page.getByTestId('ai-models-tab')).toBeVisible();

    // F-129: the Model Zoo status cards share this tab and were golden on /ai
    // but absent here — the isolation witness. They mount now.
    await expect(page.getByTestId('model-zoo-section')).toBeVisible();

    const panel = page.getByTestId('model-management-panel');
    await expect(panel).toBeVisible();

    // Summary tiles are arithmetic on the same body, and the four derived
    // states are exhaustive: they always sum to Total.
    const summary = page.getByTestId('model-status-summary');
    await expect(summary).toContainText(String(list.models.length));
    await expect(summary).toContainText(String(counts.loaded));
    await expect(summary).toContainText(String(counts.disabled));
    if (counts.unknown > 0) {
      await expect(summary).toContainText('No data');
    }

    // VRAM card mirrors the totals feed the panel now reads (the deleted feed
    // asked one endpoint for a vram_budget_mb it never sent).
    const vramSection = page.getByTestId('vram-usage-section');
    await expect(vramSection).toBeVisible();

    // Every model gets a card named by its registry name (no display_name
    // exists on the wire).
    //
    // Scoped to this panel's grid on purpose: `model-card-<name>` is emitted by
    // three components mounted on this one tab (this panel's ModelCard,
    // ModelZooPanel's ModelCard.tsx:135, and ModelZooSection.tsx:154), so a
    // page-level getByTestId resolves ambiguously and a strict expect fails on
    // 3 matches. That is a real repo finding, not a spec quirk — see the PR.
    const grid = page.getByTestId('model-cards-grid');
    await expect(grid.locator('[data-testid^="model-card-"]')).toHaveCount(list.models.length);
    for (const m of list.models) {
      const card = grid.getByTestId(`model-card-${m.name}`);
      await expect(card).toBeVisible();
      await expect(card).toContainText(m.name);
      await expect(card).toContainText(m.category);
    }

    // F-125's OWN clauses (its row text describes the Model Zoo admin panel,
    // not the management panel that threw): per-lane VRAM budget/usage, model
    // cards grouped by GPU, disabled models collapsed, and a Refresh button.
    // None of it ever mounted while the sibling panel crashed the tab, which is
    // why this row sat half-built with a crash as its evidence.
    const zoo = page.getByTestId('model-zoo-panel');
    await expect(zoo).toBeVisible();
    for (const gpu of vram.gpus) {
      await expect(page.getByTestId(`vram-bar-gpu-${gpu.gpu_id}`)).toBeVisible();
    }
    // One GPU section per distinct gpu_id the registry assigns.
    const lanes = [...new Set(list.models.map((m) => m.gpu_id))];
    for (const lane of lanes) {
      await expect(page.getByTestId(`gpu-section-${lane}`)).toBeVisible();
    }
    // The panel's own header line is arithmetic over these same bodies.
    await expect(zoo).toContainText(`${list.models.length} models`);

    // Disabled models are collapsed behind their own section, not inline.
    const disabledSection = page.getByTestId('disabled-models-section');
    if (counts.disabled > 0) {
      await expect(disabledSection).toBeVisible();
    } else {
      await expect(disabledSection).toHaveCount(0);
    }

    // Refresh is actionable: the row's last clause is "clicks Refresh".
    const refresh = page.getByRole('button', { name: 'Refresh' });
    await expect(refresh).toBeEnabled();
    await refresh.click();
    await expect(zoo).toBeVisible();

    // No pageerror across the whole run — the precise regression F-125 pinned.
    expect(errors, `pageerror: ${errors.join(' | ')}`).toEqual([]);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});

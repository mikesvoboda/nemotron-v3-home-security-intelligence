/**
 * FE-2 golden path (F2.3): F-040 — the Pipeline Telemetry widget (off by
 * default): queue depths and per-stage latency percentiles over
 * GET /api/system/telemetry.
 *
 * Decided from shipped code before writing (each claim cites where):
 *
 * - The row's clause: "enables it; sees queue depths and per-stage latency
 *   percentiles, polled every 5 s". Backend: GET /api/system/telemetry ONLY.
 * - Off-by-default is store DEFAULT_WIDGETS pipeline-telemetry visible:false
 *   (dashboard-config-store.ts:150-154); enabling goes through F-042's
 *   Configure modal — proven in config-modal.spec.ts — so this spec flips it
 *   through that SAME click path (a real click, not a jar write) and asserts
 *   the absent-before state first (the row's "off by default" half).
 * - The widget fetches its OWN data (PipelineTelemetry.tsx:121-123 via
 *   fetchTelemetry(), api.ts:2119-2121, polling on pollingInterval=5000 :95).
 *   Unlike the donut it is NOT presentation-only, so this is a DOM-vs-API
 *   mirror on the same endpoint: fetchTelemetry takes NO params, so a plain
 *   Node GET replays the identical query — and the endpoint is NOT cache-aside
 *   (system.py:3113-3156 reads Redis directly: get_queue_length +
 *   get_latency_stats, no cache.get), so the Node read is a FRESH read of the
 *   same Redis the widget read.
 * - The queue/latency state is LIVE (workers drain queues, latency samples
 *   append), so a one-shot DOM-vs-API equality could race a transient — the
 *   mirror uses AGREEMENT POLLS: each poll re-reads the API and compares to
 *   the DOM, succeeding on agreement and FAILING with the last observed
 *   "dom=… api=…" string, so a persistent mismatch names both values instead
 *   of timing out silently. On a settled idle stack both agree immediately.
 * - DOM strings come from the component's OWN formatters, reimplemented here
 *   with the cite: queue depths render RAW integers (:390-393, :412-415 — no
 *   formatter, from telemetry?.queues.* :202-203); latency rows render
 *   formatLatency (:46-50: null/undefined → "N/A", < 1000 →
 *   `${ms.toFixed(0)}ms`, else `${(ms/1000).toFixed(1)}s`) for
 *   avg / p95 / p99 (:296-298) plus `${sample_count ?? 0} samples` (:291).
 *   Row ids are DERIVED, not literals: renderLatencyRow (:284-310) builds
 *   `latency-row-${label.toLowerCase().replace(' ', '-')}` (:287) and is
 *   called with 'Detection'/'Batch Agg'/'Analysis' (:433-435), so this spec
 *   derives them the same way instead of guessing the slug. `watch` exists in
 *   the schema (PipelineLatencies, schemas/system.py:853-880) but the widget
 *   does NOT render it — only the three stages it actually shows are
 *   asserted. StageLatency fields avg/min/max/p50/p95/p99_ms + sample_count
 *   are all `float|int | None` defaults (schemas/system.py:799-852), and
 *   TelemetryResponse.latencies is nullable (:945-948), hence the optional
 *   chaining below.
 * - "polled every 5 s" is the pollingInterval DEFAULT (:95): a golden spec
 *   cannot observe a wall-clock timer without manufacturing a second data
 *   mutation, which would be a mock the guard rightly forbids. What this spec
 *   drives is the row's observable — "enables it; sees queue depths and
 *   per-stage latency percentiles" — and CITES the 5 s default rather than
 *   pretending to time it. The cadence itself is unit-territory; overclaiming
 *   it here would make the golden row mean something it doesn't.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  adminSession,
  api,
  closedByGuard,
  loginAsAdmin,
  quietBoot,
  readDashboardHarness,
  seedTourDismissed,
  type DashboardHarness,
} from './harness';

const harness = readDashboardHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

interface Stage {
  avg_ms: number | null;
  p95_ms: number | null;
  p99_ms: number | null;
  sample_count: number;
}
interface Telemetry {
  queues: { detection_queue: number; analysis_queue: number };
  latencies: { detect?: Stage | null; batch?: Stage | null; analyze?: Stage | null } | null;
}

/** Mirror of PipelineTelemetry.tsx:46-50 — the DOM's exact number→string rule. */
function formatLatency(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return 'N/A';
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/** Mirror of the component's OWN test-id derivation (:287 + calls :433-435). */
const rowId = (label: string) => `latency-row-${label.toLowerCase().replace(' ', '-')}`;
const STAGES = ['Detection', 'Batch Agg', 'Analysis'] as const;
type StageLabel = (typeof STAGES)[number];
const stageOf = (t: Telemetry, label: StageLabel) =>
  label === 'Detection'
    ? t.latencies?.detect
    : label === 'Batch Agg'
      ? t.latencies?.batch
      : t.latencies?.analyze;

async function openDashboard(page: import('@playwright/test').Page, h: DashboardHarness) {
  await seedTourDismissed(page);
  await loginAsAdmin(page, h);
  await quietBoot(page, h);
  await expect(page.getByTestId('dashboard-layout')).toBeVisible({ timeout: 20_000 });
}

/** Turn a widget ON through the shipped Configure modal (F-042's path), then save. */
async function enableWidget(page: import('@playwright/test').Page, widgetId: string) {
  await page.getByTestId('configure-dashboard-button').click();
  await expect(page.getByTestId('widget-list')).toBeVisible();
  const sw = page.getByTestId(`widget-toggle-${widgetId}`);
  await expect(sw).toHaveAttribute('role', 'switch');
  if ((await sw.getAttribute('aria-checked')) !== 'true') await sw.click();
  await expect(sw).toHaveAttribute('aria-checked', 'true');
  await page.getByTestId('save-button').click();
  await expect(page.getByTestId('widget-list')).toHaveCount(0);
}

test.describe('golden path: dashboard pipeline telemetry widget @critical', () => {
  test('F-040: enabling the off-by-default widget renders queue depths and latency percentiles that mirror GET /api/system/telemetry', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(90_000);

    await openDashboard(page, h);
    // Off by default: NOT in the DOM before enabling (DEFAULT_WIDGETS
    // visible:false, store :118-159) — the row's first word is asserted.
    await expect(page.getByTestId('pipeline-telemetry')).toHaveCount(0);

    await enableWidget(page, 'pipeline-telemetry');
    await expect(page.getByTestId('pipeline-telemetry')).toBeVisible({ timeout: 15_000 });

    // Ground truth: fresh Node GETs of the SAME paramless endpoint (it has no
    // cache layer — system.py:3113-3161). Each agreement poll re-reads it, so
    // a transient live-queue state resolves; a persistent mismatch fails with
    // both observed values in the message.
    const session = await adminSession(h);
    const read = () => api<Telemetry>(h, session, '/api/system/telemetry');
    const flat = async (locator: import('@playwright/test').Locator) =>
      (await locator.innerText()).replace(/\s+/g, ' ').trim();

    // Queue depths: the badge renders the RAW integer (:390-393, :412-415), so
    // DOM text must EQUAL the API number exactly.
    for (const [testid, key] of [
      ['detection-queue-depth', 'detection_queue'],
      ['analysis-queue-depth', 'analysis_queue'],
    ] as const) {
      await expect
        .poll(
          async () => {
            const t = await read();
            const dom = await flat(page.getByTestId(testid));
            return dom === String(t.queues[key]) ? 'agree' : `dom="${dom}" api="${t.queues[key]}"`;
          },
          {
            message: `${testid} mirrors the live queue length`,
            timeout: 20_000,
            intervals: [1_000],
          }
        )
        .toBe('agree');
    }

    // Latency rows: the SAME fresh read must appear in each row — the
    // "avg / p95 / p99" triple (:296-298, each via formatLatency) AND the
    // samples line (:291). Checking all three percentiles matters: an
    // avg-only check would still pass if the row rendered p50 where p95
    // belongs, or if it rendered the same value three times.
    for (const label of STAGES) {
      const locator = page.getByTestId(rowId(label));
      await expect(locator, `${rowId(label)} renders`).toBeVisible({ timeout: 15_000 });
      await expect
        .poll(
          async () => {
            const t = await read();
            const stage = stageOf(t, label);
            const triple = `${formatLatency(stage?.avg_ms)} / ${formatLatency(stage?.p95_ms)} / ${formatLatency(stage?.p99_ms)}`;
            const samples = `${stage?.sample_count ?? 0} samples`;
            const dom = await flat(locator);
            if (!dom.includes(triple)) return `avg/p95/p99: dom="${dom}" wants "${triple}"`;
            if (!dom.includes(samples)) return `samples: dom="${dom}" wants "${samples}"`;
            return 'agree';
          },
          {
            message: `${rowId(label)} mirrors the avg/p95/p99 triple + samples`,
            timeout: 20_000,
            intervals: [1_000],
          }
        )
        .toBe('agree');
    }

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-040: the enabled widget stays enabled across reload (persist, not per-mount state)', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(90_000);

    await openDashboard(page, h);
    await enableWidget(page, 'pipeline-telemetry');
    await expect(page.getByTestId('pipeline-telemetry')).toBeVisible({ timeout: 15_000 });
    // The jar is what carries it (F-042's mechanism, asserted here because
    // THIS row's "off by default" only means something if the ENABLE
    // persists). Key 'dashboard-config-v2' is zustand persist's own name
    // (STORAGE_KEY store:104 → name option :334, storage :335); the shape is
    // {state:{widgets:[…]}}, so the assertion parses it and reads THIS
    // widget's flag rather than matching a substring — a jar that merely
    // mentions the id while keeping visible:false must not pass.
    const jar = await page.evaluate(() => localStorage.getItem('dashboard-config-v2'));
    expect(jar, 'the store wrote its jar on save').toBeTruthy();
    const parsed = JSON.parse(String(jar)) as {
      state: { widgets: { id: string; visible: boolean }[] };
    };
    const telemetry = parsed.state.widgets.find((w) => w.id === 'pipeline-telemetry');
    expect(telemetry?.visible, 'enable persisted in the jar').toBe(true);

    // THE ROW'S CLAUSE, second half: the enable survives a reload in the same
    // context (batch 1's proven form — same jar, page.reload()).
    await quietBoot(page, h);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('dashboard-layout')).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId('pipeline-telemetry')).toBeVisible({ timeout: 15_000 });

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});

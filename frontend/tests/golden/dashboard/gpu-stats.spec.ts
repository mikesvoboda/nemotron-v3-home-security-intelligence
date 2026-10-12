/**
 * FE-2 golden path (F2.3): F-039 — the GPU statistics widget (off by default):
 * utilization, memory, temperature, inference FPS and a history chart.
 *
 * Decided from shipped code before writing (each claim cites where):
 *
 * - THE DECISIVE FACT ABOUT THIS WIDGET, and it is not in the row: GpuStats is
 *   prop-FED but query-PREFERRED. DashboardPage hands it WebSocket-derived props
 *   (DashboardPage.tsx:603-613, built :516-523), yet the component reads its OWN
 *   React-Query data first — `statsData?.utilization ?? propUtilization ?? null`
 *   (GpuStats.tsx:198-202) — and those queries ARE enabled, because the page
 *   passes no `historyData`, so `useExternalData` is false (:167, :175, :185).
 *   For utilization / memory / temperature / inference FPS the props are a
 *   fallback the query beats as soon as it resolves, so the real producer of
 *   those four DOM strings is GET /api/system/gpu (fetchGPUStats, api.ts:2089,
 *   PARAMLESS) polled every 5 s (useGpuStatsQuery.ts:109 refetchInterval,
 *   REALTIME_STALE_TIME queryClient.ts:48). A Node GET of the same paramless
 *   path is therefore honest ground truth. The two fields the query does NOT
 *   feed are exactly the two the inventory's evidence already calls broken:
 *   gpu_name is a LITERAL, 'NVIDIA RTX A5500' (DashboardPage.tsx:517), and power
 *   is hardcoded null (:522) — which is why powerUsage is read from the PROP
 *   only, with no statsData fallback (:206, :343, :348-349).
 * - WHY AGREEMENT POLLS, NOT ONE-SHOT EQUALITY: GET /api/system/gpu is two-tier
 *   cached — L1 in-memory for HEALTH_CACHE_TTL_SECONDS = 15.0 (system.py:356,
 *   checked :2305-2307; the route's docstring says "~10s", the constant says
 *   15.0) and L2 Redis 'system:gpu:latest' for SHORT_TTL = 60
 *   (cache_service.py:60, written system.py:2393-2397). A single comparison
 *   could therefore catch a transient skew and call it a product bug. Each poll
 *   re-reads the API and compares to the DOM, so a transient resolves and a
 *   persistent mismatch fails naming BOTH values. The history route is NOT
 *   cached (system.py:2405 reads the table directly), but it GROWS while the
 *   monitor runs, so its leg polls for agreement too — see below.
 * - THE CORPUS STATE IS NOT MEASURABLE FROM HERE, so every leg holds under
 *   EITHER state and this header says which half it proves in each. The probe
 *   stack starts postgres/redis/backend/frontend/ai-vlm/ai-gateway and NO
 *   gpu-monitor service (feature_check.py:84 FAKE_SERVICES), yet the backend
 *   starts a GPUMonitor IN-PROCESS (backend/main.py:1065-1066); whether that
 *   monitor writes gpu_stats rows depends on nvidia-smi inside the container,
 *   which this sandbox cannot observe. With no rows the route returns ALL NULLS
 *   (system.py:2327-2355), so the numeric leg then proves the end-to-end NULL
 *   PATH (route → hook → formatValue 'N/A' → DOM): a real chain proof that fails
 *   if the query is disabled, the key drifts, or a formatter changes — but it
 *   does NOT exercise a nonzero number and this spec does not claim it does.
 *   Nonzero formatter paths are unit-covered (GpuStats.test.tsx:108, :126, :144,
 *   :179, :197-305 — 52 cases there).
 * - DOM strings come from the component's OWN formatters, mirrored here with the
 *   cite: formatValue (:82-84) `value !== null ? `${value.toFixed(0)}${suffix}`
 *   : 'N/A'` for utilization (suffix '%', :279), temperature (suffix '°C', :320)
 *   and inference FPS (NO suffix, :362); formatMemory (:89-100) 'N/A' unless
 *   BOTH sides are non-null, else `${(used/1024).toFixed(1)} / ${(total/1024)
 *   .toFixed(1)} GB` (:295); formatValue(powerUsage ?? null, 'W') for the power
 *   span (:343).
 * - HOW THE VALUES ARE READ, since the card tags almost nothing: the shipped
 *   card carries data-testid ONLY on the device name (:265) and the power span
 *   (:341). Inventing a testid here would be an instrument the product does not
 *   have, so each metric is read the way the JSX actually nests it: one flex row
 *   with the label Text and the value Text as SIBLINGS (:274-279 utilization,
 *   :290-295 memory, :306-321 temperature, :359-363 inference FPS; power's row
 *   :328-344 pairs its label with the tagged span). Tremor's Text renders a <p>,
 *   so the locator is the label <p> matched by EXACT text, then its first
 *   following sibling — never a class-name sniff, and never a substring match on
 *   the card, which would let the bare FPS number be "found" inside the history
 *   count text.
 * - History: the app asks for `?limit=60` — the hook's own default
 *   (useGpuStatsQuery.ts:223 limit = 60 → fetchGpuHistory(limit) → api.ts:2092
 *   -2095), NOT the route's 300 (system.py:2406) — so this spec replays the
 *   identical request instead of a wider one that could report rows the widget
 *   never fetched. The panel renders EXACTLY ONE of gpu-history-loading (:399),
 *   gpu-history-error (:406), gpu-history-chart (:421), gpu-history-empty (:426)
 *   — a 4-way discriminator (:396-430) — and gpu-history-count (:435-437)
 *   appears IFF history.length > 0, reading `${n} data point` + 's' when n ≠ 1.
 *   So the honest pairing is: API rows 0 ⇒ EMPTY panel and NO count; API rows
 *   >0 ⇒ CHART and count EQUAL to the fetched length. That is asserted as a
 *   PAIR, per tick, with the row count re-read every tick — a one-shot pairing
 *   would flake the moment the monitor appends a sample between the two reads.
 * - The row's action enumerates no tab interaction, so no tab leg is written;
 *   tabs only pick the series and its formatter (:214-239), which is unit
 *   territory, and clicking them here would add a click this row never claims.
 * - Off-by-default is store DEFAULT_WIDGETS gpu-stats visible:false
 *   (dashboard-config-store.ts:144-147) and enabling goes through F-042's
 *   Configure modal, so the enable is a REAL CLICK PATH and the absent-before
 *   state is asserted first — the row's first two words.
 * - enableGpuWidget below COPIES pipeline-telemetry.spec.ts's enableWidget
 *   rather than importing it, for two reasons: (a) ruling 87's file rule keeps
 *   each batch's files inside its own area so two lanes' PRs never depend on
 *   each other's merge, and (b) that file is UNDER WITNESS at this head, so
 *   refactoring it mid-run would make the green run describe a file that no
 *   longer ships. The copy keeps the load-bearing part — a save is not trusted
 *   until the JAR carries the flag — and states the shipped draft-loss hazard by
 *   cite instead of re-litigating it (pipeline-telemetry.spec.ts:118-145; the
 *   F-040 and F-042 inventory rows carry it too).
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

interface GpuStats {
  utilization: number | null;
  memory_used: number | null;
  memory_total: number | null;
  temperature: number | null;
  power_usage: number | null;
  inference_fps: number | null;
}
interface GpuHistory {
  items: unknown[];
}

/** Mirror of GpuStats.tsx:82-84 — the DOM's exact number→string rule. */
function formatValue(value: number | null | undefined, suffix = ''): string {
  return value !== null && value !== undefined ? `${value.toFixed(0)}${suffix}` : 'N/A';
}

/** Mirror of GpuStats.tsx:89-100 — 'N/A' unless BOTH sides are non-null. */
function formatMemory(used: number | null, total: number | null): string {
  if (used === null || total === null) return 'N/A';
  return `${(used / 1024).toFixed(1)} / ${(total / 1024).toFixed(1)} GB`;
}

/** The literal the page passes as gpuName (DashboardPage.tsx:517) — NOT data. */
const SHIPPED_GPU_NAME_LITERAL = 'NVIDIA RTX A5500';

/** The app's OWN history request: the hook's default limit (hook:223 → api:2092). */
const HISTORY_PATH = '/api/system/gpu/history?limit=60';

async function openDashboard(page: import('@playwright/test').Page, h: DashboardHarness) {
  await seedTourDismissed(page);
  await loginAsAdmin(page, h);
  await quietBoot(page, h);
  await expect(page.getByTestId('dashboard-layout')).toBeVisible({ timeout: 20_000 });
}

/**
 * The painted card. The layout wraps every system widget in a div that DOES
 * carry a testid (DashboardLayout.tsx:207 `data-testid="widget-gpu-stats"`,
 * same pattern :196 for the feed and :216 for telemetry), so this is a shipped
 * attribute rather than one invented here — and unlike the device-name <p> it
 * does not depend on the hardcoded name literal, so it is the honest
 * "the card is on the page" locator.
 */
function cardRoot(page: import('@playwright/test').Page) {
  return page.getByTestId('widget-gpu-stats');
}

/**
 * The value beside a shipped metric label: the label <p> matched by EXACT text,
 * then its first following sibling (structure cited in the header). Scoped to
 * the card so a matching <p> anywhere else on the dashboard can never be read
 * by mistake. Exact match matters twice: it keeps the history tab labelled
 * "Memory" out of the way (Tremor's Tab renders a span, not the <p> this is
 * scoped to), and it keeps "Inference FPS" from matching the "Metrics History"
 * heading.
 */
function metricValue(page: import('@playwright/test').Page, label: string) {
  return cardRoot(page)
    .locator('p')
    .filter({ hasText: new RegExp(`^${label}$`) })
    .first()
    .locator('xpath=following-sibling::*[1]');
}

/** Whitespace-normalized innerText, so an icon-plus-label row still compares. */
async function flat(locator: import('@playwright/test').Locator): Promise<string> {
  return (await locator.innerText()).replace(/\s+/g, ' ').trim();
}

/** Live jar state for one widget: a sentinel string when the id is absent. */
function jarVisible(page: import('@playwright/test').Page, widgetId: string) {
  return page.evaluate((id) => {
    const raw = localStorage.getItem('dashboard-config-v2');
    if (!raw) return 'NO_JAR' as const;
    const st = JSON.parse(raw) as { state?: { widgets?: { id: string; visible: boolean }[] } };
    const w = (st?.state?.widgets ?? []).find((x) => x.id === id);
    return w === undefined ? ('ABSENT' as const) : w.visible;
  }, widgetId);
}

/**
 * Turn the GPU widget ON through the shipped Configure modal (F-042's path) and
 * return an event-driven locator for the painted card.
 *
 * Bounded (≤3) and gated on the COMMITMENT (the jar), never on a timing guess,
 * because run 38168556142 measured THIS modal discarding an unsaved draft on a
 * sibling path: DashboardConfigModal.tsx:109-113 re-seeds its in-editor draft on
 * ANY identity change of the `config` prop, and DashboardLayout.tsx:268 builds
 * that prop as a fresh object literal on every render. A save that reports
 * success the jar never confirms therefore FAILS HERE naming the hazard, rather
 * than the spec papering over it or re-driving forever.
 */
async function enableGpuWidget(page: import('@playwright/test').Page) {
  const widgetId = 'gpu-stats';
  await page.getByTestId('configure-dashboard-button').click();
  await expect(page.getByTestId('widget-list')).toBeVisible();
  for (let attempt = 1; attempt <= 3; attempt++) {
    const sw = page.getByTestId(`widget-toggle-${widgetId}`);
    await expect(sw, 'the shipped toggle is a real switch').toHaveAttribute('role', 'switch');
    if ((await sw.getAttribute('aria-checked')) !== 'true') await sw.click();
    // Poll the REAL attribute — expect.poll retries READS, never actions.
    let latched = true;
    try {
      await expect
        .poll(async () => sw.getAttribute('aria-checked'), {
          message: `gpu-stats toggle latches on (attempt ${attempt})`,
          timeout: 8_000,
        })
        .toBe('true');
    } catch {
      latched = false;
    }
    if (!latched) {
      await page.waitForTimeout(1_000);
      continue;
    }
    await page.getByTestId('save-button').click();
    await expect(page.getByTestId('widget-list'), 'Save closes the modal').toHaveCount(0);
    let saved = true;
    try {
      await expect
        .poll(() => jarVisible(page, widgetId), {
          message: 'the jar carries gpu-stats visible:true',
          timeout: 10_000,
        })
        .toBe(true);
    } catch {
      saved = false;
    }
    if (saved) break;
    if (attempt === 3) {
      throw new Error(
        'Save reported success but the jar never carried gpu-stats visible:true across 3 ' +
          'drives — the modal draft-lossy path (DashboardConfigModal.tsx:109-113 with ' +
          'DashboardLayout.tsx:268) discarded the edit. Product hazard, not an instrument ' +
          'failure; the F-040 and F-042 inventory rows carry the same finding.'
      );
    }
  }
}

test.describe('golden path: dashboard GPU statistics widget @critical', () => {
  test('F-039: off by default, then the enabled card mirrors GET /api/system/gpu (null path included); name and power are props, not data', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    // Headroom for the worst-case 3 modal drives (~57 s) plus boot and paints.
    test.setTimeout(150_000);

    await openDashboard(page, h);

    // THE ROW'S FIRST WORD: off by default means NOT in the DOM before enabling
    // (dashboard-config-store.ts:144-147). The layout only emits the wrapper for
    // a VISIBLE widget (DashboardLayout.tsx:204-212 renders by store order), so
    // the wrapper's absence is the store's own flag, independent of the name
    // literal the device-name <p> would carry.
    await expect(page.getByTestId('widget-gpu-stats')).toHaveCount(0);

    await enableGpuWidget(page);
    const card = cardRoot(page);
    await expect(card, 'the jar-committed enable paints the card').toBeVisible({
      timeout: 45_000,
    });

    // The device name is the shipped LITERAL, asserted AS a literal on purpose
    // (DashboardPage.tsx:517, rendered at GpuStats.tsx:264-268). It does not
    // come from the API, so this passes whether GET /api/system/gpu reports a
    // name or null — and if the card ever becomes data-driven this assert fails
    // LOUD, which is the point: F-039's row would then need re-ruling, not a
    // silent drift to **works**. Scoped INSIDE the card, and read off the
    // device-name node (not the wrapper, whose text is the whole card).
    await expect(
      card.getByTestId('gpu-device-name'),
      'gpu name is the hardcoded literal, not the API value'
    ).toHaveText(SHIPPED_GPU_NAME_LITERAL);

    // Power is the row's OTHER documented break and this is its witness: the
    // span reads the prop only (:206, :343) and the page hardcodes null (:522),
    // so it renders 'N/A' no matter what the API reports. If the API has a
    // wattage while the DOM says N/A, that IS the half-built condition — so it
    // is asserted here rather than avoided.
    const session = await adminSession(h);
    const read = () => api<GpuStats>(h, session, '/api/system/gpu');
    const power = page.getByTestId('gpu-power-usage');
    await expect(power, 'the power span exists in the shipped card').toBeVisible();
    await expect
      .poll(async () => flat(power), {
        message: 'the prop-only power span renders N/A',
        timeout: 15_000,
      })
      .toBe('N/A');

    // THE MIRROR: the four query-fed metrics must equal the API's own values
    // THROUGH the component's own formatters. The route's 15 s / 60 s caches
    // (system.py:356, cache_service.py:60) are why these are agreement polls.
    const metrics = [
      { label: 'Utilization', want: (t: GpuStats) => formatValue(t.utilization, '%') },
      {
        label: 'Memory',
        want: (t: GpuStats) => formatMemory(t.memory_used, t.memory_total),
      },
      { label: 'Temperature', want: (t: GpuStats) => formatValue(t.temperature, '°C') },
      { label: 'Inference FPS', want: (t: GpuStats) => formatValue(t.inference_fps) },
    ];
    for (const m of metrics) {
      await expect
        .poll(
          async () => {
            const t = await read();
            const dom = await flat(metricValue(page, m.label));
            const want = m.want(t);
            return dom === want ? 'agree' : `dom="${dom}" api="${want}"`;
          },
          {
            message: `${m.label} mirrors GET /api/system/gpu through the shipped formatter`,
            timeout: 25_000,
            intervals: [1_000],
          }
        )
        .toBe('agree');
    }

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-039: the history panel and its data-point count mirror GET /api/system/gpu/history?limit=60', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(150_000);

    await openDashboard(page, h);
    await enableGpuWidget(page);
    await expect(cardRoot(page), 'the card must paint before its panel can be read').toBeVisible({
      timeout: 45_000,
    });

    const chart = page.getByTestId('gpu-history-chart');
    const empty = page.getByTestId('gpu-history-empty');
    const count = page.getByTestId('gpu-history-count');
    const session = await adminSession(h);

    // The 4-way discriminator (:396-430) paired with the SAME request the widget
    // makes, RE-READ EVERY TICK: gpu_stats only grows while the in-process
    // monitor runs, so pinning one API read and one panel read a moment apart
    // would flake on an appended sample. A LOADING or ERROR panel is a failure
    // here, never a skip.
    await expect
      .poll(
        async () => {
          const rows = (await api<GpuHistory>(h, session, HISTORY_PATH)).items.length;
          const c = await chart.count();
          const e = await empty.count();
          const panel = c === 1 && e === 0 ? 'chart' : c === 0 && e === 1 ? 'empty' : 'other';
          const want = rows > 0 ? 'chart' : 'empty';
          return panel === want ? 'agree' : `panel=${panel} api_rows=${rows}`;
        },
        {
          message: 'chart iff the API has rows, empty iff it has none',
          timeout: 30_000,
          intervals: [1_000],
        }
      )
      .toBe('agree');

    // The count indicator, same tick against the same read: it renders IFF there
    // are rows, as `${n} data point` + 's' unless n is 1 (:435-437).
    await expect
      .poll(
        async () => {
          const rows = (await api<GpuHistory>(h, session, HISTORY_PATH)).items.length;
          const want = rows === 0 ? 'NO_COUNT' : `${rows} data point${rows === 1 ? '' : 's'}`;
          const dom = (await count.count()) === 0 ? 'NO_COUNT' : await flat(count);
          return dom === want ? 'agree' : `dom="${dom}" want="${want}"`;
        },
        {
          message: 'the data-point count equals the fetched history length',
          timeout: 20_000,
          intervals: [1_000],
        }
      )
      .toBe('agree');

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});

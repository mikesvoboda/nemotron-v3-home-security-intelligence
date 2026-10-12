/**
 * FE-2 golden path (F2.3): F-034 — the summary detail panel on `/`.
 *
 * The row's clause: "clicks 'View Full Summary' on a card; a panel opens with
 * the summary, its event timeline and links to events". Endpoint:
 * GET /api/summaries/{summary_id}/detail (`get_summary_detail`,
 * backend/api/routes/summaries.py:450, cache-first on Redis
 * `summaries:detail:{id}`).
 *
 * Decided from shipped code before writing; every claim cites where. Three
 * findings shaped this spec:
 *
 * 1. THE ROW'S LAST CLAUSE — "links to events" — IS SHIPPED DEAD, and this
 *    spec says so with behavior, not grep. The service builds every timeline
 *    row's url as `/events/{id}` (`backend/services/summary_detail_service.py:147`)
 *    and the panel renders it verbatim into a plain same-tab anchor
 *    (`ExpandableDetailPanel.tsx:127-137`, no target/react-router — a real
 *    navigation). But the SPA route table (`App.tsx:232-329`) defines NO
 *    `/events/:id` route: the catch-all `path="*"` (:329) lands on NotFoundPage
 *    (`not-found-page`, NotFoundPage.tsx:36). nginx's SPA fallback
 *    (`try_files $uri $uri/ /index.html`, docker-entrypoint.sh:285) guarantees
 *    the app itself boots on that URL, so the landing is the SPA's 404, not a
 *    server error. The app's OWN working event-navigation proves the contrast:
 *    DashboardPage routes event clicks to `/timeline?event=<id>` (:319, :327),
 *    and that chain is GREEN as witnessed behavior — F-031's leg "clicking a
 *    card opens /timeline?event=<id>" passed on first attempt (run 38181698242,
 *    ✓ 6, activity-feed.spec.ts:297). So a link to an event EXISTS in the DOM
 *    and DEAD-ENDS in the shipped product: a control wired to nothing, which
 *    is what half-built names (vocabulary section). The row's panel/timeline/
 *    narrative halves are drivable and mirrored here; the link half is
 *    witnessed-dead in test 3 wherever the data branch reaches it.
 * 2. BOTH TIMELINE BRANCHES ARE REAL SHIPPED STATES, so the spec branches on
 *    the endpoint, never on corpus luck. `event_ids` is stored only when the
 *    generator found high/critical events (`summary_generator.py:244,298`),
 *    and the boot-time job runs against the empty seeded DB — the harness's
 *    own smoke event lands AFTER boot (run 38181698242: boot stamp 23:01:00,
 *    smoke-events.json `started_at` 23:02:05), so its summaries carry
 *    event_ids=None and the panel's empty branch ("No events to display",
 *    ExpandableDetailPanel.tsx:364-368) is the expected golden default. A
 *    corpus that does yield events drives the ROWS branch, and every row
 *    assertion is keyed on a fresh Node read of the SAME detail endpoint —
 *    cameraName, summary text, conditional risk badge, conditional
 *    `event-link-<id>` with href equal to the endpoint's own `event_url`.
 *    Formatted times are browser-local (format(parseISO(...))), so they are
 *    asserted as PRESENCE/shape only — batch 5's footer rule: an equality
 *    compare across processes would be a timezone test, not a feature test.
 * 3. THE EXPORT SECTION IS NOT THIS ROW'S CLAIM — it is F-035's row, already
 *    adjudicated half-built in the inventory: the buttons call `handleExport`,
 *    which acts only `if (onExport)` (`ExpandableDetailPanel.tsx:240-247`),
 *    and the dashboard's ONLY mount never passes `onExport`
 *    (`DashboardPage.tsx:636-641`), so every click is a silent no-op, and the
 *    served `export_summary` route (`summaries.py:581`) has no frontend
 *    caller. Per the row split this spec asserts the section PRESENT (it is
 *    part of the shipped panel the user sees) and deliberately does NOT
 *    re-litigate the click behavior — that break is stated, cited and action-
 *    slated ("retire", R2a row 18) in F-035's own cell.
 *
 * Not driveable from inside a golden run, stated per ruling 86 rather than
 * faked or left red: the fetch-failure FALLBACK (DashboardPage.tsx:355-381 —
 * on a failed detail fetch the panel opens anyway from card data, INVENTING
 * `summaryType` from the window span (:366-371) and hardcoding
 * `exportFormats` (:377)). Nothing can make an existing summary's detail GET
 * fail from outside: the golden guard forbids `page.route` (guard.ts:46), the
 * harness's Node helper is GET-only, and no shipped route deletes a summary
 * (jobs.py's POSTs are cancel/abort/bulk-cancel/events-export; summaries.py
 * is GET-only). The fallback therefore stays unverified code, named here.
 *
 * `bootDashboard` is batch 5's settled-boot gate copied, not imported
 * (ruling 87 keeps each batch's files inside its own area dir): it refuses to
 * let the lane's nginx `zone=api` shed class (burst=20,
 * `frontend/docker-entrypoint.sh:139`) be misread as a product break, because
 * a shed REPLACES the whole dashboard with DashboardPage's own error page
 * (:434-449) before the layout (:478) ever appears.
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
import type { Page } from '@playwright/test';

const harness = readDashboardHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

// ---------------------------------------------------------------------------
// The detail endpoint's shape, narrowed to the fields the panel reads
// (batch 5/6/7 convention: declared locally; the mirror compares the browser
// against the SAME fields fetchSummaryDetail consumed, api.ts:8019-8045).
// ---------------------------------------------------------------------------
interface ApiTimelineEvent {
  event_id: number;
  timestamp: string | null;
  camera_name: string | null;
  summary: string;
  risk_score?: number | null;
  risk_level?: string | null;
  event_url?: string | null;
}
interface ApiDetail {
  id: number;
  summary_type: string;
  content: string;
  event_count: number;
  window_start: string;
  window_end: string;
  generated_at: string;
  timeline: ApiTimelineEvent[];
  export_formats: string[];
}
interface ApiLatestSummary {
  id: number;
  content: string;
}
interface ApiLatest {
  hourly: ApiLatestSummary | null;
  daily: ApiLatestSummary | null;
}
type SummaryType = 'hourly' | 'daily';
const TYPES: SummaryType[] = ['hourly', 'daily'];

/**
 * Mirror of the panel's OWN header derivation, not of the endpoint: the
 * heading comes from `detail.summaryType === 'hourly'` with NO case folding
 * (`ExpandableDetailPanel.tsx:253-255` fed by api.ts:8026's `as`-cast), so an
 * API value of 'HOURLY' would render "Daily Summary" and the mirror must say
 * THAT too. Mirroring the cast is the whole point — mirroring the intent
 * would agree with the spec's hope instead of the shipped code.
 */
function mirrorTypeLabel(summaryType: string): string {
  return summaryType === 'hourly' ? 'Hourly Summary' : 'Daily Summary';
}

/** The shipped event-count chip text (panel :299-301, `1 event`/`N events`). */
function mirrorCountChip(n: number): string {
  return `${n} ${n === 1 ? 'event' : 'events'}`;
}

/** Panel handles, all scoped to the dialog itself (the dashboard stays mounted
 *  behind the overlay, so a page-wide locator can collide with card text). */
function panelOf(page: Page) {
  const panel = page.getByTestId('expandable-detail-panel');
  return {
    panel,
    overlay: page.getByTestId('detail-panel-overlay'),
    title: panel.locator('h2'),
    narrative: panel.getByTestId('detail-narrative'),
    timeWindow: panel.getByTestId('detail-time-window'),
    close: page.getByTestId('detail-panel-close'),
    timelineRow: (eventId: number) => panel.getByTestId(`timeline-event-${eventId}`),
    riskBadge: (eventId: number) => panel.getByTestId(`risk-badge-${eventId}`),
    eventLink: (eventId: number) => panel.getByTestId(`event-link-${eventId}`),
    exportJson: panel.getByTestId('export-json-btn'),
    exportCsv: panel.getByTestId('export-csv-btn'),
    exportPdf: panel.getByTestId('export-pdf-btn'),
  };
}

/** Boot to a SETTLED dashboard (batch 5's shed-class gate, copied per ruling
 *  87 — see the header for why polling replaces sequencing). */
async function bootDashboard(page: Page, h: DashboardHarness) {
  await seedTourDismissed(page);
  await loginAsAdmin(page, h);
  await quietBoot(page, h);

  const errorPage = page.getByRole('heading', { name: 'Error Loading Dashboard' });
  const layout = page.getByTestId('dashboard-layout');
  await expect
    .poll(
      async () => {
        if ((await errorPage.count()) > 0) return 'shed';
        if ((await layout.count()) > 0) return 'ok';
        return 'pending';
      },
      {
        message:
          'the dashboard neither rendered nor showed its own error page — the lane nginx ' +
          'zone=api shed class (docker-entrypoint.sh:139, burst=20) landing on a boot ' +
          'replaces the dashboard with DashboardPage.tsx:434-449 before :478 appears',
        timeout: 30_000,
        intervals: [500],
      }
    )
    .toBe('ok');
}

/** Open the panel for one type the API has a summary for, then read the SAME
 *  detail from Node so every mirror is keyed on the endpoint, not the DOM. */
async function openPanel(
  page: Page,
  h: DashboardHarness,
  type: SummaryType,
  summaryId: number
): Promise<ApiDetail> {
  await page.getByTestId(`summary-view-full-${type}`).click();
  await expect(
    panelOf(page).panel,
    `${type}: clicking View Full Summary opened no dialog (the click runs ` +
      `handleViewFullSummary, DashboardPage.tsx:352-385 — an unmounted panel means the detail ` +
      `fetch threw and even the fallback path failed to mount)`
  ).toBeVisible();
  return api<ApiDetail>(h, await adminSession(h), `/api/summaries/${summaryId}/detail`);
}

test.describe('golden path: dashboard summary detail panel @critical', () => {
  test('F-034: View Full Summary opens a dialog mirroring GET /api/summaries/{id}/detail — header type label, event-count chip, narrative, window shape — and closes by button, overlay and Escape, with focus re-landed on reopen', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(120_000);

    await bootDashboard(page, h);
    const session = await adminSession(h);
    const latest = await api<ApiLatest>(h, session, '/api/summaries/latest');
    const L = panelOf(page);

    for (const type of TYPES) {
      const summary = latest[type];
      if (!summary) {
        // The empty card renders NO View Full Summary control at all
        // (SummaryCardEmpty.tsx:93-107 carries only the optional "View All
        // Events" button), so the row's entry point must be absent — an
        // AGREEING empty branch, asserted, not skipped.
        await expect(
          page.getByTestId(`summary-view-full-${type}`),
          `${type}: the empty card must not offer View Full Summary`
        ).toHaveCount(0);
        continue;
      }

      const detail = await openPanel(page, h, type, summary.id);

      // Header pair, both mirrored from the Node read (mirrorTypeLabel
      // deliberately mirrors api.ts's case-uncaring cast — see its comment).
      await expect(
        L.title,
        `${type}: the dialog heading does not mirror summary_type=${JSON.stringify(
          detail.summary_type
        )} the way ExpandableDetailPanel.tsx:253-255 derives it`
      ).toHaveText(mirrorTypeLabel(detail.summary_type));
      await expect(
        L.panel.getByText(mirrorCountChip(detail.event_count), { exact: true }),
        `${type}: the header chip does not mirror event_count=${detail.event_count} with the ` +
          `shipped pluralization (panel :299-301)`
      ).toHaveCount(1);

      // The narrative IS an API value (detail.content, :326), so unlike the
      // cards' client-parsed bullets it is asserted EXACTLY.
      await expect(
        L.narrative,
        `${type}: the narrative does not equal the endpoint's content`
      ).toHaveText(detail.content);

      // Browser-local format (format(parseISO(...), 'MMM d, h:mm a' - 'h:mm a',
      // :258-261)) → presence/shape only, batch 5's footer rule.
      await expect(
        L.timeWindow,
        `${type}: no time window rendered despite window_start/window_end both present`
      ).toContainText(/\d{1,2}:\d{2} (AM|PM)/);

      // The mount effect focuses the close button on open (:209-213) — proven,
      // because the Escape leg depends on focus living INSIDE the dialog.
      await expect(L.close, 'the close button is not focused on open').toBeFocused();

      // Close by button, prove full unmount (the dashboard's mount is `&&`-
      // gated, DashboardPage.tsx:636 — isOpen=false alone would ALSO unmount
      // via the panel's :249-251 early return; the handler nulls the detail
      // (:386-389), so this proves the shipped close, either path).
      await L.close.click();
      await expect(L.panel, 'the close button did not dismiss the dialog').toHaveCount(0);

      // Reopen → refetch → focus again. Then Escape, which is NOT the React
      // onKeyDown that rots on body-targeted events (that family fails
      // silently): the panel listens on `document` directly (:216-227), so a
      // real keyboard press must land wherever focus is.
      await page.getByTestId(`summary-view-full-${type}`).click();
      await expect(L.panel).toBeVisible();
      await expect(L.close, 'the close button is not focused after reopen').toBeFocused();
      await page.keyboard.press('Escape');
      await expect(L.panel, 'Escape did not close the dialog').toHaveCount(0);

      // Overlay click closes only when the click IS the overlay (target===
      // currentTarget guard, :230-237): the panel is centered max-w-2xl, so
      // (5,5) is overlay canvas, and the fixed inset-0 z-50 layer makes the
      // hit unambiguous.
      await page.getByTestId(`summary-view-full-${type}`).click();
      await expect(L.panel).toBeVisible();
      await L.overlay.click({ position: { x: 5, y: 5 } });
      await expect(
        L.panel,
        'a click on the overlay canvas (not the panel) must close it (:230-237)'
      ).toHaveCount(0);
    }

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test("F-034: the timeline section is keyed on the endpoint — no events renders the shipped empty branch, events render rows mirroring camera/summary/conditional badge, and the Export section is present (its click behavior is F-035's adjudicated row)", async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(120_000);

    await bootDashboard(page, h);
    const session = await adminSession(h);
    const latest = await api<ApiLatest>(h, session, '/api/summaries/latest');
    const withSummary = TYPES.find((t) => latest[t]);
    if (!withSummary) {
      test
        .info()
        .skip(
          true,
          'GET /api/summaries/latest carried neither type, so there is no card to open — ' +
            "F-033's own empty-card branch witnessed that state end-to-end; here the " +
            'detail-panel row needs at least one summary to drive.'
        );
      return;
    }
    const summary = latest[withSummary]!;
    const detail = await openPanel(page, h, withSummary, summary.id);
    const L = panelOf(page);

    if (detail.timeline.length === 0) {
      // The expected golden default (header cite 2): boot summaries carry
      // event_ids=None, the route fetches events only `if summary.event_ids`
      // (summaries.py:492), so the shipped empty branch must render AND no
      // row-shaped testid may exist anywhere in the panel.
      await expect(
        L.panel.getByText('No events to display'),
        `${withSummary}: event_ids is null on this summary, so the timeline must show the ` +
          `shipped empty branch (ExpandableDetailPanel.tsx:364-368)`
      ).toBeVisible();
      await expect(
        L.panel.locator('[data-testid^="timeline-event-"]'),
        'no timeline events, yet row-shaped testids exist'
      ).toHaveCount(0);
    } else {
      // The rows branch, every value pinned to the SAME endpoint the panel
      // rendered. Ordering is the service's own (build_timeline sorts
      // ascending, summary_detail_service.py:117) — asserted positionally
      // against the endpoint array, so a client re-sort would surface.
      await expect(
        L.panel.getByText('No events to display'),
        'the endpoint carries events but the empty branch rendered'
      ).toHaveCount(0);
      // A sequential for-of, NOT forEach: async callbacks inside forEach are
      // never awaited, so every assert below would float past the test's end
      // and the branch could not fail — an unfailable leg is a fake leg.
      for (const [i, ev] of detail.timeline.entries()) {
        const row = L.timelineRow(ev.event_id);
        await expect(
          row,
          `timeline row ${i} (event_id ${ev.event_id}) is not in the DOM`
        ).toHaveCount(1);
        if (ev.camera_name) {
          await expect(row).toContainText(ev.camera_name);
        }
        await expect(row, `row ${i}: summary text does not mirror the endpoint`).toContainText(
          ev.summary
        );
        // Conditional surfaces mirror their shipped conditions, so a badge
        // appearing from nothing fails as loudly as a missing one
        // (TimelineEventRow :114-123): risk badge iff risk_level.
        await expect(
          L.riskBadge(ev.event_id),
          `row ${i}: risk badge presence does not mirror risk_level=${JSON.stringify(
            ev.risk_level
          )}`
        ).toHaveCount(ev.risk_level ? 1 : 0);
        if (ev.risk_level) {
          await expect(L.riskBadge(ev.event_id)).toHaveText(ev.risk_level);
        }
        // The time cell renders format(parseISO(ts)) or the literal "Unknown
        // time" (:80-82) — presence only (browser-local), including for null.
        await expect(
          row.getByText(/Unknown time|\d{1,2}:\d{2}:\d{2} (AM|PM)/).first(),
          `row ${i}: no time cell (neither formatted time nor "Unknown time")`
        ).toHaveCount(1);
      }
    }

    // The Export section is PART OF THE PANEL the row opens, so it must exist;
    // its dead click behavior belongs to F-035's own inventory row (header
    // cite 3) and is stated there, cited and action-slated — not re-litigated
    // here, per the inventory's row split.
    for (const btn of [L.exportJson, L.exportCsv, L.exportPdf]) {
      await expect(btn, 'the panel mounts without an Export button').toBeVisible();
    }

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-034: the per-event link mirrors the endpoint event_url and WHERE IT LANDS when followed — the shipped /events/{id} href has no SPA route, and the dialog-less app must answer it with its own NotFoundPage', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(120_000);

    await bootDashboard(page, h);
    const session = await adminSession(h);
    const latest = await api<ApiLatest>(h, session, '/api/summaries/latest');
    const withSummary = TYPES.find((t) => latest[t]);
    if (!withSummary) {
      test.info().skip(true, 'no summary exists to open (test 2 states this branch)');
      return;
    }
    const summary = latest[withSummary]!;
    const detail = await openPanel(page, h, withSummary, summary.id);
    const linked = detail.timeline.find((ev) => ev.event_url);
    if (!linked) {
      test
        .info()
        .skip(
          true,
          `the detail for summary ${summary.id} carries no event_url row, so the deep-link leg ` +
            `has nothing to click. This is the EXPECTED golden regime, not a dodge: the boot ` +
            `summary job runs before any event exists (summary_generator.py:244,298 stores ` +
            `event_ids only when events were found; run 38181698242: boot 23:01:00 vs smoke ` +
            `event 23:02:05), and no shipped route can regenerate summaries inside a run. ` +
            `THE DEAD LINK ITSELF NEEDS NO DATA TO ESTABLISH — the href is hardcoded ` +
            `/events/{id} (summary_detail_service.py:147) and App.tsx:232-329 routes no ` +
            `/events/:id (catch-all :329 → NotFoundPage) — so a corpus whose summaries carry ` +
            `events drives this leg; where it skips, the finding stands on those cites plus ` +
            `test 2's structural mirror. (ruling 86: stated, not faked.)`
        );
      return;
    }

    const L = panelOf(page);
    const link = L.eventLink(linked.event_id);
    // Mirror first: the anchor's href IS the endpoint's event_url, verbatim
    // (api.ts maps event_url→eventUrl with `?? undefined`, :8039; the anchor
    // passes it through unmodified, panel :128). This is the clause "links to
    // events" at its BEST possible reading.
    await expect(link).toHaveAttribute('href', linked.event_url as string);

    // Then the WHOLE clause: a real click on a real anchor. The anchor has no
    // target and no router (panel :127-137), so the browser really navigates;
    // nginx's SPA fallback (docker-entrypoint.sh:285) serves index.html; and
    // the route table answers /events/<n> with NotFoundPage — the app's OWN
    // 404, with the session cookie still on the context so ProtectedRoute
    // lets the boot through to the router. Asserting this landing is GREEN
    // while naming a DEAD feature: the row cannot reach a passing grade on a
    // link that goes nowhere (that is why the row ships half-built with the
    // cite pair), and a later fix (a /timeline?event= href, the route itself,
    // or an R2a retire) must turn THIS test red to be noticed — the assert
    // below is written against the CURRENT broken destination on purpose.
    await link.click();
    await expect(
      page.getByTestId('not-found-page'),
      `following the timeline link (href ${JSON.stringify(
        linked.event_url
      )}) no longer lands on NotFoundPage — either the deep-link break at ` +
        `App.tsx:232-329 was FIXED (update F-034's row and this assert together: the app's ` +
        `working destination is /timeline?event=<id>, DashboardPage.tsx:319/:327, witnessed by ` +
        `F-031's green leg) or navigation itself regressed`
    ).toBeVisible();
    expect(new URL(page.url()).pathname).toBe(linked.event_url as string);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});

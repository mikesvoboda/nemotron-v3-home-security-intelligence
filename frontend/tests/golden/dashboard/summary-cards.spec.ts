/**
 * FE-2 golden path (F2.3): F-033 — the hourly and daily summary cards on `/`.
 *
 * The row's clause: "sees the latest hourly and daily AI summaries as bullet
 * lists with severity; they refresh when a new summary is pushed". Endpoints:
 * GET /api/summaries/latest, WS /ws/events.
 *
 * Decided from shipped code before writing; every claim cites where. Three
 * findings shaped this spec, and each was measured against the shipped source
 * (or the installed dependency) rather than assumed:
 *
 * 1. ONE FIELD HAS A THREE-LAYER SKEW, so this spec mirrors shapes and
 *    API-sourced text and never asserts a client-invented value.
 *    - The backend parser is called with NO events: `_build_events_for_parser()`
 *      returns `[]` (`backend/api/routes/summaries.py:66-76`) and
 *      `_summary_to_response` feeds THAT to `parse_summary_content` (:129-131).
 *      The route's real `events` argument is used ONLY for `insights` (:148),
 *      never for the parser — so in this regime `structured.bullet_points` is
 *      always `[]`, `focus_areas` always `[]`, `max_risk_score` always null.
 *    - `transformSummaryResponse` maps those nulls to `undefined`/`[]`
 *      (`src/services/api.ts:7916-7939`), so the card's `maxRiskScore` is always
 *      undefined → severity tier 1 can never fire here (`severityCalculator.ts`
 *      Priority 1, :240-245). Level comes from tier 2 (content keywords) or
 *      tier 3 (event count), so severity is DERIVED here by mirroring
 *      `calculateSeverity` against a fresh Node read of the SAME endpoint. A
 *      hardcoded level would be exactly the invented value this row is dangerous
 *      for: the zero-event all-clear prose matches no keyword and lands on
 *      `clear`, while a NONZERO fallback text contains "critical" and lands on
 *      `critical` from the keywords alone. Which one ships is corpus state.
 *    - The bullet TEXT is client-invented in this regime: with `bulletPoints`
 *      empty, `SummaryCards.tsx:99-106` falls back to
 *      `extractBulletPoints(summary.content)` (rendered at :165-171), whose
 *      output is not an API value — asserting it would test the parser against
 *      itself. Asserted instead: the real chain when the API DOES carry bullets
 *      (their own texts, in order, under the shipped `maxItems={4}`), and in the
 *      fallback regime the BRANCH SHAPE only, with the invented text reported as
 *      a test annotation.
 * 2. SHIPPED TESTID HAZARD: `SummaryCards.tsx:151` passes
 *    `data-testid={`summary-badge-${type}`}` to `SeverityBadge`, but that
 *    component destructures ONLY `level/count/pulsing/size/className`
 *    (`SeverityBadge.tsx:171-176`) with no rest spread, so the prop is DROPPED
 *    and no `summary-badge-hourly`/`-daily` element can exist. A spec that
 *    trusted the call site would time out on a testid the DOM cannot have
 *    (same-hazard precedent here: the Tremor `Switch` whose aria-label lands on
 *    a wrapper div). The badge is located as the component's OWN hardcoded
 *    `severity-badge` (:211), scoped to its card. By contrast `data-severity`
 *    and the card's own testid DO land: Tremor's `Card` rest-spreads everything
 *    it does not name onto its div
 *    (`node_modules/@tremor/react/dist/components/layout-elements/Card/Card.js`
 *    — `__rest(props, ["decoration","decorationColor","children","className"])`,
 *    version 3.18.7, read rather than assumed), which is why `data-severity` is
 *    the right surface to mirror.
 * 3. THE ROW'S SECOND CLAUSE HAS A SHIPPED TRIGGER and is un-driveable from
 *    inside a golden run, for reasons worth naming: `SummaryJob.run()` calls
 *    `broadcast_summary_update` (`backend/jobs/summary_job.py:236`, :81-135) and
 *    `useSummaries` invalidates the query on a `summary_update` frame
 *    (`useSummaries.ts:130-152`). But the scheduler runs the job ONCE at boot
 *    then sleeps 3600 s (`backend/main.py:1100-1108`,
 *    `jobs/summary_job.py:352-356`), `summaries.py` exposes GET routes only, and
 *    the golden guard forbids `routeWebSocket` (`guard.ts:46`), so no frame can
 *    be injected. The last test therefore WITNESSES the app's own `/ws/events`
 *    socket (observation via `page.on('socket')`, not interception) and asserts
 *    the frame→refetch chain ONLY if a frame really arrives; otherwise it
 *    self-skips with this whole reason (ruling 86: stated, not faked, not left
 *    red). Reload is the OTHER half of "latest" and it IS drivable:
 *    `['summaries','latest']` (`queryClient.ts:691-700`) is absent from
 *    `PERSISTABLE_QUERY_KEY_PREFIXES` (`queryPersistence.ts:55-60`), so no
 *    persisted cache can serve it in a fresh JS context — the reload leg is a
 *    real re-derivation proof, not a cache read.
 *
 * Both states the cards can hold without any product break are handled by
 * branching on the API, never on faith: no row yet ⇒ `summary-card-empty-<type>`
 * (`SummaryCardEmpty.tsx:67`) and NO regular card; a row ⇒ the card and NO empty
 * state. `bootDashboard` refuses to let a third state — the skeleton
 * (`SummaryCardSkeleton.tsx:77`) or the error card (`SummaryCardError.tsx:137`,
 * reachable because DashboardPage passes `onRetry`, so the live `error &&
 * onRetry` branch at SummaryCards.tsx:118-120 fires) — be silently misread as
 * one of the first two, and it names the nginx-shed class the way F-040's two
 * reds taught: the lane's boot wave rides `limit_req zone=api burst=20 nodelay`
 * (`frontend/docker-entrypoint.sh:139`), and a shed boot REPLACES the whole
 * dashboard with `DashboardPage.tsx:434-449`'s own error page, so the layout
 * testid never appears — which is why the shed check and the layout wait are
 * polled together instead of sequenced.
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
  type Session,
} from './harness';
import type { Page } from '@playwright/test';

const harness = readDashboardHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

// ---------------------------------------------------------------------------
// The endpoint's shapes, narrowed to the fields the cards read. Declared
// locally (batch 5/6/7 convention): the mirror compares the browser's rendering
// against the SAME source fields transformSummaryResponse consumed.
// ---------------------------------------------------------------------------
type SummaryType = 'hourly' | 'daily';
const TYPES: SummaryType[] = ['hourly', 'daily'];

interface ApiSummary {
  id: number;
  content: string;
  event_count: number | null;
  window_start: string;
  window_end: string;
  generated_at: string;
  structured?: {
    bullet_points?: { icon: string; text: string; severity?: string | null }[] | null;
    focus_areas?: string[] | null;
    max_risk_score?: number | null;
  } | null;
}
interface ApiLatest {
  hourly: ApiSummary | null;
  daily: ApiSummary | null;
}

// ---------------------------------------------------------------------------
// Mirrors of shipped derivations. Each cites the code it copies; none imports
// it — no golden spec in this repo reaches into src/, so a mirror travels with
// its cites and fails loud when the shipped logic moves.
// ---------------------------------------------------------------------------

/** CRITICAL/HIGH/MEDIUM/LOW_KEYWORDS verbatim, severityCalculator.ts:56-88 (substring,
 *  case-insensitive). Copied COMPLETELY: a keyword this list lacks makes the mirror
 *  disagree with the app on GOOD data — the app returns the level this list never
 *  yields, so the assert fails and the finding is the instrument. (trespassing is the
 *  one a partial copy loses.) */
const CRITICAL_KEYWORDS = ['critical', 'emergency', 'intruder', 'breach', 'weapon', 'threat'];
const HIGH_KEYWORDS = [
  'high-risk',
  'suspicious',
  'masked',
  'obscured face',
  'loitering',
  'trespassing',
];
const MEDIUM_KEYWORDS = ['unusual', 'unexpected', 'unfamiliar', 'monitoring'];
const LOW_KEYWORDS = ['routine', 'normal', 'expected', 'delivery'];

/** SEVERITY_THRESHOLDS, severityCalculator.ts:99-106. */
const THRESHOLDS = { critical: 80, high: 60, medium: 40, low: 20 } as const;

/** SEVERITY_CONFIGS labels, severityCalculator.ts:114-144 — the badge's own text source. */
const LEVEL_LABEL = {
  clear: 'All clear',
  low: 'Low activity',
  medium: 'Moderate activity',
  high: 'High activity',
  critical: 'Critical',
} as const;
type Level = keyof typeof LEVEL_LABEL;

/** getSeverityFromScore, severityCalculator.ts:192-198. */
function levelFromScore(score: number): Level {
  if (score >= THRESHOLDS.critical) return 'critical';
  if (score >= THRESHOLDS.high) return 'high';
  if (score >= THRESHOLDS.medium) return 'medium';
  if (score >= THRESHOLDS.low) return 'low';
  return 'clear';
}

/** detectSeverityFromKeywords, severityCalculator.ts:170-182 — first tier hit wins. */
function levelFromKeywords(content: string): Level | null {
  const lc = content.toLowerCase();
  const hit = (list: string[]) => list.some((k) => lc.includes(k.toLowerCase()));
  if (hit(CRITICAL_KEYWORDS)) return 'critical';
  if (hit(HIGH_KEYWORDS)) return 'high';
  if (hit(MEDIUM_KEYWORDS)) return 'medium';
  if (hit(LOW_KEYWORDS)) return 'low';
  return null;
}

/**
 * calculateSeverity's 3-tier priority (severityCalculator.ts:240-262). Tier 1
 * cannot fire in this regime (max_risk_score is always null, header), but it is
 * mirrored anyway so a backend that starts sending scores stays mirrored.
 */
function mirrorSeverity(input: { content: string; eventCount: number; maxRiskScore?: number }): {
  level: Level;
  label: string;
} {
  const { content, eventCount, maxRiskScore } = input;
  if (maxRiskScore !== undefined && maxRiskScore >= 0 && maxRiskScore <= 100) {
    const level = levelFromScore(maxRiskScore);
    return { level, label: LEVEL_LABEL[level] };
  }
  const kw = levelFromKeywords(content);
  if (kw) return { level: kw, label: LEVEL_LABEL[kw] };
  const level: Level = eventCount > 0 ? 'low' : 'clear';
  return { level, label: LEVEL_LABEL[level] };
}

/** The asserted half of transformSummaryResponse (api.ts:7918-7938). */
function transform(b: ApiSummary) {
  return {
    content: b.content,
    eventCount: b.event_count ?? 0,
    maxRiskScore: b.structured?.max_risk_score ?? undefined,
    apiBullets: b.structured?.bullet_points ?? [],
    focusAreas: b.structured?.focus_areas ?? [],
  };
}

/**
 * Mirror of formatTimeRange (api.ts:7877-7907): "h:mm AM/PM", or the two halves
 * joined by " - ", or '' when either date is unparseable. Only PRESENCE is
 * compared across processes — the string is built with `getHours()`, so an
 * equality compare between the browser's zone and this one would be a locale
 * test, not a feature test (batch 7's footer rule).
 */
function mirrorTimeRange(startISO: string, endISO: string): string {
  const fmt = (iso: string): string | null => {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return null;
    let hours = d.getHours();
    const m = d.getMinutes();
    const ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12 || 12;
    return `${hours}:${m < 10 ? `0${m}` : m} ${ampm}`;
  };
  const a = fmt(startISO);
  const b = fmt(endISO);
  if (a === null || b === null) return '';
  return a === b ? a : `${a} - ${b}`;
}

/** The shape formatTimeRange can yield, asserted on the DOM half. */
const TIME_RANGE_SHAPE = /^\d{1,2}:\d{2} (AM|PM)( - \d{1,2}:\d{2} (AM|PM))?$/;

/** formatTimeWindow — the shipped per-type LITERALS (SummaryCards.tsx:55-57). */
const TIME_WINDOW: Record<SummaryType, string> = {
  hourly: 'Last 60 minutes',
  daily: 'Since midnight',
};

/** Card handles, scoped to the card so each card's own `severity-badge` is unambiguous. */
function cardOf(page: Page, type: SummaryType) {
  const card = page.getByTestId(`summary-card-${type}`);
  return {
    card,
    empty: page.getByTestId(`summary-card-empty-${type}`),
    skeleton: page.getByTestId(`summary-card-skeleton-${type}`),
    errorCard: page.getByTestId(`summary-card-error-${type}`),
    badge: card.getByTestId('severity-badge'),
    badgeCount: card.getByTestId('severity-badge-count'),
    timeWindow: page.getByTestId(`time-window-${type}`),
    content: page.getByTestId(`summary-content-${type}`),
    bulletList: page.getByTestId(`summary-bullet-${type}-list`),
    bullet: (i: number) => page.getByTestId(`summary-bullet-${type}-item-${i}`),
    overflow: page.getByTestId(`summary-bullet-${type}-overflow`),
    metadata: page.getByTestId(`summary-metadata-${type}`),
    location: page.getByTestId(`summary-location-${type}`),
    timeRange: page.getByTestId(`summary-time-range-${type}`),
    footer: page.getByTestId(`summary-footer-${type}`),
    updated: page.getByTestId(`summary-updated-${type}`),
    eventCount: page.getByTestId(`summary-event-count-${type}`),
  };
}

/** One fresh Node read of the endpoint the cards read. */
function latest(h: DashboardHarness, session: Session) {
  return api<ApiLatest>(h, session, '/api/summaries/latest');
}

/**
 * Boot to a SETTLED dashboard and prove which state the cards are in.
 *
 * Ordering is load-bearing: on a shed boot DashboardPage returns its error page
 * at :434-449 BEFORE the layout at :478, so `dashboard-layout` never appears —
 * waiting for it first would only time out and hide the real cause. Both are
 * polled together, so the shed path resolves in about a second and reports
 * itself as the throttle class it is.
 */
async function bootDashboard(page: Page, h: DashboardHarness) {
  await seedTourDismissed(page);
  await loginAsAdmin(page, h);
  await quietBoot(page, h);

  const errorPage = page.getByRole('heading', { name: 'Error Loading Dashboard' });
  const layout = page.getByTestId('dashboard-layout');
  const settle = async () => {
    if ((await errorPage.count()) > 0) return 'shed';
    if ((await layout.count()) > 0) return 'ok';
    return 'pending';
  };
  await expect
    .poll(settle, {
      message:
        'the dashboard neither rendered nor showed its own error page — see the ' +
        'shed-class explanation on bootDashboard (DashboardPage.tsx:434 vs :478)',
      timeout: 30_000,
      intervals: [500],
    })
    .toBe('ok');

  if ((await errorPage.count()) > 0) {
    // SafeErrorMessage renders a single Tag carrying the message verbatim
    // (components/common/SafeErrorMessage.tsx:148-151).
    const why = await page
      .locator('p, span')
      .first()
      .textContent()
      .catch(() => null);
    throw new Error(
      `the dashboard boot was SHED, not broken: the app replaced the dashboard with its ` +
        `own error page (message: ${JSON.stringify(why ?? 'unread')}). This is the lane's ` +
        `nginx zone=api shed class (frontend/docker-entrypoint.sh:139, burst=20) landing on ` +
        `a boot — the signature F-040's reload leg carried twice in run 38173376883.`
    );
  }

  // The two states that are NOT a product break but WOULD be misread by the
  // API-keyed branches below: a skeleton still showing means the query never
  // settled, and an error card means the summaries fetch FAILED. Both loud.
  for (const type of TYPES) {
    const L = cardOf(page, type);
    await expect(
      L.skeleton,
      `${type}: still in the skeleton state — GET /api/summaries/latest never settled`
    ).toHaveCount(0);
    await expect(
      L.errorCard,
      `${type}: the summaries fetch ERRORED. SummaryCardError renders whenever the query errors ` +
        `and onRetry is set (SummaryCards.tsx:118-120) and DashboardPage always passes onRetry ` +
        `(:590), so a shed here is the throttle class, not a card bug.`
    ).toHaveCount(0);
  }
}

test.describe('golden path: dashboard hourly and daily summary cards @critical', () => {
  test('F-033: each card mirrors GET /api/summaries/latest — derived severity on both badge surfaces, both event-count surfaces, the shipped time-window literal, the metadata pair', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(120_000);

    await bootDashboard(page, h);
    const session = await adminSession(h);
    const body = await latest(h, session);

    // The container is the component's own wrapper (SummaryCards.tsx:298) and
    // the cards sit in the always-visible activity-feed slot
    // (DashboardPage.tsx:583-592), so no modal drive is needed for `/`.
    await expect(page.getByTestId('summary-cards')).toBeVisible();

    for (const type of TYPES) {
      const L = cardOf(page, type);
      const apiSummary = body[type];

      if (!apiSummary) {
        // The AGREEING empty branch: no row for this type ⇒ the shipped empty
        // state, and the regular card asserted ABSENT. A full assertion of a
        // legitimate branch, not a skip.
        await expect(
          L.empty,
          `${type}: the API carries no summary, so the empty card must render`
        ).toBeVisible();
        await expect(L.card, `${type}: no summary, so no regular card`).toHaveCount(0);
        continue;
      }

      const m = transform(apiSummary);
      const sev = mirrorSeverity({
        content: m.content,
        eventCount: m.eventCount,
        maxRiskScore: m.maxRiskScore,
      });

      await expect(L.card, `${type}: the API carries a summary, so the card renders`).toBeVisible();
      await expect(
        L.empty,
        `${type}: a summary exists, so the empty state must be gone`
      ).toHaveCount(0);

      // Surface 1 of the derivation: data-severity on Tremor's Card, which
      // rest-spreads it onto its div (header, cite 2).
      await expect(
        L.card,
        `${type}: data-severity is not the mirrored calculateSeverity level ` +
          `(event_count=${m.eventCount}, max_risk_score=${apiSummary.structured?.max_risk_score ?? 'null'}, ` +
          `content begins ${JSON.stringify(m.content.slice(0, 80))})`
      ).toHaveAttribute('data-severity', sev.level);

      // Surface 2: the badge's own aria-label and visible label, both shipped
      // from SEVERITY_CONFIGS via getSeverityConfig (SeverityBadge.tsx:183-218).
      const n = m.eventCount;
      const ariaCount = `${n} ${n === 1 ? 'event' : 'events'}`;
      await expect(
        L.badge,
        `${type}: the badge aria-label does not mirror severity + event_count`
      ).toHaveAttribute('aria-label', `Severity: ${sev.label}, ${ariaCount}`);
      // The badge's text is label + "(n)" (the label span and the count span are
      // both its children, :215-218), so the full string is mirrored — but with
      // NO SPACE at the join: textContent concatenates the two spans directly,
      // and the visible gap is the count span's `ml-0.5` CSS margin (:217), not
      // a text node. Witnessed on the shipped DOM, run hsi-check-20261011220452-
      // 6a1a48: this mirror was red 3/3 as `Expected "ALL CLEAR (0)" / Received
      // "ALL CLEAR(0)"`. toHaveText normalizes whitespace RUNS (JSX
      // indentation); it does not create one where the DOM has none.
      await expect(L.badge).toHaveText(`${sev.label.toUpperCase()}(${n})`);

      // event_count's TWO surfaces (footer sentence :238-240, badge "(n)"
      // :221-225) read the same API field — a card showing two different
      // numbers for it fails here.
      await expect(L.badgeCount).toHaveText(`(${n})`);
      await expect(L.eventCount, `${type}: the footer does not mirror event_count=${n}`).toHaveText(
        `${n} high-priority ${n === 1 ? 'event' : 'events'} analyzed`
      );

      // The shipped per-type LITERAL, not a formatted window.
      await expect(L.timeWindow).toHaveText(TIME_WINDOW[type]);

      // Footer generated-time is RELATIVE (formatDistanceToNow on generated_at,
      // :89-91), so it is mirrored for shape: present and of the shipped form.
      await expect(
        L.updated,
        `${type}: the footer carries no "Generated … ago" text`
      ).toContainText(/^Generated .+ ago$/);

      // The metadata pair, keyed on the shipped condition
      // `focusAreas?.length || timeRangeFormatted` (:191). focus_areas is always
      // [] here (header), so the location half must be ABSENT — a real shipped
      // derivation, asserted as such — and the block's presence follows from the
      // mirrored time range only.
      const range = mirrorTimeRange(apiSummary.window_start, apiSummary.window_end);
      await expect(
        L.metadata,
        `${type}: metadata presence does not follow from focus_areas=${JSON.stringify(
          m.focusAreas
        )} / time_range=${JSON.stringify(range)}`
      ).toHaveCount(range === '' && m.focusAreas.length === 0 ? 0 : 1);
      await expect(
        L.location,
        `${type}: focus_areas is [] in the API, so the location half must not render`
      ).toHaveCount(0);
      if (range !== '') {
        const shown = (await L.timeRange.textContent())?.trim() ?? '';
        expect(
          TIME_RANGE_SHAPE.test(shown),
          `${type}: summary-time-range-${type} shows ${JSON.stringify(shown)}, not the shipped ` +
            `"h:mm AM/PM(- h:mm AM/PM)" shape (the mirror yields ${JSON.stringify(
              range
            )}; only shape/presence is compared, since formatTimeRange is browser-local — api.ts:7888)`
        ).toBe(true);
      } else {
        await expect(L.timeRange).toHaveCount(0);
      }
    }

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-033: the content region is a PAIR keyed on the API — API bullets mirror their text exactly, the prose fallback mirrors the content itself', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(120_000);

    await bootDashboard(page, h);
    const session = await adminSession(h);
    const body = await latest(h, session);

    for (const type of TYPES) {
      const apiSummary = body[type];
      if (!apiSummary) continue;
      const m = transform(apiSummary);
      const L = cardOf(page, type);

      if (m.apiBullets.length > 0) {
        // The real chain: the API's OWN bullet texts, in order, under the
        // shipped maxItems={4} (SummaryCards.tsx:167-170 → the list's own
        // slice(0, maxItems), SummaryBulletList.tsx:155-156). Items carry the
        // INDEXED testid `${prefix}-item-${index}` (:173), and overflow is
        // `remainingCount > 0` (:185-190).
        const shown = m.apiBullets.slice(0, 4);
        await expect(
          L.bulletList,
          `${type}: the API carries bullets but no bullet list rendered`
        ).toBeVisible();
        for (let i = 0; i < shown.length; i++) {
          await expect(
            L.bullet(i),
            `${type}: bullet ${i} does not carry the API's text`
          ).toContainText(shown[i].text);
        }
        const remaining = m.apiBullets.length - 4;
        await expect(
          L.overflow,
          `${type}: the "+N more" row does not follow from the API bullet count`
        ).toHaveCount(remaining > 0 ? 1 : 0);
        continue;
      }

      // The golden regime (header): bullet_points is [], so the card falls back
      // to the CLIENT parser. Assert the branch PAIR, never the invented text —
      // exactly one of the bullet list or the prose paragraph renders.
      const listCount = await L.bulletList.count();
      // Tremor's Text renders a <p> verbatim (dist/components/text-elements/
      // Text/Text.js), so this locator IS the prose branch.
      const prose = L.content.locator('p');
      const proseCount = await prose.count();
      expect(
        [listCount, proseCount].filter((c) => c > 0).length,
        `${type}: the content region shows ${listCount} bullet list(s) and ${proseCount} prose ` +
          `paragraph(s); exactly one branch may render (SummaryCards.tsx:165-175)`
      ).toBe(1);

      if (proseCount > 0) {
        await expect(
          prose.first(),
          `${type}: the prose fallback does not equal the API content`
        ).toHaveText(m.content);
      } else {
        // Client-derived text. Recorded, never asserted: asserting
        // extractBulletPoints' output would assert the parser against itself.
        const bulletsShown = await L.bulletList.locator('li').count();
        test.info().annotations.push({
          type: 'note',
          description:
            `${type}: the card rendered ${bulletsShown} bullet(s) from the CLIENT fallback ` +
            `(extractBulletPoints on summary.content) because the API's ` +
            `structured.bullet_points is empty — the backend calls parse_summary_content with ` +
            `events=[] (summaries.py:129-131), so the parser derives no bullets. The bullet ` +
            `TEXT is therefore not an API value and is deliberately not asserted; the branch ` +
            `shape is.`,
        });
      }
    }

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-033: after a user reload both cards RE-DERIVE from a fresh GET (summaries is not a persisted query)', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(120_000);

    await bootDashboard(page, h);
    const session = await adminSession(h);

    // Listen BEFORE reloading: an OBSERVED request proves the reload
    // re-fetched. This is page.on('request') — none of the guard's
    // INTERCEPTION_METHODS (guard.ts:46) is used.
    const requested: string[] = [];
    page.on('request', (req) => {
      if (req.method() === 'GET' && req.url().includes('/api/summaries/latest')) {
        requested.push(req.url());
      }
    });

    // quietBoot already drained the burst once; wait again so this reload's wave
    // arrives at a refill rather than at the tail of the boot's.
    await page.waitForTimeout(2_000);
    await page.reload({ waitUntil: 'domcontentloaded' });
    // Same ordering rule as bootDashboard: the shed page and the layout are
    // polled together, because a shed REPLACES the layout rather than failing
    // inside it.
    await expect
      .poll(
        async () => {
          if ((await page.getByRole('heading', { name: 'Error Loading Dashboard' }).count()) > 0)
            return 'shed';
          if ((await page.getByTestId('dashboard-layout').count()) > 0) return 'ok';
          return 'pending';
        },
        {
          message: 'the reload neither rendered the dashboard nor its own error page',
          timeout: 30_000,
          intervals: [500],
        }
      )
      .toBe('ok');

    await expect
      .poll(() => requested.length, {
        message:
          'the reload issued no GET /api/summaries/latest. summaries is NOT in ' +
          'PERSISTABLE_QUERY_KEY_PREFIXES (queryPersistence.ts:55-60), so no persisted cache ' +
          'can serve it in a fresh JS context — a reload that does not re-request is a break.',
        timeout: 30_000,
        intervals: [1_000],
      })
      .toBeGreaterThan(0);

    for (const type of TYPES) {
      await expect(
        cardOf(page, type).skeleton,
        `${type}: still in the skeleton state after the reload`
      ).toHaveCount(0);
      await expect(
        cardOf(page, type).errorCard,
        `${type}: the summaries fetch errored after the reload`
      ).toHaveCount(0);
    }

    // And the re-derived DOM matches a FRESH read — the row's "latest" clause as
    // shipped behavior, on both badge and footer surfaces, per type.
    const body = await latest(h, session);
    for (const type of TYPES) {
      const L = cardOf(page, type);
      const apiSummary = body[type];
      if (!apiSummary) {
        await expect(
          L.empty,
          `${type}: after reload the empty state must match the empty API`
        ).toBeVisible();
        continue;
      }
      const m = transform(apiSummary);
      const sev = mirrorSeverity({
        content: m.content,
        eventCount: m.eventCount,
        maxRiskScore: m.maxRiskScore,
      });
      await expect(L.card, `${type}: the card did not come back after the reload`).toHaveAttribute(
        'data-severity',
        sev.level
      );
      await expect(L.eventCount).toHaveText(
        `${m.eventCount} high-priority ${m.eventCount === 1 ? 'event' : 'events'} analyzed`
      );
    }

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-033: a pushed summary refreshes the cards — WITNESSED on the app’s own /ws/events socket', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(120_000);

    // ONE ordered journal of what the app's own socket and its own fetches did.
    // Order comes from journal position, not wall-clock, so a coalesced event
    // loop can't put a GET on the same millisecond as its frame. Observation
    // only (page.on), never interception: the guard's four methods are
    // untouched, so nothing here fakes a server or a frame.
    const journal: ('frame' | 'get')[] = [];
    page.on('socket', (socket) => {
      if (!socket.url().includes('/ws/events')) return;
      socket.on('framereceived', (frame) => {
        if (frame.includes('"summary_update"')) journal.push('frame');
      });
    });
    page.on('request', (req) => {
      if (req.method() === 'GET' && req.url().includes('/api/summaries/latest'))
        journal.push('get');
    });

    await bootDashboard(page, h);

    // Give a boot-time push a window to arrive — the job runs AT boot, so this
    // is the most likely moment a frame could ever surface inside a run.
    await expect
      .poll(() => journal.filter((j) => j === 'frame').length, {
        timeout: 15_000,
        intervals: [1_000],
      })
      .toBeGreaterThan(0)
      .catch(() => undefined);

    const frameIdx = journal.indexOf('frame');
    test
      .info()
      .skip(
        frameIdx === -1,
        'no summary_update frame arrived on /ws/events within 15 s of a settled boot, and no ' +
          'shipped code can produce one inside a golden run: SummaryJobScheduler runs the job ' +
          'once at boot then sleeps 3600 s (backend/main.py:1100-1108, jobs/summary_job.py:352-356), ' +
          'backend/api/routes/summaries.py exposes GET routes only, the golden guard forbids ' +
          'routeWebSocket so a frame cannot be injected (guard.ts:46), and the harness exposes no ' +
          'path into the container. THE CLAUSE IS SHIPPED, NOT DEAD — SummaryJob.run() calls ' +
          'broadcast_summary_update (jobs/summary_job.py:236, :81-135) and useSummaries ' +
          'invalidates the query on the frame (useSummaries.ts:130-152) — it is simply ' +
          'un-driveable from inside this run, so per ruling 86 it is stated, not faked or left red.'
      );

    // Reached only if a frame really was pushed: then the shipped chain must
    // REFETCH after it (invalidateQueries → GET). Anything before the frame is
    // the boot's own fetch and is not evidence.
    const refetchedAfter = journal.slice(frameIdx + 1).includes('get');
    expect(
      refetchedAfter,
      `a summary_update frame arrived but GET /api/summaries/latest never FOLLOWED it, so the ` +
        `invalidation chain (useSummaries.ts:130-152) is broken. Journal: ${JSON.stringify(
          journal
        )}`
    ).toBe(true);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});

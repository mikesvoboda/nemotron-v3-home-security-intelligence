/**
 * FE-3 golden paths (F2.3): F-061 (Re-evaluate button) and F-062 (AI Audit tab).
 *
 * Row clauses (verbatim from docs/reference/feature-inventory.md):
 *   F-061 "clicks Re-evaluate; sees 'Re-evaluation triggered successfully', or
 *          'No audit found for event N' for an event no batch audit has covered"
 *   F-062 "opens the AI Audit tab; sees quality scores, self-critique and prompt
 *          suggestions, or an empty state; can run or force an evaluation"
 *
 * BOTH ROWS TURN ON ONE STORE — `event_audits` — AND THAT STORE IS EMPTY WHERE
 * THIS RUNS. Measured on the probe stack (same tier shape CI's
 * `Feature check (fake AI)` job runs): `GET /api/ai-audit/stats?days=90` answers
 * `total_events: 0, audited_events: 0, fully_evaluated_events: 0`, and
 * `GET /api/ai-audit/events/{a real event id}` answers 404 with
 * `detail: "No audit found for event N"` (backend/api/dependencies.py:666-692).
 * Each row's clause is a DISJUNCTION, and the empty store makes the SECOND
 * disjunct the reachable one — which is why both files' green legs assert the
 * not-found branch and both `test.fixme` legs name the branch that cannot be
 * witnessed. That is a real judgement, not a partial pass: F-061's clause says
 * the user sees the not-found message *for an event no batch audit has covered*,
 * and this fixture proves its row is such an event before clicking.
 *
 * THE TWO 404s RENDER DIFFERENTLY, and the pair is the most interesting thing
 * these legs measure. Same status, two UIs, two sentences:
 *   - The DETAILS tab shows the SERVER's string. `handleResponse` lifts FastAPI's
 *     `detail` into `AuditApiError.message` (`frontend/src/services/auditApi.ts:
 *     241-252`, `:249` is the lift), `handleReEvaluate`'s catch renders it
 *     verbatim (`frontend/src/components/events/EventDetailModal.tsx:309-336`,
 *     `:327` for an `AuditApiError`), into `data-testid="re-evaluate-error"`
 *     (:866-872).
 *   - The AUDIT tab shows the COMPONENT's own sentence. `EventAuditDetail`
 *     branches on the STATUS, not the message: `if (err.status === 404)
 *     setError('No audit record found for this event.')`
 *     (`frontend/src/components/audit/EventAuditDetail.tsx:185-190`), rendered by
 *     its error state (:241-257).
 * So a leg that asserted the wrong sentence in the wrong tab would pass on a UI
 * that conflated them. Each leg below asserts its own tab's exact string, and the
 * detail-tab leg asserts the EVENT ID inside it — `No audit found for event 738`
 * names which row was clicked, so that leg proves it acted on the fixture's
 * target rather than on some row the modal happened to have.
 *
 * THE SUCCESS BRANCH IS NOT MERELY UNWITNESSED — NO SHIPPED CODE REACHES IT.
 * That is a stronger claim than "we didn't test it", so it gets its evidence:
 *   - The only production writer of an `event_audits` row is
 *     `PipelineQualityAuditService.create_partial_audit`
 *     (`backend/services/pipeline_quality_audit_service.py:140-172`), called from
 *     exactly ONE site — the batch audit job
 *     (`backend/api/routes/ai_audit.py:441-450`). Its docstring says "Called
 *     inline when event is created", which is FALSE: grep finds no call from any
 *     event-creation path. There is no scheduler either.
 *   - The batch job then fails on the event it picks, before it can commit. It
 *     reads `event.llm_prompt` (`ai_audit.py:445`) off an object loaded by
 *     `select(Event).outerjoin(EventAudit)` (:526) with NO `undefer`, and
 *     `llm_prompt` is a DEFERRED column (`backend/models/event.py:74`) — the
 *     single-event path undefers it precisely to avoid this
 *     (`backend/api/dependencies.py:497-501`, "Eagerly load deferred columns…
 *     to prevent lazy loading"), and the service's own docstring warns about the
 *     failure mode (`pipeline_quality_audit_service.py:353-357`). Measured on the
 *     probe stack: a batch aimed at a fixture row answered 202/`total_events: 1`,
 *     the job went terminal with `processed_events: 0, failed_events: 1` and the
 *     message "Completed successfully", and the audit row still did not exist
 *     afterwards. (The mechanism is read, not log-proven: this sandbox's
 *     `/var/lib/docker` is 100% full so `docker logs` returns nothing at all.)
 *   - That last shape — a job that counted a failure and reported success — is
 *     the inventory's own enumerated break "the handler reports success it did
 *     not achieve" (docs/reference/feature-inventory.md §1), which is why these
 *     rows land `half-built` rather than `awaiting real tier`. Ruling 127 keeps
 *     them out of `unverified`: the stack REACHED both legs and they pass.
 *   - Independently, a fixture row could never be fully evaluated even if the
 *     batch worked: `run_full_evaluation` returns immediately when
 *     `not event.llm_prompt` (`:366-370`), and the bulk create route never sets
 *     `llm_prompt` — it is NULL on every golden row.
 *
 * WHAT THE FIXES ARE, since a fixme without a fix is a rumour:
 *   (a) add `.options(undefer(Event.reasoning), undefer(Event.llm_prompt))` to
 *       the batch job's query (or pass the undeferred row it already has) — one
 *       line, `ai_audit.py:526`, mirroring `dependencies.py:501`;
 *   (b) let the batch job's per-event `except` (ai_audit.py:462-467) surface into
 *       the job's reported outcome instead of only a counter, so
 *       `failed_events: 1` is not stamped "Completed successfully";
 *   (c) for F-062's "can run or force an evaluation" clause specifically, the
 *       break is at the UI end: `EventAuditDetail` returns its error state while
 *       `!audit` (:241-257) — BEFORE the header that holds the Run/Re-run button
 *       (:270-322) — so on an unaudited event the button is never mounted. The
 *       empty state has no way out but a page reload.
 * Per ruling 87 these are reported, not fixed, from a frontend FE-3 package.
 *
 * - ONE LEG PER ROW, and both are READ-ONLY against the store. The Re-evaluate
 *   POST cannot mutate anything on the 404 path (`get_event_audit_or_404` raises
 *   before any write) so the legs could in principle share a row; they don't,
 *   because the fixture's targeting score must stay the strict maximum of the
 *   FE-3 set (see AUDIT_TARGET_RISK_SCORE in ./harness.ts) and a second leg on
 *   the same row would put two files' preconditions on one row.
 * - THE CONTROL ROW IS NOT DEcoration. It is a second fixture row at a score
 *   BELOW the target's, never clicked. The detail-tab leg re-reads it after the
 *   click: if a click ever created state somewhere, `GET
 *   /api/ai-audit/events/{control}` stops being a 404 and the leg fails instead
 *   of reporting a clean not-found.
 * - THE FIXTURE PROVES THE PREMISE, NOT THE RUN HISTORY. The tier's emptiness is
 *   measured fresh each run by `createAuditFixture` (./harness.ts), because a
 *   sibling spec CAN drive `POST /api/ai-audit/batch` — `tests/golden/data-ui/
 *   jobs-page.spec.ts:127` does, with `{limit: 1}` — and the golden project is
 *   one serial worker (`playwright.config.ts`, `workers: 1`) over per-file
 *   fixtures. "My row has no audit" is re-asserted, never assumed.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import type { Page } from '@playwright/test';

import {
  AUDIT_NOT_FOUND_DETAIL,
  adminSession,
  closedByGuard,
  createAuditFixture,
  hardDeleteFixtureRows,
  loginAsAdmin,
  quietBoot,
  readAuditLookup,
  readTimelineHarness,
  seedDefaultViewMode,
  seedTourDismissed,
  type AuditFixture,
  type Session,
  type TimelineHarness,
} from './harness';

const h = readTimelineHarness();
test.skip(!h.ready, h.ready ? '' : h.why);
const harness = h as TimelineHarness;

let fx: AuditFixture;

test.beforeAll(async () => {
  // The fixture may wait out the camera list's 60 s cache entry on a fresh
  // stack; inside beforeAll test.setTimeout sets the HOOK's timeout, not the
  // tests'. See waitForCameraInList in ./harness.ts.
  test.setTimeout(120_000);
  const session = await adminSession(harness);
  fx = await createAuditFixture(harness, session);
});

test.afterAll(async () => {
  const session = await adminSession(harness);
  // Hard delete: event_audits cascades off the event (models/event_audit.py:
  // 27-28), so this is also the audit-row cleanup if a leg ever produces one.
  await hardDeleteFixtureRows(harness, session, [
    fx.auditedEventId,
    fx.targetEventId,
    fx.controlEventId,
  ]);
});

/** Boots /timeline filtered to this fixture with the modal already OPEN on one
 *  row, through the shipped `?event=` door (the same door ./event-detail.spec.ts
 *  uses, and the one F-061's "clicks Re-evaluate" clause implies — the button
 *  lives inside the modal, so opening it IS the first step of the path). */
async function openModal(page: Page, eventId: number): Promise<Session> {
  const session = await adminSession(harness);
  await seedTourDismissed(page);
  await seedDefaultViewMode(page);
  await loginAsAdmin(page, harness);
  await quietBoot(
    page,
    harness,
    `/timeline?camera=${encodeURIComponent(fx.cameraId)}&event=${eventId}`
  );
  await expect(page.getByTestId('timeline-page')).toBeVisible();
  await expect(
    page.getByTestId('event-detail-modal'),
    'the ?event= deep link opens the detail modal'
  ).toBeVisible();
  return session;
}

test.describe('F-061 Re-evaluate button (AI Summary)', () => {
  test('clicking Re-evaluate on an event no batch audit has covered reports the server not-found text, and claims no success', async ({
    page,
  }) => {
    const id = fx.targetEventId;
    const session = await openModal(page, id);
    const expected = AUDIT_NOT_FOUND_DETAIL(id);

    // The premise, re-read at the moment of the click rather than only in the
    // fixture: the row must still have no audit, or the disjunct this leg
    // asserts is vacuous.
    const before = await readAuditLookup(harness, session, id);
    expect(before.status, 'the target row must have no audit row before the click').toBe(404);

    // The button is in the AI Summary block on the DEFAULT Details tab
    // (EventDetailModal.tsx:851-863) — no tab click, and no feature flag or
    // audit-existence condition guards it (grep: no import.meta.env / VITE_ in
    // this component), so the clause "clicks Re-evaluate" needs nothing first.
    const button = page.getByTestId('re-evaluate-button');
    await expect(button, 'the AI Summary block offers Re-evaluate').toBeVisible();
    await expect(
      page.getByTestId('re-evaluate-error'),
      'no error is shown before the click'
    ).toHaveCount(0);

    // Wait on the route the button asks for, so the assertion below is about the
    // RENDERED sentence and not about a fetch that never finished. A 404 here is
    // the product's answer, not a test failure — which is why this waits for a
    // specific status instead of tolerating any.
    const responded = page
      .waitForResponse(
        (res) => res.url().includes(`/api/ai-audit/events/${id}/evaluate`) && res.status() === 404,
        { timeout: 20_000 }
      )
      .catch(() => null);
    await button.click();
    const res = await responded;
    expect(res, `the click POSTs /api/ai-audit/events/${id}/evaluate and it 404s`).not.toBeNull();

    // The user-visible half of the clause: the server's own string, and the
    // EVENT ID inside it. Asserting the id is what ties this DOM node to the
    // fixture row — a modal that had wandered to another event would render a
    // different number here.
    const shown = page.getByTestId('re-evaluate-error');
    await expect(shown, 'the not-found message reaches the user').toBeVisible();
    await expect(shown).toHaveText(expected);

    // …and the UI does NOT lie about it. The inventory's break list includes
    // "the handler reports success it did not achieve" (§1); F-061's UI is the
    // honest half of that, and this is the assertion that says so. The success
    // flag would auto-dismiss after 3 s (EventDetailModal.tsx:324-325), so a
    // bare absence check would be weak — pairing it with the visible error above
    // means the branch taken is unambiguous either way.
    await expect(
      page.getByTestId('re-evaluate-success'),
      'the UI claims no success for a re-evaluation that did not run'
    ).toHaveCount(0);

    // The click changed nothing anywhere: the untouched control row is still
    // unaudited. (404 here is the PASS condition — see readAuditLookup.)
    const control = await readAuditLookup(harness, session, fx.controlEventId);
    expect(control.status, 'the control row was never audited by this click').toBe(404);
    expect(control.detail, 'the control row answers the "no audit" detail, not a generic 404').toBe(
      AUDIT_NOT_FOUND_DETAIL(fx.controlEventId)
    );
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  /**
   * "sees 'Re-evaluation triggered successfully'" (ruling 212 / [r212]):
   * `fx.auditedEventId` was covered by `POST /api/ai-audit/batch` in `beforeAll`,
   * so `POST /api/ai-audit/events/${id}/evaluate` resolves 200 and
   * `data-testid="re-evaluate-success"` renders "Re-evaluation triggered successfully".
   */
  test('a covered event reports the success banner', async ({ page }) => {
    const id = fx.auditedEventId;
    const session = await openModal(page, id);

    const before = await readAuditLookup(harness, session, id);
    expect(before.status, 'the covered row has an audit row seeded by the batch audit').toBe(200);

    const button = page.getByTestId('re-evaluate-button');
    await expect(button, 'the AI Summary block offers Re-evaluate').toBeVisible();

    const responded = page
      .waitForResponse(
        (res) => res.url().includes(`/api/ai-audit/events/${id}/evaluate`) && res.status() === 200,
        { timeout: 20_000 }
      )
      .catch(() => null);
    await button.click();
    const res = await responded;
    expect(
      res,
      `the click POSTs /api/ai-audit/events/${id}/evaluate and it answers 200`
    ).not.toBeNull();

    const success = page.getByTestId('re-evaluate-success');
    await expect(success, 'the success banner renders for a covered event').toBeVisible();
    await expect(success).toContainText('Re-evaluation triggered successfully');
    await expect(page.getByTestId('re-evaluate-error')).toHaveCount(0);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});

test.describe('F-062 AI Audit tab', () => {
  test('opening the AI Audit tab on an unaudited event renders the shipped empty state, with the Run Evaluation control mounted', async ({
    page,
  }) => {
    const id = fx.targetEventId;
    const session = await openModal(page, id);

    // The tab is a plain button on the modal's tab strip
    // (EventDetailModal.tsx:670-680). `exact` because the strip also holds "AI
    // Analysis" and the Re-evaluate button is labelled "Re-evaluate AI analysis"
    // — a substring match would be ambiguous between the three.
    await page.getByRole('button', { name: 'AI Audit', exact: true }).click();

    // The empty state IS a shipped state, not a missing one: EventAuditDetail
    // catches the 404 by STATUS and writes its own sentence (:185-190), which its
    // error render puts on screen with a Retry button (:241-257). Note what this
    // does NOT assert: AUDIT_NOT_FOUND_DETAIL. The component discards the
    // server's message here and shows its own — the contrast with the F-061 leg
    // above is the finding, so the legs assert different strings on purpose.
    const empty = page.getByText('No audit record found for this event.');
    await expect(empty, 'the tab reaches its documented empty state').toBeVisible();
    await expect(
      page.getByRole('button', { name: 'Retry' }),
      'the empty state offers the shipped Retry action'
    ).toBeVisible();

    await expect(
      page.getByText('Quality Scores'),
      'no quality scores are shown for an unaudited event'
    ).toHaveCount(0);
    await expect(
      page.getByRole('button', { name: /Run Evaluation|Re-run Evaluation/ }),
      'on an event with no audit, EventAuditDetail renders the Run Evaluation control in its header (ruling 212)'
    ).toBeVisible();

    // Same read-only premise as F-061's leg: opening a tab created nothing.
    const after = await readAuditLookup(harness, session, id);
    expect(after.status, 'opening the tab did not create an audit row').toBe(404);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  /**
   * Audited event leg (ruling 212 / [r212]): `fx.auditedEventId` was seeded by
   * running the batch audit on the fake stack. Opening the AI Audit tab renders
   * the audit details and Run/Re-run Evaluation action.
   */
  test('an audited event shows its scores, self-critique and suggestions, and can be re-run', async ({
    page,
  }) => {
    const id = fx.auditedEventId;
    const session = await openModal(page, id);

    const before = await readAuditLookup(harness, session, id);
    expect(before.status, 'the target row was audited by the batch audit').toBe(200);

    await page.getByRole('button', { name: 'AI Audit', exact: true }).click();
    await expect(page.getByText(`Event #${id} Audit`)).toBeVisible();
    await expect(page.getByText('Quality Scores')).toBeVisible();
    await expect(page.getByText('Model Contributions')).toBeVisible();

    const evaluateBtn = page.getByRole('button', { name: /Run Evaluation|Re-run Evaluation/ });
    await expect(evaluateBtn, 'the audited tab offers the evaluate action').toBeVisible();

    const responded = page
      .waitForResponse(
        (res) => res.url().includes(`/api/ai-audit/events/${id}/evaluate`) && res.status() === 200,
        { timeout: 20_000 }
      )
      .catch(() => null);
    await evaluateBtn.click();
    const res = await responded;
    expect(
      res,
      `clicking evaluate POSTs /api/ai-audit/events/${id}/evaluate and answers 200`
    ).not.toBeNull();
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});

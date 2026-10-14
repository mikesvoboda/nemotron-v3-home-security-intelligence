/**
 * FE-3 golden paths (F2.3): F-060 (event feedback).
 *
 * Row clause (verbatim from docs/reference/feature-inventory.md):
 *   F-060 "marks the event correct, false positive, wrong severity and so on,
 *          with optional notes and expected threat level; sees the saved
 *          feedback when reopening"
 *
 * WHY THE GREEN LEGS CAN BE GREEN AT ALL. The panel's own GET reads back what
 * its POST writes — measured field-for-field on the probe stack, one run, three
 * rows: POST false_positive with notes/actual_threat_level/suggested_score/
 * actual_identity/what_was_wrong/model_failures → 201, then
 * GET /api/feedback/event/<id> → 200 echoing EVERY one of those six names
 * verbatim (keys: actual_identity, actual_threat_level, created_at, event_id,
 * feedback_type, id, model_failures, notes, suggested_score, what_was_wrong).
 * So the write→read round-trip the row's clause asserts is real, and these legs
 * assert it against the SERVER's re-read (`api(... '/api/feedback/event/…')`),
 * not against the POST's own 201 body — a server that accepted and stored a
 * different value would fail here rather than pass on the echo.
 *
 * THE ROW STILL LANDS `half-built`, and the reason is NOT any leg in this file
 * (all four non-fixme legs pass today) — it is the clause's own words,
 * "expected threat level". That field is WRITTEN and READ by nothing that ships:
 *   - The saved card (`FeedbackPanel.tsx:278-296`) renders only the type label,
 *     `notes` and a date. `actual_threat_level` / `suggested_score` /
 *     `actual_identity` / `what_was_wrong` / `model_failures` — every field the
 *     form collects beyond notes — appear in NO part of the reopened UI. The
 *     user's threat-level answer is stored and never shown again.
 *   - Behind the UI there is no consumer either. `suggested_score`,
 *     `actual_identity` and `model_failures` are read ONLY by
 *     `services/feedback_processor.py` (:250, :144, :140), which updates
 *     `CameraCalibration` and household members from them — and that module has
 *     ZERO non-test importers (its `get_feedback_processor()` singleton is
 *     referenced only inside its own file; `models/camera_calibration.py:36` is
 *     a docstring). The other learner, `CalibrationService.adjust_from_feedback`
 *     (`services/calibration_service.py:223`), has 23 call sites, ALL in
 *     `backend/tests/`, and reads only `feedback_type` + `event.risk_score` —
 *     none of the calibration columns. `GET /api/feedback/stats`
 *     (`api/routes/feedback.py:230-256`) groups by `feedback_type` and
 *     `Event.camera_id` only.
 * That is the enumerated half-built condition — "a break anywhere in the chain"
 * (docs/reference/feature-inventory.md §1) — met at BOTH ends: the chain from
 * these columns terminates in a write with no reader. It is the same shape as
 * this file's sibling F-057 ("the note has NO READER") and the reasoning F-131
 * already records for `event_feedback`. Per ruling 127 the row is NOT returned to
 * `unverified`: the stack reaches every leg here and they pass — a row the stack
 * reached and that shows a break is `half-built`, not `unverified`.
 *
 * - ONE LEG PER ROW, because `event_feedback.event_id` is UNIQUE (models/
 *   event_feedback.py:78): a second POST for the same event is a 409, so unlike
 *   read-only legs these cannot share. The fixture (see ./harness.ts) seeds a
 *   FIFTH row pre-marked, and the cascade on `ForeignKey(..., ondelete="CASCADE")`
 *   (:77-78) means the hard purge clears the feedback with the event — no
 *   feedback-delete endpoint exists, none is needed, and the second RUN cannot
 *   409 on the first run's residue.
 * - THE DERIVED-NOTES LEG ASSERTS A STORED STRING, not a rendered one.
 *   `handleSubmitWithNotes` PREFIXES `Current score: ${currentRiskScore}. ` onto
 *   the typed notes for severity_wrong (`FeedbackPanel.tsx:203-205`) before the
 *   POST — so "current score" is preserved only as concatenation into free text,
 *   not as a field. Asserting the DOM would only prove what was typed; asserting
 *   the re-read proves the UI→storage derivation. 45 is chosen in the fixture
 *   because it is `medium` under BOTH risk_level implementations, so the prefix
 *   is unambiguous regardless of which reader the row's card consults.
 * - THE 404-ON-EMPTY PATH IS THE PANEL'S, NOT A LEG. `getEventFeedback`
 *   (services/api.ts:3847-3857) swallows a 404 to `null`, which is how the panel
 *   reaches its "no feedback yet → show buttons" branch. A leg that asserted the
 *   raw 404 would be testing the transport, not the feature; the buttons-are-
 *   there legs below already depend on that 404→null path having worked.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import type { Page } from '@playwright/test';

import {
  FEEDBACK_RISK_SCORE,
  FEEDBACK_SEEDED_NOTES,
  FEEDBACK_SEEDED_THREAT_LEVEL,
  FEEDBACK_TYPED_NOTES,
  adminSession,
  api,
  closedByGuard,
  createFeedbackFixture,
  hardDeleteFixtureRows,
  loginAsAdmin,
  quietBoot,
  readTimelineHarness,
  seedDefaultViewMode,
  seedTourDismissed,
  waitForEventCards,
  type FeedbackFixture,
  type Session,
  type TimelineHarness,
} from './harness';

const h = readTimelineHarness();
test.skip(!h.ready, h.ready ? '' : h.why);
const harness = h as TimelineHarness;

let fx: FeedbackFixture;

/** Row roles. `event_feedback.event_id` is UNIQUE, so no two legs mark the same
 *  row — these indices are the legs' only isolation mechanism. */
const QUICK_ROW = 0; // accurate (one-click)
const NOTES_ROW = 1; // false_positive (full form)
const DERIVED_ROW = 2; // severity_wrong (derived notes prefix)
// row 3 is fx.seededEventId, pre-marked by the fixture for the read-back leg.

/** What the server says about a row's feedback right now, read back through the
 *  SAME endpoint the panel calls — never the POST's echo. `notes` etc. are typed
 *  so a value the server normalises shows up as a leg failure naming the real
 *  string, not a silent pass. */
interface FeedbackRow {
  feedback_type: string;
  notes: string | null;
  actual_threat_level: string | null;
  suggested_score: number | null;
  actual_identity: string | null;
  what_was_wrong: string | null;
  model_failures: string[] | null;
}

const feedbackTruth = (session: Session, id: number) =>
  api<FeedbackRow>(harness, session, `/api/feedback/event/${id}`);

test.beforeAll(async () => {
  // The fixture may wait out the camera list's 60 s cache entry on a fresh
  // stack; inside beforeAll test.setTimeout sets the HOOK's timeout.
  test.setTimeout(120_000);
  const session = await adminSession(harness);
  fx = await createFeedbackFixture(harness, session);
});

test.afterAll(async () => {
  const session = await adminSession(harness);
  // Hard delete cascades the feedback rows (event_feedback.event_id has
  // ondelete="CASCADE"); there is no feedback-delete endpoint to call.
  await hardDeleteFixtureRows(harness, session, fx.eventIds);
});

/** Opens the modal for one fixture row through the shipped `?event=` door, so
 *  the panel mounts with that event id. Mirrors event-detail.spec.ts's boot:
 *  the camera filter scopes the set and `event=` is the door the clause names. */
async function bootWithModal(page: Page, eventId: number): Promise<Session> {
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
  await waitForEventCards(page);
  await expect(
    page.getByTestId('event-detail-modal'),
    'the deep link opens the modal'
  ).toBeVisible();
  return session;
}

/* --------------------------------- legs ----------------------------------- */

test.describe('F-060 event feedback', () => {
  test('the one-click Accurate button marks it, stores only two fields, and swaps the panel to the saved card', async ({
    page,
  }) => {
    test.setTimeout(90_000);
    const id = fx.eventIds[QUICK_ROW];
    const session = await bootWithModal(page, id);

    const panel = page.getByTestId('feedback-panel');
    await expect(panel, 'the modal carries the feedback panel inline').toBeVisible();
    // Precondition read from the server, not assumed: this row starts unmarked,
    // so "the buttons were there" is a fact about this row, not a leftover.
    const before = await feedbackTruth(session, id).catch(() => null);
    expect(before, 'the quick row must start with no feedback (404 → null)').toBeNull();

    await expect(
      page.getByTestId('feedback-accurate-button'),
      'an unmarked event offers the four feedback buttons'
    ).toHaveCount(1);
    await expect(page.getByTestId('feedback-buttons')).toBeVisible();

    await page.getByTestId('feedback-accurate-button').click();

    // onSuccess invalidates ['eventFeedback', eventId] (FeedbackPanel.tsx:169),
    // so the SAME modal re-reads and flips to the saved card — no reopen needed.
    // The card is distinguished from the buttons frame by its own contents: every
    // branch of the panel carries data-testid="feedback-panel" (:251/:265/:278/
    // :314/:523), so a testid-visibility check proves nothing. The saved card is
    // the branch that shows the type label and NO buttons.
    await expect(
      page.getByTestId('feedback-buttons'),
      'the buttons are gone once the event is marked'
    ).toHaveCount(0);
    await expect(
      panel.getByText('Accurate', { exact: true }),
      'the card names the feedback type that was submitted'
    ).toBeVisible();
    await expect(panel.getByText(/^Submitted /), 'the card shows a submitted date').toBeVisible();

    // Server truth: the quick path sends ONLY event_id + feedback_type
    // (handleQuickFeedback, FeedbackPanel.tsx:174-181), so every optional field
    // must be null. This is the leg that says "accurate means just accurate".
    const after = await feedbackTruth(session, id);
    expect(after.feedback_type, 'the row is marked accurate').toBe('accurate');
    expect(after.notes, 'the quick path stores no notes').toBeNull();
    expect(after.actual_threat_level, 'the quick path stores no threat level').toBeNull();
    expect(after.suggested_score, 'the quick path stores no suggested score').toBeNull();
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('False Positive opens a form whose conditional fields all reach the server verbatim', async ({
    page,
  }) => {
    test.setTimeout(90_000);
    const id = fx.eventIds[NOTES_ROW];
    const session = await bootWithModal(page, id);

    await page.getByTestId('feedback-false_positive-button').click();

    // The false_positive branch shows threat level + identity + what-was-wrong,
    // and NOT the severity_wrong slider (:319-321). These presence/absence checks
    // are the conditional-form clause; the raw <input>/<textarea> ids are the
    // same string as the testid (verified in the source), so role-based locators
    // would double-match the label's htmlFor — testid is the unambiguous handle.
    await expect(
      page.getByTestId('threat-level-options'),
      'false positive asks the threat level'
    ).toBeVisible();
    await expect(
      page.getByTestId('actual-identity-input'),
      'false positive asks who it was'
    ).toBeVisible();
    await expect(
      page.getByTestId('suggested-score-slider'),
      'the score slider is severity_wrong-only, absent here'
    ).toHaveCount(0);

    await page.getByTestId('threat-level-genuine_threat').click();
    await page.getByTestId('what-was-wrong-textarea').fill('the delivery van idled too long');
    await page.getByTestId('actual-identity-input').fill('delivery driver');
    await page.getByTestId('submit-feedback-button').click();

    // THE CARD FIRST, THEN THE SERVER READ — an ordering that is load-bearing,
    // measured, not stylistic: click() resolves on the click, not on the
    // mutation's POST, so a Node read issued immediately can beat the commit and
    // 404 a write that lands ~100 ms later (this leg's first run failed exactly
    // that way; the failure screenshot then showed the saved card rendered with
    // the POST's date — the commit HAD landed, the read had simply left early).
    // Waiting on the card also makes the DOM clause the leg's own precondition:
    // onSuccess invalidates ['eventFeedback', eventId] (:169), so the card can
    // only appear once the panel's re-read saw the row the POST wrote.
    const panel = page.getByTestId('feedback-panel');
    await expect(
      page.getByTestId('feedback-buttons'),
      'the buttons are gone once the form submits'
    ).toHaveCount(0);
    await expect(
      panel.getByText('False Positive', { exact: true }),
      'the saved card names false positive'
    ).toBeVisible();

    // Read back EVERY calibration field the form collected. This is the row's
    // "with optional notes and expected threat level" clause, proven on the wire.
    const after = await feedbackTruth(session, id);
    expect(after.feedback_type).toBe('false_positive');
    expect(after.actual_threat_level, 'the chosen threat level round-trips').toBe('genuine_threat');
    expect(after.what_was_wrong, 'the what-was-wrong text round-trips').toBe(
      'the delivery van idled too long'
    );
    expect(after.actual_identity, 'the identity correction round-trips').toBe('delivery driver');
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('Severity Wrong stores the score context the UI derives, not just the typed note', async ({
    page,
  }) => {
    test.setTimeout(90_000);
    const id = fx.eventIds[DERIVED_ROW];
    const session = await bootWithModal(page, id);

    await page.getByTestId('feedback-severity_wrong-button').click();
    await expect(
      page.getByTestId('suggested-score-slider'),
      'severity_wrong shows the score slider'
    ).toBeVisible();
    await expect(
      page.getByTestId('threat-level-options'),
      'severity_wrong does NOT ask the threat level'
    ).toHaveCount(0);

    // Type the note WITHOUT the prefix; the panel prepends it itself.
    await page.getByTestId('feedback-notes').fill(FEEDBACK_TYPED_NOTES);
    await page.getByTestId('submit-feedback-button').click();

    // Same card-before-read ordering as the notes leg — see its comment for the
    // measured race. The severity_wrong card labels itself by its type.
    await expect(
      page.getByTestId('feedback-buttons'),
      'the buttons are gone once the form submits'
    ).toHaveCount(0);
    await expect(
      page.getByTestId('feedback-panel').getByText('Severity Wrong', { exact: true }),
      'the saved card names severity wrong'
    ).toBeVisible();

    // The assertion is on the STORED string, which is what the derivation is:
    // "Current score: 45. " + typed text (FeedbackPanel.tsx:203-205). currentRiskScore
    // is event.risk_score = FEEDBACK_RISK_SCORE (EventDetailModal.tsx:543 → :1146).
    const after = await feedbackTruth(session, id);
    expect(
      after.notes,
      `the panel stored "Current score: ${FEEDBACK_RISK_SCORE}. " + the typed note`
    ).toBe(`Current score: ${FEEDBACK_RISK_SCORE}. ${FEEDBACK_TYPED_NOTES}`);
    expect(after.feedback_type).toBe('severity_wrong');
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('a reopening sees the saved card with no write in this run', async ({ page }) => {
    test.setTimeout(90_000);
    // fx.seededEventId already has feedback from BEFORE any leg ran. This leg
    // POSTs NOTHING: it boots a fresh page and reads the panel's initial GET
    // result. That is the only way to measure the clause "sees the saved feedback
    // when reopening" without a broken write masquerading as a broken read.
    const session = await bootWithModal(page, fx.seededEventId);
    // (session is read once below; the seeded row's truth is already asserted by
    // the fixture, but we re-read here so the leg owns its own server check.)
    const truth = await feedbackTruth(session, fx.seededEventId);
    expect(truth.feedback_type, 'the fixture seeded a false_positive').toBe('false_positive');

    const panel = page.getByTestId('feedback-panel');
    await expect(panel, 'the panel mounts on reopen').toBeVisible();
    await expect(
      panel.getByText('False Positive', { exact: true }),
      'the reopened panel shows the saved feedback type, not buttons'
    ).toBeVisible();
    await expect(
      panel.getByText(FEEDBACK_SEEDED_NOTES),
      'the reopened panel shows the saved notes verbatim'
    ).toBeVisible();
    await expect(
      page.getByTestId('feedback-buttons'),
      'a marked event shows no buttons'
    ).toHaveCount(0);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test.fixme('the reopened card reports the threat level the user chose (it does not today)', async ({
    page,
  }) => {
    test.setTimeout(90_000);
    // RED today, by design: this is the row's own clause — the user answered
    // "expected threat level", so reopening should show it. It does not. The
    // saved card (FeedbackPanel.tsx:278-296) renders type label + notes + date
    // and NOTHING else; `actual_threat_level` is never rendered. The fixture
    // seeded fx.seededEventId with actual_threat_level =
    // FEEDBACK_SEEDED_THREAT_LEVEL, and the GET returns it (asserted in
    // createFeedbackFixture's precondition), so the data is present and simply
    // not shown. If a fix ever renders it, this leg turns green and F-060's
    // half-built evidence loses its UI-end half (the no-backend-reader half in
    // the file header would remain). test.fixme is this repo's instrument for a
    // written-but-known-red leg (shell/ws-status.spec.ts:184); the rest of the
    // project stays green so
    // CI's verdict stays readable.
    const session = await bootWithModal(page, fx.seededEventId);
    // The premise, stated as a passing assertion so a reader can see WHICH
    // half of "data present but not shown" is the broken one: the server has
    // the value (this passes), the card does not show it (this is the red one).
    const truth = await feedbackTruth(session, fx.seededEventId);
    expect(
      truth.actual_threat_level,
      'the stored threat level is readable — the break is at the UI end'
    ).toBe(FEEDBACK_SEEDED_THREAT_LEVEL);
    await expect(
      page.getByTestId('feedback-panel').getByText('Genuine Threat'),
      'the reopened card should surface the stored threat level'
    ).toBeVisible();
  });
});

/**
 * FE-3 golden paths (F2.3): F-056 (mark as reviewed) and F-057 (notes).
 *
 * Row clauses (verbatim from docs/reference/feature-inventory.md):
 *   F-056 "clicks Mark as Reviewed in the modal, the list-view action, or swipes
 *          a mobile card; the event shows reviewed"
 *   F-057 "types notes and clicks Save Notes; sees 'Saved'"
 *
 * WHY THESE TWO CAN BE VERIFIED AT ALL, where F-043 nearly could not: both write
 * through `PATCH /api/events/{event_id}` and then rely on the list re-reading
 * itself. `list_events` (`events.py:279`) takes ONLY `db: AsyncSession =
 * Depends(get_read_db)` — no cache dep anywhere in its body — so the `refetch()`
 * that follows a successful PATCH (EventTimeline.tsx:831, :931) reads the DB. The
 * camera list that ate F-043's deep-link legs is cache-aside by contrast
 * (`cameras.py:194-217`); the events list is not, and no `refetchInterval` churns
 * it either (useEventsInfiniteQuery sets none), so nothing re-queries underneath
 * a leg mid-assertion. That difference is the whole reason this file asserts a
 * transition rather than reporting one half-built.
 *
 * - BOTH MUTATION DOORS ARE "PRESENT UNTIL DONE", measured, which is what makes
 *   "the event shows reviewed" an assertion instead of a hope: the modal's button
 *   renders only under `onMarkReviewed && !event.reviewed` (EventDetailModal.tsx:
 *   1337-1345) and the list row's only under `!event.reviewed` (EventListView.tsx:
 *   408-416). So a successful click takes an affordance OUT and puts
 *   `data-testid="status-reviewed"` IN (:1186-1193). Asserted as 4 → 3 on the
 *   button COUNT, never 4 → 0: three fixture rows are never touched, so a UI that
 *   blanked the whole list to look "done" fails the control instead of passing.
 * - THE MODAL IS FED LIVE QUERY DATA, which is the precondition for any of this.
 *   `event={getModalEvent()}` (:1903) is rebuilt every render from
 *   `filteredEvents.find(...)` (:1061-1063); it is not a snapshot taken on open.
 *   Had it been a snapshot, `status-reviewed` could never appear and this row
 *   would be `half-built` — the reason this was read before it was written.
 * - ONE PATCH PER ROW PER TEST, on purpose. Both handlers send
 *   `version: event?.version` for optimistic locking (NEM-3625, :825-827, :927-
 *   929) and the route 409s a mismatch (`events.py:1975-1985`). Measured on the
 *   probe stack: version 1 → 2 (notes) → 3 (reviewed). A second PATCH issued
 *   before the refetch lands would therefore conflict, so each leg owns its own
 *   row, the fourth is the untouched control, and the fifth belongs to the
 *   `test.fixme` read-back leg (see ./harness.ts for why sharing is a lie here).
 * - F-057 SPLITS INTO TWO LEGS, because measuring it found that half the row
 *   works and half of it does not, and one green test could not tell both truths.
 *   THE SAVE LEG IS GREEN. The clause "sees 'Saved'" is a claim about what the
 *   user perceives, so it asserts the report the user actually gets — the success
 *   toast `toastSuccess('Notes saved')` (EventTimeline.tsx:932) — plus the
 *   substance behind it: `PATCH /api/events/{id}` writes and `GET /api/events/{id}`
 *   (no cache dep, `:1870`) echoes it back. Asserting the modal's own `notesSaved`
 *   flag instead would pass on a UI that labelled without saving.
 *   THE READ-BACK LEG IS `test.fixme`, and it is the reason F-057's row goes to
 *   half-built rather than awaiting real tier: the note has NO READER, which is
 *   one of the enumerated half-built conditions (docs/reference/feature-inventory.md
 *   §1). Measured against the probe stack, on one row, both routes in the same
 *   run: `PATCH` answered `"THE-NOTE-TEXT"`, `GET /api/events/{id}` returned
 *   `"THE-NOTE-TEXT"`, and `GET /api/events?limit=100&camera_id=…` returned
 *   `null` for that same row's `notes` — the KEY IS PRESENT, THE VALUE IS NOT.
 *   Cause: `list_events` hand-builds each response dict (`events.py:502-523`) and
 *   never puts `notes` in it, so schema revalidation fills the default; `notes` is
 *   not in `VALID_EVENT_LIST_FIELDS` (`:142`) either. The modal seeds its textarea
 *   from `getModalEvent()`, which copies `notes` off the LIST projection
 *   (`EventTimeline.tsx:1063`, `:1086`), and NOTHING in the running UI calls
 *   `GET /api/events/{id}` for display (the only single-route reader in
 *   `services/api.ts` is `getEventFeedback` at `:3847`). So the note is written and
 *   never shown again — the reopened box is blank forever. This falsifies the row's
 *   own Evidence ("`events.notes` is returned by `GET /api/events` and shown when
 *   the modal reopens"). A 10 s sampler after a reload, with the note stored and
 *   `?event=` still in the URL, read `""` at every 250 ms sample: never populated,
 *   not populated-then-wiped. `test.fixme` is this repo's instrument for exactly
 *   this (timeline/event-reevaluate.spec.ts:259): the spec
 *   is written and the failure is documented, and the rest of the golden project
 *   stays green so CI's verdict stays readable.
 * - A SECOND, SEPARATE DEFECT, frontend, reported but NOT the basis for the
 *   demotion. The modal's inline chip that literally reads "Saved" is present for
 *   ~2 ms (rAF sampler: first=365ms last=367ms samples=2/237) while the toast
 *   arrives at 385 ms and is still up 3 s later (samples=219/237). Same mechanism,
 *   worse consequence: `getModalEvent()` returns a NEW OBJECT LITERAL on every
 *   render (`:1061-1075`), so the `event` prop's IDENTITY changes on any parent
 *   render and the modal's `useEffect(..., [event])` (`EventDetailModal.tsx:240-
 *   241`) re-runs, resetting `notesText` and `notesSaved` — so text typed but NOT
 *   yet saved is silently DISCARDED by a render that changed nothing about the
 *   event. Measured with a viewport RESIZE as the trigger, no request issued:
 *   the box went `""` (`WIPED=true`) while the server row stayed bit-identical
 *   (`version 1->1 notes null->null`). That is user data loss. It does not demote
 *   this row because the toast carries the feedback the clause names — the chip is
 *   redundant, not the only signal — but it is reported to the coordinator, and it
 *   is outside this package's scope to fix (ruling 87: a batch PR touches only
 *   `frontend/tests/golden/<area>/` and its own inventory rows). The save leg
 *   asserts the toast rather than the chip because a leg aimed at the chip would be
 *   a red test about a 2 ms artifact instead of a green one about the feature.
 * - NOT asserted here, with reasons (UR-128): (1) F-056's THIRD door, the mobile
 *   swipe — `MobileEventCard` mounts only under a <640px viewport branch
 *   (:1764, :1834) and its swipe is driven by `useSwipeGesture` pointer deltas,
 *   while the card shares the grid card's `event-card-${id}` testid
 *   (MobileEventCard.tsx:153 vs EventCard.tsx:388), so a "mobile" leg here would
 *   add a viewport, not a door. (2) the reviewed FILTER is F-043's clause. (3) the
 *   409 optimistic-lock path is a backend contract with its own unit tests; the
 *   UI's response to it is a `toastError` and a silent refetch (:934-939, the
 *   source's own `// TODO: Consider adding toast` at :840 admits it is unfinished)
 *   — that is a judgement about an unfinished surface, not this row's clause.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import type { Page } from '@playwright/test';

import {
  adminSession,
  api,
  closedByGuard,
  createDetailFixture,
  DETAIL_ROWS,
  hardDeleteFixtureRows,
  loginAsAdmin,
  quietBoot,
  readTimelineHarness,
  seedDefaultViewMode,
  seedTourDismissed,
  settledReload,
  waitForEventCards,
  type DetailFixture,
  type Session,
  type TimelineHarness,
} from './harness';

/** The fields these two rows mutate, read from the uncached single-row route. */
interface EventRow {
  reviewed: boolean;
  notes: string | null;
  version: number;
}

const h = readTimelineHarness();
test.skip(!h.ready, h.ready ? '' : h.why);
const harness = h as TimelineHarness;

let fx: DetailFixture;

/** Row roles, so no two legs PATCH the same row (see the header's version note). */
const MODAL_ROW = 0;
const LIST_ROW = 1;
const NOTES_ROW = 2;
const CONTROL_ROW = 3; // never mutated — the negative control every leg checks
const REOPEN_ROW = 4; // owned by the test.fixme read-back leg; stays note-free today

const rowTruth = (session: Session, id: number) =>
  api<EventRow>(harness, session, `/api/events/${id}`);

test.beforeAll(async () => {
  // The fixture may wait out the camera list's 60 s cache entry on a fresh
  // stack; inside beforeAll test.setTimeout sets the HOOK's timeout, not the
  // tests'. See waitForCameraInList in ./harness.ts.
  test.setTimeout(120_000);
  const session = await adminSession(harness);
  fx = await createDetailFixture(harness, session);
});

test.afterAll(async () => {
  const session = await adminSession(harness);
  await hardDeleteFixtureRows(harness, session, fx.eventIds);
});

/** Opens the modal for one fixture row through the shipped `?event=` door, or
 *  boots the filtered list when no id is given (F-056's second door has no modal). */
async function bootTimeline(page: Page, eventId?: number): Promise<Session> {
  const session = await adminSession(harness);
  await seedTourDismissed(page);
  await seedDefaultViewMode(page);
  await loginAsAdmin(page, harness);
  // The camera filter scopes the set to this fixture (so a foreign row cannot
  // join the counts) and `event=` is the door the modal clause names.
  const link = `/timeline?camera=${encodeURIComponent(fx.cameraId)}${
    eventId === undefined ? '' : `&event=${eventId}`
  }`;
  await quietBoot(page, harness, link);
  await expect(page.getByTestId('timeline-page')).toBeVisible();
  await waitForEventCards(page);
  return session;
}

/** How many of THIS fixture's rows the server calls unreviewed, right now. Read
 *  rather than counted from DETAIL_ROWS, because the golden project is ONE serial
 *  worker over a per-file fixture: an earlier test's PATCH is still on the row
 *  when a later test starts, so a hardcoded starting count would be a lie about
 *  test order rather than about the product. */
async function serverUnreviewed(session: Session): Promise<number> {
  const body = await api<{ items: { id: number; reviewed: boolean }[] }>(
    harness,
    session,
    `/api/events?limit=100&camera_id=${encodeURIComponent(fx.cameraId)}`
  );
  const mine = body.items.filter((row) => fx.eventIds.includes(row.id));
  expect(
    mine.length,
    'the fixture camera must still hold every fixture row for these counts to mean anything'
  ).toBe(DETAIL_ROWS.length);
  return mine.filter((row) => !row.reviewed).length;
}

test.describe('F-056 mark as reviewed', () => {
  test('the modal action persists reviewed, the button leaves, the badge arrives', async ({
    page,
  }) => {
    const id = fx.eventIds[MODAL_ROW];
    const session = await bootTimeline(page, id);
    // Ground truth BEFORE the click: the fixture guarantees unreviewed, and this
    // is the leg's precondition stated rather than assumed.
    const before = await rowTruth(session, id);
    expect(before.reviewed, 'the row must start unreviewed').toBe(false);

    const modal = page.getByTestId('event-detail-modal');
    await expect(modal, 'the ?event= deep link opens the detail modal').toBeVisible();
    const modalReviewed = page.getByTestId('mark-reviewed');
    await expect(modalReviewed, 'an unreviewed event offers the modal action').toBeVisible();
    // The Status row says Pending Review, i.e. the modal is rendering THIS row.
    await expect(
      page.getByText('Pending Review'),
      'the modal shows the pre-click state'
    ).toBeVisible();

    await modalReviewed.click();

    // The affordance leaves (its guard is `!event.reviewed`) and the badge
    // arrives — both are consequences of the LIST re-reading, not of a local flag.
    await expect(modalReviewed, 'the action is gone once the event is reviewed').toHaveCount(0);
    await expect(
      page.getByTestId('status-reviewed'),
      'the modal reports the event as Reviewed'
    ).toBeVisible();
    await expect(page.getByText('Pending Review')).toHaveCount(0);

    // Server truth, read uncached: the UI's claim is checked against the row.
    const after = await rowTruth(session, id);
    expect(after.reviewed, 'PATCH persisted reviewed=true').toBe(true);
    expect(after.version, 'the PATCH advanced the optimistic-lock version').toBeGreaterThan(
      before.version
    );

    // The real control is server-side: the three rows this leg never opened must
    // still be unreviewed, so the badge above cannot be an artifact of a UI that
    // marked everything it had loaded.
    for (const other of [LIST_ROW, NOTES_ROW, CONTROL_ROW, REOPEN_ROW]) {
      const row = await rowTruth(session, fx.eventIds[other]);
      expect(row.reviewed, `row ${other} was untouched by this leg`).toBe(false);
    }
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('the list-view action marks its own row and leaves the others alone', async ({ page }) => {
    const id = fx.eventIds[LIST_ROW];
    // No `event=`: this door is the row action, so the list itself is the surface.
    const session = await bootTimeline(page);
    await page.getByRole('button', { name: 'Switch to list view' }).click();
    await expect(page.getByTestId(`event-list-row-${id}`)).toBeVisible();

    // Count read from the server, not from DETAIL_ROWS — see serverUnreviewed.
    const unreviewedBefore = await serverUnreviewed(session);
    expect(
      unreviewedBefore,
      'at least two of the fixture rows must still be unreviewed for this to be a delta'
    ).toBeGreaterThanOrEqual(2);

    const rowButton = page.getByRole('button', { name: `Mark event ${id} as reviewed` });
    await expect(rowButton, 'an unreviewed list row offers its own action').toBeVisible();
    // Every unreviewed row on this camera carries exactly one such button.
    await expect(
      page.getByRole('button', { name: /Mark event \d+ as reviewed/ }),
      `the list offers one action per unreviewed row (${unreviewedBefore})`
    ).toHaveCount(unreviewedBefore);

    await rowButton.click();

    await expect(rowButton, "that row's action is gone after the click").toHaveCount(0);
    // The count falls by EXACTLY ONE. This is the assertion a "all buttons gone"
    // check would hide: the surviving rows are proof the list did not simply lose
    // or blank the row it just mutated.
    await expect(
      page.getByRole('button', { name: /Mark event \d+ as reviewed/ }),
      `the other unreviewed rows keep their action (${unreviewedBefore} → ${
        unreviewedBefore - 1
      }, not → 0)`
    ).toHaveCount(unreviewedBefore - 1);

    const after = await rowTruth(session, id);
    expect(after.reviewed, 'the list-view action persisted reviewed=true').toBe(true);
    // DOM and server agree a second time, after the mutation.
    expect(await serverUnreviewed(session), 'server and DOM counts still agree').toBe(
      unreviewedBefore - 1
    );
    // The control row is untouched by every leg, including this one.
    const control = await rowTruth(session, fx.eventIds[CONTROL_ROW]);
    expect(control.reviewed, 'the control row was never marked').toBe(false);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});

test.describe('F-057 notes', () => {
  test('typing notes and saving reports success and writes the note to the store', async ({
    page,
  }) => {
    const id = fx.eventIds[NOTES_ROW];
    const typed = `fe3-note-${Date.now()}`;
    const session = await bootTimeline(page, id);
    expect((await rowTruth(session, id)).notes, 'the row must start note-free').toBeNull();

    const box = page.getByPlaceholder('Add notes about this event...');
    await expect(box, 'the modal offers the notes field on the default tab').toBeVisible();
    await expect(box).toHaveValue('');
    await box.fill(typed);
    await page.getByRole('button', { name: 'Save notes' }).click();

    // The row's clause "sees 'Saved'", aimed at what the user perceives. The
    // modal's OWN inline chip reading exactly "Saved" is present for ~2 ms (see
    // the header's SECOND DEFECT) and is not a locator a test can hold; the
    // report that actually reaches the user is the sonner toast "Notes saved".
    // Same instrument ./admin-cache-clear.spec.ts uses, and same rule it states:
    // a toast alone would pass on a toast that lies, so it is paired with the
    // server check below rather than standing in for it.
    const toast = page.locator('[data-sonner-toast]').filter({ hasText: 'Notes saved' });
    await expect(toast, 'the save reports success to the user').toBeVisible();

    // Server truth, uncached — the substance the toast is claiming. This is as
    // far as F-057 can be verified today: the note REACHES `events.notes`. The
    // other half of the row, the note COMING BACK, is the fixme below.
    const after = await rowTruth(session, id);
    expect(after.notes, 'PATCH persisted the note text').toBe(typed);
    expect(after.version, 'the PATCH advanced the optimistic-lock version').toBeGreaterThan(1);
    // The untouched control proves this leg wrote ONE row, not every row it had.
    expect(
      (await rowTruth(session, fx.eventIds[CONTROL_ROW])).notes,
      'the control row was never given a note'
    ).toBeNull();
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  /**
   * THE READ-BACK LEG (ruling 238, [r238]). `[r149d]` (#7070) added `"notes": event.notes`
   * to `list_events` (`backend/api/routes/events.py:543`), so `GET /api/events` now
   * returns the stored note and the reopened modal seeds its textarea from the list
   * projection (`EventTimeline.tsx:1063`, `:1086` → `EventDetailModal.tsx:241`).
   */
  test('the saved note is read back: reopening the modal shows the stored note', async ({
    page,
  }) => {
    const id = fx.eventIds[REOPEN_ROW];
    const typed = `fe3-reopen-${Date.now()}`;
    const session = await bootTimeline(page, id);
    expect((await rowTruth(session, id)).notes, 'the row must start note-free').toBeNull();

    await page.getByPlaceholder('Add notes about this event...').fill(typed);
    await page.getByRole('button', { name: 'Save notes' }).click();
    await expect(
      page.locator('[data-sonner-toast]').filter({ hasText: 'Notes saved' })
    ).toBeVisible();

    // A RELOAD empties all JS state, so a value that comes back can only have
    // come from the server — which is the point of this leg.
    await settledReload(page);
    await expect(page.getByTestId('event-detail-modal')).toBeVisible();
    await expect(
      page.getByPlaceholder('Add notes about this event...'),
      'reopening shows the saved note (read back from the server)'
    ).toHaveValue(typed);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});

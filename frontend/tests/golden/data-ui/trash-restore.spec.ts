/**
 * F4.3 golden path (spec 4n-trash.md:136-139, ruling 135): "open an event,
 * Delete, Undo, Delete again; find it in Trash; Restore it; Delete again;
 * Delete permanently and confirm. The event then answers 404 and its files
 * are gone."
 *
 * Every state the path visits is produced the way the user produces it. The
 * ONLY node-side writes are fixture setup: a dedicated camera plus events with
 * a linked detection each (the spec's own fake-stack scenario — "any seeded
 * event with a detection image and a thumbnail"; the thumbnail_url is derived
 * from the first linked detection at events.py:590-592). The trash entries
 * themselves are made by the UI's Delete doors — the modal's
 * `delete-event-button` and the grid's `bulk-delete-button` — which is what
 * ruling 135 replaced this file's previous API-side seeding with (its git
 * history shows the replaced `seedSoftDelete` helper: node-side DELETEs). The
 * Undo is a real click on the shipped sonner toast's action button, driving
 * performUndo → useRestoreEventMutation (EventTimeline.tsx:615-629); sonner
 * renders the toast action as `button[data-button][data-action]` (measured in
 * node_modules/sonner/dist) and the Toaster sits at z-index 999999999, above
 * the modal's z-50, so the click lands with the modal still open.
 *
 * The mirror follows the lane's observer idiom (F-184/OP-3): trash strings are
 * read from the body the PAGE itself received from /api/events/deleted, and
 * node-side reads prove end states only — chiefly the purge-proof triple this
 * path shares with B4.4's pytest golden (test_trash_purge.py): after a
 * permanent delete the event answers 404 on the single read, is gone from
 * /api/events/deleted, and its linked detection answers 404 (a merely-trashed
 * event also 404s the single read, so the trash-list absence plus the
 * detection 404 are what distinguish purged from trashed).
 *
 * No page.route interception anywhere — the guard's GUARD_MESSAGE tripwire
 * closes the test, and the observers ride the response channel instead.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  adminSession,
  api,
  apiCookie,
  apiWrite,
  closedByGuard,
  hardDeleteFixtureRows,
  loginAsAdmin,
  openTimelineEventModal,
  readOpsHarness,
  waitForCameraInList,
  waitForEventCards,
  type OpsHarness,
  type Session,
} from '../harness';

const harness = readOpsHarness();

interface DeletedEvent {
  id: number;
  camera_id: string;
  summary: string | null;
  risk_score: number | null;
  deleted_at: string;
}

interface DeletedListBody {
  items: DeletedEvent[];
}

interface EventListBody {
  items: Array<{ id: number }>;
}

interface CameraListBody {
  items?: { id: string; name: string }[];
}

/** 207 shape of POST /api/detections/bulk and /api/events/bulk. */
interface BulkResultBody {
  succeeded: number;
  results: Array<{ id: number | null; status: string; error?: string | null }>;
}

const TRASH_CAMERA_NAME = 'F4.3 Trash Golden Probe';
const TRASH_CAMERA_FOLDER = '/cameras/f43_trash_probe';
/** Three rows: the modal-door lifecycle (A), the bulk-door row (B), and an
 *  untouched control (C) the final truth read proves stayed live. */
const TRASH_ROWS = 3;
/** ~6 h ago: inside the timeline's default 24 h window (createStatsFixture's
 *  measured rationale) and fresh enough for the trash card's Deleted chip. */
const FIXTURE_AGE_MS = 6 * 3_600_000;
/** Clustering (EventTimeline.tsx:768-781) collapses >=3 same-camera rows that
 *  share a <=5-minute window in grid/grouped view — grid is the shipped default
 *  (EventTimeline.tsx:131). Spacing the fixture beyond that window keeps every
 *  row its own `event-card-{id}`. */
const SPREAD_MS = 10 * 60_000;

function apiCookieHeader(session: Session): Record<string, string> {
  return { Cookie: `${session.name}=${session.value}` };
}

/** Raw status of a GET — for the 404/200 polls `api()` cannot serve (it throws
 *  on any non-200, so a poll over its contract cannot express "expect 404"). */
async function statusOf(h: OpsHarness, session: Session, path: string): Promise<number> {
  const res = await fetch(`${h.api}${path}`, { headers: apiCookieHeader(session) });
  return res.status;
}

/* -------------------------------------------------------------------------- */
/* Local ensureCamera — harness.ts's is private; this is the modes.spec.ts:78  */
/* pattern with the 409-recovery arm (measured: a name-unique 409 carries the  */
/* DB id inside its detail, and the recovered id is confirmed uncached).       */
/* -------------------------------------------------------------------------- */
async function ensureTrashCamera(h: OpsHarness, session: Session): Promise<string> {
  const list = await api<CameraListBody>(h, session, '/api/cameras');
  const known = (list.items ?? []).find((cam) => cam.name === TRASH_CAMERA_NAME);
  if (known) return known.id;
  // Deliberately a raw fetch, not apiWrite: a 409 is an EXPECTED answer here.
  const res = await fetch(`${h.api}/api/cameras`, {
    method: 'POST',
    headers: { ...apiCookieHeader(session), 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: TRASH_CAMERA_NAME, folder_path: TRASH_CAMERA_FOLDER }),
  });
  const created = (await res.json().catch(() => null)) as { id?: string; detail?: string } | null;
  if (res.status >= 200 && res.status < 300) {
    if (!created?.id) throw new Error('fixture: camera POST 2xx carried no id');
    return created.id;
  }
  if (res.status !== 409) {
    throw new Error(
      `fixture: POST /api/cameras answered ${res.status}: ${JSON.stringify(created).slice(0, 200)}`
    );
  }
  const found = (created?.detail ?? '').match(/already exists \(id: ([^)]+)\)/);
  if (!found) {
    throw new Error(`fixture: camera 409 unparseable: ${(created?.detail ?? '').slice(0, 200)}`);
  }
  await api<{ id: string }>(h, session, `/api/cameras/${encodeURIComponent(found[1])}`);
  return found[1];
}

/* -------------------------------------------------------------------------- */
/* Fixture: COUNT events on the probe camera, each with one linked detection   */
/* (the fake-stack scenario), spaced beyond the clustering window. Returns the */
/* event ids in creation order (A = [0], B = [1], C = [2]).                    */
/* -------------------------------------------------------------------------- */
async function seedTrashFixture(
  h: OpsHarness,
  session: Session,
  count: number
): Promise<{ cameraId: string; eventIds: number[]; detectionIds: number[] }> {
  // The trash list is GLOBAL (GET /api/events/deleted takes no filter), and
  // the legs below assert exact counts on it ("1 event in trash", "Empty
  // Trash? (1 event)", the final empty read). So the trash starts EMPTY: any
  // stale row — this file's own earlier run or another spec's dev-stack
  // residue — is restored through the same cited restore endpoint (real,
  // non-destructive: the opposite of the permanent deletes this path pins;
  // on a fresh CI stack this loop is a no-op).
  const pre = await api<DeletedListBody>(h, session, '/api/events/deleted');
  for (const stale of pre.items) {
    await apiWrite<unknown>(h, session, 'POST', `/api/events/${stale.id}/restore`, {});
  }

  const cameraId = await ensureTrashCamera(h, session);
  // The timeline's camera select reads a 60 s cached list (useCamerasQuery
  // refetchInterval false) — the wait is what a fresh CI stack needs.
  await waitForCameraInList(h, session, TRASH_CAMERA_NAME);

  // Residue purge: live rows and already-trashed rows on THIS camera. Only
  // this spec's own earlier run can have left them (no other file names it).
  const stale = await api<EventListBody>(
    h,
    session,
    `/api/events?limit=100&camera_id=${encodeURIComponent(cameraId)}`
  );
  await hardDeleteFixtureRows(
    h,
    session,
    stale.items.map((row) => row.id)
  );
  // GET /api/events/deleted takes no query params (events.py:1411) and returns
  // the WHOLE trash; the camera filter here is client-side.
  const trashed = await api<DeletedListBody>(h, session, '/api/events/deleted');
  await hardDeleteFixtureRows(
    h,
    session,
    trashed.items.filter((row) => row.camera_id === cameraId).map((row) => row.id)
  );

  const salt = Date.now();
  const detections = Array.from({ length: count }, (_, i) => ({
    camera_id: cameraId,
    object_type: 'person',
    confidence: 0.9,
    detected_at: new Date(Date.now() - FIXTURE_AGE_MS - i * SPREAD_MS).toISOString(),
    // file_path is UNIQUE across detections (measured) — the salt keeps re-runs honest.
    file_path: `${TRASH_CAMERA_FOLDER}_${salt}_${i}.jpg`,
    bbox_x: 20,
    bbox_y: 20,
    bbox_width: 100,
    bbox_height: 180,
    media_type: 'image' as const,
  }));
  const detBulk = await apiWrite<BulkResultBody>(h, session, 'POST', '/api/detections/bulk', {
    detections,
  });
  if (detBulk.succeeded !== count) {
    throw new Error(
      `fixture: detections bulk succeeded ${detBulk.succeeded}/${count}; first error: ` +
        String(detBulk.results.find((r) => r.status !== 'success')?.error).slice(0, 200)
    );
  }
  const detIds = detBulk.results.map((r) => r.id).filter((id): id is number => id !== null);

  const evBulk = await apiWrite<BulkResultBody>(h, session, 'POST', '/api/events/bulk', {
    events: detections.map((d, i) => ({
      batch_id: `f43-trash-${salt}-${i}`, // UNIQUE per row (measured UniqueViolationError)
      camera_id: cameraId,
      started_at: d.detected_at,
      risk_score: 54,
      risk_level: 'medium',
      summary: `F4.3 trash golden fixture event ${i}`,
      detection_ids: [detIds[i]],
    })),
  });
  if (evBulk.succeeded !== count) {
    throw new Error(
      `fixture: events bulk succeeded ${evBulk.succeeded}/${count}; first error: ` +
        String(evBulk.results.find((r) => r.status !== 'success')?.error).slice(0, 200)
    );
  }
  const eventIds = evBulk.results.map((r) => r.id).filter((id): id is number => id !== null);

  // The thumbnail_url derivation reads the FIRST linked detection — assert the
  // link actually landed before the UI drives on it.
  const seeded = await api<{ items: Array<{ id: number; thumbnail_url: string | null }> }>(
    h,
    session,
    `/api/events?limit=100&camera_id=${encodeURIComponent(cameraId)}`
  );
  for (const id of eventIds) {
    const row = seeded.items.find((e) => e.id === id);
    if (!row || row.thumbnail_url === null) {
      throw new Error(`fixture: event ${id} has no derived thumbnail_url (detection link?)`);
    }
  }
  return { cameraId, eventIds, detectionIds: detIds };
}

test.describe('golden path: trash page restore flows @critical', () => {
  // The drive covers three modal boots, two trash visits, an Undo round-trip,
  // a bulk leg and a permanent delete; the fixture may also wait out the
  // camera-list cache on a fresh stack (waitForCameraInList's 90 s budget).
  test.setTimeout(150_000);

  let fx: Awaited<ReturnType<typeof seedTrashFixture>> | undefined;

  test.beforeAll(async () => {
    // Inside beforeAll, test.setTimeout sets the HOOK's timeout (event-detail's
    // note) — the camera-cache wait budget lives here, not on the tests.
    test.setTimeout(120_000);
    if (!harness.ready) return;
    const session = await adminSession(harness);
    fx = await seedTrashFixture(harness, session, TRASH_ROWS);
  });

  test.afterAll(async () => {
    if (!harness.ready || !fx) return;
    // Purge everything the fixture created (the rows may sit live, trashed or
    // already purged — hardDeleteFixtureRows soft-deletes first, then purges,
    // and swallows the 409/404 of an already-gone row). The purger takes each
    // event's linked detections with it, so the detection ids need no pass.
    const session = await adminSession(harness);
    await hardDeleteFixtureRows(harness, session, fx.eventIds);
  });

  test('the F4.3 path: delete, undo, delete again, restore, delete again, delete permanently — then 404 with the detection gone', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    // beforeAll seeds the fixture; a fixture failure fails the hook, but the
    // narrowing below keeps the test body honest about reaching this point.
    if (!fx) throw new Error('the beforeAll fixture never produced a fixture object');
    const h = harness;
    const [eventA, eventB] = fx.eventIds;
    const detA = fx.detectionIds[0];

    const pageErrors: string[] = [];
    page.on('pageerror', (err) => pageErrors.push(String(err)));

    // Trash-list responses the PAGE itself fetches: each carries the URL and a
    // body promise. Every trash string asserted below is read from the newest
    // of these bodies. restorePosts covers the Undo's restore, the card
    // restore and the bulk restore; the DELETE counter watches per-row DELETEs
    // only — the bulk door goes through DELETE /api/events/bulk, whose
    // pathname carries no digits and never matches.
    const trashFetches: Array<{ url: URL; body: Promise<DeletedListBody | null> }> = [];
    const restorePosts: Array<{ status: number }> = [];
    let deleteRequests = 0;
    page.on('response', (res) => {
      try {
        const url = new URL(res.url());
        if (url.pathname === '/api/events/deleted') {
          trashFetches.push({ url, body: res.json().catch(() => null) });
        } else if (
          res.request().method() === 'POST' &&
          /\/api\/events\/\d+\/restore$/.test(url.pathname)
        ) {
          restorePosts.push({ status: res.status() });
        } else if (
          res.request().method() === 'DELETE' &&
          /^\/api\/events\/\d+$/.test(url.pathname)
        ) {
          deleteRequests += 1;
        }
      } catch {
        /* non-URL-ish response — not our endpoint */
      }
    });

    /* ── Leg 1: open an event, Delete, Undo ──────────────────────────────── */
    // The `?event=` deep link opens the modal for a LIVE row (a trashed row's
    // detail fetch 404s, so every boot below happens while the row is live).
    let session = await openTimelineEventModal(page, h, {
      cameraId: fx.cameraId,
      eventId: eventA,
    });
    const modal = page.getByTestId('event-detail-modal');
    await expect(modal).toBeVisible();
    const deleteButton = page.getByTestId('delete-event-button');
    await expect(deleteButton).toBeVisible();

    await deleteButton.click();
    // Ruling 131: no confirmation — the Undo toast replaces it. The action
    // button is a real sonner-rendered `button[data-button][data-action]`
    // labelled Undo; the Toaster (z-index 999999999) floats above the modal.
    const toast = page.locator('[data-sonner-toast]').filter({ hasText: 'Moved to Trash' });
    await expect(toast).toBeVisible({ timeout: 10_000 });
    await toast.getByRole('button', { name: 'Undo' }).click();

    // The Undo restored the row: the single read answers 200 again (a trashed
    // row 404s it — get_event_or_404 filters deleted_at IS NULL). The poll
    // also guarantees the restore POST's RESPONSE has landed before the
    // observer read below — an unchecked array index here would read the
    // array a tick too early (the response handler pushes on arrival).
    await expect.poll(() => statusOf(h, session, `/api/events/${eventA}`)).toBe(200);
    await expect.poll(() => restorePosts.some((p) => p.status === 200)).toBe(true);

    /* ── Leg 2: Delete again (no Undo this time) ─────────────────────────── */
    session = await openTimelineEventModal(page, h, {
      cameraId: fx.cameraId,
      eventId: eventA,
    });
    await expect(page.getByTestId('delete-event-button')).toBeVisible();
    await page.getByTestId('delete-event-button').click();
    await expect(
      page.locator('[data-sonner-toast]').filter({ hasText: 'Moved to Trash' })
    ).toBeVisible({ timeout: 10_000 });
    // Deliberately NOT clicking Undo: this delete stands.

    /* ── Leg 3: find it in Trash ─────────────────────────────────────────── */
    const atTrash1 = trashFetches.length;
    await page.goto(`${h.ui}/trash`, { waitUntil: 'domcontentloaded' });
    await expect.poll(() => trashFetches.length).toBeGreaterThan(atTrash1);
    const trash1 = (await trashFetches[trashFetches.length - 1].body) as DeletedListBody;
    expect(
      trash1.items.map((e) => e.id),
      'the page itself saw event A in the trash'
    ).toContain(eventA);

    // Count line mirrors the page's own list (singular branch).
    await expect(page.getByText('1 event in trash')).toBeVisible();

    // Card mirrors from the page's body: camera heading, summary, risk badge,
    // the relative Deleted stamp, and the F4.3 purge-date chip (rendered
    // whenever /api/system/config reports retention_days — the exact date is
    // trashPurge's unit-tested math, not this spec's). The h3 mirror is safe
    // with the count gate above: exactly one card is mounted, and the card's
    // confirm-dialog h3 mounts only while that dialog is open.
    const cardA = page.getByTestId(`deleted-event-card-${eventA}`);
    await expect(cardA).toBeVisible();
    await expect(cardA.locator('h3')).toHaveText(trash1.items[0].camera_id);
    if (trash1.items[0].summary) await expect(cardA).toContainText(trash1.items[0].summary);
    if (trash1.items[0].risk_score !== null) {
      await expect(cardA).toContainText(riskBadgeText(trash1.items[0].risk_score));
    }
    await expect(cardA).toContainText(/Deleted\s*(Just now|\d+ minutes? ago)/);
    await expect(cardA.getByTestId(`purge-date-${eventA}`)).toContainText('Purged: ');

    // "refreshes": a reload re-boots the app and the observer proves the new
    // mount fetched the trash list again (no refresh button exists here).
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect.poll(() => trashFetches.length).toBeGreaterThan(atTrash1 + 1);

    /* ── Leg 4: Restore it ───────────────────────────────────────────────── */
    await expect(page.getByTestId(`deleted-event-card-${eventA}`)).toBeVisible();
    await page
      .getByTestId(`deleted-event-card-${eventA}`)
      .getByRole('button', { name: 'Restore', exact: true })
      .click();
    // The card drops when the invalidated trash list refetches, which lands
    // AFTER the restore response — so the status read below is safe only once
    // the card is gone; assert the drop first, then the observed status.
    await expect(page.getByTestId(`deleted-event-card-${eventA}`)).toHaveCount(0);
    expect(restorePosts[restorePosts.length - 1].status).toBe(200);
    await expect.poll(() => statusOf(h, session, `/api/events/${eventA}`)).toBe(200);

    /* ── Leg 5: Delete again (third soft delete) ─────────────────────────── */
    session = await openTimelineEventModal(page, h, {
      cameraId: fx.cameraId,
      eventId: eventA,
    });
    await expect(page.getByTestId('delete-event-button')).toBeVisible();
    await page.getByTestId('delete-event-button').click();
    await expect(
      page.locator('[data-sonner-toast]').filter({ hasText: 'Moved to Trash' })
    ).toBeVisible({ timeout: 10_000 });

    /* ── Leg 6: Delete permanently and confirm ───────────────────────────── */
    const atTrash2 = trashFetches.length;
    await page.goto(`${h.ui}/trash`, { waitUntil: 'domcontentloaded' });
    await expect.poll(() => trashFetches.length).toBeGreaterThan(atTrash2);
    const card2 = page.getByTestId(`deleted-event-card-${eventA}`);
    await expect(card2).toBeVisible();

    const deletesBeforePurge = deleteRequests; // 3 soft deletes so far
    const cardConfirm = card2.locator('[role="dialog"]');
    await card2.getByRole('button', { name: 'Delete Forever', exact: true }).click();
    await expect(cardConfirm).toBeVisible();
    await expect(cardConfirm).toContainText('Permanent Delete');
    // The measured confirm control inside the card-local dialog (the same
    // locator DeletedEventCard.test.tsx pins): the one btn-danger button.
    await cardConfirm.locator('button.btn-danger').click();
    // The card drops when the invalidated trash list refetches, which lands
    // AFTER the permanent DELETE's response the counter below reads.
    await expect(card2).toHaveCount(0);
    expect(deleteRequests).toBe(deletesBeforePurge + 1); // the permanent DELETE
    await expect(cardConfirm).toHaveCount(0);

    // The purge-proof triple (B4.4's pytest golden asserts the same three),
    // adapted to the state this drive starts from — A is TRASHED here, and a
    // trashed row already 404s the single read (get_event_or_404 filters
    // deleted_at IS NULL), so (a) proves nothing on top of the trash state and
    // the honest gates are (b) and (c), both polled until the purge lands:
    // (b) A leaves the trash the backend serves (a trashed A is IN it), and
    // (c) its linked detection answers 404 — only a purge removes a detection;
    // a trashed event's detection survives (the pytest tier additionally
    // lists the media dir and asserts the event's own 404 from a LIVE start).
    await expect
      .poll(async () => {
        const list = await api<DeletedListBody>(h, session, '/api/events/deleted');
        return list.items.map((e) => e.id);
      })
      .not.toContain(eventA);
    await expect.poll(() => statusOf(h, session, `/api/detections/${detA}`)).toBe(404);
    await expect.poll(() => statusOf(h, session, `/api/events/${eventA}`)).toBe(404);

    /* ── Leg 7: the bulk door (timeline grid) + the trash cancels ────────── */
    session = await openTimelineEventModal(page, h, { cameraId: fx.cameraId });
    // The camera-filtered grid now holds B and C (A is purged); the fixture
    // spacing defeats clustering, so both render as their own cards.
    await waitForEventCards(page);
    await expect(page.getByTestId(`event-card-${eventB}`)).toBeVisible();
    await page.getByRole('button', { name: `Select event ${eventB}` }).click();
    const bulkDelete = page.getByTestId('bulk-delete-button');
    await expect(bulkDelete).toBeVisible();
    await bulkDelete.click();
    await expect(
      page.locator('[data-sonner-toast]').filter({ hasText: 'Moved 1 event to Trash' })
    ).toBeVisible({ timeout: 10_000 });

    const atTrash3 = trashFetches.length;
    await page.goto(`${h.ui}/trash`, { waitUntil: 'domcontentloaded' });
    await expect.poll(() => trashFetches.length).toBeGreaterThan(atTrash3);
    const cardB = page.getByTestId(`deleted-event-card-${eventB}`);
    await expect(cardB).toBeVisible();

    // Empty Trash cancels clean: the dialog mirrors the count, Cancel closes
    // it, and the DELETE counter does not move.
    const deletesBeforeEmpty = deleteRequests;
    const emptyTrash = page.getByTestId('empty-trash-button');
    await emptyTrash.click();
    const pageDialog = page.getByTestId('confirm-dialog');
    await expect(pageDialog).toBeVisible();
    await expect(pageDialog).toContainText('Empty Trash? (1 event)');
    await pageDialog.getByRole('button', { name: 'Cancel', exact: true }).click();
    await expect(pageDialog).toHaveCount(0);
    expect(deleteRequests).toBe(deletesBeforeEmpty);
    await expect(cardB).toBeVisible();

    // The card's own permanent-delete overlay also cancels clean.
    await cardB.getByRole('button', { name: 'Delete Forever', exact: true }).click();
    const cardBCancel = cardB.locator('[role="dialog"]');
    await expect(cardBCancel).toBeVisible();
    await cardBCancel.getByRole('button', { name: 'Cancel', exact: true }).click();
    await expect(cardBCancel).toHaveCount(0);
    expect(deleteRequests).toBe(deletesBeforeEmpty);

    // Bulk restore (F-087's clause): Select All marks B, the bar mirrors the
    // count, and the bulk handler restores the selection.
    await page.getByTestId('select-all-button').click();
    const bar = page.getByTestId('bulk-action-bar');
    await expect(bar).toBeVisible();
    await expect(bar).toContainText('1 event selected');
    const atBulkRestore = restorePosts.length;
    await page.getByTestId('restore-selected-button').click();
    // Card drop first (the refetch lands after the response), then the status.
    await expect(cardB).toHaveCount(0);
    await expect.poll(() => restorePosts.length).toBeGreaterThan(atBulkRestore);
    expect(restorePosts[restorePosts.length - 1].status).toBe(200);
    await expect(page.getByText('Trash is empty')).toBeVisible();
    await expect(emptyTrash).toBeDisabled();

    /* ── Backend truth ───────────────────────────────────────────────────── */
    // The trash is empty at the source; B and C are live; A is neither.
    const after = await api<DeletedListBody>(h, session, '/api/events/deleted');
    expect(after.items).toEqual([]);
    const active = await api<EventListBody>(
      h,
      session,
      `/api/events?limit=100&camera_id=${encodeURIComponent(fx.cameraId)}`
    );
    const activeIds = active.items.map((e) => e.id);
    expect(activeIds).toContain(eventB);
    expect(activeIds).toContain(fx.eventIds[2]); // the untouched control
    expect(activeIds).not.toContain(eventA);

    // Per-row DELETE arithmetic over the whole drive: A's three soft deletes
    // plus its one permanent delete — the two cancels produced none.
    expect(deleteRequests).toBe(4);
    for (const p of restorePosts) expect(p.status).toBe(200);
    expect(pageErrors).toEqual([]);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-101 Data › Restore from backup modal uploads a backup ZIP, shows the safety backup link and per-table summary, and reports failure detail on a tampered archive', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    // 1. Create a real backup via the backend API (202 Accepted) and download its ZIP bytes
    const createRes = await fetch(`${h.api}/api/backup`, {
      method: 'POST',
      headers: { ...apiCookie(session), 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    expect(createRes.status).toBe(202);
    const created = (await createRes.json()) as { job_id: string; status: string };
    expect(created.job_id).toBeTruthy();

    let backupStatus = '';
    for (let i = 0; i < 60; i++) {
      const job = await api<{ status: string }>(h, session, `/api/backup/${created.job_id}`);
      backupStatus = job.status;
      if (backupStatus === 'completed' || backupStatus === 'failed') break;
      await new Promise((r) => setTimeout(r, 1000));
    }
    expect(backupStatus).toBe('completed');

    const dlRes = await fetch(`${h.api}/api/backup/${created.job_id}/download`, {
      headers: apiCookie(session),
    });
    expect(dlRes.status).toBe(200);
    const zipBuffer = Buffer.from(await dlRes.arrayBuffer());
    expect(zipBuffer.length).toBeGreaterThan(0);

    // 2. Open /data and launch RestoreModal
    const pageErrors: string[] = [];
    page.on('pageerror', (err) => pageErrors.push(String(err)));

    await page.goto(`${h.ui}/data`, { waitUntil: 'domcontentloaded' });
    const backupSection = page.getByTestId('backup-section');
    await expect(backupSection).toBeVisible();

    await backupSection.getByRole('button', { name: 'Restore', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Restore from Backup' })).toBeVisible();
    await expect(page.getByTestId('restore-warning')).toBeVisible();

    // 3. Upload the real backup ZIP and wait for completion
    await page.getByTestId('file-input').setInputFiles({
      name: 'golden_restore.zip',
      mimeType: 'application/zip',
      buffer: zipBuffer,
    });

    const completeState = page.getByTestId('complete-state');
    await expect(completeState).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId('safety-backup-banner')).toBeVisible();
    await expect(page.getByTestId('safety-backup-download-link')).toBeVisible();
    await expect(page.getByTestId('safety-backup-restore-link')).toBeVisible();
    await expect(page.getByTestId('restore-table-summary-cameras')).toContainText(
      /restored \d+ cameras/
    );
    await expect(page.getByTestId('restore-table-summary-cameras')).toContainText(
      /kept \d+ not in this backup/
    );

    await page.getByRole('button', { name: 'Close modal', exact: true }).click();
    await expect(completeState).toHaveCount(0);

    // 4. Re-open RestoreModal and upload a tampered archive to verify failure detail
    await backupSection.getByRole('button', { name: 'Restore', exact: true }).click();
    await page.getByTestId('file-input').setInputFiles({
      name: 'tampered.zip',
      mimeType: 'application/zip',
      buffer: Buffer.from('not a valid zip archive'),
    });

    const errorState = page.getByTestId('error-state');
    await expect(errorState).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId('restore-error-detail')).toContainText(/Invalid backup file/i);
    expect(pageErrors).toEqual([]);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});

/** Mirror of frontend/src/utils/risk.ts getRiskLevel + getRiskLabel (thresholds
 *  LOW 0-29 / MEDIUM 30-59 / HIGH 60-84 / CRITICAL 85-100, risk.ts:95-105,196).
 *  The card renders RiskBadge showScore, i.e. "Medium (54)" — the mirror lets
 *  the spec assert the badge from the API's own score rather than a snapshot. */
function riskBadgeText(score: number): string {
  const level = score <= 29 ? 'Low' : score <= 59 ? 'Medium' : score <= 84 ? 'High' : 'Critical';
  return `${level} (${score})`;
}

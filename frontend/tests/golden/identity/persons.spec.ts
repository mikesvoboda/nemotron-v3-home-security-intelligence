/**
 * F2.3 DO-3 golden path, known-persons half (inventory F-275, F-277; claim #6996).
 * Route: /face-recognition (`path="/face-recognition"` frontend/src/App.tsx:321).
 *
 * What this file proves per row (backend fact read BEFORE the UI that renders
 * it, so a blank screen can never pass as "renders"):
 *
 *  F-275  "sees cards for every known person with their enrolled-face count;
 *         clicks Add Person or a card" — two mounts, because the page has TWO
 *         empty states and only one of them is the passive one:
 *          (a) PASSED mount, no writes: GET /api/known-persons → 200 with
 *              {items: [], total: 0}. It is empty because the no-env fake-AI
 *              stack seeds ONLY cameras — scripts/feature_check.py calls
 *              seed_cameras() (:1284) and greps 0 for known-persons (harness.ts
 *              header, positive control `cameras` = 16). No other golden spec
 *              touches persons either: `grep -rniE 'known.?person|face.?embedding
 *              |/face-recognition' frontend/tests/golden/` returns only this
 *              batch's own files (control term `notification.?preferences`
 *              returns 3 notify-access files, so the grep reaches the tree).
 *              So the grid branch is NOT what a bare mount shows: the shipped
 *              empty copy is <p>No known persons</p> / <p>Add your first person
 *              to start tracking faces</p> (KnownPersonsTab.tsx:231-232), the
 *              count badge reads (0) (:214-216), and the Add Person button is
 *              present (:218-224).
 *           (b) A seeded row, created and deleted by THIS test: POST
 *               /api/known-persons → 201 echoing name/notes and embedding_count
 *               0 (routes/face_recognition.py:135-170, the handler returns the
 *               literal 0 at :166); the GET list then sees it; the card paints
 *               with role="button" + aria-label "View details for <name>" and a
 *               static data-testid="known-person-card" (KnownPersonsTab.tsx:60-67),
 *               and its embedding-count text is {person.embedding_count} (:82)
 *               — so the "enrolled-face count" the row promises is pinned to the
 *               API's embedding_count, not to a decoration. Clicking the card
 *               opens the detail modal (FaceRecognitionPage.tsx:57-60 sets
 *               detailPersonId + isOpen from the click) whose gallery heading is
 *               `Face Embeddings (0)` (KnownPersonDetailModal.tsx:296-297,
 *               rendered UNCONDITIONALLY once its own query settles — the only
 *               conditional above it is the isLoading branch at :284).
 *
 *  F-277  "clicks Add Person (or Edit in the detail modal); enters name,
 *         household flag and notes; saves" — the modal FORM DRIVE is not in
 *         this file yet (see Deliberate non-legs); the leg here is the route
 *         contract the save depends on: POST 201 with the body round-tripping,
 *         and PATCH /api/known-persons/{id} changing name/notes and NOT
 *         inventing one. Both mutations are undone here (DELETE 204 at
 *         :254-257; a second DELETE of the now-unknown id → 404 at :272-274,
 *         which doubles as the proof the row is gone).
 *
 * What this file deliberately does NOT claim:
 *  - It does not put a real face embedding anywhere. F-278's promise is
 *    "deletes one embedding" and the honest answer to whether that can be
 *    seeded in this stack is still open — the sanctioned writers are
 *    enroll-from-detection (needs a detection with a visible face) and
 *    bulk-enroll (an UploadFile list), and POST /known-persons/{id}/embeddings
 *    is RETIRED, always 410 Gone (the raise is at :384; the 410 in the
 *    decorator's responses map at :347 is documentation, which is why my first
 *    note cited the wrong line). F-278 stays unverified; its own spec is gated
 *    on that question, not on this file.
 *  - The Add Person form's input round-trip. AddPersonModal is its own
 *    component; its field set (name / household flag / notes) and the save
 *    leg go in persons-modal.spec.ts once the form's accessible names are
 *    pinned the same way — asserting a form drive from a locator I have not
 *    read is how a green test proves nothing.
 *  - Anything about the Face Events / Person Tracking tabs (F-276, F-279 are
 *    different rows) — Headless UI renders only the selected panel
 *    (FaceRecognitionPage.tsx:295-309) and selectedTabIndex starts at 0 (:235),
 *    so this mount never shows them.
 */
import { expect, test } from '../guard';
import {
  adminSession,
  assertGuardSurvives,
  authedFetch,
  login,
  readHarness,
  type Harness,
} from './harness';

const harness = readHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

/** A name no other test can collide with, and short enough to survive the
 *  schema's own limits. Uniqueness matters because the empty-state leg asserts
 *  total === 0: a row left behind by an earlier spec in the same stack would
 *  make THAT leg fail for someone else's reason. */
const PERSON = 'Golden DO-3 Person';

async function signIn(page: Parameters<typeof login>[0], h: Harness) {
  const session = await adminSession(h);
  await login(page, h, session);
  return authedFetch(h, session);
}

test.describe('DO-3 known persons golden path', () => {
  test('F-275 gallery: empty mount, a seeded card with its embedding count, and the detail modal', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    // --- API leg first: the stack seeds no persons, so the passive mount is
    //     the EMPTY grid branch, not a gallery. ---
    const before = await api.getJson('/api/known-persons');
    expect(before.status, 'GET /api/known-persons answers 200').toBe(200);
    expect(
      Array.isArray(before.body?.items),
      `the list response carries an items array, got ${JSON.stringify(before.body)}`
    ).toBe(true);
    expect(before.body?.items, 'the fake-AI stack seeds no known persons').toHaveLength(0);
    expect(before.body?.total, 'total agrees with the empty list').toBe(0);

    // --- UI leg: the shipped empty copy, VERBATIM. ---
    await page.goto(`${h.ui}/face-recognition`, { waitUntil: 'domcontentloaded' });
    // Real <h2> (KnownPersonsTab.tsx:213) — no Tremor <Title> here, so the
    // heading role is available (harness.ts header: per-element, not per-page).
    await expect(page.getByRole('heading', { name: 'Known Persons', level: 2 })).toBeVisible();
    // Scoped to the header (data-testid="known-persons-header", :209): the badge
    // renders as the literal text "({personCount})" (:215) and getByText is a
    // SUBSTRING match by default, so an unscoped '(0)' could bind a stat card or
    // a modal heading in a later run. exact:true would not help — the string it
    // must match IS "(0)", so the fix is scope, not strictness.
    await expect(page.getByTestId('known-persons-header').getByText('(0)')).toBeVisible();
    await expect(page.getByText('No known persons')).toBeVisible(); // :231
    await expect(page.getByText('Add your first person to start tracking faces')).toBeVisible(); // :232
    // Text-named: the button has NO name attribute (:218-224), so its accessible
    // name is its own text plus an aria-hidden icon. exact:true because
    // getByRole's name matching is a SUBSTRING match by default and this mount
    // has near-misses — UnknownStrangersPanel.tsx:204 renders "Add as New
    // Person", which a loose /Add Person/i would bind.
    const addPerson = page.getByRole('button', { name: 'Add Person', exact: true });
    await expect(addPerson).toBeVisible();
    // The grid must NOT exist while the list is empty — this is what makes the
    // empty-state asserts above mean "the page chose the empty branch" rather
    // than "my text happened to appear somewhere".
    await expect(page.getByTestId('known-persons-grid')).toHaveCount(0);

    // --- seed one person through the shipped route, then re-read through it ---
    let createdId: number | null = null;
    try {
      const created = await api.send('/api/known-persons', 'POST', {
        name: PERSON,
        is_household_member: false,
        notes: 'golden DO-3 fixture',
      });
      expect(created.status, 'POST /api/known-persons answers 201').toBe(201);
      expect(created.body?.name, 'the create response echoes the name').toBe(PERSON);
      expect(created.body?.is_household_member, 'it echoes the household flag').toBe(false);
      // :166 returns the literal 0 for a fresh person — this is the value the
      // card's count must render, so pin it at the source before the UI.
      expect(created.body?.embedding_count, 'a fresh person has 0 embeddings').toBe(0);
      expect(typeof created.body?.id, 'the create response carries an id').toBe('number');
      createdId = created.body.id as number;

      const after = await api.getJson('/api/known-persons');
      expect(after.body?.items, 'the list now sees the new person').toHaveLength(1);
      expect(after.body?.total, 'total follows the list').toBe(1);

      // --- UI leg on the seeded card: reload so the page refetches. ---
      await page.reload({ waitUntil: 'domcontentloaded' });
      const card = page.getByRole('button', { name: `View details for ${PERSON}` });
      await expect(card).toBeVisible();
      await expect(card).toHaveAttribute('data-testid', 'known-person-card');
      // The row's "with their enrolled-face count": the card prints
      // {person.embedding_count} (KnownPersonsTab.tsx:81). Text equality, not
      // a count of nodes — a card showing "2" would pass a hasText: /embed/i
      // style assert and lie about the number.
      await expect(card).toContainText('0');
      await expect(page.getByTestId('known-persons-grid')).toBeVisible();
      // The empty copy must be GONE once the grid branch is live: without this,
      // a page that rendered BOTH branches would pass every assert above.
      await expect(page.getByText('No known persons')).toHaveCount(0);

      // --- "clicks a card": the detail modal opens on this person. ---
      await card.click();
      // exact:true: '(0)' is the part a loose substring match would let a
      // later '(12)' heading satisfy, which is exactly the failure this assert
      // exists to catch.
      await expect(
        page.getByRole('heading', { name: 'Face Embeddings (0)', level: 3, exact: true })
      ).toBeVisible();
      await expect(page.getByTestId('face-embeddings-gallery')).toBeVisible();
      await expect(page.getByText('No face embeddings yet.')).toBeVisible();
    } finally {
      // Restore the stack to the state the empty-state leg found. Swallow the
      // failure: if the DELETE itself is what broke, the assertion above that
      // proves deletion never ran, and a thrown restore would bury that.
      if (createdId !== null) {
        await api.send(`/api/known-persons/${createdId}`, 'DELETE').catch(() => null);
      }
    }

    // --- the delete is proven through the API, not assumed from the 204 ---
    const gone = await api.getJson('/api/known-persons');
    expect(gone.body?.items, 'the fixture row is gone after the restore').toHaveLength(0);

    await assertGuardSurvives(page, h);
  });

  test('F-277 write routes: POST creates, PATCH edits, and both are undone here', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    const created = await api.send('/api/known-persons', 'POST', {
      name: PERSON,
      is_household_member: false,
      notes: 'before',
    });
    expect(created.status, 'POST /api/known-persons answers 201').toBe(201);
    const id = created.body?.id as number;
    expect(typeof id, 'the create response carries a numeric id').toBe('number');

    try {
      // PATCH is the route the modal's Edit save uses (row F-277 lists
      // PATCH /api/known-persons/{person_id}; :209 is the handler).
      const edited = await api.send(`/api/known-persons/${id}`, 'PATCH', {
        name: 'Golden DO-3 Renamed',
        notes: 'after',
      });
      expect(edited.status, 'PATCH /api/known-persons/{id} answers 200').toBeLessThan(300);
      expect(edited.body?.name, 'the patch changed the name').toBe('Golden DO-3 Renamed');
      expect(edited.body?.notes, 'the patch changed the notes').toBe('after');

      const seen = await api.getJson(`/api/known-persons/${id}`);
      expect(seen.status, 'GET /api/known-persons/{id} answers 200').toBe(200);
      expect(seen.body?.name, 'the store agrees the name changed').toBe('Golden DO-3 Renamed');

      // A PATCH that sends nothing must not invent a value.
      const noop = await api.send(`/api/known-persons/${id}`, 'PATCH', {});
      expect(noop.status, 'an empty PATCH still 2xx').toBeLessThan(300);
      expect(noop.body?.name, 'an empty PATCH leaves the name alone').toBe('Golden DO-3 Renamed');
    } finally {
      await api.send(`/api/known-persons/${id}`, 'DELETE').catch(() => null);
    }

    const afterDelete = await api.send(`/api/known-persons/${id}`, 'DELETE');
    expect(
      [204, 404],
      `a second DELETE of a removed person is 204 or 404, got ${afterDelete.status}`
    ).toContain(afterDelete.status);

    const list = await api.getJson('/api/known-persons');
    expect(list.body?.items, 'the gallery is back to the seeded state').toHaveLength(0);

    await assertGuardSurvives(page, h);
  });
});

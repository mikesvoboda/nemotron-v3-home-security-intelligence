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
 *              seed_cameras() (call :1836; the def is :1284) and greps 0 for
 *              known-persons (harness.ts
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
 *           (b) A seeded row, created and deleted by THIS test. THE LEGS SPLIT:
 *               the API legs are a GREEN witness, the UI legs are a MEASURED RED
 *               kept on purpose as failure-as-evidence (rulings 86/118 — this is
 *               why row F-275 is half-built, not awaiting real tier).
 *               GREEN: POST /api/known-persons → 201 echoing name/notes and
 *               embedding_count 0 (routes/face_recognition.py:135-169 — decorator
 *               :135, handler :140, return :161-169 — and the handler returns the
 *               literal 0 at :166), and the GET list then sees it.
 *               RED, by design, and the FIRST UI assertion after the seed: the
 *               card never paints, so nothing downstream of it can be reached.
 *               KnownPersonsTab.tsx:176 reads knownPersons?.length ?? 0 on the
 *               list the route answers as the ENVELOPE
 *               KnownPersonListResponse(items,total) (face_recognition.py:132,
 *               and useFaceRecognitionApi.ts:124 passes it through unwrapped),
 *               so a seeded row still counts 0 and the empty copy at :231 stands.
 *               The spec's own expect(card).toBeVisible() is the pin on that
 *               break (Break A, report #6996 `6113183779`); it is the failure the
 *               frontend fix package exists to clear.
 *               Therefore the UI claims below are the CONTRACT the fix must
 *               satisfy, read as design notes until Break A clears — the card's
 *               role="button" + aria-label "View details for <name>" and static
 *               data-testid="known-person-card" (KnownPersonsTab.tsx:60-67); its
 *               embedding-count text {person.embedding_count} (:82), pinning the
 *               "enrolled-face count" the row promises to the API's
 *               embedding_count, not a decoration; and the detail modal the click
 *               opens (FaceRecognitionPage.tsx:57-60 sets detailPersonId + isOpen)
 *               with heading `Face Embeddings (0)`
 *               (KnownPersonDetailModal.tsx:296-297, rendered UNCONDITIONALLY once
 *               its own query settles — the only conditional above it is the
 *               isLoading branch at :285).
 *
 *  F-277  "clicks Add Person (or Edit in the detail modal); enters name,
 *         household flag and notes; saves" — the modal FORM DRIVE is not in
 *         this file yet (see Deliberate non-legs); the leg here is the route
 *         contract the save depends on: POST 201 with the body round-tripping,
 *         and PATCH /api/known-persons/{id} changing name/notes and NOT
 *         inventing one. Both mutations are undone here (the restore DELETE in
 *         each test's finally; a second DELETE of the now-unknown id → 204 or
 *         404, which doubles as the proof the row is gone). Deliberately NOT
 *         line-numbered: these are SELF-cites, and a self-cite goes stale the
 *         moment the file above it grows — which is exactly what the two ranges
 *         written here before this edit had done (`:254-257` and `:272-274` in a
 *         file that is 251 lines). The rule holds for other files' lines, where
 *         grep -n re-reads them; it does not for this file's own.
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
    // name is its own text plus an aria-hidden icon — assert the text.
    // exact:true is INSURANCE here, not disambiguation, and the earlier version
    // of this comment overstated it: it blamed a near-miss at
    // UnknownStrangersPanel.tsx:204 ("Add as New Person"), which cannot fire
    // twice over — (1) that component is never mounted (its only export is
    // commented out, components/face-recognition/index.ts:105), and (2) even
    // mounted it is not a substring match, since "Add as New Person" does not
    // CONTAIN "Add Person" and getByRole's loose name match is a substring test.
    // The real candidate set, measured repo-wide for visible strings containing
    // "add person" case-insensitively: this button (:223) and, once the modal is
    // open, AddPersonModal's Dialog.Title "Add Person" (:216) — a HEADING, so
    // getByRole('button') could not bind it either. Other tabs are not mounted at
    // all: Tab.Panel with the default `unmount` renders an aria-hidden stub
    // instead of its children for an inactive tab (@headlessui/react 2.2.9,
    // dist/components/tabs/tabs.js — `!selected && (unmount ?? true)`), and
    // selectedTabIndex starts at 0 (FaceRecognitionPage.tsx:235). Keeping
    // exact:true anyway: Playwright locators are ALWAYS strict — the day a second
    // "Add Person" BUTTON lands on this mount, a loose locator resolves to two
    // nodes and throws `strict mode violation` on every action, in whoever's PR
    // adds the button, naming a spec they never touched. exact:true pins this
    // locator to my element regardless of what else shares the label.
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
      // Capture the id BEFORE asserting anything about the response. The row
      // exists server-side the moment the POST returns it; an assert that throws
      // before the capture would leak the fixture, and the leak surfaces as the
      // NEXT test's empty-state leg failing for this test's reason. A loose
      // capture (typeof guard, no cast) so a malformed body cannot throw here.
      createdId = typeof created.body?.id === 'number' ? created.body.id : null;
      // The count the UI leg must render, taken from the same response rather
      // than hard-coded, so the card assert compares the page against the API
      // instead than against a literal I could drift away from.
      const seededCount =
        typeof created.body?.embedding_count === 'number' ? created.body.embedding_count : -1;
      expect(created.status, 'POST /api/known-persons answers 201').toBe(201);
      expect(created.body?.name, 'the create response echoes the name').toBe(PERSON);
      expect(created.body?.is_household_member, 'it echoes the household flag').toBe(false);
      // :166 returns the literal 0 for a fresh person — this is the value the
      // card's count must render, so pin it at the source before the UI.
      expect(created.body?.embedding_count, 'a fresh person has 0 embeddings').toBe(0);
      expect(typeof created.body?.id, 'the create response carries an id').toBe('number');

      const after = await api.getJson('/api/known-persons');
      expect(after.body?.items, 'the list now sees the new person').toHaveLength(1);
      expect(after.body?.total, 'total follows the list').toBe(1);

      // --- UI leg on the seeded card: reload so the page refetches. ---
      await page.reload({ waitUntil: 'domcontentloaded' });
      const card = page.getByRole('button', { name: `View details for ${PERSON}` });
      await expect(card).toBeVisible();
      await expect(card).toHaveAttribute('data-testid', 'known-person-card');
      // The row's "with their enrolled-face count": the card prints
      // {person.embedding_count} (KnownPersonsTab.tsx:82) in its OWN <span>, so
      // assert a node whose ENTIRE text is the number the API reported — scoped
      // to this card. Two weaker forms this replaces, both measured: the
      // `toContainText('0')` that was here is a substring test over the whole
      // concatenated card (measured card textContent "Golden DO-3 Person0" —
      // name + count + Household badge with NO separator), so it also passes on
      // 10 or 100; and a page-wide getByText('0',{exact:true}) is not the fix
      // either, because the header badge renders "(0)" and joins the match.
      // Binding to seededCount (not a literal 0) so the UI leg compares against
      // the value the API leg pinned.
      await expect(card.getByText(`${seededCount}`, { exact: true })).toHaveText(`${seededCount}`);
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
      // The shipped copy in full: KnownPersonDetailModal.tsx:311 is
      // "No face embeddings yet. Add one from a detection event." — one plain
      // text node in a plain <div> (no <strong> to break the string). The
      // previous leg here matched only the first sentence, so a copy that lost
      // its second sentence — the part that names the sanctioned write path —
      // still passed. Assert the whole thing.
      await expect(
        page.getByText('No face embeddings yet. Add one from a detection event.')
      ).toBeVisible();
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

    // The id is null until the POST answers, and the finally below runs either
    // way: the try opens BEFORE the request so a POST that creates the row and
    // then throws in transit still gets cleaned up, and the delete is skipped
    // (not sent to /null) when no id was ever learned.
    let id: number | null = null;
    try {
      const created = await api.send('/api/known-persons', 'POST', {
        name: PERSON,
        is_household_member: false,
        notes: 'before',
      });
      id = typeof created.body?.id === 'number' ? created.body.id : null;
      expect(created.status, 'POST /api/known-persons answers 201').toBe(201);
      expect(typeof id, 'the create response carries a numeric id').toBe('number');

      // PATCH is the route the modal's Edit save uses (row F-277 lists
      // PATCH /api/known-persons/{person_id}; decorator :209, handler :210).
      const edited = await api.send(`/api/known-persons/${id}`, 'PATCH', {
        name: 'Golden DO-3 Renamed',
        notes: 'after',
      });
      // 200, not merely "2xx": the decorator (face_recognition.py:209) declares
      // no status_code, so 200 is FastAPI's default for a body-returning route —
      // and it is pinned in a committed artifact, the generated client's
      // responses map (types/generated/api.ts:54603 lists 200 and 422 only). A
      // 202 "accepted, applied asynchronously" would satisfy toBeLessThan(300)
      // while this message says 200, and the async variant would break the
      // read-back below rather than here.
      expect(edited.status, 'PATCH /api/known-persons/{id} answers 200').toBe(200);
      expect(edited.body?.name, 'the patch changed the name').toBe('Golden DO-3 Renamed');
      expect(edited.body?.notes, 'the patch changed the notes').toBe('after');

      const seen = await api.getJson(`/api/known-persons/${id}`);
      expect(seen.status, 'GET /api/known-persons/{id} answers 200').toBe(200);
      expect(seen.body?.name, 'the store agrees the name changed').toBe('Golden DO-3 Renamed');

      // A PATCH that sends nothing must not invent a value. Pinned at 200 for the
      // same reason as the leg above, plus one that is specific to THIS body:
      // KnownPersonUpdate (backend/api/schemas/face_recognition.py:64-78) defaults
      // all three fields to None, so {} validates (the name field's min_length=1
      // never applies to an absent field) — which rules out 422 — and the handler
      // has only two exits, 404 at :237-241 and 200 at :243, so a found row leaves
      // 200 standing. What the leg is really about is the next line: the service
      // guard (backend/services/face_recognition_service.py:213-218) applies each
      // field under `if … is not None`, so an empty PATCH must be a no-op and not
      // a wipe. A toBeLessThan(300) here would also pass on a 202 or a 204-with-
      // no-body, and the name assert would then fail for the wrong reason.
      const noop = await api.send(`/api/known-persons/${id}`, 'PATCH', {});
      expect(noop.status, 'an empty PATCH answers 200').toBe(200);
      expect(noop.body?.name, 'an empty PATCH leaves the name alone').toBe('Golden DO-3 Renamed');
    } finally {
      // Mirror test 1's `createdId !== null` guard: when the POST never returned
      // an id the expect() above THREW, so this finally is the only exit that
      // runs — the afterDelete leg below is unreachable — and an unguarded send
      // here is a real DELETE /api/known-persons/null on the wire.
      if (id !== null) {
        await api.send(`/api/known-persons/${id}`, 'DELETE').catch(() => null);
      }
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

/**
 * F2.3 DO-3 golden path, household half (inventory F-270, F-271; claim #6996).
 * Route: /household (`path="/household"` frontend/src/App.tsx:319).
 *
 * STATUS: no golden run has executed this file yet. Both rows stay `unverified`
 * until one does (ruling 114: the run names its commit and command; ruling 103:
 * a green path MOVES a row, it is not moved in advance of the witness). Nothing
 * below is licensed by a log until a run says so.
 *
 * What this file proves per row (API leg BEFORE the UI leg that renders it, so
 * a blank screen cannot pass as "renders" and an absent row cannot pass as
 * "deleted" — harness.ts:175-177):
 *
 *  F-270 "opens the page; sees household members; adds or edits a member (name,
 *         role, trust level, notes); deletes one after confirming" — a full
 *         form drive, not a mount: the Add form (name input, role select, trust
 *         select, notes textarea) → the card the save must paint → the Edit
 *         form (notes change, visible on the card) → the Delete CONFIRMATION
 *         dialog → the API re-read that proves the row is gone.
 *
 *  F-271 "sees registered vehicles; adds or edits one (plate, type, color,
 *         owner); deletes one after confirming" — the vehicle form drive with
 *         its four named fields plus the trusted checkbox, and the owner
 *         linkage asserted where it is actually decidable: the Owner <select>
 *         is populated from the members list, but the vehicle CARD renders no
 *         owner text (HouseholdPage.tsx:1063-1088 shows description, plate, Trusted badge,
 *         color only), so the leg pins the select option set in the DOM and the
 *         persisted owner_id through the API, and the card leg asserts what the
 *         card actually shows. A second API leg pins the owner-integrity
 *         contract the form depends on: create_vehicle 404s an unknown owner_id
 *         (routes/household.py:259-266, the raise at :265-266), so the form's
 *         "No owner assigned" option (value '', HouseholdPage.tsx:621) is the
 *         only null the backend accepts.
 *
 * Component ground truth, each item read at this head before being asserted:
 *  - The lists are BARE. GET /api/household/members and /vehicles answer
 *    `list[...]` (household.py:61, :218 response_model) and useHouseholdApi.ts
 *    consumes them verbatim (:250-256, :301-307) — NO {items,total} envelope,
 *    which is what killed persons.spec.ts's UI leg (Break A: the known-persons
 *    route answers an envelope the component counts as a list). So household's
 *    seeded card SHOULD paint, and if it does not, that is a real frontend
 *    break this spec is the instrument to catch, not a locator artifact.
 *  - The grid refreshes WITHOUT a reload: every mutation's onSuccess calls
 *    invalidateQueries on the list key (useHouseholdApi.ts:419 members create,
 *    :434 update, :448 delete, :473/:488/:502 vehicles). So the
 *    asserts after clicking Save read a live refetch — a reload here would
 *    paper over a broken invalidation, which is half the shipped write path.
 *  - Modal titles are level-2 HEADINGS: Dialog.Title's defaultTag is "h2"
 *    (measured in the installed dependency, @headlessui/react 2.2.10
 *    dist/components/dialog/dialog.js — `let Xe="h2"` feeding the DialogTitle
 *    factory), and HouseholdPage.tsx:177 wraps it. "Confirm Delete" (:207),
 *    "Add Member"/"Edit Member" (:1099), "Add Vehicle"/"Edit Vehicle" (:1122)
 *    are therefore getByRole('heading', {level: 2}) — the same level as the
 *    page's own section <h2>s (Members :940, Vehicles :1031), so every heading
 *    assert here also pins the NAME, never the level alone.
 *  - An aria-label beats the visible text, which matters because three strings
 *    on this page carry a zero-width space: the buttons' visible text is
 *    "Add Membe[U+200B]r" (:956) and "Add Vehicl[U+200B]e" (:1044), but each
 *    button carries aria-label="Add Member"/"Add Vehicle" (:952, :1040), so the
 *    accessible name is clean and getByRole(name) is the SAFE route here while
 *    getByText on the visible text would have to carry the U+200B. The count
 *    badges are the inverse trap and they are NOT symmetric: the member badge
 *    has data-testid="member-count-badge" and a CLEAN {memberCount} text node
 *    (:943-947), the vehicle badge has NO testid and renders
 *    {vehicleCount}[U+200B] (:1034-1036). So the vehicle count assert below
 *    spells the ZWSP into its expected string on purpose — it is shipped copy,
 *    and a "prettier" assert without it would be asserting text the page does
 *    not print.
 *  - The cards have no testid and no role (harness.ts:221-241) — hence the
 *    shared householdCard() ancestor locator, which exists for exactly these
 *    two rows and no others.
 *  - Card edit/delete buttons are aria-label="Edit"/"Delete" with NO name
 *    disambiguator (HouseholdPage.tsx:992/:996 members, :1075/:1082 vehicles), so identical
 *    labels exist in BOTH sections the moment both have a card. Every leg here
 *    scopes them through householdCard(), which is the difference between a
 *    locator and a coincidence.
 *  - The delete is a DIALOG, not window.confirm: handleDeleteMember/
 *    handleDeleteVehicle (HouseholdPage.tsx:798-800, :845-847) only set deleteTarget + open, and
 *    the wire call happens in handleConfirmDelete (:851-868) behind the
 *    "Confirm" button (:221-228). The dialog quotes the item name (itemName =
 *    member.name / vehicle.description, :209) — that span is the leg that
 *    proves the dialog is about MY row.
 *  - PATCH semantics here differ from persons.spec.ts's, and the comment says
 *    so rather than borrowing the other file's reason: both update handlers
 *    apply `updates.model_dump(exclude_unset=True)` (household.py:173-175
 *    members, :347 then :360-361 setattr on vehicles), so an absent field is
 *    not just skipped by an `is not None` guard, it never reaches setattr.
 *
 * Why this file may not leak, stated because the cost is somebody else's PR:
 * the golden project is workers: 1, fullyParallel: false
 * (frontend/playwright.config.ts:282-288), so every golden spec in the repo
 * runs sequentially in ONE stack, and collection is alphabetical —
 * household.spec.ts runs BEFORE persons.spec.ts and zones.spec.ts. My own
 * zones.spec.ts test 'F-258 …' asserts `expect(membersBefore.body).toHaveLength(0)`
 * (zones.spec.ts:560/:569 at head 913e23cea; anchors: grep "the stack seeds no") and
 * notify-access/access.spec.ts creates its own rows under a per-process MARK
 * (:81) and deletes them (:324/:329, :497). A row leaked by THIS file does not
 * just fail my later legs — it indicts the zones F-258 row and possibly access.
 * Hence: every fixture id is captured from its POST before any assert on that
 * response (persons.spec.ts learned this the hard way), every finally deletes
 * with .catch(() => null), and each test ENDS with the API re-read that proves
 * both tables are back to empty.
 *
 * What this file deliberately does NOT claim:
 *  - The link-to-known-person affordance (the Linked Known Person select at HouseholdPage.tsx
 *    :383-414, PATCH /api/household/members/{id}/link-person at routes/household.py
 *    :402-452, and the data-testid="linked-known-person" card line at HouseholdPage.tsx:1009).
 *    F-270's API-calls cell lists GET /api/known-persons and this spec DOES
 *    depend on that route existing, but driving the link needs a known person
 *    row, and the persons gallery's card leg is a measured red
 *    (persons.spec.ts Break A) — writing a green link leg over a surface whose
 *    sibling is red would be choosing the leg that cannot fail. F-275's row is
 *    the place that break gets cleared; the link leg goes with it, not here.
 *  - The loading state (data-testid="loading-state", HouseholdPage.tsx:880-886) and the error
 *    state (:893-909). Both are transient branches on a mounted stack; pinning
 *    them means racing a fetch, which is how a suite grows flaky at 1 worker.
 *  - Toast copy ("Member created successfully" etc.). The suite DOES assert
 *    sonner toasts where they are the timed subject (shell/rate-limit.spec.ts
 *    :309-315); here they auto-dismiss and every mutation already has a
 *    stronger, non-timed witness: the invalidate-driven card and the API
 *    re-read.
 *  - The household-ORG tables (/api/v1/households, useHouseholdApi.ts:352+) —
 *    a different surface, not F-270/F-271's promise.
 *  - The member Edit form's Linked-person select interplay (mode === 'edit'
 *    renders it, HouseholdPage.tsx:383) — see the link exclusion above; the edit leg
 *    changes notes only, which the card prints at HouseholdPage.tsx:1018.
 */
import { expect, test } from '../guard';
import type { Page, Response } from '@playwright/test';
import {
  adminSession,
  apiPath,
  assertGuardSurvives,
  authedFetch,
  householdCard,
  login,
  readHarness,
  type AuthedFetch,
  type Harness,
} from './harness';

const harness = readHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

/** Fixture names that cannot collide with the other DO-3 specs' constants
 *  ('Golden DO-3 Member'/'Golden DO-3 Vehicle' in zones.spec.ts:170-171,
 *  'Golden DO-3 Person' in persons.spec.ts:111). Distinctness is belt-and-
 *  braces: each spec deletes what it creates, but a leak under a SHARED name
 *  would let one spec's residue satisfy another's assert, which is the failure
 *  mode where everything passes and nothing is proven. */
const MEMBER = 'Golden DO-3 Resident';
const VEHICLE = 'Golden DO-3 Sedan';
/** U+200B, the exact character HouseholdPage.tsx:1035 prints after the vehicle
 *  count. Written as an escape, not as the character itself: an invisible byte
 *  in a source file is unauditable — a reader (or a grep) cannot tell whether
 *  it is there, which is the property that makes the shipped copy worth
 *  naming. Named so the asserts below read as what they are: shipped copy. */
const ZWSP = '\u200b';

async function signIn(page: Page, h: Harness): Promise<AuthedFetch> {
  const session = await adminSession(h);
  await login(page, h, session);
  return authedFetch(h, session);
}

/** Exact-path + exact-method response matcher — never endsWith(): members and
 *  vehicles share the /api/household prefix, and a predicate that can never
 *  fire silently skips the code in the finally it guards (harness.ts:198-212,
 *  DO-2's measured skip). */
function waitFor(page: Page, path: string, method: string): Promise<Response> {
  return page.waitForResponse((r) => apiPath(r.url()) === path && r.request().method() === method);
}

/** One fixture row through the shipped route, id captured BEFORE any assert.
 *  Returns the id or null — a POST that 4xx'd must not leave the caller with a
 *  null to interpolate into a DELETE /api/household/members/null. */
async function createMember(api: AuthedFetch, name: string): Promise<number | null> {
  const res = await api.send('/api/household/members', 'POST', {
    name,
    role: 'resident',
    trusted_level: 'full',
  });
  return typeof res.body?.id === 'number' ? res.body.id : null;
}

test.describe('DO-3 household golden path', () => {
  test('F-270 members: empty mount, add via the form, edit via the form, delete behind the confirm dialog', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    // --- API leg first. The fake-AI stack seeds ONLY cameras (harness.ts:15-24),
    //     so the passive mount is the EMPTY branch, and the route answers a BARE
    //     list — both pinned before any locator exists. ---
    const before = await api.getJson('/api/household/members');
    expect(before.status, 'GET /api/household/members answers 200').toBe(200);
    expect(
      Array.isArray(before.body),
      `members is a bare list, got ${JSON.stringify(before.body)}`
    ).toBe(true);
    expect(before.body, 'the stack seeds no household members').toHaveLength(0);

    // --- UI leg: the shipped empty copy, verbatim. ---
    await page.goto(`${h.ui}/household`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('household-page')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Household Members', level: 1 })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Members', level: 2 })).toBeVisible();
    await expect(page.getByText('No members yet')).toBeVisible(); // HouseholdPage.tsx:963
    await expect(page.getByText('Add your first household member to get started')).toBeVisible(); // HouseholdPage.tsx:965
    // The badge BEFORE any write: clean text node, testid-scoped (HouseholdPage.tsx:943-947).
    await expect(page.getByTestId('member-count-badge')).toHaveText('0');
    // aria-label route (see header: the visible text carries a U+200B the label
    // overrides). exact:true pins it regardless of what shares the label later.
    const addMember = page.getByRole('button', { name: 'Add Member', exact: true });
    await expect(addMember).toBeVisible();

    let memberId: number | null = null;
    let vehicleId: number | null = null;
    try {
      // --- the ADD form drive, the row's literal promise (name, role, trust
      //     level, notes), through the shipped submit path (HouseholdPage.tsx:318 <form
      //     onSubmit>, Save is the type="submit" button at :449). ---
      await addMember.click();
      await expect(
        page.getByRole('heading', { name: 'Add Member', level: 2, exact: true })
      ).toBeVisible();
      await page.getByLabel('Name').fill(MEMBER);
      // Native <select>s (harness.ts:47-51: Playwright maps one <select> to
      // role combobox; options are invisible, so selectOption by VALUE — the
      // option VALUES are the backend enum strings, HouseholdPage.tsx:53-64 ∩
      // backend/models/household.py:33-53).
      await page.getByLabel('Role').selectOption('family');
      await page.getByLabel('Trust Level').selectOption('partial');
      await page.getByLabel('Notes').fill('golden F-270 fixture');
      const createdResp = waitFor(page, '/api/household/members', 'POST');
      await page.getByRole('button', { name: 'Save', exact: true }).click();
      const post = await createdResp;
      expect(post.status(), 'the form POST /api/household/members answers 201').toBe(201);
      const postBody = await post.json();
      memberId = typeof postBody?.id === 'number' ? postBody.id : null;
      expect(postBody?.name, 'the POST echoes the typed name').toBe(MEMBER);
      expect(postBody?.role, 'the POST carries the chosen role').toBe('family');
      expect(postBody?.trusted_level, 'the POST carries the chosen trust level').toBe('partial');
      expect(postBody?.notes, 'the POST carries the typed notes').toBe('golden F-270 fixture');

      // --- the card the save must paint, WITHOUT a reload: the refetch is the
      //     mutation's invalidate (useHouseholdApi.ts:418-420), so a reload
      //     here would hide a broken invalidation. The dialog must also be gone
      //     (handleSaveMember closes it at HouseholdPage.tsx:774). ---
      await expect(
        page.getByRole('heading', { name: 'Add Member', level: 2, exact: true })
      ).toHaveCount(0);
      const card = householdCard(page, MEMBER);
      await expect(card).toBeVisible();
      // The card's badges print the LABELS, not the enum values
      // (ROLE_LABELS/TRUST_LEVEL_LABELS at HouseholdPage.tsx:984-985) — so this leg pins the
      // value→label mapping the row's "role, trust level" depends on.
      await expect(card.getByText('Family', { exact: true })).toBeVisible();
      await expect(card.getByText('Partial Trust', { exact: true })).toBeVisible();
      await expect(card.getByText('golden F-270 fixture')).toBeVisible(); // :1018
      await expect(page.getByTestId('member-count-badge')).toHaveText('1');
      // The empty copy must be GONE — otherwise "both branches rendered" would
      // satisfy every assert above (the persons.spec.ts:228-230 pattern).
      await expect(page.getByText('No members yet')).toHaveCount(0);

      // --- the EDIT form drive: same card's Edit, change notes, and read the
      //     changed value where the card prints it. This exercises the shipped
      //     PATCH (handleSaveMember routes to updateMemberMutation because the
      //     payload carries an id, HouseholdPage.tsx:767-768) rather than a PATCH I typed. ---
      await card.getByRole('button', { name: 'Edit', exact: true }).click();
      await expect(
        page.getByRole('heading', { name: 'Edit Member', level: 2, exact: true })
      ).toBeVisible();
      await page.getByLabel('Notes').fill('edited by golden F-270');
      const patched = waitFor(page, `/api/household/members/${memberId}`, 'PATCH');
      await page.getByRole('button', { name: 'Save', exact: true }).click();
      const patch = await patched;
      expect(patch.status(), 'the form PATCH answers 200').toBe(200);
      expect((await patch.json())?.notes, 'the PATCH body carries the edited notes').toBe(
        'edited by golden F-270'
      );
      await expect(card.getByText('edited by golden F-270')).toBeVisible();
      // The name is unchanged by an edit that never touched it — exclude_unset
      // semantics (household.py:173-175), witnessed through the UI.
      await expect(card.getByText(MEMBER, { exact: true })).toBeVisible();

      // --- "deletes one after confirming": the DELETE button must NOT delete —
      //     it opens the dialog (handleDeleteMember HouseholdPage.tsx:798-800), and the API
      //     re-read below the click proves the row SURVIVES the first click.
      //     That ordering leg is the difference between testing a confirmation
      //     and testing a delete twice. ---
      await card.getByRole('button', { name: 'Delete', exact: true }).click();
      const dialog = page.getByRole('dialog');
      await expect(
        dialog.getByRole('heading', { name: 'Confirm Delete', level: 2, exact: true })
      ).toBeVisible();
      // The dialog names MY row (member name into deleteTarget at HouseholdPage.tsx:799 → :209).
      await expect(dialog.getByText(MEMBER, { exact: true })).toBeVisible();
      const survived = await api.getJson('/api/household/members');
      expect(survived.body, 'clicking Delete alone deletes nothing').toHaveLength(1);

      const confirmed = waitFor(page, `/api/household/members/${memberId}`, 'DELETE');
      await dialog.getByRole('button', { name: 'Confirm', exact: true }).click();
      const del = await confirmed;
      // 204 EXACTLY, not "2xx": delete_member declares status_code=204
      // (household.py:183) and returns no body, so 200 would mean the route
      // changed shape, and a 2xx-range assert would let that pass right up to
      // the re-read below. The loose 204-or-404 form belongs to the RESTORE
      // legs in the finally (harness.ts:167-171), not to a delete the test
      // itself triggered and witnessed.
      expect(del.status(), 'the confirmed DELETE answers 204').toBe(204);

      // --- back to the empty branch, live (delete's invalidate, useHouseholdApi.ts:447-449). ---
      await expect(page.getByText('No members yet')).toBeVisible();
      await expect(page.getByTestId('member-count-badge')).toHaveText('0');
      await expect(householdCard(page, MEMBER)).toHaveCount(0);
    } finally {
      // Both ids guarded — a throw before either capture must not put `/null`
      // on the wire, and a finally cannot rescue the in-flight throw anyway
      // (a finally without its own return propagates it; persons.spec.ts:322-
      // 331 records exactly that measurement). The re-read below the try is
      // only reachable on a clean path, so the finally is what the NEXT spec
      // (zones F-258 asserts toHaveLength(0)) is protected by.
      if (vehicleId !== null)
        await api.send(`/api/household/vehicles/${vehicleId}`, 'DELETE').catch(() => null);
      if (memberId !== null)
        await api.send(`/api/household/members/${memberId}`, 'DELETE').catch(() => null);
    }

    // --- the delete is proven through the API, not assumed from the 2xx ---
    const gone = await api.getJson('/api/household/members');
    expect(gone.body, 'the fixture member is gone after the restore').toHaveLength(0);

    await assertGuardSurvives(page, h);
  });

  test('F-271 vehicles: empty mount, add with plate/type/color/owner, edit the color, delete behind the confirm dialog', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    const membersBefore = await api.getJson('/api/household/members');
    expect(membersBefore.status, 'GET members answers 200').toBe(200);
    expect(membersBefore.body, 'this test starts on an empty members table').toHaveLength(0);
    const vehiclesBefore = await api.getJson('/api/household/vehicles');
    expect(vehiclesBefore.status, 'GET /api/household/vehicles answers 200').toBe(200);
    expect(
      Array.isArray(vehiclesBefore.body),
      `vehicles is a bare list, got ${JSON.stringify(vehiclesBefore.body)}`
    ).toBe(true);
    expect(vehiclesBefore.body, 'the stack seeds no vehicles').toHaveLength(0);

    // The owner-integrity contract the Owner select rests on, pinned at the
    // route that enforces it: an unknown owner_id is a 404, never a silent
    // null (household.py:259-266).
    const bogus = await api.send('/api/household/vehicles', 'POST', {
      description: `${VEHICLE} ghost owner`,
      vehicle_type: 'car',
      owner_id: 999_999_999,
    });
    expect(bogus.status, 'an unknown owner_id is 404, not a saved null').toBe(404);
    const ghostCheck = await api.getJson('/api/household/vehicles');
    expect(ghostCheck.body, 'the rejected POST created no row').toHaveLength(0);

    // The vehicle form's Owner select lists MEMBERS, so the fixture for that
    // leg is a member — created through the API here because this row's promise
    // is about the vehicle form, and deleted in this test's finally.
    let ownerId: number | null = null;
    let vehicleId: number | null = null;
    try {
      ownerId = await createMember(api, `${VEHICLE} Owner`);
      expect(ownerId, 'the owner fixture member was created').not.toBeNull();

      await page.goto(`${h.ui}/household`, { waitUntil: 'domcontentloaded' });
      await expect(page.getByRole('heading', { name: 'Vehicles', level: 2 })).toBeVisible();
      await expect(page.getByText('No vehicles yet')).toBeVisible(); // HouseholdPage.tsx:1051
      await expect(page.getByText('Add your first vehicle to get started')).toBeVisible(); // HouseholdPage.tsx:1052
      // The vehicle count badge, shipped form: the digits PLUS the U+200B the
      // page prints (header: no testid here, unlike the member badge).
      await expect(
        // The span immediately after the heading (HouseholdPage.tsx:1031-1036). NOT
        // `section… span.rounded-full`: the local Badge renders
        // <span className="… rounded-full …"> (:126-133), so a card's Trusted
        // badge joins that match and the locator becomes a strict-mode
        // violation on any day a card exists in the section.
        page.locator('h2#vehicles-heading + span')
      ).toHaveText(`0${ZWSP}`);

      await page.getByRole('button', { name: 'Add Vehicle', exact: true }).click();
      await expect(
        page.getByRole('heading', { name: 'Add Vehicle', level: 2, exact: true })
      ).toBeVisible();
      await page.getByLabel('Description').fill(VEHICLE);
      await page.getByLabel('Vehicle Type').selectOption('truck');
      await page.getByLabel('License Plate').fill('GLD031985');
      await page.getByLabel('Color').fill('Silver');
      // The select's option set is the owner linkage in the DOM: the sentinel
      // plus exactly the one fixture member (HouseholdPage.tsx:621-626). count() does not
      // require visibility, which native <option>s would fail.
      const ownerSelect = page.getByLabel('Owner');
      await expect(ownerSelect.locator('option')).toHaveCount(2);
      await ownerSelect.selectOption(String(ownerId));
      // Trusted ships CHECKED (RegisteredVehicleCreate trusted default True,
      // schemas/household.py:172-173; form init HouseholdPage.tsx:489) — a native checkbox, so
      // toBeChecked is the honest assert (harness.ts:52-54: no Tremor Switch
      // here, DO-2's aria-checked trap does not apply).
      await expect(page.getByLabel('Trusted Vehicle')).toBeChecked();

      const createdResp = waitFor(page, '/api/household/vehicles', 'POST');
      await page.getByRole('button', { name: 'Save', exact: true }).click();
      const post = await createdResp;
      expect(post.status(), 'the form POST /api/household/vehicles answers 201').toBe(201);
      const postBody = await post.json();
      vehicleId = typeof postBody?.id === 'number' ? postBody.id : null;
      expect(postBody?.description, 'the POST echoes the description').toBe(VEHICLE);
      expect(postBody?.vehicle_type, 'the POST carries the chosen type').toBe('truck');
      expect(postBody?.license_plate, 'the POST carries the plate').toBe('GLD031985');
      expect(postBody?.color, 'the POST carries the color').toBe('Silver');
      expect(postBody?.owner_id, 'the POST persisted the chosen owner').toBe(ownerId);
      expect(postBody?.trusted, 'the POST carried the trusted checkbox').toBe(true);

      // The card: description heading, plate text, the Trusted badge
      // (conditional on vehicle.trusted, HouseholdPage.tsx:1068 — a local <span> Badge, :119-
      // 134), and the color line (:1088). No owner text exists on this card
      // (header), which is why owner_id is asserted through the API above.
      const card = householdCard(page, VEHICLE);
      await expect(card).toBeVisible();
      await expect(card.getByText('GLD031985', { exact: true })).toBeVisible();
      await expect(card.getByText('Trusted', { exact: true })).toBeVisible();
      await expect(card.getByText('Color: Silver')).toBeVisible();
      await expect(page.getByText('No vehicles yet')).toHaveCount(0);

      // --- the EDIT form drive: color only, read back where the card prints
      //     it. Same shipped PATCH path (handleSaveVehicle HouseholdPage.tsx:828-830). ---
      await card.getByRole('button', { name: 'Edit', exact: true }).click();
      await expect(
        page.getByRole('heading', { name: 'Edit Vehicle', level: 2, exact: true })
      ).toBeVisible();
      await page.getByLabel('Color').fill('Midnight Silver');
      const patched = waitFor(page, `/api/household/vehicles/${vehicleId}`, 'PATCH');
      await page.getByRole('button', { name: 'Save', exact: true }).click();
      const patch = await patched;
      expect(patch.status(), 'the form PATCH answers 200').toBe(200);
      await expect(card.getByText('Color: Midnight Silver')).toBeVisible();

      // --- delete behind the confirm, and the survivor ordering leg again. ---
      await card.getByRole('button', { name: 'Delete', exact: true }).click();
      const dialog = page.getByRole('dialog');
      await expect(
        dialog.getByRole('heading', { name: 'Confirm Delete', level: 2, exact: true })
      ).toBeVisible();
      await expect(dialog.getByText(VEHICLE, { exact: true })).toBeVisible();
      const survived = await api.getJson('/api/household/vehicles');
      expect(survived.body, 'clicking Delete alone deletes nothing').toHaveLength(1);

      const confirmed = waitFor(page, `/api/household/vehicles/${vehicleId}`, 'DELETE');
      await dialog.getByRole('button', { name: 'Confirm', exact: true }).click();
      const del = await confirmed;
      expect(del.status(), 'the confirmed DELETE is 2xx').toBeLessThan(300);

      await expect(page.getByText('No vehicles yet')).toBeVisible();
      await expect(page.locator('h2#vehicles-heading + span')).toHaveText(`0${ZWSP}`);
      await expect(householdCard(page, VEHICLE)).toHaveCount(0);
    } finally {
      if (vehicleId !== null)
        await api.send(`/api/household/vehicles/${vehicleId}`, 'DELETE').catch(() => null);
      if (ownerId !== null)
        await api.send(`/api/household/members/${ownerId}`, 'DELETE').catch(() => null);
    }

    // Both tables back to empty — this is the guarantee zones.spec.ts's F-258
    // test (:399/:408) and access.spec.ts's before-legs depend on.
    const membersGone = await api.getJson('/api/household/members');
    expect(membersGone.body, 'the owner fixture is gone').toHaveLength(0);
    const vehiclesGone = await api.getJson('/api/household/vehicles');
    expect(vehiclesGone.body, 'the fixture vehicle is gone').toHaveLength(0);

    await assertGuardSurvives(page, h);
  });
});

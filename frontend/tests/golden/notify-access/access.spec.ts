/**
 * F2.3 DO-2 golden path, access-control half (inventory F-240 to F-243, all on
 * /settings/access; claim #6996). These four rows are the only ones in the
 * batch that write server state — households, household_members,
 * registered_vehicles, zone_household_configs — so restore discipline is the
 * file: every mutation is undone in a finally block in the same test that made
 * it, because the golden project runs workers: 1 (playwright.config.ts:288)
 * against one shared stack, and a leaked row is the next spec's false pass.
 *
 * Laws this file encodes (all read at this head, cited by line):
 * - Route prefixes are SPLIT across one page: F-240 is /api/v1/households
 *   (hierarchy.py:70) while the member/vehicle legs have NO version segment
 *   (/api/household/..., household.py:53) and the zone legs are /api/cameras +
 *   /api/zones (zones.py:18, zone_household.py:31). All four are live — the
 *   hooks call them exactly that way (useHouseholdApi.ts:353/251/302,
 *   useZoneHouseholdConfig.ts:159) — so the inventory's asymmetry is shipped
 *   contract, not a typo to fix.
 * - The household row the page shows is the UI's `?? 'My Household'` fallback
 *   (HouseholdSettings.tsx:527), NOT a seeded record: feature_check boots
 *   up → register_admin → seed_cameras (feature_check.py:1803-1805) and seeds
 *   no household (scripts/seed-events.py:3370 does, but no compose file runs
 *   it), so the F-240 row's real contract is a PAIR — with no row the save is
 *   INERT (handleSaveHouseholdName returns at :277 before its try, so Edit and
 *   typing work while Save does nothing: no PATCH, no toast, no exit from edit
 *   mode), and with a row the same button renames it. This spec asserts both
 *   halves and DELETES its row after, which is load-bearing rather than tidy:
 *   list_households orders by NAME (hierarchy.py:21), so a leftover row would
 *   reorder items?.[0] for every sibling spec that reads it.
 * - Zone Access offers ONLY the first camera's zones, and "first" is the API's
 *   order, not a name: list_cameras has no ORDER BY (cameras.py:222 is a plain
 *   select(Camera)), so `cameras?.[0]?.id` (AccessControlSettings.tsx:124) is
 *   read here from GET /api/cameras — the same array the UI reads — rather than
 *   guessed. The negative leg then proves the limitation the inventory names: a
 *   zone seeded on a SECOND camera cannot appear in the picker.
 * - Same label, two roles, one zone. ZoneAccessSettings renders each member
 *   name twice — once as the owner chip (:436), once as the allowed-member chip
 *   (:463) — and both are plain buttons with no testid. A name-keyed locator
 *   binds the OWNER (earlier in the document), so the allowed-panel assert
 *   resolves the panel by its own heading AND the chip, then takes the deepest
 *   match: ancestors precede descendants in document order, so .last() is the
 *   panel itself, the smallest div that can hold both.
 * - No Tremor Select is automated. The repo's only selectOptions precedent
 *   (ScheduledReportForm.test.tsx:118) drives a NATIVE <select>
 *   (ScheduledReportForm.tsx:395), not Tremor's listbox, and this disk has no
 *   node_modules to read the rendered role from. Role/trust therefore travel by
 *   API and are asserted through their badges — RoleBadge/TrustBadge print
 *   Resident/Visitor and Full Trust/Partial (HouseholdSettings.tsx:170-196) —
 *   and the vehicle 'Trusted' badge is conditional on vehicle.trusted (:692).
 * - Auth needs no header. buildHeaders sends Content-Type only
 *   (useHouseholdApi.ts:215-220, no Authorization leg), and the gate that could
 *   reject that runs ONLY under EXPOSE_LAN and reads the session cookie
 *   (auth.py:613, :12). harness.login puts that cookie on the UI origin, so the
 *   browser authenticates as a logged-in user does: no route interception, no
 *   key, and the guard stays armed (assertGuardSurvives at the end).
 * - Two disabled-states are used as pins, because they are the cheapest proof
 *   a branch mounted: household save is disabled while the input is blank
 *   (:506), and zone Save Changes is disabled until hasUnsavedChanges (:553) —
 *   the second half is also how this file proves Clear actually cleared.
 */
import type { Page } from '@playwright/test';

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

/** Unique per run so a row left behind by an interrupted run can never satisfy
 *  an assert. */
const MARK = `GoldenAcc${Date.now().toString(36)}${process.pid}`;
const PLATE = `GA${Date.now().toString(36).toUpperCase().slice(-6)}`; // license_plate max_length 20 (schemas/household.py:156)
const COORDS = [
  [0.05, 0.05],
  [0.55, 0.05],
  [0.55, 0.65],
  [0.05, 0.65],
]; // 4 points clears min_length 3 (schemas/zone.py:180)

async function signIn(page: Page, h: Harness) {
  await login(page, h, await adminSession(h));
}

test.describe('DO-2 access control golden path (F-240 to F-243)', () => {
  test('F-240 household name: fallback renders, the UI rename lands in the table, the fallback returns', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = authedFetch(h, await adminSession(h));

    // --- API leg FIRST, so the fallback claim is about state, not a blank
    // screen: no household exists until this test makes one. The boot order is
    // up → register_admin → seed_cameras (feature_check.py:1803-1805) and
    // nothing seeds a household (seed_households lives in the manual
    // scripts/seed-events.py, which no compose file invokes), so this asserts
    // the assumption rather than assuming it: if a future boot seeds the table,
    // this fails LOUD and the edit below stops binding a foreign row. ---
    const before = await api.getJson('/api/v1/households');
    expect(before.status, 'GET /api/v1/households answers 200').toBe(200);
    const seeded = (before.body?.items ?? []) as { id: number; name: string }[];
    expect(
      seeded.length,
      'this test assumes it owns the households table (it restores by deleting ' +
        'its own row, and `items?.[0]` must therefore be its own record)'
    ).toBe(0);

    // Declared outside the try so the finally can reach it: the row is created
    // halfway through the test, but the restore has to run either way.
    let householdId: number | null = null;

    try {
      await signIn(page, h);
      await page.goto(`${h.ui}/settings/access`, { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('access-control-settings')).toBeVisible();

      const nameCard = page.getByTestId('household-name-section');
      await expect(nameCard).toBeVisible();
      await expect(nameCard).toContainText('My Household'); // the :527 fallback, with no row to name

      // --- the inert-save half of the row's contract. With items?.[0]
      // undefined, handleSaveHouseholdName returns at :277 BEFORE its try
      // block: the Edit button exists (it is gated on loading, not on a row),
      // the input takes text, and Save silently does nothing — no PATCH, no
      // toast, and edit mode stays open because setIsEditingHouseholdName(false)
      // is unreachable. Pinned without touching the network. ---
      await page.getByTestId('household-name-edit').click();
      const input = page.getByTestId('household-name-input');
      await expect(input).toHaveValue(''); // seeded from household?.name ?? '' (:272)
      // Disabled-while-blank (:506) — the edit branch mounted and its save is
      // gated on the value, not on the click landing.
      await expect(page.getByTestId('household-name-save')).toBeDisabled();
      await input.fill('Inert On Purpose');
      await expect(page.getByTestId('household-name-save')).toBeEnabled();
      await page.getByTestId('household-name-save').click();
      await expect(input).toBeVisible(); // still editing: the early return never left edit mode
      // The negation is asserted AFTER leaving edit mode, because while the
      // edit branch is mounted the Title is not rendered at all — a
      // not.toContainText taken there would pass even if the PATCH had landed,
      // which makes it no evidence of anything. Cancel first (the unit test's
      // own move, HouseholdSettings.test.tsx:220), then judge the Title.
      await page.getByTestId('household-name-cancel').click();
      await expect(input).toHaveCount(0);
      await expect(nameCard).toContainText('My Household');
      await expect(nameCard).not.toContainText('Inert On Purpose');

      // --- a row now exists, so the same UI becomes the rename path the row
      // documents. POST (not the UI): the page offers no create affordance. ---
      const created = await api.send('/api/v1/households', 'POST', { name: `${MARK} origin` });
      expect(created.status, 'POST /api/v1/households answers 201').toBe(201);
      householdId = Number(created.body?.id);
      expect(Number.isFinite(householdId), 'the created household carries an id').toBe(true);

      await page.reload({ waitUntil: 'domcontentloaded' });
      await expect(nameCard).toContainText(`${MARK} origin`); // items?.[0] is now this row (asserted sole row above)

      await page.getByTestId('household-name-edit').click();
      await expect(input).toHaveValue(`${MARK} origin`); // prefilled from the row (:272)
      await input.fill(`${MARK} renamed`);
      await page.getByTestId('household-name-save').click();

      await expect
        .poll(
          async () => {
            const check = await api.getJson('/api/v1/households');
            const row = (check.body?.items ?? []).find(
              (item: { id: number }) => item.id === householdId
            );
            return row?.name ?? null;
          },
          { message: 'PATCH /api/v1/households/{id} persisted the typed value' }
        )
        .toBe(`${MARK} renamed`);

      // The mutation invalidates the households query (useHouseholdApi.ts:527),
      // so the SAME mount re-renders the Title with no navigation.
      await expect(nameCard).toContainText(`${MARK} renamed`);
      await expect(input).toHaveCount(0); // and leaves edit mode this time
    } finally {
      // Restore = delete, which puts the page back on its shipped fallback
      // (hierarchy.py:264 answers 204). Guarded because the row is created
      // mid-test: if the inert-save half failed, there is nothing to delete.
      if (householdId !== null) {
        const removed = await api.send(`/api/v1/households/${householdId}`, 'DELETE');
        expect([204, 404]).toContain(removed.status);
      }
    }
  });

  test('F-241/F-242 members and vehicles: both panels round-trip add/edit/delete, badges follow the table', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = authedFetch(h, await adminSession(h));

    // --- API legs first: an absent row must never pass as "deleted". ---
    const membersBefore = await api.getJson('/api/household/members');
    expect(membersBefore.status).toBe(200);
    const vehiclesBefore = await api.getJson('/api/household/vehicles');
    expect(vehiclesBefore.status).toBe(200);
    const memberName = `${MARK} member`;
    const description = `${MARK} car`;

    let memberId: number | null = null;
    let vehicleId: number | null = null;

    try {
      await signIn(page, h);
      await page.goto(`${h.ui}/settings/access`, { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('members-section')).toBeVisible();
      await expect(page.getByTestId('vehicles-section')).toBeVisible();

      // --- member add (UI) ---
      await page.getByTestId('members-section').getByTestId('add-member-btn').click();
      await expect(page.getByTestId('member-modal')).toBeVisible();
      await page.getByTestId('member-name-input').fill(memberName);
      await page.getByTestId('member-modal-save').click();
      await expect(page.getByTestId('member-modal')).toHaveCount(0); // handleCloseMemberModal (:323)

      const afterCreate = await api.getJson('/api/household/members');
      const createdMember = (afterCreate.body ?? []).find(
        (m: { name: string }) => m.name === memberName
      );
      expect(createdMember, 'the new member is in GET /api/household/members').toBeTruthy();
      memberId = Number(createdMember.id);

      // The row testid is `member-${id}` (:585) — row-scoped, so a badge match
      // cannot be credited to another member's row.
      const memberRow = page.getByTestId(`member-${memberId}`);
      await expect(memberRow).toBeVisible(); // no reload: invalidateQueries (:419)
      await expect(memberRow).toContainText(memberName);
      // Badges read the CREATED defaults: role/trust are required in the schema
      // (household.py:41/45) and the form seeds resident/full (:313-318).
      await expect(memberRow).toContainText('Resident');
      await expect(memberRow).toContainText('Full Trust');

      // --- member edit (UI) → table ---
      await page.getByTestId(`edit-member-${memberId}`).click();
      await expect(page.getByTestId('member-modal')).toBeVisible();
      await expect(page.getByTestId('member-name-input')).toHaveValue(memberName); // prefilled from the row (:304)
      await page.getByTestId('member-name-input').fill(`${memberName}2`);
      await page.getByTestId('member-modal-save').click();
      await expect
        .poll(
          async () => {
            const check = await api.getJson('/api/household/members');
            const row = (check.body ?? []).find((m: { id: number }) => m.id === memberId);
            return row?.name ?? null;
          },
          { message: 'PATCH /api/household/members/{id} persisted the edit' }
        )
        .toBe(`${memberName}2`);
      await expect(memberRow).toContainText(`${memberName}2`);

      // --- member delete (UI + its confirm modal) ---
      await page.getByTestId(`delete-member-${memberId}`).click();
      await expect(page.getByTestId('delete-member-modal')).toBeVisible();
      await page.getByTestId('confirm-delete-member').click();
      await expect
        .poll(
          async () => {
            const check = await api.getJson('/api/household/members');
            return (check.body ?? []).filter((m: { id: number }) => m.id === memberId).length;
          },
          { message: 'DELETE /api/household/members/{id} removed the row' }
        )
        .toBe(0);
      await expect(page.getByTestId(`member-${memberId}`)).toHaveCount(0);
      memberId = null; // removed through the UI; nothing left to restore

      // --- vehicle add, with trusted cleared ---
      await page.getByTestId('vehicles-section').getByTestId('add-vehicle-btn').click();
      await expect(page.getByTestId('vehicle-modal')).toBeVisible();
      await page.getByTestId('vehicle-description-input').fill(description);
      await page.getByTestId('vehicle-plate-input').fill(PLATE);
      // The form seeds trusted: true (:406), so clearing it is what makes the
      // conditional badge at :692 say something.
      await page.getByTestId('vehicle-trusted-checkbox').uncheck();
      await page.getByTestId('vehicle-modal-save').click();
      await expect(page.getByTestId('vehicle-modal')).toHaveCount(0);

      const afterVehicle = await api.getJson('/api/household/vehicles');
      const createdVehicle = (afterVehicle.body ?? []).find(
        (v: { description: string }) => v.description === description
      );
      expect(createdVehicle, 'the new vehicle is in GET /api/household/vehicles').toBeTruthy();
      vehicleId = Number(createdVehicle.id);
      expect(createdVehicle.trusted, 'the cleared checkbox reached the table').toBe(false);

      const vehicleRow = page.getByTestId(`vehicle-${vehicleId}`);
      await expect(vehicleRow).toBeVisible();
      await expect(vehicleRow).toContainText(description);
      await expect(vehicleRow).toContainText(PLATE); // plate badge (:688)
      await expect(vehicleRow.getByText('Trusted', { exact: true })).toHaveCount(0);

      // --- API-side leg: a member the UI never made, at a role/trust pair the
      // form cannot reach by its own defaults. A second member also makes the
      // vehicle modal's Owner select exist (:983) without this spec having to
      // drive a listbox it cannot verify. ---
      const second = await api.send('/api/household/members', 'POST', {
        name: `${MARK} visitor`,
        role: 'frequent_visitor',
        trusted_level: 'partial',
      });
      expect(second.status, 'POST /api/household/members answers 201').toBe(201);
      memberId = Number(second.body?.id);
      await page.reload({ waitUntil: 'domcontentloaded' });
      const visitorRow = page.getByTestId(`member-${memberId}`);
      await expect(visitorRow).toContainText(`${MARK} visitor`);
      await expect(visitorRow).toContainText('Visitor'); // RoleBadge frequent_visitor (:190)
      await expect(visitorRow).toContainText('Partial'); // TrustBadge partial label (:172)
    } finally {
      if (memberId !== null) {
        expect([204, 404]).toContain(
          (await api.send(`/api/household/members/${memberId}`, 'DELETE')).status
        );
      }
      if (vehicleId !== null) {
        expect([204, 404]).toContain(
          (await api.send(`/api/household/vehicles/${vehicleId}`, 'DELETE')).status
        );
      }
    }
  });

  test('F-243 zone access: first camera only, chip + schedule round-trip the PUT, Clear de-arms Save', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = authedFetch(h, await adminSession(h));

    // --- Which camera does the UI call first? Ask the endpoint the hook reads;
    // there is no ORDER BY to appeal to. ---
    const cameras = await api.getJson('/api/cameras');
    expect(cameras.status).toBe(200);
    const cameraIds = (cameras.body?.items ?? []).map((c: { id: string | number }) => String(c.id));
    expect(cameraIds.length, 'feature_check seeds the scenario cameras').toBeGreaterThanOrEqual(2);
    const [firstCameraId, secondCameraId] = cameraIds;

    const zoneName = `${MARK} zone`;
    const decoyZoneName = `${MARK} decoy`;
    const zone = await api.send(`/api/cameras/${firstCameraId}/zones`, 'POST', {
      name: zoneName,
      coordinates: COORDS,
    });
    expect(zone.status, 'POST /api/cameras/{id}/zones answers 201').toBe(201);
    const zoneId = String(zone.body?.id);
    const decoy = await api.send(`/api/cameras/${secondCameraId}/zones`, 'POST', {
      name: decoyZoneName,
      coordinates: COORDS,
    });
    expect(decoy.status, 'the second camera accepts a zone too').toBe(201);
    const decoyZoneId = String(decoy.body?.id);

    const member = await api.send('/api/household/members', 'POST', {
      name: `${MARK} allowed`,
      role: 'resident',
      trusted_level: 'full',
    });
    expect(member.status).toBe(201);
    const memberId = Number(member.body?.id);

    try {
      await signIn(page, h);
      await page.goto(`${h.ui}/settings/access`, { waitUntil: 'domcontentloaded' });
      await page.getByRole('tab', { name: 'Zone Access' }).click();

      const panel = page.getByTestId('zone-access-settings');
      await expect(panel).toBeVisible();

      // --- the first-camera constraint, both directions ---
      await page.getByTestId('zone-selector').click();
      const zoneOption = page.getByRole('button', { name: zoneName, exact: true });
      await expect(zoneOption).toBeVisible();
      // Proves AccessControlSettings.tsx:124 really stops at cameras?.[0]:
      // this zone EXISTS (the API created it, asserted below) and is unreachable.
      await expect(page.getByText(decoyZoneName, { exact: true })).toHaveCount(0);
      await zoneOption.click();
      await expect(page.getByTestId('zone-selector')).toContainText(zoneName);

      await expect(panel.getByText('Zone Owner')).toBeVisible();
      await expect(panel.getByText('Allowed Members')).toBeVisible();
      await expect(panel.getByText('Allowed Vehicles')).toBeVisible();
      await expect(panel.getByText('Access Schedules')).toBeVisible();

      // --- allowed-member toggle, past the identically-labelled owner chip.
      // Resolve the panel as the DEEPEST div holding both the heading and the
      // chip: no smaller div can, and ancestors sort before descendants. ---
      const allowedPanel = panel
        .locator('div')
        .filter({ has: page.getByText('Allowed Members', { exact: true }) })
        .filter({ has: page.getByRole('button', { name: `${MARK} allowed`, exact: true }) })
        .last();
      const memberChip = allowedPanel.getByRole('button', { name: `${MARK} allowed`, exact: true });
      await expect(memberChip).toHaveCount(1);
      await memberChip.click();

      const saveBtn = page.getByTestId('save-zone-config-btn');
      await expect(saveBtn).toBeEnabled(); // hasUnsavedChanges flipped (:553)
      await saveBtn.click();

      await expect
        .poll(
          async () => {
            const check = await api.getJson(`/api/zones/${zoneId}/household`);
            return ((check.body?.allowed_member_ids ?? []) as number[]).includes(memberId);
          },
          { message: 'PUT /api/zones/{id}/household stored the member' }
        )
        .toBe(true);

      // --- access schedule (F-243's "edits access schedules") ---
      const editor = page.getByTestId('access-schedule-editor');
      const addSchedule = editor.getByTestId('add-schedule-btn');
      // Disabled while members.length === 0 (AccessScheduleEditor.tsx:546), so
      // this being clickable is itself a pin on the household → zone feed.
      await expect(addSchedule).toBeEnabled();
      await addSchedule.click();
      const form = page.getByTestId('schedule-form');
      await expect(form).toBeVisible();
      // The form's own member chip sits inside 'schedule-form', which cannot
      // collide with the zone-level chip above.
      await form.getByRole('button', { name: `${MARK} allowed`, exact: true }).click();
      await form.locator('#start-time').fill('09:00');
      await form.locator('#end-time').fill('17:00'); // :264-266 defaults, re-stated so the cron string is not left to chance
      await form.getByRole('button', { name: 'Save Schedule' }).click();

      // The schedule lives in LOCAL state until the next save — the row alone
      // is not proof the PUT carried it, so Save Changes gets clicked again.
      await expect(saveBtn).toBeEnabled();
      await saveBtn.click();

      // generateCronExpression (:88-92): leading "0 " + hour range + the
      // default weekday set 1,2,3,4,5 (Number-sorted).
      const expectedCron = '0 9-17 * * 1,2,3,4,5';
      await expect
        .poll(
          async () => {
            const check = await api.getJson(`/api/zones/${zoneId}/household`);
            const schedules = (check.body?.access_schedules ?? []) as {
              cron_expression: string;
              member_ids: number[];
            }[];
            const withSchedule = schedules.some(
              (s) => s.cron_expression === expectedCron && s.member_ids.includes(memberId)
            );
            // The same PUT must not drop the chip it did not touch.
            const stillAllowed = ((check.body?.allowed_member_ids ?? []) as number[]).includes(
              memberId
            );
            return withSchedule && stillAllowed;
          },
          { message: 'the second PUT carried the schedule AND kept the allowed member' }
        )
        .toBe(true);

      // --- Clear All Settings: modal → DELETE → the save button de-arms ---
      await page.getByRole('button', { name: 'Clear All Settings' }).click();
      await expect(page.getByTestId('delete-config-modal')).toBeVisible();
      await page.getByTestId('confirm-delete-config').click();

      await expect
        .poll(
          async () => {
            const check = await api.getJson(`/api/zones/${zoneId}/household`);
            return check.body === null || check.body === undefined;
          },
          { message: 'DELETE /api/zones/{id}/household removed the config' }
        )
        .toBe(true);
      // Delete clears the cache entry and invalidates
      // (useZoneHouseholdConfig.ts:304-311), and the config sync effect resets
      // hasUnsavedChanges (ZoneAccessSettings.tsx:205-210) — so a Save that is
      // disabled again is the UI-side proof the clear reached this mount.
      await expect(saveBtn).toBeDisabled();
    } finally {
      // Order matters: config references zone, zone references camera. A 404 is
      // agreement that the row is gone, so every leg accepts either.
      const config = await api.send(`/api/zones/${zoneId}/household`, 'DELETE');
      expect([204, 404]).toContain(config.status);
      expect([204, 404]).toContain(
        (await api.send(`/api/cameras/${firstCameraId}/zones/${zoneId}`, 'DELETE')).status
      );
      expect([204, 404]).toContain(
        (await api.send(`/api/cameras/${secondCameraId}/zones/${decoyZoneId}`, 'DELETE')).status
      );
      expect([204, 404]).toContain(
        (await api.send(`/api/household/members/${memberId}`, 'DELETE')).status
      );
    }
  });

  test('the guard survives the access drive', async ({ page }) => {
    const h = harness as Harness;
    await signIn(page, h);
    await page.goto(`${h.ui}/settings/access`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('members-section')).toBeVisible();
    await assertGuardSurvives(page, h);
  });
});

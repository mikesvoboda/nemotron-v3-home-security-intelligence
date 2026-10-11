/**
 * F2.3 DO-2 golden path, ambient-status half (inventory row F-238; claim
 * #6996). Client-only by the row's own contract — the backend column is "—",
 * the declared contract is the localStorage key — so the API leg a normal
 * DO-2 test runs first collapses to "login so the protected route mounts"
 * and the pin lives in storage.
 *
 * Why the pin is the STORAGE READ, not a checked-paint assert: Tremor's
 * Switch spreads its props and the exact rendered role/label cardinality is
 * not verifiable from this disk (no node_modules — CI is the type gate). The
 * CI-proven precedent (tests/e2e/pages/SettingsPage.ts:116 pins a Tremor
 * switch through getByLabel(/Email Notifications/i)) shows the aria-labels
 * are reachable; it does not certify match cardinality, so the locators here
 * take .first() and the CONTRACT assertion reads the v1 key through
 * readV1Settings — which is exactly what the row declares. A paint-only
 * pass was never the target; "toggles ... the favicon alert badge" means a
 * stored flag AmbientStatusProvider (:82) reads app-wide.
 *
 * Laws this file encodes (read at this head, cited by line):
 * - Defaults live in CODE, not on disk: useSettings.ts:86-102 ships every
 *   flag true (volume 0.5, suppressWhenFocused false), and useLocalStorage
 *   only writes on SET (:57) — a fresh mount has NO key. So the pre-click
 *   read is {} (or, on a same-context re-run, the all-true object a previous
 *   Enable All left — the assert admits both readings explicitly).
 * - The write is synchronous inside the setter (useLocalStorage.ts:47-57,
 *   no effect): click → read cannot race.
 * - Two storage keys, one trap: 'security-dashboard-settings' (v1,
 *   useSettings.ts:108) is what the mounted page writes; the zustand store
 *   at settings-store.ts:132 owns '-v2' and its migration REMOVES v1 (:375).
 *   The migration runs at boot, before any click here, and the click
 *   re-creates v1 synchronously — so read-after-click within one page is
 *   safe; no later navigation happens before the read.
 * - The buttons the inventory names exist: 'Enable All' /'Disable All' at
 *   AmbientStatusSettings.tsx:73/:81 (getByRole button, exact names — the
 *   only Buttons in this page's header block). The four switches carry the
 *   verified aria-labels (:110/:135/:190/:260); the suppress switch (:233)
 *   is inside the desktop branch.
 * - F-239's dead-wire law is visible in the same object: Disable All flips
 *   audio/desktop flags into storage too, but AmbientStatusProvider (:82)
 *   destructures ONLY ambientEnabled and faviconBadgeEnabled — so this file
 *   asserts the two flags a production consumer reads, and leaves the other
 *   two unasserted rather than pinning writes-nothing-reads (the inventory
 *   rows F-239 for retirement; do not grow its coverage).
 */
import { expect, test } from '../guard';
import { adminSession, assertGuardSurvives, login, readHarness, readV1Settings, type Harness } from './harness';

const harness = readHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

test.describe('DO-2 ambient status golden path (F-238)', () => {
  test('the ambient toggles persist to the v1 key the app-wide provider reads', async ({ page }) => {
    const h = harness as Harness;
    const session = await adminSession(h);
    await login(page, h, session);

    await page.goto(`${h.ui}/settings/ambient`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Ambient Status Awareness' })).toBeVisible();

    // Pre-state: defaults are CODE-side; a fresh context has no key, a
    // same-context re-run has the all-true object Enable All left. Both
    // readings mean "not disabled" — anything else is a leaked mutation.
    const before = await readV1Settings(page);
    expect(
      Object.keys(before).length === 0 ||
        (before.ambientStatus?.ambient?.enabled === true &&
          before.ambientStatus?.favicon?.enabled === true),
      `pre-click v1 state is absent or default-true, saw ${JSON.stringify(before)}`
    ).toBe(true);

    // The two production-read switches are visible by their verified labels
    // (.first(): label-spread cardinality is unverifiable from this disk —
    // header comment).
    await expect(page.getByLabel('Enable ambient background effects').first()).toBeVisible();
    await expect(page.getByLabel('Enable favicon badge').first()).toBeVisible();

    // --- Disable All: one click, four flags, read the two that matter ---
    await page.getByRole('button', { name: 'Disable All', exact: true }).click();
    const disabled = await readV1Settings(page);
    expect(
      disabled.ambientStatus?.ambient?.enabled,
      'ambient.enabled reaches the v1 key as false (the flag AmbientStatusProvider reads)'
    ).toBe(false);
    expect(
      disabled.ambientStatus?.favicon?.enabled,
      'favicon.enabled reaches the v1 key as false'
    ).toBe(false);
    // The page survived the state flip (no error boundary ate it): the
    // Title is still painted. The Eye→EyeOff icon branch (:93-97) is the
    // real paint evidence but svgs carry no accessible text, so the paint
    // claim here is deliberately this weak — the CONTRACT pin is the
    // storage read above.
    await expect(page.getByText('Ambient Status Awareness')).toBeVisible();

    // --- Enable All puts both flags back to the shipped default. It is not
    // the test's restore — the single-switch leg below flips ambient off
    // again and that leg restores it itself (see the switch-back-on at the
    // end of this test). What bounds the blast radius of any of this is not
    // run order: this file sends zero non-GET legs, and every write it makes
    // is a per-context localStorage write that dies with its context
    // (harness.ts header, invariant 1). ---
    await page.getByRole('button', { name: 'Enable All', exact: true }).click();
    const enabled = await readV1Settings(page);
    expect(enabled.ambientStatus?.ambient?.enabled, 'Enable All round-trips ambient on').toBe(true);
    expect(enabled.ambientStatus?.favicon?.enabled, 'Enable All round-trips favicon on').toBe(true);

    // The single-switch leg the inventory words literally ("toggles ambient
    // background effects"): click the switch itself, watch ONE flag move
    // while its sibling holds — proves per-flag persistence, not just the
    // batch setters.
    await page.getByLabel('Enable ambient background effects').first().click();
    const soloed = await readV1Settings(page);
    expect(soloed.ambientStatus?.ambient?.enabled, 'the ambient switch alone flips its own flag').toBe(false);
    expect(
      soloed.ambientStatus?.favicon?.enabled,
      'the favicon flag is untouched by the ambient switch (no clobber)'
    ).toBe(true);

    // Restore for any same-context reader: switch back on.
    await page.getByLabel('Enable ambient background effects').first().click();
    const restored = await readV1Settings(page);
    expect(restored.ambientStatus?.ambient?.enabled, 'switch restored to shipped default true').toBe(true);
  });

  test('the guard survives the ambient drive', async ({ page }) => {
    const h = harness as Harness;
    const session = await adminSession(h);
    await login(page, h, session);
    await page.goto(`${h.ui}/settings/ambient`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Ambient Status Awareness' })).toBeVisible();
    await assertGuardSurvives(page, h);
  });
});

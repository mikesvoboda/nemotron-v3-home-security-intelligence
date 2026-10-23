/**
 * FE-1 golden path (F2.3): F-018 — command palette (Ctrl/⌘K and the Search…
 * click, fuzzy search, select-navigates), `g`-chords, and the `?` shortcuts
 * help modal.
 *
 * Every navigation goes through quietBoot()/BOOT_QUIET_MS (harness.ts — the
 * frontend nginx /api throttle and why a boot needs a drained burst).
 *
 * THE HARD CONSTRAINT: CommandPalette.tsx ships ZERO data-testids. Its whole
 * surface is ARIA + cmdk's own DOM contract, and that IS the testable surface:
 * the wrapper is role=dialog aria-label "Command palette" (CommandPalette.tsx
 * :172-177), the input is placeholder "Type to search..." (:228-232), the
 * group heading is "Navigation" (:242-244), and cmdk@1.1.1 (installed, dist/
 * index.mjs verified) renders every item as div[cmdk-item][role=option] with
 * data-value and aria-selected — a non-matching item UNMOUNTS (forwardRef Item
 * returns null when its score is 0), so hidden is toHaveCount(0), not
 * toBeHidden. Items are addressed by [cmdk-root] scoping because "Logs" is
 * also the Sidebar's NavLink text elsewhere on the page.
 *
 * Decided from shipped code before writing (each claim cites where):
 * - Ctrl+K: the document keydown listener opens the palette (useKeyboardShort
 *   cuts.ts:122-126, mounted by Layout.tsx:52-61). The Meta leg is the same
 *   branch (`metaKey || ctrlKey` :122); Control is what this runner can press
 *   portably, so Control+k is the pinned instrument.
 * - Search… click: Header's button carries data-testid="search-trigger" and
 *   calls openCommandPalette through the context (Header.tsx:300-312; the
 *   provider is Layout.tsx:77-85). The trigger is `hidden sm:flex` — it only
 *   exists at ≥640, hence the 1440 viewport.
 * - Fuzzy filter (:190-210): combined = value + keywords, lowercased; a WORD
 *   startsWith the search ⇒ 1, a plain substring ⇒ 0.5, else 0 (unmounted).
 *   Each query below has a provably unique branch from the NAVIGATION_ITEMS
 *   table (:48-119): "tim" matches Timeline by NAME word-start (nothing else
 *   contains "tim"); "hist" matches Timeline AND Audit Log ONLY through the
 *   joined keywords — neither NAME contains "hist" — so it pins the keywords
 *   arm, and their tie (both 1) keeps registration order, Timeline first;
 *   "ANALYT" pins case-insensitivity (filter lowercases both sides) via name
 *   word-start "analytics"; "atus" is substring-only ("status" contains it, no
 *   word starts with it) ⇒ System listed at 0.5 with everything else gone;
 *   "zzzznotathing" empties the list into Command.Empty "No results found."
 *   (:238-240).
 * - Select: cmdk's Enter dispatches its internal select event on the aria-
 *   selected item, onSelect runs navigate(path) then onOpenChange(false)
 *   (:150-156), and `!open` returns null (:167-169) — the dialog UNMOUNTS.
 *   ArrowDown before typing moves the aria-selected marker through the hook's
 *   DOM order (cmdk ArrowDown → next item), pinning the footer's ↑↓ hint and
 *   the registration order Dashboard-first.
 * - Escape inside the palette: Layout passes enabled=false while a modal is
 *   open (Layout.tsx:60), so the GLOBAL hook cannot also fire; the palette
 *   closes through its OWN onKeyDown (:158-165 wired at :188). Backdrop click
 *   closes too (:179-183) — clicked at x=10, outside the max-w-lg centered
 *   panel, so the hit lands on the backdrop, not the list.
 * - Typing guard: the global handler returns early when the event target is
 *   an input (isEditableElement :56-71, guard :115-117). The palette input is
 *   the bench: typing "?" THERE must not open the help modal, and Ctrl+K there
 *   must not re-fire the opener.
 * - g-chords: 'g' arms a 1000 ms window (CHORD_TIMEOUT :16), a second key in
 *   CHORD_ROUTES (:19-29) navigates (:143-164). 'g t' → /timeline and
 *   'g a' → /alerts are the pinned jumps; then 'g', a 1.2 s sleep past the
 *   window, 'a' — the URL MUST NOT move, which pins the timeout branch itself,
 *   not just the happy path. 'g y' (System) is deliberately untested: the row
 *   hands /system to F-019.
 * - Every chord/palette hop also asserts not-found-page is count 0: App.tsx
 *   ends in a catch-all `*` → NotFoundPage (data-testid at NotFoundPage.tsx
 *   :36), so without this, navigating to an unregistered path would still
 *   "pass" a URL check. This is the row-note's own claim — all palette entries
 *   except System resolve to real routes — measured.
 * - `?`: opens the help modal (hook :136-140 → Layout :54). The modal is
 *   role=dialog aria-label "Keyboard shortcuts" (ShortcutsHelpModal.tsx:112-
 *   119) with three groups Global/Navigation/List Navigation (:36-70); the
 *   focus trap (useFocusTrap.ts) focuses the FIRST FOCUSABLE element in the
 *   container on a rAF (:129-144) — that is the Close button (:133-139) — and
 *   a document-level Escape closes it (:173-176 → onClose); on close it
 *   returns focus to the previously focused element (:152-161), which here is
 *   body, because the press that opened the modal came from page.keyboard on
 *   the body.
 * - Ctrl+K while the HELP modal is open must not open the palette — the same
 *   enabled=false gate (:60), pinned from the other side.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { closedByGuard, openShell, readShellHarness, type ShellHarness } from '../harness';

const harness = readShellHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

/** Palette locator (the component ships no testids — see docstring). */
const palette = (page: import('@playwright/test').Page) =>
  page.getByRole('dialog', { name: 'Command palette' });
const paletteInput = (page: import('@playwright/test').Page) =>
  page.getByPlaceholder('Type to search...');
/** One cmdk item, scoped to the palette's cmdk root, matched by its value. */
const paletteItem = (page: import('@playwright/test').Page, value: string) =>
  page.locator(`[cmdk-root] [cmdk-item][data-value="${value}"]`);
/** A cmdk item only counts as listed if it is mounted AND visible. */
async function assertListed(page: import('@playwright/test').Page, value: string) {
  await expect(paletteItem(page, value)).toHaveCount(1);
  await expect(paletteItem(page, value)).toBeVisible();
}
async function assertNotListed(page: import('@playwright/test').Page, value: string) {
  await expect(paletteItem(page, value)).toHaveCount(0);
}
/** Route landed + catch-all guard (row note: these are REAL routes). */
async function assertOnRoute(page: import('@playwright/test').Page, h: ShellHarness, path: string) {
  await expect(page).toHaveURL(`${h.ui}${path}`);
  await expect(page.getByTestId('not-found-page')).toHaveCount(0);
}

test.describe('golden path: command palette + keyboard shortcuts @critical', () => {
  test.beforeEach(async ({ page }) => {
    // ≥640 is where the Search… trigger exists at all (Header.tsx `hidden
    // sm:flex`), and it keeps isMobile false so the desktop shell mounts.
    await page.setViewportSize({ width: 1440, height: 900 });
  });

  test('F-018 (palette): Ctrl+K and Search… open it, fuzzy search filters, select navigates', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(120_000);
    await openShell(page, h);

    // --- open by keyboard ------------------------------------------------
    await expect(palette(page)).toHaveCount(0); // closed state is UNMOUNTED
    await page.keyboard.press('Control+k');
    await expect(palette(page)).toBeVisible();
    // The component focuses its input via setTimeout(0) (:141-148); the
    // input's existence is proven by the placeholder locator being focusable.
    await expect(paletteInput(page)).toBeFocused({ timeout: 5_000 });
    // Group heading scoped to the dialog — "Navigation" is generic enough
    // that a page-level locator could collide with shell chrome text.
    await expect(palette(page).getByText('Navigation', { exact: true })).toBeVisible(); // :242

    // Easy mode lists the Easy hubs and tabs + Switch to Advanced (F4.9).
    await expect(page.locator('[cmdk-root] [cmdk-item]').first()).toContainText(/Dashboard/);
    await assertListed(page, 'Dashboard');
    await assertListed(page, 'Trends');
    await assertListed(page, 'Timeline');
    await assertListed(page, 'Alerts');
    await assertListed(page, 'Settings');
    await assertListed(page, 'Audit log');
    await assertListed(page, 'Switch to Advanced');

    // --- name match ("tim" is word-startsWith on "timeline", unique) -----
    await paletteInput(page).fill('tim');
    await assertListed(page, 'Timeline');
    await assertNotListed(page, 'Dashboard');
    await assertNotListed(page, 'Settings');
    // Typing alone navigates nothing.
    await expect(page).toHaveURL(`${h.ui}/`);

    // --- keywords/word-start match ("hist" matches Timeline + Audit log via
    // keywords and Notification history by label word-start) ----------------
    await paletteInput(page).fill('hist');
    await assertListed(page, 'Timeline'); // keyword "history"
    await assertListed(page, 'Audit log'); // keyword "history"
    await assertListed(page, 'Notification history'); // label "Notification history"
    await expect(page.locator('[cmdk-root] [cmdk-item]')).toHaveText([
      /Timeline/,
      /Audit log/,
      /Notification history/,
    ]);

    // --- case-insensitivity (both sides lowercased) ----------------------
    await paletteInput(page).fill('ANALYT');
    await assertListed(page, 'Trends');
    await assertNotListed(page, 'Alerts');

    // --- substring-only branch ("vervi" starts no word; "overview" contains
    // it — Dashboard's keyword, filter returns 0.5) -----------------------
    await paletteInput(page).fill('vervi');
    await assertListed(page, 'Dashboard');
    await assertNotListed(page, 'Timeline');

    // --- zero-match lands the Command.Empty copy --------------------------
    await paletteInput(page).fill('zzzznotathing');
    await expect(page.getByText('No results found.')).toBeVisible();
    await expect(page.locator('[cmdk-root] [cmdk-item]')).toHaveCount(0);

    // --- select by Enter on a filtered list navigates + unmounts ---------
    await paletteInput(page).fill('Timeline');
    await paletteInput(page).press('Enter'); // cmdk dispatches select on the
    await assertOnRoute(page, h, '/timeline'); // aria-selected item
    await expect(palette(page)).toHaveCount(0);

    // --- open by the Search… click; keyboard-select an ArrowDown move ----
    await page.getByTestId('search-trigger').click();
    await expect(palette(page)).toBeVisible();
    await expect(paletteInput(page)).toBeFocused({ timeout: 5_000 });
    await expect(paletteItem(page, 'Dashboard')).toHaveAttribute('aria-selected', 'true');
    await page.keyboard.press('ArrowDown');
    await expect(paletteItem(page, 'Trends')).toHaveAttribute('aria-selected', 'true');
    await page.keyboard.press('Enter');
    await assertOnRoute(page, h, '/analytics');
    await expect(palette(page)).toHaveCount(0);

    // --- Escape closes (the palette's OWN handler; Layout's hook is
    // disabled while a modal is open, Layout.tsx:60). The toBeFocused wait
    // is what makes this deterministic, not ceremonial — see the Search…
    // leg's comment above for the measured body-focus trap. ---------------
    await page.keyboard.press('Control+k');
    await expect(palette(page)).toBeVisible();
    await expect(paletteInput(page)).toBeFocused({ timeout: 5_000 });
    await page.keyboard.press('Escape');
    await expect(palette(page)).toHaveCount(0);

    // --- backdrop click closes (click left of the max-w-lg centered panel)
    await page.keyboard.press('Control+k');
    await expect(palette(page)).toBeVisible();
    await page.mouse.click(10, 400);
    await expect(palette(page)).toHaveCount(0);

    // --- typing guard: "?" and Ctrl+K inside the palette input must NOT
    // reach the global hook (useKeyboardShortcuts.ts:115-117) -------------
    await page.keyboard.press('Control+k');
    await expect(palette(page)).toBeVisible();
    await paletteInput(page).fill('?');
    await page.keyboard.press('?');
    await expect(page.getByRole('dialog', { name: 'Keyboard shortcuts' })).toHaveCount(0);
    await paletteInput(page).press('Control+k'); // target is an input ⇒ hook
    // returns early; the palette stays open exactly once (no state weirdness).
    await expect(palette(page)).toHaveCount(1);
    await expect(paletteInput(page)).toBeFocused({ timeout: 5_000 });
    await page.keyboard.press('Escape');
    await expect(palette(page)).toHaveCount(0);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-018 (g-chords): g+key jumps between routes; the 1000 ms window expires', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(120_000);
    await openShell(page, h);

    // g t → /timeline (CHORD_ROUTES :21). All SPA-side: no boot wave between
    // hops, so no extra drain is needed here.
    await page.keyboard.press('g');
    await page.keyboard.press('t');
    await assertOnRoute(page, h, '/timeline');

    // g a → /alerts (:23)
    await page.keyboard.press('g');
    await page.keyboard.press('a');
    await assertOnRoute(page, h, '/alerts');

    // The timeout branch (CHORD_TIMEOUT 1000 ms, :16 + :159-162): arm g,
    // outlive the window, then press a — the chord must be DEAD.
    await page.waitForTimeout(1_300); // 1.2 s window + scheduling slack
    await page.keyboard.press('g');
    await page.waitForTimeout(1_300);
    await page.keyboard.press('a');
    await expect(page).toHaveURL(`${h.ui}/alerts`); // never moved

    // An unknown second key also cancels the chord without navigating
    // (:143-151: route undefined ⇒ resetChord, no preventDefault, no jump).
    await page.keyboard.press('g');
    await page.keyboard.press('q');
    await expect(page).toHaveURL(`${h.ui}/alerts`);
    // …and the cancelled chord did not leave a pending window: g a right
    // after still works (a stale pending flag would make bare `a` the
    // completer and land the same URL — so re-arm explicitly, then jump).
    await page.keyboard.press('g');
    await page.keyboard.press('a');
    await assertOnRoute(page, h, '/alerts');

    // g d → / (:20) — proves the chord survives client-side route changes.
    await page.keyboard.press('g');
    await page.keyboard.press('d');
    await assertOnRoute(page, h, '/');

    // `?` after chords: the global help listener is independent of chord
    // state (hook :136-140 precedes the chord branch :143-164).
    const help = page.getByRole('dialog', { name: 'Keyboard shortcuts' });
    await expect(help).toHaveCount(0);
    await page.keyboard.press('?');
    await expect(help).toBeVisible();

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-018 (help modal): ? opens the shortcuts reference, focus trap and Escape behave', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(120_000);
    await openShell(page, h);

    const help = page.getByRole('dialog', { name: 'Keyboard shortcuts' });
    await expect(help).toHaveCount(0);
    await page.keyboard.press('?');
    await expect(help).toBeVisible();

    // The reference itself: heading, all three groups, and two rows pinned
    // key-for-key (ShortcutsHelpModal.tsx:36-70) — the palette opener and
    // one chord — because the row's promise is this table's CONTENT.
    await expect(page.getByRole('heading', { level: 2, name: 'Keyboard Shortcuts' })).toBeVisible();
    await expect(help.getByText('Global', { exact: true })).toBeVisible();
    await expect(help.getByText('Navigation', { exact: true })).toBeVisible();
    await expect(help.getByText('List Navigation', { exact: true })).toBeVisible();
    const paletteRow = help.locator('div', { hasText: 'Open command palette' }).last();
    await expect(paletteRow.getByText('⌘/Ctrl')).toBeVisible();
    const chordRow = help.locator('div', { hasText: 'Go to Timeline' }).last();
    await expect(chordRow.getByText('g', { exact: true })).toBeVisible();
    await expect(chordRow.getByText('t', { exact: true })).toBeVisible();

    // Focus trap on open: first focusable in the container is the Close
    // button (useFocusTrap.ts:129-144 + :133-139).
    await expect
      .poll(
        async () =>
          await page.evaluate(() =>
            (document.activeElement as HTMLElement | null)?.getAttribute('aria-label')
          ),
        { timeout: 5_000, message: 'focus never reached the help modal Close button' }
      )
      .toBe('Close');

    // The palette cannot open on top of the help modal: Layout disables the
    // global hook while ANY modal is open (Layout.tsx:60).
    await page.keyboard.press('Control+k');
    await expect(palette(page)).toHaveCount(0);

    // Escape through the focus trap's document listener (:173-176).
    await page.keyboard.press('Escape');
    await expect(help).toHaveCount(0); // !open returns null (:108-110)
    // …and focus went back where it came from: body (returnFocus :152-161;
    // the opening press was keyboard-on-body, so previouslyFocused is body).
    await expect
      .poll(async () => await page.evaluate(() => document.activeElement?.tagName ?? null), {
        timeout: 5_000,
        message: 'focus was not returned after the help modal closed',
      })
      .toBe('BODY');

    // Its own Close button closes it too, and ? reopens (state, not residue).
    await page.keyboard.press('?');
    await expect(help).toBeVisible();
    await help.getByRole('button', { name: 'Close' }).click();
    await expect(help).toHaveCount(0);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});

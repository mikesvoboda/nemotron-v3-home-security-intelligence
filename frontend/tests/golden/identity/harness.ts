/**
 * Shared harness plumbing for the F2.3 DO-3 golden paths (claim #6996).
 * DO-3 covers the identity surfaces: zones (F-256, F-258), household
 * (F-270, F-271) and face recognition (F-275, F-277, F-278).
 *
 * Why this file is a COPY and not an import of ../notify-access/harness.ts:
 * ruling 87's file rule keeps a batch PR inside its own
 * `frontend/tests/golden/<area>/` directory plus its inventory rows, so DO-3
 * cannot import DO-2's module even though the plumbing is nearly identical.
 * That is deliberate separation — the two batches evolve their sessions
 * independently — but it means the shape below is reproduced, and every
 * comment that carried a reason in DO-2's file is reproduced here too, because
 * a copy without the reason is how the next reader reintroduces the bug.
 *
 * What DO-3 IS relative to DO-2: these are CRUD surfaces. The no-env fake-AI
 * stack seeds ONLY cameras — scripts/feature_check.py calls seed_cameras()
 * (call :1836; the def is :1284) and nothing else; grepping `household`, `known-persons`,
 * `camera_zones` and `registered_vehicles` over feature_check.py and
 * feature-check.sh returns 0 for each (positive control: `cameras` = 16 hits
 * in the same file, 0 in the .sh). The rich seeders in scripts/seed-events.py
 * (seed_household_members, seed_registered_vehicles, seed_camera_zones) are
 * NOT on the harness path. So the passive mount of every DO-3 page is its
 * EMPTY state, and any spec that wants a row must create it and delete it in
 * its own finally — the invariant DO-2's harness documents at :45-54.
 *
 * Component ground truth (verified at a195b0984 — and it is NOT what DO-2
 * trained me to expect, NOR as clean as my first draft of this comment claimed).
 * What is true: the 3 page files (ZonesPage, HouseholdPage, FaceRecognitionPage)
 * and src/components/{household,face-recognition,common}/ hold 0 non-test
 * @tremor importers. What is FALSE, and I nearly shipped it: "ZonesPage does
 * not use Tremor." src/components/zones/ has 6 non-test Tremor files and two
 * chains reach the page — ZonesPage.tsx:47 imports CrossingTrendsChart (Tremor
 * Card/Title/AreaChart/Text at its :14) and ZonesPage.tsx:46 imports
 * ComparisonTab, which imports ZoneComparisonChart at its :21. A directory-wide
 * grep also hides the reverse error: 4 of those 6 (ZoneEditorSidebar,
 * ZoneActivityHeatmap, ZoneStatusCard, ZoneOwnershipPanel) are reachable only
 * through ZoneEditor.tsx:26 + the barrel index.ts:24-30, i.e. NOT from
 * ZonesPage at all.
 *
 * So the honest rule for DO-3 is per-ELEMENT, not per-page: every locator below
 * was checked against the markup of the element it targets, because these
 * surfaces mix frameworks. The overview grid and FilterBar are native
 * (data-testid="zone-type-select" is a real <select> at ZonesPage.tsx:219-227,
 * <option>s inside), ZoneTrustMatrix is native (8 <button>s, no Tremor), and
 * the identity cards are native. The analytics/comparison tabs are not, and no
 * DO-3 spec asserts into them. Consequences for locators:
 *   - selects are NATIVE, and Playwright maps a single <select> to role
 *     `combobox` (playwright-core: multiple/size>1 → listbox, else combobox).
 *     getByRole('listbox') finds nothing here, and native <option>s are
 *     invisible to Playwright — use selectOption()/toHaveValue(), never
 *     click-then-click. DO-2's Tremor-Select limitation does NOT apply.
 *   - the only toggles are native checkboxes (toBeChecked) and
 *     aria-pressed buttons (toHaveAttribute('aria-pressed', …)). There is no
 *     Tremor Switch, so DO-2's F-020 aria-checked trap does NOT apply either.
 *   - headings are REAL <h2>/<h3> (KnownPersonsTab.tsx:213 renders <h2>Known
 *     Persons</h2>; the card titles are <h3>), so the sectionTitle() workaround
 *     DO-2 needs (Tremor <Title> renders <p>, no heading role) is deliberately
 *     absent here: importing it would assert a page shape these pages do not
 *     have.
 *   - the inventory's prose is NOT a locator source. The F-275 row says "cards
 *     with an Add Person button", but that button has no name attribute
 *     (KnownPersonsTab.tsx:218-224 is a bare <button> whose accessible name
 *     comes from its text + an aria-hidden <Plus> icon), so getByRole('button',
 *     {name:'Add Person'}) works only because of the text. Assert the text.
 *
 * Wiring facts this layout depends on (all read at this head):
 * - feature_check.py golden() (scripts/feature_check.py:1369) runs `playwright
 *   --project=golden`; the golden project is testDir ./tests/golden with
 *   workers: 1, fullyParallel: false (frontend/playwright.config.ts:282-288).
 * - `retries: process.env.CI ? 2 : 0` (playwright.config.ts:79) is NOT
 *   overridden by the golden project, so CI gives each test two attempts and a
 *   local run gives it none. junit merges a retry-absorbed failure into
 *   `passed`, and golden() reads only junit (its two junit_results calls:
 *   :1402 for the backend specs, :1459 for Playwright; junit_results itself is
 *   :834) — so a green Feature-check row can mean "passed on retry". Promotion
 *   evidence for a DO-3 row is the run's
 *   golden-playwright.log (it prints `flaky` and `(retry #1)`), not the verdict.
 * - The page/context guard comes from ../guard, never the tests/e2e fixtures
 *   (which auto-mock). addCookies (login) and the API legs below are real
 *   traffic, not interception, so the guard does not fire on them.
 */
import { expect, type Locator, type Page } from '@playwright/test';

import { GUARD_MESSAGE } from '../guard';

export interface Harness {
  ready: true;
  api: string;
  ui: string;
  admin: { username: string; password: string };
}

/** Read the harness contract defensively: any piece missing → {ready: false,
 *  why}. Collection-time code must not throw, or `--list` breaks outside the
 *  harness. A spec consumes it as `test.skip(!h.ready, h.why)`. */
export function readHarness(): Harness | { ready: false; why: string } {
  const need = [
    'FEATURE_CHECK_UI_URL',
    'FEATURE_CHECK_API_URL',
    'FEATURE_CHECK_ADMIN_USERNAME',
    'FEATURE_CHECK_ADMIN_PASSWORD',
  ] as const;
  const missing = need.filter((name) => !process.env[name]);
  if (missing.length) return { ready: false, why: `missing ${missing.join(', ')}` };
  return {
    ready: true,
    api: String(process.env.FEATURE_CHECK_API_URL),
    ui: String(process.env.FEATURE_CHECK_UI_URL),
    admin: {
      username: String(process.env.FEATURE_CHECK_ADMIN_USERNAME),
      password: String(process.env.FEATURE_CHECK_ADMIN_PASSWORD),
    },
  };
}

export interface Session {
  name: string;
  value: string;
}

/** A real login against the real backend — the cookie is genuine state, not a
 *  mock. Split on the FIRST '=' only: a session token can carry base64 padding. */
export async function adminSession(h: Harness): Promise<Session> {
  const response = await fetch(`${h.api}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: h.admin.username, password: h.admin.password }),
  });
  if (response.status !== 200 && response.status !== 204) {
    throw new Error(`golden admin login answered ${response.status}: ${await response.text()}`);
  }
  const pair = response.headers
    .getSetCookie()
    .map((entry) => entry.split(';')[0])
    .find((entry) => entry.includes('='));
  if (!pair) throw new Error('golden admin login set no session cookie');
  const index = pair.indexOf('=');
  return { name: pair.slice(0, index), value: pair.slice(index + 1) };
}

/** The session cookie rides into the browser on the UI origin: that origin's
 *  nginx proxies /api to the backend, so the browser authenticates the way a
 *  user who logged in through this very form would. */
export async function login(page: Page, h: Harness, session: Session): Promise<void> {
  const url = new URL(h.ui);
  await page.context().addCookies([
    {
      name: session.name,
      value: session.value,
      domain: url.hostname,
      path: '/',
      httpOnly: true,
      secure: url.protocol === 'https:',
      sameSite: 'Lax',
    },
  ]);
  await page.goto(`${h.ui}/login`, { waitUntil: 'domcontentloaded' });
}

export interface ApiResponse {
  status: number;
  body: any;
}

export interface AuthedFetch {
  getJson(urlPath: string): Promise<ApiResponse>;
  /** Verb-carrying leg. DO-3 needs this more than DO-2 did: every one of its
   *  CRUD rows must create its own fixture row (the stack seeds none) and
   *  delete it in the spec's finally. 204 responses have no body, so body is
   *  null there by contract — and DELETE legs legitimately accept 204-or-404
   *  when the 404 is itself the proof the row is gone. */
  send(urlPath: string, method: string, payload?: unknown): Promise<ApiResponse>;
}

/** Backend calls with the harness admin's session. Every DO-3 spec runs its
 *  API leg BEFORE its UI leg, so a blank screen can never pass as "renders"
 *  and an absent row can never pass as "deleted". */
export function authedFetch(h: Harness, session: Session): AuthedFetch {
  const call = async (urlPath: string, init?: RequestInit): Promise<ApiResponse> => {
    const response = await fetch(`${h.api}${urlPath}`, {
      ...init,
      headers: {
        Cookie: `${session.name}=${session.value}`,
        ...(init?.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(init?.headers ?? {}),
      },
    });
    const body = await response.json().catch(() => null);
    return { status: response.status, body };
  };
  return {
    getJson: (urlPath) => call(urlPath),
    send: (urlPath, method, payload) =>
      call(urlPath, { method, body: payload === undefined ? undefined : JSON.stringify(payload) }),
  };
}

/** The URL PATH a Playwright request/response carried, normalized: origin and
 *  query stripped, ONE optional trailing slash removed.
 *
 *  Why exact-path equality and not endsWith(): a waitForResponse predicate that
 *  can never fire is worse than a wrong assert — the assert fails loudly, the
 *  matcher silently skips the code in the finally that restores state (DO-2
 *  measured exactly that in CI run 38148818888, where the preferences PUT's
 *  trailing-slash form never matched an endsWith predicate and the restore was
 *  skipped). DO-3 is more exposed to the sibling-route half of the same
 *  hazard: /api/household/members and /api/household/vehicles share the
 *  /api/household prefix, and a prefix matcher binds both. */
export function apiPath(url: string): string {
  const p = new URL(url).pathname;
  return p.length > 1 && p.endsWith('/') ? p.slice(0, -1) : p;
}

/** End-of-spec honesty, the guard surviving the whole drive (F2.1's pin,
 *  re-armed per batch so a DO-3 spec that reached for a mock fails LOUD). */
export async function assertGuardSurvives(page: Page, h: Harness): Promise<void> {
  expect(new URL(page.url()).host).toBe(new URL(h.ui).host);
  expect(() => page.route('**/api/**', (route) => route.abort())).toThrow(GUARD_MESSAGE);
}

/** The card container for a HOUSEHOLD member or vehicle, by its title.
 *
 *  The household cards are the one surface here with no testid and no role at
 *  all: a member card is a bare <div className="rounded-lg …"> at
 *  HouseholdPage.tsx:976-979 wrapping <h3>{member.name}</h3> at :982, and the
 *  vehicle card is the same shape at :1057-1059 / <h3>{vehicle.description}</h3>
 *  at :1063. So the only reachable anchor is the <h3>, and the card is whatever
 *  wraps it — hence the XPath. It is deliberately NOT used for zones or known
 *  persons, which both have better handles:
 *   - zone card: data-testid={`zone-card-${zone.id}`} at ZonesPage.tsx:307
 *     (<h3>{zone.name}</h3> at :316). Unusable as a NAME because the backend
 *     mints the id itself — `id=str(uuid.uuid4())` at
 *     backend/api/routes/zones.py:89 — so a spec can only take the testid from
 *     the POST response it just made.
 *   - known-person card: static data-testid="known-person-card" plus
 *     role="button" and aria-label={`View details for ${person.name}`}
 *     (KnownPersonsTab.tsx:60-67). Use getByRole('button', {name:
 *     `View details for …`}) — accessible, and it also pins the a11y surface.
 *
 *  Naming it after the two rows that need it keeps a later DO-3 spec from
 *  reaching for XPath where a real testid exists. */
export function householdCard(page: Page, title: string): Locator {
  return page
    .getByRole('heading', { name: title, level: 3 })
    .locator('xpath=ancestor::div[contains(@class,"rounded-lg")][1]');
}

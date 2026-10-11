/**
 * Golden path: the setup page / first-admin bootstrap (inventory F-002).
 *
 * Row claim: "with no users in the database, fills username, email, password
 * and confirm; clicks Create account; lands on the dashboard".
 *
 * WHY THIS SPEC COVERS THE POPULATED-DB SHAPE, AND WHAT THAT LEAVES OPEN
 * (decided from shipped code + live probes 2026-10-11, not assumed):
 *   The positive leg needs `users` EMPTY. That state occurs exactly once per
 *   harness lifetime — and it IS exercised on every CI boot: feature_check.py
 *   brings the stack up and calls register_admin() (scripts/feature_check.py:1268,
 *   invoked :1804), a real POST /api/auth/register against the fresh DB that
 *   returns 201 and creates the one admin every other golden spec logs in as.
 *   So the chain (register → INSERT users → invalidate_setup_cache →
 *   setup_required flips) is proven real by the harness's own boot, but a
 *   golden spec CANNOT RE-RUN it on a live stack, and the wall is arithmetic,
 *   not policy: the only route that removes a user is DELETE
 *   /api/admin/users/{user_id} (backend/api/routes/admin.py:1499 → db.delete
 *   :1550), it refuses self-deletion (:1533-1537), and the harness stack has
 *   exactly ONE user — the one that bootstrap created. There is no way to
 *   empty `users` without deleting the sole admin from their own session,
 *   which the shipped code refuses by design. Destroying the shared stack is
 *   also off the table for a spec that runs beside 60 siblings.
 *   What remains genuinely provable on a populated stack — and what this spec
 *   proves end to end through the UI, zero interception:
 *     1. The setup page's REAL current shape: with setup_required=false the
 *        page does NOT redirect (SetupPage's docstring says "redirects away"
 *        — the shipped return at :374-385 renders instead: full form PLUS an
 *        "An account already exists on this system." block linking to /login;
 *        /setup is a bare client route, App.tsx:239-246, outside
 *        ProtectedRoute, so nginx serves the SPA and the page paints
 *        regardless of the flag).
 *     2. The SHIPPED NEGATIVE PATH: a valid-shaped POST /api/auth/register
 *        answers 409 {detail: "Registration is closed. Users already exist in
 *        the system."} (auth.py:175-187). SetupPage maps it exactly:
 *        authApi.handleResponse extracts body.detail into the thrown Error
 *        (authApi.ts:100-122) → handleSubmit's catch sets apiError
 *        (SetupPage.tsx:184-199) → role=alert renders it (:234-242). The
 *        form survives, the URL stays /setup.
 *     3. The 409 CREATES NOTHING (the "reports success it did not achieve"
 *        door, closed by measurement): the existence check is the FIRST thing
 *        in register_user (:175-187) — before any INSERT, before
 *        invalidate_setup_cache — so the probe is read-only server-side.
 *        Asserted around one page-observed 409: GET /api/admin/users total
 *        and id-set identical before/after, and logging in with the probe
 *        credential answers 401 (no session was created for a user that isn't
 *        there). Safe on a shared stack because the 409 branch cannot mutate.
 *     4. The row's INPUT leg verbatim: the client validation matrix
 *        (validateForm :75-115) — required errors on empty submit, per-field
 *        rule errors on submit, errors cleared as the user types into the
 *        field (:147-150) — with no server round-trip at all (handleSubmit
 *        returns before registerUser when validation fails, :167-171).
 *   The positive leg (201 → navigate('/') → dashboard, :177-183) is a
 *   one-shot-on-empty-DB behavior: reachable for an automated instrument only
 *   on a stack nobody else is using, which is the operator's real tier
 *   (ruling 66). The row stays unverified, NOT half-built — the status
 *   vocabulary requires a break between user and store, and every link of
 *   this chain demonstrably works; the harness boot's own 201 is the proof.
 *
 * Live probe reads this spec mirrors (2026-10-11, probe stack):
 *   GET /api/auth/setup-status → {"setup_required":false,"auth_required":false}
 *   GET /setup through the UI nginx → 200 text/html (SPA fallback, ~1.4 kB)
 *   POST /api/auth/register (valid body) → 409 with that detail, IDENTICALLY
 *   through the API origin :18000 and the UI origin :18080 (the path the app's
 *   own fetch uses — the same nginx the boot wave crosses).
 *
 * Throttle discipline: every UI boot here goes through quietBoot (harness.ts —
 * the shared nginx /api burst; a shed setup-status fail-closes the guard, and
 * SetupPage shows its spinner forever while isLoading).
 */
import type { Page } from '@playwright/test';

import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  adminSession,
  api,
  closedByGuard,
  quietBoot,
  readShellHarness,
  seedTourDismissed,
} from './harness';

const harness = readShellHarness();

interface AdminUsers {
  items: { id: string; username: string }[];
  total: number;
}

interface SetupStatus {
  setup_required: boolean;
  auth_required?: boolean;
}

/** Fixed, never-submittable-successfully identity: the 409 fires before any
 *  write, so the name is harmless residue in a request the stack refuses. */
const PROBE = {
  username: 'golden-f002-spec',
  email: 'golden-f002-spec@example.com',
  password: 'GoldenF002Probe1',
} as const;

/** Fill the four shipped fields (labels: Email, Username, Password, Confirm
 *  Password — SetupPage.tsx:246, :273, :300, :330). 'Password' needs exact:
 *  getByLabel defaults to substring and 'Confirm Password' would collide. */
async function fillSetupForm(
  page: Page,
  f: Partial<{ username: string; email: string; password: string; confirm: string }>
): Promise<void> {
  if (f.username !== undefined) await page.getByLabel('Username').fill(f.username);
  if (f.email !== undefined) await page.getByLabel('Email').fill(f.email);
  if (f.password !== undefined) await page.getByLabel('Password', { exact: true }).fill(f.password);
  if (f.confirm !== undefined)
    await page.getByLabel('Confirm Password').fill(f.confirm ?? f.password ?? '');
}

async function submitSetup(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Create Account' }).click();
}

test.describe('golden path: setup page first-admin bootstrap @critical', () => {
  test.setTimeout(90_000);

  test('the real current shape: no redirect — the full form plus "account already exists" with a link to /login', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    await seedTourDismissed(page);

    // The precondition, mirrored from the API rather than assumed. Read
    // ANONYMOUSLY, exactly as the app itself does on boot (AuthContext's
    // getSetupStatus fires with credentials:include but needs no session —
    // setup-status is on the SetupGuard whitelist precisely so it answers
    // before anyone exists to log in).
    const status = await fetch(`${h.api}/api/auth/setup-status`).then(
      (r) => r.json() as Promise<SetupStatus>
    );
    expect(status.setup_required).toBe(false); // populated stack (register_admin at boot)

    await quietBoot(page, h, '/setup');

    // The whole registration form paints anyway — no Navigate guards it:
    // heading, sub-copy, all four inputs (SetupPage.tsx:227-228, :244-358).
    await expect(page.getByRole('heading', { name: 'First Time Setup' })).toBeVisible();
    await expect(page.getByText('Create your admin account to get started')).toBeVisible();
    for (const label of ['Email', 'Username', 'Confirm Password']) {
      await expect(page.getByLabel(label)).toBeVisible();
    }
    await expect(page.getByLabel('Password', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Create Account' })).toBeVisible();
    // The password requirements copy the validation cites (labelledby :309, :318).
    await expect(page.getByText(/at least 8 characters with uppercase/)).toBeVisible();

    // …and because setup_required came back false, the "already exists" block
    // renders too (:374-385) — the branch the row never mentions and the only
    // /setup state an automated non-destructive instrument can ever see.
    await expect(page.getByText('An account already exists on this system.')).toBeVisible();
    await page.getByRole('link', { name: 'Login with existing account' }).click();
    await expect(page).toHaveURL(/\/login/, { timeout: 15_000 });

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('the input leg: empty submit names every required field, each rule errors on submit, typing clears its error', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    await seedTourDismissed(page);
    await quietBoot(page, h, '/setup');

    // Empty submit: validateForm's required clauses (:79-98). Confirm has no
    // required error here BY DESIGN — its only rule is equality, gated on a
    // non-empty password (`if (data.password && …)` :110).
    await submitSetup(page);
    await expect(page.getByText('Username is required')).toBeVisible();
    await expect(page.getByText('Email is required')).toBeVisible();
    await expect(page.getByText('Password is required')).toBeVisible();
    await expect(page).toHaveURL(/\/setup/); // handleSubmit returns before the API (:167-171)

    // Typing into a field clears ONLY its own error (:147-150).
    await page.getByLabel('Username').fill('ab');
    await expect(page.getByText('Username is required')).toHaveCount(0);
    await expect(page.getByText('Email is required')).toBeVisible();

    // Per-rule clauses on the second submit (:81-112):
    await fillSetupForm(page, {
      email: 'nope',
      password: 'short1A', // 7 chars — under MIN_PASSWORD_LENGTH :65
      confirm: 'different1A',
    });
    await submitSetup(page);
    await expect(page.getByText('Username must be at least 3 characters')).toBeVisible();
    await expect(page.getByText('Invalid email format')).toBeVisible();
    await expect(page.getByText('Password must be at least 8 characters')).toBeVisible();
    await expect(page.getByText('Passwords do not match')).toBeVisible();
    await expect(page).toHaveURL(/\/setup/);

    // A fully-valid form is what the row fills — assembled here (and left
    // unsubmitted: on THIS stack the submit's end is test 3's measured 409).
    await fillSetupForm(page, {
      username: PROBE.username,
      email: PROBE.email,
      password: PROBE.password,
      confirm: PROBE.password,
    });
    await expect(page.getByText('Passwords do not match')).toHaveCount(0);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('the shipped negative path: a valid-shaped Create Account answers 409, names it on the form, and creates nothing', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    await seedTourDismissed(page);

    // Server ledger BEFORE the page leg (admin read with a real login's
    // cookie — the same adminSession every sibling spec uses).
    const session = await adminSession(h);
    const before = await api<AdminUsers>(h, session, '/api/admin/users');
    expect(before.total).toBeGreaterThanOrEqual(1);

    await quietBoot(page, h, '/setup');
    await fillSetupForm(page, {
      username: PROBE.username,
      email: PROBE.email,
      password: PROBE.password,
      confirm: PROBE.password,
    });
    await submitSetup(page);

    // The 409 round-trip, told by the app's own chain: handleResponse lifts
    // body.detail into the Error (authApi.ts:100-122) → apiError (:195) →
    // role=alert (:234-242). Exact shipped wording (probe-confirmed identical
    // through UI nginx and API origin).
    await expect(page.getByRole('alert')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole('alert')).toContainText(
      'Registration is closed. Users already exist in the system.'
    );
    await expect(page).toHaveURL(/\/setup/); // no navigation on failure
    await expect(page.getByLabel('Username')).toHaveValue(PROBE.username); // form survives

    // The app's own transport still reports the gate closed — the 409 flipped
    // nothing.
    const after = await page.evaluate(async () => {
      const r = await fetch('/api/auth/setup-status');
      return (await r.json()) as SetupStatus;
    });
    expect(after.setup_required).toBe(false);

    // Server ledger AFTER: the 409 branch (auth.py:175-187) is a pure read +
    // raise — same total, same id set, and the probe credential has no
    // session to log into (401).
    const post = await api<AdminUsers>(h, session, '/api/admin/users');
    expect(post.total).toBe(before.total);
    expect(new Set(post.items.map((u) => u.id))).toEqual(new Set(before.items.map((u) => u.id)));
    const ghostLogin = await fetch(`${h.api}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: PROBE.username, password: PROBE.password }),
    });
    expect(ghostLogin.status).toBe(401);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('the guard rail before the form even renders: the anonymous setup-status the empty stack still answers', async () => {
    // The row's precondition, READ rather than simulated. When `users` IS
    // empty, SetupGuardMiddleware answers 503 for everything off its
    // whitelist (backend/api/middleware/setup_guard.py:1-24) — a state a live
    // populated stack cannot show, and one the harness's own boot demonstrates
    // instead: scripts/feature_check.py:1268 registers through that wall
    // before any spec exists and gets 201. What the client side can pin on
    // THIS stack is the single property that makes the whole bootstrap
    // possible at all: setup-status sits ON that whitelist, so it answers
    // anonymously while the stack is still unbootstrappable — the only API
    // SetupPage can consult before there is anyone to log in as.
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const raw = await fetch(`${h.api}/api/auth/setup-status`);
    expect(raw.status).toBe(200);
    const body = (await raw.json()) as SetupStatus;
    expect(typeof body.setup_required).toBe('boolean');
    expect(typeof body.auth_required).toBe('boolean');
  });
});

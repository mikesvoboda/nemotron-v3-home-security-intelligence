/**
 * F2.3 DO-4 golden path — F-254, delete a scheduled report and confirm (ruling 191).
 *
 * Inventory row (F-254): "clicks Delete on a report and confirms", over
 * `DELETE /api/scheduled-reports/{report_id}` (`/scheduled-reports` page,
 * `delete_scheduled_report` at backend/api/routes/scheduled_reports.py:343).
 *
 * WHY THE SPEC LIVES IN golden/webhooks/ RATHER THAN A NEW golden/scheduled-reports/.
 * Ruling 191 named this directory for F-254, and the reason is legible: `webhooks/` is DO-4's
 * delete-through-the-native-confirm batch (F-248, delete.spec.ts), and F-254 is the same SHAPE —
 * a delete behind `window.confirm`, not an in-app modal (`ScheduledReportsPage.tsx:337`). The
 * scheduled-reports *feature* is a different page and API (`/api/scheduled-reports`, not
 * `/api/outbound-webhooks`), so this file does NOT reach into webhooks/harness.ts for fixtures —
 * it imports only that harness's proven transport primitives through the sibling
 * scheduled-reports-harness.ts, and adds scheduled-report create/teardown of its own. Ruling 87's
 * file rule is what forces the sibling rather than an edit (see that file's header). A future
 * batch that adds more `/scheduled-reports` rows can grow a `scheduled-reports/` directory; making
 * one now for a single spec, against the ruling's named home, would be the coordinator's call,
 * not this PR's.
 *
 * The dialog mechanics are F-248's, already paid for, and are REUSED VERBATIM rather than
 * re-litigated here: a native `window.confirm` can be answered only by a `page.on('dialog')`
 * HANDLER, because registering a listener suppresses Playwright's auto-dismiss and `window.confirm`
 * blocks the page's JS thread until answered — so a `waitForEvent('dialog')` waiter DEADLOCKS
 * (the click never finishes dispatching). That is measured and explained once, at
 * webhooks/delete.spec.ts:89-124; `answerConfirm` below is that handler. The `addInitScript`
 * alternative — replace `window.confirm` — is rejected for the same reason F-248 rejects it
 * (delete.spec.ts:21-25): replacing the function the row under test depends on would fake the very
 * thing the row is about, that the user says "yes" to the browser.
 *
 * What differs from F-248, measured on this page (so a locator copied blind would be wrong):
 * - THE DELETE IS INLINE, NOT IN A DROPDOWN. The card's action row holds Run Now / Disable / Edit /
 *   Delete as four always-visible <Button>s (ScheduledReportsPage.tsx:183-227), so there is no
 *   `More actions` menu to open first — F-248's `openDeleteItem` opens one and this does not. Every
 *   locator is still scoped to `report-card-<id>` (:137) because `Delete` and `Edit` render once per
 *   card and the page lists many cards: a page-wide getByText('Delete') strict-modes the moment the
 *   stack has two reports. Row scope is sufficient because the button lives inside that card.
 * - THE ACCEPT'S REPAINT IS A LIST REFETCH, AND ONLY A LIST REFETCH. `useDeleteScheduledReportMutation`
 *   onSuccess invalidates `['scheduled-reports','list']` and removeQueries the row's detail
 *   (useScheduledReports.ts:418-433); there is no `['webhooks','health']`-style second card on this
 *   page. So the only refetch the spec can witness is `GET /api/scheduled-reports` — and it must be
 *   EXACT-path matched, because a detail GET (`/api/scheduled-reports/<id>`) shares the prefix and
 *   would satisfy an endsWith() matcher that never proved the list refreshed (webhooks/harness.ts:154-158,
 *   and `apiPath()` is exact-after-normalization for exactly that reason).
 *
 * The two arms and their anchors are F-248's, because the failure modes are identical:
 * - DISMISS fires nothing. handleDelete early-returns on a false confirm
 *   (ScheduledReportsPage.tsx:337-338), so the DELETE leg is an ABSENCE, and an absence is anchored
 *   three ways or a matcher that cannot match passes vacuously: the dialog's own message asserted
 *   against the shipped template carrying THIS row's name, the row still in the DOM, and the row
 *   still in the STORE (an API read — a UI that still shows a row proves only the UI).
 * - ACCEPT deletes. `delete_scheduled_report` answers 204 with no body
 *   (status_code=HTTP_204_NO_CONTENT, scheduled_reports.py:335) after db.delete + commit, so the
 *   spec witnesses the 204, then the list refetch, and only then asserts absence.
 */
import { expect, test } from '../guard';
import {
  adminSession,
  apiPath,
  assertGuardSurvives,
  authedFetch,
  createScheduledReport,
  deleteScheduledReport,
  login,
  readHarness,
  scheduledReportIds,
  SCHEDULED_REPORTS_URL,
  type AuthedFetch,
  type Harness,
} from './scheduled-reports-harness';

const harness = readHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

const ROW_NAME = 'DO-4 f254 delete row';

/** Answer the page's native confirm and capture what it said, in one handler. The shape — a
 *  handler, not a waiter; decision mutable because the arms differ; running-total asserted per arm
 *  so a stray confirm shows up as a wrong count rather than a silent accept — is F-248's, with the
 *  deadlock reasoning that forced it at webhooks/delete.spec.ts:89-124. Nothing here re-derives
 *  it; that is the point of a twin. */
function answerConfirm(page: Parameters<typeof login>[0]): {
  prompts: { type: string; message: string }[];
  setDecision: (d: 'dismiss' | 'accept') => void;
} {
  const prompts: { type: string; message: string }[] = [];
  let decision: 'dismiss' | 'accept' = 'dismiss';
  page.on('dialog', (dialog) => {
    prompts.push({ type: dialog.type(), message: dialog.message() });
    // Deliberately not awaited: answering IS what unblocks the click we are awaiting.
    void (decision === 'dismiss' ? dialog.dismiss() : dialog.accept());
  });
  return { prompts, setDecision: (d) => (decision = d) };
}

async function signIn(page: Parameters<typeof login>[0], h: Harness): Promise<AuthedFetch> {
  const session = await adminSession(h);
  await login(page, h, session);
  return authedFetch(h, session);
}

function watchRequests(page: Parameters<typeof login>[0]): string[] {
  const log: string[] = [];
  page.on('request', (req) => log.push(`${req.method()} ${apiPath(req.url())}`));
  return log;
}

const countOf = (log: string[], entry: string) => log.filter((e) => e === entry).length;

/** The row's Delete button. Unlike F-248 there is no dropdown to open: the Delete <Button> is a
 *  direct child of the card's action row. Still row-scoped, because Delete renders once per card. */
async function deleteButtonOf(page: Parameters<typeof login>[0], rowId: string) {
  const row = page.getByTestId(`report-card-${rowId}`);
  await expect(row).toBeVisible();
  const button = row.getByRole('button', { name: 'Delete', exact: true });
  await expect(button).toBeVisible();
  return button;
}

test.describe('DO-4 delete a scheduled report through the native confirm (F-254)', () => {
  test('dismissing the confirm fires nothing; accepting it deletes, repaints, and restores', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);
    const log = watchRequests(page);
    const before = await scheduledReportIds(api);

    let id = '';
    let deletedThroughUi = false;
    try {
      id = await createScheduledReport(api, ROW_NAME);
      // The API leg runs BEFORE the UI leg (the DO-2 rule): a row the backend does not have cannot
      // pass as "deleted", and a single GET to the row's own path is a positive control that the
      // fixture is real before any click reads it as gone.
      const stored = await api.getJson(`${SCHEDULED_REPORTS_URL}/${id}`);
      expect(stored.status, 'the row exists before the UI touches it').toBe(200);
      const storedName = String(stored.body?.name);

      await page.goto(`${h.ui}/scheduled-reports`, { waitUntil: 'domcontentloaded' });
      const row = page.getByTestId(`report-card-${id}`);
      await expect(row).toBeVisible();

      // ---- ARM 1: dismiss. The contract is an ABSENCE, anchored three ways. ----
      const confirm = answerConfirm(page);
      await (await deleteButtonOf(page, id)).click();

      // The non-null / count-1 check comes FIRST: the arms below are abscences, and if the handler
      // never fired there was no prompt and "0 DELETEs" would pass for the wrong reason — a spec bug
      // reading as the feature working (webhooks/harness.ts:29-32).
      expect(confirm.prompts, 'the page raised exactly one prompt').toHaveLength(1);
      const [dismissed] = confirm.prompts;
      // The exact shipped template (ScheduledReportsPage.tsx:337), carrying THIS row's stored name.
      // If the app ever switched to an in-app modal there is no dialog and this line fails naming
      // exactly that — loud, never vacuous.
      expect(dismissed.type, 'the prompt is the browser-native confirm').toBe('confirm');
      expect(dismissed.message, 'the native prompt carries the row name').toBe(
        `Are you sure you want to delete "${storedName}"?`
      );
      const deletePath = `DELETE ${SCHEDULED_REPORTS_URL}/${id}`;
      expect(countOf(log, deletePath), 'a dismissed confirm sends no DELETE').toBe(0);
      await expect(row, 'the row survives a dismissed confirm').toBeVisible();
      expect(await scheduledReportIds(api), 'and the store still has it').toContain(id);

      // ---- ARM 2: accept. The only leg that touches the network. ----
      // EXACT list path: a detail GET shares the prefix but is a different apiPath, so this count
      // moves only when the LIST refetches — which is the whole repaint story on this page.
      const listGetsBefore = countOf(log, `GET ${SCHEDULED_REPORTS_URL}`);

      // Armed BEFORE THE CLICK: the handler calls accept() mid-click, so the DELETE is in flight
      // before this line could run any later (webhooks/delete.spec.ts:201-210).
      const deleted = page
        .waitForResponse(
          (r) =>
            apiPath(r.url()) === `${SCHEDULED_REPORTS_URL}/${id}` &&
            r.request().method() === 'DELETE'
        )
        .then((r) => r.status());

      confirm.setDecision('accept');
      await (await deleteButtonOf(page, id)).click();
      confirm.setDecision('dismiss');

      expect(confirm.prompts, 'the second attempt also prompted').toHaveLength(2);
      expect(confirm.prompts[1].message, 'the prompt is the same template the first time').toBe(
        `Are you sure you want to delete "${storedName}"?`
      );

      expect(await deleted, 'the accept DELETEs and answers 204').toBe(204);
      deletedThroughUi = true;

      // The row's removal is a refetch of ['scheduled-reports','list'], not a local splice
      // (useScheduledReports.ts:418-433; no optimistic path).
      await expect
        .poll(() => countOf(log, `GET ${SCHEDULED_REPORTS_URL}`) > listGetsBefore, {
          message: 'the list refetch is what removes the card',
        })
        .toBe(true);

      await expect(page.getByTestId(`report-card-${id}`), 'the card is gone').toHaveCount(0);
      expect(await scheduledReportIds(api), 'the store agrees').not.toContain(id);
    } finally {
      // No double-delete: the accept arm already removed the row, and deleteScheduledReport asserts
      // a 204 that a second call cannot return.
      if (id && !deletedThroughUi && (await scheduledReportIds(api)).includes(id)) {
        await deleteScheduledReport(api, id);
      }
    }

    expect(await scheduledReportIds(api), 'the stack is exactly as this spec found it').toEqual(
      before
    );
  });

  test('the guard survives the native-dialog drive', async ({ page }) => {
    const h = harness as Harness;
    await signIn(page, h);
    await page.goto(`${h.ui}/scheduled-reports`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('scheduled-reports-page')).toBeVisible();
    // Proves the dialog handler did not require — and does not license — any route interception:
    // the F2.1 tripwire still throws the same message (guard.ts:46).
    await assertGuardSurvives(page, h);
  });
});

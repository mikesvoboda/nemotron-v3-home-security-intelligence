/**
 * F2.3 DO-4 golden helpers for the `/scheduled-reports` batch (F-254, ruling 191).
 *
 * WHY THIS FILE IS NOT `webhooks/harness.ts` EDITED.
 * Ruling 87 scopes a package to its own files, and `webhooks/harness.ts` is F-245/247/248/249's
 * harness — the batch that recorded its own learnings in its header (no `page.route()`, the
 * created row is the fixture, exact-path matching). Editing that file to serve F-254 would make
 * my row's history live in another batch's file, and would let a F-254 edit break four rows that
 * already shipped. So the schedule-report helpers are a sibling here and only the *transport*
 * primitives are shared: this file re-exports the session and fetch helpers the webhooks harness
 * already proved, because they are stack plumbing, not webhook domain logic. `adminSession` and
 * `login` are literally the harness contract in `readHarness()`/`FEATURE_CHECK_*` form; refactoring
 * them into a shared root harness would touch four other batches' imports for no behavior change,
 * which is a bigger decision than this package.
 *
 * The one place scheduled-reports genuinely differs from webhooks, and why the twin's helpers
 * could not be reused even if the file rule allowed it:
 *
 * - `createScheduledReport()` is the fixture, exactly as `createWebhook()` is F-248's: the fake
 *   stack seeds NO scheduled report (ruling 191 says no spec names the row, and there is no
 *   scheduled-report wiring in the fake harness either), so a row only exists because this spec
 *   POSTed it. That is also why the create body carries every field explicitly rather than leaning
 *   on defaults — see `createScheduledReport` for which fields the schema defaults and why a
 *   delete-row spec should not care.
 * - A scheduled report's id is an INTEGER (autoincrement primary key), not a webhook uuid, so the
 *   store snapshot is a set of numeric strings and the row id appears in a `data-testid`, not a
 *   route param type the browser cares about.
 */
import { expect } from '@playwright/test';
import {
  adminSession,
  apiPath,
  assertGuardSurvives,
  authedFetch,
  login,
  readHarness,
  type AuthedFetch,
  type Harness,
  type Session,
} from './harness';

export {
  adminSession,
  apiPath,
  assertGuardSurvives,
  authedFetch,
  login,
  readHarness,
  type AuthedFetch,
  type Harness,
  type Session,
};

/** The scheduled-reports collection. `/api/scheduled-reports` is the router prefix
 *  (`backend/api/routes/scheduled_reports.py:36`), mounted unprefixed on the app
 *  (`backend/main.py:1659`), so the exact path for a row is `/api/scheduled-reports/<id>`.
 *  It is a DIFFERENT path from the webhooks one in this very directory
 *  (`WEBHOOKS_URL = '/api/outbound-webhooks'`): a reader who assumes the directory names the API
 *  will match a matcher that can never fire. */
export const SCHEDULED_REPORTS_URL = '/api/scheduled-reports';

/** Create a scheduled report the real way — the route `ScheduledReportsPage`'s create modal posts
 *  to (`create_scheduled_report`, scheduled_reports.py:41, answers 201).
 *
 *  Required vs defaulted, read from `ScheduledReportCreate`
 *  (`backend/api/schemas/scheduled_report.py:90-150`): `name` (`...`, min_length 1) and
 *  `frequency` (`...`) are required; `hour` (8), `minute` (0), `timezone` ("UTC"), `format`
 *  (ReportFormat.PDF), `enabled` (True), `include_charts`/`include_event_details` (True) carry
 *  defaults, and `day_of_week`/`day_of_month` are None — with an after-validator that REQUIRES
 *  day_of_week for weekly and day_of_month for monthly (:174, :177).
 *
 *  `frequency: 'daily'` is therefore the smallest shape that passes that validator: a `weekly`
 *  fixture would 422 without a `day_of_week`, and a `monthly` one without a `day_of_month`. The
 *  row's own promise ("clicks Delete on a report and confirms") is about the DELETE, so the cadence
 *  is not what is under test — but `hour`/`minute`/`format`/`enabled` are set explicitly anyway,
 *  not taken from defaults, for the reason F-248's harness gives its own `enabled`/`max_retries`
 *  (webhooks/harness.ts:187-193): a spec must not depend on a default it did not read. */
export async function createScheduledReport(api: AuthedFetch, name: string): Promise<string> {
  const res = await api.send(SCHEDULED_REPORTS_URL, 'POST', {
    name,
    frequency: 'daily',
    hour: 8,
    minute: 0,
    timezone: 'UTC',
    format: 'pdf',
    enabled: true,
  });
  expect(res.status, 'the batch fixture creates its row (201)').toBe(201);
  const id = String(res.body?.id ?? '');
  expect(/^\d+$/.test(id), 'the create response carries an integer id').toBeTruthy();
  return id;
}

/** Teardown: `delete_scheduled_report` (scheduled_reports.py:343) answers 204 with no body
 *  (`status_code=HTTP_204_NO_CONTENT` at :342) after `db.delete` + `db.commit`. A teardown that
 *  asserts is a teardown that reports its own failure instead of hiding a leak. */
export async function deleteScheduledReport(api: AuthedFetch, id: string): Promise<void> {
  const res = await api.send(`${SCHEDULED_REPORTS_URL}/${id}`, 'DELETE');
  expect(res.status, 'teardown removes the row it created (204)').toBe(204);
}

/** Sorted id set of every scheduled report on the stack. `ScheduledReportListResponse`
 *  (scheduled_report.py:328) wraps the rows as `items` plus a `total`, so the parse reads `items`
 *  and falls back to a bare array defensively — the same shape tolerance webhookIds() keeps
 *  (webhooks/harness.ts:227-231), because "which key wraps the rows" is exactly the kind of detail
 *  a spec should not die on twice. The restore proof is SET EQUALITY against this snapshot (DO-2's
 *  rule, notify-access/quiet-hours.spec.ts:76-78): a stack that seeds a report later must not make
 *  this batch red, and "as I found it" is a stronger claim than "empty". */
export async function scheduledReportIds(api: AuthedFetch): Promise<string[]> {
  const res = await api.getJson(SCHEDULED_REPORTS_URL);
  expect(res.status, 'GET /api/scheduled-reports answers 200').toBe(200);
  const rows = Array.isArray(res.body?.items)
    ? res.body.items
    : Array.isArray(res.body)
      ? res.body
      : [];
  return rows.map((row: Record<string, unknown>) => String(row.id)).sort();
}

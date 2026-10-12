/**
 * F-089 (inventory 3.6): the Jobs page at /jobs — list, debounced search,
 * URL-synced filters, refresh, selection, and the "Stats" button.
 *
 * Mirrors follow the lane's observer idiom (F-184/OP-3): the numbers and
 * strings asserted here come from the /api/jobs/search body the PAGE itself
 * received (JobSearchService reads an in-memory JobTracker — two reads are two
 * moments if anything runs a job), never a node-side pre-read. The spec never
 * re-derives the SERVER's filter semantics — it proves the rendered list is
 * the page's own body, and that a filter made the body strictly smaller.
 *
 * What the live sweep at this head measured about each row clause:
 * - "searches by text" — works: /api/jobs/search?q=orphan returned 15 of 17
 *   (JobSearchService._matches_query scans job_type/error/message/result).
 * - "filters by status" — works: status is a real filter (status=failed -> 0,
 *   status=completed -> all).
 * - "and type (URL-synced)" — BREAKS at the wire, measured: the dropdown
 *   writes ?type= (JobsPage.tsx:121-138) and the client forwards
 *   type=<value> (api.ts:4078-4091), but the route declares the parameter as
 *   job_type WITHOUT an alias (jobs.py:296-299; contrast job_status, which
 *   carries alias="status"). FastAPI treats the unknown ?type= as absent:
 *   ?type=batch_audit returned all 17 jobs; ?job_type=batch_audit returned
 *   exactly the 2 batch_audit jobs. The clause is named in the row's demotion.
 * - "refreshes" — the Refresh button has aria-label="Refresh jobs" and calls
 *   refetchJobs; the observer proves the CLICK produced a new fetch.
 * - the row's standing evidence "The Stats button has no click handler" is
 *   pinned, not repaired: a click must change nothing (no fetch, no URL).
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  api,
  authPost,
  authPostOk,
  closedByGuard,
  loginAsAdmin,
  readOpsHarness,
  type OpsHarness,
  type Session,
} from '../operations/harness';

const harness = readOpsHarness();

interface SearchJob {
  job_id: string;
  job_type: string;
  status: string;
  progress: number;
  message: string | null;
  error?: string | null;
  result?: unknown;
}

interface SearchBody {
  data: SearchJob[];
  meta: { total: number | null };
  aggregations: { by_status: Record<string, number>; by_type: Record<string, number> };
}

interface JobBody extends SearchJob {
  created_at: string;
}

// JobsListItem/JobHeader's local formatJobType: capitalize first letter only.
function capType(t: string): string {
  return t.charAt(0).toUpperCase() + t.slice(1);
}

// The server's own text matcher (job_search_service.py:143-184) scans
// job_type, error, message and result — a string result, else the STRING
// VALUES of a dict result. Mirror that field set so "matches q" / "misses q"
// here can never disagree with what /api/jobs/search actually filters.
function searchableStrings(j: SearchJob): string[] {
  const out = [j.job_type, j.message ?? '', j.error ?? ''];
  if (typeof j.result === 'string') {
    out.push(j.result);
  } else if (j.result && typeof j.result === 'object') {
    for (const v of Object.values(j.result as Record<string, unknown>)) {
      if (typeof v === 'string') out.push(v);
    }
  }
  return out;
}

function matchesQuery(j: SearchJob, q: string): boolean {
  return searchableStrings(j).some((s) => s.toLowerCase().includes(q));
}

/**
 * Guarantee the tracker holds BOTH classes the q-mirror needs: >=1 job that
 * matches q="orphan" and >=1 whose searchable fields all miss it. A fresh CI
 * golden stack's tracker starts EMPTY (measured at 0438ea1b9: jobs-page saw
 * exactly 1 job — the dry-run seed job-detail-panel.spec.ts leaves behind,
 * which matches "orphan") — so the strictly-smaller precondition is
 * unsatisfiable there unless this spec seeds the missing class itself.
 *
 * Non-matching seed: POST /api/ai-audit/batch {limit:1} — the backend's own
 * batch-audit trigger (ai_audit.py:494-575, answers 202 and registers a job
 * on BOTH branches: create_job("batch_audit") even when no events match).
 * batch_audit's searchable fields never contain "orphan": job_type
 * "batch_audit", messages "Starting batch audit of N events..."/"Processing
 * event i of N"/"No events found matching criteria" (ai_audit.py:406,420,546),
 * a null-or-pipeline-error error, and an int-only result dict
 * (total/processed/failed_events, :470-477). It audits at most 1 event — the
 * same pipeline the AI Audit page's button drives — and the job must reach a
 * TERMINAL state before returning: the status=failed -> 0 leg below mirrors a
 * page body on a stack this spec seeded, so a still-running seed would break
 * it with a false 1.
 *
 * Matching seed (only if somehow absent): the panel spec's precedent —
 * dry-run orphan cleanup, deletes nothing, completes synchronously.
 */
async function ensureTwoJobClasses(
  h: OpsHarness,
  session: Session,
  body: SearchBody
): Promise<SearchBody> {
  const misses = (j: SearchJob) => !matchesQuery(j, 'orphan');
  if (!body.data.some((j) => !misses(j))) {
    // No orphan-matching job on this stack: dry-run orphan scan registers one.
    await authPost<unknown>(h, session, '/api/admin/cleanup/orphans?dry_run=true', {
      dry_run: true,
    });
  }
  if (!body.data.some(misses)) {
    // NO job misses q — the fresh-CI shape (every job is the bootstrap/panel
    // dry-run orphan_cleanup). Seed the batch_audit class.
    await authPostOk(h, session, '/api/ai-audit/batch', { limit: 1, force_reevaluate: false });
    // The audit runs in a FastAPI background task; wait until NO batch_audit
    // job is still active (terminal, so the failed->0 leg below is stable).
    const settle = Date.now() + 30_000;
    for (;;) {
      const audit = await api<SearchBody>(
        h,
        session,
        '/api/jobs/search?job_type=batch_audit&limit=50'
      );
      if (audit.data.every((j) => j.status !== 'running' && j.status !== 'pending')) break;
      if (Date.now() > settle) throw new Error('seeded batch_audit job never reached terminal');
      await new Promise((r) => setTimeout(r, 1_000));
    }
  }
  // Poll until BOTH classes are visible in one unfiltered read.
  const deadline = Date.now() + 20_000;
  for (;;) {
    const next = await api<SearchBody>(h, session, '/api/jobs/search?limit=50');
    const matchCount = next.data.filter((j) => !misses(j)).length;
    if (matchCount > 0 && matchCount < next.data.length) return next;
    if (Date.now() > deadline) {
      throw new Error(
        `jobs seed never produced both classes: ${next.data.length} jobs, ${matchCount} matching q`
      );
    }
    await new Promise((r) => setTimeout(r, 1_000));
  }
}

test.describe('golden path: jobs page list, search and URL filters @critical', () => {
  test.setTimeout(90_000);

  test('the jobs list mirrors the search API, text and status filters narrow it with the URL, refresh re-fetches, and Stats is pinned dead', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    // Backend leg: the search endpoint answers for an admin session and the
    // in-memory tracker has BOTH a q-matching and a q-missing job to render —
    // seeded node-side through the backend's own routes when the stack lacks
    // one (a FRESH CI golden stack's tracker holds only the panel spec's
    // dry-run cleanup job; measured at 0438ea1b9). `live` is that guaranteed
    // snapshot, read through the same endpoint the page uses.
    const preSeed = await api<SearchBody>(h, session, '/api/jobs/search?limit=50');
    const live = await ensureTwoJobClasses(h, session, preSeed);
    expect(live.data.length).toBeGreaterThan(0);

    const pageErrors: string[] = [];
    page.on('pageerror', (err) => pageErrors.push(String(err)));

    let searchRequests = 0;
    const searchBodies: Array<Promise<SearchBody | null>> = [];
    const detailBodies: Array<Promise<JobBody | null>> = [];
    page.on('response', (res) => {
      try {
        const url = new URL(res.url());
        const method = res.request().method();
        if (url.pathname === '/api/jobs/search' && method === 'GET') {
          searchRequests += 1;
          searchBodies.push(res.json().catch(() => null));
        } else if (method === 'GET' && /^\/api\/jobs\/[0-9a-fA-F-]+$/.test(url.pathname)) {
          detailBodies.push(res.json().catch(() => null));
        }
      } catch {
        /* non-URL-ish response — not our endpoint */
      }
    });

    // URL-synced entry (the row's "URL-synced" clause on arrival): the page
    // reads ?q= off the location and debounces it into the query (300 ms,
    // JobsPage.tsx:60). The q is chosen from the LIVE sweep so it must match
    // at least one job and exclude at least one — the assert below is
    // strictly-smaller, so no server-semantics re-derivation. Matching uses
    // the server's own searchable-field set (job_search_service.py:143-184).
    const q = 'orphan';
    const wouldMatch = live.data.filter((j) => matchesQuery(j, q));
    expect(wouldMatch.length).toBeGreaterThan(0);
    expect(wouldMatch.length).toBeLessThan(live.data.length);

    const atBoot = searchRequests;
    await page.goto(`${h.ui}/jobs?q=${q}`, { waitUntil: 'domcontentloaded' });
    // Wait on the observer COUNTER first (jobs-page's own idiom, mirrored
    // from trash-restore's atSeed): polling the body-value alone would exit
    // on whatever the "no body yet" sentinel happens to satisfy.
    await expect.poll(() => searchRequests).toBeGreaterThan(atBoot);
    // The mount fetch carries no q (state syncs urlQuery via effect AFTER the
    // first query build); the debounced follow-up does. Poll the NEWEST body
    // until it is the smaller, filtered set — "no body yet" returns
    // MAX_SAFE_INTEGER so it can never satisfy the strictly-smaller exit.
    await expect
      .poll(async () => {
        const body = (await searchBodies[searchBodies.length - 1]) as SearchBody | null;
        return body ? body.data.length : Number.MAX_SAFE_INTEGER;
      })
      .toBeLessThan(live.data.length);
    const searched = (await searchBodies[searchBodies.length - 1]) as SearchBody;
    expect(searched.data.length).toBeGreaterThan(0);
    expect(pageErrors).toEqual([]);

    // Page frame.
    await expect(page.getByRole('heading', { name: 'Jobs', exact: true })).toBeVisible();
    await expect(page.getByTestId('jobs-list')).toBeVisible();

    // The rendered list mirrors the page's own body, order for order (the
    // tracker's created_at desc pass-through — no pin on WHICH jobs, only
    // that every body row is a row and every row is a body row).
    const renderedIds = await page
      .getByTestId(/^job-item-/)
      .evaluateAll((els) =>
        els.map((e) => (e.getAttribute('data-testid') ?? '').replace('job-item-', ''))
      );
    expect(renderedIds).toEqual(searched.data.map((j) => j.job_id));

    // Item mirrors its API row: status word (rendered raw — CSS capitalize
    // does not change DOM text) and the capitalize-first job type. Measured
    // DOM text: "completed3 minutes agoOrphan_cleanup#74d762…" — the badge
    // and timestamp are adjacent siblings with NO separator node, so a \b
    // boundary after the status cannot exist (d|3 are both \w). The honest
    // form is the lane's own sibling rule: anchor the raw token at the
    // start of the item's text, where JobsListItem mounts the badge.
    const first = searched.data[0];
    const firstItem = page.getByTestId(`job-item-${first.job_id}`);
    await expect(firstItem).toContainText(new RegExp(`^${first.status}`));
    await expect(firstItem).toContainText(capType(first.job_type));

    // Status-bar count mirrors meta.total of the page's own response.
    // JobsSearchBar.tsx:209 renders "{total} {total === 1 ? 'job' : 'jobs'}"
    // — a fresh-CI-shaped filtered set of exactly 1 job says "1 job", so the
    // plural is derived from the mirrored total, not hard-coded.
    await expect(
      page
        .getByText(
          new RegExp(
            `^\\s*${searched.meta.total} ${searched.meta.total === 1 ? 'job' : 'jobs'}\\s*$`
          )
        )
        .first()
    ).toBeVisible();

    // Detail placeholder until something is selected.
    await expect(page.getByTestId('job-detail-panel')).toContainText(
      'Select a job to view details'
    );

    // "selects a job": clicking the row fires the page's own GET
    // /api/jobs/{id} (F-090's panel leg fills in from it).
    const atSelect = detailBodies.length;
    await firstItem.click();
    await expect.poll(() => detailBodies.length).toBeGreaterThan(atSelect);
    const detail = (await detailBodies[detailBodies.length - 1]) as JobBody;
    expect(detail.job_id).toBe(first.job_id);
    const panel = page.getByTestId('job-detail-panel');
    await expect(panel).toContainText(capType(detail.job_type));
    // Header badge: label + "(100%)" — the paren group is ONE template string
    // with a literal leading space, but keep \s* per the sibling-node rule.
    await expect(panel).toContainText(
      new RegExp(`${capType(detail.status)}\\s*\\(${detail.progress}%\\)`)
    );

    // "filters by status": the dropdown writes ?status= and the refetched
    // list narrows — mirrored from the page's own newest body.
    const atStatus = searchRequests;
    await page.selectOption('#jobs-status-filter', 'failed');
    await expect(page).toHaveURL(/status=failed/);
    await expect.poll(() => searchRequests).toBeGreaterThan(atStatus);
    await expect
      .poll(async () => {
        const body = (await searchBodies[searchBodies.length - 1]) as SearchBody | null;
        return body?.data.length;
      })
      .toBe(0);
    await expect(page.getByTestId('active-filters-indicator')).toBeVisible();
    await expect(page.getByText('No jobs match your search')).toBeVisible();
    // Back to completed so the next legs start from the full-status view.
    await page.selectOption('#jobs-status-filter', 'completed');
    await expect
      .poll(async () => {
        const body = (await searchBodies[searchBodies.length - 1]) as SearchBody | null;
        return body?.data.length ?? 0;
      })
      .toBeGreaterThan(0);

    // "and type (URL-synced)": the URL half works; the server half is the
    // measured no-op (header). Pin OBSERVED behavior: selecting a type leaves
    // the fetched set EXACTLY as wide as without it, while the parameter name
    // the route actually declares does filter (node proves the wire cause).
    const beforeType = (await searchBodies[searchBodies.length - 1]) as SearchBody;
    await page.selectOption('#jobs-type-filter', 'batch_audit');
    await expect(page).toHaveURL(/type=batch_audit/);
    await expect
      .poll(async () => {
        const body = (await searchBodies[searchBodies.length - 1]) as SearchBody | null;
        return body?.data.length;
      })
      .toBe(beforeType.data.length);
    // The wire proof compares like with like: the DECLARED parameter against
    // an unfiltered read at the same moment (beforeType is q- AND status-
    // filtered, so comparing against it compared two different filters — on a
    // fresh CI stack both sides were 1 and the strict form was unsatisfiable).
    // The tracker never prunes during a run (job_tracker.py: del appears only
    // in cleanup_completed_jobs, which no runtime path calls), so the
    // unfiltered set is a superset here, and the guaranteed orphan_cleanup job
    // makes the subset strict.
    const byName = await api<SearchBody>(
      h,
      session,
      '/api/jobs/search?job_type=batch_audit&limit=50'
    );
    const allNow = await api<SearchBody>(h, session, '/api/jobs/search?limit=50');
    expect(byName.data.every((j) => j.job_type === 'batch_audit')).toBeTruthy();
    expect(allNow.data.some((j) => j.job_type !== 'batch_audit')).toBeTruthy();
    expect(byName.data.length).toBeLessThan(allNow.data.length);
    await page.selectOption('#jobs-type-filter', '');

    // "refreshes": the Refresh button must produce a NEW fetch.
    const atRefresh = searchRequests;
    await page.getByRole('button', { name: 'Refresh jobs', exact: true }).click();
    await expect.poll(() => searchRequests, { timeout: 10_000 }).toBeGreaterThan(atRefresh);

    // The row's standing finding, pinned: "Stats" has no click handler
    // (JobsPage.tsx:179-185 renders aria-label="View stats" with no onClick).
    // A click must leave the fetch counter and the URL exactly where they are.
    const atStats = searchRequests;
    const urlBefore = page.url();
    await page.getByRole('button', { name: 'View stats', exact: true }).click();
    await page.waitForTimeout(500);
    expect(searchRequests).toBe(atStats);
    expect(page.url()).toBe(urlBefore);

    // Clear all strips every param: the bar unmounts and a fresh unfiltered
    // fetch went out whose set is at least as wide as the filtered one.
    const atClear = searchRequests;
    await page.getByRole('button', { name: 'Clear all', exact: true }).click();
    await expect(page).toHaveURL((u) => !u.search);
    await expect.poll(() => searchRequests).toBeGreaterThan(atClear);
    const cleared = (await searchBodies[searchBodies.length - 1]) as SearchBody;
    expect(cleared.data.length).toBeGreaterThanOrEqual(beforeType.data.length);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});

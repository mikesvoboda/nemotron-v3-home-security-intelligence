/**
 * F-090 (inventory 3.6): the job detail panel at /jobs — header, progress,
 * metadata and result JSON mirrored from the page's own GET /api/jobs/{id}.
 *
 * The row's chain is GET /api/jobs/{job_id} -> get_job_status (jobs.py:455)
 * -> JobTracker. On a live stack the tracker is in-memory and busy — the
 * sweep carried 17 completed jobs from this stack's own probes — so a spec
 * that pre-reads a job and later clicks it races the list it came from. The
 * lane's observer idiom decides the shape instead: click the FIRST rendered
 * row of the page's own (unfiltered) list body, capture the detail response
 * the click itself triggers, and mirror every panel number off that body.
 *
 * CI determinism: a fresh golden stack's tracker may hold zero jobs, so the
 * spec guarantees one exists via POST /api/admin/cleanup/orphans dry_run=true
 * — the same admin-gated, non-deleting call OP-3's admin-orphan-cleanup spec
 * proves through the UI, issued here node-side (F-089 seeds through system's
 * own route, not this spec's subject chain; the seeded job's TYPE is not
 * assumed anywhere — mirrors read whatever first row comes back).
 *
 * Error/View-Details clauses: the sweep's tracker had ZERO failed jobs
 * (status=failed -> 0 measured), and faking one would mean writing store
 * state no real caller produced; the row's named clauses — header, progress,
 * metadata, result JSON — all prove green on the completed row, so the row
 * keeps unverified with this citation and the green-path note says exactly
 * which clause the golden path covers. The error branch additionally pins
 * count 0 for a job whose API error is null, so the branch is observed, not
 * absent.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  api,
  authPost,
  closedByGuard,
  loginAsAdmin,
  readOpsHarness,
  type OpsHarness,
  type Session,
} from '../operations/harness';

const harness = readOpsHarness();

interface SearchBody {
  data: Array<{ job_id: string }>;
  meta: { total: number | null };
}

interface JobBody {
  job_id: string;
  job_type: string;
  status: string;
  progress: number;
  message: string | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  result: unknown;
}

// JobHeader.tsx getStatusConfig (labels run raw status capitalized: completed
// -> "Completed", running -> "Running") and the local formatJobType.
function capWord(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** Guarantee a tracker job exists; returns once search shows >= 1. */
async function ensureJobExists(h: OpsHarness, session: Session): Promise<void> {
  let body = await api<SearchBody>(h, session, '/api/jobs/search?limit=50');
  if (body.data.length > 0) return;
  // Dry-run orphan scan: creates an orphan_cleanup job, deletes nothing.
  await authPost<unknown>(h, session, '/api/admin/cleanup/orphans?dry_run=true', {
    dry_run: true,
  });
  const deadline = Date.now() + 20_000;
  for (;;) {
    body = await api<SearchBody>(h, session, '/api/jobs/search?limit=50');
    if (body.data.length > 0) return;
    if (Date.now() > deadline) throw new Error('seeded cleanup job never appeared in search');
    await new Promise((r) => setTimeout(r, 1_000));
  }
}

test.describe('golden path: job detail panel mirrors GET /api/jobs/{id} @critical', () => {
  test.setTimeout(90_000);

  test('selecting a job renders its header, progress, metadata and result JSON from the detail response', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    await ensureJobExists(h, session);
    // Backend leg independent of the page: the detail route answers.
    const probe = await api<SearchBody>(h, session, '/api/jobs/search?limit=50');
    await api<JobBody>(h, session, `/api/jobs/${probe.data[0].job_id}`);

    const pageErrors: string[] = [];
    page.on('pageerror', (err) => pageErrors.push(String(err)));

    const listBodies: Array<Promise<SearchBody | null>> = [];
    const detailBodies: Array<Promise<JobBody | null>> = [];
    page.on('response', (res) => {
      try {
        const url = new URL(res.url());
        const method = res.request().method();
        if (url.pathname === '/api/jobs/search' && method === 'GET') {
          listBodies.push(res.json().catch(() => null));
        } else if (method === 'GET' && /^\/api\/jobs\/[0-9a-fA-F-]+$/.test(url.pathname)) {
          detailBodies.push(res.json().catch(() => null));
        }
      } catch {
        /* non-URL-ish response — not our endpoint */
      }
    });

    const atBoot = listBodies.length;
    await page.goto(`${h.ui}/jobs`, { waitUntil: 'domcontentloaded' });
    await expect.poll(() => listBodies.length).toBeGreaterThan(atBoot);
    const listBody = (await listBodies[listBodies.length - 1]) as SearchBody;
    expect(listBody.data.length).toBeGreaterThan(0);
    expect(pageErrors).toEqual([]);

    // Placeholder BEFORE any selection (the panel's own no-job state).
    const panel = page.getByTestId('job-detail-panel');
    await expect(panel).toBeVisible();
    await expect(panel).toContainText('Select a job to view details');

    // Click the first row; the click fires the page's detail fetch, and THAT
    // body is the mirror source (jobs-page.spec.ts:49 route pattern).
    const firstId = listBody.data[0].job_id;
    const atDetail = detailBodies.length;
    await page.getByTestId(`job-item-${firstId}`).click();
    await expect.poll(() => detailBodies.length).toBeGreaterThan(atDetail);
    const job = (await detailBodies[detailBodies.length - 1]) as JobBody;
    expect(job.job_id).toBe(firstId);

    // Header mirrors: type label and the status badge "Completed (100%)".
    // The "(100%)" rides the same span as the label with a literal space
    // (JobHeader.tsx:150), but sibling nodes taught the \s* rule — keep it.
    await expect(panel).toContainText(capWord(job.job_type));
    await expect(panel.getByTestId('status-badge')).toContainText(
      new RegExp(`${capWord(job.status)}\\s*\\(${job.progress}%\\)`)
    );
    // Progress bar: ARIA carries the API's own number (aria-valuenow).
    await expect(panel.locator('[role="progressbar"]')).toHaveAttribute(
      'aria-valuenow',
      String(job.progress)
    );

    // Metadata mirrors: Type repeats in the metadata block; the Completed row
    // renders only because the API's completed_at is non-null (branch pinned
    // from the body, not assumed).
    const meta = panel.getByTestId('job-metadata');
    await expect(meta.getByTestId('job-type')).toHaveText(capWord(job.job_type));
    if (job.status === 'completed' && job.completed_at) {
      await expect(meta.getByTestId('metadata-item-completed')).toBeVisible();
    }
    // Message renders raw from the body (JobMetadata message-section).
    if (job.message) {
      await expect(meta.getByTestId('message-section')).toContainText(job.message);
    }

    // Error branch observed-inactive for this job: null API error pins no
    // section (an error job on the tracker would flip this branch live —
    // header cites why none is manufactured).
    if (job.error === null) {
      await expect(panel.getByTestId('error-section')).toHaveCount(0);
      await expect(panel.getByTestId('view-error-details-button')).toHaveCount(0);
    }

    // Result JSON mirrors: <pre> renders JSON.stringify(job.result, null, 2)
    // (JobDetailPanel.tsx:260-266) — assert the panel text contains the exact
    // 2-space render the component produces for the API's own result object.
    if (job.result !== null && job.result !== undefined) {
      const rendered = JSON.stringify(job.result, null, 2);
      await expect(panel.locator('pre')).toContainText(rendered.slice(0, 40));
    }

    // Selecting a DIFFERENT job refetches and re-mirrors (selection is live,
    // not sticky): pick the last row if it differs from the first.
    if (listBody.data.length > 1) {
      const otherId = listBody.data[listBody.data.length - 1].job_id;
      const atOther = detailBodies.length;
      await page.getByTestId(`job-item-${otherId}`).click();
      await expect.poll(() => detailBodies.length).toBeGreaterThan(atOther);
      const other = (await detailBodies[detailBodies.length - 1]) as JobBody;
      expect(other.job_id).toBe(otherId);
      await expect(panel.getByTestId('status-badge')).toContainText(
        new RegExp(`${capWord(other.status)}\\s*\\(${other.progress}%\\)`)
      );
    }

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});

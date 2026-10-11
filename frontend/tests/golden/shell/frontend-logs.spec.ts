/**
 * Golden path: Boot › Frontend error and log reporting (inventory F-024).
 *
 * Row claim: "nothing visible: uncaught errors, error-boundary crashes and
 * client log/navigation events are sent to the backend" | `POST
 * /api/logs/frontend` and `POST /api/logs/frontend/batch` | `ingest_frontend_log`
 * backend/api/routes/logs.py:221, `ingest_frontend_logs_batch` :260 → Redis
 * rate-limit key → `frontend_logger.log` (:196) → structured log sink.
 *
 * TWO HANDLERS, TWO ENDPOINTS — THE CONTRACT THIS SPEC PINS
 *   The boot installs TWO independent global error paths, and they deliver
 *   through different endpoints with different timing:
 *     - services/errorReporting.ts, initialized first at src/main.tsx:15,
 *       addEventListener('error'/'unhandledrejection') (:274-275) → ONE fetch
 *       per event to the SINGLE endpoint (reportToBackend :111-126,
 *       config.endpoint :36), component 'error_reporting', plus a 10 s
 *       same-site dedup map (:37, :94-104 — measured: two identical throws
 *       produced exactly one POST).
 *     - services/logger.ts's module singleton (`export const logger = new
 *       Logger()`) assigns the window.onerror/onunhandledrejection PROPERTIES
 *       (:86, :98) — last-writer semantics, but nothing else ever assigns
 *       them (grep: these are the only two writers in src) — and queues every
 *       entry for a batched POST to the BATCH endpoint on a 5 s timer
 *       (defaultConfig :46-53, flush :171-192).
 *   One real uncaught exception therefore feeds BOTH, and this spec asserts
 *   both copies on the wire and the backend's answers to both endpoints.
 *
 * WHY THE STORE LEG READS MESSAGE TEXT (and only for one copy)
 *   On this stack the row's "structured log sink" is NOT Loki — no Loki
 *   service exists in docker-compose.ci/fake-ai — but it is not unreachable
 *   either: core/logging.py:699 DatabaseHandler mirrors every root-logger
 *   record into the Postgres `logs` table, which GET /api/logs (logs.py:330,
 *   session-auth) pages over. Measured here (probe3, 2026-10-11): the
 *   errorReporting copy lands as exactly one row —
 *     level=ERROR, component='frontend', message='[error_reporting] Uncaught
 *     Error: <mark>'
 *   — and that row is the store oracle, matched on a per-run marker inside
 *   the message text, because the message is the ONLY durable channel:
 *     (1) component column = record.name, so it is the backend logger's name
 *         ('frontend'), never the entry's own component (logging.py:795) — the
 *         entry's component survives only as the "[component] " prefix the
 *         route builds into the message (routes/logs.py:198);
 *     (2) the frontend's rich payload never reaches the DB at all, and the
 *         SINK drops it, not validation: the schema accepts the app's `extra`
 *         key outright (`context = Field(None, alias="extra")` +
 *         `populate_by_name=True`, schemas/logs.py:85,:93 — the docstring at
 *         :73 says "renamed from 'extra'", which is a name note, not a
 *         rejection). The route flattens url/user_agent/context onto the LOG
 *         RECORD as attributes (`frontend_*`, `ctx_<key>`, carried by logging's
 *         own extra= kwarg, logs.py:130-199), but DatabaseHandler.emit
 *         persists only a five-key whitelist (camera_id/event_id/detection_id/
 *         duration_ms/file_path) plus a `record.extra` attribute this route
 *         never sets (:782-790) — so every frontend-specific attribute falls on
 *         the floor. The logger copy is worse: its mark
 *         lives in extra.message, so the batch entry is wire-visible but
 *         DB-invisible (measured: DB search for the rejection's mark → none).
 *     (3) level gates what lands at all: root log_level on this stack is
 *         WARNING (authoritative read inside the container: log_level=WARNING,
 *         log_db_enabled=True, log_db_min_level=DEBUG — and the DB handler's
 *         effective gate is the ROOT level, setup_logging :907), so INFO/DEBUG
 *         entries are dropped by the DB sink: a batch answered 200
 *         {"count":2} for one INFO + one WARNING, and only the WARNING row
 *         appeared (measured). That is why the navigation leg — an INFO
 *         user_event — is wire-only, and why this spec asserts its landing
 *         nowhere. (The DEBUG rows sitting in the table are residue from an
 *         earlier DEBUG-level run of the same volume, not a contradiction.)
 *
 * WHAT WAS MEASURED BEFORE WRITING (probes on the lane stack, 2026-10-11;
 * reproducible via frontend/.r55-probes/f024-probe*.mjs, untracked)
 *   probe1 (anonymous /login boot): marked throw → single POST at +45 ms,
 *   component=error_reporting, extra.type=uncaught_exception; identical throw
 *   1 s later → still ONE POST (frontend dedup works); rejection via a promise
 *   RETURNED from evaluate → zero posts — a harness bug (Playwright awaits the
 *   returned promise, which makes it HANDLED; probe2/3 drop it inside a timer
 *   callback instead).
 *   probe2 + probe3 (authed boot of a never-booted path): one flush cycle
 *   carried BOTH global-handler ERROR entries on the batch endpoint (count=7,
 *   alongside the WebSocketManager chatter that a logged-in dashboard
 *   generates on its own); both endpoints answered 200 with
 *   {"success":true,"count":N}; the rejection's single POST always carries
 *   message "Unknown error" — but NOT because handleRejection reads a missing
 *   event.message (it reads event.reason, errorReporting.ts:186): it builds its
 *   errorData WITHOUT a message key (:223-229), so reportToBackend's
 *   `message: errorData.message || 'Unknown error'` fallback (:119) fires; the
 *   reason rides in extra.reason only, hence no DB oracle for it); the NotFound
 *   page's "Return to Dashboard" button (src/pages/NotFoundPage.tsx:30-44,
 *   useNavigate('/')) produced the navigation batch entry
 *     level=INFO component=user_event message=navigation
 *     extra={"from":"/golden-f024-p3-<ts>","to":"/","url":…}
 *   at +5 s (the flush timer; +1.2 s saw nothing) — first render deliberately
 *   unlogged (NavigationTracker.tsx:33-36).
 *
 * WHAT IS DELIBERATELY NOT ASSERTED, WITH THE MEASURED REASON
 *   - The ErrorBoundary retry screen: it has NO interception-free trigger on
 *     this product. App.tsx:225-228 mounts the boundary (title "Application
 *     Error") around every route; there are no /:param routes and no
 *     useParams page (grep), the two localStorage JSON.parse sites are
 *     try/catch-guarded (Sidebar.tsx:14-17, :165-168), corrupted zustand
 *     blobs boot clean (probe1 LEG5: role=alert=0, app renders), and
 *     ChunkLoadErrorBoundary only catches module-fetch failures (its
 *     isChunkLoadError patterns, :41-55), which a real failure needs a
 *     route.intercept to fake — forbidden here. Asserting it would mean
 *     manufacturing the crash; its contract stays with the vitest unit suite
 *     (components/common/ErrorBoundary.test.tsx) until a URL-reachable throw
 *     exists. The row's "error-boundary crashes" clause thus stays unverified
 *     at the golden tier — recorded so, not papered over (ruling 86).
 *   - The rejection's store side (measured above) and every INFO/DEBUG entry
 *     (level gate). `works` on the row waits on the real tier (ruling 66).
 *
 * Throttle discipline: boots go through quietBoot (nginx /api burst, see
 * harness.ts); the backend rate-limit tier is 60 req/min/IP
 * (routes/logs.py:80-ish _logging_rate_limiter) and this spec's few POSTs ride
 * inside it. /api/logs reads are Node-side with a real admin session, like
 * every backend-state read in this lane.
 */
import type { Page, Request, Response } from '@playwright/test';

import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  adminSession,
  api,
  closedByGuard,
  quietBoot,
  readShellHarness,
  seedTourDismissed,
  type Session,
  type ShellHarness,
} from './harness';

const harness = readShellHarness();

/** The app's own batch body shape (services/logger.ts flush :183-191). */
interface WireEntry {
  level: string;
  component: string;
  message: string;
  extra?: Record<string, unknown> & { message?: string; from?: string; to?: string };
  timestamp?: string;
}
interface WireBody {
  entries?: WireEntry[];
  level?: string;
  component?: string;
  message?: string;
  extra?: Record<string, unknown> & { type?: string; url?: string; reason?: string };
}

/** The backend's answer to both ingest endpoints (schemas/logs.py:151-162). */
interface IngestResponse {
  success: boolean;
  count: number;
  message: string | null;
}

/** A page from GET /api/logs (routes/logs.py:330, LogsListResponse). */
interface LogsPage {
  items: { id: number; level: string; component: string; message: string }[];
}

interface Post {
  url: string;
  body: string;
  status: number | null;
  json: IngestResponse | null;
}

/** Observe the app's own log POSTs passively; responses pair by Request. */
function watchLogPosts(page: Page): Post[] {
  const posts: Post[] = [];
  const byRequest = new Map<Request, Post>();
  page.on('request', (req) => {
    if (req.method() === 'POST' && req.url().includes('/api/logs/')) {
      const entry: Post = {
        url: req.url(),
        body: req.postData() ?? '',
        status: null,
        json: null,
      };
      posts.push(entry);
      byRequest.set(req, entry);
    }
  });
  page.on('response', (res: Response) => {
    const entry = byRequest.get(res.request());
    if (!entry) return;
    entry.status = res.status();
    void res
      .json()
      .then((parsed: IngestResponse) => {
        entry.json = parsed;
      })
      .catch(() => {
        /* non-JSON answer: status remains the assertion target */
      });
  });
  return posts;
}

function parseBody(post: Post): WireBody {
  return JSON.parse(post.body) as WireBody;
}
function singles(posts: Post[]): Post[] {
  return posts.filter((p) => p.url.endsWith('/api/logs/frontend'));
}
function batchEntries(posts: Post[]): WireEntry[] {
  return posts
    .filter((p) => p.url.endsWith('/api/logs/frontend/batch'))
    .flatMap((p) => parseBody(p).entries ?? []);
}

/** Per-RUN unique marker and boot path (module scope, once at collection), so
 *  the DB read can never match a past run's residue and the navigation's
 *  extra.from belongs to this boot alone. */
const RUN_MARK = Date.now();
const MARK = `F024_UNCAUGHT_${RUN_MARK}`;
const MARK_REJECT = `F024_REJECT_${RUN_MARK}`;
const BOOT_PATH = `/golden-f024-${RUN_MARK}`;
const NAV_PATH = `/golden-f024-nav-${RUN_MARK}`;

/** Newest frontend ERROR row id, so the store leg only counts rows this test
 *  caused — /api/logs is shared and monotonically growing. */
async function errorWatermark(h: ShellHarness, session: Session): Promise<number> {
  const page = await api<LogsPage>(h, session, '/api/logs?component=frontend&level=ERROR&limit=1');
  return page.items[0]?.id ?? 0;
}
async function newErrorRows(h: ShellHarness, session: Session, watermark: number) {
  const page = await api<LogsPage>(
    h,
    session,
    '/api/logs?component=frontend&level=ERROR&limit=100'
  );
  return page.items.filter((r) => r.id > watermark);
}

/** Throw from a timer callback so the browser sees it uncaught; a promise
 *  RETURNED from evaluate gets awaited by Playwright and counts as HANDLED
 *  (probe1 measured zero posts for that shape). */
function throwUncaught(page: Page, mark: string): Promise<unknown> {
  return page.evaluate((m) => {
    setTimeout(() => {
      throw new Error(m);
    }, 0);
  }, mark);
}
function rejectUnhandled(page: Page, mark: string): Promise<unknown> {
  return page.evaluate((m) => {
    setTimeout(() => {
      void Promise.reject(new Error(m));
    }, 0);
  }, mark);
}

test.describe('golden path: frontend error/log reporting → backend ingest @critical', () => {
  test.setTimeout(120_000);

  test('one real uncaught error and one real rejection reach BOTH global handlers — the errorReporting single POST and the logger batch — and the backend ingests both endpoints', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await adminSession(h);
    const watermark = await errorWatermark(h, session);

    await seedTourDismissed(page);
    const posts = watchLogPosts(page);
    await quietBoot(page, h, BOOT_PATH);
    await page.waitForLoadState('load');
    await page.waitForTimeout(1_000);

    await throwUncaught(page, MARK);
    // The rejection rides the same window and the same 5 s batch timer; the
    // frontend dedup keys on message+filename+lineno (errorReporting.ts:84-86)
    // so the two different events cannot suppress each other.
    await rejectUnhandled(page, MARK_REJECT);

    // Handler 1, immediate copy: errorReporting's single POST per event.
    await expect
      .poll(() => singles(posts).filter((p) => p.body.includes(MARK)).length, {
        message: 'errorReporting.ts must POST the uncaught error to /api/logs/frontend',
        timeout: 10_000,
      })
      .toBe(1);
    await expect
      .poll(() => singles(posts).filter((p) => p.body.includes(MARK_REJECT)).length, {
        message: 'errorReporting.ts must POST the unhandled rejection too',
        timeout: 10_000,
      })
      .toBe(1);

    const uncaughtPost = singles(posts).find((p) => p.body.includes(MARK))!;
    const rejectionPost = singles(posts).find((p) => p.body.includes(MARK_REJECT))!;
    const uncaught = parseBody(uncaughtPost);
    expect(uncaught.level).toBe('ERROR');
    expect(uncaught.component, 'errorReporting stamps its own component name').toBe(
      'error_reporting'
    );
    // event.message on an ErrorEvent is the browser's "Uncaught Error: …" text.
    expect(uncaught.message).toBe(`Uncaught Error: ${MARK}`);
    expect(uncaught.extra?.type).toBe('uncaught_exception');
    expect(uncaught.extra?.url, 'extra.url carries the boot path').toBe(h.ui + BOOT_PATH);

    // The rejection quirk, pinned as shipped (mechanism corrected per ops-b
    // for-the-record #1, 2026-10-11): handleRejection reads event.reason
    // (errorReporting.ts:186) and posts an errorData with NO message key
    // (:223-229), so the ingested message is reportToBackend's
    // `errorData.message || 'Unknown error'` fallback (:119) — and the reason
    // survives only in extra.reason, which the DB sink drops.
    const rejection = parseBody(rejectionPost);
    expect(rejection.extra?.type).toBe('unhandled_rejection');
    expect(String(rejection.extra?.reason)).toContain(MARK_REJECT);
    expect(rejection.message, 'measured: rejections ingest as "Unknown error"').toBe(
      'Unknown error'
    );

    // Handler 2, batched copy: logger singleton's window.onerror /
    // onunhandledrejection (logger.ts:86,:98) queue entries for the 5 s
    // flushIntervalMs timer (logger.ts:48) onto the BATCH endpoint.
    await expect
      .poll(
        () =>
          batchEntries(posts).some(
            (e) => e.message === 'Unhandled error' && String(e.extra?.message).includes(MARK)
          ),
        {
          message: 'logger.ts must batch the same error to /api/logs/frontend/batch',
          timeout: 12_000,
          intervals: [1_000],
        }
      )
      .toBe(true);
    const batchedError = batchEntries(posts).find(
      (e) => e.message === 'Unhandled error' && String(e.extra?.message).includes(MARK)
    )!;
    expect(batchedError.level).toBe('ERROR');
    expect(batchedError.component).toBe('frontend');
    expect(String(batchedError.extra?.url)).toBe(h.ui + BOOT_PATH);
    expect(
      batchEntries(posts).some(
        (e) =>
          e.message === 'Unhandled promise rejection' &&
          String(e.extra?.reason).includes(MARK_REJECT)
      ),
      'the rejection must ride the same batch bus'
    ).toBe(true);

    // Both endpoints' own answers to the requests this test just made.
    for (const post of [uncaughtPost, rejectionPost]) {
      expect(post.status, `${post.url} ingest status`).toBe(200);
      await expect
        .poll(() => post.json, { message: 'ingest response never parsed', timeout: 5_000 })
        .not.toBeNull();
      expect(post.json!.success).toBe(true);
      expect(post.json!.count).toBe(1);
      expect(post.json!.message).toBe('Successfully ingested 1 log entry');
    }

    // The store leg: the errorReporting copy lands in the queryable logs
    // table as one new ERROR row, message-bracketed by ITS component name
    // (core/logging.py:795 + routes/logs.py:198), with the marker in the only
    // durable channel there is.
    await expect
      .poll(
        async () =>
          (await newErrorRows(h, session, watermark)).filter((r) => r.message.includes(MARK))
            .length,
        {
          message: 'the ingested error must land as a [error_reporting] row on GET /api/logs',
          timeout: 15_000,
          intervals: [1_000],
        }
      )
      .toBe(1);
    const landed = (await newErrorRows(h, session, watermark)).find((r) =>
      r.message.includes(MARK)
    )!;
    expect(landed.message).toBe(`[error_reporting] Uncaught Error: ${MARK}`);
    expect(landed.component, 'component column carries the backend logger name').toBe('frontend');
    // The rejection landed too — as the fixed fallback text, which is why the
    // marker-match above finds exactly one row. Attribution note: that message
    // is not unique, so this reads as THIS test's row only because the golden
    // project runs one serial worker (playwright.config.ts:288-289) and the
    // watermark already excludes every older row.
    expect(
      (await newErrorRows(h, session, watermark)).some(
        (r) => r.message === '[error_reporting] Unknown error'
      ),
      'the rejection lands under its fallback message'
    ).toBe(true);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('a route change is tracked as a user_event navigation entry carrying the boot path in from', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;

    await seedTourDismissed(page);
    const posts = watchLogPosts(page);
    await quietBoot(page, h, NAV_PATH);
    await page.waitForLoadState('load');

    // The watermark goes DOWN before the navigation fires (ops-b blocker,
    // 2026-10-11): in the gate-open world the INFO row would land with an id
    // ABOVE this newest-ERROR watermark, so the absence check at the end has
    // a positive witness it could actually find. Watermarking after the
    // ingest poll (the previous shape) let ordinary ERROR churn pass the nav
    // row's id before the read — the some() could then never see the row it
    // claimed to hunt. Same pre-event shape as test 1's :261.
    const session = await adminSession(h);
    const watermark = await errorWatermark(h, session);

    // NavigationTracker skips the first render on purpose
    // (NavigationTracker.tsx:33-36), so a boot alone must produce no
    // navigation entry — this click is the first route change that counts.
    await page.locator('button', { hasText: 'Return to Dashboard' }).click();

    // The entry goes out on the logger's batch bus, which fires on the 5 s
    // timer (measured: absent at +1.2 s, present at +5 s).
    await expect
      .poll(
        () =>
          batchEntries(posts).find(
            (e) => e.message === 'navigation' && e.component === 'user_event'
          ),
        {
          message:
            'NavigationTracker must logger.navigate() onto /api/logs/frontend/batch within the 5 s flushIntervalMs (logger.ts:48)',
          timeout: 12_000,
          intervals: [1_000],
        }
      )
      .toBeDefined();
    const nav = batchEntries(posts).find(
      (e) => e.message === 'navigation' && e.component === 'user_event'
    )!;
    expect(nav.level, 'logger.event() logs at INFO').toBe('INFO');
    expect(nav.extra?.from, 'from = the path this boot started on').toBe(NAV_PATH);
    expect(nav.extra?.to).toBe('/');

    // The backend accepted the batch that carried it — the negative below
    // only means something once the ingest said yes.
    const navPost = posts.find(
      (p) => p.url.endsWith('/api/logs/frontend/batch') && p.body.includes('"navigation"')
    )!;
    await expect
      .poll(() => navPost.json?.success ?? false, {
        message: 'ingest_frontend_logs_batch must answer success for the navigation batch',
        timeout: 5_000,
      })
      .toBe(true);
    expect(navPost.status).toBe(200);
    expect(navPost.json!.count).toBeGreaterThan(0);

    // The INFO level gate, asserted as a measured negative (see header): the
    // DB sink is leveled at the root WARNING, so this entry — unlike the
    // ERROR legs — never lands in the queryable table. A row for it WOULD
    // read "[user_event] navigation" (routes/logs.py:193,198 build the
    // message as "[component] message" from the ENTRY's component), and its
    // id would be ABOVE the watermark taken before the click above.
    // Read the EXACT bucket the row would join (component=frontend comes from
    // record.name, so a landing navigation row would be level=INFO there):
    // newest frontend INFO rows. An unfiltered limit=100 window would sit
    // entirely above the watermark — ERROR churn alone exceeds 100 rows in the
    // window — and the some() would then be measuring WebSocket noise instead
    // of the absence it claims.
    await page.waitForTimeout(1_000);
    const asRow = (
      await api<LogsPage>(h, session, '/api/logs?component=frontend&level=INFO&limit=50')
    ).items.some((r) => r.id > watermark && r.message === '[user_event] navigation');
    expect(asRow, 'INFO navigation entries are dropped by the WARNING-leveled DB sink').toBe(false);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});

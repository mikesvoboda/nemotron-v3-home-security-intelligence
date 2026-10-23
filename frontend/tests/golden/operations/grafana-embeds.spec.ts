/**
 * F-164, F-165, F-166, F-167, F-169, F-174 (inventory 3.8): the six Grafana
 * dashboard embed pages in the operations area:
 *   - F-164 `/operations-dashboard` (uid `hsi-consolidated`)
 *   - F-165 `/gpu-metrics`          (uid `hsi-gpu-metrics`)
 *   - F-166 `/request-profiling`    (uid `hsi-request-profiling`)
 *   - F-167 `/tracing`              (uid `hsi-tracing`)
 *   - F-169 `/pyroscope`            (uid `hsi-profiling`)
 *   - F-174 `/logs`                 (uid `hsi-logs`)
 *
 * Each page fetches `GET /api/system/config` on mount, resolves `grafana_url`
 * through `resolveGrafanaUrl`, wires its header external link(s) and its
 * `<iframe>` src to the provisioned Grafana dashboard UID, and resets/restores
 * the iframe `src` when the user clicks Refresh.
 *
 * On the CI fake stack (`docker-compose.ci.yml`), no `grafana` service runs,
 * so `${h.ui}/grafana/api/health` answers 502 Bad Gateway through nginx while
 * the React page chrome, config binding, external links, Refresh action and
 * iframe URL contract all execute against the real backend. On the `O2.5`
 * production-shape real tier (`feature_check.py --real --prod-shape`, ruling
 * 144), Grafana runs behind `/grafana/` and the same spec also asserts the
 * live Grafana health and provisioned dashboard UID over the stack's proxy.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, apiCookie, closedByGuard, loginAsAdmin, readOpsHarness } from '../harness';

const harness = readOpsHarness();

interface SystemConfigBody {
  grafana_url?: string;
}

interface EmbedPageSpec {
  id: string;
  route: string;
  pageTestId: string;
  heading: string;
  iframeTestId: string;
  refreshTestId: string;
  errorTestId: string;
  grafanaLinkTestId: string;
  dashboardPath: string;
  uid: string;
  extraLinks?: Array<{ testId: string; hrefContains: string }>;
}

const EMBED_PAGES: readonly EmbedPageSpec[] = [
  {
    id: 'F-164',
    route: '/operations-dashboard',
    pageTestId: 'operations-dashboard-page',
    heading: 'Operations Dashboard',
    iframeTestId: 'operations-dashboard-iframe',
    refreshTestId: 'operations-dashboard-refresh-button',
    errorTestId: 'operations-dashboard-error',
    grafanaLinkTestId: 'operations-dashboard-external-link',
    dashboardPath: '/d/hsi-consolidated/home-security-intelligence-operations',
    uid: 'hsi-consolidated',
  },
  {
    id: 'F-165',
    route: '/gpu-metrics',
    pageTestId: 'gpu-metrics-page',
    heading: 'GPU Metrics',
    iframeTestId: 'gpu-metrics-iframe',
    refreshTestId: 'gpu-metrics-refresh-button',
    errorTestId: 'gpu-metrics-error',
    grafanaLinkTestId: 'gpu-metrics-external-link',
    dashboardPath: '/d/hsi-gpu-metrics/hsi-gpu-metrics',
    uid: 'hsi-gpu-metrics',
  },
  {
    id: 'F-166',
    route: '/request-profiling',
    pageTestId: 'request-profiling-page',
    heading: 'Request Profiling',
    iframeTestId: 'request-profiling-iframe',
    refreshTestId: 'request-profiling-refresh-button',
    errorTestId: 'request-profiling-error',
    grafanaLinkTestId: 'request-profiling-grafana-external-link',
    dashboardPath: '/d/hsi-request-profiling/hsi-request-profiling',
    uid: 'hsi-request-profiling',
  },
  {
    id: 'F-167',
    route: '/tracing',
    pageTestId: 'tracing-page',
    heading: 'Distributed Tracing',
    iframeTestId: 'tracing-iframe',
    refreshTestId: 'tracing-refresh-button',
    errorTestId: 'tracing-error',
    grafanaLinkTestId: 'grafana-external-link',
    dashboardPath: '/d/hsi-tracing/hsi-distributed-tracing',
    uid: 'hsi-tracing',
    extraLinks: [{ testId: 'jaeger-external-link', hrefContains: 'localhost:16686' }],
  },
  {
    id: 'F-169',
    route: '/pyroscope',
    pageTestId: 'pyroscope-page',
    heading: 'Profiling',
    iframeTestId: 'pyroscope-iframe',
    refreshTestId: 'pyroscope-refresh-button',
    errorTestId: 'pyroscope-error',
    grafanaLinkTestId: 'grafana-external-link',
    dashboardPath: '/d/hsi-profiling/hsi-profiling',
    uid: 'hsi-profiling',
    extraLinks: [
      { testId: 'explore-link', hrefContains: '/explore?orgId=1&theme=dark&left=' },
      { testId: 'pyroscope-external-link', hrefContains: 'localhost:4040' },
    ],
  },
  {
    id: 'F-174',
    route: '/logs',
    pageTestId: 'logs-page',
    heading: 'System Logs',
    iframeTestId: 'logs-iframe',
    refreshTestId: 'logs-refresh-button',
    errorTestId: 'logs-error',
    grafanaLinkTestId: 'grafana-external-link',
    dashboardPath: '/d/hsi-logs/hsi-system-logs',
    uid: 'hsi-logs',
    extraLinks: [{ testId: 'explore-external-link', hrefContains: '/explore?orgId=1&left=' }],
  },
];

test.describe('golden path: operations grafana embed pages (F-164..F-167, F-169, F-174) @critical', () => {
  test.setTimeout(90_000);

  for (const spec of EMBED_PAGES) {
    test(`${spec.id} ${spec.route} binds config.grafana_url, links, iframe and Refresh`, async ({
      page,
    }) => {
      test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
      if (!harness.ready) return;
      const h = harness;
      const session = await loginAsAdmin(page, h);

      // Backend leg: read grafana_url from GET /api/system/config.
      const cfg = await api<SystemConfigBody>(h, session, '/api/system/config');
      expect(typeof cfg.grafana_url).toBe('string');
      const expectedPrefix = cfg.grafana_url?.startsWith('/') ? cfg.grafana_url : '/grafana';

      // Probe whether Grafana is mounted behind nginx on this stack (502 on CI
      // --fake where grafana is absent; 200 on a --prod-shape run). The run's
      // harness file names the shape itself (FEATURE_CHECK_PROD_SHAPE=1, a
      // r323a-pinned env name), so the spec can branch on it: a prod-shape run
      // REQUIRES Grafana's health to answer 200 and each dashboard's uid to
      // come back — the two asserts a pass alone never showed — while the CI
      // fake tier keeps its 502 soft branch (no grafana service runs there).
      const prodShape = process.env.FEATURE_CHECK_PROD_SHAPE === '1';
      const grafanaHealth = await fetch(`${h.ui}/grafana/api/health`, {
        headers: apiCookie(session),
      }).catch(() => null);
      const dashRes = await fetch(`${h.ui}/grafana/api/dashboards/uid/${spec.uid}`, {
        headers: apiCookie(session),
      }).catch(() => null);
      if (prodShape) {
        expect(grafanaHealth?.status).toBe(200);
        expect(dashRes?.status).toBe(200);
        const dashBody = (await dashRes?.json()) as { dashboard?: { uid?: string } };
        expect(dashBody.dashboard?.uid).toBe(spec.uid);
      } else if (grafanaHealth && grafanaHealth.status === 200) {
        expect(dashRes?.status).toBe(200);
        const dashBody = (await dashRes?.json()) as { dashboard?: { uid?: string } };
        expect(dashBody.dashboard?.uid).toBe(spec.uid);
      }

      let configFetches = 0;
      page.on('response', (res) => {
        try {
          if (new URL(res.url()).pathname === '/api/system/config') configFetches += 1;
        } catch {
          /* ignore non-URL responses */
        }
      });

      await page.goto(`${h.ui}${spec.route}`, { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId(spec.pageTestId)).toBeVisible();
      await expect(page.getByRole('heading', { name: spec.heading, exact: true })).toBeVisible();
      await expect(page.getByTestId(spec.errorTestId)).toHaveCount(0);
      expect(configFetches).toBeGreaterThanOrEqual(1);

      const expectedIframeSrc = `${expectedPrefix}${spec.dashboardPath}?orgId=1&kiosk=1&theme=dark&refresh=30s`;
      const expectedExternalHref = `${expectedPrefix}${spec.dashboardPath}?orgId=1&theme=dark`;

      const iframe = page.getByTestId(spec.iframeTestId);
      await expect(iframe).toBeVisible();
      await expect(iframe).toHaveAttribute('src', expectedIframeSrc);

      const grafanaLink = page.getByTestId(spec.grafanaLinkTestId);
      await expect(grafanaLink).toBeVisible();
      await expect(grafanaLink).toHaveAttribute('href', expectedExternalHref);

      for (const extra of spec.extraLinks ?? []) {
        const link = page.getByTestId(extra.testId);
        await expect(link).toBeVisible();
        const href = await link.getAttribute('href');
        expect(href ?? '').toContain(extra.hrefContains);
      }

      // Refresh button reads the DOM property `iframeRef.current.src` (which
      // resolves the relative `/grafana/...` attribute against `h.ui`), blanks
      // it, and writes the resolved URL back into `src` after 100 ms — so the
      // attribute moving from `expectedIframeSrc` to `${h.ui}${expectedIframeSrc}`
      // directly witnesses `handleRefresh` executing.
      const refreshBtn = page.getByTestId(spec.refreshTestId);
      await expect(refreshBtn).toBeVisible();
      await expect(refreshBtn).toBeEnabled();
      await refreshBtn.click();
      await expect(refreshBtn).toBeEnabled({ timeout: 5_000 });
      await expect(iframe).toHaveAttribute('src', `${h.ui}${expectedIframeSrc}`);

      expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
    });
  }
});

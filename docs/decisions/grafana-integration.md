# Decision: Grafana Integration Strategy

**Date:** 2025-12-27
**Status:** Partly superseded (annotated 2026-10-02) — monitoring pages in the React app now embed Grafana dashboards directly (kiosk iframes built from `resolveGrafanaUrl`, e.g. `frontend/src/components/operations/GpuMetricsPage.tsx:130`, proxied at `/grafana/` per `frontend/nginx.conf:117`), so "link out, never embed" no longer describes the shipped UI (the CSP at `frontend/nginx.conf:117` documents `frame-src 'self'` as covering Grafana embeds through an nginx `/grafana/` proxy). Tremor remains the chart library for dashboard widgets (`@tremor/react`, `frontend/package.json:51`). The shipped Grafana runs with embedding allowed (`GF_SECURITY_ALLOW_EMBEDDING=true`) and anonymous access at `GF_AUTH_ANONYMOUS_ORG_ROLE=Admin` (`docker-compose.prod.yml`, `grafana` service) — the Viewer-role caution in Implementation Notes is the safer posture the compose does not take. _(Further annotated 2026-10-09, `O1.11`: that posture now holds whenever the box is exposed — with `EXPOSE_LAN=true` the anonymous Admin access is derived off and `/grafana/` sits behind the app login, arriving as Grafana `auth.proxy` with the Viewer role; the compose's `GF_AUTH_PROXY_AUTO_SIGN_UP_ORG_ROLE=Viewer` is exactly this caution made config. Unexposed, the anonymous Admin default stands — loopback is the boundary.)_ The AI stack this decision's metrics ride is two services, `ai-gateway` and `ai-vlm`; see `docs/architecture/ai-pipeline-current-state.md`.
**Related Beads:** 6fj, c3s

## Context

This project is a **local single-user deployment** for home security monitoring. We needed to decide how to display system metrics and whether/how to integrate Grafana into the dashboard.

## Decision Summary

1. **Use native Tremor charts** for dashboard metrics visualization (not Grafana embeds)
2. **Link to standalone Grafana** at `localhost:3002` for detailed metrics exploration

## Options Evaluated

### Bead 6fj: Embed Grafana vs Native Charts

| Option | Description                                       | Pros                                             | Cons                                                                   |
| ------ | ------------------------------------------------- | ------------------------------------------------ | ---------------------------------------------------------------------- |
| A      | iframe embed Grafana panels                       | Rich visualization, pre-built dashboards         | Auth complexity, CSP/X-Frame-Options issues, cross-origin challenges   |
| B      | Grafana public/snapshot dashboards                | Shareable, no auth for viewers                   | Requires Grafana Enterprise or public exposure, overkill for local use |
| C      | Pull Grafana-rendered images                      | Simple integration, no iframe issues             | Stale data, requires image generation API, polling overhead            |
| **D**  | **Native Tremor charts from backend metrics API** | **Simple, no auth, already in stack, real-time** | **Less feature-rich than Grafana**                                     |

**Decision: Option D - Native Tremor Charts**

### Bead c3s: Local Auth Strategy for Grafana

| Option                         | Description                         | Pros                               | Cons                                         |
| ------------------------------ | ----------------------------------- | ---------------------------------- | -------------------------------------------- |
| Anonymous mode                 | Enable anonymous access in Grafana  | Simple, no login required          | Security concern if exposed beyond localhost |
| Reverse proxy auth             | Auth at nginx/traefik level         | Single sign-on possible            | Complex setup, overkill for single-user      |
| API token + server-side render | Backend fetches panels with token   | Secure, controlled access          | Adds complexity, latency                     |
| **Minimal integration**        | **Just link to standalone Grafana** | **Simple, separation of concerns** | **User must navigate separately**            |

**Decision: Minimal Integration - Link to Standalone Grafana**

## Rationale

### Why Native Tremor Charts

1. **No additional auth complexity** - The dashboard already has no authentication (single-user local deployment). Adding Grafana embeds would require configuring anonymous mode, dealing with CORS, and potentially CSP headers.

2. **No CSP/iframe issues** - Embedding Grafana panels in iframes requires:

   - Setting `allow_embedding = true` in Grafana
   - Configuring `X-Frame-Options` header
   - Handling cross-origin cookie issues (SameSite)
   - Potential browser security warnings

3. **Tremor already in frontend stack** - The frontend uses React + Tremor for UI components. Tremor provides excellent chart components (LineChart, BarChart, AreaChart, DonutChart) that integrate seamlessly with React state management.

4. **Backend already has metrics endpoints** - The backend exposes metrics through existing API routes:

   - `/api/system/health` - System health status
   - `/api/system/gpu` - GPU metrics (utilization, memory, temperature)
   - Event and detection statistics

5. **Simpler deployment** - No need to configure Grafana data sources, dashboards, or authentication for the embedded use case.

### Why Link to Standalone Grafana

1. **Grafana remains valuable** - For detailed historical analysis, custom queries, and infrastructure monitoring, Grafana at `localhost:3002` provides superior capabilities.

2. **Separation of concerns** - The React dashboard focuses on security events and real-time monitoring. Grafana handles infrastructure metrics and long-term trends.

3. **Optional dependency** - Users who want detailed metrics can run Grafana. Users who just want security monitoring don't need it.

## Implementation Notes

### Dashboard Metrics (Native Tremor)

The dashboard will display key metrics using Tremor components:

```typescript
// Example: GPU utilization chart
import { AreaChart } from '@tremor/react';

<AreaChart
  data={gpuMetrics}
  index="timestamp"
  categories={["utilization", "memory_used"]}
  colors={["blue", "cyan"]}
/>
```

Metrics to display natively:

- GPU utilization and memory (from `/api/system/gpu`)
- Event counts by risk level (from `/api/events/stats`)
- Detection counts by object type
- System health indicators

### Grafana Link

Add a link in the dashboard settings or header:

```typescript
<a href="http://localhost:3002" target="_blank" rel="noopener">
  Open Grafana for detailed metrics
</a>
```

### Grafana Configuration (if used)

For users who want Grafana, the recommended configuration:

```ini
# grafana.ini
[auth.anonymous]
enabled = true
org_role = Viewer  # IMPORTANT: Never use Admin for anonymous access

[security]
allow_embedding = true
admin_user = admin
admin_password = <strong-password>  # Change before network exposure
```

**Security Notes:**

1. **Anonymous users must have Viewer role only** - Never set `org_role = Admin` for anonymous access as this allows anyone to modify dashboards, data sources, and settings.
2. **Enable login form** - Keep `disable_login_form = false` so administrators can log in to make changes.
3. **Set strong admin password** - Change the default `admin/admin` credentials via `GF_ADMIN_PASSWORD` environment variable before exposing to network.
4. **Localhost only** - Only enable anonymous mode for localhost access. Do not expose to network without proper authentication.

## Consequences

### Positive

- Simpler architecture
- Faster dashboard load times
- No cross-origin complications
- Easier to maintain and test

### Negative

- Less sophisticated charting than Grafana
- No built-in alerting through dashboard (Grafana has this)
- Users wanting detailed metrics must open separate Grafana window

### Neutral

- Grafana remains available for power users
- Backend metrics API serves both dashboard and Grafana data sources

## References

- [Tremor Charts Documentation](https://tremor.so/docs/components/area-chart)
- [Grafana Embedding Documentation](https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/#allow_embedding)

# Operations Components

## Purpose

Grafana-embedded monitoring pages. Each page is a thin React shell that resolves the Grafana base URL and iframes an existing dashboard — no charting code lives here.

## Key Files

| File                        | Purpose                                        | Grafana dashboard id       |
| --------------------------- | ---------------------------------------------- | -------------------------- |
| `index.ts`                  | Barrel for the three pages                     | —                          |
| `OperationsDashboardPage.tsx` | Consolidated operations / service health     | HSI Operations             |
| `GpuMetricsPage.tsx`        | GPU utilization, memory, temperature, power    | `hsi-gpu-metrics`          |
| `RequestProfilingPage.tsx`  | Request latency percentiles, slow queries      | HSI Request Profiling      |

## Related Files

| File                                  | Purpose                                            |
| ------------------------------------- | -------------------------------------------------- |
| `frontend/src/services/api.ts`        | `fetchConfig()` — source of `grafana_url`          |
| `frontend/src/utils/grafanaUrl.ts`    | `resolveGrafanaUrl()` — normalizes the configured URL |
| `frontend/src/App.tsx`                | Routes: `/operations-dashboard`, `/gpu-metrics`, `/request-profiling` (`/operations` is `SystemMonitoringPage` from `frontend/src/components/system/`) |

## Patterns

- **URL resolution:** `fetchConfig()` → `resolveGrafanaUrl()` → state, falling back to `/grafana` if config lacks `grafana_url` or the fetch fails. Do not hardcode a Grafana host in components.
- **Iframe refresh:** refresh buttons work by clearing and re-setting `iframe.src`; the dashboards load with `kiosk=1&theme=dark&refresh=30s`.
- **Dashboard URLs are built per page** — adding a page means a new `${grafanaUrl}/d/<id>/...` string, not a shared helper.

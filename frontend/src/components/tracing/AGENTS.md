# Distributed Tracing Components

## Overview

The tracing directory contains the distributed tracing visualization page. It embeds the
provisioned **HSI Distributed Tracing** Grafana dashboard (uid `hsi-tracing`,
`monitoring/grafana/dashboards/tracing.json`) in an iframe. Traces are collected by Alloy and
stored in **Tempo** (Jaeger was removed under NEM-5545 — there is no Jaeger container in
`docker-compose.prod.yml`).

> **Known dead affordance:** the header still renders an "Open Jaeger" button pointing at
> `http://localhost:16686`, which nothing serves in the current stack. It is a code-side
> follow-up (replace with an Open-Tempo / Grafana Explore link); this document describes it
> as-is, not as intended.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        YOUR APP                                 │
├─────────────────────────────────────────────────────────────────┤
│  Sidebar              │  TracingPage                            │
│  ───────              │  ───────────                            │
│  OPERATIONS           │  [Open in Grafana] [Open Jaeger*] [Refresh]
│  ├─ Jobs              │  ┌───────────────────────────────────┐  │
│  ├─ Pipeline          │  │  Grafana dashboard hsi-tracing    │  │
│  ├─ Tracing  ◄────────┼──│  (iframe, kiosk=1, theme=dark,    │  │
│  └─ Logs              │  │   refresh=30s)                    │  │
│                       │  └───────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                    │
              Grafana (:3002, /grafana proxy)
                    │ queries
        ┌───────────┴───────────┐
        ▼                       ▼
   Prometheus :9090        Tempo :3200  ◄── OTLP gRPC :4317 ◄── Alloy ◄── services
```

_\* renders but is dead — see Overview._

## Key Files

| File                   | Purpose                                                             |
| ---------------------- | ------------------------------------------------------------------- |
| `TracingPage.tsx`      | Main page component embedding the Grafana dashboard in an iframe    |
| `TracingPage.test.tsx` | Unit tests covering rendering, loading/error states, links, refresh |
| `index.ts`             | Barrel export for TracingPage component                             |

## Behavior (as implemented)

- **Config fetch**: on mount the page loads settings and reads `grafana_url`, resolved via
  `frontend/src/utils/grafanaUrl.ts`; on failure it shows an error banner and falls back to
  the `/grafana` path.
- **Dashboard URL**: `${grafanaUrl}/d/hsi-tracing/hsi-distributed-tracing?orgId=1&kiosk=1&theme=dark&refresh=30s`
  embedded as the iframe src; the "Open in Grafana" button links the same dashboard without
  `kiosk`.
- **Refresh**: clears and re-sets the iframe `src` (100 ms reattach delay) to force reload.
- **Loading state**: skeleton (`tracing-loading`) while config loads; error banner
  (`tracing-error`) if the config fetch fails.

Not implemented (older docs claimed these — they do not exist in the component):
view-mode toggles, Compare Traces / split view, span-click metric correlation panels.

## Testing

`TracingPage.test.tsx` asserts: title render, refresh button, both external links
(`grafana-external-link`, `jaeger-external-link` — the latter pinned until the button is
retargeted to Tempo), iframe presence, loading skeleton, config-failure error banner, and
default-URL fallback.

## Related Documentation

- `docs/ui/tracing.md` — user-facing tracing page guide (Tempo provisioning, ports)
- `monitoring/grafana/dashboards/tracing.json` — the embedded dashboard (uid `hsi-tracing`)

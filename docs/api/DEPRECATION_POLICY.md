---
title: API Deprecation Policy
description: Guidelines and process for deprecating API endpoints, including timelines, migration guides, and communication standards
source_refs:
  - docs/developer/api/README.md
  - docs/developer/contributing/README.md
  - backend/api/routes/system.py
---

# API Deprecation Policy

This document defines the standard process for deprecating API endpoints in the Home Security Intelligence system. Following a consistent deprecation policy ensures API consumers have adequate time to migrate while maintaining system reliability.

The policy has two halves. The **conventions** below (timeline, OpenAPI extension, migration-guide template) are the written standard a deprecation follows. The **mechanisms** section records what the backend actually executes today, so you know which checks are code and which are review discipline.

## Overview

API deprecation follows a structured timeline with clear communication at each phase. The goal is to provide API consumers with:

1. Early notice of upcoming changes
2. Clear migration paths to replacement APIs
3. Sufficient time to update integrations
4. Predictable and documented behavior during transitions

## Deprecation Timeline

All API deprecations follow a **90-day timeline** from announcement to removal:

```
Timeline:
  T-90 (Announcement) ─────┬──────────────────────────────────────────────┐
                           │                                              │
                           │  Phase 1: Announcement                       │
                           │  - Deprecation notice added to docs          │
                           │  - deprecated=True + x-deprecation in spec   │
                           │  - CHANGELOG entry created                   │
                           │  - Replacement API documented                │
                           │                                              │
  T-30 (Warning) ──────────┼──────────────────────────────────────────────┤
                           │                                              │
                           │  Phase 2: Active Warning                     │
                           │  - Deprecation + Sunset headers on responses │
                           │  - Response includes deprecation_warning     │
                           │  - Monitoring for deprecated endpoint usage  │
                           │                                              │
  T-0 (Removal) ───────────┼──────────────────────────────────────────────┘
                           │
                           │  Phase 3: Removal
                           │  - Endpoint removed from codebase
                           │  - Tombstone route returns 410 Gone
                           │  - OpenAPI spec updated
                           │  - CHANGELOG entry for removal
```

### Phase 1: Announcement (T-90)

**Actions required:**

| Action                                                  | Owner    | Location                   |
| ------------------------------------------------------- | -------- | -------------------------- |
| Add deprecation notice to endpoint documentation        | API Team | `docs/developer/api/*.md`  |
| Add `deprecated=True` and the `x-deprecation` extension | API Team | `backend/api/routes/*.py`  |
| Create CHANGELOG entry                                  | API Team | `CHANGELOG.md`             |
| Document replacement API                                | API Team | `docs/developer/api/*.md`  |
| Update migration guide                                  | API Team | `docs/api/migrations/*.md` |

### Phase 2: Active Warning (T-30)

**Actions required:**

| Action                                          | Owner    | Location               |
| ----------------------------------------------- | -------- | ---------------------- |
| Set `Deprecation` and `Sunset` headers          | API Team | Route handler          |
| Add `deprecation_warning` field to responses    | API Team | Response schema        |
| Enable monitoring for deprecated endpoint usage | DevOps   | Grafana dashboard      |
| Send notification to known API consumers        | API Team | Communication channels |

### Phase 3: Removal (T-0)

**Actions required:**

| Action                             | Owner    | Location                   |
| ---------------------------------- | -------- | -------------------------- |
| Remove endpoint from router        | API Team | `backend/api/routes/*.py`  |
| Remove associated schemas          | API Team | `backend/api/schemas/*.py` |
| Update OpenAPI spec                | API Team | Auto-generated             |
| Create CHANGELOG entry for removal | API Team | `CHANGELOG.md`             |
| Leave a 410 Gone tombstone         | API Team | Tombstone route            |

---

## OpenAPI Extension Format

Use `deprecated=True` on the route decorator plus an `x-deprecation` extension for machine-readable deprecation metadata in the generated OpenAPI specification.

The backend's generated spec is built from the FastAPI route metadata. `deprecated: true` is the
built-in key FastAPI emits; the `x-deprecation` object below is the project convention for the
dates and replacement path that ride beside it, and is supplied per route by the API Team as part
of Phase 1 — there is no framework or middleware filling it in for you.

### Schema Definition

```yaml
x-deprecation:
  deprecated: boolean # Required: true if endpoint is deprecated
  announced_at: string # Required: ISO 8601 date of announcement (T-90)
  warning_at: string # Required: ISO 8601 date warnings begin (T-30)
  removal_at: string # Required: ISO 8601 date of planned removal (T-0)
  replacement: string # Required: Path to replacement endpoint
  migration_guide: string # Optional: URL to migration documentation
  reason: string # Optional: Brief explanation of why deprecated
```

### FastAPI Implementation

Add deprecation metadata to route definitions using OpenAPI extensions:

```python
from fastapi import APIRouter

router = APIRouter()

# Deprecation metadata
WIDGETS_DEPRECATION = {
    "deprecated": True,
    "announced_at": "2026-04-01",
    "warning_at": "2026-05-01",
    "removal_at": "2026-07-01",
    "replacement": "/api/v2/widgets",
    "reason": "replaced by the v2 widgets API",
}


@router.get(
    "/widgets",
    deprecated=True,  # FastAPI built-in deprecation flag
    openapi_extra={"x-deprecation": WIDGETS_DEPRECATION},
    summary="List widgets (DEPRECATED)",
)
async def list_widgets():
    ...
```

### Generated OpenAPI Spec

The above implementation produces the following OpenAPI specification:

```json
{
  "paths": {
    "/api/widgets": {
      "get": {
        "summary": "List widgets (DEPRECATED)",
        "deprecated": true,
        "x-deprecation": {
          "deprecated": true,
          "announced_at": "2026-04-01",
          "warning_at": "2026-05-01",
          "removal_at": "2026-07-01",
          "replacement": "/api/v2/widgets",
          "reason": "replaced by the v2 widgets API"
        }
      }
    }
  }
}
```

---

## Deprecation Warning Response Headers

During Phase 2 (T-30 to T-0), deprecated endpoints include warning headers on every response.

### HTTP Headers

The backend emits the standard three-header set — `Deprecation`, `Sunset`, and `Link` — rather
than an invented `Deprecation-Warning` header, so consumers see one vocabulary across every
deprecated route:

```http
HTTP/1.1 200 OK
Deprecation: true
Sunset: 2026-07-01T00:00:00Z
Link: </api/v1/settings>; rel="successor-version"; title="Use /api/v1/settings for detection settings"
X-Deprecated-Message: detection_confidence_threshold is deprecated. Use /api/v1/settings detection.confidence_threshold instead.
Content-Type: application/json
```

| Header                 | Purpose                                                       |
| ---------------------- | ------------------------------------------------------------- |
| `Deprecation`          | Marks the response as coming from a deprecated feature        |
| `Sunset`               | Planned removal date (RFC 8594)                               |
| `Link`                 | Points to replacement endpoint with `rel="successor-version"` |
| `X-Deprecated-Message` | Human-readable explanation of what to move to                 |

The header-setting code is `set_deprecation_headers()` (`backend/api/pagination.py:421`) for
pagination deprecation, and inline `response.headers[...]` assignments in the handlers for
per-route deprecation — `get_config()` and `patch_config()`
(`backend/api/routes/system.py:2474`, `backend/api/routes/system.py:2590`) both set the four
headers above on every response.

The middleware counterpart — a `DeprecationLoggerMiddleware` that watches for the `Deprecation`
header, logs the caller, and adds an RFC 7234 `Warning` header — exists at
`backend/api/middleware/deprecation_logger.py:45` but is not in the app's middleware chain, so
nothing populates its counter from live traffic today.

### Response Body Field

List responses that carry a deprecated pagination mode include a `deprecation_warning` field:

```json
{
  "items": [],
  "pagination": {
    "total": 150,
    "limit": 50,
    "offset": 20,
    "cursor": null,
    "next_cursor": null,
    "has_more": true
  },
  "deprecation_warning": "Offset pagination is deprecated and will be removed in a future version. Please use cursor-based pagination instead by using the 'cursor' parameter with the 'next_cursor' value from the response."
}
```

The field is `None` whenever the client used a cursor or left `offset` at its default. The text
comes from `get_deprecation_warning()` (`backend/api/pagination.py:395`), and the four list
endpoints that populate it are listed in the next section.

---

## Mechanisms In The Running Backend

These are the deprecation behaviours the shipped code enforces. Everything else on this page is
convention that a reviewer has to check.

### Offset pagination is deprecated on four list endpoints

| Endpoint              | Handler           | Deprecation code                               |
| --------------------- | ----------------- | ---------------------------------------------- |
| `GET /api/events`     | `list_events`     | `backend/api/routes/events.py:525`, `:528`     |
| `GET /api/detections` | `list_detections` | `backend/api/routes/detections.py:323`, `:326` |
| `GET /api/audit`      | audit list        | `backend/api/routes/audit.py:178`, `:181`      |
| `GET /api/logs`       | logs list         | `backend/api/routes/logs.py:474`, `:477`       |

Each one calls `get_deprecation_warning()` to fill the `deprecation_warning` response field and
`set_deprecation_headers()` to set `Deprecation: true` plus `Sunset: 2026-06-01`. Both helpers
live in `backend/api/pagination.py`; the default sunset date is a parameter of
`set_deprecation_headers()` (`backend/api/pagination.py:425`), so the header is the single place
to change it. Passing both `cursor` and a non-zero `offset` is rejected outright rather than
silently preferring one (`backend/api/pagination.py:391`).

### Field-level deprecation

`ConfigResponse.detection_confidence_threshold` and
`ConfigUpdateRequest.detection_confidence_threshold` are declared with Pydantic's
`deprecated=True` (`backend/api/schemas/system.py:507`, `backend/api/schemas/system.py:579`), so
the field is marked deprecated in the generated JSON Schema as well as in the description text.

### Routes that carry deprecation signals

Two routes are deprecated in behaviour but still serve traffic; three have finished the timeline
and return 410. The column that matters for a spec reader is which signal each one actually
carries — a `deprecated=True` decorator is not the same thing as a handler that sets the headers:

| Route                                            | Signal carried today                                                                                                   | Location                                      |
| ------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| `GET /api/system/config`                         | Deprecation/Sunset/Link/`X-Deprecated-Message` headers + deprecated response field; the decorator itself is not marked | `backend/api/routes/system.py:2474`           |
| `PATCH /api/system/config`                       | Same header set + deprecated request field; decorator not marked                                                       | `backend/api/routes/system.py:2590`           |
| `POST /api/known-persons/{person_id}/embeddings` | `deprecated=True` decorator, returns 410 Gone                                                                          | `backend/api/routes/face_recognition.py:357`  |
| `POST /api/face-events/match`                    | `deprecated=True` decorator, returns 410 Gone                                                                          | `backend/api/routes/face_recognition.py:1333` |
| `POST /api/household-matcher/match-person`       | `deprecated=True` decorator, returns 410 Gone                                                                          | `backend/api/routes/household_matcher.py:86`  |

A new Phase-1 deprecation should carry both signals — the decorator flag so it is struck through
in the docs UI, and the headers so a live caller is warned — which is why the running
`/api/system/config` pair above is the shape you graduate _from_, not the target state.

### 410 Gone tombstones

Three endpoints have already completed the timeline and stand as tombstones. Each handler raises
`HTTPException(status_code=410)` unconditionally, declares the 410 in its `responses` map so the
contract appears in the OpenAPI spec, and names the sanctioned replacement in the detail string:

| Tombstone                                                                                       | Replacement named in the response                                                              |
| ----------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `POST /api/known-persons/{person_id}/embeddings` (`backend/api/routes/face_recognition.py:357`) | `enroll-from-detection` / `bulk-enroll` (`backend/api/routes/face_recognition.py:641`, `:868`) |
| `POST /api/face-events/match` (`backend/api/routes/face_recognition.py:1333`)                   | the pipeline's face leg, which computes the vector server-side                                 |
| `POST /api/household-matcher/match-person` (`backend/api/routes/household_matcher.py:86`)       | the pipeline's `person_reid` leg, or member enrollment                                         |

The shared reason: a vector the server did not compute carries no `model_id`, so it cannot be
trusted to live in the gallery's embedding space. See
[Face Recognition](../guides/face-recognition.md) for the provenance rule.

**Writing a tombstone:** keep the route registered, keep the request schema in place so the path
still appears in the spec, mark it `deprecated=True`, declare the 410 in `responses`, and make the
detail string name the replacement paths verbatim. Do not return a redirect and do not accept the
payload and discard it silently.

---

## CHANGELOG Format

Document all deprecations in the project CHANGELOG following the Keep a Changelog format.

### Deprecation Announcement (T-90)

```markdown
## [Unreleased]

### Deprecated

- **GET /api/system/config**: `detection_confidence_threshold` is deprecated in
  favor of `GET /api/v1/settings`.
  - Reason: detection settings moved to the dedicated settings API
  - Replacement: `GET /api/v1/settings`
  - Timeline: warnings begin 2026-06-01, removal 2026-07-01
```

### Active Warning Phase (T-30)

```markdown
## [Unreleased]

### Changed

- **GET /api/system/config**: Now returns `Deprecation`, `Sunset`, `Link` and
  `X-Deprecated-Message` headers. Scheduled for removal on 2026-07-01.
```

### Removal (T-0)

```markdown
## [Unreleased]

### Removed

- **POST /api/face-events/match**: Removed; the path now returns 410 Gone.
  Matching runs on the server-side face leg instead.
```

---

## Migration Guide Template

Create migration guides in `docs/api/migrations/` for each deprecated endpoint.

### File Naming Convention

```
docs/api/migrations/{resource}-v{old}-to-v{new}.md
```

The directory holds the migration guides themselves plus the schema migrations applied at
deployment time; see [migrations/README.md](migrations/README.md), whose index lists active
deprecations.

### Template

````markdown
---
title: Migrating <deprecated path> to <replacement path>
description: Step-by-step migration guide for <resource>
---

# <Resource> API Migration Guide

## Overview

| Attribute            | Value                        |
| -------------------- | ---------------------------- |
| Deprecated Endpoint  | `<METHOD /deprecated-path>`  |
| Replacement Endpoint | `<METHOD /replacement-path>` |
| Announcement Date    | YYYY-MM-DD                   |
| Warning Phase Begins | YYYY-MM-DD                   |
| Removal Date         | YYYY-MM-DD                   |
| Breaking Changes     | Yes / No                     |

## Summary of Changes

### New capabilities in the replacement

- <what the consumer gains>

### Breaking Changes

1. <response shape change>
2. <renamed field>
3. <removed parameter>

## Request Changes

### Deprecated request

```bash
GET /deprecated-path?limit=10&offset=20
```

### Replacement request

```bash
GET /replacement-path?limit=10&cursor=eyJpZCI6IDEwfQ==
```

### Query Parameter Mapping

| Old Parameter | New Parameter | Notes                             |
| ------------- | ------------- | --------------------------------- |
| `limit`       | `limit`       | No change                         |
| `offset`      | `cursor`      | Use cursor from previous response |

## Response Changes

### Deprecated response

```json
{
  "items": [],
  "count": 1
}
```

### Replacement response

The shipped list envelope is `{items, pagination}` — `pagination` carries
`total`, `limit`, `offset`, `cursor`, `next_cursor` and `has_more`
(`PaginationMeta`, `backend/api/schemas/pagination.py:36`). Use that shape in the example rather
than inventing a `data` key.

```json
{
  "items": [],
  "pagination": {
    "total": 1,
    "limit": 10,
    "offset": null,
    "cursor": null,
    "next_cursor": null,
    "has_more": false
  }
}
```

### Response Field Mapping

| Old Field | New Field             | Notes                      |
| --------- | --------------------- | -------------------------- |
| `count`   | `pagination.total`    | Moved to pagination object |
| -         | `pagination.has_more` | New                        |

## Code Migration Steps

### Python Example

#### Before

```python
import requests

def fetch_all(session):
    rows = []
    offset = 0
    limit = 100
    while True:
        response = session.get(
            "http://localhost:8000/api/events",
            params={"limit": limit, "offset": offset},
        )
        data = response.json()
        rows.extend(data["items"])
        if not data["pagination"]["has_more"]:
            break
        offset += limit
    return rows
```

#### After

```python
import requests

def fetch_all(session):
    rows = []
    cursor = None
    while True:
        params = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        response = session.get(
            "http://localhost:8000/api/events", params=params
        )
        data = response.json()
        rows.extend(data["items"])
        cursor = data["pagination"]["next_cursor"]
        if not cursor:
            break
    return rows
```

### TypeScript Example

#### Before

```typescript
async function fetchAll(offset = 0): Promise<Event[]> {
  const params = new URLSearchParams({ limit: '100', offset: String(offset) });
  const response = await fetch(`/api/events?${params}`);
  const data = await response.json();
  return data.items;
}
```

#### After

```typescript
async function fetchAll(): Promise<Event[]> {
  const rows: Event[] = [];
  let cursor: string | null = null;

  do {
    const params = new URLSearchParams({ limit: '100' });
    if (cursor) params.set('cursor', cursor);

    const response = await fetch(`/api/events?${params}`);
    const data = await response.json();

    rows.push(...data.items);
    cursor = data.pagination.next_cursor;
  } while (cursor);

  return rows;
}
```

## Testing Your Migration

1. **Update API client code** following the examples above
2. **Run your test suite** to catch any missed field references
3. **Test pagination** by verifying cursor-based iteration works correctly
4. **Verify field mappings** especially renamed fields
5. **Test edge cases** like empty results and single-page results

## Support

If you encounter issues during migration:

- Review this guide for common field mapping changes
- Check the [API Reference](../developer/api/core-resources.md) for complete documentation
- Open a GitHub issue with the `api-migration` label

## Timeline Reminder

Fill this table with the real dates from the CHANGELOG entry; never leave sample dates in a
published guide.

| Date       | Event                 |
| ---------- | --------------------- |
| YYYY-MM-DD | Deprecation announced |
| YYYY-MM-DD | Warning headers begin |
| YYYY-MM-DD | Endpoint removed      |
````

---

## Monitoring Deprecated Endpoints

Track usage of deprecated endpoints to ensure consumers migrate before removal.

### Measuring usage today

Every HTTP route is already instrumented. `http_request_duration_seconds` is a Histogram with
labels `method`, `handler`, `status` and `http_route`
(`backend/api/middleware/prometheus.py:64`), and it is observed by the observability middleware
that is actually in the app's chain (`backend/api/middleware/observability.py:282`). Prometheus
scrapes it from `backend:8000` under the `hsi-backend-metrics` job
(`monitoring/prometheus.yml:61`). Unmatched paths are collapsed to a single pattern rather than
exported raw, so a deprecated route you have already deregistered shows up as the unmatched
pattern, not under its own path.

So the honest way to watch a deprecated endpoint's traffic is by `handler`:

```promql
# Request rate for a deprecated handler
sum by (http_route) (
  rate(http_request_duration_seconds_count{job="hsi-backend-metrics", handler="get_config"}[5m])
)

# How often the deprecated offset pagination path is taken
sum (
  rate(http_request_duration_seconds_count{
    job="hsi-backend-metrics", handler=~"list_events|list_detections"
  }[5m])
)
```

### The dedicated counter

`backend/api/middleware/deprecation_logger.py:38` defines

```python
DEPRECATED_CALLS_TOTAL = Counter(
    "hsi_api_deprecated_calls_total",
    "Total calls to deprecated API endpoints",
    labelnames=["endpoint", "client_id"],
)
```

`endpoint` and `client_id` are the labels, sanitised and length-capped before use. The counter is
wired into the "API Deprecation Tracking" panels of the API health dashboard
(`monitoring/grafana/dashboards/api-health.json:342`), and a `prometheus_client` Counter is
exported at zero even before its first `.labels()` call, so those panels read 0 rather than
"No data" — which is exactly why a 0 there is not yet proof anyone stopped calling the endpoint.

Two conditions have to hold before traffic reaches it: `DeprecationLoggerMiddleware` must be in
the app's middleware chain (it is not; see
[HTTP Headers](#http-headers)), and no route handler currently calls the
`record_deprecated_call()` helper directly. Until one of those changes, treat this counter as the
placement for a metric that live traffic does not yet feed, and use the `handler`-based queries
above for real migration tracking. If you add a deprecation that needs caller-attributed tracking,
re-register the middleware in `backend/main.py` and confirm the panel moves before relying on it.

### Alert Rule

```yaml
groups:
  - name: api_deprecation
    rules:
      - alert: DeprecatedEndpointStillInUse
        expr: >
          sum by (handler) (
            rate(http_request_duration_seconds_count{
              job="hsi-backend-metrics", handler=~"get_config|patch_config"
            }[24h])
          ) > 0
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: 'Deprecated handler {{ $labels.handler }} still receiving traffic'
          description: >
            The deprecated handler {{ $labels.handler }} served requests in the last
            24 hours. Confirm usage has dropped before removing it.
```

---

## Communication Checklist

Use this checklist when deprecating an endpoint:

### T-90 (Announcement)

- [ ] Created deprecation entry in CHANGELOG
- [ ] Added `deprecated=True` to route decorator
- [ ] Added `x-deprecation` OpenAPI extension
- [ ] Updated endpoint documentation with deprecation notice
- [ ] Created migration guide document
- [ ] Documented replacement API
- [ ] Announced in project release notes

### T-30 (Warning)

- [ ] Added `Deprecation`, `Sunset` and `Link` headers to responses
- [ ] Added `X-Deprecated-Message` explaining the migration
- [ ] Added `deprecation_warning` field to response body
- [ ] Confirmed the handler is visible in `http_request_duration_seconds_count`
- [ ] Created Grafana dashboard panel
- [ ] Configured alert rule for usage monitoring
- [ ] Sent notification to known API consumers (if applicable)

### T-0 (Removal)

- [ ] Verified usage has dropped to acceptable level
- [ ] Removed endpoint from router
- [ ] Removed associated schemas
- [ ] Updated CHANGELOG with removal entry
- [ ] Left a tombstone route returning 410 Gone
- [ ] Updated documentation to remove references

---

## Related Documentation

- [API Reference](../developer/api/README.md) - API documentation standards
- [Contributing Guide](../developer/contributing/README.md) - Development workflow
- [API Migration Guides](migrations/README.md) - Index of active deprecations
- [CHANGELOG](../../CHANGELOG.md) - Project change history

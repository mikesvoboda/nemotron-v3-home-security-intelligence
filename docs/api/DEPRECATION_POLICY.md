---
title: API Deprecation Policy
description: Guidelines and process for deprecating API endpoints, including timelines, migration guides, and communication standards
source_refs:
  - docs/developer/api/README.md
  - docs/development/contributing.md
  - backend/api/routes/
---

# API Deprecation Policy

This document defines the standard process for deprecating API endpoints in the Home Security Intelligence system. Following a consistent deprecation policy ensures API consumers have adequate time to migrate while maintaining system reliability.

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
                           │  - OpenAPI spec updated with x-deprecation   │
                           │  - CHANGELOG entry created                   │
                           │  - Replacement API documented                │
                           │                                              │
  T-30 (Warning) ──────────┼──────────────────────────────────────────────┤
                           │                                              │
                           │  Phase 2: Active Warning                     │
                           │  - Deprecation-Warning header added          │
                           │  - Response includes deprecation_warning     │
                           │  - Monitoring for deprecated endpoint usage  │
                           │                                              │
  T-0 (Removal) ───────────┼──────────────────────────────────────────────┘
                           │
                           │  Phase 3: Removal
                           │  - Endpoint removed from codebase
                           │  - Returns 410 Gone for 30 days (optional)
                           │  - OpenAPI spec updated
                           │  - CHANGELOG entry for removal
```

### Phase 1: Announcement (T-90)

**Actions required:**

| Action                                           | Owner    | Location                   |
| ------------------------------------------------ | -------- | -------------------------- |
| Add deprecation notice to endpoint documentation | API Team | `docs/developer/api/*.md`  |
| Add `x-deprecation` extension to OpenAPI spec    | API Team | `backend/api/routes/*.py`  |
| Create CHANGELOG entry                           | API Team | `CHANGELOG.md`             |
| Document replacement API                         | API Team | `docs/developer/api/*.md`  |
| Update migration guide                           | API Team | `docs/api/migrations/*.md` |

### Phase 2: Active Warning (T-30)

**Actions required:**

| Action                                          | Owner    | Location               |
| ----------------------------------------------- | -------- | ---------------------- |
| Add `Deprecation-Warning` HTTP header           | API Team | Route decorator        |
| Add `deprecation_warning` field to responses    | API Team | Response schema        |
| Enable monitoring for deprecated endpoint usage | DevOps   | Grafana dashboard      |
| Send notification to known API consumers        | API Team | Communication channels |

### Phase 3: Removal (T-0)

**Actions required:**

| Action                                 | Owner    | Location                   |
| -------------------------------------- | -------- | -------------------------- |
| Remove endpoint from router            | API Team | `backend/api/routes/*.py`  |
| Remove associated schemas              | API Team | `backend/api/schemas/*.py` |
| Update OpenAPI spec                    | API Team | Auto-generated             |
| Create CHANGELOG entry for removal     | API Team | `CHANGELOG.md`             |
| (Optional) Return 410 Gone for 30 days | API Team | Tombstone route            |

---

## OpenAPI Extension Format

Use the `x-deprecation` extension to provide machine-readable deprecation metadata in OpenAPI specifications.

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
from datetime import date
from fastapi import APIRouter

router = APIRouter()

# Deprecation metadata
CAMERAS_V1_DEPRECATION = {
    "deprecated": True,
    "announced_at": "2026-01-10",
    "warning_at": "2026-02-10",
    "removal_at": "2026-04-10",
    "replacement": "/api/v2/cameras",
    "migration_guide": "/docs/api/migrations/cameras-v1-to-v2.md",
    "reason": "Replaced by v2 API with improved filtering and pagination"
}


@router.get(
    "/api/v1/cameras",
    deprecated=True,  # FastAPI built-in deprecation flag
    openapi_extra={"x-deprecation": CAMERAS_V1_DEPRECATION},
    summary="List cameras (DEPRECATED)",
    description="**DEPRECATED**: Use /api/v2/cameras instead. This endpoint will be removed on 2026-04-10."
)
async def list_cameras_v1():
    """List all cameras (deprecated endpoint)."""
    ...
```

### Generated OpenAPI Spec

The above implementation produces the following OpenAPI specification:

```json
{
  "paths": {
    "/api/v1/cameras": {
      "get": {
        "summary": "List cameras (DEPRECATED)",
        "description": "**DEPRECATED**: Use /api/v2/cameras instead. This endpoint will be removed on 2026-04-10.",
        "deprecated": true,
        "x-deprecation": {
          "deprecated": true,
          "announced_at": "2026-01-10",
          "warning_at": "2026-02-10",
          "removal_at": "2026-04-10",
          "replacement": "/api/v2/cameras",
          "migration_guide": "/docs/api/migrations/cameras-v1-to-v2.md",
          "reason": "Replaced by v2 API with improved filtering and pagination"
        }
      }
    }
  }
}
```

---

## Deprecation Warning Response Headers

During Phase 2 (T-30 to T-0), deprecated endpoints must include warning headers and response fields.

### HTTP Headers

```http
HTTP/1.1 200 OK
Deprecation-Warning: This endpoint is deprecated and will be removed on 2026-04-10. Use /api/v2/cameras instead.
Sunset: Fri, 10 Apr 2026 00:00:00 GMT
Link: </api/v2/cameras>; rel="successor-version"
Content-Type: application/json
```

| Header                | Purpose                                                       |
| --------------------- | ------------------------------------------------------------- |
| `Deprecation-Warning` | Human-readable warning message                                |
| `Sunset`              | RFC 7231 compliant removal date                               |
| `Link`                | Points to replacement endpoint with `rel="successor-version"` |

### Response Body Field

Include `deprecation_warning` in all response models:

```json
{
  "cameras": [...],
  "count": 5,
  "deprecation_warning": "This endpoint is deprecated and will be removed on 2026-04-10. Please migrate to /api/v2/cameras. See migration guide: /docs/api/migrations/cameras-v1-to-v2.md"
}
```

### FastAPI Implementation

```python
from fastapi import Response
from datetime import datetime


def add_deprecation_headers(
    response: Response,
    removal_date: str,
    replacement: str,
    migration_guide: str | None = None
) -> None:
    """Add deprecation warning headers to response."""
    msg = f"This endpoint is deprecated and will be removed on {removal_date}. Use {replacement} instead."
    if migration_guide:
        msg += f" See migration guide: {migration_guide}"

    response.headers["Deprecation-Warning"] = msg
    response.headers["Sunset"] = datetime.fromisoformat(removal_date).strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )
    response.headers["Link"] = f'<{replacement}>; rel="successor-version"'


@router.get("/api/v1/cameras")
async def list_cameras_v1(response: Response):
    add_deprecation_headers(
        response,
        removal_date="2026-04-10",
        replacement="/api/v2/cameras",
        migration_guide="/docs/api/migrations/cameras-v1-to-v2.md"
    )

    result = await get_cameras()
    return {
        **result,
        "deprecation_warning": "This endpoint is deprecated and will be removed on 2026-04-10. Please migrate to /api/v2/cameras."
    }
```

---

## CHANGELOG Format

Document all deprecations in the project CHANGELOG following the Keep a Changelog format.

### Deprecation Announcement (T-90)

```markdown
## [Unreleased]

### Deprecated

- **GET /api/v1/cameras**: Deprecated in favor of `/api/v2/cameras`.
  Will be removed on 2026-04-10. See [migration guide](docs/api/migrations/cameras-v1-to-v2.md).
  - Reason: New v2 API provides cursor-based pagination and improved filtering
  - Replacement: `GET /api/v2/cameras`
  - Timeline: Warnings begin 2026-02-10, removal 2026-04-10
```

### Active Warning Phase (T-30)

```markdown
## [Unreleased]

### Changed

- **GET /api/v1/cameras**: Now returns `Deprecation-Warning` header and
  `deprecation_warning` response field. Scheduled for removal on 2026-04-10.
```

### Removal (T-0)

```markdown
## [Unreleased]

### Removed

- **GET /api/v1/cameras**: Removed deprecated endpoint. Use `/api/v2/cameras` instead.
  See [migration guide](docs/api/migrations/cameras-v1-to-v2.md) for upgrade instructions.
```

---

## Migration Guide Template

Create migration guides in `docs/api/migrations/` for each deprecated endpoint.

### File Naming Convention

```
docs/api/migrations/{resource}-v{old}-to-v{new}.md
```

Example: `docs/api/migrations/cameras-v1-to-v2.md`

### Template

````markdown
---
title: Migrating from /api/v1/cameras to /api/v2/cameras
description: Step-by-step migration guide for cameras API v1 to v2
---

# Cameras API Migration Guide: v1 to v2

## Overview

| Attribute            | Value                 |
| -------------------- | --------------------- |
| Deprecated Endpoint  | `GET /api/v1/cameras` |
| Replacement Endpoint | `GET /api/v2/cameras` |
| Announcement Date    | 2026-01-10            |
| Warning Phase Begins | 2026-02-10            |
| Removal Date         | 2026-04-10            |
| Breaking Changes     | Yes                   |

## Summary of Changes

### New Features in v2

- Cursor-based pagination (improved performance for large datasets)
- Enhanced filtering options (`status`, `location`, `created_after`)
- Consistent response envelope format
- Additional camera metadata fields

### Breaking Changes

1. Response structure changed (see examples below)
2. Offset pagination replaced with cursor pagination
3. Field `folder_path` renamed to `storage_path`
4. Field `last_seen_at` moved to `metadata.last_activity`

## Request Changes

### v1 Request (Deprecated)

```bash
GET /api/v1/cameras?limit=10&offset=20
```
````

### v2 Request (Replacement)

```bash
GET /api/v2/cameras?limit=10&cursor=eyJpZCI6IDEwfQ==
```

### Query Parameter Mapping

| v1 Parameter | v2 Parameter    | Notes                             |
| ------------ | --------------- | --------------------------------- |
| `limit`      | `limit`         | No change                         |
| `offset`     | `cursor`        | Use cursor from previous response |
| `status`     | `status`        | No change                         |
| -            | `location`      | New in v2                         |
| -            | `created_after` | New in v2                         |

## Response Changes

### v1 Response (Deprecated)

```json
{
  "cameras": [
    {
      "id": "front_door",
      "name": "Front Door Camera",
      "folder_path": "/export/foscam/front_door",
      "status": "online",
      "created_at": "2025-12-23T10:00:00Z",
      "last_seen_at": "2025-12-23T12:00:00Z"
    }
  ],
  "count": 1
}
```

### v2 Response (Replacement)

```json
{
  "data": [
    {
      "id": "front_door",
      "name": "Front Door Camera",
      "storage_path": "/export/foscam/front_door",
      "status": "online",
      "created_at": "2025-12-23T10:00:00Z",
      "metadata": {
        "last_activity": "2025-12-23T12:00:00Z",
        "location": "front_entrance"
      }
    }
  ],
  "pagination": {
    "total": 1,
    "limit": 10,
    "has_more": false,
    "next_cursor": null
  }
}
```

### Response Field Mapping

| v1 Field         | v2 Field                   | Notes                         |
| ---------------- | -------------------------- | ----------------------------- |
| `cameras`        | `data`                     | Array renamed for consistency |
| `count`          | `pagination.total`         | Moved to pagination object    |
| `*.folder_path`  | `*.storage_path`           | Renamed                       |
| `*.last_seen_at` | `*.metadata.last_activity` | Moved to metadata             |
| -                | `pagination.has_more`      | New in v2                     |
| -                | `pagination.next_cursor`   | New in v2                     |

## Code Migration Steps

### Python Example

#### Before (v1)

```python
import requests

def get_cameras():
    cameras = []
    offset = 0
    limit = 100

    while True:
        response = requests.get(
            "http://localhost:8000/api/v1/cameras",
            params={"limit": limit, "offset": offset}
        )
        data = response.json()
        cameras.extend(data["cameras"])

        if len(data["cameras"]) < limit:
            break
        offset += limit

    return cameras

# Accessing camera data
for camera in get_cameras():
    print(f"{camera['name']}: {camera['folder_path']}")
    print(f"Last seen: {camera['last_seen_at']}")
```

#### After (v2)

```python
import requests

def get_cameras():
    cameras = []
    cursor = None

    while True:
        params = {"limit": 100}
        if cursor:
            params["cursor"] = cursor

        response = requests.get(
            "http://localhost:8000/api/v2/cameras",
            params=params
        )
        data = response.json()
        cameras.extend(data["data"])

        if not data["pagination"]["has_more"]:
            break
        cursor = data["pagination"]["next_cursor"]

    return cameras

# Accessing camera data (note field name changes)
for camera in get_cameras():
    print(f"{camera['name']}: {camera['storage_path']}")  # Changed: folder_path -> storage_path
    print(f"Last seen: {camera['metadata']['last_activity']}")  # Changed: last_seen_at -> metadata.last_activity
```

### TypeScript Example

#### Before (v1)

```typescript
interface CameraV1 {
  id: string;
  name: string;
  folder_path: string;
  status: string;
  created_at: string;
  last_seen_at: string | null;
}

interface CameraListResponseV1 {
  cameras: CameraV1[];
  count: number;
}

async function getCamerasV1(): Promise<CameraV1[]> {
  const response = await fetch('/api/v1/cameras');
  const data: CameraListResponseV1 = await response.json();
  return data.cameras;
}
```

#### After (v2)

```typescript
interface CameraV2 {
  id: string;
  name: string;
  storage_path: string; // Changed from folder_path
  status: string;
  created_at: string;
  metadata: {
    last_activity: string | null; // Changed from last_seen_at
    location?: string;
  };
}

interface PaginationV2 {
  total: number;
  limit: number;
  has_more: boolean;
  next_cursor: string | null;
}

interface CameraListResponseV2 {
  data: CameraV2[]; // Changed from cameras
  pagination: PaginationV2;
}

async function getCamerasV2(): Promise<CameraV2[]> {
  const cameras: CameraV2[] = [];
  let cursor: string | null = null;

  do {
    const params = new URLSearchParams({ limit: '100' });
    if (cursor) params.set('cursor', cursor);

    const response = await fetch(`/api/v2/cameras?${params}`);
    const data: CameraListResponseV2 = await response.json();

    cameras.push(...data.data);
    cursor = data.pagination.next_cursor;
  } while (cursor);

  return cameras;
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
- Check the [API Reference](/docs/developer/api/core-resources.md) for complete v2 documentation
- Open a GitHub issue with the `api-migration` label

## Timeline Reminder

| Date       | Event                 |
| ---------- | --------------------- |
| 2026-01-10 | Deprecation announced |
| 2026-02-10 | Warning headers begin |
| 2026-04-10 | v1 endpoint removed   |

**Migrate before 2026-04-10 to avoid service disruption.**

````

---

## Monitoring Deprecated Endpoints

Track usage of deprecated endpoints to ensure consumers migrate before removal.

### Prometheus Metrics

```python
from prometheus_client import Counter

deprecated_endpoint_calls = Counter(
    "api_deprecated_endpoint_calls_total",
    "Total calls to deprecated API endpoints",
    ["endpoint", "removal_date"]
)

# In route handler
@router.get("/api/v1/cameras")
async def list_cameras_v1():
    deprecated_endpoint_calls.labels(
        endpoint="/api/v1/cameras",
        removal_date="2026-04-10"
    ).inc()
    ...
````

### Grafana Dashboard Query

```promql
# Deprecated endpoint usage over time
sum by (endpoint) (rate(api_deprecated_endpoint_calls_total[5m]))

# Alert on high usage as removal date approaches
api_deprecated_endpoint_calls_total{removal_date=~".*"} > 0
```

### Alert Rule

```yaml
groups:
  - name: api_deprecation
    rules:
      - alert: DeprecatedEndpointStillInUse
        expr: increase(api_deprecated_endpoint_calls_total[24h]) > 100
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: 'Deprecated endpoint {{ $labels.endpoint }} still receiving traffic'
          description: 'The deprecated endpoint {{ $labels.endpoint }} (removal: {{ $labels.removal_date }}) received {{ $value }} calls in the last 24 hours.'
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

- [ ] Added `Deprecation-Warning` header to responses
- [ ] Added `deprecation_warning` field to response body
- [ ] Enabled Prometheus metrics for deprecated endpoint
- [ ] Created Grafana dashboard panel
- [ ] Configured alert rule for usage monitoring
- [ ] Sent notification to known API consumers (if applicable)

### T-0 (Removal)

- [ ] Verified usage has dropped to acceptable level
- [ ] Removed endpoint from router
- [ ] Removed associated schemas
- [ ] Updated CHANGELOG with removal entry
- [ ] (Optional) Added tombstone route returning 410 Gone
- [ ] Updated documentation to remove references

---

## Related Documentation

- [API Reference](../developer/api/README.md) - API documentation standards
- [Contributing Guide](../development/contributing.md) - Development workflow
- [CHANGELOG](../../CHANGELOG.md) - Project change history

---

## Version History

| Version | Date       | Changes                    |
| ------- | ---------- | -------------------------- |
| 1.0.0   | 2026-01-10 | Initial deprecation policy |

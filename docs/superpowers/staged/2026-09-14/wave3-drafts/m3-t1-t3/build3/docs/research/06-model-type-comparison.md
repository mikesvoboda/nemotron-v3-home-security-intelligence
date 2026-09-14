# Backend Models vs Frontend Types Comparison

## Executive Summary

The system is **mostly well-aligned** between backend models and frontend types, but there are **type safety improvements needed**, particularly around JSONB fields and optimistic locking.

## Critical Findings

### 1. Optimistic Locking Mismatch (Priority 1)

**Issue:** Backend models have `version` or `version_id` fields for optimistic locking, but frontend manually overrides types instead of using auto-generated types.

**Backend:**

```python
class Alert(Base):
    version_id: Mapped[int] = mapped_column(default=1)
```

**Frontend (alerts.ts):**

```typescript
// Manual override instead of using generated type
interface Alert {
  // version_id not included in auto-generated type
}
```

**Recommendation:** Include `version_id` in OpenAPI schema so it's auto-generated.

### 2. Type Safety Issues (Priority 1)

**Issue:** JSONB fields typed as `dict[str, Any]` with no validation.

**Affected Fields:**

- `enrichment_data` - Detection enrichment
- `entities` - Entity metadata
- `flags` - Risk flags
- `entity_metadata` - Entity JSONB

**Backend:**

```python
enrichment_data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
```

**Frontend receives:** Unvalidated dictionary data

**Recommendation:** Create typed Pydantic models for JSONB structures.

### 3. Deferred Fields Not Documented (Priority 2)

**Issue:** `reasoning` and `llm_prompt` in Event model are deferred (not loaded by default), but frontend types don't indicate this.

**Backend:**

```python
reasoning: Mapped[str | None] = deferred(mapped_column(Text, nullable=True))
llm_prompt: Mapped[str | None] = deferred(mapped_column(Text, nullable=True))
```

**Impact:** May cause missing data in list views.

**Recommendation:** Document deferred fields in OpenAPI schema description.

## Model-by-Model Comparison

### Camera

| Backend Field      | Schema Field       | Frontend Type | Status        |
| ------------------ | ------------------ | ------------- | ------------- | --- |
| id                 | id                 | string        | ✅            |
| name               | name               | string        | ✅            |
| folder_path        | folder_path        | string        | ✅            |
| status             | status             | CameraStatus  | ✅            |
| created_at         | created_at         | string (ISO)  | ✅            |
| last_seen_at       | last_seen_at       | string        | ✅            |
| deleted_at         | deleted_at         | string        | null          | ✅  |
| property_id        | property_id        | string        | null          | ✅  |
| rtsp_url           | rtsp_url           | string        | null          | ✅  |
| rtsp_username      | rtsp_username      | string        | null          | ✅  |
| rtsp_password      | rtsp_password      | string        | null          | ✅  |
| stream_profile     | stream_profile     | string        | null          | ✅  |
| motion_sensitivity | motion_sensitivity | number        | null          | ✅  |
| -                  | areas              | Area[]        | ✅ (computed) |

**Status:** ✅ Complete

### Detection

| Backend Field     | Schema Field           | Frontend Type       | Status           |
| ----------------- | ---------------------- | ------------------- | ---------------- | --- |
| id                | id                     | string              | ✅               |
| camera_id         | camera_id              | string              | ✅               |
| object_type       | object_type            | string              | ✅               |
| confidence        | confidence             | number              | ✅               |
| bbox              | bbox                   | number[]            | ✅               |
| timestamp         | timestamp              | string              | ✅               |
| image_path        | image_path             | string              | null             | ✅  |
| enrichment_data   | enrichment_data        | Record<string, any> | ⚠️ Untyped       |
| entity_id         | entity_id              | string              | null             | ✅  |
| track_id          | track_id               | string              | null             | ✅  |
| detection_count   | detection_count        | number              | ✅ (computed)    |
| thumbnail_url     | thumbnail_url          | string              | ✅ (computed)    |
| enrichment_status | enrichment_status      | string              | ✅ (computed)    |
| -                 | association_created_at | string              | ✅ (schema only) |

**Status:** ⚠️ enrichment_data untyped

### Alert

| Backend Field     | Schema Field      | Frontend Type       | Status           |
| ----------------- | ----------------- | ------------------- | ---------------- | --- |
| id                | id                | string              | ✅               |
| event_id          | event_id          | string              | ✅               |
| rule_id           | rule_id           | string              | ✅               |
| status            | status            | AlertStatus         | ✅               |
| severity          | severity          | AlertSeverity       | ✅               |
| created_at        | created_at        | string              | ✅               |
| acknowledged_at   | acknowledged_at   | string              | null             | ✅  |
| acknowledged_by   | acknowledged_by   | string              | null             | ✅  |
| dismissed_at      | dismissed_at      | string              | null             | ✅  |
| dismissed_by      | dismissed_by      | string              | null             | ✅  |
| notification_sent | notification_sent | boolean             | ✅               |
| metadata          | metadata          | Record<string, any> | ⚠️               |
| version_id        | -                 | -                   | ❌ Not in schema |

**Status:** ⚠️ version_id not in schema

### Event

| Backend Field     | Schema Field      | Frontend Type       | Status         |
| ----------------- | ----------------- | ------------------- | -------------- | ----------- |
| id                | id                | string              | ✅             |
| camera_id         | camera_id         | string              | ✅             |
| timestamp         | timestamp         | string              | ✅             |
| risk_score        | risk_score        | number              | null           | ✅          |
| risk_level        | risk_level        | RiskLevel           | ✅             |
| summary           | summary           | string              | null           | ✅          |
| reasoning         | reasoning         | string              | null           | ⚠️ Deferred |
| llm_prompt        | llm_prompt        | string              | null           | ⚠️ Deferred |
| entities          | entities          | Record<string, any> | ⚠️ Untyped     |
| flags             | flags             | Record<string, any> | ⚠️ Untyped     |
| enrichment_status | enrichment_status | string              | ✅             |
| detection_count   | detection_count   | number              | ✅ (computed)  |
| version           | version           | number              | ⚠️ Sync needed |

**Status:** ⚠️ Multiple issues (deferred fields, untyped JSONB)

### Entity

| Backend Field        | Schema Field | Frontend Type | Status             |
| -------------------- | ------------ | ------------- | ------------------ |
| id                   | ?            | ?             | ⚠️ No schema found |
| type                 | ?            | ?             | ⚠️                 |
| first_seen           | ?            | ?             | ⚠️                 |
| last_seen            | ?            | ?             | ⚠️                 |
| detection_count      | ?            | ?             | ⚠️                 |
| trust_status         | ?            | ?             | ⚠️                 |
| entity_metadata      | ?            | ?             | ⚠️                 |
| primary_detection_id | ?            | ?             | ⚠️                 |

**Status:** ❌ No schema found for Entity model

### Job

| Backend Field | Schema Field | Frontend Type       | Status |
| ------------- | ------------ | ------------------- | ------ | --- |
| id            | id           | string              | ✅     |
| job_type      | job_type     | JobType             | ✅     |
| status        | status       | JobStatus           | ✅     |
| created_at    | created_at   | string              | ✅     |
| started_at    | started_at   | string              | null   | ✅  |
| completed_at  | completed_at | string              | null   | ✅  |
| progress      | progress     | number              | ✅     |
| result        | result       | Record<string, any> | ⚠️     |
| error         | error        | string              | null   | ✅  |
| metadata      | metadata     | Record<string, any> | ⚠️     |

**Status:** ✅ Complete (some untyped JSONB)

## Datetime Serialization

**Working correctly:**

- SQLAlchemy datetime → Pydantic ISO strings → Frontend strings
- No type mismatches observed

## Recommendations

### Immediate Actions

1. **Add version_id to Alert schema**

   ```python
   class AlertResponse(BaseModel):
       version_id: int
   ```

2. **Create typed models for JSONB fields**

   ```python
   class EnrichmentData(BaseModel):
       scene_description: str | None
       context: dict | None
       ...
   ```

3. **Document deferred fields**
   ```python
   reasoning: str | None = Field(
       None,
       description="Deferred field - not loaded in list queries"
   )
   ```

### Medium-term Actions

1. **Create Entity schema** (currently missing)
2. **Add JSONB validation** at API boundary
3. **Generate frontend types** from OpenAPI spec

### Files Location

| Type            | Location               |
| --------------- | ---------------------- |
| Backend Models  | `backend/models/`      |
| Backend Schemas | `backend/api/schemas/` |
| Frontend Types  | `frontend/src/types/`  |

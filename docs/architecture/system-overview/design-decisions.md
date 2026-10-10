# Design Decisions

This document captures the key architectural decisions in ADR (Architecture Decision Record) format, with source code citations for verification.

## Table of Contents

- [DD-001: LLM-Determined Risk Scoring](#dd-001-llm-determined-risk-scoring)
- [DD-002: 90-Second Batch Windows](#dd-002-90-second-batch-windows)
- [DD-003: PostgreSQL with Async SQLAlchemy](#dd-003-postgresql-with-async-sqlalchemy)
- [DD-004: Redis Multi-Pool Architecture](#dd-004-redis-multi-pool-architecture)
- [DD-005: On-Demand Model Loading (Model Zoo)](#dd-005-on-demand-model-loading-model-zoo)
- [DD-006: WebSocket + Redis Pub/Sub](#dd-006-websocket-redis-pubsub)
- [DD-007: Single-User No-Auth MVP](#dd-007-single-user-no-auth-mvp)

---

## DD-001: LLM-Determined Risk Scoring

**Status:** Accepted
**Date:** 2024-12-21

### Context

Each security event needs a risk score (0-100) and risk level (low/medium/high/critical). This could be calculated algorithmically based on rules (e.g., "person at night = high") or determined by the LLM based on contextual understanding.

### Decision

Let the **VLM determine risk scores** based on contextual analysis rather than using algorithmic rules.

**Source:** `backend/services/vlm_analyzer.py:380` - `VlmAnalyzer.analyze_batch` turns a closed batch
into a verdict and writes the event's `risk_score`, `risk_level`, `summary` and `reasoning`. Before
the write, `apply_verdict_invariants` (`backend/services/vlm_analyzer.py:255-304`) derives
`risk_level` from the score through the severity service, clamps a `rejected` verdict's score so it
cannot present above the configured low band (the clamp is left visible in the stored reasoning), and
writes NULL score/level when the ladder produced no verdict at all.

### Rationale

1. **Context-aware**: "person at 2am approaching back door" scores higher than "person at 2pm on sidewalk"
2. **Reasoning**: LLM provides human-readable explanation of WHY it scored the event
3. **Flexibility**: No hardcoded rules to maintain as scenarios evolve
4. **Batch context**: LLM sees multiple detections together, understanding motion sequences

### Alternatives Rejected

| Alternative           | Why Rejected                                                   |
| --------------------- | -------------------------------------------------------------- |
| **Algorithmic rules** | Cannot understand context, requires extensive rule maintenance |
| **ML classifier**     | Needs labeled training data we don't have, still a black box   |
| **Hybrid approach**   | Added complexity without clear benefit given LLM capabilities  |

### Consequences

- **Positive**: Contextual understanding, natural language explanations, zero rule maintenance
- **Negative**: 2-5s latency per batch (vs milliseconds for rules), potential inconsistency

---

## DD-002: 90-Second Batch Windows

**Status:** Accepted
**Date:** 2024-12-21

### Context

A single "person walks to door" scenario generates 15+ camera images over 30 seconds. Processing each image independently would waste GPU resources, generate noisy alerts, and miss contextual story.

### Decision

Batch detections into **90-second time windows** with **30-second idle timeout**, then analyze as a single event.

**Source:** `backend/services/batch_aggregator.py:7-13`

```python
# Batching Logic:
#     - Create new batch when first detection arrives for a camera
#     - Add subsequent detections within 90-second window
#     - Close batch if:
#         * 90 seconds elapsed from batch start (window timeout)
#         * 30 seconds with no new detections (idle timeout)
```

**Configuration Source:** `backend/core/config.py:874-883`

```python
batch_window_seconds: int = Field(
    default=90,
    gt=0,
    description="Time window for batch processing detections",
)
batch_idle_timeout_seconds: int = Field(
    default=30,
    description="Idle timeout before processing incomplete batch",
)
```

### Rationale

1. **Natural grouping**: A single activity becomes one coherent event
2. **Reduced API calls**: One LLM call per event vs per frame (~90% reduction)
3. **Better context**: LLM reasons about sequences ("approached, paused, left")
4. **Configurable**: Can tune via `BATCH_WINDOW_SECONDS` and `BATCH_IDLE_TIMEOUT_SECONDS`

### Alternatives Rejected

| Alternative                 | Why Rejected                                                 |
| --------------------------- | ------------------------------------------------------------ |
| **Immediate per-image**     | Noisy (15 alerts vs 1), expensive (15 LLM calls), no context |
| **Fixed 60-second windows** | May split natural events, delays short events                |
| **Event-driven clustering** | Complex ML required, harder to implement and debug           |

### Fast Path Exception

`BatchAggregator` has a fast-path branch that would skip the window for a high-confidence detection,
but it ships inert: `FAST_PATH_OBJECT_TYPES` defaults to an empty list, so the branch never matches
(`backend/core/config.py:1684-1700`). Every detection reaches the analyzer through the normal batch
gate.

---

## DD-003: PostgreSQL with Async SQLAlchemy

**Status:** Accepted
**Date:** 2024-12-28

### Context

The system needs a database for storing security events, detections, camera configurations, and GPU statistics. Multiple pipeline workers (FileWatcher, BatchAggregator, CleanupService) perform concurrent writes.

### Decision

Use **PostgreSQL** with `asyncpg` async driver via SQLAlchemy 2.0.

**Source:** `backend/core/config.py:354-358`

```python
database_url: str = Field(
    default="",
    description="PostgreSQL database URL (format: postgresql+asyncpg://user:pass@host:port/db)...",  # pragma: allowlist secret,
)
```

**Pool Configuration Source:** `backend/core/config.py:373-385`

```python
database_pool_size: int = Field(
    default=20,
    ge=5,
    le=100,
    description="Base number of database connections to maintain in pool",
)
database_pool_overflow: int = Field(
    default=30,
    ge=0,
    le=100,
    description="Additional connections beyond pool_size when under load",
)
```

### Rationale

1. **Concurrency**: Multiple workers need concurrent writes without blocking
2. **Production-ready**: Proven for concurrent workloads, proper transaction isolation
3. **Testing reliability**: SQLite's concurrency issues caused test flakiness
4. **Modern features**: JSONB for flexible data, full-text search, proper indexing

### Alternatives Rejected

| Alternative   | Why Rejected                                                      |
| ------------- | ----------------------------------------------------------------- |
| **SQLite**    | Single-writer limitation causes bottlenecks with parallel workers |
| **MongoDB**   | Overkill for structured data, additional complexity               |
| **In-memory** | No persistence, data loss on restart                              |

---

## DD-004: Redis Multi-Pool Architecture

**Status:** Accepted
**Date:** 2025-01-15

### Context

Redis serves multiple workload types: cache operations (fast, short-lived), queue operations (may block on BLPOP), pub/sub (long-lived connections), and rate limiting (high frequency). A single connection pool cannot optimize for all patterns.

### Decision

Implement **dedicated connection pools** for each workload type.

**Source:** `backend/core/redis.py:74-91`

```python
class PoolType(str, Enum):
    """Redis connection pool types for workload isolation (NEM-3368)."""

    CACHE = "cache"
    """Pool for cache operations (get/set/delete) - fast, high availability."""

    QUEUE = "queue"
    """Pool for queue operations (BLPOP/RPUSH) - can block."""

    PUBSUB = "pubsub"
    """Pool for pub/sub operations - long-lived connections."""

    RATELIMIT = "ratelimit"
    """Pool for rate limiting operations - high frequency."""

    DEFAULT = "default"
    """Fallback pool when dedicated pools are disabled."""
```

**Pool Size Configuration Source:** `backend/core/config.py:499-526`

```python
redis_pool_dedicated_enabled: bool = Field(
    default=True,
    description="Enable dedicated connection pools by workload type.",
)
redis_pool_size_cache: int = Field(
    default=20,
    description="Max connections for cache operations.",
)
redis_pool_size_queue: int = Field(
    default=15,
    description="Max connections for queue operations.",
)
redis_pool_size_pubsub: int = Field(
    default=10,
    description="Max connections for pub/sub operations.",
)
redis_pool_size_ratelimit: int = Field(
    default=10,
    description="Max connections for rate limiting operations.",
)
```

### Rationale

1. **Workload isolation**: Blocking queue ops don't starve cache operations
2. **Optimized sizing**: Each pool sized for its access pattern
3. **Connection efficiency**: Pub/sub doesn't compete with high-frequency cache
4. **Graceful fallback**: Can disable with `redis_pool_dedicated_enabled=False`

### Alternatives Rejected

| Alternative             | Why Rejected                                       |
| ----------------------- | -------------------------------------------------- |
| **Single pool**         | Blocking BLPOP exhausts connections, starves cache |
| **Per-operation pools** | Too many pools, management overhead                |
| **No pooling**          | Connection overhead per operation                  |

---

## DD-005: On-Demand Model Loading (Model Zoo)

**Status:** Accepted
**Date:** 2025-01-10

### Context

The backend carries a set of optional lookup models — license plates, faces, person re-ID, OCR. Loading every one at startup would occupy VRAM (and, for the face leg, host RAM) that the perception model needs, and most are touched only when a matching detection lands.

### Decision

Implement **on-demand model loading** via ModelManager, with a per-row `preload` opt-in for the legs
that must be resident.

**Source:** `backend/services/model_zoo.py:1-9`

```python
"""Model Zoo for on-demand model loading.

This module provides a registry of AI models that can be loaded on-demand during
batch processing to extract additional context (license plates, faces, OCR text,
pose estimation).

The ModelManager handles VRAM-efficient loading and unloading of models using
async context managers that automatically release GPU memory when done.
```

**VRAM budget source:** `backend/services/model_zoo.py:26-29` — the module docstring's budget block.
Read it with care: its first line names the always-loaded LLM slot but cites `VLM_MODEL_SLOTS`, a
variable that exists in no shipped file, and its second line gives YOLO26v2 650 MB. The third line —
models load sequentially, never concurrently — is the part the code actually enforces.

The registry itself lives in `models.yml`; every row declares `vram_mb`, `enabled`, and `preload`.
Only three rows carry `preload: true` — `osnet-ain-x1-0` (100 MB), `face-detector-scrfd` (0), and
`face-recognizer` (0) — at `models.yml:134`, `models.yml:166`, and `models.yml:191`.

### Rationale

1. **VRAM efficiency**: Only loaded models consume GPU memory
2. **Flexible coverage**: Add models without pre-allocating VRAM
3. **Sequential loading**: Prevents concurrent load spikes
4. **Auto-unload**: Context managers release memory when done

### Residency Is a Boot-Time Decision

The face and re-ID legs never trigger their own load: `osnet_loader.get_reid_handle()`
(`backend/services/osnet_loader.py:182-203`) and `face_recognizer_loader.get_face_leg_handles()`
(`backend/services/face_recognizer_loader.py:466-490`) are membership reads. The handle exists only
if the boot sweep ran, and that sweep is gated on `BACKEND_MODEL_PRELOAD`, which ships `false`
(`.env.example:231`, `backend/main.py:1215`). `setup.py` sets it to true only when detected VRAM is
at least 24 GB. The plate leg is the exception — `fast_alpr_loader` loads on demand.

So on a sub-24 GB host the `faces` and `person_reid` specialist lines report `unavailable` on every
event while the pipeline stays healthy. The counter that answers "has this ever run" is
`hsi_specialist_unavailable_total` on `/api/metrics`.

### Alternatives Rejected

| Alternative             | Why Rejected                      |
| ----------------------- | --------------------------------- |
| **Load all at startup** | Exceeds the host's VRAM budget    |
| **CPU fallback**        | Too slow for real-time processing |
| **External API**        | Adds latency, requires network    |

---

## DD-006: WebSocket + Redis Pub/Sub

**Status:** Accepted
**Date:** 2024-12-21

### Context

The dashboard needs real-time updates for security events, system status (GPU, cameras), and worker health. Multiple backend instances may be deployed behind a load balancer.

### Decision

Use **WebSocket** for client connections with **Redis pub/sub** as the event backbone.

**Source:** `backend/services/event_broadcaster.py:1-8`

```python
"""Event broadcaster service for WebSocket real-time event distribution.

This service manages WebSocket connections and broadcasts security events
to all connected clients using Redis pub/sub as the event backbone.
"""
```

**Channel Configuration Source:** `backend/core/config.py:471-475`

```python
redis_event_channel: str = Field(
    default="security_events",
    description="Redis pub/sub channel for security events",
)
```

### Rationale

1. **Sub-second delivery**: Events reach dashboard instantly
2. **Bidirectional**: Clients can send messages back
3. **Multi-instance support**: Redis pub/sub fans out to all backend instances
4. **Native browser support**: No polyfills needed

### Communication Pattern

```
VlmAnalyzer --> Redis PUBLISH --> EventBroadcaster(s) --> WebSocket --> Dashboard
```

The analyzer commits the event first and publishes last, best-effort: `VlmAnalyzer._broadcast`
calls `event_broadcaster.get_broadcaster()` after the DB session closes, so a failed broadcast never
un-does the write (`backend/services/vlm_analyzer.py:765-773`). The broadcaster publishes to
`settings.redis_event_channel` and each backend instance's subscriber loop fans out to its own
WebSocket clients (`backend/services/event_broadcaster.py:346`, `:641`, `:820`).

### Alternatives Rejected

| Alternative          | Why Rejected                                |
| -------------------- | ------------------------------------------- |
| **Polling**          | Latency, wasted requests, server load       |
| **SSE**              | No bidirectional, limited connections       |
| **Direct WebSocket** | Doesn't scale to multiple backend instances |

---

## DD-007: Single-User No-Auth MVP

**Status:** Accepted
**Date:** 2024-12-21

### Context

This is a single-user home security system deployed on a trusted local network. The system processes sensitive camera images that should never leave the local network.

### Decision

**No authentication**, with two standing gates: binding to `127.0.0.1` is the network boundary, and
`SetupGuardMiddleware` returns 503 for every non-whitelisted endpoint until the first admin
registration exists, after which the API is open. System assumes trusted network access by single user.

**Source:** `backend/main.py:1489`

```python
# Add setup guard middleware (NEM-5312: Phase 2 API Protection)
# Returns 503 for all endpoints except whitelist when no users exist
# This ensures the application cannot be used until initial setup is complete
# Must be early in the middleware chain (after auth) to block requests before processing
app.add_middleware(SetupGuardMiddleware)
```

Per-route dependencies (`verify_api_key`, `require_admin_access`, `get_current_admin_user`) protect
the admin endpoints regardless (`backend/api/routes/system.py:271`,
`backend/api/routes/admin.py:262`, `backend/api/routes/auth.py:479` — B1.5 deleted the
`backend/main.py` comment that used to carry this claim).

### Rationale

1. **Simplicity**: Zero authentication complexity
2. **Local deployment**: Designed for LAN access only
3. **Privacy focus**: All processing stays local, no cloud
4. **Fast iteration**: No password management or recovery flows

### Security Mitigations

| Control                   | Implementation                                |
| ------------------------- | --------------------------------------------- |
| Path traversal prevention | Media endpoints validate paths                |
| Local-only design         | Documentation warns against internet exposure |
| Optional API keys         | Can be enabled via `API_KEY_ENABLED=true`     |
| CORS restrictions         | Configurable via `CORS_ORIGINS`               |

### Future Considerations

For multi-user or internet-facing deployments:

- Set `EXPOSE_LAN=true` (login session or API key required on every request)
- Use HTTPS for all endpoints
- Add rate limiting
- Deploy behind reverse proxy with TLS

### Alternatives Rejected

| Alternative    | Why Rejected                                   |
| -------------- | ---------------------------------------------- |
| **JWT tokens** | Overkill for single-user local system          |
| **OAuth/OIDC** | Requires identity provider, massive complexity |
| **Basic auth** | Passwords in headers, poor UX                  |

---

## Decision Dependencies

```mermaid
flowchart TB
    DD001["DD-001<br/>LLM Risk Scoring"]
    DD002["DD-002<br/>90s Batch Windows"]
    DD003["DD-003<br/>PostgreSQL"]
    DD004["DD-004<br/>Redis Multi-Pool"]
    DD005["DD-005<br/>Model Zoo"]
    DD006["DD-006<br/>WebSocket + Pub/Sub"]
    DD007["DD-007<br/>No Auth MVP"]

    DD002 --> DD001
    DD003 --> DD002
    DD004 --> DD002
    DD004 --> DD006
    DD005 --> DD001
```

## Related Documentation

- [Full ADR Collection](/docs/architecture/decisions.md)
- [Architecture Overview](/docs/architecture/overview.md)
- [Configuration Reference](configuration.md)

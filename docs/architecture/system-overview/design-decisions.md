# Design Decisions

This document captures the key architectural decisions in ADR (Architecture Decision Record) format, with source code citations for verification.

## Table of Contents

- [DD-001: LLM-Determined Risk Scoring](#dd-001-llm-determined-risk-scoring)
- [DD-002: 90-Second Batch Windows](#dd-002-90-second-batch-windows)
- [DD-003: PostgreSQL with Async SQLAlchemy](#dd-003-postgresql-with-async-sqlalchemy)
- [DD-004: Redis Multi-Pool Architecture](#dd-004-redis-multi-pool-architecture)
- [DD-005: On-Demand Model Loading (Model Zoo)](#dd-005-on-demand-model-loading-model-zoo)
- [DD-006: WebSocket + Redis Pub/Sub](#dd-006-websocket--redis-pubsub)
- [DD-007: Single-User No-Auth MVP](#dd-007-single-user-no-auth-mvp)

---

## DD-001: LLM-Determined Risk Scoring

![LLM Risk Scoring Concept](../../images/architecture/system-overview/concept-llm-risk-scoring.png)

**Status:** Accepted
**Date:** 2024-12-21

### Context

Each security event needs a risk score (0-100) and risk level (low/medium/high/critical). This could be calculated algorithmically based on rules (e.g., "person at night = high") or determined by the LLM based on contextual understanding.

### Decision

Let the **Nemotron LLM determine risk scores** based on contextual analysis rather than using algorithmic rules.

**Source:** `backend/services/nemotron_analyzer.py` - NemotronAnalyzer processes batches and extracts risk scores from LLM responses.

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

![Batch vs Real-Time Processing](../../images/architecture/system-overview/concept-batch-vs-realtime.png)

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

**Configuration Source:** `backend/core/config.py:626-634`

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

High-confidence person detections (>90%) bypass batching for immediate alerts.

**Source:** `backend/core/config.py:343-344`

```python
FAST_PATH_CONFIDENCE_THRESHOLD=${FAST_PATH_CONFIDENCE_THRESHOLD:-0.90}
FAST_PATH_OBJECT_TYPES=["person"]
```

---

## DD-003: PostgreSQL with Async SQLAlchemy

**Status:** Accepted
**Date:** 2024-12-28

### Context

The system needs a database for storing security events, detections, camera configurations, and GPU statistics. Multiple pipeline workers (FileWatcher, BatchAggregator, CleanupService) perform concurrent writes.

### Decision

Use **PostgreSQL** with `asyncpg` async driver via SQLAlchemy 2.0.

**Source:** `backend/core/config.py:313-316`

```python
database_url: str = Field(
    default="",
    description="PostgreSQL database URL (format: postgresql+asyncpg://user:pass@host:port/db)...",  # pragma: allowlist secret,
)
```

**Pool Configuration Source:** `backend/core/config.py:321-344`

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

**Source:** `backend/core/redis.py:50-66`

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
```

**Pool Size Configuration Source:** `backend/core/config.py:370-405`

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

The system supports many optional AI models for enrichment (license plate detection, face detection, pose estimation, etc.). Loading all models at startup would exhaust GPU VRAM. A 24GB GPU has limited budget after core models.

### Decision

Implement **on-demand model loading** via ModelManager with VRAM budget constraints.

**Source:** `backend/services/model_zoo.py:1-38`

```python
"""Model Zoo for on-demand model loading.

VRAM Budget:
    - Nemotron LLM: 21,700 MB (always loaded)
    - RT-DETRv2: 650 MB (always loaded)
    - Available for Model Zoo: ~1,650 MB
    - Models load sequentially, never concurrently
"""
```

**Enrichment VRAM Budget Source:** `docker-compose.prod.yml:284`

```yaml
# VRAM management
- VRAM_BUDGET_GB=6.8
```

### Rationale

1. **VRAM efficiency**: Only loaded models consume GPU memory
2. **Flexible enrichment**: Add models without pre-allocating VRAM
3. **Sequential loading**: Prevents concurrent load spikes
4. **Auto-unload**: Context managers release memory when done

### VRAM Allocation

| Component        | VRAM (MB) | Notes                              |
| ---------------- | --------- | ---------------------------------- |
| Nemotron LLM     | ~21,700   | Always loaded, Q4_K_M quantization |
| RT-DETRv2        | ~650      | Always loaded, object detection    |
| Model Zoo Budget | ~1,650    | On-demand enrichment models        |
| **Total**        | ~24,000   | Fits RTX A5500 24GB                |

### Alternatives Rejected

| Alternative             | Why Rejected                      |
| ----------------------- | --------------------------------- |
| **Load all at startup** | Exceeds 24GB VRAM budget          |
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

**Channel Configuration Source:** `backend/core/config.py:359-362`

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
NemotronAnalyzer --> Redis PUBLISH --> EventBroadcaster(s) --> WebSocket --> Dashboard
```

### Alternatives Rejected

| Alternative          | Why Rejected                                |
| -------------------- | ------------------------------------------- |
| **Polling**          | Latency, wasted requests, server load       |
| **SSE**              | No bidirectional, limited connections       |
| **Direct WebSocket** | Doesn't scale to multiple backend instances |

---

## DD-007: Single-User No-Auth MVP

![Single-User Local Deployment](../../images/architecture/system-overview/concept-single-user-local.png)

**Status:** Accepted
**Date:** 2024-12-21

### Context

This is a single-user home security system deployed on a trusted local network. The system processes sensitive camera images that should never leave the local network.

### Decision

**No authentication** for MVP. System assumes trusted network access by single user.

**Source:** `backend/main.py:1002-1003`

```python
# Add authentication middleware (if enabled in settings)
app.add_middleware(AuthMiddleware)
```

**Auth Middleware Source:** The AuthMiddleware exists but is disabled by default, allowing opt-in authentication when needed.

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

- Enable `API_KEY_ENABLED=true` with strong keys
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

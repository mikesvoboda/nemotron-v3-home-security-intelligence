# FastAPI Backend Architecture Evaluation

**Date**: 2026-02-08
**Scope**: Backend performance optimization, connection pooling, async patterns, AI service communication
**Codebase Version**: `8401aaf1` (HEAD)

---

## Executive Summary

The backend is a well-architected FastAPI application with 203 service files, 64 registered routers, and 16 middleware layers. It manages AI inference pipelines across 5+ GPU-powered services (YOLO26, Nemotron LLM, Florence-2, CLIP, Enrichment) communicating via HTTP/httpx, with PostgreSQL (asyncpg) and Redis 7.4 (Streams + cache + pub/sub) as data stores. The system runs on a single uvicorn worker with 2 CPUs and 6GB memory.

**Key Findings:**

1. **CRITICAL**: The NemotronAnalyzer creates a new `httpx.AsyncClient` per request (5+ locations), destroying connection pooling and adding ~50-100ms overhead per LLM call. CLIP, Florence, Enrichment, and Detector clients already use persistent clients correctly.
2. **HIGH**: Redis `allkeys-lru` eviction policy risks silently evicting Streams queue data and DLQ entries under memory pressure (450MB limit).
3. **HIGH**: The 16-middleware stack adds measurable latency to every request; several are conditionally loaded but the stack is still deep.
4. **MEDIUM**: Database pool (20+30=50 max) is well-tuned but warming only pre-establishes 5 connections; increasing to 10-15 would better match the 4+ background workers.
5. **MEDIUM**: No structured concurrency (TaskGroup) is used for parallel AI enrichment calls, despite `AsyncTaskGroup` being available in `async_utils.py`.

**Estimated Impact of Top 3 Fixes**: 20-40% reduction in per-event processing latency, elimination of queue data loss risk, and 15-25% reduction in request overhead.

---

## Current Configuration Analysis

### Application Architecture

| Component        | Configuration                      | Notes                                                                                                                                                                                   |
| ---------------- | ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FastAPI app      | Single process, 1 uvicorn worker   | Correct for in-process background services                                                                                                                                              |
| Middleware stack | 16 layers                          | SetupGuard, ContentType, RequestID, Baggage, Profiling, Prometheus, Timing, Logging, Recording, Deprecation, DeprecationLogger, CORS, SecurityHeaders, BodySizeLimit, GZip, Idempotency |
| Routers          | 64 registered                      | Covers cameras, events, detections, zones, AI audit, etc.                                                                                                                               |
| Service files    | 203 total                          | Substantial business logic layer                                                                                                                                                        |
| Container limits | 2 CPUs, 6GB memory                 | Was OOM at 4GB, now at ~68% utilization                                                                                                                                                 |
| Python runtime   | 3.14 (standard build, GIL enabled) | Free-threaded build commented out in Dockerfile                                                                                                                                         |

### HTTP Client Patterns (AI Services)

| Client               | Pattern                                        | Persistent Pool?       | Limits                          |
| -------------------- | ---------------------------------------------- | ---------------------- | ------------------------------- |
| DetectorClient       | `self._http_client = httpx.AsyncClient(...)`   | Yes (NEM-1721)         | max_connections=10, keepalive=5 |
| CLIPClient           | `self._http_client = httpx.AsyncClient(...)`   | Yes (NEM-1721)         | max_connections=10, keepalive=5 |
| FlorenceClient       | `self._http_client = httpx.AsyncClient(...)`   | Yes (NEM-1721)         | max_connections=10, keepalive=5 |
| EnrichmentClient     | `self._http_client = httpx.AsyncClient(...)`   | Yes (NEM-1721)         | max_connections=10, keepalive=5 |
| **NemotronAnalyzer** | `async with httpx.AsyncClient(...) as client:` | **NO** -- per-request! | No pooling                      |

### Database Configuration

| Setting                               | Value                  | Notes                                 |
| ------------------------------------- | ---------------------- | ------------------------------------- |
| `pool_size`                           | 20                     | Base connections maintained           |
| `max_overflow`                        | 30                     | Max overflow = 50 total               |
| `pool_timeout`                        | 30s                    | Wait for connection                   |
| `pool_recycle`                        | 1800s (30min)          | Recycle stale connections             |
| `pool_pre_ping`                       | True                   | Verify before checkout                |
| `pool_use_lifo`                       | True                   | Better cache locality                 |
| `pool_warming_size`                   | 5                      | Pre-established on startup            |
| `statement_timeout`                   | 300s                   | Max query duration                    |
| `idle_in_transaction_session_timeout` | 180s                   | Kill idle transactions                |
| PgBouncer support                     | Available but disabled | `use_pgbouncer=False`                 |
| Read replica                          | Supported              | `database_url_read` setting available |
| Prepared statement cache              | Enabled                | Auto-disabled when pgbouncer=True     |

### Redis Configuration

| Setting            | Value                                 | Notes                                       |
| ------------------ | ------------------------------------- | ------------------------------------------- |
| `maxmemory`        | 450MB                                 | Shared cache + queue + streams              |
| `maxmemory-policy` | allkeys-lru                           | **Risky for queue data**                    |
| Persistence        | AOF (appendfsync everysec)            | Durable but not instant                     |
| Dedicated pools    | Enabled                               | cache=20, queue=15, pubsub=10, ratelimit=10 |
| Compression        | Zstd (Python 3.14 native)             | Threshold: 1024 bytes                       |
| Streams            | Consumer groups, DLQ, max 10K entries | NEM-3364                                    |
| Sentinel support   | Available                             | For HA deployments                          |

---

## Recommended Optimizations

### 1. [HIGH] Fix NemotronAnalyzer httpx Connection Pooling

**What**: The `NemotronAnalyzer` creates a new `httpx.AsyncClient` on every call (at least 5 locations: `_make_llm_call`, `check_health`, `_check_guided_json_support`, `warmup_inference`, and `analyze_batch`). Each new client triggers TCP connection establishment, TLS handshake (if applicable), and HTTP/2 negotiation.

**Current code** (at `backend/services/nemotron_analyzer.py` lines 400, 983, 1375, 3504, 4072):

```python
async with httpx.AsyncClient(timeout=self._timeout) as client:
    response = await client.post(...)
```

**Should be** (matching the pattern in DetectorClient, CLIPClient, FlorenceClient, EnrichmentClient):

```python
# In __init__:
self._http_client = httpx.AsyncClient(
    timeout=self._timeout,
    limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
)

# In methods:
response = await self._http_client.post(...)
```

**Expected impact**: 50-100ms reduction per LLM call from eliminated TCP/TLS setup. With 90-second batch windows processing multiple events, this compounds significantly. At 10 events per batch with 2 LLM calls each, savings are 1-2 seconds per batch.

**Implementation effort**: LOW -- 2-3 hours. The pattern is already established in 4 other AI clients. Add `__init__` client creation, `close()` method, and replace `async with` blocks.

**Risks**: Must ensure `close()` is called during shutdown. The DI container already handles this for other clients.

**Reference**: [httpx Clients documentation](https://www.python-httpx.org/advanced/clients/) -- "If you do anything more than experimentation, one-off scripts, or prototyping, then you should use a Client instance."

---

### 2. [HIGH] Fix Redis Eviction Policy for Queue/Stream Safety

**What**: Redis is configured with `maxmemory-policy allkeys-lru` and a 450MB limit. This means when memory pressure hits, Redis will evict **any** key, including Stream entries (`detections:stream`, `detections:stream:dlq`), queue items, and rate limit counters. Stream data loss is silent -- no errors are raised, entries simply disappear.

**Current configuration** (`docker-compose.prod.yml` line 791):

```
redis-server --maxmemory 450mb --maxmemory-policy allkeys-lru
```

**Recommended changes**:

Option A (Preferred): Switch to `volatile-lru` and ensure all cache keys have TTLs:

```
redis-server --maxmemory 512mb --maxmemory-policy volatile-lru
```

This only evicts keys with TTL set, preserving Streams/queues (which have no TTL). Cache keys already should have TTLs.

Option B: Increase memory and use `noeviction` for queue safety:

```
redis-server --maxmemory 768mb --maxmemory-policy noeviction
```

This rejects writes when full, allowing the application to handle backpressure (the `QueueOverflowPolicy` already supports this).

Option C: Run two Redis instances -- one for cache (allkeys-lru), one for queues/streams (noeviction). This is the [Redis-recommended approach](https://redis.io/docs/latest/develop/reference/eviction/) for mixed workloads.

**Expected impact**: Eliminates risk of silent queue/stream data loss. Current `QueueAddResult` with DLQ handling becomes reliable.

**Implementation effort**: LOW (Option A) to MEDIUM (Option C).

- Option A: Change one line in docker-compose, verify all cache keys have TTLs.
- Option B: Change one line + increase memory allocation.
- Option C: Add second Redis instance to docker-compose, update config to route cache vs queue traffic.

**Risks**: Option A requires auditing all Redis `SET` calls to ensure TTLs are present on cache keys. Without TTLs, `volatile-lru` will not evict anything and Redis will reject writes when full. Option B may reject writes under heavy load.

**Reference**: [Redis Key eviction documentation](https://redis.io/docs/latest/develop/reference/eviction/) -- "it is usually a better idea to run two Redis instances" for mixed cache+persistent workloads.

---

### 3. [HIGH] Reduce Middleware Stack Overhead

**What**: Every HTTP request passes through 16 middleware layers. In Starlette's ASGI middleware model, each layer is an async function call with potential `await` overhead. For high-frequency endpoints (health checks, WebSocket upgrades, metrics scraping), this adds unnecessary latency.

**Current stack** (16 layers, innermost to outermost):

1. IdempotencyMiddleware (conditional)
2. GZipMiddleware
3. BodySizeLimitMiddleware
4. SecurityHeadersMiddleware
5. CORSMiddleware
6. DeprecationLoggerMiddleware
7. DeprecationMiddleware
8. RequestRecorderMiddleware (conditional)
9. RequestLoggingMiddleware (conditional)
10. RequestTimingMiddleware
11. PrometheusMiddleware
12. ProfilingMiddleware
13. BaggageMiddleware
14. RequestIDMiddleware
15. ContentTypeValidationMiddleware
16. SetupGuardMiddleware

**Recommended optimizations**:

A. **Merge related middleware**: Combine `RequestTimingMiddleware`, `RequestLoggingMiddleware`, and `PrometheusMiddleware` into a single `ObservabilityMiddleware` that handles all three concerns in one pass. This eliminates 2 async function call boundaries.

B. **Short-circuit health endpoints**: Add path-based early exit for `/health`, `/ready`, and `/metrics` endpoints in the outermost middleware to bypass the full stack. PrometheusMiddleware already excludes health/metrics, but the request still traverses all layers.

C. **Remove DeprecationMiddleware/DeprecationLoggerMiddleware** if no deprecated endpoints are registered (currently empty -- `_get_deprecation_config()` returns an empty config).

**Expected impact**: 2-5ms reduction per request from reduced async call overhead. At 100+ requests/second during batch processing, this adds up.

**Implementation effort**: MEDIUM -- 1-2 days. Merging middleware requires careful testing. Short-circuit path checking is simpler.

**Risks**: Must ensure merged middleware preserves correct ordering of header writes and timing measurements. Test coverage for middleware is needed.

---

### 4. [HIGH] Use Structured Concurrency for Parallel AI Enrichment

**What**: The enrichment pipeline calls multiple AI services (vehicle classification, pet classification, depth estimation, pose analysis, action recognition, clothing classification) but these calls appear to be made sequentially within the batch analysis flow. The codebase already has `AsyncTaskGroup` and `bounded_gather` in `backend/core/async_utils.py` but these are not used for parallel AI service calls.

**Recommended change**: When enriching a detection, dispatch all applicable enrichment calls in parallel using `asyncio.TaskGroup`:

```python
async with asyncio.TaskGroup() as tg:
    vehicle_task = tg.create_task(enrichment_client.classify_vehicle(image, bbox))
    depth_task = tg.create_task(enrichment_client.estimate_depth(image))
    pose_task = tg.create_task(enrichment_client.analyze_pose(image, bbox))
```

**Expected impact**: If 3 enrichment calls currently run sequentially at ~100ms each, parallelization reduces total from ~300ms to ~100ms (limited by slowest call). With the enrichment pipeline hard timeout of 30s, this allows more enrichments to complete within budget.

**Implementation effort**: MEDIUM -- Requires refactoring the enrichment orchestration layer. The individual client methods are already async.

**Risks**: Increased concurrent load on AI services. The inference semaphore (`AI_MAX_CONCURRENT_INFERENCES=4`) may need adjustment. Circuit breakers per endpoint (already implemented) protect against cascading failures.

---

### 5. [MEDIUM] Increase Connection Pool Warming Target

**What**: The database pool warming pre-establishes only 5 connections at startup (`database_pool_warming_size=5`), but the application immediately starts 4+ background workers (detection, analysis, batch_timeout, metrics) plus file watcher, system broadcaster, GPU monitor, and cleanup service. The first batch of requests after startup will still face cold-start latency for connections 6-8.

**Recommended change**: Increase `database_pool_warming_size` from 5 to 10-12 (still within the pool_size of 20):

```env
DATABASE_POOL_WARMING_SIZE=12
```

**Expected impact**: Eliminates cold-start latency for the first 12 connections instead of 5. Startup time increases by ~200ms (12 vs 5 concurrent `SELECT 1` queries).

**Implementation effort**: LOW -- Single environment variable change.

**Risks**: Minimal. The warming function already clamps to pool_size and handles failures gracefully.

---

### 6. [MEDIUM] Optimize Database Pool for Single-Worker Architecture

**What**: With `pool_size=20` and `max_overflow=30` (50 max), the pool is sized for multi-worker scenarios. But the Dockerfile explicitly runs 1 uvicorn worker. The actual concurrent connection need is:

- 4 pipeline workers (detection, analysis, timeout, metrics)
- File watcher (1 connection)
- System broadcaster (1 connection)
- GPU monitor (occasional)
- API requests (varies, but single worker limits concurrency)

Total realistic concurrent need: 10-15 connections.

**Recommended change**:

```env
DATABASE_POOL_SIZE=15
DATABASE_POOL_OVERFLOW=15
```

This reduces max connections from 50 to 30, freeing PostgreSQL resources for admin tools, migrations, and monitoring. With `pool_use_lifo=True`, most requests will reuse the same few connections anyway.

**Expected impact**: Reduced PostgreSQL memory usage (~5MB per idle connection), cleaner connection state, faster pool checkout under contention.

**Implementation effort**: LOW -- Environment variable changes.

**Risks**: Under extreme load, may see pool exhaustion sooner. Monitor `checkedout` vs `pool_size` via the existing `get_pool_status()` endpoint.

**Reference**: [SQLAlchemy Connection Pooling documentation](https://docs.sqlalchemy.org/en/20/core/pooling.html) -- pool_use_lifo "allows excess connections to be cleaned up from the pool more quickly."

---

### 7. [MEDIUM] Evaluate gRPC for AI Service Communication

**What**: All AI service communication uses HTTP/1.1 with JSON payloads via httpx. For image-heavy payloads (base64-encoded images sent to CLIP, Florence, Enrichment), HTTP overhead includes JSON serialization, base64 encoding (33% size increase), and HTTP header overhead.

**Benchmark data** from industry sources:

- gRPC delivers 7-10x throughput improvement over REST
- 48% average latency reduction
- 60% bandwidth reduction via binary Protocol Buffers
- 40% less CPU, 30% less memory for equivalent workloads

**For this system specifically**:

- YOLO26 detector sends raw image bytes (multipart/form-data) -- moderate overhead
- CLIP/Florence/Enrichment send base64-encoded images in JSON -- significant overhead
- Nemotron LLM sends text prompts and receives text -- minimal overhead from JSON

**Recommended approach**: Start with the highest-traffic path: YOLO26 detection. Replace HTTP POST with gRPC unary call. Measure latency improvement. Then extend to CLIP/Florence/Enrichment.

**Expected impact**: 30-50% latency reduction for image-heavy AI calls (CLIP embedding, Florence extraction). Nemotron LLM calls would see minimal improvement since payloads are text.

**Implementation effort**: HIGH -- Requires defining .proto files, generating Python stubs, updating all AI service servers to serve gRPC, and updating all client code. Would need to maintain HTTP endpoints for health checks during transition.

**Risks**: Significant migration effort. Debugging gRPC is harder than HTTP. Browser-based tools cannot directly test gRPC endpoints. May not be worth the effort given that AI inference time (100-2000ms) dominates over HTTP overhead (5-20ms).

**Recommendation**: Defer unless latency profiling shows HTTP overhead is a significant bottleneck (>10% of total request time). The persistent httpx connection pooling already eliminates TCP setup overhead.

---

### 8. [MEDIUM] Add PgBouncer for Connection Multiplexing

**What**: The application already has PgBouncer support built in (`use_pgbouncer=True` setting), but it is disabled. With a single-worker architecture, PgBouncer provides limited benefit. However, if the architecture scales to multiple workers or separate pipeline containers (as suggested in the Dockerfile comments), PgBouncer becomes essential.

**Current state**: The prepared statement cache is automatically disabled when `use_pgbouncer=True` is set, showing this was already considered.

**Recommended change for scaling**: When moving to multi-worker or multi-container architecture:

```env
USE_PGBOUNCER=true
# PgBouncer config: transaction pooling mode
# pool_mode = transaction
# max_client_conn = 200
# default_pool_size = 20
```

**Expected impact**: Enables scaling to multiple backend instances sharing a smaller PostgreSQL connection pool. Transaction pooling mode is compatible with the application's session patterns.

**Implementation effort**: LOW to deploy PgBouncer container, MEDIUM to verify all query patterns work in transaction mode.

**Risks**: Prepared statements do not work in transaction mode (handled by existing `use_pgbouncer` setting). SET commands and advisory locks may behave differently (advisory locks are used for schema init -- needs testing).

---

### 9. [MEDIUM] Optimize Materialized Views for Time-Series Queries

**What**: The backend has materialized view support (`backend/services/materialized_views.py`, `backend/services/materialized_view_scheduler.py`) for pre-computing expensive queries. For time-series security event data, materialized views are critical for dashboard performance.

**Recommended additional patterns**:

A. **Time-bucketed materialized views**: Create hourly/daily aggregation views for event counts, detection distributions, and risk score distributions. These avoid expensive GROUP BY queries on the main events table.

B. **Partial indexes**: Add partial indexes for hot queries (e.g., `WHERE risk_score > 70` for high-risk events, `WHERE created_at > now() - interval '24 hours'` for recent events).

C. **BRIN indexes**: For the events table which is append-only and ordered by timestamp, BRIN (Block Range INdex) indexes are 100x smaller than B-tree indexes and faster for range scans.

**Expected impact**: 10-100x improvement for dashboard aggregate queries. BRIN indexes reduce index storage by 95% compared to B-tree for time-series data.

**Implementation effort**: MEDIUM -- Requires Alembic migrations and scheduling refresh cycles.

**Risks**: Materialized views consume storage and need refresh scheduling. Stale data between refreshes may confuse users. The existing scheduler already handles this.

---

### 10. [MEDIUM] Python 3.14 Free-Threaded Mode Assessment

**What**: The Dockerfile has the free-threaded Python image commented out:

```dockerfile
# FROM ghcr.io/mikesvoboda/python:3.14t-slim-bookworm AS base
FROM ghcr.io/mikesvoboda/nemotron-base:latest AS base
```

The application already has full free-threading detection and adaptation (`backend/core/free_threading.py`, `check_free_threading_support()`, `verify_free_threading()`). When free-threading is active, concurrency limits auto-scale: inference semaphore goes from 4 to 20, preprocessing workers from 2 to 8.

**Current status (2026-02)**: Python 3.14 free-threaded build is a first-class citizen with Phase 2 acceptance. FastAPI supports Python 3.14. However, the codebase uses several C extensions (PIL/Pillow, numpy, torch, ultralytics) that may re-enable the GIL when imported.

**Recommendation**: Test in a staging environment:

1. Build with the free-threaded base image
2. Check `sys._is_gil_enabled()` after importing all dependencies
3. Benchmark batch processing throughput with GIL disabled vs enabled
4. Monitor for segfaults or race conditions in C extension code

**Expected impact**: If all extensions support free-threading, potential 2-4x throughput improvement for CPU-bound preprocessing (image loading, resizing, base64 encoding) that currently runs in ThreadPoolExecutor with GIL limitations.

**Implementation effort**: LOW to test (uncomment Dockerfile line), MEDIUM to validate and resolve incompatibilities.

**Risks**: C extensions may silently re-enable GIL, negating benefits. Some extensions may have thread-safety bugs in free-threaded mode. The 5-10% single-threaded performance penalty may not be offset by parallelism gains for I/O-bound workloads.

**Reference**: [Python free-threading documentation](https://docs.python.org/3/howto/free-threading-python.html) -- "Third-party packages, in particular ones with an extension module, may not be ready for use in a free-threaded build."

---

### 11. [LOW] Redis Streams Optimization

**What**: Redis Streams is the correct choice for the detection pipeline queue. It provides consumer groups for worker scaling, message acknowledgment with automatic redelivery, and stream trimming. The current configuration is reasonable:

- `DEFAULT_STREAM_MAXLEN = 10000` entries
- `DEFAULT_BLOCK_MS = 5000` (5s block timeout)
- `DEFAULT_CLAIM_MIN_IDLE_MS = 60000` (1min before claiming)
- `DEFAULT_MAX_DELIVERY_COUNT = 3` before DLQ

**Minor optimizations**:

A. **Reduce BLOCK_MS to 2000**: The 5s block timeout means workers are idle for up to 5s between messages during low traffic. Reducing to 2s improves responsiveness for sporadic events.

B. **Use XAUTOCLAIM instead of XCLAIM+XPENDING**: If using Redis 6.2+, `XAUTOCLAIM` combines pending message discovery and claiming into a single command, reducing round trips.

C. **Consider pipeline/MULTI for batch ack**: When acknowledging multiple messages, use Redis pipelines to batch the XACK commands.

**Expected impact**: Minor latency improvements (2-3s faster response to sporadic events). Pipeline batching reduces Redis round trips.

**Implementation effort**: LOW -- Single constant change for BLOCK_MS, minimal code change for XAUTOCLAIM.

**Risks**: Minimal. Lower BLOCK_MS slightly increases Redis CPU from more frequent polling.

---

### 12. [LOW] Batch Processing Window Optimization

**What**: The current batch processing uses fixed 90-second windows with 30-second idle timeout. This means:

- Best case: Events batch for up to 90s before LLM analysis
- Worst case: Single event waits 30s (idle timeout) before processing
- Average latency: ~45-60s from detection to analysis

**Alternative patterns**:

A. **Adaptive batching**: Start with a short timeout (5s), extend if events are still arriving (up to max window). Reduces latency for sporadic events while maintaining batching benefits for bursts.

B. **Size-triggered batching**: Process batch when it reaches N events OR when timeout expires, whichever comes first. This ensures large batches process quickly without waiting for the full window.

C. **Priority-based batching**: High-confidence detections (person detected at night) get shorter batch windows (10s) while routine detections (pet during day) can batch longer.

**Expected impact**: Reduces average event-to-analysis latency from ~45s to ~15-20s for adaptive batching, while maintaining throughput for burst scenarios.

**Implementation effort**: MEDIUM -- Requires refactoring the batch timeout worker logic.

**Risks**: Shorter batch windows increase LLM calls (less batching), increasing GPU utilization. Must balance latency vs throughput.

---

### 13. [LOW] Service Architecture Considerations

**What**: With 203 service files, the backend is a substantial monolith. The Dockerfile comments already suggest extracting background services to separate containers (`python -m backend.services.pipeline_workers`).

**Current single-worker constraint**: Multiple uvicorn workers would cause duplicate file processing, race conditions in pipeline workers, and duplicate WebSocket broadcasts.

**Recommended evolution path**:

1. **Short-term**: Keep monolith but extract pipeline workers to separate process (already supported)
2. **Medium-term**: Use Redis Streams consumer groups for worker scaling (infrastructure already in place)
3. **Long-term**: Consider service mesh only if scaling beyond 3-4 backend instances

**Assessment**: A service mesh is overkill for a single-user home security deployment. The existing circuit breaker pattern (10 per-endpoint breakers) and Redis-based coordination are sufficient. The DI container (`backend/core/container.py`) and health service registry provide adequate internal coordination.

**Expected impact**: Separating pipeline workers enables independent scaling of detection/analysis workload from API request handling.

**Implementation effort**: MEDIUM -- The `pipeline_workers.py` standalone mode exists but needs testing and docker-compose configuration.

**Risks**: Adds operational complexity (more containers to manage). Only justified if the single-worker process becomes a bottleneck.

---

### 14. [LOW] Merge Conflict Resolution in clip_client.py

**What**: The file `backend/services/clip_client.py` has unresolved Git merge conflict markers at lines 135-158:

```python
<<<<<<< HEAD
        _cb_config = CircuitBreakerConfig(
=======
        _cb_kwargs = dict(
>>>>>>> 95005836
```

This is a blocking issue that must be resolved before the code can function. The HEAD version (using `CircuitBreakerConfig`) is the correct pattern matching the rest of the codebase.

**Implementation effort**: LOW -- 5 minutes to resolve.

**Risks**: Code will not run until resolved.

---

## Summary: Prioritized Action Plan

| Priority | Recommendation                           | Impact   | Effort | Risk   |
| -------- | ---------------------------------------- | -------- | ------ | ------ |
| 1        | Fix NemotronAnalyzer httpx pooling       | HIGH     | LOW    | LOW    |
| 2        | Fix Redis eviction policy (volatile-lru) | HIGH     | LOW    | LOW    |
| 3        | Reduce middleware overhead               | HIGH     | MEDIUM | MEDIUM |
| 4        | Structured concurrency for AI enrichment | HIGH     | MEDIUM | LOW    |
| 5        | Resolve clip_client.py merge conflicts   | BLOCKING | LOW    | NONE   |
| 6        | Increase pool warming target             | MEDIUM   | LOW    | LOW    |
| 7        | Right-size database pool                 | MEDIUM   | LOW    | LOW    |
| 8        | BRIN indexes + partial indexes           | MEDIUM   | MEDIUM | LOW    |
| 9        | Test free-threaded Python 3.14t          | MEDIUM   | MEDIUM | MEDIUM |
| 10       | PgBouncer for future scaling             | MEDIUM   | MEDIUM | LOW    |
| 11       | gRPC for AI communication                | MEDIUM   | HIGH   | MEDIUM |
| 12       | Redis Streams tuning                     | LOW      | LOW    | LOW    |
| 13       | Adaptive batch windows                   | LOW      | MEDIUM | MEDIUM |
| 14       | Service extraction planning              | LOW      | MEDIUM | LOW    |

**Quick wins (items 1, 2, 5, 6, 7)** can be completed in a single session with immediate measurable improvement. Items 3 and 4 require more careful implementation but deliver the next tier of performance gains. Items 9-14 are strategic improvements for future scaling.

---

## References

### Documentation Sources

- [FastAPI Release Notes](https://fastapi.tiangolo.com/release-notes/)
- [httpx Clients - Connection Pooling](https://www.python-httpx.org/advanced/clients/)
- [httpx Resource Limits](https://www.python-httpx.org/advanced/resource-limits/)
- [SQLAlchemy Connection Pooling](https://docs.sqlalchemy.org/en/20/core/pooling.html)
- [SQLAlchemy asyncpg Pool Tuning](https://www.pythontutorials.net/blog/how-to-properly-set-pool-size-and-max-overflow-in-sqlalchemy-for-asgi-app/)
- [Redis Key Eviction](https://redis.io/docs/latest/develop/reference/eviction/)
- [Redis Streams vs Pub/Sub](https://dev.to/lovestaco/redis-pubsub-vs-redis-streams-a-dev-friendly-comparison-39hm)
- [Python Free-Threading Guide](https://docs.python.org/3/howto/free-threading-python.html)
- [Python 3.14 Free-Threading](https://towardsdatascience.com/python-3-14-and-the-end-of-the-gil/)
- [gRPC vs REST Benchmarks 2025](https://markaicode.com/grpc-vs-rest-benchmarks-2025/)
- [Scaling LLM Inference: REST to gRPC](https://medium.com/@michael.hannecke/scaling-llm-inference-from-rest-to-grpc-to-gain-performance-in-production-0190b0469f4c)
- [8 httpx + asyncio Patterns](https://medium.com/@sparknp1/8-httpx-asyncio-patterns-for-safer-faster-clients-f27bc82e93e6)
- [httpx AsyncClient Discussion](https://github.com/encode/httpx/discussions/2662)

### Codebase Files Analyzed

- `/backend/main.py` -- Application entry point, lifespan, middleware stack
- `/backend/core/database.py` -- Database engine, pool configuration, session management
- `/backend/core/redis.py` -- Redis client, connection pools, compression, retry logic
- `/backend/core/config.py` -- Settings (pool sizes, timeouts, feature flags)
- `/backend/core/async_utils.py` -- AsyncTaskGroup, bounded_gather, async I/O helpers
- `/backend/core/free_threading.py` -- Free-threading detection and verification
- `/backend/services/detector_client.py` -- YOLO26 client (persistent httpx)
- `/backend/services/clip_client.py` -- CLIP client (persistent httpx, has merge conflict)
- `/backend/services/florence_client.py` -- Florence-2 client (persistent httpx)
- `/backend/services/enrichment_client.py` -- Enrichment client (persistent httpx)
- `/backend/services/nemotron_analyzer.py` -- LLM client (**per-request httpx -- needs fix**)
- `/backend/services/redis_streams.py` -- Redis Streams consumer groups
- `/backend/Dockerfile` -- Container configuration, uvicorn settings
- `/docker-compose.prod.yml` -- Resource limits, Redis configuration

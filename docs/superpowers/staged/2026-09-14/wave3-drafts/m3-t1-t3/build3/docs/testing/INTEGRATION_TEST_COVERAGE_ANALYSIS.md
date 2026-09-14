# Backend Integration Test Coverage Analysis

**Date**: 2026-01-17
**Analyzer**: Claude Code (Sonnet 4.5)
**Total Integration Tests**: ~2,327 test functions across 129 test files

---

## Executive Summary

**API Route Files**: 27 route modules
**Service Files**: 114 service modules
**Repository Tests**: 5 files (base, camera, detection, entity, event)
**Service Integration Tests**: 3 files (cache_behavior, calibration, model_loaders)

### Key Findings:

- **88.9%** of API routes have integration tests (24/27)
- **13.2%** of services have dedicated integration tests (~15/114)
- **Critical gaps**: Export pipeline, Debug endpoints, RUM metrics, Notification delivery
- **Strong coverage**: WebSocket integration, Database isolation, Error scenarios, Cache invalidation

---

## 1. API Endpoints WITHOUT Integration Tests

### 1.1 Missing Route Integration Tests

#### `/api/exports` - Export Job Management (0% coverage)

**Endpoints missing tests**:

- `POST /api/exports` - Start export job
- `GET /api/exports` - List export jobs with filters
- `GET /api/exports/{job_id}` - Get export status
- `DELETE /api/exports/{job_id}` - Cancel export job
- `GET /api/exports/{job_id}/download` - Download completed file
- `GET /api/exports/{job_id}/download/info` - Download metadata

**Business Impact**: Export is a critical user-facing feature. Lack of tests means:

- No validation of background task execution
- No testing of database + Redis job state coordination
- No verification of progress tracking accuracy
- No cancellation edge case coverage

#### `/api/debug` - Debug Endpoints (0% coverage)

**Endpoints missing tests**:

- `GET /api/debug/config` - Configuration inspection with redaction
- `GET /api/debug/redis` - Redis connection stats
- `GET /api/debug/websocket` - WebSocket connection states
- `GET /api/debug/circuit-breaker` - Circuit breaker states
- `GET /api/debug/pipeline` - Pipeline state (queues, workers, errors)
- `POST /api/debug/log-level` - Runtime log level override
- `GET /api/debug/recordings` - Request/response recordings
- `POST /api/debug/replay/{recording_id}` - Replay recorded requests
- Plus 7+ more debug endpoints

**Business Impact**: Debug endpoints are gated by `debug=True`, but:

- No testing of security (404 when debug=False)
- No validation of sensitive data redaction
- No verification of runtime state inspection accuracy

#### `/api/rum` - Real User Monitoring (0% coverage)

**Endpoints missing tests**:

- `POST /api/rum` - Ingest Core Web Vitals metrics (LCP, FID, INP, CLS, TTFB, FCP)

**Business Impact**: RUM is critical for frontend performance monitoring:

- No validation of Prometheus histogram recording
- No testing of batch ingestion and error handling
- No verification of metric labeling (path, rating)

### 1.2 Partial Coverage Routes (Need Enhancement)

#### `/api/prompt_management` - Partial coverage

**Missing scenarios**:

- Template variable substitution with missing/invalid variables
- A/B testing with multiple active versions
- Version rollback and history tracking
- Template analytics and performance metrics

#### `/api/notification` - Partial coverage

**Missing scenarios**:

- Actual notification delivery (email/webhook with mocked clients)
- Retry logic on delivery failures
- Rate limiting and throttling
- Delivery status tracking

#### `/api/notification_preferences` - Partial coverage

**Missing scenarios**:

- Preference filtering during notification delivery
- Muting rules application
- User-specific channel preferences
- Notification frequency limits

#### `/api/calibration` - Partial coverage

**Missing scenarios**:

- Severity adjustment impact on existing events
- Bulk re-evaluation after calibration changes
- Cache invalidation cascade
- WebSocket broadcast of recalculated risk scores

#### `/api/services` - Partial coverage

**Missing scenarios**:

- Service lifecycle management (start/stop/restart)
- Dependency graph validation
- Health check propagation
- Container orchestration integration

---

## 2. Cross-Service Workflows NOT Tested End-to-End

### 2.1 Export Pipeline (CRITICAL GAP)

**Flow**: Camera → Events → Filter → Export Service → Job Tracker → File Download

**Missing integration tests**:

1. Create export job → Background task starts → Progress updates via WebSocket
2. Filter events by camera/risk/date → Generate CSV/JSON/ZIP
3. Database persistence (ExportJob table) + Redis coordination (JobTracker)
4. Export completion → File ready → Download endpoint serves file
5. Export cancellation during execution → Cleanup and state update
6. Export failure → Error handling → User notification

**Testing gaps**:

- No validation of `BackgroundTasks` execution
- No verification of progress percentage accuracy
- No testing of file generation and serving
- No cancellation race condition tests

### 2.2 Notification Pipeline (HIGH PRIORITY)

**Flow**: Event Creation → Alert Rule Evaluation → Notification Delivery

**Missing integration tests**:

1. Event created with high risk → Alert rule matches → Notification queued
2. Notification preferences applied → Channel selection (email/webhook)
3. Email delivery via SMTP (mocked) → Delivery confirmation
4. Webhook delivery via HTTP POST (mocked) → Retry on failure
5. Deduplication → Same event doesn't trigger duplicate notifications
6. Rate limiting → Max notifications per hour enforced

**Testing gaps**:

- No actual delivery tests (even with mocked clients)
- No retry logic validation
- No preference filtering tests
- No deduplication verification

### 2.3 Calibration Impact Pipeline (MEDIUM PRIORITY)

**Flow**: Severity Adjustment → Re-evaluation → Event Risk Score Update

**Missing integration tests**:

1. Adjust severity multiplier for "person" class → Save to database
2. Trigger re-evaluation of all events with "person" detections
3. Update risk scores in database (batch update)
4. Invalidate cache for affected events
5. Broadcast WebSocket notification of changes
6. Verify alerts triggered/dismissed based on new scores

**Testing gaps**:

- No end-to-end impact validation
- No cache invalidation cascade tests
- No WebSocket broadcast verification
- No alert re-evaluation tests

### 2.4 Debug Recording Pipeline (LOW PRIORITY)

**Flow**: Request Recording → Storage → Replay → Response Validation

**Missing integration tests**:

1. Enable recording → Make API request → Request stored with sanitization
2. List recordings → Verify metadata (timestamp, method, path)
3. Replay recording → Verify same response returned
4. Correlation ID preserved through replay
5. Sensitive data (passwords, API keys) redacted in storage

**Testing gaps**:

- No recording storage verification
- No replay accuracy tests
- No sanitization validation
- No correlation ID propagation tests

### 2.5 Container Orchestration Pipeline (MEDIUM PRIORITY)

**Flow**: Service Discovery → Health Monitoring → Container Start/Stop

**Missing integration tests**:

1. Discover running containers → Parse labels → Build service map
2. Health check all services → Update status in registry
3. Start missing container → Wait for healthy → Update status
4. Stop unhealthy container → Cleanup resources → Restart
5. Dependency graph validation → Ensure correct start order

**Testing gaps**:

- No Docker/Podman API integration tests
- No service discovery validation
- No dependency graph tests
- No container lifecycle tests

### 2.6 Background Evaluation Pipeline (LOW PRIORITY)

**Flow**: Scheduled Re-evaluation → Batch Processing → Updates

**Missing integration tests**:

1. Scheduled task triggers → Fetch events needing re-evaluation
2. Batch process events (100 at a time) → Call LLM
3. Update risk scores in database → Commit batch
4. Broadcast WebSocket notifications → Clients receive updates
5. Error handling → Failed events moved to DLQ

**Testing gaps**:

- Only basic test exists (`test_background_evaluator.py`)
- No batch processing validation
- No error scenario tests
- No WebSocket broadcast verification

### 2.7 Prompt Management Pipeline (LOW PRIORITY)

**Flow**: Template Selection → Variable Substitution → LLM Invocation

**Missing integration tests**:

1. Create prompt template with variables → Save to database
2. Create prompt version → Set as active
3. Select template for event analysis → Substitute variables
4. Invoke LLM with rendered prompt → Capture response
5. A/B testing → Randomly select version → Track results
6. Analytics → Compare performance across versions

**Testing gaps**:

- No template variable substitution tests
- No A/B testing validation
- No version management tests
- No analytics tracking tests

---

## 3. Database Operations Lacking Integration Coverage

### 3.1 Missing Repository Tests

**Repositories without dedicated test files**:

1. **`AlertRepository`** - Alert CRUD operations
2. **`AlertRuleRepository`** - Rule management and evaluation
3. **`ZoneRepository`** - Zone geometry and intersection queries
4. **`ExportJobRepository`** - Export job persistence
5. **`GPUStatsRepository`** - Time-series GPU metrics
6. **`LogRepository`** - Log storage and retrieval
7. **`PromptRepository`** - Prompt template management

**Impact**: No verification of:

- Complex query correctness
- Index usage and performance
- Constraint enforcement (unique, foreign key)
- Cascade delete behavior
- Transaction isolation

### 3.2 Complex Query Integration (Not Covered)

**Missing query tests**:

1. **Time-series queries with partitioning**:

   - GPU stats queries across multiple partitions
   - Log retrieval with time range filters
   - Partition pruning verification

2. **Aggregation queries**:

   - Dashboard analytics (event counts by camera/risk)
   - Detection frequency by object type
   - Alert rule trigger statistics

3. **Full-text search**:

   - Trigram index usage for event search
   - Search query performance validation
   - Ranking and relevance testing

4. **Spatial queries**:

   - Zone intersection with detection bboxes
   - Point-in-polygon tests for geofencing
   - Geometry validation and normalization

5. **Cursor pagination**:
   - Large result set pagination (1000+ records)
   - Complex filtering + sorting + pagination
   - Cursor stability across concurrent updates

### 3.3 Transaction Scenarios (Limited Coverage)

**Missing transaction tests**:

1. **Multi-table updates with rollback**:

   - Event creation + detection creation + cache update (atomic)
   - Rollback on any failure → Verify clean state

2. **Savepoint nested transactions**:

   - Outer transaction → Savepoint → Inner update fails → Rollback to savepoint
   - Verify partial commit scenarios

3. **Optimistic locking**:

   - Version field increment on update
   - Concurrent update detection → Retry logic
   - Lost update prevention

4. **Foreign key cascade operations**:
   - Delete camera → Cascade to events, detections, zones
   - Performance under load (1000+ child records)
   - Deadlock prevention and recovery

### 3.4 Database Performance Under Load (Limited Coverage)

**Missing performance tests**:

1. **Connection pool exhaustion**:

   - 100 concurrent requests → Pool saturated → Request queuing
   - Recovery after pool exhaustion → Verify no leaks

2. **Slow query timeout**:

   - Query exceeds timeout → Cancelled gracefully
   - No lingering connections or locks

3. **Index usage validation**:

   - EXPLAIN ANALYZE for complex queries
   - Verify index scan (not seq scan) for critical paths

4. **Partition pruning**:
   - Time-range query → Only relevant partitions scanned
   - Verify partition elimination in query plan

---

## 4. Missing Error Scenario Integration Tests

### 4.1 Service Degradation Scenarios

**Missing tests**:

1. **Redis unavailable → Graceful degradation**:

   - Cache disabled → Fall back to database-only mode
   - Job tracker disabled → Jobs still run (no progress tracking)
   - Verify no crashes or deadlocks

2. **LLM timeout → Fallback to default risk scores**:

   - Nemotron service slow/unresponsive → Timeout after 30s
   - Assign default risk score (50) → Log warning
   - Verify event still created successfully

3. **Object detection service down → Queue backpressure**:

   - YOLO26 unavailable → Detection queue grows
   - Backpressure mechanism → Stop accepting new files
   - Recovery when service returns → Drain queue

4. **Database connection pool exhausted → Request queuing**:
   - Pool size = 10 → 100 concurrent requests
   - Requests queued → Wait for available connection
   - Timeout after 30s → Return 503 Service Unavailable

### 4.2 Data Integrity Scenarios

**Missing tests**:

1. **Duplicate detection handling**:

   - Unique constraint violation → Catch IntegrityError
   - Return existing record instead of failing
   - Verify idempotency

2. **Orphaned records cleanup**:

   - Cascade delete fails → Manual cleanup required
   - Scheduled job detects orphans → Deletes them
   - Verify referential integrity restored

3. **Corrupt JSON field data**:

   - Invalid JSON in JSONB column → Validation error
   - Graceful error handling → Log and skip
   - Prevent entire batch failure

4. **Missing foreign key reference**:
   - Event references non-existent camera → FK constraint fails
   - Handle gracefully → Create placeholder camera or reject event
   - Prevent data inconsistency

### 4.3 Concurrent Modification Scenarios

**Missing tests**:

1. **Race conditions on camera status updates**:

   - Two workers update same camera status simultaneously
   - Last write wins → Verify no data corruption
   - Test with optimistic locking (version field)

2. **Multiple workers updating same event**:

   - Event risk score updated by calibration AND re-evaluation
   - Detect concurrent update → Retry with latest version
   - Verify no lost updates

3. **Alert rule modification during evaluation**:

   - Rule modified while being evaluated for events
   - Consistent read → Use snapshot isolation
   - Verify no race conditions

4. **Export job cancellation during execution**:
   - Export running → User cancels → Background task aborted
   - Cleanup partial files → Update database status
   - Verify no zombie jobs

### 4.4 Resource Exhaustion Scenarios

**Missing tests**:

1. **Disk full during export file creation**:

   - Export generates large file → Disk full error
   - Graceful error handling → Clean up partial file
   - User notified of failure

2. **Memory pressure during large batch processing**:

   - Batch size = 10,000 events → Memory usage spikes
   - Implement streaming/pagination → Keep memory constant
   - Verify no OOM errors

3. **File descriptor exhaustion from WebSocket connections**:

   - 1,000 concurrent WebSocket connections → FD limit reached
   - Reject new connections → Return 503
   - Verify no crashes

4. **CPU saturation during parallel detections**:
   - 100 detection jobs queued → CPU maxed out
   - Rate limiting → Max 10 concurrent detections
   - Verify response time degradation gracefully

### 4.5 External Dependency Failures

**Missing tests**:

1. **S3/file storage unavailable during media retrieval**:

   - Media endpoint → S3 timeout
   - Return 503 Service Unavailable → Retry later
   - Verify no crashes

2. **SMTP server timeout during notification delivery**:

   - Email send → SMTP timeout after 30s
   - Retry with exponential backoff → Max 3 retries
   - Move to DLQ if all retries fail

3. **Webhook endpoint unreachable**:

   - Webhook URL → Connection refused
   - Retry with backoff → Mark as failed after 3 attempts
   - User notified of delivery failure

4. **Monitoring target scraping failures**:
   - Prometheus scrape → Target down
   - Mark target as unhealthy → Continue scraping others
   - Verify no monitoring pipeline breakage

---

## 5. Recommended High-Priority Integration Tests

### Priority 1: Critical Business Flows

#### 1. Export Pipeline Integration

**File**: `backend/tests/integration/test_export_pipeline_integration.py`

**Test scenarios**:

```python
async def test_export_pipeline_csv_success():
    """Test complete export pipeline: create → process → download."""
    # 1. Create events in database
    # 2. Start export job (CSV format)
    # 3. Verify job status transitions: pending → running → completed
    # 4. Check progress updates via job tracker
    # 5. Verify file created on disk
    # 6. Download file → Verify CSV contents
    # 7. Verify database persistence (ExportJob table)

async def test_export_cancellation():
    """Test export cancellation during execution."""
    # 1. Start long-running export
    # 2. Cancel export mid-execution
    # 3. Verify background task stopped
    # 4. Check partial file cleanup
    # 5. Verify database status = FAILED with cancellation message

async def test_export_with_filters():
    """Test export with camera, risk, and date filters."""
    # 1. Create events across multiple cameras and risk levels
    # 2. Export with camera_id filter
    # 3. Verify only matching events included
    # 4. Test risk_level filter
    # 5. Test date range filter
    # 6. Test combination of filters

async def test_export_error_handling():
    """Test export failure scenarios."""
    # 1. Simulate disk full during export
    # 2. Verify job status = FAILED
    # 3. Check error message recorded
    # 4. Verify partial file cleaned up
```

**Dependencies**: ExportService, JobTracker, Database, FileResponse

---

#### 2. Notification Delivery Integration

**File**: `backend/tests/integration/test_notification_delivery_integration.py`

**Test scenarios**:

```python
async def test_notification_email_delivery():
    """Test email notification delivery pipeline."""
    # 1. Create high-risk event
    # 2. Alert rule matches event
    # 3. Notification queued (email channel)
    # 4. Mock SMTP client sends email
    # 5. Verify delivery status tracked
    # 6. Check deduplication (same event doesn't trigger duplicate)

async def test_notification_webhook_delivery():
    """Test webhook notification delivery."""
    # 1. Configure webhook notification channel
    # 2. High-risk event created
    # 3. Mock HTTP client posts to webhook URL
    # 4. Verify payload format
    # 5. Test retry on failure (3 attempts)
    # 6. Verify DLQ on permanent failure

async def test_notification_preferences_filtering():
    """Test notification preference filtering."""
    # 1. User mutes notifications for camera "backyard"
    # 2. High-risk event from backyard camera
    # 3. Verify notification NOT sent
    # 4. Event from "front_door" camera → Notification sent

async def test_notification_rate_limiting():
    """Test notification rate limiting."""
    # 1. Create 100 high-risk events in 1 minute
    # 2. Verify max 10 notifications sent (rate limit)
    # 3. Remaining events batched into summary notification
```

**Dependencies**: AlertEngine, NotificationService, AlertRuleRepository, SMTP/HTTP mocks

---

#### 3. Calibration Impact Integration

**File**: `backend/tests/integration/test_calibration_impact_integration.py`

**Test scenarios**:

```python
async def test_calibration_adjustment_impact():
    """Test calibration adjustment impact on existing events."""
    # 1. Create 10 events with "person" detections (risk = 60)
    # 2. Adjust severity for "person" class (multiplier 1.0 → 1.5)
    # 3. Trigger re-evaluation of affected events
    # 4. Verify risk scores updated in database (60 → 90)
    # 5. Check cache invalidated for updated events
    # 6. Verify WebSocket broadcast of changes

async def test_calibration_alert_impact():
    """Test calibration impact on alert triggering."""
    # 1. Alert rule: trigger on risk > 75
    # 2. Event with risk = 70 (no alert)
    # 3. Adjust calibration → Risk becomes 80
    # 4. Verify alert now triggered
    # 5. Notification sent to user

async def test_calibration_bulk_reevaluation():
    """Test bulk re-evaluation performance."""
    # 1. Create 1000 events with calibrated object type
    # 2. Adjust calibration
    # 3. Trigger bulk re-evaluation
    # 4. Verify batch processing (100 at a time)
    # 5. Check all 1000 events updated
    # 6. Verify performance acceptable (< 10s for 1000 events)
```

**Dependencies**: CalibrationService, EventRepository, CacheService, WebSocket broadcaster

---

#### 4. Debug Pipeline Integration

**File**: `backend/tests/integration/test_debug_pipeline_integration.py`

**Test scenarios**:

```python
async def test_debug_recording_pipeline():
    """Test request recording and replay."""
    # 1. Enable debug mode (settings.debug = True)
    # 2. Enable recording
    # 3. Make API request (POST /api/events)
    # 4. Verify request recorded with sanitized data
    # 5. List recordings → Verify metadata correct
    # 6. Replay recording → Verify same response
    # 7. Check correlation ID preserved

async def test_debug_endpoint_security():
    """Test debug endpoints security gating."""
    # 1. Disable debug mode (settings.debug = False)
    # 2. Request debug endpoint → Verify 404 (not 403)
    # 3. Enable debug mode
    # 4. Request debug endpoint → Verify 200 with data

async def test_debug_sensitive_data_redaction():
    """Test sensitive data redaction in debug output."""
    # 1. Request /api/debug/config
    # 2. Verify DATABASE_URL password redacted
    # 3. Verify API keys redacted
    # 4. Check Redis password redacted
```

**Dependencies**: Debug routes, Settings, Request recording service

---

#### 5. RUM Metrics Integration

**File**: `backend/tests/integration/test_rum_metrics_integration.py`

**Test scenarios**:

```python
async def test_rum_metrics_ingestion():
    """Test Core Web Vitals ingestion."""
    # 1. POST batch of RUM metrics (LCP, FID, INP, CLS, TTFB, FCP)
    # 2. Verify Prometheus histograms recorded
    # 3. Check labels (path, rating) applied correctly
    # 4. Query Prometheus → Verify metrics retrievable

async def test_rum_batch_processing():
    """Test batch ingestion with errors."""
    # 1. POST batch with 10 valid + 2 invalid metrics
    # 2. Verify 10 metrics processed successfully
    # 3. Check 2 errors returned in response
    # 4. Verify partial success handled gracefully

async def test_rum_metric_validation():
    """Test metric validation and error handling."""
    # 1. POST invalid metric name → Verify rejected
    # 2. POST negative metric value → Verify rejected
    # 3. POST missing required fields → Verify 422 error
```

**Dependencies**: RUM routes, Prometheus metrics, httpx AsyncClient

---

### Priority 2: Service Integration

#### 6. Container Orchestration Integration

**File**: `backend/tests/integration/test_container_orchestration_integration.py`

**Test scenarios**:

- Service discovery from Docker/Podman
- Health check propagation
- Container start/stop coordination
- Dependency graph validation

---

#### 7. Background Evaluator Integration

**File**: `backend/tests/integration/test_background_evaluator_integration.py`

**Test scenarios**:

- Scheduled re-evaluation task execution
- Batch processing with database updates
- WebSocket notifications of changes
- Error handling and DLQ

---

#### 8. Prompt Management Integration

**File**: `backend/tests/integration/test_prompt_management_integration.py`

**Test scenarios**:

- Template CRUD operations
- Variable substitution
- A/B testing with version selection
- Analytics tracking

---

#### 9. Repository CRUD Integration

**Files**: `test_alert_repository.py`, `test_zone_repository.py`, etc.

**Test scenarios**:

- Complete CRUD operations with real database
- Complex queries and filters
- Cascade operations and constraints
- Index usage verification

---

### Priority 3: Error Handling

#### 10. Service Degradation Integration

**File**: `backend/tests/integration/test_service_degradation_integration.py`

**Test scenarios**:

- Redis unavailable → DB-only mode
- LLM timeout → Default risk scores
- Detection service down → Queue backpressure
- Database pool exhausted → Request queuing

---

#### 11. Data Integrity Integration

**File**: `backend/tests/integration/test_data_integrity_integration.py`

**Test scenarios**:

- Duplicate detection handling
- Orphaned record cleanup
- Corrupt JSON field recovery
- Foreign key constraint violations

---

#### 12. Concurrent Operations Integration

**File**: `backend/tests/integration/test_concurrent_operations_integration.py`

**Test scenarios**:

- Race conditions on camera status
- Multiple workers updating same event
- Alert rule modification during evaluation
- Export cancellation during execution

---

## Test Coverage Metrics

### Current Coverage

- **API Routes Tested**: 24/27 (88.9%)
- **Service Integration Tests**: ~15/114 services (13.2%)
- **Repository Tests**: 5 repositories (Camera, Detection, Event, Entity, Base)
- **WebSocket Tests**: 3 files (basic, auth, broadcast)
- **Error Scenario Tests**: 64 files with error tests (~50% coverage estimate)

### Gaps by Category

1. **Export workflows**: 0% integration coverage ❌
2. **Debug endpoints**: 0% integration coverage ❌
3. **RUM metrics**: 0% integration coverage ❌
4. **Notification delivery**: Partial (no actual delivery tests) ⚠️
5. **Calibration impact**: Partial (severity logic only) ⚠️
6. **Container orchestration**: No integration tests ❌
7. **Background evaluation**: Basic test only (no complex scenarios) ⚠️

### Strong Coverage Areas

1. **WebSocket integration**: 3 dedicated test files ✅
2. **Database isolation**: Comprehensive transaction tests ✅
3. **Error scenarios**: 64+ files with error handling ✅
4. **Cache invalidation**: Multiple test files for cache consistency ✅
5. **API endpoint CRUD**: 24/27 routes tested ✅

---

## Implementation Recommendations

### Test Development Strategy

#### Phase 1: Critical Gaps (Weeks 1-4)

**Week 1-2**: Export + Debug pipeline integration tests

- `test_export_pipeline_integration.py` (Priority 1.1)
- `test_debug_pipeline_integration.py` (Priority 1.4)

**Week 3-4**: Notification + Calibration integration tests

- `test_notification_delivery_integration.py` (Priority 1.2)
- `test_calibration_impact_integration.py` (Priority 1.3)

#### Phase 2: Service Integration (Weeks 5-8)

**Week 5-6**: RUM + Container orchestration tests

- `test_rum_metrics_integration.py` (Priority 1.5)
- `test_container_orchestration_integration.py` (Priority 2.1)

**Week 7-8**: Repository pattern completion

- `test_alert_repository.py`
- `test_zone_repository.py`
- `test_export_job_repository.py`
- Other missing repository tests (Priority 2.4)

#### Phase 3: Error Scenarios (Weeks 9-10)

**Week 9-10**: Error handling and degradation tests

- `test_service_degradation_integration.py` (Priority 3.1)
- `test_data_integrity_integration.py` (Priority 3.2)
- `test_concurrent_operations_integration.py` (Priority 3.3)

---

### Testing Patterns to Use

#### 1. Real Database Operations

```python
# Use testcontainers PostgreSQL or local PostgreSQL
async with get_session() as session:
    camera = Camera(id="test_cam", name="Test Camera")
    session.add(camera)
    await session.commit()
    # Verify database state
```

#### 2. Mock External Dependencies

```python
# Mock SMTP for email notifications
with patch("smtplib.SMTP") as mock_smtp:
    mock_smtp.return_value.sendmail = MagicMock()
    # Test notification delivery
```

#### 3. Redis Integration

```python
# Use testcontainers Redis or local Redis (DB 15)
async with redis_client.pipeline() as pipe:
    await pipe.set("key", "value")
    await pipe.expire("key", 60)
    await pipe.execute()
```

#### 4. Background Task Testing

```python
# Use FastAPI BackgroundTasks
background_tasks = BackgroundTasks()
response = await client.post("/api/exports", json={...})
# Wait for background task completion
await asyncio.sleep(0.1)
# Verify task side effects
```

#### 5. WebSocket Integration

```python
# Use httpx websocket_connect
async with client.websocket_connect("/api/ws") as ws:
    await ws.send_json({"type": "subscribe"})
    response = await ws.receive_json()
    assert response["type"] == "subscribed"
```

#### 6. Parallel Execution Safety

```python
# Use worker-isolated databases with pytest-xdist
@pytest.fixture
async def worker_db(worker_id):
    """Create isolated database for each xdist worker."""
    db_name = f"test_db_{worker_id}"
    # Setup worker-specific database
```

---

### Metrics to Track

#### Test Coverage Metrics

- **Integration test count per route/service**

  - Target: 100% of API routes
  - Target: 50% of service modules

- **End-to-end workflow coverage percentage**

  - Target: 100% of critical user-facing workflows
  - Target: 80% of internal background workflows

- **Error scenario coverage by category**

  - Service degradation: 100%
  - Data integrity: 100%
  - Concurrent operations: 80%
  - Resource exhaustion: 80%
  - External dependencies: 80%

- **Database operation coverage**
  - CRUD operations: 100% (all repositories)
  - Complex queries: 80%
  - Transaction scenarios: 80%
  - Performance under load: 60%

#### Quality Metrics

- **Integration test execution time**

  - Target: < 60s for full suite (parallel execution)
  - Current: ~33s with 8 workers

- **Test flakiness rate**

  - Target: < 1% flaky tests
  - Monitor: Retry failures in CI

- **Test maintenance burden**
  - Target: < 5% tests need updates per API change
  - Use shared fixtures to reduce duplication

---

## Conclusion

The backend integration test suite is **strong in fundamentals** (88.9% route coverage, robust error handling) but has **critical gaps in end-to-end workflows** (Export, Debug, RUM, Notification delivery).

**Immediate action items**:

1. Implement Export Pipeline Integration tests (highest priority)
2. Add Debug endpoint security and recording tests
3. Create RUM metrics ingestion tests
4. Enhance Notification delivery with actual client tests
5. Complete missing repository tests (Alert, Zone, ExportJob, etc.)

**Long-term improvements**:

- Increase service integration coverage from 13.2% to 50%
- Add comprehensive error scenario tests for all critical paths
- Implement performance benchmarks for database queries
- Create chaos engineering tests for service resilience

**Estimated effort**: 10 weeks (1 engineer, full-time on testing)

---

**Generated by**: Claude Code (Sonnet 4.5)
**Date**: 2026-01-17
**Source**: `/home/msvoboda/.claude-squad/worktrees/msvoboda/post3_188b99c4c7c05c76/`

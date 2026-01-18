# RUM Integration Tests

## Overview

Integration tests for Real User Monitoring (RUM) metrics ingestion endpoint `/api/rum`.

**File**: `backend/tests/integration/test_rum_api.py`
**Test Count**: 25 integration tests
**Coverage Areas**: Core Web Vitals ingestion, batch processing, validation, Prometheus integration

## Test Classes

### 1. TestRUMCoreWebVitalsIngestion (7 tests)

End-to-end tests for individual Core Web Vitals metrics:

- `test_ingest_lcp_metric_end_to_end` - LCP (Largest Contentful Paint)
- `test_ingest_fid_metric_end_to_end` - FID (First Input Delay)
- `test_ingest_inp_metric_end_to_end` - INP (Interaction to Next Paint)
- `test_ingest_cls_metric_end_to_end` - CLS (Cumulative Layout Shift)
- `test_ingest_ttfb_metric_end_to_end` - TTFB (Time to First Byte)
- `test_ingest_fcp_metric_end_to_end` - FCP (First Contentful Paint)
- `test_ingest_page_load_time_metric_end_to_end` - PAGE_LOAD_TIME

Each test verifies:

1. POST /api/rum accepts the metric
2. Returns success response with correct structure
3. Metric is recorded to Prometheus histograms
4. Metric appears in /api/metrics endpoint

### 2. TestRUMBatchIngestion (4 tests)

Batch metrics ingestion scenarios:

- `test_ingest_multiple_metrics_batch` - Multiple metrics in single request
- `test_ingest_all_core_web_vitals_batch` - All 7 metric types together
- `test_ingest_batch_with_different_paths` - Metrics from different page paths
- `test_ingest_batch_with_different_ratings` - Metrics with good/needs-improvement/poor ratings

Verifies:

- Correct `metrics_count` in response
- No errors in response
- All metrics recorded to Prometheus

### 3. TestRUMMetricsValidation (6 tests)

Error handling and validation:

- `test_empty_metrics_array_returns_422` - Empty metrics array validation
- `test_missing_metrics_field_returns_422` - Missing required field
- `test_invalid_metric_name_returns_422` - Invalid metric name (not in enum)
- `test_invalid_rating_returns_422` - Invalid rating value
- `test_missing_required_fields_returns_422` - Missing required metric fields
- `test_invalid_value_type_returns_422` - Wrong data type for value

All validation tests expect HTTP 422 Unprocessable Entity.

### 4. TestRUMPrometheusIntegration (3 tests)

Prometheus metrics integration:

- `test_rum_metrics_in_prometheus_format` - HELP/TYPE declarations, text/plain content type
- `test_rum_histograms_have_buckets` - Histogram buckets, sum, count entries
- `test_multiple_rum_metric_observations` - Multiple observations accumulate correctly

Verifies:

- Proper Prometheus exposition format
- Histogram structure (buckets, sum, count)
- Metric accumulation across requests

### 5. TestRUMSessionTracking (3 tests)

Session and metadata tracking:

- `test_ingest_with_session_id` - Optional session_id field
- `test_ingest_with_user_agent` - Optional user_agent field
- `test_ingest_with_navigation_type` - Optional navigationType field

Ensures optional tracking fields are accepted without errors.

### 6. TestRUMConcurrentRequests (2 tests)

Concurrency handling:

- `test_concurrent_metric_ingestion` - 5 concurrent requests with same metric type
- `test_concurrent_different_metric_types` - Concurrent requests with different metric types

Verifies:

- All concurrent requests succeed
- No race conditions
- All metrics recorded to Prometheus

## Running Tests

### Local Development

Integration tests require PostgreSQL. Tests are designed to work with:

1. Testcontainers (automatic in CI)
2. Local PostgreSQL with expected credentials

```bash
# Run all RUM integration tests
uv run pytest backend/tests/integration/test_rum_api.py -v

# Run specific test class
uv run pytest backend/tests/integration/test_rum_api.py::TestRUMCoreWebVitalsIngestion -v

# Run specific test
uv run pytest backend/tests/integration/test_rum_api.py::TestRUMCoreWebVitalsIngestion::test_ingest_lcp_metric_end_to_end -v

# Run with keyword filter
uv run pytest backend/tests/integration/ -k "rum" -v
```

### CI/CD

Tests run automatically in CI with testcontainers providing PostgreSQL and Redis.

## Coverage

These integration tests provide:

- **End-to-end coverage**: API request → Prometheus recording → metrics endpoint
- **All metric types**: LCP, FID, INP, CLS, TTFB, FCP, PAGE_LOAD_TIME
- **Batch processing**: Multiple metrics in single request
- **Validation**: Invalid inputs return appropriate 422 errors
- **Concurrency**: Safe handling of simultaneous requests
- **Prometheus integration**: Correct histogram format and accumulation

## Related Files

- **Implementation**: `backend/api/routes/rum.py`
- **Schemas**: `backend/api/schemas/rum.py`
- **Metrics Functions**: `backend/core/metrics.py` (observe*rum*\* functions)
- **Unit Tests**: `backend/tests/unit/api/routes/test_rum.py`
- **Schema Tests**: `backend/tests/unit/api/schemas/test_rum.py`

## Linear Issue

**Issue**: NEM-2760 - Add integration tests for RUM Metrics - Core Web Vitals ingestion
**Status**: Complete ✅
**Test Count**: 25 integration tests
**Files Changed**: `backend/tests/integration/test_rum_api.py` (new)

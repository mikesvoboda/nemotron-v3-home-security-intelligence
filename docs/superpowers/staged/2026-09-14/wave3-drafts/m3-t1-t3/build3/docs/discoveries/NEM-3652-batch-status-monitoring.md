# Discovery: Batch Configuration Lacks Real-Time Status Monitoring

**Issue:** NEM-3652
**Epic:** NEM-3530 (Platform Integration Gaps & Production Readiness)
**Date:** 2026-01-26

## Summary

While batch **configuration is settable** and **basic real-time events are available**, there is significant **gap in quantitative monitoring and performance visibility** for the batch processing pipeline.

## Current Batch Configuration Capabilities

### Backend Configuration (Environment Variables)

- `BATCH_WINDOW_SECONDS` (default: 90) - Time window for grouping detections
- `BATCH_IDLE_TIMEOUT_SECONDS` (default: 30) - Inactivity timeout before closing batch
- `BATCH_CHECK_INTERVAL_SECONDS` (default: 5.0) - Interval between timeout checks
- `BATCH_MAX_DETECTIONS` (default: 500) - Maximum detections per batch

### Configuration API

- Settable via `/api/v1/settings` GET/PATCH endpoints
- Batch settings grouped under "batch" category in SettingsResponse
- Changes persisted to `data/runtime.env` file

### Backend Service

`BatchAggregator` in `backend/services/batch_aggregator.py`:

- Creates time-window based batches
- Applies idle timeout detection
- Enforces max detection size limits
- Manages fast path for high-confidence detections

## Status Information Currently Available

### REST API (`/api/system/pipeline`)

Returns `PipelineStatusResponse` with `BatchAggregatorStatusResponse`:

- Active batch count
- Per-batch: ID, camera_id, detection_count, started_at, age_seconds, last_activity_seconds
- Configured timeouts (batch_window_seconds, idle_timeout_seconds)

### WebSocket Events (Real-time)

1. `detection.new` - Individual detection added to batch
2. `detection.batch` - Batch closed and ready for analysis
3. `batch.analysis_started` - Analysis beginning
4. `batch.analysis_completed` - Analysis finished
5. `batch.analysis_failed` - Analysis failed

### Frontend Visualization

- `BatchStatisticsDashboard` component displays batch statistics
- Uses `useBatchStatistics` hook combining REST API + WebSocket data
- Shows active batches, closure reasons, per-camera breakdown

## Real-Time Monitoring Gaps

### Missing Metrics

1. **Batch Processing Rate Metrics**

   - No per-camera throughput metrics (detections/minute)
   - No queue depth monitoring
   - No batch closure velocity

2. **Queue Depth Visibility**

   - No real-time monitoring of analysis queue size
   - No visibility into batches pending analysis
   - No worker availability metrics

3. **Performance Degradation Indicators**

   - No alerts when batch window approaches timeout
   - No tracking of queue wait time
   - No bottleneck detection

4. **Latency Metrics**

   - Pipeline latency tracked but not exposed in UI
   - No batch-to-analysis delay visibility
   - No per-camera average batch duration

5. **Batch Processing Health Metrics**

   - No batch failure rate tracking
   - No detection of stalled batches
   - No batch reprocessing metrics

6. **Configuration Impact Visibility**
   - No way to preview impact of configuration changes
   - No metrics showing current batch age relative to timeouts

## Recommended Status Metrics to Expose

1. **Queue Metrics:** Active batches in analysis queue, average queue wait time, queue depth trend
2. **Throughput Metrics:** Detections/minute by camera, batches closed/minute, analysis throughput
3. **Performance Metrics:** Average batch age at closure, max batch age, closure reason breakdown
4. **Health Indicators:** Queue backpressure status, analysis queue health, processing velocity

## Architectural Notes

- Batch status stored in Redis with 1-hour TTL
- No persistent batch history in database (session-only in WebSocket)
- REST API provides point-in-time snapshot of active batches only
- No aggregated statistics endpoint for historical analysis

## Status

**Assessment:** Significant gap in operational monitoring. Requires new API endpoints and frontend dashboard enhancements.

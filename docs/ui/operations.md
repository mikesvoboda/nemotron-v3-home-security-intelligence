# Operations

The operations dashboard for pipeline visualization, circuit breaker management, file cleanup, and detailed system metrics through Grafana integration.

## What You're Looking At

The Operations page is your control center for system administration. Unlike the Dashboard which focuses on security events, Operations provides:

- **Pipeline Flow Visualization** - See how images move through the AI processing stages
- **Circuit Breaker Controls** - Reset tripped circuit breakers to restore service connectivity
- **File Operations** - Manage disk storage and run cleanup tasks
- **Debug Mode** - Enable additional diagnostics when troubleshooting

For detailed historical metrics and custom dashboards, click the Grafana link banner at the top.

## Key Components

### Pipeline Flow Visualization

The pipeline visualization shows the four processing stages as a horizontal flow diagram:

```
+--------+     +--------+     +--------+     +---------+
| Files  | --> | Detect | --> | Batch  | --> | Analyze |
+--------+     +--------+     +--------+     +---------+
  Camera        RT-DETR       Group          Nemotron
  Uploads       Detection     Related        Risk
                             Detections      Analysis
```

**Stage Cards**: Each stage displays:

- **Queue depth** - Items waiting to be processed (Detect and Analyze stages)
- **Average latency** - Average processing time (Detect and Analyze stages)
- **Throughput** - Items processed per minute (Batch stage only)
- **Pending count** - Files awaiting processing (Files and Batch stages)

**Health Status Colors**:
| Border Color | Status | Meaning |
|-------------|--------|---------|
| Emerald | Healthy | Queue < 10, latency normal |
| Yellow | Degraded | Queue 10-50 or latency 2-5x baseline |
| Red | Critical | Queue > 50 or latency > 5x baseline |

**Background Workers Section**: Below the pipeline shows worker status with a summary badge indicating how many workers are running (e.g., "5/5 Running"). Click "Expand Details" to see the full list with status for each worker.

Worker types:

- **Watcher** (file_watcher) - Monitors camera FTP directories for new images
- **Detector** (detection_worker) - Processes the detection queue with RT-DETRv2
- **Aggregator** (batch_aggregator) - Groups related detections into batches (90-second windows)
- **Analyzer** (analysis_worker) - Processes batches through Nemotron for risk analysis
- **Cleanup** (cleanup_service) - Removes old data based on retention policy

Worker status dots:

- Green = Running
- Yellow = Degraded
- Red = Stopped

**Total Pipeline Latency**: Shows end-to-end timing (avg, P95, P99) from file arrival to analysis completion. This is calculated by summing the detect and analyze stage latencies.

### Circuit Breakers Panel

Circuit breakers protect the system from cascading failures by temporarily blocking requests to failing services. The panel header displays a summary badge (e.g., "3/3 Healthy") showing how many circuit breakers are in a healthy closed state.

**Circuit States**:
| State | Badge Color | Description |
|-------|------------|-------------|
| closed | Green | Normal operation, requests pass through |
| open | Red | Service failing, requests blocked |
| half_open | Yellow | Testing if service recovered |

**Circuit Breaker Details** (shown for each circuit breaker):

- **Failure count** - Number of consecutive failures
- **Last failure** - Time since the last recorded failure (displayed as relative time, e.g., "5s ago")
- **Configuration** - Threshold, recovery timeout (seconds), and half-open max calls

**Reset Button**: When a circuit breaker is open or half_open, a "Reset" button appears. Clicking it will:

1. Force the circuit back to closed state
2. Clear the failure count
3. Allow requests through immediately

**When to reset**: After fixing the underlying issue (service restarted, network restored, etc.)

**When NOT to reset**: If the root cause hasn't been addressed - the circuit will just trip again.

### File Operations Panel

Manages disk storage and data cleanup tasks. The panel header shows a summary badge with current disk usage percentage and can be collapsed/expanded by clicking the header.

**Disk Usage Section**:

- Progress bar showing percent used (emerald when healthy, yellow when >= 85%)
- Total/used/free space in human-readable format
- Warning banner when usage exceeds 85% with recommendation to run cleanup

**Storage Breakdown**:

- **Thumbnails** - Detection preview images (blue icon)
- **Images** - Full-resolution camera captures from Foscam (purple icon)
- **Video Clips** - Event video recordings (cyan icon)

Each category shows file count and total size.

**Database Records**: Shows counts for:

- Events
- Detections
- GPU Stats
- Logs

**Cleanup Service Summary**:

- Running state with status indicator (green checkmark or gray X)
- Scheduled cleanup time
- Retention period (default: 30 days)
- Next scheduled cleanup timestamp (if available)

**Orphaned Files Warning**: Appears when files exist on disk but aren't referenced in the database. Shows the count of orphaned files and total size that can be reclaimed. Click "Clean Up" to delete these files.

**Run Cleanup Button**: Opens a confirmation modal showing what will be deleted:

- Events older than retention period
- Associated detections
- GPU stats
- Log entries
- Thumbnails
- Estimated space to reclaim

The modal requires explicit confirmation before deletion proceeds.

**Export Data Button**: Initiates data export jobs. Disabled when export jobs are already running or pending.

**Active Exports Section**: Shows recent export jobs with:

- Job status (pending, running, completed, failed)
- Progress bar for running jobs
- Start/creation time
- Error messages for failed jobs

**Last Updated**: Displays when data was last refreshed. Click "Refresh" to manually update.

### Debug Mode Toggle

Available only when the backend has `DEBUG=true` in its configuration. The toggle appears in the page header next to the title.

When enabled (orange highlight):

- The toggle container shows an orange border and background tint
- A wrench icon appears in orange color
- The toggle state persists to localStorage

**Note**: The Circuit Breakers panel component supports an optional WebSocket Broadcasters debug section that can display event and system broadcaster status. This feature requires additional implementation to pass the `debugMode` and `webSocketStatus` props to the panel.

### Grafana Integration Banner

A blue Callout banner appears below the page header, linking to Grafana at the configured URL (default: `http://localhost:3002`).

The banner reads: "View detailed metrics, historical data, and system monitoring dashboards in Grafana." with an "Open Grafana" link that opens in a new tab.

Grafana provides:

- Detailed historical metrics and time-series charts
- Custom dashboards for infrastructure monitoring
- Advanced queries and alerting capabilities
- No authentication required (anonymous access enabled)

## Settings & Configuration

Operations page settings are managed through environment variables and backend configuration:

### Grafana URL

Set via `GRAFANA_URL` environment variable or backend config API. Default: `http://localhost:3002`. The frontend fetches this from `/api/system/config` on page load.

### Cleanup Configuration

- **Retention days** - How long to keep data (default: 30 days)
- **Cleanup time** - Daily scheduled cleanup time
- Configured in backend settings via `CLEANUP_TIME` and `RETENTION_DAYS` environment variables

### Circuit Breaker Thresholds

Each circuit breaker has configurable:

- **Failure threshold** - Failures before opening (default: 5)
- **Recovery timeout** - Seconds before attempting recovery (default: 30)
- **Half-open max calls** - Test calls allowed in half-open state (default: 3)
- **Success threshold** - Successful calls needed to close from half-open (default: 2)

### Debug Mode

Enable by setting `DEBUG=true` in backend environment. The toggle visibility is controlled by the backend config. When shown, the toggle persists its state to localStorage under the key `system-debug-mode`.

### Poll Intervals

- Telemetry data: 5 seconds (automatic polling)
- Worker status: 10 seconds (automatic polling)
- File operations: 30 seconds (configurable via `pollingInterval` prop)

### Section State Persistence

The collapsible sections (Circuit Breakers, File Operations) persist their expanded/collapsed state to localStorage via the `useSystemPageSections` hook.

## Troubleshooting

### Pipeline Stage Shows Critical (Red Border)

**Symptoms**: Queue depth > 50 or latency > 5x baseline

**Possible causes**:

1. AI model service is down or slow
2. GPU is overloaded with other tasks
3. Many cameras detecting motion simultaneously

**Resolution**:

1. Check AI Models on the Dashboard page for service health
2. Review GPU Stats for utilization and memory
3. Check circuit breaker states for tripped services
4. Consider reducing camera sensitivity temporarily

### Circuit Breaker Won't Stay Closed

**Symptoms**: Circuit breaker trips again shortly after reset

**Root cause**: The underlying service is still experiencing failures

**Resolution**:

1. Check service logs for error messages
2. Verify network connectivity to the service
3. Ensure service container is running (check docker/podman)
4. Review resource usage (memory, CPU, GPU)
5. Fix the underlying issue before resetting

### High Disk Usage Warning

**Symptoms**: Yellow warning banner showing > 85% disk usage

**Resolution**:

1. Click "Run Cleanup" to preview deletable data
2. If orphaned files exist, click "Clean Up" in the warning banner
3. Consider reducing retention period in settings
4. Add more disk space if cleanup doesn't free enough

### Worker Shows Stopped (Red Dot)

**Symptoms**: One or more workers have red status dots

**Possible causes**:

1. Container crashed and needs restart
2. Service encountered unrecoverable error
3. Insufficient system resources

**Resolution**:

1. Check container status in Grafana or with `docker ps`
2. Review container logs for error messages
3. Restart the affected container
4. Check system resources (memory, disk)

### Debug Mode Toggle Not Appearing

**Symptoms**: Debug mode toggle is not visible in the header

**Cause**: Backend doesn't have `DEBUG=true` in its environment

**Resolution**: Set `DEBUG=true` in the backend environment and restart the service. This is a security feature - debug mode should only be enabled in development.

### Grafana Link Returns Error

**Symptoms**: Clicking "Open Grafana" shows connection error

**Possible causes**:

1. Grafana container is not running
2. Wrong URL configured
3. Port not exposed correctly

**Resolution**:

1. Check Grafana container status
2. Verify `GRAFANA_URL` configuration
3. Ensure port 3002 is accessible

---

## Technical Deep Dive

For developers wanting to understand the underlying systems.

### Architecture

- **AI Pipeline**: [AI Pipeline Architecture](../architecture/ai-pipeline.md) - How images flow through detection and analysis
- **Resilience Patterns**: [Circuit Breakers and Degradation](../architecture/resilience.md) - Fault tolerance and recovery strategies
- **Real-time Updates**: [Real-time Architecture](../architecture/real-time.md) - WebSocket and event broadcasting
- **System Overview**: [System Architecture Overview](../architecture/overview.md) - High-level system design

### Related Code

| Component              | File Path                                                      |
| ---------------------- | -------------------------------------------------------------- |
| Operations Page        | `frontend/src/components/system/SystemMonitoringPage.tsx`      |
| Pipeline Visualization | `frontend/src/components/system/PipelineFlowVisualization.tsx` |
| Circuit Breaker Panel  | `frontend/src/components/system/CircuitBreakerPanel.tsx`       |
| File Operations Panel  | `frontend/src/components/system/FileOperationsPanel.tsx`       |
| Debug Mode Toggle      | `frontend/src/components/system/DebugModeToggle.tsx`           |
| Collapsible Section    | `frontend/src/components/system/CollapsibleSection.tsx`        |
| Backend API Routes     | `backend/api/routes/system.py`                                 |

### Hooks Used

| Hook                    | Purpose                                                         |
| ----------------------- | --------------------------------------------------------------- |
| `useSystemPageSections` | Manages collapsible section state with localStorage persistence |
| `useSystemConfigQuery`  | Fetches system configuration including debug flag               |
| `useLocalStorage`       | Persists debug mode toggle state                                |
| `useStorageStatusStore` | Global store for storage status (enables header warnings)       |

### API Endpoints

| Endpoint                                    | Method | Description                                                  |
| ------------------------------------------- | ------ | ------------------------------------------------------------ |
| `/api/system/telemetry`                     | GET    | Pipeline queue depths and latencies                          |
| `/api/system/health/ready`                  | GET    | Worker status and readiness                                  |
| `/api/system/circuit-breakers`              | GET    | Circuit breaker states                                       |
| `/api/system/circuit-breakers/{name}/reset` | POST   | Reset a circuit breaker (requires API key)                   |
| `/api/system/storage`                       | GET    | Storage statistics and database record counts                |
| `/api/system/cleanup`                       | POST   | Trigger data cleanup (requires API key)                      |
| `/api/system/cleanup/status`                | GET    | Cleanup service status                                       |
| `/api/system/cleanup/orphaned-files`        | POST   | Clean orphaned files (requires API key, dry_run query param) |
| `/api/system/config`                        | GET    | System configuration (includes Grafana URL, debug flag)      |
| `/api/jobs`                                 | GET    | List export/cleanup jobs with status                         |

# System Configuration and Settings Coverage

## Executive Summary

The backend has **40+ system endpoints** covering health, GPU config, performance, and service management. The frontend has **11 settings tabs** plus dedicated pages, but **UI lags behind API capabilities**.

## Backend Endpoints

### Health & Status

| Endpoint                  | Purpose                    | UI Status  |
| ------------------------- | -------------------------- | ---------- |
| GET `/health`             | Comprehensive health check | ⚠️ Partial |
| GET `/health/live`        | K8s liveness probe         | ❌ No UI   |
| GET `/health/ready`       | K8s readiness probe        | ❌ No UI   |
| GET `/health/websocket`   | WebSocket broadcaster      | ❌ No UI   |
| GET `/monitoring/health`  | Prometheus stack health    | ❌ No UI   |
| GET `/monitoring/targets` | Prometheus scrape targets  | ❌ No UI   |

### GPU Configuration

| Endpoint                  | Purpose            | UI Status      |
| ------------------------- | ------------------ | -------------- |
| GET `/gpus`               | List GPUs          | ✅             |
| GET `/gpu-config`         | Get configuration  | ✅             |
| PUT `/gpu-config`         | Update assignments | ✅             |
| POST `/gpu-config/apply`  | Apply and restart  | ✅ (simulated) |
| GET `/gpu-config/status`  | Apply progress     | ✅             |
| POST `/gpu-config/detect` | Re-scan GPUs       | ✅             |
| GET `/gpu-config/preview` | Preview strategy   | ✅             |

### Performance & Metrics

| Endpoint                         | Purpose                 | UI Status    |
| -------------------------------- | ----------------------- | ------------ |
| GET `/performance`               | CPU/RAM/network metrics | ⚠️ Partial   |
| GET `/performance/history`       | Historical performance  | ❌ No UI     |
| GET `/gpu`                       | GPU utilization         | ✅           |
| GET `/gpu/history`               | GPU history             | ❌ No UI     |
| GET `/telemetry`                 | Pipeline latency        | ✅ Analytics |
| GET `/pipeline-latency`          | Current latencies       | ✅           |
| GET `/pipeline-latency/history`  | Latency history         | ❌ No UI     |
| GET `/nemotron-optimizer`        | LLM optimization        | ❌ No UI     |
| POST `/nemotron-optimizer/reset` | Reset optimizer         | ❌ No UI     |

### Configuration Management

| Endpoint                | Purpose              | UI Status  |
| ----------------------- | -------------------- | ---------- |
| GET `/config`           | Runtime config       | ⚠️ Partial |
| PATCH `/config`         | Update config        | ⚠️ Partial |
| GET `/anomaly-config`   | Anomaly thresholds   | ✅         |
| PATCH `/anomaly-config` | Update anomaly       | ✅         |
| GET `/severity`         | Severity definitions | ✅         |
| PUT `/severity`         | Update severity      | ✅         |

### System Operations

| Endpoint                              | Purpose                | UI Status  |
| ------------------------------------- | ---------------------- | ---------- |
| GET `/stats`                          | Aggregate statistics   | ⚠️ Partial |
| GET `/storage`                        | Storage usage          | ✅         |
| POST `/cleanup`                       | Trigger cleanup        | ✅         |
| POST `/cleanup/orphaned-files`        | Orphan cleanup         | ✅         |
| GET `/cleanup/status`                 | Cleanup progress       | ✅         |
| GET `/circuit-breakers`               | Circuit breaker status | ⚠️ Partial |
| POST `/circuit-breakers/{name}/reset` | Reset CB               | ❌ No UI   |

### Service Management

| Endpoint                                  | Purpose                  | UI Status  |
| ----------------------------------------- | ------------------------ | ---------- |
| GET `/supervisor`                         | Worker supervisor status | ⚠️ Partial |
| POST `/supervisor/reset/{worker}`         | Reset worker             | ❌ No UI   |
| GET `/supervisor/status`                  | Comprehensive status     | ⚠️ Partial |
| POST `/supervisor/force-restart/{worker}` | Force restart            | ❌ No UI   |
| GET `/supervisor/restart-history`         | Restart events           | ❌ No UI   |
| GET `/websocket/events`                   | Registered WS events     | ❌ No UI   |
| GET `/pipeline`                           | Pipeline status          | ✅         |

### Settings Endpoints

| Endpoint                               | Purpose           | UI Status  |
| -------------------------------------- | ----------------- | ---------- |
| GET `/api/v1/settings`                 | All user settings | ✅         |
| PATCH `/api/v1/settings`               | Update settings   | ✅         |
| GET `/api/v1/system-settings`          | Key-value store   | ⚠️ Partial |
| GET `/api/v1/system-settings/{key}`    | Get setting       | ⚠️ Partial |
| PATCH `/api/v1/system-settings/{key}`  | Upsert setting    | ⚠️ Partial |
| DELETE `/api/v1/system-settings/{key}` | Delete setting    | ❌ No UI   |

## Frontend Settings UI

### Main Settings Page Tabs

| Tab            | Purpose                      | Coverage   |
| -------------- | ---------------------------- | ---------- |
| Cameras        | Camera configuration         | ✅ Good    |
| Rules          | Alert rules                  | ✅ Good    |
| Processing     | Detection sensitivity        | ✅ Good    |
| Notifications  | Email, push, webhook         | ✅ Good    |
| Ambient        | Environmental awareness      | ✅ Good    |
| Calibration    | Camera calibration           | ✅ Good    |
| Access Control | Household, vehicles          | ✅ Good    |
| Prompts        | AI prompt management         | ✅ Good    |
| Storage        | Retention, cleanup           | ✅ Good    |
| AI Models      | YOLO26, Nemotron             | ✅ Good    |
| Admin          | Toggles, config, maintenance | ⚠️ Partial |

### Admin Settings Sections

**Feature Toggles:**

- Vision Extraction (Florence-2)
- Re-ID Tracking (CLIP)
- Scene Change Detection
- Clip Generation
- Image Quality Assessment
- Background Evaluation

**System Config:**

- Rate limiting (requests/minute, burst)
- Queue settings (max size, backpressure)

**Maintenance Actions:**

- Orphaned file cleanup
- Cache clear
- Flush queues

**Developer Tools (debug mode):**

- Seed test cameras
- Seed test events
- Clear seeded data

### Dedicated Pages

| Page                 | Route                | Purpose           |
| -------------------- | -------------------- | ----------------- |
| GpuSettingsPage      | `/gpu-settings`      | GPU configuration |
| SystemMonitoringPage | `/system-monitoring` | System health     |
| DeveloperToolsPage   | `/developer-tools`   | Debug tools       |

### System Monitoring Panels

- Circuit Breaker Status
- Containers/Services Status
- Database Health
- File Operations
- Host System Info
- Pipeline Metrics
- Pipeline Flow Visualization
- Severity Configuration
- Services Management

## Settings NOT in UI

### System Settings (Key-Value Store)

| Setting                  | Backend | UI  |
| ------------------------ | ------- | --- |
| GPU strategy persistence | ✅      | ❌  |
| Custom app-wide config   | ✅      | ❌  |
| Raw env var overrides    | ✅      | ❌  |

### Advanced Health Monitoring

| Feature                   | Backend                          | UI         |
| ------------------------- | -------------------------------- | ---------- |
| Circuit breaker details   | ✅ `/circuit-breakers`           | ⚠️ Partial |
| Prometheus stack health   | ✅ `/monitoring/health`          | ❌         |
| Prometheus scrape targets | ✅ `/monitoring/targets`         | ❌         |
| WebSocket broadcaster     | ✅ `/health/websocket`           | ❌         |
| Nemotron optimizer        | ✅ `/nemotron-optimizer`         | ❌         |
| Worker restart history    | ✅ `/supervisor/restart-history` | ❌         |

### Latency & Performance

| Feature                  | Backend                              | UI  |
| ------------------------ | ------------------------------------ | --- |
| Historical performance   | ✅ `/performance/history`            | ❌  |
| GPU history trends       | ✅ `/gpu/history`                    | ❌  |
| Pipeline latency history | ✅ `/pipeline-latency/history`       | ❌  |
| Model latency history    | ✅ `/pipeline-latency/model-history` | ❌  |

### Operational Maintenance

| Feature               | Backend                                      | UI  |
| --------------------- | -------------------------------------------- | --- |
| Cleanup dry-run       | ✅ `POST /cleanup`                           | ❌  |
| Circuit breaker reset | ✅ `POST /circuit-breakers/{name}/reset`     | ❌  |
| Worker force restart  | ✅ `POST /supervisor/force-restart/{worker}` | ❌  |
| GPU re-detection      | ✅ `POST /gpu-config/detect`                 | ✅  |

## Missing System Management

| Feature                  | Status             |
| ------------------------ | ------------------ |
| Logging configuration    | ❌ Not exposed     |
| Backup/Restore UI        | ❌ Not in Settings |
| Service-level SLA config | ❌ Not exposed     |
| Webhook management       | ⚠️ Separate page   |
| API key management       | ❌ Not exposed     |
| Audit log access         | ⚠️ Separate page   |
| Performance profiling    | ✅ DevTools        |
| Cache management         | ⚠️ Partial         |
| Database optimization    | ❌ Not exposed     |
| Certificate management   | ❌ Not exposed     |
| Network configuration    | ❌ Not exposed     |

## Recommendations

### High Priority

1. **Circuit Breaker Management**

   - Add reset buttons in System Monitoring
   - Show detailed state and failure counts

2. **Historical Performance Data**

   - Add charts for performance/history
   - GPU utilization trends
   - Pipeline latency trends

3. **Worker Management**
   - Show restart history
   - Add force restart button (with confirmation)

### Medium Priority

4. **Prometheus Integration Display**

   - Show monitoring stack health
   - Display scrape target status

5. **Nemotron Optimizer**

   - Show optimization status
   - Add manual reset button

6. **Dry-run Cleanup**
   - Preview what will be deleted
   - Show space to be reclaimed

### Low Priority

7. **System Settings Key-Value UI**

   - Admin interface for raw settings
   - Import/export configuration

8. **Logging Configuration**
   - Log level per component
   - Log rotation settings

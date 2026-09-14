# Backend API Inventory

## Overview

The backend exposes **150+ API endpoints** across **50 route files** organized by domain.

## Endpoints by Domain

### Analytics & Reporting (`/api/analytics`)

| Method | Path                       | Description                       | Response Schema               |
| ------ | -------------------------- | --------------------------------- | ----------------------------- |
| GET    | `/detection-trends`        | Detection counts by day           | DetectionTrendsResponse       |
| GET    | `/risk-history`            | Risk level distribution over time | RiskHistoryResponse           |
| GET    | `/camera-uptime`           | Camera uptime percentages         | CameraUptimeResponse          |
| GET    | `/object-distribution`     | Detection counts by object type   | ObjectDistributionResponse    |
| GET    | `/risk-score-distribution` | Risk score histogram              | RiskScoreDistributionResponse |
| GET    | `/risk-score-trends`       | Average risk score trends         | RiskScoreTrendsResponse       |

### Alerts & Alert Rules (`/api/alerts`)

| Method | Path                      | Description                         |
| ------ | ------------------------- | ----------------------------------- |
| GET    | `/rules`                  | List alert rules with pagination    |
| POST   | `/rules`                  | Create new alert rule               |
| GET    | `/rules/{rule_id}`        | Get specific alert rule             |
| PUT    | `/rules/{rule_id}`        | Update alert rule                   |
| DELETE | `/rules/{rule_id}`        | Delete alert rule                   |
| POST   | `/rules/{rule_id}/test`   | Test rule against historical events |
| POST   | `/{alert_id}/acknowledge` | Acknowledge alert                   |
| POST   | `/{alert_id}/dismiss`     | Dismiss alert                       |

### Cameras (`/api/cameras`)

| Method | Path                                          | Description                       |
| ------ | --------------------------------------------- | --------------------------------- |
| GET    | `/`                                           | List all cameras with caching     |
| GET    | `/{camera_id}`                                | Get specific camera               |
| POST   | `/`                                           | Create new camera                 |
| PATCH  | `/{camera_id}`                                | Update camera                     |
| DELETE | `/{camera_id}`                                | Delete camera                     |
| GET    | `/deleted`                                    | List soft-deleted cameras         |
| POST   | `/{camera_id}/restore`                        | Restore soft-deleted camera       |
| GET    | `/{camera_id}/snapshot`                       | Get latest camera snapshot        |
| GET    | `/validation/paths`                           | Validate all camera paths         |
| GET    | `/{camera_id}/baseline`                       | Get camera baseline activity      |
| GET    | `/{camera_id}/baseline/anomalies`             | Get baseline anomalies            |
| GET    | `/{camera_id}/baseline/activity`              | Get activity baseline data        |
| GET    | `/{camera_id}/baseline/classes`               | Get class frequency baseline      |
| GET    | `/{camera_id}/scene-changes`                  | Get scene changes with pagination |
| POST   | `/{camera_id}/scene-changes/{id}/acknowledge` | Acknowledge scene change          |

### Detections (`/api/detections`)

| Method | Path                              | Description                                        |
| ------ | --------------------------------- | -------------------------------------------------- |
| GET    | `/`                               | List detections with filters and cursor pagination |
| GET    | `/stats`                          | Get detection statistics and trends                |
| GET    | `/search`                         | Full-text search on detections                     |
| GET    | `/labels`                         | List all unique detection labels                   |
| GET    | `/{detection_id}`                 | Get specific detection                             |
| GET    | `/{detection_id}/thumbnail`       | Get detection thumbnail                            |
| GET    | `/{detection_id}/image`           | Get detection image with overlay                   |
| GET    | `/{detection_id}/enrichment`      | Get enrichment data                                |
| GET    | `/{detection_id}/video`           | Stream video with range support                    |
| GET    | `/{detection_id}/video/thumbnail` | Get video thumbnail                                |
| POST   | `/bulk`                           | Bulk create detections                             |
| PATCH  | `/bulk`                           | Bulk update detections                             |
| DELETE | `/bulk`                           | Bulk delete detections                             |
| GET    | `/export`                         | Export detections as CSV/JSON                      |

### Zones (`/api/cameras/{camera_id}/zones`)

| Method | Path         | Description           |
| ------ | ------------ | --------------------- |
| GET    | `/`          | List zones for camera |
| POST   | `/`          | Create zone           |
| GET    | `/{zone_id}` | Get specific zone     |
| PUT    | `/{zone_id}` | Update zone           |
| DELETE | `/{zone_id}` | Delete zone           |

### GPU Configuration (`/api/system`)

| Method | Path                  | Description                            |
| ------ | --------------------- | -------------------------------------- |
| GET    | `/gpus`               | List detected GPUs with utilization    |
| GET    | `/gpu-config`         | Get current assignments and strategies |
| PUT    | `/gpu-config`         | Update assignments                     |
| POST   | `/gpu-config/apply`   | Apply config and restart services      |
| GET    | `/gpu-config/status`  | Get restart progress and health        |
| POST   | `/gpu-config/detect`  | Re-scan for GPUs                       |
| GET    | `/gpu-config/preview` | Preview auto-assignment for strategy   |

### Face Recognition (`/api`)

| Method | Path                                  | Description                |
| ------ | ------------------------------------- | -------------------------- |
| GET    | `/known-persons`                      | List known persons         |
| POST   | `/known-persons`                      | Create person              |
| GET    | `/known-persons/{id}`                 | Get specific person        |
| PATCH  | `/known-persons/{id}`                 | Update person              |
| DELETE | `/known-persons/{id}`                 | Delete person              |
| POST   | `/known-persons/{id}/embeddings`      | Add face embedding         |
| GET    | `/known-persons/{id}/embeddings`      | List embeddings            |
| DELETE | `/known-persons/{id}/embeddings/{id}` | Delete embedding           |
| GET    | `/face-events`                        | List face detection events |
| GET    | `/face-events/unknown`                | Unknown stranger alerts    |
| POST   | `/face-events/match`                  | Match face embedding       |

### Household (`/api/household`)

| Method | Path                       | Description              |
| ------ | -------------------------- | ------------------------ |
| GET    | `/members`                 | List members             |
| POST   | `/members`                 | Create member            |
| GET    | `/members/{id}`            | Get member               |
| PATCH  | `/members/{id}`            | Update member            |
| DELETE | `/members/{id}`            | Delete member            |
| GET    | `/vehicles`                | List vehicles            |
| POST   | `/vehicles`                | Create vehicle           |
| GET    | `/vehicles/{id}`           | Get vehicle              |
| PATCH  | `/vehicles/{id}`           | Update vehicle           |
| DELETE | `/vehicles/{id}`           | Delete vehicle           |
| POST   | `/members/{id}/embeddings` | Add embedding from event |

### Entities (`/api/entities`)

| Method | Path                      | Description                      |
| ------ | ------------------------- | -------------------------------- |
| GET    | `/`                       | List entities with pagination    |
| GET    | `/stats`                  | Entity statistics by type/camera |
| GET    | `/trusted`                | List trusted entities            |
| GET    | `/untrusted`              | List untrusted entities          |
| PATCH  | `/{id}/trust`             | Update trust status              |
| GET    | `/{id}`                   | Get entity details               |
| GET    | `/{id}/history`           | Appearance timeline              |
| GET    | `/matches/{detection_id}` | Find re-ID matches               |
| GET    | `/v2`                     | Historical entity lookup         |
| GET    | `/v2/{id}`                | Get PostgreSQL entity            |
| GET    | `/v2/{id}/detections`     | List entity detections           |

## Additional Route Files (43 total)

| File                        | Domain         | Purpose                     |
| --------------------------- | -------------- | --------------------------- |
| action_events.py            | Events         | Action event tracking       |
| admin.py                    | Administration | Admin operations            |
| ai_audit.py                 | AI             | AI model audit trails       |
| alertmanager.py             | Alerts         | AlertManager integration    |
| analytics_zones.py          | Analytics      | Zone-level analytics        |
| audit.py                    | Audit          | Audit log access            |
| backup.py                   | System         | Backup/restore operations   |
| calibration.py              | Camera         | Camera calibration          |
| debug.py                    | Debug          | Debug utilities             |
| detector.py                 | Detection      | Detector service control    |
| dlq.py                      | Queue          | Dead letter queue           |
| entities.py                 | Entities       | Entity management           |
| exports.py                  | Export         | Data export operations      |
| face_recognition.py         | AI             | Face detection/recognition  |
| feedback.py                 | Feedback       | User feedback collection    |
| gpu_config.py               | System         | GPU configuration           |
| heatmaps.py                 | Analytics      | Heatmap generation          |
| health_ai_services.py       | Health         | AI service health           |
| hierarchy.py                | Hierarchy      | Property/area hierarchy     |
| household.py                | Household      | Household member management |
| jobs.py                     | Jobs           | Background job management   |
| logs.py                     | Logs           | System log access           |
| media.py                    | Media          | Media file serving          |
| metrics.py                  | Metrics        | Prometheus metrics          |
| notification_preferences.py | Notifications  | User notification settings  |
| notification.py             | Notifications  | Notification delivery       |
| onvif.py                    | Camera         | ONVIF camera integration    |
| outbound_webhooks.py        | Webhooks       | Outbound webhook delivery   |
| plate_reads.py              | AI             | License plate detection     |
| prompt_management.py        | AI             | LLM prompt management       |
| queues.py                   | Queue          | Queue status monitoring     |
| rum.py                      | Monitoring     | Real user monitoring        |
| scheduled_reports.py        | Reports        | Scheduled report generation |
| services.py                 | Services       | Service status/control      |
| settings_api.py             | Settings       | Application settings        |
| summaries.py                | Summaries      | Event/detection summaries   |
| system_settings.py          | Settings       | System configuration        |
| tracks.py                   | Tracking       | Object tracking data        |
| webhooks.py                 | Webhooks       | Webhook configuration       |
| websocket.py                | WebSocket      | WebSocket connections       |
| zone_anomalies.py           | Zones          | Zone anomaly detection      |
| zone_baselines.py           | Zones          | Zone baseline data          |
| zone_household.py           | Zones          | Zone-household mapping      |

## API Characteristics

### Authentication

- API key-based authentication for most endpoints
- Media endpoints exempt (browser direct access)
- Rate limiting by tier (MEDIA, BULK, EXPORT)

### Response Formats

- JSON (default with ORJSONResponse)
- CSV/JSON export support
- File streaming for media
- HTTP 206 Partial Content for video range requests

### Pagination

- Cursor-based pagination (recommended)
- Legacy offset-based pagination (deprecated)
- Sparse fieldsets support

### Features

- Full-text search across detections
- Bulk operations with partial success (HTTP 207)
- Cache-aside pattern with Redis
- Background task processing
- Optimistic locking
- Soft delete support
- WebSocket event broadcasting
- Outbound webhook triggers

# Unexposed Backend Services Analysis

## Executive Summary

Analysis of 150+ backend services identified significant functionality NOT exposed via REST API endpoints. This document catalogs services with unexposed methods and recommends endpoints to add.

## Priority Summary

| Priority | Service              | Unexposed Methods | Impact                            |
| -------- | -------------------- | ----------------- | --------------------------------- |
| **HIGH** | Notification Service | 8                 | Cannot send notifications via API |
| **HIGH** | Model Zoo            | 7                 | Cannot manage AI model lifecycle  |
| **HIGH** | Baseline Service     | 11                | Limited analytics access          |
| **HIGH** | Track Service        | 8                 | Motion tracking data hidden       |
| MEDIUM   | Alert Service        | 5                 | No manual alert management        |
| MEDIUM   | Household Matcher    | 3                 | Matching not available for UI     |
| MEDIUM   | Re-ID Service        | 3                 | Similarity scoring not exposed    |
| MEDIUM   | Materialized Views   | 8                 | No admin control over refreshes   |

## HIGH Priority Services

### 1. Notification Service (`backend/services/notification.py`)

**0 of 8 methods exposed**

| Method                     | Description                   | Recommended Endpoint                     |
| -------------------------- | ----------------------------- | ---------------------------------------- |
| `send_email()`             | Send email notifications      | `POST /api/notifications/send`           |
| `send_webhook()`           | Send webhook notifications    | (same)                                   |
| `send_push()`              | Send push notifications       | (same)                                   |
| `deliver_alert()`          | Deliver via multiple channels | (same)                                   |
| `get_available_channels()` | List notification channels    | `GET /api/notifications/channels`        |
| `is_email_configured()`    | Check email config            | `GET /api/notifications/channels/status` |
| `is_webhook_configured()`  | Check webhook config          | (same)                                   |
| `is_push_configured()`     | Check push config             | (same)                                   |

**Recommended Endpoints:**

```
POST /api/notifications/send
  - channel: email|webhook|push
  - recipients: [...]
  - subject/body/template

GET /api/notifications/channels
GET /api/notifications/channels/status
POST /api/notifications/test/{channel}
```

### 2. Model Zoo (`backend/services/model_zoo.py`)

**1 of 8 methods exposed**

| Method              | Description        | Status              |
| ------------------- | ------------------ | ------------------- |
| `load()`            | Load model         | NOT EXPOSED         |
| `preload()`         | Preload model      | NOT EXPOSED         |
| `unload()`          | Unload model       | NOT EXPOSED         |
| `unload_all()`      | Unload all models  | NOT EXPOSED         |
| `reload()`          | Reload model       | NOT EXPOSED         |
| `get_status()`      | Get model status   | Partial (in health) |
| `loaded_models`     | List loaded models | NOT EXPOSED         |
| `total_loaded_vram` | VRAM usage         | NOT EXPOSED         |

**Recommended Endpoints:**

```
GET /api/system/models - List models with load state
POST /api/system/models/{model}/load
POST /api/system/models/{model}/unload
POST /api/system/models/{model}/reload
POST /api/system/models/unload-all
GET /api/system/models/{model}/status
```

### 3. Baseline Service (`backend/services/baseline.py`)

**4 of 15 methods exposed**

| Method                                 | Status      |
| -------------------------------------- | ----------- |
| `get_camera_baseline_summary()`        | EXPOSED     |
| `get_activity_baselines_raw()`         | EXPOSED     |
| `get_class_baselines_raw()`            | EXPOSED     |
| `get_recent_anomalies()`               | EXPOSED     |
| `update_baseline()`                    | NOT EXPOSED |
| `get_activity_rate()`                  | NOT EXPOSED |
| `get_class_frequency()`                | NOT EXPOSED |
| `is_anomalous()`                       | NOT EXPOSED |
| `get_hourly_patterns()`                | NOT EXPOSED |
| `get_daily_patterns()`                 | NOT EXPOSED |
| `get_object_baselines()`               | NOT EXPOSED |
| `get_current_deviation()`              | NOT EXPOSED |
| `get_baseline_established_date()`      | NOT EXPOSED |
| `get_class_baselines_by_camera_hour()` | NOT EXPOSED |
| `update_config()`                      | NOT EXPOSED |

**Recommended Endpoints:**

```
GET /api/analytics/baselines/{camera_id}/hourly
GET /api/analytics/baselines/{camera_id}/daily
GET /api/analytics/baselines/{camera_id}/objects
GET /api/analytics/baselines/{camera_id}/deviation
GET /api/analytics/baselines/{camera_id}/raw
```

### 4. Track Service (`backend/services/track_service.py`)

**1 of 9 methods exposed**

| Method                         | Description           | Status      |
| ------------------------------ | --------------------- | ----------- |
| `create_or_update_track()`     | Create/update track   | NOT EXPOSED |
| `get_track()`                  | Get track by ID       | NOT EXPOSED |
| `get_track_history()`          | Get track history     | NOT EXPOSED |
| `get_tracks_by_camera()`       | Get tracks for camera | NOT EXPOSED |
| `prune_old_tracks()`           | Delete old tracks     | NOT EXPOSED |
| `mark_track_lost()`            | Mark track as lost    | NOT EXPOSED |
| `get_active_track_count()`     | Get active count      | NOT EXPOSED |
| `update_active_track_counts()` | Update counts         | NOT EXPOSED |
| `calculate_metrics()`          | Calculate metrics     | NOT EXPOSED |

**Recommended Endpoints:**

```
GET /api/tracks - List all tracks (with filters)
GET /api/tracks/{id} - Track details
GET /api/tracks/{id}/history - Detection history
GET /api/cameras/{id}/tracks/active
GET /api/cameras/{id}/tracks/lost
```

## MEDIUM Priority Services

### 5. Alert Service (`backend/services/alert_service.py`)

**2 of 7 methods exposed**

| Method                | Status                 |
| --------------------- | ---------------------- |
| `acknowledge_alert()` | EXPOSED                |
| `dismiss_alert()`     | EXPOSED                |
| `create_alert()`      | NOT EXPOSED            |
| `get_alert()`         | NOT EXPOSED            |
| `update_alert()`      | NOT EXPOSED            |
| `delete_alert()`      | NOT EXPOSED            |
| `set_emitter()`       | NOT EXPOSED (internal) |

**Recommended Endpoints:**

```
POST /api/alerts - Manual alert creation
GET /api/alerts/{id} - Get single alert
PATCH /api/alerts/{id} - Update alert fields
DELETE /api/alerts/{id} - Delete alert
```

### 6. Household Matcher (`backend/services/household_matcher.py`)

**0 of 3 methods exposed** (internal pipeline function)

| Method               | Description                         |
| -------------------- | ----------------------------------- |
| `match_person()`     | Match person to household member    |
| `match_vehicle()`    | Match vehicle to registered vehicle |
| `match_detections()` | Match multiple detections           |

**Consideration:** These are pipeline functions, but UI may need:

```
POST /api/household/match-person - Match detected person
POST /api/household/match-vehicle - Match detected vehicle
```

### 7. Re-ID Service (`backend/services/reid_service.py`)

**1 of 4 methods exposed**

| Method                     | Status      |
| -------------------------- | ----------- |
| `generate_embedding()`     | NOT EXPOSED |
| `store_embedding()`        | NOT EXPOSED |
| `find_matching_entities()` | NOT EXPOSED |
| `get_entity_history()`     | PARTIAL     |

**Recommended Endpoints:**

```
GET /api/entities/{id}/similar-entities - Find similar with scores
POST /api/detections/{id}/re-match - Force re-matching
POST /api/entities/{id}/regenerate-embedding
```

### 8. Materialized Views (`backend/services/materialized_views.py`)

**2 of 10 methods exposed**

| Method                              | Status      |
| ----------------------------------- | ----------- |
| `refresh_all_views()`               | NOT EXPOSED |
| `refresh_view()`                    | NOT EXPOSED |
| `get_daily_detection_counts()`      | PARTIAL     |
| `get_hourly_event_stats()`          | NOT EXPOSED |
| `get_risk_score_aggregations()`     | PARTIAL     |
| `get_detection_type_distribution()` | PARTIAL     |
| `get_entity_tracking_summary()`     | NOT EXPOSED |
| `get_enrichment_summary()`          | NOT EXPOSED |
| `check_view_exists()`               | NOT EXPOSED |
| `get_view_stats()`                  | NOT EXPOSED |

**Recommended Endpoints:**

```
POST /api/system/materialized-views/refresh
POST /api/system/materialized-views/{view}/refresh
GET /api/system/materialized-views/stats
```

## Well-Exposed Services (No Action Needed)

| Service            | Exposed/Total | Status   |
| ------------------ | ------------- | -------- |
| Webhook Service    | 12/12         | Complete |
| Face Recognition   | 13/13         | Complete |
| Prompt Service     | 11/11         | Complete |
| ALPR Service       | 7/8           | Good     |
| Export Service     | 6/7           | Good     |
| Dwell Time Service | 4/8           | Adequate |

## Internal Pipeline Services (Correctly Not Exposed)

These services are internal pipeline functions and should NOT be exposed:

- Context Enricher
- Entity Clustering Service
- Health Monitor (system control)
- Zone Service utilities
- Zone Crossing Service

## Recommended New Endpoints Summary

### Notification Management

```
POST /api/notifications/send
GET /api/notifications/channels
GET /api/notifications/channels/status
POST /api/notifications/test/{channel}
```

### Model Management

```
GET /api/system/models
POST /api/system/models/{model}/load
POST /api/system/models/{model}/unload
POST /api/system/models/{model}/reload
POST /api/system/models/unload-all
```

### Track Management

```
GET /api/tracks
GET /api/tracks/{id}
GET /api/tracks/{id}/history
GET /api/cameras/{id}/tracks/active
```

### Baseline Analytics

```
GET /api/analytics/baselines/{camera_id}/hourly
GET /api/analytics/baselines/{camera_id}/daily
GET /api/analytics/baselines/{camera_id}/deviation
```

### Alert Management

```
POST /api/alerts
GET /api/alerts/{id}
PATCH /api/alerts/{id}
DELETE /api/alerts/{id}
```

### Admin/Debug

```
POST /api/system/materialized-views/refresh
POST /api/system/nemotron/warmup
POST /api/debug/analyze-event/{event_id}
```

# Frontend Gap Analysis - Executive Summary

## Research Overview

15 parallel research agents analyzed the codebase to identify frontend gaps, orphaned components, and unexposed backend functionality. This document summarizes the key findings.

## Key Statistics

| Metric                  | Count |
| ----------------------- | ----- |
| Backend API Endpoints   | 150+  |
| Frontend Components     | 358   |
| Frontend Pages          | 7     |
| Custom React Hooks      | 80+   |
| API Client Files        | 11    |
| Orphaned Components     | 5     |
| WebSocket Message Types | 57    |

## Critical Frontend Gaps

### 1. Face Recognition & Person Re-ID (Priority: HIGH)

**Backend capabilities exist but NO frontend UI:**

- Face management UI for known persons/embeddings
- Face event viewer and unknown stranger alerts
- Face enrollment workflow
- Person tracking history beyond entity re-ID

**Files:** `backend/services/face_detector.py`, `backend/services/reid_service.py`, `backend/services/household_matcher.py`

### 2. Zone Analytics (Priority: HIGH)

**Backend has 651+ lines of spatial heuristics, only ~60% exposed:**

- Line crossing counts (in_count/out_count tracked, no UI)
- Loitering threshold customization
- Dwell statistics dashboard
- Access schedule editor
- Approach vector visualization
- Anomaly investigation with associated detections

**Files:** `backend/services/zone_service.py`, `backend/services/dwell_time_service.py`

### 3. Camera RTSP/ONVIF Configuration (Priority: HIGH)

**Backend supports but UI missing:**

- RTSP URL input field
- RTSP credentials (backend has encryption support)
- Stream profile selection (main/sub/both)
- Connection testing with capability detection
- ONVIF device discovery
- Live video preview via WebRTC

**Design doc ready:** `docs/plans/2025-01-30-rtsp-camera-configuration-ui-design.md`

### 4. Notification Service (Priority: HIGH)

**8 public methods, 0 exposed via API:**

- No endpoint to send notifications directly
- No endpoint to list available channels
- No endpoint to check channel configuration status

### 5. Model Zoo Management (Priority: HIGH)

**7 unexposed methods:**

- No endpoint to load/unload/reload models
- No endpoint to view loaded model status
- Operators cannot manage AI model lifecycle

### 6. Track Service (Priority: HIGH)

**8 unexposed methods:**

- No endpoint for track details
- No endpoint for tracks by camera
- No endpoint for active track count
- Fundamental motion tracking data hidden from frontend

## Medium Priority Gaps

### WebSocket Events Not Handled by Frontend

- Worker events (6 types) - COMPLETE GAP
- Prometheus alerts - NOT IMPLEMENTED
- Detailed camera status per-camera
- Scene change acknowledgment

### Missing Pages/Routes

- Household Members management
- License Plate Recognition statistics
- Face Recognition known persons database
- ONVIF Camera Control (PTZ)
- Heatmaps visualization
- Activity Baselines tuning

### System Settings Not in UI

- Circuit breaker management details
- Prometheus/monitoring stack health
- WebSocket broadcaster status
- Worker restart history
- Historical performance/latency data
- Dry-run cleanup preview

## Orphaned Components (Delete Recommended)

| Component                | Confidence  | Reason                                 |
| ------------------------ | ----------- | -------------------------------------- |
| FeedbackPanel            | HIGH        | Exported but never imported            |
| NotificationHistoryPanel | HIGH        | Exported but never imported            |
| BatchProcessingIndicator | MEDIUM-HIGH | Never integrated                       |
| DateRangePicker          | MEDIUM      | Superseded by specific implementations |
| RetryIndicator           | MEDIUM      | Superseded by RetryingIndicator        |

## Type Safety Issues

- JSONB fields (`enrichment_data`, `entities`, `flags`) typed as `dict[str, Any]` - no validation
- Optimistic locking mismatch: Backend has `version` fields, frontend manually overrides types
- Deferred fields (`reasoning`, `llm_prompt`) not indicated in frontend types
- Entity model has no Pydantic schema

## Analytics Coverage

**Core analytics endpoints: 100% covered**

- detection-trends, risk-history, camera-uptime, object-distribution, risk-score-distribution, risk-score-trends

**Zone analytics: 0% UI coverage**

- Line crossing patterns and trends
- Polygon zone activity heatmaps
- Dwell time analytics
- Loitering alerts history

## GPU Configuration

**~80% complete:**

- Core functionality works (detection, configuration, strategy selection, preview)
- Missing: Real container restart (simulated), VRAM budget override input, strategy comparison view, configuration version history

## Recommendations

### Immediate Actions

1. Create Face Recognition management page (`/face-recognition`)
2. Create Household Members page (`/household`)
3. Add RTSP configuration fields to camera modal
4. Add Zone Analytics dashboard
5. Delete 5 orphaned components

### Short-term Actions

1. Expose Notification Service endpoints
2. Expose Model Zoo management endpoints
3. Add Track Service endpoints
4. Implement WebSocket handlers for worker events
5. Add missing navigation routes

### Long-term Actions

1. Implement ONVIF device discovery UI
2. Add live video preview via WebRTC
3. Build comprehensive system monitoring dashboard
4. Add configuration version history and rollback

## Research Documents

| #   | Document                         | Focus Area                       |
| --- | -------------------------------- | -------------------------------- |
| 01  | backend-api-inventory.md         | All backend API endpoints        |
| 02  | frontend-api-coverage.md         | Frontend API client analysis     |
| 03  | frontend-components-inventory.md | All React components             |
| 04  | unexposed-backend-services.md    | Services without API exposure    |
| 05  | frontend-hooks-analysis.md       | Custom React hooks               |
| 06  | model-type-comparison.md         | Backend models vs frontend types |
| 07  | websocket-coverage.md            | WebSocket feature coverage       |
| 08  | analytics-coverage.md            | Analytics endpoints vs frontend  |
| 09  | gpu-config-coverage.md           | GPU configuration coverage       |
| 10  | zone-analytics-coverage.md       | Zone/video analytics coverage    |
| 11  | face-reid-coverage.md            | Face recognition/Re-ID coverage  |
| 12  | orphaned-components.md           | Unused frontend components       |
| 13  | routing-navigation.md            | Frontend routing analysis        |
| 14  | system-settings-coverage.md      | System/settings coverage         |
| 15  | camera-management-coverage.md    | Camera management coverage       |

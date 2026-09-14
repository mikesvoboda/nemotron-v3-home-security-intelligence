# Camera Management Coverage Analysis

## Executive Summary

Camera management has **comprehensive backend support** for RTSP streaming, ONVIF integration, and advanced configuration, but the **frontend UI significantly lags behind**. A design document exists for phased implementation.

## Backend Services

### CameraService (`backend/services/camera_service.py`)

**Capabilities:**

- Camera status updates with optimistic concurrency control
- WebSocket event emission with 30-second debouncing
- Soft delete with restore functionality
- Camera path validation with fallback strategies

### CameraStatusService (`backend/services/camera_status_service.py`)

**Capabilities:**

- Manages camera status changes
- Automatic WebSocket broadcasting

### CameraRepository (`backend/repositories/camera_repository.py`)

**Capabilities:**

- Database operations with optimistic concurrency control
- Timestamp-based updates for race condition prevention

## API Endpoints

### CRUD Operations

| Method | Endpoint            | Description                        |
| ------ | ------------------- | ---------------------------------- |
| GET    | `/api/cameras`      | List cameras with status filtering |
| GET    | `/api/cameras/{id}` | Get single camera                  |
| POST   | `/api/cameras`      | Create camera                      |
| PATCH  | `/api/cameras/{id}` | Update camera                      |
| DELETE | `/api/cameras/{id}` | Hard delete                        |

### Soft Delete & Restore

| Method | Endpoint                    | Description               |
| ------ | --------------------------- | ------------------------- |
| GET    | `/api/cameras/deleted`      | List soft-deleted cameras |
| POST   | `/api/cameras/{id}/restore` | Restore deleted camera    |

### Media & Validation

| Method | Endpoint                        | Description         |
| ------ | ------------------------------- | ------------------- |
| GET    | `/api/cameras/{id}/snapshot`    | Get latest snapshot |
| GET    | `/api/cameras/validation/paths` | Validate all paths  |

### Analytics & Baseline

| Method | Endpoint                               | Description                     |
| ------ | -------------------------------------- | ------------------------------- |
| GET    | `/api/cameras/{id}/baseline`           | Baseline summary                |
| GET    | `/api/cameras/{id}/baseline/activity`  | Activity baseline (168 entries) |
| GET    | `/api/cameras/{id}/baseline/anomalies` | Anomaly events                  |
| GET    | `/api/cameras/{id}/baseline/classes`   | Class frequency baseline        |

### Scene Change Detection

| Method | Endpoint                                           | Description                   |
| ------ | -------------------------------------------------- | ----------------------------- |
| GET    | `/api/cameras/{id}/scene-changes`                  | Scene changes with pagination |
| POST   | `/api/cameras/{id}/scene-changes/{id}/acknowledge` | Acknowledge scene change      |

## Camera Data Model

### Core Fields (Exposed in UI)

| Field              | Type  | UI Status             |
| ------------------ | ----- | --------------------- |
| id                 | str   | ✅ Auto-generated     |
| name               | str   | ✅ Input field        |
| folder_path        | str   | ✅ Input field        |
| status             | enum  | ✅ Dropdown           |
| motion_sensitivity | float | ✅ Conditional slider |

### RTSP/Streaming Fields (NOT in UI)

| Field          | Type                  | UI Status             |
| -------------- | --------------------- | --------------------- |
| ingestion_mode | enum (ftp/rtsp/onvif) | ❌ Auto-detected only |
| rtsp_url       | str                   | ❌ NOT EXPOSED        |
| rtsp_username  | str                   | ❌ NOT EXPOSED        |
| rtsp_password  | str                   | ❌ NOT EXPOSED        |
| stream_profile | enum (main/sub/both)  | ❌ NOT EXPOSED        |

## Frontend Implementation

### Components

| Component                 | Lines | Purpose                   |
| ------------------------- | ----- | ------------------------- |
| CamerasSettings.tsx       | 1036  | Main camera management UI |
| CameraSelector.tsx        | -     | Dropdown with status      |
| CameraAnomalyTimeline.tsx | -     | Anomaly visualization     |
| SceneChangeHistory.tsx    | -     | Scene change list         |
| SceneChangeIndicator.tsx  | -     | Status indicator          |

### React Query Hooks

| Hook                         | Purpose                          |
| ---------------------------- | -------------------------------- |
| useCamerasQuery              | Main query with placeholder data |
| useCameraQuery               | Single camera fetch              |
| useCameraMutation            | CRUD with optimistic updates     |
| useOnlineCamerasQuery        | Filter to online cameras         |
| useCameraCountsQuery         | Aggregate by status              |
| useCameraStatusWebSocket     | Real-time status                 |
| useCameraAnalytics           | Analytics data                   |
| useCameraAnomaliesQuery      | Anomaly events                   |
| useCameraBaselineQuery       | Baseline data                    |
| useCameraPathValidationQuery | Path validation                  |
| useCameraSnapshotStatus      | Snapshot availability            |
| useCameraUptimeQuery         | Uptime statistics                |

## Critical Gaps

### HIGH Priority - Backend Fields NOT in UI

| Field            | Backend Support    | UI Status           |
| ---------------- | ------------------ | ------------------- |
| `rtsp_url`       | Full support       | ❌ No input field   |
| `rtsp_username`  | Encrypted storage  | ❌ No input field   |
| `rtsp_password`  | Encrypted storage  | ❌ No input field   |
| `stream_profile` | main/sub/both      | ❌ No dropdown      |
| `ingestion_mode` | Explicit selection | ❌ Auto-detect only |

### HIGH Priority - Backend Capabilities NOT in UI

| Capability              | Backend Support           | UI Status           |
| ----------------------- | ------------------------- | ------------------- |
| RTSP Connection Testing | ✅ Available              | ❌ No "Test" button |
| Capability Detection    | ✅ Resolution, codec, fps | ❌ Not displayed    |
| Stream Configuration    | ✅ Bitrate, fps, codec    | ❌ No controls      |
| ONVIF Discovery         | ✅ Device discovery       | ❌ No UI            |
| ONVIF Auto-Configure    | ✅ Auto-setup from ONVIF  | ❌ No UI            |
| Live Video Preview      | ✅ WebRTC via go2rtc      | ❌ No preview       |
| Connection Status       | ✅ Last test timestamp    | ❌ Not displayed    |

### MEDIUM Priority

| Feature                   | Backend | UI Status |
| ------------------------- | ------- | --------- |
| Snapshot cache TTL config | ✅      | ❌        |
| Manual snapshot refresh   | ✅      | ❌        |
| Video file settings       | ✅      | ❌        |

## WebSocket Events

### Exposed in Frontend

| Event                 | Handler                  |
| --------------------- | ------------------------ |
| camera.online         | useCameraStatusWebSocket |
| camera.offline        | useCameraStatusWebSocket |
| camera.error          | useCameraStatusWebSocket |
| camera.status_changed | useCameraStatusWebSocket |
| camera.enabled        | useCameraStatusWebSocket |
| camera.disabled       | useCameraStatusWebSocket |
| camera.config_updated | useCameraStatusWebSocket |

## Design Document

A comprehensive design document exists: `docs/plans/2025-01-30-rtsp-camera-configuration-ui-design.md`

### Proposed Implementation Phases

**Phase 1: Basic RTSP**

- Add RTSP URL input to camera modal
- Add username/password fields
- Basic validation

**Phase 2: Connection Testing**

- "Test Connection" button
- Capability detection display
- Connection status tracking

**Phase 3: ONVIF Discovery**

- Discovery panel
- Auto-configuration from ONVIF
- PTZ controls (if supported)

**Phase 4: Live Preview**

- WebRTC preview via go2rtc
- Stream settings control
- Resolution/bitrate configuration

## Recommended Actions

### Immediate

1. **Add RTSP fields to CameraForm**

   ```typescript
   // New fields needed:
   rtsp_url: string;
   rtsp_username: string;
   rtsp_password: string;
   stream_profile: 'main' | 'sub' | 'both';
   ```

2. **Add ingestion mode selector**
   - Radio buttons: FTP / RTSP / ONVIF
   - Show/hide relevant fields based on selection

### Short-term

1. **Connection Testing UI**

   - "Test Connection" button
   - Show detected capabilities
   - Display last test timestamp and result

2. **Credential Handling**
   - Password field with show/hide toggle
   - Encrypted storage (backend already supports)

### Medium-term

1. **ONVIF Discovery Panel**

   - Scan network for ONVIF devices
   - Auto-populate configuration
   - Show device capabilities

2. **Live Preview**
   - WebRTC integration with go2rtc
   - Play/pause controls
   - Snapshot from preview

### Long-term

1. **Stream Configuration**

   - Resolution selector
   - Bitrate control
   - Codec selection
   - Frame rate adjustment

2. **PTZ Controls**
   - Pan/tilt/zoom controls
   - Preset positions
   - Tour configuration

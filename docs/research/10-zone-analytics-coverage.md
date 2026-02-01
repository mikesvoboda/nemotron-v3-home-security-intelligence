# Zone and Video Analytics Coverage Analysis

## Executive Summary

The backend has **extensive zone analytics capabilities** with 651+ lines of spatial heuristics in `zone_service.py` alone. However, **only ~60% is exposed in the frontend UI**, creating significant gaps in zone intelligence features.

## Backend Services

### 1. Zone Service (`backend/services/zone_service.py`)

**Capabilities (651+ lines):**

- Spatial heuristics and geometry utilities
- Point-in-zone detection
- Bounding box center calculation
- Zone overlap detection
- Approach vector calculation (ETA to zone)

### 2. Zone Crossing Service (`backend/services/zone_crossing_service.py`)

**Capabilities:**

- Line crossing detection (bidirectional)
- Crossing event recording
- Entry/exit counting
- Cross-camera handoff detection

### 3. Dwell Time Service (`backend/services/dwell_time_service.py`)

**Capabilities:**

- Zone entry/exit recording
- Active dweller tracking
- Dwell duration calculation
- Loitering detection with configurable thresholds
- Zone statistics (avg, min, max dwell times)

### 4. Zone Anomaly Service (`backend/services/zone_anomaly_service.py`)

**Capabilities:**

- Baseline pattern analysis
- Anomaly score calculation
- Expected vs actual comparison
- Anomaly event recording

### 5. Zone Baseline Service (`backend/services/zone_baseline_service.py`)

**Capabilities:**

- Per-zone activity baselines
- Hourly/daily patterns
- Staleness detection

### 6. Zone Household Service (`backend/services/zone_household_service.py`)

**Capabilities:**

- Member-to-zone permissions
- Vehicle-to-zone permissions
- Access schedule management
- Trust level evaluation

## API Endpoints

### Line Zone Endpoints (`/api/analytics-zones`)

| Method | Endpoint                             | Description           |
| ------ | ------------------------------------ | --------------------- |
| POST   | `/line-zones`                        | Create line zone      |
| GET    | `/line-zones/{zone_id}`              | Get single zone       |
| GET    | `/line-zones/camera/{camera_id}`     | Get zones by camera   |
| PATCH  | `/line-zones/{zone_id}`              | Update zone           |
| DELETE | `/line-zones/{zone_id}`              | Delete zone           |
| POST   | `/line-zones/{zone_id}/reset-counts` | Reset crossing counts |

### Polygon Zone Endpoints

| Method | Endpoint                                 | Description         |
| ------ | ---------------------------------------- | ------------------- |
| POST   | `/polygon-zones`                         | Create polygon zone |
| GET    | `/polygon-zones/{zone_id}`               | Get single zone     |
| GET    | `/polygon-zones/camera/{camera_id}`      | Get zones by camera |
| PATCH  | `/polygon-zones/{zone_id}`               | Update zone         |
| DELETE | `/polygon-zones/{zone_id}`               | Delete zone         |
| POST   | `/polygon-zones/{zone_id}/toggle-active` | Toggle status       |

### Dwell Time Endpoints

| Method | Endpoint                                    | Description      |
| ------ | ------------------------------------------- | ---------------- |
| GET    | `/polygon-zones/{zone_id}/dwellers`         | Active dwellers  |
| GET    | `/polygon-zones/{zone_id}/dwell-history`    | Historical data  |
| POST   | `/polygon-zones/{zone_id}/check-loitering`  | Loitering alerts |
| GET    | `/polygon-zones/{zone_id}/dwell-statistics` | Aggregated stats |

### Zone Anomaly Endpoints

| Method | Endpoint                     | Description         |
| ------ | ---------------------------- | ------------------- |
| GET    | `/zones/{zone_id}/anomalies` | Zone anomaly events |
| GET    | `/zones/{zone_id}/baseline`  | Zone baseline data  |

## Frontend Components

### Implemented (100%)

| Component        | Purpose                   |
| ---------------- | ------------------------- |
| ZoneEditor       | Zone drawing/editing      |
| ZoneCanvas       | Canvas visualization      |
| ZoneForm         | Configuration form        |
| ZoneList         | Zone listing              |
| ZoneCrossingFeed | Real-time crossing events |

### Partially Implemented

| Component           | Status       | Gap                             |
| ------------------- | ------------ | ------------------------------- |
| ZoneAnomalyFeed     | Has feed     | No explanation of why anomalies |
| ZoneAnomalyAlert    | Basic alerts | No investigation UI             |
| ZoneStatusCard      | Basic status | No dwell statistics             |
| CameraBaselinePanel | Query exists | Minimal visualization           |

### Missing (0% UI)

| Feature                         | Backend Support               | Frontend Status |
| ------------------------------- | ----------------------------- | --------------- |
| Crossing count display          | `in_count`, `out_count` in DB | NO UI           |
| Loitering threshold config      | Per-zone thresholds           | NO UI           |
| Dwell statistics dashboard      | avg/min/max calculated        | NO UI           |
| Access schedule editor          | Time-based access             | NO UI           |
| Approach vector viz             | ETA to zone                   | NO UI           |
| Entity distribution by zone     | Tracked in DB                 | NO UI           |
| Baseline staleness warnings     | Staleness detected            | NO UI           |
| Trust level evaluation          | Evaluated in backend          | NO UI           |
| Member/vehicle zone permissions | Full backend support          | NO UI           |
| Anomaly investigation           | Associated detections stored  | NO UI           |

## Data Models

### LineZone

```python
- id: UUID
- camera_id: str
- name: str
- start_point: (x, y)
- end_point: (x, y)
- direction: bidirectional | left_to_right | right_to_left
- in_count: int  # NOT EXPOSED IN UI
- out_count: int  # NOT EXPOSED IN UI
- created_at: datetime
- enabled: bool
```

### PolygonZone

```python
- id: UUID
- camera_id: str
- name: str
- vertices: [(x, y), ...]
- zone_type: entry | exit | restricted | monitoring
- loitering_threshold_seconds: int  # NOT CONFIGURABLE IN UI
- enabled: bool
```

### DwellTimeRecord

```python
- id: UUID
- zone_id: UUID
- entity_id: UUID
- entered_at: datetime
- exited_at: datetime
- duration_seconds: int
- is_loitering: bool
```

### ZoneAnomaly

```python
- id: UUID
- zone_id: UUID
- detection_id: UUID
- anomaly_type: str
- expected_value: float
- actual_value: float  # NOT DISPLAYED IN UI
- score: float
- timestamp: datetime
```

## Critical Gaps

### 1. Line Crossing Counts (HIGH)

**Backend:** Tracks bidirectional crossings with `in_count` and `out_count`
**API:** `POST /line-zones/{zone_id}/reset-counts` exists
**UI:** No display of counts, no reset button

**Recommendation:**

- Add count display to ZoneStatusCard
- Add reset button with confirmation
- Add count history chart

### 2. Loitering Detection (HIGH)

**Backend:** Configurable `loitering_threshold_seconds` per zone
**API:** `POST /polygon-zones/{zone_id}/check-loitering` exists
**UI:** Cannot set per-zone thresholds

**Recommendation:**

- Add threshold slider to ZoneForm
- Show loitering alerts prominently
- Add loitering history view

### 3. Dwell Statistics Dashboard (HIGH)

**Backend:** Calculates avg/min/max dwell times
**API:** `GET /polygon-zones/{zone_id}/dwell-statistics` exists
**UI:** No dashboard to view statistics

**Recommendation:**

- Create ZoneDwellStatistics component
- Show distribution chart
- Add comparison across zones

### 4. Access Schedules (MEDIUM)

**Backend:** Supports time-based zone access
**API:** Zone-household service methods
**UI:** No visual schedule editor

**Recommendation:**

- Add weekly schedule grid
- Allow per-member/vehicle schedules
- Show access violations

### 5. Anomaly Investigation (MEDIUM)

**Backend:** Stores expected vs actual values, associated detections
**UI:** Shows anomalies but no context

**Recommendation:**

- Click anomaly → show associated detection
- Display expected vs actual comparison
- Show what triggered the anomaly

## Frontend Hooks

### Implemented

| Hook             | Purpose                           |
| ---------------- | --------------------------------- |
| useZones         | Zone CRUD with optimistic updates |
| useZoneCrossings | Crossing events                   |
| useZoneAnomalies | Anomaly events                    |

### Missing

| Hook                   | Needed For                 |
| ---------------------- | -------------------------- |
| useZoneDwellStatistics | Dwell statistics dashboard |
| useZoneAccessSchedule  | Schedule management        |
| useZoneCrossingCounts  | Count display/reset        |
| useZoneLoiteringConfig | Threshold configuration    |

## Recommended Implementation Plan

### Phase 1: Core Visibility

1. Add crossing counts to ZoneStatusCard
2. Add count reset functionality
3. Create basic dwell statistics view

### Phase 2: Configuration

1. Add loitering threshold to ZoneForm
2. Create access schedule editor
3. Add zone permissions UI

### Phase 3: Intelligence

1. Anomaly investigation modal
2. Expected vs actual comparison
3. Zone comparison dashboard
4. Entity distribution by zone

### Phase 4: Advanced

1. Approach vector visualization
2. Predictive zone analytics
3. Cross-zone journey mapping

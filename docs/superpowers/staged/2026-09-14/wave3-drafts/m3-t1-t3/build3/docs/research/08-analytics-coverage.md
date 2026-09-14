# Analytics Endpoints vs Frontend Coverage

## Executive Summary

**Core analytics endpoints are 100% covered** in the frontend. However, **zone analytics have 0% UI coverage** despite robust backend support.

## Core Analytics Endpoints (100% Covered)

| Endpoint                                 | Frontend Component        | Chart Type   | Status |
| ---------------------------------------- | ------------------------- | ------------ | ------ |
| `/api/analytics/detection-trends`        | DetectionTrendsCard       | Area chart   | ✅     |
| `/api/analytics/risk-history`            | RiskHistoryCard           | Stacked area | ✅     |
| `/api/analytics/camera-uptime`           | CameraUptimeCard          | Bar list     | ✅     |
| `/api/analytics/object-distribution`     | ObjectDistributionCard    | Donut chart  | ✅     |
| `/api/analytics/risk-score-distribution` | RiskScoreDistributionCard | Bar chart    | ✅     |
| `/api/analytics/risk-score-trends`       | RiskScoreTrendCard        | Line chart   | ✅     |

### Endpoint Details

#### GET `/api/analytics/detection-trends`

- **Returns:** Daily detection counts
- **Schema:** DetectionTrendsResponse
- **Parameters:** start_date, end_date (365 days max)
- **Frontend:** DetectionTrendsCard with area chart

#### GET `/api/analytics/risk-history`

- **Returns:** Daily event counts by risk level
- **Schema:** RiskHistoryResponse
- **Data:** Date + low/medium/high/critical counts
- **Frontend:** RiskHistoryCard with stacked area chart

#### GET `/api/analytics/camera-uptime`

- **Returns:** Per-camera uptime percentage
- **Schema:** CameraUptimeResponse
- **Data:** Camera ID, name, uptime %, detection count
- **Frontend:** CameraUptimeCard with bar list and health colors

#### GET `/api/analytics/object-distribution`

- **Returns:** Detection counts by object type
- **Schema:** ObjectDistributionResponse
- **Data:** Object type + count + percentage
- **Frontend:** ObjectDistributionCard with donut chart

#### GET `/api/analytics/risk-score-distribution`

- **Returns:** Risk score histogram
- **Schema:** RiskScoreDistributionResponse
- **Parameters:** bucket_size (default 10, range 1-50)
- **Frontend:** RiskScoreDistributionCard with bar chart

#### GET `/api/analytics/risk-score-trends`

- **Returns:** Daily average risk scores
- **Schema:** RiskScoreTrendsResponse
- **Data:** Date + avg_score + event count
- **Frontend:** RiskScoreTrendCard with line chart

## Zone Analytics Endpoints (0% UI Coverage)

### Line Zone Endpoints

| Endpoint                                                 | Purpose          | UI Status     |
| -------------------------------------------------------- | ---------------- | ------------- |
| POST `/api/analytics-zones/line-zones`                   | Create line zone | ✅ ZoneEditor |
| GET `/api/analytics-zones/line-zones/{id}`               | Get zone         | ✅            |
| GET `/api/analytics-zones/line-zones/camera/{id}`        | List by camera   | ✅            |
| PATCH `/api/analytics-zones/line-zones/{id}`             | Update zone      | ✅            |
| DELETE `/api/analytics-zones/line-zones/{id}`            | Delete zone      | ✅            |
| POST `/api/analytics-zones/line-zones/{id}/reset-counts` | Reset counts     | ❌ NO UI      |

### Polygon Zone Endpoints

| Endpoint                                                     | Purpose | UI Status  |
| ------------------------------------------------------------ | ------- | ---------- |
| POST `/api/analytics-zones/polygon-zones`                    | Create  | ✅         |
| GET `/api/analytics-zones/polygon-zones/{id}`                | Get     | ✅         |
| PATCH `/api/analytics-zones/polygon-zones/{id}`              | Update  | ✅         |
| DELETE `/api/analytics-zones/polygon-zones/{id}`             | Delete  | ✅         |
| POST `/api/analytics-zones/polygon-zones/{id}/toggle-active` | Toggle  | ⚠️ Partial |

### Dwell Time Endpoints (NO UI)

| Endpoint                                   | Purpose          | UI Status |
| ------------------------------------------ | ---------------- | --------- |
| GET `/polygon-zones/{id}/dwellers`         | Active dwellers  | ❌ NO UI  |
| GET `/polygon-zones/{id}/dwell-history`    | Historical data  | ❌ NO UI  |
| POST `/polygon-zones/{id}/check-loitering` | Loitering alerts | ❌ NO UI  |
| GET `/polygon-zones/{id}/dwell-statistics` | Aggregated stats | ❌ NO UI  |

## Frontend Analytics Components

### Main Page

- **AnalyticsPage** - Two view modes:
  - Grafana (default) - Embedded dashboard in kiosk mode
  - Native - Custom React components

### Dashboard Widgets

| Component                 | Purpose            | Data Source             |
| ------------------------- | ------------------ | ----------------------- |
| DetectionTrendsCard       | Detection volume   | detection-trends        |
| RiskHistoryCard           | Risk distribution  | risk-history            |
| CameraUptimeCard          | Camera health      | camera-uptime           |
| ObjectDistributionCard    | Object types       | object-distribution     |
| RiskScoreDistributionCard | Risk histogram     | risk-score-distribution |
| RiskScoreTrendCard        | Risk over time     | risk-score-trends       |
| CameraAnalyticsDetail     | Per-camera stats   | Per-camera              |
| WeekOverWeekCard          | Comparative        | Derived                 |
| PipelineLatencyPanel      | System performance | Telemetry               |
| ActivityHeatmap           | Time patterns      | Derived                 |
| CameraBaselinePanel       | Baselines          | Baseline API            |
| AnomalyConfigPanel        | Configuration      | Config API              |
| SceneChangePanel          | Scene changes      | Scene API               |

### Frontend Hooks

| Hook                       | Endpoint                | Purpose           |
| -------------------------- | ----------------------- | ----------------- |
| useDetectionTrendsQuery    | detection-trends        | Detection counts  |
| useRiskHistoryQuery        | risk-history            | Risk distribution |
| useCameraUptimeQuery       | camera-uptime           | Uptime stats      |
| useObjectDistributionQuery | object-distribution     | Object counts     |
| useRiskScoreDistribution   | risk-score-distribution | Risk histogram    |
| useRiskScoreTrends         | risk-score-trends       | Risk trends       |
| useCameraAnalytics         | (per-camera)            | Camera-specific   |

### TypeScript Types

All 6 main endpoints have corresponding interfaces:

```typescript
// frontend/src/types/analytics.ts
interface DetectionTrendsResponse { ... }
interface DetectionTrendDataPoint { ... }
interface RiskHistoryResponse { ... }
interface RiskHistoryDataPoint { ... }
interface CameraUptimeResponse { ... }
interface CameraUptimeDataPoint { ... }
interface ObjectDistributionResponse { ... }
interface ObjectDistributionDataPoint { ... }
interface RiskScoreDistributionResponse { ... }
interface RiskScoreDistributionBucket { ... }
interface RiskScoreTrendsResponse { ... }
interface RiskScoreTrendDataPoint { ... }
```

## Gaps and Missing Visualizations

### Zone Analytics (HIGH Priority)

| Feature                | Backend                | Frontend         |
| ---------------------- | ---------------------- | ---------------- |
| Line crossing patterns | ✅ in_count, out_count | ❌ No display    |
| Polygon zone activity  | ✅ Full tracking       | ❌ No heatmap    |
| Dwell time analytics   | ✅ Full statistics     | ❌ No dashboard  |
| Loitering alerts       | ✅ Configurable        | ❌ No UI         |
| Zone comparison        | ✅ Data available      | ❌ No comparison |

### Granular Filtering (MEDIUM Priority)

| Feature              | Backend              | Frontend           |
| -------------------- | -------------------- | ------------------ |
| Per-camera analytics | ⚠️ Separate endpoint | ❌ No filter       |
| Per-object type      | ✅ Data available    | ❌ No filter       |
| Custom date range    | ✅ 365 days max      | ⚠️ Limited presets |
| Risk level filtering | ✅ Available         | ❌ No filter       |

### Advanced Charts (MEDIUM Priority)

| Feature            | Backend           | Frontend           |
| ------------------ | ----------------- | ------------------ |
| Detection velocity | ✅ Derivable      | ❌ Not implemented |
| Risk correlations  | ✅ Data available | ❌ Not implemented |
| Hourly breakdowns  | ✅ Data available | ❌ Only daily      |
| Detection accuracy | ✅ Tracked        | ❌ Not visualized  |

### Anomaly Detection (MEDIUM Priority)

| Feature             | Backend       | Frontend           |
| ------------------- | ------------- | ------------------ |
| Baseline deviations | ✅ Calculated | ❌ Not highlighted |
| Outlier detection   | ✅ Available  | ❌ Not shown       |
| Anomaly scores      | ✅ Tracked    | ❌ No trend chart  |

### Export/Reports (LOW Priority)

| Feature           | Backend          | Frontend             |
| ----------------- | ---------------- | -------------------- |
| PDF reports       | ❌ Not available | ❌                   |
| CSV export        | ⚠️ Events only   | ❌ Not for analytics |
| Scheduled reports | ✅ Available     | ⚠️ Limited scope     |

## Recommendations

### High Priority

1. **Implement Zone Analytics Dashboard**

   - Line crossing trends
   - Dwell time statistics
   - Zone comparison

2. **Add Dwell Statistics View**
   - Active dwellers panel
   - Historical dwell chart
   - Loitering alerts feed

### Medium Priority

3. **Add Per-Camera Filtering**

   - Camera selector on analytics page
   - Camera-specific trend charts

4. **Implement Hourly Analytics**
   - Hourly breakdown option
   - Hour-of-day patterns

### Low Priority

5. **Add Export Functionality**

   - Export analytics as CSV
   - Generate PDF reports

6. **Real-time Analytics**
   - Live detection rate
   - Current risk level widget

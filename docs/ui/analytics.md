# Analytics

The analytics dashboard provides comprehensive insights into detection patterns, risk trends, and camera performance over time.

## What You're Looking At

The Analytics page is your data analysis hub for understanding security trends and system performance. It provides:

- **Detection Trends** - Daily detection counts visualized over time
- **Risk Analysis** - Risk score distribution and historical breakdown
- **Camera Performance** - Uptime statistics, activity patterns, and pipeline latency
- **Anomaly Detection** - Configurable settings for detecting unusual activity

The page is organized into four main tabs: Overview, Detections, Risk Analysis, and Camera Performance.

## Key Components

### Date Range Selector

Located in the top-right corner, the date range dropdown lets you filter all analytics data:

- **Last hour** - Real-time activity view (`1h`)
- **Last 24 hours** - Daily perspective (`24h`)
- **Today** - Start of today to now (`today`)
- **Last 7 days** - Default view for recent trends (`7d`)
- **Last 30 days** - Monthly perspective (`30d`)
- **Last 90 days** - Quarterly view (`90d`)
- **All time** - No date filtering (`all`)
- **Custom range** - Select specific start and end dates (`custom`)

The selected range is persisted in the URL query parameters, so you can bookmark or share specific views.

### Camera Selector

Choose between viewing aggregate statistics across all cameras or drilling down into a specific camera:

- **All Cameras** (default) - Shows combined statistics across your entire system with "Showing aggregate stats across all cameras" indicator
- **Individual Camera** - Shows camera-specific baselines and detailed metrics

When a specific camera is selected, additional information appears:

- **Total samples** count
- **Learning status** badge ("Learning Complete" in green or "Still Learning" in yellow)

### Refresh Button

A "Refresh" button next to the camera selector allows manual data refresh. The button shows a spinning icon while refreshing and is disabled during refresh to prevent duplicate requests.

### Overview Tab

The Overview tab provides a high-level summary of your security system:

#### Key Metrics Cards

Four metric cards at the top show:

| Metric             | Description                                      |
| ------------------ | ------------------------------------------------ |
| Total Events       | Number of security events in the selected period |
| Total Detections   | Number of object detections processed            |
| Average Confidence | Mean confidence score of AI detections           |
| High Risk Events   | Count of events flagged as high risk             |

#### Detection Trend Chart

An area chart showing daily detection counts over time. The chart displays the date range in the title (e.g., "Detection Trend (2026-01-11 to 2026-01-18)").

**How data is aggregated:**

- Detections are grouped by the date portion of `detected_at` timestamp
- Days with no detections show as zero (gaps are filled)
- The chart uses TanStack Query for efficient data fetching with caching

Useful for identifying:

- Activity spikes (unusual increases in detections)
- Quiet periods (potential camera issues or legitimate low activity)
- Day-of-week patterns (weekday vs. weekend differences)

#### Top Cameras by Activity

A bar chart ranking cameras by event count, helping you identify:

- Most active monitoring zones
- Cameras that may need attention
- Activity distribution across your property

### Detections Tab

The Detections tab focuses on what the AI is detecting:

#### Object Type Distribution

A horizontal bar list showing detection counts by object type (person, vehicle, animal, etc.):

- Color-coded by category (cyan, violet, amber, rose, emerald, fuchsia cycling)
- Shows detection count for each type with "X detections" label
- Total detection count displayed in the header
- Identifies the most common detections

**Color mapping for common classes:**

- Person: NVIDIA Green (#76B900)
- Vehicle/Car: Amber (#F59E0B)
- Truck: Dark amber (#D97706)
- Animal: Purple (#8B5CF6)
- Dog/Cat/Bird: Various purple shades

#### Class Frequency Baseline

_Available when a specific camera is selected._ Titled "Object Class Distribution" in the UI.

Shows the learned distribution of object classes for the selected camera:

- **Horizontal bar chart** showing each detected object class
- **Frequency score** per object class (higher = more common)
- **Sample count** (how much data backs the baseline) shown as "(X samples)"
- **Most common class** highlighted in the header (e.g., "Most common: Person")
- **Color-coded legend** at the bottom showing all unique classes

**Color assignments:**

- Person: NVIDIA Green (#76B900)
- Vehicle/Car: Amber tones
- Animals: Purple tones
- Other classes: Gray default

This baseline is used for anomaly detection - significant deviations from this learned pattern may indicate unusual activity. When "All Cameras" is selected, a message prompts to select a specific camera.

#### Detection Quality Metrics

Shows the overall quality of AI detections:

- Average confidence percentage
- Total detection count

### Risk Analysis Tab

The Risk Analysis tab helps you understand threat levels across your system:

#### Risk Score Distribution

A bar list showing events grouped by risk level:

| Risk Level | Score Range | Color  |
| ---------- | ----------- | ------ |
| Low        | 0-30        | Green  |
| Medium     | 31-60       | Yellow |
| High       | 61-80       | Orange |
| Critical   | 81-100      | Red    |

#### Anomaly Detection Settings

Configure how sensitive the system is to unusual activity:

- **Detection Threshold** - Slider from 1.0 to 4.0 standard deviations

  - Lower values = more sensitive (more alerts, more false positives)
  - Higher values = less sensitive (fewer alerts, may miss events)
  - Sensitivity levels: Very High (1.0-1.5), High (1.5-2.0), Medium (2.0-2.5), Low (2.5-3.0), Very Low (3.0-4.0)

- **Minimum Samples** - Number of samples required before anomaly detection is reliable (default: varies)

- **System-managed settings** (read-only):
  - Decay Factor: How quickly old data loses relevance
  - Window Days: Time window for baseline calculations

#### Recent High-Risk Events

A table listing the most recent high-risk events with:

- Timestamp
- Camera name
- Risk score badge
- AI reasoning/description

#### Risk Level Breakdown

A stacked area chart showing the daily breakdown of events by risk level over time. The chart displays the date range in the title.

**How data is aggregated:**

- Events are grouped by date and `risk_level` field
- Each day shows stacked counts for each risk level
- Days with no events show as zero for all levels
- Data fetched via `useRiskHistoryQuery` hook with TanStack Query

The legend shows:

- Critical (81+) - Red (#EF4444)
- High (61-80) - Orange (#F97316)
- Medium (31-60) - Yellow (#F59E0B)
- Low (0-30) - Emerald (#10B981)

### Camera Performance Tab

The Camera Performance tab monitors system health and efficiency:

#### Detection Counts by Camera

A bar list showing event counts per camera, helping you verify all cameras are functioning.

#### Camera Uptime Card

Shows uptime percentage for each camera based on detection activity. **Note:** This card always displays the last 30 days, regardless of the global date range selection.

| Status   | Uptime | Indicator       |
| -------- | ------ | --------------- |
| Healthy  | 95%+   | Green (emerald) |
| Degraded | 80-94% | Yellow          |
| Warning  | 60-79% | Orange          |
| Critical | <60%   | Red             |

Uptime is calculated as: (days with at least one detection) / (total days in 30-day range)

The card displays:

- Camera name and uptime percentage
- Visual progress bar color-coded by health status
- Legend explaining the status thresholds

#### Activity Heatmap

_Available when a specific camera is selected._

A 24x7 grid showing weekly activity patterns titled "Weekly Activity Pattern":

- **Rows (Y-axis)**: Days of the week (Mon-Sun)
- **Columns (X-axis)**: Hours (0-23, displayed as 12a, 3a, 6a, 9a, 12p, 3p, 6p, 9p)
- **Green shades**: Normal activity levels (intensity based on avg_count relative to max)
- **Orange shades**: Peak hours (statistically higher activity flagged by `is_peak`)
- **Gray cells**: Insufficient data (sample_count < min_samples_required)

**Color intensity scale:**

- 0-20% of max: Light green (#76B900/20)
- 20-40% of max: Medium-light green (#76B900/40)
- 40-60% of max: Medium green (#76B900/60)
- 60-80% of max: Medium-dark green (#76B900/80)
- 80-100% of max: Full green (#76B900)
- Peak hours use orange scale instead

Hover over cells to see:

- Day and hour (e.g., "Mon 9a")
- Average detection count
- Sample count
- Peak hour indicator if applicable

Shows "Learning (X / 168 slots)" badge if `learning_complete` is false. A complete baseline requires data for all 168 hour/day combinations (24 hours x 7 days).

#### Pipeline Latency Breakdown

Shows processing time through each stage of the AI pipeline:

| Stage                        | Internal Key       | Description                                    |
| ---------------------------- | ------------------ | ---------------------------------------------- |
| File Watcher -> RT-DETR      | `watch_to_detect`  | Time to detect new images and start processing |
| RT-DETR -> Batch Aggregator  | `detect_to_batch`  | Object detection processing time               |
| Batch Aggregator -> Nemotron | `batch_to_analyze` | Risk analysis queue time                       |
| Total End-to-End             | `total_pipeline`   | Complete pipeline processing time              |

For each stage, displays:

- **Avg**: Average latency in milliseconds
- **P50**: Median latency (50th percentile)
- **P95**: 95th percentile latency
- **P99**: 99th percentile latency
- **Samples**: Number of measurements

The **Bottleneck** badge (red) highlights the stage with the highest P95 latency.

**Time range selector** (dropdown):

- 1 hour (60 minutes, 60-second buckets)
- 6 hours (360 minutes, 5-minute buckets)
- 24 hours (1440 minutes, 15-minute buckets)

**Historical Trend** panel shows a sparkline visualization of P95 latency over time for each stage.

The panel auto-refreshes every 60 seconds by default and includes a manual refresh button.

#### Scene Change Detection

_Available when a specific camera is selected._

Monitors for potential camera tampering with a summary showing total and unacknowledged counts:

| Change Type   | Internal Key    | Description                                  |
| ------------- | --------------- | -------------------------------------------- |
| View Blocked  | `view_blocked`  | Camera view obstructed (red badge)           |
| Angle Changed | `angle_changed` | Camera physically moved (orange badge)       |
| View Tampered | `view_tampered` | Deliberate interference detected (red badge) |

Each scene change shows:

- **Change type badge** - Color-coded by severity
- **Detection timestamp** - When the change was detected
- **Similarity score** - Percentage (lower = more different from baseline)
- **Acknowledgment status** - Green "Acknowledged" badge if reviewed
- **Acknowledged timestamp** - When it was acknowledged (if applicable)

Click the green "Acknowledge" button to mark a scene change as reviewed. This action calls the POST endpoint to update the database.

**Footer note**: "Scene changes are detected when the camera view significantly differs from the baseline. Low similarity scores indicate potential tampering or view changes."

## Settings & Configuration

### Anomaly Detection Tuning

Access anomaly settings in the Risk Analysis tab. Adjust based on your needs:

| Environment       | Recommended Threshold | Notes                          |
| ----------------- | --------------------- | ------------------------------ |
| High security     | 1.5-2.0 std           | More alerts, review frequently |
| Standard home     | 2.0-2.5 std           | Balanced approach              |
| High traffic area | 2.5-3.0 std           | Fewer false positives          |

### Date Range Persistence

The selected date range is stored in the URL query parameter `?range=`. Options:

- `1h` - Last hour
- `24h` - Last 24 hours
- `today` - Today only
- `7d` - Last 7 days (default)
- `30d` - Last 30 days
- `90d` - Last 90 days
- `all` - All time (no filtering)
- `custom` with `start` and `end` parameters (YYYY-MM-DD format)

Example custom range URL: `?range=custom&start=2026-01-01&end=2026-01-15`

## Troubleshooting

### Charts show "No data available"

1. Check the date range - expand to a longer period
2. Verify cameras are uploading images to `/export/foscam/{camera_name}/`
3. Check that the AI pipeline is running (see System Health in header)

### Activity Heatmap shows "Still Learning"

The baseline requires data collection over time. Each hour/day combination needs multiple samples before patterns are reliable. Continue monitoring for 1-2 weeks for complete baseline.

### Camera Uptime shows Critical (<60%)

Possible causes:

1. Camera is offline or disconnected
2. FTP upload settings are incorrect
3. Camera directory permissions issue
4. Network connectivity problems

Check:

- Camera power and network connection
- FTP configuration on the camera
- Directory exists at `/export/foscam/{camera_name}/`
- File watcher service is running

### Pipeline Latency is High

If the Nemotron stage shows high latency:

1. Check GPU utilization (should be available but not maxed)
2. Verify llama.cpp server is running
3. Consider adjusting batch window settings

If the RT-DETR stage shows high latency:

1. Check detector service health
2. Verify GPU memory availability

### Anomaly Config Won't Save

1. Check backend connectivity
2. Ensure values are within valid ranges:
   - Threshold: 1.0 to 4.0
   - Minimum Samples: 1 to 100

---

## Technical Deep Dive

For developers wanting to understand the underlying systems.

### Architecture

- **Analytics API**: [Backend Routes](../../backend/api/routes/analytics.py)
- **System API** (anomaly config): [System Routes](../../backend/api/routes/system.py)
- **AI Pipeline**: [AI Pipeline Architecture](../architecture/ai-pipeline.md)
- **Data Model**: [Data Model Documentation](../architecture/data-model.md)

### Related Code

**Frontend Components:**

- Main Page: `frontend/src/components/analytics/AnalyticsPage.tsx`
- Activity Heatmap: `frontend/src/components/analytics/ActivityHeatmap.tsx`
- Class Frequency: `frontend/src/components/analytics/ClassFrequencyChart.tsx`
- Camera Uptime: `frontend/src/components/analytics/CameraUptimeCard.tsx`
- Date Range Dropdown: `frontend/src/components/analytics/DateRangeDropdown.tsx`
- Custom Date Picker: `frontend/src/components/analytics/CustomDateRangePicker.tsx`
- Anomaly Config: `frontend/src/components/analytics/AnomalyConfigPanel.tsx`
- Pipeline Latency: `frontend/src/components/analytics/PipelineLatencyPanel.tsx`
- Scene Changes: `frontend/src/components/analytics/SceneChangePanel.tsx`

**Backend Routes:**

- Analytics Routes: `backend/api/routes/analytics.py` (detection-trends, risk-history, camera-uptime, object-distribution)
- System Routes: `backend/api/routes/system.py` (anomaly-config endpoints)
- Event Stats: `backend/api/routes/events.py`
- Detection Stats: `backend/api/routes/detections.py`
- Camera Routes: `backend/api/routes/cameras.py` (baselines, scene-changes)

**Backend Services:**

- Baseline Service: `backend/services/baseline.py`
- Scene Baseline: `backend/services/scene_baseline.py`
- Scene Change Detector: `backend/services/scene_change_detector.py`

**React Hooks:**

- `frontend/src/hooks/useDateRangeState.ts` - Date range state management with URL persistence
- `frontend/src/hooks/useDetectionTrendsQuery.ts` - Detection trends data fetching (TanStack Query)
- `frontend/src/hooks/useRiskHistoryQuery.ts` - Risk history data fetching (TanStack Query)
- `frontend/src/hooks/useCameraUptimeQuery.ts` - Camera uptime data fetching (TanStack Query)

### API Endpoints

| Endpoint                                             | Method | Description                                                |
| ---------------------------------------------------- | ------ | ---------------------------------------------------------- |
| `/api/analytics/detection-trends`                    | GET    | Daily detection counts (requires `start_date`, `end_date`) |
| `/api/analytics/risk-history`                        | GET    | Daily risk level breakdown by low/medium/high/critical     |
| `/api/analytics/camera-uptime`                       | GET    | Camera uptime percentages based on active days             |
| `/api/analytics/object-distribution`                 | GET    | Detection counts by object type with percentages           |
| `/api/cameras/{id}/baseline/activity`                | GET    | Camera activity baseline (24x7 hour/day matrix)            |
| `/api/cameras/{id}/baseline/classes`                 | GET    | Camera class frequency baseline                            |
| `/api/system/anomaly-config`                         | GET    | Get current anomaly detection configuration                |
| `/api/system/anomaly-config`                         | PUT    | Update anomaly detection configuration                     |
| `/api/metrics/pipeline-latency`                      | GET    | Pipeline stage latencies (watch, detect, batch, analyze)   |
| `/api/metrics/pipeline-latency-history`              | GET    | Historical pipeline latency data                           |
| `/api/cameras/{id}/scene-changes`                    | GET    | Scene change detections for tampering monitoring           |
| `/api/cameras/{id}/scene-changes/{scid}/acknowledge` | POST   | Acknowledge a scene change                                 |

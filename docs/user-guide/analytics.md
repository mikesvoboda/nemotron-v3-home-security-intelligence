---
title: Analytics Dashboard
description: View detection patterns, risk trends, and camera performance analytics
source_refs:
  - frontend/src/components/analytics/AnalyticsPage.tsx
  - frontend/src/components/analytics/ActivityHeatmap.tsx
  - frontend/src/components/analytics/ClassFrequencyChart.tsx
  - frontend/src/components/analytics/CameraUptimeCard.tsx
  - frontend/src/components/analytics/AnomalyConfigPanel.tsx
---

# Analytics Dashboard

The Analytics page provides deep insights into your security system's activity patterns, detection trends, and camera performance over time. Use these analytics to understand normal activity patterns, identify anomalies, and optimize your security coverage.

---

## Accessing Analytics

1. Click **Analytics** in the left sidebar navigation
2. The page opens showing the Overview tab by default
3. Use the date range selector in the top-right to adjust the time period

---

## Page Header

At the top of the Analytics page, you will find:

### Date Range Selector

Select the time period for analytics data:

| Preset | Description           |
| ------ | --------------------- |
| 24h    | Last 24 hours         |
| 7d     | Last 7 days (default) |
| 30d    | Last 30 days          |
| Custom | Select specific dates |

### Camera Selector

Filter analytics by camera:

- **All Cameras** - View aggregate statistics across all cameras
- **Specific Camera** - View data for a single camera

When a specific camera is selected, additional features become available:

- Activity heatmap (24x7 pattern)
- Class frequency baseline
- Scene change detection
- Learning status indicator

### Refresh Button

Click **Refresh** to reload all analytics data with the latest information.

---

## Analytics Tabs

The Analytics page organizes information into four tabs:

### Overview Tab

The Overview tab provides a high-level summary of your security system activity.

#### Key Metrics Cards

Four summary cards display at the top:

| Metric             | Description                              | Color  |
| ------------------ | ---------------------------------------- | ------ |
| Total Events       | Number of security events in time period | Green  |
| Total Detections   | Number of AI object detections           | Blue   |
| Average Confidence | AI detection confidence (0-100%)         | Yellow |
| High Risk Events   | Events with risk score 60 or higher      | Red    |

#### Detection Trend Chart

An area chart shows daily detection counts over the selected time period:

- **X-axis**: Days in the selected range
- **Y-axis**: Number of detections
- **Hover**: Shows exact count for each day

Look for patterns like:

- Weekday vs weekend differences
- Time-of-day patterns
- Unusual spikes that may indicate incidents

#### Top Cameras by Activity

A bar chart shows which cameras have the most events:

- Cameras are ranked by event count
- Helps identify which areas have the most activity
- Useful for optimizing camera placement

---

### Detections Tab

The Detections tab provides detailed analysis of what the AI detects.

#### Object Type Distribution

A horizontal bar list shows detection counts by object type:

- **Person** - People detected across all cameras
- **Vehicle** - Cars, trucks, motorcycles
- **Animal** - Pets and wildlife (if enabled)

The total detection count appears in the top-right corner.

#### Class Frequency Chart

**Requires a specific camera to be selected.**

Shows the baseline frequency of each object class for the selected camera:

- Displays unique classes detected
- Shows the most common class
- Helps understand what "normal" looks like for each camera

#### Detections Over Time

An area chart showing detection volume trends:

- Useful for identifying busy periods
- Compare against historical baselines
- Spot unusual patterns

#### Detection Quality Metrics

Shows the health of your AI detection system:

| Metric             | Description                    | Good Value |
| ------------------ | ------------------------------ | ---------- |
| Average Confidence | Mean confidence across all     | Above 70%  |
| Total Detections   | Volume of detections processed | Varies     |

---

### Risk Analysis Tab

The Risk Analysis tab helps you understand threat patterns and configure anomaly detection.

#### Risk Score Distribution

A bar list shows events grouped by risk level:

| Risk Level     | Score Range | Color  |
| -------------- | ----------- | ------ |
| Low (0-30)     | 0-30        | Green  |
| Medium (31-60) | 31-60       | Amber  |
| High (61-80)   | 61-80       | Orange |
| Critical (81+) | 81-100      | Red    |

The total event count appears in the top-right corner.

#### Anomaly Configuration Panel

Configure how the system detects unusual activity:

| Setting        | Description                              | Default |
| -------------- | ---------------------------------------- | ------- |
| Enabled        | Turn anomaly detection on/off            | On      |
| Sensitivity    | How easily anomalies are flagged (0-100) | 50      |
| Time Window    | Period for baseline comparison (hours)   | 24      |
| Min Confidence | Minimum detection confidence to consider | 0.5     |

> **Tip:** Start with default settings and adjust based on false positive/negative rates.

#### Recent High-Risk Events

A table showing the most recent high-risk events:

| Column      | Description                         |
| ----------- | ----------------------------------- |
| Time        | When the event occurred             |
| Camera      | Which camera detected it            |
| Risk Score  | Numeric risk value (red badge)      |
| Description | AI-generated reasoning for the risk |

Click any row to investigate that event further.

#### Risk Level Breakdown Chart

A stacked area chart showing how risk levels change over time:

- **Red area**: Critical events
- **Orange area**: High-risk events
- **Yellow area**: Medium-risk events
- **Green area**: Low-risk events

Use this to identify:

- Time periods with elevated risk
- Whether high-risk events are increasing or decreasing
- Patterns in when threats typically occur

---

### Camera Performance Tab

The Camera Performance tab focuses on the health and efficiency of your camera infrastructure.

#### Detection Counts by Camera

A bar list ranking cameras by detection volume:

- Helps identify underperforming cameras
- Shows which cameras capture the most activity
- Total detections displayed in header

#### Camera Uptime Card

Shows camera reliability over the last 30 days:

| Metric          | Description                          |
| --------------- | ------------------------------------ |
| Uptime %        | Percentage of time camera was online |
| Online Hours    | Total hours with active connection   |
| Offline Periods | Number of disconnection events       |

Green indicates good uptime (above 95%), yellow indicates moderate (80-95%), and red indicates poor (below 80%).

#### Activity Heatmap

**Requires a specific camera to be selected.**

A 24x7 grid showing activity patterns:

- **X-axis**: Days of the week (Sun-Sat)
- **Y-axis**: Hours of the day (0-23)
- **Color intensity**: Darker = more activity

Use this to understand:

- Peak activity hours
- Quiet periods
- Day-of-week patterns

##### Learning Status

The heatmap shows a learning indicator:

| Status            | Meaning                                    |
| ----------------- | ------------------------------------------ |
| Still Learning    | Less than minimum samples collected        |
| Learning Complete | Baseline established, anomalies detectable |

The total sample count is displayed to show data volume.

#### Pipeline Latency Panel

Shows AI processing performance:

| Metric         | Description                  | Good Value  |
| -------------- | ---------------------------- | ----------- |
| Detection Time | Time to run object detection | Under 100ms |
| Inference Time | Full AI pipeline time        | Under 500ms |
| Queue Depth    | Pending frames to process    | Under 10    |

High latency may indicate:

- GPU under heavy load
- Too many cameras for hardware
- Network issues

#### Scene Change Detection

**Requires a specific camera to be selected.**

Monitors for significant changes in the camera view:

- Detects if camera was moved or obstructed
- Identifies lighting changes
- Flags tampering attempts

---

## Understanding Baseline Learning

When you select a specific camera, the system displays baseline learning status:

### What is Baseline Learning?

The AI builds a model of "normal" activity for each camera by:

1. Collecting detection samples over time
2. Analyzing patterns in timing and frequency
3. Building statistical models of expected behavior

### Learning Indicators

| Indicator         | Samples    | Meaning                           |
| ----------------- | ---------- | --------------------------------- |
| Still Learning    | < minimum  | Need more data for reliable model |
| Learning Complete | >= minimum | Baseline established              |

### Why Baselines Matter

With a complete baseline, the system can:

- Flag unusual activity automatically
- Reduce false positives for known patterns
- Detect genuine anomalies more accurately

---

## Using Analytics Effectively

### Daily Review

1. Check the Overview tab for any unusual spikes
2. Review High-Risk Events in Risk Analysis
3. Glance at Camera Performance for uptime issues

### Weekly Review

1. Compare this week's trends to previous weeks
2. Check if any cameras are underperforming
3. Review the Activity Heatmap for pattern changes
4. Adjust Anomaly Configuration if needed

### After Incidents

1. Use the Risk Analysis tab to understand severity
2. Check Detection Trend for similar past events
3. Review Camera Uptime to ensure coverage during incident
4. Verify Scene Change Detection did not miss tampering

---

## Troubleshooting

### No Data Showing

**Check:**

- Selected date range includes actual events
- Cameras are online and sending images
- Backend services are running

### Charts Not Loading

**Try:**

- Click the Refresh button
- Select a different date range
- Check network connectivity
- Clear browser cache

### Activity Heatmap Empty

**Causes:**

- "All Cameras" selected (heatmap needs specific camera)
- Camera has insufficient data
- Learning still in progress

**Fix:** Select a specific camera and wait for baseline learning to complete.

### Risk History Not Accurate

**Check:**

- Date range is appropriate for analysis
- Events have risk scores assigned
- AI pipeline is processing events

---

## Related Documentation

- [Dashboard Overview](dashboard-overview.md) - Main dashboard features
- [Understanding Alerts](understanding-alerts.md) - Risk scoring explained
- [Detection Zones](zones.md) - Focus AI analysis on specific areas
- [System Monitoring](system-monitoring.md) - Overall system health

---

[Back to User Hub](../user/README.md)

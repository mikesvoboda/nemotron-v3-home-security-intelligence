# AI Performance Page Redesign

**Date:** 2026-01-04
**Status:** Approved

## Overview

Redesign the AI Performance page to better organize metrics, incorporate components moving from AI Audit page, and add Model Zoo visibility. Support three use cases: real-time monitoring, historical analysis, and model comparison.

## Goals

1. Add summary row for instant AI health status
2. Integrate Model Contribution Rates and Leaderboard from AI Audit (NEM-1136)
3. Add Model Zoo panels showing all 18 models (NEM-1129)
4. Make distribution charts clickable to filter Timeline (NEM-1135)
5. Organize into logical sections with clear visual hierarchy

## Current State

The page displays components in a single-column layout:

- RT-DETRv2 and Nemotron status panels
- Latency Over Time timeseries with dropdown
- Queue Depths panel (Detection, Analysis, DLQ)
- Detection Class Distribution bar chart (broken)
- Risk Score Distribution bar chart
- Recent Detections table

## Proposed Changes

### 1. Page Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│ AI Performance                   [5m] [15m] [60m]    [Open Grafana →]   │
├─────────────────────────────────────────────────────────────────────────┤
│ ┌───────────┬───────────┬───────────┬───────────┬───────────┐           │
│ │ RT-DETRv2 │ Nemotron  │  Queues   │Throughput │  Errors   │ ← Summary │
│ │  ✓ 14ms   │  ✓ 2.1s   │ 0 queued  │  1.2/min  │ 0 errors  │    Row    │
│ └───────────┴───────────┴───────────┴───────────┴───────────┘           │
├─────────────────────────────────────────────────────────────────────────┤
│ PIPELINE PERFORMANCE                                                    │
│ [Latency Over Time - full width                                        ]│
│ [Detection Class Dist (1/2)] [Risk Score Distribution (1/2)]            │
├─────────────────────────────────────────────────────────────────────────┤
│ AI MODELS                                                               │
│ [Model Zoo Grid - full width, active only + Show All toggle            ]│
│ [Contribution Rates (1/2)  ] [Model Leaderboard (1/2)                  ]│
├─────────────────────────────────────────────────────────────────────────┤
│ RECENT ACTIVITY                                                         │
│ [Recent Detections Table - full width                                  ]│
└─────────────────────────────────────────────────────────────────────────┘
```

### 2. Summary Row

```
┌───────────┬───────────┬───────────┬───────────┬───────────┐
│ RT-DETRv2 │ Nemotron  │  Queues   │Throughput │  Errors   │
│  ✓ 14ms   │  ✓ 2.1s   │ 0 queued  │  1.2/min  │ 0 errors  │
└───────────┴───────────┴───────────┴───────────┴───────────┘
```

**Indicator Thresholds:**

| Indicator  | Green          | Yellow            | Red            |
| ---------- | -------------- | ----------------- | -------------- |
| RT-DETRv2  | Running, <50ms | Running, 50-200ms | Down or >200ms |
| Nemotron   | Running, <5s   | Running, 5-15s    | Down or >15s   |
| Queues     | 0-10 items     | 11-50 items       | 50+ items      |
| Throughput | >0.5/min       | 0.1-0.5/min       | <0.1/min or 0  |
| Errors     | 0 errors       | 1-10 errors       | 10+ errors     |

**Behavior:**

- Click any indicator → smooth scroll to relevant section
- Hover shows tooltip with additional detail
- Real-time updates via WebSocket

**Responsive:**

- Desktop: 5 columns in row
- Tablet: 5 smaller columns
- Mobile: 2x3 grid

### 3. Pipeline Performance Section

```
┌─────────────────────────────────────────────────────────────────────────┐
│ PIPELINE PERFORMANCE                                                    │
├─────────────────────────────────────────────────────────────────────────┤
│ Latency Over Time                             [Stage: Total Pipeline ▼] │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ [Full-width timeseries graph with avg, p95, p99 lines]              │ │
│ │                                                                     │ │
│ │  ── avg (14.2s)  ── p95 (43.1s)  ── p99 (98.2s)                    │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│ ┌────────────────────────────────┐ ┌────────────────────────────────┐   │
│ │ Detection Class Distribution   │ │ Risk Score Distribution        │   │
│ │                                │ │                                │   │
│ │ person  ████████████████  847  │ │ Low     ████████████████  52   │   │
│ │ car     ████████████     523   │ │ Medium  ████████         28   │   │
│ │ truck   ██████           298   │ │ High    ████             12   │   │
│ │                                │ │ Critical██                4   │   │
│ │ Click bar to filter Timeline   │ │ Click bar to filter Timeline   │   │
│ └────────────────────────────────┘ └────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

**Latency Graph:**

- Full width for clear trend visibility
- Shows avg, p95, p99 lines (toggleable in legend)
- Dropdown options: File Watch→Detection, Detection→Batch, Batch→Analysis, Total Pipeline
- Time range controlled by header buttons (5m/15m/60m)

**Distribution Charts (Clickable - NEM-1135):**

- Horizontal bar charts with counts
- Click bar → navigate to Timeline with filter applied
- Detection Class: `/timeline?class=person`
- Risk Score: `/timeline?minScore=60&maxScore=84`

### 4. AI Models Section

```
┌─────────────────────────────────────────────────────────────────────────┐
│ AI MODELS                                                               │
├─────────────────────────────────────────────────────────────────────────┤
│ Model Zoo                    Active: 3/18   VRAM: 2.0/24GB   [Show All] │
│ ┌───────────┐ ┌───────────┐ ┌───────────┐                               │
│ │ RT-DETRv2 │ │ CLIP ViT  │ │ Florence-2│                               │
│ │  ● Loaded │ │  ● Loaded │ │ ◐ Loading │                               │
│ │ 1.2GB     │ │ 0.8GB     │ │ 0.1GB...  │                               │
│ │ 1,847 inf │ │ 1,203 inf │ │ -         │                               │
│ │ 14ms avg  │ │ 45ms avg  │ │ -         │                               │
│ └───────────┘ └───────────┘ └───────────┘                               │
├─────────────────────────────────────────────────────────────────────────┤
│ ┌────────────────────────────────┐ ┌────────────────────────────────┐   │
│ │ Model Contribution Rates       │ │ Model Leaderboard              │   │
│ │                                │ │                                │   │
│ │ RT-DETRv2   ██████████████ 62% │ │ Rank Model       Inf   Lat     │   │
│ │ CLIP ViT    ████████       34% │ │ 1.   RT-DETRv2  1847  14ms    │   │
│ │ Florence-2  █               4% │ │ 2.   CLIP ViT   1203  45ms    │   │
│ │                                │ │ ...                            │   │
│ └────────────────────────────────┘ └────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

**Model Zoo Grid (NEM-1129):**

- Shows only loaded/loading models by default
- Each card: model name, status, VRAM, inference count, avg latency
- Status indicators: ● Loaded (green), ◐ Loading (yellow), ○ Unloaded (gray), ✗ Error (red)
- "Show All" expands to full 18-model grid
- VRAM budget bar in header

**Model Contribution Rates (from AI Audit - NEM-1136):**

- Horizontal bar chart showing % of total inferences
- Only shows models with >0 inferences
- Sorted by contribution (highest first)

**Model Leaderboard (from AI Audit - NEM-1136):**

- Table: Rank, Model, Inferences, Avg Latency
- Sorted by inference count (default), click header to re-sort
- Shows top 5 by default, expandable to all 12

### 5. Additional Metrics (from Prometheus)

Based on metrics being collected in `backend/core/metrics.py` but not currently displayed:

**Detection Confidence Distribution:**

```
┌────────────────────────────────────────────────────────────────────────────┐
│ Detection Confidence Distribution                                          │
├────────────────────────────────────────────────────────────────────────────┤
│ 0.9-1.0  ████████████████████████████████████████  847 (62%)               │
│ 0.8-0.9  ████████████████████                      312 (23%)               │
│ 0.7-0.8  ██████████                                 142 (10%)               │
│ 0.5-0.7  ████                                        68 (5%)                │
│                                                                            │
│ Metric: hsi_detection_confidence (Histogram)                               │
└────────────────────────────────────────────────────────────────────────────┘
```

- Shows distribution of RT-DETRv2 detection confidence scores
- Helps identify if model is producing low-confidence results
- Click bar → filter Timeline to show detections in that confidence range

**Per-Model Latency Comparison:**

```
┌────────────────────────────────────────────────────────────────────────────┐
│ Model Latency Breakdown                           [Last 5m ▼]              │
├────────────────────────────────────────────────────────────────────────────┤
│ RT-DETRv2    ██  14ms avg   │  p50: 12ms  p95: 28ms  p99: 45ms            │
│ Nemotron     ████████████████████████████  2.1s avg  │  p50: 1.8s  p95: 4.2s │
│ Florence-2   ████  180ms avg │  p50: 150ms  p95: 320ms                     │
│ CLIP ViT     ██  45ms avg   │  p50: 40ms  p95: 85ms                        │
│                                                                            │
│ Metric: hsi_ai_request_duration_seconds (Histogram, by service label)      │
└────────────────────────────────────────────────────────────────────────────┘
```

- Shows latency percentiles for each active model
- Helps identify which model is the bottleneck
- Data from `AI_REQUEST_DURATION` histogram with `service` label

**Filtered Detections Counter:**

Add to Summary Row or Pipeline Performance section:

```
│ Filtered │
│  12 low  │  ← Detections filtered due to low confidence
│ conf/hr  │
```

- Metric: `hsi_detections_filtered_low_confidence_total` (Counter)
- Shows how many detections were dropped due to confidence threshold
- Helps tune YOLO-World confidence threshold

**Events by Camera:**

```
┌────────────────────────────────────────────────────────────────────────────┐
│ Events by Camera                                  [Last 24h ▼]             │
├────────────────────────────────────────────────────────────────────────────┤
│ front_door       ████████████████████████████████  312 events              │
│ driveway         ████████████████████               198 events              │
│ backyard         ████████████                       124 events              │
│ kitchen          ████                                52 events              │
│                                                                            │
│ Metric: hsi_events_by_camera_total (Counter, by camera_id/camera_name)     │
└────────────────────────────────────────────────────────────────────────────┘
```

- Shows which cameras generate the most events
- Click bar → filter Timeline to that camera
- Helps identify noisy cameras or coverage gaps

### 6. Recent Activity Section

```
┌─────────────────────────────────────────────────────────────────────────┐
│ RECENT ACTIVITY                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│ Recent Detections                                       [View All →]    │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ Time     │ Camera          │ Classes        │ Risk  │ Status       │ │
│ │ 1:52:14  │ front_door      │ person, car    │ ██ 72 │ ✓ Analyzed   │ │
│ │ 1:51:48  │ backyard        │ dog            │ █  15 │ ✓ Analyzed   │ │
│ │ 1:51:22  │ driveway        │ car, truck     │ █  28 │ ✓ Analyzed   │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│ Showing 5 most recent  •  Auto-updates via WebSocket  •  [View All →]   │
└─────────────────────────────────────────────────────────────────────────┘
```

**Table Features:**

- Shows 5 most recent detections
- Columns: Time, Camera, Classes, Risk (with mini-bar), Status
- Click row → opens event detail modal
- Auto-updates via WebSocket
- "View All →" navigates to Timeline

## Implementation Tasks

1. **Create Summary Row component**

   - 5 indicators with thresholds
   - Click-to-scroll behavior
   - Real-time WebSocket updates

2. **Refactor Pipeline Performance section**

   - Full-width latency graph
   - Two-column distribution charts below
   - Add click handlers for Timeline navigation

3. **Build AI Models section**

   - Model Zoo mini-card grid (active-only default)
   - Move Contribution Rates from AI Audit
   - Move Leaderboard from AI Audit

4. **Update Recent Activity section**

   - Compact 5-row table
   - Real-time updates
   - Row click opens modal

5. **Fix broken data sources (NEM-1128)**
   - Detection Class Distribution
   - Batch to Analysis latency
   - Total Pipeline latency

## Related Issues

- NEM-1128: Fix Detection Class Distribution and Pipeline Latency bugs
- NEM-1129: Add Model Zoo panels
- NEM-1135: Make Risk Score Distribution clickable
- NEM-1136: Move components from AI Audit page

## Success Criteria

- [ ] Summary row visible above the fold with 5 indicators
- [ ] All indicators show accurate real-time status
- [ ] Latency graph full-width with working dropdown
- [ ] Distribution charts clickable → navigate to Timeline
- [ ] Model Zoo shows active models with Show All toggle
- [ ] Contribution Rates and Leaderboard integrated
- [ ] Recent Detections auto-updates via WebSocket
- [ ] Responsive layout works on tablet/mobile

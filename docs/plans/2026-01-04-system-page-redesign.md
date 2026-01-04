# System Page Redesign

**Date:** 2026-01-04
**Status:** Approved

## Overview

Redesign the System Monitoring page to improve visual hierarchy, reduce information density, and support three primary use cases: quick health checks, troubleshooting, and capacity planning.

## Goals

1. Enable "2-second health check" via summary row
2. Reduce scrolling by consolidating 13 components into 3 logical sections
3. Support drill-down for troubleshooting without cluttering the default view
4. Visualize pipeline flow to help users understand system architecture

## Current State

The page displays 13 separate components in a single-column layout:

- Header with time range buttons and Grafana link
- System Health card
- Services card
- GPU Statistics with tabbed graph
- RT-DETRv2 status card (broken)
- Nemotron status card (broken)
- AI Model Zoo table (18 rows)
- Pipeline Metrics card
- Databases card (broken)
- Background Workers expandable section
- Containers card (broken)
- Host System card (broken)
- Circuit Breakers card (broken)
- Severity Configuration (read-only)

## Proposed Changes

### 1. Remove Severity Configuration

Moved to Settings page per NEM-1142 (will be made editable there).

### 2. Add Summary Row

Five clickable indicators at the top for instant health status:

```
┌────────────┬────────────┬────────────┬────────────┬────────────┐
│  OVERALL   │    GPU     │  PIPELINE  │ AI MODELS  │   INFRA    │
│     ✓      │  38% 40°C  │   0 queue  │   2/2 ✓    │   4/4 ✓    │
│  healthy   │  0.2/24GB  │  1.2/min   │  1.8k inf  │            │
└────────────┴────────────┴────────────┴────────────┴────────────┘
```

**Indicator States:**
| State | Color | Meaning |
|-------|-------|---------|
| Healthy | Green | All components OK |
| Degraded | Yellow | Performance issues, warnings |
| Critical | Red | Component down or failing |

**Behavior:**

- Click any indicator → smooth scroll to that section
- Hover shows tooltip with component breakdown
- Updates in real-time via WebSocket
- Overall uses simple aggregate (worst component status)

**Responsive:**

- Desktop: 5 columns in row
- Tablet: 5 smaller columns
- Mobile: 2x3 grid (Overall spans full width on top)

### 3. Reorganized Page Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│ System Monitoring            [5m] [15m] [60m]    [Open Grafana →]  [↻]  │
├─────────────────────────────────────────────────────────────────────────┤
│ ┌───────────┬───────────┬───────────┬───────────┬───────────┐           │
│ │  OVERALL  │    GPU    │ PIPELINE  │ AI MODELS │   INFRA   │ ← Summary │
│ │  healthy  │ 38% 40°C  │  0 queue  │   2/2 ✓   │   4/4 ✓   │    Row    │
│ └───────────┴───────────┴───────────┴───────────┴───────────┘           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  GPU & AI MODELS                                                        │
│  ┌────────────────────────────────┬───────────────────────────────────┐ │
│  │ GPU Statistics                 │ AI Model Zoo                      │ │
│  │ (stacked sparklines)           │ (active models + show all toggle) │ │
│  │ RT-DETRv2 | Nemotron           │                                   │ │
│  └────────────────────────────────┴───────────────────────────────────┘ │
│                                                                         │
│  PIPELINE                                                               │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ Pipeline Flow Visualization (FileWatch→Detect→Batch→Analyze)       │ │
│  │ Workers: 8/8 Running                                               │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  INFRASTRUCTURE                                                         │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐              │
│  │PostgreSQL│  Redis   │Containers│   Host   │ Circuits │              │
│  │    ✓     │    ✓     │   5/5    │    ✓     │   3/3    │              │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘              │
│  [Expandable detail panel when any card is clicked]                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4. GPU & AI Models Section

```
┌─────────────────────────────────────────────────────────────────────────┐
│ GPU & AI MODELS                                                         │
├──────────────────────────────────┬──────────────────────────────────────┤
│ GPU Statistics    RTX A5500      │ AI Model Zoo         VRAM: 2.0/24GB  │
│                                  │                           [Show All] │
│ Utilization  38%  ▁▂▃▅▇█▆▄▃▂▁▂▃▄ │ ┌──────────────────────────────────┐ │
│ Temperature  40°C ▂▂▂▂▃▃▃▃▃▃▃▃▃▃ │ │ Model         Status  VRAM  Inf  │ │
│ Memory      0.2GB ▁▁▁▁▁▁▁▂▂▂▂▂▁▁ │ │ RT-DETRv2     Loaded  1.2GB 1.8k │ │
│ Power        31W  ▁▂▃▄▅▄▃▂▁▂▃▄▅▆ │ │ CLIP ViT-L    Loaded  0.8GB 1.2k │ │
│                                  │ ├──────────────────────────────────┤ │
│ Inference FPS: 2.4               │ │ 16 models unloaded    [Show All→]│ │
│              [Open Grafana →]    │ └──────────────────────────────────┘ │
├──────────────────────────────────┴──────────────────────────────────────┤
│ RT-DETRv2                        │ Nemotron                             │
│ ● Running    Latency: 14ms       │ ● Running    Latency: 2.1s           │
│ Inferences: 1,847  Errors: 0     │ Analyses: 64     Errors: 0           │
└──────────────────────────────────┴──────────────────────────────────────┘
```

**GPU Statistics:**

- Stacked sparklines (not tabbed) showing all 4 metrics simultaneously
- 20-point history matching the time range selector
- Each row: label, current value, mini-graph
- Inference FPS prominent at bottom

**AI Model Zoo:**

- Shows only loaded/loading models by default
- "Show All" toggle expands to full 18-model table in-place
- VRAM budget bar at top shows capacity usage
- Columns: Model name, Status, VRAM, Inference count

**Primary Models (RT-DETRv2 & Nemotron):**

- Dedicated mini-cards below GPU stats
- Show: running status, latency, count, errors
- Always visible (not affected by "Show All" toggle)

### 5. Pipeline Section

```
┌─────────────────────────────────────────────────────────────────────────┐
│ PIPELINE                                                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐       │
│   │  📁     │      │  🔍     │      │  📦     │      │  🧠     │       │
│   │ Files   │ ───▶ │ Detect  │ ───▶ │ Batch   │ ───▶ │ Analyze │       │
│   └─────────┘      └─────────┘      └─────────┘      └─────────┘       │
│    12/min           Queue: 0         3 pending        Queue: 0         │
│                     Avg: 14s                          Avg: 2.1s        │
│                     P95: 43s                          P95: 4.8s        │
│                                                                         │
│   Total Pipeline: 16.1s avg → 47.8s p95 → 102s p99                     │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│ Background Workers                                         8/8 Running  │
│ ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐                      │
│ │ ●   │ ●   │ ●   │ ●   │ ●   │ ●   │ ●   │ ●   │                      │
│ │ Det │ Ana │Batch│Clean│Watch│ GPU │Metr │Bcast│                      │
│ └─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘    [Expand Details]  │
└─────────────────────────────────────────────────────────────────────────┘
```

**Pipeline Flow:**

- Visual left-to-right diagram showing data journey
- Each stage shows: queue depth, avg latency, p95 latency
- Stage boxes change color based on health:
  - Green: queue 0-10, latency < 2x baseline
  - Yellow: queue 11-50, latency 2-5x baseline
  - Red: queue 50+, latency > 5x baseline
- Total pipeline latency summarized at bottom

**Background Workers:**

- Compact grid of 8 status dots with abbreviations
- Green = running, Red = stopped, Yellow = degraded
- "Expand Details" reveals full worker list with descriptions

### 6. Additional Metrics (from Prometheus)

Based on metrics being collected in `backend/core/metrics.py` but not currently displayed:

**Pipeline Error Breakdown:**

Add to Pipeline section or as expandable detail:

```
┌────────────────────────────────────────────────────────────────────────────┐
│ Pipeline Errors                                   [Last 1h ▼]              │
├────────────────────────────────────────────────────────────────────────────┤
│ By Type:                                                                   │
│   rtdetr_timeout      ████████████████  12                                 │
│   nemotron_error      ████████          6                                  │
│   file_not_found      ████              3                                  │
│   batch_overflow      ██                1                                  │
│                                                                            │
│ Metric: hsi_pipeline_errors_total (Counter, by error_type label)           │
└────────────────────────────────────────────────────────────────────────────┘
```

- Shows breakdown of pipeline errors by type
- Helps identify specific failure modes (AI timeout vs file issues)
- Click error type → filter logs/events to that error

**Queue Health Metrics:**

Add to Pipeline section below the flow diagram:

```
┌────────────────────────────────────────────────────────────────────────────┐
│ Queue Health                                      [Last 1h ▼]              │
├────────────────────────────────────────────────────────────────────────────┤
│ Detection Queue │ Analysis Queue │ DLQ                                     │
│ Depth: 0        │ Depth: 0       │ Depth: 3                                │
│ Dropped: 0      │ Dropped: 0     │ Moved: 3                                │
│ Rejected: 0     │ Rejected: 0    │                                         │
│ Overflow: 0     │ Overflow: 0    │                                         │
│                                                                            │
│ Metrics:                                                                   │
│   hsi_queue_overflow_total (Counter, by queue_name, policy)                │
│   hsi_queue_items_dropped_total (Counter, by queue_name)                   │
│   hsi_queue_items_rejected_total (Counter, by queue_name)                  │
└────────────────────────────────────────────────────────────────────────────┘
```

- Shows queue overflow events and policies applied
- Dropped: items removed due to overflow policy
- Rejected: items rejected before entering queue
- Overflow: total overflow events (may trigger drop/reject/DLQ move)

**Queue Overflow Policies:**

| Policy        | Behavior                           |
| ------------- | ---------------------------------- |
| `drop_oldest` | Remove oldest items when full      |
| `drop_newest` | Reject new items when full         |
| `move_to_dlq` | Move overflow to Dead Letter Queue |

### 7. Infrastructure Section

```
┌─────────────────────────────────────────────────────────────────────────┐
│ INFRASTRUCTURE                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐  │
│ │ PostgreSQL│ │   Redis   │ │Containers │ │   Host    │ │ Circuits  │  │
│ │     ✓     │ │     ✓     │ │   5/5 ✓   │ │     ✓     │ │   3/3 ✓   │  │
│ │   12ms    │ │  1.2k/s   │ │           │ │  CPU 12%  │ │           │  │
│ └───────────┘ └───────────┘ └───────────┘ └───────────┘ └───────────┘  │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ ▼ PostgreSQL Details (expanded)                                     │ │
│ │   Connection Pool: 8/20 active                                      │ │
│ │   Query Latency: 12ms avg, 45ms p95                                 │ │
│ │   Active Queries: 2                                                 │ │
│ │   Database Size: 1.2 GB                                             │ │
│ │   Last Backup: 2026-01-04 02:00                                     │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

**Status Grid:**

- 5 compact cards showing: component name, status icon, key metric
- Click any card to expand details below (accordion - one at a time)

**Detail Panels:**
| Component | Details |
|-----------|---------|
| PostgreSQL | Pool usage, query latency, active queries, DB size, last backup |
| Redis | Memory usage, ops/sec, connected clients, hit rate |
| Containers | List with status, CPU, memory, restart counts |
| Host | CPU, Memory, Disk usage with progress bars |
| Circuits | Circuit breaker states, failure counts |

## Implementation Tasks

1. **Create Summary Row component**

   - 5 health indicators with click-to-scroll
   - Real-time WebSocket updates
   - Color-coded status states

2. **Refactor GPU Statistics**

   - Replace tabbed graph with stacked sparklines
   - Add RT-DETRv2 and Nemotron mini-cards below

3. **Update AI Model Zoo**

   - Default to showing only active models
   - Add "Show All" toggle
   - Add VRAM budget bar

4. **Build Pipeline Flow visualization**

   - Visual diagram with stage boxes and arrows
   - Live metrics at each stage
   - Color-coded health states
   - Compact worker grid with expand option

5. **Create Infrastructure status grid**

   - 5 compact status cards
   - Accordion-style expandable details
   - Lazy load detail data on expand

6. **Fix broken data sources (NEM-1141)**
   - RT-DETRv2 and Nemotron status
   - Database metrics (resolve inconsistency)
   - Container status
   - Host system metrics
   - Circuit breaker data

## Success Criteria

- [ ] Page loads with summary row visible above the fold
- [ ] All 5 summary indicators show accurate real-time status
- [ ] Click on summary indicator scrolls to section
- [ ] GPU shows 4 stacked sparklines (no tabs)
- [ ] Model Zoo defaults to active models only
- [ ] Pipeline visualization shows flow with live metrics
- [ ] Infrastructure grid expands on click
- [ ] All previously broken metrics now display data
- [ ] Page height reduced by ~40% from current
- [ ] Responsive layout works on tablet and mobile

## Related Issues

- NEM-1141: System page metrics not working (prerequisite bug fixes)
- NEM-1142: Move Severity Configuration to Settings

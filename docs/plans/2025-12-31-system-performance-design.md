# System Performance Dashboard Design

> Enhance the existing `/system` monitoring page with comprehensive GPU, AI models, inference stats, databases, and host metrics.

**Created:** 2025-12-31
**Status:** Approved

## Overview

Enhance the existing `SystemMonitoringPage` at `/system` to provide full observability without requiring external tools like Grafana. Metrics are pushed via WebSocket every 5 seconds with historical charts for 5min/15min/60min windows.

### Goals

1. **Debugging AI performance** - See which model consumes resources when inference is slow
2. **Capacity planning** - Monitor VRAM limits before adding more cameras
3. **General observability** - Comprehensive system health at a glance

## Existing Components Analysis

The `/system` route already has these components:

| Component                 | Current Function                    | Action                                   |
| ------------------------- | ----------------------------------- | ---------------------------------------- |
| **System Overview Card**  | Uptime, cameras, events, detections | **KEEP** - valuable operational stats    |
| **Service Health Card**   | DB, Redis, RT-DETR, Nemotron status | **MERGE** into Containers panel          |
| **WorkerStatusPanel**     | 8 background workers                | **KEEP** - critical for debugging        |
| **PipelineQueues**        | Detection + analysis queue depths   | **MERGE** into Inference Stats           |
| **GpuStats**              | GPU util, memory, temp, power, FPS  | **ENHANCE** - add nvidia-smi, time range |
| **Pipeline Latency Card** | detect/analyze avg/P95/P99          | **ENHANCE** - add charts, throughput     |
| **ObservabilityPanel**    | GPU charts, Grafana link (unused)   | **REMOVE** - redundant                   |

### New Sections to Add

| New Section             | Purpose                              |
| ----------------------- | ------------------------------------ |
| **Time Range Selector** | 5m/15m/60m historical view           |
| **Alert Callouts**      | Threshold breach warnings            |
| **AI Models Panel**     | RT-DETRv2 vs Nemotron separate stats |
| **Databases Panel**     | PostgreSQL + Redis metrics           |
| **Host System Panel**   | CPU, RAM, Disk usage                 |
| **Containers Panel**    | Health timeline with Tracker         |

## Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         BACKEND                                  │
├─────────────────────────────────────────────────────────────────┤
│  ┌─ PerformanceCollector (new service) ───────────────────────┐ │
│  │                                                             │ │
│  │  Sources (checked every 5s):                                │ │
│  │                                                             │ │
│  │  1. Prometheus (if available)                               │ │
│  │     └─ Query: hsi_gpu_*, hsi_stage_duration_*, etc.        │ │
│  │                                                             │ │
│  │  2. Direct fallback (if Prometheus unavailable):            │ │
│  │     ├─ nvidia-smi via pynvml (host GPU stats)              │ │
│  │     ├─ RT-DETRv2 /health (VRAM, status)                    │ │
│  │     ├─ Nemotron /slots (context, processing)               │ │
│  │     ├─ psutil (CPU, RAM, disk, network)                    │ │
│  │     └─ PipelineLatencyTracker (inference stats)            │ │
│  │                                                             │ │
│  │  3. Container health (always direct):                       │ │
│  │     └─ Health endpoint pings                               │ │
│  │                                                             │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                           │                                      │
│                           ▼                                      │
│  ┌─ SystemBroadcaster (existing) ─────────────────────────────┐ │
│  │  WebSocket /ws/system channel                               │ │
│  │  New message type: "performance_update"                     │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Data Sources

| Source                        | Metrics                                       | Priority      |
| ----------------------------- | --------------------------------------------- | ------------- |
| Prometheus                    | All metrics when monitoring profile active    | 1 (preferred) |
| pynvml                        | GPU utilization, VRAM, temperature, power     | 2 (fallback)  |
| RT-DETRv2 `/health`           | VRAM usage, model status, device              | 2             |
| Nemotron `/slots`             | Active slots, context size, processing status | 2             |
| PostgreSQL `pg_stat_database` | Connections, cache hit ratio, transactions    | 2             |
| Redis `INFO`                  | Clients, memory, hit ratio                    | 2             |
| psutil                        | CPU, RAM, disk usage                          | 2             |
| Container health endpoints    | Status for all 6 containers                   | Always direct |

## UI Layout

### Enhanced Page Structure

```
┌─────────────────────────────────────────────────────────────────────┐
│  SYSTEM MONITORING                      [5m] [15m] [60m]  [Live ●]  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─ ALERTS (conditional - only shows when thresholds breached) ───┐ │
│  │  ⚠️  GPU temperature high: 82°C (threshold: 80°C)              │ │
│  │  🔴 Redis keyspace hit ratio critical: 0.01% (threshold: 50%)  │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌─ ROW 1: Overview + Workers (EXISTING - KEEP AS-IS) ────────────┐ │
│  │                                                                 │ │
│  │  ┌─ System Overview ─────┐  ┌─ Background Workers ───────────┐ │ │
│  │  │  Uptime: 5d 12h 30m   │  │  8/8 Running                   │ │ │
│  │  │  Cameras: 4           │  │  ● detection_worker [Critical] │ │ │
│  │  │  Events: 1,234        │  │  ● analysis_worker [Critical]  │ │ │
│  │  │  Detections: 45,678   │  │  ● file_watcher ...            │ │ │
│  │  └───────────────────────┘  └─────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌─ ROW 2: GPU Overview (ENHANCED) ───────────────────────────────┐ │
│  │  RTX A5500 (cuda:0) │ 38% util │ 22.7/24 GB │ 38°C │ 31W       │ │
│  │                                                                 │ │
│  │  ┌─ Utilization ──────────┐  ┌─ VRAM Usage ───────────┐        │ │
│  │  │ [AreaChart 5m/15m/60m] │  │ [AreaChart 5m/15m/60m] │        │ │
│  │  └────────────────────────┘  └────────────────────────┘        │ │
│  │  ┌─ Temperature ──────────┐  ┌─ Power ────────────────┐        │ │
│  │  │ [AreaChart 5m/15m/60m] │  │ [AreaChart 5m/15m/60m] │        │ │
│  │  └────────────────────────┘  └────────────────────────┘        │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌─ ROW 3: AI Models (NEW) ───────────────────────────────────────┐ │
│  │                                                                 │ │
│  │  ┌─ RT-DETRv2 (Detection) ───┐  ┌─ Nemotron (LLM) ───────────┐ │ │
│  │  │  ● Healthy                │  │  ● Healthy                 │ │ │
│  │  │  VRAM: 0.17 GB            │  │  Slots: 0/2 active         │ │ │
│  │  │  Model: rtdetr_r50vd      │  │  Context: 4096 tokens      │ │ │
│  │  │  Device: cuda:0           │  │  Model: Nemotron-3-Nano    │ │ │
│  │  │  [DonutChart: VRAM]       │  │                            │ │ │
│  │  └───────────────────────────┘  └────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌─ ROW 4: Inference Statistics (ENHANCED from Pipeline Latency) ─┐ │
│  │                                                                 │ │
│  │  RT-DETRv2: 45ms avg, 82ms P95    Nemotron: 2.1s avg, 4.8s P95 │ │
│  │  Pipeline E2E: 3.2s avg           Throughput: 12.4 img/min     │ │
│  │  Queue: Detection 0 │ Analysis 0                                │ │
│  │                                                                 │ │
│  │  ┌─ RT-DETRv2 Latency ────┐  ┌─ Nemotron Latency ─────┐        │ │
│  │  │ [AreaChart with P95]   │  │ [AreaChart with P95]   │        │ │
│  │  └────────────────────────┘  └────────────────────────┘        │ │
│  │  ┌─ Pipeline Throughput ──────────────────────────────┐        │ │
│  │  │ [AreaChart: images/min, events/min]                │        │ │
│  │  └────────────────────────────────────────────────────┘        │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌─ ROW 5: Databases (NEW) ───────────────────────────────────────┐ │
│  │                                                                 │ │
│  │  ┌─ PostgreSQL ──────────────┐  ┌─ Redis ────────────────────┐ │ │
│  │  │  ● Healthy                │  │  ● Healthy                 │ │ │
│  │  │  Connections: 5/30 pool   │  │  Clients: 8                │ │ │
│  │  │  Cache hit: 98.2%         │  │  Memory: 1.44 MB           │ │ │
│  │  │  Txns: 1.2k/min           │  │  Hit ratio: 0.01%          │ │ │
│  │  │  [AreaChart: Connections] │  │  [AreaChart: Memory]       │ │ │
│  │  └───────────────────────────┘  └────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌─ ROW 6: Host System (NEW) ─────────────────────────────────────┐ │
│  │                                                                 │ │
│  │  CPU: 12%  │  RAM: 8.2/32 GB (26%)  │  Disk: 156/500 GB (31%)  │ │
│  │                                                                 │ │
│  │  ┌─ CPU Usage ────────────┐  ┌─ RAM Usage ────────────┐        │ │
│  │  │ [AreaChart]            │  │ [AreaChart]            │        │ │
│  │  └────────────────────────┘  └────────────────────────┘        │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌─ ROW 7: Containers (NEW - replaces Service Health) ────────────┐ │
│  │                                                                 │ │
│  │  6/6 Healthy                                                    │ │
│  │                                                                 │ │
│  │  ┌─ backend ─────┐ ┌─ frontend ───┐ ┌─ postgres ───┐           │ │
│  │  │ [Tracker]     │ │ [Tracker]    │ │ [Tracker]    │           │ │
│  │  └───────────────┘ └──────────────┘ └──────────────┘           │ │
│  │  ┌─ redis ───────┐ ┌─ ai-detector ┐ ┌─ ai-llm ─────┐           │ │
│  │  │ [Tracker]     │ │ [Tracker]    │ │ [Tracker]    │           │ │
│  │  └───────────────┘ └──────────────┘ └──────────────┘           │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### Time Range Selector

| Range | Resolution | Data Points |
| ----- | ---------- | ----------- |
| 5m    | 5 seconds  | 60 points   |
| 15m   | 15 seconds | 60 points   |
| 60m   | 1 minute   | 60 points   |

### Tremor Components Used

| Section         | Components                               |
| --------------- | ---------------------------------------- |
| Alerts          | `Callout` (yellow=warning, red=critical) |
| System Overview | `Card`, `Metric` (existing)              |
| Workers         | `Card`, `Badge` (existing)               |
| GPU Overview    | `AreaChart`, `ProgressBar`, `Metric`     |
| AI Models       | `Card`, `Badge`, `DonutChart`            |
| Inference Stats | `AreaChart`, `Metric`                    |
| Databases       | `Card`, `AreaChart`, `ProgressBar`       |
| Host System     | `AreaChart`, `ProgressBar`               |
| Containers      | `Tracker`, `Badge`                       |

## Alert Thresholds

| Metric                 | Warning (⚠️)         | Critical (🔴)        |
| ---------------------- | -------------------- | -------------------- |
| GPU Utilization        | > 90% sustained 2min | > 98% sustained 5min |
| GPU Temperature        | > 75°C               | > 85°C               |
| GPU VRAM               | > 90%                | > 95%                |
| GPU Power              | > 300W               | > 350W               |
| RT-DETRv2 Latency P95  | > 200ms              | > 500ms              |
| Nemotron Latency P95   | > 10s                | > 30s                |
| PostgreSQL Connections | > 80% pool           | > 95% pool           |
| PostgreSQL Cache Hit   | < 90%                | < 80%                |
| Redis Memory           | > 100MB              | > 500MB              |
| Redis Hit Ratio        | < 50%                | < 10%                |
| Host CPU               | > 80% sustained      | > 95% sustained      |
| Host RAM               | > 85%                | > 95%                |
| Host Disk              | > 80%                | > 90%                |
| Container Health       | 1 unhealthy          | 2+ unhealthy         |

## WebSocket Message Format

```json
{
  "type": "performance_update",
  "timestamp": "2025-01-01T12:00:00Z",
  "gpu": {
    "name": "NVIDIA RTX A5500",
    "utilization": 38,
    "vram_used_gb": 22.7,
    "vram_total_gb": 24.0,
    "temperature": 38,
    "power_watts": 31
  },
  "ai_models": {
    "rtdetr": {
      "status": "healthy",
      "vram_gb": 0.17,
      "model": "rtdetr_r50vd_coco_o365",
      "device": "cuda:0"
    },
    "nemotron": {
      "status": "healthy",
      "slots_active": 0,
      "slots_total": 2,
      "context_size": 4096
    }
  },
  "inference": {
    "rtdetr_latency_ms": { "avg": 45, "p95": 82, "p99": 120 },
    "nemotron_latency_ms": { "avg": 2100, "p95": 4800, "p99": 8200 },
    "pipeline_latency_ms": { "avg": 3200, "p95": 6100 },
    "throughput": { "images_per_min": 12.4, "events_per_min": 2.1 },
    "queues": { "detection": 0, "analysis": 0 }
  },
  "databases": {
    "postgresql": {
      "status": "healthy",
      "connections_active": 5,
      "connections_max": 30,
      "cache_hit_ratio": 98.2,
      "transactions_per_min": 1200
    },
    "redis": {
      "status": "healthy",
      "connected_clients": 8,
      "memory_mb": 1.44,
      "hit_ratio": 0.01,
      "blocked_clients": 2
    }
  },
  "host": {
    "cpu_percent": 12,
    "ram_used_gb": 8.2,
    "ram_total_gb": 32,
    "disk_used_gb": 156,
    "disk_total_gb": 500
  },
  "containers": [
    { "name": "backend", "status": "running", "health": "healthy" },
    { "name": "frontend", "status": "running", "health": "healthy" },
    { "name": "postgres", "status": "running", "health": "healthy" },
    { "name": "redis", "status": "running", "health": "healthy" },
    { "name": "ai-detector", "status": "running", "health": "healthy" },
    { "name": "ai-llm", "status": "running", "health": "healthy" }
  ],
  "alerts": [
    {
      "severity": "warning",
      "metric": "gpu_temperature",
      "value": 82,
      "threshold": 80,
      "message": "GPU temperature high: 82°C"
    }
  ]
}
```

## File Changes

### New Files to Create

```
backend/
  services/
    performance_collector.py     # Metrics aggregation service
  api/
    schemas/
      performance.py             # Pydantic models for performance data

frontend/
  src/
    components/
      system/
        PerformanceAlerts.tsx    # Alert callouts (NEW)
        AiModelsPanel.tsx        # RT-DETRv2 + Nemotron (NEW)
        DatabasesPanel.tsx       # PostgreSQL + Redis (NEW)
        HostSystemPanel.tsx      # CPU, RAM, Disk (NEW)
        ContainersPanel.tsx      # Container health with Tracker (NEW)
        TimeRangeSelector.tsx    # 5m/15m/60m toggle (NEW)
    hooks/
      usePerformanceMetrics.ts   # WebSocket subscription (NEW)
```

### Existing Files to Modify

| File                                                      | Change                                     |
| --------------------------------------------------------- | ------------------------------------------ |
| `backend/main.py`                                         | Initialize PerformanceCollector on startup |
| `backend/services/system_broadcaster.py`                  | Add `broadcast_performance()` method       |
| `backend/requirements.txt`                                | Add `psutil`                               |
| `frontend/src/components/system/SystemMonitoringPage.tsx` | Add new sections, time range, alerts       |
| `frontend/src/components/system/index.ts`                 | Export new components                      |
| `frontend/src/components/dashboard/GpuStats.tsx`          | Add time range prop support                |

### Files to Remove

| File                                                         | Reason                                              |
| ------------------------------------------------------------ | --------------------------------------------------- |
| `frontend/src/components/system/ObservabilityPanel.tsx`      | Redundant - functionality merged into enhanced page |
| `frontend/src/components/system/ObservabilityPanel.test.tsx` | Associated test file                                |

## Dependencies

### Backend

- `psutil` - Host system metrics (CPU, RAM, disk)

### Frontend

- None new (Tremor v3.17.4 already installed)

## Implementation Notes

1. **Keep existing functionality** - System Overview and WorkerStatusPanel stay as-is
2. **Merge PipelineQueues** - Queue depths move into Inference Stats section
3. **Merge Service Health** - Service status moves into Containers panel with Tracker
4. **Enhance GpuStats** - Add time range support, nvidia-smi source
5. **Prometheus fallback** - Check availability on startup, cache result, retry periodically
6. **History buffers** - Frontend maintains circular buffers for each time range (60 points each)
7. **Alert computation** - Backend computes alerts server-side, included in WebSocket message
8. **Container health** - Direct HTTP pings to container health endpoints

## Testing Strategy

- Unit tests for each new panel component
- Unit tests for `usePerformanceMetrics` hook
- Unit tests for `PerformanceCollector` service
- Update existing `SystemMonitoringPage.test.tsx` for new sections
- Integration test for WebSocket message flow
- E2E test for page load and data display

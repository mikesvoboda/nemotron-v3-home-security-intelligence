# System Performance Dashboard Design

> Comprehensive in-app system monitoring with GPU, AI models, inference stats, databases, host metrics, and container health.

**Created:** 2025-12-31
**Status:** Approved

## Overview

Add a System Performance tab (`/system`) to the React dashboard providing full observability without requiring external tools like Grafana. Metrics are pushed via WebSocket every 5 seconds with historical charts for 5min/15min/60min windows.

### Goals

1. **Debugging AI performance** - See which model consumes resources when inference is slow
2. **Capacity planning** - Monitor VRAM limits before adding more cameras
3. **General observability** - Comprehensive system health at a glance

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

### Page Structure

```
┌─────────────────────────────────────────────────────────────────────┐
│  SYSTEM PERFORMANCE                     [5m] [15m] [60m]  [Live ●]  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─ ALERTS (conditional) ─────────────────────────────────────────┐ │
│  │  ⚠️  GPU temperature high: 82°C (threshold: 80°C)              │ │
│  │  🔴 Redis keyspace hit ratio critical: 0.01% (threshold: 50%)  │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌─ GPU OVERVIEW ─────────────────────────────────────────────────┐ │
│  │  RTX A5500 │ 38% util │ 22.7/24 GB │ 38°C │ 31W                │ │
│  │  [AreaChart: Utilization]  [AreaChart: VRAM]                   │ │
│  │  [AreaChart: Temperature]  [AreaChart: Power]                  │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌─ AI MODELS ──────────────────────────────┬─────────────────────┐ │
│  │  RT-DETRv2 (Detection)                   │  Nemotron (LLM)     │ │
│  │  ● Healthy  │  VRAM: 0.17 GB             │  ● Healthy          │ │
│  │  Model: rtdetr_r50vd                     │  Slots: 0/2 active  │ │
│  │  [DonutChart: VRAM breakdown]            │  Context: 4096 tok  │ │
│  └──────────────────────────────────────────┴─────────────────────┘ │
│                                                                     │
│  ┌─ INFERENCE STATISTICS ─────────────────────────────────────────┐ │
│  │  RT-DETRv2: 45ms avg, 82ms P95    Nemotron: 2.1s avg, 4.8s P95 │ │
│  │  [AreaChart: RT-DETRv2 Latency]  [AreaChart: Nemotron Latency] │ │
│  │  [AreaChart: Pipeline Throughput]                              │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌─ DATABASES ────────────────────────────┬───────────────────────┐ │
│  │  PostgreSQL                            │  Redis                │ │
│  │  ● Healthy                             │  ● Healthy            │ │
│  │  Connections: 5/30 pool                │  Clients: 8           │ │
│  │  Cache hit: 98.2%                      │  Memory: 1.44 MB      │ │
│  │  [AreaChart: Connections]              │  [AreaChart: Memory]  │ │
│  └────────────────────────────────────────┴───────────────────────┘ │
│                                                                     │
│  ┌─ HOST SYSTEM ──────────────────────────────────────────────────┐ │
│  │  CPU: 12%  │  RAM: 8.2/32 GB  │  Disk: 156/500 GB              │ │
│  │  [AreaChart: CPU]  [AreaChart: RAM]                            │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌─ CONTAINERS (6) ───────────────────────────────────────────────┐ │
│  │  ● backend  ● frontend  ● postgres  ● redis  ● ai-detector     │ │
│  │  ● ai-llm                                                      │ │
│  │  [Tracker: Health timeline for each container]                 │ │
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

| Section     | Components                               |
| ----------- | ---------------------------------------- |
| GPU metrics | `AreaChart`, `ProgressBar`, `Metric`     |
| AI Models   | `Card`, `Badge`, `DonutChart`            |
| Inference   | `AreaChart`, `Metric`                    |
| Databases   | `AreaChart`, `ProgressBar`               |
| Host System | `AreaChart`, `ProgressBar`               |
| Containers  | `Tracker`, `Badge`                       |
| Alerts      | `Callout` (yellow=warning, red=critical) |

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
    "throughput": { "images_per_min": 12.4, "events_per_min": 2.1 }
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

## File Structure

### New Files

```
backend/
  services/
    performance_collector.py     # Metrics aggregation service
  api/
    schemas/
      performance.py             # Pydantic models

frontend/
  src/
    pages/
      SystemPerformancePage.tsx  # Main page (route component)
    components/
      system/
        PerformanceAlerts.tsx    # Alert callouts
        GpuOverviewPanel.tsx     # GPU metrics + charts
        AiModelsPanel.tsx        # RT-DETRv2 + Nemotron
        InferenceStatsPanel.tsx  # Latency + throughput
        DatabasesPanel.tsx       # PostgreSQL + Redis
        HostSystemPanel.tsx      # CPU, RAM, Disk
        ContainersPanel.tsx      # Container health tracker
    hooks/
      usePerformanceMetrics.ts   # WebSocket subscription

docs/
  plans/
    2025-12-31-system-performance-design.md  # This document
```

### Files to Modify

| File                                         | Change                                     |
| -------------------------------------------- | ------------------------------------------ |
| `backend/main.py`                            | Initialize PerformanceCollector on startup |
| `backend/services/system_broadcaster.py`     | Add `broadcast_performance()` method       |
| `backend/requirements.txt`                   | Add `psutil`                               |
| `frontend/src/App.tsx`                       | Add `/system` route                        |
| `frontend/src/components/layout/Sidebar.tsx` | Add nav link                               |

## Dependencies

### Backend

- `psutil` - Host system metrics (CPU, RAM, disk)

### Frontend

- None new (Tremor v3.17.4 already installed)

## Implementation Notes

1. **Prometheus fallback**: Check Prometheus availability on startup, cache result, retry periodically
2. **History buffers**: Frontend maintains circular buffers for each time range (60 points each)
3. **Alert computation**: Backend computes alerts server-side, included in WebSocket message
4. **Container health**: Direct HTTP pings to container health endpoints (not via Prometheus)
5. **Existing integration**: Reuse `SystemBroadcaster` for WebSocket delivery, add new message type

## Testing Strategy

- Unit tests for each panel component
- Unit tests for `usePerformanceMetrics` hook
- Unit tests for `PerformanceCollector` service
- Integration test for WebSocket message flow
- E2E test for page load and data display

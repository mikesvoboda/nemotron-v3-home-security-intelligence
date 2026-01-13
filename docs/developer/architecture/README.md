# Architecture Documentation

> System design, technology decisions, and component interactions for Home Security Intelligence.

---

## Overview

| Document                                                | Description                             |
| ------------------------------------------------------- | --------------------------------------- |
| [Architecture Overview](../../architecture/overview.md) | High-level system design and data flow  |
| [Data Model](../../architecture/data-model.md)          | PostgreSQL schemas and Redis structures |
| [AI Pipeline](../../architecture/ai-pipeline.md)        | Detection to analysis flow              |
| [Real-time System](../../architecture/real-time.md)     | WebSocket and pub/sub architecture      |
| [Design Decisions](../../architecture/decisions.md)     | ADRs - why we made key choices          |
| [Resilience](../../architecture/resilience.md)          | Error handling and graceful degradation |
| [Frontend Hooks](../../architecture/frontend-hooks.md)  | Custom React hook architecture          |

---

## System Diagram

```
Cameras -> FTP -> FileWatcher -> detection_queue -> RT-DETRv2 -> Detections
                                                          |
Dashboard <- WebSocket <- Events <- Nemotron <- analysis_queue <- BatchAggregator
```

---

## Technology Stack

| Layer       | Technology         | Purpose                              |
| ----------- | ------------------ | ------------------------------------ |
| Frontend    | React + TypeScript | Dashboard UI                         |
| Frontend    | Tailwind + Tremor  | Styling and data visualization       |
| Backend     | FastAPI + Python   | REST API and WebSocket server        |
| Database    | PostgreSQL         | Persistent storage                   |
| Cache/Queue | Redis              | Pub/sub and job queues               |
| Detection   | RT-DETRv2          | Object detection (30-50ms inference) |
| Analysis    | Nemotron           | Risk reasoning via llama.cpp         |

---

## Component Layers

### Backend Services

| Service          | Location                                | Responsibility                |
| ---------------- | --------------------------------------- | ----------------------------- |
| FileWatcher      | `backend/services/file_watcher.py`      | Monitor camera directories    |
| DetectorClient   | `backend/services/detector_client.py`   | RT-DETRv2 HTTP client         |
| BatchAggregator  | `backend/services/batch_aggregator.py`  | Group detections into batches |
| NemotronAnalyzer | `backend/services/nemotron_analyzer.py` | LLM risk analysis             |
| EventBroadcaster | `backend/services/event_broadcaster.py` | WebSocket distribution        |

### Frontend Hooks

| Hook            | Location                                | Purpose                   |
| --------------- | --------------------------------------- | ------------------------- |
| useWebSocket    | `frontend/src/hooks/useWebSocket.ts`    | Core WebSocket management |
| useEventStream  | `frontend/src/hooks/useEventStream.ts`  | Real-time security events |
| useSystemStatus | `frontend/src/hooks/useSystemStatus.ts` | System health broadcasts  |

---

## Deep Dive Documents

For detailed implementation specifics, see:

- [Detection Service](../detection-service.md) - RT-DETRv2 integration
- [Batching Logic](../batching-logic.md) - Time-windowed aggregation
- [Risk Analysis](../risk-analysis.md) - Nemotron prompts
- [Resilience Patterns](../resilience-patterns.md) - Circuit breakers

---

[Back to Developer Hub](../README.md) | [Back to Documentation Index](../../README.md)

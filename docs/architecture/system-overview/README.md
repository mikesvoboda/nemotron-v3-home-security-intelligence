# System Overview Hub

This hub provides high-level architecture understanding of the Home Security Intelligence system.

## Component Architecture

![Three-Tier Architecture](../../images/architecture/system-overview/concept-three-tier.png)

### Backend Layer Organization

![Backend Layered Architecture](../../images/architecture/backend-layered-architecture.png)

```mermaid
flowchart TB
    subgraph Frontend["Frontend Layer"]
        FE["React + TypeScript<br/>Vite + Tailwind + Tremor<br/>dev :8444 HTTPS / prod :8080 :8444"]
    end

    subgraph Backend["Backend Layer"]
        BE["FastAPI<br/>Python 3.14+<br/>:8000"]
        WS["WebSocket<br/>/ws/events, /ws/system"]
    end

    subgraph AI["AI Services Layer"]
        GW["ai-gateway :8090<br/>YOLO26 · re-ID<br/>(via Triton)"]
        VLM["ai-vlm :8098<br/>Qwen3VL-8B<br/>llama.cpp llama-server"]
    end

    subgraph Data["Data Layer"]
        PG[(PostgreSQL<br/>:5432)]
        RD[(Redis<br/>:6379)]
        FS[("/export/foscam/<br/>Camera Storage")]
    end

    FE <-->|REST API| BE
    FE <-->|WebSocket| WS
    BE --> GW
    BE --> VLM
    BE <--> PG
    BE <--> RD
    BE --> FS
```

## Service Inventory

![Service Dependency Graph](../../images/architecture/service-dependencies.png)

| Service          | Port                        | Container      | Source                         | Description                                                        |
| ---------------- | --------------------------- | -------------- | ------------------------------ | ------------------------------------------------------------------ |
| **Frontend**     | host 8444 HTTPS / 8080 HTTP | `frontend`     | `frontend/`                    | React dashboard with real-time updates                             |
| **Backend**      | 8000                        | `backend`      | `backend/main.py:1449`         | FastAPI server with WebSocket support                              |
| **PostgreSQL**   | 5432                        | `postgres`     | `docker-compose.prod.yml:44`   | Primary database for events, detections                            |
| **Redis**        | 6379                        | `redis`        | `docker-compose.prod.yml:671`  | Queues, pub/sub, batch state                                       |
| **ai-gateway**   | 8090 (+8002 metrics)        | `ai-gateway`   | `docker-compose.prod.yml:347`  | Triton serving `{yolo26, reid}`; mounts `/yolo26` and `/enrich-lt` |
| **ai-vlm**       | 8098                        | `ai-vlm`       | `docker-compose.prod.yml:134`  | llama.cpp `llama-server` serving Qwen3VL-8B; default compose set   |
| **Prometheus**   | 9090                        | `prometheus`   | `docker-compose.prod.yml:1002` | Metrics collection                                                 |
| **Grafana**      | host 3002 (container 3000)  | `grafana`      | `docker-compose.prod.yml:1049` | Monitoring dashboards at `/grafana/` via proxy                     |
| **Tempo**        | 3200                        | `tempo`        | `docker-compose.prod.yml:973`  | Distributed trace storage                                          |
| **Alertmanager** | 9093                        | `alertmanager` | `docker-compose.prod.yml:1178` | Alert routing                                                      |

There are exactly two AI services: `ai-gateway` and `ai-vlm`. ai-vlm is the only LLM service.

## Technology Stack

```mermaid
flowchart TB
    subgraph Stack["Technology Stack"]
        direction TB

        subgraph FE["Frontend"]
            React["React 19"]
            TS["TypeScript 6.0"]
            Tailwind["Tailwind CSS 3.4"]
            Tremor["Tremor 3.18"]
            Vite["Vite 7.3"]
        end

        subgraph BE["Backend"]
            Python["Python 3.14"]
            FastAPI["FastAPI ≥0.115"]
            SQLAlchemy["SQLAlchemy 2.0"]
            Pydantic["Pydantic 2.0"]
        end

        subgraph DB["Database"]
            PG["PostgreSQL 16"]
            Redis["Redis 7.4"]
        end

        subgraph ML["AI/ML"]
            PyTorch["PyTorch 2.x"]
            Triton["Triton (ai-gateway)"]
            YOLO26["YOLO26 (TensorRT)"]
            VLM["Qwen3VL-8B-Instruct<br/>Q4_K_M + mmproj"]
            LlamaCpp["llama.cpp llama-server (ai-vlm)"]
            ONNX["onnxruntime lookups<br/>face · re-ID · ALPR"]
        end

        subgraph Infra["Infrastructure"]
            Docker["Docker/Podman"]
            NVIDIA["NVIDIA Container Toolkit"]
            Prom["Prometheus"]
            Graf["Grafana"]
        end
    end
```

## Quick Links

| Document                                      | Description                                         |
| --------------------------------------------- | --------------------------------------------------- |
| [Design Decisions](design-decisions.md)       | ADR-format architectural decisions with rationale   |
| [Deployment Topology](deployment-topology.md) | Container architecture, GPU passthrough, networking |
| [Configuration](configuration.md)             | Settings architecture, environment variables        |

## Data Flow Summary

1. **Image Capture**: Foscam cameras FTP upload images to `/export/foscam/{camera}/`
2. **Detection**: FileWatcher queues images onto `detections:stream`, YOLO26 performs object detection
3. **Batching**: BatchAggregator groups detections (90s window, 30s idle timeout), closing a batch
   publishes it to `analysis:stream`
4. **Analysis**: `VlmAnalyzer.analyze_batch` selects 1-4 key frames, gathers the three in-process
   lookup legs (faces, plates, person re-ID), and asks ai-vlm for a verdict; the verdict becomes the
   event's `risk_score` / `risk_level` / `summary` / `reasoning` plus an `event_verifications` row
5. **Broadcast**: `VlmAnalyzer._broadcast` publishes on the single `security_events` Redis channel;
   each backend's broadcaster fans that out to its WebSocket clients
   (`backend/services/vlm_analyzer.py:765-773`, `backend/services/event_broadcaster.py:346`)
6. **Display**: React dashboard updates in real-time

## Script Dependencies

![Script Dependency Graph showing relationships between build, test, and deployment scripts](../../images/architecture/script-dependency-graph.png)

The project includes various scripts for development, testing, and deployment. This dependency graph illustrates how scripts relate to each other and their execution order.

## Related Documentation

| Document                                          | Purpose                             |
| ------------------------------------------------- | ----------------------------------- |
| `/docs/architecture/overview.md`                  | Comprehensive architecture overview |
| `/docs/architecture/decisions.md`                 | Full ADR collection                 |
| `/docs/architecture/ai-pipeline-current-state.md` | AI processing pipeline as it runs   |
| `/docs/architecture/real-time.md`                 | WebSocket and pub/sub patterns      |
| `/AGENTS.md`                                      | Project navigation guide            |

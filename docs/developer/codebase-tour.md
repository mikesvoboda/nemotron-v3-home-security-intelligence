# Codebase Tour

> Navigate the project structure and understand where things live.

**Time to read:** ~8 min
**Prerequisites:** [Local Setup](local-setup.md)

---

## Directory Overview

```
/
├── backend/              # Python FastAPI backend
│   ├── api/              # REST + WebSocket endpoints
│   │   ├── routes/       # FastAPI route handlers
│   │   └── schemas/      # Pydantic request/response models
│   ├── core/             # Infrastructure (database, Redis, config)
│   ├── models/           # SQLAlchemy ORM models
│   ├── services/         # Business logic (AI pipeline)
│   └── tests/            # Unit and integration tests
│
├── frontend/             # React TypeScript dashboard
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── hooks/        # Custom hooks (WebSocket, API)
│   │   ├── services/     # API client
│   │   └── types/        # TypeScript type definitions
│   └── tests/            # Component and E2E tests
│
├── ai/                   # AI model integration
│   ├── rtdetr/           # RT-DETRv2 detection server
│   └── nemotron/         # Nemotron LLM configuration
│
├── docs/                 # Documentation
│   ├── architecture/     # System design docs
│   ├── development/      # Dev guides
│   ├── api-reference/    # API documentation
│   └── plans/            # Design documents
│
├── scripts/              # Development and deployment scripts
├── monitoring/           # Prometheus + Grafana configuration
└── .github/              # CI/CD workflows
```

---

## Backend Structure

### Entry Point

```
backend/main.py           # FastAPI app, lifespan management, middleware
```

The app starts here. Key responsibilities:

- Creates FastAPI application
- Mounts API routers
- Initializes database and Redis connections
- Starts background workers (FileWatcher, BatchAggregator, etc.)

### Core Infrastructure

```
backend/core/
├── config.py             # Settings from environment variables
├── database.py           # PostgreSQL async session management
├── redis.py              # Redis client with queues and pub/sub
├── logging.py            # Structured logging configuration
└── metrics.py            # Prometheus metrics
```

**Key file:** `config.py` - All environment variables are defined here as Pydantic Settings.

### API Layer

```
backend/api/
├── routes/
│   ├── cameras.py        # GET/POST/PATCH/DELETE /api/cameras
│   ├── events.py         # GET /api/events, PATCH /api/events/{id}
│   ├── detections.py     # GET /api/detections
│   ├── system.py         # GET /api/system/health, /api/system/gpu
│   ├── media.py          # GET /api/media/thumbnails/{file}
│   ├── logs.py           # GET /api/logs
│   └── websocket.py      # /ws/events, /ws/system
│
└── schemas/
    ├── cameras.py        # CameraCreate, CameraResponse
    ├── events.py         # EventResponse, EventFilter
    ├── detections.py     # DetectionResponse
    └── system.py         # HealthResponse, GPUStats
```

Routes handle HTTP/WebSocket requests. Schemas define request/response shapes.

### Data Models

```
backend/models/
├── camera.py             # Camera table
├── detection.py          # Detection table
├── event.py              # Event table
├── gpu_stats.py          # GPUStats table
├── log.py                # Log table
└── api_key.py            # APIKey table
```

SQLAlchemy ORM models. Each file defines one table.

### Services (AI Pipeline)

```
backend/services/
├── file_watcher.py       # Monitor camera directories for new images
├── dedupe.py             # Prevent duplicate processing
├── detector_client.py    # HTTP client for RT-DETRv2
├── batch_aggregator.py   # Group detections into batches
├── nemotron_analyzer.py  # LLM risk analysis
├── thumbnail_generator.py # Create detection thumbnails
├── event_broadcaster.py  # WebSocket event distribution
├── system_broadcaster.py # System status updates
├── gpu_monitor.py        # NVIDIA GPU metrics
├── cleanup_service.py    # Data retention enforcement
├── health_monitor.py     # Service health checks
├── retry_handler.py      # Exponential backoff, dead-letter queues
├── pipeline_workers.py   # Background worker management
└── prompts.py            # LLM prompt templates
```

Services contain business logic. The AI pipeline flows through these in order:

1. `file_watcher.py` - Detects new images
2. `detector_client.py` - Runs RT-DETRv2 detection
3. `batch_aggregator.py` - Groups detections
4. `nemotron_analyzer.py` - LLM analysis
5. `event_broadcaster.py` - Sends to dashboard

---

## Frontend Structure

### Entry Point

```
frontend/src/
├── App.tsx               # Root component, routing
├── main.tsx              # React DOM render
└── index.css             # Global styles, Tailwind
```

### Components

```
frontend/src/components/
├── dashboard/            # Main dashboard view
│   ├── DashboardPage.tsx # Dashboard container
│   ├── RiskGauge.tsx     # Current risk level display
│   ├── CameraGrid.tsx    # Camera status grid
│   └── ActivityFeed.tsx  # Recent events feed
│
├── events/               # Event views
│   ├── EventTimeline.tsx # Event list with filtering
│   └── EventDetailModal.tsx
│
├── settings/             # Settings pages
│   ├── SettingsPage.tsx
│   ├── CameraSettings.tsx
│   └── AISettings.tsx
│
├── logs/                 # Logs dashboard
│   └── LogsDashboard.tsx
│
├── layout/               # App layout
│   ├── Header.tsx
│   ├── Sidebar.tsx
│   └── Layout.tsx
│
└── common/               # Shared components
    ├── StatusBadge.tsx
    └── LoadingSpinner.tsx
```

### Hooks

```
frontend/src/hooks/
├── useWebSocket.ts       # Base WebSocket connection
├── useWebSocketStatus.ts # Channel status tracking
├── useEventStream.ts     # Security event stream (/ws/events)
├── useSystemStatus.ts    # System health (/ws/system)
├── useConnectionStatus.ts # Multi-channel manager
├── useGpuHistory.ts      # GPU metrics polling
├── useHealthStatus.ts    # Health endpoint polling
└── useStorageStats.ts    # Storage statistics
```

Hooks abstract WebSocket connections and REST polling.

### Services

```
frontend/src/services/
├── api.ts                # REST API client (axios-based)
└── logger.ts             # Frontend logging
```

---

## AI Services

```
ai/
├── rtdetr/
│   ├── model.py          # FastAPI server for RT-DETRv2
│   ├── Dockerfile        # Container build
│   └── requirements.txt  # PyTorch, transformers
│
└── nemotron/
    ├── config.json       # llama.cpp configuration
    └── Dockerfile        # Container with llama.cpp
```

RT-DETRv2 detects objects. Nemotron analyzes risk.

---

## Key Patterns

### Finding Code for a Feature

1. **API endpoint** - Look in `backend/api/routes/`
2. **Database model** - Look in `backend/models/`
3. **Business logic** - Look in `backend/services/`
4. **Frontend component** - Look in `frontend/src/components/`
5. **Custom hook** - Look in `frontend/src/hooks/`

### AGENTS.md Files

Every directory has an `AGENTS.md` explaining its purpose:

```bash
# Find all AGENTS.md files
find . -name "AGENTS.md" -type f

# Read a specific one
cat backend/services/AGENTS.md
```

### Understanding Data Flow

For any feature, trace the flow:

```
User Action → Frontend Component → API Call → Backend Route
    → Service Logic → Database/Redis → Response
        → Frontend State Update → UI Render
```

---

## Important Files to Know

| File                                    | What It Does              |
| --------------------------------------- | ------------------------- |
| `backend/core/config.py`                | All environment variables |
| `backend/main.py`                       | Application startup       |
| `backend/services/batch_aggregator.py`  | Core batching logic       |
| `backend/services/nemotron_analyzer.py` | LLM integration           |
| `frontend/src/hooks/useEventStream.ts`  | Real-time events          |
| `frontend/src/services/api.ts`          | API client                |
| `docker-compose.prod.yml`               | Container orchestration   |
| `.pre-commit-config.yaml`               | Code quality hooks        |

---

## Next Steps

- [Testing Guide](../development/testing.md) - Write tests for your changes
- [AI Pipeline](../architecture/ai-pipeline.md) - Deep dive into detection flow
- [Real-time System](../architecture/real-time.md) - WebSocket architecture

---

[Back to Developer Hub](../developer-hub.md)

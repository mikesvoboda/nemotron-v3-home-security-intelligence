# Home Security Intelligence MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an AI-powered home security monitoring dashboard that processes camera uploads through RT-DETRv2 for object detection and Nemotron for contextual risk assessment.

**Architecture:** File watcher monitors FTP uploads, RT-DETRv2 detects objects, batches aggregate in Redis, Nemotron analyzes risk, results display in React dashboard via WebSocket.

**Tech Stack:** React/TypeScript + Tailwind/Tremor (frontend), FastAPI + SQLite + Redis (backend), RT-DETRv2 + Nemotron/llama.cpp (AI), Docker Compose (deployment)

---

## Issue Tracking

All tasks are tracked in `bd` (beads). Use these commands:

```bash
bd ready                    # Find available work
bd show <id>               # View task details
bd update <id> --status in_progress  # Claim work
bd close <id>              # Complete work
bd epic status             # View epic progress
bd sync                    # Sync with git
```

---

## Epic Overview

| Epic ID | Name | Tasks |
|---------|------|-------|
| home_security_intelligence-337 | Project Setup & Infrastructure | 8 |
| home_security_intelligence-7z7 | Backend Core - FastAPI & Database | 18 |
| home_security_intelligence-61l | AI Pipeline - RT-DETRv2 & Nemotron | 13 |
| home_security_intelligence-m9u | Frontend Dashboard - React UI | 20 |
| home_security_intelligence-fax | Integration & E2E Testing | 8 |

**Total: 67 tasks** (includes 14 TDD test tasks)

---

## Execution Phases

Tasks are organized into **8 execution phases** using labels. Complete phases in order.

### Phase 1: Project Setup (P0) - 7 tasks
```bash
bd list --label phase-1
```
- Create backend directory structure
- Create frontend directory structure
- Create Docker Compose configuration
- Create environment configuration
- Create AI model startup scripts
- Create backend requirements.txt
- Create frontend package.json

### Phase 2: Database & Layout Foundation (P1) - 6 tasks
```bash
bd list --label phase-2
```
- Implement SQLite database models
- Implement database connection and migrations
- Implement Redis connection
- Configure Tailwind with NVIDIA theme
- Implement app layout with sidebar navigation
- **TDD:** Write tests for database models

### Phase 3: Core APIs & Components (P2) - 11 tasks
```bash
bd list --label phase-3
```
- Implement cameras API endpoints
- Implement system API endpoints
- Implement media serving endpoint
- Implement API client service
- Implement WebSocket hooks
- Implement BoundingBoxOverlay component
- Implement RiskBadge component
- **TDD:** Write tests for cameras API
- **TDD:** Write tests for system API
- **TDD:** Write tests for API client
- **TDD:** Write tests for RiskBadge component

### Phase 4: AI Pipeline (P3/P4) - 13 tasks
```bash
bd list --label phase-4
```
- Implement file watcher service (with debounce & integrity checks)
- Implement RT-DETRv2 inference wrapper
- Implement detector client service
- Implement batch aggregator service
- Implement Nemotron analyzer service
- Implement Nemotron prompt template
- Configure llama.cpp server for Nemotron
- Implement thumbnail generation with bounding boxes
- Create model download script
- **TDD:** Write tests for file watcher service
- **TDD:** Write tests for detector client
- **TDD:** Write tests for batch aggregator
- **TDD:** Write tests for Nemotron analyzer

### Phase 5: Events & Real-time (P4) - 9 tasks
```bash
bd list --label phase-5
```
- Implement events API endpoints
- Implement detections API endpoints
- Implement WebSocket event channel
- Implement WebSocket system channel
- Implement GPU monitor service
- Implement data cleanup service
- Implement 'Fast Path' high-confidence alerts
- **TDD:** Write tests for events API
- **TDD:** Write tests for Fast Path alerts
- **TDD:** Write tests for detections API
- **TDD:** Write tests for WebSocket channels

### Phase 6: Dashboard Components (P3) - 7 tasks
```bash
bd list --label phase-6
```
- Implement circular Risk Gauge component
- Implement Live Activity Feed component
- Implement Camera Grid component
- Implement GPU Stats component
- Implement EventCard component
- **TDD:** Write tests for Dashboard components
- **TDD:** Write tests for EventCard component

### Phase 7: Pages & Modals (P4) - 6 tasks
```bash
bd list --label phase-7
```
- Implement main Dashboard page
- Implement Event Timeline page
- Implement Event Detail Modal
- Implement Settings page - Cameras tab
- Implement Settings page - Processing tab
- Implement Settings page - AI Models tab

### Phase 8: Integration & E2E (P4) - 8 tasks
```bash
bd list --label phase-8
```
- Create backend unit tests
- Create frontend component tests
- Create E2E pipeline integration test
- Test Docker Compose deployment
- Test native AI model startup
- Create seed cameras script
- Create project README
- Create setup script
- Implement basic API Key authentication middleware
- **TDD:** Write tests for API Key middleware

---

## TDD Workflow

Tasks labeled `tdd` are test-first tasks. For each feature:

1. **Write failing test first** (tdd task)
2. **Implement feature** (feature task)
3. **Verify tests pass**
4. **Commit both together**

Find all TDD tasks:
```bash
bd list --label tdd
```

---

## Epic 1: Project Setup & Infrastructure

### Task 1.1: Create backend directory structure

**Issue:** `home_security_intelligence-337.1`

**Files:**
- Create: `backend/api/__init__.py`
- Create: `backend/api/routes/__init__.py`
- Create: `backend/core/__init__.py`
- Create: `backend/models/__init__.py`
- Create: `backend/services/__init__.py`
- Create: `backend/data/.gitkeep`

**Step 1: Create directories**

```bash
mkdir -p backend/api/routes backend/core backend/models backend/services backend/data
```

**Step 2: Create __init__.py files**

```bash
touch backend/__init__.py
touch backend/api/__init__.py
touch backend/api/routes/__init__.py
touch backend/core/__init__.py
touch backend/models/__init__.py
touch backend/services/__init__.py
touch backend/data/.gitkeep
```

**Step 3: Commit**

```bash
git add backend/
git commit -m "feat: create backend directory structure"
bd close home_security_intelligence-337.1
```

---

### Task 1.2: Create frontend directory structure

**Issue:** `home_security_intelligence-337.2`

**Files:**
- Create: `frontend/src/components/layout/`
- Create: `frontend/src/components/dashboard/`
- Create: `frontend/src/components/events/`
- Create: `frontend/src/components/common/`
- Create: `frontend/src/hooks/`
- Create: `frontend/src/services/`
- Create: `frontend/src/styles/`

**Step 1: Create directories**

```bash
mkdir -p frontend/src/components/{layout,dashboard,events,common}
mkdir -p frontend/src/{hooks,services,styles}
mkdir -p frontend/public
```

**Step 2: Create placeholder files**

```bash
touch frontend/src/components/layout/.gitkeep
touch frontend/src/components/dashboard/.gitkeep
touch frontend/src/components/events/.gitkeep
touch frontend/src/components/common/.gitkeep
touch frontend/src/hooks/.gitkeep
touch frontend/src/services/.gitkeep
touch frontend/src/styles/.gitkeep
```

**Step 3: Commit**

```bash
git add frontend/
git commit -m "feat: create frontend directory structure"
bd close home_security_intelligence-337.2
```

---

### Task 1.3: Create Docker Compose configuration

**Issue:** `home_security_intelligence-337.3`

**Files:**
- Create: `docker-compose.yml`

**Step 1: Write docker-compose.yml**

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./backend/data:/app/data
      - /export/foscam:/cameras:ro
    environment:
      - DATABASE_URL=sqlite:///data/security.db
      - REDIS_URL=redis://redis:6379
      - DETECTOR_URL=http://host.docker.internal:8001
      - LLM_URL=http://host.docker.internal:8002
      - CAMERA_ROOT=/cameras
    depends_on:
      - redis
    restart: unless-stopped
    extra_hosts:
      - "host.docker.internal:host-gateway"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - VITE_API_URL=http://localhost:8000
      - VITE_WS_URL=ws://localhost:8000
    depends_on:
      - backend
    restart: unless-stopped

volumes:
  redis_data:
```

**Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add Docker Compose configuration"
bd close home_security_intelligence-337.3
```

---

### Task 1.4: Create environment configuration

**Issue:** `home_security_intelligence-337.4`

**Files:**
- Create: `.env.example`

**Step 1: Write .env.example**

```bash
# Camera Configuration
CAMERA_ROOT=/export/foscam

# Database
DATABASE_URL=sqlite:///data/security.db

# Redis
REDIS_URL=redis://localhost:6379

# AI Services (native, not in Docker)
DETECTOR_URL=http://localhost:8001
LLM_URL=http://localhost:8002

# Processing
BATCH_WINDOW_SECONDS=90
BATCH_IDLE_TIMEOUT_SECONDS=30
DETECTION_CONFIDENCE_THRESHOLD=0.5

# Retention
RETENTION_DAYS=30

# GPU Monitoring
GPU_POLL_INTERVAL_SECONDS=2
```

**Step 2: Commit**

```bash
git add .env.example
git commit -m "feat: add environment configuration template"
bd close home_security_intelligence-337.4
```

---

### Task 1.5: Create AI model startup scripts

**Issue:** `home_security_intelligence-337.5`

**Files:**
- Create: `ai/start_detector.sh`
- Create: `ai/start_llm.sh`
- Create: `ai/rtdetr/.gitkeep`
- Create: `ai/nemotron/.gitkeep`

**Step 1: Create directories**

```bash
mkdir -p ai/rtdetr ai/nemotron
```

**Step 2: Write start_detector.sh**

```bash
#!/bin/bash
# Start RT-DETRv2 detection server
cd "$(dirname "$0")/rtdetr"
python model.py --port 8001 --device cuda:0
```

**Step 3: Write start_llm.sh**

```bash
#!/bin/bash
# Start Nemotron llama.cpp server
llama-server \
  --model /path/to/nemotron.Q4_K_M.gguf \
  --port 8002 \
  --ctx-size 2048 \
  --n-gpu-layers 35 \
  --host 0.0.0.0
```

**Step 4: Make executable and commit**

```bash
chmod +x ai/start_detector.sh ai/start_llm.sh
git add ai/
git commit -m "feat: add AI model startup scripts"
bd close home_security_intelligence-337.5
```

---

### Task 1.6: Create backend requirements.txt

**Issue:** `home_security_intelligence-337.6`

**Files:**
- Create: `backend/requirements.txt`

**Step 1: Write requirements.txt**

```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
sqlalchemy>=2.0.0
aiosqlite>=0.19.0
redis>=5.0.0
watchdog>=3.0.0
pillow>=10.0.0
pynvml>=11.5.0
python-multipart>=0.0.6
httpx>=0.26.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
```

**Step 2: Commit**

```bash
git add backend/requirements.txt
git commit -m "feat: add backend Python dependencies"
bd close home_security_intelligence-337.6
```

---

### Task 1.7: Create frontend package.json

**Issue:** `home_security_intelligence-337.7`

**Files:**
- Create: `frontend/package.json`

**Step 1: Write package.json**

```json
{
  "name": "home-security-dashboard",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "test": "vitest"
  },
  "dependencies": {
    "@headlessui/react": "^1.7.18",
    "@tremor/react": "^3.14.0",
    "lucide-react": "^0.309.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.21.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.48",
    "@types/react-dom": "^18.2.18",
    "@vitejs/plugin-react": "^4.2.1",
    "autoprefixer": "^10.4.17",
    "postcss": "^8.4.33",
    "tailwindcss": "^3.4.1",
    "typescript": "^5.3.3",
    "vite": "^5.0.12",
    "vitest": "^1.2.0"
  }
}
```

**Step 2: Commit**

```bash
git add frontend/package.json
git commit -m "feat: add frontend package.json with dependencies"
bd close home_security_intelligence-337.7
```

---

### Task 1.8: Configure Tailwind with NVIDIA theme

**Issue:** `home_security_intelligence-337.8`

**Files:**
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/src/styles/globals.css`

**Step 1: Write tailwind.config.js**

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
    "./node_modules/@tremor/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        nvidia: {
          green: '#76B900',
        },
        background: {
          DEFAULT: '#0E0E0E',
          panel: '#1A1A1A',
          card: '#1E1E1E',
        },
        risk: {
          low: '#76B900',
          medium: '#FFB800',
          high: '#E74856',
        },
      },
    },
  },
  plugins: [],
}
```

**Step 2: Write postcss.config.js**

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

**Step 3: Write globals.css**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  @apply bg-background text-white;
}
```

**Step 4: Commit**

```bash
git add frontend/tailwind.config.js frontend/postcss.config.js frontend/src/styles/globals.css
git commit -m "feat: configure Tailwind with NVIDIA theme colors"
bd close home_security_intelligence-337.8
```

---

## Epic 2: Backend Core - FastAPI & Database

### Task 2.1: Implement SQLite database models

**Issue:** `home_security_intelligence-7z7.1`

**Files:**
- Create: `backend/models/camera.py`
- Create: `backend/models/detection.py`
- Create: `backend/models/event.py`
- Create: `backend/models/gpu_stats.py`

**Step 1: Write camera.py**

```python
from sqlalchemy import Column, String, DateTime, func
from backend.core.database import Base

class Camera(Base):
    __tablename__ = "cameras"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    folder_path = Column(String, nullable=False)
    status = Column(String, default="online")
    created_at = Column(DateTime, default=func.now())
    last_seen_at = Column(DateTime, default=func.now(), onupdate=func.now())
```

**Step 2: Write detection.py**

```python
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, func
from backend.core.database import Base

class Detection(Base):
    __tablename__ = "detections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(String, ForeignKey("cameras.id"))
    file_path = Column(String, nullable=False)
    file_type = Column(String)
    detected_at = Column(DateTime, default=func.now())
    object_type = Column(String)
    confidence = Column(Float)
    bbox_x = Column(Integer)
    bbox_y = Column(Integer)
    bbox_width = Column(Integer)
    bbox_height = Column(Integer)
    thumbnail_path = Column(String)
```

**Step 3: Write event.py**

```python
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, func
from backend.core.database import Base

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String, nullable=False)
    camera_id = Column(String, ForeignKey("cameras.id"))
    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    risk_score = Column(Integer)
    risk_level = Column(String)
    summary = Column(Text)
    reasoning = Column(Text)
    detection_ids = Column(Text)  # JSON array
    reviewed = Column(Boolean, default=False)
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now())
```

**Step 4: Write gpu_stats.py**

```python
from sqlalchemy import Column, Integer, Float, DateTime, func
from backend.core.database import Base

class GpuStats(Base):
    __tablename__ = "gpu_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    recorded_at = Column(DateTime, default=func.now())
    gpu_utilization = Column(Float)
    memory_used = Column(Integer)
    memory_total = Column(Integer)
    temperature = Column(Float)
    inference_fps = Column(Float)
```

**Step 5: Update models/__init__.py**

```python
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.gpu_stats import GpuStats

__all__ = ["Camera", "Detection", "Event", "GpuStats"]
```

**Step 6: Commit**

```bash
git add backend/models/
git commit -m "feat: implement SQLAlchemy database models"
bd close home_security_intelligence-7z7.1
```

---

### Task 2.2: Implement database connection and migrations

**Issue:** `home_security_intelligence-7z7.2`

**Files:**
- Create: `backend/core/database.py`

**Step 1: Write database.py**

```python
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from backend.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from backend.models import Camera, Detection, Event, GpuStats
    Base.metadata.create_all(bind=engine)
```

**Step 2: Commit**

```bash
git add backend/core/database.py
git commit -m "feat: implement database connection and initialization"
bd close home_security_intelligence-7z7.2
```

---

### Task 2.3: Implement Redis connection

**Issue:** `home_security_intelligence-7z7.3`

**Files:**
- Create: `backend/core/redis.py`

**Step 1: Write redis.py**

```python
import redis.asyncio as redis
from backend.core.config import settings

redis_client = None

async def get_redis():
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return redis_client

async def close_redis():
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None
```

**Step 2: Commit**

```bash
git add backend/core/redis.py
git commit -m "feat: implement Redis connection"
bd close home_security_intelligence-7z7.3
```

---

*[Remaining tasks follow same detailed pattern...]*

---

## Execution Commands

After each task, close it in bd:

```bash
bd close <issue-id>
```

After completing an epic, verify:

```bash
bd epic status
```

At session end, sync:

```bash
bd sync
git push
```

---

## Dependencies Between Phases

```
Phase 1 (Setup) → Phase 2 (DB/Layout) → Phase 3 (APIs) → Phase 4 (AI) → Phase 5 (Events) → Phase 6 (Components) → Phase 7 (Pages) → Phase 8 (E2E)

Phase Dependencies:
- Phase 2 requires Phase 1 (directory structure, dependencies)
- Phase 3 requires Phase 2 (database models, connections)
- Phase 4 requires Phase 3 (API endpoints for AI to call)
- Phase 5 requires Phase 4 (AI pipeline generates events)
- Phase 6 requires Phase 3 (API client, WebSocket hooks)
- Phase 7 requires Phase 6 (dashboard components)
- Phase 8 requires Phase 7 (full system to test)

Parallel Work Opportunities:
- Within Phase 3: Backend APIs and Frontend components can proceed in parallel
- Within Phase 4: RT-DETRv2 and Nemotron setup can proceed in parallel
- Within Phase 6: Individual components are independent
```

---

## Quick Start for Agent

```bash
# 1. Check current phase (start with phase-1)
bd list --label phase-1

# 2. Pick a task from current phase
bd show home_security_intelligence-337.1

# 3. Claim the task
bd update home_security_intelligence-337.1 --status in_progress

# 4. For TDD tasks: write test first, verify it fails
# 5. Implement the feature
# 6. Verify tests pass

# 7. Close and move to next
bd close home_security_intelligence-337.1

# 8. When phase complete, move to next phase
bd list --label phase-2

# 9. End of session
bd sync && git push
```

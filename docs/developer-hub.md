# Developer Hub

> Understand, contribute to, and extend Home Security Intelligence.

This hub is for software developers who want to understand the codebase, contribute features or fixes, or extend the system with new capabilities. It assumes programming experience and familiarity with Python, TypeScript, and web development concepts.

> See [Stability Levels](reference/stability.md) for what’s stable vs still evolving.

**Quick Start:** [Local Setup](developer/local-setup.md) | [Codebase Tour](developer/codebase-tour.md) | [Testing Guide](development/testing.md)

---

## Key Concepts

Before diving into the codebase, understand these core abstractions:

### Detection vs Event

```
Detection: Single object found in one image
  - person at 0.95 confidence in front_door/img001.jpg
  - car at 0.87 confidence in driveway/img002.jpg

Event: Analyzed group of detections over time
  - "Person approached front door, lingered 45s, left"
  - risk_score: 65, risk_level: high
  - Contains reasoning from LLM
```

Detections are raw AI outputs. Events are what users see in the dashboard.

### Batch Aggregation

The system groups 30-90 seconds of detections into batches before LLM analysis:

```
Camera uploads img001.jpg → Detection (person, 0.95)
Camera uploads img002.jpg → Detection (person, 0.92)  → Batch → LLM → Event
Camera uploads img003.jpg → Detection (car, 0.87)
...30 seconds of no activity...
Batch closes → Queued for analysis
```

This provides context ("person walked to door, paused, left") instead of noise ("15 separate person alerts").

### Fast Path

High-confidence person detections (>90%) bypass batching for immediate alerts. Critical events reach the dashboard in 3-6 seconds instead of 30-90 seconds.

### Risk Scoring

The LLM determines risk scores (0-100) based on context:

| Level    | Score  | Example                                  |
| -------- | ------ | ---------------------------------------- |
| Low      | 0-29   | Pet in yard, known vehicle               |
| Medium   | 30-59  | Unknown person during daytime            |
| High     | 60-84  | Person at unusual hour, loitering        |
| Critical | 85-100 | Multiple unknowns at night, forced entry |

See [Risk Levels Reference](reference/config/risk-levels.md) for the canonical definition.

---

## Architecture

| Document                                          | Description                                                            |
| ------------------------------------------------- | ---------------------------------------------------------------------- |
| [Architecture Overview](architecture/overview.md) | High-level system design, technology stack, component responsibilities |
| [Codebase Tour](developer/codebase-tour.md)       | Directory structure, key files, entry points                           |
| [Data Model Overview](architecture/data-model.md) | PostgreSQL schemas, Redis structures, entity relationships             |
| [Data Model Reference](developer/data-model.md)   | Complete database model documentation with code examples               |
| [AI Pipeline](architecture/ai-pipeline.md)        | FileWatcher -> RT-DETRv2 -> BatchAggregator -> Nemotron flow           |

**AI Pipeline Deep Dives:**

| Document                                            | Description                               | Time    |
| --------------------------------------------------- | ----------------------------------------- | ------- |
| [Pipeline Overview](developer/pipeline-overview.md) | High-level flow, timing characteristics   | ~8 min  |
| [Detection Service](developer/detection-service.md) | RT-DETRv2 API, bounding boxes, confidence | ~8 min  |
| [Batching Logic](developer/batching-logic.md)       | Window timing, Redis keys, fast path      | ~8 min  |
| [Risk Analysis](developer/risk-analysis.md)         | Nemotron prompts, scoring, validation     | ~10 min |

### Quick Architecture Diagram

```
Cameras → FTP → FileWatcher → detection_queue → RT-DETRv2 → Detections
                                                     ↓
Dashboard ← WebSocket ← Events ← Nemotron ← analysis_queue ← BatchAggregator
```

---

## Development

| Document                                 | Description                                              |
| ---------------------------------------- | -------------------------------------------------------- |
| [Local Setup](development/setup.md)      | Development environment, dependencies, IDE configuration |
| [Testing Guide](development/testing.md)  | Unit tests, integration tests, coverage requirements     |
| [Pre-commit Hooks](developer/hooks.md)   | Ruff, MyPy, ESLint, Prettier - code quality enforcement  |
| [Code Patterns](development/patterns.md) | Async patterns, dependency injection, error handling     |

### Development Commands

```bash
# Start development environment
source .venv/bin/activate
podman-compose -f docker-compose.prod.yml up -d postgres redis

# Run backend
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Run frontend
cd frontend && npm run dev

# Run tests
pytest backend/tests/ -v
cd frontend && npm test

# Full validation (before committing)
./scripts/validate.sh
```

---

## Deep Dives

| Document                                          | Description                                             |
| ------------------------------------------------- | ------------------------------------------------------- |
| [Alert System](developer/alerts.md)               | Alert rules, evaluation pipeline, notification channels |
| [Real-time System](architecture/real-time.md)     | WebSocket channels, Redis pub/sub, EventBroadcaster     |
| [Video Processing](developer/video.md)            | FTP uploads, file watching, ffmpeg, frame extraction    |
| [Frontend Hooks](architecture/frontend-hooks.md)  | useWebSocket, useEventStream, useSystemStatus           |
| [Design Decisions](architecture/decisions.md)     | ADRs - why PostgreSQL, why Redis, why batching          |
| [Resilience Patterns](architecture/resilience.md) | Error handling, retry logic, dead-letter queues         |

### WebSocket Channels

| Endpoint     | Purpose                     | Message Type                           |
| ------------ | --------------------------- | -------------------------------------- |
| `/ws/events` | Security event stream       | `{type: "event", data: {...}}`         |
| `/ws/system` | System health (5s interval) | `{type: "system_status", data: {...}}` |

---

## Contributing

| Document                                          | Description                                 |
| ------------------------------------------------- | ------------------------------------------- |
| [Contributing Guide](development/contributing.md) | PR process, commit conventions, code review |
| [Design Decisions](architecture/decisions.md)     | ADRs explaining why we made key choices     |

### Contribution Workflow

```bash
# 1. Find and claim work
bd ready                                    # List available tasks
bd update <id> --status in_progress         # Claim task

# 2. Create branch
git checkout -b feature/my-feature

# 3. Develop with tests
# Write tests first (TDD for tasks labeled 'tdd')
pytest backend/tests/ -v
cd frontend && npm test

# 4. Commit (hooks run automatically)
git add -A
git commit -m "feat(scope): description"

# 5. Push and create PR
git push -u origin feature/my-feature
gh pr create --title "feat: my feature"

# 6. After merge, close task
bd close <id>
```

### Commit Message Format

```
<type>(<scope>): <description>

Types: feat, fix, docs, style, refactor, perf, test, chore
Scopes: cameras, events, detections, websocket, ai, frontend, etc.
```

---

## Quick Reference

### API Reference

| Document                                      | Description                                    |
| --------------------------------------------- | ---------------------------------------------- |
| [API Overview](reference/api/overview.md)     | REST endpoints, authentication, error handling |
| [Cameras API](api-reference/cameras.md)       | Camera CRUD, status management                 |
| [Events API](api-reference/events.md)         | Event listing, filtering, marking reviewed     |
| [Detections API](api-reference/detections.md) | Detection queries, thumbnails                  |
| [System API](api-reference/system.md)         | Health checks, GPU stats, cleanup              |
| [WebSocket API](api-reference/websocket.md)   | Real-time event and status channels            |

### AGENTS.md Navigation

Every directory has an `AGENTS.md` file documenting its purpose, key files, and patterns:

| Directory                                                        | Purpose                        |
| ---------------------------------------------------------------- | ------------------------------ |
| [/AGENTS.md](../AGENTS.md)                                       | Project overview, entry points |
| [/backend/AGENTS.md](../backend/AGENTS.md)                       | Backend architecture           |
| [/backend/services/AGENTS.md](../backend/services/AGENTS.md)     | AI pipeline services           |
| [/backend/api/routes/AGENTS.md](../backend/api/routes/AGENTS.md) | REST endpoints                 |
| [/backend/models/AGENTS.md](../backend/models/AGENTS.md)         | Database models                |
| [/frontend/AGENTS.md](../frontend/AGENTS.md)                     | Frontend architecture          |
| [/frontend/src/hooks/AGENTS.md](../frontend/src/hooks/AGENTS.md) | Custom React hooks             |
| [/ai/AGENTS.md](../ai/AGENTS.md)                                 | AI model integration           |

```bash
# List all AGENTS.md files
find . -name "AGENTS.md" -type f | head -20
```

### Service Ports

| Service     | Port | Protocol |
| ----------- | ---- | -------- |
| Frontend    | 5173 | HTTP     |
| Backend API | 8000 | HTTP/WS  |
| PostgreSQL  | 5432 | TCP      |
| Redis       | 6379 | TCP      |
| RT-DETRv2   | 8090 | HTTP     |
| Nemotron    | 8091 | HTTP     |

### Key Files

| File                                    | Purpose                             |
| --------------------------------------- | ----------------------------------- |
| `backend/main.py`                       | FastAPI application entry point     |
| `backend/core/config.py`                | Environment variable settings       |
| `backend/core/database.py`              | PostgreSQL async session management |
| `backend/services/file_watcher.py`      | Camera directory monitoring         |
| `backend/services/batch_aggregator.py`  | Detection batching logic            |
| `backend/services/nemotron_analyzer.py` | LLM risk analysis                   |
| `frontend/src/App.tsx`                  | React application root              |
| `frontend/src/hooks/useEventStream.ts`  | WebSocket event hook                |
| `frontend/src/services/api.ts`          | API client                          |

---

## Code Examples

### Adding a New API Endpoint

```python
# backend/api/routes/my_feature.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_session
from backend.api.schemas.my_feature import MyResponse

router = APIRouter(prefix="/my-feature", tags=["my-feature"])

@router.get("/", response_model=MyResponse)
async def get_my_feature(
    session: AsyncSession = Depends(get_session),
) -> MyResponse:
    """Get my feature data."""
    # Implementation here
    return MyResponse(data="example")
```

### Adding a New React Hook

```typescript
// frontend/src/hooks/useMyFeature.ts
import { useState, useEffect } from 'react';
import { api } from '../services/api';

interface MyFeatureData {
  data: string;
}

export function useMyFeature() {
  const [data, setData] = useState<MyFeatureData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await api.get('/my-feature');
        setData(response.data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  return { data, loading, error };
}
```

### Writing a Unit Test

```python
# backend/tests/unit/test_my_feature.py
import pytest
from unittest.mock import AsyncMock, patch

from backend.services.my_feature import MyFeatureService

@pytest.mark.asyncio
async def test_my_feature_success():
    """Test successful feature operation."""
    mock_session = AsyncMock()
    service = MyFeatureService(mock_session)

    result = await service.do_something()

    assert result.success is True
    mock_session.commit.assert_called_once()

@pytest.mark.asyncio
async def test_my_feature_handles_error():
    """Test graceful error handling."""
    mock_session = AsyncMock()
    mock_session.execute.side_effect = Exception("DB error")
    service = MyFeatureService(mock_session)

    result = await service.do_something()

    assert result.success is False
    assert "DB error" in result.error
```

---

## Troubleshooting

### Common Issues

| Issue                     | Solution                                       |
| ------------------------- | ---------------------------------------------- |
| Pre-commit fails          | Run `pre-commit run --all-files` to see errors |
| Database connection error | Ensure PostgreSQL is running: `podman ps`      |
| Import errors in tests    | Activate venv: `source .venv/bin/activate`     |
| WebSocket not connecting  | Check backend is running on port 8000          |
| GPU not detected          | Verify NVIDIA Container Toolkit: `nvidia-smi`  |

### Getting Help

1. Read the relevant `AGENTS.md` file for context
2. Check existing tests for usage examples
3. Review [Design Decisions](architecture/decisions.md) for rationale
4. Search existing code for similar patterns

---

## Related Documentation

| Hub                             | Audience                                                      |
| ------------------------------- | ------------------------------------------------------------- |
| [User Hub](user-hub.md)         | End users - dashboard usage, understanding alerts             |
| [Operator Hub](operator-hub.md) | System administrators - deployment, configuration, monitoring |
| **Developer Hub**               | You are here                                                  |

---

**Navigation:**

- [Back to README](../README.md)
- [CLAUDE.md](../CLAUDE.md) - Project instructions for AI assistants
- [ROADMAP.md](ROADMAP.md) - Post-MVP enhancement ideas

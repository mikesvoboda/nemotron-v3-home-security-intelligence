# GitHub Copilot Instructions

This is an AI-powered home security monitoring system that processes camera footage,
detects objects using RT-DETRv2, and analyzes security risks using Nemotron LLM.

## Tech Stack

### Backend (Python 3.11)

- **Framework**: FastAPI with async/await patterns
- **Database**: SQLAlchemy ORM with SQLite
- **Cache/Queue**: Redis for real-time messaging
- **Validation**: Pydantic schemas for all API inputs/outputs

### Frontend (TypeScript)

- **Framework**: React 18 with functional components and hooks
- **Styling**: Tailwind CSS with Tremor component library
- **Build**: Vite with strict TypeScript
- **Testing**: Vitest with React Testing Library

### AI Pipeline

- **Object Detection**: RT-DETRv2 running as HTTP service on GPU
- **Risk Analysis**: Nemotron LLM via llama.cpp for security reasoning
- **Hardware**: NVIDIA RTX A5500 (24GB VRAM)

## Coding Conventions

### Python

- Line length: 100 characters
- Use type hints for all function signatures
- Async functions for I/O operations
- Pydantic models for data validation
- SQLAlchemy models with proper relationships
- pytest for testing with async support

```python
# Example function signature
async def get_events(
    db: AsyncSession,
    camera_id: str | None = None,
    limit: int = 50,
) -> list[Event]:
    ...
```

### TypeScript/React

- Functional components with TypeScript interfaces
- Custom hooks prefixed with `use`
- No explicit `any` types (use proper generics)
- Import ordering: builtin > external > internal > relative
- Tailwind for styling, avoid inline styles

```typescript
// Example component
interface EventCardProps {
  event: SecurityEvent;
  onSelect?: (id: string) => void;
}

export function EventCard({ event, onSelect }: EventCardProps) {
  // ...
}
```

### Testing

- Unit tests alongside implementation
- Integration tests for API endpoints
- 90%+ coverage requirement
- Mock external services in tests

## Domain Context

### Security Monitoring Concepts

- **Camera**: Foscam IP cameras uploading via FTP
- **Detection**: RT-DETRv2 identifies objects (person, vehicle, animal)
- **Event**: Aggregated detections within a time window
- **Risk Score**: 0-100 rating from Nemotron analysis
- **Batch Window**: 90-second aggregation with 30-second idle timeout

### Key Entities

- `Camera` - surveillance camera configuration
- `Detection` - single object detected in an image
- `Event` - security event grouping related detections
- `RiskAssessment` - LLM-generated risk analysis

### File Paths

- Camera images: `/export/foscam/{camera_name}/`
- Backend code: `backend/`
- Frontend code: `frontend/src/`
- AI services: `ai/rtdetr/`, `ai/nemotron/`

## What NOT to Suggest

- Authentication/authorization code (single-user local deployment)
- Cloud service integrations (fully self-hosted)
- Alternative ML frameworks (committed to RT-DETRv2 + Nemotron)
- Database migrations for SQLite (simple schema evolution)

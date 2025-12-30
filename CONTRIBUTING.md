# Contributing to Home Security Intelligence

Thank you for your interest in contributing to this project!

## Development Setup

### Prerequisites

- Python 3.14+
- Node.js 18+
- Podman (for container management)

### Getting Started

1. Clone the repository
2. Run the setup script:

```bash
./scripts/setup.sh
```

This will:

- Create a Python virtual environment at `.venv/`
- Install backend dependencies
- Install frontend dependencies
- Set up pre-commit hooks

## API Types Synchronization

This project uses auto-generated TypeScript types from the backend OpenAPI specification to ensure frontend-backend type safety.

### How It Works

1. **Backend Schemas**: Pydantic models in `backend/api/schemas/` define API data structures
2. **OpenAPI Spec**: FastAPI automatically generates an OpenAPI specification from these models
3. **TypeScript Types**: The `generate-types.sh` script extracts the OpenAPI spec and generates TypeScript types using `openapi-typescript`

### Generated Files

- **Input**: `backend/api/schemas/*.py` (Pydantic models)
- **Output**: `frontend/src/types/generated/api.ts` (TypeScript types)
- **Exports**: `frontend/src/types/generated/index.ts` (convenient re-exports)

### When to Regenerate Types

Regenerate TypeScript types whenever you:

- Add or modify Pydantic schemas in `backend/api/schemas/`
- Change API endpoint request/response models
- Modify FastAPI route response models

### Regenerating Types

```bash
# Generate types (run from project root)
./scripts/generate-types.sh

# Or from frontend directory
cd frontend && npm run generate-types
```

### Checking If Types Are Current

```bash
# Check if types need regeneration (for CI)
./scripts/generate-types.sh --check

# Or from frontend directory
cd frontend && npm run generate-types:check
```

### Automatic Enforcement

Types are automatically checked to prevent drift:

1. **Pre-push Hook**: The `api-types-contract` hook runs on every git push
2. **CI Pipeline**: The `api-types-check` job fails PRs with outdated types

### Workflow for Schema Changes

1. Modify Pydantic schema in `backend/api/schemas/`
2. Run `./scripts/generate-types.sh` to regenerate TypeScript types
3. Update frontend code to use new types
4. Commit both the schema changes and regenerated types

### Example Usage

**Backend schema** (`backend/api/schemas/camera.py`):

```python
from pydantic import BaseModel, Field

class CameraResponse(BaseModel):
    id: int
    name: str = Field(..., description="Camera display name")
    location: str | None = None
```

**Generated TypeScript type** (`frontend/src/types/generated/api.ts`):

```typescript
export interface CameraResponse {
  id: number;
  name: string;
  location?: string | null;
}
```

**Frontend usage** (`frontend/src/services/api.ts`):

```typescript
import type { Camera } from "@/types/generated";

async function getCamera(id: number): Promise<Camera> {
  const response = await fetch(`/api/cameras/${id}`);
  return response.json();
}
```

## Testing

### Running Tests

```bash
# Backend unit tests
source .venv/bin/activate
pytest backend/tests/unit/ -v

# Backend integration tests
pytest backend/tests/integration/ -v

# Frontend tests
cd frontend && npm test

# Full validation (recommended before PRs)
./scripts/validate.sh
```

### Test Requirements

All features must have tests written at time of development:

- **Unit tests**: Test individual functions/components in isolation
- **Integration tests**: Test interactions between components

## Pre-commit Hooks

Pre-commit hooks run automatically on every commit:

- Python linting (ruff)
- Python formatting (ruff format)
- Python type checking (mypy)
- TypeScript/JavaScript linting (eslint)
- Code formatting (prettier)

On push, additional hooks run:

- Unit tests
- API types contract check

### Installing Hooks

```bash
pre-commit install                     # Pre-commit hooks
pre-commit install --hook-type pre-push  # Pre-push hooks
```

### Running Hooks Manually

```bash
pre-commit run --all-files
```

## Git Workflow

1. Create a feature branch from `main`
2. Make your changes
3. Ensure all tests pass
4. Ensure types are regenerated if schemas changed
5. Commit with a descriptive message
6. Push and create a pull request

## Code Style

- **Python**: Follow ruff rules (configured in `pyproject.toml`)
- **TypeScript**: Follow eslint rules (configured in `frontend/.eslintrc.cjs`)
- **Formatting**: Use prettier for frontend code

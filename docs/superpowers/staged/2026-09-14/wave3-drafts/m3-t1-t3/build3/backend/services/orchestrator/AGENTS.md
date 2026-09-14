# Container Orchestration Shared Models

This directory contains the canonical domain models for container orchestration.
All orchestration modules should import from here instead of defining their own duplicates.

## Purpose

Previously, `ManagedService`, `ServiceConfig`, and `ServiceRegistry` were duplicated
across multiple files with slight variations. This package consolidates them into
a single source of truth.

## Modules

### `enums.py`

Re-exports enums from `backend.api.schemas.services`:

- `ServiceCategory`: Classification (INFRASTRUCTURE, AI, MONITORING)
- `ContainerServiceStatus`: Status (RUNNING, STARTING, UNHEALTHY, STOPPED, DISABLED, NOT_FOUND)

### `models.py`

Canonical dataclass definitions:

- `ServiceConfig`: Configuration for service discovery patterns
- `ManagedService`: Runtime state of a managed container service

### `registry.py`

Thread-safe service registry with Redis persistence:

- `ServiceRegistry`: In-memory storage with Redis state persistence
- `get_service_registry()`: Global singleton accessor
- `reset_service_registry()`: Test utility to reset singleton

## Usage

```python
from backend.services.orchestrator import (
    # Enums
    ServiceCategory,
    ContainerServiceStatus,
    # Models
    ManagedService,
    ServiceConfig,
    # Registry
    ServiceRegistry,
    get_service_registry,
)

# Create a service config
config = ServiceConfig(
    display_name="PostgreSQL",
    category=ServiceCategory.INFRASTRUCTURE,
    port=5432,
    health_cmd="pg_isready -U security",
)

# Create a managed service
service = ManagedService(
    name="postgres",
    display_name="PostgreSQL",
    container_id="abc123",
    image="postgres:16-alpine",
    port=5432,
    health_endpoint=None,
    health_cmd="pg_isready -U security",
    category=ServiceCategory.INFRASTRUCTURE,
)

# Use the registry
registry = await get_service_registry()
registry.register(service)
registry.update_status("postgres", ContainerServiceStatus.RUNNING)
await registry.persist_state("postgres")
```

## Files That Import From Here

After refactoring, these files should import from this package:

- `backend/services/container_discovery.py`
- `backend/services/lifecycle_manager.py`
- `backend/services/health_monitor_orchestrator.py`
- `backend/services/service_registry.py`
- `backend/services/container_orchestrator.py`

## Key Design Decisions

1. **Enums stay in API schemas**: `ServiceCategory` and `ContainerServiceStatus` are
   defined in `backend.api.schemas.services` and re-exported here for convenience.

2. **datetime over Unix timestamps**: `ManagedService` uses `datetime` objects for
   `last_failure_at` and `last_restart_at`. The `last_failure_timestamp` property
   provides Unix timestamp access for compatibility.

3. **Thread-safe registry**: `ServiceRegistry` uses `threading.RLock` for thread safety.

4. **Optional Redis**: `ServiceRegistry` works without Redis - persistence ops are no-ops.

5. **Helper methods on ManagedService**: Methods like `record_failure()`, `record_restart()`,
   and `reset_failures()` encapsulate common state mutations.

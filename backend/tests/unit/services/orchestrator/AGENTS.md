# Unit Tests - Orchestrator Services

## Purpose

The `backend/tests/unit/services/orchestrator/` directory contains unit tests for the orchestrator service layer that coordinates AI model loading, inference routing, and service registry management.

## Directory Structure

```
backend/tests/unit/services/orchestrator/
├── AGENTS.md           # This file
├── __init__.py         # Package initialization
├── test_enums.py       # Orchestrator enum tests (4KB)
├── test_models.py      # Orchestrator model tests (12KB)
└── test_registry.py    # Service registry tests (13KB)
```

## Test Files (3 total)

| File               | Component Tested    | Key Coverage                       |
| ------------------ | ------------------- | ---------------------------------- |
| `test_enums.py`    | Orchestrator enums  | Model status, inference types      |
| `test_models.py`   | Orchestrator models | Model config, inference requests   |
| `test_registry.py` | ServiceRegistry     | Service registration and discovery |

## Running Tests

```bash
# All orchestrator unit tests
uv run pytest backend/tests/unit/services/orchestrator/ -v

# Specific component tests
uv run pytest backend/tests/unit/services/orchestrator/test_registry.py -v

# With coverage
uv run pytest backend/tests/unit/services/orchestrator/ -v --cov=backend.services.orchestrator
```

## Test Categories

### Enum Tests (`test_enums.py`)

Tests for orchestrator enumerations:

| Enum            | Values Tested                        |
| --------------- | ------------------------------------ |
| `ModelStatus`   | loading, ready, error, unloading     |
| `InferenceType` | detection, classification, embedding |
| `ModelPriority` | critical, high, normal, low          |

### Model Tests (`test_models.py`)

Tests for orchestrator data models:

| Model               | Coverage                            |
| ------------------- | ----------------------------------- |
| `ModelConfig`       | Model configuration validation      |
| `InferenceRequest`  | Request structure and serialization |
| `InferenceResponse` | Response structure and parsing      |
| `ModelHealth`       | Health status representation        |

### Registry Tests (`test_registry.py`)

Tests for service registry:

| Test Class                | Coverage                         |
| ------------------------- | -------------------------------- |
| `TestServiceRegistration` | Register and unregister services |
| `TestServiceDiscovery`    | Find services by type/capability |
| `TestServiceHealth`       | Track service health status      |
| `TestLoadBalancing`       | Route requests across instances  |

## Test Patterns

### Enum Validation

```python
def test_model_status_values():
    assert ModelStatus.LOADING.value == "loading"
    assert ModelStatus.READY.value == "ready"
    assert ModelStatus.ERROR.value == "error"

def test_model_status_from_string():
    status = ModelStatus("ready")
    assert status == ModelStatus.READY
```

### Model Configuration

```python
def test_model_config_validation():
    config = ModelConfig(
        name="rtdetr",
        model_type="detection",
        priority=ModelPriority.CRITICAL,
        memory_mb=4096
    )
    assert config.is_valid()
    assert config.requires_gpu

def test_model_config_rejects_invalid():
    with pytest.raises(ValidationError):
        ModelConfig(
            name="",  # Invalid: empty name
            model_type="detection"
        )
```

### Service Registry

```python
@pytest.mark.asyncio
async def test_register_service():
    registry = ServiceRegistry()

    await registry.register(
        name="rtdetr-1",
        service_type="detection",
        endpoint="http://localhost:8090"
    )

    services = await registry.find_by_type("detection")
    assert len(services) == 1
    assert services[0].name == "rtdetr-1"

@pytest.mark.asyncio
async def test_load_balancing():
    registry = ServiceRegistry()
    await registry.register("rtdetr-1", "detection", "http://host1:8090")
    await registry.register("rtdetr-2", "detection", "http://host2:8090")

    # Should round-robin between instances
    endpoints = [await registry.get_endpoint("detection") for _ in range(4)]
    assert endpoints.count("http://host1:8090") == 2
    assert endpoints.count("http://host2:8090") == 2
```

## Related Documentation

- `/backend/services/orchestrator/AGENTS.md` - Orchestrator implementation
- `/backend/tests/unit/services/AGENTS.md` - Service unit tests overview
- `/backend/tests/integration/services/AGENTS.md` - Service integration tests

# Florence-2 Tests Directory

## Purpose

Unit tests for the Florence-2 Vision-Language Server (`ai/florence/model.py`).
Tests validate the region endpoints (`/describe-region`, `/phrase-grounding`)
and their Pydantic models without requiring a GPU or actual model files.

> The `/analyze-scene` endpoint and its dedicated test file
> (`test_analyze_scene.py`, 18 tests) were deleted under ADDENDUM 2 A7.2 —
> the route was unreachable (no backend client method, no openapi path, no
> frontend consumer; census in the deletion commit body). The registry op
> `florence_analyze_scene` is ratcheted absent by
> `backend/tests/contracts/ai_providers/test_ai_contract_registry.py`
> (`DELETED_REGISTRY_OPS` / `DELETED_SERVER_ROUTES`).

## Directory Structure

```
ai/florence/tests/
├── AGENTS.md                # This file
├── __init__.py              # Package marker
└── test_region_endpoints.py # Region/phrase endpoint + model unit tests
```

## Running Tests

```bash
# Run all Florence-2 tests
uv run pytest ai/florence/tests/ -v

# Run with coverage
uv run pytest ai/florence/tests/ -v --cov=ai.florence
```

## Test Files

### `test_region_endpoints.py`

Covers the NEM-3911 region endpoints and the shared Pydantic models:

| Class                                                               | Description                                 |
| ------------------------------------------------------------------- | ------------------------------------------- |
| `TestBoundingBoxModel`                                              | BoundingBox validation (ranges, coercion)   |
| `TestRegionDescriptionRequest` / `...Response`                      | /describe-region wire shapes                |
| `TestPhraseGroundingRequest` / `TestGroundedPhrase` / `...Response` | /phrase-grounding wire shapes               |
| `TestDescribeRegionEndpoint`                                        | Endpoint behavior with mocked Triton client |
| `TestPhraseGroundingEndpoint`                                       | Endpoint behavior with mocked Triton client |
| `TestEndpointMetrics`                                               | Prometheus counters/latency per endpoint    |
| `TestSecurityScenarios`                                             | Security-relevant payload shapes            |

## Testing Patterns

### Mocking the Triton client

Tests patch the Triton inference client to avoid GPU requirements — see the
`mock_triton` fixture in `test_region_endpoints.py`, mirroring
`ai/gateway/tests/test_adapters_florence.py`.

## Related Documentation

- `/ai/florence/AGENTS.md` - Florence-2 service documentation
- `/ai/florence/model.py` - Main server implementation
- `/ai/AGENTS.md` - AI pipeline overview

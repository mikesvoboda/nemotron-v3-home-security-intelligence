# backend/tests/contracts/

## Purpose

Contract tests: assertions about the API's external shape rather than its
behavior — OpenAPI schema validity, endpoint/response contracts, and WebSocket
message formats. These fail when the public surface drifts, independent of any
service logic.

## Key Files

| File | What it pins |
| --- | --- |
| `test_api_contracts.py` | Endpoint presence and response-shape contracts |
| `test_openapi_schema_validation.py` | Generated OpenAPI document validity (schema-level) |
| `test_websocket_contracts.py` | WebSocket message envelope/format contracts |
| `conftest.py` | Shared fixtures for the contract tier |
| `ai_providers/` | AI-provider conformance tier (own index: `ai_providers/AGENTS.md`) |

## Patterns

- Run: `uv run pytest backend/tests/contracts/` (ci.yml runs this tier
  directly; `scripts/validate.sh` includes it in the combined pass, and
  `scripts/check-api-contracts.sh` wraps the API-shape check).
- When you add/change a route, fix the contract here too — CI drift failures
  originate from this tier, not the unit tier.
- The `ai_providers/` subdir tests AI services against generated golden
  contracts (regenerated via `scripts/gen-ai-contract.py`); see its AGENTS.md
  for the no-xfail rules.

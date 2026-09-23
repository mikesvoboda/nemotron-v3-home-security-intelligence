# AI Gateway Tests Directory

## Purpose

Unit tests for the AI Gateway (`ai/gateway/`): FastAPI app, Triton gRPC client wrapper, device-patching script, and all five adapter modules. Fully mocked — no GPU, no running Triton.

## Directory Structure

```
ai/gateway/tests/
├── AGENTS.md                          # This file
├── __init__.py                        # Package marker
├── test_main.py                       # App, health aggregation, metrics, router mounting
├── test_metrics_middleware.py         # hsi_ai_inference_* duration/error observation + labels
├── test_triton_client.py              # gRPC wrapper: pooling, timeouts, error paths
├── test_patch_triton_configs.py       # models.yml -> config.pbtxt rewriting
├── test_adapters_yolo26.py            # /yolo26 endpoints
├── test_adapters_clip.py              # /clip endpoints
├── test_adapters_florence.py          # /florence endpoints
├── test_adapters_enrichment.py        # /enrichment fan-out + /enrich dispatch
└── test_adapters_enrichment_light.py  # /enrich-lt endpoints
```

## Running Tests

```bash
uv run pytest ai/gateway/tests/ -v
```

## Testing Patterns

- Patch `triton_client` at the adapter boundary (`mock_triton` fixtures) — adapters build `InferInput`/parse `InferOutput` against mocked responses.
- Tests assert **wire compatibility** with the legacy AI containers: exact JSON response shapes the backend clients expect (multipart in, `detections`/`image_width`/... out).
- `test_patch_triton_configs.py` uses temp dirs with synthetic `models.yml`/`config.pbtxt` text — never touches the real repository.

## Related

- `/ai/gateway/AGENTS.md` — service documentation
- `/ai/florence/tests/AGENTS.md` — mirrors the florence adapter mock pattern

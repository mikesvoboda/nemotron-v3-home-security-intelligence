# AI Model Testing Guide

This guide covers testing strategies for the AI stack that ships: the Triton
detection lane behind `ai-gateway`, the `ai-vlm` reasoning service, and the
three in-process specialist lookup legs in the backend. Each has a different
seam — an HTTP adapter over a Triton gRPC client, an OpenAI-compatible
completion endpoint, and in-process model loaders with DB gallery lookups —
and each has its own mocking pattern.

## Test layout

```
ai/gateway/tests/                       # the gateway + Triton lane
├── conftest.py                         # path + Triton-stub fixtures
├── test_adapters_yolo26.py             # /yolo26 adapter (Triton client mocked)
├── test_adapters_enrichment_light.py   # /enrich-lt readiness adapter
├── test_residency.py                   # model_repository pruning per GATEWAY_MODEL_SET
├── test_entrypoint_residency.py        # what the container entrypoint actually starts
├── test_triton_client.py               # the gRPC client wrapper
├── test_export_yolo26.py               # engine export for the shipped set
├── test_export_reid.py
├── test_main.py                        # router mounts, /health
├── test_metrics_middleware.py
├── test_patch_triton_configs.py
└── test_py312_compat.py

ai/tests/                               # shared GPU/torch helpers under ai/
├── test_module_hygiene.py
├── test_cuda_graph_manager.py
└── ...

backend/tests/unit/services/            # the live specialist legs + VLM path
├── test_osnet_loader.py                # person re-identification loader
├── test_face_recognizer_loader.py      # face detection + embedding loader
├── test_vlm_specialists.py             # the three-lookup gather
├── test_vlm_analyzer.py                # batch -> verdict -> Event
├── test_vlm_verdict.py                 # verdict invariants
└── test_vlm_client.py                  # prompt fitting, image budget

backend/tests/integration/services/
├── test_osnet_loader.py                # weights-resent degradation contract
└── test_fast_alpr_loader.py
```

## Unit testing a gateway adapter

An adapter is a thin FastAPI router over `ai/gateway/triton_client.py`. Test
it with `httpx.ASGITransport` against the mounted router and a mocked Triton
client — no Triton server, no GPU.

```python
# ai/gateway/tests/test_adapters_yolo26.py (shape of the real imports)
import io
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from PIL import Image

from ai.gateway.adapters.yolo26 import (
    COCO_CLASSES,
    CONFIDENCE_THRESHOLD,
    MODEL_NAME,
    NMS_THRESHOLD,
    TARGET_SIZE,
    _postprocess_yolo,
    router,
)
from ai.gateway.triton_client import TritonClientError


def _make_test_image(width: int = 640, height: int = 480, fmt: str = "JPEG") -> bytes:
    """A minimal decodable image — adapters validate media before inference."""
    img = Image.new("RGB", (width, height), color=(128, 64, 32))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router, prefix="/yolo26")
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_detect_returns_boxes(client):
    with patch("ai.gateway.adapters.yolo26.TritonClient.infer", new_callable=AsyncMock) as infer:
        infer.return_value = _raw_yolo_output(...)  # adapter-shaped ndarray
        resp = await client.post("/yolo26/detect", files={"file": ("a.jpg", _make_test_image())})
        assert resp.status_code == 200
        assert resp.json()["detections"][0]["class_name"] in COCO_CLASSES


@pytest.mark.asyncio
async def test_triton_failure_is_not_a_200(client):
    with patch("ai.gateway.adapters.yolo26.TritonClient.infer", new_callable=AsyncMock) as infer:
        infer.side_effect = TritonClientError("model not ready")
        resp = await client.post("/yolo26/detect", files={"file": ("a.jpg", _make_test_image())})
        assert resp.status_code >= 500
```

Assert on the adapter's postprocessing contract, not on Triton internals:
confidence filtering (`CONFIDENCE_THRESHOLD`), `NMS_THRESHOLD` suppression,
letterbox coordinate reversal back to the source frame, and `TARGET_SIZE`
rescaling. `test_adapters_yolo26.py` covers all four against `_postprocess_yolo`
directly, which is the cheapest place to pin them.

## Unit testing an in-process specialist loader

The live specialist legs are `osnet_loader` (person re-ID),
`face_recognizer_loader` (SCRFD detection + w600k embedding) and
`fast_alpr_loader` (plates). Their defining behaviour is **residency**:
`get_reid_handle()` and `get_face_leg_handles()` are membership reads that
never trigger a load, so on a host with `BACKEND_MODEL_PRELOAD=false` the leg
reports unavailable instead of loading. The tests below pin that, because a
test that patches the loader to succeed erases the behaviour that matters.

The handles live in the model-zoo manager's loaded-models dict, so the seam is
`backend.services.model_zoo.get_model_manager` — which is imported lazily
inside the read precisely to avoid an import cycle. Patch it where it is
looked up, not where it is defined:

```python
from unittest.mock import MagicMock

from backend.services import osnet_loader as ol

OSNET_ID = ol.osnet_model_id()


def test_absent_model_answers_none(monkeypatch):
    fake_manager = MagicMock()
    fake_manager._loaded_models = {}
    monkeypatch.setattr("backend.services.model_zoo.get_model_manager", lambda: fake_manager)
    assert ol.get_reid_handle() is None


def test_read_never_triggers_a_load(monkeypatch):
    fake_manager = MagicMock()
    fake_manager._loaded_models = {}
    monkeypatch.setattr("backend.services.model_zoo.get_model_manager", lambda: fake_manager)
    ol.get_reid_handle()
    assert fake_manager.load.call_count == 0
    assert fake_manager.preload.call_count == 0
```

`get_face_leg_handles()` (`backend/services/face_recognizer_loader.py:466`)
mirrors the same shape and is tested the same way. Wrong-weight bytes get the
same answer as no bytes — the sha pin is enforced _before_ `torch.load`, so a
hash-miss test asserts the load never ran.

Two rules these tests encode:

- **Never assert "loads on demand" for the face or re-ID legs.** Only the
  plate leg (`fast_alpr_loader.load_fast_alpr`) loads on demand; asserting it
  of the other two would let a change break residency silently.
- **The degradation must be observable.** A leg that cannot run has to bump
  `hsi_specialist_unavailable_total` with a bounded reason code
  (`weights_absent`, `package_absent`, `space_mismatch`, …) rather than return
  an empty result — see `docs/architecture/ai-pipeline-current-state.md` §2.3.
  `test_osnet_loader.py` asserts the counter, because it is the only signal
  that answers "has this leg ever run".

## VRAM and GPU-marked tests

GPU inference tests are marked `@pytest.mark.gpu` and are excluded from the
default run: `pyproject.toml:584` sets
`addopts = "-n 8 --dist=worksteal -v --strict-markers --tb=short -p randomly -m 'not gpu'"`.
Run them explicitly:

```bash
# GPU tests only (needs a CUDA host with the shipped weights)
uv run pytest -m gpu -o addopts='' --no-cov -q

# Everything except the GPU tier (the default)
uv run pytest ai/gateway/tests backend/tests/unit/services/test_osnet_loader.py
```

A GPU test that allocates real VRAM must release it, or the xdist worker it
runs in poisons every later test on that worker:

```python
import asyncio
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

WEIGHTS = Path("/models/zoo/osnet/osnet_ain_x1_0_msmt17.pth")


@pytest.mark.gpu
@pytest.mark.skipif(not WEIGHTS.exists(), reason="shipped weights not mounted")
def test_vram_returns_after_unload():
    from backend.services import osnet_loader as ol

    initial = torch.cuda.memory_allocated()
    handle = asyncio.run(ol.load_osnet_model(str(WEIGHTS)))
    assert torch.cuda.memory_allocated() > initial

    handle["model"] = None
    del handle
    torch.cuda.empty_cache()
    assert torch.cuda.memory_allocated() < initial + 10 * 1024 * 1024  # 10MB slack
```

`pytest.importorskip` rather than a bare `import torch` keeps the file
collectable on a CPU-only CI worker — collection failures under
`--strict-markers` fail the whole session, not just the one test.

## Testing the VLM path

`VlmAnalyzer` is tested against a mocked `VlmClient` so the assertions land on
what the analyzer decides, not on whether a llama.cpp server answered:

```python
@pytest.mark.asyncio
async def test_unreachable_vlm_still_writes_an_event(analyzer, batch):
    """A blind VLM must not lose the event: the row lands with a NULL score."""
    with patch.object(VlmClient, "assess", new_callable=AsyncMock, return_value=None):
        event = await analyzer.analyze_batch(batch)

    assert event is not None
    assert event.risk_score is None
    assert event.verification.verdict == "verification_failed"
```

Three invariants worth pinning when you touch this path (all of them are
silent-failure surfaces — a healthy pipeline and a stalled one look identical
from the console otherwise):

- **A verdict rejection clamps the score, it does not drop the event.**
- **`verdict=None` writes the Event row anyway**, with `risk_score` and
  `risk_level` NULL.
- **Broadcast happens last and best-effort**; a failed broadcast never undoes
  the commit. Test it by making the broadcast raise and asserting the row is
  still there.

`ai/gateway/tests/test_vlm_client.py` covers the client side: prompt fitting
to the served context slot, the base64 image budget, and the
`exceed_context_size_error` shape.

## Integration testing

Backend-side integration tests need postgres/redis only — the AI HTTP layer is
mocked, so nothing GPU-side has to be up:

```bash
podman-compose -f docker-compose.test.yml up -d
uv run pytest backend/tests/integration/services/test_osnet_loader.py -v
uv run pytest backend/tests/integration/services/test_fast_alpr_loader.py -v
```

For a real end-to-end check the shipped stack must actually be up, including
the VLM, which a plain `up -d` starts as part of the default set:

```bash
podman compose -f docker-compose.prod.yml up -d ai-vlm
curl -s http://127.0.0.1:8098/health | jq          # up is NOT the same as able to see
```

`ai-vlm` answers `200` on `/health` even when it was started without its
mmproj projector, i.e. text-only. Confirm multimodality before you trust a
green health check:

```bash
podman exec ai-vlm sh -c 'echo "MODEL_PATH=$MODEL_PATH"; echo "MMPROJ_PATH=$MMPROJ_PATH"'
podman logs ai-vlm 2>&1 | grep -i mmproj
```

Then triage from `events`, never from `alerts` — no event auto-creates an
Alert, so a stalled and a healthy-but-unnotified pipeline both show zero
notifications. The query that distinguishes them:

```sql
SELECT verdict, count(*), max(created_at)
FROM events e JOIN event_verifications ev ON ev.event_id = e.id
GROUP BY verdict ORDER BY max(created_at) DESC;
```

## Benchmarking

Mark benchmarks `@pytest.mark.benchmark` (registered in `pyproject.toml`) and
report distribution, not a single number — p95 is what the batch window
feels:

```python
import statistics
import time

import pytest
from PIL import Image


@pytest.mark.benchmark
@pytest.mark.gpu
def test_yolo26_postprocess_is_not_the_hot_path():
    """Postprocessing cost, Triton excluded. Guards the CPU side of the lane."""
    from ai.gateway.adapters.yolo26 import _postprocess_yolo

    raw = _raw_yolo_output(n_boxes=200)
    for _ in range(3):
        _postprocess_yolo(raw)
    times = []
    for _ in range(50):
        start = time.perf_counter()
        _postprocess_yolo(raw)
        times.append((time.perf_counter() - start) * 1000)

    print(f"\n  avg {statistics.mean(times):.1f}ms  p95 {statistics.quantiles(times, n=20)[18]:.1f}ms")
```

```bash
uv run pytest ai/gateway/tests -m benchmark -o addopts='' -s --no-cov
uv run pytest ai/gateway/tests -v -s --durations=10   # slowest tests, no plugin needed
```

Do not assert a wall-clock bound that depends on weights you may not have: a
benchmark that cannot run should skip, not fail the gate.

## Troubleshooting test failures

| Symptom                                         | Cause                                                           | Fix                                                                        |
| ----------------------------------------------- | --------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `ModuleNotFoundError: ai`                       | run from outside the repo root                                  | run pytest from the repo root; `testpaths` is repo-relative                |
| `DuplicateTimeseries` on a metrics import       | a module imported twice (package chain + flat path)             | let `ai/conftest.py` bind the flat name; do not re-insert `sys.path` hacks |
| GPU test "passes" on a CPU worker               | the marker was never applied, so `-m 'not gpu'` did not exclude | `@pytest.mark.gpu` is required on anything that allocates VRAM             |
| Specialist leg test passes but prod is degraded | the test patched the load to succeed                            | keep the "membership read never loads" test; it is the contract            |
| xdist worker dies mid-session                   | VRAM not released by a GPU test                                 | `empty_cache()` + drop the handle in teardown                              |

## Related Documentation

- [Testing Guide](testing.md) - General testing guide
- [TDD Workflow](testing-workflow.md) - Test-driven development patterns
- [Code Quality](code-quality.md) - Quality tools and standards
- `ai/gateway/AGENTS.md` - Gateway architecture
- [AI pipeline current state](../architecture/ai-pipeline-current-state.md) - what runs today, hop by hop

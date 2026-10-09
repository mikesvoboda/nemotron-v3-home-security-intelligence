# Model Zoo

The Model Zoo is the backend-side registry of the weights the backend process can load: the
specialist lookup weights (plates, faces, person re-ID) and the detector weights the gateway export
consumes. `models.yml` at the repo root is the single source of truth for the registry, and
`backend/services/model_zoo.py` builds it from that file at first use.

## Source Files

- **Registry + manager**: `backend/services/model_zoo.py`
- **Row source of truth**: `models.yml` (repo root; copied to `/app/models.yml` in the image)
- **Loaders wired by name**: `backend/services/osnet_loader.py`,
  `backend/services/face_recognizer_loader.py`, `backend/services/fast_alpr_loader.py`
- **Provisioning**: `ai/download_models.sh`

## How The Registry Is Built

`MODEL_ZOO` starts empty and `_init_model_zoo()` fills it from `models.yml`
(`backend/services/model_zoo.py:393`). A row reaches the registry only when both conditions hold:

1. `service` is `backend` or `both` (`backend/services/model_zoo.py:423`)
2. the row's `name` has an entry in `_LOADER_MAP` (`backend/services/model_zoo.py:334-356`)

Rows with no loader are logged at debug and skipped. A row that carries `sha256` gets that hash
bound into its loader with `functools.partial`, so the loader verifies the bytes before it loads
them (`backend/services/model_zoo.py:436-440`) — wrong bytes are the same answer as no bytes.

```python
@dataclass(slots=True)
class ModelConfig:
    name: str            # matches the models.yml row name
    path: str            # resolved against MODEL_ZOO_PATH
    category: str
    vram_mb: int
    load_fn: Callable[[str], Awaitable[Any]]
    enabled: bool = True       # models.yml `enabled`
    available: bool = False    # set True after a successful load
    priority: str = "medium"
    preload: bool = False      # models.yml `preload`
    never_evict: bool = False
```

`priority` and `never_evict` are read from the rows and carried on the config, and nothing consumes
them: the model zoo has no eviction pass (`backend/main.py:654-655`). Treat them as inert.

## What Is Loadable Today

These are the `models.yml` rows that survive both filters above. `enabled` governs the backend VRAM
slot, not whether the file is fetched (`ai/download_models.sh:37`, `:510`).

| Row name                   | service | enabled | preload | `vram_mb` | Loads as                                    |
| -------------------------- | ------- | ------- | ------- | --------- | ------------------------------------------- |
| `yolo26`                   | backend | false   | false   | 0         | `load_yolo_model` (weights feed the export) |
| `osnet-ain-x1-0`           | both    | true    | true    | 100       | `load_osnet_model` (person re-ID)           |
| `face-detector-scrfd`      | backend | true    | true    | 0         | `load_face_detector` (CPU onnxruntime)      |
| `face-recognizer`          | backend | true    | true    | 0         | `load_face_recognizer` (CPU onnxruntime)    |
| `threat-detection-yolov8n` | both    | true    | false   | 300       | `load_yolo_model`                           |
| `yolo11-face`              | both    | true    | false   | 200       | `load_yolo_model`                           |
| `yolo11-license-plate`     | both    | true    | false   | 300       | `load_yolo_model`                           |
| `fast-alpr`                | backend | true    | false   | 28        | `load_fast_alpr` (plate detect + OCR)       |
| `paddleocr`                | backend | true    | false   | 100       | `load_paddle_ocr`                           |
| `yolo26-general`           | backend | false   | false   | 400       | `load_yolo_model` (weights unreleased)      |

Three of these are the live legs the analyzer actually calls: `face-detector-scrfd` +
`face-recognizer` for `faces`, `fast-alpr` for `plates`, `osnet-ain-x1-0` for `person_reid`
(`backend/services/vlm_specialists.py:174,566,705`). The VLM is not in this registry at all —
`ai-vlm` is a separate container serving GGUF weights
(`docs/architecture/ai-orchestration/README.md`).

## Residency: The Boot Preload Sweep

The face and re-ID legs read a **resident** handle. `get_reid_handle()`
(`backend/services/osnet_loader.py:182`) and `get_face_leg_handles()`
(`backend/services/face_recognizer_loader.py:466`) look the handle up in the manager's loaded map
and return `None` when it is absent — they never load.

The sweep that places it runs at boot and is gated on the setting:

```python
# backend/main.py:1215
if settings.backend_model_preload:
    preload_names = select_preload_candidates(
        model_zoo, preload_enabled=settings.backend_model_preload
    )
    for model_name in preload_names:
        await model_manager.preload(model_name)
```

`select_preload_candidates()` is the single selection point: a row must be `enabled` **and** declare
`preload: true`, which selects exactly `osnet-ain-x1-0`, `face-detector-scrfd`, and
`face-recognizer`.

`BACKEND_MODEL_PRELOAD` ships **false** (`.env.example:231`, `docker-compose.prod.yml:494`) and
`setup.py:461-464` auto-sets it true only when detected VRAM is >= 24 GB. So on a smaller host, or
where the operator answered no, both legs answer `unavailable` on every event and nothing fails. The
plate leg is the exception — `load_fast_alpr`
(`backend/services/fast_alpr_loader.py:66`) loads on demand, so `plates` works without residency.

## Reference Counting

`ModelManager.load()` is a reference-counted context manager: a nested `load` of the same name
increments the count, and the model unloads only when the last reference exits
(`backend/services/model_zoo.py:736-777`).

```python
async with manager.load("fast-alpr") as alpr:
    async with manager.load("fast-alpr") as same:
        pass        # count decrements, model still resident
# last reference exited: unloaded, CUDA cache cleared
```

`preload()` and `unload()` are the explicit forms the boot sweep and shutdown use
(`backend/services/model_zoo.py:780,798`), and `reload()` re-loads a row under a named reason
(`oom`, `crash`, `manual`, `health_check`) recorded on `hsi_model_restarts_total`
(`backend/services/model_zoo.py:830`, `backend/core/metrics.py:2465,2477`).

## Path Resolution

`_resolve_model_path()` derives the runtime path with a fixed priority
(`backend/services/model_zoo.py:363`):

1. `runtime_path` — used verbatim (library sentinels such as `fast-alpr`)
2. `local_path` + `runtime_file` — directory model with a named weight file
3. `local_path` — directory model

`local_path` values are relative to `AI_MODELS_PATH` and start with `model-zoo/`; the base path
comes from `MODEL_ZOO_PATH`, default `/models/model-zoo` (`backend/services/model_zoo.py:313`). In
compose, `${AI_MODELS_PATH:-/export/ai_models}/model-zoo` mounts read-only at that path
(`docker-compose.prod.yml:467`).

## Provisioning

`ai/download_models.sh` fetches exactly the rows its selection rule picks and reports the rest:

- **Fetched**: `yolo26`, `osnet-ain-x1-0`, `threat-detection-yolov8n`, `yolo11-face`,
  `yolo11-license-plate` — 5 entries, 763 MB by `models.yml` `size_mb`
  (`ai/download_models.sh:480-489`).
- **Library-fetched at runtime, so excluded by rule**: `face-detector-scrfd`, `face-recognizer`
  (insightface/onnxruntime), `fast-alpr` (ONNX auto-download), `paddleocr`, and `yolo26-general`
  (weights not released) — `ai/download_models.sh:505-509`.
- **Never fetched**: the ai-vlm GGUF pair. The script creates `${AI_MODELS_PATH}/vlm` and stops
  there (`ai/download_models.sh:311-315`); placing `VLM_MODEL_PATH` and `VLM_MMPROJ_PATH` is
  operator config. Both files are one identity — without the mmproj the serve is text-only and every
  `vlm_assess` call degrades silently while events keep landing
  (`ai/download_models.sh:493-500`).

## CUDA Cache

Unloading runs the row's unloader and then clears the CUDA cache, because dropping the Python
reference does not return VRAM (`backend/services/model_zoo.py:704-725`).

## Status Reporting

`ModelManager.get_status()` is what the model-status surface reads
(`backend/api/routes/model_management.py`):

```python
status = manager.get_status()
# ModelManagerStatus: loaded model names, estimated VRAM held, and the registered rows.
```

## Thread Safety

Every mutating path takes the same `asyncio.Lock` (`backend/services/model_zoo.py:559`), so a
concurrent `load`, `preload`, and `get_status` from different request handlers cannot interleave a
half-loaded model into the map.

## Prometheus Metrics

```
hsi_model_load_duration_seconds{model}
hsi_model_restart_total{model, reason}
hsi_model_warmup_duration_seconds{model}
hsi_specialist_unavailable_total{specialist, reason}
```

`hsi_specialist_unavailable_total` (`backend/core/metrics.py:2394`) is the leg-level counter: a
degraded specialist's reason is deliberately kept **out** of the prompt text, so the bounded `reason`
code on this counter (`weights_absent`, `package_absent`, `space_mismatch`, `stage_error`, …) is
where the why lives.

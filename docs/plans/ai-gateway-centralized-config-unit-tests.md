# Unit Test Context: AI Gateway Centralized Configuration Infrastructure

This document provides context for implementing unit tests for the centralized Triton configuration infrastructure (models.yml → patch_triton_configs.py → config.pbtxt).

---

## 1. Infrastructure Overview

### Components

| Component | Path | Role |
|-----------|------|------|
| **models.yml** | `models.yml` (project root) | Single source of truth for `triton_name`, `triton_kind`, `device`, `device_env_var` |
| **patch_triton_configs.py** | `ai/gateway/patch_triton_configs.py` | Rewrites `instance_group` in each Triton `config.pbtxt` at container startup |
| **entrypoint.sh** | `ai/gateway/entrypoint.sh` | Exports device env vars, runs patch script, symlinks models, starts Triton |
| **config.pbtxt** | `ai/triton/model_repository/<model>/config.pbtxt` | Triton model configs (15 models) |

### Data Flow

```
models.yml
    ├── triton_name + triton_kind  →  patch_triton_configs.py  →  config.pbtxt (instance_group)
    └── device + device_env_var    →  entrypoint.sh (Python snippet)  →  env vars  →  model.py
```

---

## 2. Existing Test Patterns

### Test Layout

- **Backend unit tests**: `backend/tests/unit/` — mirror module structure (e.g. `setup_lib/test_model_downloader.py`)
- **Setup lib tests**: `backend/tests/unit/setup_lib/` — tests for `setup_lib/*`
- **Test runner**: `pytest` (pyproject.toml), `uv run pytest` from project root
- **Conventions**: Class-based grouping (`TestModelSpecConstants`), `TYPE_CHECKING` for imports, `unittest.mock` for patches

### Relevant Precedent

- **test_model_downloader.py** — Tests `setup_lib.model_downloader` which also consumes `models.yml`. Uses `from setup_lib.model_downloader import X` pattern.
- **test_gpu_config_service.py** — Tests YAML parsing with `yaml.safe_load` and fixture YAML strings.
- **models_config.py** — Shared loader `load_models_yaml()` used by model_downloader and model_zoo; patch_triton_configs uses its own env-based path.

### Where to Place New Tests

**Recommended**: `ai/gateway/tests/test_patch_triton_configs.py`  
- `ai/gateway/tests/` already exists (has `__init__.py`)  
- `pyproject.toml` testpaths include `ai/*/tests` — tests are auto-discovered  
- Colocated with `ai/gateway/patch_triton_configs.py`  
- Import: `from ai.gateway.patch_triton_configs import set_instance_group, collect_triton_configs, main`

---

## 3. patch_triton_configs.py — Test Targets

### 3.1 `set_instance_group(text, triton_kind, gpu_index=0) -> str`

**Pure function** — no I/O, ideal for unit tests.

| Scenario | Input | Expected |
|----------|-------|----------|
| **KIND_GPU** — CPU→GPU promotion | `kind: KIND_CPU` | `kind: KIND_GPU` + `gpus: [ 0 ]` inserted after kind |
| **KIND_GPU** — count normalization | `count: 2` | `count: 1` |
| **KIND_GPU** — remove parameters block | `parameters { key: "intra_op_thread_count" ... }` | Block omitted |
| **KIND_GPU** — drop existing gpus line | `gpus: [ 0 ]` (duplicate) | Single `gpus: [ 0 ]` (no duplicate) |
| **KIND_CPU** — leave count unchanged | `count: 2` | `count: 2` |
| **KIND_CPU** — remove gpus line | `gpus: [ 0 ]` | Line removed |
| **KIND_CPU** — preserve parameters block | `parameters { ... }` | Block preserved |
| **Idempotent** | Already correct KIND_GPU | No change |
| **Comment preservation** | `kind: KIND_CPU  # 14MB model` | `kind: KIND_CPU  # 14MB model` (comment kept) |
| **Nested parameters** | `parameters { key: "x" value: { string_value: "y" } }` | Correct depth tracking, block removed for GPU |

**Minimal config.pbtxt fixture** (sufficient for `set_instance_group`):

```text
name: "test_model"
backend: "onnxruntime"
instance_group [
  {
    count: 2
    kind: KIND_CPU
    rate_limiter { resources [ { name: "global" count: 1 } ] priority: 3 }
  }
]
```

### 3.2 `collect_triton_configs(models: list[dict]) -> list[tuple[str, str]]`

**Pure function** — parses model list into `(triton_name, triton_kind)` pairs.

| Scenario | Input | Expected |
|----------|-------|----------|
| **Simple form** | `{triton_name: "clip", triton_kind: "KIND_GPU"}` | `[("clip", "KIND_GPU")]` |
| **triton_models list** | `{triton_models: [{triton_name: "clip", triton_kind: "KIND_GPU"}, {triton_name: "clip_text", triton_kind: "KIND_CPU"}]}` | `[("clip", "KIND_GPU"), ("clip_text", "KIND_CPU")]` |
| **Both forms** | Model has both `triton_name` and `triton_models` | `triton_models` entries first, then top-level (implementation order) |
| **Skip incomplete** | `{triton_name: "x"}` (no triton_kind) | Not included |
| **Skip incomplete** | `{triton_kind: "KIND_GPU"}` (no triton_name) | Not included |
| **Empty list** | `[]` | `[]` |
| **Type coercion** | `triton_name: 123` (int) | `("123", ...)` (str) |

### 3.3 `main()` — Integration-style

| Scenario | Setup | Expected |
|----------|-------|----------|
| **models.yml missing** | `MODELS_YAML_PATH` → non-existent file | Prints warning, returns (exit 0) |
| **Empty models** | models.yml with no triton_name/triton_kind | Prints "No triton_name/triton_kind entries", returns |
| **Config missing** | triton_name points to non-existent `config.pbtxt` | Prints WARN, skips, continues |
| **Patch applied** | Config differs from models.yml | Writes file, prints "patched" |
| **Already in sync** | Config matches models.yml | No write, prints "verified" |
| **PyYAML missing** | `yaml` import fails | Prints to stderr, `sys.exit(0)` |

**Test approach**: Use `tmp_path` for a fake `TRITON_MODEL_REPOSITORY` and `MODELS_YAML_PATH`, create minimal `models.yml` and `config.pbtxt` fixtures, run `main()`, assert file contents and/or capsys.

---

## 4. models.yml — Validation Tests

These ensure the configuration file stays consistent with the Triton model repository.

| Test | Assertion |
|------|-----------|
| **All triton_name map to existing config.pbtxt** | For each `triton_name` / `triton_models` entry, `ai/triton/model_repository/<name>/config.pbtxt` exists |
| **triton_kind is valid** | Each `triton_kind` is `KIND_GPU` or `KIND_CPU` |
| **No duplicate triton_name** | No model name appears more than once across all entries |
| **Python backends have device + device_env_var** | Models with `device_env_var` also have `device` |
| **triton_models entries complete** | Each item in `triton_models` has both `triton_name` and `triton_kind` |

**Data source**: `setup_lib.models_config.load_models_yaml()` or direct `yaml.safe_load` of `models.yml`.

---

## 5. Config.pbtxt ↔ models.yml Consistency

| Test | Purpose |
|------|---------|
| **Round-trip sync** | For each model in models.yml with triton_name/triton_kind, run `set_instance_group` on the actual config.pbtxt; assert output equals input (idempotent when already correct) |
| **Patch then verify** | Take a config with `KIND_CPU`, patch to `KIND_GPU`, assert `kind: KIND_GPU` and `gpus: [ 0 ]` present |

---

## 6. Dependencies and Environment

- **PyYAML**: Required for `patch_triton_configs`; tests will need it (already in pyproject.toml via other deps).
- **No Triton runtime**: Tests are pure Python; no `tritonserver` or GPU needed.
- **Paths**: `TRITON_MODEL_REPOSITORY` and `MODELS_YAML_PATH` are read from env; tests should override with `tmp_path` or `monkeypatch`.

---

## 7. Suggested Test File Structure

```text
ai/gateway/tests/
├── __init__.py          # Already exists
├── conftest.py          # Optional: shared fixtures (minimal config.pbtxt, models.yml snippets)
└── test_patch_triton_configs.py
    ├── TestSetInstanceGroup       # Pure function tests
    ├── TestCollectTritonConfigs   # Pure function tests
    ├── TestMain                   # main() with tmp_path, capsys
    └── TestModelsYamlConsistency  # models.yml validation (can be separate file)
```

---

## 8. Example Test Snippets

### set_instance_group — CPU to GPU

```python
def test_set_instance_group_cpu_to_gpu_adds_gpus_line() -> None:
    from ai.gateway.patch_triton_configs import set_instance_group
    config = """
name: "test"
instance_group [
  { count: 2
    kind: KIND_CPU
  }
]
"""
    result = set_instance_group(config, "KIND_GPU")
    assert "kind: KIND_GPU" in result
    assert "gpus: [ 0 ]" in result
    assert "count: 1" in result
```

### collect_triton_configs — triton_models list

```python
def test_collect_triton_configs_triton_models_list() -> None:
    from ai.gateway.patch_triton_configs import collect_triton_configs
    models = [{
        "name": "siglip",
        "triton_models": [
            {"triton_name": "clip", "triton_kind": "KIND_GPU"},
            {"triton_name": "clip_text", "triton_kind": "KIND_CPU"},
        ],
    }]
    assert collect_triton_configs(models) == [
        ("clip", "KIND_GPU"),
        ("clip_text", "KIND_CPU"),
    ]
```

### main() with tmp_path

```python
def test_main_patches_config_when_out_of_sync(tmp_path: Path, monkeypatch) -> None:
    from ai.gateway import patch_triton_configs
    (tmp_path / "models.yml").write_text("""
models:
  - name: m1
    triton_name: test_model
    triton_kind: KIND_GPU
""")
    repo = tmp_path / "repo"
    (repo / "test_model").mkdir(parents=True)
    (repo / "test_model" / "config.pbtxt").write_text("""
name: "test_model"
instance_group [ { count: 2
  kind: KIND_CPU
} ]
""")
    monkeypatch.setenv("MODELS_YAML_PATH", str(tmp_path / "models.yml"))
    monkeypatch.setenv("TRITON_MODEL_REPOSITORY", str(repo))
    patch_triton_configs.main()
    content = (repo / "test_model" / "config.pbtxt").read_text()
    assert "kind: KIND_GPU" in content
    assert "gpus: [ 0 ]" in content
```

---

## 9. References

- `ai/gateway/patch_triton_configs.py` — implementation
- `models.yml` — schema and triton_* fields (lines 46–55)
- `backend/tests/unit/setup_lib/test_model_downloader.py` — test style
- `setup_lib/models_config.py` — `load_models_yaml()` for validation tests

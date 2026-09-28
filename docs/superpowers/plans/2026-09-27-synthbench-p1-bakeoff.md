# Synthbench P1 — Model Bake-off on the GB300 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the owner-approved generator slate through a fixed set of hard security-camera prompts on the GB300. Measure adherence, identity drift, plate legibility, speed and VRAM, and propose the pick for every model slot (spec §3.2) for the owner to approve into spec rev 2.

**Architecture:** Four durable modules under a new `synthbench/generate/` package carry into P3:

- a sha256-pinned weights manifest and a symlink "farm" in ComfyUI's layout;
- a GPU window that stops the flagship vLLM and always restores it;
- a pinned ComfyUI container run with rootless podman;
- a ComfyUI HTTP client with an offline graph validator and one API-graph builder per model.

A throwaway spike under `synthbench/spikes/p1_bakeoff/` drives the bake-off, measures the results with models independent of the pipeline, renders a contact sheet for the owner to rate, and writes an aggregate report.

**Tech Stack:**

- Python 3.14 (typed; ruff and mypy clean) and `httpx`.
- ComfyUI v0.37.0 on `nvcr.io/nvidia/pytorch:26.08-py3` (arm64), run with rootless podman plus CDI `nvidia.com/gpu=all`.
- `huggingface_hub` for weights (`HF_HOME=/export/models`).
- Measurement: OWLv2 (`transformers`), facenet-pytorch (VGGFace2) and EasyOCR, all inside the container.

**Spec:** `docs/superpowers/specs/2026-09-27-synthetic-benchmark-generation-design.md`. Read §3 (the generation stack: §3.1 runtime, §3.2 slots, §3.6 GPU window, §3.7 bake-off, §3.8 content rules) and §9.1 R1-R3.

## Global Constraints

- Every function has type hints. `mypy`, `ruff check` and `ruff format` are clean. Line length is 100. TDD applies to the durable code in `synthbench/generate/`. The spike (`synthbench/spikes/`) unit-tests only its pure logic.
- **Nothing under `synthbench/generate/` imports `backend`** (spec §7.1). A test enforces this (Task 1).
- **Tests live under `backend/tests/unit/synthbench/`.** CI runs only `backend/tests/unit/`. Tests must be GPU-free and fast (pytest-timeout is 5 s; `-p randomly`). Live GPU checks are CLI steps, never `@pytest.mark.gpu`: the CI GPU runner runs that marker and has no ComfyUI.
- **Storage:** weights live in the HF cache under `HF_HOME=/export/models`. Generated media, window state and caches go under `SYNTHBENCH_ROOT=/export/synthbench`. **Never write to the root filesystem** (it is 96% full), and never use `~/.cache`.
- **Ports:** ComfyUI's host port comes from `SYNTHBENCH_COMFYUI_PORT` (default `8188`, documented in `.env.example`). It binds `127.0.0.1` only.
- **Flagship:** container `dgx-inference-vllm-1` on the **rootful docker** daemon, with restart policy `unless-stopped`. Its healthcheck `StartPeriod` is 30 min, so the restore timeout is 45 min.
  - Stop and start it only with `docker stop` / `docker start`. **Never run `docker compose up`** on that stack: it would restart the stopped Cosmos container.
  - "Healthy" means docker health `healthy` **and** `GET http://127.0.0.1:8000/v1/models` returns 200.
  - Our own containers use **podman**. Never debug them through `docker`.
- **Only the controller opens GPU windows** (Task 8). Implementer subagents never stop the flagship. In Tasks 3 and 5 they may run ComfyUI beside the flagship, which leaves 48.9 GiB free (probed 2026-09-27).
- ComfyUI is pinned to `v0.37.0`. The base image is `nvcr.io/nvidia/pytorch:26.08-py3`. **Never let pip replace the base image's torch, torchvision or triton.**
- Weights are pinned to exact commits and checked by sha256 (`synthbench/generate/manifests/p1-slate.json`: 33 rows, 30 unique files, 291 GB). Two files are named `vae/flux2-vae.safetensors` but differ in content (FLUX.2 [dev] vs Klein), so link names are prefixed per model (Task 1).
- Measurement models must not be models the pipeline runs. OWLv2, facenet (VGGFace2) and EasyOCR appear nowhere in `backend/` or `ai/` (verified 2026-09-27).
- Content rules (spec §3.8): identities are generated from scratch, never from photos of real people. Threat content is realistic and non-graphic.
- Commits use conventional subjects and end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Git hooks are not installed here: run `uvx pre-commit run --files <changed files>` before each commit and re-stage what it fixes. Semgrep's `pkg_resources` crash is a known environment problem. Never use `--no-verify`.

**Deviations from spec §7.1, to record in spec rev 2:**

1. Tests live under `backend/tests/unit/synthbench/`, not `synthbench/tests/`, because CI runs `pytest backend/tests/unit/` only.
2. CI coverage stays `--cov=backend`, because its denominator is pinned by `scripts/test_coverage_denominator.py`. Each task instead measures `synthbench` coverage locally with `--cov=synthbench`. Widening CI coverage is a follow-up.

## File Structure

| File                                                                                                                              | Responsibility                                                                     |
| --------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `synthbench/__init__.py`, `synthbench/AGENTS.md`                                                                                  | package root; agent guide (purpose, layout, rules)                                 |
| `synthbench/generate/__init__.py`                                                                                                 | generation-stack package (no `backend` imports)                                    |
| `synthbench/generate/manifests/p1-slate.json`                                                                                     | **already committed with this plan**: the resolved, pinned P1 weights              |
| `synthbench/generate/weights.py`                                                                                                  | manifest loading, sha256 fetch, symlink farm, `extra_model_paths` text; CLI `sync` |
| `synthbench/generate/window.py`                                                                                                   | GPU window context manager and CLI (`run`, `restore`, `status`)                    |
| `synthbench/generate/comfy/__init__.py`                                                                                           | ComfyUI subpackage                                                                 |
| `synthbench/generate/comfy/Containerfile`, `extra_model_paths.yaml`                                                               | the pinned renderer image; the farm mapping it loads                               |
| `synthbench/generate/comfy/serve.py`                                                                                              | `podman build/run/stop` arguments, readiness wait; CLI `build`, `up`, `down`       |
| `synthbench/generate/comfy/client.py`                                                                                             | ComfyUI HTTP client (upload, queue, wait, outputs, download)                       |
| `synthbench/generate/comfy/validate.py`                                                                                           | offline validation of an API graph against `/object_info`                          |
| `synthbench/generate/comfy/graphs.py`                                                                                             | one API-graph builder per model; the three builder registries                      |
| `synthbench/generate/comfy/snapshot.py`, `object_info.v0.37.0.json`                                                               | captures `/object_info` filtered to the node types the builders use                |
| `synthbench/generate/comfy/smoke.py`                                                                                              | live smoke CLI: runs each registered builder once at low resolution                |
| `synthbench/spikes/p1_bakeoff/{__init__,cases,plan,run,measure,sheet,report}.py`                                                  | the throwaway bake-off                                                             |
| `backend/tests/unit/synthbench/...`                                                                                               | all tests (see each task)                                                          |
| `.github/workflows/ci.yml`, `.pre-commit-config.yaml`, `pyproject.toml`, `.env.example`, `docs/reference/config/env-reference.md` | wiring (Task 1)                                                                    |
| `docs/benchmarks/synthbench/p1-bakeoff.md`                                                                                        | the aggregate bake-off report (Task 8)                                             |

---

### Task 1: Package skeleton, wiring, and the weights farm

**Files:**

- Create: `synthbench/__init__.py`, `synthbench/AGENTS.md`, `synthbench/generate/__init__.py`, `synthbench/generate/comfy/__init__.py`, `synthbench/generate/weights.py`, `synthbench/generate/comfy/extra_model_paths.yaml`
- Create: `backend/tests/unit/synthbench/__init__.py`, `backend/tests/unit/synthbench/test_weights.py`, `backend/tests/unit/synthbench/test_import_rule.py`
- Modify: `.github/workflows/ci.yml` (the `Mypy` step, currently `uv run mypy backend/ --ignore-missing-imports`), `.pre-commit-config.yaml` (the `mypy` hook's `files: ^backend/`), `pyproject.toml` (`[tool.ruff.lint.per-file-ignores]`), `.env.example`, `docs/reference/config/env-reference.md`
- Already present: `synthbench/generate/manifests/p1-slate.json` (committed with this plan; do not edit it)

**Interfaces:**

- Produces:
  - `WeightFile(model, category, repo, revision, path, size, sha256)` (frozen) with property `.name`
  - `CATEGORIES: tuple[str, ...]`
  - `load_manifest(path: Path) -> list[WeightFile]`
  - `link_names(files: Iterable[WeightFile]) -> dict[WeightFile, str]`
  - `unique_by_sha(files) -> list[WeightFile]`
  - `sha256_of(path: Path) -> str`
  - `fetch(files, download: Callable[[WeightFile], Path]) -> dict[str, Path]` (sha → local path)
  - `hf_download(f: WeightFile) -> Path`
  - `build_farm(files: Sequence[WeightFile], local: dict[str, Path], farm_root: Path) -> list[Path]`
  - `extra_model_paths_yaml(farm_root: Path) -> str`
  - `main(argv, *, download=hf_download) -> int` (CLI `sync`)
  - Errors: `ManifestError`, `ChecksumError`.
- Farm root on the GB300: `/export/models/comfyui`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/synthbench/__init__.py`: empty file.

`backend/tests/unit/synthbench/test_import_rule.py`:

```python
"""Spec §7.1: nothing under synthbench/generate imports backend."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def _imported_modules(path: Path) -> Iterator[str]:
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module


def test_generate_never_imports_backend() -> None:
    offenders = [
        f"{path.relative_to(REPO_ROOT)}: {module}"
        for path in sorted((REPO_ROOT / "synthbench" / "generate").rglob("*.py"))
        for module in _imported_modules(path)
        if module == "backend" or module.startswith("backend.")
    ]
    assert offenders == []
```

`backend/tests/unit/synthbench/test_weights.py`:

```python
"""synthbench.generate.weights: pinned manifest, sha256 fetch, ComfyUI symlink farm."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from synthbench.generate import weights as w

REPO_ROOT = Path(__file__).resolve().parents[4]
P1_SLATE = REPO_ROOT / "synthbench" / "generate" / "manifests" / "p1-slate.json"
REV = "a" * 40


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _wf(model: str, category: str, path: str, data: bytes, repo: str = "org/repo") -> w.WeightFile:
    return w.WeightFile(
        model=model, category=category, repo=repo, revision=REV, path=path,
        size=len(data), sha256=_sha(data),
    )


def _write_manifest(tmp_path: Path, rows: list[dict[str, object]], version: int = 1) -> Path:
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"schema_version": version, "files": rows}))
    return path


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "model": "m", "category": "vae", "repo": "org/r", "revision": REV,
        "path": "vae/x.safetensors", "size": 3, "sha256": _sha(b"abc"),
    }
    row.update(overrides)
    return row


class TestLoadManifest:
    def test_round_trips(self, tmp_path: Path) -> None:
        files = w.load_manifest(_write_manifest(tmp_path, [_row()]))
        assert files == [w.WeightFile(**_row())]  # type: ignore[arg-type]
        assert files[0].name == "x.safetensors"

    def test_the_committed_p1_slate_loads(self) -> None:
        files = w.load_manifest(P1_SLATE)
        assert len(files) == 33
        assert len(w.unique_by_sha(files)) == 30
        assert {f.model for f in files} == {
            "flux2-dev", "qwen-image-2.1", "hidream-i1-full", "z-image-turbo",
            "flux2-klein-4b", "ideogram-4", "ltx-2.5", "wan2.2-i2v",
        }

    @pytest.mark.parametrize(
        ("field", "value", "message"),
        [
            ("category", "checkpoints", "unknown category"),
            ("sha256", "abc", "sha256"),
            ("revision", "main", "revision"),
            ("size", 0, "size"),
        ],
    )
    def test_rejects_malformed_rows(
        self, tmp_path: Path, field: str, value: object, message: str
    ) -> None:
        with pytest.raises(w.ManifestError, match=message):
            w.load_manifest(_write_manifest(tmp_path, [_row(**{field: value})]))

    def test_rejects_an_unknown_schema_version(self, tmp_path: Path) -> None:
        with pytest.raises(w.ManifestError, match="schema_version"):
            w.load_manifest(_write_manifest(tmp_path, [_row()], version=2))


class TestLinkNames:
    def test_unique_names_stay_bare(self) -> None:
        a = _wf("m1", "vae", "vae/a.safetensors", b"a")
        assert w.link_names([a]) == {a: "a.safetensors"}

    def test_same_name_same_content_shares_the_bare_name(self) -> None:
        a = _wf("m1", "vae", "x/ae.safetensors", b"same")
        b = _wf("m2", "vae", "y/ae.safetensors", b"same", repo="org/other")
        assert set(w.link_names([a, b]).values()) == {"ae.safetensors"}

    def test_same_name_different_content_is_prefixed_by_model(self) -> None:
        a = _wf("m1", "vae", "vae/v.safetensors", b"one")
        b = _wf("m2", "vae", "vae/v.safetensors", b"two", repo="org/other")
        assert w.link_names([a, b]) == {a: "m1--v.safetensors", b: "m2--v.safetensors"}

    def test_the_p1_slate_prefixes_only_the_flux2_vaes(self) -> None:
        names = w.link_names(w.load_manifest(P1_SLATE))
        assert sorted(n for n in names.values() if "--" in n) == [
            "flux2-dev--flux2-vae.safetensors",
            "flux2-klein-4b--flux2-vae.safetensors",
            "ideogram-4--flux2-vae.safetensors",
        ]


class TestFetch:
    def test_downloads_each_unique_file_once_and_verifies_it(self, tmp_path: Path) -> None:
        a = _wf("m1", "vae", "x/ae.safetensors", b"same")
        b = _wf("m2", "vae", "y/ae.safetensors", b"same", repo="org/other")
        calls: list[str] = []

        def download(f: w.WeightFile) -> Path:
            calls.append(f.repo)
            path = tmp_path / f.repo.replace("/", "_")
            path.write_bytes(b"same")
            return path

        local = w.fetch([a, b], download)
        assert calls == ["org/repo"]
        assert local == {a.sha256: tmp_path / "org_repo"}

    def test_a_checksum_mismatch_raises(self, tmp_path: Path) -> None:
        a = _wf("m1", "vae", "vae/a.safetensors", b"expected")

        def download(_f: w.WeightFile) -> Path:
            path = tmp_path / "bad"
            path.write_bytes(b"tampered")
            return path

        with pytest.raises(w.ChecksumError, match="vae/a.safetensors"):
            w.fetch([a], download)


class TestBuildFarm:
    def test_links_resolve_to_the_cached_files(self, tmp_path: Path) -> None:
        a = _wf("m1", "vae", "vae/v.safetensors", b"one")
        b = _wf("m2", "vae", "vae/v.safetensors", b"two", repo="org/other")
        cache_a, cache_b = tmp_path / "blob_a", tmp_path / "blob_b"
        cache_a.write_bytes(b"one")
        cache_b.write_bytes(b"two")
        farm = tmp_path / "farm"
        w.build_farm([a, b], {a.sha256: cache_a, b.sha256: cache_b}, farm)
        assert (farm / "vae" / "m1--v.safetensors").resolve() == cache_a.resolve()
        assert (farm / "vae" / "m2--v.safetensors").read_bytes() == b"two"

    def test_is_idempotent_and_repairs_a_wrong_link(self, tmp_path: Path) -> None:
        a = _wf("m1", "loras", "l/x.safetensors", b"x")
        right, wrong = tmp_path / "right", tmp_path / "wrong"
        right.write_bytes(b"x")
        wrong.write_bytes(b"?")
        farm = tmp_path / "farm"
        (farm / "loras").mkdir(parents=True)
        (farm / "loras" / "x.safetensors").symlink_to(wrong)
        first = w.build_farm([a], {a.sha256: right}, farm)
        second = w.build_farm([a], {a.sha256: right}, farm)
        assert first == second == [farm / "loras" / "x.safetensors"]
        assert (farm / "loras" / "x.safetensors").resolve() == right.resolve()


class TestExtraModelPaths:
    def test_lists_every_category_under_the_farm(self) -> None:
        text = w.extra_model_paths_yaml(Path("/export/models/comfyui"))
        assert text.startswith("synthbench:\n    base_path: /export/models/comfyui\n")
        for category in w.CATEGORIES:
            assert f"    {category}: {category}/\n" in text

    def test_the_committed_container_yaml_matches(self) -> None:
        committed = REPO_ROOT / "synthbench" / "generate" / "comfy" / "extra_model_paths.yaml"
        assert committed.read_text() == w.extra_model_paths_yaml(Path("/export/models/comfyui"))


class TestSyncCli:
    def test_sync_fetches_and_builds_the_farm(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path, [_row(), _row(repo="org/gated")])
        blob = tmp_path / "blob"
        blob.write_bytes(b"abc")
        farm = tmp_path / "farm"
        code = w.main(
            ["sync", "--manifest", str(manifest), "--farm-root", str(farm),
             "--skip-repo", "org/gated"],
            download=lambda _f: blob,
        )
        assert code == 0
        assert (farm / "vae" / "x.safetensors").resolve() == blob.resolve()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest backend/tests/unit/synthbench/ -n0 -q`
Expected: `test_weights.py` errors with `ModuleNotFoundError: No module named 'synthbench'`. `test_import_rule.py` passes vacuously once the directory exists. That's fine: it guards every later task.

- [ ] **Step 3: Create the package skeleton**

`synthbench/__init__.py`:

```python
"""Synthetic benchmark generation (docs/superpowers/specs/2026-09-27-synthetic-benchmark-generation-design.md)."""
```

`synthbench/generate/__init__.py`:

```python
"""The generation stack (spec §3). Never imports backend (spec §7.1)."""
```

`synthbench/generate/comfy/__init__.py`:

```python
"""The pinned ComfyUI renderer: container, client, graph builders (spec §3.1-§3.2)."""
```

`synthbench/AGENTS.md`:

```markdown
# synthbench — Agent Guide

## Purpose

Synthetic benchmark generation: spec `docs/superpowers/specs/2026-09-27-synthetic-benchmark-generation-design.md`.
Phase plans live in `docs/superpowers/plans/2026-09-27-synthbench-*.md`.

## Layout

| Path                                          | What                                                                               |
| --------------------------------------------- | ---------------------------------------------------------------------------------- |
| `generate/weights.py` + `generate/manifests/` | pinned, sha256-verified weights; ComfyUI symlink farm (`/export/models/comfyui`)   |
| `generate/window.py`                          | GPU window: stops the flagship vLLM, ALWAYS restores it                            |
| `generate/comfy/`                             | ComfyUI container (podman), HTTP client, graph validator, per-model graph builders |
| `spikes/p1_bakeoff/`                          | throwaway P1 bake-off harness (not a pattern to copy)                              |

## Rules

- `synthbench/generate/**` never imports `backend` (test: `backend/tests/unit/synthbench/test_import_rule.py`).
- Tests live in `backend/tests/unit/synthbench/` (CI runs only `backend/tests/unit/`); no GPU in tests.
- Storage: weights in `HF_HOME=/export/models`, outputs in `SYNTHBENCH_ROOT=/export/synthbench`; never the root fs.
- Only `python -m synthbench.generate.window run -- ...` may stop the flagship; never `docker compose up` on the dgx-inference stack.
- Our containers are podman; the flagship is rootful docker.
```

- [ ] **Step 4: Implement `synthbench/generate/weights.py`**

```python
"""Pinned, sha256-verified model weights for the ComfyUI renderer (spec §3.1).

A manifest (JSON) names every file a workflow needs: model, ComfyUI folder
category, Hugging Face repo, pinned revision, path, size and LFS sha256.
`fetch` downloads into the HF cache under HF_HOME (/export/models on the
GB300 - the root filesystem is nearly full, so never ~/.cache) and verifies
every file's sha256. `build_farm` exposes the cached files in ComfyUI's
folder layout (<farm>/<category>/<link name>) as symlinks, so nothing is
stored twice. The container mounts /export/models at the same path, so the
links resolve inside it too.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

CATEGORIES = ("diffusion_models", "latent_upscale_models", "loras", "text_encoders", "vae")
_HEX = frozenset("0123456789abcdef")


class ManifestError(ValueError):
    """The manifest is malformed."""


class ChecksumError(RuntimeError):
    """A downloaded file's sha256 does not match the manifest."""


@dataclass(frozen=True)
class WeightFile:
    model: str
    category: str
    repo: str
    revision: str
    path: str
    size: int
    sha256: str

    @property
    def name(self) -> str:
        return self.path.rsplit("/", 1)[-1]


def load_manifest(path: Path) -> list[WeightFile]:
    data = json.loads(path.read_text())
    if data.get("schema_version") != 1:
        raise ManifestError(f"{path}: unsupported schema_version {data.get('schema_version')!r}")
    files = [WeightFile(**row) for row in data["files"]]
    for f in files:
        where = f"{f.repo}:{f.path}"
        if f.category not in CATEGORIES:
            raise ManifestError(f"{where}: unknown category {f.category!r}")
        if len(f.sha256) != 64 or not set(f.sha256) <= _HEX:
            raise ManifestError(f"{where}: sha256 must be 64 lowercase hex characters")
        if len(f.revision) != 40 or not set(f.revision) <= _HEX:
            raise ManifestError(f"{where}: revision must be a pinned 40-character commit")
        if f.size <= 0:
            raise ManifestError(f"{where}: size must be positive")
    return files


def link_names(files: Iterable[WeightFile]) -> dict[WeightFile, str]:
    """ComfyUI file name per manifest row: the bare file name, unless another
    row in the same category has that name with DIFFERENT content - then
    `<model>--<name>`, so a workflow can never load the wrong file."""
    rows = list(files)
    contents: dict[tuple[str, str], set[str]] = {}
    for f in rows:
        contents.setdefault((f.category, f.name), set()).add(f.sha256)
    return {
        f: f.name if len(contents[(f.category, f.name)]) == 1 else f"{f.model}--{f.name}"
        for f in rows
    }


def unique_by_sha(files: Iterable[WeightFile]) -> list[WeightFile]:
    """One row per distinct content; the first row wins."""
    seen: dict[str, WeightFile] = {}
    for f in files:
        seen.setdefault(f.sha256, f)
    return list(seen.values())


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 24), b""):
            digest.update(block)
    return digest.hexdigest()


Downloader = Callable[[WeightFile], Path]


def fetch(files: Iterable[WeightFile], download: Downloader) -> dict[str, Path]:
    """Download every distinct file once and verify it; returns sha256 -> local path."""
    local: dict[str, Path] = {}
    for f in unique_by_sha(files):
        path = download(f)
        got = sha256_of(path)
        if got != f.sha256:
            raise ChecksumError(f"{f.repo}:{f.path}: sha256 {got} != manifest {f.sha256}")
        local[f.sha256] = path
    return local


def hf_download(f: WeightFile) -> Path:
    from huggingface_hub import hf_hub_download  # noqa: PLC0415 - heavy import, CLI path only

    return Path(hf_hub_download(f.repo, f.path, revision=f.revision))


def build_farm(files: Sequence[WeightFile], local: dict[str, Path], farm_root: Path) -> list[Path]:
    """Symlink every row into <farm_root>/<category>/<link name>; idempotent, repairs wrong links."""
    names = link_names(files)
    links: list[Path] = []
    for f in files:
        target = local[f.sha256]
        link = farm_root / f.category / names[f]
        link.parent.mkdir(parents=True, exist_ok=True)
        if not (link.is_symlink() and link.resolve() == target.resolve()):
            if link.is_symlink() or link.exists():
                link.unlink()
            link.symlink_to(target)
        links.append(link)
    return list(dict.fromkeys(links))


def extra_model_paths_yaml(farm_root: Path) -> str:
    """ComfyUI's extra_model_paths.yaml pointing every category at the farm."""
    lines = ["synthbench:", f"    base_path: {farm_root}"]
    lines += [f"    {category}: {category}/" for category in CATEGORIES]
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None, *, download: Downloader = hf_download) -> int:
    parser = argparse.ArgumentParser(prog="python -m synthbench.generate.weights")
    parser.add_argument("command", choices=["sync"])
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--farm-root", type=Path, default=Path("/export/models/comfyui"))
    parser.add_argument(
        "--skip-repo", action="append", default=[], help="leave a repo out (e.g. still gated)"
    )
    args = parser.parse_args(argv)
    skip = set(args.skip_repo)
    files = [f for f in load_manifest(args.manifest) if f.repo not in skip]
    local = fetch(files, download)
    links = build_farm(files, local, args.farm_root)
    sys.stdout.write(f"verified {len(local)} files; {len(links)} links under {args.farm_root}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`synthbench/generate/comfy/extra_model_paths.yaml`: write exactly the output of `extra_model_paths_yaml(Path("/export/models/comfyui"))`:

```yaml
synthbench:
  base_path: /export/models/comfyui
  diffusion_models: diffusion_models/
  latent_upscale_models: latent_upscale_models/
  loras: loras/
  text_encoders: text_encoders/
  vae: vae/
```

(Prettier must not reformat this file. If it does, add `synthbench/generate/comfy/extra_model_paths.yaml` to `.prettierignore` and say so in your report.)

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest backend/tests/unit/synthbench/ -n0 -q --cov=synthbench --cov-report=term-missing`
Expected: all pass. `weights.py` coverage is at least 90%; only the `hf_download` body and `__main__` may be missed.

- [ ] **Step 6: Wire CI, hooks, lint and env docs**

- `.github/workflows/ci.yml`: change the Mypy step's command to `uv run mypy backend/ synthbench/ --ignore-missing-imports`.
- `.pre-commit-config.yaml`: change the `mypy` hook's `files: ^backend/` to `files: ^(backend|synthbench)/`.
- `pyproject.toml`, `[tool.ruff.lint.per-file-ignores]`: add the entry below.

  ```toml
  "synthbench/**/*.py" = [
      "S603",  # subprocess with a fixed argv list (podman/docker/nvidia-smi); never a shell
      "S607",  # those tools are resolved from PATH on purpose
  ]
  ```

- `.env.example`: add a section at the end.

  ```bash

  # =============================================================================
  # SYNTHBENCH (synthetic benchmark generation)
  # docs/superpowers/specs/2026-09-27-synthetic-benchmark-generation-design.md
  # =============================================================================
  # Host port of the ComfyUI renderer (bound to 127.0.0.1 only)
  SYNTHBENCH_COMFYUI_PORT=8188
  # Generated media, GPU-window state and caches. Keep this OFF the root filesystem.
  SYNTHBENCH_ROOT=/export/synthbench
  ```

- `docs/reference/config/env-reference.md`: add a `## Synthetic Benchmark` section (before the final `---` of the file, in the style of the other tables).

  ```markdown
  ## Synthetic Benchmark

  | Variable                  | Required | Default              | Description                                                   |
  | ------------------------- | -------- | -------------------- | ------------------------------------------------------------- |
  | `SYNTHBENCH_COMFYUI_PORT` | No       | `8188`               | Host port of the synthbench ComfyUI renderer (127.0.0.1 only) |
  | `SYNTHBENCH_ROOT`         | No       | `/export/synthbench` | Generated media, GPU-window state and caches                  |
  ```

Run: `uv run mypy synthbench/ --ignore-missing-imports` → `Success`. Run `uv run ruff check --fix synthbench/ backend/tests/unit/synthbench/` and `uv run ruff format synthbench/ backend/tests/unit/synthbench/`, both clean. If ruff reports `PLR0913` (too many arguments) anywhere in `synthbench/`, add `"PLR0913"` to the new per-file-ignores entry with the comment `# injectable seams (clock, sleep, runner) for tests` rather than removing the seams.

- [ ] **Step 7: Commit**

```bash
uvx pre-commit run --files synthbench/__init__.py synthbench/AGENTS.md synthbench/generate/__init__.py synthbench/generate/comfy/__init__.py synthbench/generate/weights.py synthbench/generate/comfy/extra_model_paths.yaml backend/tests/unit/synthbench/__init__.py backend/tests/unit/synthbench/test_weights.py backend/tests/unit/synthbench/test_import_rule.py .github/workflows/ci.yml .pre-commit-config.yaml pyproject.toml .env.example docs/reference/config/env-reference.md
git add synthbench/ backend/tests/unit/synthbench/ .github/workflows/ci.yml .pre-commit-config.yaml pyproject.toml .env.example docs/reference/config/env-reference.md
git commit -m "feat(synthbench): package skeleton and sha256-pinned ComfyUI weights farm

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The GPU window

**Files:**

- Create: `synthbench/generate/window.py`
- Test: `backend/tests/unit/synthbench/test_window.py`

**Interfaces:**

- Produces:
  - `FLAGSHIP = "dgx-inference-vllm-1"`, `HEALTH_TIMEOUT_S = 2700.0`, `POLL_S = 15.0`
  - `Runtime` Protocol (`stop`, `start`, `is_healthy`) and `DockerRuntime`
  - `WindowPaths(state_dir)` with `.marker`, `.lock`, and `from_env()` (`$SYNTHBENCH_ROOT/state`)
  - `restore(runtime, container=FLAGSHIP, *, timeout_s, poll_s, sleep, clock) -> None`
  - `gpu_window(runtime, paths, *, container, before_restore, timeout_s, poll_s, sleep, clock, say)` (context manager)
  - `stop_gpu_containers() -> None`
  - `main(argv, *, runtime=None, paths=None, before_restore=stop_gpu_containers) -> int`
  - Errors: `WindowBusy`, `FlagshipNotRestored`
- Task 8 runs `python -m synthbench.generate.window run -- <command>`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/synthbench/test_window.py`:

```python
"""The GPU window always restores the flagship (spec §3.6, D9)."""

from __future__ import annotations

import fcntl
import json
import os
import signal
import sys
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

import pytest

from synthbench.generate import window as gw


class FakeRuntime:
    def __init__(
        self,
        *,
        healthy_after: int = 0,
        never_healthy: bool = False,
        stop_error: Exception | None = None,
        running: bool = True,
    ) -> None:
        self.calls: list[str] = []
        self.running = running
        self._healthy_after = healthy_after
        self._never = never_healthy
        self._stop_error = stop_error
        self._polls = 0

    def stop(self, container: str) -> None:
        self.calls.append("stop")
        if self._stop_error is not None:
            raise self._stop_error
        self.running = False

    def start(self, container: str) -> None:
        self.calls.append("start")
        self.running = True

    def is_healthy(self, container: str) -> bool:
        self.calls.append("healthy?")
        if self._never or not self.running:
            return False
        self._polls += 1
        return self._polls > self._healthy_after


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def paths(tmp_path: Path) -> gw.WindowPaths:
    return gw.WindowPaths(tmp_path / "state")


def _window(
    rt: FakeRuntime, paths: gw.WindowPaths, clock: FakeClock | None = None, **kw: Any
) -> AbstractContextManager[None]:
    fake = clock or FakeClock()
    return gw.gpu_window(rt, paths, sleep=fake.sleep, clock=fake, say=lambda _m: None, **kw)


class TestGpuWindow:
    def test_stops_runs_and_restores_in_order(self, paths: gw.WindowPaths) -> None:
        rt = FakeRuntime()
        seen: list[tuple[bool, bool]] = []
        with _window(rt, paths):
            seen.append((rt.running, paths.marker.exists()))
        assert seen == [(False, True)]
        assert rt.calls == ["stop", "start", "healthy?"]
        assert not paths.marker.exists()

    def test_the_marker_records_the_container(self, paths: gw.WindowPaths) -> None:
        with _window(FakeRuntime(), paths):
            assert json.loads(paths.marker.read_text())["container"] == gw.FLAGSHIP

    def test_a_body_error_still_restores(self, paths: gw.WindowPaths) -> None:
        rt = FakeRuntime()
        with pytest.raises(ValueError, match="boom"), _window(rt, paths):
            raise ValueError("boom")
        assert rt.running and not paths.marker.exists()

    def test_ctrl_c_still_restores(self, paths: gw.WindowPaths) -> None:
        rt = FakeRuntime()
        with pytest.raises(KeyboardInterrupt), _window(rt, paths):
            raise KeyboardInterrupt
        assert rt.running

    def test_sigterm_still_restores_and_the_old_handler_returns(
        self, paths: gw.WindowPaths
    ) -> None:
        rt = FakeRuntime()
        before = signal.getsignal(signal.SIGTERM)
        with pytest.raises(SystemExit) as exc, _window(rt, paths):
            os.kill(os.getpid(), signal.SIGTERM)
        assert exc.value.code == 128 + signal.SIGTERM
        assert rt.running
        assert signal.getsignal(signal.SIGTERM) == before

    def test_a_failed_stop_still_starts_the_flagship(self, paths: gw.WindowPaths) -> None:
        rt = FakeRuntime(stop_error=RuntimeError("docker stop failed"))
        with pytest.raises(RuntimeError, match="docker stop failed"), _window(rt, paths):
            pass
        assert "start" in rt.calls

    def test_waits_for_healthy(self, paths: gw.WindowPaths) -> None:
        rt = FakeRuntime(healthy_after=3)
        clock = FakeClock()
        with _window(rt, paths, clock=clock, poll_s=15.0):
            pass
        assert clock.now == 45.0

    def test_a_restore_timeout_keeps_the_marker(self, paths: gw.WindowPaths) -> None:
        rt = FakeRuntime(never_healthy=True)
        with (
            pytest.raises(gw.FlagshipNotRestored),
            _window(rt, paths, timeout_s=60.0, poll_s=15.0),
        ):
            pass
        assert paths.marker.exists()

    def test_a_leftover_marker_restores_before_stopping(self, paths: gw.WindowPaths) -> None:
        paths.state_dir.mkdir(parents=True)
        paths.marker.write_text("{}")
        rt = FakeRuntime(running=False)
        with _window(rt, paths):
            pass
        assert rt.calls.index("start") < rt.calls.index("stop")

    def test_a_busy_lock_refuses_without_touching_the_flagship(
        self, paths: gw.WindowPaths
    ) -> None:
        paths.state_dir.mkdir(parents=True)
        fd = os.open(paths.lock, os.O_CREAT | os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            rt = FakeRuntime()
            with pytest.raises(gw.WindowBusy), _window(rt, paths):
                pass
            assert rt.calls == []
        finally:
            os.close(fd)

    def test_before_restore_runs_before_the_flagship_starts(self, paths: gw.WindowPaths) -> None:
        rt = FakeRuntime()
        with (
            pytest.raises(ValueError, match="x"),
            _window(rt, paths, before_restore=lambda: rt.calls.append("hook")),
        ):
            raise ValueError("x")
        assert rt.calls.index("hook") < rt.calls.index("start")


class TestMain:
    def test_run_returns_the_child_exit_code(self, paths: gw.WindowPaths) -> None:
        rt = FakeRuntime()
        code = gw.main(
            ["run", "--", sys.executable, "-c", "import sys; sys.exit(3)"],
            runtime=rt, paths=paths, before_restore=lambda: None,
        )
        assert code == 3
        assert rt.calls[:2] == ["stop", "start"]

    def test_run_without_a_command_is_a_usage_error(self, paths: gw.WindowPaths) -> None:
        with pytest.raises(SystemExit):
            gw.main(["run"], runtime=FakeRuntime(), paths=paths)

    def test_status_prints_marker_and_health(
        self, paths: gw.WindowPaths, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert gw.main(["status"], runtime=FakeRuntime(), paths=paths) == 0
        assert json.loads(capsys.readouterr().out) == {"marker": False, "flagship_healthy": True}

    def test_restore_clears_the_marker(self, paths: gw.WindowPaths) -> None:
        paths.state_dir.mkdir(parents=True)
        paths.marker.write_text("{}")
        assert gw.main(["restore"], runtime=FakeRuntime(running=False), paths=paths) == 0
        assert not paths.marker.exists()

```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest backend/tests/unit/synthbench/test_window.py -n0 -q`
Expected: `ImportError: cannot import name 'window' from 'synthbench.generate'`.

- [ ] **Step 3: Implement `synthbench/generate/window.py`**

```python
"""The GPU window (spec §3.6, D9).

Stops the flagship vLLM, runs generation on the whole GB300, and ALWAYS
restores the flagship: on success, error, Ctrl-C (SIGINT) and SIGTERM. A
marker file survives a hard kill (SIGKILL, power loss), so the next
invocation restores first. One window at a time (flock).

The flagship runs on the ROOTFUL docker daemon (the dgx-inference stack),
not podman. It is stopped and started at container level: `docker compose
up` on that stack would also restart the stopped Cosmos container.

Use from the main thread only (installs a SIGTERM handler).
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import FrameType
from typing import Protocol

FLAGSHIP = "dgx-inference-vllm-1"
FLAGSHIP_MODELS_URL = "http://127.0.0.1:8000/v1/models"
# The container's healthcheck StartPeriod is 30 min (probed 2026-09-27).
HEALTH_TIMEOUT_S = 45 * 60.0
POLL_S = 15.0
GPU_LABEL_FILTER = "label=synthbench.gpu=1"


class WindowBusy(RuntimeError):
    """Another GPU window is open."""


class FlagshipNotRestored(RuntimeError):
    """The flagship did not become healthy in time; the marker stays for the next run."""


class Runtime(Protocol):
    def stop(self, container: str) -> None: ...

    def start(self, container: str) -> None: ...

    def is_healthy(self, container: str) -> bool: ...


class DockerRuntime:
    """The flagship on the rootful docker daemon."""

    def __init__(self, models_url: str = FLAGSHIP_MODELS_URL) -> None:
        self._models_url = models_url

    def stop(self, container: str) -> None:
        subprocess.run(["docker", "stop", container], check=True, capture_output=True, timeout=600)

    def start(self, container: str) -> None:
        subprocess.run(["docker", "start", container], check=True, capture_output=True, timeout=120)

    def is_healthy(self, container: str) -> bool:
        probe = subprocess.run(
            [
                "docker", "inspect", "--format",
                "{{if .State.Health}}{{.State.Health.Status}}{{end}}", container,
            ],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if probe.returncode != 0 or probe.stdout.strip() != "healthy":
            return False
        try:
            with urllib.request.urlopen(self._models_url, timeout=10) as resp:  # noqa: S310 - fixed loopback URL
                return bool(resp.status == 200)
        except OSError:
            return False


@dataclass(frozen=True)
class WindowPaths:
    state_dir: Path

    @property
    def marker(self) -> Path:
        return self.state_dir / "window.open"

    @property
    def lock(self) -> Path:
        return self.state_dir / "window.lock"

    @classmethod
    def from_env(cls) -> WindowPaths:
        return cls(Path(os.environ.get("SYNTHBENCH_ROOT", "/export/synthbench")) / "state")


def _say(message: str) -> None:
    sys.stderr.write(f"[gpu-window] {message}\n")


def restore(
    runtime: Runtime,
    container: str = FLAGSHIP,
    *,
    timeout_s: float = HEALTH_TIMEOUT_S,
    poll_s: float = POLL_S,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Start the container (a no-op when it already runs) and wait until healthy."""
    runtime.start(container)
    deadline = clock() + timeout_s
    while not runtime.is_healthy(container):
        if clock() >= deadline:
            raise FlagshipNotRestored(f"{container} not healthy {timeout_s:.0f}s after start")
        sleep(poll_s)


def _raise_on_sigterm(signum: int, _frame: FrameType | None) -> None:
    raise SystemExit(128 + signum)


@contextmanager
def gpu_window(
    runtime: Runtime,
    paths: WindowPaths,
    *,
    container: str = FLAGSHIP,
    before_restore: Callable[[], None] = lambda: None,
    timeout_s: float = HEALTH_TIMEOUT_S,
    poll_s: float = POLL_S,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    say: Callable[[str], None] = _say,
) -> Iterator[None]:
    paths.state_dir.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(paths.lock, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WindowBusy(f"another GPU window holds {paths.lock}") from exc
        if paths.marker.exists():
            say("found the marker of an interrupted window: restoring the flagship first")
            restore(runtime, container, timeout_s=timeout_s, poll_s=poll_s, sleep=sleep, clock=clock)
            paths.marker.unlink()
        say(
            f"stopping {container}: LiteLLM's claude-flagship route and any sandbox agent "
            "on it are down until this window closes"
        )
        paths.marker.write_text(
            json.dumps({"pid": os.getpid(), "container": container, "opened_at": time.time()})
        )
        previous = signal.signal(signal.SIGTERM, _raise_on_sigterm)
        try:
            runtime.stop(container)
            yield
        finally:
            signal.signal(signal.SIGTERM, previous)
            try:
                before_restore()
            finally:
                say(f"closing: starting {container} and waiting until it is healthy")
                restore(runtime, container, timeout_s=timeout_s, poll_s=poll_s, sleep=sleep, clock=clock)
                paths.marker.unlink(missing_ok=True)
                say(f"{container} is healthy again")
    finally:
        os.close(lock_fd)


def stop_gpu_containers() -> None:
    """Before the flagship restarts, stop every podman container labeled
    synthbench.gpu=1 (the ComfyUI renderer) so nothing else holds GPU memory."""
    listing = subprocess.run(
        ["podman", "ps", "-q", "--filter", GPU_LABEL_FILTER],
        capture_output=True, text=True, timeout=30, check=False,
    )
    for container_id in listing.stdout.split():
        subprocess.run(
            ["podman", "stop", "--time", "30", container_id],
            capture_output=True, timeout=120, check=False,
        )


def _run_child(command: Sequence[str]) -> int:
    child = subprocess.Popen(list(command))
    try:
        return child.wait()
    except BaseException:
        child.terminate()
        try:
            child.wait(timeout=60)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
        raise


def main(
    argv: Sequence[str] | None = None,
    *,
    runtime: Runtime | None = None,
    paths: WindowPaths | None = None,
    before_restore: Callable[[], None] = stop_gpu_containers,
) -> int:
    parser = argparse.ArgumentParser(prog="python -m synthbench.generate.window")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run COMMAND inside a GPU window")
    run.add_argument("argv", nargs=argparse.REMAINDER)
    sub.add_parser("restore", help="start the flagship and wait for healthy")
    sub.add_parser("status", help="print the marker and flagship health as JSON")
    args = parser.parse_args(argv)
    rt = runtime or DockerRuntime()
    wp = paths or WindowPaths.from_env()
    if args.command == "run":
        command = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
        if not command:
            parser.error("run needs a command: run -- python -m ...")
        with gpu_window(rt, wp, before_restore=before_restore):
            return _run_child(command)
    if args.command == "restore":
        restore(rt)
        wp.marker.unlink(missing_ok=True)
        return 0
    status = {"marker": wp.marker.exists(), "flagship_healthy": rt.is_healthy(FLAGSHIP)}
    sys.stdout.write(json.dumps(status) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest backend/tests/unit/synthbench/test_window.py -n0 -q --cov=synthbench.generate.window --cov-report=term-missing`
Expected: all pass. Only the `DockerRuntime` bodies, `stop_gpu_containers` and `__main__` may be missed.

- [ ] **Step 5: Lint, type-check, commit**

```bash
uv run ruff check --fix synthbench/generate/window.py backend/tests/unit/synthbench/test_window.py
uv run ruff format synthbench/generate/window.py backend/tests/unit/synthbench/test_window.py
uv run mypy synthbench/ --ignore-missing-imports
uvx pre-commit run --files synthbench/generate/window.py backend/tests/unit/synthbench/test_window.py
git add synthbench/generate/window.py backend/tests/unit/synthbench/test_window.py
git commit -m "feat(synthbench): GPU window that always restores the flagship

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

**Do not run the CLI against the real flagship in this task.** Only the controller opens windows (Task 8).

---

### Task 3: The ComfyUI renderer container

**Files:**

- Create: `synthbench/generate/comfy/Containerfile`, `synthbench/generate/comfy/serve.py`
- Test: `backend/tests/unit/synthbench/test_serve.py`

**Interfaces:**

- Consumes: `synthbench/generate/comfy/extra_model_paths.yaml` (Task 1).
- Produces:

  - `IMAGE = "localhost/synthbench-comfyui:v0.37.0"`, `CONTAINER = "synthbench-comfyui"`, `GPU_LABEL = "synthbench.gpu=1"`
  - `ServeConfig(port, models_root, out_dir, cache_dir)` with `.base_url` and `from_env(env=None)`
  - `build_args() -> list[str]`, `run_args(cfg) -> list[str]`
  - `start(cfg, run=subprocess.run) -> None`, `stop(run=subprocess.run) -> None`
  - `wait_ready(base_url, *, timeout_s=600.0, poll_s=2.0, get=httpx.get, sleep, clock) -> dict[str, Any]`
  - `main(argv) -> int` (CLI `build`, `up`, `down`)

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/synthbench/test_serve.py`:

```python
"""The pinned ComfyUI renderer runs loopback-only, with models read-only at the same path."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import httpx
import pytest

from synthbench.generate.comfy import serve


def _cfg(tmp_path: Path) -> serve.ServeConfig:
    return serve.ServeConfig(
        port=18188, models_root=Path("/export/models"),
        out_dir=tmp_path / "out", cache_dir=tmp_path / "cache",
    )


class TestConfig:
    def test_defaults(self) -> None:
        cfg = serve.ServeConfig.from_env({})
        assert cfg.port == 8188
        assert cfg.models_root == Path("/export/models")
        assert cfg.out_dir == Path("/export/synthbench/comfy-out")
        assert cfg.cache_dir == Path("/export/synthbench/cache")
        assert cfg.base_url == "http://127.0.0.1:8188"

    def test_env_overrides(self) -> None:
        cfg = serve.ServeConfig.from_env(
            {"SYNTHBENCH_COMFYUI_PORT": "9999", "HF_HOME": "/m", "SYNTHBENCH_ROOT": "/r"}
        )
        assert (cfg.port, cfg.models_root, cfg.out_dir) == (9999, Path("/m"), Path("/r/comfy-out"))


class TestRunArgs:
    def test_binds_loopback_only(self, tmp_path: Path) -> None:
        args = serve.run_args(_cfg(tmp_path))
        assert args[args.index("-p") + 1] == "127.0.0.1:18188:8188"

    def test_mounts_models_read_only_at_the_same_path(self, tmp_path: Path) -> None:
        assert "/export/models:/export/models:ro" in serve.run_args(_cfg(tmp_path))

    def test_gpu_label_device_and_pinned_image(self, tmp_path: Path) -> None:
        args = serve.run_args(_cfg(tmp_path))
        assert args[:2] == ["podman", "run"]
        assert args[args.index("--device") + 1] == "nvidia.com/gpu=all"
        assert args[args.index("--label") + 1] == serve.GPU_LABEL
        assert args[-1] == serve.IMAGE == "localhost/synthbench-comfyui:v0.37.0"


class TestStartStop:
    def test_start_creates_dirs_and_runs(self, tmp_path: Path) -> None:
        seen: list[list[str]] = []

        def run(argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
            seen.append(argv)
            return subprocess.CompletedProcess(argv, 0, "", "")

        cfg = _cfg(tmp_path)
        serve.start(cfg, run=run)
        assert cfg.out_dir.is_dir() and cfg.cache_dir.is_dir()
        assert seen == [serve.run_args(cfg)]

    def test_stop_ignores_a_missing_container(self) -> None:
        seen: list[list[str]] = []

        def run(argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
            seen.append(argv)
            return subprocess.CompletedProcess(argv, 0, "", "")

        serve.stop(run=run)
        assert seen == [["podman", "stop", "--ignore", "--time", "30", serve.CONTAINER]]


class TestWaitReady:
    def test_polls_until_system_stats_answers(self) -> None:
        answers = iter([httpx.ConnectError("refused"), httpx.Response(503), httpx.Response(200, json={"ok": 1})])

        def get(_url: str, **_kw: Any) -> httpx.Response:
            answer = next(answers)
            if isinstance(answer, Exception):
                raise answer
            return answer

        now = [0.0]
        stats = serve.wait_ready(
            "http://x", get=get, sleep=lambda s: now.__setitem__(0, now[0] + s),
            clock=lambda: now[0],
        )
        assert stats == {"ok": 1}

    def test_times_out(self) -> None:
        now = [0.0]
        with pytest.raises(TimeoutError, match="not ready"):
            serve.wait_ready(
                "http://x", timeout_s=4.0, poll_s=2.0,
                get=lambda _u, **_k: httpx.Response(503),
                sleep=lambda s: now.__setitem__(0, now[0] + s), clock=lambda: now[0],
            )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest backend/tests/unit/synthbench/test_serve.py -n0 -q`
Expected: `ImportError: cannot import name 'serve'`.

- [ ] **Step 3: Implement `synthbench/generate/comfy/serve.py`**

```python
"""Run the pinned ComfyUI renderer under rootless podman (spec §3.1).

The container sees /export/models read-only at the SAME path, so the symlink
farm under /export/models/comfyui resolves inside it. It writes outputs under
$SYNTHBENCH_ROOT/comfy-out, listens on 127.0.0.1 only, and carries the
synthbench.gpu=1 label that the GPU window uses to stop it before the
flagship restarts.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

IMAGE = "localhost/synthbench-comfyui:v0.37.0"
CONTAINER = "synthbench-comfyui"
GPU_LABEL = "synthbench.gpu=1"
CONTAINERFILE_DIR = Path(__file__).resolve().parent

Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class ServeConfig:
    port: int
    models_root: Path
    out_dir: Path
    cache_dir: Path

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> ServeConfig:
        e = os.environ if env is None else env
        root = Path(e.get("SYNTHBENCH_ROOT", "/export/synthbench"))
        return cls(
            port=int(e.get("SYNTHBENCH_COMFYUI_PORT", "8188")),
            models_root=Path(e.get("HF_HOME", "/export/models")),
            out_dir=root / "comfy-out",
            cache_dir=root / "cache",
        )


def build_args() -> list[str]:
    return [
        "podman", "build", "-t", IMAGE,
        "-f", str(CONTAINERFILE_DIR / "Containerfile"), str(CONTAINERFILE_DIR),
    ]


def run_args(cfg: ServeConfig) -> list[str]:
    return [
        "podman", "run", "-d", "--rm", "--name", CONTAINER,
        "--label", GPU_LABEL,
        "--device", "nvidia.com/gpu=all",
        "--shm-size", "16g",
        "-p", f"127.0.0.1:{cfg.port}:8188",
        "-v", f"{cfg.models_root}:{cfg.models_root}:ro",
        "-v", f"{cfg.out_dir}:/opt/ComfyUI/output",
        "-v", f"{cfg.cache_dir}:/root/.cache",
        IMAGE,
    ]


def start(cfg: ServeConfig, run: Runner = subprocess.run) -> None:
    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    cfg.cache_dir.mkdir(parents=True, exist_ok=True)
    run(run_args(cfg), check=True, capture_output=True, text=True)


def stop(run: Runner = subprocess.run) -> None:
    run(
        ["podman", "stop", "--ignore", "--time", "30", CONTAINER],
        check=False, capture_output=True, text=True,
    )


def wait_ready(
    base_url: str,
    *,
    timeout_s: float = 600.0,
    poll_s: float = 2.0,
    get: Callable[..., httpx.Response] = httpx.get,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Poll /system_stats until ComfyUI answers; returns its JSON."""
    deadline = clock() + timeout_s
    while True:
        try:
            resp = get(f"{base_url}/system_stats", timeout=5.0)
            if resp.status_code == 200:
                stats: dict[str, Any] = resp.json()
                return stats
        except httpx.HTTPError:
            pass
        if clock() >= deadline:
            raise TimeoutError(f"ComfyUI at {base_url} not ready after {timeout_s:.0f}s")
        sleep(poll_s)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m synthbench.generate.comfy.serve")
    parser.add_argument("command", choices=["build", "up", "down"])
    args = parser.parse_args(argv)
    cfg = ServeConfig.from_env()
    if args.command == "build":
        subprocess.run(build_args(), check=True)
        return 0
    if args.command == "up":
        start(cfg)
        sys.stdout.write(json.dumps(wait_ready(cfg.base_url), indent=1) + "\n")
        return 0
    stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Write `synthbench/generate/comfy/Containerfile`**

```dockerfile
# synthbench ComfyUI renderer (spec §3.1). arm64 + sm_103 via the NGC PyTorch base.
# Build: python -m synthbench.generate.comfy.serve build
FROM nvcr.io/nvidia/pytorch:26.08-py3

ARG COMFYUI_REF=v0.37.0
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1

WORKDIR /opt
RUN git clone --depth 1 --branch "${COMFYUI_REF}" https://github.com/comfyanonymous/ComfyUI.git
WORKDIR /opt/ComfyUI

# Never let pip replace the base image's CUDA builds of torch & friends.
# torchaudio is dropped from ComfyUI's requirements when the base lacks it
# (PyPI's torchaudio would drag in a CPU torch); audio nodes are not used.
RUN pip list --format=freeze | grep -E '^(torch|torchvision|torchaudio|triton)==' > /tmp/constraints.txt \
 && cat /tmp/constraints.txt \
 && if ! grep -q '^torchaudio==' /tmp/constraints.txt; then sed -i '/^torchaudio/d' requirements.txt; fi \
 && pip install --no-cache-dir -c /tmp/constraints.txt -r requirements.txt

# Bake-off measurement tools: independent of every pipeline model (spec §4.1).
RUN pip install --no-cache-dir -c /tmp/constraints.txt easyocr==1.7.2 \
 && pip install --no-cache-dir --no-deps facenet-pytorch==2.6.0

COPY extra_model_paths.yaml /opt/ComfyUI/extra_model_paths.yaml

EXPOSE 8188
ENTRYPOINT ["python", "main.py", "--listen", "0.0.0.0", "--port", "8188", "--disable-auto-launch"]
```

- [ ] **Step 5: Run the unit tests, lint, commit**

```bash
uv run pytest backend/tests/unit/synthbench/test_serve.py -n0 -q --cov=synthbench.generate.comfy.serve --cov-report=term-missing
uv run ruff check --fix synthbench/generate/comfy/serve.py backend/tests/unit/synthbench/test_serve.py
uv run ruff format synthbench/generate/comfy/serve.py backend/tests/unit/synthbench/test_serve.py
uv run mypy synthbench/ --ignore-missing-imports
uvx pre-commit run --files synthbench/generate/comfy/serve.py synthbench/generate/comfy/Containerfile backend/tests/unit/synthbench/test_serve.py
git add synthbench/generate/comfy/serve.py synthbench/generate/comfy/Containerfile backend/tests/unit/synthbench/test_serve.py
git commit -m "feat(synthbench): pinned ComfyUI v0.37.0 renderer image and podman helpers

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 6: Build the image and prove it runs (flagship stays up)**

This step answers risk R2 (ComfyUI on arm64/sm_103). Prerequisites:

- the background weights download has finished (the controller confirms this in the dispatch);
- the farm exists: `HF_HOME=/export/models uv run python -m synthbench.generate.weights sync --manifest synthbench/generate/manifests/p1-slate.json --skip-repo Lightricks/LTX-2.5` (add `--skip-repo` only while LTX-2.5 is still gated).

```bash
uv run python -m synthbench.generate.comfy.serve build      # pulls ~20 GB NGC base on first build
uv run python -m synthbench.generate.comfy.serve up         # prints /system_stats JSON
curl -s 127.0.0.1:${SYNTHBENCH_COMFYUI_PORT:-8188}/object_info/UNETLoader | python3 -m json.tool | head -40
uv run python -m synthbench.generate.comfy.serve down
```

Expected:

- `system_stats.devices[0].name` contains `GB300`, and the reported torch version is the base image's (not a PyPI build).
- The `UNETLoader` `unet_name` options include `z_image_turbo_bf16.safetensors` and `flux2_dev_fp8mixed.safetensors`, which proves the farm and `extra_model_paths.yaml` resolve inside the container.

Record the three facts (device, torch version, one farm file listed) in the report file.

If the build fails:

- **nofile limit:** a `RUN` step failing on the file-descriptor limit is known on this host (rootless buildah uses nofile=1024). Rebuild with `podman build --ulimit nofile=65536:65536 ...` and put that flag into `build_args()` (with a test).
- **anything else:** if ComfyUI cannot import torch or use the GPU, **stop and report BLOCKED** with the log. That triggers the spec's per-slot `diffusers` fallback decision (R2), which belongs to the owner.

---

### Task 4: ComfyUI client and offline graph validator

**Files:**

- Create: `synthbench/generate/comfy/client.py`, `synthbench/generate/comfy/validate.py`
- Test: `backend/tests/unit/synthbench/test_comfy_client.py`, `backend/tests/unit/synthbench/test_validate.py`

**Interfaces:**

- Produces:

  - `Graph = dict[str, dict[str, Any]]` (in `client.py`)
  - `OutputFile(filename, subfolder, type)` and `ComfyError(RuntimeError)`
  - `ComfyClient(base_url, *, transport=None, timeout_s=60.0)` with methods:
    - `.object_info() -> dict[str, Any]`
    - `.upload_image(path: Path) -> str`
    - `.queue(graph: Graph) -> str`
    - `.wait(prompt_id, *, timeout_s, poll_s=1.0, sleep, clock) -> dict[str, Any]`
    - `.outputs(entry) -> list[OutputFile]`
    - `.download(out: OutputFile) -> bytes`
    - `.run(graph, *, timeout_s) -> list[bytes]`
    - `.close() -> None`
  - `validate_graph(graph: Graph, object_info: dict[str, Any]) -> list[str]` (in `validate.py`; an empty list means valid)

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/synthbench/test_comfy_client.py`:

```python
"""ComfyClient against a fake ComfyUI (httpx.MockTransport)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from synthbench.generate.comfy.client import ComfyClient, ComfyError, OutputFile

GRAPH = {"1": {"class_type": "SaveImage", "inputs": {}}}


def _client(handler: httpx.MockTransport) -> ComfyClient:
    return ComfyClient("http://comfy", transport=handler)


class FakeComfy:
    def __init__(self, *, history_after: int = 0, status: str = "success") -> None:
        self.history_after = history_after
        self.status = status
        self.history_polls = 0
        self.queued: list[dict[str, object]] = []
        self.uploads: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/prompt":
            body = json.loads(request.content)
            self.queued.append(body)
            return httpx.Response(200, json={"prompt_id": "p1", "number": 0, "node_errors": {}})
        if path == "/history/p1":
            self.history_polls += 1
            if self.history_polls <= self.history_after:
                return httpx.Response(200, json={})
            entry = {
                "status": {"status_str": self.status, "completed": True, "messages": [["x", {}]]},
                "outputs": {
                    "9": {"images": [{"filename": "a.png", "subfolder": "s", "type": "output"}]},
                    "12": {"images": [{"filename": "v.mp4", "subfolder": "", "type": "output"}],
                           "animated": [True]},
                },
            }
            return httpx.Response(200, json={"p1": entry})
        if path == "/view":
            return httpx.Response(200, content=f"bytes:{request.url.params['filename']}".encode())
        if path == "/upload/image":
            self.uploads.append(request.headers["content-type"])
            return httpx.Response(200, json={"name": "ref.png", "subfolder": "", "type": "input"})
        if path == "/object_info":
            return httpx.Response(200, json={"SaveImage": {}})
        return httpx.Response(404)


def _no_sleep(_s: float) -> None:
    return None


class TestComfyClient:
    def test_run_queues_waits_and_downloads_every_output(self) -> None:
        fake = FakeComfy(history_after=2)
        client = _client(httpx.MockTransport(fake))
        blobs = client.run(GRAPH, timeout_s=10, sleep=_no_sleep)
        assert blobs == [b"bytes:a.png", b"bytes:v.mp4"]
        assert fake.queued[0]["prompt"] == GRAPH
        assert fake.history_polls == 3

    def test_outputs_collect_images_and_videos(self) -> None:
        entry = {"outputs": {"9": {"images": [{"filename": "a.png", "subfolder": "s", "type": "output"}]},
                             "3": {"text": ["not a file"]}}}
        assert ComfyClient("http://c").outputs(entry) == [OutputFile("a.png", "s", "output")]

    def test_a_failed_execution_raises(self) -> None:
        client = _client(httpx.MockTransport(FakeComfy(status="error")))
        with pytest.raises(ComfyError, match="error"):
            client.run(GRAPH, timeout_s=10, sleep=_no_sleep)

    def test_a_rejected_graph_raises_with_the_node_errors(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": {"type": "prompt_outputs_failed_validation"},
                                             "node_errors": {"1": {"errors": ["bad"]}}})

        with pytest.raises(ComfyError, match="prompt_outputs_failed_validation"):
            _client(httpx.MockTransport(handler)).queue(GRAPH)

    def test_wait_times_out(self) -> None:
        client = _client(httpx.MockTransport(FakeComfy(history_after=10**6)))
        now = [0.0]
        with pytest.raises(TimeoutError, match="p1"):
            client.wait("p1", timeout_s=3.0, poll_s=1.0,
                        sleep=lambda s: now.__setitem__(0, now[0] + s), clock=lambda: now[0])

    def test_upload_sends_multipart_and_returns_the_name(self, tmp_path: Path) -> None:
        fake = FakeComfy()
        image = tmp_path / "ref.png"
        image.write_bytes(b"\x89PNG")
        assert _client(httpx.MockTransport(fake)).upload_image(image) == "ref.png"
        assert fake.uploads[0].startswith("multipart/form-data")

    def test_object_info(self) -> None:
        assert _client(httpx.MockTransport(FakeComfy())).object_info() == {"SaveImage": {}}
```

`backend/tests/unit/synthbench/test_validate.py`:

```python
"""validate_graph: API graphs checked offline against /object_info."""

from __future__ import annotations

from typing import Any

from synthbench.generate.comfy.validate import validate_graph

INFO: dict[str, Any] = {
    "UNETLoader": {
        "input": {"required": {"unet_name": [["z.safetensors"], {}], "weight_dtype": [["default", "fp8_e4m3fn"], {}]}},
        "output": ["MODEL"],
    },
    "KSampler": {
        "input": {"required": {"model": ["MODEL", {}], "seed": ["INT", {"min": 0}],
                               "sampler_name": ["COMBO", {"options": ["euler", "res_multistep"]}]},
                  "optional": {"note": ["STRING", {}]}},
        "output": ["LATENT"],
    },
    "VAEDecode": {"input": {"required": {"samples": ["LATENT", {}]}}, "output": ["IMAGE"]},
    "AnyNode": {"input": {"required": {"x": ["*", {}]}}, "output": ["*"]},
}


def _good() -> dict[str, dict[str, Any]]:
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "z.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "seed": 3, "sampler_name": "euler"}},
        "3": {"class_type": "VAEDecode", "inputs": {"samples": ["2", 0]}},
    }


def test_a_valid_graph_has_no_errors() -> None:
    assert validate_graph(_good(), INFO) == []


def test_unknown_class_type() -> None:
    graph = _good() | {"4": {"class_type": "Nope", "inputs": {}}}
    assert validate_graph(graph, INFO) == ["4: unknown class_type 'Nope'"]


def test_missing_required_input() -> None:
    graph = _good()
    del graph["2"]["inputs"]["seed"]
    assert validate_graph(graph, INFO) == ["2 (KSampler): missing required input 'seed'"]


def test_unknown_input_name() -> None:
    graph = _good()
    graph["3"]["inputs"]["bogus"] = 1
    assert validate_graph(graph, INFO) == ["3 (VAEDecode): unknown input 'bogus'"]


def test_a_combo_value_must_be_allowed_in_both_formats() -> None:
    graph = _good()
    graph["1"]["inputs"]["unet_name"] = "missing.safetensors"
    graph["2"]["inputs"]["sampler_name"] = "dpm"
    errors = validate_graph(graph, INFO)
    assert "1 (UNETLoader): unet_name='missing.safetensors' is not an allowed value" in errors
    assert "2 (KSampler): sampler_name='dpm' is not an allowed value" in errors


def test_links_must_point_at_an_existing_node_and_output() -> None:
    graph = _good()
    graph["3"]["inputs"]["samples"] = ["9", 0]
    graph["2"]["inputs"]["model"] = ["1", 5]
    errors = validate_graph(graph, INFO)
    assert "3 (VAEDecode): samples links to missing node '9'" in errors
    assert "2 (KSampler): model links to output 5 of '1' (UNETLoader has 1)" in errors


def test_link_types_must_match_unless_wildcard() -> None:
    graph = _good()
    graph["3"]["inputs"]["samples"] = ["1", 0]
    graph["5"] = {"class_type": "AnyNode", "inputs": {"x": ["1", 0]}}
    assert validate_graph(graph, INFO) == ["3 (VAEDecode): samples expects LATENT but '1' gives MODEL"]


def test_optional_inputs_are_accepted() -> None:
    graph = _good()
    graph["2"]["inputs"]["note"] = "hi"
    assert validate_graph(graph, INFO) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest backend/tests/unit/synthbench/test_comfy_client.py backend/tests/unit/synthbench/test_validate.py -n0 -q`
Expected: `ModuleNotFoundError` for `synthbench.generate.comfy.client` / `.validate`.

- [ ] **Step 3: Implement `synthbench/generate/comfy/client.py`**

```python
"""Minimal ComfyUI HTTP client (spec §3.1): upload, queue, wait, collect outputs."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

Graph = dict[str, dict[str, Any]]


class ComfyError(RuntimeError):
    """ComfyUI rejected a graph or failed while executing it."""


@dataclass(frozen=True)
class OutputFile:
    filename: str
    subfolder: str
    type: str


class ComfyClient:
    def __init__(
        self,
        base_url: str,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout_s: float = 60.0,
    ) -> None:
        self._http = httpx.Client(base_url=base_url, transport=transport, timeout=timeout_s)
        self._client_id = uuid.uuid4().hex

    def close(self) -> None:
        self._http.close()

    def object_info(self) -> dict[str, Any]:
        resp = self._http.get("/object_info")
        resp.raise_for_status()
        info: dict[str, Any] = resp.json()
        return info

    def upload_image(self, path: Path) -> str:
        resp = self._http.post(
            "/upload/image",
            files={"image": (path.name, path.read_bytes(), "image/png")},
            data={"overwrite": "true"},
        )
        resp.raise_for_status()
        return str(resp.json()["name"])

    def queue(self, graph: Graph) -> str:
        resp = self._http.post("/prompt", json={"prompt": graph, "client_id": self._client_id})
        body: dict[str, Any] = resp.json()
        if resp.status_code != 200 or body.get("error") or body.get("node_errors"):
            raise ComfyError(f"graph rejected: {body}")
        return str(body["prompt_id"])

    def wait(
        self,
        prompt_id: str,
        *,
        timeout_s: float,
        poll_s: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> dict[str, Any]:
        deadline = clock() + timeout_s
        while True:
            resp = self._http.get(f"/history/{prompt_id}")
            resp.raise_for_status()
            entry: dict[str, Any] | None = resp.json().get(prompt_id)
            if entry is not None:
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    raise ComfyError(f"{prompt_id} failed (error): {status.get('messages')}")
                return entry
            if clock() >= deadline:
                raise TimeoutError(f"{prompt_id} not finished after {timeout_s:.0f}s")
            sleep(poll_s)

    @staticmethod
    def outputs(entry: dict[str, Any]) -> list[OutputFile]:
        found: list[OutputFile] = []
        for node_output in entry.get("outputs", {}).values():
            for value in node_output.values():
                if not isinstance(value, list):
                    continue
                for item in value:
                    if isinstance(item, dict) and "filename" in item:
                        found.append(
                            OutputFile(item["filename"], item.get("subfolder", ""), item.get("type", "output"))
                        )
        return found

    def download(self, out: OutputFile) -> bytes:
        resp = self._http.get(
            "/view", params={"filename": out.filename, "subfolder": out.subfolder, "type": out.type}
        )
        resp.raise_for_status()
        return resp.content

    def run(
        self,
        graph: Graph,
        *,
        timeout_s: float,
        sleep: Callable[[float], None] = time.sleep,
    ) -> list[bytes]:
        entry = self.wait(self.queue(graph), timeout_s=timeout_s, sleep=sleep)
        return [self.download(out) for out in self.outputs(entry)]
```

Note: `outputs` iterates the nodes in history order. `test_run_queues_waits_and_downloads_every_output` expects `a.png` before `v.mp4`, which matches the fake's insertion order.

- [ ] **Step 4: Implement `synthbench/generate/comfy/validate.py`**

```python
"""Offline validation of an API-format graph against ComfyUI's /object_info.

Catches, without a GPU: unknown node types, missing/unknown inputs, combo
values the server would reject (including model files missing from the
farm), dangling links, and link type mismatches. Both combo formats are
understood: [[options...], {...}] and ["COMBO", {"options": [...]}].
"""

from __future__ import annotations

from typing import Any

Graph = dict[str, dict[str, Any]]


def _is_link(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
    )


def _options(spec: list[Any]) -> list[Any] | None:
    if isinstance(spec[0], list):
        return spec[0]
    if spec[0] == "COMBO" and len(spec) > 1 and isinstance(spec[1], dict):
        options = spec[1].get("options")
        return options if isinstance(options, list) else None
    return None


def _types(declared: Any) -> set[str]:
    return {t.strip() for t in str(declared).split(",")}


def validate_graph(graph: Graph, object_info: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for node_id, node in graph.items():
        class_type = node.get("class_type")
        info = object_info.get(str(class_type))
        if info is None:
            errors.append(f"{node_id}: unknown class_type {class_type!r}")
            continue
        declared = info.get("input", {})
        required: dict[str, Any] = declared.get("required", {})
        optional: dict[str, Any] = declared.get("optional", {})
        inputs: dict[str, Any] = node.get("inputs", {})
        where = f"{node_id} ({class_type})"
        errors += [f"{where}: missing required input {name!r}" for name in required if name not in inputs]
        for name, value in inputs.items():
            spec = required.get(name) or optional.get(name)
            if spec is None:
                errors.append(f"{where}: unknown input {name!r}")
                continue
            if _is_link(value):
                errors += _check_link(where, name, value, spec, graph, object_info)
                continue
            options = _options(spec)
            if options is not None and value not in options:
                errors.append(f"{where}: {name}={value!r} is not an allowed value")
    return errors


def _check_link(
    where: str, name: str, value: list[Any], spec: list[Any], graph: Graph, object_info: dict[str, Any]
) -> list[str]:
    source_id, index = value
    source = graph.get(source_id)
    if source is None:
        return [f"{where}: {name} links to missing node {source_id!r}"]
    source_info = object_info.get(str(source.get("class_type")))
    if source_info is None:
        return []  # already reported as an unknown class_type
    outputs: list[Any] = source_info.get("output", [])
    if index >= len(outputs):
        return [
            f"{where}: {name} links to output {index} of {source_id!r} "
            f"({source['class_type']} has {len(outputs)})"
        ]
    wanted, given = _types(spec[0]), _types(outputs[index])
    if "*" in wanted or "*" in given or wanted & given or _options(spec) is not None:
        return []
    return [f"{where}: {name} expects {spec[0]} but {source_id!r} gives {outputs[index]}"]
```

- [ ] **Step 5: Run the tests, lint, commit**

```bash
uv run pytest backend/tests/unit/synthbench/test_comfy_client.py backend/tests/unit/synthbench/test_validate.py -n0 -q --cov=synthbench.generate.comfy --cov-report=term-missing
uv run ruff check --fix synthbench/generate/comfy/ backend/tests/unit/synthbench/
uv run ruff format synthbench/generate/comfy/ backend/tests/unit/synthbench/
uv run mypy synthbench/ --ignore-missing-imports
uvx pre-commit run --files synthbench/generate/comfy/client.py synthbench/generate/comfy/validate.py backend/tests/unit/synthbench/test_comfy_client.py backend/tests/unit/synthbench/test_validate.py
git add synthbench/generate/comfy/client.py synthbench/generate/comfy/validate.py backend/tests/unit/synthbench/test_comfy_client.py backend/tests/unit/synthbench/test_validate.py
git commit -m "feat(synthbench): ComfyUI client and offline graph validator

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: One graph builder per model, validated offline and smoke-tested live

**Files:**

- Create: `synthbench/generate/comfy/graphs.py`, `synthbench/generate/comfy/snapshot.py`, `synthbench/generate/comfy/object_info.v0.37.0.json` (generated), `synthbench/generate/comfy/smoke.py`
- Test: `backend/tests/unit/synthbench/test_graphs.py`

**Interfaces:**

- Consumes: `Graph` and `ComfyClient` (Task 4), `validate_graph` (Task 4), `ServeConfig` / `start` / `stop` / `wait_ready` (Task 3). Farm link names come from Task 1 and are listed below.
- Produces (in `graphs.py`):
  - `T2IBuilder = Callable[..., Graph]` with signature `(prompt: str, *, seed: int, width: int, height: int)`
  - `EditBuilder` with signature `(prompt: str, *, images: Sequence[str], seed: int, width: int, height: int)`
  - `I2VBuilder` with signature `(prompt: str, *, image: str, seed: int, width: int, height: int, frames: int)`
  - `T2I_BUILDERS: dict[str, T2IBuilder]` with keys `flux2-dev`, `flux2-klein-4b`, `qwen-image-2.1`, `z-image-turbo`, `hidream-i1-full`, `ideogram-4`
  - `EDIT_BUILDERS: dict[str, EditBuilder]` with keys `qwen-image-2.1`, `flux2-dev`, `flux2-klein-4b`
  - `I2V_BUILDERS: dict[str, I2VBuilder]` with keys `ltx-2.5`, `wan2.2-i2v`
  - `sample_graphs() -> dict[str, Graph]`: one graph per registered builder, keyed `"<kind>:<model>"`, built with fixed sample arguments. Used by the snapshot, the tests and the smoke CLI.
- Every graph ends in a `SaveImage` or `SaveVideo` node whose `filename_prefix` is `synthbench/<model>`.

**Farm file names to use (from the P1 manifest and the link-name rule):**

| Model           | diffusion_models                                                                                      | text_encoders                                                                                                      | vae                                                                        | other                                                                                         |
| --------------- | ----------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| flux2-dev       | `flux2_dev_fp8mixed.safetensors`                                                                      | `mistral_3_small_flux2_fp8.safetensors`                                                                            | `flux2-dev--flux2-vae.safetensors`                                         |                                                                                               |
| flux2-klein-4b  | `flux-2-klein-4b.safetensors`                                                                         | `qwen_3_4b.safetensors`                                                                                            | `flux2-klein-4b--flux2-vae.safetensors`                                    |                                                                                               |
| qwen-image-2.1  | `qwen_image_2.1_bf16.safetensors`                                                                     | `qwen3vl_8b_bf16.safetensors`                                                                                      | `qwen_image_2.1_vae_bf16.safetensors`                                      |                                                                                               |
| z-image-turbo   | `z_image_turbo_bf16.safetensors`                                                                      | `qwen_3_4b.safetensors`                                                                                            | `ae.safetensors`                                                           |                                                                                               |
| hidream-i1-full | `hidream_i1_full_fp8.safetensors`                                                                     | `clip_l_hidream`, `clip_g_hidream`, `t5xxl_fp8_e4m3fn_scaled`, `llama_3.1_8b_instruct_fp8_scaled` (`.safetensors`) | `ae.safetensors`                                                           |                                                                                               |
| ideogram-4      | `ideogram4_fp8_scaled.safetensors`, `ideogram4_unconditional_fp8_scaled.safetensors`                  | `qwen3vl_8b_fp8_scaled.safetensors`                                                                                | `ideogram-4--flux2-vae.safetensors`                                        |                                                                                               |
| ltx-2.5         | `ltx-2.5-22b-distilled-transformer-bf16.safetensors`                                                  | `gemma4-12b-with-proj-ltx-2.5-bf16.safetensors`                                                                    | `ltx-2.5-video-vae-bf16.safetensors`, `ltx-2.5-audio-vae-bf16.safetensors` | latent_upscale_models: `ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors`              |
| wan2.2-i2v      | `wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors`, `wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors` | `umt5_xxl_fp16.safetensors`                                                                                        | `wan_2.1_vae.safetensors`                                                  | loras: `wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors`, `…_low_noise.safetensors` |

**Reference templates.** Each builder is derived from the official ComfyUI template of the same model. Templates are in UI format, often with subgraphs, and must be flattened by reading them. The version matching v0.37.0 is inside the renderer image:

```bash
podman run --rm --entrypoint python localhost/synthbench-comfyui:v0.37.0 -c \
  "import comfyui_workflow_templates_json as t, os; print(os.path.dirname(t.__file__))"
podman run --rm --entrypoint cat localhost/synthbench-comfyui:v0.37.0 \
  <that dir>/templates/image_z_image_turbo.json
```

| Builder               | Template                                                                                                                                                                             |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------- | -------------------------------------------------- |
| t2i `z-image-turbo`   | `image_z_image_turbo.json` (worked example below)                                                                                                                                    |
| t2i `flux2-dev`       | `image_flux2_fp8.json`, text-to-image path, Turbo LoRA off (worked example below)                                                                                                    |
| t2i `flux2-klein-4b`  | `image_flux2_klein_text_to_image.json`                                                                                                                                               |
| t2i `qwen-image-2.1`  | `image_qwen_image_2_1_t2i.json`. Skip the optional prompt-enhancer model: prompts go straight to the text encoder                                                                    |
| t2i `hidream-i1-full` | `hidream_i1_full.json`                                                                                                                                                               |
| t2i `ideogram-4`      | `image_ideogram4_t2i.json`. Pass our prompt as plain text, the simplest form the template's encoder accepts. The structured-JSON prompt form is P3 work                              |
| edit `qwen-image-2.1` | `image_qwen_image_2_1_image_edit.json`                                                                                                                                               |
| edit `flux2-dev`      | `image_flux2_fp8.json`, reference path: each image goes `LoadImage → ImageScaleToTotalPixels → VAEEncode → ReferenceLatent`, chained on the conditioning                             |
| edit `flux2-klein-4b` | `image_flux2_klein_image_edit_4b_distilled.json`                                                                                                                                     |
| i2v `ltx-2.5`         | `video_ltx2_5_i2v.json`. Use our bf16 files (the template uses int8 ones), set the `TextGenerateLTX2Prompt` prompt-enhancer path off, and feed `prompt` to `CLIPTextEncode` directly |
| i2v `wan2.2-i2v`      | the Wan 2.2 14B I2V template in the same directory (find it with `ls templates                                                                                                       | grep -i wan2_2 | grep -i i2v`), in its 4-step lightx2v-LoRA variant |

Rules for every builder:

- Keep the template's sampler, scheduler, steps, cfg/guidance and shift values; they're the vendor-tuned defaults.
- Replace every model file name with the farm name from the table.
- Replace the seed, prompt, width, height (and frames for video) with the builder's arguments.
- Drop preview, note and UI-only nodes.
- Put a one-line comment above each builder naming its template.

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/synthbench/test_graphs.py`:

```python
"""Every registered graph builder validates against the captured /object_info (v0.37.0 + our farm)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from synthbench.generate.comfy import graphs
from synthbench.generate.comfy.validate import validate_graph

REPO_ROOT = Path(__file__).resolve().parents[4]
SNAPSHOT = REPO_ROOT / "synthbench" / "generate" / "comfy" / "object_info.v0.37.0.json"


@pytest.fixture(scope="module")
def object_info() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(SNAPSHOT.read_text())
    return data


def test_registries_cover_the_approved_slate() -> None:
    assert set(graphs.T2I_BUILDERS) == {
        "flux2-dev", "flux2-klein-4b", "qwen-image-2.1", "z-image-turbo", "hidream-i1-full", "ideogram-4",
    }
    assert set(graphs.EDIT_BUILDERS) == {"qwen-image-2.1", "flux2-dev", "flux2-klein-4b"}
    assert set(graphs.I2V_BUILDERS) == {"ltx-2.5", "wan2.2-i2v"}
    assert len(graphs.sample_graphs()) == 11


@pytest.mark.parametrize("key", sorted(graphs.sample_graphs()))
def test_every_sample_graph_validates(key: str, object_info: dict[str, Any]) -> None:
    assert validate_graph(graphs.sample_graphs()[key], object_info) == []


@pytest.mark.parametrize("key", sorted(graphs.sample_graphs()))
def test_every_graph_saves_under_its_model_prefix(key: str) -> None:
    model = key.split(":", 1)[1]
    savers = [n for n in graphs.sample_graphs()[key].values() if n["class_type"] in {"SaveImage", "SaveVideo"}]
    assert len(savers) == 1
    assert savers[0]["inputs"]["filename_prefix"] == f"synthbench/{model}"


def test_builders_thread_their_arguments() -> None:
    graph = graphs.T2I_BUILDERS["z-image-turbo"]("a porch", seed=7, width=1920, height=1088)
    values = [v for node in graph.values() for v in node["inputs"].values()]
    assert "a porch" in values and 7 in values and 1920 in values and 1088 in values
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest backend/tests/unit/synthbench/test_graphs.py -n0 -q`
Expected: `ImportError: cannot import name 'graphs'`.

- [ ] **Step 3: Implement `graphs.py`, starting from the two worked examples**

```python
"""One ComfyUI API-graph builder per model (spec §3.2 slots), derived from the
official v0.37.0 workflow templates. File names are the farm's link names
(synthbench.generate.weights.link_names over manifests/p1-slate.json)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from synthbench.generate.comfy.client import Graph

T2IBuilder = Callable[..., Graph]
EditBuilder = Callable[..., Graph]
I2VBuilder = Callable[..., Graph]


def _prefix(model: str) -> str:
    return f"synthbench/{model}"


# template: image_z_image_turbo.json
def z_image_turbo_t2i(prompt: str, *, seed: int, width: int, height: int) -> Graph:
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "z_image_turbo_bf16.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "lumina2", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "4": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": 3.0}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "6": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}},
        "7": {"class_type": "EmptySD3LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "8": {"class_type": "KSampler", "inputs": {
            "model": ["4", 0], "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["7", 0],
            "seed": seed, "steps": 8, "cfg": 1.0, "sampler_name": "res_multistep",
            "scheduler": "simple", "denoise": 1.0}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "SaveImage", "inputs": {"images": ["9", 0], "filename_prefix": _prefix("z-image-turbo")}},
    }


# template: image_flux2_fp8.json (text-to-image path; Turbo LoRA off)
def flux2_dev_t2i(prompt: str, *, seed: int, width: int, height: int) -> Graph:
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux2_dev_fp8mixed.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "mistral_3_small_flux2_fp8.safetensors", "type": "flux2", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-dev--flux2-vae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "5": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["4", 0], "guidance": 4.0}},
        "6": {"class_type": "BasicGuider", "inputs": {"model": ["1", 0], "conditioning": ["5", 0]}},
        "7": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "8": {"class_type": "Flux2Scheduler", "inputs": {"steps": 20, "width": width, "height": height}},
        "9": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "10": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "11": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["10", 0], "guider": ["6", 0], "sampler": ["9", 0], "sigmas": ["8", 0], "latent_image": ["7", 0]}},
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["3", 0]}},
        "13": {"class_type": "SaveImage", "inputs": {"images": ["12", 0], "filename_prefix": _prefix("flux2-dev")}},
    }
```

Input names in the worked examples come from the templates' widget order. The captured `/object_info` (Step 4) is the authority: if `validate_graph` reports an input name or type mismatch, fix the builder to match `/object_info`, never the other way round.

Then add the remaining nine builders, following the reference-template table and rules above:

- t2i: `flux2_klein_4b_t2i`, `qwen_image_21_t2i`, `hidream_i1_full_t2i`, `ideogram_4_t2i`;
- edit: `qwen_image_21_edit`, `flux2_dev_edit`, `flux2_klein_4b_edit`. Each takes `images: Sequence[str]`, the uploaded file names. The first image is the identity reference; build one `LoadImage` node per image;
- i2v: `ltx_25_i2v`, `wan22_i2v`. Each takes `image: str` (the uploaded keyframe name) and `frames: int`.

Close the module with the registries and `sample_graphs`:

```python
T2I_BUILDERS: dict[str, T2IBuilder] = {
    "flux2-dev": flux2_dev_t2i,
    "flux2-klein-4b": flux2_klein_4b_t2i,
    "qwen-image-2.1": qwen_image_21_t2i,
    "z-image-turbo": z_image_turbo_t2i,
    "hidream-i1-full": hidream_i1_full_t2i,
    "ideogram-4": ideogram_4_t2i,
}
EDIT_BUILDERS: dict[str, EditBuilder] = {
    "qwen-image-2.1": qwen_image_21_edit,
    "flux2-dev": flux2_dev_edit,
    "flux2-klein-4b": flux2_klein_4b_edit,
}
I2V_BUILDERS: dict[str, I2VBuilder] = {"ltx-2.5": ltx_25_i2v, "wan2.2-i2v": wan22_i2v}

_SAMPLE: dict[str, Any] = {"seed": 11, "width": 1024, "height": 576}


def sample_graphs() -> dict[str, Graph]:
    graphs: dict[str, Graph] = {}
    for model, t2i in T2I_BUILDERS.items():
        graphs[f"t2i:{model}"] = t2i("a front porch", **_SAMPLE)
    for model, edit in EDIT_BUILDERS.items():
        graphs[f"edit:{model}"] = edit("the same man", images=["ref.png"], **_SAMPLE)
    for model, i2v in I2V_BUILDERS.items():
        graphs[f"i2v:{model}"] = i2v("he walks", image="key.png", frames=33, **_SAMPLE)
    return graphs
```

Validation against the snapshot fails on `ref.png` / `key.png` if the `LoadImage.image` options are a fixed file list. Fix this in `snapshot.py`, never in the builders: when writing the snapshot, rewrite the `image` input of `LoadImage` into `["STRING", {}]`, a free string. Uploaded names are only known at run time.

- [ ] **Step 4: Capture the object_info snapshot (renderer running beside the flagship)**

`synthbench/generate/comfy/snapshot.py`:

```python
"""Capture /object_info filtered to the node types our builders use (for offline validation).

    python -m synthbench.generate.comfy.snapshot   # renderer must be up (serve up)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from synthbench.generate.comfy.client import ComfyClient
from synthbench.generate.comfy.graphs import sample_graphs
from synthbench.generate.comfy.serve import ServeConfig

OUT = Path(__file__).resolve().parent / "object_info.v0.37.0.json"


def filtered(object_info: dict[str, Any]) -> dict[str, Any]:
    used = {node["class_type"] for graph in sample_graphs().values() for node in graph.values()}
    kept = {name: object_info[name] for name in sorted(used) if name in object_info}
    if "LoadImage" in kept:  # uploaded file names are only known at run time
        kept["LoadImage"]["input"]["required"]["image"] = ["STRING", {}]
    return kept


def main() -> int:
    client = ComfyClient(ServeConfig.from_env().base_url)
    try:
        OUT.write_text(json.dumps(filtered(client.object_info()), indent=1, sort_keys=True) + "\n")
    finally:
        client.close()
    sys.stdout.write(f"wrote {OUT}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Run:

```bash
uv run python -m synthbench.generate.comfy.serve up
uv run python -m synthbench.generate.comfy.snapshot
uv run pytest backend/tests/unit/synthbench/test_graphs.py -n0 -q
```

Iterate on the builders until every `test_every_sample_graph_validates` case passes. Re-run `snapshot` whenever a builder starts using a new node type.

- [ ] **Step 5: Live smoke on the models that fit beside the flagship**

`synthbench/generate/comfy/smoke.py`:

```python
"""Queue each registered builder once at low resolution against a running renderer.

    python -m synthbench.generate.comfy.smoke --only t2i:z-image-turbo,t2i:flux2-klein-4b
Writes <SYNTHBENCH_ROOT>/smoke/<kind>_<model>.<ext> and prints seconds per graph.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from synthbench.generate.comfy import graphs
from synthbench.generate.comfy.client import ComfyClient
from synthbench.generate.comfy.serve import ServeConfig

SMOKE_REF = Path(__file__).resolve().parent / "smoke_ref.png"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m synthbench.generate.comfy.smoke")
    parser.add_argument("--only", default="", help="comma-separated keys like t2i:z-image-turbo")
    args = parser.parse_args(argv)
    wanted = {k for k in args.only.split(",") if k}
    out_dir = Path(os.environ.get("SYNTHBENCH_ROOT", "/export/synthbench")) / "smoke"
    out_dir.mkdir(parents=True, exist_ok=True)
    client = ComfyClient(ServeConfig.from_env().base_url)
    failures = 0
    try:
        ref = client.upload_image(SMOKE_REF)
        for key in sorted(graphs.sample_graphs()):
            if wanted and key not in wanted:
                continue
            kind, model = key.split(":", 1)
            small = {"seed": 11, "width": 512, "height": 288}
            if kind == "t2i":
                graph = graphs.T2I_BUILDERS[model]("a front porch in daylight", **small)
            elif kind == "edit":
                graph = graphs.EDIT_BUILDERS[model]("the same scene at dusk", images=[ref], **small)
            else:
                graph = graphs.I2V_BUILDERS[model]("the scene is still", image=ref, frames=17, **small)
            started = time.monotonic()
            try:
                blobs = client.run(graph, timeout_s=1800)
                suffix = "mp4" if kind == "i2v" else "png"
                (out_dir / f"{kind}_{model}.{suffix}").write_bytes(blobs[0])
                sys.stdout.write(f"OK   {key:28s} {time.monotonic() - started:7.1f}s\n")
            except Exception as exc:  # noqa: BLE001 - smoke reports every failure and continues
                failures += 1
                sys.stdout.write(f"FAIL {key:28s} {type(exc).__name__}: {exc}\n")
    finally:
        client.close()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
```

`smoke_ref.png` is the reference image for edit and i2v smoke runs. It must not show a real person (spec §3.8), so generate it with Z-Image-Turbo:

```bash
uv run python -c "
from pathlib import Path
from synthbench.generate.comfy.client import ComfyClient
from synthbench.generate.comfy import graphs
c = ComfyClient('http://127.0.0.1:8188')
g = graphs.T2I_BUILDERS['z-image-turbo']('a quiet suburban front porch with a potted plant, daylight', seed=5, width=512, height=288)
Path('synthbench/generate/comfy/smoke_ref.png').write_bytes(c.run(g, timeout_s=900)[0])"
```

Keep the committed PNG under 300 KB. Re-encode with `python -c "from PIL import Image; ..."` at quality settings if needed.

With the flagship up (48.9 GiB free), smoke these keys: `t2i:z-image-turbo`, `t2i:flux2-klein-4b`, `edit:flux2-klein-4b`, `t2i:ideogram-4`, `t2i:hidream-i1-full`, `t2i:qwen-image-2.1`, `edit:qwen-image-2.1`. Record each key's OK/FAIL and seconds in the report file.

**Do not** run `t2i:flux2-dev`, `edit:flux2-dev`, `i2v:ltx-2.5` or `i2v:wan2.2-i2v` here. They need the full GPU, and the controller smokes them inside the first GPU window (Task 8).

If a model OOMs beside the flagship, report it and move on. Never stop the flagship yourself.

- [ ] **Step 6: Lint, type-check, commit**

```bash
uv run python -m synthbench.generate.comfy.serve down
uv run ruff check --fix synthbench/generate/comfy/ backend/tests/unit/synthbench/test_graphs.py
uv run ruff format synthbench/generate/comfy/ backend/tests/unit/synthbench/test_graphs.py
uv run mypy synthbench/ --ignore-missing-imports
uv run pytest backend/tests/unit/synthbench/ -n0 -q
uvx pre-commit run --files synthbench/generate/comfy/graphs.py synthbench/generate/comfy/snapshot.py synthbench/generate/comfy/smoke.py synthbench/generate/comfy/object_info.v0.37.0.json synthbench/generate/comfy/smoke_ref.png backend/tests/unit/synthbench/test_graphs.py
git add synthbench/generate/comfy/ backend/tests/unit/synthbench/test_graphs.py
git commit -m "feat(synthbench): per-model ComfyUI graph builders with offline validation and live smoke

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The bake-off cases and runner (spike)

**Files:**

- Create: `synthbench/spikes/__init__.py`, `synthbench/spikes/p1_bakeoff/__init__.py`, `synthbench/spikes/p1_bakeoff/cases.py`, `synthbench/spikes/p1_bakeoff/plan.py`, `synthbench/spikes/p1_bakeoff/run.py`
- Test: `backend/tests/unit/synthbench/spikes/__init__.py`, `backend/tests/unit/synthbench/spikes/test_p1_plan.py`, `backend/tests/unit/synthbench/spikes/test_p1_run.py`

**Interfaces:**

- Consumes: `T2I_BUILDERS`, `EDIT_BUILDERS` and `I2V_BUILDERS` (Task 5); `ComfyClient` (Task 4); `ServeConfig`, `start`, `stop` and `wait_ready` (Task 3).
- Produces:
  - In `cases.py`: `CASES: tuple[Case, ...]` (9 entries); `Case` with `.id`, `.prompt`, `.owl_queries` and `.ocr_target`; `IDENTITY_REFERENCE`, `SHOTS` (5 entries), `LIGHTING` (3 keys: day, dusk, ir_night); `identity_edit_prompt(shot, lighting)` and `identity_t2i_prompt(shot, lighting)`; `CLIPS` (4 entries); `SEEDS`, `CLIP_SEEDS`; `MODEL_SIZES`, `CLIP_SIZE`, `CLIP_FRAMES`; `T2I_MODELS`, `EDIT_MODELS`, `I2V_MODELS`; `KEYFRAME_MODEL`, `KEYFRAME_SEED`.
  - In `plan.py`: `Job` (frozen) with fields `model`, `kind`, `case`, `seed`, `prompt`, `width`, `height`, `output`, `inputs` and `frames`; `image_jobs() -> list[Job]`, `clip_jobs() -> list[Job]`, `keyframe_path(ref: str) -> str`, `pending(jobs, root) -> list[Job]`.
  - In `run.py`: `parse_used_mib(text) -> int`, `VramSampler`, `run_job(job, client, root) -> dict[str, Any]`, `execute(jobs, client, root) -> None`, `main(argv) -> int`.
- Outputs under `<root>` (default `$SYNTHBENCH_ROOT/p1`):

  - `images/<model>/<case>/<seed>.png`
  - `images/<model>/identity/{reference,<shot>_<lighting>}.png`
  - `clips/<model>/<clip>/<seed>.mp4`
  - `records.jsonl` (one row per job) and `groups.jsonl` (one row per model group: `seconds`, `peak_vram_mib`).

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/synthbench/spikes/__init__.py`: empty file.

`backend/tests/unit/synthbench/spikes/test_p1_plan.py`:

```python
"""P1 bake-off job expansion: counts, stage-major order, identity and keyframe wiring."""

from __future__ import annotations

from itertools import groupby
from pathlib import Path

from synthbench.spikes.p1_bakeoff import cases as c
from synthbench.spikes.p1_bakeoff.plan import clip_jobs, image_jobs, keyframe_path, pending


def test_image_job_counts() -> None:
    jobs = image_jobs()
    per_model = len(c.CASES) * len(c.SEEDS) + 1 + len(c.SHOTS) * len(c.LIGHTING)
    assert per_model == 52
    assert len(jobs) == per_model * len(c.T2I_MODELS) == 312


def test_jobs_are_stage_major_so_each_model_loads_once() -> None:
    models = [model for model, _ in groupby(image_jobs(), key=lambda j: j.model)]
    assert models == list(c.T2I_MODELS)


def test_edit_models_edit_their_own_reference_and_others_prompt_it() -> None:
    jobs = image_jobs()
    for model in c.T2I_MODELS:
        identity = [j for j in jobs if j.model == model and j.case == "identity"]
        assert len(identity) == 15
        reference = next(j for j in jobs if j.model == model and j.case == "identity_reference")
        assert jobs.index(reference) < min(jobs.index(j) for j in identity)
        if model in c.EDIT_MODELS:
            assert {j.kind for j in identity} == {"edit"}
            assert {j.inputs for j in identity} == {(reference.output,)}
        else:
            assert {j.kind for j in identity} == {"t2i"}


def test_every_output_path_is_unique() -> None:
    outputs = [j.output for j in image_jobs() + clip_jobs()]
    assert len(outputs) == len(set(outputs))


def test_clip_jobs_use_keyframes_from_the_keyframe_model() -> None:
    jobs = clip_jobs()
    assert len(jobs) == len(c.I2V_MODELS) * len(c.CLIPS) * len(c.CLIP_SEEDS) == 16
    assert {j.inputs[0].split("/")[1] for j in jobs} == {c.KEYFRAME_MODEL}
    assert {j.frames for j in jobs if j.model == "ltx-2.5"} == {c.CLIP_FRAMES["ltx-2.5"]}


def test_keyframe_paths() -> None:
    assert keyframe_path("knife") == f"images/{c.KEYFRAME_MODEL}/knife/{c.KEYFRAME_SEED}.png"
    assert keyframe_path("identity:1:day") == f"images/{c.KEYFRAME_MODEL}/identity/1_day.png"


def test_pending_skips_finished_outputs(tmp_path: Path) -> None:
    jobs = image_jobs()[:2]
    done = tmp_path / jobs[0].output
    done.parent.mkdir(parents=True)
    done.write_bytes(b"png")
    assert pending(jobs, tmp_path) == jobs[1:]


def test_every_case_prompt_names_the_security_camera_framing() -> None:
    assert all("security camera" in case.prompt for case in c.CASES)
    assert next(case for case in c.CASES if case.id == "legible_plate").ocr_target == "8KXR-417"
```

`backend/tests/unit/synthbench/spikes/test_p1_run.py`:

```python
"""P1 runner: records failures without stopping, writes outputs, samples VRAM."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from synthbench.spikes.p1_bakeoff import run
from synthbench.spikes.p1_bakeoff.plan import image_jobs


class FakeClient:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.graphs: list[dict[str, Any]] = []

    def upload_image(self, path: Path) -> str:
        return path.name

    def run(self, graph: dict[str, Any], *, timeout_s: float) -> list[bytes]:
        self.graphs.append(graph)
        if self.fail:
            raise RuntimeError("CUDA out of memory")
        return [b"\x89PNG-bytes"]


def test_parse_used_mib_takes_the_max_line() -> None:
    assert run.parse_used_mib("1024\n  2048 \n\n") == 2048


def test_a_successful_job_writes_its_output_and_a_record(tmp_path: Path) -> None:
    job = image_jobs()[0]
    record = run.run_job(job, FakeClient(), tmp_path)
    assert (tmp_path / job.output).read_bytes() == b"\x89PNG-bytes"
    assert record["ok"] is True and record["error"] is None and record["seconds"] >= 0
    rows = [json.loads(line) for line in (tmp_path / "records.jsonl").read_text().splitlines()]
    assert rows == [record]


def test_a_failed_job_is_recorded_and_does_not_raise(tmp_path: Path) -> None:
    job = image_jobs()[0]
    record = run.run_job(job, FakeClient(fail=True), tmp_path)
    assert record["ok"] is False
    assert record["error"].startswith("RuntimeError: CUDA out of memory")
    assert not (tmp_path / job.output).exists()


def test_execute_writes_one_group_row_per_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run, "_query_used_mib", lambda: 4096)
    jobs = [j for j in image_jobs() if j.case == "knife" and j.seed == 11]
    run.execute(jobs, FakeClient(), tmp_path)
    groups = [json.loads(line) for line in (tmp_path / "groups.jsonl").read_text().splitlines()]
    assert [g["model"] for g in groups] == sorted({j.model for j in jobs}, key=[j.model for j in jobs].index)
    assert all(g["jobs"] == 1 and g["peak_vram_mib"] == 4096 for g in groups)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest backend/tests/unit/synthbench/spikes/ -n0 -q`
Expected: `ModuleNotFoundError: No module named 'synthbench.spikes'`.

- [ ] **Step 3: Implement `cases.py`**

```python
"""P1 bake-off cases (spec §3.7). Security-camera framing; realistic and
non-graphic (spec §3.8); the identity is invented, never a real person."""

from __future__ import annotations

from dataclasses import dataclass

DAY = (
    "Photorealistic still from a fixed outdoor security camera mounted under the eaves about "
    "three meters high, wide-angle lens looking down at the scene, daytime, natural color, "
    "ordinary suburban home, no text, no watermark."
)
DUSK = (
    "Photorealistic still from a fixed outdoor security camera mounted under the eaves about "
    "three meters high, wide-angle lens looking down at the scene, at dusk with low warm light "
    "and the porch light on, ordinary suburban home, no text, no watermark."
)
IR_NIGHT = (
    "Photorealistic still from a fixed outdoor security camera at night in infrared "
    "night-vision mode, monochrome grayscale, IR illumination with slight noise and bloom, "
    "wide-angle lens mounted under the eaves looking down, no text, no watermark."
)


@dataclass(frozen=True)
class Case:
    id: str
    scene: str
    camera: str
    owl_queries: tuple[str, ...]
    ocr_target: str | None = None

    @property
    def prompt(self) -> str:
        return f"{self.scene} {self.camera}"


CASES: tuple[Case, ...] = (
    Case("handgun_in_hand", "A man in a dark hoodie walks up the driveway toward the front door "
         "holding a black handgun in his right hand, arm down at his side, the handgun clearly "
         "visible.", DAY, ("a handgun", "a person")),
    Case("knife", "A person in a gray jacket stands on the front porch beside the door holding "
         "a large kitchen knife, the blade clearly visible.", DAY, ("a knife", "a person")),
    Case("crowbar_at_door", "A person crouches at the back door prying at the door frame with a "
         "steel crowbar wedged between the door and the frame.", DAY,
         ("a crowbar", "a door", "a person")),
    Case("balaclava_ir_night", "A person wearing a black balaclava ski mask that covers the "
         "whole face except the eyes walks along the side of the house.", IR_NIGHT,
         ("a ski mask", "a person")),
    Case("forced_door", "The front door has been kicked in and hangs open, the door frame "
         "splintered and broken wood scattered on the porch floor.", DAY,
         ("a broken door", "a door")),
    Case("pried_window", "A person in dark clothes climbs through a ground-floor window after "
         "prying it open, the window frame bent.", DUSK, ("a window", "a person")),
    Case("child_alone_pool", "A small child about four years old stands alone at the edge of "
         "the backyard swimming pool, with no adult anywhere in view.", DAY,
         ("a child", "a swimming pool")),
    Case("smoke_from_eave", "Thick gray smoke pours out from under the roof eave of the "
         "two-story house.", DUSK, ("smoke", "a house")),
    Case("legible_plate", "A silver sedan is parked in the driveway facing the camera, its "
         "front license plate clearly readable: 8KXR-417.", DAY,
         ("a license plate", "a car"), ocr_target="8KXR-417"),
)

IDENTITY_PERSON = (
    "a man in his forties with short curly black hair, a trimmed beard, a small scar above the "
    "left eyebrow, wearing a navy windbreaker"
)
IDENTITY_REFERENCE = (
    f"Photorealistic portrait of {IDENTITY_PERSON}, standing on a front porch facing the camera, "
    "even daylight, sharp focus on the face."
)
SHOTS: tuple[str, ...] = (
    "standing on the front porch facing the camera",
    "walking up the driveway toward the camera",
    "opening the side gate",
    "at the front door in three-quarter view",
    "looking back over his shoulder toward the street",
)
LIGHTING: dict[str, str] = {"day": DAY, "dusk": DUSK, "ir_night": IR_NIGHT}


def identity_edit_prompt(shot: str, lighting: str) -> str:
    return (
        "The same man as in the reference image, with the same face, hair, beard, scar and navy "
        f"windbreaker, {shot}. {LIGHTING[lighting]}"
    )


def identity_t2i_prompt(shot: str, lighting: str) -> str:
    return f"{IDENTITY_PERSON[0].upper()}{IDENTITY_PERSON[1:]}, {shot}. {LIGHTING[lighting]}"


@dataclass(frozen=True)
class ClipCase:
    id: str
    keyframe: str  # a Case id, or "identity:<shot index>:<lighting>"
    motion: str


CLIPS: tuple[ClipCase, ...] = (
    ClipCase("armed_approach", "handgun_in_hand", "The man keeps walking steadily up the "
             "driveway toward the front door, the handgun still in his hand. Fixed camera, no "
             "camera movement."),
    ClipCase("pry_door", "crowbar_at_door", "The person levers the crowbar back and forth, "
             "forcing the door frame. Fixed camera, no camera movement."),
    ClipCase("child_pool", "child_alone_pool", "The child takes a small step closer to the "
             "water's edge and looks down at the pool. Fixed camera, no camera movement."),
    ClipCase("identity_walk", "identity:1:day", "The man walks up the driveway toward the "
             "camera and stops near the porch. Fixed camera, no camera movement."),
)

SEEDS: tuple[int, ...] = (11, 22, 33, 44)
CLIP_SEEDS: tuple[int, ...] = (11, 22)
MODEL_SIZES: dict[str, tuple[int, int]] = {
    "flux2-dev": (1920, 1088),
    "flux2-klein-4b": (1344, 768),
    "qwen-image-2.1": (1664, 928),
    "z-image-turbo": (1920, 1088),
    "hidream-i1-full": (1360, 768),
    "ideogram-4": (1920, 1088),
}
T2I_MODELS: tuple[str, ...] = tuple(MODEL_SIZES)
EDIT_MODELS: tuple[str, ...] = ("qwen-image-2.1", "flux2-dev", "flux2-klein-4b")
I2V_MODELS: tuple[str, ...] = ("ltx-2.5", "wan2.2-i2v")
CLIP_SIZE: tuple[int, int] = (1280, 720)
CLIP_FRAMES: dict[str, int] = {"ltx-2.5": 97, "wan2.2-i2v": 81}
KEYFRAME_MODEL = "flux2-dev"
KEYFRAME_SEED = 11
```

(If Task 5's template study showed a model's native 16:9 size differs from `MODEL_SIZES`, use the template's size and note it in the report.)

- [ ] **Step 4: Implement `plan.py`**

```python
"""Expand the P1 cases into jobs, stage-major (each model's jobs are contiguous)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from synthbench.spikes.p1_bakeoff import cases as c


@dataclass(frozen=True)
class Job:
    model: str
    kind: str  # "t2i" | "edit" | "i2v"
    case: str
    seed: int
    prompt: str
    width: int
    height: int
    output: str  # relative to the bake-off root
    inputs: tuple[str, ...] = ()
    frames: int = 0


def image_jobs() -> list[Job]:
    jobs: list[Job] = []
    for model in c.T2I_MODELS:
        width, height = c.MODEL_SIZES[model]
        for case in c.CASES:
            for seed in c.SEEDS:
                out = f"images/{model}/{case.id}/{seed}.png"
                jobs.append(Job(model, "t2i", case.id, seed, case.prompt, width, height, out))
        reference = f"images/{model}/identity/reference.png"
        jobs.append(
            Job(model, "t2i", "identity_reference", c.SEEDS[0], c.IDENTITY_REFERENCE,
                width, height, reference)
        )
        for index, shot in enumerate(c.SHOTS):
            for lighting in c.LIGHTING:
                out = f"images/{model}/identity/{index}_{lighting}.png"
                if model in c.EDIT_MODELS:
                    prompt = c.identity_edit_prompt(shot, lighting)
                    jobs.append(Job(model, "edit", "identity", c.SEEDS[0], prompt, width, height,
                                    out, inputs=(reference,)))
                else:
                    prompt = c.identity_t2i_prompt(shot, lighting)
                    jobs.append(Job(model, "t2i", "identity", c.SEEDS[0], prompt, width, height, out))
    return jobs


def keyframe_path(ref: str) -> str:
    if ref.startswith("identity:"):
        _, shot, lighting = ref.split(":")
        return f"images/{c.KEYFRAME_MODEL}/identity/{shot}_{lighting}.png"
    return f"images/{c.KEYFRAME_MODEL}/{ref}/{c.KEYFRAME_SEED}.png"


def clip_jobs() -> list[Job]:
    jobs: list[Job] = []
    width, height = c.CLIP_SIZE
    for model in c.I2V_MODELS:
        for clip in c.CLIPS:
            for seed in c.CLIP_SEEDS:
                jobs.append(
                    Job(model, "i2v", clip.id, seed, clip.motion, width, height,
                        f"clips/{model}/{clip.id}/{seed}.mp4",
                        inputs=(keyframe_path(clip.keyframe),), frames=c.CLIP_FRAMES[model])
                )
    return jobs


def pending(jobs: list[Job], root: Path) -> list[Job]:
    return [job for job in jobs if not (root / job.output).exists()]
```

- [ ] **Step 5: Implement `run.py`**

```python
"""Run the P1 bake-off. Inside a GPU window:

    python -m synthbench.generate.window run -- \
        python -m synthbench.spikes.p1_bakeoff.run all

Resumable (finished outputs are skipped). One row per job goes to
<root>/records.jsonl; one row per model group (seconds, peak VRAM) to
<root>/groups.jsonl. A failed job is recorded, never fatal: "model X cannot
render Y" is a bake-off result.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import asdict
from pathlib import Path
from types import FrameType, TracebackType
from typing import Any, Protocol

from synthbench.generate.comfy import graphs, serve
from synthbench.generate.comfy.client import ComfyClient, Graph
from synthbench.spikes.p1_bakeoff.plan import Job, clip_jobs, image_jobs, pending


class Client(Protocol):
    def upload_image(self, path: Path) -> str: ...

    def run(self, graph: Graph, *, timeout_s: float) -> list[bytes]: ...


def parse_used_mib(text: str) -> int:
    return max(int(line.strip()) for line in text.splitlines() if line.strip())


def _query_used_mib() -> int:
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
        capture_output=True, text=True, timeout=10, check=True,
    ).stdout
    return parse_used_mib(out)


class VramSampler:
    """Samples GPU memory.used (MiB) once a second; .peak_mib after exit."""

    def __init__(self, interval_s: float = 1.0) -> None:
        self.peak_mib = 0
        self._interval = interval_s
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _sample(self) -> None:
        try:
            self.peak_mib = max(self.peak_mib, _query_used_mib())
        except (OSError, subprocess.SubprocessError, ValueError):
            pass

    def _loop(self) -> None:
        while not self._stop.wait(self._interval):
            self._sample()

    def __enter__(self) -> VramSampler:
        self._sample()  # synchronous first sample: a group shorter than one interval still counts
        self._thread.start()
        return self

    def __exit__(
        self, _t: type[BaseException] | None, _e: BaseException | None, _tb: TracebackType | None
    ) -> None:
        self._stop.set()
        self._thread.join(timeout=5)
        self._sample()


def _append(path: Path, row: dict[str, Any]) -> None:
    with path.open("a") as fh:
        fh.write(json.dumps(row) + "\n")


def _graph(job: Job, names: list[str]) -> Graph:
    if job.kind == "t2i":
        return graphs.T2I_BUILDERS[job.model](job.prompt, seed=job.seed, width=job.width, height=job.height)
    if job.kind == "edit":
        return graphs.EDIT_BUILDERS[job.model](
            job.prompt, images=names, seed=job.seed, width=job.width, height=job.height
        )
    return graphs.I2V_BUILDERS[job.model](
        job.prompt, image=names[0], seed=job.seed, width=job.width, height=job.height,
        frames=job.frames,
    )


def run_job(job: Job, client: Client, root: Path) -> dict[str, Any]:
    started = time.monotonic()
    record: dict[str, Any] = asdict(job) | {"ok": False, "error": None, "seconds": None}
    try:
        names = [client.upload_image(root / p) for p in job.inputs]
        blobs = client.run(_graph(job, names), timeout_s=1800.0 if job.kind == "i2v" else 600.0)
        if not blobs:
            raise RuntimeError("the graph produced no output file")
        out = root / job.output
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(blobs[0])
        record["ok"] = True
    except Exception as exc:  # noqa: BLE001 - a failure is a bake-off result, never fatal
        record["error"] = f"{type(exc).__name__}: {exc}"[:500]
    record["seconds"] = round(time.monotonic() - started, 3)
    _append(root / "records.jsonl", record)
    return record


def execute(jobs: list[Job], client: Client, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for model, group_iter in itertools.groupby(jobs, key=lambda j: j.model):
        group = list(group_iter)
        started = time.monotonic()
        with VramSampler() as vram:
            for job in group:
                run_job(job, client, root)
        _append(root / "groups.jsonl", {
            "model": model, "jobs": len(group),
            "seconds": round(time.monotonic() - started, 1), "peak_vram_mib": vram.peak_mib,
        })


def _raise_on_sigterm(signum: int, _frame: FrameType | None) -> None:
    raise SystemExit(128 + signum)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m synthbench.spikes.p1_bakeoff.run")
    parser.add_argument("stage", choices=["images", "clips", "all"])
    parser.add_argument("--root", type=Path,
                        default=Path(os.environ.get("SYNTHBENCH_ROOT", "/export/synthbench")) / "p1")
    parser.add_argument("--models", default="", help="comma-separated model filter")
    args = parser.parse_args(argv)
    wanted = {m for m in args.models.split(",") if m}
    jobs = (image_jobs() if args.stage in {"images", "all"} else []) + (
        clip_jobs() if args.stage in {"clips", "all"} else []
    )
    jobs = [j for j in pending(jobs, args.root) if not wanted or j.model in wanted]
    signal.signal(signal.SIGTERM, _raise_on_sigterm)
    cfg = serve.ServeConfig.from_env()
    serve.start(cfg)
    try:
        serve.wait_ready(cfg.base_url)
        client = ComfyClient(cfg.base_url)
        try:
            execute(jobs, client, args.root)
        finally:
            client.close()
    finally:
        serve.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Note: `stage all` runs the image jobs and then the clip jobs in one process, so the keyframes exist before the clip jobs start. `pending` is evaluated once at start, so a clip job whose keyframe failed simply records a failure.

- [ ] **Step 6: Run the tests, lint, commit**

```bash
uv run pytest backend/tests/unit/synthbench/spikes/ -n0 -q
uv run ruff check --fix synthbench/spikes/ backend/tests/unit/synthbench/spikes/
uv run ruff format synthbench/spikes/ backend/tests/unit/synthbench/spikes/
uv run mypy synthbench/ --ignore-missing-imports
uvx pre-commit run --files synthbench/spikes/__init__.py synthbench/spikes/p1_bakeoff/__init__.py synthbench/spikes/p1_bakeoff/cases.py synthbench/spikes/p1_bakeoff/plan.py synthbench/spikes/p1_bakeoff/run.py backend/tests/unit/synthbench/spikes/__init__.py backend/tests/unit/synthbench/spikes/test_p1_plan.py backend/tests/unit/synthbench/spikes/test_p1_run.py
git add synthbench/spikes/ backend/tests/unit/synthbench/spikes/
git commit -m "feat(synthbench): P1 bake-off cases, stage-major job plan and resumable runner (spike)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Measurement, contact sheet and report (spike)

**Files:**

- Create: `synthbench/spikes/p1_bakeoff/measure.py`, `synthbench/spikes/p1_bakeoff/sheet.py`, `synthbench/spikes/p1_bakeoff/report.py`
- Test: `backend/tests/unit/synthbench/spikes/test_p1_measure.py`, `backend/tests/unit/synthbench/spikes/test_p1_report.py`

**Interfaces:**

- Consumes: `records.jsonl` and `groups.jsonl` (Task 6), `CASES`, `EDIT_MODELS` and `I2V_MODELS` (Task 6).
- Produces:

  - In `measure.py`: `normalize_plate(text) -> str`, `cer(pred, target) -> float`, `cosine_distance(a, b) -> float`, `measure_record(record, root, tools) -> dict[str, Any]`, and `main()`, which runs **inside the renderer image** and writes `<root>/measures.jsonl`.
  - In `sheet.py`: `render(records, measures, root) -> str`; `main()` writes `<root>/sheet.html`.
  - In `report.py`: `summarize(records, groups, measures, ratings) -> dict[str, Any]`, `propose_picks(summary) -> dict[str, str]`, `to_markdown(summary, picks) -> str`; `main()` writes `docs/benchmarks/synthbench/p1-bakeoff.md`.

- [ ] **Step 1: Write the failing tests (pure logic only)**

`backend/tests/unit/synthbench/spikes/test_p1_measure.py`:

```python
"""P1 measurement helpers and per-record dispatch (fake tools; no GPU)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from synthbench.spikes.p1_bakeoff import measure as m


def test_normalize_plate() -> None:
    assert m.normalize_plate(" 8kxr–417 ") == "8KXR417"
    assert m.normalize_plate("8KXR-417") == "8KXR-417"


@pytest.mark.parametrize(("pred", "target", "expected"), [
    ("8KXR-417", "8KXR-417", 0.0), ("8KXR-41", "8KXR-417", 0.125), ("", "8KXR-417", 1.0),
])
def test_cer(pred: str, target: str, expected: float) -> None:
    assert m.cer(pred, target) == pytest.approx(expected)


def test_cosine_distance() -> None:
    assert m.cosine_distance([1.0, 0.0], [1.0, 0.0]) == pytest.approx(0.0)
    assert m.cosine_distance([1.0, 0.0], [0.0, 1.0]) == pytest.approx(1.0)


class FakeTools:
    def owl(self, image: Path, queries: tuple[str, ...]) -> dict[str, float]:
        return {q: 0.5 for q in queries}

    def ocr(self, image: Path) -> str:
        return "8KXR-417"

    def face(self, image: Path) -> list[float] | None:
        return [1.0, 0.0]

    def clip_faces(self, clip: Path) -> list[list[float]]:
        return [[1.0, 0.0], [0.6, 0.8]]


def _rec(**kw: Any) -> dict[str, Any]:
    return {"model": "flux2-dev", "kind": "t2i", "case": "knife", "seed": 11,
            "output": "images/x.png", "ok": True} | kw


def test_case_records_get_owl_scores(tmp_path: Path) -> None:
    out = m.measure_record(_rec(), tmp_path, FakeTools())
    assert out["owl"] == {"a knife": 0.5, "a person": 0.5}


def test_the_plate_case_is_read(tmp_path: Path) -> None:
    out = m.measure_record(_rec(case="legible_plate"), tmp_path, FakeTools())
    assert out["plate_exact"] is True and out["plate_cer"] == 0.0


def test_identity_records_get_an_embedding(tmp_path: Path) -> None:
    out = m.measure_record(_rec(case="identity"), tmp_path, FakeTools())
    assert out["face"] == [1.0, 0.0]


def test_clips_get_frame_drift(tmp_path: Path) -> None:
    out = m.measure_record(_rec(kind="i2v", case="identity_walk", output="clips/c.mp4"), tmp_path, FakeTools())
    assert out["frame_drift_max"] == pytest.approx(0.4)
```

`backend/tests/unit/synthbench/spikes/test_p1_report.py`:

```python
"""P1 report aggregation and pick proposal."""

from __future__ import annotations

from typing import Any

from synthbench.spikes.p1_bakeoff import report as r


def _records() -> list[dict[str, Any]]:
    rows = []
    for model, secs in (("a", 5.0), ("b", 20.0)):
        for case in ("knife", "handgun_in_hand", "legible_plate"):
            rows.append({"model": model, "kind": "t2i", "case": case, "seed": 11,
                         "output": f"images/{model}/{case}/11.png", "ok": True, "seconds": secs})
    rows.append({"model": "b", "kind": "t2i", "case": "knife", "seed": 22,
                 "output": "images/b/knife/22.png", "ok": False, "seconds": 1.0, "error": "OOM"})
    return rows


def _ratings() -> dict[str, dict[str, str]]:
    ratings = {f"images/a/{c}/11.png": {"rating": "good"} for c in ("knife", "handgun_in_hand")}
    ratings |= {f"images/b/{c}/11.png": {"rating": "fail"} for c in ("knife", "handgun_in_hand")}
    return ratings


def _measures() -> list[dict[str, Any]]:
    return [
        {"output": "images/a/legible_plate/11.png", "plate_exact": True, "plate_cer": 0.0},
        {"output": "images/b/legible_plate/11.png", "plate_exact": False, "plate_cer": 0.5},
    ]


def test_summarize_per_model() -> None:
    s = r.summarize(_records(), [{"model": "a", "peak_vram_mib": 30720}], _measures(), _ratings())
    a, b = s["models"]["a"], s["models"]["b"]
    assert (a["ok"], a["failed"], b["failed"]) == (3, 0, 1)
    assert a["median_seconds"] == 5.0
    assert a["peak_vram_gib"] == 30.0
    assert a["threat_good_rate"] == 1.0 and b["threat_good_rate"] == 0.0
    assert a["plate_exact_rate"] == 1.0 and b["plate_mean_cer"] == 0.5


def test_propose_picks_prefers_rated_quality_then_speed() -> None:
    s = r.summarize(_records(), [], _measures(), _ratings())
    picks = r.propose_picks(s)
    assert picks["t2i_quality"] == "a"
    assert picks["text"] == "a"


def test_markdown_has_a_row_per_model_and_the_picks() -> None:
    s = r.summarize(_records(), [], _measures(), _ratings())
    text = r.to_markdown(s, r.propose_picks(s))
    assert "| a |" in text and "| b |" in text and "Proposed picks" in text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest backend/tests/unit/synthbench/spikes/test_p1_measure.py backend/tests/unit/synthbench/spikes/test_p1_report.py -n0 -q`
Expected: `ImportError` for `measure` / `report`.

- [ ] **Step 3: Implement `measure.py`**

The pure helpers and dispatch below are complete. The `RealTools` class loads its models lazily and runs only inside the renderer image, where `transformers`, `facenet_pytorch`, `easyocr` and `av` are installed. Its imports stay inside its methods so the unit tests never need them.

```python
"""P1 measurement (spec §3.7): OWLv2 prop adherence, facenet identity drift,
EasyOCR plate reading. All three are independent of the pipeline's models.

Run inside the renderer image (GPU; the flagship may stay up):
    podman run --rm --device nvidia.com/gpu=all -v "$PWD":/work:ro -w /work \
      -v /export/synthbench:/export/synthbench -v /export/synthbench/cache:/root/.cache \
      -e SYNTHBENCH_ROOT=/export/synthbench --entrypoint python \
      localhost/synthbench-comfyui:v0.37.0 -m synthbench.spikes.p1_bakeoff.measure
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Protocol

from synthbench.spikes.p1_bakeoff.cases import CASES

_CASES = {case.id: case for case in CASES}
OWL_MODEL = "google/owlv2-base-patch16-ensemble"


def normalize_plate(text: str) -> str:
    return re.sub(r"[^A-Z0-9-]", "", text.upper())


def cer(pred: str, target: str) -> float:
    """Character error rate: Levenshtein distance / len(target)."""
    prev = list(range(len(target) + 1))
    for i, pc in enumerate(pred, start=1):
        cur = [i]
        for j, tc in enumerate(target, start=1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (pc != tc)))
        prev = cur
    return prev[-1] / max(len(target), 1)


def cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return 1.0 - dot / norm if norm else 1.0


class Tools(Protocol):
    def owl(self, image: Path, queries: tuple[str, ...]) -> dict[str, float]: ...

    def ocr(self, image: Path) -> str: ...

    def face(self, image: Path) -> list[float] | None: ...

    def clip_faces(self, clip: Path) -> list[list[float]]: ...


def measure_record(record: dict[str, Any], root: Path, tools: Tools) -> dict[str, Any]:
    path = root / record["output"]
    out: dict[str, Any] = {"output": record["output"]}
    if record["kind"] == "i2v":
        faces = tools.clip_faces(path)
        out["frames_with_face"] = len(faces)
        out["frame_drift_max"] = max((cosine_distance(faces[0], f) for f in faces[1:]), default=None)
        return out
    case = _CASES.get(record["case"])
    if case is not None:
        out["owl"] = tools.owl(path, case.owl_queries)
        if case.ocr_target:
            text = normalize_plate(tools.ocr(path))
            out["plate_text"] = text
            out["plate_exact"] = text == case.ocr_target
            out["plate_cer"] = cer(text, case.ocr_target)
    if record["case"] in {"identity", "identity_reference"}:
        out["face"] = tools.face(path)
    return out


class RealTools:  # pragma: no cover - runs in the renderer image only
    def __init__(self) -> None:
        import torch  # noqa: PLC0415

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._owl: Any = None
        self._ocr: Any = None
        self._faces: Any = None

    def owl(self, image: Path, queries: tuple[str, ...]) -> dict[str, float]:
        import torch  # noqa: PLC0415
        from PIL import Image  # noqa: PLC0415
        from transformers import Owlv2ForObjectDetection, Owlv2Processor  # noqa: PLC0415

        if self._owl is None:
            self._owl = (Owlv2Processor.from_pretrained(OWL_MODEL),
                         Owlv2ForObjectDetection.from_pretrained(OWL_MODEL).to(self._device).eval())
        processor, model = self._owl
        img = Image.open(image).convert("RGB")
        inputs = processor(text=[list(queries)], images=img, return_tensors="pt").to(self._device)
        with torch.no_grad():
            logits = model(**inputs).logits[0].sigmoid()  # (boxes, queries)
        return {q: round(float(logits[:, i].max()), 4) for i, q in enumerate(queries)}

    def ocr(self, image: Path) -> str:
        import easyocr  # noqa: PLC0415

        if self._ocr is None:
            self._ocr = easyocr.Reader(["en"], gpu=self._device == "cuda")
        results = self._ocr.readtext(str(image))
        return " ".join(text for _box, text, _conf in sorted(results, key=lambda r: -r[2]))

    def _face_models(self) -> Any:
        from facenet_pytorch import MTCNN, InceptionResnetV1  # noqa: PLC0415

        if self._faces is None:
            self._faces = (MTCNN(image_size=160, device=self._device),
                           InceptionResnetV1(pretrained="vggface2").eval().to(self._device))
        return self._faces

    def _embed(self, pil_image: Any) -> list[float] | None:
        import torch  # noqa: PLC0415

        detector, embedder = self._face_models()
        crop = detector(pil_image)
        if crop is None:
            return None
        with torch.no_grad():
            vector = embedder(crop.unsqueeze(0).to(self._device))[0]
        return [round(float(x), 6) for x in vector]

    def face(self, image: Path) -> list[float] | None:
        from PIL import Image  # noqa: PLC0415

        return self._embed(Image.open(image).convert("RGB"))

    def clip_faces(self, clip: Path) -> list[list[float]]:
        import av  # noqa: PLC0415

        with av.open(str(clip)) as container:
            frames = [f.to_image() for f in container.decode(video=0)]
        step = max(len(frames) // 8, 1)
        faces = [self._embed(frame) for frame in frames[::step][:8]]
        return [f for f in faces if f is not None]


def main() -> int:  # pragma: no cover - runs in the renderer image only
    root = Path(os.environ.get("SYNTHBENCH_ROOT", "/export/synthbench")) / "p1"
    records = [json.loads(line) for line in (root / "records.jsonl").read_text().splitlines()]
    latest = {r["output"]: r for r in records}  # a resumed job's last row wins
    tools = RealTools()
    with (root / "measures.jsonl").open("w") as fh:
        for record in latest.values():
            if record["ok"]:
                fh.write(json.dumps(measure_record(record, root, tools)) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Implement `sheet.py`**

This is a static HTML contact sheet, opened from `/export/synthbench/p1/sheet.html`. It has one section per case (and per clip case), one row per model and one column per seed. Each cell shows:

- the image or `<video controls>`;
- the OWLv2 scores or plate text from `measures.jsonl`;
- three radio buttons (`good` / `partial` / `fail`) named by the record's `output` path, plus a note input.

Failed records show their error text instead of media. A "Download ratings.json" button serializes `{output: {rating, note}}` with a `Blob` download, and the owner saves the file as `/export/synthbench/p1/ratings.json`.

`render(records, measures, root) -> str` is pure and escapes every string with `html.escape`. `main()` reads the JSONL files and writes `sheet.html`.

Add this test to `test_p1_report.py`:

```python
def test_sheet_has_one_rating_group_per_ok_record() -> None:
    from synthbench.spikes.p1_bakeoff import sheet

    html = sheet.render(_records(), _measures(), root=None)
    for rec in _records():
        if rec["ok"]:
            assert f'name="{rec["output"]}"' in html
    assert "OOM" in html and "ratings.json" in html
```

(`render` takes `root: Path | None` and uses it only to build relative media paths. The media paths already come relative to `root` from the records.)

- [ ] **Step 5: Implement `report.py`**

`summarize(records, groups, measures, ratings)`:

- Deduplicate records so that each `output`'s last row wins.
- Per model, compute:
  - `ok` and `failed` counts;
  - `median_seconds` (ok image jobs only; clips are separate);
  - `peak_vram_gib` from `groups` (MiB / 1024, rounded to 0.1);
  - `threat_good_rate`: the share of `good` ratings among rated records of the threat cases `handgun_in_hand`, `knife`, `crowbar_at_door`, `balaclava_ir_night`, `forced_door`, `pried_window`, `child_alone_pool` and `smoke_from_eave`;
  - `owl_hit_rate`: the share of case records whose first OWL query scores ≥ 0.30;
  - `plate_exact_rate` and `plate_mean_cer`;
  - `identity_drift_median`: the median cosine distance of the identity images to that model's `identity/reference.png` embedding. Skip images with no face and count them as `identity_no_face`.
- Per clip model: `median_seconds_per_clip`, `frame_drift_median`, `clip_good_rate`.

`propose_picks(summary) -> dict[str, str]` fills these slots, skipping models with fewer than 50% of jobs `ok`:

| Slot          | Rule                                                                             |
| ------------- | -------------------------------------------------------------------------------- |
| `t2i_quality` | highest `threat_good_rate`; tie → lower `median_seconds`                         |
| `t2i_volume`  | highest `threat_good_rate` among models with `median_seconds` ≤ 10               |
| `compositor`  | lowest `identity_drift_median` among `EDIT_MODELS` with `threat_good_rate` ≥ 0.5 |
| `text`        | highest `plate_exact_rate`; tie → lower `plate_mean_cer`                         |
| `animator`    | highest `clip_good_rate`; tie → lower `frame_drift_median`                       |

A slot with no eligible model maps to `"none"`.

`to_markdown(summary, picks)` produces a header with the date, commit and corpus note ("aggregate metrics only; media stays in /export/synthbench/p1"), one table per image model and one per clip model, then "Proposed picks (owner approves into spec rev 2)" and a "Risks R1-R3 outcome" section with placeholders the controller fills in Task 8.

`main()` reads `/export/synthbench/p1/*.jsonl` and `ratings.json`, then writes `docs/benchmarks/synthbench/p1-bakeoff.md`.

- [ ] **Step 6: Run the tests, lint, commit**

```bash
uv run pytest backend/tests/unit/synthbench/spikes/ -n0 -q
uv run ruff check --fix synthbench/spikes/ backend/tests/unit/synthbench/spikes/
uv run ruff format synthbench/spikes/ backend/tests/unit/synthbench/spikes/
uv run mypy synthbench/ --ignore-missing-imports
uvx pre-commit run --files synthbench/spikes/p1_bakeoff/measure.py synthbench/spikes/p1_bakeoff/sheet.py synthbench/spikes/p1_bakeoff/report.py backend/tests/unit/synthbench/spikes/test_p1_measure.py backend/tests/unit/synthbench/spikes/test_p1_report.py
git add synthbench/spikes/p1_bakeoff/ backend/tests/unit/synthbench/spikes/
git commit -m "feat(synthbench): P1 measurement, contact sheet and report aggregation (spike)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Run the bake-off and record the picks (controller + owner)

This task is not dispatched to an implementer subagent. The controller runs it because it opens GPU windows. The owner rates the contact sheet and approves the picks.

- [ ] **Step 1: Weights complete.**
  1. The owner accepts https://huggingface.co/Lightricks/LTX-2.5.
  2. The controller verifies access and then runs `HF_HOME=/export/models uv run python -m synthbench.generate.weights sync --manifest synthbench/generate/manifests/p1-slate.json` (no `--skip-repo`).
  3. Expected: `verified 30 files; 31 links under /export/models/comfyui`. `ae.safetensors` and `qwen_3_4b.safetensors` are each shared by two models, and the three `flux2-vae` files are prefixed per model. Record the output.
- [ ] **Step 2: First window: smoke the four full-GPU graphs.** Run `python -m synthbench.generate.window run -- bash -c 'uv run python -m synthbench.generate.comfy.serve up >/dev/null && uv run python -m synthbench.generate.comfy.smoke --only t2i:flux2-dev,edit:flux2-dev,i2v:ltx-2.5,i2v:wan2.2-i2v; rc=$?; uv run python -m synthbench.generate.comfy.serve down; exit $rc'`.
  - Before starting, tell the owner that the flagship (and with it LiteLLM's `claude-flagship` and the agent-vss1 sandbox) will be down.
  - Confirm afterwards that `python -m synthbench.generate.window status` shows `{"marker": false, "flagship_healthy": true}`.
  - Fix any failing builder through the Task 5 loop (validator, then smoke) before the full run.
- [ ] **Step 3: The full run.** Run `python -m synthbench.generate.window run -- uv run python -m synthbench.spikes.p1_bakeoff.run all`.
  - The run is resumable. If it must be split across windows (for example to give the flagship back during the day), rerun the same command; finished outputs are skipped.
  - Afterwards: `window status` is clean, `records.jsonl` has 328 distinct outputs (312 images + 16 clips) and `groups.jsonl` has one row per model group.
- [ ] **Step 4: Measure (flagship up).** Run the `podman run ... measure` command from the `measure.py` docstring. It writes `measures.jsonl`.
- [ ] **Step 5: Owner rating.**
  1. Run `uv run python -m synthbench.spikes.p1_bakeoff.sheet`.
  2. The owner opens `/export/synthbench/p1/sheet.html`, rates every threat, identity and clip cell, and saves `ratings.json` next to the sheet.
  3. This step waits on the owner.
- [ ] **Step 6: Report.**
  1. Run `uv run python -m synthbench.spikes.p1_bakeoff.report`.
  2. Fill the "Risks R1-R3 outcome" section:
     - **R1:** which threat props each model could or could not render;
     - **R2:** ComfyUI on arm64/sm_103 held (or the fallback used);
     - **R3:** candidate facts confirmed (existence, sizes, gating: FLUX.2-dev, Ideogram 4 and LTX-2.5 were gated and accepted).
  3. Add `docs/benchmarks/synthbench/p1-bakeoff.md` to `docs/benchmarks/AGENTS.md`'s index.
  4. Commit as `docs(synthbench): P1 bake-off report`.
- [ ] **Step 7: Spec rev 2 (owner-gated).**
  1. Present the proposed picks and the report's numbers.
  2. After the owner approves (or overrides) them, update the spec: §3.2's pick column, §3.7 ("picks recorded"), the two §7.1 deviations listed in this plan's Global Constraints, and the revision line (rev 2, date, owner approval).
  3. Commit as `docs(synthbench): spec rev 2 - P1 picks approved`.

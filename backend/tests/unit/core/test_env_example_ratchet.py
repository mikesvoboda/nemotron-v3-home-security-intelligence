"""O3.3 ratchet: every .env.example variable is read by config.py, compose or setup.py,
and every models.yml row names something that loads.

Doctrine (shared with backend/tests/unit/core/test_settings_orphan_ratchet.py and
scripts/ratchet-check.py):
- Re-runs the committed O1.7 scanner (``scripts/audit/env_dead_vars.py``) against the
  live tree rather than comparing to a static count.
- Variables in ``.env.example`` whose readers sit outside the three contract readers
  (``backend/core/config.py``, ``docker-compose*.yml``, ``setup.py``) are listed in
  ``ALLOWED_OUTSIDE_CONTRACT_READERS`` with the exact file that reads them; the test
  verifies both directions (no unreasoned dead var, no zombie allowlist entry, and the
  cited reader file actually references the variable).
- ``.env.example`` carries no duplicate variable assignments.
- Every row in ``models.yml`` is enabled and maps to a live loader:
  * ``service in ("backend", "both")`` -> registered in ``model_zoo._LOADER_MAP`` and
    present in ``get_model_zoo()``
  * ``service in ("ai-gateway", "both")`` -> ``triton_name`` in ``ai/triton/model_repository``
    with a ``config.pbtxt`` and in ``ai.gateway.residency.FULL_MODEL_SET``
  * ``service == "ai-vlm"`` -> ``/models/<runtime_file>`` mounted by ``ai-vlm`` in
    ``docker-compose.prod.yml`` and declared in ``.env.example``
- ``backend/core/config.py`` derives ``Settings.vlm_model_id``'s default from
  ``models.yml`` rather than hardcoding a duplicate model-identity string literal.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from scripts.audit.env_dead_vars import KEY_RE, scan

REPO_ROOT = Path(__file__).resolve().parents[4]
ENV_EXAMPLE = REPO_ROOT / ".env.example"
MODELS_YML = REPO_ROOT / "models.yml"
CONFIG_PY = REPO_ROOT / "backend" / "core" / "config.py"
COMPOSE_PROD = REPO_ROOT / "docker-compose.prod.yml"

# Variables in .env.example whose live readers sit outside the three contract
# files (backend/core/config.py, docker-compose*.yml, setup.py), as documented
# in 00-audit.md §7 and scripts/audit/env_dead_vars.py's DEAD_NOT_DELETABLE_NOTE.
ALLOWED_OUTSIDE_CONTRACT_READERS: dict[str, dict[str, str]] = {
    "TMPDIR": {
        "reader": "setup_lib/deploy.py",
        "reason": "setup.py deploy applies TMPDIR from .env to redirect container build staging off /var/tmp",
    },
    "VITE_DEV_BACKEND_URL": {
        "reader": "frontend/vite.config.ts",
        "reason": "Vite dev server proxy reads VITE_DEV_BACKEND_URL when forwarding /api and /ws",
    },
    "VITE_API_BASE_URL": {
        "reader": "frontend/src/config/env.ts",
        "reason": "Frontend runtime env config reads import.meta.env.VITE_API_BASE_URL",
    },
    "VITE_WS_BASE_URL": {
        "reader": "frontend/src/config/env.ts",
        "reason": "Frontend runtime env config reads import.meta.env.VITE_WS_BASE_URL",
    },
    "SYNTHBENCH_COMFYUI_PORT": {
        "reader": "synthbench/generate/comfy/serve.py",
        "reason": "Synthbench ComfyUI renderer reads SYNTHBENCH_COMFYUI_PORT from env",
    },
    "SYNTHBENCH_ROOT": {
        "reader": "synthbench/contract/store.py",
        "reason": "Synthbench corpus store and CLI commands read SYNTHBENCH_ROOT from env",
    },
    "SYNTHBENCH_PODMAN_ROOT": {
        "reader": "synthbench/generate/podman.py",
        "reason": "Synthbench podman store helper reads SYNTHBENCH_PODMAN_ROOT from env",
    },
}

DELETED_MODELS_YML_ROWS = (
    "yolo11-face",
    "yolo11-license-plate",
    "paddleocr",
    "yolo26-general",
    "nemotron-3-nano-30b-a3b-q4km",
    "florence-2-base",
    "yolov8n-pose",
    "fashion-clip",
    "weather-classification",
)


def test_no_unread_env_example_var_outside_allowlist() -> None:
    result = scan(REPO_ROOT)
    dead = set(result["dead_vars"])
    new_dead = sorted(dead - set(ALLOWED_OUTSIDE_CONTRACT_READERS))
    assert not new_dead, (
        f".env.example variables read by neither config.py, compose nor setup.py: {new_dead}. "
        "Delete dead variables from .env.example (O3.3), or add a reasoned entry in "
        "ALLOWED_OUTSIDE_CONTRACT_READERS naming the live reader file."
    )


def test_allowlist_carries_no_zombies() -> None:
    result = scan(REPO_ROOT)
    dead = set(result["dead_vars"])
    zombies = sorted(set(ALLOWED_OUTSIDE_CONTRACT_READERS) - dead)
    assert not zombies, (
        f"Allowlisted .env.example variables are no longer reported by env_dead_vars.py: {zombies}. "
        "Remove stale allowlist entries in the same PR."
    )


def test_allowlist_entries_name_a_real_reader_file_that_reads_the_var() -> None:
    for var, meta in ALLOWED_OUTSIDE_CONTRACT_READERS.items():
        reader_rel = meta.get("reader", "").strip()
        reason = meta.get("reason", "").strip()
        assert reader_rel and reason, f"{var} allowlist entry must specify reader and reason"
        reader_path = REPO_ROOT / reader_rel
        assert reader_path.is_file(), f"{var} reader file does not exist: {reader_rel}"
        text = reader_path.read_text(encoding="utf-8")
        assert re.search(rf"\b{re.escape(var)}\b", text), (
            f"{var} allowlist reader {reader_rel} no longer references {var}"
        )


def test_no_duplicate_keys_in_env_example() -> None:
    counts: Counter[str] = Counter()
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if m := KEY_RE.match(line):
            counts[m.group(1)] += 1
    duplicates = {k: v for k, v in counts.items() if v > 1}
    assert not duplicates, f"Duplicate variable assignments in .env.example: {duplicates}"


def test_models_yml_dead_rows_deleted_and_every_row_loads() -> None:
    from ai.gateway.residency import FULL_MODEL_SET

    from backend.services.model_zoo import _LOADER_MAP, get_model_zoo, reset_model_zoo

    reset_model_zoo()
    zoo = get_model_zoo()
    rows: list[dict[str, Any]] = yaml.safe_load(MODELS_YML.read_text(encoding="utf-8"))["models"]
    by_name = {r["name"]: r for r in rows}

    for dead_name in DELETED_MODELS_YML_ROWS:
        assert dead_name not in by_name, f"Dead row {dead_name!r} is still in models.yml"

    # yolo26 row corrected: served by ai-gateway Triton, enabled, critical, non-zero vram_mb
    yolo26 = by_name["yolo26"]
    assert yolo26["service"] == "ai-gateway"
    assert yolo26["enabled"] is True
    assert yolo26["vram_mb"] > 0
    assert yolo26["priority"] == "critical"
    assert yolo26["triton_name"] == "yolo26"
    assert yolo26["triton_kind"] == "KIND_GPU"

    # Shipped Qwen3-VL GGUF and mmproj rows present with pinned sha256s
    vlm_rows = [r for r in rows if r.get("service") == "ai-vlm"]
    assert len(vlm_rows) == 2, (
        f"Expected 2 ai-vlm rows (GGUF + mmproj), got {[r['name'] for r in vlm_rows]}"
    )
    vlm_by_file = {r["runtime_file"]: r for r in vlm_rows}
    assert set(vlm_by_file) == {
        "Qwen3VL-8B-Instruct-Q4_K_M.gguf",
        "mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf",
    }
    assert (
        vlm_by_file["Qwen3VL-8B-Instruct-Q4_K_M.gguf"]["sha256"]
        == "67d1659bfe71b89d50b45a4ad1a9e5b997e5bb16ce5da66a6a6167abd569e9e2"  # pragma: allowlist secret
    )
    assert (
        vlm_by_file["mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf"]["sha256"]
        == "c6ba85508d82f42590e6eb77d5340369ab6fecf107a7561d809523d8aa5f3bfd"  # pragma: allowlist secret
    )

    compose_text = COMPOSE_PROD.read_text(encoding="utf-8")
    env_text = ENV_EXAMPLE.read_text(encoding="utf-8")
    triton_repo = REPO_ROOT / "ai" / "triton" / "model_repository"

    # Every row in models.yml is enabled and names something that loads
    for row in rows:
        name = row["name"]
        service = row.get("service")
        assert row.get("enabled") is True, f"models.yml row {name!r} is disabled"
        assert service in ("backend", "ai-gateway", "ai-vlm", "both"), (
            f"models.yml row {name!r} has invalid service {service!r}"
        )
        if service in ("backend", "both"):
            assert name in _LOADER_MAP, (
                f"Backend row {name!r} has no loader in model_zoo._LOADER_MAP"
            )
            assert name in zoo, f"Backend row {name!r} is missing from get_model_zoo()"
        if service in ("ai-gateway", "both"):
            triton_name = row.get("triton_name")
            assert triton_name, f"Gateway row {name!r} has no triton_name"
            assert (triton_repo / triton_name / "config.pbtxt").is_file(), (
                f"Gateway row {name!r} triton_name {triton_name!r} has no config.pbtxt"
            )
            assert triton_name in FULL_MODEL_SET, (
                f"Gateway row {name!r} triton_name {triton_name!r} is not in FULL_MODEL_SET"
            )
        if service == "ai-vlm":
            runtime_file = row.get("runtime_file")
            assert runtime_file and row.get("local_path") == "vlm", (
                f"ai-vlm row {name!r} must declare local_path: vlm and runtime_file"
            )
            container_path = f"/models/{runtime_file}"
            assert container_path in compose_text, (
                f"ai-vlm row {name!r} path {container_path!r} not mounted in docker-compose.prod.yml"
            )
            assert container_path in env_text, (
                f"ai-vlm row {name!r} path {container_path!r} not declared in .env.example"
            )


def test_config_py_derives_vlm_model_id_from_models_yml() -> None:
    from backend.core.config import Settings, _default_vlm_model_id

    config_text = CONFIG_PY.read_text(encoding="utf-8")
    assert '"Qwen3VL-8B-Instruct-Q4_K_M"' not in config_text, (
        "backend/core/config.py must derive vlm_model_id default from models.yml, "
        "not hardcode a duplicate literal"
    )
    assert Settings.model_fields["vlm_model_id"].default == _default_vlm_model_id()
    assert _default_vlm_model_id() == "Qwen3VL-8B-Instruct-Q4_K_M"

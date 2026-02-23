"""Shared loader for models.yml — the single source of truth for model configuration.

Both setup_lib/model_downloader.py and backend/services/model_zoo.py consume this
file to eliminate configuration drift between download orchestration and runtime loading.

Usage (host-side, e.g. setup_lib/model_downloader.py):
    from setup_lib.models_config import load_models_yaml
    models = load_models_yaml()  # auto-resolves project root

Usage (container-side, e.g. backend/services/model_zoo.py):
    from pathlib import Path
    import yaml
    _MODELS_YML = Path(__file__).parents[2] / "models.yml"  # /app/models.yml
    entries = yaml.safe_load(_MODELS_YML.read_text())["models"]
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

# Project root is two levels up from setup_lib/
_PROJECT_ROOT = Path(__file__).parent.parent
_MODELS_YML = _PROJECT_ROOT / "models.yml"


def load_models_yaml(root: Path | None = None) -> list[dict[str, Any]]:
    """Load and return the full model list from models.yml.

    Args:
        root: Optional path to the project root directory. Defaults to the
              directory containing setup_lib/ (i.e. the project root).

    Returns:
        List of model definition dicts as parsed from models.yml.

    Raises:
        FileNotFoundError: If models.yml does not exist at the resolved path.
        ImportError: If PyYAML is not installed.
    """
    if yaml is None:
        raise ImportError("PyYAML is required. Install with: pip install pyyaml")

    yml_path = (root / "models.yml") if root else _MODELS_YML
    if not yml_path.exists():
        raise FileNotFoundError(f"models.yml not found at {yml_path}")

    with yml_path.open() as f:
        data = yaml.safe_load(f)

    return data["models"]


def get_backend_models(root: Path | None = None) -> list[dict[str, Any]]:
    """Return only models with service 'backend' or 'both'.

    These are the models that backend/services/model_zoo.py manages.
    """
    return [
        m for m in load_models_yaml(root)
        if m.get("service") in ("backend", "both")
    ]


def get_downloadable_models(root: Path | None = None) -> list[dict[str, Any]]:
    """Return all models that require a download step.

    Excludes models with download_method='skip' and those with no hf_repo
    and no custom download_method.
    """
    return [
        m for m in load_models_yaml(root)
        if m.get("download_method") != "skip"
        and (m.get("hf_repo") or m.get("download_method"))
    ]

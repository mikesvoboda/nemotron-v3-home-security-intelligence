"""Files that run inside the renderer image (NGC PyTorch, Python 3.12) stay 3.12-parseable."""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
# measure.py and everything it imports from synthbench, package __init__ files included
CONTAINER_FILES = (
    "synthbench/__init__.py",
    "synthbench/spikes/__init__.py",
    "synthbench/spikes/p1_bakeoff/__init__.py",
    "synthbench/spikes/p1_bakeoff/cases.py",
    "synthbench/spikes/p1_bakeoff/measure.py",
)


@pytest.mark.parametrize("rel", CONTAINER_FILES)
def test_parses_as_python_3_12(rel: str) -> None:
    ast.parse((REPO_ROOT / rel).read_text(), filename=rel, feature_version=(3, 12))


def test_ruff_targets_py312_for_every_container_file() -> None:
    ruff = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())["tool"]["ruff"]
    targets = ruff.get("per-file-target-version", {})
    assert {rel: targets.get(rel) for rel in CONTAINER_FILES} == dict.fromkeys(
        CONTAINER_FILES, "py312"
    )

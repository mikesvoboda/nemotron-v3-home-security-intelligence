"""The gateway image runs Python 3.12; the repo targets 3.14.

The ai-gateway image is built FROM the NGC Triton image (Python 3.12) and ships
ai/gateway/ and ai/triton/. The repo's ruff target is py314, and ruff-format on
py314 rewrites `except (A, B):` into PEP 758's unparenthesized form, which 3.12
cannot parse. That happened to ai/gateway/adapters/florence.py; main.py imports
it unconditionally, so the gateway app died at import and the container
restart-looped. Found on the A5500 bring-up (2026-09-28), the first time the
image was rebuilt and run since the rewrite. The synthbench renderer hit the
same trap and pinned its own files to py312 (pyproject per-file-target-version).
"""

from __future__ import annotations

import ast
import tomllib
from fnmatch import fnmatch
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
IMAGE_TREES = ("ai/gateway", "ai/triton")
IMAGE_FILES = sorted(p for tree in IMAGE_TREES for p in (REPO_ROOT / tree).rglob("*.py"))


@pytest.mark.parametrize("path", IMAGE_FILES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_parses_as_python_312(path: Path) -> None:
    try:
        ast.parse(path.read_text(encoding="utf-8"), str(path), feature_version=(3, 12))
    except SyntaxError as e:
        pytest.fail(
            f"{path.relative_to(REPO_ROOT)}:{e.lineno}: {e.msg} - the gateway image is 3.12"
        )


@pytest.mark.parametrize("tree", IMAGE_TREES)
def test_ruff_formats_the_tree_as_py312(tree: str) -> None:
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    targets = config["tool"]["ruff"].get("per-file-target-version", {})
    probe = f"{tree}/some/module.py"
    matched = [v for glob, v in targets.items() if fnmatch(probe, glob)]
    assert matched == ["py312"], (
        f"{tree} ships in the Python 3.12 gateway image, but ruff's per-file-target-version "
        f"gives it {matched or 'the repo default py314'} - ruff-format would strip except "
        "parentheses again"
    )

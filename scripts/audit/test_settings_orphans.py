#!/usr/bin/env python3
"""Tests for scripts/audit/settings_orphans.py (O1.7).

    uv run python -m pytest scripts/audit/test_settings_orphans.py -q

The fixture config pins the three decisions this census exists to get right:
  * a field on a TRANSITIVELY settings class (a nested model inherited by a
    BaseSettings child via an intermediate class) counts — a direct-base-only
    walk would miss the audit's nested fields;
  * a plain dataclass NOT in the settings chain contributes no fields;
  * reads count from compose YAML and setup.py, and a TEST file reading a
    name never rescues it (tests are not consumers).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "audit" / "settings_orphans.py"

CONFIG = """\
from pydantic_settings import BaseSettings


class Inner:
    plain_dataclass_field: int = 0


class Middle(BaseSettings):
    live_via_module: str = "x"
    orphan_field: str = "y"
    florence_url: str = ""


class Outer(Middle):
    nested_live: str = "z"
    nested_orphan: str = "w"
"""

COMPOSE = """\
services:
  backend:
    environment:
      LIVE_VIA_MODULE: ${LIVE_VIA_MODULE}
      NESTED_LIVE: ${NESTED_LIVE}
"""

SETUP_PY = """\
ENV = {"florence_url": "http://florence:8000"}
"""


def build_tree(root: Path) -> None:
    (root / "backend" / "core").mkdir(parents=True)
    (root / "backend" / "__init__.py").write_text("", encoding="utf-8")
    (root / "backend" / "core" / "__init__.py").write_text("", encoding="utf-8")
    (root / "backend" / "core" / "config.py").write_text(CONFIG, encoding="utf-8")
    # a reader in production code
    (root / "backend" / "user.py").write_text(
        "from backend.core.config import settings\n\nprint(settings.nested_live)\n", encoding="utf-8"
    )
    # a TEST reading an orphan must not rescue it
    (root / "backend" / "tests").mkdir()
    (root / "backend" / "tests" / "test_orphan.py").write_text("assert settings.orphan_field\n", encoding="utf-8")
    (root / "docker-compose.yml").write_text(COMPOSE, encoding="utf-8")
    (root / "setup.py").write_text(SETUP_PY, encoding="utf-8")


def run_script(tree: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tree)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"script failed: {proc.stderr[-500:]}"
    return json.loads(proc.stdout)


def test_fixture_orphans(tmp_path: Path):
    build_tree(tmp_path)
    result = run_script(tmp_path)
    names = {o["name"] for o in result["orphan_fields"]}
    # Inner is not a settings carrier: its field is not counted at all
    assert "plain_dataclass_field" not in names
    assert result["fields_total"] == 5  # Middle 3 + Outer 2 (transitive settings)
    # live_via_module read via compose (case-insensitive env fold),
    # nested_live via backend/user.py, florence_url via setup.py;
    # the test file reading orphan_field does not rescue it
    assert names == {"orphan_field", "nested_orphan"}
    assert result["orphans"] == 2


def test_declared_at_points_at_config(tmp_path: Path):
    build_tree(tmp_path)
    result = run_script(tmp_path)
    for o in result["orphan_fields"]:
        assert o["declared_at"].startswith("backend/core/config.py:")


def test_summary_line(tmp_path: Path):
    build_tree(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "O1.7 settings-orphans: 2 of 5 settings fields" in proc.stderr


def test_missing_config_is_loud(tmp_path: Path):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    assert "not found" in proc.stderr

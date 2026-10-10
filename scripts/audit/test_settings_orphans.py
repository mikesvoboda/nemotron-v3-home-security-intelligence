#!/usr/bin/env python3
"""Tests for scripts/audit/settings_orphans.py (O1.7).

    uv run python -m pytest scripts/audit/test_settings_orphans.py -q

The fixture config pins the five decisions this census exists to get right:
  * a field on a TRANSITIVELY settings class (a nested model inherited by a
    BaseSettings child via an intermediate class) counts — a direct-base-only
    walk would miss the audit's nested fields;
  * a plain dataclass NOT in the settings chain contributes no fields;
  * reads count from compose YAML and setup.py, and a TEST file reading a
    name never rescues it (tests are not consumers);
  * a model/field VALIDATOR inside config.py rescues the fields it reads
    (self.X and the info.data.get("X") idiom) — B3.3 shipped four false
    orphans before this class existed;
  * an env spelling the field binds (validation_alias=, or a class env_prefix=
    composed as PREFIX+UPPER(NAME)) rescues it, but a Field(description=...)
    text mentioning another field name must NOT rescue anything.
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
from pydantic import Field, model_validator


class Inner:
    plain_dataclass_field: int = 0


class Middle(BaseSettings):
    live_via_module: str = "x"
    orphan_field: str = "y"
    florence_url: str = ""
    aliased_live: int = Field(default=8, validation_alias="PARALLEL")
    aliased_dead: int = Field(default=2, validation_alias="UNSET_ALIAS")
    mentions_orphan_in_text: int = Field(default=1, description="pairs with orphan_field")


class Outer(Middle):
    nested_live: str = "z"
    nested_orphan: str = "w"
    slot_count: int = 8
    context_budget: int = 1024

    @model_validator(mode="after")
    def _divide(self):
        # the real-world idiom at config.py:1185 — a dict lookup by string
        # key, which no cross-file grep and no self.X scan can see
        info_data = {}
        slots = info_data.get("slot_count") or 8
        assert self.context_budget >= slots, f"context_budget too low for {slots} slots"
        return self


class Prefixed(BaseSettings):
    model_config = {"env_prefix": "NESTED_PREFIX_"}

    prefixed_live: int = 1
    prefixed_dead: int = 2
"""

COMPOSE = """\
services:
  backend:
    environment:
      LIVE_VIA_MODULE: ${LIVE_VIA_MODULE}
      NESTED_LIVE: ${NESTED_LIVE}
      PARALLEL: ${PARALLEL}
      NESTED_PREFIX_PREFIXED_LIVE: ${NESTED_PREFIX_PREFIXED_LIVE}
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
    assert result["fields_total"] == 12  # Middle 6 + Outer 4 (transitive) + Prefixed 2
    # live_via_module read via compose (case-insensitive env fold),
    # nested_live via backend/user.py, florence_url via setup.py;
    # the test file reading orphan_field does not rescue it
    assert names == {
        "orphan_field",
        "nested_orphan",
        "aliased_dead",             # PARALLEL is in compose; UNSET_ALIAS is nowhere
        "mentions_orphan_in_text",  # a description must NOT rescue: it names orphan_field
        "prefixed_dead",            # PREFIX+UPPER(NAME) of prefixed_live IS in compose
    }
    assert result["orphans"] == 5
    # the rescue classes fired on exactly the right fields
    assert "slot_count" not in names  # rescued by info_data.get("slot_count")
    assert "context_budget" not in names  # rescued by self.context_budget
    assert "aliased_live" not in names  # rescued by compose PARALLEL (alias spelling)
    assert "prefixed_live" not in names  # rescued by compose PREFIX+UPPER(NAME)
    assert "prefixed_dead" in names
    # an f-string message that merely spells its own field is not a read of
    # anything else: if prose counted, a fixture tweak could mask orphan_field
    assert "orphan_field" in names


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
    assert "O1.7 settings-orphans: 5 of 12 settings fields" in proc.stderr


def test_missing_config_is_loud(tmp_path: Path):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    assert "not found" in proc.stderr

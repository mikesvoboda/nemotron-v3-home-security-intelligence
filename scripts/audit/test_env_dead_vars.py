#!/usr/bin/env python3
"""Tests for scripts/audit/env_dead_vars.py (O1.7).

    uv run python -m pytest scripts/audit/test_env_dead_vars.py -q

The fixture tree pins what makes a variable live here — the three readers the
package names, and nothing else:
  * a name in backend/core/config.py (settings field or os.environ lookup),
  * a name interpolated in docker-compose*.yml,
  * a name the installer (setup.py) writes or reads,
while a name that only rides a README, a .env comment, or a test file stays
dead — the O3.3 ratchet deletes exactly that class.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "audit" / "env_dead_vars.py"

ENV_EXAMPLE = """\
# a comment mentioning GHOST_IN_COMMENT
LIVE_IN_CONFIG=1
LIVE_IN_COMPOSE=2
LIVE_IN_SETUP=3
LIVE_CASED_LOWER_TWIN=4
GHOST_ONLY=5
export EXPORTED_GHOST=6
lowercase_ghost=also-ghost
"""

CONFIG_PY = "LIVE_IN_CONFIG: str = '1'\nlive_cased_lower_twin: str = '4'\n"
COMPOSE = "services:\n  x:\n    environment:\n      LIVE_IN_COMPOSE: ${LIVE_IN_COMPOSE}\n"
SETUP_PY = 'ENV = {"LIVE_IN_SETUP": True}\n'


def build_tree(root: Path) -> None:
    (root / "backend" / "core").mkdir(parents=True)
    (root / ".env.example").write_text(ENV_EXAMPLE, encoding="utf-8")
    (root / "backend" / "core" / "config.py").write_text(CONFIG_PY, encoding="utf-8")
    (root / "docker-compose.yml").write_text(COMPOSE, encoding="utf-8")
    (root / "setup.py").write_text(SETUP_PY, encoding="utf-8")
    # distractors: names only living in non-reader surfaces
    (root / "README.md").write_text("GHOST_ONLY is documented here.\n", encoding="utf-8")
    (root / "backend" / "tests").mkdir(parents=True)
    (root / "backend" / "tests" / "test_ghost.py").write_text("GHOST_ONLY = 1\n", encoding="utf-8")


def run_script(tree: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tree)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"script failed: {proc.stderr[-500:]}"
    return json.loads(proc.stdout)


def test_fixture_dead_vars(tmp_path: Path):
    build_tree(tmp_path)
    result = run_script(tmp_path)
    assert result["vars_total"] == 7
    assert result["vars_live"] == 4
    assert set(result["dead_vars"]) == {"GHOST_ONLY", "EXPORTED_GHOST", "lowercase_ghost"}
    # travels with the JSON: contract-dead != deletable (review finding —
    # the three contract readers miss live readers elsewhere in the tree)
    assert "deletable" in result["caveat"]


def test_case_fold_rescues_lower_twin(tmp_path: Path):
    """The bug the fold exists for: REDIS_SSL_ENABLED <-> redis_ssl_enabled.

    pydantic-settings binds env names case-insensitively, so an UPPER_SNAKE
    variable whose settings field is lowercase is LIVE. Without the fold this
    name lands in dead_vars — the false-DEAD direction, which would have
    O3.3's ratchet delete a working variable (measured: 41 of the first
    run's 63 'dead' names were this shape).
    """
    build_tree(tmp_path)
    result = run_script(tmp_path)
    assert "LIVE_CASED_LOWER_TWIN" not in result["dead_vars"]


def test_summary_line(tmp_path: Path):
    build_tree(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "O1.7 env-dead-vars: 3 of 7" in proc.stderr


def test_missing_env_example_is_loud(tmp_path: Path):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    assert ".env.example" in proc.stderr

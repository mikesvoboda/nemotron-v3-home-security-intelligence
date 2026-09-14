"""Tests for scripts/fast_select.py (run explicitly; outside testpaths).

Inert-additive (M1 constraint): scripts/ is outside pytest testpaths, so this
file is not collected by validate.sh until the --fast tier lands. Run it
explicitly: uv run pytest scripts/test_fast_select.py -v -p no:randomly -o addopts=""
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "fast_select.py"


@pytest.fixture()
def repo(tmp_path):
    """Tiny synthetic repo shaped like the real one."""
    run = lambda *a: subprocess.run(a, cwd=tmp_path, check=True, capture_output=True)  # noqa: E731
    run("git", "init", "-q")
    run("git", "config", "user.email", "t@t")
    run("git", "config", "user.name", "t")
    (tmp_path / "backend/api/routes").mkdir(parents=True)
    (tmp_path / "backend/services").mkdir(parents=True)
    (tmp_path / "backend/tests/unit/api/routes").mkdir(parents=True)
    (tmp_path / "backend/tests/unit/services").mkdir(parents=True)
    (tmp_path / "backend/tests/contracts").mkdir(parents=True)
    (tmp_path / "backend/api/routes/alerts.py").write_text("def list_alerts(): ...\n")
    (tmp_path / "backend/services/alert_service.py").write_text("class AlertService: ...\n")
    (tmp_path / "backend/tests/unit/api/routes/test_alerts.py").write_text(
        "def test_x():\n    from backend.api.routes.alerts import list_alerts\n"
    )
    (tmp_path / "backend/tests/unit/services/test_alert_service.py").write_text(
        "from backend.services.alert_service import AlertService\n"
    )
    (tmp_path / "backend/tests/unit/services/test_metrics.py").write_text(
        'def test_y(mocker):\n    mocker.patch("backend.api.routes.metrics.get_x")\n'
    )
    (tmp_path / "backend/tests/contracts/test_api_contracts.py").write_text("def test_c(): ...\n")
    for p in ("backend", "backend/api", "backend/api/routes", "backend/services",
              "backend/tests", "backend/tests/unit", "backend/tests/unit/api",
              "backend/tests/unit/api/routes", "backend/tests/unit/services",
              "backend/tests/contracts"):
        init = tmp_path / p / "__init__.py"
        init.touch()
    (tmp_path / "backend/api/routes/metrics.py").write_text("def get_x(): ...\n")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "base")
    return tmp_path


def select(repo, base="HEAD", *args):
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--base", base, *args],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    return r


def write_and_stage(repo, rel, text):
    (repo / rel).write_text(text)
    subprocess.run(["git", "add", "--", rel], cwd=repo, check=True)


def test_route_change_selects_lazy_import_test(repo):
    write_and_stage(repo, "backend/api/routes/alerts.py", "def list_alerts():\n    return []  # touched\n")
    r = select(repo)
    assert r.returncode == 0, r.stderr
    assert "backend/tests/unit/api/routes/test_alerts.py" in r.stdout
    # directory policy: backend/api/** pulls the contracts smoke tier
    assert "backend/tests/contracts/test_api_contracts.py" in r.stdout


def test_patch_string_reference_counts(repo):
    write_and_stage(repo, "backend/api/routes/metrics.py", "def get_x():\n    return 1  # touched\n")
    r = select(repo)
    assert "backend/tests/unit/services/test_metrics.py" in r.stdout


def test_service_change_selects_importer_only(repo):
    write_and_stage(repo, "backend/services/alert_service.py", "class AlertService:  # touched\n    pass\n")
    r = select(repo)
    assert "backend/tests/unit/services/test_alert_service.py" in r.stdout
    assert "test_alerts.py" not in r.stdout  # the route test must NOT ride along


def test_unmapped_is_loud(repo):
    write_and_stage(repo, "backend/services/orphan.py", "def f():\n    return 1\n")
    r = select(repo)
    assert "UNMAPPED: backend/services/orphan.py" in r.stdout


def test_list_out_file(repo, tmp_path):
    out = tmp_path / "sel.txt"
    write_and_stage(repo, "backend/services/alert_service.py", "class AlertService:  # x\n    pass\n")
    r = select(repo, "--list-out", str(out))
    lines = out.read_text().strip().splitlines()
    assert lines == ["backend/tests/unit/services/test_alert_service.py"]


def test_no_changes_empty_selection(repo):
    r = select(repo)
    assert r.returncode == 0
    assert "SELECTED-BACKEND-FILES: 0" in r.stdout

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
    # alerts.py imports the service: the WP2.2 transitive edge — a change to
    # alert_service.py must pull test_alerts.py through this UNTOUCHED
    # intermediate (the class the bake-off outcome arm charged both
    # selectors for; fixture-proven repro in the plan notes).
    (tmp_path / "backend/api/routes/alerts.py").write_text(
        "from backend.services.alert_service import AlertService\n\n\ndef list_alerts(): ...\n"
    )
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
    for p in (
        "backend",
        "backend/api",
        "backend/api/routes",
        "backend/services",
        "backend/tests",
        "backend/tests/unit",
        "backend/tests/unit/api",
        "backend/tests/unit/api/routes",
        "backend/tests/unit/services",
        "backend/tests/contracts",
    ):
        init = tmp_path / p / "__init__.py"
        init.touch()
    (tmp_path / "backend/api/routes/metrics.py").write_text("def get_x(): ...\n")
    # package re-export: `from backend.api.routes import get_x` executes this
    # __init__, so a metrics.py change must pull the package-importing test
    # (the bake-off's fs_miss class, case 15d7b5a2 fault arm).
    (tmp_path / "backend/api/routes/__init__.py").write_text("from .metrics import get_x\n")
    (tmp_path / "backend/tests/unit/api").mkdir(parents=True, exist_ok=True)
    (tmp_path / "backend/tests/unit/api/__init__.py").touch()
    (tmp_path / "backend/tests/unit/api/test_package_import.py").write_text(
        "from backend.api.routes import get_x\n"
    )
    run("git", "add", "-A")
    run("git", "commit", "-qm", "base")
    return tmp_path


def select(repo, base="HEAD", *args):
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--base", base, *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return r


def write_and_stage(repo, rel, text):
    (repo / rel).write_text(text)
    subprocess.run(["git", "add", "--", rel], cwd=repo, check=True)


def test_route_change_selects_lazy_import_test(repo):
    write_and_stage(
        repo, "backend/api/routes/alerts.py", "def list_alerts():\n    return []  # touched\n"
    )
    r = select(repo)
    assert r.returncode == 0, r.stderr
    assert "backend/tests/unit/api/routes/test_alerts.py" in r.stdout
    # directory policy: backend/api/** pulls the contracts smoke tier
    assert "backend/tests/contracts/test_api_contracts.py" in r.stdout


def test_patch_string_reference_counts(repo):
    write_and_stage(
        repo, "backend/api/routes/metrics.py", "def get_x():\n    return 1  # touched\n"
    )
    r = select(repo)
    assert "backend/tests/unit/services/test_metrics.py" in r.stdout


def test_service_change_selects_transitive_importer(repo):
    """WP2.2 INVERSION of test_service_change_selects_importer_only.

    The old assertion encoded the bug this WP exists to kill: a test reaching
    the changed service through an UNTOUCHED intermediate (test_alerts.py ->
    routes/alerts.py -> alert_service.py) was declared must-not-ride-along,
    when it is precisely the test the pre-push gate must run. The bake-off
    outcome arm charged both candidate selectors for exactly this class
    (case 09872e45: route change, transitive unit test, both selectors 0/1).
    Spec WP2.2 names this test by number as the inversion target.
    """
    write_and_stage(
        repo, "backend/services/alert_service.py", "class AlertService:  # touched\n    pass\n"
    )
    r = select(repo)
    assert "backend/tests/unit/services/test_alert_service.py" in r.stdout  # direct, still
    assert "backend/tests/unit/api/routes/test_alerts.py" in r.stdout  # via alerts.py, depth 1


def test_package_importer_selected_for_module_change(repo):
    """A test importing the PACKAGE rides along when a module inside changes.

    The bake-off's case-3 class: `from backend.api import get_metrics`
    executes backend/api/__init__.py, which re-exports .metrics — a change to
    metrics.py changes the package test's outcome. The shipped selector saw
    the seed (backend.api.routes.metrics) match neither the test's bare
    package reference nor its own name, and missed it (fs_miss on
    test_metrics.py, the fault arm's transitive evidence).
    """
    write_and_stage(
        repo, "backend/api/routes/metrics.py", "def get_x():  # touched\n    return 2\n"
    )
    r = select(repo)
    assert "backend/tests/unit/api/test_package_import.py" in r.stdout


def test_closure_stops_at_test_files(repo):
    """Producer graph is production-only: a test never selects another test."""
    # test_alerts.py imports routes/alerts.py; nothing production imports
    # test_alerts.py, so changing ONLY a module test_alerts uniquely depends
    # on must not leak through the test graph into other tests.
    write_and_stage(
        repo,
        "backend/api/routes/alerts.py",
        "from backend.services.alert_service import AlertService\n\n\ndef list_alerts():  # touched\n    return [1]\n",
    )
    r = select(repo)
    out = r.stdout
    # test_alerts selected (direct); test_alert_service selected (closure
    # reaches the package via referrers? no — alert_service UNCHANGED here);
    # nothing from backend/tests/unit/services may appear via a test-to-test
    # edge: test_alert_service references alert_service only.
    assert "backend/tests/unit/api/routes/test_alerts.py" in out
    assert "backend/tests/unit/services/test_alert_service.py" not in out


def test_unmapped_is_loud(repo):
    write_and_stage(repo, "backend/services/orphan.py", "def f():\n    return 1\n")
    r = select(repo)
    assert "UNMAPPED: backend/services/orphan.py" in r.stdout


def test_list_out_file(repo, tmp_path):
    out = tmp_path / "sel.txt"
    write_and_stage(
        repo, "backend/services/alert_service.py", "class AlertService:  # x\n    pass\n"
    )
    r = select(repo, "HEAD", "--list-out", str(out))
    lines = out.read_text().strip().splitlines()
    # WP2.2: the transitive route test joins the direct one (sorted order)
    assert lines == [
        "backend/tests/unit/api/routes/test_alerts.py",
        "backend/tests/unit/services/test_alert_service.py",
    ]


def test_no_changes_empty_selection(repo):
    r = select(repo)
    assert r.returncode == 0
    assert "SELECTED-BACKEND-FILES: 0" in r.stdout

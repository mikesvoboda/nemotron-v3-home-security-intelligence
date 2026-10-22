#!/usr/bin/env python3
"""Tests for scripts/audit/dead_symbols.py (B3.3 box 3).

Run explicitly (scripts/ is outside pytest testpaths):

    uv run python -m pytest scripts/audit/test_dead_symbols.py -q

The fixture tree pins the decisions this census exists to get right -- each one was
a WRONG first implementation found by running the real repo, not a hypothetical:

  * a pytest test class named ``TestFooError`` is NOT an exception declaration. The
    first run reported 71 "unused" exception classes; 48 were collected test bodies
    (``class TestRateLimitError:`` with no bases) that the ``Error`` suffix rule
    swallowed. The suffix rule now yields to the ``Test`` prefix;
  * ``Summary`` is both a prometheus_client metric type AND this repo's own model
    class, so a metric factory is recognised by its IMPORT ORIGIN per file, not by
    name. Name-matching gave ``latest_hourly = Summary(...)`` -- an app model -- a
    metric row;
  * a dashboard/alert-rule name reference makes a caller-less metric ``queried``,
    not dead -- the falsified ``backend/AGENTS.md:248`` "the dashboards query them"
    claim survived exactly because nobody matched the metric name against the corpus;
  * a reference from a test is ``prod_dead``, not ``unused`` -- the deletion work
    includes editing that test, so the tier keeps it visible;
  * a string-keyed reference (``globals()["X"]``, a dict key) is treated as live:
    the census may over-count live (safe) but must never call a live thing dead
    (scripts/audit/AGENTS.md), because a later package deletes against this list.

The repo-wide test is the ratchet: with the scan view above, no exception declared
OUTSIDE backend/tests/ is unused. That is the Done-when for the box-3 exception
deletions, and it is the "re-measure at gate time" doctrine rather than a committed
count -- re-adding such a class fails naming it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "audit" / "dead_symbols.py"


def scan(tree: Path) -> dict:
    """Run the script as its CLI runs it: JSON on stdout is the result."""
    proc = subprocess.run(  # intentional - runs our own committed script, fixed argv list
        [sys.executable, str(SCRIPT), "--root", str(tree)],
        capture_output=True,
        text=True,
        check=False,
        timeout=240,
    )
    assert proc.returncode == 0, f"script failed: {proc.stderr[-500:]}"
    return json.loads(proc.stdout)


def by_name(result: dict, name: str) -> dict:
    rows = [r for r in result["symbols"] if r["name"] == name]
    assert rows, f"{name} not in census output"
    return rows[0]


def build_tree(root: Path) -> None:
    """A 6-file repo exercising every verdict tier."""
    pkg = root / "backend"
    (pkg / "core").mkdir(parents=True)
    (pkg / "core" / "exc.py").write_text(
        '"""exceptions module."""\n\n\n'
        "class TrulyDeadError(Exception):\n"
        '    """No one anywhere."""\n\n\n'
        "class HandledError(Exception):\n"
        '    """Caught in prod."""\n\n\n'
        "class OnlyTestedError(Exception):\n"
        '    """Named only by a test."""\n\n\n'
        "class BarreledError(Exception):\n"
        '    """Re-exported by the barrel."""\n\n\n'
        "class ReachedDynamicallyError(Exception):\n"
        '    """Reached through a string."""\n\n\n'
        "MAP = {'ReachedDynamicallyError': 1}\n",
        encoding="utf-8",
    )
    (pkg / "core" / "services.py").write_text(
        '"""prod code that catches one and reaches one by string."""\n\n'
        "from backend.core.exc import HandledError, ReachedDynamicallyError\n\n\n"
        "def go(flag):\n"
        "    try:\n"
        "        pass\n"
        "    except HandledError:\n"
        "        return None\n"
        "    return globals()[flag]\n",
        encoding="utf-8",
    )
    (pkg / "__init__.py").write_text(
        '"""the barrel §4.1 blames for hiding dead modules."""\n'
        "from backend.core.exc import BarreledError\n\n__all__ = ['BarreledError']\n",
        encoding="utf-8",
    )
    # prometheus metric: imported from prometheus_client, so the assignment counts;
    # the same-named app model below must NOT count as a metric.
    (pkg / "core" / "metrics_mod.py").write_text(
        '"""metrics."""\n'
        "from prometheus_client import Counter, Summary\n\n"
        "hsi_dead_metric = Counter('hsi_dead_metric', 'no caller, no dashboard')\n"
        "hsi_dashboard_metric = Counter('hsi_dashboard_metric', 'no caller, a dashboard')\n"
        "hsi_live_metric = Counter('hsi_live_metric', 'observed in prod')\n\n"
        "def observe():\n"
        "    hsi_live_metric.inc()\n",
        encoding="utf-8",
    )
    (pkg / "models.py").write_text(
        '"""the app model whose name collides with prometheus_client.Summary."""\n\n\n'
        "class Summary:\n"
        '    """app model, not a metric"""\n\n\n'
        "latest_hourly = Summary()\n",
        encoding="utf-8",
    )
    tests = root / "backend" / "tests" / "unit"
    tests.mkdir(parents=True)
    (tests / "test_only.py").write_text(
        '"""tests."""\n'
        "from backend.core.exc import OnlyTestedError\n\n\n"
        "def test_only():\n"
        "    assert OnlyTestedError\n\n\n"
        "class TestRateLimitError:\n"
        '    """A collected test class, NOT an exception declaration."""\n\n'
        "    def test_it(self):\n"
        "        assert True\n",
        encoding="utf-8",
    )
    mon = root / "monitoring" / "grafana" / "dashboards"
    mon.mkdir(parents=True)
    (mon / "dash.json").write_text(
        '{"targets": [{"expr": "rate(hsi_dashboard_metric_total[5m])"}]}\n',
        encoding="utf-8",
    )


@pytest.fixture(scope="module")
def tree(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("dead_symbols")
    build_tree(root)
    return root


@pytest.fixture(scope="module")
def result(tree: Path) -> dict:
    return scan(tree)


def test_dead_exception_is_reported_unused(result):
    assert by_name(result, "TrulyDeadError")["verdict"] == "unused"


def test_caught_exception_is_live(result):
    assert by_name(result, "HandledError")["verdict"] == "live"


def test_string_reached_exception_is_live(result):
    # the dict key 'ReachedDynamicallyError' is reach without a Name node
    row = by_name(result, "ReachedDynamicallyError")
    assert row["verdict"] == "live"
    assert row["dynamic_refs"]


def test_barrel_reexport_is_not_a_use(result):
    assert by_name(result, "BarreledError")["verdict"] == "reexported"


def test_test_only_exception_is_prod_dead(result):
    assert by_name(result, "OnlyTestedError")["verdict"] == "prod_dead"


def test_pytest_test_class_is_not_an_exception_declaration(result):
    # the fix for the 71 -> 23 inflation: a collected Test*Error body is absent
    assert [r for r in result["symbols"] if r["name"] == "TestRateLimitError"] == []


def test_metric_with_no_reference_is_unused(result):
    assert by_name(result, "hsi_dead_metric")["verdict"] == "unused"


def test_metric_queried_by_dashboard_is_live_not_dead(result):
    # queried by its _total suffix, the way Grafana actually spells it
    row = by_name(result, "hsi_dashboard_metric")
    assert row["verdict"] == "queried"
    assert row["query_files"]


def test_metric_observed_in_prod_is_live(result):
    assert by_name(result, "hsi_live_metric")["verdict"] == "live"


def test_app_model_named_summary_is_not_a_metric(result):
    # `latest_hourly = Summary()` -- the app model, not prometheus_client.Summary
    assert [r for r in result["symbols"] if r["name"] == "latest_hourly"] == []


@pytest.mark.timeout(300)  # the whole repo is re-scanned here (~60s measured)
def test_no_production_exception_is_unused():
    """The box-3 ratchet: no exception declared outside backend/tests/ is unused.

    A re-added dead class fails naming it, which is the point -- the tier is
    re-measured at gate time rather than compared to a committed count.
    """
    result = scan(REPO_ROOT)
    dead = [
        r["declared_at"]
        for r in result["symbols"]
        if r["kind"] == "exception" and r["verdict"] == "unused" and not r["declared_in_tests"]
    ]
    assert not dead, (
        f"exception classes declared in production, referenced nowhere: {dead}. B3.3 "
        "box 3 deleted these; if one is back on purpose it needs a raiser or handler "
        "somewhere outside its own definition -- otherwise delete it with its stale "
        "Raises: line (both classes removed here documented raises they never made)."
    )

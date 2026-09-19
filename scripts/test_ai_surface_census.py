#!/usr/bin/env python3
"""Tests for scripts/ai-surface-census.py (plan P WP5.5).

The census classifies every backend/services module into exactly one swap
bucket (HTTP-AI | INPROC-AI | DOMAIN | DEAD) BEFORE any deletion, so the
general reachability rule governs the known-bad records rather than being
retrofitted to them. Run explicitly (outside testpaths):

    uv run python -m pytest scripts/test_ai_surface_census.py -q

Fixture trees pin the two traps this census exists to get right:
  * a re-export in the package __init__ is NOT a consumer — scene_change_service
    (the WP5.6 deletion candidate) has exactly one importer, __init__.py's
    re-export, and must classify DEAD;
  * client-bypass call sites (raw httpx to an AI endpoint; reaching into a
    client's private url attribute) ARE HTTP-AI even though the module never
    imports the client — they are what an extraction most easily misses.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CENSUS = REPO_ROOT / "scripts" / "ai-surface-census.py"


def run_census(tree: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(CENSUS), "--root", str(tree), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"census failed: {proc.stderr[-800:]}"
    return json.loads(proc.stdout)


@pytest.fixture
def fixture_tree(tmp_path: Path) -> Path:
    """A miniature backend/services tree exercising every bucket + both traps."""
    root = tmp_path / "proj"
    svc = root / "backend" / "services"
    svc.mkdir(parents=True)
    (root / "backend" / "__init__.py").write_text("")

    # known-dead: imported ONLY by the package __init__ re-export and a test
    (svc / "dead_service.py").write_text("VALUE = 1\n")
    # known-live domain module: imported by a real non-test consumer
    (svc / "domain_service.py").write_text("def f():\n    return 1\n")
    (root / "backend" / "consumer.py").write_text("from backend.services.domain_service import f\n")
    # re-export-only importer (the scene_change_service trap)
    (svc / "__init__.py").write_text(
        "from backend.services.dead_service import VALUE  # re-export\n"
    )
    # a test importing dead_service must NOT rescue it
    tests = root / "backend" / "tests"
    tests.mkdir()
    (tests / "test_dead_service.py").write_text("from backend.services.dead_service import VALUE\n")

    # HTTP-AI via client import (stem is a gateway client itself, too)
    (svc / "detector_client.py").write_text(
        "import httpx\n\n\nclass DetectorClient:\n"
        "    async def get_detection(self, c):\n"
        "        async with httpx.AsyncClient() as x:\n"
        "            return await x.post('/detect', json={})\n"
    )
    (svc / "uses_client.py").write_text(
        "from backend.services.detector_client import DetectorClient\n\n"
        "async def call(c):\n    return await c.get_detection()\n"
    )
    # HTTP-AI via client-bypass: raw httpx POST to an AI route
    (svc / "bypass_service.py").write_text(
        "import httpx\n\n\nasync def ocr(url, payload):\n"
        "    async with httpx.AsyncClient() as c:\n"
        "        return await c.post(url + '/ocr-with-regions', json=payload)\n"
    )
    # HTTP-AI via private-attribute reach (nemotron_streaming.py:99 class)
    (svc / "private_reach.py").write_text("def stream(analyzer):\n    return analyzer._llm_url\n")
    # INPROC-AI: heavy lib imported into the backend process
    (svc / "heavy_loader.py").write_text("import torch\n\n\nclass Loader:\n    pass\n")
    # DOMAIN: imported, no AI evidence
    # live consumers for the AI-surface modules (DEAD > HTTP-AI precedence:
    # without a consumer these would all classify DEAD, testing the wrong
    # edge of the rule)
    (root / "backend" / "consumers.py").write_text(
        "from backend.services.bypass_service import ocr\n"
        "from backend.services.private_reach import stream\n"
        "from backend.services.heavy_loader import Loader\n"
        "from backend.services.detector_client import DetectorClient\n"
        "from backend.services.uses_client import call\n"
    )
    assert (svc / "domain_service.py").exists()
    return root


class TestFixtureTree:
    def test_every_module_gets_exactly_one_bucket(self, fixture_tree: Path) -> None:
        data = run_census(fixture_tree)
        mods = data["modules"]
        for name in (
            "dead_service",
            "domain_service",
            "uses_client",
            "bypass_service",
            "private_reach",
            "heavy_loader",
            "detector_client",
        ):
            assert name in mods, f"{name} missing from census output"
            assert mods[name]["bucket"] in {"HTTP-AI", "INPROC-AI", "DOMAIN", "DEAD"}

    def test_reexport_only_importer_still_dead(self, fixture_tree: Path) -> None:
        """THE trap: __init__.py re-exports are not consumers (WP5.6 anchors)."""
        mods = run_census(fixture_tree)["modules"]
        assert mods["dead_service"]["bucket"] == "DEAD"
        assert mods["dead_service"]["non_test_importers"] == 0

    def test_test_importers_do_not_rescue(self, fixture_tree: Path) -> None:
        mods = run_census(fixture_tree)["modules"]
        assert mods["dead_service"]["non_test_importers"] == 0

    def test_client_user_is_http_ai(self, fixture_tree: Path) -> None:
        mods = run_census(fixture_tree)["modules"]
        assert mods["uses_client"]["bucket"] == "HTTP-AI"

    def test_client_bypasses_are_http_ai(self, fixture_tree: Path) -> None:
        mods = run_census(fixture_tree)["modules"]
        assert mods["bypass_service"]["bucket"] == "HTTP-AI"
        assert mods["private_reach"]["bucket"] == "HTTP-AI"

    def test_heavy_import_is_inproc_ai(self, fixture_tree: Path) -> None:
        mods = run_census(fixture_tree)["modules"]
        assert mods["heavy_loader"]["bucket"] == "INPROC-AI"

    def test_plain_module_is_domain(self, fixture_tree: Path) -> None:
        mods = run_census(fixture_tree)["modules"]
        assert mods["domain_service"]["bucket"] == "DOMAIN"

    def test_dead_beats_ai_evidence(self, fixture_tree: Path) -> None:
        """A module with AI evidence but zero consumers is DEAD — deletion
        governs; the contract never grows for unreachable code."""
        svc = fixture_tree / "backend" / "services"
        (svc / "dead_heavy.py").write_text("import torch\n")
        mods = run_census(fixture_tree)["modules"]
        assert mods["dead_heavy"]["bucket"] == "DEAD"

    def test_bypass_sites_are_counted(self, fixture_tree: Path) -> None:
        data = run_census(fixture_tree)
        assert data["totals"]["client_bypass_sites"] >= 2


@pytest.mark.timeout(60)  # census is ~8s on the real tree; repo addopts default is 5s
class TestRealTree:
    """Anchors against the plan's MEASURE numbers (P WP5.5 reference anchors:
    22 *_loader.py modules, 21 importing heavy AI libs; the two WP5.6-known
    dead modules)."""

    @pytest.fixture(scope="class")
    def real(self) -> dict:
        return run_census(REPO_ROOT)

    def test_all_services_modules_classified(self, real: dict) -> None:
        mods = real["modules"]
        assert len(mods) >= 200, f"only {len(mods)} modules — census scope too narrow"
        for name, m in mods.items():
            assert m["bucket"] in {"HTTP-AI", "INPROC-AI", "DOMAIN", "DEAD"}, name

    @pytest.mark.timeout(30)
    def test_census_runs_in_seconds_on_real_tree(self) -> None:
        # the first draft's per-module scan took >120s; the prefix-walk must
        # keep the whole census a sub-10s tool
        import subprocess as sp
        import time as t

        t0 = t.monotonic()
        sp.run(
            [sys.executable, str(CENSUS), "--root", str(REPO_ROOT), "--json"],
            capture_output=True,
            check=True,
        )
        assert t.monotonic() - t0 < 10

    def test_loaders_are_inproc(self, real: dict) -> None:
        mods = real["modules"]
        loaders = {n: m for n, m in mods.items() if n.endswith("_loader")}
        assert len(loaders) == 22, f"anchor says 22 loaders, census sees {len(loaders)}"
        inproc = sum(1 for m in loaders.values() if m["bucket"] == "INPROC-AI")
        assert inproc >= 20, f"anchor says 21 loaders import heavy libs, got {inproc}"

    def test_known_dead_land_dead(self, real: dict) -> None:
        mods = real["modules"]
        # WP5.6 anchors: 0/385 and 1/192 (the 1 being the __init__ re-export)
        assert mods["job_state_service"]["bucket"] == "DEAD"
        assert mods["scene_change_service"]["bucket"] == "DEAD"

    def test_known_http_surface(self, real: dict) -> None:
        mods = real["modules"]
        # the five gateway-facing clients + the documented bypass sites
        for name in ("detector_client", "florence_client", "clip_client"):
            assert mods[name]["bucket"] == "HTTP-AI", name
        assert mods["scene_ocr_service"]["bucket"] == "HTTP-AI"
        assert mods["nemotron_streaming"]["bucket"] == "HTTP-AI"

    def test_json_totals_shape(self, real: dict) -> None:
        t = real["totals"]
        for key in ("HTTP-AI", "INPROC-AI", "DOMAIN", "DEAD"):
            assert isinstance(t[key], int)
        assert isinstance(t["dead_lines"], int)
        assert isinstance(t["client_bypass_sites"], int)
        assert sum(t[k] for k in ("HTTP-AI", "INPROC-AI", "DOMAIN", "DEAD")) == len(real["modules"])


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

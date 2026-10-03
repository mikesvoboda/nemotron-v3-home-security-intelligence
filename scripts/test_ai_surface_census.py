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


@pytest.mark.timeout(60)  # census is sub-second on the real tree; repo addopts default is 5s
class TestRealTree:
    """Anchors against the plan's MEASURE numbers (P WP5.5 reference anchors:
    22 *_loader.py modules, 21 importing heavy AI libs; the two WP5.6-known
    dead modules)."""

    @pytest.fixture(scope="class")
    def real(self) -> dict:
        return run_census(REPO_ROOT)

    def test_all_services_modules_classified(self, real: dict) -> None:
        mods = real["modules"]
        # 212 at the WP5.5 measurement; R8 S2 (2026-09-29) deleted the nemotron
        # analyzer, the enrichment tier and 19 loaders, taking it to 182; R8 S3
        # swept the Florence/CLIP/enrichment surface and scene_ocr_service on
        # top of that, taking it to 177. The floor is a scope canary, not a
        # count to defend - it moves WITH an authorized retirement, never under
        # an unexplained one.
        assert len(mods) >= 170, f"only {len(mods)} modules — census scope too narrow"
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
        # 22 at the WP5.5 measurement. R8 S2 retired 19 of them (spec §2: the
        # attribute zoo re-perceives what the VLM already sees); the survivors
        # are exactly the three lookup specialists whose data lives in a DB the
        # pixels cannot reach (`model_loader_base` stays too - it is their
        # shared base class, it just does not end in `_loader` so the census
        # name-filter does not see it).
        assert len(loaders) == 3, f"R8 S2 leaves 3 *_loader modules, census sees {len(loaders)}"
        assert set(loaders) == {
            "face_recognizer_loader",
            "osnet_loader",
            "fast_alpr_loader",
        }, sorted(loaders)
        inproc = sum(1 for m in loaders.values() if m["bucket"] == "INPROC-AI")
        assert inproc >= 2, f"surviving loaders still import heavy libs in-proc, got {inproc}"

    def test_known_dead_land_dead(self, real: dict) -> None:
        mods = real["modules"]
        # WP5.6 anchors, POST-DELETION (ADDENDUM 2 A6): job_state_service
        # (0 importers / 385 lines) and scene_change_service (1 importer —
        # the __init__ re-export / 192 lines) were the census's two known-
        # DEAD modules; they are DELETED, so the honest anchor is absence.
        # The re-export-is-not-a-consumer trap this census exists to get
        # right stays pinned by the fixture trees above (dead_service),
        # which the deletion cannot rot — it is synthetic, not real-tree.
        assert "job_state_service" not in mods, "WP5.6 deleted it; reappeared?"
        assert "scene_change_service" not in mods, "WP5.6 deleted it; reappeared?"

    def test_known_http_surface(self, real: dict) -> None:
        mods = real["modules"]
        # R8 S2 left three gateway-facing HTTP clients; R8 S3 (owner rulings 1
        # and 5) deleted two of them with their providers — florence_client
        # with the Florence surface, clip_client with CLIP's, which retired as
        # a prune consequence of narrowing GATEWAY_MODEL_SET to 3. detector_client
        # is the survivor: yolo26 is kept, so its client is live HTTP-AI.
        assert mods["detector_client"]["bucket"] == "HTTP-AI"
        # Absence, not a bucket: a deleted module is not in the census at all,
        # so the old `mods[name]["bucket"] == "HTTP-AI"` / `== "DEAD"` pins on
        # these names would KeyError. Stating the absence is the honest form
        # (V3 tombstone doctrine) — and it is the stronger claim: a resurrected
        # module fails here even if it comes back in the "right" bucket.
        for name in (
            "florence_client",
            "clip_client",
            "enrichment_client",
            "nemotron_streaming",
            "scene_ocr_service",
        ):
            assert name not in mods, f"{name} was deleted; reappeared?"
        # scene_ocr_service's last consumer went with the enrichment tier in S2
        # (bucket DEAD) and the module itself went in S3 with the OCR leg, so
        # the "absent from the census, present in the tree" split no longer
        # exists for it. Assert the file is really gone, else the absence above
        # would only be proving the census lost scope:
        assert not (REPO_ROOT / "backend" / "services" / "scene_ocr_service.py").exists(), (
            "module is on disk but absent from the census — that is a census "
            "scope bug, not a retirement"
        )
        # Non-vacuity: the HTTP-AI bucket the surviving pin reads is not empty,
        # and the gateway-facing VLM client is in it.
        http = {n for n, m in mods.items() if m["bucket"] == "HTTP-AI"}
        assert len(http) >= 4, f"HTTP-AI bucket collapsed to {sorted(http)}"
        assert "vlm_client" in http, sorted(http)

    def test_json_totals_shape(self, real: dict) -> None:
        t = real["totals"]
        for key in ("HTTP-AI", "INPROC-AI", "DOMAIN", "DEAD"):
            assert isinstance(t[key], int)
        assert isinstance(t["dead_lines"], int)
        assert isinstance(t["client_bypass_sites"], int)
        assert sum(t[k] for k in ("HTTP-AI", "INPROC-AI", "DOMAIN", "DEAD")) == len(real["modules"])


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

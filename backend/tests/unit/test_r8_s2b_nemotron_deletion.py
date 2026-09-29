"""R8 slice S2b: the nemotron analyzer + enrichment tier are GONE, and the VLM path still imports.

The goal prompt's S2 order is EXTRACT-THEN-DELETE, and S2a (commit `9c28b580`) did the
extract: the constrained-decoding vocabulary now lives in
`backend/services/constrained_decoding.py` and its four shipped importers were repointed
first. This file is the red-first pin of the DELETE half, written before any `rm`:

* every module on the spec §1 What-goes list is unimportable (`ModuleNotFoundError`,
  not a stub, not a shim - the owner ruling is verbatim "we do not have to support
  backwards compatability"),
* no SURVIVING shipped module imports a dying one (an import-statement scan - the same
  shape as `test_no_legacy_pipeline_branches.py`'s AST guard, not a substring grep:
  docstrings are ALLOWED to name the dead, prose about a retirement has to be able to
  say what retired),
* `backend.services` re-exports none of the dead names (the goal prompt's trap:
  `services/__init__.py` eagerly imports the analyzer at :245 and the enrichment tier
  at :95 - it must be edited BEFORE the rm or every `from backend.services import ...`
  in the app dies at the package boundary),
* the VLM path still imports the hoisted symbols from their ONE home, and
* the DI name `"nemotron_analyzer"` SURVIVES as a string: `pipeline_factory` is the
  only class-choice seam, two shipped call sites resolve the singleton by that name,
  and `test_p03_constrained_verdict.py` pins `container.lookups == ["nemotron_analyzer"]`
  - deleting the module must not silently rename the wiring (S2 retires the class, the
  name is load-bearing until a slice that says otherwise owns it).
"""

from __future__ import annotations

import ast
import importlib
import inspect
import re
from pathlib import Path
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock

import pytest

BACKEND = Path(__file__).resolve().parents[2]

# spec §1 "What goes", verbatim list (minus the hoist, which S2a moved).
DEAD_MODULES = [
    "backend.services.nemotron_analyzer",
    "backend.services.nemotron_streaming",
    "backend.services.analyzer_facade",
    "backend.services.prompt_auto_tuner",
    "backend.services.nemotron_latency_optimizer",
    "backend.services.skeleton_action_service",
    "backend.services.pose_analysis_service",
    "backend.services.enrichment_pipeline",
    "backend.services.enrichment_client",
]

# The legacy periphery that died WITH the tier: 19 of the 22 model loaders
# (spec §2 - reachable only through `enrichment_pipeline`, `model_zoo._LOADER_MAP`
# or a `TYPE_CHECKING` import in `prompts.py`, all of which are gone), plus the
# Florence extraction service and the package-tracking service whose only
# consumer was the enrichment tier. Pinned in the same list because the guard
# below treats them identically: unimportable, unre-imported, un-annotated.
DEAD_LOADERS = [
    "backend.services.age_classifier_loader",
    "backend.services.clip_loader",
    "backend.services.depth_anything_loader",
    "backend.services.fashion_clip_loader",
    "backend.services.florence_loader",
    "backend.services.gender_classifier_loader",
    "backend.services.image_quality_loader",
    "backend.services.pet_classifier_loader",
    "backend.services.segformer_loader",
    "backend.services.smoke_fire_loader",
    "backend.services.stgcn_loader",
    "backend.services.threat_detection_loader",
    "backend.services.vehicle_classifier_loader",
    "backend.services.vehicle_damage_loader",
    "backend.services.violence_loader",
    "backend.services.vitpose_loader",
    "backend.services.weather_loader",
    "backend.services.yolo_world_loader",
    "backend.services.zero_dce_loader",
]

DEAD_SUPPORT = [
    "backend.services.vision_extractor",
    "backend.services.package_tracking_service",
    # The Florence-2 attribute extractor: its loader row died with the tier and
    # its only remaining consumer was enrichment_pipeline. The ai/gateway
    # florence2 Triton model and florence_client (HTTP) are a separate matter -
    # the gateway provider retirement is S3's, one provider per slice.
    "backend.services.florence_extractor",
]

# The three loaders spec §2 names as survivors, and the base class they share.
ALIVE_LOADERS = [
    "backend.services.face_recognizer_loader",
    "backend.services.osnet_loader",
    "backend.services.fast_alpr_loader",
    "backend.services.model_loader_base",
]

DEAD_MODULES = DEAD_MODULES + DEAD_LOADERS + DEAD_SUPPORT

DEAD_TOP_NAMES = [
    "NemotronAnalyzer",
    "AnalyzerServiceFacade",
    "get_analyzer_facade",
    "reset_analyzer_facade",
    "PromptAutoTuner",
    "NemotronLatencyOptimizer",
    "LatencyOptimizerConfig",
    "LatencyStats",
    "SemaphoreAcquireTimeout",
    "get_nemotron_optimizer",
    "reset_nemotron_optimizer",
    "EnrichmentPipeline",
    "get_enrichment_pipeline",
    "reset_enrichment_pipeline",
    "EnrichmentResult",
    "DetectionInput",
    "BoundingBox",
    "FaceResult",
    "LicensePlateResult",
    # S2b's second wave: the service wrapper whose only loader died, and the
    # enrichment-prompt formatters whose whole caller tier was deleted.
    "YOLOWorldService",
    "format_weather_context",
    "format_detections_with_all_enrichment",
    "format_threat_detection_context",
    "build_enrichment_sections",
]

# module -> the importers S2a repointed; if any of these CANNOT import, the delete
# broke the shipped VLM path and the whole slice is void.
VLM_PATH_MODULES = [
    "backend.services.vlm_client",
    "backend.services.vlm_analyzer",
    "backend.evaluation.vlm_replay",
    "backend.services.constrained_decoding",
]

_DIED = "|".join(re.escape(m.rsplit(".", 1)[1]) for m in DEAD_MODULES)
_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+backend\.services\.(?:" + _DIED + r")\s+import"
    r"|from\s+backend\.services\s+import\s+(?:" + _DIED + r")\b"
    r"|import\s+backend\.services\.(?:" + _DIED + r"))\b",
    re.MULTILINE,
)


def _shipped_modules() -> list[Path]:
    files = [
        p for p in BACKEND.rglob("*.py") if "tests" not in p.parts and "__pycache__" not in p.parts
    ]
    # The floor is a live scan assertion, not a coverage claim: if the walk
    # finds almost nothing the path moved and every pin below is vacuous.
    # 551 shipped files today; S2b deletes ~30 modules + the legacy loaders.
    assert len(files) > 480, f"scanner found only {len(files)} files under {BACKEND}"
    return files


class TestDeadModulesAreGone:
    @pytest.mark.parametrize("module", DEAD_MODULES)
    def test_unimportable(self, module: str) -> None:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(module)

    def test_package_exports_no_dead_names(self) -> None:
        from backend import services

        leaked = [n for n in DEAD_TOP_NAMES if hasattr(services, n)]
        assert not leaked, f"backend.services still re-exports retired names: {leaked}"

    def test_no_survivor_imports_the_dead(self) -> None:
        dead_files = {m.rsplit(".", 1)[1] + ".py" for m in DEAD_MODULES}
        hits: list[str] = []
        for path in _shipped_modules():
            if path.name in dead_files:
                continue  # a dying module importing its dying neighbours is not a leak
            for match in _IMPORT_RE.finditer(path.read_text(encoding="utf-8")):
                hits.append(f"{path.relative_to(BACKEND)}: {match.group(0).strip()}")
        assert not hits, "surviving shipped modules still import retired code:\n" + "\n".join(hits)

    def test_no_analyzer_type_remains_anywhere_in_shipped_code(self) -> None:
        # The annotations are runtime-invisible (`from __future__ import annotations`)
        # but mypy resolves them, and a reader must not meet a class that no longer
        # exists in a live worker's signature. AST scan: Name/Attribute mentions.
        offenders: list[str] = []
        for path in _shipped_modules():
            if path.name in {m.rsplit(".", 1)[1] + ".py" for m in DEAD_MODULES}:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id in {
                    "NemotronAnalyzer",
                    "EnrichmentPipeline",
                    "EnrichmentResult",
                    "NemotronLatencyOptimizer",
                    "AnalyzerServiceFacade",
                }:
                    offenders.append(f"{path.relative_to(BACKEND)}:{node.lineno} {node.id}")
        assert not offenders, "live annotations name retired classes:\n" + "\n".join(offenders)


class TestVlmPathSurvives:
    @pytest.mark.parametrize("module", VLM_PATH_MODULES)
    def test_imports(self, module: str) -> None:
        importlib.import_module(module)

    @pytest.mark.parametrize("module", ALIVE_LOADERS)
    def test_spec2_loaders_stay(self, module: str) -> None:
        # spec §2: face/plate lookups are DB lookups the VLM cannot do from
        # pixels - they survive the loader purge by ruling, not by accident.
        importlib.import_module(module)

    def test_model_zoo_maps_exactly_the_survivors(self) -> None:
        from backend.services.model_zoo import _LOADER_MAP

        dead = {m.rsplit(".", 1)[1] for m in DEAD_MODULES}
        # keys are model ids, values the loader module names
        leaked = {
            k: v for k, v in _LOADER_MAP.items() if str(v) in dead or any(d in str(v) for d in dead)
        }
        assert not leaked, f"_LOADER_MAP still points at retired loaders: {leaked}"

    def test_one_home_for_the_vocabulary(self) -> None:
        from backend.services import constrained_decoding as cd

        assert cd.ConstrainedDecodingNotEnforced.__module__ == (
            "backend.services.constrained_decoding"
        )


class TestDiNameIsDeliberate:
    def test_container_still_wires_the_name(self) -> None:
        # pipeline_factory is the only class-choice seam; the registry NAME is
        # the load-bearing string (main.py's startup gate + core/dependencies
        # resolve by it, and test_p03 pins container.lookups). This asserts it
        # survived the class deletion ON PURPOSE, so a future rename is a
        # decision someone has to take, not drift.
        src = (BACKEND / "core" / "container.py").read_text(encoding="utf-8")
        assert 'register_async_singleton("nemotron_analyzer"' in src
        # ...and the enrichment registration is GONE: container.py:508's legacy
        # gate is what made the tier unreachable, S2 deletes what it fed.
        assert 'register_async_singleton("enrichment_pipeline"' not in src

    def test_startup_gate_has_no_legacy_analyzer_arm(self) -> None:
        # S2a left main.py's hasattr("_constrained_enabled") arm - dead code the
        # moment the class dies. It must die WITH the class, or the gate keeps
        # a branch whose true side no one can execute.
        src = (BACKEND / "main.py").read_text(encoding="utf-8")
        assert "_constrained_enabled" not in src


class TestStartupGateSurvives:
    """P0.3's startup gate must still WORK after S2b - and it lost its only
    behavioral pin when test_p03_constrained_verdict.py died with the analyzer
    it was built on. The source-text pins above prove the legacy arm is gone;
    these prove the client-shaped gate that replaced it is live and honest, so
    the retirement did not quietly un-pin the verdict vocabulary."""

    @staticmethod
    def _fake_container(analyzer: object) -> object:
        class C:
            # ClassVar on purpose: every lookup lands on the CLASS attribute
            # so the test can assert the gate crossed the registry by name.
            lookups: ClassVar[list[str]] = []

            async def get_async(self, name: str) -> object:
                C.lookups.append(name)
                return analyzer

        return C()

    @pytest.mark.asyncio
    async def test_probe_pass_reports_enforced_via_registry_name(self) -> None:
        from backend.main import run_constrained_startup_check

        client = MagicMock()
        client._settings.vlm_enforcement_probe_enabled = True
        client._probe_enforcement = AsyncMock()
        analyzer = MagicMock()
        analyzer._get_client.return_value = client
        container = self._fake_container(analyzer)

        assert await run_constrained_startup_check(container) == "enforced"
        # the gate crosses the RETIRED SPELLING as a string, on purpose
        assert type(container).lookups == ["nemotron_analyzer"]
        client._probe_enforcement.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ignored_verdict_is_not_enforced_not_crash(self) -> None:
        from backend.main import run_constrained_startup_check
        from backend.services.constrained_decoding import ConstrainedDecodingNotEnforced

        client = MagicMock()
        client._settings.vlm_enforcement_probe_enabled = True
        client._probe_enforcement = AsyncMock(
            side_effect=ConstrainedDecodingNotEnforced("verdict=IGNORED")
        )
        analyzer = MagicMock()
        analyzer._get_client.return_value = client

        assert await run_constrained_startup_check(self._fake_container(analyzer)) == (
            "not_enforced"
        )

    @pytest.mark.asyncio
    async def test_probe_disabled_reports_disabled_without_network(self) -> None:
        from backend.main import run_constrained_startup_check

        client = MagicMock()
        client._settings.vlm_enforcement_probe_enabled = False
        client._probe_enforcement = AsyncMock(
            side_effect=AssertionError("no probe expected when disabled")
        )
        analyzer = MagicMock()
        analyzer._get_client.return_value = client

        assert await run_constrained_startup_check(self._fake_container(analyzer)) == ("disabled")

    @pytest.mark.asyncio
    async def test_unreachable_endpoint_is_inconclusive_never_crashes(self) -> None:
        from backend.main import run_constrained_startup_check

        client = MagicMock()
        client._settings.vlm_enforcement_probe_enabled = True
        client._probe_enforcement = AsyncMock(side_effect=OSError("endpoint down"))
        analyzer = MagicMock()
        analyzer._get_client.return_value = client

        assert await run_constrained_startup_check(self._fake_container(analyzer)) == (
            "inconclusive"
        )

    def test_lifespan_wires_the_gate_before_the_redis_swallow(self) -> None:
        import backend.main as main_module

        src = inspect.getsource(main_module)
        lifespan_src = src[src.index("async def lifespan") :]
        assert "run_constrained_startup_check" in lifespan_src
        redis_pos = lifespan_src.index("Redis connection failed")
        gate_pos = lifespan_src.index("run_constrained_startup_check")
        assert gate_pos < redis_pos, "gate must run BEFORE the Redis block"

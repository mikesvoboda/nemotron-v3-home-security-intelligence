"""WP7.1 red-first: the AI contract registry must declare every AI-tier operation.

Contract sources (plan P WP7.1, priority order): the deployed gateway adapters
(ai/gateway/adapters/*.py), the backend client classes (consumer side), and the
llama.cpp / ai-llm wire shape. The registry is GENERATED from those surfaces
(scripts/gen-ai-contract.py), never hand-maintained.

Architecture rule this file exists to protect: backend/ai_contract must not
import ai.* at runtime (the dependency direction that made prompts.py:4381 a
live crash). The last test here enforces it on the real module graph.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

# The 38 operations, derived from the deployed surfaces (each verified by file
# evidence at the time of drafting; the generator regenerates the registry from
# the same surfaces and CI diffs it):
# - 31 functional gateway routes: direct enumeration of @router decorators over
#   the five adapters mounted at /yolo26 /clip /florence /enrichment /enrich-lt
#   (ai/gateway/main.py:181-185); the five /health routes are deliberately NOT
#   operations (per-adapter liveness, not provider capability).
# - 3 LLM-side: llama.cpp /completion (seven independent backend call sites),
#   ai/nemotron/model_hf.py /v1/chat/completions, llama.cpp-only /slots.
# - 4 client-side phantom paths: EnrichmentClient/model_management call sites
#   whose paths exist on NO gateway adapter (WP7.3 Tier A: 404 in production).
EXPECTED_OPERATIONS: frozenset[str] = frozenset(
    {
        # yolo26 adapter (deployed provider; UNFILTERED class vocabulary)
        "yolo26_detect",
        "yolo26_detect_batch",
        "yolo26_segment",
        # clip adapter
        "clip_embed",
        "clip_classify",
        "clip_similarity",
        "clip_batch_similarity",
        "clip_anomaly_score",
        # florence adapter
        "florence_extract",
        "florence_batch_extract",
        "florence_ocr",
        "florence_ocr_with_regions",
        "florence_detect",
        "florence_dense_caption",
        "florence_describe_region",
        "florence_phrase_grounding",
        "florence_detect_security_objects",
        "florence_analyze_scene",
        # enrichment (heavy) adapter
        "enrichment_vehicle_classify",
        "enrichment_clothing_classify",
        "enrichment_demographics",
        "enrichment_action_classify",
        "enrichment_pet_classify",
        "enrichment_depth_estimate",
        "enrichment_pose_analyze",
        "enrichment_enrich",
        # enrichment-light adapter (the /enrich-lt slot)
        "enrich_lt_pose_analyze",
        "enrich_lt_threat_detect",
        "enrich_lt_person_reid",
        "enrich_lt_pet_classify",
        "enrich_lt_depth_estimate",
        # LLM wire (ai-llm deployed; llama.cpp serves /completion + /slots,
        # model_hf.py serves /v1/chat/completions - Tier C divergence)
        "llm_completion",
        "llm_chat_completion",
        "llm_slots",
        # client-side phantom paths - declared HERE so the gap is
        # machine-readable (they 404 on the deployed gateway today)
        "model_status",
        "model_preload",
        "model_unload",
        "object_distance",
    }
)

# Client modules whose public methods must each map to a registry operation
# (via Operation.client_methods). Consumer side of the contract. The four
# client classes (DetectorClient, CLIPClient, FlorenceClient,
# EnrichmentClient - which fronts BOTH heavy /enrichment and /enrich-lt) are
# the "six backend clients" of the plan text counting the enrichment split.
CLIENT_GLOBS = (
    "backend/services/detector_client.py",
    "backend/services/clip_client.py",
    "backend/services/florence_client.py",
    "backend/services/enrichment_client.py",
)


def _public_client_methods() -> set[str]:
    """AST-collect public method names of classes in the client modules.

    AST, not import: a test that imports the clients drags settings/redis
    singletons in; the registry test must stay a pure structural check.
    """
    methods: set[str] = set()
    for glob in CLIENT_GLOBS:
        for path in sorted(REPO_ROOT.glob(glob)):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for sub in node.body:
                        if isinstance(
                            sub, (ast.FunctionDef, ast.AsyncFunctionDef)
                        ) and not sub.name.startswith("_"):
                            methods.add(sub.name)
    return methods


class TestContractRegistry:
    def test_package_imports_without_ai(self) -> None:
        """backend/ai_contract exists and no file in it imports ai.*.

        AST-based (not a string scan: docstrings legitimately *state* the
        rule) and not sys.modules-based (an earlier test may legitimately
        have loaded ai/, so module presence can't be attributed to this
        package). The dependency-direction rule is a source property - it is
        what made prompts.py:4381 a live crash.
        """
        from backend import ai_contract

        pkg_dir = Path(inspect.getfile(ai_contract)).parent
        offenders: list[str] = []
        for py in sorted(pkg_dir.rglob("*.py")):
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
            for node in ast.walk(tree):
                mods: list[str] = []
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    mods = [node.module]
                if any(m == "ai" or m.startswith("ai.") for m in mods):
                    offenders.append(f"{py.relative_to(pkg_dir)}: {mods}")
        assert not offenders, f"ai.* runtime imports in the contract package: {offenders}"

    def test_registry_contains_all_38_operations(self) -> None:
        from backend.ai_contract.operations import OPERATION_IDS

        assert frozenset(OPERATION_IDS) == EXPECTED_OPERATIONS, (
            f"registry/surface drift: missing="
            f"{sorted(EXPECTED_OPERATIONS - frozenset(OPERATION_IDS))} "
            f"unexpected={sorted(frozenset(OPERATION_IDS) - EXPECTED_OPERATIONS)}"
        )
        assert len(OPERATION_IDS) == 38

    def test_every_operation_declares_method_path_and_matrix_row(self) -> None:
        from backend.ai_contract.operations import OPERATIONS

        for op in OPERATIONS.values():
            assert op.method in {"GET", "POST", "PUT", "DELETE"}, op.id
            assert op.path.startswith("/"), op.id
            # availability matrix: generated, one row per provider slot
            assert op.availability, f"{op.id} has no availability row"
            assert set(op.availability) >= {
                "gateway",
                "enrichment_light_adapter",
                "per_model_server",
                "fake",
            }, f"{op.id} availability matrix is missing provider slots"

    def test_every_client_method_maps_to_an_operation(self) -> None:
        """No consumer method may hit a path the registry doesn't declare -
        that inversion (client knows a route the contract doesn't) is exactly
        how the four phantom Tier-A paths were born."""
        from backend.ai_contract.operations import CLIENT_METHODS

        unmapped = _public_client_methods() - set(CLIENT_METHODS)
        # _public_client_methods returns every public method on the client
        # classes; helpers that make no HTTP call are whitelisted IN the
        # registry (mapped_to=None records that judgement, generated-side).
        assert not unmapped, f"client methods with no registry mapping: {sorted(unmapped)}"

    def test_availability_matrix_is_generated_not_hand_maintained(self) -> None:
        """The matrix file carries the generator's provenance header; CI
        re-runs scripts/gen-ai-contract.py --check and diffs."""
        from backend.ai_contract import operations as operations_module

        # path is importlib-resolved from the installed package itself, not
        # user input (house precedent: inline nosemgrep, e.g. system.py:2560)
        src = Path(inspect.getfile(operations_module)).read_text(  # nosemgrep: path-traversal-open
            encoding="utf-8"
        )
        assert "GENERATED by scripts/gen-ai-contract.py" in src, (
            "operations.py must carry generator provenance - a hand-edited "
            "registry is the drift this whole file exists to catch"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

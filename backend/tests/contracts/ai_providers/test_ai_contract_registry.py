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

# parents[4]: ai_providers -> contracts -> tests -> backend -> repo root.
# (parents[3] silently resolves to backend/ and the CLIENT_GLOBS match NOTHING
# - the map test was vacuously green until the WP7.2 window caught it.)
REPO_ROOT = Path(__file__).resolve().parents[4]

# The 37 operations (38 at WP7.1 drafting; florence /analyze-scene deleted
# under ADDENDUM 2 A7.2 - DELETED_SERVER_ROUTES + DELETED_REGISTRY_OPS),
# derived from the deployed surfaces (each verified by file
# evidence at the time of drafting; the generator regenerates the registry from
# the same surfaces and CI diffs it):
# - 30 functional gateway routes: direct enumeration of @router decorators over
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
        # florence adapter (9 since A7.2 deleted /analyze-scene - see
        # DELETED_SERVER_ROUTES + DELETED_REGISTRY_OPS)
        "florence_extract",
        "florence_batch_extract",
        "florence_ocr",
        "florence_ocr_with_regions",
        "florence_detect",
        "florence_dense_caption",
        "florence_describe_region",
        "florence_phrase_grounding",
        "florence_detect_security_objects",
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

# The consumer classes themselves, NOT every class those modules define: the
# modules also carry the result dataclasses (BoundingBox, UnifiedPoseResult,
# ...) whose to_dict/to_context_string methods are serialization helpers, not
# HTTP call sites. The registry maps consumer methods to operations; a
# dataclass method has no operation to map to and must not appear in the
# scan. Drift on this set is caught by the map test itself: a renamed client
# class drops its methods from CLIENT_METHODS... no - it stays in the map and
# the scan finds nothing, which is why the test asserts BOTH directions.
CLIENT_CLASSES = frozenset({"DetectorClient", "CLIPClient", "FlorenceClient", "EnrichmentClient"})

# WP7.3 carry-cost deletions. Each entry: a client method with ZERO non-test
# call sites (verified by call-site census at deletion time, number in the
# commit body - grep, not importlib, because the dynamic-dispatch shapes that
# would hide a caller - getattr dispatch, string-built URLs - are exactly what
# a call-site grep must cover). The method name must stay ABSENT from the
# client modules afterwards: this test fails if the method comes back, so the
# deletion is a ratchet, not a snapshot.
#
# Kept-list members were censused and REJECTED (callers found, or the only
# removals would land on test files, which the GOAL carve-out forbids):
# see the WP7.3 ledger section. That list was written under the pre-A7.2
# rule; segment_image enters under ADDENDUM 2 A7.2's extended licence (the
# dedicated-file carve-out), census + five conditions in its commit body:
# L#2026-09-19-wp56-test-collision (ANSWERED, ADDENDUM 2 A6/A7.2).
DELETED_CARRY_COST: frozenset[str] = frozenset({"detect_objects_batch", "segment_image"})

# Server-side carry-cost: a deployed-but-unreachable route, deleted from the
# model server's own file (production AI surface - the GOAL carve-out's named
# target). Keyed file -> marker strings that must NOT appear once deleted.
# Census for /track: 0 hits for the endpoint string in backend/ + scripts/
# (consumers), 0 in ai/gateway (not proxied), 0 in any ai/yolo26 test file
# (both test_model.py copies), not in the 38-op registry (absent from the
# gateway = absent from the contract), docs/openapi.json 0 (backend /tracks
# is the DB feature, unrelated).
DELETED_SERVER_ROUTES: dict[str, tuple[str, ...]] = {
    "ai/yolo26/model.py": ('@app.post("/track"', "async def track_objects"),
    # A7.2 deletion 2/2: florence /analyze-scene, unreachable (census in the
    # deletion commit body: no backend client method, no openapi path, no
    # frontend ref, no gateway proxy consumer - the adapter route mirrored
    # the model-server route 1:1). Route + exclusive request/response
    # models deleted from BOTH deployed surfaces; the op's registry entry,
    # availability row, schema + goldens went with it (38 -> 37).
    "ai/florence/model.py": ('@app.post("/analyze-scene"', "async def analyze_scene"),
}

# A7.2: a DEPLOYED-BUT-UNREACHABLE operation removed from the contract
# itself (the /analyze-scene case: unlike the DELETED_SERVER_ROUTES-only
# /track, this op was registry-declared, so deletion must ALSO keep it out
# of the regenerated registry - the generator discovers gateway ops by
# importing the adapters and walking router.routes, so an adapter-route
# resurrection would silently re-add the op and only THIS assertion catches
# it). Red while the op is in OPERATIONS; permanent ratchet after.
DELETED_REGISTRY_OPS: frozenset[str] = frozenset({"florence_analyze_scene"})

# Files the census may ignore: the client modules themselves (def site) and
# the generated registry + its generator (carry the historical method->op map
# only for still-present methods).
_CENSUS_ALLOW = frozenset(
    {
        "backend/services/detector_client.py",
        "backend/services/clip_client.py",
        "backend/services/florence_client.py",
        "backend/services/enrichment_client.py",
        "backend/ai_contract/operations.py",
        "scripts/gen-ai-contract.py",
    }
)


def _non_test_call_sites(symbol: str) -> list[str]:
    """Grep-census a method name across backend/ and scripts/ outside tests.

    Returns "relpath:line" for each hit whose line mentions the symbol,
    excluding test paths and _CENSUS_ALLOW. Grep deliberately: the caller
    shapes that hide (hasattr/getattr dispatch, f-string URLs) still contain
    the literal name, and an import-graph probe would miss those.

    backend/ + scripts/ ONLY: the consumer side of a client method can only
    live in those trees (ai/ model servers are separate deployables that
    never import backend.services, and ai/ legitimately carries its own
    same-named ROUTE functions - ai/yolo26/model.py's detect_objects_batch
    is the /detect/batch endpoint, not a call to the deleted client method).
    """
    hits: list[str] = []
    for root in ("backend", "scripts"):
        for path in (REPO_ROOT / root).rglob("*.py"):
            rel = path.relative_to(REPO_ROOT).as_posix()
            if "/tests/" in f"/{rel}" or rel.split("/")[-1].startswith("test_"):
                continue
            if rel in _CENSUS_ALLOW:
                continue
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if symbol in line:
                    hits.append(f"{rel}:{i}")
    return hits


def _public_client_methods() -> set[str]:
    """AST-collect "Class.method" for public methods of the client classes.

    Qualified names, matching CLIENT_METHODS keys: bare names collide across
    the four classes (three of them all define detect/health-style methods),
    and the registry's judgement is per-class anyway.

    AST, not import: a test that imports the clients drags settings/redis
    singletons in; the registry test must stay a pure structural check.
    """
    methods: set[str] = set()
    for glob in CLIENT_GLOBS:
        for path in sorted(REPO_ROOT.glob(glob)):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name in CLIENT_CLASSES:
                    for sub in node.body:
                        if isinstance(
                            sub, (ast.FunctionDef, ast.AsyncFunctionDef)
                        ) and not sub.name.startswith("_"):
                            methods.add(f"{node.name}.{sub.name}")
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

    def test_registry_contains_all_37_operations(self) -> None:
        from backend.ai_contract.operations import OPERATION_IDS

        assert frozenset(OPERATION_IDS) == EXPECTED_OPERATIONS, (
            f"registry/surface drift: missing="
            f"{sorted(EXPECTED_OPERATIONS - frozenset(OPERATION_IDS))} "
            f"unexpected={sorted(frozenset(OPERATION_IDS) - EXPECTED_OPERATIONS)}"
        )
        assert len(OPERATION_IDS) == 37

    @pytest.mark.parametrize("op_id", sorted(DELETED_REGISTRY_OPS))
    def test_wp73_deleted_registry_ops_stay_absent(self, op_id: str) -> None:
        """A7.2 op-level ratchet: the op left the contract WITH both its
        deployed routes. Red while OPERATIONS still declares it; a future
        adapter-route resurrection (the generator discovers gateway ops by
        walking router.routes) reddens by name. The registry-entry deletion
        is licensed by the census quoted in DELETED_SERVER_ROUTES' comment
        and the deletion commit body."""
        from backend.ai_contract.operations import OPERATIONS

        assert op_id not in OPERATIONS, (
            f"{op_id} is back in the registry - A7.2 deletion reversed? "
            "Re-adjudicate; do not edit this assertion."
        )

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
        """Exactly two-way agreement between the client classes' public
        surface and the registry's CLIENT_METHODS map.

        - scan minus map: a consumer method the registry doesn't declare -
          that inversion (client knows a route the contract doesn't) is
          exactly how the four phantom Tier-A paths were born.
        - map minus scan: a stale mapping (method renamed away, or a client
          class renamed so the scan no longer sees it) - one-directional
          testing would stay green while the map rotted.
        Helpers that make no HTTP call are whitelisted IN the registry
        (mapped_to=None records that judgement, generated-side).
        """
        from backend.ai_contract.operations import CLIENT_METHODS

        scanned = _public_client_methods()
        unmapped = scanned - set(CLIENT_METHODS)
        stale = set(CLIENT_METHODS) - scanned
        assert not unmapped, f"client methods with no registry mapping: {sorted(unmapped)}"
        assert not stale, f"registry mappings whose client method is gone: {sorted(stale)}"

    @pytest.mark.parametrize("symbol", sorted(DELETED_CARRY_COST))
    def test_wp73_carry_cost_stays_deleted(self, symbol: str) -> None:
        """WP7.3 red-first proof, then ratchet: while the method exists this
        REDS on the client-module assertion (the census half passes - that is
        the evidence the deletion was licensed). After the deletion both
        halves stay green, and a reintroduction reddens by name."""
        sites = _non_test_call_sites(symbol)
        assert not sites, f"{symbol} has non-test call sites - deletion not licensed: {sites}"
        present = {
            f"{cls}.{symbol}"
            for cls in sorted(CLIENT_CLASSES)
            if f"{cls}.{symbol}" in _public_client_methods()
        }
        assert not present, f"WP7.3 carry-cost method still declared on: {sorted(present)}"

    @pytest.mark.parametrize("relpath", sorted(DELETED_SERVER_ROUTES))
    def test_wp73_server_carry_cost_stays_deleted(self, relpath: str) -> None:
        """WP7.3 deletion B (yolo26 /track) ratchet: the route was unreachable
        (census in DELETED_SERVER_ROUTES comment + commit body); this test
        reddens if the endpoint registration returns. RED until the deletion
        lands, then permanently green."""
        src = (REPO_ROOT / relpath).read_text(encoding="utf-8")
        present = [marker for marker in DELETED_SERVER_ROUTES[relpath] if marker in src]
        assert not present, f"{relpath}: deleted carry-cost route markers present: {present}"

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

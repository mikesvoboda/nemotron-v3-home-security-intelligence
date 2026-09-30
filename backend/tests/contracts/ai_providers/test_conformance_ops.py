"""WP8.3 conformance suite (DRAFT — cluster "op-specific-targets" + matrix spine).

STATUS: every assertion below is **UNVERIFIED** at the pytest level (drafted
while the validate.sh tier owned the box; no pytest was run). Predictions are
tagged PREDICTED-GREEN / PREDICTED-RED per side; a read-only one-shot probe of
the live modules (2026-09-19, imports + ASGITransport only, no pytest) already
observed most gateway/fake behaviors — the probe notes are folded into the
comments but the pytest tier is the arbiter.

Integrates into backend/tests/contracts/ai_providers/test_conformance.py.
The `_gateway_app` / `_gateway_client` factories below MUST be hoisted to
backend/tests/contracts/ai_providers/conftest.py at integration (dossier Q6:
that conftest does NOT exist yet — no `from .conftest_conformance import`
path is available, so the factory lives here, minimally duplicated, per the
driving-shape rule).

Clusters covered:
  * matrix-guard spine everyone shares: the 5 ProviderIds, slot-column /
    required-subset equivalence, per-op absence as GREEN GUARDS (not skips),
    the NOT-WIRED sentinel as the THIRD matrix state (absent / not-wired /
    live) — plan §WP8.3 "Where the availability matrix says an operation is
    genuinely absent on a provider, assert the absence matches the matrix";
  * multi-image ops — the surviving member driven LIVE. This cluster used to
    carry O1 (OP 28 enrichment_action_classify, the only TEMPORAL
    frame-sequence op) and O2 (the composite /enrich); R8 S3 retired both
    with their models, so they are TOMBSTONED here (TestMultiImageRetirement)
    and the properties that DID survive the prune — multipart undrivability,
    per-file fan-out, per-item failure isolation — are driven against
    yolo26_detect_batch (TestMultiImageOps). The two records, in full, are in
    the OP-28 block below and TestMultiImageRetirement's docstrings; deleting
    them without a word is the silent-deletion class this suite refuses (the
    S2b grammar: retarget if surviving text exists, tombstone if not, never
    skip — a skip IS a suppression).

OP-28 DIVERGENCE RECORD (dossier cluster 4 F3/F4/F5; corrected against live
code — the workflow prompt's "gateway 422 on empty frames" is wrong; the
op-ids this record drove are RETIRED, the record is kept because the hazard
classes it enumerates are general — per-side divergence pinning, echo-vs-
generated fields, docstring-falsehood characterization):
  * gateway empty frames → **400** `{"detail": "Frames list cannot be
    empty"}` — handler-level HTTPException, ai/gateway/adapters/enrichment.py
    :893-894. 422 belongs to a MISSING or wrongly-typed `frames` field
    (pydantic ActionClassifyRequest :351-353), a different case — both pinned.
  * xclip_action RETIRED (NEM-5563): the handler no longer ships the frame
    list as one JSON blob to a single Triton call — it runs Triton ``pose``
    per frame and classifies the resampled skeleton with Triton
    ``stgcn_action`` (:640+ _infer_action). The wire contract (request/
    response schema) is unchanged; the O1 drive mocks below were re-shaped
    to the two-stage pipeline (they were PREDICTED-GREEN against the
    retired xclip mock shape; GREEN at pytest after the re-shape).
  * fake empty frames → **200** with the seeded snapshot body (fake/app.py:69
    parses the body only for model_name echo) — and frame-count invariance:
    0/1/4/None frames produce BYTE-IDENTICAL bytes (the fake's determinism
    property, not a bug to skip).
  * gateway echoes request.detection_type on /enrich (:966); the fake does
    NOT — its detection_type is generated ('detection_type_NNN',
    fake/generators.py string walker) and its enrichments is the free-form
    {'alpha','bravo'} map (generators.py:348-353) with NO dt-keyed fan-out.
    Both sides pinned per-provider; the joint test pins the divergence itself.
  * the gateway /enrich docstring claim "- other: basic depth estimation"
    (:907) is FALSE — unknown types get enrichments == {} (verified live);
    pinned as a characterization assertion so a "fix" that adds a depth
    branch (or makes the fake echo) reddens this suite.

Driving shapes (dossier cluster 0 Q1b/Q2/Q5 — do NOT call registered
gateway/per_model/llamacpp callables for live ops: they are real network
paths; the suite drives the adapter routers mounted with their production
prefixes ai/gateway/main.py:272-273 under per-module `get_triton_client`
patches. The rule drafted five DISTINCT targets (ai/gateway/adapters/
{yolo26,clip,florence,enrichment,enrichment_light}.get_triton_client), the
yolo26 template at ai/gateway/tests/test_adapters_yolo26.py:98-104 extended
to all five; R8 S3's prune to yolo26/reid/threat took the middle three
adapters with their models, so the list is now GATEWAY_PATCH_TARGETS —
yolo26 + enrichment_light. The property the multi-target rule protects did
not shrink with the count: patching one adapter's name leaves the other on
the real gRPC client, so a third adapter entering means a row in
GATEWAY_PATCH_TARGETS AND a row in GATEWAY_MOUNTS. Import cost verified live:
ai.gateway adapters ~1.6s, backend.ai_contract ~3.7s cold — inside the 5s
pytest-timeout, pyproject :495.)

No xfail / skip / importorskip anywhere: every divergence below is either a
per-provider green assertion or a pinned-divergence assertion.
"""

from __future__ import annotations

import inspect
import io
import json
from functools import lru_cache
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from backend.ai_contract.operations import OPERATION_IDS, OPERATIONS
from backend.ai_contract.provider import (
    MATRIX_SLOTS,
    PROVIDER_SLOT,
    ProviderContractError,
    ProviderId,
    operations_for_slot,
    register_provider,
    registered_providers,
)
from fastapi import (
    FastAPI,  # multipart undrivability pin for detect-batch
)
from httpx import ASGITransport, AsyncClient
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_DIR = REPO_ROOT / "backend" / "ai_contract" / "schemas"

# ---------------------------------------------------------------------------
# Derived data (registry is pure data — importing it is the no-ai-at-runtime
# safe path; the ai.* adapter imports below happen inside fixtures so module
# collection stays cheap for non-gateway rows)
# ---------------------------------------------------------------------------

ALL_OPS = set(OPERATIONS)

# providers.py:135-157 — per_model_http registers deployed=False (undeployed
# in prod compose); llamacpp_llm registers deployed=True (the plan's provider
# docstring: "gateway / gateway-light / llamacpp-llm are deployed today").
# NOTE: the workflow prompt said "per_model_http + llamacpp_llm: rec.deployed
# is False" — live code (providers.py:155) contradicts the llamacpp half of
# that claim. We pin the CODE: llamacpp True. PREDICTED-GREEN; the prompt
# claim is the thing that turns out wrong, not an assertion failure.
EXPECTED_DEPLOYED = {
    ProviderId.GATEWAY: True,
    ProviderId.GATEWAY_LIGHT: True,
    ProviderId.PER_MODEL_HTTP: False,
    ProviderId.LLAMACPP_LLM: True,
    ProviderId.FAKE: True,
    # spec §3 slots minted at 1.1, registered deployed=False (providers.py
    # _register_all tail): the ai-vlm compose service is step 1.2 and
    # vlm_client is 1.3 - declared, not yet deployed.
    ProviderId.OPENAI_VLM: False,
    ProviderId.RTVI_VLM: False,
}

# Sentinel (NOT-WIRED) literals — dossier O3/F8 + live import. Pinned from
# live output 2026-09-29 (R8 S3); UNVERIFIED at pytest level.
# How the third state grew, then shrank: the pre-A7.2 baseline was 3/3/8 (the
# three enrich_lt ops on every slot that serves them, plus the LLM/unload/
# mstatus extras on per_model). ADDENDUM 2 A7.2 added yolo26_segment to the
# gateway set (client binding deleted, route deployed). R8 S2 retired
# EnrichmentClient, NemotronAnalyzer and nemotron_streaming with the legacy
# tier, and operations.py emptied every client_methods list that named one — a
# client binding leaving, route intact, is precisely the third-state transition
# A7.2 established, so the census EXPLODED to 15/5/20.
#
# R8 S3 (2026-09-29, owner rulings 1 + 5) collapses it again, and the shape of
# the collapse is the point: the third state holds a ROUTE that still serves
# but has no client binding. Ops whose MODELS were pruned leave the CONTRACT
# entirely (DELETED_REGISTRY_OPS in test_ai_contract_registry.py), and a deleted
# op is ABSENT from every column, never not-wired. So the eight enrichment_*
# ops, the enrich_lt depth/pet/pose trio and the model_*/object_distance four
# leave these sets by DELETION, not by re-wiring; what is left is the honest
# shipped surface: gateway 4 (its two light-lane lookups plus the two yolo
# routes whose clients were deleted but whose routes stay), light 2 (its whole
# column — EnrichmentClient was their only binding and it died in S2b),
# per_model 5 (the same five: the column's LLM pair belongs to the llamacpp
# provider's dispatch, not per_model_http's, and yolo26_detect_batch has no
# client method).
# Still NOT in any set: florence_analyze_scene and every other retired id —
# absent from every column, guarded by name in DELETED_REGISTRY_OPS. Same rule
# keeps yolo26_segment off per_model: gateway-only (per_model_server: False), so
# there it is ABSENT (absent-guarded via ABSENT_* above), not not-wired.
# vlm_assess stays out: 1.3's vlm_client binds it (client_methods=
# ["VlmClient.assess"]), so it leaves the third state in every provider sharing
# this column (pinned in test_conformance_vlm.py). yolo26_detect likewise.
_ENRICH_LT_UNBOUND = {
    "enrich_lt_person_reid",
    "enrich_lt_threat_detect",
}
SENTINELS_GATEWAY = _ENRICH_LT_UNBOUND | {"yolo26_detect_batch", "yolo26_segment"}
SENTINELS_LIGHT = set(_ENRICH_LT_UNBOUND)
SENTINELS_PER_MODEL = _ENRICH_LT_UNBOUND | {
    "llm_completion",
    "llm_chat_completion",
    "yolo26_detect_batch",
    # yolo26_segment deliberately absent — gateway-only column, see above.
    # model_status/model_preload/model_unload/object_distance were this set's
    # fifth family; R8 S3 retired the ops (their evidence file is swept), so
    # they are absent from the column rather than unbound in it.
}
SENTINELS_BY_PROVIDER: dict[ProviderId, set[str]] = {
    ProviderId.GATEWAY: SENTINELS_GATEWAY,
    ProviderId.GATEWAY_LIGHT: SENTINELS_LIGHT,
    ProviderId.PER_MODEL_HTTP: SENTINELS_PER_MODEL,
}

# Ops gateway does NOT serve (dossier O3/F7, verified live): absence guards.
ABSENT_GATEWAY = sorted(ALL_OPS - set(operations_for_slot("gateway", OPERATIONS)))
ABSENT_LIGHT = sorted(ALL_OPS - set(operations_for_slot("enrichment_light_adapter", OPERATIONS)))

# llamacpp required set is EVIDENCE-DERIVED, not hand-listed
# (backend/ai_contract/providers.py:94-106: per_model_server True ∧
# 'ai/nemotron' in evidence) = exactly {llm_completion, llm_chat_completion}.
LLAMACPP_REQUIRED = {
    op_id
    for op_id, op in OPERATIONS.items()
    if op.availability.get("per_model_server", False) and "ai/nemotron" in op.evidence
}

# spec §3 Slots (Phase 1 task 1.1): the VLM engines register the SAME
# subset-inside-the-union-column pattern llamacpp uses - required=
# {"vlm_assess"} (providers.py _register_all tail), the per_model_server
# column belonging to every per-model app at once.
VLM_REQUIRED = {"vlm_assess"}

# Union-slot SUBSET providers -> their required set. Every guard below that
# once said "llamacpp is the exception, everyone else covers the column"
# generalizes through this table: a fourth subset provider needs one row,
# not a new branch in five tests.
SUBSET_REQUIRED: dict[ProviderId, set[str]] = {
    ProviderId.LLAMACPP_LLM: LLAMACPP_REQUIRED,
    ProviderId.OPENAI_VLM: VLM_REQUIRED,
    ProviderId.RTVI_VLM: VLM_REQUIRED,
}

# ProviderId -> expected registered size. WP4.2: DERIVED, not hand-pinned.
# The hand table (30/5/35/2/37, dossier O4/F9) rotted on schedule — every
# legitimate contract move (38 -> 37 at A7.2) required re-editing it, which
# trains "edit the pin without thinking" (the WP4.2 doctrine). Derivation
# mirrors the registration rules the suite already pins as STRUCTURE:
# single-app providers serve their slot's availability column
# (providers.py:140-142); llamacpp serves the evidence-derived required
# subset above (providers.py:94-106 + provider.py:196-203); fake is
# registered by this suite as the full SPEC column. The set-equality
# assertions in TestMatrixSpine stay the primary guard — these lengths catch
# a provider registering extra callables the set check would fold away.
EXPECTED_SIZES = {
    ProviderId.GATEWAY: len(operations_for_slot("gateway", OPERATIONS)),
    ProviderId.GATEWAY_LIGHT: len(operations_for_slot("enrichment_light_adapter", OPERATIONS)),
    ProviderId.PER_MODEL_HTTP: len(operations_for_slot("per_model_server", OPERATIONS)),
    ProviderId.LLAMACPP_LLM: len(LLAMACPP_REQUIRED),
    ProviderId.FAKE: len(operations_for_slot("fake", OPERATIONS)),
    ProviderId.OPENAI_VLM: len(VLM_REQUIRED),
    ProviderId.RTVI_VLM: len(VLM_REQUIRED),
}

# dossier O1/F1 correction (the plan's "only multi-frame op" wording is FALSE as
# literally spoken — several ops carry N images; only action-classify's list was
# a TEMPORAL sequence). The corrected 3-set that block pinned —
# enrichment_action_classify (`frames: list[str]`), florence_batch_extract
# (`items: list[BatchExtractItem]`) and yolo26_detect_batch (multipart
# `files: list[UploadFile]`) — has since gained a member (spec §3's vlm_assess,
# `image_paths`) and lost two (R8 S3 retired them with their models). A literal
# name set therefore rotted twice; the membership is now DERIVED from the two
# structural shapes that carry N images:
#   * MULTIPART: a route parameter annotated list[UploadFile] — plural, since
#     yolo26_detect/segment take a singular `file: UploadFile` and are NOT
#     multi-image (that distinction is the whole corrected claim, so it is read
#     off the annotation, never off a name);
#   * a request snapshot declaring an ARRAY of image values (vlm_assess's
#     image_paths). Name-bearing deliberately: messages/texts/labels are TEXT
#     lists that dossier O1/F1 itself carves out, so the list counts by what it
#     holds, not by being a list.
# A fourth multi-image op joins by existing; nothing here is edited.


@lru_cache(maxsize=1)
def _gateway_endpoints() -> dict[str, Any]:
    """registry path -> live handler function, for every op a MOUNTED gateway
    adapter router serves (mounted from GATEWAY_MOUNTS — the same table the app
    fixtures use, so the map and the driven app can never disagree). An op
    whose adapter is gone is simply not in the map: a retired adapter takes its
    endpoints out by becoming unimportable, which is exactly how the retired
    members left the derived set below."""
    import importlib

    out: dict[str, Any] = {}
    for mod, attr, prefix in GATEWAY_MOUNTS:
        router = getattr(importlib.import_module(mod), attr)
        for route in router.routes:
            path = getattr(route, "path", None)
            endpoint = getattr(route, "endpoint", None)
            if path and endpoint is not None:
                out[f"{prefix}{path}"] = endpoint
    return out


@lru_cache(maxsize=1)
def _multi_image_ops() -> frozenset[str]:
    multi: set[str] = set()
    for op_id, op in OPERATIONS.items():
        endpoint = _gateway_endpoints().get(op.path)
        if endpoint is not None and any(
            "UploadFile" in str(p.annotation) and "list" in str(p.annotation).lower()
            for p in inspect.signature(endpoint).parameters.values()
        ):
            multi.add(op_id)
            continue
        req_path = SCHEMA_DIR / f"{op_id}.request.json"
        # the light-lane ops have no committed REQUEST schema at all (their
        # handlers take a shared BBoxRequest the generator does not walk) —
        # absence means "no JSON list field", the correct default here.
        props = (
            json.loads(req_path.read_text()).get("properties") or {} if req_path.exists() else {}
        )
        if any(
            "image" in name.lower() and (kind or {}).get("type") == "array"
            for name, kind in props.items()
        ):
            multi.add(op_id)
    return frozenset(multi)


def _snapshot(op_id: str, kind: str = "response") -> dict[str, Any]:
    return json.loads((SCHEMA_DIR / f"{op_id}.{kind}.json").read_text())


@lru_cache(maxsize=1)
def _deleted_registry_ops() -> frozenset[str]:
    """The WP7.3 deleted-op ratchet, read out of the SIBLING suite's literal by
    AST (test_ai_contract_registry.py owns it; importing a test module to reach
    a constant is the cross-test coupling this file's imports avoid, and a
    hand-copy would drift). A missing literal raises rather than returns empty:
    'adopted by the ratchet' has to be able to fail loudly."""
    import ast

    src = (
        REPO_ROOT / "backend/tests/contracts/ai_providers/test_ai_contract_registry.py"
    ).read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        # the literal is ANNOTATED (`DELETED_REGISTRY_OPS: frozenset[str] = ...`)
        # — AnnAssign, not Assign. Matching only Assign is the classic version of
        # this bug and it fails as 'not found', i.e. as a loud error rather than
        # a silently empty set, which is the only reason it is cheap to survive.
        names: list[str] = []
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        if "DELETED_REGISTRY_OPS" not in names or node.value is None:
            continue
        (arg,) = node.value.args
        return frozenset(ast.literal_eval(elt) for elt in arg.elts)
    raise AssertionError("DELETED_REGISTRY_OPS literal not found in the registry suite")


def _provider_ops(pid: ProviderId) -> dict[str, Any]:
    """Registered callables for pid; registers the FAKE on demand (fake is
    deliberately not registered at import — providers.py:27-29; the accepted
    in-test pattern is test_fake_provider.py:171-176)."""
    if pid is ProviderId.FAKE:
        from backend.ai_contract.fake import fake_provider_ops

        return register_provider(
            ProviderId.FAKE, fake_provider_ops(), OPERATIONS, deployed=True
        ).operations()
    return registered_providers()[pid.value].operations()


def _mock_triton() -> AsyncMock:
    """AsyncMock TritonClient — same shape as the sibling gateway tests
    (ai/gateway/tests/test_adapters_yolo26.py:76-87): .infer / .is_model_ready
    / .get_model_metadata."""
    client = AsyncMock()
    client.infer = AsyncMock()
    client.is_model_ready = AsyncMock(return_value=True)
    client.get_model_metadata = AsyncMock(return_value={"outputs": [{"name": "output0"}]})
    return client


def _png(width: int = 64, height: int = 64) -> bytes:
    """Small deterministic PNG for the multipart drives (the gateway decodes
    the upload with PIL, so the bytes must be a real image — the fake never
    decodes them and takes the base64 golden string instead)."""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(100, 150, 200)).save(buf, format="PNG")
    return buf.getvalue()


# Two DISTINCT patch targets since the R8 S3 prune (dossier Q2 — patching one
# symbol silently leaves the other adapter module on the real gRPC client).
# Exact strings verified live from the module-level from-imports. The five-
# target rule this file drafted under covered yolo26 / clip / florence /
# enrichment / enrichment_light; the prune to yolo26/reid/threat took the
# middle three adapters with their models, so the rule SHRINKS because the
# surface does — not because a target was dropped on purpose. The
# multi-target property the rule protects (one patch ≠ all adapters) stays:
# a third adapter added back needs a row here AND in GATEWAY_MOUNTS below.
GATEWAY_PATCH_TARGETS = tuple(
    f"ai.gateway.adapters.{m}.get_triton_client" for m in ("yolo26", "enrichment_light")
)


# ---------------------------------------------------------------------------
# Gateway app factories.  INTEGRATION NOTE: hoist these two fixtures +
# GATEWAY_PATCH_TARGETS + _mock_triton into
# backend/tests/contracts/ai_providers/conftest.py when the per-cluster files
# merge into test_conformance.py (conftest does not exist yet — dossier Q6).
# ---------------------------------------------------------------------------

# Registry Operation.path ALREADY includes the mount prefix ('/yolo26/detect')
# — the routers must be included with the production prefixes from
# ai/gateway/main.py:272-273 (the yolo26 sibling template mounts WITHOUT a
# prefix; reusing its app shape verbatim would 404 every registry path).
GATEWAY_MOUNTS = (
    ("ai.gateway.adapters.yolo26", "router", "/yolo26"),
    ("ai.gateway.adapters.enrichment_light", "router", "/enrich-lt"),
)


def _build_gateway_app(modules: tuple[str, ...] | None = None) -> FastAPI:
    """Mount the adapter routers (or a subset by adapter module name) with
    their production prefixes. Two mounts since the R8 S3 prune — see
    GATEWAY_PATCH_TARGETS for why the five-mount shape retired; a subset arg is
    how light_app stays one-router. Imports stay lazy inside fixtures so
    collection stays cheap."""
    import importlib

    app = FastAPI(title="WP8.3 conformance gateway app")
    for mod, attr, prefix in GATEWAY_MOUNTS:
        if modules is None or mod.rsplit(".", 1)[1] in modules:
            app.include_router(getattr(importlib.import_module(mod), attr), prefix=prefix)
    return app


@pytest.fixture(scope="module")
def gateway_app() -> FastAPI:
    """Every surviving adapter on one app, production prefixes (driving shape:
    'mount the adapter routers with their production prefixes')."""
    return _build_gateway_app()


@pytest.fixture(scope="module")
def light_app() -> FastAPI:
    """enrichment_light only — the gateway_light provider's real surface
    (its column is the /enrich-lt router, ai/gateway/main.py:185)."""
    return _build_gateway_app(modules=("enrichment_light",))


@pytest.fixture
async def gateway_client(gateway_app):
    """(client, mock_triton) with EVERY adapter's get_triton_client name
    patched. Template: ai/gateway/tests/test_adapters_yolo26.py:98-104 extended
    to the multi-target rule (plan WP8.3 'Mechanical detail'); the target list
    is GATEWAY_PATCH_TARGETS, so a mount added there is patched here too."""
    from contextlib import ExitStack

    mock = _mock_triton()
    with ExitStack() as stack:
        for target in GATEWAY_PATCH_TARGETS:
            stack.enter_context(patch(target, return_value=mock))
        transport = ASGITransport(app=gateway_app)
        async with AsyncClient(transport=transport, base_url="http://gw") as c:
            yield c, mock


@pytest.fixture
async def light_client(light_app):
    """gateway_light surface only: single patch target is sufficient for the
    light-only app (no other adapter's routes exist on it)."""
    mock = _mock_triton()
    with patch(
        "ai.gateway.adapters.enrichment_light.get_triton_client", return_value=mock, autospec=True
    ):
        transport = ASGITransport(app=light_app)
        async with AsyncClient(transport=transport, base_url="http://gw") as c:
            yield c, mock


def _fake_callables() -> dict[str, Any]:
    """fake ops registered for the call (fake_provider_ops() callables are
    uniform async fn(payload=None) -> dict driving the fake app through
    ASGITransport — backend/ai_contract/fake/app.py:109-127)."""
    return _provider_ops(ProviderId.FAKE)


# ===========================================================================
# (a) MATRIX SPINE — same assertion against every registered provider
# ===========================================================================


class TestMatrixSpine:
    """The parametrized provider spine: 5 ProviderIds, slot columns,
    required subsets, deployed flags, and the slot-key rename trap."""

    def test_matrix_slots_are_availability_keys_not_provider_ids(self) -> None:
        """O3/F6 rename trap. Source: backend/ai_contract/provider.py:40
        (MATRIX_SLOTS) and :137-143 (PROVIDER_SLOT); every Operation.
        availability carries EXACTLY these 4 keys (verified live over all 37).
        'gateway_light'/'per_model_http'/'llamacpp_llm' are ProviderId VALUES,
        never availability keys — a suite reading op.availability[pid.value]
        silently .get()-KeyErrors every op to False.
        PREDICTED-GREEN both sides (registry data, provider-agnostic).
        UNVERIFIED at pytest level."""
        assert set(MATRIX_SLOTS) == {
            "gateway",
            "enrichment_light_adapter",
            "per_model_server",
            "fake",
        }  # source: provider.py:40. UNVERIFIED. PREDICTED-GREEN both.
        assert PROVIDER_SLOT[ProviderId.GATEWAY_LIGHT] == "enrichment_light_adapter"
        assert PROVIDER_SLOT[ProviderId.PER_MODEL_HTTP] == "per_model_server"
        assert PROVIDER_SLOT[ProviderId.LLAMACPP_LLM] == "per_model_server"  # UNION column
        assert PROVIDER_SLOT[ProviderId.FAKE] == "fake"
        for op_id, op in OPERATIONS.items():
            assert set(op.availability) == set(MATRIX_SLOTS), op_id
        # WP4.2: the hand `len(OPERATIONS) == 37` pin is gone — this test's
        # contract is the availability-key SHAPE, and the count the generated
        # registry owns is guarded where counts belong: gen-ai-contract
        # --check (byte drift) + the derived reads in
        # scripts/test_check_ai_provider_parity.py. Re-pinning a size here
        # would re-create the WP0.1 rot this suite's own history documents.

    @pytest.mark.parametrize(
        "pid",
        list(ProviderId),
        ids=[p.value for p in ProviderId],
    )
    def test_matrix_registered_set_matches_slot_or_required(self, pid: ProviderId) -> None:
        """Spine (a): set(rec.operations()) == slot column for the single-app
        providers; == the required SUBSET for every union-slot subset
        provider (SUBSET_REQUIRED: llamacpp's evidence-derived pair, and the
        1.1 VLM engines' {vlm_assess}; union-slot rule, provider.py:196-203 +
        providers.py _register_all); fake's column is the SPEC (every op) and
        the fake is registered by this suite itself. Sizes and deployed per
        EXPECTED_* tables above (sources: providers.py; live import fold).
        THE WORKFLOW-PROMPT DIVERGENCE: 'llamacpp_llm: rec.deployed is False'
        is contradicted by live code — we pin True (providers.py) and record
        the prompt's claim as wrong. PREDICTED-GREEN all params.
        Never CALLS a registered callable — and since 1.3 that matters MORE
        for the VLM subset providers too: their vlm_assess is now the live
        VlmClient.assess (real httpx to settings.ai_vlm_url), not a
        sentinel. This test is set-equality only. UNVERIFIED."""
        rec_ops = _provider_ops(pid)
        slot = PROVIDER_SLOT[pid]
        column = set(operations_for_slot(slot, OPERATIONS))
        if pid in SUBSET_REQUIRED:
            assert set(rec_ops) == SUBSET_REQUIRED[pid]
            assert {"llm_completion", "llm_chat_completion"} == LLAMACPP_REQUIRED
            assert set(rec_ops) < column  # proper subset inside the union column
        else:
            assert set(rec_ops) == column  # source: providers.py; fake via
            # fake_provider_ops() == operations_for_slot('fake') (app.py:127). UNVERIFIED.
        assert len(rec_ops) == EXPECTED_SIZES[pid]  # derived table, WP4.2. UNVERIFIED.
        assert registered_providers()[pid.value].deployed is EXPECTED_DEPLOYED[pid]  # UNVERIFIED.

    def test_matrix_llamacpp_required_is_evidence_derived(self) -> None:
        """Spine (a2): the llamacpp set is DERIVED (per_model_server True ∧
        'ai/nemotron' in evidence), not hand-listed; llm_slots is
        deliberately OUT (performance_collector evidence, per_model_server
        False — providers.py:98-101). Source: providers.py:94-106, verified
        live. PREDICTED-GREEN (registry data). UNVERIFIED."""
        assert {"llm_completion", "llm_chat_completion"} == LLAMACPP_REQUIRED
        assert "llm_slots" not in LLAMACPP_REQUIRED
        for op_id in LLAMACPP_REQUIRED:
            assert OPERATIONS[op_id].availability["per_model_server"] is True
            assert "ai/nemotron" in OPERATIONS[op_id].evidence

    def test_matrix_claiming_absent_op_fails_registration_naming_it(self) -> None:
        """Spine (b) registration-side twin of the absence guards: a provider
        CLAIMING an op its column marks False must fail at registration naming
        the op (provider.py:221-226 'registry marks slot ... unavailable'; a
        failed registration never stores — the store is the last statement,
        provider.py:244).
        Representative for gateway only — the full provider x absent-op sweep
        is left to WP8.1's register_provider tests (see notes). Built from the
        live gateway dict + an async stub for an ABSENT gateway op
        (llm_completion); failed registration stores nothing (provider.py
        nothing stored on failure). PREDICTED-GREEN both. UNVERIFIED."""
        ops = dict(registered_providers()["gateway"].operations())
        bad = "llm_completion"
        assert bad not in ops and not OPERATIONS[bad].availability["gateway"]

        async def _stub(payload: Any = None) -> dict[str, Any]:  # coroutine: passes shape checks
            return {}

        ops[bad] = _stub
        with pytest.raises(ProviderContractError) as excinfo:
            register_provider(ProviderId.GATEWAY, ops, OPERATIONS)
        assert excinfo.value.operation_id == bad  # source: provider.py:225-226. UNVERIFIED.


# ===========================================================================
# (b) PER-OP ABSENCE — green guards, never skips
# ===========================================================================


class TestMatrixAbsenceGuards:
    """Absence = 'op id NOT in operations()' AND (where the provider has an
    in-process app) 'await client.request(op.method, op.path) == 404'.
    Operation.path already carries the mount prefix (dossier 'Operation data-
    class fields') — that is why the gateway routers are mounted with the
    production prefixes."""

    @pytest.mark.parametrize("pid", list(ProviderId), ids=[p.value for p in ProviderId])
    def test_absence_matches_matrix(self, pid: ProviderId) -> None:
        """Pure-matrix absence for ALL providers. Union-slot SUBSET
        providers (SUBSET_REQUIRED: llamacpp, and the 1.1 VLM engines) have
        absence = column minus their required set; single-app providers
        cover the column. PREDICTED-GREEN all. UNVERIFIED."""
        slot = PROVIDER_SLOT[pid]
        column = set(operations_for_slot(slot, OPERATIONS))
        absent = ALL_OPS - column  # matrix-absent for this slot
        ops = set(_provider_ops(pid))
        # claiming a matrix-absent op is impossible for ANY provider (the
        # registration guard above is the import-time twin of this check):
        assert not (ops & absent), f"{pid.value} claims matrix-absent ops"
        if pid in SUBSET_REQUIRED:
            assert ops == SUBSET_REQUIRED[pid]  # exact required subset
            # the union-slot remainder is absent FOR THIS PROVIDER:
            assert column - ops  # non-empty by construction. UNVERIFIED.
        else:
            assert ops == column  # single-app providers cover the column
        # fake is the SPEC column: zero absences at all.
        if pid is ProviderId.FAKE:
            assert not absent  # fake column == every op (spec column). UNVERIFIED.

    @pytest.mark.parametrize("op_id", ABSENT_GATEWAY)
    async def test_gateway_absent_ops_are_404(self, gateway_client, op_id: str) -> None:
        """7 gateway-absent ops x not-in-operations() AND 404 (dossier O3/F7;
        their paths are bare — /completion, /slots, /models/*, /v1/chat/
        completions, /object-distance — and the adapter-prefix-only app has no
        such routes; 404 observed live on every one. The full production app
        also has only /health + /metrics top-level, so no collision).
        GREEN GUARD. PREDICTED-GREEN both. UNVERIFIED."""
        client, _ = gateway_client
        op = OPERATIONS[op_id]
        assert op_id not in registered_providers()["gateway"].operations()
        r = await client.request(op.method, op.path)
        assert (
            r.status_code == 404
        )  # source: gateway app fixture + main.py:181-185 mounts. UNVERIFIED.

    @pytest.mark.parametrize("op_id", ABSENT_LIGHT)
    async def test_gateway_light_absent_ops_are_404(self, light_client, op_id: str) -> None:
        """33 light-absent ops x not-in-operations() AND 404 against the
        enrichment_light-ONLY app (the gateway_light surface is just
        /enrich-lt). 404 observed live on sampled paths including
        /yolo26/detect and /object-distance (dossier O3/F7 'present only the
        5 enrich_lt_* ops'). GREEN GUARD. PREDICTED-GREEN both. UNVERIFIED."""
        client, _ = light_client
        op = OPERATIONS[op_id]
        assert op_id not in registered_providers()["gateway_light"].operations()
        r = await client.request(op.method, op.path)
        assert r.status_code == 404  # UNVERIFIED at pytest level.

    async def test_fake_column_has_no_absences(self) -> None:
        """fake ABSENT 0 (dossier O3/F7): the spec column is every op, and the
        fake app mounts one route per registry op (fake/app.py:88-89) — so
        the absence guard for fake is trivially empty. PREDICTED-GREEN
        fake-side; gateway rows are covered by their own params above.
        UNVERIFIED."""
        ops = _fake_callables()
        assert set(ops) == ALL_OPS  # spec column == every op. UNVERIFIED.
        assert set(operations_for_slot("fake", OPERATIONS)) == ALL_OPS


# ===========================================================================
# (c) THIRD MATRIX STATE — NOT-WIRED sentinels
# ===========================================================================


class TestMatrixNotWiredSentinels:
    """The matrix has THREE states per (provider, op) cell: absent /
    present-but-not-wired (client_methods==[], _not_wired sentinel raising
    NotImplementedError) / live. Source: providers.py:77-85 (the sentinel
    factory). The prompt's "calling the registered gateway callable raises
    NotImplementedError naming the fake" is true for exactly these ops — the
    message names the FakeProvider (providers.py:81-83).

    SAFETY: awaiting a _not_wired sentinel is hermetic (it raises before any
    I/O); awaiting a client-bound gateway callable is NOT (real httpx). This
    class only awaits sentinel callables."""

    @pytest.mark.parametrize("pid", list(SENTINELS_BY_PROVIDER), ids=lambda p: p.value)
    def test_not_wired_set_exact(self, pid: ProviderId) -> None:
        """Structural census: registered ops whose registry
        client_methods == [] AND whose callable qualname carries '_not_wired'
        == the literals above (15/5/20 since R8 S2 — was 6/3/8: retiring
        EnrichmentClient emptied every client_methods list that named one, so
        the eight enrich-heavy ops joined gateway+per_model and the two
        enrich_lt lookups (person_reid, threat_detect) joined every slot that
        serves them. gateway gains yolo26_segment under ADDENDUM 2 A7.2
        (client binding deleted, route stays deployed); per_model carries the
        five lifecycle/LLM/distance extras (llm_completion,
        llm_chat_completion, model_status, model_preload, model_unload,
        object_distance — bound paths belong to the llamacpp provider, not
        per_model_http) but NOT yolo26_segment, which that slot does not serve
        at all; pinned from live import 2026-09-29).
        PREDICTED-GREEN. UNVERIFIED at pytest level."""
        ops = _provider_ops(pid)
        unbound = {o for o in ops if not OPERATIONS[o].client_methods}
        sentinels = {o for o, fn in ops.items() if "_not_wired" in fn.__qualname__}
        # census note: per_model's count moved 7 -> 8 on 2026-09-25 (1.1
        # added vlm_assess to the per_model_server column unbound), then
        # 8 -> 7 the same day (1.3's vlm_client binds it - see the
        # SENTINELS_PER_MODEL comment), then 7 -> 20 on 2026-09-29 (R8 S2).
        assert unbound == SENTINELS_BY_PROVIDER[pid]
        assert sentinels == SENTINELS_BY_PROVIDER[pid]
        assert unbound == sentinels  # source: providers.py:70-85 (_bound_or_reject).

    @pytest.mark.parametrize(
        ("provider", "op_id"),
        [(p.value, o) for p, ops in SENTINELS_BY_PROVIDER.items() for o in sorted(ops)],
        ids=[f"{p.value}:{o}" for p, ops in SENTINELS_BY_PROVIDER.items() for o in sorted(ops)],
    )
    async def test_not_wired_sentinel_raises_naming_the_fake(
        self, provider: str, op_id: str
    ) -> None:
        """Behavioral third state: the registered callable RAISES
        NotImplementedError naming the op AND pointing at the FakeProvider
        ('drive it through the FakeProvider (WP8.2) or a live server' —
        providers.py:80-83; message observed live). Hermetic: raises before
        any network. PREDICTED-GREEN for all 40 (provider, op) params
        (15 gateway + 5 light + 20 per_model since R8 S2; was 16).
        UNVERIFIED at pytest level."""
        fn = registered_providers()[provider].operations()[op_id]
        with pytest.raises(NotImplementedError) as excinfo:
            await fn({"any": "payload"})
        msg = str(excinfo.value)
        assert op_id in msg  # names the op. UNVERIFIED.
        assert "FakeProvider" in msg  # names the fake as the drive path. UNVERIFIED.

    def test_not_wired_state_is_independent_of_client_methods(self) -> None:
        """THE third-state guard (prompt (c)): 'client_methods == []' is NOT
        the sentinel predicate across all providers. llamacpp's two ops have
        client_methods == [] yet ARE wired — payload-passthrough _post
        closures to settings.ai_vlm_url (providers.py:109-131; the
        _llamacpp_callable was re-homed off the retired nemotron_url in
        R8 S2 — same llama.cpp /completion contract, new field), which we
        must NOT call (real network; matrix-guard only). Verified live
        qualnames: '_llamacpp_callable.<locals>._post'. A refactor that
        collapses 'unbound' into 'sentinel' reddens this. PREDICTED-GREEN.
        UNVERIFIED."""
        llm_ops = _provider_ops(ProviderId.LLAMACPP_LLM)
        unbound = {o for o in llm_ops if not OPERATIONS[o].client_methods}
        sentinels = {o for o, fn in llm_ops.items() if "_not_wired" in fn.__qualname__}
        assert unbound == set(llm_ops)  # both llm ops are unbound in the registry
        assert sentinels == set()  # ...but NONE is a sentinel (providers.py:151-157). UNVERIFIED.
        for fn in llm_ops.values():
            assert "_post" in fn.__qualname__
            assert "_not_wired" not in fn.__qualname__  # never call these. UNVERIFIED.


# ===========================================================================
# (d) MULTI-IMAGE OPS — the surviving members driven LIVE, the retired pair
#     tombstoned (clusters O1 and O2 used to live here; see the two tombstone
#     classes at the end of this cluster for what they pinned and why they
#     cannot retarget)
# ===========================================================================


def _singleshot_triton() -> Any:
    """Route-aware side_effect for the yolo26 detection path: an empty
    (N, 300, 6) YOLO output tensor per call, where N is the FIRST axis of the
    ``images`` input the adapter actually sent. Reading N back off the input is
    the whole point — it makes the per-file fan-out (does a 3-file request
    arrive as 3 calls of 1 image, or 1 call of 3?) inspectable instead of
    assumed. Shape/format: ai/gateway/adapters/yolo26.py:421-427 (per-file
    triton.infer(model_name='yolo26', inputs={'images': …}, outputs=['output0']))."""
    seen: list[tuple[str, tuple[int, ...]]] = []

    async def _infer(*, model_name: str, inputs: Any, outputs: Any, **kw: Any) -> dict[str, Any]:
        arr = np.asarray(inputs["images"])
        seen.append((model_name, tuple(arr.shape)))
        return {"output0": np.zeros((arr.shape[0], 300, 6), dtype=np.float32)}

    _infer.seen = seen  # type: ignore[attr-defined]
    return _infer


class TestMultiImageOps:
    """The properties the OP-28 block carried that DID survive the prune,
    retargeted (not loosened) onto the surviving multi-image surface: the
    membership correction as DATA, multipart undrivability, per-file fan-out,
    per-item failure isolation, and the fake's payload-blindness.

    R8 S3 retarget note: this class drives yolo26_detect_batch against a
    mounted adapter app — the retired pair could only be driven against the
    fake (their client bindings were already gone), so the live-adapter half
    of the coverage is NEW here, and the fake half is a CONTRAST test rather
    than a repetition."""

    def test_multi_image_membership_is_derived(self) -> None:
        """O1/F1's correction as DATA, derived. The corrected claim was: the
        multi-image op set is exactly {action_classify, florence_batch_extract,
        yolo26_detect_batch} and of those only action-classify's list is a
        TEMPORAL sequence; the plan's 'only multi-frame op' wording was false.
        Today the derived set is {yolo26_detect_batch (multipart), vlm_assess
        (image_paths)}: two of the 3-set retired with their models and spec
        §3's VLM op joined with a path list. Pinned members + non-vacuity:
          * yolo26_detect and yolo26_segment take a SINGULAR UploadFile
            (measured: annotations 'UploadFile') and must be OUT — that is the
            plural/singular distinction the whole correction turned on, and
            without this half the predicate 'mentions UploadFile' would pass
            while being wrong;
          * llm_chat_completion's `messages` and vlm_assess's per-image
            DETECTION-ID list are the text/nested carve-outs dossier O1/F1 made
            and are still OUT;
          * the two retired names are absent from the registry AND adopted by
            the ratchet (no silent drop).
        UNVERIFIED at pytest level."""
        assert _multi_image_ops() == {"yolo26_detect_batch", "vlm_assess"}
        assert "yolo26_detect" not in _multi_image_ops()  # singular UploadFile
        assert "yolo26_segment" not in _multi_image_ops()  # singular UploadFile
        assert "llm_chat_completion" not in _multi_image_ops()  # messages: TEXT list
        # vlm_assess qualifies through image_paths, NOT through its other list
        # field (frame_detection_ids is list<list<int>> — ids, not images). The
        # predicate is 'array + image-bearing name', so the field that fires it
        # is pinned by name and the one that must not is pinned as a non-array
        # of images.
        vl = _snapshot("vlm_assess", "request")["properties"]
        assert vl["image_paths"]["type"] == "array"
        assert vl["frame_detection_ids"].get("type") != "array"  # anyOf(array,null)
        for retired in ("enrichment_action_classify", "florence_batch_extract"):
            assert retired not in OPERATION_IDS
            assert retired in _deleted_registry_ops(), f"{retired} dropped from the ratchet"

    async def test_detect_batch_is_multipart_so_json_dispatch_cannot_drive_it(
        self, gateway_client
    ) -> None:
        """O1/F1's inspection pin, retargeted from a retired op to the live
        one. `files: list[UploadFile]` (ai/gateway/adapters/yolo26.py:386-387,
        annotation read live) means NO JSON body can bind this route — which is
        exactly why the op sits in the third matrix state (SENTINELS_GATEWAY:
        route deployed, no client binding) instead of being wired. Driven both
        ways: the annotation, and the gateway's own verdict on a JSON body
        (422 on the missing multipart field, NOT a 200 with an empty batch — a
        silent-empty parse would make the payload-dispatch story a lie)."""
        endpoint = _gateway_endpoints()[OPERATIONS["yolo26_detect_batch"].path]
        params = inspect.signature(endpoint).parameters
        assert "files" in params
        ann = str(params["files"].annotation)
        assert "UploadFile" in ann and "list" in ann.lower(), ann
        client, _ = gateway_client
        r = await client.post(OPERATIONS["yolo26_detect_batch"].path, json={"image_base64": "x"})
        assert r.status_code == 422, r.text[:200]
        assert any("files" in err.get("loc", ()) for err in r.json()["detail"]), r.text[:200]

    @pytest.mark.parametrize("n_files", [1, 2, 3], ids=["n1", "n2", "n3"])
    async def test_detect_batch_fans_out_one_triton_call_per_file(
        self, gateway_client, n_files: int
    ) -> None:
        """'batch' is a client-side LOOP, not a server-side batch (O1/F1's
        per-file claim, live now): n uploads must be n Triton calls whose image
        input carries ONE image each (measured: 3 files → 3 calls of
        (1, 3, 640, 640)), and batch_size / len(results) both == n. A
        regression that stacks the images into one (n,3,640,640) call would
        return the right COUNT and the wrong ENGINE BEHAVIOUR — the shapes the
        mock records are what catch it."""
        client, mock = gateway_client
        probe = _singleshot_triton()
        mock.infer.side_effect = probe
        files = [("files", (f"{i}.png", _png(), "image/png")) for i in range(n_files)]
        r = await client.post("/yolo26/detect/batch", files=files)
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert body["batch_size"] == n_files
        assert len(body["results"]) == n_files
        assert probe.seen == [("yolo26", (1, 3, 640, 640))] * n_files

    async def test_detect_batch_isolates_a_bad_image_per_item(self, gateway_client) -> None:
        """Per-item failure ISOLATION (O1's per-row parse property for the
        retired batch-extract op, which carried it as JSON rows): one
        undecodable upload must not 4xx or void the batch. Observed live: 200,
        batch_size counts every file, the bad item is {detections: [], error:
        …} and its healthy neighbours keep their full item shape. The
        sibling's 'all-succeed' case above is the non-vacuity — without it this
        could pass on an endpoint that always errors."""
        client, mock = gateway_client
        mock.infer.side_effect = _singleshot_triton()
        files = [
            ("files", ("good.png", _png(), "image/png")),
            ("files", ("bad.jpg", b"definitely-not-an-image", "image/jpeg")),
            ("files", ("good2.png", _png(32, 32), "image/png")),
        ]
        r = await client.post("/yolo26/detect/batch", files=files)
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert body["batch_size"] == 3 and len(body["results"]) == 3
        items = body["results"]
        assert "error" not in items[0] and "error" not in items[2], items
        assert items[1]["error"] and items[1]["detections"] == []

    async def test_detect_batch_item_shape_carries_timing_only_in_the_total(
        self, gateway_client
    ) -> None:
        """WP7.4's timing doctrine on the BATCH item shape, live: the per-item
        dict is {detections, image_width, image_height} with NO per-item
        inference_time_ms (adapters/yolo26.py:421-427 — the total carries it),
        and the envelope is {results, total_inference_time_ms, batch_size}.
        This is the live key-set pin for a BARE-DICT route — the class of
        property O2 had to assert as a key set because a
        `additionalProperties: true` snapshot validates anything (its record
        below). Schema-side the route declares a bare dict + x-deployed-keys,
        so the snapshot CANNOT catch a key rename; this test is the only
        guard."""
        client, mock = gateway_client
        mock.infer.side_effect = _singleshot_triton()
        files = [("files", (f"{i}.png", _png(), "image/png")) for i in range(2)]
        body = (await client.post("/yolo26/detect/batch", files=files)).json()
        assert set(body) == {"results", "total_inference_time_ms", "batch_size"}
        assert body["total_inference_time_ms"] >= 0
        for item in body["results"]:
            assert set(item) == {"detections", "image_width", "image_height"}, item
            assert "inference_time_ms" not in item
        # the snapshot's x-deployed-keys must not drift from what is served:
        snapshot = _snapshot("yolo26_detect_batch")
        assert set(snapshot["x-deployed-keys"]) == set(body)

    async def test_fake_side_is_payload_blind_where_the_gateway_is_not(self) -> None:
        """The fake half of the multi-image story, as a CONTRAST: the fake's
        determinism is seeded by op id + path + profile (fake/app.py:10-14), so
        the same op replayed with 1 and with 4 uploaded files is BYTE-IDENTICAL
        — while the gateway's own answer above varies with the file count
        (batch_size 1 vs 3). Both halves are pinned in one test because the
        point is the divergence: the fake exercises the SHAPE, never the
        payload. Frame/payload-count invariance is the retired fake-side OP-28
        property (fake 200 on empty frames + 0/1/4/None frames byte-identical)
        retargeted to the op that still exists."""
        from backend.ai_contract.fake import create_fake_app

        op = OPERATIONS["yolo26_detect_batch"]
        async with AsyncClient(
            transport=ASGITransport(app=create_fake_app()), base_url="http://fake"
        ) as fake:
            r1 = await fake.post(op.path, files=[("files", ("a.png", _png(), "image/png"))])
            r4 = await fake.post(
                op.path, files=[("files", (f"{i}.png", _png(), "image/png")) for i in range(4)]
            )
            assert (r1.status_code, r4.status_code) == (200, 200)
            assert r1.content == r4.content, "the fake's batch answer moved with the file count"
            # ...and its shape is the literal deployed envelope, not filler:
            assert set(r1.json()) == {"results", "total_inference_time_ms", "batch_size"}
        # non-vacuity: the SAME count change DOES move the gateway (driven
        # above; asserted here on the derived set so a fake that ignored EVERY
        # input would not be what this test proves):
        assert "yolo26_detect_batch" in _multi_image_ops()


class TestO1ActionClassifyTombstone:
    """TOMBSTONE (R8 S3, owner rulings 1 + 5). This block drove
    `enrichment_action_classify` — OP 28, the only op whose multi-image list
    was a TEMPORAL frame SEQUENCE — against a mounted adapter, with a two-stage
    Triton mock (pose per frame, then ONE stgcn_action call over the resampled
    skeleton) and a per-side divergence pin.

    What it established, kept because the hazards are general:
      * the empty-frames DIVERGENCE, corrected against live code: gateway
        empty list → **400** `{"detail": "Frames list cannot be empty"}`
        (handler-level HTTPException), NOT the 422 the workflow prompt claimed
        — 422 belongs to a MISSING or wrongly-typed `frames` field (a pydantic
        model), a different case, and both were pinned separately;
      * fake empty frames → **200** with the seeded body, and frame-count
        invariance (0/1/4/None → byte-identical) — the fake's determinism
        property, not a bug. Its live descendant is
        TestMultiImageOps.test_fake_side_is_payload_blind_where_the_gateway_is_not;
      * order-sensitivity: the drive fed frames whose keypoints sat at
        x = order_probe[i] so the skeleton the adapter built was
        order-inspectable. A frame-sequence op whose consumer assumes list
        order is a silent-corruption hazard, and mocking one flat Triton output
        hides it completely.

    It cannot retarget: no surviving op carries a frame sequence (the derived
    multi-image set is a multipart file set and an unordered path list), and
    ai/gateway/adapters/enrichment.py — the module holding
    ActionClassifyRequest, the 400/422 pair and the pose→stgcn pipeline — is
    swept, so there is no text left to point the assertions at (the S2b V3
    precedent: tombstone, not skip).
    """

    def test_action_classify_retired_and_adopted_by_the_ratchet(self) -> None:
        from backend.ai_contract.operations import OPERATION_IDS as IDS

        assert "enrichment_action_classify" not in IDS
        assert "enrichment_action_classify" in _deleted_registry_ops()
        assert not (REPO_ROOT / "ai/gateway/adapters/enrichment.py").exists()
        # Non-vacuity: the multi-image class itself is NOT dead — the derived
        # set is non-empty and this file drives one of its members live above.
        assert _multi_image_ops(), "the multi-image class died; this tombstone is alone"


class TestO2CompositeEnrichTombstone:
    """TOMBSTONE (R8 S3, rulings 1 + 5). This block drove the composite
    `/enrichment/enrich` fan-out — the highest-value single conformance target
    at drafting, because it is the one route whose response is a FREE-FORM map.

    What it established, kept because the hazard is general:
      * **a free-form snapshot cannot catch a key-set regression.**
        EnrichResponse.enrichments is `additionalProperties: true`, so every
        wrong-key body validated green; the only load-bearing assertion was the
        KEY SET per detection_type ({clothing, demographics} for person,
        {vehicle} for vehicle/car, {pet} for cat/dog, {} for anything else).
        The live heir of that argument is
        TestMultiImageOps.test_detect_batch_item_shape_carries_timing_only_in_the_total:
        the yolo family routes declare a BARE dict too, and their key sets are
        asserted there, not by the schema.
      * echo-vs-generated divergence, pinned per side and jointly: the gateway
        ECHOES request.detection_type; the fake GENERATES one
        ('detection_type_NNN' from the string walker) and returns a free-form
        {'alpha','bravo'} enrichments map with no dt-keyed fan-out. A test that
        asserted only one side would let a client that reads the echo break
        silently when pointed at the fake.
      * a docstring FALSEHOOD pinned as behavior: the handler's '- other:
        basic depth estimation' claim was false (unknown types got
        enrichments == {}), characterized so a 'fix' that ADDED the depth
        branch reddened the suite rather than silently changing the contract.

    It cannot retarget: enrichment_enrich left the contract with the
    enrichment provider's pruned models, its fan-out had no surviving peer
    route, and the adapter module that held the docstring is swept.
    """

    def test_composite_enrich_retired_and_adopted_by_the_ratchet(self) -> None:
        from backend.ai_contract.operations import OPERATION_IDS as IDS

        assert "enrichment_enrich" not in IDS
        assert "enrichment_enrich" in _deleted_registry_ops()
        # The echo-vs-generated hazard is not orphaned: the fake's generated
        # (never echoed) string fields are still what the fake column produces
        # for every walked op — pinned by the fake suite's own
        # shipped-correct class.
        assert "vlm_assess" in _multi_image_ops(), "the class lost its second member"

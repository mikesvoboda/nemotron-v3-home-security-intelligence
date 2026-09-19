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
  * O1 — OP 28 enrichment_action_classify, the only TEMPORAL frame-sequence
    op (the plan's dedicated OP-28 property block; the plan's "only
    multi-frame" wording is FALSE as literally spoken — florence_batch_extract
    and yolo26_detect_batch also carry multiple images — the correction is
    pinned, not propagated);
  * O2 — the composite /enrich (ai/gateway/adapters/enrichment.py:899), the
    highest-value single conformance target: which response keys the fan-out
    actually returns per detection_type, vs what the free-form snapshot
    claims, vs what the FakeProvider returns.

OP-28 DIVERGENCE RECORD (dossier cluster 4 F3/F4/F5; corrected against live
code — the workflow prompt's "gateway 422 on empty frames" is wrong):
  * gateway empty frames → **400** `{"detail": "Frames list cannot be
    empty"}` — handler-level HTTPException, ai/gateway/adapters/enrichment.py
    :749-750. 422 belongs to a MISSING or wrongly-typed `frames` field
    (pydantic ActionClassifyRequest :343-345), a different case — both pinned.
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
gateway/per_model/llamacpp callables for live ops: 26+28+2 of them are real
network paths; the suite drives the five adapter routers mounted with their
production prefixes ai/gateway/main.py:181-185 under per-module
`get_triton_client` patches — five DISTINCT targets (ai/gateway/adapters/
{yolo26,clip,florence,enrichment,enrichment_light}.get_triton_client), the
yolo26 template at ai/gateway/tests/test_adapters_yolo26.py:98-104 extended
to all five. Import cost verified live: ai.gateway adapters ~1.6s,
backend.ai_contract ~3.7s cold — inside the 5s pytest-timeout, pyproject
:495.)

No xfail / skip / importorskip anywhere: every divergence below is either a
per-provider green assertion or a pinned-divergence assertion.
"""

from __future__ import annotations

import base64
import inspect
import io
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import jsonschema
import numpy as np
import pytest
from backend.ai_contract.operations import OPERATIONS
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
    FastAPI,
    UploadFile,  # multipart undrivability pin for detect-batch
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

# ProviderId -> expected registered size (dossier O4/F9, verified live import:
# {'gateway': 31, 'gateway_light': 5, 'per_model_http': 36, 'llamacpp_llm': 2}
# + fake 38 once this suite registers it).
EXPECTED_SIZES = {
    ProviderId.GATEWAY: 31,
    ProviderId.GATEWAY_LIGHT: 5,
    ProviderId.PER_MODEL_HTTP: 36,
    ProviderId.LLAMACPP_LLM: 2,
    ProviderId.FAKE: 38,
}

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
}

# Sentinel (NOT-WIRED) literals — dossier O3/F8 + live import. per_model_http
# is 8, not the dossier-note's 6: llm_completion / llm_chat_completion are
# per_model_server=True with client_methods=[] (the bound LLM path belongs to
# the llamacpp provider, not per_model_http), so _bound_or_reject sentinels
# them too (backend/ai_contract/providers.py:77-85). Pinned from live output
# 2026-09-19; UNVERIFIED at pytest level.
SENTINELS_GATEWAY = {
    "enrich_lt_depth_estimate",
    "enrich_lt_pet_classify",
    "enrich_lt_pose_analyze",
    "florence_analyze_scene",
    "yolo26_detect_batch",
}
SENTINELS_LIGHT = {
    "enrich_lt_depth_estimate",
    "enrich_lt_pet_classify",
    "enrich_lt_pose_analyze",
}
SENTINELS_PER_MODEL = SENTINELS_GATEWAY | {
    "llm_completion",
    "llm_chat_completion",
    "model_unload",
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

# OP-28 block + O2 literals.
AC_OP = "enrichment_action_classify"
ENRICH_OP = "enrichment_enrich"
# dossier O1/F1 correction: multi-IMAGE ops are a 3-set; action-classify is
# the only TEMPORAL frame-sequence one. yolo26_detect_batch is MULTIPART
# (ai/gateway/adapters/yolo26.py:387 files: list[UploadFile]) — not
# JSON-drivable against a real gateway by design.
MULTI_IMAGE_OPS = {"enrichment_action_classify", "florence_batch_extract", "yolo26_detect_batch"}


def _snapshot(op_id: str, kind: str = "response") -> dict[str, Any]:
    return json.loads((SCHEMA_DIR / f"{op_id}.{kind}.json").read_text())


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


def _b64_image() -> str:
    """Small deterministic PNG, same helper as
    ai/gateway/tests/test_adapters_enrichment.py:33-38."""
    img = Image.new("RGB", (8, 8), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# Five DISTINCT patch targets (dossier Q2 — patching one symbol silently
# leaves four adapter modules on the real gRPC client). Exact strings verified
# live from the module-level from-imports: yolo26.py:28, enrichment.py:31,
# enrichment_light.py:30, florence.py:39, clip.py:40.
GATEWAY_PATCH_TARGETS = tuple(
    f"ai.gateway.adapters.{m}.get_triton_client"
    for m in ("yolo26", "clip", "florence", "enrichment", "enrichment_light")
)


# ---------------------------------------------------------------------------
# Gateway app factories.  INTEGRATION NOTE: hoist these two fixtures +
# GATEWAY_PATCH_TARGETS + _mock_triton into
# backend/tests/contracts/ai_providers/conftest.py when the per-cluster files
# merge into test_conformance.py (conftest does not exist yet — dossier Q6).
# ---------------------------------------------------------------------------

# Registry Operation.path ALREADY includes the mount prefix ('/yolo26/detect')
# — the routers must be included with the production prefixes from
# ai/gateway/main.py:181-185 (the yolo26 sibling template mounts WITHOUT a
# prefix; reusing its app shape verbatim would 404 every registry path).
GATEWAY_MOUNTS = (
    ("ai.gateway.adapters.yolo26", "router", "/yolo26"),
    ("ai.gateway.adapters.clip", "router", "/clip"),
    ("ai.gateway.adapters.florence", "router", "/florence"),
    ("ai.gateway.adapters.enrichment", "router", "/enrichment"),
    ("ai.gateway.adapters.enrichment_light", "router", "/enrich-lt"),
)


def _build_gateway_app(modules: tuple[str, ...] | None = None) -> FastAPI:
    """Mount the FIVE adapter routers (or a subset by adapter module name)
    with their production prefixes. Import of ai.gateway.* pulls CPU torch via
    clip.py:36 (~1.6s verified) — done lazily inside fixtures, not at module
    import, so collection stays cheap."""
    import importlib

    app = FastAPI(title="WP8.3 conformance gateway app")
    for mod, attr, prefix in GATEWAY_MOUNTS:
        if modules is None or mod.rsplit(".", 1)[1] in modules:
            app.include_router(getattr(importlib.import_module(mod), attr), prefix=prefix)
    return app


@pytest.fixture(scope="module")
def gateway_app() -> FastAPI:
    """All five adapters on one app, production prefixes (driving shape:
    'mount the FIVE adapter routers with their production prefixes')."""
    return _build_gateway_app()


@pytest.fixture(scope="module")
def light_app() -> FastAPI:
    """enrichment_light only — the gateway_light provider's real surface
    (its column is the /enrich-lt router, ai/gateway/main.py:185)."""
    return _build_gateway_app(modules=("enrichment_light",))


@pytest.fixture
async def gateway_client(gateway_app):
    """(client, mock_triton) with ALL FIVE get_triton_client names patched.
    Template: ai/gateway/tests/test_adapters_yolo26.py:98-104 extended to the
    five-target rule (plan WP8.3 'Mechanical detail')."""
    mock = _mock_triton()
    with (
        patch(GATEWAY_PATCH_TARGETS[0], return_value=mock),
        patch(GATEWAY_PATCH_TARGETS[1], return_value=mock),
        patch(GATEWAY_PATCH_TARGETS[2], return_value=mock),
        patch(GATEWAY_PATCH_TARGETS[3], return_value=mock),
        patch(GATEWAY_PATCH_TARGETS[4], return_value=mock),
    ):
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
        availability carries EXACTLY these 4 keys (verified live over all 38).
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
        assert len(OPERATIONS) == 38  # WP7.1 registry size

    @pytest.mark.parametrize(
        "pid",
        list(ProviderId),
        ids=[p.value for p in ProviderId],
    )
    def test_matrix_registered_set_matches_slot_or_required(self, pid: ProviderId) -> None:
        """Spine (a): set(rec.operations()) == slot column for the single-app
        providers; == the evidence-derived required SUBSET for llamacpp
        (union-slot rule, provider.py:196-203 + providers.py:94-106); fake's
        column is the SPEC (all 38) and the fake is registered by this suite
        itself. Sizes and deployed per EXPECTED_* tables above (sources:
        providers.py:135-157; live import fold). THE WORKFLOW-PROMPT DIVERGENCE:
        'llamacpp_llm: rec.deployed is False' is contradicted by live code —
        we pin True (providers.py:155) and record the prompt's claim as wrong.
        PREDICTED-GREEN all five params (sizes 31/5/36/2/38 observed live).
        Never CALLS a registered callable (gateway/per_model/llamacpp live ops
        would do real network). UNVERIFIED."""
        rec_ops = _provider_ops(pid)
        slot = PROVIDER_SLOT[pid]
        column = set(operations_for_slot(slot, OPERATIONS))
        if pid is ProviderId.LLAMACPP_LLM:
            assert set(rec_ops) == LLAMACPP_REQUIRED  # {llm_completion, llm_chat_completion}
            assert {"llm_completion", "llm_chat_completion"} == LLAMACPP_REQUIRED
            assert set(rec_ops) < column  # proper subset inside the union column
        else:
            assert set(rec_ops) == column  # source: providers.py:140-142; fake via
            # fake_provider_ops() == operations_for_slot('fake') (app.py:127). UNVERIFIED.
        assert len(rec_ops) == EXPECTED_SIZES[pid]  # 31/5/36/2/38. UNVERIFIED.
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
        """Pure-matrix absence for ALL providers (llamacpp's absence is the
        column minus its derived subset — 34). PREDICTED-GREEN all.
        UNVERIFIED."""
        slot = PROVIDER_SLOT[pid]
        column = set(operations_for_slot(slot, OPERATIONS))
        absent = ALL_OPS - column  # matrix-absent for this slot
        ops = set(_provider_ops(pid))
        # claiming a matrix-absent op is impossible for ANY provider (the
        # registration guard above is the import-time twin of this check):
        assert not (ops & absent), f"{pid.value} claims matrix-absent ops"
        if pid is ProviderId.LLAMACPP_LLM:
            assert ops == LLAMACPP_REQUIRED  # exact derived subset
            # the union-slot remainder is absent FOR THIS PROVIDER (34 ops):
            assert column - ops  # non-empty by construction. UNVERIFIED.
        else:
            assert ops == column  # single-app providers cover the column
        # fake is the SPEC column: zero absences at all.
        if pid is ProviderId.FAKE:
            assert not absent  # fake column == all 38. UNVERIFIED.

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
        """fake ABSENT 0 (dossier O3/F7): the spec column is all 38, and the
        fake app mounts one route per registry op (fake/app.py:88-89) — so
        the absence guard for fake is trivially empty. PREDICTED-GREEN
        fake-side; gateway rows are covered by their own params above.
        UNVERIFIED."""
        ops = _fake_callables()
        assert set(ops) == ALL_OPS  # 38 == 38. UNVERIFIED.
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
        == the literals above (5/3/8 — per_model's 8 includes the two LLM ops
        and model_unload; the dossier NOTE's 'plus model_unload' count of 6
        is stale vs live output; pinned from live import 2026-09-19).
        PREDICTED-GREEN. UNVERIFIED at pytest level."""
        ops = _provider_ops(pid)
        unbound = {o for o in ops if not OPERATIONS[o].client_methods}
        sentinels = {o for o, fn in ops.items() if "_not_wired" in fn.__qualname__}
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
        any network. PREDICTED-GREEN for all 16 (provider, op) params.
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
        closures to settings.nemotron_url (providers.py:109-131), which we
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
# (d) O1 / OP-28 — action-classify: the only TEMPORAL frame-sequence op
# ===========================================================================


class TestO1ActionClassifyMultiFrame:
    """Plan's OP-28 dedicated property block. Registry identity
    (operations.py:144-156), the multi-image uniqueness CORRECTION
    (dossier O1/F1: the plan's 'only multi-frame op' wording is false —
    florence_batch_extract items and yolo26_detect_batch multipart files also
    carry N images; action-classify is the only one whose list is a TEMPORAL
    sequence), and the empty-frames DIVERGENCE fake-vs-gateway, pinned per
    side (module docstring carries the record: gateway 400 / fake 200)."""

    def test_action_classify_registry_identity(self) -> None:
        """O1/F0. Source: backend/ai_contract/operations.py:144-156 (id,
        POST, /enrichment/action-classify, availability
        gateway=T/light=F/per_model=T/fake=T; client_methods
        ['EnrichmentClient.classify_action']). Registry data — same on every
        provider. PREDICTED-GREEN both. UNVERIFIED."""
        op = OPERATIONS[AC_OP]
        assert (op.method, op.path) == ("POST", "/enrichment/action-classify")
        assert op.availability == {
            "gateway": True,
            "enrichment_light_adapter": False,
            "per_model_server": True,
            "fake": True,
        }
        assert op.client_methods == ["EnrichmentClient.classify_action"]

    def test_action_classify_only_temporal_frame_sequence(self) -> None:
        """O1/F1 correction as DATA, not prose: the multi-image op set is
        exactly the 3-set; of those, only action-classify's request field is
        a frame sequence — gateway ActionClassifyRequest.frames: list[str]
        required + top_k: int = 5 (adapters/enrichment.py:343-345, field
        model verified live), florence_batch_extract carries items:
        list[BatchExtractItem] (adapters/florence.py:149-155 — verified live),
        and yolo26_detect_batch is MULTIPART UploadFile (adapters/yolo26.py
        :387 — inspect-pinned below; JSON payload dispatch cannot drive it,
        which is WHY it is fake-side/not-wired on the gateway). A naive 'one
        image per request' assertion would fail on batch-extract — we assert
        the corrected statement. PREDICTED-GREEN both. UNVERIFIED."""
        # membership pin (the registry carries no request-shape data, so the
        # uniqueness claim decomposes into: these 3 EXIST and carry list-
        # valued request fields — pinned via the request models below — and
        # single-image peers are single-image, pinned via their models):
        assert MULTI_IMAGE_OPS <= ALL_OPS  # registry membership. UNVERIFIED.
        # request-field proof of the CORRECTED claim (the 3-set is exactly
        # what carries >1 image; the field models below are the witnesses,
        # and e.g. clip_classify texts/labels are TEXT lists, not frames —
        # dossier O1/F1):
        from ai.gateway.adapters.enrichment import ActionClassifyRequest

        fields = ActionClassifyRequest.model_fields
        assert set(fields) == {"frames", "top_k"}  # :343-345. UNVERIFIED.
        assert fields["frames"].is_required()
        assert fields["top_k"].default == 5

        from ai.gateway.adapters.florence import BatchExtractRequest

        assert set(BatchExtractRequest.model_fields) == {"items"}  # :149-155. UNVERIFIED.

        from ai.gateway.adapters.yolo26 import detect_batch

        sig = inspect.signature(detect_batch)
        # multipart: the payload is files: list[UploadFile] = File(...) — not
        # a JSON body; the suite must not JSON-drive it (dossier O1/F1).
        ann = str(sig.parameters["files"].annotation)
        assert UploadFile.__name__ in ann  # source: yolo26.py:387 (files:
        # list[UploadFile] = File(...)) — a JSON payload can never bind it, so
        # payload-dispatch conformance for this op runs against the fake only.
        # UNVERIFIED.

    async def test_action_classify_fake_frame_count_invariance(self) -> None:
        """Fake side of the OP-28 divergence (dossier O3/F3): the fake parses
        the body only for model_name echo (fake/app.py:69-83), so N frames,
        1 frame, [] and payload=None are BYTE-IDENTICAL through the provider
        callable, and the raw HTTP bytes match too (create_fake_app driven
        directly — snapshot-walked body, generators.py entry point). This
        invariance IS the fake's determinism property, asserted — not a
        divergence to skip. PREDICTED-GREEN fake side (observed in probe:
        empty == 4-frame == None). UNVERIFIED."""
        ops = _fake_callables()
        b_empty = await ops[AC_OP]({"frames": []})
        b_one = await ops[AC_OP]({"frames": ["a"]})
        b_four = await ops[AC_OP]({"frames": ["a", "b", "c", "d"]})
        b_none = await ops[AC_OP]()
        assert b_empty == b_one == b_four == b_none  # source: fake/app.py:69. UNVERIFIED.

        from backend.ai_contract.fake.app import create_fake_app

        async with AsyncClient(
            transport=ASGITransport(app=create_fake_app()), base_url="http://fake"
        ) as fc:
            r0 = await fc.post("/enrichment/action-classify", json={"frames": []})
            r4 = await fc.post("/enrichment/action-classify", json={"frames": ["x"] * 4})
        assert r0.status_code == 200  # fake 200-seeds on empty frames (divergence vs
        # gateway's 400). PREDICTED-GREEN fake side. UNVERIFIED.
        assert r0.content == r4.content  # byte identity at the HTTP layer. UNVERIFIED.
        jsonschema.validate(r0.json(), _snapshot(AC_OP))  # snapshot-valid even
        # for the body-ignored empty request. PREDICTED-GREEN fake side. UNVERIFIED.

    async def test_action_classify_gateway_rejects_empty_frames_400(self, gateway_client) -> None:
        """Gateway side of the OP-28 divergence, pinned at its TRUE status:
        {'frames': []} → 400 'Frames list cannot be empty' — handler-level
        HTTPException, adapters/enrichment.py:749-750 (status + detail string
        observed live in the patched app). THE WORKFLOW PROMPT'S 'gateway 422'
        IS WRONG for this payload: 422 is pydantic's verdict for a MISSING or
        non-list `frames` FIELD (:343-345), pinned as its own case below.
        Native server diverges again (ai/enrichment/model.py:2898-2899, 400
        after decode, different message) — not drivable here, recorded only.
        PREDICTED-GREEN gateway-app side (this NEVER runs against the fake —
        per-provider expectation by construction; against the fake it would
        PREDICTED-RED 200-vs-400, which is exactly the divergence the module
        docstring records). UNVERIFIED."""
        client, _ = gateway_client
        r = await client.post("/enrichment/action-classify", json={"frames": []})
        assert r.status_code == 400  # :749-750, NOT 422. UNVERIFIED.
        assert r.json()["detail"] == "Frames list cannot be empty"  # UNVERIFIED.
        # distinct field-level case: frames absent entirely → 422 (pydantic
        # 'Field required'); wrong type → 422 'Input should be a valid list'.
        r_missing = await client.post("/enrichment/action-classify", json={})
        assert r_missing.status_code == 422  # :344 required field. UNVERIFIED.
        r_bad = await client.post("/enrichment/action-classify", json={"frames": 7})
        assert r_bad.status_code == 422  # UNVERIFIED.

    async def test_action_classify_gateway_driven_response_validates(self, gateway_client) -> None:
        """OP-28 driven gateway response conformance: 4-frame payload → 200,
        validates against the committed WP7.2 snapshot
        (schemas/enrichment_action_classify.response.json — required
        action/confidence/inference_time_ms), all_scores is dict[str, float]
        (dossier O1/F2 assertion), and the is_suspicious/risk_weight pair is
        derived from the ACTION NAME (SUSPICIOUS_ACTIONS keyword table,
        adapters/enrichment.py:605-631 — 'loitering' → True / 0.8; observed
        live with a shaped xclip mock). Mock shape follows the xclip Python
        backend contract the handler parses (:570-596: object-dtype arrays;
        all_scores is a JSON blob) — an unshaped AsyncMock AttributeError's
        inside the handler (observed), so the mock IS part of the property."""
        client, mock = gateway_client
        scores = json.dumps({"all_scores": {"loitering": 0.9, "walking": 0.1}}).encode()
        mock.infer.return_value = {
            "action": np.array([b"loitering"], dtype=object),
            "confidence": np.array([0.9]),
            "all_scores": np.array([scores], dtype=object),
        }
        frames = ["aaa", "bbb", "ccc", "ddd"]  # intersection payload ONLY:
        # gateway takes frames+top_k, the NATIVE server takes frames+labels
        # (model.py:2838-2843) — send just frames, the shared surface
        # (dossier O1/F2 divergence).
        r = await client.post("/enrichment/action-classify", json={"frames": frames})
        assert r.status_code == 200  # UNVERIFIED (observed in probe).
        body = r.json()
        jsonschema.validate(body, _snapshot(AC_OP))  # committed snapshot. UNVERIFIED.
        assert isinstance(body["all_scores"], dict) and all(
            isinstance(v, float) for v in body["all_scores"].values()
        )  # dossier O1/F2. UNVERIFIED.
        assert body["action"] == "loitering"
        assert (
            body["is_suspicious"] is True and body["risk_weight"] == 0.8
        )  # :605-631 pair. UNVERIFIED.

    async def test_action_classify_gateway_preserves_frame_order(self, gateway_client) -> None:
        """OP-28's real content: ORDER is the contract for a temporal
        sequence. The handler packs frames as a JSON array in request order
        (adapters/enrichment.py:556-560 json.dumps(frames_b64) → object-
        array input to xclip). Assert the mock triton received the EXACT
        ordered list. Gateway-only (the fake body-ignores — frame ORDER is
        unobservable there, dossier O3/F3; live-Triton order is WP8.4).
        PREDICTED-GREEN gateway-app side. UNVERIFIED."""
        client, mock = gateway_client
        scores = json.dumps({"all_scores": {"walking": 0.7}}).encode()
        mock.infer.return_value = {
            "action": np.array([b"walking"], dtype=object),
            "confidence": np.array([0.7]),
            "all_scores": np.array([scores], dtype=object),
        }
        sent = ["f1", "f2", "f3"]  # deliberately not sorted
        r = await client.post("/enrichment/action-classify", json={"frames": sent})
        assert r.status_code == 200  # UNVERIFIED.
        call = mock.infer.call_args
        frames_input = call.kwargs["inputs"]["frames"]
        payload = json.loads(
            bytes(frames_input.flat[0]).decode("utf-8")
        )  # :556-560 shape. UNVERIFIED.
        assert payload == sent  # temporal order preserved to the wire. UNVERIFIED.


# ===========================================================================
# (e) O2 — composite /enrich: aggregated shape vs claimed sub-schemas
# ===========================================================================

# EnrichmentResponse.enrichments is additionalProperties:true in the
# committed snapshot — sub-shapes are NOT schema-pinned, so the joint
# property must be KEY-SET driven (dossier O2/F4). EnrichRequest{image req,
# detection_type req, bbox|None, extra|None} + EnrichmentResponse{
# detection_type, enrichments, inference_time_ms} at
# ai/gateway/adapters/enrichment.py:357-367 (route :899, def :900 — the
# plan's ~:899 cite is EXACT, verified live).
ENRICH_SUBSHAPES = {
    "clothing": {
        "clothing_type",
        "color",
        "style",
        "confidence",
        "top_category",
        "description",
        "is_suspicious",
        "is_service_uniform",
        "inference_time_ms",
    },  # _infer_clothing placeholder/zero-shot return, :451-490 (placeholder
    # literal return :481-490, reached when the text-encoder seam returns None at :474)
    "demographics": {
        "age_range",
        "age_confidence",
        "gender",
        "gender_confidence",
        "inference_time_ms",
    },  # _infer_demographics literal return :541-546
    "vehicle": {
        "vehicle_type",
        "display_name",
        "confidence",
        "is_commercial",
        "all_scores",
        "inference_time_ms",
    },  # _infer_vehicle literal return :441-447
    "pet": {"pet_type", "confidence", "is_household_pet"},  # inline enrich() pet branch :957-961
}


def _patched_person_triton() -> Any:
    """Side-effect router for the person fan-out (clothing + age + gender —
    three triton calls under asyncio.gather, :915-918). clothing via the
    'embedding' output key (:466), demographics via 'output' (:514-523)."""
    age = np.zeros(8, dtype=np.float32)
    age[2] = 5.0

    def _se(model_name: str | None = None, inputs: Any = None, outputs: Any = None, **kw: Any):
        if model_name == "fashion_clip":
            return {"embedding": np.zeros((1, 768), dtype=np.float32)}
        if model_name == "demographics_age":
            return {"output": np.array([age])}
        return {"output": np.array([np.array([5.0, 1.0], dtype=np.float32)])}

    return _se


class TestO2CompositeEnrich:
    """O2/F4+F5: which response keys the composite FAN-OUT returns per
    detection_type vs what the free-form snapshot claims vs what the fake
    returns. The handler does NOT route action-classify, pose, or depth for
    the enrich path (:908-968) — and its docstring's 'other: basic depth
    estimation' (:907) is a recorded FALSEHOOD pinned as enrichments == {}."""

    @pytest.mark.parametrize(
        ("detection_type", "expected_keys", "case"),
        [
            ("person", {"clothing", "demographics"}, "person"),
            ("vehicle", {"vehicle"}, "vehicle"),
            ("car", {"vehicle"}, "vehicle"),
            ("cat", {"pet"}, "pet"),
            ("dog", {"pet"}, "pet"),
            ("chair", set(), "none"),  # docstring-falsehood pin
        ],
        ids=["person", "vehicle", "car", "cat", "dog", "chair-empty"],
    )
    async def test_composite_enrich_gateway_keyset_per_detection_type(
        self, gateway_client, detection_type: str, expected_keys: set[str], case: str
    ) -> None:
        """Gateway fan-out key-set == {clothing,demographics} / {vehicle} /
        {pet} / {} — observed live on every case in the patched app; the
        gateway ECHOES request.detection_type (:966, observed) — a fake
        assertion of this exact shape PREDICTED-REDs against the fake
        (generated dt + free-form {'alpha','bravo'} — dossier O2/F5), so it
        is written gateway-side only, fake pinned in its own test below.
        Sub-shape key-sets from ENRICH_SUBSHAPES (sources cited at the
        table). clothing-classify needs the zero-shot text-encoder seam
        patched (return_value=None → placeholder branch, :474 + :481-490) exactly
        like the sibling suite (test_adapters_enrichment.py:638-642 —
        unpatched it loads FashionSigLIP weights from the network mid-test).
        UNVERIFIED at pytest level."""
        client, mock = gateway_client
        if case == "vehicle":
            logits = np.zeros(11, dtype=np.float32)
            logits[4] = 5.0  # 'car' index in the adapter's class table :405-417
            mock.infer.return_value = {"output": np.array([logits])}
        elif case == "pet":
            mock.infer.return_value = {"output": np.array([np.array([5.0, 1.0], dtype=np.float32)])}
        elif case == "person":
            mock.infer.side_effect = _patched_person_triton()

        seams = ("ai.gateway.adapters.enrichment._ensure_clothing_text_embeddings",)
        with patch(seams[0], return_value=None):
            r = await client.post(
                "/enrichment/enrich", json={"image": _b64_image(), "detection_type": detection_type}
            )
        assert r.status_code == 200  # UNVERIFIED (observed live per case).
        body = r.json()
        jsonschema.validate(body, _snapshot(ENRICH_OP))  # free-form enrichments
        # validates trivially — the snapshot CANNOT catch this property (the
        # point of the key-set assertion). PREDICTED-GREEN. UNVERIFIED.
        assert body["detection_type"] == detection_type  # gateway echo :966.
        # FAKE DIVERGENCE: fk['detection_type'] != sent (generator string,
        # dossier O2/F5) — asserted on the fake side, not shared.
        assert set(body["enrichments"]) == expected_keys  # UNVERIFIED (observed).
        for key, sub in body["enrichments"].items():
            assert set(sub) == ENRICH_SUBSHAPES[key]  # UNVERIFIED (observed).

    async def test_composite_enrich_gateway_tolerates_partial_subop_failure(
        self, gateway_client
    ) -> None:
        """Dossier O2/F4's PARTIAL-FAILURE property: person fan-out runs
        asyncio.gather(..., return_exceptions=True) (:915-918) — a failed
        sub-op's key is simply ABSENT (:920-930). clothing raises
        TritonClientError, demographics succeeds → 200 with enrichments ==
        {'demographics'} only (observed live). This is a DEPLOYED-SEMANTICS
        pin: a provider that 500s on partial failure would match the naive
        'all-or-nothing' expectation and break downstream consumers. The
        FakeProvider trivially satisfies the KEY-SHAPE ({}-shaped free-form)
        but cannot exhibit fan-out at all — per-provider expectation, fake
        covered below. PREDICTED-GREEN gateway-app. UNVERIFIED."""
        client, mock = gateway_client

        def _se(model_name: str | None = None, **kw: Any):
            from ai.gateway.triton_client import TritonClientError

            if model_name == "fashion_clip":
                raise TritonClientError("clothing model down (conftest draft scenario)")
            if model_name == "demographics_age":
                age = np.zeros(8, dtype=np.float32)
                age[2] = 5.0
                return {"output": np.array([age])}
            return {"output": np.array([np.array([5.0, 1.0], dtype=np.float32)])}

        mock.infer.side_effect = _se
        with patch(
            "ai.gateway.adapters.enrichment._ensure_clothing_text_embeddings",
            return_value=None,
            autospec=True,
        ):
            r = await client.post(
                "/enrichment/enrich", json={"image": _b64_image(), "detection_type": "person"}
            )
        assert r.status_code == 200  # partial failure tolerated. UNVERIFIED.
        assert set(r.json()["enrichments"]) == {"demographics"}  # failed key absent. UNVERIFIED.

    async def test_composite_enrich_fake_free_form_and_no_echo(self) -> None:
        """Fake side of O2 (dossier O2/F5, observed live): /enrich through
        the fake is the generic snapshot-walk — enrichments == {'alpha',
        'bravo'} free-form (generators.py:348-353), detection_type ==
        generated 'detection_type_NNN' ≠ the sent 'person' (fake parses the
        body only for model_name, fake/app.py:69-83), person and vehicle
        payloads return IDENTICAL bytes (no dt-keyed fan-out exists on the
        fake), and everything is deterministic + snapshot-valid. PREDICTED-
        GREEN fake side; the naive joint assertions ('dt echoed', 'dt-keyed
        keys') PREDICTED-RED against the fake — which is the divergence the
        next test pins explicitly. UNVERIFIED at pytest level."""
        ops = _fake_callables()
        person = await ops[ENRICH_OP]({"image": "x", "detection_type": "person"})
        vehicle = await ops[ENRICH_OP]({"image": "x", "detection_type": "vehicle"})
        assert person["detection_type"] != "person"  # generator, not echo. UNVERIFIED.
        assert set(person["enrichments"]) == {"alpha", "bravo"}  # free-form map. UNVERIFIED.
        assert person == vehicle  # body-ignored: no dt fan-out on the fake. UNVERIFIED.
        again = await ops[ENRICH_OP]({"image": "x", "detection_type": "person"})
        assert person == again  # determinism. UNVERIFIED.
        jsonschema.validate(person, _snapshot(ENRICH_OP))  # additionalProperties:true
        # snapshot accepts the free-form map — the schema is the reason the
        # suite needs the gateway-side key-set test above. PREDICTED-GREEN. UNVERIFIED.

    async def test_composite_enrich_divergence_echo_vs_generated(self, gateway_client) -> None:
        """THE pinned joint divergence (dossier O2/F5 'assertion'): same
        payload through BOTH surfaces in one test — gateway echoes
        detection_type, fake generates it. A future 'fix' that makes the
        fake echo (or makes the gateway generate) reddens this and forces a
        RULING; it is NOT parked as a skip. Gateway vehicle branch (single
        triton call, shaped logits, observed live). PREDICTED-GREEN as
        written (both halves observed live). UNVERIFIED at pytest level."""
        client, mock = gateway_client
        logits = np.zeros(11, dtype=np.float32)
        logits[4] = 5.0
        mock.infer.return_value = {"output": np.array([logits])}
        payload = {"image": _b64_image(), "detection_type": "truck"}
        gw = (await client.post("/enrichment/enrich", json=payload)).json()
        fk = await _fake_callables()[ENRICH_OP](payload)
        assert gw["detection_type"] == "truck"  # echo (:966). UNVERIFIED.
        assert fk["detection_type"] != "truck"  # generated (app.py:69). UNVERIFIED.
        assert set(gw["enrichments"]) == {"vehicle"}  # fan-out … UNVERIFIED.
        assert set(fk["enrichments"]) == {"alpha", "bravo"}  # … vs free-form. UNVERIFIED.

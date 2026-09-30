"""WP8.3 conformance — cluster "numeric-invariants" (N1a-N6).

Drafted per docs/superpowers/plans/2026-09-19-swap-readiness-72h.md §WP8.3
("Numeric invariants" bullets) against the verified dossier
.wp25-feed/wp83-evidence/full-results.json → result.clusters[group ==
"numeric-invariants"] (findings N1a..N6) plus cluster "WP8.3 suite mechanics"
(driving shapes Q1-Q7). This module is a sibling of the eventual single
parametrized backend/tests/contracts/ai_providers/test_conformance.py; it
carries ONLY the numeric-invariant properties.

R8 S3 REWRITE (2026-09-29, owner rulings 1-5). The prune to three models
(GATEWAY_MODEL_SET = yolo26 / reid / threat) made gateway CLIP unbootable, so
CLIP's whole surface retired in S3 as a prune consequence: the five adapter
mounts became two, the five Triton patch targets became two, and the five ops
this cluster drove numerically (``clip_embed``, ``clip_classify``,
``clip_similarity``, ``clip_anomaly_score``, ``clip_batch_similarity``) became
one (``enrich_lt_person_reid``). Every property below is RETARGETED onto
surviving shipped surface or TOMBSTONED with its hazard stated in full —
never skipped, never silently deleted (the S2b grammar; the tier's own
precedents are TestO1ActionClassifyTombstone / TestO2CompositeEnrichTombstone
in test_conformance_ops.py). The "UNVERIFIED / predicted RED" status the draft
carried is gone: every assertion here is executed.

WHAT THE CLUSTER LOOKS AT NOW
  * the embedding numeric property (fixed dim + L2 unit norm + declared dim ==
    vector length) drives the one surviving embedding route, the light lane's
    ``/enrich-lt/person-reid``, on both sides of the matrix;
  * the classify/similarity/anomaly NUMERIC CONTRACT survives as shape
    arithmetic (a distribution, and the sigmoid head that is not one) while
    the CLIP routes that carried it are tombstones;
  * the range/which-layer-enforces-it finding reproduces on the surviving
    lane's confidence number, whose response model is just as bare as CLIP's
    was;
  * the dim-confusion hazard (N5) is graded against the surviving 512-d slot,
    where the RAISE side and the SILENT side are both live and now asserted as
    one pair on one seam, and the retired multi-slot claim's METHOD survives
    as a four-way agreement over the shipped artifacts that name the width;
  * the three source/schema characterizations (N1b fixture-corpus anti-pin,
    N4 risk-score layer disagreement, N6 summary maxLength) survive intact —
    diagnosed, not assumed: their subjects are LLM schema modules, one ORM
    model and one live test fixture, none of which the vision prune touches.

DIVERGENCE POLICY (plan §WP8.3 procedure + goal rule):
  * NO xfail, NO skip, NO importorskip anywhere in this file — ever.
  * Every divergence between providers is asserted as a per-provider green
    assertion or as a pinned-divergence assertion. The one red this file used
    to carry (N2a: the fake's ``clip_classify`` was snapshot-WALKED, so it
    answered ``{alpha, bravo}`` / ``top_label_544`` for requested labels
    ``[person, dog, car]``) retired with its op; its lesson — a distribution
    must key EXACTLY the labels it was asked for — now runs as the shipped
    arithmetic invariant in TestN2NumericContractShape.

DRIVING SHAPES (dossier mechanics Q1b/Q4/Q5):
  * fake    — create_fake_app() driven over httpx.ASGITransport; when the
              registry record is needed: register_provider(ProviderId.FAKE,
              fake_provider_ops(), OPERATIONS, deployed=True) IN-TEST — the
              fake is NOT registered at import (backend/ai_contract/
              providers.py module docstring).
  * gateway — the surviving adapter routers with their PRODUCTION prefixes
              (ai/gateway/main.py:272-273: /yolo26 and /enrich-lt) onto one
              FastAPI app, with BOTH module-level get_triton_client names
              patched (adapters/yolo26.py:28, adapters/enrichment_light.py:27
              — two DISTINCT from-import sites: patching one silently leaves
              the other on real gRPC, and patching the original in
              ai.gateway.triton_client hits neither). The target list is
              DERIVED from the mount table, and the mount table is checked
              against ai/gateway/main.py by AST.
  * gateway_light — the enrichment_light router ALONE at /enrich-lt. It
              survives for the reason the draft gave: the mounted routers ARE
              a provider's availability surface, so "this column lacks op X"
              is only assertable as a 404 on an app that lacks the router. On
              the merged app a /yolo26 path answers 422 (the route exists and
              wants a multipart file), which would grade pydantic, not
              availability. The VICTIMS are derived from the column delta
              (the yolo26 ops) instead of the retired ``/clip`` list.
  * per_model_http / llamacpp_llm / the VLM engines — MATRIX-GUARD ONLY:
              set(rec.operations()) vs the slot column (equality; subset for
              the evidence-derived sets) and rec.deployed. Never network —
              their registered callables are unbound client methods / live
              httpx closures (dossier Q1a/Q5). This suite NEVER INVOKES
              registered_providers()[...].operations() callables.

UNIT-NORM TOLERANCE: abs_tol=1e-5, NOT 1e-9, and the reason is now SHIPPED.
The light reid adapter normalizes behind a ``if norm > 1e-8`` guard at
ai/gateway/adapters/enrichment_light.py:205-207 — a below-threshold input
leaks the RAW (non-unit) vector, which is exactly what a 1e-9 budget would be
too tight to see and a 1e-3 budget too loose to see. The fake's override is
exact (unit_embedding 512, backend/ai_contract/fake/generators.py:222-223)
and the face loader's own normalizer REFUSES the zero vector outright
(backend/services/face_recognizer_loader.py:249-252): three providers, three
answers to "what is a zero vector", one tolerance.
"""

from __future__ import annotations

import ast
import base64
import contextlib
import io
import json
import math
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from backend.ai_contract.operations import OPERATION_IDS, OPERATIONS
from backend.ai_contract.provider import (
    ProviderId,
    operations_for_slot,
    register_provider,
    registered_providers,
)
from backend.api.schemas.llm import LLMRiskResponse as RivalRiskResponse
from backend.api.schemas.llm_response import (
    RISK_ANALYSIS_JSON_SCHEMA,
)
from backend.api.schemas.llm_response import (
    LLMRiskResponse as StrictRiskResponse,
)
from backend.core.exceptions import InvalidEmbeddingError
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_DIR = REPO_ROOT / "backend" / "ai_contract" / "schemas"

# ---------------------------------------------------------------------------
# op subsets of the registry. The driven set is DERIVED, not remembered: a
# numeric-response op joins by having a committed snapshot with a numeric
# ``embedding`` array (WP4.2 — a hand-numbered op table is the rot this tier
# already removed elsewhere; the draft's NUMERIC_OPS was exactly such a table).
# ---------------------------------------------------------------------------


def _snapshot(op_id: str, kind: str = "response") -> dict[str, Any]:
    return json.loads((SCHEMA_DIR / f"{op_id}.{kind}.json").read_text(encoding="utf-8"))


def _embedding_ops() -> frozenset[str]:
    """Registry ops whose COMMITTED response snapshot carries a numeric
    embedding vector. Today exactly one; a future embedding op joins without
    an edit here."""
    out: set[str] = set()
    for op_id in OPERATION_IDS:
        if (SCHEMA_DIR / f"{op_id}.response.json").exists():
            emb = (_snapshot(op_id).get("properties") or {}).get("embedding") or {}
            if emb.get("type") == "array" and emb.get("items", {}).get("type") == "number":
                out.add(op_id)
    return frozenset(out)


EMBEDDING_OPS = _embedding_ops()
REID_OP = "enrich_lt_person_reid"
THREAT_OP = "enrich_lt_threat_detect"

# ops this cluster grades numerically for the matrix guards (derived, above).
NUMERIC_OPS = tuple(sorted(EMBEDDING_OPS))

# Production mounts, mirrored from ai/gateway/main.py:272-273 — and pinned
# against that file by AST in
# TestMatrixNumericSurface.test_matrix_mount_table_is_derived_from_main, so
# the mirror cannot rot. GATEWAY_PATCH_TARGETS folds off this table: adding a
# third adapter forces a patch target with it (dossier Q2's "one patch != all
# adapters" hazard survives the shrink from five to two — the rule shrank
# because the SURFACE did, not because a target was dropped on purpose).
GATEWAY_MOUNTS: tuple[tuple[str, str], ...] = (
    ("ai.gateway.adapters.yolo26", "/yolo26"),
    ("ai.gateway.adapters.enrichment_light", "/enrich-lt"),
)

GATEWAY_PATCH_TARGETS: tuple[str, ...] = tuple(
    f"{module}.get_triton_client" for module, _prefix in GATEWAY_MOUNTS
)

LIGHT_TARGETS: tuple[str, ...] = tuple(
    target for target in GATEWAY_PATCH_TARGETS if "enrichment_light" in target
)
assert len(LIGHT_TARGETS) == 1, "the light lane must have exactly one patch target"

# provider id -> matrix slot (backend/ai_contract/provider.py PROVIDER_SLOT,
# dossier Q7; the three subset providers and PER_MODEL_HTTP share the union
# slot 'per_model_server' — the WP8.1 union-slot rule)
SLOT_OF = {
    "gateway": "gateway",
    "gateway_light": "enrichment_light_adapter",
    "per_model_http": "per_model_server",
    "llamacpp_llm": "per_model_server",
    # 1.1 spec §3: the VLM engines share the union column too, registering
    # required={"vlm_assess"} (mirrors test_conformance_ops SUBSET_REQUIRED).
    "openai_vlm": "per_model_server",
    "rtvi_vlm": "per_model_server",
    # discovery fix: the loop below reaches the fake too (it joins the
    # registry in-test); its slot column is the ops it registers against.
    "fake": "fake",
}

# union-slot SUBSET providers -> their required set (the declared map is the
# subset, NOT the column — llamacpp's evidence pair; the 1.1 VLM engines'
# single VLM op).
SUBSET_REQUIRED = {
    "llamacpp_llm": {"llm_completion", "llm_chat_completion"},
    "openai_vlm": {"vlm_assess"},
    "rtvi_vlm": {"vlm_assess"},
}


# ---------------------------------------------------------------------------
# Shipped literals this cluster's fixtures are built FROM (AST, never
# transcribed) — defined first because the canned-shape defaults below read
# them at def time.
# ---------------------------------------------------------------------------


def _shipped_threat_table() -> list[str]:
    """The light adapter's threat vocabulary, read from shipped source — the
    tensor channel count derived from it can then never drift away from the
    names it indexes (WP4.2: a hand-numbered channel count is the rot)."""
    src = (REPO_ROOT / "ai" / "gateway" / "adapters" / "enrichment_light.py").read_text(
        encoding="utf-8"
    )
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "THREAT_CLASSES":
                return list(ast.literal_eval(node.value))
    raise AssertionError("THREAT_CLASSES no longer shipped in the light adapter")


def _shipped_reid_dim() -> int:
    """``OSNET_EMBEDDING_DIM`` read out of backend/services/osnet_loader.py by
    AST — the shipped width of the one embedding space. AST rather than import
    because that module costs ~2.3s to import and this tier's budget is
    per-test; the width's registry-side twin is pinned by
    test_conformance_dbvocabulary.py's embedding-dim registry test."""
    src = (REPO_ROOT / "backend" / "services" / "osnet_loader.py").read_text(encoding="utf-8")
    for node in ast.parse(src).body:
        targets = node.targets if isinstance(node, ast.Assign) else []
        for target in targets:
            if isinstance(target, ast.Name) and target.id == "OSNET_EMBEDDING_DIM":
                return int(ast.literal_eval(node.value))
    raise AssertionError("OSNET_EMBEDDING_DIM no longer a module-level literal")


# Derived fixture shapes: nothing below hand-pins a dimensionality or a class
# count — both follow the shipped weights.
_THREAT_CLASS_COUNT = len(_shipped_threat_table())
_CANNED_REID_DIM = _shipped_reid_dim()


# ---------------------------------------------------------------------------
# canned vectors / payloads — deterministic and MODULE-LEVEL so the exact
# value behind every assertion below is greppable, not fixture-order
# dependent.
# ---------------------------------------------------------------------------


def _canned_reid_embedding(dim: int = _CANNED_REID_DIM) -> np.ndarray:
    """Canned OSNet-shaped Triton output ``[1, dim]`` with norm
    ~2.5*sqrt(dim), i.e. deliberately NOT unit. The guarded inline
    normalization at ai/gateway/adapters/enrichment_light.py:205-207 is
    therefore the thing producing the unit vector N1a asserts — an adapter
    that stopped normalizing would leak this vector verbatim and trip the
    1e-5 tolerance."""
    rng = np.random.RandomState(7)
    return (rng.randn(1, dim) * 2.5).astype(np.float32)


# (class id, class score) rows for the canned threat tensor. Three classes,
# three different scores, all above the adapter's 0.25 threshold: enough to
# grade the emitted numbers and the envelope max, and a `rifle` row on
# purpose — rifle is legal in the light adapter's table and ILLEGAL in the DB
# CHECK the same word flows toward (test_conformance_dbvocabulary.py pins that
# seam; this file's job is only the numeric shape).
_THREAT_ROWS: tuple[tuple[int, float], ...] = ((0, 0.91), (1, 0.62), (2, 0.31))


def _canned_threat_output(rows: tuple[tuple[int, float], ...] = _THREAT_ROWS) -> np.ndarray:
    """Threat tensor in the orientation the light adapter normalizes at
    adapters/enrichment_light.py:87-88: ``preds.shape[0] < preds.shape[1]``
    triggers a transpose, so the shipped post-processor is fed
    ``[1, 4 + n_classes, n_candidates]`` here — channels x candidates, the
    same layout its docstring's ``(1, 8, 8400)`` describes, where the 4 is the
    box-channel half of that 8. Each candidate is
    ``[cx, cy, w, h, *class_scores]``, so ``np.argmax(class_scores, axis=1)``
    — the INDEX that becomes the emitted class name at :107-108 — is exactly
    what the row asks for. Filler sub-threshold rows keep the candidate count
    off a round power of two so a shape assumption cannot pass by accident."""
    n = len(rows) + 13
    out = np.zeros((1, 4 + _THREAT_CLASS_COUNT, n), dtype=np.float32)
    for i, (cls_id, conf) in enumerate(rows):
        assert cls_id < _THREAT_CLASS_COUNT, f"class id {cls_id} is off the shipped table"
        out[0, 0:4, i] = (320.0, 240.0, 60.0, 120.0)
        out[0, 4 + cls_id, i] = conf
    return out


def _canned_infer(
    inputs: dict[str, Any],
    model_name: str = "",
    reid_dim: int = _CANNED_REID_DIM,
    **kw: Any,
) -> dict[str, Any]:
    """AsyncMock side_effect dispatching by Triton model name. The shipped
    GATEWAY_MODEL_SET is exactly three residents (owner ruling 5's prune):
    yolo26, reid and threat — this answers all three at their real output
    keys. An unknown model name is a loud error, never a silently-shared
    default vector (the same silent-drift class the N5 dim guard refuses).
    ``reid_dim`` is the one knob the N5 pair needs: the shipped adapter never
    counts the vector it forwards."""
    if model_name == "reid":
        return {"embedding": _canned_reid_embedding(reid_dim)}
    if model_name == "threat":
        return {"output0": _canned_threat_output()}
    if model_name == "yolo26":
        return {"output0": np.zeros((1, 300, 6), dtype=np.float32)}
    raise AssertionError(f"unpinned gateway Triton model name {model_name!r}")


def _b64_png(width: int = 224, height: int = 224) -> str:
    from PIL import Image

    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# built once at import (~ms PIL; the gateway adapters decode it —
# ai/gateway/utils.py decode_base64_image (:17) expects uint8 RGB (H,W,3))
_B64_IMAGE = _b64_png()


# Gateway request payloads. The light adapter's request model is BBoxRequest
# (ai/gateway/adapters/enrichment_light.py:40-52): field ``image`` with alias
# ``image_base64``, extras ignored. The yolo26 routes take multipart uploads,
# not JSON, so they are driven where their own cluster drives them; this
# cluster's JSON surface is the light lane.
def _gateway_payload(op_id: str) -> dict[str, Any]:
    if op_id in (REID_OP, THREAT_OP):
        return {"image": _B64_IMAGE}
    raise AssertionError(f"no gateway payload for {op_id}")


# Fake payloads. The fake parses bodies ONLY for echo fields
# (backend/ai_contract/fake/app.py:71-80) — these documents exist so a future
# echo-driven fake still receives contract-shaped requests.
def _fake_payload(op_id: str) -> dict[str, Any]:
    if op_id in (REID_OP, THREAT_OP):
        return {"image_base64": "ZmFrZS1pbWFnZQ=="}
    raise AssertionError(f"no fake payload for {op_id}")


async def _drive(provider_id: str, client: AsyncClient, op_id: str) -> dict[str, Any]:
    """THE single request path for every app-driven provider (the plan's
    'same assertions, every provider' reduced to one helper)."""
    op = OPERATIONS[op_id]
    payload = _fake_payload(op_id) if provider_id == "fake" else _gateway_payload(op_id)
    r = await client.request(op.method, op.path, json=payload)
    assert r.status_code == 200, f"{provider_id}/{op_id}: {r.status_code} {r.text[:200]}" + (
        ""
        if provider_id == "fake"
        else " — check the get_triton_client patch targets derived from GATEWAY_MOUNTS (dossier Q2)"
    )
    return r.json()


# ---------------------------------------------------------------------------
# fixtures (dossier Q1b template + Q4; module-scoped apps, per-test fresh
# AsyncClient — mirrors test_fake_provider.py:101-112, pytest-randomly safe)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fake_app() -> FastAPI:
    """The fake IS an app (dossier Q4; backend/ai_contract/fake/app.py:57-88,
    one route per registry op)."""
    from backend.ai_contract.fake import create_fake_app

    return create_fake_app()


def _build_gateway_app(modules: tuple[str, ...] | None = None) -> FastAPI:
    """Mount the adapter routers (or a subset by adapter module name) with
    their production prefixes. Imports stay inside the fixture/helper so
    collection stays cheap; both surviving adapters import in ~0.35s (the
    module that pulled torch was CLIP's, and it is gone)."""
    import importlib

    app = FastAPI(title="WP8.3 numeric conformance gateway app")
    for module, prefix in GATEWAY_MOUNTS:
        if modules is None or module.rsplit(".", 1)[1] in modules:
            app.include_router(importlib.import_module(module).router, prefix=prefix)
    return app


@pytest.fixture(scope="module")
def gateway_app() -> FastAPI:
    """Every surviving adapter, production prefixes, one app, so
    Operation.path values (prefix already included — dossier Q7) route."""
    return _build_gateway_app()


@pytest.fixture(scope="module")
def gateway_light_app() -> FastAPI:
    """enrichment_light ALONE at /enrich-lt — gateway_light's real surface,
    and the only app on which its column's ABSENCES are assertable as 404s."""
    return _build_gateway_app(modules=("enrichment_light",))


def _mock_triton(reid_dim: int = _CANNED_REID_DIM) -> AsyncMock:
    """AsyncMock with .infer/.is_model_ready/.get_model_metadata (template:
    ai/gateway/tests/test_adapters_yolo26.py:76-87), dispatching canned
    per-model outputs so the three residents' shapes stay distinct."""
    mock = AsyncMock()
    mock.infer = AsyncMock(
        side_effect=lambda inputs=None, model_name="", **kw: _canned_infer(
            inputs or {}, model_name=model_name, reid_dim=reid_dim, **kw
        )
    )
    mock.is_model_ready = AsyncMock(return_value=True)
    mock.get_model_metadata = AsyncMock(return_value={})
    return mock


@contextlib.asynccontextmanager
async def _patched_http(
    app: FastAPI,
    patch_targets: tuple[str, ...],
    mock_triton: AsyncMock | None = None,
) -> AsyncIterator[AsyncClient]:
    mock_triton = mock_triton if mock_triton is not None else _mock_triton()
    async with contextlib.AsyncExitStack() as tx:
        # ALL named targets patched — one missed module = a silent real gRPC
        # connect attempt (dossier Q2 divergence).
        for target in patch_targets:
            tx.enter_context(patch(target, return_value=mock_triton))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            yield client


@pytest.fixture
async def provider_client(request: pytest.FixtureRequest):
    """Indirect-parametrized (provider_id, client) pair — THE parametrized
    driving shape for the app-driven providers, one entry point so every
    property test below is literally the same code for both. getfixturevalue
    touches ONLY the sync module-scoped app fixtures (no async-fixture
    loop-scope hazard, pytest-asyncio>=0.23 / asyncio_mode=auto)."""
    provider_id: str = request.param
    if provider_id == "fake":
        app = request.getfixturevalue("fake_app")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://fake") as client:
            yield provider_id, client
    elif provider_id == "gateway":
        app = request.getfixturevalue("gateway_app")
        async with _patched_http(app, GATEWAY_PATCH_TARGETS) as client:
            yield provider_id, client
    else:  # pragma: no cover - table guard
        raise AssertionError(f"provider_client: unhandled id {provider_id!r}")


# every app-driven property test parametrizes over exactly this
PROVIDER_PARAMS = ["fake", "gateway"]


def _retired_registry_ops() -> frozenset[str]:
    """The WP7.3 deleted-op ratchet, read out of the sibling suite's literal by
    AST (test_ai_contract_registry.py owns it; importing a test module to reach
    a constant is the cross-test coupling this file's imports avoid, and a
    hand-copy would drift). A missing literal raises rather than returns
    empty: "adopted by the ratchet" has to be able to fail loudly."""
    src = (
        REPO_ROOT / "backend/tests/contracts/ai_providers/test_ai_contract_registry.py"
    ).read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
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


# ---------------------------------------------------------------------------
# N1a — the surviving embedding surface: fixed dim AND L2 unit norm, plus the
# adapter's own "declared dim == vector length" construction
# ---------------------------------------------------------------------------


class TestN1aEmbeddingsUnitNorm:
    """N1a, RETARGETED (R8 S3). It used to drive two embedding ops — CLIP's
    768-d ``/clip/embed`` and the light lane's 512-d reid — and to pin that
    BOTH normalized, in three different layers: the legacy CLIP server's
    epsilon-divided normalize (ai/clip/model.py:801-804, epsilon 1e-8), the
    gateway's epsilon-FREE ``l2_normalize`` (ai/gateway/utils.py:172-184,
    RAW passthrough when norm < 1e-12 at :182-183 — that helper is now
    uncalled, its only caller being the swept clip adapter), and the light
    adapter's inline guarded normalize.

    The CLIP half is retired (ruling 5); the property is not. ``EMBEDDING_OPS``
    is DERIVED from the committed response snapshots, so the cluster grades
    whatever embedding surface ships, and today that is
    ``/enrich-lt/person-reid``: 512-d, L2-normalized at
    adapters/enrichment_light.py:202-207, with
    ``embedding_dimension=len(embedding)`` at :213. The fake-side half of this
    same 768→512 retarget is already pinned by
    test_fake_provider.py::test_unit_norm_embedding_at_the_surviving_home —
    cited, not repeated."""

    @pytest.mark.parametrize("provider_client", PROVIDER_PARAMS, indirect=True)
    async def test_N1a_embeddings_are_fixed_dim_and_unit_norm(self, provider_client) -> None:
        provider_id, client = provider_client
        assert EMBEDDING_OPS, (
            "no registry op declares a numeric embedding vector — this "
            "cluster has lost its subject; the derived set, not a remembered "
            "op list, is the guard"
        )
        for op_id in sorted(EMBEDDING_OPS):
            body = await _drive(provider_id, client, op_id)
            emb = body["embedding"]
            # length is the schema-visible half ...
            assert len(emb) == body["embedding_dimension"], (
                f"{provider_id}/{op_id}: len={len(emb)} != declared {body['embedding_dimension']}"
            )
            # ...unit L2 norm is the half NO committed response schema
            # declares (schemas/enrich_lt_person_reid.response.json items are
            # bare {"type": "number"}) — precisely what a provider swap breaks
            # silently, and what none of the repo's fixed-dim test literals
            # ever checked (see TestN1b).
            norm = math.sqrt(sum(x * x for x in emb))
            assert abs(norm - 1.0) <= 1e-5, (
                f"{provider_id}/{op_id}: L2 norm {norm!r} is not unit "
                "(tol 1e-5, NOT 1e-9 — the adapter's normalize is guarded by "
                "`norm > 1e-8` at adapters/enrichment_light.py:206, so a "
                "below-threshold input leaks the RAW vector; 1e-9 would also "
                "be tighter than the float32 arithmetic here is accurate to)"
            )

    @pytest.mark.parametrize("provider_client", PROVIDER_PARAMS, indirect=True)
    async def test_N1a_person_reid_declared_dim_matches_vector(self, provider_client) -> None:
        """Two DIFFERENT constructions of one property. The gateway's is
        ``embedding_dimension=len(embedding)``
        (adapters/enrichment_light.py:213) — the self-report equals the vector
        BY CONSTRUCTION, and that construction is what a swap can break (an
        osnet-padded provider could report the pre-pad dim). The fake's is two
        independent override entries — ('unit_embedding', 512) generating the
        vector and ('const', 512) declaring the dim
        (backend/ai_contract/fake/generators.py:222-223) — so a re-dim of one
        without the other reddens here."""
        provider_id, client = provider_client
        body = await _drive(provider_id, client, REID_OP)
        assert body["embedding_dimension"] == len(body["embedding"]), (
            f"{provider_id}: declared dim {body['embedding_dimension']} != "
            f"vector len {len(body['embedding'])} — the reid op is the only "
            "surviving embedding slot, so a mismatch here is the whole "
            "dim-confusion matrix collapsing into one unverified number"
        )

    def test_N1a_the_declared_dimension_is_still_derived_by_ast(self) -> None:
        """Source-side half, read by AST (live forms only): the response's
        ``embedding_dimension`` keyword is built from ``len()`` of the vector
        it describes, not from a constant. ``ReIDResponse`` declares the field
        as a bare ``int``, so nothing schema-side refuses a wrong declaration —
        this pin is what notices the by-construction equality turning into a
        remembered number (the drift N1a's assertion cannot see from the wire:
        see TestN5DimConfusion's wrong-dim pair)."""
        src = (REPO_ROOT / "ai" / "gateway" / "adapters" / "enrichment_light.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(src)
        reported: list[str] = []
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            if node.func.id != "ReIDResponse":
                continue
            for kw in node.keywords:
                if kw.arg == "embedding_dimension":
                    reported.append(ast.unparse(kw.value))
        assert reported == ["len(embedding)"], (
            f"ReIDResponse(embedding_dimension=...) reads {reported} — the "
            "declaration stopped being derived from its own vector "
            "(adapters/enrichment_light.py:213), which is the exact drift the "
            "wire-visible equality cannot detect"
        )


# ---------------------------------------------------------------------------
# N1b — the repo's fixed-dim test literals are NON-unit: this suite is the
# FIRST unit-norm assertion anywhere (anti-pin; property about the TEST
# CORPUS, not a provider — dossier providers: matrix-only)
# ---------------------------------------------------------------------------


class TestN1bLegacyLiteralsAreNotUnitNorm:
    """N1b source (dossier N1b, cites verified): backend/tests/integration/
    test_enrichment_pipeline.py:384 (dossier cite)
        test_embedding = [0.1] * 768  # Normalized CLIP embedding
    true L2 norm 0.1*sqrt(768) = 2.771. Spot sites at dossier time:
    test_vision_extraction_pipeline.py:877,:922; test_scene_baseline.py:181;
    test_enrichment_models.py:502 ([0.1]*512). PLAN CITE CORRECTION (dossier):
    the '87 literals' count does NOT reproduce — the actual census is 145
    lines matching `[0.1] *` and 125 lines mentioning 768 under
    backend/tests — but the CORE claim is true: zero of them assert unit norm
    (every np.linalg.norm hit normalizes a fixture before use, e.g.
    test_osnet_loader.py:71). This suite's N1a assertions are therefore the
    FIRST, and the fake's exact-unit outputs diverge from every legacy fixture
    by design (the dossier's mock-vs-real numeric mismatch).

    RE-ARMED 2026-09-27 by the re-ID full swap (ledger item 20): the canonical
    fixture literal became the B5 producer tuple
    ``([0.1] * 512, "osnet-test@weights@abc123")`` one line down at :385 —
    this is precisely the anti-pin's own escape hatch ("if someone fixed the
    literal, rewrite against the NEW canonical literal"). The property is
    unchanged: 0.1*sqrt(512) = 2.263 != 1, so N1a's unit-norm provider still
    contradicts the fixture corpus.

    RE-ARMED AGAIN 2026-09-29 by R8 S2: backend/tests/integration/
    test_enrichment_pipeline.py was deleted with the enrichment tier, and the
    canonical B5 fixture pair moved to its surviving home —
    backend/tests/unit/api/test_household.py:738-742 (mock_embedding =
    [0.1] * 512 feeding the (vector, "osnet-test@weights@abc123") AsyncMock
    return — the same B5 producer tuple, spelled across the mock's
    return_value instead of one line). Same escape hatch as always: fix the
    literal and this reddens by name.

    R8 S3 DIAGNOSIS: the property is arithmetic plus a read of a LIVE test
    file, so neither the CLIP prune nor the adapter sweep touches it — no
    retarget needed. The dossier's dead-literal prose was corrected out of the
    docstring (prose may name the dead; assertions may not read dead forms)."""

    # no provider (characterization). fake n/a, gateway n/a.
    def test_N1b_canonical_literal_norm_is_2_26_not_1(self) -> None:
        # The swap's canonical person-vector fixture literal (OSNet 512-dim).
        v = [0.1] * 512
        norm = math.sqrt(sum(x * x for x in v))
        assert abs(norm - 1.0) > 1.0, (
            f"[0.1]*512 norm={norm!r}: if this ever reads ~1, someone fixed "
            "the literal — then N1a's unit-norm provider property stops "
            "contradicting the fixture corpus and this anti-pin must be "
            "rewritten against the NEW canonical literal."
        )
        # cite-pinned drift guard: the canonical embedding fixture pair must
        # still sit where R8 S2 left it (line churn = the census claim needs
        # re-running against the new corpus).
        lines = (
            (REPO_ROOT / "backend/tests/unit/api/test_household.py")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        assert "[0.1] * 512" in lines[737], f"test_household.py:738 drifted: {lines[737]!r}"
        assert "osnet-test@weights@abc123" in lines[741], (
            f"test_household.py:742 drifted: {lines[741]!r}"
        )


# ---------------------------------------------------------------------------
# N2 — the classify/similarity NUMERIC CONTRACT, as shape arithmetic
# (retarget) and as tombstones (the CLIP routes that carried it)
# ---------------------------------------------------------------------------


def _softmax(logits: list[float]) -> list[float]:
    """The shipped softmax spelling this cluster pinned: ``exp(s - s.max())``
    over ``sum(...) + 1e-8``. The max-subtraction is what makes it
    overflow-safe and the denominator epsilon is why a softmax sums to
    1 - ~1e-8 and NEVER exactly 1.0 — which is why the drafted N2a refused
    ``== 1.0`` (dossier N2b)."""
    top = max(logits)
    exps = [math.exp(x - top) for x in logits]
    total = sum(exps) + 1e-8
    return [e / total for e in exps]


class TestN2NumericContractShape:
    """N2a/N2b RETARGETED onto the shape, not the dead routes.

    What the classify bullets established, kept because the shape is general:
    (1) a classify answer has ONE score per requested label, keyed by the
    REQUESTED labels, and its top label is the argmax — the fake used to
    answer ``top_label_544`` for labels ``[person, dog, car]``, the divergence
    that made N2a land red and then forced a label-seeded softmax into the
    shipped generator; (2) a softmax sums to 1 within the producer's rounding
    budget and never exactly; (3) N2b's swap lesson — a SIGMOID-headed
    provider returns independent per-label probabilities that do NOT sum to 1
    while staying fully schema-valid, because the response model was bare
    pydantic: the schema is silent, only the number catches drift.

    None of that requires a CLIP route to be assertable, and the fake's
    classify op is gone, so there is nothing left to be red against. The
    shipped softmax went with its adapter, so the invariant now runs as the
    arithmetic pin those two route-level assertions were shorthand for, with
    the sigmoid counterexample asserted as DATA beside it."""

    def test_N2_softmax_over_requested_labels_is_a_distribution(self) -> None:
        labels = ["person", "dog", "car"]
        scores = _softmax([2.0, 0.5, -1.0])
        assert len(scores) == len(labels), (
            "a softmax answers one score per label ASKED FOR — the fake's "
            "walked answer keyed {alpha, bravo} regardless of the request, "
            "which shifted every per-label confidence table silently"
        )
        total = sum(scores)
        assert abs(total - 1.0) <= 1e-4, (
            f"softmax sum {total!r} — the 1e-4 (not zero) budget is the "
            "gateway's own: round(., 6) per label costs <= n*5e-7, and the "
            "denominator epsilon costs ~1e-8"
        )
        assert 1.0 - total > 0.0, (
            f"a softmax summing to EXACTLY {total!r} means the epsilon/"
            "max-subtraction left the formula — every producer this bullet "
            "pinned was 1-minus-1e-8-ish, which is why N2a never asserted "
            "== 1.0 (dossier N2b forbade it)"
        )
        assert scores.index(max(scores)) == 0, (
            "top_label = labels[argmax] — an argmax that ignores score order "
            "is how a classify provider 'passes' while naming a random label"
        )

    def test_N2_a_sigmoid_head_is_schema_valid_and_does_not_sum_to_one(self) -> None:
        """N2b's finding as DATA: the swap that mattered was not "softmax vs
        no softmax" in the schema — it was that a SigLIP-style sigmoid head
        answers three INDEPENDENT probabilities for the same request. Both
        spellings are legal against a bare {label: number} map, so only the
        SUM can tell them apart."""
        sigmoid = [0.9, 0.7, 0.6]
        softmax = _softmax([2.0, 0.5, -1.0])
        assert abs(sum(sigmoid) - 1.0) > 0.1, (
            f"a sigmoid head's sum {sum(sigmoid)!r} read as a distribution — "
            "an over-permissive tolerance turns a head swap into a passing "
            "confidence number"
        )
        assert abs(sum(softmax) - 1.0) <= 1e-4
        assert len(sigmoid) == len(softmax), (
            "both heads answer len(labels) floats: the SHAPE is identical, "
            "which is precisely why the sum (not a key or type check) is the "
            "tripwire"
        )
        assert max(softmax) < max(sigmoid), (
            "the same class ranked by softmax and by sigmoid gives different "
            "rankings at the top — a threshold tuned on one head is "
            "mis-scaled on the other, with the schema unchanged"
        )


class TestN2aClassifyTombstone:
    """TOMBSTONE (R8 S3, owner ruling 5). ``clip_classify`` drove a softmax
    over EXACTLY the requested labels against both app-driven providers, with
    three assertions: ``scores`` keys == ``request.labels``, ``sum(scores)``
    within the 6dp rounding budget, and ``top_label`` a MEMBER of the
    requested list. The hazard under them was the per-label confidence
    tables: two downstream tables filter the stream by class name, so a
    provider keying scores anything else (the fake did — ``{alpha, bravo}``,
    plus the generic ``top_label_NNN`` string generator) silently shifted
    every threshold with nothing schema-side to refuse it. Sources: gateway
    manual softmax ``exp(s - s.max())/(sum + 1e-8)`` with ``round(., 6)`` and
    ``top_label = labels[argmax]``; legacy server ``torch.softmax`` +
    ``dict(zip(labels, ...))``.

    It cannot retarget: no surviving op is a classify op. The derived
    embedding set is the whole numeric response surface, and the fake's one
    remaining free-form map (``enrich_lt_threat_detect``'s
    ``threats_detected`` items, walked as ``{"alpha": .., "bravo": ..}``) is
    not a label-indexed distribution — there is no requested-label set for it
    to echo. The shape its three assertions graded now runs as a live
    assertion in TestN2NumericContractShape."""

    def test_classify_retired_and_the_ratchet_adopted_it(self) -> None:
        assert "clip_classify" not in OPERATION_IDS
        assert "clip_classify" in _retired_registry_ops()
        # Its response snapshot went with it: a leftover snapshot would mean
        # the contract generator still walks a dead route.
        assert not (SCHEMA_DIR / "clip_classify.response.json").exists()
        # Non-vacuity: the label-distribution class is not dead — the shape
        # above asserts it, and this file still drives a JSON response whose
        # numbers the same tolerance discipline grades.
        assert NUMERIC_OPS, "no numeric op survives; this tombstone is alone"


class TestN2bGatewaySigLipTombstone:
    """TOMBSTONE (R8 S3, owner ruling 5). This drove ``/clip/classify`` on the
    GATEWAY ALONE and pinned that the gateway had already swapped CLIP
    ViT-L/14 for SigLIP-2 at 768 dims (the Triton clip config said so at
    :1-2, with output dims [768] at :22-25) while still presenting a SOFTMAX
    contract: it did its own dot plus a manual softmax, never surfaced
    SigLIP's sigmoid head, and answered through a bare pydantic
    ``ClassifyResponse`` — so the only thing standing between a head swap and
    a wrong confidence number was the sum of four labels' scores.

    It cannot retarget: the route, its adapter (``adapters/clip.py``) and the
    Triton model directory it read are all swept, and no surviving gateway
    adapter emits a label-indexed distribution (yolo26 emits COCO detections,
    enrichment_light emits 4 threat classes — neither normalized across the
    label set). The swap lesson survives as data in
    TestN2NumericContractShape.test_N2_a_sigmoid_head_...; the Triton
    repository sweep is pinned by backend/tests/unit/
    test_r8_s3_florence_provider_retirement.py."""

    def test_the_siglip_era_surface_is_gone_from_the_shipped_gateway(self) -> None:
        assert not (REPO_ROOT / "ai" / "gateway" / "adapters" / "clip.py").exists()
        assert not (REPO_ROOT / "ai" / "triton" / "model_repository" / "clip").exists()
        assert "clip_embed" not in OPERATION_IDS
        # Non-vacuity: the mounted gateway still offers a numeric surface for
        # a future head-swap check to land on, read off the live app.
        mounted_paths = _mounted_paths()
        assert OPERATIONS[REID_OP].path in mounted_paths, (
            "the gateway app no longer mounts the op this cluster drives — "
            "the tombstone's non-vacuity claim would be its only live one"
        )


def _mounted_paths() -> set[str]:
    """Every path the mount table's routers actually answer, prefix included —
    read from the same table the app fixtures mount, so the map and the driven
    app can never disagree."""
    import importlib

    paths: set[str] = set()
    for module, prefix in GATEWAY_MOUNTS:
        router = importlib.import_module(module).router
        paths |= {f"{prefix}{route.path}" for route in router.routes}
    return paths


# ---------------------------------------------------------------------------
# N3 — value ranges AND which layer actually ENFORCES them (pydantic ge/le vs
# bare floats vs schema none)
# ---------------------------------------------------------------------------


class TestN3RangesAndConstraintPresence:
    """N3 source (dossier N3): the legacy CLIP server enforced
    ``anomaly_score`` ge=0/le=1 and ``similarity`` ge=-1/le=1 in ITS OWN
    pydantic models, and the finding was that the GATEWAY's response models
    were bare floats — the range lived only in a clamp formula, and a float32
    dot that landed at 1.0000001 500'd the legacy server while sailing
    through the gateway. Same quantity, three answers depending on which
    provider answered, and the committed WP7.2 snapshots could catch none of
    it.

    RETARGETED (R8 S3). The range-carrying numeric that survives is the light
    lane's CONFIDENCE: ``round(float(confidences[i]), 4)`` per detection at
    ai/gateway/adapters/enrichment_light.py:112 (the argmax class score) and
    ``max_confidence=round(max_confidence, 4)`` at :158-163, answered through
    ``ThreatResponse`` whose ``max_confidence`` is a BARE
    ``float = Field(default=0.0)`` (:58) and whose committed snapshot says
    ``{"type": "number"}`` with no bound. The asymmetry reproduces on the
    surviving lane, one column over: a model emitting a >1.0 score, or a
    provider swapping sigmoid for raw logits, puts an out-of-range confidence
    on the wire with nothing schema-side to refuse it — and the DB refuses it
    only at INSERT (ck_threat_detections_confidence_range), which is WP8.5's
    whole "enforced too late" thesis. The CLIP-side bullets (anomaly in [0,1],
    batch-similarity items in [-1,1]) are tombstoned in TestN3RangeTombstone."""

    async def test_N3_gateway_confidence_is_within_its_mathematical_range(
        self, gateway_app
    ) -> None:
        """One request, three checks on PRODUCED numbers: bounded [0,1],
        rounded to the 4dp the adapter claims, and internally consistent (the
        envelope's max equals the max of the items). Non-vacuity first: the
        canned class scores sit above the adapter's 0.25 threshold, so an
        empty list here means the fixture died and this test would otherwise
        grade nothing."""
        async with _patched_http(gateway_app, GATEWAY_PATCH_TARGETS) as client:
            body = await _drive("gateway", client, THREAT_OP)
        items = body["threats_detected"]
        assert items, (
            "the canned threat rows all fell below the adapter's "
            "conf_threshold — a pass here would grade the empty list, not the "
            "number this class exists to bound"
        )
        assert len(items) == len(_THREAT_ROWS), (
            f"emitted {len(items)} of the {len(_THREAT_ROWS)} above-threshold "
            "rows the fixture supplied — the post-processor's mask moved"
        )
        for item in items:
            conf = item["confidence"]
            assert 0.0 <= conf <= 1.0, (
                f"gateway confidence {conf!r} outside [0,1] — nothing "
                "schema-side refuses it (ThreatResponse declares a bare "
                "float), so the range survives only as producer arithmetic"
            )
            assert conf == round(conf, 4), (
                f"{conf!r} is not 4dp-rounded: "
                "adapters/enrichment_light.py:112 is the rounding site; a "
                "provider that stops rounding changes the wire bytes with no "
                "schema noticing"
            )
        assert body["max_confidence"] == max(item["confidence"] for item in items), (
            f"envelope max_confidence {body['max_confidence']!r} disagrees "
            f"with the emitted items {[i['confidence'] for i in items]} — a "
            "consumer alerting on the envelope while filtering on the items "
            "would disagree silently"
        )

    @pytest.mark.parametrize("provider_client", PROVIDER_PARAMS, indirect=True)
    async def test_N3_embedding_component_range_is_invisible_to_the_contract(
        self, provider_client
    ) -> None:
        """The N3 shape finding, on the op that survived: a unit vector's
        components are bounded by 1.0 in magnitude, and the committed contract
        says nothing of the kind — ``items`` is a bare ``{"type": "number"}``.
        Green here is no evidence about ranges; that IS the finding, restated
        for the lane that is still shipped. Both providers are graded because
        the fake's unit embedding is drawn from U(-1,1) normalized (it DOES
        carry negative components, which is why the bound is on magnitude)
        while the gateway's comes from a float32 tensor."""
        provider_id, client = provider_client
        body = await _drive(provider_id, client, REID_OP)
        emb = body["embedding"]
        items = _snapshot(REID_OP)["properties"]["embedding"]["items"]
        assert items == {"type": "number"}, (
            f"the committed embedding item schema gained keywords ({items!r}) "
            "— if a range ever lands here, N3's 'schema can catch none of "
            "this' premise changed; promote the range checks into schema "
            "validation and cite the snapshot edit"
        )
        assert max(abs(x) for x in emb) <= 1.0, (
            f"{provider_id}: a component of {max(abs(x) for x in emb)!r} in a "
            "UNIT vector cannot exceed 1.0 — this is the bound the snapshot "
            "cannot express, and the first thing a non-normalized provider "
            "trips (the DB-side analogue is where the refusal actually "
            "happens: too late)"
        )

    def test_N3_committed_snapshots_declare_no_range_on_the_vision_lane(self) -> None:
        """The contrast IS the finding, DERIVED off the whole schema
        directory: a range keyword IS expressible in this contract format —
        the VLM op's snapshot expresses ``minimum``/``maximum`` on
        ``risk_score`` — and none of the light-lane snapshots expresses one. A
        range landing on a light-lane snapshot reddens here (premise changed:
        promote to schema validation and cite the edit); so does the format
        losing ranges EVERYWHERE, because then the contrast stopped existing."""
        bounded = sorted(
            p.name.removesuffix(".response.json")
            for p in SCHEMA_DIR.glob("*.response.json")
            if '"maximum"' in p.read_text(encoding="utf-8")
            or '"minimum"' in p.read_text(encoding="utf-8")
        )
        light_lane = set(operations_for_slot("enrichment_light_adapter", OPERATIONS))
        assert light_lane, "the light slot went empty — the derived comparison is vacuous"
        assert not (light_lane & set(bounded)), (
            f"light-lane ops {sorted(light_lane & set(bounded))} gained range "
            "keywords — promote the range checks into schema validation and "
            "cite the snapshot edit"
        )
        assert bounded, (
            "no committed snapshot expresses a range anywhere — the premise "
            "below (ranges ARE expressible, just not here) stopped holding; "
            "re-cite what enforces boundedness now"
        )

    def test_N3_backend_schemas_still_carry_the_bounds_the_gateway_does_not(self) -> None:
        """Consumer-side half of the asymmetry, on surviving files only: the
        backend's own response models DO carry ge/le for the quantities the
        wire leaves unbounded, and the reid lane's bound is NARROWER than the
        cosine math (ge=0, not ge=-1) — same quantity, two contracts, which is
        what dossier N3 recorded and what still ships. The final leg is the
        anti-pin: the gateway-side model must still be BARE next to them, or
        the asymmetry closed and this becomes a range-PRESENCE assertion."""
        baseline_src = (REPO_ROOT / "backend/api/schemas/baseline.py").read_text(encoding="utf-8")
        assert "ge=0.0" in baseline_src and "le=1.0" in baseline_src, (
            "backend/api/schemas/baseline.py AnomalyEvent.anomaly_score "
            "constraint drifted (cite :225-228)"
        )
        reid_src = (REPO_ROOT / "backend/api/schemas/reid.py").read_text(encoding="utf-8")
        assert "ge=0.0" in reid_src, (
            "backend/api/schemas/reid.py lost its ge=0.0 — NOTE the reid lane "
            "constrains cosine to NON-negative (ge=0/le=1), narrower than the "
            "[-1,1] cosine arithmetic promises (dossier N3)."
        )
        adapter_src = (REPO_ROOT / "ai" / "gateway" / "adapters" / "enrichment_light.py").read_text(
            encoding="utf-8"
        )
        assert "max_confidence: float = Field(default=0.0)" in adapter_src, (
            "ThreatResponse.max_confidence gained a constraint — the "
            "asymmetry (backend ge/le vs gateway bare float) CLOSED; flip "
            "this into a range-PRESENCE assertion and cite the fix"
        )


class TestN3RangeTombstone:
    """TOMBSTONE (R8 S3, owner ruling 5). ``clip_similarity``,
    ``clip_anomaly_score`` and ``clip_batch_similarity`` graded three value
    ranges at once — similarity in [-1,1], anomaly_score in [0,1] (clamped
    ``max(0.0, min(1.0, 1.0 - sim))``, with both inputs re-normalized before
    the dot), and a batch map whose every item was a cosine — AND pinned
    which layer enforced each: the legacy server by pydantic ``ge``/``le``,
    the gateway by that clamp formula and nothing else, the committed WP7.2
    snapshots by nothing at all. The concrete failure mode was a float32 dot
    landing at 1.0000001: it 500'd the legacy server (``le=1.0``) and passed
    the gateway, so WHICH PROVIDER ANSWERED decided whether an out-of-range
    score was an error or a stored fact.

    It cannot retarget: no surviving op emits a cosine, an anomaly score or a
    batch similarity map — the remaining numeric surface is the embedding
    vector and the threat confidences above. The METHOD (read the response
    model for a constraint, then grade the number against the range the model
    cannot express) is alive in TestN3RangesAndConstraintPresence."""

    def test_the_range_ops_are_gone_and_the_ratchet_owns_them(self) -> None:
        retired = _retired_registry_ops()
        victims = sorted(
            op_id for op_id in retired if op_id.endswith(("_similarity", "_anomaly_score"))
        )
        assert len(victims) >= 2, f"the retired range family derived to {victims}"
        for op_id in victims:
            assert op_id not in OPERATION_IDS, op_id
            assert not (SCHEMA_DIR / f"{op_id}.response.json").exists(), op_id
        # Derived victim identity (WP4.2: sorted(x)[0] with a len guard, not a
        # hand-typed id list): the anomaly op is the one whose legacy producer
        # alone enforced [0,1] in pydantic.
        assert sorted(victims)[0] == "clip_anomaly_score"
        # Non-vacuity: producer-side clamp/max enforcement still has a live
        # instance, so "only the producer bounds the range" is not a
        # retired-only story.
        src = (REPO_ROOT / "ai" / "gateway" / "adapters" / "enrichment_light.py").read_text(
            encoding="utf-8"
        )
        assert "max_confidence = max(" in src, (
            "the surviving producer-side max went away — the hazard this "
            "tombstone records has no live instance left"
        )


# ---------------------------------------------------------------------------
# N4 — risk_score int [0,100] at three layers with DIFFERENT strictness;
# the 0-1-float provider silently truncates to 0
# ---------------------------------------------------------------------------

# Both schema modules import probe-verified once-shot (~3.1s incl. siblings;
# module imports are stdlib+pydantic only — llm_response.py:21-27 head,
# llm.py:16-21), so a module-level import is safe under the 5s tier.


class TestN4RiskScoreLayersDisagree:
    """N4 source (dossier N4 — PLAN CITE CORRECTED: the plan's
    backend/models/llm_response.py DOES NOT EXIST; the file is
    backend/api/schemas/llm_response.py; :393 field and :436 def
    coerce_risk_score are EXACT there):
      L1 guided_json: RISK_ANALYSIS_JSON_SCHEMA at llm_response.py:34,
        risk_score {'type':'integer','minimum':0,'maximum':100} at :37-42 —
        the only layer that rejects a non-integer at the SOURCE (NIM).
      L2 pydantic LLMRiskResponse: risk_score int ge=0 le=100 at :393-397 +
        BEFORE-validator coerce_risk_score at :434-460: float -> int(v)
        TRUNCATES; str -> int(float(v)); ge/le runs AFTER coercion, so
        out-of-range still raises.
      L3 Postgres CHECK ck_events_risk_score_range
        'risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)' at
        backend/models/event.py:241-243.
    RIVAL schema backend/api/schemas/llm.py LLMRiskResponse (class :227,
    Annotated int ge=0 le=100 at :288) has a DIFFERENT before-validator at
    :305-326 that CLAMPS (150->100, -10->0; 'return max(0, min(100, score))'
    at :326) instead of rejecting, plus a model-validator that REWRITES
    risk_level from the coerced score (:371-415 region).

    R8 S3 DIAGNOSIS (not assumed): all four tests survive untouched. Every
    subject here is the LLM risk layer — two schema modules and one ORM model
    — none of which the vision prune touches. The only provider-shaped claim
    in the class is the ABSENCE of a provider assertion (a generic int
    walker's output reads as a plausible risk score and catches nothing), and
    that warning is still true of the fake's llm ops."""

    # All four tests: no provider drives them — contract-layer
    # characterization (fake/gateway n/a for the pydantic layers; the fake's
    # llm ops are chat-completion snapshots whose response schemas carry NO
    # risk_score at all — llm_completion.response.json = {content,
    # tokens_predicted}). Dossier runtime-verified (0.5->0 both schemas;
    # llm_response 150 raises; llm.py 150->100).

    def test_N4_before_validator_truncates_floats_silently(self) -> None:
        r = StrictRiskResponse(risk_score=0.5, risk_level="low", summary="s", reasoning="r")
        assert r.risk_score == 0, (
            "0.5 must TRUNCATE to 0 — int(0.5) in coerce_risk_score "
            "(llm_response.py:450-452). A provider speaking risk on a 0-1 "
            "scale is 'valid, stored, catastrophically wrong' (plan N4): "
            "everything below 1.0 becomes 0 at every layer under the guided "
            "schema. If this ever reads 1, the validator started ROUNDING — "
            "re-cite the hazard direction."
        )
        r2 = StrictRiskResponse(risk_score="0.9", risk_level="low", summary="s", reasoning="r")
        assert r2.risk_score == 0, (
            "str '0.9' -> int(float('0.9')) == 0 (llm_response.py:453-457) — "
            "stringly risk payloads truncate identically"
        )

    def test_N4_out_of_range_rejected_by_strict_clamped_by_rival(self) -> None:
        with pytest.raises(ValidationError):
            StrictRiskResponse(risk_score=150, risk_level="low", summary="s", reasoning="r")
        rival = RivalRiskResponse(risk_score=150, risk_level="low", summary="s", reasoning="r")
        assert rival.risk_score == 100, (
            "the rival CLAMPS (backend/api/schemas/llm.py:326 "
            "max(0, min(100, score))) where llm_response.py:393-397 REJECTS — "
            "two LLMRiskResponse schemas in one codebase DISAGREE on "
            "out-of-range; whichever parses the provider output decides "
            "whether a 150 is an error or a quiet 100."
        )
        rival2 = RivalRiskResponse(risk_score=0.75, risk_level="high", summary="s", reasoning="r")
        assert rival2.risk_score == 0, "int(float(0.75)) truncates in the rival too (llm.py:321)"
        assert str(rival2.risk_level).lower().endswith("low"), (
            f"risk_level 'high' rewritten from the coerced score -> "
            f"{rival2.risk_level!r} (llm.py model-validator :371-415) — "
            "truncation cascades into the label"
        )

    def test_N4_guided_schema_is_the_integer_layer(self) -> None:
        rs = RISK_ANALYSIS_JSON_SCHEMA["properties"]["risk_score"]
        assert rs["type"] == "integer" and rs["minimum"] == 0 and rs["maximum"] == 100, (
            "L1 (llm_response.py:37-42) is the only layer that forbids the "
            "FLOAT itself; pydantic accepts floats and destroys them, so "
            "dropping 'integer' here turns the truncation from 'provider "
            "misbehaved' into 'the contract invited it'."
        )

    def test_N4_postgres_check_constraint_parity(self) -> None:
        src = (REPO_ROOT / "backend/models/event.py").read_text(encoding="utf-8")
        assert "risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)" in src, (
            "L3 drifted from ck_events_risk_score_range (event.py:241-243) — "
            "CHECK parity with the pydantic ge/le is the last line; note both "
            "are RANGES, neither is INTEGER-NESS: the DB would happily store "
            "a float 0.5 where the int pydantic already made it 0."
        )
        assert "ck_events_risk_score_range" in src


# ---------------------------------------------------------------------------
# N5 — competing dimensionalities with INCONSISTENT failure modes (raise /
# silent 0.0 / silent passthrough), graded on the one surviving slot
# ---------------------------------------------------------------------------


class TestN5DimConfusion:
    """N5's dossier table had four columns. The prune took the provider-side
    multi-slot claim (CLIP's 768-d slot retired with its model — tombstoned in
    TestN5MultiSlotTombstone) and left the three failure-mode columns
    standing on live code, one of them newly EXECUTABLE.

      RAISE-ON-WRONG-DIM. The service that owned this mode
      (``backend/services/scene_baseline.py``, which raised
      ``InvalidEmbeddingError`` unless len == its 768 constant) is gone with
      the CLIP surface, but the MODE is still shipped in two live places and
      its EXCEPTION still ships in backend/core/exceptions.py: the face
      loader refuses a 768-d vector against its 512-d gallery space
      (face_recognizer_loader.py:239-244) and
      ``osnet_loader._enforce_embedding_dim`` refuses anything but 512
      (:160-180, D-5). ``test_N5a_wrong_dim_raises_in_the_matcher_and_passes_
      the_adapter`` grades the contrast across the seam where it still
      matters: the SAME mismatched vector raises at the backend and 200s at
      the gateway adapter.
      SILENT 0.0. ``reid_matcher._cosine_similarity`` still returns exactly
      0.0 for unequal lengths (:255-256), and
      ``DEFAULT_EMBEDDING_DIMENSION`` (:57) is still a constant with no
      consumer — asserted from the AST, not from a remembered grep.
      RAISE, NEVER PAD. The re-ID full swap's D-5 ruling turned osnet's
      silent pad/truncate into a raise, so this column is no longer a source
      characterization: it is executed.
      DOCUMENTATION-ONLY 512. ``backend/models/face_identity.py`` gained no
      validator; dimension remains convention, not constraint.

      Provider side: one slot remains (see TestN5MultiSlotTombstone), and the
      fake-side 768->512 bullet is already
      test_fake_provider.py::test_unit_norm_embedding_at_the_surviving_home
      — cited, not repeated."""

    # backend-internal, executed (the pre-swap version of this test could only
    # characterize source because exercising the pad path needed weights).
    def test_N5c_osnet_loader_raises_on_wrong_dim(self) -> None:
        """D-5: "a wrong checkpoint must never become a plausible vector". The
        raise path needs only an array, so this is now the real behaviour plus
        the source pins that keep the RETIRED pad/truncate branches from
        coming back (the N5 table's pad column changes mode, it never goes
        blank). Import cost of this module is ~2.3s, inside the tier budget."""
        from backend.services.osnet_loader import OSNET_EMBEDDING_DIM, _enforce_embedding_dim

        assert OSNET_EMBEDDING_DIM == 512
        assert _enforce_embedding_dim(np.zeros((1, 512))).shape == (512,)
        for wrong in (511, 768, 1024):
            with pytest.raises(RuntimeError, match=str(OSNET_EMBEDDING_DIM)):
                _enforce_embedding_dim(np.zeros((1, wrong)))
        src = (REPO_ROOT / "backend/services/osnet_loader.py").read_text(encoding="utf-8")
        assert "np.pad(" not in src, (
            "the retired silent-pad path came back (pre-swap osnet_loader "
            ":352-355) — D-5 ruled a wrong dim RAISES, never pads"
        )
        assert "embedding.flatten()[:OSNET_EMBEDDING_DIM]" not in src, (
            "the retired silent-truncate path came back (pre-swap :350)"
        )

    def test_N5b_reid_matcher_dim_mismatch_is_silent_zero(self) -> None:
        from backend.services.reid_matcher import ReIDMatcher

        assert ReIDMatcher._cosine_similarity([0.1] * 512, [0.1] * 768) == 0.0, (
            "reid_matcher.py:255-256 returns 0.0 for unequal lengths — the "
            "plan's 'defaults 512' mode is FALSE (the module-level "
            "DEFAULT_EMBEDDING_DIMENSION is asserted dead below by AST); a "
            "dim mistake in the reid lane reads as 'no match', never an "
            "error — the WORST of the three failure modes for swap readiness."
        )

    def test_N5b_the_default_dimension_constant_is_still_dead(self) -> None:
        """The dossier's N5b claim — the 512 default is a DEAD constant — is a
        grep-shaped claim, so it is graded from the AST: the name is defined at
        module level and has ZERO other mentions in its own module. Wiring it
        up later turns 'defaults 512' from FALSE into TRUE, which is a FOURTH
        failure mode (silent defaulting) and has to restate this."""
        src = (REPO_ROOT / "backend/services/reid_matcher.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        defined = any(
            isinstance(n, (ast.Assign, ast.AnnAssign))
            and any(
                t.id == "DEFAULT_EMBEDDING_DIMENSION"
                for t in (n.targets if isinstance(n, ast.Assign) else [n.target])
                if isinstance(t, ast.Name)
            )
            for n in tree.body
        )
        uses = sum(
            1
            for n in ast.walk(tree)
            if isinstance(n, ast.Name) and n.id == "DEFAULT_EMBEDDING_DIMENSION"
        )
        assert defined, (
            "the constant this property calls dead is not defined at module "
            "level any more — re-cite which module carries the reid default "
            "dimension"
        )
        assert uses == 1, (
            f"DEFAULT_EMBEDDING_DIMENSION appears {uses}x (1 == definition "
            "only): it gained a consumer, so 'no code defaults to 512' is "
            "stale and the N5 failure-mode table gains a DEFAULTING column"
        )

    async def test_N5a_wrong_dim_raises_in_the_backend_and_passes_the_adapter(
        self, gateway_app
    ) -> None:
        """The surviving half of N5a, as ONE pair on ONE seam, because the
        contrast — not either leg — is the finding.

        Raising side: ``InvalidEmbeddingError(expected_dim=512,
        actual_dim=511)`` carries BOTH dimensions into its details payload.
        That exception class is the shipped backend answer to a dimension
        mistake, and it survives the sweep that took the service which used to
        raise it (backend/core/exceptions.py:893).

        Passing side: the same 511-vs-512 mismatch driven through the shipped
        light adapter returns 200 with a 511-vector and
        ``embedding_dimension == 511``. The adapter takes
        ``result["embedding"][0]`` (adapters/enrichment_light.py:200) and
        nothing between there and the wire counts anything; the response model
        declares ``embedding: list[float]`` and a bare ``int`` dim, so the
        declaration faithfully reports the wrong size it carries. That is why
        N1a's ``declared == len(vector)`` equality — green, correct, worth
        keeping — CANNOT catch a wrong-slot provider: it is an internal
        consistency check, and this is its blind spot, pinned rather than
        assumed."""
        err = InvalidEmbeddingError(expected_dim=512, actual_dim=511)
        assert err.details == {"expected_dim": 512, "actual_dim": 511}, (
            "N5a's raising side lost both dimensions from the error it names "
            f"— details now {err.details!r}"
        )

        async with _patched_http(
            gateway_app, GATEWAY_PATCH_TARGETS, mock_triton=_mock_triton(reid_dim=511)
        ) as client:
            op = OPERATIONS[REID_OP]
            r = await client.request(op.method, op.path, json={"image": _B64_IMAGE})
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert len(body["embedding"]) == 511, (
            "the adapter's tensor row is 511 long — if the response is not, "
            "something between the Triton mock and the wire changed the "
            "vector and this pair is no longer grading one input shape"
        )
        assert body["embedding_dimension"] == 511, (
            "the declared dim followed the tensor instead of refusing it — "
            "if this ever raises/4xx, the adapter gained a dimension gate and "
            "N5a's silent side CLOSED; restate this leg as a raises-check "
            "and cite the gate"
        )

    def test_N5_the_single_slot_is_one_number_across_four_shipped_artifacts(self) -> None:
        """The RETARGETED half of the retired multi-slot claim. What that test
        actually bought was "the per-op dimensions are pinned against shipped
        artifacts, not against each other" (it read clip's 768 from its
        snapshot AND its adapter constant, reid's 512 from its snapshot AND its
        loader constant). With one slot left, the live form of that property is
        the AGREEMENT of the shipped artifacts that describe it — four
        independent places a width is written down, none derived from another:

          1. the Triton weights' own width (``OSNET_EMBEDDING_DIM``, AST-read
             from backend/services/osnet_loader.py);
          2. the fake's generator override that BUILDS the vector;
          3. the fake's separate ``const`` override that DECLARES the dim
             (generators.py:222-223 — two entries, so a re-dim of one without
             the other is exactly what this catches);
          4. the number the fake actually SERVES, both as vector length and as
             ``embedding_dimension``, driven over ASGI (the committed snapshot
             pins only the field TYPE — ``integer``, no size — which the wire
             leg above is the size-half of).

        Non-vacuity is structural: four independent sources are compared, and
        the wire is driven, so a provider that declares what it does not emit
        reddens as well as a registry that re-dims one artifact."""
        from backend.ai_contract.fake import create_fake_app
        from backend.ai_contract.fake.generators import _OVERRIDES

        vector_override = _OVERRIDES[(REID_OP, "embedding")]
        declared_override = _OVERRIDES[(REID_OP, "embedding_dimension")]
        assert vector_override[0] == "unit_embedding", (
            f"the fake's embedding generator is now {vector_override!r} — the "
            "unit-norm guarantee this cluster asserts comes from that speller"
        )
        assert vector_override[1] == declared_override[1] == _CANNED_REID_DIM, (
            f"weights {_CANNED_REID_DIM} / built {vector_override[1]} / "
            f"declared {declared_override[1]} — the fake's build and declare "
            "entries drifted apart, which is the silent half of a dim change"
        )
        snapshot_dim = _snapshot(REID_OP)["properties"]["embedding_dimension"]
        assert snapshot_dim["type"] == "integer", snapshot_dim

        async def drive() -> tuple[int, int]:
            from httpx import ASGITransport, AsyncClient

            async with AsyncClient(
                transport=ASGITransport(app=create_fake_app()), base_url="http://f"
            ) as client:
                op = OPERATIONS[REID_OP]
                body = (
                    await client.request(op.method, op.path, json=_fake_payload(REID_OP))
                ).json()
            return len(body["embedding"]), body["embedding_dimension"]

        import asyncio

        built, declared = asyncio.run(drive())
        assert built == declared == _CANNED_REID_DIM, (
            f"wire: {built} built / {declared} declared vs weights "
            f"{_CANNED_REID_DIM} — all four artifacts must name ONE slot"
        )

    def test_N5d_face_identity_512_is_documentation_only(self) -> None:
        """(dossier N5d: 512 is documentation + service convention, not a
        constraint.) Verified: docstring present, validators absent — the
        asymmetry IS the finding."""
        src = (REPO_ROOT / "backend/models/face_identity.py").read_text(encoding="utf-8")
        assert "512-dimensional ArcFace" in src, "face_identity.py:116 doc drifted"
        tree = ast.parse(src)
        validators = [
            n
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and any(
                (
                    isinstance(d, ast.Call)
                    and isinstance(d.func, ast.Name)
                    and d.func.id in {"field_validator", "model_validator"}
                )
                or (
                    isinstance(d, ast.Attribute)
                    and d.attr in {"field_validator", "model_validator"}
                )
                or (isinstance(d, ast.Name) and d.id in {"field_validator", "model_validator"})
                for d in n.decorator_list
            )
        ]
        assert not validators, (
            "face_identity.py gained a validator — the doc-only "
            "characterization is stale: promote this to a raises-check and "
            "cite the validator (the dim-failure-mode table gains a FOURTH "
            "column only if this happens)."
        )


class TestN5MultiSlotTombstone:
    """TOMBSTONE (R8 S3, owner ruling 5). ``test_N5_provider_dims_are_the_
    distinct_slots`` drove BOTH embedding ops against both app-driven
    providers and asserted ``len(clip_embedding) == 768``,
    ``len(reid_embedding) == 512`` and — the load-bearing one —
    ``len(clip) != len(reid)``. Its point was that the two embedding spaces
    were different sizes ON PURPOSE: a cross-space cosine was then
    detectably meaningless because the shapes disagreed and the matcher
    returned its documented silent 0.0. If the two ever collapsed to one
    dimensionality, cross-space scores would start LOOKING comparable and
    nothing on either side would say so. Per-op dims were pinned per schema
    (clip 768 via its snapshot + the adapter's constant; reid 512 via its
    snapshot + the loader constant).

    It cannot retarget as a multi-slot claim: CLIP's 768-d slot retired with
    its model (ruling 5), so the shipped registry has exactly ONE embedding
    slot and there is no second dimensionality left to be distinct from. Two
    things survive it, both live in TestN5DimConfusion: the single-slot
    HAZARDS (a wrong dim passing the adapter; silent 0.0 in the matcher; the
    dead default constant; the raise-never-pad guard), and the claim's METHOD
    — per-op dims pinned against shipped artifacts, which with one slot is the
    four-way AGREEMENT test ``test_N5_the_single_slot_is_one_number_across_four_
    shipped_artifacts``. The fake-side half of the width retarget — the
    surviving slot's width pinned against the committed snapshot's own
    ``embedding_dimension`` instead of a remembered 768 — is
    test_fake_provider.py::test_unit_norm_embedding_at_the_surviving_home; this
    file cites it rather than repeating it."""

    def test_the_second_embedding_slot_is_gone_and_the_ratchet_owns_it(self) -> None:
        assert "clip_embed" not in OPERATION_IDS
        assert "clip_embed" in _retired_registry_ops()
        assert not (SCHEMA_DIR / "clip_embed.response.json").exists()
        assert len(_embedding_ops()) == 1, (
            f"{sorted(_embedding_ops())} — a second embedding op came back; "
            "the multi-slot claim has a live subject again and must be "
            "restored, not left as this tombstone"
        )

    def test_the_surviving_slot_is_the_one_every_column_names(self) -> None:
        """Non-vacuity for the whole N5 cluster, derived off the matrix rather
        than asserted as a count: every slot that serves the embedding op
        serves it by PATH, so the slot this cluster's numeric properties grade
        exists on the wire — and a column that quietly lost it reddens."""
        embedding_ops = _embedding_ops()
        assert embedding_ops == {REID_OP}
        mounted = _mounted_paths()
        for slot in ("gateway", "enrichment_light_adapter", "per_model_server", "fake"):
            column = set(operations_for_slot(slot, OPERATIONS))
            assert column & embedding_ops == embedding_ops, (
                f"slot {slot!r} lost the surviving embedding op — the dim "
                "this cluster pins would have no column to be pinned in"
            )
        assert OPERATIONS[REID_OP].path in mounted, (
            f"{OPERATIONS[REID_OP].path} is in every column but no mounted "
            "router — a decorative column is the class gen-ai-contract's "
            "phantom check refuses"
        )


# ---------------------------------------------------------------------------
# N6 — guided schema summary maxLength 200; the pydantic model does NOT
# enforce it (generation-time contract, invisible at runtime)
# ---------------------------------------------------------------------------


class TestN6SummaryMaxLengthUnenforced:
    """N6 source (dossier N6): guided summary {'type':'string','maxLength':
    200} at backend/api/schemas/llm_response.py:49-52 vs pydantic summary:
    str = Field(...) with NO max_length at :404-407; rival backend/api/
    schemas/llm.py summary carries min_length=1 only (:336-342 region). A
    201+ char summary is contract-violating yet PARSES AND STORES. The fake
    never trips it: the generic string generator emits ~11 chars
    ('summary_NNN') — invisible to any provider-parametrized assertion, hence
    a contract-layer characterization (dossier providers: matrix-only).
    Runtime-probed: 'x'*250 passes straight through.

    R8 S3 DIAGNOSIS (not assumed): both subjects are LLM schema modules; the
    prune retired vision surface only, so nothing here moves."""

    def test_N6_summary_250_chars_passes_pydantic_alongside_schema_maxlength(self) -> None:
        s = "x" * 250
        assert (
            StrictRiskResponse(risk_score=5, risk_level="low", summary=s, reasoning="r").summary
            == s
        ), "pydantic side gained enforcement — flip this into a raises-check"
        assert RISK_ANALYSIS_JSON_SCHEMA["properties"]["summary"]["maxLength"] == 200, (
            "the guided side drifted; the two DISAGREE BY DESIGN (that is the "
            "finding) — if the schema lost maxLength the generation-time "
            "contract vanished and this pair must be re-cited to whatever "
            "enforces brevity now (the frontend keyword-matches the summary — "
            "severityCalculator.ts, plan's semantics block)."
        )


# ---------------------------------------------------------------------------
# Matrix guards — presence == slot column, absence == 404 (green guards,
# never skips). per_model_http + llamacpp_llm + the VLM engines appear ONLY
# here (hard rule: their registered callables do real network — dossier Q5 —
# never invoked).
# ---------------------------------------------------------------------------


class TestMatrixNumericSurface:
    """The availability half of every numeric op — for every numeric op the
    registry actually has (``NUMERIC_OPS`` is derived; the draft hand-listed
    five ids whose numeric surface was mostly CLIP's, which is exactly the
    hand-numbered-table rot WP4.2 removed elsewhere in this tier)."""

    def test_matrix_registered_op_set_matches_slot_column(self) -> None:
        from backend.ai_contract.fake import fake_provider_ops

        reg = registered_providers()
        # fake joins the registry the way the suite registers it (the fake is
        # NOT import-registered — providers.py docstring;
        # test_fake_provider.py:166-175 is the in-test precedent).
        # register_provider stores by ProviderId.value, so a repeat call is a
        # replace, not an accumulation; `reg` is the COPY registered_providers
        # hands back (provider.py:261), so the local binding below is what this
        # test reads and no provider table is mutated behind another test.
        reg["fake"] = register_provider(
            ProviderId.FAKE, fake_provider_ops(), OPERATIONS, deployed=True
        )
        for provider_id, slot in SLOT_OF.items():
            rec = reg[provider_id]
            column = set(operations_for_slot(slot, OPERATIONS))
            declared = set(rec.operations())  # READ the map, NEVER call it
            if provider_id in SUBSET_REQUIRED:
                # union-slot rule: a subset provider declares its own
                # required SUBSET (SUBSET_REQUIRED), not the column. Numeric
                # ops are not any subset provider's surface at all.
                assert declared <= column, provider_id
                assert not declared & set(NUMERIC_OPS), provider_id
                assert declared == SUBSET_REQUIRED[provider_id], provider_id
            else:
                assert declared == column, (
                    f"{provider_id}: declared {len(declared)} != slot {slot!r} column {len(column)}"
                )
            for op_id in NUMERIC_OPS:
                if provider_id in SUBSET_REQUIRED:
                    # union-slot rule (asserted above): a subset provider
                    # declares only its required subset (a subset of the
                    # column), so per-op column EQUALITY is the wrong guard —
                    # it would claim NO numeric op.
                    assert op_id not in declared, f"{provider_id}/{op_id}"
                else:
                    assert (op_id in declared) == (op_id in column), (
                        f"{provider_id}/{op_id}: presence disagrees with the column"
                    )

    def test_matrix_deployed_flags(self) -> None:
        reg = registered_providers()
        assert reg["per_model_http"].deployed is False
        assert reg["gateway"].deployed is True
        assert reg["gateway_light"].deployed is True
        assert reg["llamacpp_llm"].deployed is True
        # 1.1: the VLM engines are declared, not deployed (compose service
        # is step 1.2, vlm_client step 1.3) - providers.py registers both
        # deployed=False.
        assert reg["openai_vlm"].deployed is False
        assert reg["rtvi_vlm"].deployed is False

    def test_matrix_mount_table_is_derived_from_main(self) -> None:
        """The mount list and the patch-target list are the same fact stated
        twice, so the mount list is checked against the shipped composition
        root by AST instead of remembered: an adapter added to
        ai/gateway/main.py reddens HERE, which is what forces a patch target
        alongside it (dossier Q2's real hazard — one adapter patched, one
        silently on real gRPC)."""
        src = (REPO_ROOT / "ai" / "gateway" / "main.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        # router aliases: `from X import router as Y` — main.py mounts the
        # ALIAS, so resolve alias -> (module, original name) before comparing.
        aliases: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    aliases[alias.asname or alias.name] = node.module
        shipped: set[tuple[str, str]] = set()
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "include_router"
                and node.args
            ):
                continue
            arg = node.args[0]
            if not (isinstance(arg, ast.Name) and arg.id in aliases):
                continue
            prefixes = [kw.value.value for kw in node.keywords if kw.arg == "prefix"]
            if prefixes:
                shipped.add((aliases[arg.id], prefixes[0]))
        assert shipped, "no aliased, prefix-bearing include_router in the gateway main"
        assert shipped == set(GATEWAY_MOUNTS), (
            f"gateway/main.py mounts {sorted(shipped)} but this cluster mounts "
            f"{sorted(GATEWAY_MOUNTS)} — an unmounted adapter grades an "
            "availability column against an app that cannot answer it, and an "
            "unpatched adapter answers on real gRPC"
        )
        assert tuple(f"{module}.get_triton_client" for module, _ in GATEWAY_MOUNTS) == (
            GATEWAY_PATCH_TARGETS
        )
        assert len(GATEWAY_PATCH_TARGETS) == len(set(GATEWAY_PATCH_TARGETS)) >= 2, (
            "the multi-target rule needs at least two DISTINCT module-level "
            "names — a single-target list is the shape that silently leaves "
            "an adapter on real gRPC"
        )

    async def test_matrix_gateway_light_column_absences_are_real_404s(
        self, gateway_light_app
    ) -> None:
        """Absence == 404, graded against the light-only app, with a positive
        control on the SAME client so the 404s read as ABSENCE rather than a
        dead mount or a dead patch.

        The VICTIM list is DERIVED off the columns
        (``gateway - gateway_light``) instead of the drafted hand-list of four
        ``/clip`` ids: today the derived victims are the three /yolo26 ops,
        and on the merged gateway app they answer 422 (the route EXISTS and
        wants a multipart upload), which would grade pydantic instead of
        availability — so the light-only app earns its keep for the reason the
        draft gave, with a different retired-free victim set."""
        reg = registered_providers()
        light_ops = set(reg["gateway_light"].operations())
        gateway_ops = set(reg["gateway"].operations())
        assert REID_OP in light_ops
        victims = sorted(gateway_ops - light_ops)
        assert len(victims) >= 2, (
            f"the derived absence set is {victims} — a single victim is a "
            "brittle pin, and an empty one would make this whole test vacuous"
        )
        async with _patched_http(gateway_light_app, LIGHT_TARGETS) as client:
            for op_id in victims:
                op = OPERATIONS[op_id]
                r = await client.request(op.method, op.path, json={})
                assert r.status_code == 404, (
                    f"{op_id}: expected 404 on gateway_light's surface "
                    f"(its column says absent), got {r.status_code}"
                )
            # Positive control: the same patched client answers a claimed op.
            r = await client.post(OPERATIONS[REID_OP].path, json={"image": _B64_IMAGE})
            assert r.status_code == 200, r.text[:200]
            assert len(r.json()["embedding"]) == _CANNED_REID_DIM

    async def test_matrix_the_light_column_holds_exactly_its_own_routes(
        self, gateway_light_app
    ) -> None:
        """The other direction of the same column: no route the light adapter
        mounts is outside the column, and no column op lacks a route. Derived
        both ways (the router's real paths, the slot's real column), so a
        route added without a registry row — or a row without a route —
        reddens. ``/health`` is the adapter's liveness route (the residency
        probe reads it), not a registry op: excluded as DATA rather than by
        loosening the comparison."""
        import importlib

        light_module = importlib.import_module("ai.gateway.adapters.enrichment_light")
        mounted = {f"/enrich-lt{route.path}" for route in light_module.router.routes}
        column_paths = {
            OPERATIONS[op_id].path
            for op_id in operations_for_slot("enrichment_light_adapter", OPERATIONS)
        }
        assert column_paths <= mounted, (
            f"column ops with no route: {sorted(column_paths - mounted)}"
        )
        assert mounted - column_paths == {"/enrich-lt/health"}, (
            f"light-adapter routes outside the column: "
            f"{sorted(mounted - column_paths)} — either an unregistered op is "
            "being served or the non-op liveness-route exclusion needs "
            "restating (it is the residency probe's target)"
        )
        assert len(column_paths) >= 2, "the light column went singular; re-derive"
        async with _patched_http(gateway_light_app, LIGHT_TARGETS) as client:
            body = await _drive("gateway", client, THREAT_OP)
        assert "is_threat" in body, sorted(body)

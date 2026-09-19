"""WP8.3 conformance — cluster "numeric-invariants" (N1a-N6). DRAFT — NOT IN THE REPO.

Drafted per docs/superpowers/plans/2026-09-19-swap-readiness-72h.md §WP8.3
("Numeric invariants" bullets) against the verified dossier
.wp25-feed/wp83-evidence/full-results.json → result.clusters[group ==
"numeric-invariants"] (findings N1a..N6) plus cluster "WP8.3 suite mechanics"
(driving shapes Q1-Q7). This module is a sibling of the eventual single
parametrized backend/tests/contracts/ai_providers/test_conformance.py; it
carries ONLY the numeric-invariant properties.

STATUS: every assertion is UNVERIFIED — nothing here was executed under pytest
(a full validate.sh tier was running while this was drafted; the only live
executions allowed were one-shot `.venv/bin/python` import probes, and each
runtime-verified behavior below says so in its comment). Each block carries:
source (file:line from the dossier), predicted RED/GREEN against the fake,
predicted gateway behavior, and "UNVERIFIED".

DIVERGENCE POLICY (plan §WP8.3 procedure + goal rule):
  * NO xfail, NO skip, NO importorskip anywhere in this file — ever.
  * Where a property cannot hold TODAY against the fake (N2a: the fake's
    clip_classify is snapshot-WALKED, not a literal op, so its scores are
    {alpha, bravo} free-form U(0.1,0.9) — dossier N2a;
    backend/ai_contract/fake/generators.py:347-352 emits the free-form map and
    :342 the generic 'top_label_NNN' string), THIS DRAFT asserts the property
    so it lands RED against the fake. The red IS the generator fix (add a
    clip_classify softmax/literal path), per the plan: "land each divergence
    as (a) a fix, making a real assertion green... The branch ends green."
  * Where a plan cite is WRONG, this file cites the corrected line (dossier
    cite-corrections): the plan's backend/models/llm_response.py does NOT
    exist — the file is backend/api/schemas/llm_response.py (field :393 and
    coerce_risk_score :436 are EXACT there).

DRIVING SHAPES (dossier mechanics Q1b/Q4/Q5, verified there):
  * fake    — create_fake_app() driven over httpx.ASGITransport; when the
              registry record is needed: register_provider(ProviderId.FAKE,
              fake_provider_ops(), OPERATIONS) IN-TEST — the fake is NOT
              registered at import (backend/ai_contract/providers.py module
              docstring). Its callables are uniform async fn(payload=None)->dict
              (fake/app.py:109-127) but this file drives the app directly,
              mirroring test_fake_provider.py:101-112.
  * gateway — the FIVE adapter routers with their PRODUCTION prefixes
              (ai/gateway/main.py:181-185: /yolo26 /clip /florence
              /enrichment /enrich-lt) onto one FastAPI app; ALL FIVE
              module-level get_triton_client names patched (five distinct
              from-import sites — adapters/yolo26.py:28, enrichment.py:31,
              enrichment_light.py:30, florence.py:39, clip.py:40; patching the
              original in ai.gateway.triton_client hits NONE of them,
              dossier Q2). Template: ai/gateway/tests/
              test_adapters_yolo26.py:98-104, extended with the clip
              text-encoder patches of ai/gateway/tests/test_adapters_clip.py:88-101.
  * gateway_light — the SAME enrichment_light router ALONE at /enrich-lt: the
              full app cannot express "gateway_light's column lacks every /clip
              op" as a 404, because the clip router answers on the full app —
              the mounted routers ARE the provider's availability surface, so
              absence is graded against a light-only app.
  * per_model_http / llamacpp_llm — MATRIX-GUARD ONLY: set(rec.operations())
              vs the slot column (equality; subset for llamacpp's
              evidence-derived set) and rec.deployed. Never network — the
              registered callables are unbound client methods / live httpx
              closures (dossier Q1a/Q5). This suite NEVER INVOKES
              registered_providers()['gateway'].operations() callables.
  * absent ops — registry absence AND (app-driven) a real 404. Green guards,
              never skips.

UNIT-NORM TOLERANCE: abs_tol=1e-5, NOT 1e-9 — ai/clip/model.py:801-804 divides
by (norm + 1e-8) so the legacy server's true norm is ~1-1e-8; the fake's
override generator is exact (fake/generators.py:173-177, :242-244); the
gateway's ai/gateway/utils.py l2_normalize (:172-184) is epsilon-FREE and
returns the RAW vector when norm < 1e-12 (:182-183) — 1e-5 absorbs the legacy
epsilon but still catches an unnormalized vector.
"""

from __future__ import annotations

import ast
import base64
import contextlib
import io
import math
import re
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from backend.ai_contract.operations import OPERATIONS
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
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_DIR = REPO_ROOT / "backend" / "ai_contract" / "schemas"

# ---------------------------------------------------------------------------
# numeric-invariant op subsets of the registry (ids/methods/paths verified
# live against OPERATIONS; UNVERIFIED only in the sense that registry drift
# must re-run this file)
# ---------------------------------------------------------------------------
CLASSIFY_OPS = ("clip_classify",)
RANGE_OPS = ("clip_similarity", "clip_anomaly_score", "clip_batch_similarity")
# ops whose RESPONSE this cluster grades numerically (fake + gateway):
NUMERIC_OPS = ("clip_embed", "enrich_lt_person_reid", *CLASSIFY_OPS, *RANGE_OPS)

# Production mounts (ai/gateway/main.py:181-185, verified). This cluster needs
# /clip and /enrich-lt; carry all five (dossier Q5) so sibling clusters merge
# into one app/fixture set.
GATEWAY_MOUNTS: tuple[tuple[str, str], ...] = (
    ("ai.gateway.adapters.yolo26", "/yolo26"),
    ("ai.gateway.adapters.clip", "/clip"),
    ("ai.gateway.adapters.florence", "/florence"),
    ("ai.gateway.adapters.enrichment", "/enrichment"),
    ("ai.gateway.adapters.enrichment_light", "/enrich-lt"),
)

# Dossier Q2: five DISTINCT module-level names; patching one adapter silently
# leaves the other four on the real gRPC Triton client.
GATEWAY_PATCH_TARGETS: tuple[str, ...] = tuple(
    f"{module}.get_triton_client" for module, _prefix in GATEWAY_MOUNTS
)

# provider id -> matrix slot (backend/ai_contract/provider.py PROVIDER_SLOT,
# dossier Q7; PER_MODEL_HTTP and LLAMACPP_LLM share the union slot
# 'per_model_server' — the WP8.1 union-slot rule)
SLOT_OF = {
    "gateway": "gateway",
    "gateway_light": "enrichment_light_adapter",
    "per_model_http": "per_model_server",
    "llamacpp_llm": "per_model_server",
    # discovery fix: the loop below reaches the fake too (it joins the
    # registry in-test); its slot column is the 38 ops it registers against.
    "fake": "fake",
}

# the label set the classify tests REQUEST (the property is "a softmax over
# EXACTLY the requested labels" — dossier N2a)
CLASSIFY_LABELS = ["person", "dog", "car"]


# ---------------------------------------------------------------------------
# canned vectors / payloads — deterministic and MODULE-LEVEL so the exact
# value behind every prediction below is greppable, not fixture-order
# dependent. The runtime predictions (sum 1.3106 etc.) were pulled once with
# `.venv/bin/python` + generators.generate(); UNVERIFIED under pytest.
# ---------------------------------------------------------------------------


def _canned_vision_embedding() -> np.ndarray:
    """Canned 768-dim vision output shaped as the clip adapter consumes it:
    ai/gateway/adapters/clip.py:295-297 reads result["pooler_output"][0]
    .tolist() then l2_normalize()s it — the ADAPTER DOES NORMALIZE
    (dossier N1a; this pins that fact). Deliberately NOT pre-normalized (norm
    ~3*sqrt(768)) so the /embed unit-norm assertion actually grades the
    adapter's normalize step (ai/gateway/utils.py:172-184)."""
    rng = np.random.RandomState(42)
    return (rng.randn(1, 768) * 3.0).astype(np.float32)


def _canned_reid_embedding() -> np.ndarray:
    """Canned 512-dim OSNet output (same [0] row indexing at
    adapters/enrichment_light.py:440) with norm ~2.5*sqrt(512), so the
    inline >1e-8-guarded normalization at enrichment_light.py:443-445 is
    what produces the unit vector the N1a test asserts."""
    rng = np.random.RandomState(7)
    return (rng.randn(1, 512) * 2.5).astype(np.float32)


def _canned_infer(inputs: dict[str, Any], model_name: str = "", **kw: Any) -> dict[str, Any]:
    """AsyncMock side_effect dispatching by model name — vision ('clip',
    adapters/clip.py:48 VISION_MODEL_NAME) vs reid ('reid',
    adapters/enrichment_light.py:436). Name-dispatch (not per-test
    return_value mutation) keeps the shared mock fixed for every test."""
    if model_name == "reid":
        return {"embedding": _canned_reid_embedding()}
    return {"pooler_output": _canned_vision_embedding()}


def _make_text_embeddings(texts: list[str]) -> np.ndarray:
    """Deterministic per-text L2-normalized 768-dim rows for the clip text
    fallback (patched in as _encode_texts_siglip, priority-2 at
    adapters/clip.py:360-366). Same idea as ai/gateway/tests/
    test_adapters_clip.py:75-84, but seeded by text CONTENT, not hash() —
    hash() is PYTHONHASHSEED-random per process, so those fixtures' scores are
    not reproducible; ours are."""
    import hashlib

    rows = []
    for text in texts:
        seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
        v = np.random.RandomState(seed).randn(768).astype(np.float32)
        rows.append(v / (np.linalg.norm(v) + 1e-8))
    return np.stack(rows)


def _b64_png(width: int = 224, height: int = 224) -> str:
    from PIL import Image

    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# built once at import (~ms PIL; the gateway adapters decode + preprocess it —
# ai/gateway/utils.py decode_base64_image (:17) + preprocess_clip (:102-126)
# expect uint8 RGB (H,W,3))
_B64_IMAGE = _b64_png()


# Gateway request payloads. Gateway request models verified: EmbedRequest
# {image} at ai/gateway/adapters/clip.py:209-210; ClassifyRequest {image,
# labels, use_ensemble, camera_type} :218-222; SimilarityRequest {image,text}
# (~:231-234); AnomalyScoreRequest {image, baseline_embedding} :252-254;
# BatchSimilarityRequest {image, texts} :242-244; reid BBoxRequest {image
# (alias image_base64), bbox?} at adapters/enrichment_light.py:60-69
# (populate_by_name=True accepts the field name; extras ignored).
def _gateway_payload(op_id: str) -> dict[str, Any]:
    if op_id == "clip_embed":
        return {"image": _B64_IMAGE}
    if op_id == "clip_classify":
        return {"image": _B64_IMAGE, "labels": CLASSIFY_LABELS}
    if op_id == "clip_similarity":
        return {"image": _B64_IMAGE, "text": "a person near the fence"}
    if op_id == "clip_anomaly_score":
        # 768-dim REQUIRED or the adapter 400s first (clip.py:503-507);
        # [0.1]*768 is fine unnormalized — _cosine_similarity divides by both
        # norms (clip.py:303-311). (Yes: this is the N1b mislabeled literal —
        # the gateway is exactly the surface that tolerates it.)
        return {"image": _B64_IMAGE, "baseline_embedding": [0.1] * 768}
    if op_id == "clip_batch_similarity":
        return {"image": _B64_IMAGE, "texts": ["a person", "a dog"]}
    if op_id == "enrich_lt_person_reid":
        return {"image": _B64_IMAGE}
    raise AssertionError(f"no gateway payload for {op_id}")


# Fake payloads. The fake parses bodies ONLY for echo fields
# (backend/ai_contract/fake/app.py:71-80) — these documents exist so a future
# echo-driven fake still receives contract-shaped requests.
def _fake_payload(op_id: str) -> dict[str, Any]:
    payload: dict[str, Any] = {"image_base64": "ZmFrZS1pbWFnZQ=="}
    if op_id == "clip_classify":
        payload["labels"] = CLASSIFY_LABELS
    elif op_id == "clip_similarity":
        payload["text"] = "a person near the fence"
    elif op_id == "clip_anomaly_score":
        payload["baseline_embedding"] = [0.1] * 768
    elif op_id == "clip_batch_similarity":
        payload["texts"] = ["a person", "a dog"]
    return payload


async def _drive(provider_id: str, client: AsyncClient, op_id: str) -> dict[str, Any]:
    """THE single request path for every app-driven provider (the plan's
    'same assertions, every provider' reduced to one helper)."""
    op = OPERATIONS[op_id]
    payload = _fake_payload(op_id) if provider_id == "fake" else _gateway_payload(op_id)
    r = await client.request(op.method, op.path, json=payload)
    assert r.status_code == 200, f"{provider_id}/{op_id}: {r.status_code} {r.text[:200]}" + (
        ""
        if provider_id == "fake"
        else " — check the five get_triton_client patch targets (dossier "
        "Q2) and the clip text-encoder fallback patches"
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


@pytest.fixture(scope="module")
def gateway_app() -> FastAPI:
    """Five adapter routers, production prefixes, one app, so Operation.path
    values (prefix already included — dossier Q7) route. Importing ai.gateway.*
    pulls torch via adapters/clip.py:36; CPU wheel, import verified rc=0
    ~1.6s (dossier Q3) — UNVERIFIED against the global 5s pytest-timeout
    (pyproject.toml:495) for the first test that pays it."""
    import importlib

    app = FastAPI()
    for module, prefix in GATEWAY_MOUNTS:
        app.include_router(importlib.import_module(module).router, prefix=prefix)
    return app


@pytest.fixture(scope="module")
def gateway_light_app() -> FastAPI:
    """The enrichment_light router ALONE at /enrich-lt — gateway_light's whole
    column is enrich_lt_* (5 ops, dossier Q5), so /clip paths legitimately 404
    here while the SAME patched mock still serves /enrich-lt/person-reid."""
    from ai.gateway.adapters.enrichment_light import router as light_router

    app = FastAPI()
    app.include_router(light_router, prefix="/enrich-lt")
    return app


def _mock_triton() -> AsyncMock:
    """AsyncMock with .infer/.is_model_ready/.get_model_metadata (template:
    ai/gateway/tests/test_adapters_yolo26.py:76-87). is_model_ready=False
    forces the clip adapter onto its priority-2 text path
    (adapters/clip.py:360-366), whose encoder we patch below — no tokenizer,
    no SigLIP weights, no network."""
    mock = AsyncMock()
    mock.infer = AsyncMock(side_effect=_canned_infer)
    mock.is_model_ready = AsyncMock(return_value=False)
    mock.get_model_metadata = AsyncMock(return_value={})
    return mock


async def _patched_http(app: FastAPI, patch_targets: tuple[str, ...]) -> AsyncIterator[AsyncClient]:
    mock_triton = _mock_triton()
    with contextlib.ExitStack() as tx:
        # ALL named targets patched — one missed module = a silent real gRPC
        # connect attempt (dossier Q2 divergence).
        for target in patch_targets:
            tx.enter_context(patch(target, return_value=mock_triton))
        # clip text-encoder fallback, per ai/gateway/tests/
        # test_adapters_clip.py:88-101 (module-scoped names; harmless no-op
        # for apps that never hit /clip). autospec (WP4.2 ratchet): the
        # side_effect mirrors _encode_texts_siglip's (list[str]) -> ndarray
        # signature, clip.py:177.
        tx.enter_context(
            patch(
                "ai.gateway.adapters.clip._ensure_text_encoder",
                return_value=True,
                autospec=True,
            )
        )
        tx.enter_context(
            patch(
                "ai.gateway.adapters.clip._encode_texts_siglip",
                side_effect=_make_text_embeddings,
                autospec=True,
            )
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            yield client


@pytest.fixture
async def fake_http(fake_app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=fake_app), base_url="http://fake") as client:
        yield client


@pytest.fixture
async def gateway_http(gateway_app) -> AsyncIterator[AsyncClient]:
    async for client in _patched_http(gateway_app, GATEWAY_PATCH_TARGETS):
        yield client


@pytest.fixture
async def gateway_light_http(gateway_light_app) -> AsyncIterator[AsyncClient]:
    async for client in _patched_http(
        gateway_light_app, ("ai.gateway.adapters.enrichment_light.get_triton_client",)
    ):
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
        async for client in _patched_http(app, GATEWAY_PATCH_TARGETS):
            yield provider_id, client
    else:  # pragma: no cover - table guard
        raise AssertionError(f"provider_client: unhandled id {provider_id!r}")


# every app-driven property test parametrizes over exactly this
PROVIDER_PARAMS = ["fake", "gateway"]


# ---------------------------------------------------------------------------
# N1a — CLIP/reid embeddings: fixed dim AND L2 unit norm (epsilon story)
# ---------------------------------------------------------------------------


class TestN1aEmbeddingsUnitNorm:
    """N1a source (dossier N1a): ai/clip/model.py:801-804 epsilon=1e-8
    normalize inside extract_embedding (def :762); EMBEDDING_DIMENSION=768 at
    ai/clip/model.py:227. Gateway normalizes via ai/gateway/utils.py:172-184
    l2_normalize — epsilon-FREE, RAW passthrough when norm<1e-12 at :182-183 —
    called at ai/gateway/adapters/clip.py:297 (PIN: the clip adapter DOES
    normalize). reid adapter normalizes inline behind a >1e-8 guard at
    adapters/enrichment_light.py:443-445."""

    # fake: GREEN — semantic overrides ('unit_embedding', 768) for clip_embed
    #   and ('unit_embedding', 512) + ('const', 512) for enrich_lt_person_reid
    #   at backend/ai_contract/fake/generators.py:242-244; _unit_embedding
    #   (generators.py:173-177) is exact unit norm. Live-pulled: clip_embed
    #   len 768 norm 1.0; person_reid len 512 dim 512 norm 1.0. UNVERIFIED.
    # gateway: GREEN — the adapters normalize the canned non-unit vectors
    #   above; a norm<1e-12 input would leak RAW (utils.py:182-183) and trip
    #   abs_tol=1e-5. UNVERIFIED.
    @pytest.mark.parametrize("provider_client", PROVIDER_PARAMS, indirect=True)
    async def test_N1a_embeddings_are_fixed_dim_and_unit_norm(self, provider_client) -> None:
        provider_id, client = provider_client
        expected_dim = {"clip_embed": 768, "enrich_lt_person_reid": 512}
        for op_id in ("clip_embed", "enrich_lt_person_reid"):
            body = await _drive(provider_id, client, op_id)
            emb = body["embedding"]
            # length is the schema-visible half (768: ai/clip/model.py:227 +
            # adapters/clip.py:50; 512: OSNET_EMBEDDING_DIM,
            # backend/services/osnet_loader.py:41)...
            assert len(emb) == expected_dim[op_id], (
                f"{provider_id}/{op_id}: len={len(emb)} != {expected_dim[op_id]}"
            )
            # ...unit L2 norm is the half NO committed response schema
            # declares (backend/ai_contract/schemas/clip_embed.response.json
            # items are bare {"type": "number"}) — precisely what a provider
            # swap breaks silently, and what none of the repo's 145 fixed-dim
            # test literals ever checked (see TestN1b).
            norm = math.sqrt(sum(x * x for x in emb))
            assert abs(norm - 1.0) <= 1e-5, (
                f"{provider_id}/{op_id}: L2 norm {norm!r} is not unit "
                "(tol 1e-5, NOT 1e-9 — legacy ai/clip/model.py:801-804 "
                "epsilon yields 1-~1e-8; gateway utils.py:182-183 returns the "
                "RAW vector when norm<1e-12, which this also catches)"
            )

    # fake: GREEN — embedding_dimension is ('const', 512) (generators.py:244).
    # gateway: GREEN — adapters/enrichment_light.py:449-451 sets
    #   embedding_dimension=len(embedding): the self-report equals the vector
    #   BY CONSTRUCTION there; that construction is the property a swap could
    #   break (an osnet-padded provider could report the pre-pad dim).
    #   UNVERIFIED.
    @pytest.mark.parametrize("provider_client", PROVIDER_PARAMS, indirect=True)
    async def test_N1a_person_reid_declared_dim_matches_vector(self, provider_client) -> None:
        provider_id, client = provider_client
        body = await _drive(provider_id, client, "enrich_lt_person_reid")
        assert body["embedding_dimension"] == len(body["embedding"]), (
            f"{provider_id}: declared dim {body['embedding_dimension']} != "
            f"vector len {len(body['embedding'])} — the reid op is the 512 "
            "column of the dim-confusion matrix (TestN5DimConfusion)"
        )


# ---------------------------------------------------------------------------
# N1b — the repo's fixed-dim test literals are NON-unit: this suite is the
# FIRST unit-norm assertion anywhere (anti-pin; property about the TEST
# CORPUS, not a provider — dossier providers: matrix-only)
# ---------------------------------------------------------------------------


class TestN1bLegacyLiteralsAreNotUnitNorm:
    """N1b source (dossier N1b, cites verified): backend/tests/integration/
    test_enrichment_pipeline.py:384
        test_embedding = [0.1] * 768  # Normalized CLIP embedding
    true L2 norm 0.1*sqrt(768) = 2.771. Spot sites:
    test_vision_extraction_pipeline.py:877,:922; test_scene_baseline.py:181;
    test_enrichment_models.py:502 ([0.1]*512). PLAN CITE CORRECTION (dossier):
    the '87 literals' count does NOT reproduce — the actual census is 145
    lines matching `[0.1] *` and 125 lines mentioning 768 under
    backend/tests — but the CORE claim is true: zero of them assert unit norm
    (every np.linalg.norm hit normalizes a fixture before use, e.g.
    test_osnet_loader.py:71). This suite's N1a assertions are therefore the
    FIRST, and the fake's exact-unit outputs diverge from every legacy fixture
    by design (the dossier's mock-vs-real numeric mismatch)."""

    # no provider (characterization). fake n/a, gateway n/a. Predicted GREEN
    # (pure math + file read). UNVERIFIED under pytest.
    def test_N1b_canonical_literal_norm_is_2_77_not_1(self) -> None:
        v = [0.1] * 768
        norm = math.sqrt(sum(x * x for x in v))
        assert abs(norm - 1.0) > 1.0, (
            f"[0.1]*768 norm={norm!r}: if this ever reads ~1, someone fixed "
            "the literal — then N1a's unit-norm provider property stops "
            "contradicting the fixture corpus and this anti-pin must be "
            "rewritten against the NEW canonical literal."
        )
        # cite-pinned drift guard: the literal and its WRONG comment must
        # still sit at the dossier's line (line churn = the census claim needs
        # re-running against the new corpus).
        lines = (
            (REPO_ROOT / "backend/tests/integration/test_enrichment_pipeline.py")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        assert "[0.1] * 768" in lines[383] and "Normalized CLIP embedding" in lines[383], (
            f"test_enrichment_pipeline.py:384 drifted: {lines[383]!r}"
        )


# ---------------------------------------------------------------------------
# N2a — /classify scores = softmax over EXACTLY the requested labels:
# keys == labels, sum == 1.0, top_label is a member
# ---------------------------------------------------------------------------


class TestN2aClassifySoftmaxOverRequestedLabels:
    """N2a source (dossier N2a): legacy CLIP server ai/clip/model.py classify()
    def :875, torch.softmax(logits_per_image, dim=-1) :919, scores =
    dict(zip(labels, ...)) :925, top_label = labels[argmax] :928. Gateway:
    manual softmax exp(s - s.max())/(sum + 1e-8) at
    ai/gateway/adapters/clip.py:427-428, round(·, 6) at :430, top_label =
    labels[argmax] :431-432.
    fake output (live-pulled from generators.generate('clip_classify')):
        scores {'alpha': 0.5655, 'bravo': 0.7451}   (sum 1.3106; keys ignore
        the request)   top_label 'top_label_544'
    — all three properties below VIOLATED (dossier N2a divergence:
    clip_classify is absent from _LITERAL_OPS at generators.py:490-498, so it
    is WALKED; the free-form-object branch :347-352 and string generator :342
    produce exactly this).

    RESOLVED (discovery run 2026-09-19, red count 11/422): the fake now
    softmaxes over payload labels — generators._softmax_over_labels, seeded
    from the labels so byte-identity holds; payload None keeps the walked
    shape (WP8.2 direct-generate path). fake GREEN."""

    # fake: GREEN post-fix (_softmax_over_labels picks labels[argmax]).
    # gateway: GREEN (top_label chosen from request.labels, clip.py:431-432).
    @pytest.mark.parametrize("provider_client", PROVIDER_PARAMS, indirect=True)
    async def test_N2a_classify_top_label_is_a_requested_label(self, provider_client) -> None:
        provider_id, client = provider_client
        body = await _drive(provider_id, client, "clip_classify")
        assert body["top_label"] in CLASSIFY_LABELS, (
            f"{provider_id}: top_label {body['top_label']!r} not among the "
            f"REQUESTED labels {CLASSIFY_LABELS} — the softmax-over-"
            "requested-labels contract (ai/clip/model.py:925-928). Known fake "
            "cause: generic string generator 'top_label_NNN' "
            "(backend/ai_contract/fake/generators.py:342)."
        )

    # fake: PREDICTED RED (scores keyed {alpha, bravo} regardless of request —
    #   dossier N2a; pred_red_fake). gateway: GREEN (dict keyed over
    #   request.labels, clip.py:430). UNVERIFIED.
    @pytest.mark.parametrize("provider_client", PROVIDER_PARAMS, indirect=True)
    async def test_N2a_classify_scores_keyed_by_requested_labels(self, provider_client) -> None:
        provider_id, client = provider_client
        body = await _drive(provider_id, client, "clip_classify")
        assert set(body["scores"]) == set(CLASSIFY_LABELS), (
            f"{provider_id}: score keys {sorted(body['scores'])} != the "
            "requested labels — downstream thresholds are PER-LABEL "
            "(two confidence tables filter the stream by class name), so a "
            "provider keying scores anything else silently shifts every "
            "threshold with no schema noticing."
        )

    # fake: PREDICTED RED (alpha+bravo sum 1.3106 — no tolerance saves it;
    #   pred_red_fake → generator fix). gateway: GREEN at abs=1e-4 — the
    #   round(·,6) at adapters/clip.py:430 costs ≤ n_labels*5e-7 (1.5e-6 for
    #   3 labels); NEVER assert == 1.0 exactly (dossier N2b forbids it).
    #   UNVERIFIED.
    @pytest.mark.parametrize("provider_client", PROVIDER_PARAMS, indirect=True)
    async def test_N2a_classify_scores_sum_to_one(self, provider_client) -> None:
        provider_id, client = provider_client
        body = await _drive(provider_id, client, "clip_classify")
        total = sum(body["scores"].values())
        assert abs(total - 1.0) <= 1e-4, (
            f"{provider_id}: scores sum {total!r} — /classify is a SOFTMAX "
            "over the labels (torch.softmax ai/clip/model.py:919; gateway "
            "manual exp/sum adapters/clip.py:427-428). tol 1e-4 ONLY for the "
            "gateway's 6dp rounding; a SigLIP sigmoid-head provider returns "
            "INDEPENDENT per-label probs that do not sum to 1 (plan N2b) — "
            "this is the assertion that catches that swap."
        )


# ---------------------------------------------------------------------------
# N2b — the gateway ALREADY swapped CLIP ViT-L for SigLIP-2 at 768 dims yet
# still presents a softmax contract — pin the adapter behavior
# ---------------------------------------------------------------------------


class TestN2bGatewaySigLipStillSoftmax:
    """N2b source (dossier N2b): ai/triton/model_repository/clip/config.pbtxt
    :1-2 'SigLIP 2 Base ... Replaces CLIP ViT-L/14', output dims [768] at
    :22-25. The gateway never surfaces SigLIP's sigmoid head: it does its own
    dot + manual softmax at adapters/clip.py:423-427, and the
    response_model=ClassifyResponse is bare pydantic (clip.py:225-229) — the
    schema is SILENT; only the number catches drift. Gateway-specific red
    prediction: NONE (softmax holds; sum off-by ≤ 4*5e-7 at round-6dp —
    dossier: 'passes except exact-equality'). fake: n/a here (covered by N2a).
    UNVERIFIED."""

    async def test_N2b_gateway_classify_sum_survives_siglip_swap(self, gateway_http) -> None:
        r = await gateway_http.post(
            "/clip/classify", json={"image": _B64_IMAGE, "labels": ["a", "b", "c", "d"]}
        )
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert set(body["scores"]) == {"a", "b", "c", "d"}
        assert abs(sum(body["scores"].values()) - 1.0) <= 1e-4, body["scores"]
        assert body["top_label"] in {"a", "b", "c", "d"}


# ---------------------------------------------------------------------------
# N3 — similarity ∈ [-1,1], anomaly_score ∈ [0,1]: value ranges PLUS which
# layer actually ENFORCES them (pydantic ge/le vs bare floats vs schema none)
# ---------------------------------------------------------------------------


class TestN3RangesAndConstraintPresence:
    """N3 source (dossier N3): legacy server ai/clip/model.py
    AnomalyScoreResponse anomaly_score ge=0.0/le=1.0 at :359-361 and
    similarity_to_baseline ge=-1.0/le=1.0 at :362-364; anomaly clamped
    max(0,min(1,1-sim)) at :869 with inputs re-normalized at :855-859.
    Backend consumer schema backend/api/schemas/baseline.py:225-228
    AnomalyEvent.anomaly_score ge=0/le=1. backend/api/schemas/reid.py:91
    SimilarityMatch.similarity ge=0/le=1 — NON-negative, NARROWER than the
    [-1,1] cosine math (dossier N3: same quantity, two contracts).
    GAP (the finding): the gateway's OWN response models are bare floats —
    SimilarityResponse.similarity at ai/gateway/adapters/clip.py:237-238,
    AnomalyScoreResponse at :257-260, BatchSimilarityResponse :247-248 — and
    its _cosine_similarity (:303-311, float32 dot) can exceed 1.0 (no
    epsilon) or 0.0-out zero-vectors with nothing schema-side to refuse:
    a float32 dot >1.0 would 500 the legacy server (pydantic le=1.0) but
    SAILS THROUGH the gateway."""

    # fake: GREEN TRIVIALLY — the generic number walker emits U(0.1,0.9),
    #   never negative (generators.py:336; live-pulled: similarity 0.1088,
    #   anomaly 0.2454 / similarity_to_baseline 0.5448, batch {alpha 0.7339,
    #   bravo 0.8299}). Dossier warning stands: the fake MASKS out-of-range
    #   bugs — green here is no evidence about ranges. UNVERIFIED.
    # gateway: GREEN for the canned vectors — unit-vs-unit float32 dot of
    #   INDEPENDENT random 768-rows lands near 0, so the >1.0 hazard is not
    #   reproducible with isotropic fixtures (it needs near-parallel float32
    #   unit rows); the clamp at clip.py:514 keeps anomaly in [0,1] by
    #   construction. The hazard itself is pinned only by the constraint-
    #   asymmetry characterization below. UNVERIFIED.
    @pytest.mark.parametrize("provider_client", PROVIDER_PARAMS, indirect=True)
    async def test_N3_similarity_and_anomaly_within_mathematical_range(
        self, provider_client
    ) -> None:
        provider_id, client = provider_client
        sim = (await _drive(provider_id, client, "clip_similarity"))["similarity"]
        assert -1.0 <= sim <= 1.0, f"{provider_id}: clip_similarity {sim!r} outside [-1,1]"
        anomaly_body = await _drive(provider_id, client, "clip_anomaly_score")
        assert 0.0 <= anomaly_body["anomaly_score"] <= 1.0, (
            f"{provider_id}: anomaly_score {anomaly_body['anomaly_score']!r} "
            "— legacy enforces ge=0/le=1 via pydantic (ai/clip/model.py:"
            "359-361); the gateway enforces it ONLY via the clamp at "
            "adapters/clip.py:514"
        )
        assert -1.0 <= anomaly_body["similarity_to_baseline"] <= 1.0, (
            f"{provider_id}: similarity_to_baseline {anomaly_body['similarity_to_baseline']!r}"
        )
        for text, s in (await _drive(provider_id, client, "clip_batch_similarity"))[
            "similarities"
        ].items():
            assert -1.0 <= s <= 1.0, f"{provider_id}: batch_similarity[{text!r}] {s!r}"

    # no provider — schema-presence characterization: the committed WP7.2
    # response snapshots are TYPE-ONLY, so the committed contract carries NO
    # range at all; the range lives only in producer pydantic — and only in
    # SOME producers. Predicted GREEN (snapshots read verbatim from
    # backend/ai_contract/schemas/). fake n/a, gateway n/a. UNVERIFIED.
    def test_N3_committed_contract_snapshots_declare_no_range(self) -> None:
        blob = "\n".join(
            (SCHEMA_DIR / f"{op}.response.json").read_text(encoding="utf-8") for op in RANGE_OPS
        )
        assert '"maximum"' not in blob and '"minimum"' not in blob, (
            "a range keyword appeared in the committed snapshots — N3's "
            "'schema can catch none of this' premise changed; promote the "
            "range checks into schema validation and cite the snapshot edit."
        )

    def test_N3_legacy_server_and_backend_schemas_carry_the_bounds(self) -> None:
        clip_src = (REPO_ROOT / "ai" / "clip" / "model.py").read_text(encoding="utf-8")
        assert "ge=-1.0, le=1.0" in clip_src, (
            "ai/clip/model.py similarity_to_baseline lost its ge=-1.0/le=1.0 "
            "(dossier cite :362-364) — the ONLY place [-1,1] is enforced"
        )
        assert "ge=0.0, le=1.0" in clip_src, (
            "ai/clip/model.py anomaly_score lost its ge=0.0/le=1.0 (cite :359-361)"
        )
        baseline_src = (REPO_ROOT / "backend/api/schemas/baseline.py").read_text(encoding="utf-8")
        assert "ge=0.0" in baseline_src and "le=1.0" in baseline_src, (
            "backend/api/schemas/baseline.py AnomalyEvent.anomaly_score "
            "constraint drifted (cite :225-228)"
        )
        reid_src = (REPO_ROOT / "backend/api/schemas/reid.py").read_text(encoding="utf-8")
        assert "ge=0.0" in reid_src, (
            "backend/api/schemas/reid.py:91 lost its ge=0.0 — NOTE the reid "
            "lane constrains cosine to NON-negative (ge=0/le=1), narrower "
            "than the [-1,1] the /clip endpoints promise (dossier N3)."
        )

    # characterization of the GAP (anti-pin on the gateway's bare response
    # models; dossier N3). Predicted GREEN — they ARE bare today; if someone
    # closes the gap this reds and must flip into a range-PRESENCE assertion.
    # fake n/a, gateway n/a (source read, no request). UNVERIFIED.
    def test_N3_gateway_response_models_are_still_bare_floats(self) -> None:
        src = (REPO_ROOT / "ai" / "gateway" / "adapters" / "clip.py").read_text(encoding="utf-8")
        for cls in ("SimilarityResponse", "BatchSimilarityResponse", "AnomalyScoreResponse"):
            body = re.search(rf"class {cls}\(BaseModel\):\n((?:[ \t].*\n|\n)+)", src)
            assert body, f"class {cls} missing from ai/gateway/adapters/clip.py"
            assert "le=1.0" not in body.group(1) and "ge=-1.0" not in body.group(1), (
                f"gateway {cls} now carries range constraints — the dossier "
                "N3 asymmetry (legacy ge/le vs gateway bare float) was CLOSED; "
                "flip this into a range-PRESENCE assertion and cite the fix."
            )
        assert "anomaly = max(0.0, min(1.0, 1.0 - sim))" in src, (
            "gateway anomaly clamp (adapters/clip.py:514) changed formula — it "
            "is the ONLY thing keeping anomaly_score in [0,1] on the gateway"
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
        BEFORE-validator coerce_risk_score at :434-460: float → int(v)
        TRUNCATES; str → int(float(v)); ge/le runs AFTER coercion, so
        out-of-range still raises.
      L3 Postgres CHECK ck_events_risk_score_range
        'risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)' at
        backend/models/event.py:241-243.
    RIVAL schema backend/api/schemas/llm.py LLMRiskResponse (class :227,
    Annotated int ge=0 le=100 at :288) has a DIFFERENT before-validator at
    :305-326 that CLAMPS (150→100, -10→0; 'return max(0, min(100, score))'
    at :326) instead of rejecting, plus a model-validator that REWRITES
    risk_level from the coerced score (:371-415 region)."""

    # All four tests: no provider drives them — contract-layer
    # characterization (fake/gateway n/a for the pydantic layers; the fake's
    # llm ops are chat-completion snapshots whose response schemas carry NO
    # risk_score at all — llm_completion.response.json = {content,
    # tokens_predicted}). Dossier runtime-verified (0.5→0 both schemas;
    # llm_response 150 raises; llm.py 150→100) AND re-probed once-shot while
    # drafting this file. UNVERIFIED under pytest. The dossier's suite-side
    # warning is why there is NO parametrized "provider risk_score in
    # [0,100]" assertion here: the fake's generic int walker emits U[1,8]
    # ints that read as plausible risk scores and catch nothing.

    # Runtime-probed: LLMRiskResponse(risk_score=0.5).risk_score == 0 and
    # '0.5' → 0 on llm_response.py. Predicted GREEN.
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
            "str '0.9' → int(float('0.9')) == 0 (llm_response.py:453-457) — "
            "stringly risk payloads truncate identically"
        )

    # Runtime-probed: strict REJECTS 150 (ValidationError); rival CLAMPS to
    # 100; rival 0.75/'high' → (0, RiskLevel.LOW) — the level rewritten from
    # the coerced score (llm.py model-validator :371-415). Predicted GREEN.
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
            f"risk_level 'high' rewritten from the coerced score → "
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
# N5 — competing dimensionalities with THREE inconsistent failure modes
# (raise / dead-default + silent 0.0 / silent pad) + the per-provider dim
# matrix as green guards
# ---------------------------------------------------------------------------


class TestN5DimConfusion:
    """N5 source (dossier N5a/N5b/N5c/N5d):
      N5a backend/services/scene_baseline.py:260-263 (update_baseline) and
        :327-330 (set_baseline) RAISE InvalidEmbeddingError (class :75) unless
        len == EMBEDDING_DIMENSION (768, :47).
      N5b reid_matcher: DEFAULT_EMBEDDING_DIMENSION = 512 at :57 is DEAD
        (dossier grep: no consumer — the plan's 'defaults 512' mode is FALSE);
        store records len(embedding) verbatim (:312-313) and
        ReIDMatcher._cosine_similarity (:244) SILENTLY returns 0.0 for unequal
        lengths (:255-256).
      N5c backend/services/osnet_loader.py:347-358 SILENTLY truncates
        (flatten()[:512] at :350) / zero-PADs to OSNET_EMBEDDING_DIM=512
        (:41; np.pad :353-355) and re-normalizes the mangled vector
        (:360-363); batch path duplicates at :446-453.
      N5d backend/models/face_identity.py:116: 'Stores 512-dimensional
        ArcFace embeddings' is DOCSTRING only — no validator rejects 768-dim
        faces (dimension is convention, not constraint).
    Provider-side (assertable per provider from driven responses): the dim
    matrix clip_embed=768 vs enrich_lt_person_reid=512."""

    # fake: GREEN — overrides pin 768 vs 512 exactly (generators.py:242-244);
    #   the fake NEVER exercises osnet's pad branch (dossier N5c divergence:
    #   it always returns exact 512). UNVERIFIED.
    # gateway: GREEN — the clip adapter 500s on any len != 768
    #   (adapters/clip.py:385-389) and reid reports len(embedding); with the
    #   canned 768/512 rows both answer at their slot's dim. UNVERIFIED.
    @pytest.mark.parametrize("provider_client", PROVIDER_PARAMS, indirect=True)
    async def test_N5_provider_dims_are_the_distinct_slots(self, provider_client) -> None:
        provider_id, client = provider_client
        clip_emb = (await _drive(provider_id, client, "clip_embed"))["embedding"]
        reid_body = await _drive(provider_id, client, "enrich_lt_person_reid")
        assert len(clip_emb) == 768
        assert len(reid_body["embedding"]) == 512
        assert len(clip_emb) != len(reid_body["embedding"]), (
            f"{provider_id}: clip and reid collapsed to ONE dimensionality — "
            "cross-space cosines would start LOOKING comparable instead of "
            "silently scoring 0.0 (reid_matcher.py:255-256). Dims differ per "
            "op per schema: clip 768 (schemas/clip_embed.response.json + "
            "adapter clip.py:50), reid 512 (schemas/enrich_lt_person_reid."
            "response.json + osnet :41)."
        )

    # backend-internal (matrix-only in the dossier — no provider drives it).
    # Runtime-probed once-shot while drafting: SceneBaselineService(
    # redis_client=None) constructs (guard runs BEFORE any redis use —
    # :260/:327 are the first statements after the docstring) and both calls
    # raise InvalidEmbeddingError. Import cost 3.09s probe — UNVERIFIED
    # against the 5s tier for the first payer. Predicted GREEN.
    async def test_N5a_scene_baseline_raises_on_wrong_dim(self) -> None:
        from backend.services.scene_baseline import InvalidEmbeddingError, SceneBaselineService

        svc = SceneBaselineService(redis_client=None)
        with pytest.raises(InvalidEmbeddingError):
            await svc.set_baseline("cam-x", [0.1] * 512)  # guard at :327-330
        with pytest.raises(InvalidEmbeddingError):
            await svc.update_baseline("cam-x", [0.1] * 769)  # guard at :260-263

    # backend-internal. Runtime-probed: _cosine_similarity([0.1]*512,
    # [0.1]*768) == 0.0 exactly. Predicted GREEN. UNVERIFIED under pytest.
    def test_N5b_reid_matcher_dim_mismatch_is_silent_zero(self) -> None:
        from backend.services.reid_matcher import ReIDMatcher

        assert ReIDMatcher._cosine_similarity([0.1] * 512, [0.1] * 768) == 0.0, (
            "reid_matcher.py:255-256 returns 0.0 for unequal lengths — the "
            "plan's 'defaults 512' mode is FALSE (dossier N5b: "
            "DEFAULT_EMBEDDING_DIMENSION at :57 is a DEAD constant); a dim "
            "mistake in the reid lane reads as 'no match', never an error — "
            "the WORST of the three failure modes for swap readiness."
        )

    # backend-internal characterization via AST (the pad path needs model
    # weights to EXERCISE — the dossier ruled N5c cite-only; a source pin is
    # the honest drift-sensitive stand-in). torch imports live inside methods
    # (osnet_loader.py:108 lazy), but a weight-loaded run is not
    # one-shot-safe here — see file notes (left_out). Predicted GREEN.
    # UNVERIFIED.
    def test_N5c_osnet_loader_pads_and_truncates_to_512(self) -> None:
        src = (REPO_ROOT / "backend/services/osnet_loader.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        consts = {
            t.id: ast.literal_eval(n.value)
            for n in ast.walk(tree)
            if isinstance(n, ast.Assign)
            for t in n.targets
            if isinstance(t, ast.Name) and t.id == "OSNET_EMBEDDING_DIM"
        }
        assert consts.get("OSNET_EMBEDDING_DIM") == 512
        assert "embedding.flatten()[:OSNET_EMBEDDING_DIM]" in src, (
            "truncate path (osnet_loader.py:350) drifted"
        )
        assert "np.pad(" in src, "pad path (osnet_loader.py:352-355) drifted"
        # NOTE: the SILENT pad/truncate + re-normalize (:360-363, batch twin
        # :446-453) means an osnet-shaped provider emitting 256-dim rows gets
        # a zero-padded 512 vector nobody complained about — contrast N5a
        # (raise) and N5b (silent 0.0). Three modes, one pipeline (plan N5).

    # backend-internal characterization (dossier N5d: 512 is documentation +
    # service convention, not a constraint). Predicted GREEN (docstring
    # present, validators absent — the asymmetry IS the finding). UNVERIFIED.
    def test_N5d_face_identity_512_is_documentation_only(self) -> None:
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
    ('summary_NNN', generators.py:342) — invisible to any provider-
    parametrized assertion, hence a contract-layer characterization (dossier
    providers: matrix-only). Runtime-probed once-shot: 'x'*250 passthrough
    True. Predicted GREEN. UNVERIFIED under pytest."""

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
# never skips). per_model_http + llamacpp_llm appear ONLY here (hard rule:
# their registered callables do real network — dossier Q5 — never invoked).
# ---------------------------------------------------------------------------


class TestMatrixNumericSurface:
    """The availability half of every numeric op, for all five ids."""

    # Predicted GREEN for all five ids (the presence direction is already
    # import-time-enforced by register_provider; the per-op column fold and
    # the llamacpp equality-of-derived-subset are this test's own).
    # UNVERIFIED.
    def test_matrix_registered_op_set_matches_slot_column(self) -> None:
        from backend.ai_contract.fake import fake_provider_ops

        reg = registered_providers()
        # fake joins the registry the way the suite registers it (the fake is
        # NOT import-registered — providers.py docstring;
        # test_fake_provider.py:166-175 is the in-test precedent). Repeated
        # registration is idempotent: _PROVIDERS keys by ProviderId.value
        # (provider.py:244) and the write just replaces the record.
        reg["fake"] = register_provider(
            ProviderId.FAKE, fake_provider_ops(), OPERATIONS, deployed=True
        )
        for provider_id in ("gateway", "gateway_light", "per_model_http", "llamacpp_llm", "fake"):
            rec = reg[provider_id]
            slot = SLOT_OF[provider_id]
            column = set(operations_for_slot(slot, OPERATIONS))
            declared = set(rec.operations())  # READ the map, NEVER call it
            if provider_id == "llamacpp_llm":
                # union-slot rule: llamacpp declares its EVIDENCE-DERIVED
                # SUBSET ({llm_completion, llm_chat_completion}; providers.py
                # _llamacpp_required). Numeric ops are not its surface at all.
                assert declared <= column, provider_id
                assert not declared & set(NUMERIC_OPS), provider_id
                assert declared == {"llm_completion", "llm_chat_completion"}, provider_id
            else:
                assert declared == column, (
                    f"{provider_id}: declared {len(declared)} != slot {slot!r} column {len(column)}"
                )
            for op_id in NUMERIC_OPS:
                if provider_id == "llamacpp_llm":
                    # union-slot rule (asserted above): llamacpp declares the
                    # 2-op evidence subset ⊆ column, so per-op column EQUALITY
                    # is the wrong guard — it claims NO numeric op. Discovery
                    # fix: the drafted loop ran equality on this subset slot
                    # too and failed on clip_embed.
                    assert op_id not in declared, f"{provider_id}/{op_id}"
                else:
                    assert (op_id in declared) == (op_id in column), (
                        f"{provider_id}/{op_id}: presence disagrees with the column"
                    )

    # Predicted GREEN (providers.py _register_all: PER_MODEL_HTTP deployed
    # False — matrix-declared UNDEPLOYED; the rest True; fake registered
    # here with deployed=True). UNVERIFIED.
    def test_matrix_deployed_flags(self) -> None:
        reg = registered_providers()
        assert reg["per_model_http"].deployed is False
        assert reg["gateway"].deployed is True
        assert reg["gateway_light"].deployed is True
        assert reg["llamacpp_llm"].deployed is True

    # GREEN guard on the light-only app: gateway_light's column holds the 5
    # enrich_lt_* ops (person_reid among them) and NONE of the /clip numeric
    # ops; each /clip path answers a REAL 404 (plan procedure: absence must
    # MATCH the matrix — asserted, never skipped). The positive control on the
    # same app (200 + 512-dim reid) proves the 404s are ABSENCE, not a dead
    # mount. fake n/a; gateway_light predicted GREEN. UNVERIFIED.
    async def test_matrix_gateway_light_has_reid_not_clip(self, gateway_light_http) -> None:
        reg = registered_providers()
        light_ops = set(reg["gateway_light"].operations())
        assert "enrich_lt_person_reid" in light_ops
        for op_id in ("clip_embed", "clip_classify", "clip_similarity", "clip_anomaly_score"):
            assert op_id not in light_ops, f"gateway_light claims {op_id}"
            r = await gateway_light_http.request(
                OPERATIONS[op_id].method, OPERATIONS[op_id].path, json={}
            )
            assert r.status_code == 404, (
                f"gateway_light {op_id}: expected 404 (column says absent), got {r.status_code}"
            )
        r = await gateway_light_http.post("/enrich-lt/person-reid", json={"image": _B64_IMAGE})
        assert r.status_code == 200, r.text[:200]
        assert len(r.json()["embedding"]) == 512

"""WP8.4 — drive the six real backend AI clients through the FakeProvider.

INTEGRATED (2026-09-19): drafted under /tmp with a draft-only conftest (not
carried over — the repo tier gets ENVIRONMENT=test from
backend/tests/conftest.py:107 and the autouse settings-cache reset around
every test, so the autouse cache-clear below is redundant but harmless).
First in-tree pytest contact: 82 passed / 1 failed — the single failure was
the ONE predicted-red leg (pose keypoint shape), exactly the draft's
predicted-red list. Per the goal rule (branch stays GREEN; a RULING-blocked
finding is pinned as a characterization, never left red) that leg now
characterizes the shipped raise, so the module is 83/83 green in-tree.
Residual ``# UNVERIFIED:`` tags below mark claims the draft guessed that the
in-tree run has since confirmed or reframed; each names its own status.
There is **no xfail, no skip, no importorskip anywhere in this file** (goal
rule). Never respx: every hop is ``httpx.ASGITransport`` (goal rule; the fake
IS an app — backend/ai_contract/fake/app.py).

Plan: docs/superpowers/plans/2026-09-19-swap-readiness-72h.md §WP8.4
(lines 1001-1026). WP8.3 (test_conformance_geometry.py et al.) tested
providers; this tests the **other half** — the client parse methods — so the
two halves can no longer stay independently green. Done-when: "renaming a
response key in a contract model reddens a CLIENT test, not just a schema
snapshot" (:1024-1026). Satisfied structurally: every expected key is a
literal below (``_EXPECTED_CLIENT_OUTPUTS`` values were read from the ACTUAL
fake generators via a one-shot ``generate(op_id)`` dump at draft time, not
transcribed from schemas), and the rename-proof tests prove sensitivity by
deleting keys from a response copy / rewriting the served body.

=============================================================================
SEAMS USED PER CLIENT (point a client at the fake with ZERO production change)
=============================================================================
Every client builds its OWN persistent ``httpx.AsyncClient`` inside
``__init__`` (detector_client.py:321/:325, florence_client.py:368,
clip_client.py:152, enrichment_client.py:917/:919, nemotron_analyzer.py:404)
against a DNS name that does not exist here — so the seam is always
(a) get the right base_url in (constructor kwarg where one exists, else patch
the *module-level* ``get_settings`` name the client imported — patching
backend.core.config.get_settings would hit none of them; same trap as the
five-distinct ``get_triton_client`` lesson in
backend/tests/contracts/ai_providers/test_conformance_geometry.py:68-70) and
(b) swap the private pools onto the fake (``_http_client`` /
``_health_http_client``).

* DetectorClient        — NO base_url ctor kwarg (detector_client.py:262).
  Seam: patch ``backend.services.detector_client.get_settings`` (imported at
  :73; ``self._detector_url = settings.yolo26_url`` at :287) + swap pools.
* FlorenceClient        — ctor base_url (florence_client.py:309/:321) + swap
  ``_http_client`` (:368).
* CLIPClient            — ctor base_url (clip_client.py:99/:111) + swap
  ``_http_client`` (:152).
* EnrichmentClient      — ctor base_url/light_base_url (enrichment_client.py
  :838/:855/:865) are NOT sufficient: per-model ops resolve through
  ``_get_service_for_model`` (:928-943) → ``settings.get_enrichment_url_for_model``
  (backend/core/config.py:1432-1453), and ``self._settings`` is captured at
  ctor (:847). Seam: patch ``backend.services.enrichment_client.get_settings``
  with a Settings whose enrichment_url/enrichment_light_url are fake prefixes.
* NemotronAnalyzer      — no base_url kwarg; ``self._llm_url =
  settings.nemotron_url`` (nemotron_analyzer.py:336). Seam: patch
  ``backend.services.nemotron_analyzer.get_settings`` + swap pools.
* SceneOCRService (client-BYPASS site, plan :1011) — real ctor url kwarg
  (backend/services/scene_ocr_service.py:381) + LAZY pool (:387/:397-402):
  pre-seed ``svc._client`` with an ASGITransport client.
* nemotron_streaming.call_llm_streaming (client-BYPASS site, plan :1012) —
  builds its own client INSIDE the function (nemotron_streaming.py:96,
  ``httpx`` imported at module level :14). Seam: rebind the name ``httpx`` ON
  THE STREAMING MODULE (monkeypatch, auto-restored) to a shim that injects the
  transport. The real httpx module is never patched.

=============================================================================
CONTRACT FACTS THIS FILE RELIES ON (all read from the tree at HEAD a8c25c5e)
=============================================================================
* The fake mounts EXACTLY the 38 registry paths with no prefix
  (fake/app.py) — and the registry paths ALREADY carry the service prefixes
  (/florence/extract, /clip/embed, /enrichment/vehicle-classify,
  /enrich-lt/person-reid, /models/status, /object-distance, /completion,
  /yolo26/segment). The gateway mounts its five adapter routers under THE SAME
  prefixes (ai/gateway/main.py:181-185), so one base_url works against either
  app — that is what makes every gateway-vs-fake pair below legible.
* Service defaults (config.py:1373-1408): pose/threat/reid/pet/depth → LIGHT,
  vehicle/clothing/action/demographics → HEAVY. So per-model client legs hit
  /enrich-lt/* and the expected bodies are the LIGHT ops (their values DIFFER
  from the heavy ops — both were dumped).
* The fake performs NO request validation (it parses the body only to echo
  model_name) and always answers 200 on registry paths → it can never 422.
  Every 422/404 pin therefore drives the real gateway adapter routers, and the
  fake side of those tests pins the 200. The asymmetry IS the finding.
* The fake serves NO /health route (no registry op has one): every client
  health probe 404s against the bare fake (characterized for
  DetectorClient; for EnrichmentClient a /health shim route is added — see
  ``_health_aware_fake``).
* Deterministic fake values were dumped at draft time via
  ``backend.ai_contract.fake.generate(op_id)`` (profile "gateway"); the
  literals below are those dumps. A change to the generator seed logic reddens
  this file BY DESIGN — that is the point (fake ⇄ client lockstep).

Cites relied on (re-verify any that a rebase moves):
  plan §WP8.4 :1001-1026; Tier A table :769-800
  backend/ai_contract/operations.py (38 ops; availability flags; client_methods)
  backend/ai_contract/fake/{__init__.py,app.py,generators.py} (generate/snapshot)
  backend/services/detector_client.py:73,103,262,287,321,325,415,981,1032,1116,1177,1292,1310,1331-1336,1409,1424
  backend/services/florence_client.py:73(BoundingBox),309,321,368,561,582,727,749-752,881,980,998,1083,1102-1104,1189,1299,1411,1432-1434,1524,1543-1563
  backend/services/clip_client.py:54,99,111,152,332,352-366,488-493,512,680,700-701,830,983,1005
  backend/services/enrichment_client.py:838,847,855,865,917,928-943,1085-1133,1136-1149,1203,1216,1407,1613-1621,1626,1806,1945-1956,2013,2226-2241,2320,2443-2448,2620-2623,2782-2786,2944-2948,3048-3116,3161-3200,3253-3260,3285-3300
  backend/services/nemotron_analyzer.py:336,404,1003-1065,4257,4348
  backend/services/nemotron_streaming.py:14,83-92,96,99,104-116
  backend/services/scene_ocr_service.py:59,367,381,387,397-402,508-571,600-700
  backend/services/enrichment_pipeline.py:554(BoundingBox),1954-1974(DetectionInput)
  backend/models/detection.py:29,54-67
  backend/api/routes/model_management.py:186,486,560,639,646
  ai/gateway/main.py:181-185
  ai/gateway/adapters/enrichment.py:292-296(BBoxRequest),360-364(EnrichRequest),902-977(enrich handler)
  ai/gateway/adapters/enrichment_light.py:43-68(ImageRequest/BBoxRequest alias+list),326(pose route)
  ai/gateway/adapters/clip.py:218-223(ClassifyRequest.camera_type: str),242-245(BatchSimilarityRequest, NO validator)
  ai/clip/model.py:258-259(MAX_BATCH_TEXTS_SIZE),377(CameraType enum),409-426(texts validator)
  ai/enrichment/model.py:2694(object-distance),3552(POST /models/unload query-param)
  backend/tests/contracts/ai_providers/test_conformance_geometry.py:68-70,121-215
"""

from __future__ import annotations

import asyncio
import copy
import io
import json
import os
import re
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio
from backend.ai_contract.operations import OPERATIONS
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent
for _p in (Path.cwd(), *Path(__file__).resolve().parents):
    if (_p / "backend" / "ai_contract" / "operations.py").exists():
        REPO_ROOT = _p
        break
GOLDEN_DIR = REPO_ROOT / "backend/tests/contracts/ai_providers/golden/payloads"

FAKE_BASE = "http://fake"

# The /tmp probe runs WITHOUT the repo ini (pytest never reads
# pyproject.toml when args live outside the rootdir), so pytest-asyncio
# sits in strict mode there: every async leg carries an explicit
# @pytest.mark.asyncio and the one async fixture uses pytest_asyncio.
# fixture. In-tree (asyncio_mode=auto) both are redundant but legal.
_aio = pytest.mark.asyncio

# The five production mount prefixes (ai/gateway/main.py:181-185) — identical
# to the registry's own path prefixes, so a client base_url works on either app.
GATEWAY_MOUNTS = (
    ("/yolo26", "ai.gateway.adapters.yolo26"),
    ("/clip", "ai.gateway.adapters.clip"),
    ("/florence", "ai.gateway.adapters.florence"),
    ("/enrichment", "ai.gateway.adapters.enrichment"),
    ("/enrich-lt", "ai.gateway.adapters.enrichment_light"),
)

# UNVERIFIED (import cost): the WP8.3 dossier measured ~1.6s cold for the
# gateway adapters and ~3.4s for ai.clip.model (native CLIP). The repo tier is
# pytest-timeout=5s, so every leg that imports those carries an explicit
# @pytest.mark.timeout override instead of relying on luck.


# ---------------------------------------------------------------------------
# repo conftest parity: the in-tree tier clears the get_settings cache around
# every test (backend/tests/conftest.py autouse reset_settings_cache); the
# /tmp probe has no such conftest, so do it here (idempotent in-tree).
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from backend.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# fake app + recording transport
# ---------------------------------------------------------------------------


def _fake_app() -> FastAPI:
    from backend.ai_contract.fake import create_fake_app

    return create_fake_app()


class _RecordingTransport(httpx.AsyncBaseTransport):
    """ASGITransport wrapper that records (method, path, body) of what the
    CLIENT actually sent. Pins about client URL composition and payload shape
    assert on this capture, not on the fake's reply."""

    def __init__(self, app: FastAPI, store: list[dict[str, Any]]) -> None:
        self._inner = ASGITransport(app=app)
        self._store = store

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        body = await request.aread()
        self._store.append({"method": request.method, "path": request.url.path, "body": body})
        return await self._inner.handle_async_request(request)


def _point_at(client: Any, app: FastAPI, store: list[dict[str, Any]] | None = None) -> None:
    """Swap a client's private persistent pools onto the in-process fake."""
    transport = _RecordingTransport(app, store if store is not None else [])
    swapped = 0
    for attr in ("_http_client", "_health_http_client"):
        existing = getattr(client, attr, None)
        if isinstance(existing, httpx.AsyncClient):
            setattr(
                client,
                attr,
                httpx.AsyncClient(transport=transport, timeout=existing.timeout),
            )
            swapped += 1
    assert swapped, (
        f"{type(client).__name__} exposes no _http_client/_health_http_client "
        "pool — the client seam changed; re-read its __init__"
    )


def _patch_settings(monkeypatch: pytest.MonkeyPatch, module_path: str, settings: Any) -> None:
    """Patch the module-level ``get_settings`` name the client module imported.

    Clients do ``from backend.core.config import get_settings`` (e.g.
    detector_client.py:73), so patching the original in backend.core.config
    would hit NONE of them."""
    import importlib

    mod = importlib.import_module(module_path)
    monkeypatch.setattr(mod, "get_settings", lambda: settings)


async def _served_body(op_id: str, **kw: Any) -> dict[str, Any]:
    """The body the fake ACTUALLY serves for the registry path.

    NOT ``generate(op_id)`` directly: generate() with payload=None keeps the
    walked shape for the payload-echoing ops (clip_classify softmaxes over the
    REQUESTED labels, generators.py:532-539; model_preload/unload echo
    model_name, generators.py:459-475), while the ASGI app parses the body
    before generating (fake/app.py:70-83). This helper drives the app itself —
    the exact bytes a client sees (the registry request example stands in for
    a real body)."""
    op = OPERATIONS[op_id]
    body_kwargs = _request_kwargs(op_id)
    body_kwargs.update(kw)
    async with AsyncClient(transport=ASGITransport(app=_fake_app()), base_url=FAKE_BASE) as c:
        r = await c.request(op.method, op.path, **body_kwargs)
        assert r.status_code == 200, (op_id, r.status_code, r.text[:200])
        return r.json()


def _fake_body(op_id: str) -> dict[str, Any]:
    """Sync wrapper for non-async legs (rename table). NOTE the served body
    for clip_classify WITHOUT a labels payload is the walked alpha/bravo shape;
    async legs use _served_body with the real payload."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_served_body(op_id))
    finally:
        loop.close()


async def _one_shot(app: FastAPI, method: str, path: str, **kw) -> httpx.Response:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=FAKE_BASE) as c:
        return await c.request(method, path, **kw)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fake_app() -> FastAPI:
    return _fake_app()


@pytest.fixture
def captured() -> list[dict[str, Any]]:
    return []


@pytest.fixture
def pil_image() -> Image.Image:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (10, 140, 60)).save(buf, format="PNG")
    buf.seek(0)
    img = Image.open(buf)
    img.load()
    return img


@pytest.fixture
def settings_factory():
    """A real Settings with every AI URL on the fake's registry prefixes and
    retries pinned to 1 (retry loops sleep 2**attempt — the detector's backoff —
    and the fake is deterministic, so one attempt is all a conformance run
    needs). use_ai_gateway stays False: each client gets exactly one prefix,
    no gateway rewrite."""

    def _make(**overrides: Any) -> Any:
        from backend.core.config import Settings

        base: dict[str, Any] = {
            "yolo26_url": f"{FAKE_BASE}/yolo26",
            "florence_url": f"{FAKE_BASE}/florence",
            "clip_url": f"{FAKE_BASE}/clip",
            "enrichment_url": f"{FAKE_BASE}/enrichment",  # heavy
            "enrichment_light_url": f"{FAKE_BASE}/enrich-lt",  # light
            "nemotron_url": FAKE_BASE,  # registry op is bare /completion
            "use_ai_gateway": False,
            "ai_gateway_url": None,
            "detector_max_retries": 1,
            "enrichment_max_retries": 1,
            "nemotron_max_retries": 1,
            "nemotron_use_guided_json": False,  # skip the NIM guided-JSON probe
        }
        base.update(overrides)
        # _env_file=None so the sandbox .env cannot bleed prod values into
        # validators (config.py skips the weak-password check for env "test";
        # the probe conftest / repo conftest sets ENVIRONMENT=test).
        return Settings(_env_file=None, **base)

    return _make


@pytest.fixture
def detector_client(fake_app, monkeypatch, settings_factory):
    from backend.services import detector_client as dcmod

    _patch_settings(monkeypatch, "backend.services.detector_client", settings_factory())
    client = dcmod.DetectorClient(max_retries=1)
    _point_at(client, fake_app)
    yield client


@pytest.fixture
def florence_client(fake_app):
    from backend.services.florence_client import FlorenceClient

    client = FlorenceClient(base_url=f"{FAKE_BASE}/florence")  # ctor seam :321
    _point_at(client, fake_app)
    yield client


@pytest.fixture
def clip_client(fake_app):
    from backend.services.clip_client import CLIPClient

    client = CLIPClient(base_url=f"{FAKE_BASE}/clip")  # ctor seam :111
    _point_at(client, fake_app)
    yield client


@pytest.fixture
def enrichment_client(fake_app, monkeypatch, settings_factory):
    _patch_settings(monkeypatch, "backend.services.enrichment_client", settings_factory())
    from backend.services.enrichment_client import EnrichmentClient

    client = EnrichmentClient()  # heavy/light from patched settings (:855/:865)
    _point_at(client, fake_app)
    yield client


@pytest.fixture
def nemotron_analyzer(fake_app, monkeypatch, settings_factory):
    _patch_settings(monkeypatch, "backend.services.nemotron_analyzer", settings_factory())
    from backend.services.nemotron_analyzer import NemotronAnalyzer

    analyzer = NemotronAnalyzer(
        redis_client=object(),  # never touched by the legs driven here
        use_enriched_context=False,
        use_enrichment_pipeline=False,
        max_retries=1,
        service_facade=MagicMock(),  # don't build the real facade at ctor
    )
    _point_at(analyzer, fake_app)
    yield analyzer


@pytest.fixture(scope="module")
def big_image_file(tmp_path_factory):
    """DetectorClient.detect_objects reads a REAL file, PIL-validates it
    (detector_client.py:1177-1184) and enforces MIN_DETECTION_IMAGE_SIZE=10240
    (:103) — the golden request example is a 19-byte string, NOT a usable file,
    so generate a random-noise PNG (large after compression; bytes are
    irrelevant: the fake never decodes them)."""
    rng = os.urandom(512 * 512 * 3)
    img = Image.frombytes("RGB", (512, 512), rng)
    p = tmp_path_factory.mktemp("wp84") / "frame.png"
    img.save(p, format="PNG")
    assert p.stat().st_size >= 10240, p.stat().st_size
    return p


def _request_kwargs(op_id: str) -> dict[str, Any]:
    """Contract-driven request builder (mirrors test_fake_provider.py:72-98)."""
    op = OPERATIONS[op_id]
    if op.method == "GET":
        return {}
    example = GOLDEN_DIR / f"{op_id}.request.example.json"
    if example.exists():
        payload = json.loads(example.read_text(encoding="utf-8"))
        if isinstance(payload, str):
            return {"files": [("file", ("f.jpg", payload.encode(), "image/jpeg"))]}
        if payload == {}:
            return {}
        return {"json": payload}
    return {"json": {"image": "aGVsbG8="}}


@pytest.fixture(scope="module")
def gateway_app() -> FastAPI:
    """The five adapter routers with their PRODUCTION prefixes
    (ai/gateway/main.py:181-185). Factory precedent:
    test_conformance_geometry.py:169-181 (bare routers leave registry paths
    unreachable — must mount with prefixes)."""
    from importlib import import_module

    app = FastAPI()
    for prefix, module in GATEWAY_MOUNTS:
        app.include_router(import_module(module).router, prefix=prefix)
    return app


@pytest_asyncio.fixture
async def gateway_client(gateway_app):
    """All FIVE module-level ``get_triton_client`` names patched — five
    distinct targets; patching one leaves four calling real gRPC
    (test_conformance_geometry.py:199-215)."""
    from contextlib import ExitStack

    triton = AsyncMock()
    triton.infer = AsyncMock(return_value={"output0": [], "output": []})
    triton.is_model_ready = AsyncMock(return_value=True)
    triton.get_model_metadata = AsyncMock(return_value={"outputs": [{"name": "output0"}]})
    with ExitStack() as stack:
        for _, module in GATEWAY_MOUNTS:
            stack.enter_context(patch(f"{module}.get_triton_client", return_value=triton))
        async with AsyncClient(
            transport=ASGITransport(app=gateway_app), base_url=FAKE_BASE
        ) as client:
            yield client


# ---------------------------------------------------------------------------
# THE CLIENT PARSE SURFACE AS DATA. Values are the deterministic fake bodies
# dumped at draft time (generate(op_id)); expected PARSED shapes come from the
# client dataclasses (fields dumped too). "op" is the registry op the client is
# ROUTED to under default settings — asserting store path == OPERATIONS[op].path
# pins the settings→service routing (config.py:1373-1408) as well as the parse.
# ---------------------------------------------------------------------------

_EXPECTED_CLIENT_OUTPUTS: dict[str, dict[str, Any]] = {
    # ---- FlorenceClient (parse cites in header) ----
    "florence.extract": {
        "call": lambda c, d: c.extract(d["image"], "<CAPTION>"),
        "value": "result_418",
        "op": "florence_extract",
    },
    "florence.ocr": {
        "call": lambda c, d: c.ocr(d["image"]),
        "value": "text_931",
        "op": "florence_ocr",
    },
    "florence.ocr_with_regions": {
        "call": lambda c, d: c.ocr_with_regions(d["image"]),
        # OCRRegion(text, bbox); 8-coord quad preserved verbatim (:998)
        "value": {
            "count": 2,
            "elem": {
                "text": "text_893",
                "bbox": [
                    113.0671,
                    78.9737,
                    145.1082,
                    78.9737,
                    145.1082,
                    145.1246,
                    113.0671,
                    145.1246,
                ],
            },
        },
        "op": "florence_ocr_with_regions",
    },
    "florence.detect": {
        "call": lambda c, d: c.detect(d["image"]),
        "value": {"count": 2, "elem": {"label": "label_501", "score": 0.2445}},
        "op": "florence_detect",
    },
    "florence.dense_caption": {
        "call": lambda c, d: c.dense_caption(d["image"]),
        "value": {"count": 2, "elem": {"caption": "caption_882"}},
        "op": "florence_dense_caption",
    },
    "florence.describe_regions": {
        "call": lambda c, d: c.describe_regions(
            d["image"], [d["bbox_cls"](x1=1.0, y1=2.0, x2=30.0, y2=40.0)]
        ),
        "value": {"count": 2, "elem": {"caption": "caption_368"}},
        "op": "florence_describe_region",
    },
    "florence.phrase_grounding": {
        "call": lambda c, d: c.phrase_grounding(d["image"], ["a dog"]),
        "value": {"count": 2, "elem": {"phrase": "phrase_440"}},
        "op": "florence_phrase_grounding",
    },
    "florence.detect_security_objects": {
        "call": lambda c, d: c.detect_security_objects(d["image"]),
        # SecurityObjectsResult(detections=[SecurityObjectDetection(label,bbox,confidence)], objects_queried=[...])
        "value": {
            "obj_rows": "detections",
            "count": 2,
            "elem": {"label": "label_828", "confidence": 0.8701},
        },
        "op": "florence_detect_security_objects",
    },
    # ---- CLIPClient ----
    "clip.embed": {
        "call": lambda c, d: c.embed(d["image"]),
        # list[float]; client hard-rejects dim != EMBEDDING_DIMENSION (:352-366)
        "value": {"len": 768},
        "op": "clip_embed",
    },
    "clip.classify": {
        "call": lambda c, d: c.classify(d["image"], ["person", "car"]),
        # tuple[dict[str,float], str] — the fake SOFTMAXES over the requested
        # labels (generators.py:500-539): keys are the labels themselves and
        # top_label is one of them (seeded choice, not the walked literal).
        # Values checked against the served body in the leg (labels-dependent,
        # so not a static literal here); KEY-SENSITIVITY is pinned separately.
        "value": {"tuple_labels": ["person", "car"]},
        "op": "clip_classify",
    },
    "clip.similarity": {
        "call": lambda c, d: c.similarity(d["image"], "a person"),
        "value": 0.1088,
        "op": "clip_similarity",
    },
    "clip.batch_similarity": {
        "call": lambda c, d: c.batch_similarity(d["image"], ["a", "b"]),
        "value": {"keys": {"alpha", "bravo"}},
        "op": "clip_batch_similarity",
    },
    "clip.anomaly_score": {
        # client requires len(baseline)==768 before sending (:488-493)
        "call": lambda c, d: c.anomaly_score(d["image"], [0.0] * 768),
        "value": {"tuple": (0.2454, 0.5448)},
        "op": "clip_anomaly_score",
    },
    # ---- EnrichmentClient (routing defaults decide heavy/light per model) ----
    "enrichment.classify_vehicle": {
        "call": lambda c, d: c.classify_vehicle(d["image"]),
        "value": {
            "vehicle_type": "vehicle_type_508",
            "display_name": "display_name_657",
            "confidence": 0.8946,
            "is_commercial": True,
            "inference_time_ms": 12.5,
        },
        "op": "enrichment_vehicle_classify",  # heavy default (config.py:1393+)
    },
    "enrichment.classify_pet": {
        "call": lambda c, d: c.classify_pet(d["image"]),
        # LIGHT op values (pet defaults to light → /enrich-lt/pet-classify)
        "value": {
            "pet_type": "pet_type_878",
            "breed": "breed_486",
            "confidence": 0.8803,
            "is_household_pet": False,
            "inference_time_ms": 12.5,
        },
        "op": "enrich_lt_pet_classify",
    },
    "enrichment.classify_clothing": {
        "call": lambda c, d: c.classify_clothing(d["image"]),
        "value": {
            "clothing_type": "clothing_type_487",
            "color": "color_375",
            "style": "style_214",
            "confidence": 0.3179,
            "top_category": "top_category_741",
            "description": "description_261",
            "is_suspicious": True,
            "is_service_uniform": True,
            "inference_time_ms": 12.5,
        },
        "op": "enrichment_clothing_classify",  # heavy default
    },
    "enrichment.analyze_demographics": {
        "call": lambda c, d: c.analyze_demographics(d["image"]),
        # .get() defaults are "unknown"/0.0 (:2782-2786) — a rename degrades
        # SILENTLY in production; value equality is what catches it here.
        "value": {
            "age_range": "age_range_835",
            "age_confidence": 0.3432,
            "gender": "gender_967",
            "gender_confidence": 0.7296,
            "inference_time_ms": 12.5,
        },
        "op": "enrichment_demographics",  # heavy default
    },
    "enrichment.detect_threats": {
        "call": lambda c, d: c.detect_threats(d["image"]),
        # threats_detected is a LIST of dicts on the wire (:2620 default [])
        "value": {
            "threats_detected_len": 2,
            "is_threat": False,
            "max_confidence": 0.4489,
            "inference_time_ms": 12.5,
        },
        "op": "enrich_lt_threat_detect",  # light default
    },
    "enrichment.compute_reid_embedding": {
        "call": lambda c, d: c.compute_reid_embedding(d["image"]),
        # CONTRACT key is ``embedding_dimension`` (fake/enrich_lt_person_reid)
        # but the client reads ``embedding_dim`` with default len(embedding)
        # (:2944-2948) — a rename there is MASKED because the default equals
        # the true length; see test_reid_key_drift_masked_by_len_default.
        "value": {"embedding_len": 512, "embedding_dim": 512, "inference_time_ms": 12.5},
        "op": "enrich_lt_person_reid",  # light default
    },
    "enrichment.estimate_depth": {
        "call": lambda c, d: c.estimate_depth(d["image"]),
        # LIGHT default → /enrich-lt/depth-estimate (its own seeded values)
        "value": {
            "depth_map_base64": "depth_map_base64_290",
            "min_depth": 0.3497,
            "max_depth": 0.446,
            "mean_depth": 0.128,
            "inference_time_ms": 12.5,
        },
        "op": "enrich_lt_depth_estimate",
    },
    "enrichment.classify_action": {
        "call": lambda c, d: c.classify_action([d["image"]]),
        "value": {
            "action": "action_709",
            "confidence": 0.2032,
            "is_suspicious": True,
            "risk_weight": 0.5599,
            "inference_time_ms": 12.5,
        },
        "op": "enrichment_action_classify",  # heavy default
    },
}

# Methods whose fake-vs-client shape makes a GREEN happy path impossible TODAY.
# NOT skips — each is its own explicit characterization test in section 5.
_REDACTED_METHODS = {
    "enrichment.analyze_pose": "pose keypoints have no name/x/y/confidence on the contract",
    "enrichment.enrich_detection": "no /enrich response carries the keys _parse_unified_response reads",
    "enrichment.estimate_object_distance": "client composes {light}/object-distance; registry is bare",
    "enrichment.get_model_status": "client composes {heavy}/models/status; registry is bare",
    "enrichment.preload_model": "client composes {heavy}/models/preload; registry is bare",
}


def _check_rows(name: str, got: Any, exp: dict, raw: Any) -> None:
    """Row-shaped expectations: ``obj_rows`` (rows under a named attribute) or
    ``count`` (bare list of rows). Split out of ``_check`` to keep its
    dispatch under the PLR0911 return cap; both branches end the check."""
    if "obj_rows" in exp:  # rows nested under a named attribute
        rows = getattr(got, exp["obj_rows"])
        assert len(rows) == exp["count"], (
            f"{name}.{exp['obj_rows']}: {len(rows)} rows vs contract {exp['count']}"
        )
        for i, row in enumerate(rows):
            for k, v in exp["elem"].items():
                _eq(f"{name}.{exp['obj_rows']}[{i}].{k}", getattr(row, k), v, raw)
    else:  # "count" in exp — list-of-rows return
        assert isinstance(got, list), f"{name}: expected list, got {type(got)}"
        assert len(got) == exp["count"], f"{name}: {len(got)} rows vs contract {exp['count']}"
        for i, row in enumerate(got):
            for k, v in exp["elem"].items():
                assert hasattr(row, k), (
                    f"{name}[{i}]: parsed row lost field {k!r} (raw {str(raw)[:200]})"
                )
                _eq(f"{name}[{i}].{k}", getattr(row, k), v, raw)


def _check(name: str, got: Any, exp: Any, raw: Any) -> None:
    """Compare a parsed client output against the expected shape (literals)."""
    if isinstance(exp, dict):
        if "obj_rows" in exp or "count" in exp:  # row shapes -> shared helper
            _check_rows(name, got, exp, raw)
            return
        if "len" in exp and "embedding_dim" not in exp:  # list[float] return
            assert isinstance(got, list) and len(got) == exp["len"], (
                f"{name}: embedding length {len(got) if isinstance(got, list) else got} != {exp['len']}"
            )
            return
        if "keys" in exp:  # dict return
            assert set(got) == exp["keys"], f"{name}: {set(got)} != {exp['keys']}"
            return
        if "tuple_labels" in exp:  # (dict, str) tuple with label-keyed scores
            scores, top = got
            assert set(scores) == set(exp["tuple_labels"]), (
                f"{name}: score keys {set(scores)} != requested labels {set(exp['tuple_labels'])} "
                "— the fake softmaxes over REQUESTED labels (generators.py:532-539)"
            )
            assert raw["scores"] == scores, f"{name}: scores != served {raw['scores']}"
            assert top == raw["top_label"] and top in exp["tuple_labels"], (
                f"{name}: top_label {top!r} not the served top of the requested labels"
            )
            return
        if "tuple" in exp:  # plain (float, float) tuple return
            for i, (g, e) in enumerate(zip(got, exp["tuple"], strict=True)):
                _eq(f"{name}[{i}]", g, e, raw)
            return
        for k, v in exp.items():
            if k == "embedding_len":
                assert isinstance(got.embedding, list) and len(got.embedding) == v, (
                    f"{name}.embedding: length {len(got.embedding)} != {v}"
                )
                continue
            if k == "threats_detected_len":
                assert isinstance(got.threats_detected, list) and len(got.threats_detected) == v, (
                    f"{name}.threats_detected: {got.threats_detected!r} (want len {v})"
                )
                continue
            assert hasattr(got, k), f"{name}: parsed result lost field {k!r} (raw {str(raw)[:200]})"
            _eq(f"{name}.{k}", getattr(got, k), v, raw)
        return
    _eq(name, got, exp, raw)


def _eq(label: str, got: Any, exp: Any, raw: Any = None) -> None:
    if (
        isinstance(exp, (int, float))
        and not isinstance(exp, bool)
        and isinstance(got, (int, float))
    ):
        assert got == pytest.approx(exp, abs=1e-6), f"{label}: {got} != {exp}"
        return
    assert got == exp, f"{label}: {got!r} != contract {exp!r} (raw {str(raw)[:200]})"


# ---------------------------------------------------------------------------
# 1. HAPPY PATH: client method -> fake ASGI app -> PARSED output == contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method", sorted(_EXPECTED_CLIENT_OUTPUTS))
@_aio
async def test_client_parsed_output_matches_the_contract(
    method: str, request, fake_app, pil_image, captured
) -> None:
    """WP8.4 Done-when, executed: the client's PARSED fields (not "no
    exception") match the contract-declared keys, AND the client hit the exact
    registry path the settings routing declares (config.py:1373-1408).
    PREDICTED-GREEN. A contract-model key rename reddens this test (the rename
    table in section 2 proves each row is sensitive to its own key)."""
    spec = _EXPECTED_CLIENT_OUTPUTS[method]
    client_name, _, _meth = method.partition(".")
    client = request.getfixturevalue(f"{client_name}_client")
    deps = {
        "image": pil_image,
        "bbox_cls": __import__(
            "backend.services.florence_client", fromlist=["BoundingBox"]
        ).BoundingBox,
    }
    _point_at(client, fake_app, captured)  # ensure THIS leg's calls are recorded
    op = OPERATIONS[spec["op"]]
    got = await spec["call"](client, deps)
    assert captured, f"{method}: client sent no request at all"
    sent = captured[-1]
    assert sent["path"] == op.path, (
        f"{method}: client requested {sent['path']!r} but the registry declares "
        f"{op.path!r} for {spec['op']} — path drift or a routing-default change"
    )
    # Rebuild the served body the SAME way fake/app.py:70-83 does: parse the
    # request body, feed it to generate() (clip_classify softmaxes over the
    # REQUESTED labels — generators.py:532-539 — so a golden-payload dump is
    # the WRONG body for that leg; this one is by construction exact).
    from backend.ai_contract.fake import generate as _gen

    sent_payload = json.loads(sent["body"]) if sent["body"] else None
    raw = json.loads(json.dumps(_gen(spec["op"], sent_payload, "gateway")))
    assert got is not None, f"{method}: client degraded to None on a 200 — parse broke"
    _check(method, got, spec["value"], raw)


@_aio
async def test_florence_batch_extract_parses_per_row_fields(fake_app, pil_image) -> None:
    """Per-row parse of /florence/batch-extract: client reads
    result/prompt_used/inference_time_ms/error per row (florence_client.py:749-752).
    Dedicated leg because its input dataclass BatchExtractItem(image, prompt)
    doesn't fit the shared table's deps. PREDICTED-GREEN."""
    from backend.services.florence_client import BatchExtractItem, FlorenceClient

    client = FlorenceClient(base_url=f"{FAKE_BASE}/florence")
    _point_at(client, fake_app)
    rows = await client.batch_extract(
        [
            BatchExtractItem(image=pil_image, prompt="<CAPTION>"),
            BatchExtractItem(image=pil_image, prompt="<OCR>"),
        ]
    )
    body = await _served_body("florence_batch_extract")
    assert len(rows) == len(body["results"]), f"{len(rows)} rows vs {len(body['results'])}"
    src = body["results"][0]
    for row in rows:
        assert row.result == src["result"], row
        assert row.prompt_used == src["prompt_used"], row
        assert row.inference_time_ms == pytest.approx(src["inference_time_ms"]), row


# ---------------------------------------------------------------------------
# DetectorClient.detect_objects: DB-model leg + the WP7.4 video-dims pin.
# ---------------------------------------------------------------------------


@_aio
async def test_detector_client_detect_objects_parses_the_shipped_bbox_dict(
    detector_client, big_image_file
) -> None:
    """DetectorClient.detect_objects → fake /yolo26/detect → Detection rows.
    Pins (all from the shipped dict-of-INTS bbox shape, fake/generators):
      * object_type from the wire key ``class`` (:1310,:1409);
      * bbox keys x/y/width/height read as ints (:1331-1336);
      * image_width/image_height land on video_width/video_height (:1292,:1424)
        — WP7.4's headline field, None on any older wire shape.
    Session mocked like backend/tests/unit/services/test_detector_client.py:38-45.
    PREDICTED-GREEN. UNVERIFIED: whether an un-awaited AsyncMock session makes
    the camera last_seen update raise — session.get returns None to skip it."""
    from backend.services import detector_client as dcmod
    from sqlalchemy.ext.asyncio import AsyncSession

    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.get = AsyncMock(return_value=None)

    body = await _served_body("yolo26_detect")
    assert len(body["detections"]) == 3, "fake shape changed: re-read the dump"

    with patch.object(
        dcmod,
        "get_baseline_service",
        autospec=True,
        return_value=MagicMock(update_baseline=AsyncMock()),
    ):
        rows = await detector_client.detect_objects(str(big_image_file), "cam-1", session)

    assert len(rows) == 3, (
        f"detector dropped rows: {len(rows)}/3 fake detections (fake confidences "
        "0.665-0.9292 are all above the default threshold)"
    )
    for row, det in zip(rows, body["detections"], strict=True):
        assert row.object_type == det["class"]
        assert row.confidence == pytest.approx(det["confidence"])
        assert row.bbox_x == det["bbox"]["x"]
        assert row.bbox_y == det["bbox"]["y"]
        assert row.bbox_width == det["bbox"]["width"]
        assert row.bbox_height == det["bbox"]["height"]
        assert row.video_width == body["image_width"], "WP7.4: video_width not carried"
        assert row.video_height == body["image_height"]
    session.add.assert_called()
    session.commit.assert_awaited()


@_aio
async def test_rename_proof_detector_bbox_key_reddens_the_client_leg(
    big_image_file, monkeypatch, settings_factory
) -> None:
    """THE Done-when mechanism demonstrated end-to-end (plan :1024-1026): rename
    the contract key ``bbox`` → ``bounding_box`` in the SERVED body and the same
    client call stops producing the pinned geometry. Achieved with zero
    production change: a wrapper ASGI app rewrites the fake's JSON response.
    PREDICTED-GREEN (a self-test of this suite's own sensitivity)."""
    inner = _fake_app()

    async def renamed_app(scope, receive, send):  # ASGI callable
        if scope["type"] != "http" or scope["path"] != "/yolo26/detect":
            await inner(scope, receive, send)
            return
        captured_body: dict[str, bytes] = {"b": b""}

        async def _send(msg: dict[str, Any]) -> None:
            if msg["type"] == "http.response.body":
                captured_body["b"] += msg.get("body", b"")

        await inner(scope, receive, _send)
        payload = json.loads(captured_body["b"])
        for d in payload.get("detections", []):
            if "bbox" in d:
                d["bounding_box"] = d.pop("bbox")
        body = json.dumps(payload).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    from sqlalchemy.ext.asyncio import AsyncSession

    _patch_settings(monkeypatch, "backend.services.detector_client", settings_factory())
    from backend.services import detector_client as dcmod

    client = dcmod.DetectorClient(max_retries=1)
    client._http_client = httpx.AsyncClient(
        transport=ASGITransport(app=renamed_app), timeout=client._timeout
    )
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.get = AsyncMock(return_value=None)

    with patch.object(
        dcmod,
        "get_baseline_service",
        autospec=True,
        return_value=MagicMock(update_baseline=AsyncMock()),
    ):
        try:
            rows = await client.detect_objects(str(big_image_file), "cam-1", session)
            dropped = rows == []  # client's "missing bbox → skip row" branch (:1327-1341)
        except Exception:
            dropped = True  # or an outright parse failure — either way, RED

    assert dropped, (
        "renaming bbox→bounding_box did NOT change client output: the happy-path "
        "test above is not actually sensitive to the key (Done-when violated)"
    )


# ---------------------------------------------------------------------------
# 2. RENAME PROOF (pure logic on the real fake bodies): every happy-path row is
#    sensitive to its own keys — a contract rename reaches the client as a
#    missing key.
# ---------------------------------------------------------------------------

_RENAME_CASES = [
    ("florence.extract", "result"),
    ("florence.ocr", "text"),
    ("florence.ocr_with_regions", "regions"),
    ("florence.ocr_with_regions", "regions[].text"),
    ("florence.detect", "detections"),
    ("florence.detect", "detections[].label"),
    ("florence.dense_caption", "regions[].caption"),
    ("florence.describe_regions", "descriptions"),
    ("florence.phrase_grounding", "grounded_phrases[].phrase"),
    ("florence.detect_security_objects", "detections[].confidence"),
    ("florence.batch_extract", "results"),
    ("florence.batch_extract", "results[].prompt_used"),
    ("clip.embed", "embedding"),
    ("clip.classify", "scores"),
    ("clip.classify", "top_label"),
    ("clip.similarity", "similarity"),
    ("clip.batch_similarity", "similarities"),
    ("clip.anomaly_score", "anomaly_score"),
    ("clip.anomaly_score", "similarity_to_baseline"),
    ("enrichment.classify_vehicle", "vehicle_type"),
    ("enrichment.classify_pet", "pet_type"),
    ("enrichment.classify_clothing", "clothing_type"),
    ("enrichment.analyze_demographics", "age_range"),
    ("enrichment.detect_threats", "max_confidence"),
    ("enrichment.compute_reid_embedding", "embedding"),
    ("enrichment.estimate_depth", "depth_map_base64"),
    ("enrichment.classify_action", "action"),
]


@pytest.mark.parametrize(("method", "key"), _RENAME_CASES)
def test_rename_proof_table_entries_are_sensitive(method: str, key: str) -> None:
    """For each (client method, contract key) the client parse depends on:
    (a) the fake's body still CARRIES the key (stale table guard), and (b) the
    mutation helper finds and removes it. Together with section 1's
    value-equality assertions this is the mechanical half of the Done-when:
    rename the key in the contract model + fake and section 1 reddens.
    PREDICTED-GREEN.

    Note the ``.get()``-with-default parsers (demographics :2782-2786, threats
    :2620-2623, reid :2944-2948) degrade SILENTLY in production when a key is
    renamed — which is exactly why section 1 compares VALUES, not survival."""
    op = (
        _EXPECTED_CLIENT_OUTPUTS[method]["op"]
        if method in _EXPECTED_CLIENT_OUTPUTS
        else "florence_batch_extract"  # lives in its own test, not the table
    )
    raw = _fake_body(op)
    root = key.split("[", maxsplit=1)[0]
    assert root in raw, f"{op} response lacks {root!r} — this table is stale"
    mutated = _mutate(raw, key)
    with pytest.raises((KeyError, IndexError, StopIteration)):
        _deref(mutated, key)
    _deref(raw, key)  # sanity: the untouched body resolves fine


def _deref(resp: dict[str, Any], path: str) -> Any:
    m = re.match(r"^([\w\-.]+)\[\](.*)$", path)
    if m:
        head, rest = m.group(1), m.group(2).lstrip(".")
        items = resp[head]
        if not items:
            raise IndexError(f"{path}: empty rows")
        row = items[0]
        return row if not rest else row[rest]
    return resp[path]


def _mutate(resp: dict[str, Any], path: str) -> dict[str, Any]:
    out = copy.deepcopy(resp)
    m = re.match(r"^([\w\-.]+)\[\](.*)$", path)
    if m:
        items = out[m.group(1)]
        rest = m.group(2).lstrip(".")
        if not rest:
            del out[m.group(1)]
        else:
            del items[0][rest]
        return out
    del out[path]
    return out


def test_reid_key_drift_masked_by_len_default() -> None:
    """A rename the CURRENT client does NOT see (documented blind spot, not a
    skip): the contract/fake declares ``embedding_dimension``
    (enrich_lt_person_reid body) but EnrichmentClient.compute_reid_embedding
    reads ``embedding_dim`` with default ``len(embedding)`` (:2944-2948), so
    deleting the contract key changes nothing observable — the default
    coincidentally equals 512. Pinned so whoever aligns the client key (or the
    contract key) reddens this test and revisits the table row.
    PREDICTED-GREEN."""
    raw = _fake_body("enrich_lt_person_reid")
    assert "embedding_dimension" in raw, "contract key renamed — align client at :2947"
    assert "embedding_dim" not in raw
    mutated = _mutate(raw, "embedding_dimension")
    embedding = mutated.get("embedding", [])
    # emulate the client's read: the default masks the rename
    assert mutated.get("embedding_dim", len(embedding)) == len(embedding) == 512


# ---------------------------------------------------------------------------
# 3. TIER A DEFECT PINS AT THE ASGI LEVEL (plan §WP7.3 table :769-800).
#    Real gateway adapter routers, real client code.
# ---------------------------------------------------------------------------


class TestTierABboxShape422:
    """Tier A row 1: heavy gateway types bbox ``dict[str,float]``
    (ai/gateway/adapters/enrichment.py:292-296) while EnrichmentClient sends
    ``list(bbox)`` (:1203,:1583). vehicle/clothing default to heavy
    (config.py:1373-1408) → the production call 422s. ASGI proof: gateway 422
    vs fake 200; the client-side wire shape pinned from the recording."""

    @pytest.mark.timeout(20)  # adapter import cost
    @pytest.mark.parametrize(
        "path", ["/enrichment/vehicle-classify", "/enrichment/clothing-classify"]
    )
    @_aio
    async def test_gateway_rejects_the_client_bbox_list(self, path: str, gateway_client) -> None:
        r = await gateway_client.post(
            path, json={"image": "aGVsbG8=", "bbox": [10.0, 20.0, 100.0, 200.0]}
        )
        assert r.status_code == 422, (
            f"{path} returned {r.status_code} for a LIST bbox — if the gateway "
            "now accepts lists, Tier A row 1 is fixed; update the client cites "
            "and delete this pin"
        )

    @pytest.mark.timeout(20)
    @_aio
    async def test_gateway_accepts_the_dict_shape_it_demands(self, gateway_client) -> None:
        # control leg: same route, dict bbox → past validation (the handler may
        # still fail on the non-image payload; anything but 422 proves the
        # validator, not the handler).
        r = await gateway_client.post(
            "/enrichment/vehicle-classify",
            json={"image": "aGVsbG8=", "bbox": {"x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0}},
        )
        assert r.status_code != 422, r.text[:200]

    @_aio
    async def test_client_sends_a_list_on_the_wire(
        self, enrichment_client, fake_app, pil_image, captured
    ) -> None:
        """The client half of the same defect, proven on the wire."""
        _point_at(enrichment_client, fake_app, captured)
        await enrichment_client.classify_vehicle(pil_image, bbox=(10.0, 20.0, 100.0, 200.0))
        sent = json.loads(captured[-1]["body"])
        assert isinstance(sent["bbox"], list), (
            f"client now sends {type(sent['bbox'])} — Tier A row 1 may be fixed; re-verify"
        )
        assert OPERATIONS["enrichment_vehicle_classify"].availability["gateway"] is True

    @pytest.mark.timeout(20)
    def test_light_gateway_accepts_both_shapes(self) -> None:
        """The Tier B asymmetry (plan :795-799): the /enrich-lt adapter model
        accepts dict OR list (adapters/enrichment_light.py:55-68) where the
        heavy one does not. Model-level (no route call) so no image decode is
        involved. PREDICTED-GREEN."""
        from ai.gateway.adapters import enrichment_light as light_mod

        m = light_mod.BBoxRequest
        m.model_validate({"image": "a", "bbox": [1.0, 2.0, 3.0, 4.0]})
        m.model_validate({"image": "a", "bbox": {"x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0}})
        # alias: the light side also accepts ``image_base64`` (populate_by_name)
        m.model_validate({"image_base64": "a"})


class TestTierAMissingPaths:
    """Tier A row 2: ``models/status``, ``models/preload``, ``models/unload``
    and ``object-distance`` exist on NEITHER gateway prefix (registry says
    gateway=False; grep over ai/gateway/adapters/ returns nothing) yet
    EnrichmentClient.get_model_status/.preload_model and
    backend/api/routes/model_management.py:186,:486 call them against
    gateway-shaped base URLs."""

    @pytest.mark.timeout(20)
    @pytest.mark.parametrize(
        ("op_id", "client_path"),
        [
            ("model_status", "/enrichment/models/status"),
            ("model_preload", "/enrichment/models/preload"),
            ("model_unload", "/enrichment/models/unload"),
            ("object_distance", "/enrichment/object-distance"),
            ("object_distance", "/enrich-lt/object-distance"),
        ],
    )
    @_aio
    async def test_absent_on_gateway_present_bare_on_the_registry(
        self, op_id: str, client_path: str, gateway_client, fake_app
    ) -> None:
        op = OPERATIONS[op_id]
        assert op.availability["gateway"] is False, (
            f"{op_id} matrix now says gateway — re-read operations.py; this absence guard is stale"
        )
        r = await getattr(gateway_client, op.method.lower())(client_path)
        assert r.status_code == 404, (
            f"{client_path} returned {r.status_code} on the gateway app — the "
            "absence moved; re-verify Tier A row 2"
        )
        r2 = await _one_shot(fake_app, op.method, op.path, **_request_kwargs(op_id))
        assert r2.status_code == 200, f"registry path {op.path} not served: {r2.status_code}"

    @pytest.mark.timeout(20)
    @_aio
    async def test_gateway_openapi_has_no_models_paths(self, gateway_app) -> None:
        paths = set(gateway_app.openapi()["paths"])
        for banned in (
            "/enrichment/models/status",
            "/enrichment/object-distance",
            "/object-distance",
        ):
            assert banned not in paths, f"{banned} appeared on the gateway — Tier A row 2 fixed?"

    @pytest.mark.timeout(20)
    @_aio
    async def test_client_model_status_404s_on_gateway_prefix_and_works_bare(
        self, monkeypatch, settings_factory, fake_app
    ) -> None:
        """End-to-end form: with a gateway-shaped enrichment base URL,
        get_model_status() swallows the 404 into {"error": "HTTP 404",
        "loaded_models": []} (:3259-3260) and preload_model() returns False
        (:3292-3295) — the backend believes "no models loaded" while the
        endpoint simply is not there. Against the base URL the registry
        declares (bare), both succeed. PREDICTED-GREEN (characterization of a
        live gap)."""
        from importlib import import_module

        from backend.services.enrichment_client import EnrichmentClient

        gw = FastAPI()
        for prefix, module in GATEWAY_MOUNTS:
            gw.include_router(import_module(module).router, prefix=prefix)
        _patch_settings(monkeypatch, "backend.services.enrichment_client", settings_factory())
        client = EnrichmentClient()
        _point_at(client, gw)
        status = await client.get_model_status()
        assert status.get("error") == "HTTP 404", status
        assert status.get("loaded_models") == [], status
        assert await client.preload_model("pose") is False

        bare = EnrichmentClient(base_url=FAKE_BASE, light_base_url=FAKE_BASE)
        _point_at(bare, fake_app)
        ok = await bare.get_model_status()
        assert "error" not in ok, ok
        assert ok["status"] == "healthy", ok
        assert await bare.preload_model("pose") is True


class TestTierAUnloadPathMismatch:
    """Tier A row 3: the backend posts ``POST /models/{name}/unload``
    (model_management.py:560,:639) but the server's route is
    ``POST /models/unload`` with model_name as a QUERY param
    (ai/enrichment/model.py:3552; the registry op model_unload path agrees) →
    404 even against the real undeployed server."""

    @_aio
    async def test_registry_unload_is_query_param_not_path_param(self, fake_app) -> None:
        assert OPERATIONS["model_unload"].path == "/models/unload"
        r = await _one_shot(fake_app, "POST", "/models/unload", params={"model_name": "pose"})
        assert r.status_code == 200, r.text[:200]
        assert "/models/{model_name}/unload" not in {op.path for op in OPERATIONS.values()}
        r2 = await _one_shot(fake_app, "POST", "/models/pose/unload")
        assert r2.status_code == 404, (
            "the /models/{name}/unload shape is now served — Tier A row 3 is "
            "fixed: update model_management.py:560,639 and delete this pin"
        )

    def test_backend_route_still_posts_the_wrong_shape(self) -> None:
        """AST pin on the URL template (the route-level test would need a live
        enrichment service to 404 against). PREDICTED-GREEN. UNVERIFIED: the
        f-string may be assembled from fragments; the AST walk only catches a
        single JoinedStr containing both '/models/' and '/unload'."""
        import ast

        src = (REPO_ROOT / "backend/api/routes/model_management.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        bad = [
            node.lineno
            for node in ast.walk(tree)
            if isinstance(node, ast.JoinedStr)
            and "/unload" in ast.unparse(node)
            and "/models/" in ast.unparse(node)
        ]
        assert bad, (
            "no f-string posting /models/{model_name}/unload found — Tier A row 3 "
            "FIXED (or the URL moved out of an f-string); re-read the route and "
            "delete this pin"
        )


class TestTierASegmentOnlyOnGateway:
    """Tier A row 4: /segment exists ONLY on the gateway
    (adapters/yolo26.py:447; registry per_model_server=False) while
    DetectorClient.segment_image posts ``{detector_url}/segment`` (:981) — so
    off-gateway (settings.yolo26_url = bare host) the call 404s and the client
    raises ValueError('... HTTP 404') (:1032-1033)."""

    def test_matrix_says_gateway_only(self) -> None:
        op = OPERATIONS["yolo26_segment"]
        assert op.availability["gateway"] is True
        assert op.availability["per_model_server"] is False, (
            "the matrix now claims /segment on the per-model server — re-read "
            "ai/yolo26/model.py (plan grep: 0 hits)"
        )

    @_aio
    async def test_segment_404s_off_the_gateway_prefix(
        self, fake_app, monkeypatch, settings_factory
    ) -> None:
        from backend.services import detector_client as dcmod

        _patch_settings(
            monkeypatch,
            "backend.services.detector_client",
            settings_factory(yolo26_url=FAKE_BASE),  # bare host = deployed shape
        )
        client = dcmod.DetectorClient(max_retries=1)
        _point_at(client, fake_app)
        with pytest.raises(ValueError, match="404"):
            await client.segment_image(b"fake-image-bytes")

    @_aio
    async def test_segment_succeeds_through_the_gateway_prefix(self, detector_client) -> None:
        """Same client method, base URL WITH the /yolo26 prefix (what
        use_ai_gateway=True produces) → the fake serves /yolo26/segment and the
        client passes the body through raw (:981 returns the dict). A rollout
        flag silently flips which branch runs. PREDICTED-GREEN."""
        result = await detector_client.segment_image(b"fake-image-bytes")
        body = await _served_body("yolo26_segment")
        assert result["detections"]
        assert [d["class"] for d in result["detections"]] == [
            d["class"] for d in body["detections"]
        ]
        assert result["image_width"] == body["image_width"] == 640


class TestTierACLIPDivergences:
    """Tier A row 7: gateway types ``camera_type`` as bare str
    (adapters/clip.py:218-223) where the server uses the CameraType enum
    (ai/clip/model.py:377), and the gateway has NO MAX_BATCH_TEXTS_SIZE
    validator (adapters/clip.py:242-245 vs ai/clip/model.py:409-426, default
    100 at :258-259)."""

    @pytest.mark.timeout(90)  # ai.clip.model cold import measured ~3.4s + native weights
    def test_native_clamps_texts_gateway_does_not(self) -> None:
        import ai.clip.model as native
        from ai.gateway.adapters import clip as gw
        from pydantic import ValidationError

        oversized = [f"t{i}" for i in range(native.MAX_BATCH_TEXTS_SIZE + 1)]
        with pytest.raises(ValidationError):
            native.BatchSimilarityRequest(image="a", texts=oversized)
        req = gw.BatchSimilarityRequest(image="a", texts=oversized)
        assert len(req.texts) == native.MAX_BATCH_TEXTS_SIZE + 1, "gateway gained a validator"

    @pytest.mark.timeout(90)
    def test_camera_type_enum_vs_bare_str(self) -> None:
        import ai.clip.model as native
        from ai.gateway.adapters import clip as gw
        from pydantic import ValidationError

        junk = "totally-not-a-camera-type"
        gw.ClassifyRequest(image="a", labels=["x"], camera_type=junk)
        with pytest.raises(ValidationError):
            native.ClassifyRequest(image="a", labels=["x"], camera_type=junk)

    @_aio
    async def test_deployed_client_sends_neither_field(
        self, clip_client, fake_app, pil_image, captured
    ) -> None:
        """The leg nobody counted: CLIPClient.classify's payload is only
        {image, labels} — the divergence above is invisible to the deployed
        client and only bites a consumer that starts speaking the server's
        dialect. PREDICTED-GREEN. UNVERIFIED: exact payload key set beyond
        image/labels (headers excluded from capture)."""
        _point_at(clip_client, fake_app, captured)
        await clip_client.classify(pil_image, ["person"])
        sent = json.loads(captured[-1]["body"])
        assert "camera_type" not in sent, sent
        assert "image" in sent and "labels" in sent, sent


# ---------------------------------------------------------------------------
# 4. is_healthy probes ONLY the heavy base URL (plan :1022-1024):
#    enrichment_client.py:1099-1101 is the sole health URL; :1149 maps
#    ("healthy","degraded") → True. A dead LIGHT service reads healthy.
# ---------------------------------------------------------------------------


def _health_aware_fake() -> FastAPI:
    """The fake + a /enrichment/health 200 route (the fake serves NO /health —
    no registry op has one). A light URL under a non-registry prefix 404s,
    standing in for a dead LIGHT service."""
    app = _fake_app()
    from fastapi.responses import JSONResponse

    @app.get("/enrichment/health")
    async def _heavy_health() -> JSONResponse:
        return JSONResponse({"status": "healthy"})

    return app


@_aio
async def test_dead_light_service_still_reads_healthy(monkeypatch, settings_factory) -> None:
    """Executed proof: heavy /health says healthy, light URL pointed at a
    prefix the fake 404s (a dead service), yet is_healthy() → True and the
    probe store shows the ONLY health call was the heavy one. The light-model
    call (classify_pet) fails (→ None via the client's 4xx map).
    PREDICTED-GREEN (characterization of the defect the plan names)."""
    from backend.services.enrichment_client import EnrichmentClient

    app = _health_aware_fake()
    store: list[dict[str, Any]] = []
    _patch_settings(
        monkeypatch,
        "backend.services.enrichment_client",
        settings_factory(enrichment_light_url=f"{FAKE_BASE}/dead"),
    )
    client = EnrichmentClient()
    _point_at(client, app, store)

    assert await client.is_healthy() is True, (
        "is_healthy() no longer True from the heavy URL alone — the "
        "dead-light-reads-healthy defect (plan :1022-1024) is FIXED"
    )
    pet = await client.classify_pet(Image.new("RGB", (8, 8)))
    assert pet is None, f"a dead light service still produced {pet!r}"
    health_calls = [c["path"] for c in store if c["path"].endswith("/health")]
    assert health_calls == ["/enrichment/health"], (
        f"health probes were {health_calls} — if a light /health probe was added, delete this pin"
    )


@_aio
async def test_every_client_health_probe_reads_down_against_the_fake(
    fake_app, monkeypatch, settings_factory
) -> None:
    """Characterization (no plan line): the fake serves NO /health (no registry
    op has one — a rollout to a gateway that also has no per-service /health
    would look EXACTLY like this), and every client maps a 404 health probe to
    "down" rather than surfacing it: DetectorClient.health_check() → False
    (:436-443 catches HTTPStatusError — the WP7.3 recon note claiming it
    ESCAPED was checked against the source at :415-448 and corrected),
    EnrichmentClient.check_health() → {"status": "error"} (:1117-1123) and
    is_healthy() → False (:1149). PREDICTED-GREEN. If a future /health op
    enters the registry, this test reddens and the health pins across the file
    should be revisited."""
    from backend.services import detector_client as dcmod
    from backend.services.enrichment_client import EnrichmentClient

    _patch_settings(monkeypatch, "backend.services.detector_client", settings_factory())
    det = dcmod.DetectorClient(max_retries=1)
    _point_at(det, fake_app)
    assert await det.health_check() is False

    enr_store: list[dict[str, Any]] = []
    _patch_settings(monkeypatch, "backend.services.enrichment_client", settings_factory())
    enr = EnrichmentClient()
    _point_at(enr, fake_app, enr_store)
    health = await enr.check_health()
    assert health["status"] == "error", health
    assert await enr.is_healthy() is False
    assert all(c["path"] == "/enrichment/health" for c in enr_store) and len(enr_store) >= 1, (
        enr_store
    )


# ---------------------------------------------------------------------------
# 5. THE RED / CHARACTERIZATION LEGS the plan expects to stay red until fixed.
# ---------------------------------------------------------------------------


@_aio
async def test_pose_analyze_raises_on_the_nameless_contract_shape(
    enrichment_client, fake_app, pil_image, captured
) -> None:
    """CHARACTERIZATION of CURRENT shipped behavior (pinned GREEN; a future
    pose-shape ruling changes the behavior, then this flips to red — this
    docstring says so). The plan drafted this leg predicted-RED; under the
    goal rule a RULING-blocked finding is pinned as a characterization of
    what ships, never left red on the branch.

    What ships: under the LIGHT default the client hits
    /enrich-lt/pose-analyze, whose fake body carries posture+alerts and
    keypoints of shape {alpha, bravo} (an additionalProperties bag — the
    committed heavy snapshot
    backend/ai_contract/schemas/enrichment_pose_analyze.response.json has NO
    name/x/y/confidence either). EnrichmentClient.analyze_pose reads
    kp["name"] first (:2226), the KeyError lands in the catch-all that logs
    "Unexpected error during pose analysis" (:2331) and re-raises
    EnrichmentUnavailableError whose message embeds the missing key repr —
    the observed chain at first in-tree contact:
    KeyError('name') -> EnrichmentUnavailableError("Unexpected error during
    pose analysis: 'name'"). So the DEPLOYED contract for pose-analyze, as
    the shipped client can actually consume it, is: nameless keypoints make
    the op UNAVAILABLE, not degraded and not partially parsed.

    RULING parked (pose keypoint shape: contract gains name/x/y/confidence,
    or the client stops requiring them): when that lands, this test goes red
    by construction and must be rewritten to the ruling's shape — that red
    is the tripwire, not a defect escaping."""
    from backend.core.exceptions import EnrichmentUnavailableError

    _point_at(enrichment_client, fake_app, captured)
    with pytest.raises(EnrichmentUnavailableError) as excinfo:
        await enrichment_client.analyze_pose(pil_image, bbox=(0.0, 0.0, 40.0, 40.0))
    # The KeyError's repr rides in the message: the ONLY way the client can
    # fail on this body is the missing keypoint key — pin that it is 'name'
    # (the first deref at :2226), so a future shape change that renames or
    # reorders fields trips here instead of masking itself.
    assert "'name'" in str(excinfo.value), str(excinfo.value)


@_aio
async def test_enrich_detection_parses_everything_away(
    enrichment_client, fake_app, pil_image, captured
) -> None:
    """/enrich characterization (PREDICTED-GREEN, documents a real hole):
    EnrichmentClient.enrich_detection posts
    {image, detection_type, bbox{x1,y1,x2,y2}, frames, options}
    (:3161-3174) and _parse_unified_response (:3048-3116) reads
    models_loaded/pose/clothing/demographics/vehicle/pet/threat/reid_embedding/
    action/depth — but NO /enrich responder emits any of those keys: the fake
    body is {detection_type, enrichments, inference_time_ms} and the gateway's
    EnrichmentResponse (adapters/enrichment.py:366-369) is the same shape. So
    every SUCCESSFUL unified call parses to an all-empty result (only
    inference_time_ms survives). If a future response starts carrying "pose",
    this test reddens and demands real parsing. NOTE: the plan's Tier A row 3
    claim that the gateway /enrich handler dereferences request.bbox was NOT
    reproducible at HEAD (the handler at :902-977 never touches bbox for
    person/vehicle) — recorded as a plan-cite correction, UNVERIFIED."""
    from backend.services.enrichment_client import UnifiedEnrichmentResult

    _point_at(enrichment_client, fake_app, captured)
    result = await enrichment_client.enrich_detection(
        b"fake-image-bytes", detection_type="person", bbox=(0.0, 0.0, 40.0, 40.0)
    )
    assert captured[-1]["path"] == "/enrichment/enrich", captured[-1]["path"]
    sent = json.loads(captured[-1]["body"])
    assert set(sent) == {"image", "detection_type", "bbox", "frames", "options"}, sent
    assert isinstance(result, UnifiedEnrichmentResult)
    for field in (
        "pose",
        "clothing",
        "demographics",
        "vehicle",
        "pet",
        "threat",
        "reid_embedding",
        "action",
        "depth",
    ):
        assert getattr(result, field) is None, (
            f"/enrich now populates {field} — update this characterization"
        )
    assert result.inference_time_ms == pytest.approx(12.5)
    assert result.models_loaded is None


@_aio
async def test_object_distance_404s_through_the_client_paths(
    monkeypatch, settings_factory, fake_app, pil_image
) -> None:
    """Client-leg of Tier A row 2's object-distance half: the client composes
    ``{light_service}/object-distance`` (:1945-1956,:2013 — the depth model's
    URL, i.e. /enrich-lt) and the registry op is BARE ``/object-distance`` on
    the per-model server only → the composed path 404s and the client's 4xx
    branch returns None, while the bare registry path answers 200
    (estimated_distance_m 3.49). PREDICTED-GREEN. UNVERIFIED: the 404 branch's
    exact shape (None vs raise); the composed-path assertion is the
    load-bearing one."""
    from backend.services.enrichment_client import EnrichmentClient

    _patch_settings(monkeypatch, "backend.services.enrichment_client", settings_factory())
    client = EnrichmentClient()
    store: list[dict[str, Any]] = []
    _point_at(client, fake_app, store)
    try:
        result = await client.estimate_object_distance(pil_image, bbox=(0.0, 0.0, 40.0, 40.0))
    except httpx.HTTPStatusError:
        result = None  # the raise-branch of the same defect
    sent = [c for c in store if c["method"] == "POST"]
    assert sent, store
    assert sent[-1]["path"] == "/enrich-lt/object-distance", sent[-1]["path"]
    assert result is None, f"unexpected {result!r} from a 404 path"
    bare = await _one_shot(
        fake_app,
        "POST",
        "/object-distance",
        json={"image": "aGVsbG8=", "bbox": {"x": 1, "y": 2, "width": 3, "height": 4}},
    )
    assert bare.status_code == 200
    assert bare.json()["estimated_distance_m"] == pytest.approx(3.49)


# ---------------------------------------------------------------------------
# 6. CLIENT-BYPASS SITES (plan :1011-1012).
# ---------------------------------------------------------------------------


class TestSceneOCRClientBypass:
    """SceneOCRService bypasses FlorenceClient: own httpx.AsyncClient (:387,
    :397-402), posts ``{florence_url}/ocr-with-regions`` (:526 full frame,
    :634 crops), re-implements the parse (:537-566). It inherits NONE of
    FlorenceClient's parse contract/breakers/timeouts — the reason WP8.4 exists.
    Driven here through the fake so at least ONE contract test covers it."""

    @_aio
    async def test_full_frame_bypass_parses_the_fake_body(self, fake_app, pil_image) -> None:
        from backend.services.scene_ocr_service import SceneOCRService

        svc = SceneOCRService(florence_url=f"{FAKE_BASE}/florence", timeout=5.0)  # ctor seam :381
        svc._client = httpx.AsyncClient(transport=ASGITransport(app=fake_app), base_url=FAKE_BASE)
        rows = await svc._run_full_frame_ocr(pil_image)
        body = await _served_body("florence_ocr_with_regions")
        assert len(rows) == len(body["regions"]), f"{len(rows)} vs {len(body['regions'])}"
        quad = body["regions"][0]["bbox"]
        xs, ys = quad[0::2], quad[1::2]
        for row in rows:
            assert row.text == body["regions"][0]["text"], row
            # quad → axis-aligned int tuple (:547-557)
            assert row.bbox == (int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))), row
            assert row.source == "frame", row
            assert row.confidence == pytest.approx(0.90), row  # default at :538

    @_aio
    async def test_crop_bypass_offsets_crop_coords(self, fake_app) -> None:
        """The crop leg (:600-700) OFFSETS crop-local coords by the crop origin
        (:663-668) — the full-frame leg above cannot catch a dropped offset.
        DetectionInput per enrichment_pipeline.py:1954-1974 with BoundingBox
        from :554. class_name "person" passes the ocr-class filter (:599).
        PREDICTED-GREEN."""
        from backend.services.enrichment_pipeline import BoundingBox, DetectionInput
        from backend.services.scene_ocr_service import SceneOCRService

        image = Image.new("RGB", (200, 200), (9, 9, 9))
        svc = SceneOCRService(florence_url=f"{FAKE_BASE}/florence", timeout=5.0)
        svc._client = httpx.AsyncClient(transport=ASGITransport(app=fake_app), base_url=FAKE_BASE)
        det = DetectionInput(
            class_name="person",
            confidence=0.9,
            bbox=BoundingBox(x1=100.0, y1=100.0, x2=150.0, y2=150.0),
            id=7,
        )
        out = await svc._run_crop_ocr(image, [det])
        assert set(out) == {"7"}, out
        rows = out["7"]
        assert rows, rows
        body = await _served_body("florence_ocr_with_regions")
        quad = body["regions"][0]["bbox"]
        xs, ys = quad[0::2], quad[1::2]
        want = (int(min(xs)) + 100, int(min(ys)) + 100, int(max(xs)) + 100, int(max(ys)) + 100)
        assert rows[0].bbox == want, rows[0].bbox
        assert rows[0].source == "crop" and rows[0].detection_id == "7"


class TestNemotronStreamingBypass:
    """nemotron_streaming.call_llm_streaming builds its own client (:96) and
    POSTs the SSE-flagged payload to ``{analyzer._llm_url}/completion`` (:99).
    The fake's llm_completion body is ``{"content": "the quick brown fox",
    "tokens_predicted": 9}`` — NOT SSE — and the parser consumes only
    ``data: ``-prefixed lines (:104-116), so the bypass yields NOTHING from a
    non-SSE provider. Pinned: this is the class of bug WP8.4 exists to expose."""

    @_aio
    async def test_streaming_leg_posts_the_registry_completion_path_and_yields_nothing(
        self, nemotron_analyzer, fake_app, monkeypatch
    ) -> None:
        import backend.services.nemotron_streaming as streammod
        from backend.services.nemotron_streaming import call_llm_streaming

        store: list[dict[str, Any]] = []
        real_client = httpx.AsyncClient

        def _client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
            # nemotron_streaming.py:96 calls httpx.AsyncClient(analyzer._timeout)
            # — positional; normalize before injecting the transport.
            kwargs = dict(kwargs)
            if args:
                kwargs.setdefault("timeout", args[0])
            kwargs["transport"] = _RecordingTransport(fake_app, store)
            return real_client(**kwargs)

        class _HttpxShim:
            """Module-local ``httpx`` rebind — the real httpx module is never
            patched (monkeypatch restores the streaming module's attribute)."""

            AsyncClient = _client
            Timeout = httpx.Timeout
            ConnectError = httpx.ConnectError
            TimeoutException = httpx.TimeoutException
            HTTPError = httpx.HTTPError

        monkeypatch.setattr(streammod, "httpx", _HttpxShim())

        chunks = [
            c
            async for c in call_llm_streaming(
                nemotron_analyzer,
                camera_name="porch",
                start_time="2026-09-19T00:00:00+00:00",
                end_time="2026-09-19T00:01:00+00:00",
                detections_list="a person at the door",
            )
        ]
        assert store, "streaming bypass sent no request"
        assert store[-1]["path"] == OPERATIONS["llm_completion"].path, store[-1]["path"]
        payload = json.loads(store[-1]["body"])
        assert payload["stream"] is True, payload
        assert {"prompt", "temperature", "top_p", "max_tokens", "stop"} <= set(payload), payload
        assert chunks == [], (
            f"the streaming parser yielded {chunks!r} from a NON-SSE body — the "
            "parser is no longer SSE-only; re-read nemotron_streaming.py:104-116"
        )


# ---------------------------------------------------------------------------
# 7. NemotronAnalyzer client legs (llm_completion contract).
# ---------------------------------------------------------------------------


@_aio
async def test_nemotron_posts_the_contract_payload_and_reads_content(
    nemotron_analyzer, fake_app, captured
) -> None:
    """NemotronAnalyzer._call_llm_with_version (:1003-1065) posts
    {prompt, temperature, top_p, max_tokens, stop} to ``{llm_url}/completion``
    (:1045-1049) and reads ``content`` (:1054) before parse (:1059→:4257) and
    risk validation (:1062→:4348). The contract's own body has prose in
    ``content`` ("the quick brown fox"), so the honest contract-level pins are:
    path, payload keys, and that the client RAISES (ValueError) when there is
    no parsable risk JSON — i.e. ``content`` is load-bearing. PREDICTED-GREEN.
    UNVERIFIED: the exact ValueError message text; matched loosely. NOTE the
    facade-free path: _call_llm (:3811) needs
    get_inference_semaphore()/the service facade, so this leg drives
    _call_llm_with_version directly, which is what _call_llm delegates to."""
    _point_at(nemotron_analyzer, fake_app, captured)
    with pytest.raises(ValueError):
        await nemotron_analyzer._call_llm_with_version("a person at the door")
    assert captured[-1]["path"] == "/completion", captured[-1]["path"]
    sent = json.loads(captured[-1]["body"])
    assert {"prompt", "temperature", "top_p", "max_tokens", "stop"} <= set(sent), sent


def _risk_json() -> str:
    return json.dumps(
        {
            "risk_score": 82,
            "risk_level": "high",
            "summary": "person testing the door handle",
            "reasoning": "repeated loitering with deliberate interaction",
        }
    )


@_aio
async def test_nemotron_parses_a_contract_shaped_risk_json(monkeypatch, settings_factory) -> None:
    """The positive form: with ``content`` carrying risk JSON (the fake's seeded
    default is prose), the client's chain yields those exact values. Done by
    wrapping ONLY /completion on the fake — zero production change.
    PREDICTED-GREEN. UNVERIFIED: _parse_llm_response's tolerance for extra /
    missing optional keys and whether risk validation rewrites any of the four
    values (:4348 region) — the four-key assertion is what the prompt schema
    promises."""
    inner = _fake_app()

    async def llm_json_app(scope, receive, send):  # ASGI callable
        if scope["type"] != "http" or scope["path"] != "/completion":
            await inner(scope, receive, send)
            return
        body = json.dumps({"content": _risk_json(), "tokens_predicted": 9}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    _patch_settings(monkeypatch, "backend.services.nemotron_analyzer", settings_factory())
    from backend.services.nemotron_analyzer import NemotronAnalyzer

    analyzer = NemotronAnalyzer(
        redis_client=object(),
        use_enriched_context=False,
        use_enrichment_pipeline=False,
        max_retries=1,
        service_facade=MagicMock(),
    )
    analyzer._http_client = httpx.AsyncClient(
        transport=ASGITransport(app=llm_json_app), timeout=analyzer._timeout
    )
    risk = await analyzer._call_llm_with_version("a person at the door")
    assert risk["risk_score"] == 82, risk
    assert risk["risk_level"] == "high", risk
    assert risk["summary"] == "person testing the door handle", risk


# ---------------------------------------------------------------------------
# 8. COVERAGE GUARD: the registry's client_methods column can no longer be a
#    comment — every declared method is claimed by a test in this file.
# ---------------------------------------------------------------------------

_COVERAGE = {
    # happy-path parametrization
    **dict.fromkeys(
        (
            "FlorenceClient.extract",
            "FlorenceClient.ocr",
            "FlorenceClient.ocr_with_regions",
            "FlorenceClient.detect",
            "FlorenceClient.dense_caption",
            "FlorenceClient.describe_regions",
            "FlorenceClient.phrase_grounding",
            "FlorenceClient.detect_security_objects",
            "CLIPClient.embed",
            "CLIPClient.classify",
            "CLIPClient.similarity",
            "CLIPClient.batch_similarity",
            "CLIPClient.anomaly_score",
            "EnrichmentClient.classify_vehicle",
            "EnrichmentClient.classify_pet",
            "EnrichmentClient.classify_clothing",
            "EnrichmentClient.analyze_demographics",
            "EnrichmentClient.detect_threats",
            "EnrichmentClient.compute_reid_embedding",
            "EnrichmentClient.estimate_depth",
            "EnrichmentClient.classify_action",
        ),
        "test_client_parsed_output_matches_the_contract",
    ),
    "FlorenceClient.batch_extract": "test_florence_batch_extract_parses_per_row_fields",
    "DetectorClient.detect_objects": "test_detector_client_detect_objects_parses_the_shipped_bbox_dict",
    "DetectorClient.segment_image": "TestTierASegmentOnlyOnGateway.test_segment_succeeds_through_the_gateway_prefix",
    "EnrichmentClient.analyze_pose": "test_pose_analyze_raises_on_the_nameless_contract_shape",
    "EnrichmentClient.enrich_detection": "test_enrich_detection_parses_everything_away",
    "EnrichmentClient.estimate_object_distance": "test_object_distance_404s_through_the_client_paths",
    "EnrichmentClient.get_model_status": "TestTierAMissingPaths.test_client_model_status_404s_on_gateway_prefix_and_works_bare",
    "EnrichmentClient.preload_model": "TestTierAMissingPaths.test_client_model_status_404s_on_gateway_prefix_and_works_bare",
}


def test_every_registry_declared_client_method_is_driven() -> None:
    """MEASURE hook (plan :1024): ``client_methods`` is a registry CLAIM that
    the client speaks the op; every claim must be covered here, and this
    module may not claim methods the registry retired. PREDICTED-GREEN: 29
    declared methods, all mapped above (verified against
    OPERATIONS[*].client_methods at draft time)."""
    declared = {m for op in OPERATIONS.values() for m in op.client_methods}
    missing = sorted(declared - set(_COVERAGE))
    extra = sorted(set(_COVERAGE) - declared)
    assert not missing, f"registry client_methods with NO client-level test: {missing}"
    assert not extra, f"_COVERAGE names methods the registry no longer declares: {extra}"


# ---------------------------------------------------------------------------
# 9. Deliberately NOT asserted here, with the reason (scope notes, not skips).
# ---------------------------------------------------------------------------
# * FlorenceClient's legacy ``<region:>`` bbox prompt protocol
#   (florence_client.py ~:600-640) — prompt-echo contract, owned by WP8.3's
#   numeric/geometry suites; the fake echoes the snapshot, not the prompt.
# * EnrichmentPipeline / NemotronAnalyzer full ``analyze()`` legs need DB +
#   Redis + the real facade; the repo's own unit suites own that wiring. WP8.4's
#   stated scope is the CLIENT layer against the fake.
# * /v1/chat/completions (llm_chat_completion) and /slots (llm_slots): no
#   backend client method declares them (registry client_methods is empty for
#   those ops) — nothing in this tier to drive; the coverage guard above
#   reddens if a client ever claims them without a test here.
# * GET /models/status against ai/enrichment/model.py directly (the real
#   server) needs the native enrichment service; the fake + registry cites
#   carry that leg at unit-ASGI level.

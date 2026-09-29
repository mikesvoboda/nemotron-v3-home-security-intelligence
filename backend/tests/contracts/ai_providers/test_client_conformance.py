"""WP8.4 — drive the real backend AI clients through the FakeProvider.

INTEGRATED (2026-09-19): drafted under /tmp with a draft-only conftest (not
carried over — the repo tier gets ENVIRONMENT=test from
backend/tests/conftest.py:107 and the autouse settings-cache reset around
every test, so the autouse cache-clear below is redundant but harmless).
First in-tree pytest contact: 82 passed / 1 failed — the single failure was
the ONE predicted-red leg (pose keypoint shape), exactly the draft's
predicted-red list. Per the goal rule (branch stays GREEN; a RULING-blocked
finding is pinned as a characterization, never left red) that leg pinned the
shipped raise — until R8 S2 deleted its subject with the tier (below).
Residual ``# UNVERIFIED:`` tags below mark claims the draft guessed that the
in-tree run has since confirmed or reframed; each names its own status.
There is **no xfail, no skip, no importorskip anywhere in this file** (goal
rule). Never respx: every hop is ``httpx.ASGITransport`` (goal rule; the fake
IS an app — backend/ai_contract/fake/app.py).

DRIVEN HERE SINCE R8 S2 (2026-09-29): DetectorClient, FlorenceClient,
CLIPClient, VlmClient — the four AI clients that survived the legacy-tier
deletion. ``EnrichmentClient``, ``NemotronAnalyzer`` and
``nemotron_streaming`` were deleted with the tier, so the legs that drove them
went with them; where the driven BEHAVIOR survived in shipped code it was
re-pointed rather than dropped (the ``/completion`` client-BYPASS legs now run
against ``SummaryGenerator``, one of the three surviving sites). The
``enrich*`` ops those clients spoke for are still IN the registry (deployed
gateway surface) and stay under contract in the gateway-side classes below —
they are simply no longer reachable through a backend client, which is exactly
what ``test_conformance_ops.py``'s NOT-WIRED census now pins.

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
clip_client.py:152) against a DNS name that does not exist here — so the seam
is always
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
* VlmClient             — takes its transport in ``__init__`` (no pool swap);
  dedicated leg in section 7.
* SceneOCRService (client-BYPASS site, plan :1011) — real ctor url kwarg
  (backend/services/scene_ocr_service.py:381) + LAZY pool (:412):
  pre-seed ``svc._client`` with an ASGITransport client.
* SummaryGenerator._call_nemotron (client-BYPASS family, plan :1012's
  successor) — builds its own client INSIDE the method
  (summary_generator.py:441, ``httpx`` imported at module level :27) and posts
  ``{settings.ai_vlm_url}/completion`` (:443). Seam: rebind the name ``httpx``
  ON THE SERVICE MODULE (monkeypatch, auto-restored) to a shim that injects the
  transport. The real httpx module is never patched. The same shape is used by
  prompt_service.py:938 and pipeline_quality_audit_service.py:390.

=============================================================================
CONTRACT FACTS THIS FILE RELIES ON (all read from the tree at HEAD a8c25c5e)
=============================================================================
* The fake mounts one route per registry op with no prefix (fake/app.py) —
  and the registry paths ALREADY carry the service prefixes
  (/florence/extract, /clip/embed, /enrichment/vehicle-classify,
  /enrich-lt/person-reid, /models/status, /object-distance, /completion,
  /yolo26/segment). The gateway mounts its five adapter routers under THE SAME
  prefixes (ai/gateway/main.py:181-185), so one base_url works against either
  app — that is what makes every gateway-vs-fake pair below legible.
* Service defaults (config.py:1642-1663): pose/threat/reid/pet/depth → LIGHT,
  vehicle/clothing/action/demographics → HEAVY — the split that decided which
  prefix the retired EnrichmentClient resolved per model; the settings fields
  still drive ai/gateway routing reports (model_management.py:157-168).
* The fake performs NO request validation (it parses the body only to echo
  model_name) and always answers 200 on registry paths → it can never 422.
  Every 422/404 pin therefore drives the real gateway adapter routers, and the
  fake side of those tests pins the 200. The asymmetry IS the finding.
* The fake serves NO /health route (no registry op has one): every client
  health probe 404s against the bare fake (characterized for DetectorClient,
  FlorenceClient and CLIPClient in section 4).
* Deterministic fake values were dumped at draft time via
  ``backend.ai_contract.fake.generate(op_id)`` (profile "gateway"); the
  literals below are those dumps. A change to the generator seed logic reddens
  this file BY DESIGN — that is the point (fake ⇄ client lockstep).

Cites relied on (re-verify any that a rebase moves):
  plan §WP8.4 :1001-1026; Tier A table :769-800
  backend/ai_contract/operations.py (38 ops; availability flags; client_methods)
  backend/ai_contract/fake/{__init__.py,app.py,generators.py} (generate/snapshot)
  backend/services/detector_client.py:73,103,262,287,321,325,415,993,1054,1169,1187,1208-1213,1286,1301 (re-spaced -123 by the A7.2 segment_image deletion; 981/1032 died with it)
  backend/services/florence_client.py:73(BoundingBox),309,321,368,561,582,727,749-752,881,980,998,1083,1102-1104,1189,1299,1411,1432-1434,1524,1543-1563
  backend/services/clip_client.py:54,99,111,152,332,352-366,488-493,512,680,700-701,830,983,1005
  backend/services/summary_generator.py:87,441,443-447,452 (R8 S2 re-home)
  backend/services/prompt_service.py:681,938-947; backend/services/pipeline_quality_audit_service.py:137,390-398
  backend/services/scene_ocr_service.py:57-66(DetectionLike),381,412,526,547-557,634,663-668
  backend/models/detection.py:29,54-67
  backend/api/routes/model_management.py:152-169(get_router_urls),306-338(_fetch_router_health) (R8 S2 re-home; the :186/:486 EnrichmentClient call sites died with it — lifecycle routes are 501)
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
            # heavy/light prefixes: no backend client resolves them any more
            # (EnrichmentClient was deleted in R8 S2), but the fields are live
            # settings read by the gateway-routing report (model_management.py
            # :157-168), so the fixture still pins them off-box.
            "enrichment_url": f"{FAKE_BASE}/enrichment",  # heavy
            "enrichment_light_url": f"{FAKE_BASE}/enrich-lt",  # light
            # The /completion endpoint (registry op is bare /completion):
            # R8 S2 re-homed every consumer of the retired nemotron_url onto
            # ai_vlm_url (summary_generator.py:87, prompt_service.py:681,
            # pipeline_quality_audit_service.py:137, providers.py
            # _llamacpp_callable), so this is the survivor's field.
            "ai_vlm_url": FAKE_BASE,
            "use_ai_gateway": False,
            "ai_gateway_url": None,
            "detector_max_retries": 1,
            "enrichment_max_retries": 1,
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
# ROUTED to — asserting store path == OPERATIONS[op].path pins the client's URL
# composition as well as the parse. Since R8 S2 the table holds only the
# surviving FlorenceClient/CLIPClient rows: the EnrichmentClient block that
# used to sit here (8 heavy/light routing rows) went with its client, and the
# heavy/light routing it pinned is no longer a CLIENT behavior — the ops stay
# in the registry and stay contracted gateway-side (see the tier-A gateway
# classes below and test_conformance_ops.py's NOT-WIRED census).
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
    # The EnrichmentClient block that used to continue this table (8
    # heavy/light routing rows) and the _REDACTED_METHODS dict below it went
    # with the client in R8 S2 — see the module docstring; their registry
    # residue is census-pinned in test_conformance_ops.py.
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
        if "len" in exp:  # list[float] return (the retired reid row's
            # ``embedding_dim`` guard went with it — ``len`` alone is exact now)
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
    # The 8 enrichment.* rows went with EnrichmentClient in R8 S2 (the
    # fake-vs-client sensitivity they proved needs a client to be sensitive);
    # the ops' key sets stay contract-pinned by test_schema_snapshots.py and
    # test_conformance_ops.py on the gateway side.
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


def test_person_reid_contract_still_declares_embedding_dimension() -> None:
    """Re-homed in R8 S2 from test_reid_key_drift_masked_by_len_default: the
    blind spot that test pinned lived in EnrichmentClient.compute_reid_
    embedding's ``embedding_dim``-with-default-len(embedding) read, and the
    client was deleted with the tier — the client half cannot be re-pointed
    (no survivor reads this op through a client; it is NOT-WIRED, census in
    test_conformance_ops.py). The CONTRACT half stays pinned: the fake's body
    carries ``embedding_dimension`` (never ``embedding_dim``), so a contract
    rename still trips a witness here and a future client that reads the key
    gets a red test, not a silent default. PREDICTED-GREEN."""
    raw = _fake_body("enrich_lt_person_reid")
    assert "embedding_dimension" in raw, "contract key renamed — revisit any re-wiring"
    assert "embedding_dim" not in raw
    assert len(raw["embedding"]) == 512


# ---------------------------------------------------------------------------
# 3. TIER A DEFECT PINS AT THE ASGI LEVEL (plan §WP7.3 table :769-800).
#    Real gateway adapter routers, real client code.
# ---------------------------------------------------------------------------


class TestTierABboxShape422:
    """Tier A row 1: heavy gateway types bbox ``dict[str,float]``
    (ai/gateway/adapters/enrichment.py:292-296) while the legacy client sent
    ``list(bbox)`` (EnrichmentClient.py:1203,:1583 — cites frozen; the client
    was deleted in R8 S2). vehicle/clothing default to heavy
    (config.py:1373-1408) → the production call 422s. ASGI proof: gateway 422
    vs fake 200. The client-wire leg that completed this pair is gone with
    its client (R8 S2); since no shipped caller speaks the list shape any
    more, the two gateway legs stay as a deployed-surface guard — a fix that
    widens the adapter's bbox acceptance reddens the pin and its message
    says what to delete."""

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

    # test_client_sends_a_list_on_the_wire deleted with R8 S2: its subject was
    # EnrichmentClient's wire shape, and that client is gone.

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
    gateway=False; grep over ai/gateway/adapters/ returns nothing). The
    backend callers that made that absence a DEFECT — EnrichmentClient
    .get_model_status/.preload_model — were deleted in R8 S2, and
    model_management.py's surviving router calls target ``{router}/health``
    (a real gateway surface), so what stays here is the pure topology guard:
    absent on the gateway adapters, served bare on the registry/fake."""

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
    @pytest.mark.timeout(20)
    @_aio
    async def test_registry_paths_unreachable_on_gateway_but_live_on_fake(
        self, gateway_client, fake_app
    ) -> None:
        """The E2E half of this row, re-homed in R8 S2 from
        EnrichmentClient.get_model_status/.preload_model (that client drove
        the same composition through real client code). ``{router}/models/
        status`` is exactly the shape a settings-fed base URL composes for
        the registry's bare ``/models/status`` op — still gateway=False
        (the adapter routers expose /health + the registry ops; the
        :1121 adapter /health is NOT a registry op and not a models path),
        while the bare registry path serves 200 on the fake. The op is
        NOT-WIRED (no backend client speaks it since the deletion), so this
        pins the topology the moment anything re-wires it."""
        for client_path in ("/enrichment/models/status", "/enrich-lt/models/status"):
            r = await gateway_client.get(client_path)
            assert r.status_code == 404, (
                f"{client_path} returned {r.status_code} on the gateway app — "
                "the absence moved; re-verify Tier A row 2"
            )
        op = OPERATIONS["model_status"]
        r2 = await _one_shot(fake_app, op.method, op.path, **_request_kwargs("model_status"))
        assert r2.status_code == 200, f"bare {op.path} not served: {r2.status_code}"

    @pytest.mark.timeout(20)
    @_aio
    async def test_router_health_probe_resolves_off_settings_and_reads_a_router_health(
        self, gateway_client, fake_app, monkeypatch, settings_factory
    ) -> None:
        """The surviving-backend-caller fact (re-homed in R8 S2): the legacy
        clients died, but model_management's readiness surface still derives
        its probe URLs from settings — get_router_urls (:152-169) reads the
        SAME enrichment_url / enrichment_light_url fields the deleted
        EnrichmentClient resolved, and gateway mode composes
        ``{root}/enrichment`` + ``{root}/enrich-lt`` from ai_gateway_url.
        Pinned: (a) that composition; (b) ``{router}/health`` IS a live
        gateway surface on BOTH routers (adapters/enrichment.py:1121 and the
        light adapter's twin answer {status, models} — the Tier A row 2
        absence is about the models/status PRELOAD surface probed above, not
        about /health) and _fetch_router_health (:306-338) reads it through
        the same helper the readiness report uses; (c) on a non-200 the
        helper swallows to None — probed against a fake-based router URL
        (the fake serves NO /health, section 4) — so a missing surface reads
        as "router unavailable", never as "route missing": the silent-degrade
        shape this file keeps watching. gateway_client's five
        get_triton_client patches make the adapter handlers hermetic
        (is_model_ready → True → "healthy")."""
        from backend.api.routes import model_management as mm

        _patch_settings(
            monkeypatch,
            "backend.api.routes.model_management",
            settings_factory(
                ai_gateway_url=FAKE_BASE,
                use_ai_gateway=True,
                enrichment_url=f"{FAKE_BASE}/enrichment",
                enrichment_light_url=f"{FAKE_BASE}/enrich-lt",
            ),
        )
        heavy, light = mm.get_router_urls()
        assert (heavy, light) == (f"{FAKE_BASE}/enrichment", f"{FAKE_BASE}/enrich-lt"), (
            "get_router_urls' gateway-mode composition changed — re-read "
            "model_management.py:152-169 before trusting either probe leg"
        )
        for url in (heavy, light):
            payload = await mm._fetch_router_health(gateway_client, url)
            assert payload is not None and payload["status"] == "healthy", (url, payload)
        async with httpx.AsyncClient(
            transport=ASGITransport(app=fake_app), base_url=FAKE_BASE
        ) as probe:
            assert await mm._fetch_router_health(probe, f"{FAKE_BASE}/enrich-lt") is None, (
                "a /health appeared for this base on the fake — either a registry "
                "op grew one (revisit every health pin in this file) or the "
                "helper's swallow-to-None broke"
            )


class TestTierAUnloadPathMismatch:
    """Tier A row 3 (half remaining): the server's canonical route is
    ``POST /models/unload`` with model_name as a QUERY param
    (ai/enrichment/model.py:3552; the registry op model_unload path agrees).
    The backend's former ``POST /models/{name}/unload`` proxy leg is gone —
    model_management.py's lifecycle routes return 501 without egress after
    the ai-gateway consolidation — so the client-side AST pin that asserted
    the wrong shape still shipped was deleted when that fix landed; the
    registry-shape leg below stays as the durable guard."""

    @_aio
    async def test_registry_unload_is_query_param_not_path_param(self, fake_app) -> None:
        assert OPERATIONS["model_unload"].path == "/models/unload"
        r = await _one_shot(fake_app, "POST", "/models/unload", params={"model_name": "pose"})
        assert r.status_code == 200, r.text[:200]
        assert "/models/{model_name}/unload" not in {op.path for op in OPERATIONS.values()}
        r2 = await _one_shot(fake_app, "POST", "/models/pose/unload")
        assert r2.status_code == 404, (
            "the /models/{name}/unload shape is now served — Tier A row 3's "
            "server side grew a path-param route; re-verify the registry op"
        )


class TestTierASegmentOnlyOnGateway:
    """Tier A row 4: /segment exists ONLY on the gateway
    (adapters/yolo26.py:447; registry per_model_server=False). The client-
    driven legs that used to live here (DetectorClient.segment_image posted
    the bare ``{detector_url}/segment`` and 404ed off the gateway prefix)
    went with the A7.2 deletion — zero non-test callers, census in that
    commit body. The TOPOLOGY fact survives the client: the gateway still
    serves /yolo26/segment, the native server still does not, and the fake
    still serves the op (test_conformance_vocabulary drives it). The parity
    checker's golden D4 pins the same matrix row from the AST side."""

    def test_matrix_says_gateway_only(self) -> None:
        op = OPERATIONS["yolo26_segment"]
        assert op.availability["gateway"] is True
        assert op.availability["per_model_server"] is False, (
            "the matrix now claims /segment on the per-model server — re-read "
            "ai/yolo26/model.py (plan grep: 0 hits)"
        )


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
# 4. is_healthy/check_health characterization (plan :1022-1024's surviving
#    half). The defect the plan pinned — "is_healthy probes ONLY the heavy
#    base URL, a dead LIGHT service reads healthy" — was an
#    EnrichmentClient property; the client died with R8 S2 and took the defect
#    with it: there is no heavy/light client-side split left to probe. What
#    survives is the surrounding fact the plan's recon depended on: the fake
#    serves NO /health (no registry op has one), and every surviving client
#    maps a failed health probe to "down" rather than surfacing it.
# ---------------------------------------------------------------------------


@_aio
async def test_every_client_health_probe_reads_down_against_the_fake(
    fake_app, monkeypatch, settings_factory
) -> None:
    """Characterization (re-homed in R8 S2 from the Detector+Enrichment pair
    to the three surviving pooled clients): the fake serves NO /health (no
    registry op has one — a rollout to a gateway that also has no per-service
    /health would look EXACTLY like this), and every client maps a failed
    health probe to "down" rather than surfacing it:
    DetectorClient.health_check() → False (detector_client.py:436-443 catches
    HTTPStatusError — the WP7.3 recon note claiming it ESCAPED was checked
    against the source at :415-448 and corrected), and
    FlorenceClient.check_health() / CLIPClient.check_health() → False
    (each posts ``{base}/health`` — a path NOT in the registry, so the bare
    fake 404s — catches HTTPStatusError, logs, returns False;
    florence_client.py:~490-510, clip_client.py:~270-290). The retired
    EnrichmentClient's {"status": "error"} leg went with its client.
    PREDICTED-GREEN. If a future /health op enters the registry, this test
    reddens and the health pins across the file should be revisited."""
    from backend.services import detector_client as dcmod
    from backend.services.clip_client import CLIPClient
    from backend.services.florence_client import FlorenceClient

    _patch_settings(monkeypatch, "backend.services.detector_client", settings_factory())
    det = dcmod.DetectorClient(max_retries=1)
    _point_at(det, fake_app)
    assert await det.health_check() is False

    # The house _point_at swaps _http_client AND _health_http_client, so both
    # probe pools speak to the fake; ctor base_url is the same seam the
    # dedicated fixtures use.
    flo = FlorenceClient(base_url=f"{FAKE_BASE}/florence")
    _point_at(flo, fake_app)
    assert await flo.check_health() is False

    clip = CLIPClient(base_url=f"{FAKE_BASE}/clip")
    _point_at(clip, fake_app)
    assert await clip.check_health() is False


# ---------------------------------------------------------------------------
# 5. THE RED / CHARACTERIZATION LEGS the plan expected to stay red until fixed.
#    EMPTY as of R8 S2: all five legs (pose keypoint shape, /enrich parse-away,
#    object-distance 404 path, gateway-prefix models/status, dead-light-reads-
#    healthy) characterized ENRICHMENTCLIENT behavior, and that client was
#    deleted with the legacy tier. Their contract-side residuals — the ops are
#    still registry entries with gateway routes, still unreachable through any
#    backend client — are now pinned by test_conformance_ops.py's NOT-WIRED
#    census (SENTINELS_BY_PROVIDER), not here. The section number stays so the
#    header cites in the rename table above keep resolving.
# ---------------------------------------------------------------------------


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
        R8 S2 re-home: the crop path's nominal input type
        ``enrichment_pipeline.DetectionInput`` retired with the tier; the
        service now reads a structural ``DetectionLike`` protocol (.id /
        .class_name / .bbox, scene_ocr_service.py:52-66) whose bbox contract
        is ``to_int_tuple()`` — so the witnesses here are florence_client's
        BoundingBox (:75, it carries to_int_tuple) and a local stand-in for
        the detection row itself. class_name "person" passes the ocr-class
        filter (:599). PREDICTED-GREEN."""
        from dataclasses import dataclass

        from backend.services.florence_client import BoundingBox
        from backend.services.scene_ocr_service import SceneOCRService

        @dataclass
        class _Det:
            """DetectionLike witness — .id/.class_name/.bbox, nothing else."""

            id: int | None
            class_name: str
            bbox: BoundingBox

        image = Image.new("RGB", (200, 200), (9, 9, 9))
        svc = SceneOCRService(florence_url=f"{FAKE_BASE}/florence", timeout=5.0)
        svc._client = httpx.AsyncClient(transport=ASGITransport(app=fake_app), base_url=FAKE_BASE)
        det = _Det(
            class_name="person",
            id=7,
            bbox=BoundingBox(x1=100.0, y1=100.0, x2=150.0, y2=150.0),
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


class TestSummaryGeneratorCompletionBypass:
    """The /completion client-BYPASS family (plan :1012's successor — its
    original subject nemotron_streaming was deleted in R8 S2, and the shipped
    code this leg now drives is one of the three surviving {ai_vlm_url}/
    completion sites). SummaryGenerator._call_nemotron builds its own client
    INSIDE the method (summary_generator.py:441, ``httpx`` imported at module
    level :27) and posts {settings.ai_vlm_url}/completion (:443-447) — no
    pooled client to swap, so the seam is the module-local ``httpx`` rebind
    (monkeypatched HERE, auto-restored) to a shim that injects the transport;
    the real httpx module is never patched. Same shape covers
    prompt_service.py:938 and pipeline_quality_audit_service.py:390."""

    @_aio
    async def test_completion_leg_posts_the_registry_path_and_reads_content(
        self, fake_app, monkeypatch, settings_factory
    ) -> None:
        from datetime import UTC, datetime

        import backend.services.summary_generator as sgmod

        store: list[dict[str, Any]] = []
        real_client = httpx.AsyncClient

        def _client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
            # summary_generator.py:441 calls httpx.AsyncClient(timeout=...) —
            # keyword; normalize anyway before injecting the transport.
            kwargs = dict(kwargs)
            if args:
                kwargs.setdefault("timeout", args[0])
            kwargs["transport"] = _RecordingTransport(fake_app, store)
            return real_client(**kwargs)

        class _HttpxShim:
            """Module-local ``httpx`` rebind — the real module is untouched."""

            AsyncClient = _client
            Timeout = httpx.Timeout
            ConnectError = httpx.ConnectError
            TimeoutException = httpx.TimeoutException
            HTTPError = httpx.HTTPError

        _patch_settings(monkeypatch, "backend.services.summary_generator", settings_factory())
        monkeypatch.setattr(sgmod, "httpx", _HttpxShim())

        svc = sgmod.SummaryGenerator()
        assert svc._llm_url == FAKE_BASE, (
            "the re-home broke: _llm_url must default to settings.ai_vlm_url "
            "(summary_generator.py:87) — the fake's /completion route hangs "
            "off exactly that base"
        )
        out = await svc._call_nemotron(
            datetime(2026, 9, 29, tzinfo=UTC),
            datetime(2026, 9, 29, 1, tzinfo=UTC),
            "hour",
            [],
        )
        assert store, "the /completion bypass sent no request at all"
        assert store[-1]["path"] == OPERATIONS["llm_completion"].path, store[-1]["path"]
        payload = json.loads(store[-1]["body"])
        # The service's OWN payload contract (:429-436) + the ChatML prompt it
        # is built from; no "stream" key — the SSE-flagged variant died with
        # nemotron_streaming, and this site never set it.
        assert {"prompt", "temperature", "top_p", "max_tokens", "stop"} <= set(payload), payload
        assert "stream" not in payload, payload
        assert "<|im_start|>" in payload["prompt"], "ChatML framing lost from the prompt"
        # The fake's llm_completion body is {"content": "the quick brown fox",
        # "tokens_predicted": 9} — the client reads ``content`` verbatim
        # (:452), so a contract rename of that key would raise ValueError
        # ("Empty completion from LLM") and redden this leg.
        assert out == "the quick brown fox", out


# ---------------------------------------------------------------------------
# 7. VlmClient legs (llm/vlm contract) — the NemotronAnalyzer legs that used
#    to sit in this section went with the analyzer in R8 S2; the /completion
#    payload+content pins they carried re-homed to
#    TestSummaryGeneratorCompletionBypass above, and the risk-JSON parse leg
#    had no survivor (no shipped code parses that JSON any more).
# ---------------------------------------------------------------------------


@_aio
async def test_vlm_client_assess_round_trips_the_generated_verdict(
    settings_factory, tmp_path
) -> None:
    """1.3's COVERAGE leg for VlmClient.assess - DEDICATED, not a table row,
    because of the divergence the registry itself records: the fake answers
    the op at its CONTRACT path /vlm/chat/completions (one route per op.path;
    /v1/chat/completions is already taken by llm_chat_completion) while the
    client dials the ENGINE wire /v1/chat/completions (op.evidence). A shared
    table asserting `sent path == op.path` would RED by design here, so this
    leg pins the engine path itself, then checks the half the table owns: the
    client's PARSED fields equal the contract body the fake served.

    The shim below is what a chat server actually does: it forwards the
    client's bytes to the fake's own vlm_assess handler and puts the
    verdict JSON in choices[0].message.content. Nothing here hand-writes a
    verdict - the answer is the generator's, so a contract rename reddens it.
    Probe off: the §3 gate has its own hermetic tier (test_vlm_client.py);
    the fake has no grammar to prove."""
    from backend.ai_contract.fake import create_fake_app
    from backend.ai_contract.fake import generate as _gen
    from backend.services.vlm_client import VlmClient
    from backend.services.vlm_verdict import VlmAssessRequest

    root = tmp_path / "foscam"
    (root / "front").mkdir(parents=True)
    (root / "front" / "a.jpg").write_bytes(b"\xff\xd8\xff" + b"\x00" * 32)  # D10 synthetic

    contract_app = create_fake_app()

    async def _engine_asgi(scope: Any, receive: Any, send: Any) -> None:
        """Raw ASGI (a FastAPI route would need a module-level Request
        annotation for get_type_hints; this is the same hand-rolled shape as
        the llm_json_app echo app above). Forward the client's bytes to the
        fake's vlm_assess handler and wrap its verdict the way a chat server
        does - the envelope is ours, the PAYLOAD is the generator's."""
        body = b""
        while True:
            event = await receive()
            body += event.get("body", b"")
            if not event.get("more_body", False):
                break
        assert scope["type"] == "http" and scope["method"] == "POST"
        async with AsyncClient(
            transport=ASGITransport(app=contract_app), base_url=FAKE_BASE
        ) as inner:
            answer = await inner.post(OPERATIONS["vlm_assess"].path, content=body)
        assert answer.status_code == 200, answer.text[:200]
        payload = json.dumps(
            {"choices": [{"message": {"content": answer.text}}], "usage": {"total_tokens": 7}}
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(payload)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": payload})

    settings = settings_factory(
        foscam_base_path=str(root),
        vlm_enforcement_probe_enabled=False,
    )
    # VlmClient takes its transport in __init__ (no pool swap needed - the
    # house _point_at looks for _http_client, which this client never had).
    store: list[dict[str, Any]] = []
    client = VlmClient(
        base_url=FAKE_BASE,
        transport=_RecordingTransport(_engine_asgi, store),
        settings=settings,
    )

    req = VlmAssessRequest(
        image_paths=["front/a.jpg"],
        context={
            "camera_id": "front",
            "detections": [{"object_type": "person", "confidence": 0.9}],
            "zones": ["porch"],
            "timestamp": "2026-09-25T12:00:00+00:00",
        },
    )
    verdict = await client.assess(req)
    await client.close()

    assert store, "VlmClient.assess sent no request at all"
    sent = store[-1]
    assert sent["method"] == "POST"
    assert sent["path"] == "/v1/chat/completions", (
        "the client left the engine wire for the contract handle - the "
        "registry PATH is a fake mount point, not the llama.cpp spelling"
    )
    chat = json.loads(sent["body"])
    content = chat["messages"][0]["content"]
    uris = [p["image_url"]["url"] for p in content if p["type"] == "image_url"]
    assert len(uris) == 1 and uris[0].startswith("data:image/"), "image part lost"
    assert chat["response_format"]["json_schema"]["schema"]["properties"], (
        "the nested arm-B wrapper must carry the schema"
    )
    # The generator the fake's handler ran on THESE bytes (the chat body has
    # no image_paths key, so the walk shape answers, seeded op+profile).
    served = json.loads(json.dumps(_gen("vlm_assess", chat, "gateway")))
    # Provenance is the client's stamp of the served identity, never the
    # model's copy (A5500 2026-09-28: the model wrote the camera id there).
    # No /props here, so the stamp is the configured label and model id.
    parsed = verdict.model_dump()
    assert parsed.pop("provenance") == {
        "engine": settings.nemotron_verification_engine,
        "model_id": settings.vlm_model_id,
    }, "provenance must be stamped by the client, not parsed from the reply"
    served.pop("provenance")
    assert parsed == served, "client parse diverged from the contract body the fake served"


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
        ),
        "test_client_parsed_output_matches_the_contract",
    ),
    "FlorenceClient.batch_extract": "test_florence_batch_extract_parses_per_row_fields",
    "DetectorClient.detect_objects": "test_detector_client_detect_objects_parses_the_shipped_bbox_dict",
    "VlmClient.assess": "test_vlm_client_assess_round_trips_the_generated_verdict",
}


def test_every_registry_declared_client_method_is_driven() -> None:
    """MEASURE hook (plan :1024): ``client_methods`` is a registry CLAIM that
    the client speaks the op; every claim must be covered here, and this
    module may not claim methods the registry retired. 16 declared methods
    map above (the 29-row pre-R8-S2 set lost its 13 EnrichmentClient entries
    when operations.py emptied every client_methods list that named the
    deleted client — the ops stay contracted gateway-side, see
    test_conformance_ops.py's NOT-WIRED census)."""
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
# * (R8 S2) The EnrichmentPipeline / NemotronAnalyzer full ``analyze()``
#   scope-note retired with its subjects — both modules were deleted with the
#   legacy tier, so there is no analyze()-with-DB+Redis leg left to defer.
# * /v1/chat/completions (llm_chat_completion) and /slots (llm_slots): no
#   backend client method declares them (registry client_methods is empty for
#   those ops) — nothing in this tier to drive; the coverage guard above
#   reddens if a client ever claims them without a test here.
# * GET /models/status against ai/enrichment/model.py directly (the real
#   server) needs the native enrichment service; the fake + registry cites
#   carry that leg at unit-ASGI level.

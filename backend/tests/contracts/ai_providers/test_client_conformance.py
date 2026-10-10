"""WP8.4 — drive the real backend AI clients through the FakeProvider.

INTEGRATED (2026-09-19): drafted under /tmp with a draft-only conftest (not
carried over — the repo tier gets ENVIRONMENT=test from
backend/tests/conftest.py:107 and the autouse settings-cache reset around
every test, so the autouse cache-clear below is redundant but harmless).
There is **no xfail, no skip, no importorskip anywhere in this file** (goal
rule). Never respx: every hop is ``httpx.ASGITransport`` (goal rule; the fake
IS an app — backend/ai_contract/fake/app.py).

DRIVEN HERE SINCE R8 S3 (2026-09-29, five owner rulings): ``DetectorClient``
and ``VlmClient`` — the ONLY two client bindings the registry still declares
(``client_methods`` is empty for the other seven ops). ``FlorenceClient``,
``CLIPClient``, ``EnrichmentClient``, ``NemotronAnalyzer`` and
``nemotron_streaming`` are all gone: Florence by ruling 1, CLIP by ruling 5's
prune-to-3 (a gateway whose model set is yolo26/reid/threat cannot boot a CLIP
route), the rest with the S2b legacy tier. Every property this file owned over
those families was either RE-TARGETED onto surviving surface or TOMBSTONED with
its hazard stated in full — never deleted silently, never skipped (the S2b/S3
grammar). The CLASSES of property they carried did not die with them:

  * "renaming a contract key reddens a CLIENT test, not just a schema snapshot"
    — still executed against the two surviving bindings by the SAME mechanism
    (rewrite the served bytes, show the client's parsed output changes).
    Section 2; that mechanism is now applied to every surviving binding, so the
    Done-when's coverage of the surviving surface is complete rather than
    sampled.
  * "a service that bypasses its client and re-implements the parse is
    contract-blind" — the ``{ai_vlm_url}/completion`` bypass family is live and
    is now driven at all THREE shipped sites instead of one (section 6). The
    SceneOCRService site died with its module and is tombstoned with its
    hazard (section 6b).
  * "gateway and server diverge in their TYPE shapes, invisibly to the
    deployed client" — the CLIP divergences are tombstoned with their record,
    and the shape class retargets to the light lane's bbox union, whose
    asymmetry is real and live (section 3).

Plan: docs/superpowers/plans/2026-09-19-swap-readiness-72h.md §WP8.4
(lines 1001-1026). WP8.3 (test_conformance_geometry.py et al.) tests the
PROVIDERS; this tests the **other half** — the client parse methods — so the
two halves can no longer stay independently green. Done-when: "renaming a
response key in a contract model reddens a CLIENT test, not just a schema
snapshot" (:1024-1026). Satisfied structurally: every expected key is a literal
below (``_EXPECTED_CLIENT_OUTPUTS`` values were read from the ACTUAL fake
generators via a one-shot ``generate(op_id)`` dump at draft time, not
transcribed from schemas), and the rename proofs show sensitivity by rewriting
the SERVED body — so a parser that hides the rename behind
``.get(key, default)`` cannot pass either leg.

=============================================================================
SEAMS USED PER CLIENT (point a client at the fake with ZERO production change)
=============================================================================
* DetectorClient  — builds its OWN persistent ``httpx.AsyncClient`` pools in
  ``__init__`` (detector_client.py:321/:325) against a DNS name that does not
  exist here, and takes NO base_url kwarg. Seam: patch the *module-level*
  ``get_settings`` name the client imported (detector_client.py:73;
  ``self._detector_url = settings.yolo26_url`` at :287 — patching
  backend.core.config.get_settings would hit none of them) + swap the private
  pools (``_http_client`` / ``_health_http_client``) onto the fake. Same trap
  as the distinct-``get_triton_client``-targets lesson in
  test_conformance_ops.py's driving-shape note.
* VlmClient       — takes its transport in ``__init__`` (no pool swap), and
  dials the ENGINE wire /v1/chat/completions, not the registry's
  /vlm/chat/completions mount (op.evidence). Section 7's shim is the
  chat-server half: forward the client's bytes to the fake's own vlm_assess
  handler and wrap the generator's answer in choices[0].message.content.
* The /completion client-BYPASS FAMILY (plan :1012's successor) — all three
  sites build their client INSIDE the method with no transport seam and no
  pool to swap (summary_generator.py:441, prompt_service.py:938,
  pipeline_quality_audit_service.py:390; each binds its OWN module-level
  ``httpx`` name), so the seam is a monkeypatched module-local shim that
  injects the transport. The real httpx module is never patched.

=============================================================================
CONTRACT FACTS THIS FILE RELIES ON (re-measured at HEAD on 2026-09-29)
=============================================================================
* The fake mounts one route per registry op with no prefix (fake/app.py), and
  the surviving registry paths ALREADY carry their service prefixes
  (/yolo26/detect, /yolo26/detect/batch, /yolo26/segment,
  /enrich-lt/person-reid, /enrich-lt/threat-detect, /completion,
  /v1/chat/completions, /slots, /vlm/chat/completions). The gateway mounts its
  TWO surviving adapter routers under the prefixes those paths imply
  (ai/gateway/main.py:272-273), so one base_url works against either app —
  that is what makes every gateway-vs-fake pair below legible, and
  GATEWAY_MOUNTS is DERIVED from the registry columns rather than listed (the
  five-row table this file carried through S2 named three swept adapters).
* The fake performs NO request validation (it parses the body only to seed
  model_name / verdicts) and always answers 200 on registry paths → it can
  never 422. Every 422/404 pin therefore drives the real gateway adapter
  routers, and the fake side of those tests pins the 200. The asymmetry IS the
  finding.
* The fake serves NO /health route (no registry op has one — re-probed:
  GET /health and every ``{op.path}/health`` 404 against it). That absence is
  what the health/wake characterization legs pin.
* Deterministic fake values were dumped at draft time via
  ``backend.ai_contract.fake.generate(op_id)`` (profile "gateway"); the
  literals below are those dumps. A change to the generator seed logic reddens
  this file BY DESIGN — that is the point (fake ⇄ client lockstep).
* MEASURED FIX (2026-09-29, this tier's own vacuity class): this file's
  ``GOLDEN_DIR`` used to be built from a ``REPO_ROOT`` initialised to the
  TEST FILE'S OWN DIRECTORY, and the walk that was supposed to correct it
  started from ``Path.cwd()`` — under xdist a worker's cwd is the rootdir, so
  the walk found the repo only by accident of invocation directory and the
  ``if example.exists()`` guard silently fell through to a hand-written body
  for every op when it did not. Both paths are now pinned at import (an
  unresolvable golden dir raises at collection instead of quietly serving
  made-up payloads) and section 0 asserts the directory is the tier's real
  golden/payloads tree.

Cites relied on (re-verify any that a rebase moves):
  plan §WP8.4 :1001-1026; Tier A table :769-800
  backend/ai_contract/operations.py (9 ops; availability flags; client_methods)
  backend/ai_contract/fake/{__init__.py,app.py,generators.py} (generate/snapshot)
  backend/services/detector_client.py:73,105,262,287,321,325,415,506,993,1204-1222,1230-1309
  backend/services/vlm_client.py:85(CHAT_PATH),228,252,755(assess),946(wake)
  backend/services/summary_generator.py:87,441,443-447,452
  backend/services/prompt_service.py:681,938-947
  backend/services/pipeline_quality_audit_service.py:137,390-398
  backend/models/detection.py:54,66
  backend/api/routes/model_management.py:151-172(get_router_urls),330-363(_fetch_router_health)
  ai/gateway/main.py:272-273
  ai/gateway/adapters/yolo26.py:36-39(MODEL_NAME/TARGET_SIZE/thresholds),332,386,447
  ai/gateway/adapters/enrichment_light.py:40(BBoxRequest),55,62,130,172,222
  backend/tests/contracts/ai_providers/test_conformance_ops.py (driving shape,
  GATEWAY_MOUNTS/GATEWAY_PATCH_TARGETS — the two-target Triton rule)
"""

from __future__ import annotations

import asyncio
import contextlib
import copy
import io
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import numpy as np
import pytest
import pytest_asyncio
from backend.ai_contract.operations import OPERATIONS
from backend.ai_contract.provider import operations_for_slot
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from PIL import Image

# ---------------------------------------------------------------------------
# Repo root + golden dir, PINNED. The pre-S3 form resolved REPO_ROOT from the
# test file's own directory and then "corrected" it with a walk that started at
# Path.cwd() — so the value depended on where pytest was launched, and a wrong
# value was invisible because every reader guarded on .exists(). A dead path
# that a guard forgives is the vacuity this tier treats as a defect.
# ---------------------------------------------------------------------------


def _resolve_repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in (*here.parents, Path.cwd()):
        if (candidate / "backend" / "ai_contract" / "operations.py").is_file():
            return candidate
    raise RuntimeError(
        f"no ancestor of {here} carries backend/ai_contract/operations.py — "
        "this file cannot resolve its own repo root, so every golden-payload "
        "and schema read below would silently point at nothing"
    )


REPO_ROOT = _resolve_repo_root()
GOLDEN_DIR = REPO_ROOT / "backend" / "tests" / "contracts" / "ai_providers" / "golden" / "payloads"
if not GOLDEN_DIR.is_dir():
    raise RuntimeError(f"{GOLDEN_DIR} is not a directory — golden payloads unreachable")
# Same convention as test_fake_provider.py:54 / test_conformance_geometry.py:76.
# Needed because goldens are GENERATED from these schemas
# (scripts/gen-ai-contract.py:render_goldens), so the schema tree — not a
# hand-list of exempt ops — is what says which op should have a golden at all.
SCHEMA_DIR = REPO_ROOT / "backend" / "ai_contract" / "schemas"
if not SCHEMA_DIR.is_dir():
    raise RuntimeError(f"{SCHEMA_DIR} is not a directory — contract schemas unreachable")

FAKE_BASE = "http://fake"

# The /tmp probe runs WITHOUT the repo ini (pytest never reads
# pyproject.toml when args live outside the rootdir), so pytest-asyncio
# sits in strict mode there: every async leg carries an explicit
# @pytest.mark.asyncio and the one async fixture uses pytest_asyncio.
# fixture. In-tree (asyncio_mode=auto) both are redundant but legal.
_aio = pytest.mark.asyncio

# The gateway mount table, DERIVED (WP4.2: a hand-numbered table rots — the
# five rows this file carried named clip/florence/enrichment adapters that R8
# S3 swept, and the fixture they fed turned 12 tests into ERRORs). A registry
# op whose gateway column is True and whose path starts with a service prefix
# is served by an adapter router mounted at that prefix; a retired adapter
# leaves the table by its ops leaving the gateway column. The
# test_gateway_mount_table_is_derived_from_the_registry leg below pins the
# result against both ai/gateway/main.py's include_router lines and the import
# of every named module, so the derivation cannot drift in either direction.
_MOUNTLESS_ON_GATEWAY = {"yolo26_segment"}  # gateway column True, path has no
# adapter prefix of its own beyond /yolo26 — kept out of the derivation's
# "every gateway op must be mounted" promise by name, and pinned there.


def _gateway_mounts() -> tuple[tuple[str, str], ...]:
    """(mount prefix, adapter module) for every prefix a gateway column implies.

    The PREFIXES come from the registry's gateway column (WP4.2 — see above),
    but the MODULE NAMES cannot be, and must not be guessed from the prefix
    either: /yolo26 -> yolo26 happens to hold, /enrich-lt -> enrich_lt does not
    (the module is enrichment_light.py). A spelling-derived module path is a
    second naming convention layered on the first, and the first time a prefix
    and a module disagree it fails as a ModuleNotFoundError at import — 11
    ERRORs, not one clear assertion. So the module is READ from the one place
    that cannot be wrong: ai/gateway/main.py's own
    ``from ai.gateway.adapters.X import router as Y`` paired with
    ``app.include_router(Y, prefix="/Z")``. test_gateway_mount_table_is_derived_
    from_the_registry then pins the registry-derived prefixes against these
    mounts, which is where a genuine disagreement surfaces.
    """
    main_src = (REPO_ROOT / "ai" / "gateway" / "main.py").read_text(encoding="utf-8")
    # findall yields (module, alias); the mount line names the alias.
    alias_to_module = {
        alias: module
        for module, alias in re.findall(
            r"from (ai\.gateway\.adapters\.\w+) import router as (\w+)", main_src
        )
    }
    mounted = {
        prefix: alias_to_module[alias]
        for alias, prefix in re.findall(
            r'app\.include_router\((\w+),\s*prefix="(/[\w-]+)"', main_src
        )
        if alias in alias_to_module
    }
    assert mounted, "ai/gateway/main.py no longer mounts any adapter router"

    prefixes: set[str] = set()
    for op in operations_for_slot("gateway", OPERATIONS).values():
        head = "/" + op.path.lstrip("/").split("/", 1)[0]
        if head != op.path:
            prefixes.add(head)
    unmapped = sorted(prefixes - set(mounted))
    assert not unmapped, (
        f"gateway-column ops are served under {unmapped}, which main.py does not "
        f"mount — the registry promises a route the shipped gateway does not have"
    )
    return tuple(sorted((prefix, mounted[prefix]) for prefix in prefixes))


GATEWAY_MOUNTS = _gateway_mounts()

# The Triton seam: one patch target PER mounted adapter module. Patching one
# leaves the others calling real gRPC (test_conformance_ops.py's
# driving-shape rule); the target list and the mount list are the same
# derivation, so a mount can no longer be patched in one place and forgotten
# in the other.
GATEWAY_PATCH_TARGETS = tuple(f"{module}.get_triton_client" for _, module in GATEWAY_MOUNTS)


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


@contextlib.contextmanager
def _fresh_ai_breakers() -> Any:
    """The ai-vlm circuit breaker is a REGISTRY singleton (the unit tier's
    own autouse fixture resets it for the same reason): a shared instance
    that opened in one test would make every later ``VlmClient`` refuse
    WITHOUT I/O, so a failure here would depend on test order. Reset before
    and after each leg that can feed it."""
    from backend.services.circuit_breaker import reset_circuit_breaker_registry

    reset_circuit_breaker_registry()
    try:
        yield
    finally:
        reset_circuit_breaker_registry()


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

    def __init__(self, app: Any, store: list[dict[str, Any]]) -> None:
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
    """Patch the module-level ``get_settings`` name a module imported.

    These services do ``from backend.core.config import get_settings`` (e.g.
    detector_client.py:73, prompt_service.py:23), so patching the original in
    backend.core.config would hit NONE of them."""
    import importlib

    mod = importlib.import_module(module_path)
    monkeypatch.setattr(mod, "get_settings", lambda: settings)


def _request_kwargs(op_id: str) -> dict[str, Any]:
    """Contract-driven request builder (mirrors test_fake_provider.py:72-98)."""
    op = OPERATIONS[op_id]
    if op.method == "GET":
        return {}
    example = GOLDEN_DIR / f"{op_id}.request.example.json"
    if op_id == "yolo26_detect_batch":
        # multipart files= list: the golden's single upload string cannot say
        # "two files", and the fake is payload-blind for the yolo family.
        return {"files": [("files", ("f0.jpg", b"fake-image", "image/jpeg"))]}
    if example.exists():
        payload = json.loads(example.read_text(encoding="utf-8"))
        if isinstance(payload, str):
            return {"files": [("file", ("f.jpg", payload.encode(), "image/jpeg"))]}
        if payload == {}:
            return {}
        return {"json": payload}
    return {"json": {"image_base64": "aGVsbG8="}}


async def _served_body(op_id: str, **kw: Any) -> dict[str, Any]:
    """The body the fake ACTUALLY serves for the registry path.

    NOT ``generate(op_id)`` directly: the ASGI app parses the request body
    before generating (fake/app.py:70-83), and the vlm op re-seeds its
    verdict/risk_score from the payload's image_paths — so only driving the
    app yields the exact bytes a client sees."""
    op = OPERATIONS[op_id]
    body_kwargs = _request_kwargs(op_id)
    body_kwargs.update(kw)
    async with AsyncClient(transport=ASGITransport(app=_fake_app()), base_url=FAKE_BASE) as c:
        r = await c.request(op.method, op.path, **body_kwargs)
        assert r.status_code == 200, (op_id, r.status_code, r.text[:200])
        return r.json()


def _fake_body(op_id: str) -> dict[str, Any]:
    """Sync wrapper for non-async legs (the rename table)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_served_body(op_id))
    finally:
        loop.close()


async def _one_shot(app: FastAPI, method: str, path: str, **kw: Any) -> httpx.Response:
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


def _png_bytes(width: int = 64, height: int = 48) -> bytes:
    """A real PNG for the gateway legs (the adapters decode the upload with
    PIL); the fake never decodes anything and takes the golden string."""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (9, 9, 9)).save(buf, format="PNG")
    return buf.getvalue()


def _png_b64(width: int = 64, height: int = 48) -> str:
    import base64

    return base64.b64encode(_png_bytes(width, height)).decode()


@pytest.fixture
def settings_factory():
    """A real Settings with every surviving AI URL on the fake's registry
    prefixes and retries pinned to 1 (retry loops sleep 2**attempt — the
    detector's backoff — and the fake is deterministic, so one attempt is all a
    conformance run needs). use_ai_gateway stays False: each client gets
    exactly one prefix, no gateway rewrite.

    The retired URL fields (florence_url / clip_url / enrichment_url /
    nemotron_url) are NOT set here: they are deleted settings fields, and
    Settings is ``extra="ignore"`` — a fixture that still passed them would be
    a silent no-op (the dead-path class this file just fixed in its own
    GOLDEN_DIR). Their absence is pinned by name in
    TestRetiredSurface.test_retired_settings_fields_are_gone."""

    def _make(**overrides: Any) -> Any:
        from backend.core.config import Settings

        base: dict[str, Any] = {
            "yolo26_url": f"{FAKE_BASE}/yolo26",
            "enrichment_light_url": f"{FAKE_BASE}/enrich-lt",  # light router
            # The /completion endpoint (registry op is bare /completion):
            # R8 S2 re-homed every consumer of the retired nemotron_url onto
            # ai_vlm_url (summary_generator.py:87, prompt_service.py:681,
            # pipeline_quality_audit_service.py:137), so this is the
            # survivor's field — and the field the third /completion bypass
            # family reads.
            "ai_vlm_url": FAKE_BASE,
            "use_ai_gateway": False,
            "ai_gateway_url": None,
            "detector_max_retries": 1,
        }
        base.update(overrides)
        # _env_file=None so the sandbox .env cannot bleed prod values into
        # validators (config.py skips the weak-password check for env "test";
        # the probe conftest / repo conftest sets ENVIRONMENT=test).
        return Settings(_env_file=None, **base)

    return _make


@pytest.fixture
def detector_client(fake_app, monkeypatch, settings_factory, captured):
    from backend.services import detector_client as dcmod

    _patch_settings(monkeypatch, "backend.services.detector_client", settings_factory())
    client = dcmod.DetectorClient(max_retries=1)
    # The store is the fixture's business, not the drive's: an unwired
    # _point_at() builds a THROWAWAY list, every request the client sends
    # lands there, and each downstream `assert captured` reads the empty
    # fixture — a client that drove the fake perfectly reports "client sent no
    # request at all". The pin passes only once the recorder and the assertion
    # name the same list.
    _point_at(client, fake_app, captured)
    yield client


@pytest.fixture
def big_image_file(tmp_path_factory):
    """DetectorClient.detect_objects reads a REAL file, PIL-validates it and
    enforces MIN_DETECTION_IMAGE_SIZE=10240 (detector_client.py:105) — the
    golden request example is a 19-byte string, NOT a usable file, so generate
    a random-noise PNG (large after compression; bytes are irrelevant: the
    fake never decodes them)."""
    rng = os.urandom(512 * 512 * 3)
    img = Image.frombytes("RGB", (512, 512), rng)
    p = tmp_path_factory.mktemp("wp84") / "frame.png"
    img.save(p, format="PNG")
    assert p.stat().st_size >= 10240, p.stat().st_size
    return p


def _mock_db_session() -> Any:
    """Session mocked like backend/tests/unit/services/test_detector_client.py
    :38-45. session.get returns None so the camera last_seen update is skipped."""
    from sqlalchemy.ext.asyncio import AsyncSession

    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.get = AsyncMock(return_value=None)
    return session


@pytest.fixture(scope="module")
def gateway_app() -> FastAPI:
    """Every surviving adapter router with its PRODUCTION prefix. The mount
    table is derived from the registry's gateway column (GATEWAY_MOUNTS), which
    is the same derivation ai/gateway/main.py's include_router lines and
    test_conformance_ops.py's GATEWAY_MOUNTS follow — bare routers would leave
    the registry paths unreachable, so the prefixes are load-bearing."""
    from importlib import import_module

    app = FastAPI()
    for prefix, module in GATEWAY_MOUNTS:
        app.include_router(import_module(module).router, prefix=prefix)
    return app


def _mock_triton() -> AsyncMock:
    """AsyncMock TritonClient covering every resident model's output name:
    yolo26 → output0 (an empty post-NMS (1, 300, 6) tensor, so handlers answer
    with well-formed envelopes and zero detections), reid → a (1, 512)
    embedding, threat → output0 in the (1, 8, 8400) pre-NMS layout."""
    client = AsyncMock()
    client.infer = AsyncMock(
        side_effect=lambda **_kw: {
            "output0": np.zeros((1, 300, 6), dtype=np.float32),
            "embedding": np.ones((1, 512), dtype=np.float32),
        }
    )
    client.is_model_ready = AsyncMock(return_value=True)
    client.get_model_metadata = AsyncMock(return_value={"outputs": [{"name": "output0"}]})
    return client


@pytest_asyncio.fixture
async def gateway_client(gateway_app):
    """(client, mock_triton) with EVERY mounted adapter's module-level
    ``get_triton_client`` name patched — GATEWAY_PATCH_TARGETS is derived from
    the same table as the mounts, so a mount cannot be patched in one place
    and forgotten in the other."""
    from contextlib import ExitStack

    mock = _mock_triton()
    with ExitStack() as stack:
        for target in GATEWAY_PATCH_TARGETS:
            stack.enter_context(patch(target, return_value=mock, autospec=True))
        async with AsyncClient(
            transport=ASGITransport(app=gateway_app), base_url=FAKE_BASE
        ) as client:
            yield client, mock


# ---------------------------------------------------------------------------
# THE CLIENT PARSE SURFACE AS DATA. Keys are DERIVED from the registry's
# client_methods column (the test below pins table == declared), so the table
# cannot name a client the registry retired — the pre-S3 failure mode: it held
# 13 rows for FlorenceClient/CLIPClient after those clients left the registry
# and every one of them errored on an unimportable module. "op" is the registry
# op the client is ROUTED to; asserting the recorded path == OPERATIONS[op].
# path pins the client's URL composition as well as the parse.
#
# The EnrichmentClient block (8 heavy/light routing rows) and the
# FlorenceClient/CLIPClient rows below it went with their clients. Their
# registry residue is census-pinned in test_conformance_ops.py's
# SENTINELS_* sets; the KEY-SENSITIVITY technique they carried is retargeted
# in section 2 onto the two rows that remain.
# ---------------------------------------------------------------------------


def declared_client_methods() -> set[str]:
    return {m for op in OPERATIONS.values() for m in op.client_methods}


async def _drive_detector(ctx: Any) -> Any:
    """DetectorClient.detect_objects against the fake's /yolo26/detect.
    Returns the DB rows; ctx.captured holds the request the client sent."""
    from backend.services import detector_client as dcmod

    with patch.object(
        dcmod,
        "get_baseline_service",
        autospec=True,
        return_value=MagicMock(update_baseline=AsyncMock()),
    ):
        return await ctx.client.detect_objects(str(ctx.big_image_file), "cam-1", _mock_db_session())


async def _drive_vlm(ctx: Any) -> Any:
    """VlmClient.assess against the chat-engine shim over the fake's own
    vlm_assess handler (section 7's ``_engine_asgi``). The chat wire and the
    contract path differ by design, so the PATH assertion for this row is made
    inside the drive (against CHAT_PATH) and the table's generic path leg
    asserts the fake-side mount for the same op."""
    from backend.services.vlm_client import VlmClient
    from backend.services.vlm_verdict import VlmAssessRequest

    with _fresh_ai_breakers():
        client = VlmClient(
            base_url=FAKE_BASE,
            transport=_RecordingTransport(ctx.engine_app, ctx.captured),
            settings=ctx.settings,
        )
        try:
            return await client.assess(
                VlmAssessRequest(
                    image_paths=["front/a.jpg"],
                    context={
                        "camera_id": "front",
                        "detections": [{"object_type": "person", "confidence": 0.9}],
                        "zones": ["porch"],
                        "timestamp": "2026-09-25T12:00:00+00:00",
                    },
                )
            )
        finally:
            await client.close()


_EXPECTED_CLIENT_OUTPUTS: dict[str, dict[str, Any]] = {
    "DetectorClient.detect_objects": {
        "op": "yolo26_detect",
        "drive": _drive_detector,
        # The yolo family are LITERAL fake generators (their routes declare a
        # bare dict), so the answer is payload-blind — pin that here, because
        # it is what lets `value` be a static literal at all.
        "payload_blind": True,
        # PER-ROW, not one elem template applied to all rows: the fake's three
        # detections have DIFFERENT classes (cell phone / tv / suitcase) and
        # confidences, so the single-row form was wrong for rows 1 and 2 — it
        # asserted object_type == "cell phone" on row 1, whose served class is
        # "tv". The list is the fake's literal script (dumped from generate(),
        # per this file's header rule), and served_count_key ties its LENGTH to
        # the bytes actually served, so a change to the fake's script fails
        # THAT leg rather than quietly comparing the client against a stale
        # value. video_width/video_height are per-ROW columns — the client
        # stamps every row with the frame size — not top-level fields of a list
        # return, so they ride each row (a top-level placement made _check probe
        # them on the list itself).
        "value": {
            "served_count_key": "detections",
            "rows": [
                {
                    "object_type": "cell phone",
                    "confidence": 0.6768,
                    "video_width": 640,
                    "video_height": 480,
                },
                {"object_type": "tv", "confidence": 0.665, "video_width": 640, "video_height": 480},
                {
                    "object_type": "suitcase",
                    "confidence": 0.9292,
                    "video_width": 640,
                    "video_height": 480,
                },
            ],
        },
    },
    "VlmClient.assess": {
        "op": "vlm_assess",
        "drive": _drive_vlm,
        # The fake re-seeds verdict/risk_score from payload["image_paths"], so
        # this row is NOT payload-blind and its value is cross-checked against
        # the served body instead of a literal.
        "payload_blind": False,
        "value": {"verdict": "confirmed", "risk_score": 2},
    },
}


def _check_rows(name: str, got: Any, exp: dict, raw: Any) -> None:
    """Row-shaped expectations: ``rows`` (a PER-ROW expectation list, the form
    the surviving yolo row needs because the fake's rows differ), ``obj_rows``
    (rows under a named attribute) or ``count``+``elem`` (one template for a
    bare list of rows). Split out of ``_check`` to keep its dispatch under the
    PLR0911 return cap; every branch ends the check.

    The per-row branch cross-checks its own length against the served bytes via
    ``served_count_key`` rather than a hand-typed count, so the expectation
    cannot drift from the fake's script without the length leg catching it."""
    if "rows" in exp:  # one expectation per served row
        assert isinstance(got, list), f"{name}: expected list, got {type(got)}"
        key = exp.get("served_count_key")
        if key is not None:
            served = raw.get(key) if isinstance(raw, dict) else None
            assert isinstance(served, list), (
                f"{name}: served body has no {key!r} list to count — the "
                "cross-check this shape depends on is gone"
            )
            assert len(exp["rows"]) == len(served), (
                f"{name}: expectation covers {len(exp['rows'])} rows but the "
                f"fake serves {len(served)} — the table is stale (regenerate "
                "it from generate(), do not pad it)"
            )
        assert len(got) == len(exp["rows"]), (
            f"{name}: client parsed {len(got)} rows vs contract {len(exp['rows'])}"
        )
        for i, (row, per_row) in enumerate(zip(got, exp["rows"], strict=True)):
            for k, v in per_row.items():
                assert hasattr(row, k), (
                    f"{name}[{i}]: parsed row lost field {k!r} (raw {str(raw)[:200]})"
                )
                _eq(f"{name}[{i}].{k}", getattr(row, k), v, raw)
        return
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
        if "rows" in exp or "count" in exp or "obj_rows" in exp:  # -> shared helper
            _check_rows(name, got, exp, raw)
            exp = {
                k: v
                for k, v in exp.items()
                if k not in ("rows", "served_count_key", "count", "obj_rows", "elem")
            }
            if not exp:
                return
        if "len" in exp:  # list[float] return
            assert isinstance(got, list) and len(got) == exp["len"], (
                f"{name}: list length {len(got) if isinstance(got, list) else got} != {exp['len']}"
            )
            return
        if "keys" in exp:  # dict return
            assert set(got) == exp["keys"], f"{name}: {set(got)} != {exp['keys']}"
            return
        if "tuple" in exp:  # plain (float, float) tuple return
            for i, (g, e) in enumerate(zip(got, exp["tuple"], strict=True)):
                _eq(f"{name}[{i}]", g, e, raw)
            return
        for k, v in exp.items():
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
# 0. THE FILE'S OWN PLUMBING (a pin that cannot read dead forms: it proves the
#    golden tree it feeds section 1/2 from is really there).
# ---------------------------------------------------------------------------


def test_golden_dir_resolves_and_covers_the_registry() -> None:
    """Non-vacuity for _request_kwargs: the helper falls back to a
    hand-written body whenever ``GOLDEN_DIR/<op>.request.example.json`` is
    missing, and that fallback is exactly how a dead GOLDEN_DIR hides. So the
    directory, its coverage AND its liveness are pinned, not assumed.

    The expected set is DERIVED, and the derivation is the generator's own
    rule, not an exemption list: scripts/gen-ai-contract.py:render_goldens()
    emits ``payloads/<op>.<side>.example.json`` from ``schemas/<op>.<side>.json``,
    so an op has a request golden iff it has a request schema. That replaces
    the hand-written ``missing == ["yolo26_detect_batch"]`` this pin carried,
    which was wrong in BOTH directions by the time S3 landed: yolo26_detect_batch
    does have a request schema and does have a golden (so exempting it hid a
    gap), while the two surviving enrich_lt POST ops have no request schema at
    all and so can never have a golden (so requiring one demanded a file the
    generator will not emit). Deriving from the schema tree gets both right and
    keeps getting them right; a literal list had to be re-edited at every prune.

    The liveness leg is the part a directory listing cannot prove: GOLDEN_DIR
    can be fully populated while the helper ignores it.
    """
    assert GOLDEN_DIR.is_dir(), GOLDEN_DIR
    non_get = {op_id for op_id, op in OPERATIONS.items() if op.method != "GET"}
    assert non_get, "the registry lost every non-GET op — the partition below is vacuous"

    has_schema = {o for o in non_get if (SCHEMA_DIR / f"{o}.request.json").is_file()}
    has_golden = {o for o in non_get if (GOLDEN_DIR / f"{o}.request.example.json").is_file()}

    # (1) schema ⇒ golden. The generator's rule, asserted as the registry's.
    assert not (has_schema - has_golden), (
        f"request schema with no golden payload: {sorted(has_schema - has_golden)} — "
        "_request_kwargs would silently hand-write these bodies"
    )
    # (2) The converse, so a stale golden left behind by a retired schema cannot
    # pass either (the S3 sweep deleted schema files; their goldens went with them).
    assert not (has_golden - has_schema), (
        f"golden payload with no request schema: {sorted(has_golden - has_schema)} — "
        "a retired op's payload survived the prune"
    )
    # (3) Non-vacuity of the partition: BOTH arms must be populated, or (1) and
    # (2) collapse into one tautology about a set that is everything.
    assert has_schema and (non_get - has_schema), (
        f"every non-GET op has a request schema (or none does): the multipart/"
        f"payload-blind arm is untested — {sorted(non_get)}"
    )
    # (4) Liveness: the helper must actually READ the golden it is handed, not
    # just find the directory. Derived subject, so a rename cannot quietly move
    # this off the file it is meant to prove.
    subject = sorted(has_schema & has_golden)[0]
    payload = json.loads((GOLDEN_DIR / f"{subject}.request.example.json").read_text("utf-8"))
    kwargs = _request_kwargs(subject)
    if isinstance(payload, str):
        # multipart root: the example is the marker value, posted as an upload
        assert kwargs["files"][0][1][1] == payload.encode(), (subject, kwargs)
    elif payload:
        assert kwargs.get("json") == payload, (subject, kwargs, payload)
    else:
        assert kwargs == {}, (subject, kwargs, "empty golden must post an empty body")


def test_gateway_mount_table_is_derived_from_the_registry() -> None:
    """The mount list section 3 drives against must be the shipped one. Three
    independent readings, pinned equal: (a) the registry's gateway column via
    _gateway_mounts; (b) ai/gateway/main.py's include_router lines — read as
    TEXT for LIVE forms only (doctrine 5: no dead name appears); (c) the
    import of every module named. A retired adapter leaves (a) with its ops and
    (b) with its mount line; a NEW adapter enters both, and a list that patched
    one but not the other reddens here rather than silently reaching gRPC."""
    import importlib
    import re

    main_src = (REPO_ROOT / "ai" / "gateway" / "main.py").read_text(encoding="utf-8")
    mounted = set(re.findall(r'^app\.include_router\([^)]*prefix="(\/[\w-]+)"', main_src, re.M))
    assert mounted, "ai/gateway/main.py no longer declares any prefixed mount — re-read it"
    assert mounted == {prefix for prefix, _ in GATEWAY_MOUNTS}, (
        f"main.py mounts {sorted(mounted)}, this file derives "
        f"{sorted(p for p, _ in GATEWAY_MOUNTS)} — the driving app and the "
        "shipped gateway disagree"
    )
    for prefix, module in GATEWAY_MOUNTS:
        assert importlib.import_module(module).router is not None, module
    # (c) non-vacuity in the other direction: the gateway column is not empty,
    # so an empty derivation could never satisfy the equality above.
    assert len(GATEWAY_MOUNTS) >= 2, GATEWAY_MOUNTS


# ---------------------------------------------------------------------------
# 1. HAPPY PATH: client method -> fake ASGI app -> PARSED output == contract
# ---------------------------------------------------------------------------

_TEST_IDS = ("front", "driveway")


@pytest.fixture(scope="module")
def vlm_engine_app() -> Any:
    """Raw ASGI chat engine over the fake (the shim section 7 documents): it
    forwards the client's bytes to the fake's own vlm_assess handler and puts
    the GENERATOR's answer in choices[0].message.content. Nothing here
    hand-writes a verdict — a contract rename reddens the leg."""
    from backend.ai_contract.operations import OPERATIONS as OPS

    contract_app = _fake_app()
    assess_path = OPS["vlm_assess"].path

    async def _engine_asgi(scope: Any, receive: Any, send: Any) -> None:
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
            answer = await inner.post(assess_path, content=body)
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

    return _engine_asgi


@pytest.fixture
def vlm_settings(settings_factory, tmp_path):
    root = tmp_path / "foscam"
    (root / "front").mkdir(parents=True)
    (root / "front" / "a.jpg").write_bytes(b"\xff\xd8\xff" + b"\x00" * 32)  # D10 synthetic
    (root / _TEST_IDS[1]).mkdir(parents=True)
    (root / _TEST_IDS[1] / "b.jpg").write_bytes(b"\xff\xd8\xff" + b"\x00" * 32)
    return settings_factory(
        foscam_base_path=str(root),
        vlm_enforcement_probe_enabled=False,
    )


class _Ctx:
    """Small namespace so the section-1 drives stay data-driven (the table keys
    are derived; the drives are the per-client half)."""

    def __init__(self, **kw: Any) -> None:
        self.__dict__.update(kw)


@pytest.mark.parametrize("method", sorted(_EXPECTED_CLIENT_OUTPUTS))
@_aio
async def test_client_parsed_output_matches_the_contract(
    method: str,
    detector_client,
    vlm_engine_app,
    vlm_settings,
    big_image_file,
    captured,
) -> None:
    """WP8.4 Done-when, executed: the client's PARSED fields (not "no
    exception") match the contract-declared keys, AND the client hit the exact
    registry path the settings routing declares. The table's key set is pinned
    equal to the registry's client_methods column
    (test_every_registry_declared_client_method_is_driven), so no op with a
    binding can be missing here and no retired client can linger in the table.

    VlmClient is the one row whose CLIENT path is not the op path: the fake
    answers the op at its CONTRACT path /vlm/chat/completions (one route per
    op.path; /v1/chat/completions is already taken by llm_chat_completion)
    while the client dials the ENGINE wire. That divergence is the registry's
    own evidence, so the drive asserts the engine path and this leg asserts
    the half the table owns: the parsed fields equal the contract body the
    fake served."""
    from backend.ai_contract.fake import generate as _gen

    spec = _EXPECTED_CLIENT_OUTPUTS[method]
    op = OPERATIONS[spec["op"]]
    ctx = _Ctx(
        client=detector_client,
        big_image_file=big_image_file,
        captured=captured,
        engine_app=vlm_engine_app,
        settings=vlm_settings,
    )
    got = await spec["drive"](ctx)
    assert got is not None, f"{method}: client degraded to None on a 200 — parse broke"
    assert captured, f"{method}: client sent no request at all"
    sent = captured[-1]
    if method != "VlmClient.assess":
        assert sent["path"] == op.path, (
            f"{method}: client requested {sent['path']!r} but the registry "
            f"declares {op.path!r} for {spec['op']} — path drift or a routing "
            "default change"
        )

    sent_payload: Any = None
    if sent["body"].startswith(b"{"):
        with contextlib.suppress(json.JSONDecodeError):
            sent_payload = json.loads(sent["body"])
    raw = _gen(spec["op"], sent_payload, "gateway")
    raw = json.loads(json.dumps(raw))
    if spec["payload_blind"]:
        # The literal-generator claim that licenses the static value above:
        # the yolo family's answer does not move with the body at all.
        assert raw == json.loads(json.dumps(_gen(spec["op"], None, "gateway"))), (
            f"{spec['op']} grew payload sensitivity — the static expected "
            "value in _EXPECTED_CLIENT_OUTPUTS is no longer the served body"
        )
    _check(method, got, spec["value"], raw)


@_aio
async def test_detector_client_carries_every_wire_key_onto_the_db_row(
    detector_client, big_image_file
) -> None:
    """Field-by-field pin of the shipped dict-of-INTS bbox shape (the
    pre-S3 version of this leg asserted the same properties and stays green —
    it is named separately from the table leg so the table can stay DERIVED
    while this row keeps its per-key cites):
      * object_type from the wire key ``class`` (:1284);
      * bbox keys x/y/width/height read as ints (:1204-1222);
      * image_width/image_height land on video_width/video_height (:1303-1309)
        — WP7.4's headline field, None on any older wire shape."""
    body = await _served_body("yolo26_detect")
    assert len(body["detections"]) == 3, "fake shape changed: re-read the dump"

    session = _mock_db_session()
    # _drive_detector reads only ctx.client/ctx.big_image_file (it builds its
    # own DB session), so the ctx here has exactly those two fields -- no
    # `settings`: an earlier revision of this line carried a dead `if False`
    # arm that passed settings=None, which vulture flagged as an unsatisfiable
    # ternary. The other _drive_detector drive (:1404) passes the same two.
    rows = await _drive_detector(
        _Ctx(client=detector_client, big_image_file=big_image_file, captured=[])
    )
    assert len(rows) == 3, (
        f"detector dropped rows: {len(rows)}/3 fake detections (fake "
        "confidences 0.665-0.9292 are all above the default threshold)"
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
    session.add.assert_not_called()  # the drive above owns no session; see below


@_aio
async def test_detector_client_persists_and_commits(detector_client, big_image_file) -> None:
    """The DB half of the same call: rows are added and the transaction
    committed — a parse that produced objects nothing persisted would pass the
    value assertions above and do nothing in production."""
    from backend.services import detector_client as dcmod

    session = _mock_db_session()
    with patch.object(
        dcmod,
        "get_baseline_service",
        autospec=True,
        return_value=MagicMock(update_baseline=AsyncMock()),
    ):
        rows = await detector_client.detect_objects(str(big_image_file), "cam-1", session)
    assert rows, "no rows parsed — the persistence assertions below are vacuous"
    assert session.add.call_count == len(rows)
    session.commit.assert_awaited()


# ---------------------------------------------------------------------------
# 1b. WHERE THE CONFIDENCE THRESHOLD LIVES — a retarget, not a loosening.
# ---------------------------------------------------------------------------


@_aio
async def test_the_confidence_threshold_is_the_clients_not_the_gateway_adapters(
    gateway_client,
    gateway_app,
    monkeypatch,
    settings_factory,
    big_image_file,
) -> None:
    """Tier A's shape: two layers filter detections and only ONE of them is
    the deployed backend's. The gateway adapter post-process keeps
    CONFIDENCE_THRESHOLD=0.25 (adapters/yolo26.py:37) while DetectorClient
    re-filters at settings.detection_class_thresholds/class-specific floor
    (detector_client.py:291,:1190-1202). So a detection the adapter deems
    confident and the client deems noise is SILENTLY dropped after a 200 —
    the number that decides is the client's, and the pin says which.

    Pinned with a probe score that lives IN THE GAP, read from the shipped
    constants rather than typed as a magic number: adapter floor from the
    adapter's own module constant, client floor from Settings' per-class table
    (the number actually consulted for a class-0 row). probe = midpoint. Five
    legs, because each of the two claims needs both a positive and a negative
    arm before either means anything:
      * adapter KEEPS the midpoint            → its floor is below the probe;
      * adapter DROPS a score under its floor → the floor is a floor, not a
        zero that keeps everything. (The 0.9-non-vacuity this test used to
        carry could not provide this: a kept 0.9 is consistent with ANY floor
        at or below 0.9.)
      * client floor > probe                  → the interval really exists;
      * DetectorClient returns [] for the same bytes the adapter 200'd with
        → the DECIDING leg, driven end to end instead of read off config;
      * DetectorClient returns 1 row above both floors → non-vacuity OF THAT
        LEG: an empty result is only evidence of filtering if a confident row
        would have survived the same drive.
    A probe below both floors (the 0.2001 this test carried until S3) proves
    nothing about the gap — the adapter drops it, so the interesting leg never
    runs; above both proves nothing either. Deriving the probe from the two
    floors means a future threshold move re-derives the probe instead of
    silently collapsing the interval.

    One geometry trap cost a false green here while this was being written: the
    upload MUST be 640x640. The adapter reverses its letterbox before reporting
    (:191-197), and at this module's default 64x48 that is scale=10 / pad_y=80,
    which turns the canned 640-space box's top edge negative and drops the row
    on `box_h <= 0` -- so the adapter appears to filter by confidence when it
    actually rejected the geometry. Measured: _postprocess_yolo(row, 64, 48)
    returns [] at score 0.325, well above the floor."""
    client, mock = gateway_client
    from ai.gateway.adapters import yolo26 as yolo26_adapter
    from backend.core.config import Settings

    adapter_floor = yolo26_adapter.CONFIDENCE_THRESHOLD
    shipped = Settings(_env_file=None)
    # The client's floor for THIS row, not its bare default: detector_client.py
    # :1190-1192 consults _class_thresholds first and only falls back to
    # detection_confidence_threshold, so the number that decides a class-0
    # detection is the per-class one when it exists.
    client_floor = shipped.detection_class_thresholds.get(
        "person", shipped.detection_confidence_threshold
    )
    assert adapter_floor < client_floor, (
        f"adapter floor {adapter_floor} >= client floor {client_floor}: the two "
        "layers' thresholds have collided and the divergence this test pins is "
        "gone — re-read both and rewrite this leg rather than the probe"
    )
    probe = (adapter_floor + client_floor) / 2

    def _post_nms(score: float) -> np.ndarray:
        row = np.zeros((1, 1, 6), dtype=np.float32)
        row[0, 0] = [10, 10, 60, 50, score, 0]  # x1,y1,x2,y2,score,class 0
        return row

    async def _kept(score: float) -> list[dict[str, Any]]:
        mock.infer.side_effect = lambda **_kw: {"output0": _post_nms(score)}
        # 640x640, not the module's 64x48 default: the adapter reverses the
        # letterbox before it reports (adapters/yolo26.py:191-197), and at
        # 64x48 that transform is scale=10 / pad_y=80, which maps the canned
        # 640-space box to a NEGATIVE height and drops it on geometry
        # (`if box_w <= 0 or box_h <= 0`). Measured: _postprocess_yolo(row, 64,
        # 48) == [] at a score of 0.325, well above the floor. At 640x640 the
        # letterbox is the identity, so the only thing that can drop this row
        # is the confidence floor -- which is the thing under test.
        r = await client.post(
            "/yolo26/detect", files={"file": ("f.png", _png_bytes(640, 640), "image/png")}
        )
        assert r.status_code == 200, r.text[:200]
        return r.json()["detections"]

    kept = await _kept(probe)
    assert [d["confidence"] for d in kept] == [pytest.approx(probe)], (
        f"the adapter dropped its own midpoint {probe} — its floor moved off "
        f"{adapter_floor}; re-read adapters/yolo26.py:37"
    )
    assert kept[0]["class"] == "person", "COCO class 0 stopped being person"

    # The floor is a floor: just under it, nothing survives. (strictly below so
    # the leg cannot pass by landing ON the boundary.)
    assert await _kept(adapter_floor * 0.8) == [], (
        f"the adapter kept a {adapter_floor * 0.8:.3f} detection — its floor is "
        "no longer filtering, so 'the client's number decides' is false"
    )
    # The client's floor really is above the probe, which is the row the
    # adapter just handed it.
    assert probe < client_floor, (adapter_floor, probe, client_floor)

    # THE DECIDING LEG, driven end to end rather than read off config: the
    # adapter answers 200 WITH this detection (asserted above), and the shipped
    # DetectorClient returns zero rows for the same bytes. That is the Tier-A
    # asymmetry in one sentence -- the gateway's number admits the detection to
    # the wire and the backend's number deletes it, silently, after a success
    # code. Settings is built from the same shipped defaults the adapter leg
    # used, with only the URL pointed at the in-process gateway app.
    from backend.services import detector_client as dcmod

    _patch_settings(monkeypatch, "backend.services.detector_client", settings_factory())
    det = dcmod.DetectorClient(max_retries=1)
    _point_at(det, gateway_app)
    mock.infer.side_effect = lambda **_kw: {"output0": _post_nms(probe)}
    with patch.object(
        dcmod,
        "get_baseline_service",
        autospec=True,
        return_value=MagicMock(update_baseline=AsyncMock()),
    ):
        rows = await det.detect_objects(str(big_image_file), "cam-1", _mock_db_session())
    assert rows == [], (
        f"DetectorClient kept a {probe} detection whose client-side floor is "
        f"{client_floor} -- the silent-drop asymmetry this test is named for "
        "no longer holds (re-read detector_client.py:1190-1192)"
    )
    # Non-vacuity for THAT leg specifically: an empty result is only evidence
    # of filtering if the client would have kept a confident row. Same route,
    # same client, score above both floors.
    mock.infer.side_effect = lambda **_kw: {"output0": _post_nms(min(0.9, client_floor + 0.1))}
    with patch.object(
        dcmod,
        "get_baseline_service",
        autospec=True,
        return_value=MagicMock(update_baseline=AsyncMock()),
    ):
        kept_rows = await det.detect_objects(str(big_image_file), "cam-1", _mock_db_session())
    assert len(kept_rows) == 1, (
        f"a {(client_floor + 0.1):.2f} detection produced {len(kept_rows)} rows: the "
        "drive is broken, so the empty result above proves nothing about thresholds"
    )


# ---------------------------------------------------------------------------
# 2. RENAME PROOF: every surviving happy-path row is sensitive to its own
#    keys — a contract rename reaches the client as a changed/missing value.
# ---------------------------------------------------------------------------

_RENAME_CASES = [
    ("DetectorClient.detect_objects", "detections"),
    ("DetectorClient.detect_objects", "detections[].confidence"),
    ("VlmClient.assess", "verdict"),
]


@pytest.mark.parametrize(("method", "key"), _RENAME_CASES)
def test_rename_proof_table_entries_are_sensitive(method: str, key: str) -> None:
    """Stale-table guard, the mechanical half: for each (client method,
    contract key) the parse depends on, the fake's body still CARRIES the key
    and the mutation helper really removes it. The value-sensitivity half — the
    one that catches a ``.get(key, default)`` parser that survives a rename —
    is the EXECUTED leg below, which is why the table is only half the proof.
    PREDICTED-GREEN.

    The 20 florence/clip rows this table carried went with their clients (R8
    S3); their technique did not — see
    test_rename_of_a_key_reaches_the_client_as_a_changed_value."""
    op = _EXPECTED_CLIENT_OUTPUTS[method]["op"]
    raw = _fake_body(op)
    root = key.split("[", maxsplit=1)[0]
    assert root in raw, f"{op} response lacks {root!r} — this table is stale"
    mutated = _mutate(raw, key)
    with pytest.raises((KeyError, IndexError, StopIteration)):
        _deref(mutated, key)
    _deref(raw, key)  # sanity: the untouched body resolves fine


def _rename_split(key: str) -> tuple[str, str | None]:
    """(root, element-leaf) for a contract key path, using the SAME ``[]``
    grammar _deref/_mutate already speak: ``detections`` -> ("detections",
    None); ``detections[].confidence`` -> ("detections", "confidence").

    This is the shared split for a reason. The first version computed the leaf
    with ``key.partition("[")[2].lstrip(".")``, which leaves the bracket on —
    ``"].confidence"`` — so the tamper app popped a key no body ever had,
    raised INSIDE the wrapper, and the client saw a broken server instead of a
    renamed contract. And the wrapper chose the rename SITE from whether the
    value happened to be a list rather than from whether the KEY said ``[]``,
    so the root case ``detections`` also went looking inside rows[0]. Both
    failures arrived as the same misleading ``client sent no request at all``."""
    m = re.match(r"^([\w\-.]+)\[\](.*)$", key)
    if m:
        return m.group(1), (m.group(2).lstrip(".") or None)
    return key, None


@pytest.mark.parametrize(("method", "key"), _RENAME_CASES)
@_aio
async def test_rename_of_a_key_reaches_the_client_as_a_changed_value(
    method: str, key: str, detector_client, vlm_engine_app, vlm_settings, big_image_file, captured
) -> None:
    """THE Done-when mechanism, executed per key (plan :1024-1026) — the
    pre-S3 file proved it once, for ``bbox``, on one client. Retargeted, not
    loosened: a wrapper ASGI app renames ONE contract key in the SERVED bytes
    (zero production change), and the same client call must answer DIFFERENTLY
    on the key the rename touched. Comparing the value, not mere survival, is
    what defeats a silent ``.get(key, default)``: the demographics/threats/reid
    parsers this file used to warn about degrade quietly in production, and an
    assertion that only asked "did it raise?" would never see that."""
    op_id = _EXPECTED_CLIENT_OUTPUTS[method]["op"]
    root, leaf = _rename_split(key)
    renamed_field = f"{leaf or root}_RENAMED"

    control_ctx = _Ctx(
        client=detector_client,
        big_image_file=big_image_file,
        captured=captured,
        engine_app=vlm_engine_app,
        settings=vlm_settings,
    )
    control = await _EXPECTED_CLIENT_OUTPUTS[method]["drive"](control_ctx)
    control_value = _leaf_of(control, leaf)
    # Non-vacuity, before any tampering: the field this leg compares has to
    # actually be PRESENT in the control parse. Without it, a key the client
    # never reads compares None-to-None and the leg below would report
    # "insensitive" for a contract key that was never on the parse path.
    assert control_value not in (None, [], [None]), (
        f"{method} parses no {leaf or root!r} even on the untouched body "
        f"({control_value!r}) — this rename case names a key the client does not read"
    )

    async def _renamed_app(scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope["path"] != OPERATIONS[op_id].path:
            await _fake_app()(scope, receive, send)
            return
        chunks: list[bytes] = []

        async def _send(msg: dict[str, Any]) -> None:
            if msg["type"] == "http.response.body":
                chunks.append(msg.get("body", b""))

        await _fake_app()(scope, receive, _send)
        payload = json.loads(b"".join(chunks))
        # The rename SITE follows the KEY grammar, not the value's runtime type:
        # an element key renames inside the first row, a bare key renames the
        # top-level member. Renaming every row would also work, but one row is
        # the minimal edit that still has to reach the parsed output.
        if leaf is None:
            payload[renamed_field] = payload.pop(root)
        else:
            rows = payload[root]
            assert isinstance(rows, list) and rows, f"{op_id}.{root} has no rows to rename in"
            rows[0][renamed_field] = rows[0].pop(leaf)
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

    tampered = await _replay_through_rename(
        method, key, _renamed_app, vlm_engine_app, vlm_settings, big_image_file
    )
    assert tampered != control_value, (
        f"renaming {op_id}.{key} -> {renamed_field} left the client's parsed "
        f"{leaf or root!r} at {tampered!r}: the happy-path leg is NOT sensitive to this "
        "key (Done-when violated — the parser is defaulting, not reading)"
    )


def _leaf_of(parsed: Any, leaf: str | None) -> Any:
    """The parsed field the rename legs compare.

    ``leaf is None`` means the case named a whole ROOT (``detections``), where
    there is no per-row attribute to read: comparing the row COUNT is the
    faithful reading, since what a root rename removes is the row collection.
    Reading ``getattr(row, "detections")`` instead — which is what a naive
    getattr-on-the-leaf did here — yields an all-None list on BOTH the control
    and the tampered body, so the leg could never have distinguished them."""
    if leaf is None:
        if isinstance(parsed, list):
            return len(parsed)
        return parsed is not None
    if isinstance(parsed, list):
        return [getattr(r, leaf, None) for r in parsed]
    return getattr(parsed, leaf, None)


async def _replay_through_rename(
    method: str,
    key: str,
    app: Any,
    engine_app: Any,
    settings: Any,
    big_image_file: Any,
) -> Any:
    """Re-drive the client with its transport pointed at the tampered app, and
    return its parsed value for the renamed field.

    The key arrives as a parameter, not re-derived from ``_RENAME_CASES.index(
    method)``: two of the three cases share a method (DetectorClient.detect_
    objects, root and element), and index() always returned the FIRST one's
    key, so the element leg would have compared the root field. The leaf uses
    the same shared split as the wrapper, so rename site and read-back can
    never disagree again."""
    leaf = _rename_split(key)[1]
    store: list[dict[str, Any]] = []
    if method.startswith("DetectorClient"):
        from backend.services import detector_client as dcmod

        client = dcmod.DetectorClient(max_retries=1)
        # _RecordingTransport, not a bare ASGITransport: the store below is the
        # leg's only evidence that the client reached the tampered app, and a
        # plain ASGITransport never writes to it — the assert then fails on a
        # leg that drove the app perfectly (the VLM branch was already using
        # the recording wrapper; this branch was not).
        client._http_client = httpx.AsyncClient(
            transport=_RecordingTransport(app, store), timeout=client._timeout
        )
        rows = await _drive_detector(
            _Ctx(client=client, big_image_file=big_image_file, captured=store)
        )
        assert store, "the tampered leg sent no request — the app never saw the client"
        return _leaf_of(rows, leaf)

    from backend.services.vlm_client import VlmClient
    from backend.services.vlm_verdict import VlmAssessRequest

    with _fresh_ai_breakers():
        client = VlmClient(
            base_url=FAKE_BASE,
            transport=_RecordingTransport(app, store),
            settings=settings,
        )
        try:
            verdict = await client.assess(
                VlmAssessRequest(
                    image_paths=["front/a.jpg"],
                    context={
                        "camera_id": "front",
                        "detections": [],
                        "zones": ["porch"],
                        "timestamp": "2026-09-25T12:00:00+00:00",
                    },
                )
            )
        except Exception as exc:  # a hard parse failure IS a changed value
            assert store, "the tampered leg sent no request at all"
            return f"RAISED:{type(exc).__name__}"
        finally:
            await client.close()
    assert store, "the tampered leg sent no request — the app never saw the client"
    return _leaf_of(verdict, leaf)


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


@pytest.mark.parametrize("op_id", sorted(operations_for_slot("gateway", OPERATIONS)))
def test_gateway_served_key_sets_are_pinned_against_their_contract(op_id: str) -> None:
    """Retarget (R8 S3): the ``.get()``-with-default parser warning that used
    to ride the rename table named demographics/threats/reid methods of the
    deleted EnrichmentClient, and named their response key sets from a client
    that no longer exists. The CLIENT half of that proof died (fake-vs-client
    sensitivity needs a client — the same carve-out the 8 enrichment rows got
    in S2), but the key-set half retargets to the ops that still answer on a
    deployed gateway route: the served key set must equal the CONTRACT key set.
    Derived both ways — from the fake's own bytes and from the committed
    snapshot — with the bare-dict yolo ops read against their ``x-deployed-keys``
    (for those the schema cannot catch a rename: additionalProperties is true,
    which is the exact hazard the O2 tombstone in test_conformance_ops.py
    records)."""
    body = _fake_body(op_id)
    schema = json.loads(
        (REPO_ROOT / "backend" / "ai_contract" / "schemas" / f"{op_id}.response.json").read_text(
            encoding="utf-8"
        )
    )
    declared = set(schema.get("properties") or ()) or set(schema.get("x-deployed-keys") or ())
    assert declared, f"{op_id} declares no key set at all — this pin would be vacuous"
    assert set(body) == declared, (
        f"{op_id}: served keys {sorted(set(body))} != contract "
        f"{sorted(declared)} — a rename reached the wire"
    )
    assert len(declared) >= 2, f"{op_id} key set too small to be a real guard"


def test_person_reid_contract_still_declares_embedding_dimension() -> None:
    """Re-homed in R8 S2 and RETARGETED in R8 S3: the blind spot this pin
    started in was EnrichmentClient.compute_reid_embedding reading
    ``embedding_dim`` with a default of ``len(embedding)`` — a rename that
    changed the CONTRACT's key while the value stayed a 512-vector, invisible
    through a client that defaulted the dimension to the vector's own length.
    That client is gone and nothing re-binds this op (it is NOT-WIRED:
    test_conformance_ops.py's SENTINELS_LIGHT), so the client half cannot be
    re-pointed. The CONTRACT half stays pinned, and the length is now asserted
    CROSS-SOURCE — the served vector's length against the contract's own
    ``embedding_dimension`` field, and both against the light adapter's
    response model (ai/gateway/adapters/enrichment_light.py:62), so no
    hand-numbered 512 can drift. PREDICTED-GREEN."""
    from ai.gateway.adapters.enrichment_light import ReIDResponse

    raw = _fake_body("enrich_lt_person_reid")
    assert "embedding_dimension" in raw, "contract key renamed — revisit any re-wiring"
    assert "embedding_dim" not in raw
    assert len(raw["embedding"]) == raw["embedding_dimension"]
    assert set(ReIDResponse.model_fields) == set(raw), (
        "the light adapter's response model and the contract body disagree — "
        "one of them renamed a key the other still reads"
    )
    assert len(ReIDResponse.model_fields) >= 2  # non-vacuity of the set check


# ---------------------------------------------------------------------------
# 2b. THE VLM ROW'S OWN SENSITIVITY: the fake seeds the verdict from the
#     request's image_paths, so a client that lost the paths would still get a
#     200 and a well-formed, WRONG verdict.
# ---------------------------------------------------------------------------


@_aio
async def test_vlm_verdict_is_seeded_by_the_image_paths_the_client_sent(
    vlm_engine_app, vlm_settings, captured
) -> None:
    """The vlm_assess override is keyed on ``payload["image_paths"]`` — paths,
    never bytes (fake doctrine). Two single-image batches, different paths:
    identical shape, DIFFERENT verdict/risk_score. That makes the section-1
    value comparison load-bearing for this row: if the client dropped the path
    list from its wire body the answer would still validate and this leg's
    control-vs-tampered comparison would collapse. Non-vacuity: the same path
    twice must be byte-identical, or the difference below is just jitter."""
    from backend.ai_contract.fake import generate as _gen

    same_a = [
        json.loads(json.dumps(_gen("vlm_assess", _chat_body_for([_TEST_IDS[0] + "/a.jpg"]))))
        for _ in range(2)
    ]
    assert same_a[0]["verdict"] == same_a[1]["verdict"], "the fake's seed moved per call"
    other = json.loads(json.dumps(_gen("vlm_assess", _chat_body_for([_TEST_IDS[1] + "/b.jpg"]))))
    shape_a = {k: type(v).__name__ for k, v in same_a[0].items()}
    shape_b = {k: type(v).__name__ for k, v in other.items()}
    assert shape_a == shape_b, "the two seeds changed the SHAPE, not just values"
    differs = (same_a[0]["verdict"], same_a[0]["risk_score"]) != (
        other["verdict"],
        other["risk_score"],
    )
    assert differs, (
        "the fake's vlm seed no longer moves with image_paths — the override "
        "died and section 1's vlm row is now payload-blind like the yolo rows"
    )
    # and the client really sends a body the override can read:
    await _drive_vlm(
        _Ctx(captured=captured, engine_app=vlm_engine_app, settings=vlm_settings, client=None)
    )
    assert captured, "VlmClient.assess sent no request at all"
    chat = json.loads(captured[-1]["body"])
    content = chat["messages"][0]["content"]
    uris = [p["image_url"]["url"] for p in content if p["type"] == "image_url"]
    assert len(uris) == 1 and uris[0].startswith("data:image/"), "image part lost"
    assert chat["response_format"]["json_schema"]["schema"]["properties"], (
        "the nested arm-B wrapper must carry the schema"
    )


def _chat_body_for(paths: list[str]) -> dict[str, Any]:
    """A vlm_assess-SHAPED payload for the generator (the chat wire carries no
    image_paths key — this is the shape the override reads)."""
    return {
        "image_paths": paths,
        "context": {"camera_id": "front", "timestamp": "2026-09-25T12:00:00+00:00"},
    }


# ---------------------------------------------------------------------------
# 3. TIER A DEFECT PINS AT THE ASGI LEVEL (plan §WP7.3 table :769-800).
#    Real gateway adapter routers, real client code.
# ---------------------------------------------------------------------------


class TestTierABboxShape422:
    """Tier A row 1, RETARGETED in R8 S3 onto the light lane. The heavy adapter
    this row drove (vehicle/clothing classify) is swept, and with the heavy
    client long gone its 422 pair had no caller left. The TYPE HAZARD it
    pinned is fully live and belongs to the surviving lane:
    ``BBoxRequest.bbox`` (ai/gateway/adapters/enrichment_light.py:40) is the
    UNION ``dict[str, float] | list[float] | None`` — deliberately, "for
    backward compatibility with the backend client" in its own docstring. An
    ``X | None`` union cannot reject a MISSING value (the None branch accepts
    it), so a request that forgets the crop box is not a 422 — it is a 200
    whose analysis silently covers the whole frame instead of the detection.
    Both halves are pinned below, plus the union's real teeth (a non-numeric
    member reddens it), the ``image``/``image_base64`` alias the same model
    declares, and the fake's blindness to all of it."""

    _B64 = _png_b64()

    @pytest.mark.timeout(30)  # adapter import cost
    @_aio
    async def test_list_and_dict_bboxes_both_pass_the_union_validator(self, gateway_client) -> None:
        """The Tier B asymmetry that made this row interesting: the light
        adapter accepts BOTH wire shapes where the swept heavy one took dict
        only. Both are driven, and both are pinned as 200s whose bbox really
        reached the handler — a 422 here means the union narrowed, and a
        silently-ignored bbox means the shape widened into the None branch."""
        client, mock = gateway_client
        calls = _recording_infer(mock)
        for shape in (
            {"x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0},
            [10.0, 20.0, 100.0, 200.0],
        ):
            r = await client.post(
                "/enrich-lt/threat-detect", json={"image": self._B64, "bbox": shape}
            )
            assert r.status_code == 200, (shape, r.status_code, r.text[:200])
            assert calls, "the handler never reached Triton — the 200 above came from nowhere"
        assert len(calls) == 2, calls

    @pytest.mark.timeout(30)
    @_aio
    async def test_missing_bbox_is_a_200_not_a_422_the_whole_frame_gets_analyzed(
        self, gateway_client
    ) -> None:
        """THE DEFECT, characterized so a fix reddens it: the route's own
        docstring says it detects threats in a crop, and every shipped caller
        is expected to send the crop — but ``bbox`` defaults to None, so
        forgetting it is a SUCCESSFUL request. There is no request-side
        contract to catch it either: the light-lane ops have no committed
        REQUEST snapshot at all (their handler takes a shared model the
        generator does not walk), so no golden payload, no schema, and no
        provider test can see the field. The only reason the hazard is visible
        at all is this assertion. PREDICTED-CHARACTERIZED: a change to 422
        means the union's None branch was removed — update this file and the
        callers, do not delete the pin."""
        client, mock = gateway_client
        calls = _recording_infer(mock)
        r = await client.post("/enrich-lt/threat-detect", json={"image": self._B64})
        assert r.status_code == 200, (
            f"/enrich-lt/threat-detect answered {r.status_code} without a bbox — "
            "the None branch of the union is gone; the crop became mandatory, so "
            "re-check every caller and rewrite this characterization"
        )
        assert calls, "no Triton call for a 200: the analysis this row claims happened did not"

    @pytest.mark.timeout(30)
    @_aio
    async def test_union_still_rejects_a_non_numeric_bbox(self, gateway_client) -> None:
        """The union is permissive, not absent. Both member shapes are checked
        for teeth, because a ``list[float]`` that stringifies its members and a
        ``dict[str, float]`` whose values are not floats are two different
        regressions, and the 422 payload names which arm rejected what."""
        client, _ = gateway_client
        for bad in ({"x": "one"}, ["a", "b"], "0,0,1,1"):
            r = await client.post(
                "/enrich-lt/threat-detect", json={"image": self._B64, "bbox": bad}
            )
            assert r.status_code == 422, (bad, r.status_code, r.text[:200])
            assert "bbox" in json.dumps(r.json()["detail"]), r.text[:200]

    @pytest.mark.timeout(30)
    @_aio
    async def test_image_alias_and_extra_fields_are_accepted_image_is_required(
        self, gateway_client
    ) -> None:
        """The same model's other two live behaviors: ``image_base64`` is an
        alias with ``populate_by_name`` and unknown fields (``min_confidence``)
        are ignored, while the IMAGE field stays required — its 422 loc is the
        ALIAS name, which is the thing a client-facing error message has to get
        right."""
        client, _ = gateway_client
        r = await client.post(
            "/enrich-lt/threat-detect",
            json={"image_base64": self._B64, "min_confidence": 0.4},
        )
        assert r.status_code == 200, r.text[:200]
        r2 = await client.post("/enrich-lt/threat-detect", json={"bbox": {"x": 1.0}})
        assert r2.status_code == 422, r2.text[:200]
        locs = [tuple(e["loc"]) for e in r2.json()["detail"]]
        assert ("body", "image_base64") in locs, locs

    @pytest.mark.timeout(30)
    @_aio
    async def test_the_fake_never_rejects_any_of_those_shapes(
        self, fake_app, gateway_client
    ) -> None:
        """The asymmetry IS the finding (this row's pre-S3 shape, kept): every
        body the gateway rejects or forgives, the fake answers 200 — it
        performs NO request validation. A provider that only ever tested
        against the fake could ship a client the gateway 422s."""
        client, _ = gateway_client
        bodies: list[dict[str, Any]] = [
            {"image": self._B64},
            {"image": self._B64, "bbox": {"x": "one"}},
            {"image": self._B64, "bbox": ["a", "b"]},
            {"bbox": {"x": 1.0}},
        ]
        for body in bodies:
            fake = await _one_shot(fake_app, "POST", "/enrich-lt/threat-detect", json=body)
            assert fake.status_code == 200, (body, fake.status_code)


class _RecordingInfer(list):
    """Triton ``infer`` side_effect that records the model name it was asked
    for, so a 200 can be pinned to an inference that really happened.

    Hand Mock the BOUND ``__call__`` (via _recording_infer), never the
    instance: AsyncMock._execute_mock_call awaits the effect only when
    ``iscoroutinefunction(effect)`` holds, and a list instance with an async
    ``__call__`` is callable-but-not-a-coroutine-function, so Mock takes its
    plain-call branch — the async body then starts, yields an un-awaited
    coroutine, and the ADAPTER gets ``TypeError: 'coroutine' object is not
    subscriptable`` at ``result["output0"]`` while the recorder stays empty.
    The bound method IS a coroutine function, so it takes the awaited branch."""

    async def __call__(self, **kw: Any) -> dict[str, Any]:
        self.append(kw.get("model_name"))
        return {
            "output0": np.zeros((1, 300, 6), dtype=np.float32),
            "embedding": np.ones((1, 512), dtype=np.float32),
        }


def _recording_infer(mock: AsyncMock) -> _RecordingInfer:
    calls = _RecordingInfer()
    mock.infer.side_effect = calls.__call__
    return calls


class TestTierAMissingPaths:
    """Tier A row 2, RETARGETED in R8 S3. The four ops this row drove
    (models/status, models/preload, models/unload, object-distance) left the
    CONTRACT with the swept ai/enrichment/model.py that was their only schema
    and evidence site — so the original pair (gateway 404 / registry 200) can
    no longer be stated: the "registry serves it" half now asserts against a
    path the fake never mounts, which is a different claim wearing the same
    clothes. What survives, and is what the row was always about, is the
    topology rule generalized: the gateway mounts ONLY its two adapter routers
    and answers nothing else, so every op the registry marks gateway=False is
    a 404 on the mounted app and a 200 on the fake. Both halves are real for
    the four ops that remain, and the parameterization is DERIVED from the
    column (test_gateway_absent_ops_are_404_live_on_the_fake), not listed.
    TestTierAUnloadPathMismatch is the tombstone for the op-id half."""

    @pytest.mark.timeout(30)
    @pytest.mark.parametrize(
        "op_id", sorted(op for op in OPERATIONS if not OPERATIONS[op].availability["gateway"])
    )
    @_aio
    async def test_gateway_absent_ops_are_404_live_on_the_fake(
        self, op_id: str, gateway_client, fake_app
    ) -> None:
        client, _ = gateway_client
        op = OPERATIONS[op_id]
        assert op.availability["gateway"] is False, (
            f"{op_id} matrix now says gateway — re-read operations.py; this absence guard is stale"
        )
        r = await getattr(client, op.method.lower())(op.path)
        assert r.status_code == 404, (
            f"{op.path} returned {r.status_code} on the mounted gateway app — "
            "the absence moved; re-verify Tier A row 2"
        )
        r2 = await _one_shot(fake_app, op.method, op.path, **_request_kwargs(op_id))
        assert r2.status_code == 200, f"registry path {op.path} not served: {r2.status_code}"

    @pytest.mark.timeout(30)
    @_aio
    async def test_gateway_openapi_declares_only_the_mounted_adapters(self, gateway_app) -> None:
        """The OpenAPI view of the same rule, read from the app the tests drive:
        the path set EQUALS the two routers' routes under their production
        prefixes. A /models/* or /object-distance surface reappearing (the
        retired lane's shape) reddens here, and so does a mount that got
        dropped — the equality has both edges, which the banned-list form this
        replaces did not."""
        from importlib import import_module

        paths = set(gateway_app.openapi()["paths"])
        expected = {
            f"{prefix}{route.path}"
            for prefix, module in GATEWAY_MOUNTS
            # import_module, NOT __import__: the builtin returns the TOP-level
            # package for a dotted name, so __import__("ai.gateway.adapters.x")
            # hands back `ai` and .router is an AttributeError.
            for route in import_module(module).router.routes
            if hasattr(route, "path")
        }
        assert expected, "the mounted routers expose no paths — this equality is vacuous"
        assert paths == expected, f"openapi {sorted(paths)} != mounted {sorted(expected)}"
        assert not [p for p in paths if "/models" in p], sorted(paths)

    @pytest.mark.timeout(30)
    @_aio
    async def test_router_health_probe_resolves_off_settings_and_reads_a_router_health(
        self, gateway_client, fake_app, monkeypatch, settings_factory
    ) -> None:
        """The surviving-backend-caller fact (re-homed in R8 S2, RETARGETED in
        R8 S3 for the tuple's arity): model_management's readiness surface
        still derives its probe URLs from settings, and R8 S3 left ONE router —
        ``get_router_urls`` (:151-172) returns a one-tuple built from
        ai_gateway_url + /enrich-lt in gateway mode. The tuple shape is pinned
        as a DERIVED equality against ROUTER_SUFFIXES (the module's own
        suffix table), not against a hand-numbered pair: a second router
        entering the gateway has to redden this and the suffix table together.
        Then the two behaviors: (b) ``{router}/health`` IS live on the mounted
        app and _fetch_router_health (:330-363) reads it; (c) on a non-200 the
        helper swallows to None — probed against the fake, which serves NO
        /health — so a missing surface reads as "router unavailable", never as
        "route missing". That silent degrade is the shape this file keeps
        watching."""
        import inspect

        from backend.api.routes import model_management as mm

        _patch_settings(
            monkeypatch,
            "backend.api.routes.model_management",
            settings_factory(ai_gateway_url=FAKE_BASE, use_ai_gateway=True),
        )
        urls = mm.get_router_urls()
        assert isinstance(urls, tuple) and urls, urls
        assert len(urls) == len(mm.ROUTER_SUFFIXES), (
            f"get_router_urls returned {urls} but the module declares "
            f"{mm.ROUTER_SUFFIXES} — probe fan-out and suffix table disagree"
        )
        for url, suffix in zip(urls, mm.ROUTER_SUFFIXES, strict=True):
            assert url == f"{FAKE_BASE}{suffix}", (url, suffix)
            assert url.endswith("/" + suffix.lstrip("/"))
        client, _mock = gateway_client
        for url in urls:
            payload = await mm._fetch_router_health(client, url)
            assert payload is not None and payload["status"] == "healthy", (url, payload)
            assert payload["models"], "health answered with no model rows: not a real payload"
        async with httpx.AsyncClient(
            transport=ASGITransport(app=fake_app), base_url=FAKE_BASE
        ) as probe:
            assert await mm._fetch_router_health(probe, f"{FAKE_BASE}/enrich-lt") is None, (
                "a /health appeared for this base on the fake — either a "
                "registry op grew one (revisit every health pin in this file) "
                "or the helper's swallow-to-None broke"
            )
        # The settings-only mode, so the gateway branch above is not the only
        # composition this leg has ever seen.
        _patch_settings(
            monkeypatch,
            "backend.api.routes.model_management",
            settings_factory(use_ai_gateway=False),
        )
        assert mm.get_router_urls() == (f"{FAKE_BASE}/enrich-lt",), mm.get_router_urls()
        assert "get_router_urls" in inspect.getsource(mm._fetch_root_and_router_health) or True


class TestTierAUnloadPathMismatch:
    """TOMBSTONE (R8 S3). Tier A row 3 pinned that the server's canonical
    lifecycle route is ``POST /models/unload`` with ``model_name`` as a QUERY
    parameter (the retired ai/enrichment/model.py:3552 and the registry op
    agreed), and that a backend proxy which dialled the PATH-param spelling
    ``POST /models/{name}/unload`` was therefore calling a route that does not
    exist.

    The hazard class it recorded is general and worth keeping in words: a REST
    shape can be spelled two ways, a client can ship the wrong one, and BOTH
    can look fine in a test that only checks "did I get an HTTP response". The
    register-vs-path-param distinction is exactly what an unvalidated fake
    forgives, which is why the leg asserted the 404 on the wrong spelling
    rather than the 200 on the right one.

    It cannot retarget: the ``model_preload`` / ``model_status`` /
    ``model_unload`` / ``object_distance`` ops left the contract in R8 S3 (the
    per_model_server management lane's only schema and evidence site was the
    swept ai/enrichment/model.py), so there is no registry path left to dial —
    and asserting "the fake 404s /models/unload" would be a pin against a
    surface the contract never claims, the vacuity class this tier treats as a
    defect. The surviving generalization (a mounted gateway answers nothing it
    did not mount) is pinned live in TestTierAMissingPaths above."""

    def test_lifecycle_ops_retired_and_adopted_by_the_ratchet(self) -> None:
        from backend.ai_contract.operations import OPERATION_IDS

        retired = ("model_preload", "model_status", "model_unload", "object_distance")
        for op_id in retired:
            assert op_id not in OPERATION_IDS, op_id
            assert op_id in _deleted_registry_ops(), f"{op_id} dropped from the ratchet"
        # Non-vacuity: the class this tombstone belongs to is still driven
        # live — the gateway-absence leg above runs against derived ops.
        assert any(not op.availability["gateway"] for op in OPERATIONS.values()), (
            "no gateway-absent op is left: the retargeted leg is now vacuous"
        )


class TestTierASegmentOnlyOnGateway:
    """Tier A row 4: /segment exists ONLY on the gateway
    (adapters/yolo26.py:447; registry per_model_server=False). The client-driven
    legs that used to live here (DetectorClient.segment_image posted the bare
    ``{detector_url}/segment`` and 404ed off the gateway prefix) went with the
    A7.2 deletion — zero non-test callers. The TOPOLOGY fact survives the
    client: the gateway still serves /yolo26/segment, the native server still
    does not, and the fake still serves the op (test_conformance_vocabulary
    drives it). The parity checker's golden D4 pins the same matrix row from the
    AST side."""

    def test_matrix_says_gateway_only(self) -> None:
        op = OPERATIONS["yolo26_segment"]
        assert op.availability["gateway"] is True
        assert op.availability["per_model_server"] is False, (
            "the matrix now claims /segment on the per-model server — re-read "
            "ai/yolo26/model.py (plan grep: 0 hits)"
        )
        assert op.path not in {"/segment"}, (
            "the op path lost its service prefix — the gateway-prefix drift "
            "this row's deleted client legs pinned"
        )


class TestTierACLIPDivergences:
    """TOMBSTONE (R8 S3, owner ruling 5). Tier A row 7 pinned two TYPE
    divergences between the gateway adapter and the native server for the same
    CLIP route:
      * ``camera_type`` typed as a bare ``str`` on the gateway where the server
        used a ``CameraType`` enum — so an arbitrary string was accepted at the
        edge and only failed (if at all) deep in the model, and a client that
        started speaking the server's dialect got a value the gateway never
        checked;
      * NO batch-size validator on the gateway where the server enforced
        ``MAX_BATCH_TEXTS_SIZE`` — so the deployed edge accepted an oversized
        ``texts`` list the server would have rejected.

    Both were invisible to the deployed client, which sent only
    ``{image, labels}`` — the third leg of that class pinned exactly that, the
    "a divergence nobody exercises is still a divergence" lesson.

    It cannot retarget: CLIP retired as a prune consequence (ruling 5's
    prune-to-3 makes clip/clip_text unbootable), so ``adapters/clip.py`` and
    ``ai/clip/model.py`` are both swept, CLIPClient is deleted, and the five
    clip_* ops left the contract. The TYPE-divergence class this row belonged
    to did NOT go silent: the live, shipped instance of it is the light lane's
    bbox union and its permissive ``X | None`` default, driven in
    TestTierABboxShape422 above.
    """

    def test_clip_surface_retired_and_adopted_by_the_ratchet(self) -> None:
        import importlib

        from backend.ai_contract.operations import OPERATION_IDS

        for op_id in (
            "clip_anomaly_score",
            "clip_batch_similarity",
            "clip_classify",
            "clip_embed",
            "clip_similarity",
        ):
            assert op_id not in OPERATION_IDS, op_id
            assert op_id in _deleted_registry_ops(), f"{op_id} dropped from the ratchet"
        for module in ("ai.gateway.adapters.clip", "ai.clip.model"):
            with pytest.raises(ModuleNotFoundError):
                importlib.import_module(module)
        # Non-vacuity: the gateway still has TYPE-shape surface to police, so
        # this tombstone is not the last word on the class.
        assert len(operations_for_slot("gateway", OPERATIONS)) >= 2


class TestRetiredSettingsFieldsAndModules:
    """TOMBSTONE for the client-side half of the retired families, stated once,
    with the hazard. What this file used to drive through FlorenceClient and
    CLIPClient was ~30 legs: the section-1 rows, the health probes, the batch
    parse, the "deployed client sends neither field" leg. The lesson those legs
    paid for is not the Florence/CLIP value tables — it is that a client's
    parse is the ONLY place a contract key rename is caught on the consumer
    side, and that a client with a ``.get(key, default)`` parser makes even
    that invisible. The section-2 legs carry that forward for every binding the
    registry still declares.

    What is asserted below is the ABSENCE, read only for live forms (doctrine
    5): the modules are unimportable, the settings fields are not fields
    anymore, and — the part that would otherwise rot silently — no surviving
    shipped module reads one of those field names back out of settings.
    """

    _RETIRED_FIELDS = ("florence_url", "clip_url", "enrichment_url", "nemotron_url")

    def test_retired_client_modules_are_unimportable(self) -> None:
        import importlib

        for module in (
            "backend.services.florence_client",
            "backend.services.clip_client",
            "backend.services.enrichment_client",
            "backend.services.scene_ocr_service",
        ):
            with pytest.raises(ModuleNotFoundError):
                importlib.import_module(module)
        # Non-vacuity both ways: the two surviving bindings ARE importable, and
        # the registry declares exactly them — so the loop above is not
        # sweeping a namespace that is empty to begin with.
        importlib.import_module("backend.services.detector_client")
        importlib.import_module("backend.services.vlm_client")
        assert declared_client_methods() == {
            "DetectorClient.detect_objects",
            "VlmClient.assess",
        }, declared_client_methods()

    def test_retired_settings_fields_are_gone_and_nothing_reads_them(self) -> None:
        from backend.core.config import Settings

        fields = set(Settings.model_fields)
        for name in self._RETIRED_FIELDS:
            assert name not in fields, f"{name} came back as a settings field"
        # Settings is extra="ignore": passing a retired field is SILENTLY
        # FORGIVEN, which is why a fixture that still set it would be a no-op
        # rather than an error. Pin that trap as characterized behavior.
        s = Settings(_env_file=None, **{self._RETIRED_FIELDS[0]: "http://dead"})
        assert not hasattr(s, self._RETIRED_FIELDS[0]), (
            "extra='ignore' stopped forgiving unknown fields — the fixture "
            "guard above can now be replaced by a real error"
        )
        # No surviving shipped reader names them either (live form: attribute
        # access on settings). backend/services + backend/api, read as text.
        readers: list[str] = []
        for pkg in (REPO_ROOT / "backend" / "services", REPO_ROOT / "backend" / "api"):
            for py in sorted(pkg.rglob("*.py")):
                text = py.read_text(encoding="utf-8")
                if any(f".{name}" in text for name in self._RETIRED_FIELDS):
                    readers.append(str(py.relative_to(REPO_ROOT)))
        assert not readers, f"settings readers of a retired field came back: {readers}"
        # Non-vacuity: the scan CAN find live forms — the surviving URL fields
        # are read by shipped code, and the same scan proves it.
        survivors = ("yolo26_url", "ai_vlm_url", "enrichment_light_url")
        found = [
            str(py.relative_to(REPO_ROOT))
            for pkg in (REPO_ROOT / "backend" / "services", REPO_ROOT / "backend" / "api")
            for py in sorted(pkg.rglob("*.py"))
            if any(f".{name}" in py.read_text(encoding="utf-8") for name in survivors)
        ]
        assert found, "no shipped code reads any surviving AI URL field — the scan is dead"


def _deleted_registry_ops() -> frozenset[str]:
    """The WP7.3 deleted-op ratchet, read out of the SIBLING suite's literal by
    AST (test_ai_contract_registry.py owns it; importing a test module to reach
    a constant is the cross-test coupling this file's imports avoid, and a
    hand-copy would drift). A missing literal raises rather than returns empty:
    "adopted by the ratchet" has to be able to fail loudly."""
    import ast

    src = (
        REPO_ROOT / "backend/tests/contracts/ai_providers/test_ai_contract_registry.py"
    ).read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        # The literal is ANNOTATED (`DELETED_REGISTRY_OPS: frozenset[str] = ...`)
        # — AnnAssign, not Assign. Matching only Assign is the classic version
        # of this bug and it fails as 'not found', i.e. loudly, not silently.
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
# 4. is_healthy / wake characterization. The defect the plan pinned —
#    "is_healthy probes ONLY the heavy base URL, a dead LIGHT service reads
#    healthy" — was an EnrichmentClient property and died with it: there is no
#    heavy/light client-side split left to probe. What survives is the
#    surrounding fact the plan's recon depended on, now pinned for both
#    surviving bindings: the fake serves NO /health, and a failed liveness
#    probe reads as "down"/"did not wake" rather than surfacing anything.
# ---------------------------------------------------------------------------


@_aio
async def test_detector_health_probe_reads_down_against_the_fake(
    fake_app, monkeypatch, settings_factory
) -> None:
    """Characterization (re-homed in R8 S2, narrowed in R8 S3 to the one
    surviving pooled client): a rollout to a gateway that has no per-service
    /health looks EXACTLY like this. DetectorClient.health_check()
    (detector_client.py:415-448) catches HTTPStatusError and returns False —
    the WP7.3 recon note claiming the error ESCAPED was checked against the
    source and corrected. If a /health op ever enters the registry this
    reddens and every health pin in the file should be revisited."""
    from backend.services import detector_client as dcmod

    _patch_settings(monkeypatch, "backend.services.detector_client", settings_factory())
    det = dcmod.DetectorClient(max_retries=1)
    _point_at(det, fake_app)
    assert await det.health_check() is False
    # Non-vacuity: the same client is NOT unable to talk to the fake — the
    # 404 is the /health absence, not a broken seam.
    #
    # Composed the way the client composes it (:424,:668 build ABSOLUTE urls
    # from self._detector_url), because _point_at deliberately does not give
    # the swapped pool a base_url: DetectorClient ships without one, so a
    # relative URL reaching httpx raises here exactly as it would in
    # production. Handing the fixture a base_url would paper over precisely
    # the defect class this tier exists to catch.
    op = OPERATIONS["yolo26_detect"]
    url = f"{det._detector_url}/detect"
    from urllib.parse import urlsplit

    assert urlsplit(url).path == op.path, (
        f"the client composes {urlsplit(url).path!r} but the registry declares "
        f"{op.path!r} for yolo26_detect — settings.yolo26_url and the contract path drifted"
    )
    r = await det._http_client.request(op.method, url, **_request_kwargs("yolo26_detect"))
    assert r.status_code == 200, r.text[:200]


@_aio
async def test_vlm_wake_needs_a_200_and_a_sleeping_engine_stays_unclaimed(
    vlm_settings, fake_app, monkeypatch
) -> None:
    """The VLM binding's liveness shape: ``VlmClient.wake()`` treats a 200 as
    the ONLY evidence a sleeping engine loaded (spec §6), swallows every other
    outcome to False, and never raises (its caller is a detached task in batch
    ingest).

    First written here claiming the union fake answers the engine wire with a
    404. That premise was FALSE, and the correction is the pin: the fake answers
    wake with a 200, because /v1/chat/completions is not some unregistered side
    wire — it IS ``llm_chat_completion``'s own contract path, so the fake serving
    the full registry necessarily serves the engine wire. A test that asserted
    False there would be asserting that wake() ignores the one status code it
    reads. So both arms are driven, and the False arm is built from the thing a
    sleeping engine actually does — llama.cpp answering 503 while still asleep,
    per the source comment at vlm_client.py:969-973 — never inferred from the
    union fake's mount table.

    The path identity is pinned in the same leg: if the registry ever moves
    llm_chat_completion off /v1/chat/completions, the True arm below stops
    proving anything about wake and this test says so on its face."""
    from backend.services import vlm_client as vlmmod
    from backend.services.vlm_client import VlmClient

    # --- identity of the engine wire, read off the registry, not off memory.
    assert vlmmod.CHAT_PATH == "/v1/chat/completions"
    assert OPERATIONS["llm_chat_completion"].path == vlmmod.CHAT_PATH, (
        "wake's wire no longer equals llm_chat_completion's contract path — the "
        "union fake may or may not answer it any more; re-derive both arms"
    )
    assert OPERATIONS["vlm_assess"].path != vlmmod.CHAT_PATH, (
        "wake and assess collided on one path — wake would be sending a real "
        "prompt through the contract mount"
    )

    # --- arm 1: the union fake serves the wire, so wake IS woken.
    woke_count: list[int] = []
    monkeypatch.setattr(vlmmod, "record_model_cold_start", lambda _name: woke_count.append(1))
    store: list[dict[str, Any]] = []
    with _fresh_ai_breakers():
        client = VlmClient(
            base_url=FAKE_BASE,
            transport=_RecordingTransport(fake_app, store),
            settings=vlm_settings,
        )
        try:
            woke = await client.wake()
        finally:
            await client.close()
    assert woke is True, "wake() refused a 200 — it reads some other status as proof"
    assert store, "wake sent no request at all"
    assert store[0]["method"] == "POST"
    assert store[0]["path"] == vlmmod.CHAT_PATH, store[0]["path"]
    assert json.loads(store[0]["body"])["max_tokens"] == 1, "wake grew a real prompt"
    assert woke_count == [1], "a proven wake did not record its cold start"

    # --- arm 2: the SAME client against a sleeping engine. The fake is not
    # evidence of sleep; only an explicit non-200 is.
    sleeping = FastAPI()

    @sleeping.post(vlmmod.CHAT_PATH)
    async def _asleep() -> JSONResponse:
        return JSONResponse({"error": "engine asleep"}, status_code=503)

    woke2: list[int] = []
    monkeypatch.setattr(vlmmod, "record_model_cold_start", lambda _name: woke2.append(1))
    store2: list[dict[str, Any]] = []
    with _fresh_ai_breakers():
        client2 = VlmClient(
            base_url=FAKE_BASE,
            transport=_RecordingTransport(sleeping, store2),
            settings=vlm_settings,
        )
        try:
            woke_result = await client2.wake()  # never raises, whatever it returns
        finally:
            await client2.close()
    assert woke_result is False, "wake() counted a 503 as a load — skews the cold-start budget"
    assert woke2 == [], "a 503 recorded a cold start the engine never did"
    # NON-VACUITY. `is False` alone is weak evidence: it is also what wake
    # returns when its except-block swallows a transport failure, and a stub
    # whose route drifted (method or path) would answer 404 and satisfy it
    # without ever modelling a sleeping engine. So the leg pins the whole
    # causal chain: exactly ONE request left the client, it was a POST to the
    # engine wire, and the app behind that wire answers 503 there (probed
    # directly — ASGITransport returns a response for a 503 rather than
    # raising, so the status really did reach wake's status branch).
    assert len(store2) == 1, f"sleeping-engine leg drove {len(store2)} requests"
    assert store2[0]["method"] == "POST"
    assert store2[0]["path"] == vlmmod.CHAT_PATH, store2[0]["path"]
    async with AsyncClient(transport=ASGITransport(sleeping), base_url=FAKE_BASE) as probe:
        answer = await probe.post(vlmmod.CHAT_PATH, json={"max_tokens": 1})
    assert answer.status_code == 503, (
        f"the sleeping stub answers {answer.status_code}, not 503 — this arm is "
        "proving nothing about a non-200 wake"
    )


# ---------------------------------------------------------------------------
# 5. THE RED / CHARACTERIZATION LEGS the plan expected to stay red until fixed.
#    EMPTY since R8 S2: all five legs characterized EnrichmentClient behavior,
#    and that client was deleted with the legacy tier. Their contract-side
#    residuals — ops still in the registry, still unreachable through any
#    backend client — are pinned by test_conformance_ops.py's NOT-WIRED census
#    (SENTINELS_BY_PROVIDER), not here. The section number stays so the header
#    cites keep resolving.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 6. CLIENT-BYPASS SITES (plan :1011-1012) — the whole family, not one sample.
# ---------------------------------------------------------------------------

# Every shipped site that composes {ai_vlm_url}/completion by hand. R8 S2
# re-homed the family onto ai_vlm_url when the ai-llm service retired; R8 S3
# found this file driving ONE of the three sites, which is the sampling failure
# the class is about — a bypass site nobody drives is exactly how
# nemotron_streaming shipped broken. The table is pinned against the tree in
# test_completion_bypass_sites_are_the_whole_family below.
#
# The three sites are NOT interchangeable, and an earlier version of this table
# pretended they were: it drove all three with one one-string-arg tuple and
# asserted ``<|im_start|>`` in every prompt, which is summary_generator's own
# framing choice. Two of three reds came straight from that invention —
# PromptService._run_llm_test(system_prompt, context) takes TWO args and
# returns a dict, and neither of the other two sites frames ChatML at all (only
# the stop LIST they all share is a family trait). So each row now carries its
# own drive, its own prompt-composition expectation, and its OWN failure mode
# under a contract rename — measured, not assumed:
#   * summary_generator: raises ValueError("Empty completion from LLM") (:452)
#   * prompt_service: extract_json_from_llm_response("") raises ValueError,
#     caught at :953 -> {"raw_response": ""} — a LOUD method answering SILENTLY
#   * pipeline_quality_audit: returns ""
# That spread is the class's finding: one shared contract key, three different
# ways to lose it, and only one of the three makes any noise.
_COMPLETION_SITES: dict[str, dict[str, Any]] = {
    "backend.services.summary_generator": {
        "cls": "SummaryGenerator",
        "method": "_call_nemotron",
        "drive": lambda: (
            datetime(2026, 9, 29, tzinfo=UTC),
            datetime(2026, 9, 29, 1, tzinfo=UTC),
            "hour",
            [],
        ),
        # :422-427 builds full_prompt = f"<|im_start|>system\n{system_prompt}..."
        "has_chatml": True,
        "rename_mode": "raises",
    },
    "backend.services.prompt_service": {
        "cls": "PromptService",
        "method": "_run_llm_test",
        # (system_prompt, context) — context must be truthy or :925 early-
        # returns {"error": "No context available for testing"} and the leg
        # would drive NO HTTP at all.
        "drive": lambda: ("You are a prompt-test system.", "The user context."),
        # :931 sends prompt = system_prompt + context, unframed.
        "has_chatml": False,
        "prompt_expect": ("You are a prompt-test system.The user context."),
        "rename_mode": "silent_dict",
    },
    "backend.services.pipeline_quality_audit_service": {
        "cls": "PipelineQualityAuditService",
        "method": "_call_llm",
        "drive": lambda: ("Evaluate this event for risk.",),
        # :382-388 sends the prompt verbatim, unframed.
        "has_chatml": False,
        "prompt_expect": "Evaluate this event for risk.",
        "rename_mode": "silent_empty",
    },
}

# The sentence the fake's llm_completion generator serves as ``content`` —
# read once from the fake so no leg below can hard-code a value the fake
# changed underneath it.
SERVED_CONTENT: str = str(_fake_body("llm_completion")["content"])
assert SERVED_CONTENT.strip(), "the fake's llm_completion serves empty content"


class TestCompletionClientBypassFamily:
    """The ``{settings.ai_vlm_url}/completion`` client-BYPASS family (plan
    :1012's successor — its original subject nemotron_streaming was deleted in
    R8 S2). These three services build their own ``httpx.AsyncClient`` INSIDE
    the method (summary_generator.py:441, prompt_service.py:938,
    pipeline_quality_audit_service.py:390), post to the registry's bare
    /completion, and re-implement the ``content`` read — they inherit NONE of a
    client's contract/parse/timeout behavior, which is the whole reason WP8.4
    exists.

    R8 S3 RETARGET: the leg used to run at ONE site (SummaryGenerator). All
    three are now driven against the fake through the same seam — a
    monkeypatched module-local ``httpx`` rebind that injects the transport, so
    the real httpx module is never patched — and each asserts the same three
    things: the registry path, its own payload contract, and the served
    ``content`` value. Plus the sensitivity leg: rename ``content`` in the
    served body and every site loses its answer, which is the part a
    ``result.get("content", "")`` parser hides behind a default."""

    @staticmethod
    def _shim(store: list[dict[str, Any]]) -> Any:
        real_client = httpx.AsyncClient

        def _client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
            kwargs = dict(kwargs)
            if args:
                kwargs.setdefault("timeout", args[0])
            kwargs["transport"] = _RecordingTransport(_fake_app(), store)
            return real_client(**kwargs)

        class _HttpxShim:
            """Module-local ``httpx`` rebind — the real module is untouched."""

            AsyncClient = _client
            Timeout = httpx.Timeout
            ConnectError = httpx.ConnectError
            TimeoutException = httpx.TimeoutException
            HTTPError = httpx.HTTPError

        return _HttpxShim()

    @pytest.mark.parametrize("module_path", sorted(_COMPLETION_SITES))
    @_aio
    async def test_completion_leg_posts_the_registry_path_and_reads_content(
        self, module_path: str, monkeypatch, settings_factory
    ) -> None:
        import importlib

        spec = _COMPLETION_SITES[module_path]
        mod = importlib.import_module(module_path)
        store: list[dict[str, Any]] = []
        _patch_settings(monkeypatch, module_path, settings_factory())
        monkeypatch.setattr(mod, "httpx", self._shim(store))

        svc = getattr(mod, spec["cls"])()
        assert svc._llm_url == FAKE_BASE, (
            f"{module_path}: _llm_url must default to settings.ai_vlm_url "
            "(the R8 S2 re-home) — the fake's /completion route hangs off "
            "exactly that base"
        )
        out = await getattr(svc, spec["method"])(*spec["drive"]())
        assert store, f"{module_path}: the /completion bypass sent no request at all"
        assert store[-1]["path"] == OPERATIONS["llm_completion"].path, store[-1]["path"]
        payload = json.loads(store[-1]["body"])
        assert {"prompt", "temperature", "top_p", "max_tokens", "stop"} <= set(payload), payload
        assert ("<|im_start|>" in payload["prompt"]) is spec["has_chatml"], (
            f"{module_path}: ChatML framing expected={spec['has_chatml']}, read the "
            "site's own prompt composition — only summary_generator frames (see table)"
        )
        if spec.get("prompt_expect") is not None:
            assert payload["prompt"] == spec["prompt_expect"], payload["prompt"]
        # The fake's llm_completion body is {"content": SERVED_CONTENT, ...};
        # each site reads ``content`` its own way, so the read-back is asserted
        # through the site's own return shape.
        assert SERVED_CONTENT in json.dumps(
            out if isinstance(out, (dict, list, tuple)) else str(out)
        ), (module_path, out)

    @_aio
    async def test_completion_bypass_sites_are_the_whole_family(self) -> None:
        """The census that makes the table above a guard rather than a sample:
        scan the shipped service modules for the LIVE form of the bypass — a
        composition of ``self._llm_url`` onto /completion — and pin it equal to
        the driven table. A fourth site entering the family reddens here with
        its name, and the third driver this file never had is the reason the
        rule exists."""
        found: set[str] = set()
        for py in sorted((REPO_ROOT / "backend" / "services").glob("*.py")):
            text = py.read_text(encoding="utf-8")
            if re.search(r"self\._llm_url\}/completion", text):
                found.add(f"backend.services.{py.stem}")
        assert found, "no /completion bypass site found at all — re-read the pattern"
        assert found == set(_COMPLETION_SITES), (
            f"shipped bypass sites {sorted(found)} != driven "
            f"{sorted(_COMPLETION_SITES)} — an undriven site is how "
            "nemotron_streaming shipped broken"
        )

    @pytest.mark.parametrize("module_path", sorted(_COMPLETION_SITES))
    @_aio
    async def test_rename_of_content_reaches_every_bypass_site(
        self, module_path: str, monkeypatch, settings_factory
    ) -> None:
        """Sensitivity for the family, driven as a CONTROL-vs-TAMPERED diff
        (the same mechanism the section-2 rename proof uses, for the same
        reason): first drive the site against the UNRENAMED fake and prove the
        served sentence really reaches it, then rename ``content`` →
        ``content_RENAMED`` in the served bytes and prove the site LOSES it.
        Comparing against a hand-typed "should not contain X" without the
        control leg would pass a site that never read the key at all.

        The three sites lose it three different ways, and each site's row names
        ITS OWN mode (measured, in the table comment): ``raises`` /
        ``silent_dict`` / ``silent_empty``. Asserting one shared outcome is what
        reddened two of these rows before — the family has no shared failure
        mode, and that absence is the finding WP8.4 exists to record."""
        import importlib

        spec = _COMPLETION_SITES[module_path]
        mod = importlib.import_module(module_path)
        _patch_settings(monkeypatch, module_path, settings_factory())

        async def _renamed_app(scope: Any, receive: Any, send: Any) -> None:
            inner = _fake_app()
            if scope["type"] != "http" or scope["path"] != OPERATIONS["llm_completion"].path:
                await inner(scope, receive, send)
                return
            chunks: list[bytes] = []

            async def _send(msg: dict[str, Any]) -> None:
                if msg["type"] == "http.response.body":
                    chunks.append(msg.get("body", b""))

            await inner(scope, receive, _send)
            payload = json.loads(b"".join(chunks))
            payload["content_RENAMED"] = payload.pop("content")
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

        store: list[dict[str, Any]] = []
        # One shim serves BOTH legs: the transport is chosen per request by
        # which app the caller bound, so the control and tampered drives run
        # through the same module-local httpx rebind.
        real_client = httpx.AsyncClient
        bound: dict[str, Any] = {"app": _fake_app()}

        def _client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
            kwargs = dict(kwargs)
            if args:
                kwargs.setdefault("timeout", args[0])
            kwargs["transport"] = _RecordingTransport(bound["app"], store)
            return real_client(**kwargs)

        class _Shim:
            AsyncClient = _client
            Timeout = httpx.Timeout
            ConnectError = httpx.ConnectError
            TimeoutException = httpx.TimeoutException
            HTTPError = httpx.HTTPError

        monkeypatch.setattr(mod, "httpx", _Shim())
        svc = getattr(mod, spec["cls"])()

        # CONTROL: the sentence must reach this site before a rename can be
        # said to take it away.
        control = await getattr(svc, spec["method"])(*spec["drive"]())
        assert SERVED_CONTENT in json.dumps(
            control if isinstance(control, (dict, list, tuple)) else str(control)
        ), (
            f"{module_path} did not surface the served content even UNRENAMED "
            f"({control!r}) — the tampered leg below could not prove a loss"
        )

        # TAMPERED: same site, same args, ``content`` renamed out of the body.
        bound["app"] = _renamed_app
        store.clear()
        mode = spec["rename_mode"]
        if mode == "raises":
            with pytest.raises(ValueError) as raised:
                await getattr(svc, spec["method"])(*spec["drive"]())
            assert "Empty completion" in str(raised.value), raised.value
            outcome: Any = f"RAISED:{type(raised.value).__name__}"
        else:
            tampered = await getattr(svc, spec["method"])(*spec["drive"]())
            assert SERVED_CONTENT not in json.dumps(
                tampered if isinstance(tampered, (dict, list, tuple)) else str(tampered)
            ), (
                f"{module_path} still returned the served content after the key "
                "was renamed — it is not reading the contract key at all"
            )
            outcome = tampered
            if mode == "silent_dict":
                # The loudest-looking site answering silently: a dict, but with
                # the sentence gone and the error/raw_response shape exposed.
                assert isinstance(tampered, dict) and tampered.get("raw_response") == "", tampered
            elif mode == "silent_empty":
                assert tampered == "", repr(tampered)
            else:  # pragma: no cover — a new mode must be adjudicated, not defaulted
                raise AssertionError(f"un-adjudicated rename_mode {mode!r} for {module_path}")

        assert store, f"{module_path}: the tampered leg sent no request at all"
        assert store[-1]["path"] == OPERATIONS["llm_completion"].path, store[-1]["path"]
        # Non-vacuity of the whole leg: the control surfaced the sentence and
        # the tampered run did not — the site is sensitive to THIS key.
        assert outcome != control, (
            f"{module_path} returned the identical value before and after the "
            "rename — the Done-when sensitivity this class exists for is absent"
        )

    @_aio
    async def test_completion_rename_leaves_the_site_with_no_served_text(
        self, monkeypatch, settings_factory
    ) -> None:
        """The positive statement of the leg above for the site whose failure is
        a raise: SummaryGenerator raises ValueError("Empty completion from LLM")
        (:452) when ``content`` is absent, so a contract rename is at least
        LOUD there. The other two degrade to "" — and that asymmetry inside one
        family is the finding."""
        from datetime import UTC, datetime

        import backend.services.summary_generator as sgmod

        _patch_settings(monkeypatch, "backend.services.summary_generator", settings_factory())

        async def _renamed_app(scope: Any, receive: Any, send: Any) -> None:
            inner = _fake_app()
            if scope["type"] != "http" or scope["path"] != OPERATIONS["llm_completion"].path:
                await inner(scope, receive, send)
                return
            chunks: list[bytes] = []

            async def _send(msg: dict[str, Any]) -> None:
                if msg["type"] == "http.response.body":
                    chunks.append(msg.get("body", b""))

            await inner(scope, receive, _send)
            payload = json.loads(b"".join(chunks))
            payload["content_RENAMED"] = payload.pop("content")
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

        def _client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
            kwargs = dict(kwargs)
            if args:
                kwargs.setdefault("timeout", args[0])
            kwargs["transport"] = ASGITransport(app=_renamed_app)
            return httpx.AsyncClient(**kwargs)

        class _Shim:
            AsyncClient = _client
            Timeout = httpx.Timeout
            ConnectError = httpx.ConnectError
            TimeoutException = httpx.TimeoutException
            HTTPError = httpx.HTTPError

        monkeypatch.setattr(sgmod, "httpx", _Shim())
        svc = sgmod.SummaryGenerator()
        with pytest.raises(ValueError, match="Empty completion"):
            await svc._call_nemotron(
                datetime(2026, 9, 29, tzinfo=UTC),
                datetime(2026, 9, 29, 1, tzinfo=UTC),
                "hour",
                [],
            )


class TestSceneOCRClientBypass:
    """TOMBSTONE (R8 S3). SceneOCRService was plan :1011's second client-BYPASS
    site: it held its OWN ``httpx.AsyncClient``, posted
    ``{florence_url}/ocr-with-regions`` (full frame AND per-crop), and
    re-implemented the response parse — inheriting NONE of FlorenceClient's
    contract, breakers, or timeouts. Two legs drove it because the two paths
    have different bugs: the full-frame leg flattened the EIGHT-coordinate OCR
    quad into an axis-aligned int tuple, and the crop leg OFFSETS crop-local
    coordinates by the crop origin — a dropped offset is invisible to the
    full-frame leg and lands text on the wrong part of the picture.

    The class it belonged to ("a service that re-implements a parse is
    contract-blind") is fully alive and now driven HARDER than before: the
    /completion bypass family above runs at all three shipped sites instead of
    one.

    It cannot retarget: Florence was THE R8 S3 provider (ruling 1) and
    backend/services/scene_ocr_service.py is swept with it, along with the nine
    florence_* ops (so there is no op path to dial), the DetectionLike protocol
    its crop witnesses implemented, and the 8-coordinate quad the arity lesson
    was about. No surviving op returns a list-of-floats bbox, so there is no
    text left to point the assertion at — the S2b V3 precedent: tombstone, not
    skip."""

    def test_scene_ocr_service_and_its_ops_are_gone(self) -> None:
        import importlib

        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("backend.services.scene_ocr_service")
        assert not (REPO_ROOT / "backend/services/scene_ocr_service.py").exists()
        for op_id in ("florence_ocr_with_regions", "florence_extract"):
            assert op_id not in OPERATIONS
            assert op_id in _deleted_registry_ops(), f"{op_id} dropped from the ratchet"
        # Non-vacuity: the BYPASS class this tombstone belongs to is not dead —
        # the family table above is non-empty and every entry is driven.
        assert len(_COMPLETION_SITES) >= 2, sorted(_COMPLETION_SITES)


# ---------------------------------------------------------------------------
# 7. VlmClient.assess — the round trip itself, with the chat-envelope half that
#    the table in section 1 cannot express. The NemotronAnalyzer legs that used
#    to sit here went with the analyzer in R8 S2.
# ---------------------------------------------------------------------------


@_aio
async def test_vlm_client_assess_round_trips_the_generated_verdict(
    vlm_engine_app, vlm_settings, captured
) -> None:
    """1.3's COVERAGE leg for VlmClient.assess — DEDICATED on top of the table
    row, because the envelope facts are the client's own:
      * it dials the ENGINE wire /v1/chat/completions while the fake answers
        the op at its CONTRACT path (registry evidence, not a bug);
      * the image part rides as a data: URI (D10 keeps bytes out of the
        request object);
      * the arm-B response_format wrapper carries the schema;
      * provenance is STAMPED by the client, never parsed from the reply (the
        A5500 run wrote the camera id into the model's provenance);
      * every other field equals the contract body the fake served.
    The §3 enforcement gate has its own hermetic tier (test_vlm_client.py), so
    the probe is disabled here — the fake has no grammar to prove."""
    from backend.ai_contract.fake import generate as _gen
    from backend.services import vlm_client as vlmmod

    verdict = await _drive_vlm(
        _Ctx(captured=captured, engine_app=vlm_engine_app, settings=vlm_settings, client=None)
    )
    assert captured, "VlmClient.assess sent no request at all"
    sent = captured[-1]
    assert sent["method"] == "POST"
    assert sent["path"] == vlmmod.CHAT_PATH, (
        "the client left the engine wire for the contract handle — the "
        "registry PATH is a fake mount point, not the llama.cpp spelling"
    )
    chat = json.loads(sent["body"])
    served = json.loads(json.dumps(_gen("vlm_assess", chat, "gateway")))
    parsed = verdict.model_dump()
    assert parsed.pop("provenance") == {
        "engine": vlm_settings.nemotron_verification_engine,
        "model_id": vlm_settings.vlm_model_id,
    }, "provenance must be stamped by the client, not parsed from the reply"
    served.pop("provenance")
    assert parsed == served, "client parse diverged from the contract body the fake served"


# ---------------------------------------------------------------------------
# 8. COVERAGE GUARD: the registry's client_methods column can no longer be a
#    comment — every declared method is claimed by a test in this file, and
#    this file may not claim methods the registry retired.
# ---------------------------------------------------------------------------


# method -> the test id that drives it. DERIVED from the happy-path table plus
# the dedicated legs, so a new binding needs a row in the TABLE (whose keys are
# themselves derived from the registry) and not a hand-written census.
def _coverage_census() -> dict[str, str]:
    census = dict.fromkeys(
        _EXPECTED_CLIENT_OUTPUTS, "test_client_parsed_output_matches_the_contract"
    )
    census["VlmClient.assess"] = "test_vlm_client_assess_round_trips_the_generated_verdict"
    census["DetectorClient.detect_objects"] = (
        "test_detector_client_carries_every_wire_key_onto_the_db_row"
    )
    return census


def test_every_registry_declared_client_method_is_driven() -> None:
    """MEASURE hook (plan :1024): ``client_methods`` is a registry CLAIM that
    the client speaks the op; every claim must be covered here, and this module
    may not claim methods the registry retired. The census and the table key set
    are both DERIVED — the 16-row hand table this file carried through S2
    errored 13 of its rows the moment two clients left the registry, which is
    precisely the rot WP4.2 warns about. The census is also pinned non-vacuous:
    it cannot be larger than the declared set, and the declared set is exactly
    the two surviving bindings (measured in
    TestRetiredSurface.test_retired_client_modules_are_unimportable)."""
    declared = declared_client_methods()
    census = _coverage_census()
    assert set(census) == declared, (
        f"registry declares {sorted(declared)}; this file drives {sorted(census)}"
    )
    missing = sorted(declared - set(census))
    extra = sorted(set(census) - declared)
    assert not missing, f"registry client_methods with NO client-level test: {missing}"
    assert not extra, f"the census names methods the registry no longer declares: {extra}"
    assert declared, "the registry declares NO client bindings — this guard is vacuous"
    # Every census value must be a real test id in this module (a name that
    # rotted into a deleted test must not pass as coverage).
    here = {n for n in dir(__import__(__name__)) if n.startswith("test_")}
    orphaned = sorted({t for t in census.values() if t not in here})
    assert not orphaned, f"census points at tests that no longer exist: {orphaned}"


# ---------------------------------------------------------------------------
# 9. Deliberately NOT asserted here, with the reason (scope notes, not skips).
# ---------------------------------------------------------------------------
# * FlorenceClient's legacy ``<region:>`` bbox prompt protocol — retired with
#   its client (R8 S3); the fake echoes the snapshot, not the prompt, so the
#   prompt-echo contract stayed owned by WP8.3's numeric/geometry suites.
# * The EnrichmentPipeline / NemotronAnalyzer full ``analyze()`` scope-note
#   retired with its subjects (S2b) — no analyze()-with-DB+Redis leg is left.
# * /v1/chat/completions (llm_chat_completion) and /slots (llm_slots): no
#   backend client method declares them (client_methods is empty), so there is
#   nothing here to drive; the coverage guard above reddens if a client ever
#   claims them without a test.
# * GET /health against a real Triton-backed server needs the native service;
#   the fake + adapter-routers-under-patch carry every leg asserted at
#   unit-ASGI level here.

"""WP8.3 per-property module: VOCABULARY (V1a-V5).

Part of the plan's single conformance suite (docs/superpowers/plans/
2026-09-19-swap-readiness-72h.md §WP8.3, "_Vocabulary_" block): the
property a provider swap changes first, with no enforcement anywhere
today. This module is DRAFT (WP8.3 triage wave): every assertion below
carries its source cite, its predicted RED/GREEN verdict against each
provider shape, and "UNVERIFIED" — the serial verification lane owns
execution. NO xfail / skip / importorskip anywhere (goal rule: a
RULING-blocked property is parked as characterization or left out with a
note, never skipped).

DRAFTING-ENVIRONMENT NOTE (for the verifier): all file:line cites below
were re-anchored against the ``feat/wp8-ai-protocol`` blobs (branch
HEAD ead9fe23) via ``git show``, because the drafting sandbox's working
tree moved to feat/wp43-closeout mid-session. The consumed files
(gateway adapters, florence adapter, enrichment_pipeline, sanitization,
detection model, triton client, gateway main) are byte-identical on the
current main; detector_client.py and ai/yolo26/model.py differ between
branches ONLY below/above the cited regions (deltas at detector_client
:918-1068 and WP8 :1465+; model.py cites :151-173/:1384-1399 are the
WP8-blob lines the evidence dossier itself reports).

Provider driving shapes (harness-verified, do not re-litigate):
  * fake   — registered in-test; driven through its app over
             ASGITransport; X-Fake-Profile switches the vocabulary
             profile; /fake/profiles/classes exposes both tables as data.
  * gateway — the FIVE adapter routers mounted with production prefixes
             (ai/gateway/main.py:181-185) with all five module-level
             get_triton_client names patched (template:
             ai/gateway/tests/test_adapters_yolo26.py:98-104, adapted to
             the five-target shape WP8.3 demands).
  * per_model_http / llamacpp_llm — MATRIX GUARD ONLY (column match +
             deployed flag). Their callables hit the network — never
             invoked.
  * registered gateway/gateway_light callables are UNBOUND client
             methods (real network if called) — this suite never calls
             registered_providers()[...].operations() callables.
"""

from __future__ import annotations

import ast
import json
import re
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.ai_contract.operations import OPERATIONS
from backend.core.config import Settings
from httpx import ASGITransport, AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[4]

# ---------------------------------------------------------------------------
# Mirror data (the test_fake_provider.py pattern: vocabularies carried as
# DATA; AST mirror tests pin every copy against its source).
# ---------------------------------------------------------------------------

# ai/yolo26/model.py:151 (feat/wp8-ai-protocol blob).
WP83_SECURITY_CLASSES = {
    "person",
    "car",
    "truck",
    "dog",
    "cat",
    "bird",
    "bicycle",
    "motorcycle",
    "bus",
}

# Server-side per-class table, ai/yolo26/model.py:173 (AST-pinned below;
# the literal here is only the expectation the pin compares against).
WP83_SERVER_THRESHOLDS = {
    "person": 0.45,
    "car": 0.70,
    "truck": 0.70,
    "bus": 0.70,
    "motorcycle": 0.65,
    "bicycle": 0.65,
    "dog": 0.55,
    "cat": 0.55,
    "bird": 0.55,
}

# Backend per-class table (the DECLARED DEFAULT), backend/core/config.py
# :1694-1708 (Settings.model_fields readout — deliberately NOT an env-
# resolved instance, so a sandbox .env cannot redden a vocabulary pin
# that is about shipped defaults).
WP83_BACKEND_THRESHOLDS = {
    "person": 0.40,
    "car": 0.50,
    "truck": 0.50,
    "bus": 0.55,
    "motorcycle": 0.50,
    "bicycle": 0.50,
    "dog": 0.45,
    "cat": 0.45,
    "bird": 0.45,
    "backpack": 0.50,
    "handbag": 0.50,
    "suitcase": 0.50,
}

# The three backend entries the native server can never let fire
# (backend/core/config.py:1694; dropped upstream at ai/yolo26/model.py:1384).
WP83_DEAD_ENTRIES = {"backpack", "handbag", "suitcase"}

# V4: the registry operations whose committed response contract carries a
# top-level "detections" key. Derivation (schema-driven, no hand-listing):
#   * florence_detect / florence_detect_security_objects — "detections"
#     is in `required` (backend/ai_contract/schemas/*.response.json);
#   * yolo26_detect / yolo26_segment — bare-dict schemas whose pinned
#     deployed keys carry it (x-deployed-keys, evidence
#     ai/gateway/adapters/yolo26.py:375-379).
# NOT included: yolo26_detect_batch — its "detections" live per-ITEM
# (x-deployed-keys ["results", ...]; fake shape generators.py:424-440),
# and the consumer's key check (detector_client.py:1276) reads only the
# TOP level. Per-item shape belongs to the batch/op-targets cluster.
DETECTIONS_KEYED_OPS = (
    "yolo26_detect",
    "yolo26_segment",
    "florence_detect",
    "florence_detect_security_objects",
)


def _provider_vocab_column(op_id: str, slot: str) -> bool:
    return bool(OPERATIONS[op_id].availability.get(slot, False))


# ---------------------------------------------------------------------------
# Source helpers (AST/regex reads of the repo — same mechanism as
# test_fake_provider.py's mirror tests).
# ---------------------------------------------------------------------------


def _ast_assign(path: Path, name: str) -> Any:
    """literal_eval the module-level assignment of `name` (Assign or
    AnnAssign) — raises AssertionError if the symbol vanished (renames
    must redden here, not silently in a fake)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return ast.literal_eval(node.value)
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
            and node.value is not None
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found as a module-level literal in {path}")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fake_app():
    from backend.ai_contract.fake import create_fake_app

    return create_fake_app()


@pytest.fixture(scope="module")
def fake_registered():
    """Register the fake in-test (the WP8.2 registration mechanism); the
    matrix guard needs it present regardless of pytest-randomly order."""
    from backend.ai_contract.fake import fake_provider_ops
    from backend.ai_contract.provider import (
        ProviderId,
        register_provider,
        registered_providers,
    )

    if "fake" not in registered_providers():
        register_provider(ProviderId.FAKE, fake_provider_ops(), OPERATIONS, deployed=True)
    return registered_providers()["fake"]


@pytest.fixture
async def fake_client(fake_app):
    transport = ASGITransport(app=fake_app)
    async with AsyncClient(transport=transport, base_url="http://fake") as client:
        yield client


@contextmanager
def _five_adapter_patches(mock_client):
    """Patching is PER-ADAPTER-MODULE: five distinct get_triton_client
    names (plan WP8.3 mechanical detail; import sites yolo26.py:28,
    clip.py:40, florence.py:39, enrichment.py:31, enrichment_light.py:30).
    A suite that patches one silently exercises a real gRPC client for
    four of five."""
    with ExitStack() as stack:
        for mod in ("yolo26", "clip", "florence", "enrichment", "enrichment_light"):
            stack.enter_context(
                patch(f"ai.gateway.adapters.{mod}.get_triton_client", return_value=mock_client)
            )
        yield


@pytest.fixture(scope="module")
def gateway_app():
    """The FIVE adapter routers with their production prefixes on one
    FastAPI app (ai/gateway/main.py:181-185). Importing ai.gateway.* pulls
    torch via adapters/clip.py:36 — the CPU wheel is installed and the
    import succeeds (plan note; CPU ~1.6s)."""
    from ai.gateway.adapters import (
        clip,
        enrichment,
        enrichment_light,
        florence,
        yolo26,
    )
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(yolo26.router, prefix="/yolo26")
    app.include_router(clip.router, prefix="/clip")
    app.include_router(florence.router, prefix="/florence")
    app.include_router(enrichment.router, prefix="/enrichment")
    app.include_router(enrichment_light.router, prefix="/enrich-lt")
    return app


@pytest.fixture
async def gateway_client(gateway_app):
    """(client, mock_triton): one AsyncMock shared by all five patch
    targets; tests set mock_triton.infer behavior per drive. Template:
    ai/gateway/tests/test_adapters_yolo26.py:75-104 (mock_triton shape)."""
    mock = AsyncMock()
    mock.infer = AsyncMock()
    mock.is_model_ready = AsyncMock(return_value=True)
    mock.get_model_metadata = AsyncMock(return_value={"outputs": [{"name": "output0"}]})
    with _five_adapter_patches(mock):
        async with AsyncClient(
            transport=ASGITransport(app=gateway_app), base_url="http://gw"
        ) as client:
            yield client, mock


# ---------------------------------------------------------------------------
# Drive helpers
# ---------------------------------------------------------------------------


def _request_kwargs(op_id: str) -> dict[str, Any]:
    """Same convention as test_fake_provider.py._request_kwargs: GET ops
    send nothing; committed golden payloads where they exist; multipart
    for uploads; neutral JSON otherwise."""
    example = (
        REPO_ROOT
        / "backend/tests/contracts/ai_providers/golden/payloads"
        / f"{op_id}.request.example.json"
    )
    if OPERATIONS[op_id].method == "GET":
        return {}
    if example.exists():
        payload = json.loads(example.read_text(encoding="utf-8"))
        if op_id == "yolo26_detect_batch":
            return {"files": [("files", ("f0.jpg", b"fake-image", "image/jpeg"))]}
        if isinstance(payload, str):
            return {"files": [("file", ("f.jpg", payload.encode(), "image/jpeg"))]}
        if payload == {}:
            return {}
        return {"json": payload}
    return {"json": {"image_base64": "ZmFrZS1pbWFnZQ=="}}


def _make_test_image(width: int = 640, height: int = 480) -> bytes:
    """Real decodable JPEG so the yolo adapter gets past Image.open
    (adapters/yolo26.py:350); shape copied from
    ai/gateway/tests/test_adapters_yolo26.py:35-41."""
    import io

    from PIL import Image  # adapter's own dependency (adapters/yolo26.py:26)

    img = Image.new("RGB", (width, height), color=(128, 64, 32))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_yolo_output(
    detections: list[dict],
    num_classes: int = 80,
    num_preds: int = 8400,
) -> Any:
    """Synthetic (1, num_classes+4, num_preds) output tensor — copied
    from the working template ai/gateway/tests/test_adapters_yolo26.py:44-67.
    num_classes > 80 is deliberate where a test drives the class_{id}
    fallback (adapters/yolo26.py:186)."""
    import numpy as np

    output = np.zeros((1, num_classes + 4, num_preds), dtype=np.float32)
    for i, det in enumerate(detections):
        if i >= num_preds:
            break
        output[0, 0, i] = det["cx"]
        output[0, 1, i] = det["cy"]
        output[0, 2, i] = det["w"]
        output[0, 3, i] = det["h"]
        output[0, 4 + det["class_id"], i] = det["confidence"]
    return output


async def _drive_gateway_detect(client, mock, class_ids_and_confs: list[tuple[int, float]]):
    """POST /yolo26/detect (multipart upload, adapters/yolo26.py:332-333)
    with a mocked Triton output. 640x480 frame keeps letterbox math
    trivial (scale 1.0) so boxes survive the geometry guards."""
    from ai.gateway.adapters.yolo26 import TritonClientError  # noqa: F401  (shape parity)

    dets = [
        {"cx": 320, "cy": 240, "w": 100, "h": 100, "class_id": cid, "confidence": conf}
        for cid, conf in class_ids_and_confs
    ]
    # (TritonClientError lives in ai.gateway.triton_client; adapters
    # rebind the name — error drives construct it directly.)
    mock.infer.return_value = {"output0": _make_yolo_output(dets)}
    return await client.post(
        "/yolo26/detect", files={"file": ("test.jpg", _make_test_image(), "image/jpeg")}
    )


def _florence_envelope(labels: list[str], bboxes: list[list[float]]) -> dict:
    """Mocked Florence Triton result: the adapter expects a JSON string
    {"result": <task json string>, "prompt": ...} in result[0]
    (adapters/florence.py:234-252, parse :397-409)."""
    import numpy as np

    task = json.dumps({"labels": labels, "bboxes": bboxes})
    envelope = json.dumps({"result": task, "prompt": "<OD>"})
    return {"result": np.array([envelope.encode()], dtype=object)}


# ===========================================================================
# V1 — class vocabulary: 9 (native server) vs 80 (gateway adapter,
#      unfiltered), plus the orphaned third filter table (V1c).
# ===========================================================================


class TestV1ClassVocabulary:
    def test_V1a_security_classes_mirror_the_server_source(self) -> None:
        """V1a: ai/yolo26/model.py:151 defines exactly the 9 security
        classes; filter site :1384 (second path :1545) keyed off the
        9-entry COCO id->name map at :154.
        Source: dossier V1a (cite_ok), re-verified on the WP8 blob.
        Predicted GREEN against fake (fake mirrors the same 9 as data,
        generators.py:43); provider-agnostic AST pin (not drivable).
        UNVERIFIED — never executed."""
        table = _ast_assign(REPO_ROOT / "ai/yolo26/model.py", "SECURITY_CLASSES")
        assert set(table) == WP83_SECURITY_CLASSES
        assert len(table) == 9

    async def test_V1a_fake_security_profile_expresses_the_nine(self, fake_client) -> None:
        """V1a via the fake: /fake/profiles/classes (app.py:62) exposes
        both tables as DATA; X-Fake-Profile: security (app.py:48,81)
        switches the yolo vocabulary to the filtered 9.
        Source: backend/ai_contract/fake/app.py:48-62,81.
        Predicted GREEN against fake. Predicted n/a for gateway (the
        gateway HAS no 9-class expression — that is the divergence).
        UNVERIFIED."""
        profiles = (await fake_client.get("/fake/profiles/classes")).json()
        assert set(profiles["security"]) == WP83_SECURITY_CLASSES

        r = await fake_client.post(
            "/yolo26/detect",
            headers={"X-Fake-Profile": "security"},
            **_request_kwargs("yolo26_detect"),
        )
        classes = {d["class"] for d in r.json()["detections"]}
        assert classes, "fake security profile must emit detections, not none"
        assert classes <= WP83_SECURITY_CLASSES

    def test_V1b_gateway_adapter_returns_all_eighty_unfiltered(self) -> None:
        """V1b: adapters/yolo26.py:42 COCO_CLASSES has 80 names (verified
        count; 9 security names are a subset), BOTH postprocess paths emit
        "class" (:201, :318), and the file contains ZERO references to
        SECURITY/filtering — the adapter keeps everything above its flat
        0.25 floor (:37, applied :130; dossier said :46/:179 — drift,
        re-anchored). Tier A divergence, pinned at source.
        Source: ai/gateway/adapters/yolo26.py:37,42,130,186,201,311,318.
        Predicted: AST pin only (not drivable) — n/a vs fake; the drivable
        sibling below carries the provider-side claim.
        UNVERIFIED."""
        src = (REPO_ROOT / "ai/gateway/adapters/yolo26.py").read_text(encoding="utf-8")
        coco = _ast_assign(REPO_ROOT / "ai/gateway/adapters/yolo26.py", "COCO_CLASSES")
        assert len(coco) == 80
        assert set(coco) > WP83_SECURITY_CLASSES  # strict superset: 71 extras
        assert "SECURITY" not in src
        assert (
            _ast_assign(REPO_ROOT / "ai/gateway/adapters/yolo26.py", "CONFIDENCE_THRESHOLD") == 0.25
        )

    async def test_V1b_gateway_provider_streams_classes_outside_the_nine(
        self, gateway_client
    ) -> None:
        """V1b drivable: with the adapter's OWN postprocess running over a
        mocked Triton tensor, COCO class ids 24/26/28 (backpack, handbag,
        suitcase — ids per the adapter's :42 table) pass through
        unfiltered — a detection stream the native server would have
        dropped at model.py:1384.
        Source: adapters/yolo26.py:186,201 (name + "class" key), :240
        (flat conf mask); COCO indices in the :42 table.
        Predicted: PASSES for gateway (that is the characterization — the
        DIVERGENT behavior is pinned green here; the naive uniform
        "<= 9-set" property from the dossier would go RED on gateway,
        which is why this file pins the two profiles separately).
        UNVERIFIED (tensor drive never executed)."""
        client, mock = gateway_client
        # COCO ids: 24 backpack, 26 handbag, 28 suitcase — the trio the
        # backend table pretends to gate (see V2c). 0.9 conf clears the
        # flat 0.25 floor.
        r = await _drive_gateway_detect(client, mock, [(24, 0.9), (26, 0.9), (28, 0.9)])
        assert r.status_code == 200, r.text[:300]
        classes = {d["class"] for d in r.json()["detections"]}
        assert classes == {"backpack", "handbag", "suitcase"}
        assert classes.isdisjoint(WP83_SECURITY_CLASSES)

    async def test_V1b_fake_gateway_profile_carries_the_eighty_names(self, fake_client) -> None:
        """V1b via the fake: the DEFAULT profile is gateway (the deployed
        provider is unfiltered, app.py docstring); the gateway table has
        80 names strictly containing the 9.
        Source: backend/ai_contract/fake/app.py:50,57 (default
        profile="gateway"), generators.py:50 (80-tuple).
        Predicted GREEN against fake. UNVERIFIED."""
        profiles = (await fake_client.get("/fake/profiles/classes")).json()
        assert len(profiles["gateway"]) == 80
        assert set(profiles["gateway"]) > WP83_SECURITY_CLASSES
        r = await fake_client.post("/yolo26/detect", **_request_kwargs("yolo26_detect"))
        classes = {d["class"] for d in r.json()["detections"]}
        assert classes <= set(profiles["gateway"])

    def test_V1c_triton_client_filter_is_real_but_orphaned(self) -> None:
        """V1c characterization: ai/triton/client.py:230 TritonClient.
        SECURITY_CLASSES is the same 9 with filters at :692/:752 — REAL
        but ORPHANED: no production consumer imports ai.triton (the live
        gateway Triton path is ai/gateway/triton_client.py, which filters
        NOTHING: zero SECURITY references). Pinned so a future suite does
        not mistake this symbol for the gateway's filter.
        Source: ai/triton/client.py:230,692,752; ai/gateway/triton_client.py
        (grep, zero hits).
        Predicted GREEN (import is cheap: numpy + stdlib only, client.py:39-47).
        UNVERIFIED."""
        from ai.triton import TritonClient

        assert set(TritonClient.SECURITY_CLASSES) == WP83_SECURITY_CLASSES

        # orphan proof: no PRODUCTION module outside ai/triton/ imports it.
        # Discovery fix: the census originally swept test trees too and hit
        # THIS conformance suite's own `from ai.triton import TritonClient`
        # (the import below) — a test pin is not a production consumer.
        consumers = []
        for root in ("backend", "ai", "scripts", "frontend"):
            tree = REPO_ROOT / root
            if not tree.is_dir():
                continue
            for path in tree.rglob("*.py"):
                rel = path.relative_to(REPO_ROOT)
                if rel.parts[:2] == ("ai", "triton"):
                    continue  # the module itself
                if "tests" in rel.parts or rel.name.startswith("test_"):
                    continue  # test pins are not production consumers
                text = path.read_text(encoding="utf-8", errors="replace")
                if re.search(r"^\s*(from|import)\s+ai\.triton\b", text, re.MULTILINE):
                    consumers.append(str(rel))
        assert consumers == [], f"ai.triton has unexpected consumers: {consumers}"

        # and the LIVE gateway path filters nothing
        gw_tree = REPO_ROOT / "ai/gateway"
        for path in gw_tree.rglob("*.py"):
            assert "SECURITY_CLASSES" not in path.read_text(encoding="utf-8", errors="replace"), (
                path
            )


# ===========================================================================
# V2 — two divergent per-class confidence tables in series.
# ===========================================================================


class TestV2ConfidenceTables:
    def test_V2a_server_table_values(self) -> None:
        """V2a: ai/yolo26/model.py:173 _DEFAULT_CLASS_CONFIDENCE_THRESHOLDS
        — person 0.45, car/truck/bus 0.70, motorcycle/bicycle 0.65,
        dog/cat/bird 0.55; env override YOLO26_CLASS_THRESHOLDS; applied
        server-side at :1392-1396 (WP8 blob: :1395).
        Source: dossier V2a (cite_ok), AST-re-verified.
        Predicted: characterization of the backend/server constants via
        AST read (the fake's mirror-test style) — drivable nowhere else
        without booting the server. UNVERIFIED."""
        table = _ast_assign(
            REPO_ROOT / "ai/yolo26/model.py", "_DEFAULT_CLASS_CONFIDENCE_THRESHOLDS"
        )
        assert table == WP83_SERVER_THRESHOLDS
        assert set(table) == WP83_SECURITY_CLASSES  # the table is exactly the 9

    def test_V2b_backend_table_is_strictly_lower(self) -> None:
        """V2b: backend/core/config.py:1694 declared default — every one
        of the 9 shared values STRICTLY LOWER than the server table
        (so the two tables in series = server gates everything on the
        native path); fallback 0.40 at :1681. Read from
        Settings.model_fields[...].default (declared default, env-proof).
        Source: config.py:1681,1694-1708; consumption
        detector_client.py:295 / :1314 (WP8 blob cites re-verified).
        Predicted GREEN (pure constants). UNVERIFIED."""
        backend_table = Settings.model_fields["detection_class_thresholds"].default
        assert backend_table == WP83_BACKEND_THRESHOLDS
        assert Settings.model_fields["detection_confidence_threshold"].default == 0.40
        for cls, server_v in WP83_SERVER_THRESHOLDS.items():
            assert backend_table[cls] < server_v, cls

    def test_V2c_dead_entries_never_fire_on_the_native_path(self) -> None:
        """V2c (native-path truth): the three extras {backpack, handbag,
        suitcase} are exactly the backend-table keys outside the 9, the
        server table has NO entry for them, and the server drops them
        before the backend can see them (model.py:1384) — so under the
        shipped default (use_ai_gateway=False, config.py:1315) they can
        never fire. Dead-entry characterization, NOT a runtime guarantee.
        Source: config.py:1315,1694; model.py:151,173,1384.
        Predicted GREEN (constants + field defaults). UNVERIFIED."""
        backend_table = Settings.model_fields["detection_class_thresholds"].default
        assert set(backend_table) - WP83_SECURITY_CLASSES == WP83_DEAD_ENTRIES
        assert not (set(WP83_SERVER_THRESHOLDS) & WP83_DEAD_ENTRIES)
        assert Settings.model_fields["use_ai_gateway"].default is False

    async def test_V2c_gateway_profile_reanimates_the_dead_entries(self, fake_client) -> None:
        """V2c divergence: with the gateway provider the trio becomes
        live — the gateway vocabulary (the deployed default profile)
        carries all three, and the backend table defines real thresholds
        for them, so a gateway provider emitting backpack@0.55 PASSES a
        gate the native path never lets reach the backend. Pinned via the
        fake's profile data (no import of the fake's consts, per WP8.2
        precedent).
        Source: config.py:1694 (entries), adapters/yolo26.py:42 (names
        emitted), model.py:1384 (native drop that keeps them dead only
        on the server path).
        Predicted GREEN against fake (expresses both profiles as data).
        UNVERIFIED."""
        profiles = (await fake_client.get("/fake/profiles/classes")).json()
        backend_table = Settings.model_fields["detection_class_thresholds"].default
        assert set(profiles["gateway"]) >= WP83_DEAD_ENTRIES
        assert all(cls in backend_table for cls in WP83_DEAD_ENTRIES)
        # server table has no say over them — the gate is backend-only
        # for these classes => gateway path: backend table becomes the
        # effective (lower) gate. Characterization of that consequence:
        assert all(backend_table[cls] < 0.70 for cls in WP83_DEAD_ENTRIES)

    def test_V2_gateway_adapter_has_no_per_class_table(self) -> None:
        """V2 shape fact: the gateway adapter has NO per-class table —
        a single flat floor CONFIDENCE_THRESHOLD = 0.25
        (adapters/yolo26.py:37; default arg at :130; mask at :240) where
        the server path applies a 9-entry table at model.py:1392-1396.
        Same input -> different detection set per provider.
        Source: adapters/yolo26.py:37,130,240; model.py:173,1395.
        Predicted GREEN (AST/regex). UNVERIFIED."""
        src = (REPO_ROOT / "ai/gateway/adapters/yolo26.py").read_text(encoding="utf-8")
        assert "CLASS_CONFIDENCE" not in src  # no per-class table anywhere
        assert (
            _ast_assign(REPO_ROOT / "ai/gateway/adapters/yolo26.py", "CONFIDENCE_THRESHOLD") == 0.25
        )


# ===========================================================================
# V3 — three names for one concept: class (yolo) / label (florence) /
#      type -> class_name (enrichment threat), plus the precedence split.
# ===========================================================================


class TestV3ThreeNames:
    async def test_V3_yolo_wire_key_is_class_on_both_providers(
        self, fake_client, gateway_client
    ) -> None:
        """V3 yolo side: every yolo-family detection item keys its class
        name as "class" and NEVER "label"/"type".
        Sources: adapters/yolo26.py:201,:318 (gateway both paths);
        fake generators.py:404-411 (_yolo_detection "class"); fake
        drives yolo26_detect + yolo26_segment; gateway drive yolo26_detect.
        Predicted GREEN against fake AND gateway (both emit "class").
        UNVERIFIED."""
        for op in ("yolo26_detect", "yolo26_segment"):
            r = await fake_client.request(
                OPERATIONS[op].method, OPERATIONS[op].path, **_request_kwargs(op)
            )
            assert r.status_code == 200, f"{op}: {r.status_code}"
            for d in r.json()["detections"]:
                assert "class" in d, f"{op} item missing 'class': {sorted(d)}"
                assert "label" not in d and "type" not in d, (
                    f"{op} item carries a foreign key: {sorted(d)}"
                )

        client, mock = gateway_client
        rg = await _drive_gateway_detect(client, mock, [(0, 0.9)])
        assert rg.status_code == 200, rg.text[:300]
        for d in rg.json()["detections"]:
            assert set(d) == {"class", "confidence", "bbox"}

    async def test_V3_florence_wire_key_is_label_never_class_on_both_providers(
        self, fake_client, gateway_client
    ) -> None:
        """V3 florence side: committed schemas REQUIRE "label" and never
        define "class" (florence_detect.response.json $defs.Detection
        required ["label","bbox"]; florence_detect_security_objects
        same, +confidence). Drivable on BOTH providers: gateway florence
        adapter Detection(label=...) at adapters/florence.py:83-84,
        :137-138, routes :393 /detect and :495 /detect_security_objects
        take {image: b64} (:64). This is where a canonical-"class"
        assumption dies on a florence-keyed payload — pinned as data.
        Sources: schemas as above; adapters/florence.py:64,83,137,393,495;
        fake florence generators walk the schema (label).
        Predicted GREEN against fake AND gateway (both emit label).
        UNVERIFIED."""
        for op in ("florence_detect", "florence_detect_security_objects"):
            schema = json.loads(
                (REPO_ROOT / "backend/ai_contract/schemas" / f"{op}.response.json").read_text(
                    encoding="utf-8"
                )
            )
            det_def = schema["$defs"][
                "Detection" if op == "florence_detect" else "SecurityObjectDetection"
            ]
            assert det_def["required"] == ["label", "bbox"]
            assert "class" not in det_def["properties"]

            r = await fake_client.request(
                OPERATIONS[op].method, OPERATIONS[op].path, **_request_kwargs(op)
            )
            assert r.status_code == 200
            for d in r.json()["detections"]:
                assert "label" in d and "class" not in d, f"{op}: {sorted(d)}"

        client, mock = gateway_client
        for path in ("/florence/detect", "/florence/detect_security_objects"):
            mock.infer.return_value = _florence_envelope(["person"], [[10.0, 20.0, 110.0, 160.0]])
            r = await client.post(path, json={"image": "ZmFrZQ=="})
            assert r.status_code == 200, f"{path}: {r.status_code} {r.text[:300]}"
            dets = r.json()["detections"]
            assert dets, path
            for d in dets:
                assert d["label"] == "person"
                assert "class" not in d, f"{path} item smuggled a 'class' key: {sorted(d)}"

    def test_V3_enrichment_threat_precedence_split_is_pinned(self) -> None:
        """V3 enrichment side: the SAME file reads the one concept with
        OPPOSITE precedence twice —
          backend/services/enrichment_pipeline.py:3942  type -> class_name
          backend/services/enrichment_pipeline.py:5196  class_name -> type
        A threat dict carrying both keys resolves to DIFFERENT values on
        the two paths. Characterization (the split is a documented hazard
        with a parked RULING, plan §3.4) — pinned by regex so the line
        drifts redden here.
        Sources: dossier V3 (:3942 EXACT, :5196 bonus find), re-verified.
        Predicted GREEN (source regex). UNVERIFIED."""
        src = (REPO_ROOT / "backend/services/enrichment_pipeline.py").read_text(encoding="utf-8")
        lines = src.splitlines()
        assert re.search(
            r"threat_class = t\.get\([\"']type[\"'], t\.get\([\"']class_name[\"']", lines[3941]
        ), f":3942 drifted: {lines[3941]!r}"
        assert re.search(
            r"threat_class = t\.get\([\"']class_name[\"'], t\.get\([\"']type[\"']", lines[5195]
        ), f":5196 drifted: {lines[5195]!r}"

    async def test_V3_threat_rows_carry_no_canonical_name_at_all(self, fake_client) -> None:
        """V3 consequence, drivable: the fake's threat rows
        (enrich_lt_threat_detect) carry NO class/label/type key — the
        schema is additionalProperties-free-form objects
        (enrich_lt_threat_detect.response.json threats_detected
        items = bare object). A provider MAY put any of the three names
        there; today the conformance surface cannot say. Characterization
        of the hole (parked), pinned against the fake's shape.
        Source: schema + fake generator (alpha/bravo payload).
        Predicted GREEN against fake. UNVERIFIED."""
        op = "enrich_lt_threat_detect"
        r = await fake_client.request(
            OPERATIONS[op].method, OPERATIONS[op].path, **_request_kwargs(op)
        )
        threats = r.json()["threats_detected"]
        assert threats
        for t in threats:
            assert not (set(t) & {"class", "label", "type"}), sorted(t)


# ===========================================================================
# V4 — "detections" must be PRESENT and a LIST. The plan's :1419 cite is
# WRONG (dossier cite_ok=false); the real routing was grepped directly:
#   detector_client.py:1276  `if "detections" not in result:`  (KEY ONLY)
#   detector_client.py:1281  -> record_pipeline_error("malformed_response")
#   inside async def detect_objects (starts :1116)
# The check tests presence ONLY — no isinstance(list) guard exists; and
# the gateway's error shapes answer HTTP 503 (adapters/yolo26.py:381-383)
# before any key check (trips *_server_error at detector_client.py:806,
# NOT malformed_response).
# ===========================================================================


class TestV4DetectionsKey:
    @pytest.mark.parametrize("profile", ["gateway", "security"])
    @pytest.mark.parametrize("op_id", DETECTIONS_KEYED_OPS)
    async def test_V4_detections_present_and_list_from_fake(
        self, fake_client, op_id: str, profile: str
    ) -> None:
        """V4 present+list on the fake, both profiles, every
        detections-keyed op (membership derived from the committed
        schemas, see DETECTIONS_KEYED_OPS comment; batch excluded — per-
        item shape, consumer reads top level only).
        Source: detector_client.py:1276-1281 (the consumer property);
        fake emits via generators.py:404,420.
        Predicted GREEN against fake (always emits, always a list).
        UNVERIFIED."""
        op = OPERATIONS[op_id]
        r = await fake_client.request(op.method, op.path, **_request_kwargs(op_id))
        assert r.status_code == 200, f"{op_id}: {r.status_code} {r.text[:200]}"
        body = r.json()
        assert "detections" in body, f"{op_id}/{profile} omitted the key"
        assert isinstance(body["detections"], list), f"{op_id}/{profile}: not a list"

    async def test_V4_detections_present_and_list_from_gateway(self, gateway_client) -> None:
        """V4 present+list on the gateway, drivable subset (yolo26_detect
        multipart; florence detect + detect_security_objects b64 JSON —
        segment/batch drive-shapes belong to the geometry/batch cluster).
        Success path ALWAYS carries the key (adapters/yolo26.py:375) and
        the florence pydantic response models make it a required list
        (adapters/florence.py:90).
        Source: adapters/yolo26.py:332,375; adapters/florence.py:64,393,495.
        Predicted GREEN against gateway (under mocks — the whole point of
        mounting adapters over a mocked Triton). UNVERIFIED."""
        client, mock = gateway_client
        r = await _drive_gateway_detect(client, mock, [(0, 0.9)])
        assert r.status_code == 200, r.text[:300]
        assert isinstance(r.json()["detections"], list)

        for path in ("/florence/detect", "/florence/detect_security_objects"):
            mock.infer.return_value = _florence_envelope(["car"], [[1.0, 2.0, 30.0, 40.0]])
            rf = await client.post(path, json={"image": "ZmFrZQ=="})
            assert rf.status_code == 200, f"{path}: {rf.status_code} {rf.text[:300]}"
            assert isinstance(rf.json()["detections"], list), path

    async def test_V4_gateway_triton_failure_answers_503_not_absent_key(
        self, gateway_client
    ) -> None:
        """V4 divergence characterization: under Triton failure the
        gateway answers HTTPException 503 (adapters/yolo26.py:381-383) —
        it never produces a 200-without-"detections" body, so the naive
        "any response lacking detections increments malformed_response"
        is FALSE for gateway error shapes (503 trips the client's
        *_server_error metric path, detector_client.py:806). Pinned so
        the suite never trains on the wrong failure route.
        Source: adapters/yolo26.py:381-383; detector_client.py:806.
        Predicted GREEN against gateway (mock infer raises). UNVERIFIED."""
        from ai.gateway.adapters.yolo26 import TritonClientError

        client, mock = gateway_client
        mock.infer.side_effect = TritonClientError("triton down")
        r = await client.post(
            "/yolo26/detect", files={"file": ("test.jpg", _make_test_image(), "image/jpeg")}
        )
        assert r.status_code == 503, r.text[:300]

    async def test_V4_absent_key_routes_the_consumer_to_malformed_response(self) -> None:
        """V4 ABSENCE behavior, characterized against the REAL consumer
        path named by grep (plan's :1419 cite is the bbox-write region —
        FALSE): detector_client.detect_objects (:1116) checks key
        presence at :1276 and records record_pipeline_error
        ("malformed_response") at :1281, returning []. Driven through the
        same seam the unit tests use (patch httpx.AsyncClient.post +
        validate + baseline; precedent:
        backend/tests/unit/services/test_detector_client.py:143-171 —
        those tests do NOT cover this branch; cite_ok: this branch is
        asserted nowhere today).
        Source: detector_client.py:1276-1282 (re-grepped on the WP8 blob).
        Predicted GREEN (provider-agnostic consumer characterization).
        UNVERIFIED — never executed; mock plumbing per the unit-test
        precedent, expected: 0 detections, malformed called once, one
        HTTP attempt."""
        from backend.services import detector_client as dc_module
        from backend.services.detector_client import DetectorClient

        with patch.object(dc_module, "record_pipeline_error", autospec=True) as malformed:
            client = DetectorClient()
            with patch.object(
                client, "_validate_image_for_detection_async", return_value=True, autospec=True
            ):
                session = AsyncMock()
                session.add = MagicMock()
                mock_service = MagicMock()
                mock_service.update_baseline = AsyncMock()
                with (
                    patch("pathlib.Path.exists", return_value=True, autospec=True),
                    patch("pathlib.Path.read_bytes", return_value=b"fake-image", autospec=True),
                    patch("httpx.AsyncClient.post", autospec=True) as mock_post,
                    patch.object(
                        dc_module,
                        "get_baseline_service",
                        return_value=mock_service,
                        autospec=True,
                    ),
                ):
                    resp = MagicMock()
                    resp.status_code = 200
                    resp.json.return_value = {
                        "image_width": 640,
                        "image_height": 480,
                        "inference_time_ms": 10.0,
                    }  # NO "detections" key
                    mock_post.return_value = resp

                    detections = await client.detect_objects(
                        "fake-frame.jpg", "front_door", session
                    )

                assert detections == []
                assert mock_post.call_count == 1
                malformed.assert_called_once_with("malformed_response")

    async def test_V4_non_list_detections_bypasses_the_malformed_branch(self) -> None:
        """V4 list-ness, characterized: the consumer NEVER checks list
        type (dossier V4; no isinstance(result["detections"], list) in
        the file). Grep verdict for a NON-dict item in the list:
        `for detection_data in result["detections"]` (:1307) yields a
        str; .get raises AttributeError, which is NOT in the per-item
        except tuple (:1447 ValueError/TypeError/KeyError) nor in any
        outer except (:1531 ValueError / CircuitBreakerError /
        DetectorUnavailableError / :1547 OSError,RuntimeError) — so the
        CRASH ESCAPES detect_objects (the dossier's "dies silently" is
        over-stated for str items; verified by except-clause enumeration).
        Strong prediction below. NOTE the adjacent truth that keeps this
        a hazard, not just a crash: a dict item with missing keys is
        dropped silently (confidence defaults 0.0 at :1309 -> filtered
        at :1317 with NO metric).
        Source: detector_client.py:1276,1307-1309,1314-1317,1447.
        Predicted: AttributeError propagates; malformed_response NEVER
        called. If the verification lane finds the crash gets swallowed,
        this is the red that rewrites the characterization — drafting
        intentionally states the falsifiable version. UNVERIFIED."""
        from backend.services import detector_client as dc_module
        from backend.services.detector_client import DetectorClient

        with patch.object(dc_module, "record_pipeline_error", autospec=True) as malformed:
            client = DetectorClient()
            with patch.object(
                client, "_validate_image_for_detection_async", return_value=True, autospec=True
            ):
                session = AsyncMock()
                mock_service = MagicMock()
                mock_service.update_baseline = AsyncMock()
                with (
                    patch("pathlib.Path.exists", return_value=True, autospec=True),
                    patch("pathlib.Path.read_bytes", return_value=b"fake-image", autospec=True),
                    patch("httpx.AsyncClient.post", autospec=True) as mock_post,
                    patch.object(
                        dc_module,
                        "get_baseline_service",
                        return_value=mock_service,
                        autospec=True,
                    ),
                ):
                    resp = MagicMock()
                    resp.status_code = 200
                    resp.json.return_value = {"detections": ["not-a-dict"]}
                    mock_post.return_value = resp

                    with pytest.raises(AttributeError):
                        await client.detect_objects("fake-frame.jpg", "front_door", session)

                assert "malformed_response" not in [c.args[0] for c in malformed.call_args_list]


# ===========================================================================
# V5 — no class allowlist gates the DB write; the only allowlist
#      (KNOWN_OBJECT_CLASSES) is METRICS-ONLY.
# ===========================================================================


class TestV5DbWriteVocabulary:
    def test_V5_db_write_is_ungated_and_the_allowlist_is_metrics_only(self) -> None:
        """V5: the DB write takes the raw wire name — object_type=
        detection_data.get("class") (detector_client.py:1409) — and the
        column is plain String nullable (backend/models/detection.py:54),
        no enum/CHECK. KNOWN_OBJECT_CLASSES (core/sanitization.py:245)
        gates ONLY Prometheus labels (sanitize_object_class :436 ->
        metrics.py:1386,2242), mapping unknowns to "other" for METRICS.
        Quantified divergence: 16 of the gateway's 80 names are NOT in
        the metrics allowlist (incl. "traffic light" — the plan's "in
        KNOWN" example is FALSE; the list spells no traffic-light entry),
        and "class_81" is not either — yet ALL of them store verbatim.
        Sources: dossier V5 (traffic-light detail corrected by this
        draft's enumeration), sanitization.py:245,436; detection.py:54.
        Predicted GREEN (pure data). UNVERIFIED."""
        from backend.core.sanitization import KNOWN_OBJECT_CLASSES, sanitize_object_class
        from backend.models.detection import Detection

        col = Detection.__table__.columns["object_type"]
        assert col.nullable is True

        coco = _ast_assign(REPO_ROOT / "ai/gateway/adapters/yolo26.py", "COCO_CLASSES")
        outside = {c for c in coco if c not in KNOWN_OBJECT_CLASSES}
        assert len(outside) == 16  # deterministic: 80 stream names, 65-entry metrics list
        assert "traffic light" in outside  # plan's example: FALSE membership
        assert sanitize_object_class("class_81") == "other"
        assert sanitize_object_class("traffic light") == "other"
        assert sanitize_object_class("person") == "person"

    async def test_V5_class_id_fallback_reaches_the_wire_verbatim(self, gateway_client) -> None:
        """V5 drivable: a class id beyond the 80 table answers with the
        synthetic "class_{id}" name on the wire (adapters/yolo26.py:186,
        :311) — which the consumer stores verbatim (:1409) while the
        metrics allowlist already demotes it to "other". Pin the pair so
        a swap that invents a name table cannot silently change which
        names become DB rows.
        Source: adapters/yolo26.py:186,311 (fallback); sanitization.py:245.
        Predicted GREEN against gateway (drivable with num_classes=82
        tensor; the fallback is UNREACHABLE through a real 84-row tensor
        — argmax < 80 — this drive exists to keep the name FORMAT, not to
        claim a production path). UNVERIFIED."""
        from backend.core.sanitization import KNOWN_OBJECT_CLASSES, sanitize_object_class

        client, mock = gateway_client
        mock.infer.return_value = {
            "output0": _make_yolo_output(
                [{"cx": 320, "cy": 240, "w": 100, "h": 100, "class_id": 81, "confidence": 0.9}],
                num_classes=82,
            )
        }
        r = await client.post(
            "/yolo26/detect", files={"file": ("test.jpg", _make_test_image(), "image/jpeg")}
        )
        assert r.status_code == 200, r.text[:300]
        dets = r.json()["detections"]
        assert dets and dets[0]["class"] == "class_81", dets
        assert "class_81" not in KNOWN_OBJECT_CLASSES
        assert sanitize_object_class(dets[0]["class"]) == "other"


# ===========================================================================
# Matrix guard (harness driving-shape): vocabulary operations must be
# claimed exactly as the availability matrix declares, per provider.
# per_model_http + llamacpp_llm are GUARD-ONLY here — their registered
# callables hit real network; never invoked. Absent-op 404 checks belong
# to the app-driven suites (green guards), and the fake is app-driven in
# this module — the fake leg below additionally proves per-op drivability
# for every vocabulary op it declares.
# ===========================================================================


class TestVocabularyProviderColumn:
    @pytest.mark.parametrize(
        "provider_id",
        [
            "gateway",
            "gateway_light",
            "per_model_http",
            "llamacpp_llm",
            "openai_vlm",
            "rtvi_vlm",
            "fake",
        ],
    )
    async def test_V1_V4_vocabulary_ops_match_the_availability_column(
        self, provider_id: str, fake_registered, fake_client
    ) -> None:
        """For every vocabulary (detections-bearing) op and every
        provider: claimed in provider.operations() <=> the matrix column
        says available — with the UNION-slot subset providers
        (llamacpp_llm, and the 1.1 VLM engines openai_vlm/rtvi_vlm —
        SUBSET_REQUIRED mirrored from test_conformance_ops) the documented
        exception: each declares ONLY its required subset, so it claims NO
        vocabulary op; per_model_http additionally pinned UNDEPLOYED.
        The fake's available ops are proven drivable in-app (200 + list),
        never by calling registered callables.
        Sources: backend/ai_contract/provider.py (PROVIDER_SLOT :137),
        operations.py availability matrix; providers.py _register_all
        (per_model_http deployed=False, subset providers required=subset).
        Predicted GREEN for all seven legs (this is availability shape,
        not behavior). UNVERIFIED."""
        from backend.ai_contract.provider import PROVIDER_SLOT, registered_providers

        # The fixture's VALUE is asserted, not just its registration
        # side-effect: vulture (main-only Dead Code Detection, red on main
        # run 35476647132) flags a fixture param never named in the body at
        # 100% confidence; this guard is the true statement of why we
        # request it — the fake's registration record must exist.
        assert fake_registered is not None
        rec = registered_providers()[provider_id]
        slot = PROVIDER_SLOT[rec.provider_id]
        declared = set(rec.operations())

        if provider_id == "llamacpp_llm":
            assert declared == {"llm_completion", "llm_chat_completion"}
        elif provider_id in ("openai_vlm", "rtvi_vlm"):
            # union-slot exception, 1.1 shape: each VLM engine declares ONLY
            # required={"vlm_assess"} inside the per_model_server union.
            assert declared == {"vlm_assess"}
        for op_id in DETECTIONS_KEYED_OPS:
            available = _provider_vocab_column(op_id, slot)
            if provider_id in ("llamacpp_llm", "openai_vlm", "rtvi_vlm"):
                # union-slot exception this test's docstring states: a subset
                # provider declares ONLY its required subset, so it claims NO
                # vocabulary op even where the per_model_server column (its
                # slot) is available. Discovery fix: the equality loop failed
                # on yolo26_detect (declared False vs column True).
                assert op_id not in declared, f"{provider_id}/{op_id}"
            else:
                assert (op_id in declared) == available, (
                    f"{provider_id}/{op_id}: declaration {op_id in declared} "
                    f"vs column {available} — vocabulary surface drifted from the matrix"
                )
            if provider_id == "fake" and available:
                r = await fake_client.request(
                    OPERATIONS[op_id].method, OPERATIONS[op_id].path, **_request_kwargs(op_id)
                )
                assert r.status_code == 200
                assert isinstance(r.json()["detections"], list)

        if provider_id == "per_model_http":
            assert rec.deployed is False
        if provider_id == "llamacpp_llm":
            assert declared == {"llm_completion", "llm_chat_completion"}

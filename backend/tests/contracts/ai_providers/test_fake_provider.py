"""WP8.2: the deterministic FakeProvider — reference implementation + fixture source.

A FastAPI app implementing ALL 37 registry operations with fixed, seeded,
byte-deterministic outputs, served over httpx.ASGITransport (never respx:
the fake IS an app, and driving it through ASGITransport exercises the real
request/response path the contract speaks). No weights, no GPU, no network.

The plan's Done-when properties, tested here:

  * two identical requests produce BYTE-IDENTICAL responses (seeded
    generators; no wall-clock, no randomness, no set-iteration anywhere);
  * the fake satisfies the WP8.1 Protocol — register_provider(FAKE, ...)
    accepts it against the fake column (the SPEC: all 37);
  * it emits shipped-correct values: the 9-class SECURITY_CLASSES profile
    AND the unfiltered 80-name gateway profile (the divergence is the point;
    both expressible), dict-of-int bbox for yolo26, list-of-float bbox for
    florence (4 coords; OCR 8-coord quads on the ocr-with-regions path),
    inference_time_ms and NEVER processing_time_ms, L2-normalized 768-dim
    CLIP embeddings, and `class` as the wire key;
  * every response validates against the committed WP7.2 JSON-Schema
    snapshot (schema-driven: the fake cannot drift from the contract without
    reddening this suite).

Runs under pytest-randomly (module-scoped app + fresh ASGITransport client
per test; no test mutates shared state) and inside the global 5s
pytest-timeout (pure Python generators, no I/O).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from backend.ai_contract.operations import OPERATIONS
from backend.ai_contract.provider import (
    ProviderContractError,
    ProviderId,
    operations_for_slot,
    register_provider,
)
from httpx import ASGITransport, AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_DIR = REPO_ROOT / "backend" / "ai_contract" / "schemas"

# The 9 SECURITY_CLASSES the server/triton path filters to
# (ai/yolo26/model.py:151, ai/triton/client.py:230) — mirrored as DATA here
# because the no-ai-at-runtime rule forbids importing ai.* into the contract
# package; test_security_classes_mirror pins the copy against the source.
WP82_SECURITY_CLASSES = {
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

# COCO in gateway order is part of the generated registry's evidence base
# (adapters/yolo26.py:42 builds it as data); the fake must carry the same
# 80 for the unfiltered profile.
WP82_GATEWAY_CLASSES = 80


def _request_kwargs(op_id: str) -> dict[str, Any]:
    """Drive requests from the WP7.2 goldens where a request example
    exists — the payload the contract itself declares valid. Ops without a
    committed request snapshot (multipart upload endpoints) get the golden
    base64 image string the generator emitted for uploads."""
    example = (
        REPO_ROOT
        / "backend/tests/contracts/ai_providers/golden/payloads"
        / f"{op_id}.request.example.json"
    )
    # no body at all for GET-style ops, golden example where committed,
    # upload multipart where the endpoint takes a file, else neutral JSON.
    if OPERATIONS[op_id].method == "GET":
        return {}
    if example.exists():
        payload = json.loads(example.read_text(encoding="utf-8"))
        if op_id == "yolo26_detect_batch":
            return {"files": [("files", ("f0.jpg", b"fake-image", "image/jpeg"))]}
        if isinstance(payload, str):
            # multipart endpoints: the string payload stands for the upload
            return {"files": [("file", ("f.jpg", payload.encode(), "image/jpeg"))]}
        if payload == {}:
            return {}
        return {"json": payload}
    # no request snapshot: neutral minimal JSON body (server-side these are
    # image/bbox requests; the fake ignores content, it is seeded by op id)
    return {"json": {"image_base64": "ZmFrZS1pbWFnZQ=="}}


@pytest.fixture(scope="module")
def fake_app():
    from backend.ai_contract.fake import create_fake_app

    return create_fake_app()


@pytest.fixture
async def fake_client(fake_app):
    transport = ASGITransport(app=fake_app)
    async with AsyncClient(transport=transport, base_url="http://fake") as client:
        yield client


class TestFakeProviderDeterminism:
    async def test_two_identical_requests_are_byte_identical(self, fake_client) -> None:
        """The Done-when, literal: byte-identical, not merely equal-JSON.
        Every one of the 37 ops, so no op hides a set-iteration or a
        time-derived default."""
        for op_id in sorted(OPERATIONS):
            op = OPERATIONS[op_id]
            kw = _request_kwargs(op_id)
            r1 = await fake_client.request(op.method, op.path, **kw)
            r2 = await fake_client.request(op.method, op.path, **kw)
            assert r1.status_code == 200, f"{op_id}: {r1.status_code} {r1.text[:200]}"
            assert r1.content == r2.content, f"{op_id} not byte-identical across calls"
            assert r1.headers.get("content-length") == r2.headers.get("content-length")

    async def test_digest_stable_across_app_rebuild(self, fake_app) -> None:
        """Seeded from the registry, not from process state: a second app
        instance must replay byte-for-byte (pytest-randomly may import the
        fixture in any order; a hash-seeded dict order would leak through)."""
        from backend.ai_contract.fake import create_fake_app

        app2 = create_fake_app()
        async with AsyncClient(transport=ASGITransport(app=app2), base_url="http://fake") as c2:
            for op_id in ("yolo26_detect", "florence_ocr_with_regions", "clip_embed"):
                op = OPERATIONS[op_id]
                kw = _request_kwargs(op_id)
                ra = await fake_client_request(fake_app, op, kw)
                rb = await fake_client_request(app2, op, kw)
                assert ra == rb, f"{op_id} differs across app instances"

    async def test_no_wall_clock_in_any_response(self, fake_client) -> None:
        """inference_time_ms is a SEEDED value, not time.monotonic(): the
        byte-identity property depends on it."""
        for op_id in sorted(OPERATIONS):
            op = OPERATIONS[op_id]
            r = await fake_client.request(op.method, op.path, **_request_kwargs(op_id))
            body = r.json()
            text = json.dumps(body, sort_keys=True)
            assert "processing_time_ms" not in text, f"{op_id} emits processing_time_ms"
            if isinstance(body, dict):
                for key in ("inference_time_ms", "total_inference_time_ms"):
                    if key in body:
                        assert isinstance(body[key], int | float)


async def fake_client_request(app, op, kw) -> bytes:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://fake") as c:
        r = await c.request(op.method, op.path, **kw)
        return r.content


class TestFakeProviderProtocol:
    def test_fake_satisfies_the_wp81_protocol(self) -> None:
        """The other half of the Done-when: the fake IS a provider —
        register_provider(FAKE, ...) against the fake column (all 37, the
        SPEC column) accepts it. Signature conformance is checked by the
        SAME mechanism as every other provider."""
        from backend.ai_contract.fake import fake_provider_ops

        ops = fake_provider_ops()
        assert set(ops) == set(operations_for_slot("fake", OPERATIONS))
        rec = register_provider(ProviderId.FAKE, ops, OPERATIONS, deployed=True)
        assert rec.provider_id is ProviderId.FAKE

    def test_dropping_one_op_fails_naming_it(self) -> None:
        """The fake obeys the same import-time rule as the live providers:
        36 of 37 must fail, naming the hole."""
        from backend.ai_contract.fake import fake_provider_ops

        ops = fake_provider_ops()
        dropped = "florence_dense_caption"
        del ops[dropped]
        with pytest.raises(ProviderContractError) as excinfo:
            register_provider(ProviderId.FAKE, ops, OPERATIONS)
        assert excinfo.value.operation_id == dropped


class TestFakeProviderShippedCorrect:
    """The plan's 'shipped-correct values' list, one test per bullet."""

    async def test_yolo26_dict_bbox_and_class_key(self, fake_client) -> None:
        r = await fake_client.post("/yolo26/detect", **_request_kwargs("yolo26_detect"))
        body = r.json()
        assert set(body) == {"detections", "image_width", "image_height", "inference_time_ms"}
        dets = body["detections"]
        assert dets, "fake must emit detections, not an empty list"
        for d in dets:
            assert set(d) == {"class", "confidence", "bbox"}  # `class` key, WP7.4 shape
            assert isinstance(d["bbox"], dict)
            assert set(d["bbox"]) == {"x", "y", "width", "height"}
            assert all(isinstance(v, int) for v in d["bbox"].values())  # ints, absolute px
            assert 0 <= d["confidence"] <= 1

    async def test_class_vocabulary_both_profiles(self, fake_client) -> None:
        """9 (the filtered native server) AND 80 (the unfiltered gateway
        profile). The divergence is the point; the fake expresses both:
        DEFAULT is gateway because the deployed provider is the unfiltered
        one (WP7.3 Tier A: adapters/yolo26.py does not filter), and the
        X-Fake-Profile: security header switches to the filtered table."""
        r = await fake_client.post("/yolo26/detect", **_request_kwargs("yolo26_detect"))
        gateway_classes = {d["class"] for d in r.json()["detections"]}
        profiles_r = await fake_client.get("/fake/profiles/classes")
        profiles = profiles_r.json()
        assert gateway_classes <= set(profiles["gateway"])

        r_sec = await fake_client.post(
            "/yolo26/detect",
            headers={"X-Fake-Profile": "security"},
            **_request_kwargs("yolo26_detect"),
        )
        sec_classes = {d["class"] for d in r_sec.json()["detections"]}
        assert sec_classes and sec_classes <= WP82_SECURITY_CLASSES

        assert set(profiles["security"]) == WP82_SECURITY_CLASSES
        assert len(profiles["gateway"]) == WP82_GATEWAY_CLASSES
        # a security-class profile is a strict subset of the 80-name table
        assert set(profiles["gateway"]) > WP82_SECURITY_CLASSES

    async def test_florence_list_bbox_and_ocr_quads(self, fake_client) -> None:
        """bbox list-of-floats [x1,y1,x2,y2]; the OCR-with-regions path
        returns EIGHT floats (quad corners, ai/florence/model.py:190,1101).
        A fake emitting 4 there would train consumers on the wrong arity."""
        r = await fake_client.post("/florence/detect", **_request_kwargs("florence_detect"))
        for d in r.json()["detections"]:
            assert isinstance(d["bbox"], list) and len(d["bbox"]) == 4
            assert all(isinstance(v, float) for v in d["bbox"])
        r2 = await fake_client.post(
            "/florence/ocr-with-regions", **_request_kwargs("florence_ocr_with_regions")
        )
        regions = r2.json()["regions"]
        assert regions
        for reg in regions:
            assert isinstance(reg["bbox"], list) and len(reg["bbox"]) == 8

    async def test_clip_embedding_768_dims_l2_normalized(self, fake_client) -> None:
        r = await fake_client.post("/clip/embed", **_request_kwargs("clip_embed"))
        emb = r.json()["embedding"]
        assert len(emb) == 768
        assert math.isclose(math.sqrt(sum(x * x for x in emb)), 1.0, abs_tol=1e-6)

    async def test_inference_time_ms_never_processing_time_ms(self, fake_client) -> None:
        for op_id in sorted(OPERATIONS):
            op = OPERATIONS[op_id]
            r = await fake_client.request(op.method, op.path, **_request_kwargs(op_id))
            assert "processing_time_ms" not in r.text, op_id


class TestFakeProviderSchemaDriven:
    """Schema-driven means schema-VALIDATED: every response re-passes the
    committed WP7.2 snapshot, and the snapshot's presence per op is pinned
    (the fake-side gap WP8.2 closes by adding the 7 missing snapshots from
    deployed-surface models)."""

    @pytest.mark.parametrize("op_id", sorted(OPERATIONS))
    def test_response_snapshot_exists(self, op_id: str) -> None:
        path = SCHEMA_DIR / f"{op_id}.response.json"
        assert path.exists(), (
            f"{op_id} has no committed response snapshot: the fake cannot be "
            "schema-driven for an op with no schema. Add it from the DEPLOYED "
            "surface model (WP7.2 generator), not by hand."
        )

    @pytest.mark.parametrize("op_id", sorted(OPERATIONS))
    async def test_response_validates_against_snapshot(self, fake_client, op_id: str) -> None:
        op = OPERATIONS[op_id]
        snapshot = json.loads((SCHEMA_DIR / f"{op_id}.response.json").read_text(encoding="utf-8"))
        r = await fake_client.request(op.method, op.path, **_request_kwargs(op_id))
        assert r.status_code == 200, f"{op_id}: {r.status_code} {r.text[:200]}"
        try:
            jsonschema.validate(r.json(), snapshot)
        except jsonschema.ValidationError as exc:  # pragma: no cover - failure path
            pytest.fail(
                f"{op_id} response violates its snapshot: {exc.message} at {list(exc.path)}"
            )


class TestFakeProviderVocabularyMirror:
    def test_security_classes_mirror_the_source(self) -> None:
        """The fake copies ai/yolo26 SECURITY_CLASSES as DATA (the
        no-ai-at-runtime rule). AST-read the source table and pin equality —
        a rename upstream reddens HERE, not silently in a fake."""
        import ast

        src = (REPO_ROOT / "ai" / "yolo26" / "model.py").read_text(encoding="utf-8")
        table = None
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "SECURITY_CLASSES" for t in node.targets
            ):
                table = set(ast.literal_eval(node.value))
        assert table == WP82_SECURITY_CLASSES

    def test_gateway_classes_mirror_the_adapter(self) -> None:
        import ast

        src = (REPO_ROOT / "ai" / "gateway" / "adapters" / "yolo26.py").read_text(encoding="utf-8")
        table = None
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id == "COCO_CLASSES" and node.value is not None:
                    table = list(ast.literal_eval(node.value))
        assert table is not None and len(table) == WP82_GATEWAY_CLASSES


def test_wp82_wall_clock_budget() -> None:
    """MEASURE hook: a full fake-backed pass over EVERY registry op must fit
    the 5s per-test timeout (plan constraint). WP4.2: the `ok == 37` count
    assertion became `ok == len(OPERATIONS)` — the pass loop already iterates
    the registry, so the pin added rot risk and no coverage (a skipped op
    still shows as ok < len)."""
    import asyncio
    import time

    from backend.ai_contract.fake import create_fake_app

    async def full_pass() -> int:
        app = create_fake_app()
        ok = 0
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://fake") as c:
            for op_id in sorted(OPERATIONS):
                op = OPERATIONS[op_id]
                r = await c.request(op.method, op.path, **_request_kwargs(op_id))
                if r.status_code == 200:
                    ok += 1
        return ok

    start = time.monotonic()
    ok = asyncio.run(full_pass())
    elapsed = time.monotonic() - start
    print(f"WP8.2 MEASURE: {ok}/{len(OPERATIONS)} ops, full pass {elapsed:.3f}s")
    assert ok == len(OPERATIONS)
    assert elapsed < 5.0, f"full fake pass took {elapsed:.2f}s — violates the 5s budget"
